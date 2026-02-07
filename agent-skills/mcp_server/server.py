"""
MCP Server Module

This module implements the MCP (Multi-Computer Protocol) server for controlled external actions.
It provides endpoints for executing approved actions with security validations.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uvicorn
import threading
import time
import uuid
from mcp_server.approval_validator import MCPServerApprovalValidator
from core.logger import Logger


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

    def __init__(self, host: str = "localhost", port: int = 8000, logger: Optional[Logger] = None):
        """
        Initialize the MCP server.

        Args:
            host: Host address for the server
            port: Port number for the server
            logger: Logger instance for auditability
        """
        self.host = host
        self.port = port
        self.app = FastAPI(title="MCP Server", version="1.0.0")
        self.running = False
        self.logger = logger
        self.approval_validator = MCPServerApprovalValidator(logger) if logger else None

        # In-memory storage for execution logs (in production, use a proper database)
        self.execution_logs = {}

        # Define allowed and disallowed actions
        self.allowed_actions = [
            "email_send", "linkedin_post", "notification_send",
            "file_create_external", "calendar_event_create"
        ]
        self.disallowed_actions = [
            "payment", "data_deletion", "irreversible_operation",
            "system_configuration_change", "user_privilege_modification"
        ]

        # Initialize routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup the API routes for the MCP server."""
        @self.app.post("/execute/action")
        async def execute_action(request: ExecuteActionRequest):
            """Execute an approved action."""
            return self._handle_execute_action(request)

        @self.app.get("/status")
        async def get_status():
            """Get the current status of the MCP server."""
            return self._handle_get_status()

        @self.app.post("/validate/approval")
        async def validate_approval(request: ValidateApprovalRequest):
            """Validate that an approval token is valid and has not expired."""
            return self._handle_validate_approval(request)

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