# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
Health Monitor — centralized system health monitoring for the AI Employee.

Monitors processes, system resources, API connectivity, and vault integrity.
Auto-restarts crashed processes with exponential backoff (max 3/hour).
Sends alerts via Needs_Action/ files and updates Dashboard.md.

Usage:
    uv run health_monitor.py --vault-path ../../obsidian-vault --once
    uv run health_monitor.py --vault-path ../../obsidian-vault --monitor --interval 60
    uv run health_monitor.py --vault-path ../../obsidian-vault --status
    uv run health_monitor.py --vault-path ../../obsidian-vault --report
    uv run health_monitor.py --vault-path ../../obsidian-vault --restart gmail-watcher
    uv run health_monitor.py --vault-path ../../obsidian-vault --list-processes
"""

import argparse
import json
import logging
import logging.handlers
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Local imports (same directory)
sys.path.insert(0, str(Path(__file__).parent))
from process_manager import ProcessManager
from resource_checker import ResourceChecker
from alert_sender import AlertSender

logger = logging.getLogger("health-monitor")


class HealthMonitor:
    """
    Centralized health monitoring for all AI Employee components.

    Monitors:
    - Process liveness (PID-based)
    - System resources (disk, memory, CPU)
    - Vault accessibility (read/write)
    - API connectivity (configurable endpoints)
    - Custom health checks (shell commands)

    Auto-restarts crashed processes with exponential backoff.
    """

    def __init__(self, vault_path: str, project_root: str = ".") -> None:
        self.vault_path = Path(vault_path).resolve()
        self.project_root = Path(project_root).resolve()
        self.running = False

        # Ensure directories exist
        self.logs_dir = self.vault_path / "Logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.process_mgr = ProcessManager(
            vault_path=str(self.vault_path),
            project_root=str(self.project_root),
        )
        self.resource_checker = ResourceChecker()
        self.alert_sender = AlertSender(vault_path=str(self.vault_path))

        # Custom health checks: {name: command}
        self.custom_checks: Dict[str, str] = {}

        # Health log
        self.health_log_path = self.logs_dir / "health_monitor.json"

        # Setup logging
        self._setup_logging()

        # Load API endpoints from config
        self.api_endpoints = self._load_api_endpoints()

    # ------------------------------------------------------------------
    # Logging setup
    # ------------------------------------------------------------------
    def _setup_logging(self) -> None:
        """Configure rotating file + console logging."""
        if logger.handlers:
            return

        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

        # Rotating file handler — 5 MB, 3 backups
        fh = logging.handlers.RotatingFileHandler(
            self.logs_dir / "health_monitor.log",
            maxBytes=5_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    def _load_api_endpoints(self) -> List[Dict[str, str]]:
        """Load API endpoints from config or use defaults."""
        config_path = self.vault_path / "config" / "health_endpoints.yaml"
        if config_path.exists():
            try:
                import yaml

                data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "endpoints" in data:
                    return data["endpoints"]
            except Exception as e:
                logger.warning("Failed to load endpoints config: %s", e)

        return [
            {"name": "google-apis", "url": "https://www.googleapis.com"},
            {"name": "github", "url": "https://api.github.com"},
        ]

    # ------------------------------------------------------------------
    # Core: Single check cycle
    # ------------------------------------------------------------------
    def check_once(self) -> Dict[str, Any]:
        """
        Run a single health check cycle.

        Steps:
        1. Check all registered processes
        2. Check system resources
        3. Check vault accessibility
        4. Auto-restart crashed processes
        5. Send alerts for failures
        6. Run custom health checks
        7. Update Dashboard.md
        8. Log results

        Returns:
            Full health report dict.
        """
        now = datetime.now(timezone.utc)
        report: Dict[str, Any] = {
            "timestamp": now.isoformat(),
            "healthy": True,
            "processes": {},
            "resources": {},
            "vault": {},
            "apis": {},
            "custom_checks": {},
            "alerts_sent": 0,
            "restarts_attempted": 0,
        }

        # 1. Check processes
        process_statuses = self.process_mgr.check_all()
        for status in process_statuses:
            name = status["name"]
            report["processes"][name] = status

            if not status["running"]:
                report["healthy"] = False

                # Auto-restart
                restart_result = self.process_mgr.restart_process(name)
                report["restarts_attempted"] += 1

                if restart_result["success"]:
                    # Info alert: restarted successfully
                    alert_path = self.alert_sender.send_alert(
                        severity="info",
                        component=name,
                        message=f"Process '{name}' was down and has been restarted.",
                        details={
                            "new_pid": restart_result.get("pid"),
                            "backoff_seconds": restart_result.get("backoff_seconds", 0),
                        },
                    )
                    if alert_path:
                        report["alerts_sent"] += 1

                    # Clear previous critical alert
                    self.alert_sender.clear_alert(name)
                else:
                    # Critical alert: restart failed
                    alert_path = self.alert_sender.send_alert(
                        severity="critical",
                        component=name,
                        message=(
                            f"Process '{name}' is DOWN and could not be restarted. "
                            f"Reason: {restart_result.get('message', 'unknown')}"
                        ),
                        details={"last_pid": status.get("pid")},
                    )
                    if alert_path:
                        report["alerts_sent"] += 1

        # 2. Check resources
        resources = self.resource_checker.check_all(
            vault_path=str(self.vault_path),
            endpoints=self.api_endpoints,
        )
        report["resources"] = {
            "disk": resources["disk"],
            "memory": resources["memory"],
            "cpu": resources["cpu"],
        }
        report["vault"] = resources["vault"]
        report["apis"] = resources["apis"]

        # Resource alerts
        if not resources["disk"].get("ok", True):
            alert_path = self.alert_sender.send_alert(
                severity="critical",
                component="disk",
                message=(
                    f"Disk usage at {resources['disk']['percent_used']}% "
                    f"(threshold: {self.resource_checker.disk_threshold}%). "
                    f"Free: {resources['disk']['free_gb']} GB."
                ),
                details=resources["disk"],
            )
            if alert_path:
                report["alerts_sent"] += 1
            report["healthy"] = False

        if not resources["memory"].get("ok", True):
            alert_path = self.alert_sender.send_alert(
                severity="warning",
                component="memory",
                message=(
                    f"Memory usage at {resources['memory']['percent_used']}% "
                    f"(threshold: {self.resource_checker.memory_threshold}%). "
                    f"Available: {resources['memory']['available_mb']} MB."
                ),
                details=resources["memory"],
            )
            if alert_path:
                report["alerts_sent"] += 1
            report["healthy"] = False

        if not resources["cpu"].get("ok", True):
            alert_path = self.alert_sender.send_alert(
                severity="warning",
                component="cpu",
                message=(
                    f"CPU usage at {resources['cpu']['percent_used']}% "
                    f"(threshold: {self.resource_checker.cpu_threshold}%). "
                    f"Load: {resources['cpu'].get('load_1m', 0)}"
                ),
                details=resources["cpu"],
            )
            if alert_path:
                report["alerts_sent"] += 1
            report["healthy"] = False

        if not resources["vault"].get("ok", True):
            alert_path = self.alert_sender.send_alert(
                severity="critical",
                component="vault",
                message="Vault is not accessible! Check permissions and disk space.",
                details=resources["vault"],
            )
            if alert_path:
                report["alerts_sent"] += 1
            report["healthy"] = False

        # API connectivity alerts
        if not resources["apis"].get("all_ok", True):
            for ep_name, ep_status in resources["apis"].get("results", {}).items():
                if not ep_status.get("reachable"):
                    alert_path = self.alert_sender.send_alert(
                        severity="warning",
                        component=f"api-{ep_name}",
                        message=f"API endpoint '{ep_name}' is unreachable.",
                        details=ep_status,
                    )
                    if alert_path:
                        report["alerts_sent"] += 1

        # 3. Custom health checks
        if self.custom_checks:
            report["custom_checks"] = self.run_custom_checks()
            for name, result in report["custom_checks"].items():
                if not result.get("ok"):
                    alert_path = self.alert_sender.send_alert(
                        severity="warning",
                        component=f"custom-{name}",
                        message=f"Custom health check '{name}' failed.",
                        details=result,
                    )
                    if alert_path:
                        report["alerts_sent"] += 1
                    report["healthy"] = False

        # 4. Clear alerts for recovered components
        for status in process_statuses:
            if status["running"] and status["responsive"]:
                self.alert_sender.clear_alert(status["name"])

        if resources["disk"].get("ok"):
            self.alert_sender.clear_alert("disk")
        if resources["memory"].get("ok"):
            self.alert_sender.clear_alert("memory")
        if resources["cpu"].get("ok"):
            self.alert_sender.clear_alert("cpu")
        if resources["vault"].get("ok"):
            self.alert_sender.clear_alert("vault")

        # 5. Update Dashboard and log
        self.update_dashboard(report)
        self._log_health(report)

        status_str = "HEALTHY" if report["healthy"] else "UNHEALTHY"
        logger.info(
            "Health check: %s | Processes: %d/%d | Alerts: %d | Restarts: %d",
            status_str,
            sum(1 for s in process_statuses if s["running"]),
            len(process_statuses),
            report["alerts_sent"],
            report["restarts_attempted"],
        )

        return report

    # ------------------------------------------------------------------
    # Continuous monitoring
    # ------------------------------------------------------------------
    def monitor(self, interval: int = 60) -> None:
        """
        Continuous health monitoring loop.

        Args:
            interval: Seconds between check cycles.
        """
        self.running = True
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        logger.info(
            "Starting health monitor (interval: %ds, processes: %d)",
            interval,
            len(self.process_mgr.processes),
        )

        while self.running:
            try:
                self.check_once()
            except Exception as e:
                logger.error("Health check cycle failed: %s", e, exc_info=True)

            # Sleep in small increments for responsive shutdown
            for _ in range(interval * 10):
                if not self.running:
                    break
                time.sleep(0.1)

        logger.info("Health monitor stopped")

    def _shutdown(self, signum: int, frame: Any) -> None:
        """Signal handler for graceful shutdown."""
        logger.info("Shutdown signal received (%d)", signum)
        self.running = False

    # ------------------------------------------------------------------
    # Custom health checks
    # ------------------------------------------------------------------
    def add_custom_check(self, name: str, command: str) -> None:
        """
        Register a custom health check.

        The command is run via shell. Exit code 0 = healthy.
        """
        self.custom_checks[name] = command
        logger.info("Registered custom check: %s → %s", name, command)

    def remove_custom_check(self, name: str) -> bool:
        """Remove a custom health check."""
        if name in self.custom_checks:
            del self.custom_checks[name]
            return True
        return False

    def run_custom_checks(self) -> Dict[str, Dict[str, Any]]:
        """Execute all custom health checks."""
        results = {}
        for name, command in self.custom_checks.items():
            try:
                proc = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(self.project_root),
                )
                results[name] = {
                    "ok": proc.returncode == 0,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout.strip()[:200],
                    "stderr": proc.stderr.strip()[:200],
                }
            except subprocess.TimeoutExpired:
                results[name] = {
                    "ok": False,
                    "exit_code": -1,
                    "error": "Timed out (30s)",
                }
            except Exception as e:
                results[name] = {
                    "ok": False,
                    "exit_code": -1,
                    "error": str(e),
                }
        return results

    # ------------------------------------------------------------------
    # Status & Reporting
    # ------------------------------------------------------------------
    def show_status(self) -> None:
        """Print current health status to stdout."""
        print("=" * 60)
        print("  SYSTEM HEALTH STATUS")
        print("=" * 60)

        # Processes
        print("\n--- Processes ---")
        processes = self.process_mgr.check_all()
        for p in processes:
            status = "RUNNING" if p["running"] else "DOWN"
            uptime = ProcessManager.format_uptime(p["uptime_seconds"])
            pid_str = f"PID {p['pid']}" if p["pid"] else "no PID"
            print(f"  {p['name']:25s} {status:10s} {uptime:>12s}  ({pid_str})")

        # Resources
        print("\n--- Resources ---")
        resources = self.resource_checker.check_all(str(self.vault_path))

        disk = resources["disk"]
        status = "OK" if disk.get("ok") else "ALERT"
        print(f"  Disk:   {disk['percent_used']:>5.1f}% used  ({disk['free_gb']} GB free)  [{status}]")

        mem = resources["memory"]
        status = "OK" if mem.get("ok") else "ALERT"
        print(f"  Memory: {mem['percent_used']:>5.1f}% used  ({mem['available_mb']} MB avail) [{status}]")

        cpu = resources["cpu"]
        status = "OK" if cpu.get("ok") else "ALERT"
        print(f"  CPU:    {cpu['percent_used']:>5.1f}% used  (load: {cpu.get('load_1m', 0)})    [{status}]")

        # Vault
        vault = resources["vault"]
        vault_status = "OK" if vault.get("ok") else "ALERT"
        print(f"\n--- Vault ---")
        print(f"  Read:  {'yes' if vault.get('readable') else 'NO'}")
        print(f"  Write: {'yes' if vault.get('writable') else 'NO'}")
        print(f"  Status: {vault_status}")

        # Active alerts
        active_alerts = self.alert_sender.get_active_alerts()
        print(f"\n--- Alerts ---")
        print(f"  Active: {len(active_alerts)}")
        for alert in active_alerts[-5:]:
            print(f"    [{alert.get('severity', '?').upper()}] {alert.get('component', '?')}: {alert.get('message', '')[:60]}")

        print("\n" + "=" * 60)

    def show_report(self, period: str = "24h") -> None:
        """
        Generate health report from logs.

        Args:
            period: Time period — "24h", "7d", "30d"
        """
        # Parse period
        hours = 24
        if period.endswith("d"):
            hours = int(period[:-1]) * 24
        elif period.endswith("h"):
            hours = int(period[:-1])

        cutoff = time.time() - (hours * 3600)
        logs = self._load_health_logs()
        period_logs = [l for l in logs if l.get("epoch", 0) > cutoff]

        print(f"\n{'=' * 60}")
        print(f"  HEALTH REPORT — Last {period}")
        print(f"{'=' * 60}")

        if not period_logs:
            print("\n  No health check data for this period.")
            return

        # Overall health
        total = len(period_logs)
        healthy = sum(1 for l in period_logs if l.get("healthy", False))
        uptime_pct = round((healthy / total) * 100, 1) if total > 0 else 0

        print(f"\n  Checks run:      {total}")
        print(f"  Healthy:         {healthy} ({uptime_pct}%)")
        print(f"  Unhealthy:       {total - healthy}")

        # Restart count
        restart_history = self.process_mgr._load_restart_history()
        period_restarts = [r for r in restart_history if r.get("epoch", 0) > cutoff]
        print(f"  Restarts:        {len(period_restarts)}")

        # Alerts
        alert_history = self.alert_sender.get_alert_history()
        period_alerts = [a for a in alert_history if a.get("epoch", 0) > cutoff]
        critical = sum(1 for a in period_alerts if a.get("severity") == "critical")
        warning = sum(1 for a in period_alerts if a.get("severity") == "warning")
        print(f"  Alerts:          {len(period_alerts)} ({critical} critical, {warning} warning)")

        # Per-process summary
        print(f"\n  --- Process Summary ---")
        for name in self.process_mgr.processes:
            proc_restarts = [r for r in period_restarts if r.get("process") == name]
            proc_alerts = [a for a in period_alerts if a.get("component") == name]
            current = self.process_mgr.check_process(name)
            status = "UP" if current["running"] else "DOWN"
            print(
                f"    {name:25s} {status:5s} | "
                f"restarts: {len(proc_restarts)} | "
                f"alerts: {len(proc_alerts)}"
            )

        # Incidents (critical alerts)
        if critical > 0:
            print(f"\n  --- Critical Incidents ---")
            crit_alerts = [a for a in period_alerts if a.get("severity") == "critical"]
            for a in crit_alerts[-10:]:
                ts = a.get("timestamp", "?")[:19]
                print(f"    {ts} | {a.get('component', '?')}: {a.get('message', '')[:50]}")

        print(f"\n{'=' * 60}")

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def update_dashboard(self, report: Optional[Dict[str, Any]] = None) -> None:
        """Write System Health section to Dashboard.md."""
        dashboard_path = self.vault_path / "Dashboard.md"

        if report is None:
            report = self.check_once()

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # Build process table
        proc_lines = []
        for name, status in report.get("processes", {}).items():
            state = "Running" if status.get("running") else "DOWN"
            uptime = ProcessManager.format_uptime(status.get("uptime_seconds", 0))
            proc_lines.append(f"| {name} | {state} | {uptime} | {now} |")

        proc_table = "\n".join(proc_lines) if proc_lines else "| No processes registered | - | - | - |"

        # Resource summary
        disk = report.get("resources", {}).get("disk", {})
        mem = report.get("resources", {}).get("memory", {})
        cpu = report.get("resources", {}).get("cpu", {})

        disk_pct = disk.get("percent_used", 0)
        mem_pct = mem.get("percent_used", 0)
        cpu_pct = cpu.get("percent_used", 0)

        # Active alerts count
        active_alerts = self.alert_sender.get_active_alerts()
        overall = "Healthy" if report.get("healthy", False) else "UNHEALTHY"

        section = (
            f"## System Health\n\n"
            f"**Status:** {overall} | **Last Check:** {now}\n\n"
            f"| Component | Status | Uptime | Last Check |\n"
            f"|-----------|--------|--------|------------|\n"
            f"{proc_table}\n\n"
            f"**Resources:** Disk {disk_pct}% | Memory {mem_pct}% | CPU {cpu_pct}%\n\n"
            f"**Alerts:** {len(active_alerts)} active"
        )

        # Read existing dashboard or create
        if dashboard_path.exists():
            content = dashboard_path.read_text(encoding="utf-8")

            # Replace existing section
            pattern = r"## System Health\n.*?(?=\n## |\Z)"
            if re.search(pattern, content, re.DOTALL):
                content = re.sub(pattern, section, content, flags=re.DOTALL)
            else:
                content = content.rstrip() + "\n\n" + section + "\n"
        else:
            content = f"# Dashboard\n\n{section}\n"

        dashboard_path.write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------
    # Health logging
    # ------------------------------------------------------------------
    def _log_health(self, report: Dict[str, Any]) -> None:
        """Append health check result to log."""
        entry = {
            "timestamp": report.get("timestamp"),
            "epoch": time.time(),
            "healthy": report.get("healthy"),
            "alerts_sent": report.get("alerts_sent", 0),
            "restarts_attempted": report.get("restarts_attempted", 0),
            "process_count": len(report.get("processes", {})),
            "processes_running": sum(
                1 for p in report.get("processes", {}).values() if p.get("running")
            ),
        }

        logs = self._load_health_logs()
        logs.append(entry)

        # Keep last 2000 entries
        logs = logs[-2000:]

        try:
            self.health_log_path.write_text(
                json.dumps(logs, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error("Failed to write health log: %s", e)

    def _load_health_logs(self) -> List[Dict[str, Any]]:
        """Load health check logs."""
        if not self.health_log_path.exists():
            return []
        try:
            data = json.loads(self.health_log_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return []


# ======================================================================
# CLI
# ======================================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Health Monitor — system health monitoring for the AI Employee"
    )

    # Actions
    parser.add_argument(
        "--monitor", action="store_true", help="Continuous monitoring loop"
    )
    parser.add_argument(
        "--once", action="store_true", help="Single health check cycle"
    )
    parser.add_argument(
        "--status", action="store_true", help="Print health status summary"
    )
    parser.add_argument(
        "--report", action="store_true", help="Generate health report"
    )
    parser.add_argument(
        "--period", default="24h", help="Report period: 24h, 7d, 30d (default: 24h)"
    )
    parser.add_argument(
        "--restart", metavar="PROCESS", help="Manually restart a process"
    )
    parser.add_argument(
        "--stop-process", metavar="PROCESS", help="Stop a process"
    )
    parser.add_argument(
        "--register", metavar="NAME", help="Register a new process"
    )
    parser.add_argument(
        "--command", metavar="CMD", help="Command for --register"
    )
    parser.add_argument(
        "--list-processes", action="store_true", help="List registered processes"
    )

    # Common
    parser.add_argument(
        "--vault-path",
        default=os.getenv("VAULT_PATH", "./obsidian-vault"),
        help="Obsidian vault path (default: ./obsidian-vault)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Monitor interval in seconds (default: 60)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Debug logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    monitor = HealthMonitor(
        vault_path=args.vault_path,
        project_root=str(Path(__file__).parent.parent.parent.parent),
    )

    # Dispatch
    if args.list_processes:
        processes = monitor.process_mgr.list_processes()
        print(f"\nRegistered Processes ({len(processes)}):\n")
        for name, info in processes.items():
            status = "RUNNING" if info.get("running") else "DOWN"
            uptime = ProcessManager.format_uptime(info.get("uptime_seconds", 0))
            print(f"  {name:25s} {status:10s} {uptime:>12s}")
            print(f"    cmd: {info.get('command', 'N/A')[:70]}")
        return

    if args.register:
        if not args.command:
            print("Error: --command required with --register")
            sys.exit(1)
        monitor.process_mgr.register_process(args.register, args.command)
        print(f"Registered: {args.register}")
        return

    if args.restart:
        result = monitor.process_mgr.restart_process(args.restart)
        print(f"Restart {args.restart}: {result['message']}")
        sys.exit(0 if result["success"] else 1)

    if args.stop_process:
        result = monitor.process_mgr.stop_process(args.stop_process)
        print(f"Stop {args.stop_process}: {result['message']}")
        sys.exit(0 if result["success"] else 1)

    if args.status:
        monitor.show_status()
        return

    if args.report:
        monitor.show_report(period=args.period)
        return

    if args.once:
        report = monitor.check_once()
        status = "HEALTHY" if report["healthy"] else "UNHEALTHY"
        print(f"\nHealth check: {status}")
        print(f"  Processes: {sum(1 for p in report['processes'].values() if p.get('running'))}/{len(report['processes'])}")
        print(f"  Alerts sent: {report['alerts_sent']}")
        print(f"  Restarts: {report['restarts_attempted']}")
        sys.exit(0 if report["healthy"] else 1)

    if args.monitor:
        monitor.monitor(interval=args.interval)
        return

    # Default: show status
    monitor.show_status()


if __name__ == "__main__":
    main()
