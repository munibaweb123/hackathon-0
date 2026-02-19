# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
Cloud Agent — always-on agent for the AI Employee Platinum Tier.

Runs on a remote VM with read-only API access. Creates drafts, monitors services,
and syncs state to the local agent via Git-based vault synchronization.

Usage:
    uv run cloud/agent.py --vault-path ./obsidian-vault
    uv run cloud/agent.py --vault-path ./obsidian-vault --once
    uv run cloud/agent.py --status
"""

import argparse
import logging
import logging.handlers
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add parent dir so agent-skills/core is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
from agent_skills.core.agent_identity import AgentIdentity
from agent_skills.core.audit_logger import AuditLogger
from agent_skills.core.security_boundary import SecurityBoundary

logger = logging.getLogger("cloud-agent")


class CloudAgent:
    """
    Cloud agent entry point.

    Lifecycle:
    1. Load config
    2. Initialize identity (zone=cloud)
    3. Start managed processes (gmail-watcher, health-monitor, vault-sync)
    4. Run scheduled tasks (briefings, audits)
    5. Write heartbeat each cycle
    6. Graceful shutdown on SIGTERM/SIGINT
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
            agent_id=agent_cfg.get("id", "cloud-001"),
            zone="cloud",
            vault_path=str(self.vault_path),
            capabilities=[p["name"] for p in self.config.get("processes", []) if p.get("enabled")],
            sync_interval=self.config.get("vault", {}).get("sync_interval_seconds", 300),
            version=agent_cfg.get("version", "1.0.0"),
        )

        # Security boundary
        self.security = SecurityBoundary(
            zone="cloud",
            vault_path=str(self.vault_path),
            config=self.config.get("security"),
        )

        # Audit logger
        self.audit = AuditLogger(
            agent_id=self.identity.agent_id,
            zone="cloud",
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
        """Start the cloud agent."""
        self.running = True
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        self.identity.start()
        self.audit.log("agent-started", f"cloud-agent/{self.identity.agent_id}")

        logger.info("Cloud agent started: %s", self.identity.agent_id)
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
            # Responsive sleep
            for _ in range(sync_interval * 10):
                if not self.running:
                    break
                time.sleep(0.1)

        self._stop_processes()
        self.identity.stop()
        self.audit.log("agent-stopped", f"cloud-agent/{self.identity.agent_id}")
        logger.info("Cloud agent stopped")

    def _cycle(self) -> None:
        """Execute one agent cycle: heartbeat + process check + lead scan."""
        self.identity.heartbeat()
        self._check_processes()
        self._scan_for_leads()
        self._check_health_thresholds()

    def _scan_for_leads(self) -> None:
        """
        Scan Drafts/email/ for potential leads alongside draft creation (T040).

        After the gmail-watcher creates drafts, this scans them for lead
        signals and creates lead files in Needs_Action/cloud/leads/.
        """
        drafts_dir = self.vault_path / "Drafts" / "email"
        if not drafts_dir.exists():
            return

        leads_dir = self.vault_path / "Needs_Action" / "cloud" / "leads"

        for draft_file in drafts_dir.glob("*.md"):
            try:
                text = draft_file.read_text(encoding="utf-8")
                # Quick lead signal check — keywords in body
                body = text.split("---", 2)[-1] if "---" in text else text
                lead_keywords = [
                    "partnership", "proposal", "rfp", "quote", "pricing",
                    "interested in", "inquiry", "demo", "contract",
                    "collaboration", "budget", "vendor",
                ]
                if any(kw in body.lower() for kw in lead_keywords):
                    # Check if lead already created for this draft
                    lead_marker = leads_dir / f"LEAD_{draft_file.stem}.md"
                    if lead_marker.exists():
                        continue

                    # Parse frontmatter for source info
                    fm = {}
                    if text.startswith("---"):
                        end = text.find("---", 3)
                        if end > 0:
                            fm = yaml.safe_load(text[3:end]) or {}

                    # Validate write permission
                    rel_path = f"Needs_Action/cloud/leads/LEAD_{draft_file.stem}.md"
                    if not self.security.can_write(rel_path):
                        continue

                    leads_dir.mkdir(parents=True, exist_ok=True)
                    now = datetime.now(timezone.utc)
                    lead_content = (
                        "---\n"
                        f"type: lead\n"
                        f"status: new\n"
                        f"source: email\n"
                        f"priority: {fm.get('priority', 'medium')}\n"
                        f"created-at: {now.isoformat()}\n"
                        f"email-draft: {draft_file.name}\n"
                        f"sender: {fm.get('from', 'unknown')}\n"
                        f"subject: {fm.get('subject', draft_file.stem)}\n"
                        "---\n\n"
                        f"# Lead: {fm.get('subject', draft_file.stem)}\n\n"
                        f"Detected from email draft. Review and categorize.\n"
                    )
                    lead_marker.write_text(lead_content, encoding="utf-8")
                    self.audit.log("lead-detected", rel_path, {
                        "source_draft": draft_file.name,
                        "sender": fm.get("from", "unknown"),
                    })
                    logger.info("Lead detected from draft: %s", draft_file.name)
            except Exception as e:
                logger.debug("Error scanning draft for leads: %s — %s", draft_file.name, e)

    def _check_health_thresholds(self) -> None:
        """
        Check health thresholds from config and write alerts (T047).

        Uses configurable thresholds from cloud/config.yaml health section:
        CPU 80%, memory 80%, disk 90%.
        """
        health_cfg = self.config.get("health", {})
        cpu_threshold = health_cfg.get("cpu_threshold_percent", 80)
        mem_threshold = health_cfg.get("memory_threshold_percent", 80)
        disk_threshold = health_cfg.get("disk_threshold_percent", 90)
        alert_path_prefix = health_cfg.get("alert_path", "Signals/health/")

        try:
            import shutil
            # Disk check
            usage = shutil.disk_usage(str(self.vault_path))
            disk_pct = (usage.used / usage.total) * 100 if usage.total > 0 else 0

            if disk_pct > disk_threshold:
                self._write_health_signal(
                    alert_path_prefix, "disk",
                    "degraded" if disk_pct < 95 else "down",
                    f"Disk usage at {disk_pct:.1f}% (threshold: {disk_threshold}%)",
                )

            # Memory check (Linux only)
            meminfo = Path("/proc/meminfo")
            if meminfo.exists():
                mem_text = meminfo.read_text()
                total = available = 0
                for line in mem_text.splitlines():
                    if line.startswith("MemTotal:"):
                        total = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        available = int(line.split()[1])
                if total > 0:
                    mem_pct = ((total - available) / total) * 100
                    if mem_pct > mem_threshold:
                        self._write_health_signal(
                            alert_path_prefix, "memory",
                            "degraded",
                            f"Memory usage at {mem_pct:.1f}% (threshold: {mem_threshold}%)",
                        )

            # CPU check (Linux only — 1-minute load average)
            loadavg = Path("/proc/loadavg")
            if loadavg.exists():
                load_1m = float(loadavg.read_text().split()[0])
                cpu_count = len(list(Path("/sys/devices/system/cpu").glob("cpu[0-9]*"))) or 1
                cpu_pct = (load_1m / cpu_count) * 100
                if cpu_pct > cpu_threshold:
                    self._write_health_signal(
                        alert_path_prefix, "cpu",
                        "degraded",
                        f"CPU load at {cpu_pct:.1f}% (threshold: {cpu_threshold}%)",
                    )
        except Exception as e:
            logger.debug("Health threshold check error: %s", e)

    def _write_health_signal(
        self, alert_path: str, component: str, status: str, message: str
    ) -> None:
        """Write a health alert signal to Signals/health/."""
        signals_dir = self.vault_path / "Signals" / "health"
        signals_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        filename = f"{component}.yaml"
        signal_file = signals_dir / filename

        signal_data = {
            "service-name": component,
            "status": status,
            "timestamp": now.isoformat(),
            "message": message,
            "agent": self.identity.agent_id,
            "action-taken": "alert-generated",
        }

        signal_file.write_text(
            yaml.dump(signal_data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        self.audit.log("health-alert", f"Signals/health/{filename}", {
            "component": component,
            "status": status,
        })
        logger.warning("Health alert: %s — %s (%s)", component, status, message)

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
        print(f"  CLOUD AGENT: {self.identity.agent_id}")
        print(f"{'=' * 50}")
        print(f"  Zone:     {self.identity.zone}")
        print(f"  Status:   {self.identity.status}")
        print(f"  Vault:    {self.vault_path}")
        print(f"  Skills:   {', '.join(self.identity.capabilities)}")
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
            self.logs_dir / "cloud-agent.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8",
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
    parser = argparse.ArgumentParser(description="AI Employee — Cloud Agent")
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

    agent = CloudAgent(config_path=args.config, vault_path_override=args.vault_path)

    if args.status:
        agent.show_status()
        return

    agent.run(once=args.once)


if __name__ == "__main__":
    main()
