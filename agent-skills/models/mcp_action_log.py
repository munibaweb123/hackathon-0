"""
MCP Action Log Model

This module represents logs of executed actions through the MCP server.
These logs include action type, parameters, approval reference, and results.
"""

from datetime import datetime
from typing import Dict, Any, Optional


class MCPActionLog:
    """
    Represents logs of executed actions through the MCP server.
    Includes action type, parameters, approval reference, and results.
    """

    def __init__(self, id: str, action_type: str, action_params: Dict[str, Any],
                 approval_id: str, execution_timestamp: str, result: str,
                 error_message: Optional[str] = None):
        """
        Initialize an MCPActionLog instance.

        Args:
            id: Unique identifier for the log entry
            action_type: Type of action executed
            action_params: Parameters for the action
            approval_id: Reference to the approval that authorized the action
            execution_timestamp: When the action was executed
            result: Result of the action (success, failure)
            error_message: Error details if the action failed
        """
        self.id = id
        self.action_type = action_type
        self.action_params = action_params
        self.approval_id = approval_id
        self.execution_timestamp = execution_timestamp
        self.result = result
        self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the MCPActionLog instance to a dictionary.

        Returns:
            Dictionary representation of the MCPActionLog
        """
        return {
            "id": self.id,
            "action_type": self.action_type,
            "action_params": self.action_params,
            "approval_id": self.approval_id,
            "execution_timestamp": self.execution_timestamp,
            "result": self.result,
            "error_message": self.error_message
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPActionLog':
        """
        Create an MCPActionLog instance from a dictionary.

        Args:
            data: Dictionary containing MCPActionLog data

        Returns:
            MCPActionLog instance
        """
        return cls(
            id=data.get('id', ''),
            action_type=data.get('action_type', ''),
            action_params=data.get('action_params', {}),
            approval_id=data.get('approval_id', ''),
            execution_timestamp=data.get('execution_timestamp', ''),
            result=data.get('result', ''),
            error_message=data.get('error_message')
        )

    def validate(self) -> bool:
        """
        Validate the MCPActionLog instance.

        Returns:
            True if the instance is valid, False otherwise
        """
        # Check for required fields
        if not self.id or not self.action_type or not self.approval_id or not self.execution_timestamp or not self.result:
            return False

        # Validate action_type
        if not isinstance(self.action_type, str) or len(self.action_type.strip()) == 0:
            return False

        # Validate action_params
        if not isinstance(self.action_params, dict):
            return False

        # Validate approval_id
        if not isinstance(self.approval_id, str) or len(self.approval_id.strip()) == 0:
            return False

        # Validate execution_timestamp format (ISO format)
        try:
            timestamp = datetime.fromisoformat(self.execution_timestamp.replace('Z', '+00:00'))
        except ValueError:
            return False

        # Validate result
        if self.result not in ['success', 'failure']:
            return False

        # Validate error_message if present
        if self.error_message is not None and not isinstance(self.error_message, str):
            return False

        return True

    def mark_success(self):
        """
        Mark the action log as successful.
        """
        self.result = "success"
        self.error_message = None

    def mark_failure(self, error_message: str):
        """
        Mark the action log as failed with an error message.

        Args:
            error_message: Error message for the failure
        """
        self.result = "failure"
        self.error_message = error_message

    def is_success(self) -> bool:
        """
        Check if the action was successful.

        Returns:
            True if the action was successful, False otherwise
        """
        return self.result == "success"

    def is_failure(self) -> bool:
        """
        Check if the action failed.

        Returns:
            True if the action failed, False otherwise
        """
        return self.result == "failure"