"""
Approval File Model

This module represents human-created files that authorize specific actions in Plan.md files.
These files include expiration timestamps and matching plan references.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional


class ApprovalFile:
    """
    Represents human-created files that authorize specific actions in Plan.md files.
    Includes expiration timestamps and matching plan references.
    """

    def __init__(self, id: str, plan_id: str, approved_actions: List[str],
                 approver: str, approval_timestamp: str, expiration_timestamp: str,
                 status: str = "valid"):
        """
        Initialize an ApprovalFile instance.

        Args:
            id: Unique identifier for the approval
            plan_id: Reference to the plan being approved
            approved_actions: List of specific actions that are approved
            approver: Identity of the person who approved
            approval_timestamp: When the approval was given
            expiration_timestamp: When the approval expires
            status: Current status of the approval (valid, expired, revoked)
        """
        self.id = id
        self.plan_id = plan_id
        self.approved_actions = approved_actions
        self.approver = approver
        self.approval_timestamp = approval_timestamp
        self.expiration_timestamp = expiration_timestamp
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the ApprovalFile instance to a dictionary.

        Returns:
            Dictionary representation of the ApprovalFile
        """
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "approved_actions": self.approved_actions,
            "approver": self.approver,
            "approval_timestamp": self.approval_timestamp,
            "expiration_timestamp": self.expiration_timestamp,
            "status": self.status
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ApprovalFile':
        """
        Create an ApprovalFile instance from a dictionary.

        Args:
            data: Dictionary containing ApprovalFile data

        Returns:
            ApprovalFile instance
        """
        return cls(
            id=data.get('id', ''),
            plan_id=data.get('plan_id', ''),
            approved_actions=data.get('approved_actions', []),
            approver=data.get('approver', ''),
            approval_timestamp=data.get('approval_timestamp', ''),
            expiration_timestamp=data.get('expiration_timestamp', ''),
            status=data.get('status', 'valid')
        )

    def validate(self) -> bool:
        """
        Validate the ApprovalFile instance.

        Returns:
            True if the instance is valid, False otherwise
        """
        # Check for required fields
        if not self.id or not self.plan_id or not self.approver or not self.approval_timestamp or not self.expiration_timestamp:
            return False

        # Validate plan_id
        if not isinstance(self.plan_id, str) or len(self.plan_id.strip()) == 0:
            return False

        # Validate approver
        if not isinstance(self.approver, str) or len(self.approver.strip()) == 0:
            return False

        # Validate approved_actions
        if not isinstance(self.approved_actions, list):
            return False

        # Validate timestamps format (ISO format)
        try:
            approval_time = datetime.fromisoformat(self.approval_timestamp.replace('Z', '+00:00'))
            expiration_time = datetime.fromisoformat(self.expiration_timestamp.replace('Z', '+00:00'))
        except ValueError:
            return False

        # Check if approval timestamp is in the past
        if approval_time > datetime.now():
            return False

        # Check if expiration timestamp is in the future
        if expiration_time < datetime.now():
            return False

        # Validate status
        if self.status not in ['valid', 'expired', 'revoked']:
            return False

        return True

    def is_expired(self) -> bool:
        """
        Check if the approval is expired.

        Returns:
            True if the approval is expired, False otherwise
        """
        try:
            expiration_time = datetime.fromisoformat(self.expiration_timestamp.replace('Z', '+00:00'))
            return datetime.now() > expiration_time
        except ValueError:
            return True  # If timestamp is invalid, treat as expired

    def mark_expired(self):
        """
        Mark the approval as expired.
        """
        self.status = "expired"

    def mark_revoked(self):
        """
        Mark the approval as revoked.
        """
        self.status = "revoked"

    def get_approved_actions(self) -> List[str]:
        """
        Get the list of approved actions.

        Returns:
            List of approved action IDs
        """
        return self.approved_actions.copy()

    def is_action_approved(self, action_id: str) -> bool:
        """
        Check if a specific action is approved.

        Args:
            action_id: ID of the action to check

        Returns:
            True if the action is approved, False otherwise
        """
        return action_id in self.approved_actions