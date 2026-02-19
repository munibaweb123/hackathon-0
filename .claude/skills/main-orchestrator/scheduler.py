"""
Scheduler — lightweight cron-based task scheduler.

Parses cron expressions from config and runs due jobs via subprocess.
No APScheduler dependency — pure stdlib implementation.
"""

import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("orchestrator.scheduler")


class Scheduler:
    """
    Simple cron scheduler that checks schedules each orchestrator cycle.

    Parses standard 5-field cron expressions (minute hour day month weekday).
    Supports * wildcard and */N step syntax.
    Tracks last_run to prevent duplicate execution within the same minute.
    """

    def __init__(
        self,
        schedules_config: Dict[str, Dict[str, Any]],
        vault_path: str,
        project_root: str = ".",
    ) -> None:
        self.vault_path = str(Path(vault_path).resolve())
        self.project_root = str(Path(project_root).resolve())
        self.schedules: Dict[str, Dict[str, Any]] = {}

        # Parse schedule configs
        for name, conf in schedules_config.items():
            if not conf.get("enabled", True):
                continue

            cron_str = conf.get("cron", "")
            if not cron_str:
                logger.warning("Schedule '%s' has no cron expression — skipping", name)
                continue

            parsed = self._parse_cron(cron_str)
            if parsed is None:
                logger.warning("Invalid cron '%s' for schedule '%s'", cron_str, name)
                continue

            self.schedules[name] = {
                "description": conf.get("description", ""),
                "cron": cron_str,
                "cron_parsed": parsed,
                "command": conf.get("command", ""),
                "enabled": True,
                "last_run": None,
                "last_run_minute": None,  # (hour, minute) tuple to prevent re-runs
            }

        logger.info("Loaded %d schedules", len(self.schedules))

    # ------------------------------------------------------------------
    # Cron parsing
    # ------------------------------------------------------------------
    def _parse_cron(self, cron_str: str) -> Optional[Dict[str, Any]]:
        """
        Parse a 5-field cron expression.

        Format: minute hour day month weekday
        Supports: *, */N, specific values, comma-separated lists

        Returns:
            Dict with {minute, hour, day, month, weekday} field specs,
            or None if invalid.
        """
        parts = cron_str.strip().split()
        if len(parts) != 5:
            return None

        fields = ["minute", "hour", "day", "month", "weekday"]
        ranges = {
            "minute": (0, 59),
            "hour": (0, 23),
            "day": (1, 31),
            "month": (1, 12),
            "weekday": (0, 6),  # 0 = Monday (Python convention)
        }

        parsed = {}
        for i, (field, part) in enumerate(zip(fields, parts)):
            spec = self._parse_cron_field(part, ranges[field])
            if spec is None:
                return None
            parsed[field] = spec

        return parsed

    def _parse_cron_field(
        self, field_str: str, value_range: tuple
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a single cron field.

        Returns:
            {type: "any"} for *
            {type: "step", step: N} for */N
            {type: "values", values: [int, ...]} for specific values
        """
        low, high = value_range

        if field_str == "*":
            return {"type": "any"}

        if field_str.startswith("*/"):
            try:
                step = int(field_str[2:])
                if step <= 0:
                    return None
                return {"type": "step", "step": step}
            except ValueError:
                return None

        # Comma-separated values
        try:
            values = []
            for part in field_str.split(","):
                val = int(part.strip())
                if val < low or val > high:
                    return None
                values.append(val)
            return {"type": "values", "values": values}
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    def _matches(self, schedule: Dict[str, Any], now: datetime) -> bool:
        """Check if current time matches a schedule's cron expression."""
        cron = schedule["cron_parsed"]

        # Check each field
        checks = [
            self._field_matches(cron["minute"], now.minute),
            self._field_matches(cron["hour"], now.hour),
            self._field_matches(cron["day"], now.day),
            self._field_matches(cron["month"], now.month),
            self._field_matches(cron["weekday"], now.weekday()),
        ]

        return all(checks)

    def _field_matches(self, spec: Dict[str, Any], value: int) -> bool:
        """Check if a time value matches a cron field specification."""
        if spec["type"] == "any":
            return True
        elif spec["type"] == "step":
            return value % spec["step"] == 0
        elif spec["type"] == "values":
            return value in spec["values"]
        return False

    # ------------------------------------------------------------------
    # Run cycle
    # ------------------------------------------------------------------
    def check_and_run(self) -> List[str]:
        """
        Check all schedules and run any that are due.

        Called each orchestrator cycle. Prevents duplicate execution
        within the same minute.

        Returns:
            List of schedule names that were launched.
        """
        now = datetime.now()
        current_minute = (now.hour, now.minute)
        launched = []

        for name, schedule in self.schedules.items():
            if not schedule["enabled"]:
                continue

            # Skip if already run this minute
            if schedule["last_run_minute"] == current_minute:
                continue

            if self._matches(schedule, now):
                command = schedule["command"]
                if not command:
                    continue

                logger.info("Schedule '%s' triggered — running", name)
                result = self.run_job(name, command)

                schedule["last_run"] = now.isoformat()
                schedule["last_run_minute"] = current_minute

                if result["success"]:
                    logger.info("Schedule '%s' completed successfully", name)
                else:
                    logger.warning(
                        "Schedule '%s' failed: %s",
                        name,
                        result.get("error", "unknown"),
                    )

                launched.append(name)

        return launched

    def run_job(self, name: str, command: str) -> Dict[str, Any]:
        """
        Execute a scheduled job command via subprocess.

        Substitutes {vault} placeholder with vault_path.

        Returns:
            {success, output, error, exit_code}
        """
        # Substitute placeholders
        cmd = command.replace("{vault}", self.vault_path)

        try:
            proc = subprocess.run(
                cmd.split(),
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for scheduled jobs
                cwd=self.project_root,
            )

            return {
                "success": proc.returncode == 0,
                "output": proc.stdout.strip()[:500],
                "error": proc.stderr.strip()[:500] if proc.returncode != 0 else "",
                "exit_code": proc.returncode,
            }
        except subprocess.TimeoutExpired:
            logger.error("Schedule '%s' timed out (600s)", name)
            return {
                "success": False,
                "output": "",
                "error": "Timed out (600s)",
                "exit_code": -1,
            }
        except Exception as e:
            logger.error("Schedule '%s' error: %s", name, e)
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "exit_code": -1,
            }

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all schedules."""
        result = {}
        for name, schedule in self.schedules.items():
            result[name] = {
                "description": schedule["description"],
                "cron": schedule["cron"],
                "enabled": schedule["enabled"],
                "last_run": schedule["last_run"],
            }
        return result

    def show_schedules(self) -> None:
        """Print schedule status to stdout."""
        if not self.schedules:
            print("  No schedules configured.")
            return

        print(f"\n  Schedules ({len(self.schedules)}):\n")
        print(f"  {'Name':25s} {'Cron':18s} {'Last Run':22s} {'Description'}")
        print(f"  {'─' * 25} {'─' * 18} {'─' * 22} {'─' * 30}")

        for name, sched in self.schedules.items():
            last = sched["last_run"] or "never"
            if len(last) > 20:
                last = last[:19]
            print(
                f"  {name:25s} {sched['cron']:18s} {last:22s} {sched['description'][:30]}"
            )
