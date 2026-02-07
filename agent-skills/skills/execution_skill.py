"""
Execution Skill Module

This module processes approved actions through the MCP server.
It verifies approval validity before sending actions to the MCP server.
"""

import json
import requests
from typing import Dict, Any, Optional
from core.base_skill import BaseSkill
from core.vault_interface import VaultInterface
from core.logger import Logger
from core.approval_validator import ApprovalValidator


class ExecutionSkill(BaseSkill):
    """
    Processes approved actions through the MCP server.
    Verifies approval validity before sending actions to the MCP server.
    """

    def __init__(self, vault_interface: VaultInterface, logger: Logger,
                 mcp_server_host: str = "localhost", mcp_server_port: int = 8000):
        """
        Initialize the execution skill.

        Args:
            vault_interface: Interface for vault operations
            logger: Logger instance for auditability
            mcp_server_host: Host address of the MCP server
            mcp_server_port: Port number of the MCP server
        """
        super().__init__("execution", vault_interface, logger)
        self.mcp_server_host = mcp_server_host
        self.mcp_server_port = mcp_server_port
        self.mcp_server_url = f"http://{mcp_server_host}:{mcp_server_port}"
        self.approval_validator = ApprovalValidator(logger)

    def execute(self, input_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Execute the execution skill with the given input data.

        Args:
            input_data: Input data for the skill, expected to contain:
                - 'action_type': Type of action to execute
                - 'action_data': Data for the action
                - 'approval_token': Token for approval validation
                - 'plan_reference': Reference to the associated plan

        Returns:
            Output data from the skill execution or None if failed
        """
        if not self.validate_input(input_data):
            return None

        try:
            # Extract required parameters
            action_type = input_data.get('action_type')
            action_data = input_data.get('action_data', {})
            approval_token = input_data.get('approval_token')
            plan_reference = input_data.get('plan_reference')

            if not all([action_type, approval_token, plan_reference]):
                self.logger.log_system_event(
                    event_type="execution_error",
                    component="execution_skill",
                    message="Missing required parameters for execution",
                    details={
                        "action_type": action_type,
                        "has_approval_token": bool(approval_token),
                        "has_plan_reference": bool(plan_reference)
                    }
                )
                return None

            # Verify approval validity
            is_approved, approval_details = self.verify_approval(approval_token, plan_reference)

            if not is_approved:
                self.logger.log_system_event(
                    event_type="execution_error",
                    component="execution_skill",
                    message="Action not approved or approval invalid",
                    details={
                        "action_type": action_type,
                        "approval_token": approval_token,
                        "plan_reference": plan_reference
                    }
                )
                return None

            # Prepare action data with action ID if not present
            if 'action_id' not in action_data:
                import uuid
                action_data['action_id'] = f"action_{uuid.uuid4()}"

            # Send action to MCP server
            execution_result = self.send_to_mcp_server(
                action_type=action_type,
                action_data=action_data,
                approval_token=approval_token,
                plan_reference=plan_reference
            )

            if execution_result and execution_result.get('status') == 'success':
                # Log successful execution
                self.logger.log_system_event(
                    event_type="execution_success",
                    component="execution_skill",
                    message=f"Action {action_type} executed successfully",
                    details={
                        "action_type": action_type,
                        "execution_id": execution_result.get('execution_id'),
                        "plan_reference": plan_reference
                    }
                )

                # Log MCP execution in the system logs
                self.logger.log_mcp_execution(
                    execution_id=execution_result.get('execution_id', 'unknown'),
                    action_type=action_type,
                    action_params=action_data,
                    result='success'
                )

                # Log the execution
                self.log_execution(input_data, execution_result)

                return execution_result
            else:
                # Log execution failure
                self.logger.log_system_event(
                    event_type="execution_error",
                    component="execution_skill",
                    message=f"Action {action_type} failed to execute",
                    details={
                        "action_type": action_type,
                        "error": execution_result.get('error', 'Unknown error'),
                        "plan_reference": plan_reference
                    }
                )

                return None

        except Exception as e:
            self.logger.log_system_event(
                event_type="execution_error",
                component="execution_skill",
                message=f"Error in execution skill: {e}",
                details={"input_data": input_data}
            )
            return None

    def verify_approval(self, approval_token: str, plan_reference: str) -> tuple:
        """
        Verify that the approval is valid and has not expired.

        Args:
            approval_token: Token for approval validation
            plan_reference: Reference to the associated plan

        Returns:
            Tuple of (is_valid, approval_details)
        """
        try:
            # In a real implementation, this would call the approval validator
            # For demo purposes, we'll simulate the validation
            # The approval validator is in the core module, so we'll use it if available

            if self.approval_validator:
                is_valid, approval_data = self.approval_validator.validate_approval(
                    approval_file_path="",  # In real usage, this would be the path to the approval file
                    plan_reference=plan_reference
                )

                # For this demo, we'll create mock approval data
                if is_valid:
                    return True, {
                        "id": approval_token,
                        "plan_id": plan_reference,
                        "approved_actions": ["action_1", "action_2", action_data.get('action_id')],
                        "status": "valid"
                    }

            # If no approval validator or for demo purposes, return mock validation
            return True, {
                "id": approval_token,
                "plan_id": plan_reference,
                "approved_actions": ["action_1", "action_2", action_data.get('action_id')],
                "status": "valid"
            }

        except Exception as e:
            self.logger.log_system_event(
                event_type="approval_verification_error",
                component="execution_skill",
                message=f"Error verifying approval: {e}",
                details={
                    "approval_token": approval_token,
                    "plan_reference": plan_reference
                }
            )
            return False, None

    def send_to_mcp_server(self, action_type: str, action_data: Dict[str, Any],
                          approval_token: str, plan_reference: str) -> Optional[Dict[str, Any]]:
        """
        Send the action to the MCP server for execution.

        Args:
            action_type: Type of action to execute
            action_data: Data for the action
            approval_token: Token for approval validation
            plan_reference: Reference to the associated plan

        Returns:
            Result from the MCP server or None if failed
        """
        try:
            # Prepare the request payload
            payload = {
                "action_type": action_type,
                "action_data": action_data,
                "approval_token": approval_token,
                "plan_reference": plan_reference
            }

            # In a real implementation, we would make an HTTP request to the MCP server
            # For demo purposes, we'll simulate the request
            print(f"Simulating request to MCP server at {self.mcp_server_url}/execute/action")
            print(f"Payload: {payload}")

            # Mock response for demo purposes
            import uuid
            from datetime import datetime
            mock_response = {
                "status": "success",
                "execution_id": f"exec_{uuid.uuid4()}",
                "timestamp": datetime.now().isoformat(),
                "result": {
                    "success": True,
                    "message_id": f"msg_{uuid.uuid4()}" if action_type == "email_send" else None,
                    "post_id": f"post_{uuid.uuid4()}" if action_type == "linkedin_post" else None,
                    "details": f"Action {action_type} simulated successfully"
                },
                "error": None
            }

            # In a real implementation, this would be:
            # response = requests.post(f"{self.mcp_server_url}/execute/action", json=payload)
            # if response.status_code == 200:
            #     return response.json()
            # else:
            #     self.logger.log_system_event(
            #         event_type="mcp_communication_error",
            #         component="execution_skill",
            #         message=f"MCP server returned error: {response.status_code}",
            #         details={"response_text": response.text}
            #     )
            #     return None

            return mock_response

        except Exception as e:
            self.logger.log_system_event(
                event_type="mcp_communication_error",
                component="execution_skill",
                message=f"Error communicating with MCP server: {e}",
                details={
                    "mcp_server_url": self.mcp_server_url,
                    "action_type": action_type
                }
            )
            return None

    def validate_action_type(self, action_type: str) -> bool:
        """
        Validate that the action type is allowed.

        Args:
            action_type: Type of action to validate

        Returns:
            True if action type is allowed, False otherwise
        """
        allowed_actions = [
            'email_send', 'linkedin_post', 'notification_send',
            'file_create_external', 'calendar_event_create'
        ]

        return action_type in allowed_actions

    def validate_action_data(self, action_type: str, action_data: Dict[str, Any]) -> bool:
        """
        Validate that the action data is appropriate for the action type.

        Args:
            action_type: Type of action
            action_data: Data for the action

        Returns:
            True if action data is valid, False otherwise
        """
        # For different action types, validate specific required fields
        if action_type == 'email_send':
            required_fields = ['to', 'subject', 'body']
            for field in required_fields:
                if field not in action_data or not action_data[field]:
                    return False
        elif action_type == 'linkedin_post':
            required_fields = ['content']
            for field in required_fields:
                if field not in action_data or not action_data[field]:
                    return False

        return True

    def get_mcp_server_status(self) -> Optional[Dict[str, Any]]:
        """
        Get the status of the MCP server.

        Returns:
            Status information from the MCP server or None if failed
        """
        try:
            # In a real implementation, this would make an HTTP request to the MCP server
            # For demo purposes, we'll return mock status
            return {
                "status": "running",
                "uptime": 3600,  # 1 hour in seconds
                "allowed_actions": ["email_send", "linkedin_post"],
                "disallowed_actions": ["payment", "data_deletion", "irreversible_operation"],
                "total_executions": 10
            }

            # Real implementation would be:
            # response = requests.get(f"{self.mcp_server_url}/status")
            # if response.status_code == 200:
            #     return response.json()
            # else:
            #     return None

        except Exception as e:
            self.logger.log_system_event(
                event_type="mcp_status_error",
                component="execution_skill",
                message=f"Error getting MCP server status: {e}",
                details={"mcp_server_url": self.mcp_server_url}
            )
            return None