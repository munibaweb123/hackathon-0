"""
Approval Watcher Module

Watches the Approved/ and Rejected/ folders for approval decision files.
When an APPROVAL_REQUIRED_*.md file appears in either folder, it triggers
the corresponding action execution or cancellation.

Silver Tier: Bridges the approval gate between Reasoning and Action phases.
"""

import json
import yaml
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.vault_interface import VaultInterface
from core.logger import Logger


class ApprovalWatcher:
    """
    Watches Approved/ and Rejected/ folders for approval decision files.
    Calls registered handlers when approvals or rejections are detected.
    """

    def __init__(self, vault_interface: VaultInterface, logger: Logger):
        self.vault = vault_interface
        self.logger = logger
        self._seen_approved: set = set()
        self._seen_rejected: set = set()
        self._on_approve_handlers: List[Callable] = []
        self._on_reject_handlers: List[Callable] = []

    def on_approve(self, handler: Callable[[Dict[str, Any]], None]):
        """Register a handler for approved actions."""
        self._on_approve_handlers.append(handler)

    def on_reject(self, handler: Callable[[Dict[str, Any]], None]):
        """Register a handler for rejected actions."""
        self._on_reject_handlers.append(handler)

    def _parse_approval_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse an APPROVAL_REQUIRED file and extract metadata."""
        try:
            data = self.vault.read_event_file(file_path)
            metadata = data.get("metadata", {})
            if not metadata.get("id"):
                return None

            return {
                "id": metadata.get("id"),
                "action_type": metadata.get("action_type"),
                "plan_id": metadata.get("plan_id"),
                "risk_level": metadata.get("risk_level"),
                "created": metadata.get("created"),
                "expires": metadata.get("expires"),
                "file_path": str(file_path),
                "filename": Path(file_path).name,
                "content": data.get("content", ""),
            }
        except Exception as e:
            self.logger.log_system_event(
                event_type="approval_parse_error",
                component="approval_watcher",
                message=f"Failed to parse approval file: {e}",
                details={"file_path": str(file_path)},
            )
            return None

    def check_approvals(self) -> List[Dict[str, Any]]:
        """
        Check for new approvals in the Approved/ folder.

        Returns:
            List of newly approved action metadata dicts
        """
        new_approvals = []

        for file_path in self.vault.get_approved_files():
            filename = Path(file_path).name
            if filename in self._seen_approved:
                continue
            if not filename.startswith("APPROVAL_REQUIRED_"):
                continue

            approval_data = self._parse_approval_file(file_path)
            if approval_data:
                approval_data["decision"] = "approved"
                approval_data["decided_at"] = datetime.utcnow().isoformat()
                self._seen_approved.add(filename)
                new_approvals.append(approval_data)

                self.logger.log_system_event(
                    event_type="approval_detected",
                    component="approval_watcher",
                    message=f"Approval detected: {approval_data.get('action_type')}",
                    details=approval_data,
                )

                # Call registered handlers
                for handler in self._on_approve_handlers:
                    try:
                        handler(approval_data)
                    except Exception as e:
                        self.logger.log_system_event(
                            event_type="approval_handler_error",
                            component="approval_watcher",
                            message=f"Error in approval handler: {e}",
                            details={"approval_id": approval_data.get("id")},
                        )

        return new_approvals

    def check_rejections(self) -> List[Dict[str, Any]]:
        """
        Check for new rejections in the Rejected/ folder.

        Returns:
            List of newly rejected action metadata dicts
        """
        new_rejections = []

        for file_path in self.vault.get_rejected_files():
            filename = Path(file_path).name
            if filename in self._seen_rejected:
                continue
            if not filename.startswith("APPROVAL_REQUIRED_"):
                continue

            rejection_data = self._parse_approval_file(file_path)
            if rejection_data:
                rejection_data["decision"] = "rejected"
                rejection_data["decided_at"] = datetime.utcnow().isoformat()
                self._seen_rejected.add(filename)
                new_rejections.append(rejection_data)

                self.logger.log_system_event(
                    event_type="rejection_detected",
                    component="approval_watcher",
                    message=f"Rejection detected: {rejection_data.get('action_type')}",
                    details=rejection_data,
                )

                for handler in self._on_reject_handlers:
                    try:
                        handler(rejection_data)
                    except Exception as e:
                        self.logger.log_system_event(
                            event_type="rejection_handler_error",
                            component="approval_watcher",
                            message=f"Error in rejection handler: {e}",
                            details={"approval_id": rejection_data.get("id")},
                        )

        return new_rejections

    def check_expired(self) -> List[Dict[str, Any]]:
        """
        Check for expired pending approvals (older than 24 hours).

        Returns:
            List of expired approval metadata dicts
        """
        expired = []
        now = datetime.utcnow()

        for file_path in self.vault.get_pending_approvals():
            filename = Path(file_path).name
            if not filename.startswith("APPROVAL_REQUIRED_"):
                continue

            approval_data = self._parse_approval_file(file_path)
            if not approval_data:
                continue

            expires_str = approval_data.get("expires", "")
            if not expires_str:
                continue

            try:
                expires_at = datetime.fromisoformat(expires_str.rstrip("Z"))
                if now > expires_at:
                    approval_data["decision"] = "expired"
                    expired.append(approval_data)

                    self.logger.log_system_event(
                        event_type="approval_expired",
                        component="approval_watcher",
                        message=f"Approval expired: {approval_data.get('action_type')}",
                        details=approval_data,
                    )
            except ValueError:
                pass

        return expired

    def poll(self) -> Dict[str, List]:
        """
        Single poll cycle: check approvals, rejections, and expirations.

        Returns:
            Dict with 'approved', 'rejected', 'expired' lists
        """
        return {
            "approved": self.check_approvals(),
            "rejected": self.check_rejections(),
            "expired": self.check_expired(),
        }
