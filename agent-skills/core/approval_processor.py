"""
Approval Processor Module

Processes approved and rejected actions, triggering execution or cancellation.
Bridges the approval gate between the Reasoning and Action phases.

Task T034: Approval status change detection and action triggering
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.vault_interface import VaultInterface
from core.logger import Logger
from core.approval_validator import ApprovalValidator


class ApprovalProcessor:
    """
    Processes approved actions by routing them to the appropriate MCP action executor.
    Handles rejected actions by logging and archiving.
    """

    def __init__(self, vault_interface: VaultInterface, logger: Logger):
        self.vault = vault_interface
        self.logger = logger
        self.validator = ApprovalValidator(logger, vault_interface)
        self._action_handlers: Dict[str, Callable] = {}

    def register_action_handler(self, action_type: str, handler: Callable):
        """
        Register an action handler for a specific action type.

        Args:
            action_type: The action type (email_send, linkedin_post, etc.)
            handler: Callable that takes approval_data dict and executes the action
        """
        self._action_handlers[action_type] = handler
        self.logger.log_system_event(
            event_type="handler_registered",
            component="approval_processor",
            message=f"Action handler registered for: {action_type}",
        )

    def process_approval(self, approval_data: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """
        Process an approved action by executing it through the registered handler.

        Args:
            approval_data: Approval metadata from the approval watcher
            dry_run: If True, log but don't execute

        Returns:
            Dict with execution result
        """
        action_type = approval_data.get("action_type", "")
        approval_id = approval_data.get("id", "")

        # Validate first
        validation = self.validator.validate_approval_request(approval_data)
        if not validation["valid"]:
            self.logger.log_system_event(
                event_type="approval_validation_failed",
                component="approval_processor",
                message=f"Approval validation failed: {validation['errors']}",
                details={"approval_id": approval_id},
            )
            return {
                "status": "failed",
                "reason": "validation_failed",
                "errors": validation["errors"],
            }

        # Check expiry
        if self.validator.is_expired(approval_data):
            self.logger.log_system_event(
                event_type="approval_expired_on_process",
                component="approval_processor",
                message=f"Approval expired before processing: {action_type}",
                details={"approval_id": approval_id},
            )
            return {"status": "failed", "reason": "expired"}

        if dry_run:
            self.logger.log_system_event(
                event_type="approval_dry_run",
                component="approval_processor",
                message=f"DRY RUN: Would execute {action_type}",
                details={"approval_id": approval_id, "approval_data": approval_data},
            )
            return {"status": "dry_run", "action_type": action_type}

        # Find handler
        handler = self._action_handlers.get(action_type)
        if not handler:
            self.logger.log_system_event(
                event_type="no_handler",
                component="approval_processor",
                message=f"No handler registered for action type: {action_type}",
                details={"approval_id": approval_id},
            )
            return {"status": "failed", "reason": "no_handler"}

        # Execute
        try:
            result = handler(approval_data)

            # Log successful execution
            self._log_action_result(approval_data, "success", result)

            # Move approval file to completed
            self._archive_approval(approval_data, "completed")

            return {
                "status": "success",
                "action_type": action_type,
                "approval_id": approval_id,
                "result": result,
                "executed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            self.logger.log_system_event(
                event_type="action_execution_error",
                component="approval_processor",
                message=f"Error executing {action_type}: {e}",
                details={"approval_id": approval_id},
            )

            # Move to error folder
            self._archive_approval(approval_data, "error")

            return {
                "status": "failed",
                "reason": "execution_error",
                "error": str(e),
            }

    def process_rejection(self, rejection_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a rejected action by logging and archiving.

        Args:
            rejection_data: Rejection metadata from the approval watcher

        Returns:
            Dict with processing result
        """
        approval_id = rejection_data.get("id", "")
        action_type = rejection_data.get("action_type", "")

        self.logger.log_system_event(
            event_type="action_rejected",
            component="approval_processor",
            message=f"Action rejected: {action_type}",
            details={
                "approval_id": approval_id,
                "action_type": action_type,
                "decided_at": rejection_data.get("decided_at"),
            },
        )

        # Log the rejection result
        self._log_action_result(rejection_data, "rejected", None)

        return {
            "status": "rejected",
            "action_type": action_type,
            "approval_id": approval_id,
        }

    def process_expiration(self, expired_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an expired approval by archiving.

        Args:
            expired_data: Expired approval metadata

        Returns:
            Dict with processing result
        """
        new_path = self.validator.handle_expired(expired_data)

        return {
            "status": "expired",
            "action_type": expired_data.get("action_type"),
            "approval_id": expired_data.get("id"),
            "archived_to": new_path,
        }

    def _archive_approval(self, approval_data: Dict[str, Any], destination: str):
        """Move an approval file to the specified destination folder."""
        file_path = approval_data.get("file_path", "")
        if file_path:
            try:
                self.vault.move_file(file_path, destination)
            except Exception as e:
                self.logger.log_system_event(
                    event_type="archive_error",
                    component="approval_processor",
                    message=f"Failed to archive approval: {e}",
                    details={"file_path": file_path, "destination": destination},
                )

    def _log_action_result(
        self,
        approval_data: Dict[str, Any],
        status: str,
        result: Any,
    ):
        """Log the result of an action to the audit trail."""
        log_entry = {
            "approval_id": approval_data.get("id"),
            "action_type": approval_data.get("action_type"),
            "plan_id": approval_data.get("plan_id"),
            "risk_level": approval_data.get("risk_level"),
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if result:
            log_entry["result"] = str(result)[:500]

        # Write to audit log via vault
        try:
            self.vault.write_file(
                file_path=f"action_result_{approval_data.get('id', 'unknown')[:8]}.json",
                content=json.dumps(log_entry, indent=2),
                destination_folder="logs",
            )
        except Exception as e:
            self.logger.log_system_event(
                event_type="audit_log_error",
                component="approval_processor",
                message=f"Failed to write action result log: {e}",
            )
