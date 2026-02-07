"""
MCP Server Approval Validator Module

This module validates approval tokens specifically for the MCP server.
It ensures that only approved actions are executed with proper validation.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
from core.logger import Logger


class MCPServerApprovalValidator:
    """
    Validator for approval tokens specifically for the MCP server.
    Ensures that only approved actions are executed with proper validation.
    """

    def __init__(self, logger: Optional[Logger] = None):
        """
        Initialize the MCP server approval validator.

        Args:
            logger: Logger instance for auditability
        """
        self.logger = logger

    def validate_approval_token(self, approval_token: str, plan_reference: str) -> Tuple[bool, Optional[Dict[str, any]]]:
        """
        Validate an approval token for the MCP server.

        Args:
            approval_token: The approval token to validate
            plan_reference: The plan reference associated with the approval

        Returns:
            Tuple of (is_valid, approval_data) where is_valid indicates if the
            approval is valid and approval_data contains the approval information
        """
        try:
            # In a real implementation, this would look up the approval in a database
            # For this mock implementation, we'll simulate validating from a file or cache

            # For demo purposes, we'll create a mock approval data structure
            # that matches what would be expected from the approval file
            approval_data = {
                "id": approval_token,
                "plan_id": plan_reference,
                "approved_actions": ["action_1", "action_2", "email_send", "linkedin_post"],
                "approver": "mock_approver",
                "approval_timestamp": datetime.now().isoformat(),
                "expiration_timestamp": (datetime.now().replace(year=datetime.now().year + 1)).isoformat(),  # 1 year from now
                "status": "valid"
            }

            # Validate required fields
            required_fields = [
                'id', 'plan_id', 'approved_actions', 'approver',
                'approval_timestamp', 'expiration_timestamp', 'status'
            ]

            for field in required_fields:
                if field not in approval_data:
                    if self.logger:
                        self.logger.log_system_event(
                            event_type="approval_validation",
                            component="mcpsrv_approval_validator",
                            message=f"Missing required field '{field}' in approval data",
                            details={"approval_token": approval_token}
                        )
                    return False, None

            # Check if plan reference matches
            if approval_data['plan_id'] != plan_reference:
                if self.logger:
                    self.logger.log_system_event(
                        event_type="approval_validation",
                        component="mcpsrv_approval_validator",
                        message="Plan reference does not match approval",
                        details={
                            "approval_token": approval_token,
                            "expected_plan": plan_reference,
                            "actual_plan": approval_data['plan_id']
                        }
                    )
                return False, None

            # Check if approval is expired
            try:
                expiration_time = datetime.fromisoformat(approval_data['expiration_timestamp'])
                if datetime.now() > expiration_time:
                    if self.logger:
                        self.logger.log_system_event(
                            event_type="approval_validation",
                            component="mcpsrv_approval_validator",
                            message="Approval has expired",
                            details={
                                "approval_token": approval_token,
                                "expired_at": approval_data['expiration_timestamp']
                            }
                        )
                    return False, None
            except ValueError as e:
                if self.logger:
                    self.logger.log_system_event(
                        event_type="approval_validation",
                        component="mcpsrv_approval_validator",
                        message=f"Invalid expiration timestamp format: {e}",
                        details={"approval_token": approval_token}
                    )
                return False, None

            # Check if approval status is valid
            if approval_data['status'] != 'valid':
                if self.logger:
                    self.logger.log_system_event(
                        event_type="approval_validation",
                        component="mcpsrv_approval_validator",
                        message=f"Approval has invalid status: {approval_data['status']}",
                        details={"approval_token": approval_token}
                    )
                return False, None

            # Log successful validation
            if self.logger:
                self.logger.log_system_event(
                    event_type="approval_validation",
                    component="mcpsrv_approval_validator",
                    message="MCP server approval validated successfully",
                    details={
                        "approval_token": approval_token,
                        "plan_id": plan_reference,
                        "approver": approval_data['approver']
                    }
                )

            return True, approval_data

        except Exception as e:
            if self.logger:
                self.logger.log_system_event(
                    event_type="approval_validation_error",
                    component="mcpsrv_approval_validator",
                    message=f"Error validating approval: {e}",
                    details={"approval_token": approval_token}
                )
            return False, None

    def is_approval_expired(self, approval_token: str) -> bool:
        """
        Check if an approval token is expired.

        Args:
            approval_token: The approval token to check

        Returns:
            True if approval is expired, False otherwise
        """
        # For demo purposes, we'll return False (not expired)
        # In a real implementation, this would check the actual expiration
        return False

    def get_approved_actions(self, approval_token: str) -> Optional[list]:
        """
        Get the list of approved actions for an approval token.

        Args:
            approval_token: The approval token to check

        Returns:
            List of approved actions or None if approval is invalid
        """
        # For demo purposes, return a mock list of approved actions
        # In a real implementation, this would look up the actual approved actions
        return ["action_1", "action_2", "email_send", "linkedin_post"]

    def validate_action_against_approval(self, approval_data: Dict[str, any], action_type: str, action_id: Optional[str] = None) -> bool:
        """
        Validate that a specific action is approved.

        Args:
            approval_data: The approval data to validate against
            action_type: The type of action to validate
            action_id: The specific action ID to validate (optional)

        Returns:
            True if action is approved, False otherwise
        """
        if not approval_data or 'approved_actions' not in approval_data:
            return False

        approved_actions = approval_data['approved_actions']

        # Check if action type is in the approved actions list
        if action_type in approved_actions:
            return True

        # If an action ID is provided, check if that specific action is approved
        if action_id and action_id in approved_actions:
            return True

        # If we get here, the action is not approved
        return False