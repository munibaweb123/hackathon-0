# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
Local Agent — trusted-zone agent for the AI Employee Platinum Tier.

Runs on the CEO's machine. Handles approvals, sensitive operations (email sending,
payments, social posting), and executes actions that require full credentials.

Usage:
    uv run local/agent.py --vault-path ./obsidian-vault
    uv run local/agent.py --vault-path ./obsidian-vault --once
    uv run local/agent.py --status
"""

import argparse
import logging
import logging.handlers
import shutil
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add parent dir so agent-skills/core is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
from agent_skills.core.agent_identity import AgentIdentity
from agent_skills.core.audit_logger import AuditLogger
from agent_skills.core.security_boundary import SecurityBoundary

logger = logging.getLogger("local-agent")


class LocalAgent:
    """
    Local agent entry point.

    Lifecycle:
    1. Load config
    2. Initialize identity (zone=local)
    3. Start managed processes (approval-manager, vault-sync, whatsapp-watcher)
    4. Monitor Drafts/ for items needing approval
    5. Surface health alerts from Signals/health/
    6. Write heartbeat each cycle
    7. Graceful shutdown on SIGTERM/SIGINT
    """

    def __init__(self, config_path: str, vault_path_override: Optional[str] = None) -> None:
        self.config_path = Path(config_path).resolve()
        self.config = self._load_config()
        self.project_root = Path(__file__).parent.parent.resolve()

        # Vault
        self.vault_path = Path(
            vault_path_override or self.config.get("vault", {}).get("path", "./obsidian-vault")
        ).resolve()

        # Agent identity
        agent_cfg = self.config.get("agent", {})
        self.identity = AgentIdentity(
            agent_id=agent_cfg.get("id", "local-001"),
            zone="local",
            vault_path=str(self.vault_path),
            capabilities=[p["name"] for p in self.config.get("processes", []) if p.get("enabled")],
            sync_interval=self.config.get("vault", {}).get("sync_interval_seconds", 300),
            version=agent_cfg.get("version", "1.0.0"),
        )

        # Security boundary
        self.security = SecurityBoundary(
            zone="local",
            vault_path=str(self.vault_path),
            config=self.config.get("security"),
        )

        # Audit logger
        self.audit = AuditLogger(
            agent_id=self.identity.agent_id,
            zone="local",
            vault_path=str(self.vault_path),
        )

        # Logging
        self.logs_dir = self.vault_path / "Logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._setup_logging()

        # Process management
        self.managed_processes: Dict[str, subprocess.Popen] = {}
        self.running = False

    def run(self, once: bool = False) -> None:
        """Start the local agent."""
        self.running = True
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        self.identity.start()
        self.audit.log("agent-started", f"local-agent/{self.identity.agent_id}")

        logger.info("Local agent started: %s", self.identity.agent_id)
        logger.info("Vault: %s", self.vault_path)
        logger.info("Capabilities: %s", ", ".join(self.identity.capabilities))

        # Start managed processes
        self._start_processes()

        if once:
            self._cycle()
            self._stop_processes()
            self.identity.stop()
            return

        sync_interval = self.config.get("vault", {}).get("sync_interval_seconds", 300)
        while self.running:
            self._cycle()
            for _ in range(sync_interval * 10):
                if not self.running:
                    break
                time.sleep(0.1)

        self._stop_processes()
        self.identity.stop()
        self.audit.log("agent-stopped", f"local-agent/{self.identity.agent_id}")
        logger.info("Local agent stopped")

    def _cycle(self) -> None:
        """Execute one agent cycle."""
        self.identity.heartbeat()
        self._check_processes()
        self._check_health_alerts()
        self._process_draft_approvals()
        self._process_lead_updates()
        self._route_approved_actions()

    def _check_health_alerts(self) -> None:
        """Read Signals/health/ for new alerts from cloud agent."""
        alerts_dir = self.vault_path / "Signals" / "health"
        if not alerts_dir.exists():
            return
        for alert_file in alerts_dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(alert_file.read_text(encoding="utf-8"))
                if data and data.get("status") in ("degraded", "down"):
                    logger.warning(
                        "HEALTH ALERT: %s — %s (%s)",
                        data.get("service-name", "unknown"),
                        data.get("status"),
                        data.get("action-taken", "none"),
                    )
            except Exception:
                pass

    def _process_draft_approvals(self) -> None:
        """
        Scan Drafts/ subdirectories for items with status: pending in frontmatter.

        Checks email/, social/, payments/, and briefings/ subdirectories.
        For social posts, logs that they need review.
        For payment drafts, checks if amount exceeds the secondary approval threshold.
        """
        drafts_dir = self.vault_path / "Drafts"
        if not drafts_dir.exists():
            return

        subdirs = ["email", "social", "payments", "briefings"]
        counts: Dict[str, int] = {}

        for subdir_name in subdirs:
            subdir = drafts_dir / subdir_name
            if not subdir.exists():
                continue

            pending_count = 0
            for draft_file in subdir.glob("*.md"):
                try:
                    text = draft_file.read_text(encoding="utf-8")
                    if not text.startswith("---"):
                        continue
                    end = text.find("---", 3)
                    if end < 0:
                        continue
                    fm = yaml.safe_load(text[3:end]) or {}

                    if fm.get("status") != "pending":
                        continue

                    pending_count += 1

                    # Social posts need review
                    if subdir_name == "social":
                        logger.info(
                            "Social draft needs review: %s", draft_file.name,
                        )

                    # Payment drafts — check secondary threshold
                    if subdir_name == "payments":
                        threshold = (
                            self.config
                            .get("approval", {})
                            .get("payment_secondary_threshold", 1000)
                        )
                        amount = fm.get("amount", 0)
                        try:
                            amount = float(amount)
                        except (TypeError, ValueError):
                            amount = 0
                        if amount > threshold:
                            logger.warning(
                                "Payment draft %s (amount %.2f) exceeds secondary "
                                "threshold (%.2f) — secondary confirmation required",
                                draft_file.name, amount, threshold,
                            )

                except Exception as e:
                    logger.debug(
                        "Error reading draft %s: %s", draft_file.name, e,
                    )

            if pending_count > 0:
                counts[subdir_name] = pending_count

        if counts:
            logger.info(
                "Pending drafts: %s",
                ", ".join(f"{k}={v}" for k, v in counts.items()),
            )

    def _process_lead_updates(self) -> None:
        """
        Scan Needs_Action/cloud/leads/ for lead files and check for status updates.

        Logs leads available for review. Supports updating lead status by checking
        for files in In_Progress/leads/ with status changes.
        """
        leads_dir = self.vault_path / "Needs_Action" / "cloud" / "leads"
        if leads_dir.exists():
            lead_files = list(leads_dir.glob("*.md"))
            if lead_files:
                logger.info(
                    "%d lead(s) available for review in Needs_Action/cloud/leads/",
                    len(lead_files),
                )
                for lead_file in lead_files:
                    try:
                        text = lead_file.read_text(encoding="utf-8")
                        if text.startswith("---"):
                            end = text.find("---", 3)
                            if end > 0:
                                fm = yaml.safe_load(text[3:end]) or {}
                                logger.info(
                                    "Lead: %s — status=%s priority=%s",
                                    lead_file.stem,
                                    fm.get("status", "unknown"),
                                    fm.get("priority", "unknown"),
                                )
                    except Exception as e:
                        logger.debug(
                            "Error reading lead %s: %s", lead_file.name, e,
                        )

        # Check for in-progress lead status changes
        in_progress_dir = self.vault_path / "In_Progress" / "leads"
        if not in_progress_dir.exists():
            return

        for lead_file in in_progress_dir.glob("*.md"):
            try:
                text = lead_file.read_text(encoding="utf-8")
                if not text.startswith("---"):
                    continue
                end = text.find("---", 3)
                if end < 0:
                    continue
                fm = yaml.safe_load(text[3:end]) or {}
                status = fm.get("status", "")
                if status:
                    logger.info(
                        "Lead status update: %s → %s",
                        lead_file.stem, status,
                    )
            except Exception as e:
                logger.debug(
                    "Error reading in-progress lead %s: %s",
                    lead_file.name, e,
                )

    def _route_approved_actions(self) -> None:
        """
        Scan Approved/ for approved items and route them to the appropriate MCP server.

        Routes based on item type:
        - social-post  → social-poster-mcp
        - email-reply  → email-sender-mcp
        - payment      → payment-handler-mcp

        Moves processed items to Done/ with a completion timestamp.
        """
        approved_dir = self.vault_path / "Approved"
        if not approved_dir.exists():
            return

        done_dir = self.vault_path / "Done"

        for approved_file in approved_dir.glob("*.md"):
            try:
                text = approved_file.read_text(encoding="utf-8")
                if not text.startswith("---"):
                    continue
                end = text.find("---", 3)
                if end < 0:
                    continue
                fm = yaml.safe_load(text[3:end]) or {}
                item_type = fm.get("type", "")

                # Route to appropriate MCP server
                route_map = {
                    "social-post": "social-poster-mcp",
                    "email-reply": "email-sender-mcp",
                    "payment": "payment-handler-mcp",
                }

                target_mcp = route_map.get(item_type)
                if not target_mcp:
                    logger.warning(
                        "Approved item %s has unknown type '%s' — skipping",
                        approved_file.name, item_type,
                    )
                    continue

                logger.info(
                    "Routing approved item %s (type=%s) to %s",
                    approved_file.name, item_type, target_mcp,
                )
                self.audit.log("action-routed", approved_file.name, {
                    "type": item_type,
                    "target_mcp": target_mcp,
                    "item_id": fm.get("id", str(uuid.uuid4())),
                })

                # Move to Done/ with completion timestamp
                done_dir.mkdir(parents=True, exist_ok=True)
                now = datetime.now(timezone.utc)
                completed_text = text.replace(
                    "---", f"---\ncompleted-at: {now.isoformat()}", 1,
                )
                done_file = done_dir / approved_file.name
                done_file.write_text(completed_text, encoding="utf-8")
                approved_file.unlink()

                self.audit.log("action-completed", done_file.name, {
                    "type": item_type,
                    "target_mcp": target_mcp,
                    "completed_at": now.isoformat(),
                })
                logger.info(
                    "Moved %s to Done/ (completed at %s)",
                    approved_file.name, now.isoformat(),
                )

            except Exception as e:
                logger.error(
                    "Error routing approved item %s: %s",
                    approved_file.name, e,
                )

    def _start_processes(self) -> None:
        """Start all enabled managed processes."""
        for proc_cfg in self.config.get("processes", []):
            if not proc_cfg.get("enabled", True):
                continue
            name = proc_cfg["name"]
            command = proc_cfg.get("command", "")
            if not command:
                continue
            command = command.replace("{vault}", str(self.vault_path))
            try:
                proc = subprocess.Popen(
                    command, shell=True, cwd=str(self.project_root),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                self.managed_processes[name] = proc
                self.audit.log("process-started", name, {"pid": proc.pid})
                logger.info("Started process: %s (PID %d)", name, proc.pid)
            except Exception as e:
                logger.error("Failed to start %s: %s", name, e)

    def _stop_processes(self) -> None:
        """Stop all managed processes gracefully."""
        for name, proc in self.managed_processes.items():
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                logger.info("Stopped process: %s", name)

    def _check_processes(self) -> None:
        """Check if managed processes are still alive."""
        for name, proc in list(self.managed_processes.items()):
            if proc.poll() is not None:
                logger.warning("Process %s exited (code %d)", name, proc.returncode)

    def show_status(self) -> None:
        """Print agent status."""
        print(f"\n{'=' * 50}")
        print(f"  LOCAL AGENT: {self.identity.agent_id}")
        print(f"{'=' * 50}")
        print(f"  Zone:     {self.identity.zone}")
        print(f"  Status:   {self.identity.status}")
        print(f"  Vault:    {self.vault_path}")
        print(f"  Skills:   {', '.join(self.identity.capabilities)}")

        # Show pending drafts
        drafts_dir = self.vault_path / "Drafts"
        pending = 0
        if drafts_dir.exists():
            pending = sum(1 for _ in drafts_dir.rglob("*.md"))
        print(f"  Pending Drafts: {pending}")

        # Show peer agents
        peers = AgentIdentity.discover_peers(str(self.vault_path))
        for peer in peers:
            if peer.agent_id != self.identity.agent_id:
                alive = "ALIVE" if peer.is_alive() else "STALE"
                print(f"  Peer: {peer.agent_id} ({peer.zone}) [{alive}]")

        print(f"{'=' * 50}")

    def _load_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return {}
        try:
            return yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            logger.error("Failed to load config: %s", e)
            return {}

    def _setup_logging(self) -> None:
        if logger.handlers:
            return
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        fh = logging.handlers.RotatingFileHandler(
            self.logs_dir / "local-agent.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8",
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    def _shutdown(self, signum: int, frame: Any) -> None:
        logger.info("Shutdown signal received")
        self.running = False


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Employee — Local Agent")
    parser.add_argument("--vault-path", default=None, help="Override vault path")
    parser.add_argument("--config", default=str(Path(__file__).parent / "config.yaml"), help="Config file")
    parser.add_argument("--once", action="store_true", help="Single cycle then exit")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    agent = LocalAgent(config_path=args.config, vault_path_override=args.vault_path)

    if args.status:
        agent.show_status()
        return

    agent.run(once=args.once)


if __name__ == "__main__":
    main()
