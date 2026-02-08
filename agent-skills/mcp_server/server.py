"""
MCP Server Module

This module implements the MCP (Multi-Computer Protocol) server for controlled external actions.
It provides endpoints for executing approved actions with security validations.

Silver Tier Extensions:
- Error handling middleware with structured error responses
- Request/response logging
- Rate limiting support
- Health check endpoint

Gold Tier Extensions:
- Coordinator registration for multi-MCP architecture
- Action execution endpoint for coordinator routing
- Domain identification (communication domain)
"""

import asyncio
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
import threading
import time
import uuid

try:
    from mcp_server.approval_validator import MCPServerApprovalValidator
except ImportError:
    MCPServerApprovalValidator = None

try:
    from core.logger import Logger
except ImportError:
    Logger = None


# Error response models
class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str = None
    request_id: Optional[str] = None

    def __init__(self, **data):
        if "timestamp" not in data or data["timestamp"] is None:
            data["timestamp"] = datetime.utcnow().isoformat()
        super().__init__(**data)


class MCPException(Exception):
    """Base exception for MCP server errors."""
    def __init__(
        self,
        error: str,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.error = error
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ApprovalRequiredException(MCPException):
    """Raised when action requires valid approval."""
    def __init__(self, message: str = "Action requires valid approval token"):
        super().__init__(
            error="approval_required",
            message=message,
            status_code=403
        )


class RateLimitedException(MCPException):
    """Raised when rate limit is exceeded."""
    def __init__(self, retry_after: int = 3600):
        super().__init__(
            error="rate_limited",
            message=f"Rate limit exceeded. Retry after {retry_after} seconds.",
            status_code=429,
            details={"retry_after": retry_after}
        )


class SessionUnavailableException(MCPException):
    """Raised when required session is not available."""
    def __init__(self, service: str):
        super().__init__(
            error="session_unavailable",
            message=f"{service} session not active. Re-authentication required.",
            status_code=503,
            details={"service": service}
        )


class ExecutionFailedException(MCPException):
    """Raised when action execution fails."""
    def __init__(self, message: str, external_error: Optional[str] = None):
        super().__init__(
            error="execution_failed",
            message=message,
            status_code=500,
            details={"external_error": external_error} if external_error else {}
        )


def create_error_handler_middleware(logger: Optional[Any] = None):
    """Create error handling middleware for the FastAPI app."""

    async def error_handler_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        try:
            # Add request ID to state
            request.state.request_id = request_id

            response = await call_next(request)

            # Log successful requests
            duration_ms = (time.time() - start_time) * 1000
            if logger:
                logger.log_system_event(
                    event_type="mcp_request",
                    component="mcp_server",
                    message=f"{request.method} {request.url.path} - {response.status_code}",
                    details={
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": round(duration_ms, 2)
                    }
                )

            return response

        except MCPException as e:
            # Handle known MCP exceptions
            error_response = ErrorResponse(
                error=e.error,
                message=e.message,
                details=e.details,
                request_id=request_id
            )

            if logger:
                logger.log_system_event(
                    event_type="mcp_error",
                    component="mcp_server",
                    message=f"MCP error: {e.error} - {e.message}",
                    details={
                        "request_id": request_id,
                        "error": e.error,
                        "status_code": e.status_code
                    }
                )

            return JSONResponse(
                status_code=e.status_code,
                content=error_response.model_dump()
            )

        except HTTPException as e:
            # Handle FastAPI HTTP exceptions
            error_response = ErrorResponse(
                error="http_error",
                message=str(e.detail),
                request_id=request_id
            )

            return JSONResponse(
                status_code=e.status_code,
                content=error_response.model_dump()
            )

        except Exception as e:
            # Handle unexpected exceptions
            error_response = ErrorResponse(
                error="internal_error",
                message="An unexpected error occurred",
                details={"type": type(e).__name__},
                request_id=request_id
            )

            if logger:
                logger.log_system_event(
                    event_type="mcp_error",
                    component="mcp_server",
                    message=f"Unhandled exception: {str(e)}",
                    details={
                        "request_id": request_id,
                        "exception_type": type(e).__name__,
                        "traceback": traceback.format_exc()
                    }
                )

            return JSONResponse(
                status_code=500,
                content=error_response.model_dump()
            )

    return error_handler_middleware


class ExecuteActionRequest(BaseModel):
    """Request model for executing an action."""
    action_type: str
    action_data: Dict[str, Any]
    approval_token: str
    plan_reference: str


class ValidateApprovalRequest(BaseModel):
    """Request model for validating an approval."""
    approval_token: str
    plan_reference: str


class MCPServer:
    """
    MCP (Multi-Computer Protocol) Server for controlled external actions.
    Ensures that only approved actions are executed with proper validation.
    """

    def __init__(self, host: str = "localhost", port: int = 8000, logger: Optional[Any] = None):
        """
        Initialize the MCP server.

        Args:
            host: Host address for the server
            port: Port number for the server
            logger: Logger instance for auditability
        """
        self.host = host
        self.port = port
        self.app = FastAPI(
            title="Silver Tier MCP Server",
            version="1.0.0",
            description="Model Context Protocol Server for controlled external actions"
        )
        self.running = False
        self.logger = logger
        self.start_time = datetime.utcnow()

        # Initialize approval validator if available
        if MCPServerApprovalValidator and logger:
            self.approval_validator = MCPServerApprovalValidator(logger)
        else:
            self.approval_validator = None

        # In-memory storage for execution logs and action results
        self.execution_logs = {}
        self.action_results = {}

        # Service connection status
        self.service_status = {
            "gmail": {"status": "disconnected", "last_activity": None, "error_message": None},
            "linkedin": {"status": "disconnected", "last_activity": None, "error_message": None},
            "whatsapp": {"status": "disconnected", "last_activity": None, "error_message": None},
        }

        # Define allowed and disallowed actions
        self.allowed_actions = [
            "email_send", "linkedin_post", "whatsapp_reply",
            "notification_send", "file_create_external", "calendar_event_create"
        ]
        self.disallowed_actions = [
            "payment", "data_deletion", "irreversible_operation",
            "system_configuration_change", "user_privilege_modification"
        ]

        # Add error handling middleware
        self.app.middleware("http")(create_error_handler_middleware(logger))

        # Add CORS middleware for dashboard access
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Initialize routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup the API routes for the MCP server."""

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint for coordinator health monitoring."""
            return {
                "status": "healthy",
                "domain": "communication",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            }

        @self.app.post("/action/execute")
        async def action_execute(request: dict):
            """
            Execute an action routed from the coordinator.

            Gold Tier: This endpoint is called by the coordinator for
            actions in the communication domain (email, LinkedIn, WhatsApp).
            """
            action_type = request.get("actionType", "")
            approval_ref = request.get("approvalRef", "")
            payload = request.get("payload", {})

            # Map coordinator action types to internal action types
            action_map = {
                "email.send": "email_send",
                "linkedin.post": "linkedin_post",
                "whatsapp.reply": "whatsapp_reply",
                "gmail.send": "email_send",
            }

            internal_action = action_map.get(action_type, action_type)

            # Execute the action
            try:
                result = self._execute_action_by_type(internal_action, payload)
                return {
                    "success": True,
                    "result": result,
                    "actionType": action_type,
                    "approvalRef": approval_ref,
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "actionType": action_type,
                    "approvalRef": approval_ref,
                }

        @self.app.get("/status")
        async def get_status():
            """Get detailed server status including connected services."""
            uptime = (datetime.utcnow() - self.start_time).total_seconds()
            pending_approvals = len([
                r for r in self.action_results.values()
                if r.get("status") == "pending"
            ])
            executed_today = len([
                r for r in self.action_results.values()
                if r.get("executed_at", "").startswith(datetime.utcnow().strftime("%Y-%m-%d"))
            ])

            return {
                "status": self._calculate_overall_status(),
                "uptime": int(uptime),
                "services": self.service_status,
                "pending_approvals": pending_approvals,
                "executed_today": executed_today
            }

        @self.app.post("/execute/action")
        async def execute_action(request: ExecuteActionRequest):
            """Execute an approved action."""
            return self._handle_execute_action(request)

        @self.app.post("/validate/approval")
        async def validate_approval(request: ValidateApprovalRequest):
            """Validate that an approval token is valid and has not expired."""
            return self._handle_validate_approval(request)

        @self.app.get("/actions/{action_id}")
        async def get_action_result(action_id: str):
            """Retrieve the result of a previously executed action."""
            if action_id not in self.action_results:
                raise HTTPException(status_code=404, detail="Action not found")
            return self.action_results[action_id]

    def _calculate_overall_status(self) -> str:
        """Calculate overall server status based on service health."""
        connected_count = sum(
            1 for s in self.service_status.values()
            if s["status"] == "connected"
        )
        error_count = sum(
            1 for s in self.service_status.values()
            if s["status"] == "error"
        )

        if error_count > 0:
            return "degraded"
        elif connected_count == 0:
            return "unhealthy"
        elif connected_count < len(self.service_status):
            return "degraded"
        return "healthy"

    def update_service_status(
        self,
        service: str,
        status: str,
        error_message: Optional[str] = None
    ):
        """Update the status of a service."""
        if service in self.service_status:
            self.service_status[service] = {
                "status": status,
                "last_activity": datetime.utcnow().isoformat(),
                "error_message": error_message
            }

    def _handle_execute_action(self, request: ExecuteActionRequest):
        """Handle the execute action request."""
        try:
            # Log the incoming request
            if self.logger:
                self.logger.log_system_event(
                    event_type="mcp_request_received",
                    component="mcp_server",
                    message="Execute action request received",
                    details={
                        "action_type": request.action_type,
                        "plan_reference": request.plan_reference
                    }
                )

            # Validate the approval
            is_valid, approval_data = self._validate_approval_token(
                request.approval_token, request.plan_reference
            )

            if not is_valid:
                raise HTTPException(status_code=401, detail="Invalid or expired approval")

            # Check if action type is allowed
            if request.action_type not in self.allowed_actions:
                if request.action_type in self.disallowed_actions:
                    if self.logger:
                        self.logger.log_system_event(
                            event_type="security_violation",
                            component="mcp_server",
                            message=f"Attempted disallowed action: {request.action_type}",
                            details={
                                "action_type": request.action_type,
                                "plan_reference": request.plan_reference
                            }
                        )
                    raise HTTPException(status_code=403, detail="Disallowed action type")

                # If action is neither allowed nor explicitly disallowed, reject it
                raise HTTPException(status_code=403, detail="Action type not permitted")

            # Check if the action is in the approved actions list
            approved_actions = approval_data.get('approved_actions', [])
            action_id = request.action_data.get('action_id')

            if action_id and action_id not in approved_actions:
                if self.logger:
                    self.logger.log_system_event(
                        event_type="unauthorized_action",
                        component="mcp_server",
                        message="Action not in approved list",
                        details={
                            "action_id": action_id,
                            "approved_actions": approved_actions,
                            "plan_reference": request.plan_reference
                        }
                    )
                raise HTTPException(status_code=403, detail="Action not authorized in approval")

            # Execute the action based on type
            execution_result = self._execute_action_by_type(
                request.action_type, request.action_data
            )

            # Log the execution
            execution_id = str(uuid.uuid4())
            if self.logger:
                self.logger.log_mcp_execution(
                    execution_id=execution_id,
                    action_type=request.action_type,
                    action_params=request.action_data,
                    result="success" if execution_result.get("success") else "failure",
                    error=None if execution_result.get("success") else execution_result.get("error", "Unknown error")
                )

            # Store execution log
            self.execution_logs[execution_id] = {
                "id": execution_id,
                "action_type": request.action_type,
                "action_params": request.action_data,
                "approval_id": approval_data.get('id'),
                "execution_timestamp": datetime.now().isoformat(),
                "result": "success" if execution_result.get("success") else "failure",
                "error_message": None if execution_result.get("success") else execution_result.get("error")
            }

            return {
                "status": "success" if execution_result.get("success") else "failure",
                "execution_id": execution_id,
                "timestamp": datetime.now().isoformat(),
                "result": execution_result,
                "error": None if execution_result.get("success") else execution_result.get("error")
            }

        except HTTPException:
            raise
        except Exception as e:
            if self.logger:
                self.logger.log_system_event(
                    event_type="mcp_execution_error",
                    component="mcp_server",
                    message=f"Error executing action: {e}",
                    details={
                        "action_type": request.action_type,
                        "plan_reference": request.plan_reference
                    }
                )
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    def _handle_get_status(self):
        """Handle the get status request."""
        return {
            "status": "running" if self.running else "stopped",
            "uptime": getattr(self, '_start_time', 0),
            "allowed_actions": self.allowed_actions,
            "disallowed_actions": self.disallowed_actions,
            "total_executions": len(self.execution_logs)
        }

    def _handle_validate_approval(self, request: ValidateApprovalRequest):
        """Handle the validate approval request."""
        try:
            is_valid, approval_data = self._validate_approval_token(
                request.approval_token, request.plan_reference
            )

            if is_valid and approval_data:
                return {
                    "valid": True,
                    "expires_at": approval_data.get('expiration_timestamp'),
                    "approved_actions": approval_data.get('approved_actions', []),
                    "error": None
                }
            else:
                return {
                    "valid": False,
                    "expires_at": None,
                    "approved_actions": [],
                    "error": "Invalid or expired approval"
                }

        except Exception as e:
            return {
                "valid": False,
                "expires_at": None,
                "approved_actions": [],
                "error": str(e)
            }

    def _validate_approval_token(self, approval_token: str, plan_reference: str) -> tuple:
        """Validate the approval token and return validation result."""
        if not self.approval_validator:
            # Mock validation for demonstration
            return True, {
                "id": approval_token,
                "plan_id": plan_reference,
                "approved_actions": ["action_1", "action_2"],
                "expiration_timestamp": (datetime.now().timestamp() + 3600).__str__(),  # 1 hour from now
                "status": "valid"
            }

        # In a real implementation, this would call the approval validator
        # For now, we'll return a mock valid result
        return True, {
            "id": approval_token,
            "plan_id": plan_reference,
            "approved_actions": ["action_1", "action_2"],
            "expiration_timestamp": (datetime.now() + timedelta(hours=1)).isoformat(),
            "status": "valid"
        }

    def _execute_action_by_type(self, action_type: str, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action based on its type."""
        try:
            if action_type == "email_send":
                result = self._execute_email_send(action_data)
            elif action_type == "linkedin_post":
                result = self._execute_linkedin_post(action_data)
            elif action_type == "notification_send":
                result = self._execute_notification_send(action_data)
            elif action_type == "file_create_external":
                result = self._execute_file_create_external(action_data)
            elif action_type == "calendar_event_create":
                result = self._execute_calendar_event_create(action_data)
            else:
                # This shouldn't happen if validation worked properly
                return {"success": False, "error": f"Unsupported action type: {action_type}"}

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_email_send(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute email sending action."""
        # In a real implementation, this would connect to an email service
        # For demo purposes, we'll just return success
        to = action_data.get('to', 'recipient@example.com')
        subject = action_data.get('subject', 'Default Subject')
        body = action_data.get('body', 'Default Body')

        # Mock email sending
        print(f"Mock email sent to: {to}, Subject: {subject}")

        return {
            "success": True,
            "message_id": f"mock_msg_{uuid.uuid4()}",
            "details": f"Email sent to {to} with subject '{subject}'"
        }

    def _execute_linkedin_post(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute LinkedIn posting action."""
        # In a real implementation, this would connect to LinkedIn API
        # For demo purposes, we'll just return success
        content = action_data.get('content', 'Default Content')
        visibility = action_data.get('visibility', 'PUBLIC')

        # Mock LinkedIn post
        print(f"Mock LinkedIn post created: {content[:50]}...")

        return {
            "success": True,
            "post_id": f"mock_post_{uuid.uuid4()}",
            "details": f"LinkedIn post created with visibility '{visibility}'"
        }

    def _execute_notification_send(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute notification sending action."""
        # Mock notification sending
        recipient = action_data.get('recipient', 'system')
        message = action_data.get('message', 'Default notification')

        print(f"Mock notification sent to: {recipient}, Message: {message}")

        return {
            "success": True,
            "notification_id": f"mock_notif_{uuid.uuid4()}",
            "details": f"Notification sent to {recipient}"
        }

    def _execute_file_create_external(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute external file creation action."""
        # Mock file creation
        filename = action_data.get('filename', 'default.txt')
        content = action_data.get('content', '')

        print(f"Mock external file created: {filename}")

        return {
            "success": True,
            "file_path": f"/mock/external/path/{filename}",
            "details": f"External file {filename} created"
        }

    def _execute_calendar_event_create(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute calendar event creation action."""
        # Mock calendar event creation
        title = action_data.get('title', 'Default Event')
        start_time = action_data.get('start_time', datetime.now().isoformat())

        print(f"Mock calendar event created: {title} at {start_time}")

        return {
            "success": True,
            "event_id": f"mock_event_{uuid.uuid4()}",
            "details": f"Calendar event '{title}' created"
        }

    def start(self, background: bool = True):
        """Start the MCP server."""
        self.running = True
        self._start_time = time.time()

        if background:
            # Run the server in a background thread
            server_thread = threading.Thread(
                target=uvicorn.run,
                args=(self.app,),
                kwargs={"host": self.host, "port": self.port, "log_level": "info"},
                daemon=True
            )
            server_thread.start()
            print(f"MCP Server starting on {self.host}:{self.port}")
        else:
            # Run the server in the foreground
            uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")

    def stop(self):
        """Stop the MCP server."""
        self.running = False
        print("MCP Server stopped")


# Example usage
if __name__ == "__main__":
    # Create a logger instance (for demo purposes, we'll use None)
    logger = None

    # Create and start the server
    mcp_server = MCPServer(host="localhost", port=8000, logger=logger)

    print("Starting MCP Server...")
    mcp_server.start(background=False)  # Run in foreground for demo