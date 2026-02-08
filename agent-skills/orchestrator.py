"""
Silver Tier Orchestrator

Master Python script that coordinates the Perception → Reasoning → Action pipeline.
Handles timing, folder watching, and integrates all Silver Tier components.

Architecture:
1. Perception Phase: Run all watchers → event files in vault/inbox/
2. Reasoning Phase: Claude analyzes events → Plan.md in vault/plans/
3. Approval Gate: Check vault/Approved/ for approved actions
4. Action Phase: Execute approved actions via MCP server → log results
"""

import os
import sys
import time
import signal
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.vault_interface import VaultInterface
from core.logger import Logger
from core.approval_generator import ApprovalGenerator
from watchers.gmail_watcher import GmailWatcher
from watchers.linkedin_watcher import LinkedInWatcher
from watchers.approval_watcher import ApprovalWatcher
from scheduler.task_scheduler import TaskScheduler


class SilverTierOrchestrator:
    """
    Coordinates all Silver Tier components in the
    Perception → Reasoning → Action pipeline.
    """

    def __init__(self, vault_path: str = "./obsidian-vault", mock_mode: bool = False):
        # Load environment
        load_dotenv()
        load_dotenv(Path("dashboard") / ".env.local")

        self.mock_mode = mock_mode or os.getenv("DEV_MODE", "false").lower() == "true"
        self.dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
        self.running = False

        # Core infrastructure
        self.vault = VaultInterface(vault_path)
        self.logger = Logger()
        self.approval_gen = ApprovalGenerator(self.vault, self.logger)

        # Watchers (Perception)
        self.gmail_watcher = GmailWatcher(
            vault_interface=self.vault,
            logger=self.logger,
            check_interval=int(os.getenv("GMAIL_POLL_INTERVAL", "300")),
            mock_mode=self.mock_mode,
        )
        self.linkedin_watcher = LinkedInWatcher(
            vault_interface=self.vault,
            logger=self.logger,
            check_interval=int(os.getenv("LINKEDIN_POLL_INTERVAL", "900")),
            mock_mode=self.mock_mode,
        )

        # Approval Watcher (Gate)
        self.approval_watcher = ApprovalWatcher(self.vault, self.logger)
        self.approval_watcher.on_approve(self._handle_approved_action)
        self.approval_watcher.on_reject(self._handle_rejected_action)

        # Signal handling for graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        self.logger.log_system_event(
            event_type="orchestrator_init",
            component="orchestrator",
            message=f"Silver Tier Orchestrator initialized (mock={self.mock_mode}, dry_run={self.dry_run})",
            details={"vault_path": vault_path},
        )

    def _shutdown(self, signum, frame):
        """Handle graceful shutdown."""
        self.logger.log_system_event(
            event_type="orchestrator_shutdown",
            component="orchestrator",
            message="Shutdown signal received",
            details={},
        )
        self.running = False

    # --- Perception Phase ---

    def run_perception(self):
        """Run all watchers to detect external events."""
        self.logger.log_system_event(
            event_type="perception_start",
            component="orchestrator",
            message="Starting perception phase",
            details={},
        )

        # Poll Gmail
        try:
            self.gmail_watcher.poll_gmail()
        except Exception as e:
            self.logger.log_system_event(
                event_type="perception_error",
                component="orchestrator",
                message=f"Gmail watcher error: {e}",
                details={},
            )

        # Poll LinkedIn
        try:
            self.linkedin_watcher.poll_linkedin()
        except Exception as e:
            self.logger.log_system_event(
                event_type="perception_error",
                component="orchestrator",
                message=f"LinkedIn watcher error: {e}",
                details={},
            )

    # --- Reasoning Phase ---

    def run_reasoning(self):
        """
        Process new events in the inbox through Claude reasoning loop.
        Creates Plan.md files with recommended actions.

        NOTE: Requires Claude API key. Without it, events stay in inbox
        until reasoning is available.
        """
        new_events = self.vault.get_files_in_folder("inbox")
        md_events = [f for f in new_events if str(f).endswith(".md")]

        if not md_events:
            return

        self.logger.log_system_event(
            event_type="reasoning_start",
            component="orchestrator",
            message=f"Processing {len(md_events)} new events",
            details={"event_count": len(md_events)},
        )

        # For now, log that reasoning would run here
        # Full Claude API integration will be in reasoning_skill.py (Phase 6)
        for event_file in md_events:
            self.logger.log_system_event(
                event_type="reasoning_pending",
                component="orchestrator",
                message=f"Event awaiting reasoning: {event_file}",
                details={"file": str(event_file)},
            )

    # --- Approval Gate ---

    def check_approval_gate(self):
        """Check for approved/rejected actions and process them."""
        results = self.approval_watcher.poll()

        approved = results.get("approved", [])
        rejected = results.get("rejected", [])
        expired = results.get("expired", [])

        if approved:
            self.logger.log_system_event(
                event_type="approvals_found",
                component="orchestrator",
                message=f"{len(approved)} actions approved",
                details={"count": len(approved)},
            )

        if rejected:
            self.logger.log_system_event(
                event_type="rejections_found",
                component="orchestrator",
                message=f"{len(rejected)} actions rejected",
                details={"count": len(rejected)},
            )

        if expired:
            self.logger.log_system_event(
                event_type="expirations_found",
                component="orchestrator",
                message=f"{len(expired)} approvals expired",
                details={"count": len(expired)},
            )

    def _handle_approved_action(self, approval_data: dict):
        """Handle an approved action — trigger MCP execution."""
        action_type = approval_data.get("action_type", "unknown")

        if self.dry_run:
            self.logger.log_system_event(
                event_type="dry_run_action",
                component="orchestrator",
                message=f"[DRY RUN] Would execute: {action_type}",
                details=approval_data,
            )
            return

        # Full MCP execution will be implemented in Phase 7
        self.logger.log_system_event(
            event_type="action_queued",
            component="orchestrator",
            message=f"Action queued for MCP execution: {action_type}",
            details=approval_data,
        )

    def _handle_rejected_action(self, rejection_data: dict):
        """Handle a rejected action — log and cancel."""
        self.logger.log_system_event(
            event_type="action_rejected",
            component="orchestrator",
            message=f"Action rejected: {rejection_data.get('action_type', 'unknown')}",
            details=rejection_data,
        )

    # --- Action Phase ---

    def run_actions(self):
        """
        Execute approved actions via MCP server.
        Only runs if DRY_RUN is False and actions are approved.

        NOTE: Full implementation in Phase 7 (MCP Server).
        """
        pass

    # --- Main Loop ---

    def run_once(self):
        """Run a single cycle of the Perception → Reasoning → Action pipeline."""
        self.run_perception()
        self.run_reasoning()
        self.check_approval_gate()
        self.run_actions()

    def run(self, poll_interval: int = 60):
        """
        Run the orchestrator in a continuous loop.

        Args:
            poll_interval: Seconds between each full pipeline cycle
        """
        self.running = True

        self.logger.log_system_event(
            event_type="orchestrator_started",
            component="orchestrator",
            message=f"Orchestrator running (interval={poll_interval}s)",
            details={"poll_interval": poll_interval, "mock_mode": self.mock_mode},
        )

        print(f"Silver Tier Orchestrator started (mock={self.mock_mode}, dry_run={self.dry_run})")
        print(f"Vault: {self.vault.vault_path}")
        print(f"Poll interval: {poll_interval}s")
        print("Press Ctrl+C to stop.\n")

        while self.running:
            try:
                cycle_start = time.time()
                self.run_once()
                elapsed = time.time() - cycle_start

                # Sleep for remaining interval
                sleep_time = max(0, poll_interval - elapsed)
                if sleep_time > 0 and self.running:
                    time.sleep(sleep_time)

            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.log_system_event(
                    event_type="orchestrator_error",
                    component="orchestrator",
                    message=f"Error in main loop: {e}",
                    details={},
                )
                time.sleep(5)  # Back off on error

        print("\nOrchestrator stopped.")
        self.logger.log_system_event(
            event_type="orchestrator_stopped",
            component="orchestrator",
            message="Orchestrator stopped gracefully",
            details={},
        )

    def status(self) -> dict:
        """Get current orchestrator status."""
        return {
            "running": self.running,
            "mock_mode": self.mock_mode,
            "dry_run": self.dry_run,
            "vault_path": str(self.vault.vault_path),
            "watchers": {
                "gmail": {"mock": self.gmail_watcher.mock_mode},
                "linkedin": {"mock": self.linkedin_watcher.mock_mode},
            },
            "vault_stats": {
                "inbox": len(self.vault.get_files_in_folder("inbox")),
                "pending_approval": len(self.vault.get_pending_approvals()),
                "approved": len(self.vault.get_approved_files()),
                "rejected": len(self.vault.get_rejected_files()),
                "plans": len(self.vault.get_plans()),
                "posts": len(self.vault.get_posts()),
            },
        }


def main():
    """CLI entry point for the orchestrator."""
    import argparse

    parser = argparse.ArgumentParser(description="Silver Tier AI Employee Orchestrator")
    parser.add_argument("--vault", default="./obsidian-vault", help="Path to Obsidian vault")
    parser.add_argument("--interval", type=int, default=60, help="Poll interval in seconds")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode")
    parser.add_argument("--once", action="store_true", help="Run single cycle then exit")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    args = parser.parse_args()

    orchestrator = SilverTierOrchestrator(
        vault_path=args.vault,
        mock_mode=args.mock,
    )

    if args.status:
        import json
        print(json.dumps(orchestrator.status(), indent=2))
        return

    if args.once:
        orchestrator.run_once()
        print(json.dumps(orchestrator.status(), indent=2))
        return

    orchestrator.run(poll_interval=args.interval)


if __name__ == "__main__":
    main()
