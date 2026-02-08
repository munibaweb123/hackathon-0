"""
Approval Validator Module

This module validates approval files and expiration.
Ensures that human approval is maintained for sensitive actions.

Silver Tier Extensions:
- Support for YAML frontmatter APPROVAL_REQUIRED_*.md files
- 24-hour expiry check for pending approvals
- Pending approval summary with expiry status
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from core.logger import Logger


class ApprovalValidator:
    """
    Validator for approval files and expiration.
    Ensures human approval is maintained for sensitive actions.

    Silver Tier: Also handles APPROVAL_REQUIRED_*.md files with YAML frontmatter.
    """

    DEFAULT_EXPIRY_HOURS = 24

    def __init__(self, logger: Logger, vault_interface=None):
        """
        Initialize the approval validator.

        Args:
            logger: Logger instance for auditability
            vault_interface: Optional VaultInterface for Silver Tier operations
        """
        self.logger = logger
        self.vault = vault_interface

    # --- Bronze Tier Methods (JSON-based approvals) ---

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

    # --- Silver Tier Methods (YAML frontmatter-based approvals) ---

    def validate_approval_request(self, approval_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate an APPROVAL_REQUIRED request has all required fields.

        Args:
            approval_data: Approval request metadata

        Returns:
            Dict with 'valid' bool and optional 'errors' list
        """
        errors = []
        required_fields = ["id", "action_type", "risk_level"]

        for field in required_fields:
            if not approval_data.get(field):
                errors.append(f"Missing required field: {field}")

        valid_action_types = ["email_send", "linkedin_post", "whatsapp_reply", "escalate"]
        action_type = approval_data.get("action_type", "")
        if action_type and action_type not in valid_action_types:
            errors.append(f"Invalid action_type: {action_type}")

        valid_risk_levels = ["low", "medium", "high"]
        risk_level = approval_data.get("risk_level", "")
        if risk_level and risk_level not in valid_risk_levels:
            errors.append(f"Invalid risk_level: {risk_level}")

        return {"valid": len(errors) == 0, "errors": errors}

    def is_expired(self, approval_data: Dict[str, Any]) -> bool:
        """
        Check if a Silver Tier approval request has expired.

        Args:
            approval_data: Approval metadata with 'expires' or 'created' field

        Returns:
            True if the approval has expired
        """
        now = datetime.utcnow()

        # Check explicit expiry
        expires_str = approval_data.get("expires", "")
        if expires_str:
            try:
                expires_at = datetime.fromisoformat(expires_str.rstrip("Z"))
                return now > expires_at
            except ValueError:
                pass

        # Fall back to created + default expiry
        created_str = approval_data.get("created", "")
        if created_str:
            try:
                created_at = datetime.fromisoformat(created_str.rstrip("Z"))
                return now > (created_at + timedelta(hours=self.DEFAULT_EXPIRY_HOURS))
            except ValueError:
                pass

        return False

    def get_expired_approvals(self) -> List[Dict[str, Any]]:
        """
        Find all expired approvals in the pending-approval folder.
        Requires vault_interface to be set.

        Returns:
            List of expired approval metadata dicts
        """
        if not self.vault:
            return []

        expired = []

        for file_path in self.vault.get_pending_approvals():
            filename = Path(file_path).name
            if not filename.startswith("APPROVAL_REQUIRED_"):
                continue

            try:
                data = self.vault.read_event_file(file_path)
                metadata = data.get("metadata", {})

                if self.is_expired(metadata):
                    expired.append({
                        "id": metadata.get("id"),
                        "action_type": metadata.get("action_type"),
                        "plan_id": metadata.get("plan_id"),
                        "risk_level": metadata.get("risk_level"),
                        "created": metadata.get("created"),
                        "expires": metadata.get("expires"),
                        "file_path": str(file_path),
                        "filename": filename,
                        "status": "expired",
                    })
            except Exception as e:
                self.logger.log_system_event(
                    event_type="approval_validation_error",
                    component="approval_validator",
                    message=f"Error checking approval expiry: {e}",
                    details={"file_path": str(file_path)},
                )

        return expired

    def handle_expired(self, approval_data: Dict[str, Any]) -> Optional[str]:
        """
        Handle an expired approval by moving it to the archive folder.

        Args:
            approval_data: Expired approval metadata

        Returns:
            New file path or None on failure
        """
        if not self.vault:
            return None

        file_path = approval_data.get("file_path", "")
        if not file_path:
            return None

        try:
            new_path = self.vault.move_file(
                source_path=file_path,
                destination_folder="archive",
            )

            self.logger.log_system_event(
                event_type="approval_expired_archived",
                component="approval_validator",
                message=f"Expired approval archived: {approval_data.get('action_type')}",
                details={
                    "approval_id": approval_data.get("id"),
                    "original_path": file_path,
                    "archive_path": str(new_path),
                },
            )

            return str(new_path)
        except Exception as e:
            self.logger.log_system_event(
                event_type="approval_archive_error",
                component="approval_validator",
                message=f"Failed to archive expired approval: {e}",
                details={"approval_id": approval_data.get("id")},
            )
            return None

    def get_pending_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all pending approvals with expiry status.

        Returns:
            Dict with 'total', 'expiring_soon', 'expired' counts and details
        """
        if not self.vault:
            return {"total": 0, "pending": 0, "expiring_soon": 0, "expired": 0, "details": {}}

        pending = []
        expiring_soon = []
        expired = []
        now = datetime.utcnow()

        for file_path in self.vault.get_pending_approvals():
            filename = Path(file_path).name
            if not filename.startswith("APPROVAL_REQUIRED_"):
                continue

            try:
                data = self.vault.read_event_file(file_path)
                metadata = data.get("metadata", {})
                info = {
                    "id": metadata.get("id"),
                    "action_type": metadata.get("action_type"),
                    "risk_level": metadata.get("risk_level"),
                    "created": metadata.get("created"),
                    "expires": metadata.get("expires"),
                    "filename": filename,
                }

                if self.is_expired(metadata):
                    expired.append(info)
                else:
                    pending.append(info)
                    # Check if expiring within 2 hours
                    expires_str = metadata.get("expires", "")
                    if expires_str:
                        try:
                            expires_at = datetime.fromisoformat(expires_str.rstrip("Z"))
                            if (expires_at - now).total_seconds() < 7200:
                                expiring_soon.append(info)
                        except ValueError:
                            pass
            except Exception:
                pass

        return {
            "total": len(pending) + len(expired),
            "pending": len(pending),
            "expiring_soon": len(expiring_soon),
            "expired": len(expired),
            "details": {
                "pending": pending,
                "expiring_soon": expiring_soon,
                "expired": expired,
            },
        }
