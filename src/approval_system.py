"""Approval system for human oversight."""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from .entities import ApprovalEntity, OperationEntity
from .vault_manager import VaultManager
from .logger import Logger
from .file_monitor import FileMonitor


class ApprovalSystem:
    """Manages human approval workflows."""

    def __init__(self, vault_manager: VaultManager, logger: Logger):
        self.vault_manager = vault_manager
        self.logger = logger
        self.pending_approvals: Dict[str, ApprovalEntity] = {}
        self.approval_queue = []

        # Set up file monitoring for approval responses
        self.approval_monitor = FileMonitor(self.vault_manager.vault_path / "pending-approval")
        self.approval_monitor.add_callback(self._handle_approval_response)

    def _handle_approval_response(self, file_path: str, event_type: str):
        """Handle approval response files."""
        file_path_obj = Path(file_path)

        # Only process JSON files that look like approval responses
        if file_path_obj.suffix.lower() == '.json' and 'approval' in file_path_obj.name.lower():
            self.logger.info("approval_system", "approval_response_detected",
                            f"Detected approval response: {file_path_obj.name}",
                            file_ref=file_path)

            # Process the approval response
            self._process_approval_response(file_path_obj)

    def _process_approval_response(self, file_path: Path):
        """Process an approval response file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                response_data = json.load(f)

            # Extract approval information
            request_id = response_data.get('request_id')
            approved = response_data.get('approved')
            approver_id = response_data.get('approver_id', 'unknown')
            comments = response_data.get('comments', '')
            selected_option = response_data.get('selected_option', '')

            if not request_id:
                self.logger.error("approval_system", "invalid_approval_response",
                                 f"Approval response missing request_id: {file_path.name}")
                return

            # Update the approval entity
            if request_id in self.pending_approvals:
                approval = self.pending_approvals[request_id]
                approval.approved = approved
                approval.approver_id = approver_id
                approval.comments = comments
                approval.selected_option = selected_option
                approval.responded_at = datetime.now()

                # Log the approval decision
                status = "approved" if approved else "rejected"
                self.logger.audit("approval_system", f"request_{status}",
                                 f"Approval request {request_id} {status} by {approver_id}",
                                 operation_ref=request_id)

                # Move the approval request file to appropriate folder
                if approved:
                    self.vault_manager.move_file(file_path, 'completed')
                else:
                    self.vault_manager.move_file(file_path, 'rejected')

                # Execute the approved operation
                if approved:
                    self._execute_approved_operation(approval)
            else:
                self.logger.warn("approval_system", "approval_not_found",
                                f"Approval response for unknown request: {request_id}")

        except Exception as e:
            self.logger.error("approval_system", "approval_response_error",
                             f"Error processing approval response {file_path.name}: {str(e)}")

    def _execute_approved_operation(self, approval: ApprovalEntity):
        """Execute an operation that has been approved."""
        # This is a simplified implementation - in a real system, you would
        # need to know what operation to execute based on the approval
        self.logger.info("approval_system", "executing_approved_operation",
                        f"Executing approved operation: {approval.operation_id}")

    def create_approval_request(self, operation: OperationEntity,
                              justification: str,
                              options: List[Dict[str, str]]) -> Optional[ApprovalEntity]:
        """Create an approval request for an operation."""
        try:
            # Create approval entity
            approval = ApprovalEntity(
                operation_id=operation.id,
                request_type=operation.type,
                description=operation.description,
                justification=justification,
                options=options
            )

            # Add to pending approvals
            self.pending_approvals[approval.id] = approval

            # Create approval request data for file
            approval_data = {
                "request_id": approval.id,
                "timestamp": approval.requested_at.isoformat(),
                "request_type": approval.request_type,
                "description": approval.description,
                "justification": approval.justification,
                "options": approval.options,
                "file_context": operation.file_id,
                "risk_level": "medium",  # Could be determined based on operation
                "urgency": "normal",     # Could be determined based on operation
                "created_by": "ai-employee"
            }

            # Create the approval request file in the pending-approval folder
            approval_filename = f"approval_request_{approval.id}.json"
            approval_file = self.vault_manager.create_file(
                "pending-approval",
                approval_filename,
                json.dumps(approval_data, indent=2)
            )

            if approval_file:
                self.logger.audit("approval_system", "approval_request_created",
                                f"Created approval request {approval.id}",
                                file_ref=str(approval_file),
                                operation_ref=approval.operation_id)

                return approval
            else:
                self.logger.error("approval_system", "approval_request_failed",
                                 f"Failed to create approval request {approval.id}")
                return None

        except Exception as e:
            self.logger.error("approval_system", "create_approval_error",
                             f"Error creating approval request: {str(e)}")
            return None

    def get_pending_approvals(self) -> List[ApprovalEntity]:
        """Get all pending approval requests."""
        return [approval for approval in self.pending_approvals.values()
                if approval.approved is None]

    def get_approval_status(self, approval_id: str) -> Optional[ApprovalEntity]:
        """Get the status of a specific approval request."""
        return self.pending_approvals.get(approval_id)

    def start_monitoring_approvals(self):
        """Start monitoring for approval responses."""
        self.approval_monitor.start_monitoring()
        self.logger.info("approval_system", "approval_monitoring_started",
                        "Started monitoring for approval responses")

    def stop_monitoring_approvals(self):
        """Stop monitoring for approval responses."""
        self.approval_monitor.stop_monitoring()
        self.logger.info("approval_system", "approval_monitoring_stopped",
                        "Stopped monitoring for approval responses")