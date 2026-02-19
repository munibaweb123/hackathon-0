# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
Notification Router — configurable notification channels for the AI Employee.

Routes critical alerts and notifications to multiple channels:
- Vault file (default, always active) — writes to Needs_Action/
- Email (optional) — via email-sender-mcp if configured
- Dashboard (optional) — writes to Dashboard.md status section

Supports per-severity routing and channel configuration via YAML.

Part of Phase 11 (T058) of the Platinum Tier AI Employee.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# Default channel config
DEFAULT_CONFIG = {
    "channels": {
        "vault_file": {
            "enabled": True,
            "path": "Needs_Action/",
            "severity_filter": ["critical", "warning", "info"],
        },
        "dashboard": {
            "enabled": True,
            "severity_filter": ["critical", "warning"],
        },
        "email": {
            "enabled": False,
            "recipient": None,
            "severity_filter": ["critical"],
        },
    },
    "dedup_cooldown_minutes": 30,
}


class NotificationRouter:
    """
    Routes notifications to configured channels based on severity.

    Usage:
        router = NotificationRouter(vault_path)
        router.notify("critical", "disk", "Disk space at 95%")
    """

    def __init__(
        self,
        vault_path: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.vault = Path(vault_path).resolve()
        self.config = config or self._load_config()
        self.channels = self.config.get("channels", DEFAULT_CONFIG["channels"])
        self._sent_log: List[Dict[str, Any]] = []

    def notify(
        self,
        severity: str,
        component: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Route a notification to all configured channels.

        Args:
            severity: critical | warning | info
            component: Source component name
            message: Human-readable notification message
            details: Optional metadata

        Returns:
            Dict with delivery results per channel.
        """
        results: Dict[str, Any] = {"severity": severity, "component": component}

        for channel_name, channel_cfg in self.channels.items():
            if not channel_cfg.get("enabled", False):
                results[channel_name] = {"skipped": "disabled"}
                continue

            severity_filter = channel_cfg.get("severity_filter", [])
            if severity_filter and severity not in severity_filter:
                results[channel_name] = {"skipped": "severity_filtered"}
                continue

            try:
                if channel_name == "vault_file":
                    path = self._send_vault_file(severity, component, message, details, channel_cfg)
                    results[channel_name] = {"sent": True, "path": path}
                elif channel_name == "dashboard":
                    self._send_dashboard(severity, component, message)
                    results[channel_name] = {"sent": True}
                elif channel_name == "email":
                    self._send_email(severity, component, message, details, channel_cfg)
                    results[channel_name] = {"sent": True}
                else:
                    results[channel_name] = {"skipped": "unknown_channel"}
            except Exception as e:
                logger.error("Channel %s failed: %s", channel_name, e)
                results[channel_name] = {"error": str(e)}

        # Log notification
        self._log_notification(severity, component, message, results)
        return results

    def _send_vault_file(
        self,
        severity: str,
        component: str,
        message: str,
        details: Optional[Dict[str, Any]],
        config: Dict[str, Any],
    ) -> str:
        """Write notification as a markdown file in the vault."""
        base_path = config.get("path", "Needs_Action/")
        out_dir = self.vault / base_path
        out_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y%m%d_%H%M%S")
        filename = f"NOTIFY_{severity.upper()}_{component}_{ts}.md"
        filepath = out_dir / filename

        fm = {
            "type": "notification",
            "severity": severity,
            "component": component,
            "created": now.isoformat(),
        }
        if details:
            fm["details"] = details

        body = f"# Notification: {component}\n\n**Severity:** {severity.upper()}\n\n{message}\n"

        content = f"---\n{yaml.dump(fm, default_flow_style=False, sort_keys=False)}---\n\n{body}"
        filepath.write_text(content, encoding="utf-8")
        return str(filepath.relative_to(self.vault))

    def _send_dashboard(self, severity: str, component: str, message: str) -> None:
        """Append notification to Dashboard.md alerts section."""
        dashboard = self.vault / "Dashboard.md"
        if not dashboard.exists():
            return

        now = datetime.now(timezone.utc).strftime("%H:%M UTC")
        icon = {"critical": "🔴", "warning": "🟡", "info": "🟢"}.get(severity, "⚪")
        line = f"| {icon} {severity} | {component} | {message[:80]} | {now} |"

        text = dashboard.read_text(encoding="utf-8")

        # Find or create Alerts section
        marker = "## Recent Alerts"
        if marker not in text:
            text += f"\n\n{marker}\n\n| Status | Component | Message | Time |\n|--------|-----------|---------|------|\n"

        # Insert new alert line after the table header
        parts = text.split(marker, 1)
        header_and_table = parts[1]
        # Find the last table row
        lines = header_and_table.split("\n")
        insert_idx = 0
        for i, l in enumerate(lines):
            if l.startswith("|"):
                insert_idx = i + 1
        lines.insert(insert_idx, line)
        text = parts[0] + marker + "\n".join(lines)

        dashboard.write_text(text, encoding="utf-8")

    def _send_email(
        self,
        severity: str,
        component: str,
        message: str,
        details: Optional[Dict[str, Any]],
        config: Dict[str, Any],
    ) -> None:
        """
        Send notification via email (placeholder — requires email-sender-mcp).

        Creates a draft email notification file that the email-sender-mcp
        can pick up and send.
        """
        recipient = config.get("recipient")
        if not recipient:
            logger.warning("Email channel enabled but no recipient configured")
            return

        # Write email draft for email-sender-mcp to pick up
        drafts_dir = self.vault / "Drafts" / "email"
        drafts_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y%m%d_%H%M%S")
        filename = f"notification-email-{ts}.md"

        fm = {
            "type": "notification-email",
            "to": recipient,
            "subject": f"[{severity.upper()}] AI Employee Alert: {component}",
            "created-at": now.isoformat(),
            "auto-send": True,
        }

        body = f"# Alert: {component}\n\n{message}\n"
        if details:
            body += "\n## Details\n\n"
            for k, v in details.items():
                body += f"- **{k}:** {v}\n"

        content = f"---\n{yaml.dump(fm, default_flow_style=False, sort_keys=False)}---\n\n{body}"
        (drafts_dir / filename).write_text(content, encoding="utf-8")

    def _load_config(self) -> Dict[str, Any]:
        """Load notification config from vault config directory."""
        config_file = self.vault / "config" / "notifications.yaml"
        if config_file.exists():
            try:
                return yaml.safe_load(config_file.read_text(encoding="utf-8")) or DEFAULT_CONFIG
            except Exception:
                pass
        return DEFAULT_CONFIG.copy()

    def _log_notification(
        self,
        severity: str,
        component: str,
        message: str,
        results: Dict[str, Any],
    ) -> None:
        """Log notification to Logs/notifications.json."""
        logs_dir = self.vault / "Logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / "notifications.json"

        entries: List[Dict[str, Any]] = []
        if log_file.exists():
            try:
                entries = json.loads(log_file.read_text(encoding="utf-8"))
                if not isinstance(entries, list):
                    entries = []
            except (json.JSONDecodeError, OSError):
                entries = []

        entries.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": severity,
            "component": component,
            "message": message[:200],
            "channels": {k: v for k, v in results.items() if k not in ("severity", "component")},
        })

        # Keep last 500 entries
        entries = entries[-500:]
        log_file.write_text(json.dumps(entries, indent=2, default=str), encoding="utf-8")
