"""
Alert Sender — creates health alert notifications in the vault.

Follows the same pattern as approval-manager's NotificationSender:
creates Needs_Action/ markdown files with YAML frontmatter and
deduplicates via a JSON log with configurable cooldown.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("health-monitor.alerts")


class AlertSender:
    """
    Sends health alerts by creating files in Needs_Action/.

    Deduplicates alerts using Logs/health_alerts.json with a
    configurable cooldown period (default 30 minutes).
    """

    def __init__(self, vault_path: str, cooldown_minutes: int = 30) -> None:
        self.vault_path = Path(vault_path)
        self.needs_action_dir = self.vault_path / "Needs_Action"
        self.needs_action_dir.mkdir(parents=True, exist_ok=True)

        self.logs_dir = self.vault_path / "Logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.alerts_log_path = self.logs_dir / "health_alerts.json"
        self.cooldown_minutes = cooldown_minutes

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def send_alert(
        self,
        severity: str,
        component: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Create a health alert file in Needs_Action/.

        Args:
            severity: critical | warning | info
            component: Component name (e.g., "gmail-watcher", "disk")
            message: Human-readable alert message
            details: Optional additional details dict

        Returns:
            Path to created alert file, or None if deduped/suppressed.
        """
        alert_type = f"{severity}_{component}"

        # Dedup check
        if self._already_alerted(component, alert_type):
            logger.debug("Alert suppressed (cooldown): %s %s", severity, component)
            return None

        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        filename = f"ALERT_{severity.upper()}_{component}_{timestamp}.md"
        filepath = self.needs_action_dir / filename

        # Build YAML frontmatter
        frontmatter_lines = [
            "---",
            "type: health_alert",
            f"severity: {severity}",
            f"component: {component}",
            f"created: {now.isoformat()}",
            f"timestamp: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "auto_resolved: false",
            "---",
        ]

        # Build body
        body_lines = [
            f"# Health Alert: {component}",
            "",
            f"**Severity:** {severity.upper()}",
            f"**Component:** {component}",
            f"**Time:** {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            f"## Message",
            "",
            message,
        ]

        if details:
            body_lines.extend(["", "## Details", ""])
            for key, value in details.items():
                body_lines.append(f"- **{key}:** {value}")

        body_lines.extend([
            "",
            "## Action Required",
            "",
        ])

        if severity == "critical":
            body_lines.append(
                "This is a **critical** alert. The component may be down or "
                "a resource is exhausted. Immediate attention required."
            )
        elif severity == "warning":
            body_lines.append(
                "This is a **warning** alert. The component is degraded or "
                "approaching resource limits. Monitor closely."
            )
        else:
            body_lines.append(
                "This is an **informational** alert. No immediate action required."
            )

        content = "\n".join(frontmatter_lines) + "\n\n" + "\n".join(body_lines) + "\n"
        filepath.write_text(content, encoding="utf-8")

        # Log the alert
        self._log_alert({
            "timestamp": now.isoformat(),
            "epoch": time.time(),
            "severity": severity,
            "component": component,
            "message": message,
            "file": filename,
            "resolved": False,
        })

        logger.info("Alert sent: %s %s → %s", severity, component, filename)
        return str(filepath)

    def clear_alert(self, component: str) -> None:
        """
        Mark alerts for a component as auto-resolved in the log.

        Does NOT remove the Needs_Action/ file — that's handled by
        the approval/orchestrator pipeline.
        """
        alerts = self._load_alerts_log()
        updated = False

        for alert in alerts:
            if alert.get("component") == component and not alert.get("resolved"):
                alert["resolved"] = True
                alert["resolved_at"] = datetime.now(timezone.utc).isoformat()
                updated = True

        if updated:
            self._save_alerts_log(alerts)
            logger.info("Cleared alerts for component: %s", component)

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all unresolved alerts."""
        alerts = self._load_alerts_log()
        return [a for a in alerts if not a.get("resolved", False)]

    def get_alert_history(
        self, component: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get alert history, optionally filtered by component."""
        alerts = self._load_alerts_log()
        if component:
            alerts = [a for a in alerts if a.get("component") == component]
        return alerts[-limit:]

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------
    def _already_alerted(self, component: str, alert_type: str) -> bool:
        """
        Check if an alert was already sent within the cooldown period.

        Prevents alert fatigue for persistent issues.
        """
        cutoff = time.time() - (self.cooldown_minutes * 60)
        alerts = self._load_alerts_log()

        for alert in reversed(alerts):
            if (
                alert.get("component") == component
                and not alert.get("resolved", False)
                and alert.get("epoch", 0) > cutoff
            ):
                return True

        return False

    # ------------------------------------------------------------------
    # Log persistence
    # ------------------------------------------------------------------
    def _load_alerts_log(self) -> List[Dict[str, Any]]:
        """Load alerts log from JSON file."""
        if not self.alerts_log_path.exists():
            return []
        try:
            data = json.loads(self.alerts_log_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load alerts log: %s", e)
        return []

    def _save_alerts_log(self, alerts: List[Dict[str, Any]]) -> None:
        """Save alerts log. Keep last 1000 entries."""
        try:
            trimmed = alerts[-1000:]
            self.alerts_log_path.write_text(
                json.dumps(trimmed, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error("Failed to save alerts log: %s", e)

    def _log_alert(self, alert_data: Dict[str, Any]) -> None:
        """Append a single alert entry to the log."""
        alerts = self._load_alerts_log()
        alerts.append(alert_data)
        self._save_alerts_log(alerts)
