"""
Process Manager — PID-based process lifecycle management.

Tracks processes via PID files, checks liveness, and handles
restart with exponential backoff. Max 3 restarts per hour.
"""

import json
import logging
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("health-monitor.process")

# Default process registry — known AI Employee components
DEFAULT_PROCESSES: Dict[str, Dict[str, Any]] = {
    "gmail-watcher": {
        "command": "uv run .claude/skills/gmail-watcher/gmail_watcher.py --vault-path {vault} --monitor",
        "max_restarts": 3,
    },
    "whatsapp-watcher": {
        "command": "uv run .claude/skills/whatsapp-watcher/whatsapp_watcher.py --vault-path {vault} --monitor",
        "max_restarts": 3,
    },
    "filesystem-watcher": {
        "command": "uv run .claude/skills/filesystem-watcher/filesystem_watcher.py --vault-path {vault} --watch",
        "max_restarts": 3,
    },
    "approval-manager": {
        "command": "uv run .claude/skills/approval-manager/approval_manager.py --vault-path {vault} --monitor",
        "max_restarts": 3,
    },
    "vault-sync": {
        "command": "uv run .claude/skills/vault-sync/vault_sync.py --vault-path {vault} --watch",
        "max_restarts": 3,
    },
}


class ProcessManager:
    """
    Manages process lifecycle using PID files.

    PID files stored in /tmp/ai-employee/{name}.pid.
    Restart history logged to vault Logs/restart_history.json.
    """

    def __init__(self, vault_path: str, project_root: str = ".") -> None:
        self.vault_path = Path(vault_path).resolve()
        self.project_root = Path(project_root).resolve()
        self.pid_dir = Path("/tmp/ai-employee")
        self.pid_dir.mkdir(parents=True, exist_ok=True)

        self.logs_dir = self.vault_path / "Logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.restart_history_path = self.logs_dir / "restart_history.json"
        self.restart_history: List[Dict[str, Any]] = self._load_restart_history()

        # Load process registry
        self.processes: Dict[str, Dict[str, Any]] = self._load_registry()

    # ------------------------------------------------------------------
    # Registry
    # ------------------------------------------------------------------
    def _load_registry(self) -> Dict[str, Dict[str, Any]]:
        """Load process registry from config or use defaults."""
        config_path = self.vault_path / "config" / "processes.yaml"
        registry = dict(DEFAULT_PROCESSES)

        if config_path.exists():
            try:
                import yaml

                data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "processes" in data:
                    for name, conf in data["processes"].items():
                        registry[name] = {
                            "command": conf.get("command", ""),
                            "max_restarts": conf.get("max_restarts", 3),
                        }
                    logger.info("Loaded %d processes from config", len(data["processes"]))
            except Exception as e:
                logger.warning("Failed to load processes config: %s", e)

        return registry

    def register_process(
        self, name: str, command: str, max_restarts: int = 3
    ) -> None:
        """Add or update a process in the registry."""
        self.processes[name] = {
            "command": command,
            "max_restarts": max_restarts,
        }
        logger.info("Registered process: %s", name)

    def unregister_process(self, name: str) -> bool:
        """Remove a process from the registry."""
        if name in self.processes:
            del self.processes[name]
            logger.info("Unregistered process: %s", name)
            return True
        return False

    def list_processes(self) -> Dict[str, Dict[str, Any]]:
        """Return the full process registry with current status."""
        result = {}
        for name in self.processes:
            status = self.check_process(name)
            result[name] = {**self.processes[name], **status}
        return result

    # ------------------------------------------------------------------
    # PID file operations
    # ------------------------------------------------------------------
    def _pid_file(self, name: str) -> Path:
        """Get PID file path for a process."""
        return self.pid_dir / f"{name}.pid"

    def _read_pid(self, name: str) -> Optional[int]:
        """Read PID from file. Returns None if not found."""
        pid_file = self._pid_file(name)
        if not pid_file.exists():
            return None
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            return pid
        except (ValueError, OSError):
            return None

    def _write_pid(self, name: str, pid: int) -> None:
        """Write PID to file."""
        self._pid_file(name).write_text(str(pid), encoding="utf-8")

    def _remove_pid(self, name: str) -> None:
        """Remove PID file."""
        pid_file = self._pid_file(name)
        if pid_file.exists():
            pid_file.unlink()

    # ------------------------------------------------------------------
    # Process checks
    # ------------------------------------------------------------------
    def check_process(self, name: str) -> Dict[str, Any]:
        """
        Check if a process is running and responsive.

        Returns:
            {name, pid, running, responsive, uptime_seconds}
        """
        pid = self._read_pid(name)
        result: Dict[str, Any] = {
            "name": name,
            "pid": pid,
            "running": False,
            "responsive": False,
            "uptime_seconds": 0,
        }

        if pid is None:
            return result

        # Check if process exists
        try:
            # /proc/{pid} check (Linux)
            proc_dir = Path(f"/proc/{pid}")
            if proc_dir.exists():
                result["running"] = True
            else:
                # Fallback: try signal 0
                os.kill(pid, 0)
                result["running"] = True
        except (ProcessLookupError, PermissionError):
            # ProcessLookupError: PID doesn't exist
            # PermissionError: PID exists but we can't signal it (still running)
            if isinstance(pid, int):
                try:
                    os.kill(pid, 0)
                    result["running"] = True
                except ProcessLookupError:
                    pass
                except PermissionError:
                    result["running"] = True
        except OSError:
            pass

        # Check responsiveness (can we signal it?)
        if result["running"]:
            try:
                os.kill(pid, 0)
                result["responsive"] = True
            except (ProcessLookupError, PermissionError, OSError):
                pass

        # Calculate uptime from PID file mtime
        if result["running"]:
            try:
                pid_file = self._pid_file(name)
                start_time = pid_file.stat().st_mtime
                result["uptime_seconds"] = int(time.time() - start_time)
            except OSError:
                pass

        # Clean up stale PID file if process is not running
        if not result["running"] and pid is not None:
            self._remove_pid(name)
            result["pid"] = None

        return result

    def check_all(self) -> List[Dict[str, Any]]:
        """Check all registered processes."""
        return [self.check_process(name) for name in self.processes]

    # ------------------------------------------------------------------
    # Start / Stop / Restart
    # ------------------------------------------------------------------
    def start_process(self, name: str) -> Dict[str, Any]:
        """
        Start a registered process.

        Returns:
            {success, pid, message}
        """
        if name not in self.processes:
            return {"success": False, "pid": None, "message": f"Unknown process: {name}"}

        # Check if already running
        status = self.check_process(name)
        if status["running"]:
            return {
                "success": True,
                "pid": status["pid"],
                "message": f"{name} already running (PID {status['pid']})",
            }

        command = self.processes[name]["command"]
        # Substitute vault path
        command = command.replace("{vault}", str(self.vault_path))

        try:
            proc = subprocess.Popen(
                command.split(),
                cwd=str(self.project_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._write_pid(name, proc.pid)
            logger.info("Started %s (PID %d)", name, proc.pid)
            return {
                "success": True,
                "pid": proc.pid,
                "message": f"Started {name} (PID {proc.pid})",
            }
        except Exception as e:
            logger.error("Failed to start %s: %s", name, e)
            return {"success": False, "pid": None, "message": str(e)}

    def stop_process(self, name: str) -> Dict[str, Any]:
        """
        Stop a process. SIGTERM first, SIGKILL after 5s if needed.

        Returns:
            {success, message}
        """
        pid = self._read_pid(name)
        if pid is None:
            return {"success": True, "message": f"{name} not running"}

        try:
            # Try graceful shutdown
            os.kill(pid, signal.SIGTERM)
            logger.info("Sent SIGTERM to %s (PID %d)", name, pid)

            # Wait up to 5 seconds
            for _ in range(50):
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except ProcessLookupError:
                    break
            else:
                # Force kill
                try:
                    os.kill(pid, signal.SIGKILL)
                    logger.warning("Sent SIGKILL to %s (PID %d)", name, pid)
                except ProcessLookupError:
                    pass

            self._remove_pid(name)
            return {"success": True, "message": f"Stopped {name} (PID {pid})"}
        except ProcessLookupError:
            self._remove_pid(name)
            return {"success": True, "message": f"{name} already stopped"}
        except PermissionError:
            return {
                "success": False,
                "message": f"Permission denied stopping {name} (PID {pid})",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def restart_process(self, name: str) -> Dict[str, Any]:
        """
        Restart a process with backoff check.

        Returns:
            {success, pid, message, backoff_seconds}
        """
        allowed, reason = self._can_restart(name)
        if not allowed:
            logger.warning("Restart denied for %s: %s", name, reason)
            return {
                "success": False,
                "pid": None,
                "message": f"Restart denied: {reason}",
                "backoff_seconds": 0,
            }

        # Calculate backoff delay
        recent = self._recent_restarts(name, hours=1)
        backoff_delays = [5, 15, 45]
        delay = backoff_delays[min(len(recent), len(backoff_delays) - 1)]

        # Stop existing
        stop_result = self.stop_process(name)
        if not stop_result["success"]:
            return {
                "success": False,
                "pid": None,
                "message": f"Failed to stop: {stop_result['message']}",
                "backoff_seconds": 0,
            }

        # Backoff delay
        if delay > 0 and len(recent) > 0:
            logger.info("Backoff: waiting %ds before restarting %s", delay, name)
            time.sleep(delay)

        # Start
        start_result = self.start_process(name)

        # Record restart
        self._record_restart(name, start_result["success"])

        return {
            "success": start_result["success"],
            "pid": start_result.get("pid"),
            "message": start_result["message"],
            "backoff_seconds": delay if len(recent) > 0 else 0,
        }

    # ------------------------------------------------------------------
    # Restart budget
    # ------------------------------------------------------------------
    def _can_restart(self, name: str) -> Tuple[bool, str]:
        """
        Check if a restart is allowed (max 3 per hour).

        Returns:
            (allowed, reason)
        """
        if name not in self.processes:
            return False, f"Unknown process: {name}"

        max_restarts = self.processes[name].get("max_restarts", 3)
        recent = self._recent_restarts(name, hours=1)

        if len(recent) >= max_restarts:
            return False, (
                f"Max restarts ({max_restarts}/hour) reached. "
                f"Last restart: {recent[-1].get('timestamp', 'unknown')}. "
                "Manual intervention required."
            )

        return True, "OK"

    def _recent_restarts(self, name: str, hours: int = 1) -> List[Dict[str, Any]]:
        """Get restart events for a process within the last N hours."""
        cutoff = time.time() - (hours * 3600)
        return [
            r
            for r in self.restart_history
            if r.get("process") == name and r.get("epoch", 0) > cutoff
        ]

    def _record_restart(self, name: str, success: bool) -> None:
        """Record a restart event."""
        now = datetime.now(timezone.utc)
        entry = {
            "process": name,
            "timestamp": now.isoformat(),
            "epoch": time.time(),
            "success": success,
        }
        self.restart_history.append(entry)
        self._save_restart_history()

    # ------------------------------------------------------------------
    # Restart history persistence
    # ------------------------------------------------------------------
    def _load_restart_history(self) -> List[Dict[str, Any]]:
        """Load restart history from JSON file."""
        if not self.restart_history_path.exists():
            return []
        try:
            data = json.loads(self.restart_history_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load restart history: %s", e)
        return []

    def _save_restart_history(self) -> None:
        """Save restart history to JSON file. Keep last 500 entries."""
        try:
            # Trim to last 500 entries
            history = self.restart_history[-500:]
            self.restart_history_path.write_text(
                json.dumps(history, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error("Failed to save restart history: %s", e)

    # ------------------------------------------------------------------
    # Uptime formatting
    # ------------------------------------------------------------------
    @staticmethod
    def format_uptime(seconds: int) -> str:
        """Format seconds into human-readable uptime string."""
        if seconds <= 0:
            return "not running"

        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or not parts:
            parts.append(f"{minutes}m")

        return " ".join(parts)
