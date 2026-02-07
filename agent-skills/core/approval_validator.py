"""
Approval Validator Module

This module validates approval files and expiration.
Ensures that human approval is maintained for sensitive actions.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
from core.logger import Logger


class ApprovalValidator:
    """
    Validator for approval files and expiration.
    Ensures human approval is maintained for sensitive actions.
    """

    def __init__(self, logger: Logger):
        """
        Initialize the approval validator.

        Args:
            logger: Logger instance for auditability
        """
        self.logger = logger

    def validate_approval(self, approval_file_path: str,
                         plan_reference: str) -> Tuple[bool, Optional[Dict[str, any]]]:
        """
        Validate an approval file and check expiration.

        Args:
            approval_file_path: Path to the approval file
            plan_reference: Reference to the plan being approved

        Returns:
            Tuple of (is_valid, approval_data) where is_valid indicates if the
            approval is valid and approval_data contains the approval information
        """
        try:
            # Read the approval file
            with open(approval_file_path, 'r', encoding='utf-8') as f:
                approval_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            self.logger.log_system_event(
                event_type="approval_validation",
                component="approval_validator",
                message=f"Failed to read approval file: {e}",
                details={"approval_file": approval_file_path}
            )
            return False, None

        # Validate required fields
        required_fields = [
            'id', 'plan_id', 'approved_actions', 'approver',
            'approval_timestamp', 'expiration_timestamp', 'status'
        ]

        for field in required_fields:
            if field not in approval_data:
                self.logger.log_system_event(
                    event_type="approval_validation",
                    component="approval_validator",
                    message=f"Missing required field '{field}' in approval file",
                    details={"approval_file": approval_file_path}
                )
                return False, None

        # Check if plan reference matches
        if approval_data['plan_id'] != plan_reference:
            self.logger.log_system_event(
                event_type="approval_validation",
                component="approval_validator",
                message="Plan reference does not match approval",
                details={
                    "approval_file": approval_file_path,
                    "expected_plan": plan_reference,
                    "actual_plan": approval_data['plan_id']
                }
            )
            return False, None

        # Check if approval is expired
        try:
            expiration_time = datetime.fromisoformat(approval_data['expiration_timestamp'])
            if datetime.now() > expiration_time:
                self.logger.log_system_event(
                    event_type="approval_validation",
                    component="approval_validator",
                    message="Approval has expired",
                    details={
                        "approval_file": approval_file_path,
                        "expired_at": approval_data['expiration_timestamp']
                    }
                )
                return False, None
        except ValueError as e:
            self.logger.log_system_event(
                event_type="approval_validation",
                component="approval_validator",
                message=f"Invalid expiration timestamp format: {e}",
                details={"approval_file": approval_file_path}
            )
            return False, None

        # Check if approval status is valid
        if approval_data['status'] != 'valid':
            self.logger.log_system_event(
                event_type="approval_validation",
                component="approval_validator",
                message=f"Approval has invalid status: {approval_data['status']}",
                details={"approval_file": approval_file_path}
            )
            return False, None

        # Log successful validation
        self.logger.log_system_event(
            event_type="approval_validation",
            component="approval_validator",
            message="Approval validated successfully",
            details={
                "approval_file": approval_file_path,
                "plan_id": plan_reference,
                "approver": approval_data['approver']
            }
        )

        return True, approval_data

    def is_approval_expired(self, approval_file_path: str) -> bool:
        """
        Check if an approval file is expired without validating the full approval.

        Args:
            approval_file_path: Path to the approval file

        Returns:
            True if approval is expired, False otherwise
        """
        try:
            with open(approval_file_path, 'r', encoding='utf-8') as f:
                approval_data = json.load(f)

            if 'expiration_timestamp' not in approval_data:
                return True

            expiration_time = datetime.fromisoformat(approval_data['expiration_timestamp'])
            return datetime.now() > expiration_time
        except:
            return True  # If we can't read it, treat as expired

    def get_approved_actions(self, approval_file_path: str) -> Optional[list]:
        """
        Get the list of approved actions from an approval file.

        Args:
            approval_file_path: Path to the approval file

        Returns:
            List of approved actions or None if approval is invalid
        """
        try:
            with open(approval_file_path, 'r', encoding='utf-8') as f:
                approval_data = json.load(f)

            if 'approved_actions' in approval_data:
                return approval_data['approved_actions']
        except:
            pass

        return None