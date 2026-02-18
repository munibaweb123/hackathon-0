"""
Notification Sender — creates notification files for pending approvals.

Generates Needs_Action/ files that email-sender-mcp or other notification
channels can pick up to alert humans about pending/expiring approvals.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class NotificationSender:
    """
    Creates notification action files for approval events.

    Notifications are written to Needs_Action/ for downstream skills
    (e.g., email-sender-mcp) to pick up and deliver.
    """

    def __init__(self, vault_path: str) -> None:
        self.vault = Path(vault_path).resolve()
        self.needs_dir = self.vault / "Needs_Action"
        self.needs_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.vault / "Logs" / "approval_notifications.json"
        (self.vault / "Logs").mkdir(parents=True, exist_ok=True)

    def notify_pending(self, approval_data: Dict[str, Any]) -> Optional[str]:
        """Create notification for a new pending approval."""
        meta = approval_data.get("metadata", {})
        approval_id = meta.get("id", "unknown")

        if self._already_notified(approval_id, "pending"):
            return None

        now = datetime.now(timezone.utc)
        action_type = meta.get("action_type", "unknown")
        risk_level = meta.get("risk_level", "medium")
        expires = meta.get("expires", "")
        risk_emoji = {"low": "LOW", "medium": "MEDIUM", "high": "HIGH"}.get(risk_level, "MEDIUM")

        filename = f"NOTIFY_APPROVAL_PENDING_{approval_id[:8]}.md"
        content = f"""---
type: notification
category: approval_pending
approval_id: "{approval_id}"
created: {now.isoformat()}
priority: {"high" if risk_level == "high" else "normal"}
---

# Approval Pending: {action_type} ({risk_emoji} risk)

A new approval request requires your attention.

| Field | Value |
|-------|-------|
| Action | {action_type} |
| Risk Level | {risk_emoji} |
| Approval ID | {approval_id[:8]} |
| Expires | {expires} |

## How to Approve

Move the file from `pending-approval/` to `Approved/` in the vault.

## How to Reject

Move the file from `pending-approval/` to `Rejected/` in the vault.

---
_Notification generated at {now.strftime('%Y-%m-%d %H:%M UTC')}_
"""

        file_path = self.needs_dir / filename
        file_path.write_text(content, encoding="utf-8")
        self._record_notification(approval_id, "pending")
        return str(file_path)

    def notify_expiring_soon(
        self, approval_data: Dict[str, Any], hours_remaining: float
    ) -> Optional[str]:
        """Create urgent notification for approval expiring soon."""
        meta = approval_data.get("metadata", {})
        approval_id = meta.get("id", "unknown")

        if self._already_notified(approval_id, "expiring_soon"):
            return None

        now = datetime.now(timezone.utc)
        action_type = meta.get("action_type", "unknown")

        filename = f"NOTIFY_APPROVAL_EXPIRING_{approval_id[:8]}.md"
        content = f"""---
type: notification
category: approval_expiring
approval_id: "{approval_id}"
created: {now.isoformat()}
priority: high
---

# URGENT: Approval Expiring in {hours_remaining:.1f}h

The following approval will expire soon and requires immediate attention.

| Field | Value |
|-------|-------|
| Action | {action_type} |
| Approval ID | {approval_id[:8]} |
| Time Remaining | ~{hours_remaining:.1f} hours |

**Action required:** Approve or reject before expiry.

---
_Notification generated at {now.strftime('%Y-%m-%d %H:%M UTC')}_
"""

        file_path = self.needs_dir / filename
        file_path.write_text(content, encoding="utf-8")
        self._record_notification(approval_id, "expiring_soon")
        return str(file_path)

    def notify_expired(self, approval_data: Dict[str, Any]) -> Optional[str]:
        """Create notification that approval has expired."""
        meta = approval_data.get("metadata", {})
        approval_id = meta.get("id", "unknown")

        if self._already_notified(approval_id, "expired"):
            return None

        now = datetime.now(timezone.utc)
        action_type = meta.get("action_type", "unknown")

        filename = f"NOTIFY_APPROVAL_EXPIRED_{approval_id[:8]}.md"
        content = f"""---
type: notification
category: approval_expired
approval_id: "{approval_id}"
created: {now.isoformat()}
priority: normal
---

# Approval Expired: {action_type}

The following approval request has expired without a decision.

| Field | Value |
|-------|-------|
| Action | {action_type} |
| Approval ID | {approval_id[:8]} |
| Status | Expired (auto-rejected) |

The request has been moved to Rejected/ with expiry reason.

---
_Notification generated at {now.strftime('%Y-%m-%d %H:%M UTC')}_
"""

        file_path = self.needs_dir / filename
        file_path.write_text(content, encoding="utf-8")
        self._record_notification(approval_id, "expired")
        return str(file_path)

    def notify_bulk_summary(self, pending_list: List[Dict[str, Any]]) -> Optional[str]:
        """Create a single digest notification with all pending approvals."""
        if not pending_list:
            return None

        now = datetime.now(timezone.utc)
        filename = f"NOTIFY_APPROVAL_DIGEST_{now.strftime('%Y%m%d_%H%M')}.md"

        rows = []
        for item in pending_list:
            meta = item.get("metadata", {})
            aid = meta.get("id", "?")[:8]
            action = meta.get("action_type", "?")
            risk = meta.get("risk_level", "?")
            expires = meta.get("expires", "?")
            rows.append(f"| {aid} | {action} | {risk} | {expires} |")

        table = "\n".join(rows)
        high_risk = sum(
            1 for p in pending_list
            if p.get("metadata", {}).get("risk_level") == "high"
        )

        content = f"""---
type: notification
category: approval_digest
created: {now.isoformat()}
priority: {"high" if high_risk > 0 else "normal"}
pending_count: {len(pending_list)}
---

# Approval Digest: {len(pending_list)} Pending

You have {len(pending_list)} approval request(s) waiting for review.
{"**" + str(high_risk) + " HIGH RISK** items require immediate attention." if high_risk else ""}

| ID | Action | Risk | Expires |
|----|--------|------|---------|
{table}

## Instructions

Review each approval in `pending-approval/` and move to `Approved/` or `Rejected/`.

---
_Digest generated at {now.strftime('%Y-%m-%d %H:%M UTC')}_
"""

        file_path = self.needs_dir / filename
        file_path.write_text(content, encoding="utf-8")
        return str(file_path)

    # ------------------------------------------------------------------
    # Dedup
    # ------------------------------------------------------------------
    def _already_notified(self, approval_id: str, notification_type: str) -> bool:
        """Check if we already sent this notification type for this approval."""
        log = self._read_log()
        key = f"{approval_id}:{notification_type}"
        return key in {f"{e['approval_id']}:{e['type']}" for e in log}

    def _record_notification(self, approval_id: str, notification_type: str) -> None:
        """Record that we sent a notification."""
        log = self._read_log()
        log.append({
            "approval_id": approval_id,
            "type": notification_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self.log_file.write_text(
            json.dumps(log, indent=2, default=str), encoding="utf-8"
        )

    def _read_log(self) -> list:
        """Read the notification log."""
        if not self.log_file.exists():
            return []
        try:
            return json.loads(self.log_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return []
