"""
Approval Monitor Skill

Agent Skill that monitors the approval workflow, processes decisions,
and coordinates between the approval watcher and action execution.

Task T035: ApprovalMonitorSkill
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from core.base_skill import BaseSkill, SkillResult
from core.vault_interface import VaultInterface
from core.logger import Logger
from core.approval_validator import ApprovalValidator
from core.approval_processor import ApprovalProcessor
from watchers.approval_watcher import ApprovalWatcher


class ApprovalMonitorSkill(BaseSkill):
    """
    Skill that monitors and processes the approval workflow.
    Coordinates between approval detection and action execution.
    """

    def __init__(
        self,
        vault_interface: VaultInterface,
        logger: Logger,
        dry_run: bool = False,
    ):
        super().__init__(
            name="approval_monitor",
            vault_interface=vault_interface,
            logger=logger,
        )
        self.dry_run = dry_run
        self.watcher = ApprovalWatcher(vault_interface, logger)
        self.processor = ApprovalProcessor(vault_interface, logger)
        self.validator = ApprovalValidator(logger, vault_interface)

    @property
    def id(self) -> str:
        return "approval_monitor"

    @property
    def description(self) -> str:
        return "Monitors approval workflow and processes decisions"

    async def execute_async(self, input_data: Dict[str, Any]) -> SkillResult:
        """
        Execute a single approval monitoring cycle.

        Args:
            input_data: Optional context dict

        Returns:
            SkillResult with approval processing results
        """
        results = {
            "approved": [],
            "rejected": [],
            "expired": [],
            "errors": [],
        }

        # Poll for new decisions
        poll_results = self.watcher.poll()

        # Process approvals
        for approval in poll_results.get("approved", []):
            try:
                result = self.processor.process_approval(approval, dry_run=self.dry_run)
                results["approved"].append(result)
            except Exception as e:
                results["errors"].append({
                    "approval_id": approval.get("id"),
                    "error": str(e),
                })

        # Process rejections
        for rejection in poll_results.get("rejected", []):
            try:
                result = self.processor.process_rejection(rejection)
                results["rejected"].append(result)
            except Exception as e:
                results["errors"].append({
                    "approval_id": rejection.get("id"),
                    "error": str(e),
                })

        # Process expirations
        for expired in poll_results.get("expired", []):
            try:
                result = self.processor.process_expiration(expired)
                results["expired"].append(result)
            except Exception as e:
                results["errors"].append({
                    "approval_id": expired.get("id"),
                    "error": str(e),
                })

        # Log summary
        total = (
            len(results["approved"])
            + len(results["rejected"])
            + len(results["expired"])
        )

        if total > 0 and self.logger:
            self.logger.log_system_event(
                event_type="approval_cycle_complete",
                component="approval_monitor_skill",
                message=f"Processed {total} approval decisions",
                details={
                    "approved": len(results["approved"]),
                    "rejected": len(results["rejected"]),
                    "expired": len(results["expired"]),
                    "errors": len(results["errors"]),
                },
            )

        return SkillResult(
            success=True,
            data=results,
        )

    def register_action_handler(self, action_type: str, handler):
        """Register an action handler with the processor."""
        self.processor.register_action_handler(action_type, handler)

    def get_status(self) -> Dict[str, Any]:
        """Get current approval workflow status."""
        summary = self.validator.get_pending_summary()
        return {
            "skill": self.name,
            "dry_run": self.dry_run,
            "pending_approvals": summary,
            "timestamp": datetime.utcnow().isoformat(),
        }
