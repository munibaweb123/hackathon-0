# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "jinja2>=3.1.0",
#     "python-dotenv>=1.0.0",
#     "pyyaml>=6.0",
# ]
# ///
"""
Approval Manager — unified HITL approval workflow orchestrator.

Monitors pending-approval/, Approved/, and Rejected/ folders. Processes
approved actions via per-type handlers, handles expiration, notifications,
bulk operations, delegation, and generates reports.

Usage with UV (recommended):
    uv run approval_manager.py --vault-path ../../obsidian-vault --once
    uv run approval_manager.py --vault-path ../../obsidian-vault --pending
    uv run approval_manager.py --vault-path ../../obsidian-vault --monitor
"""

import argparse
import json
import logging
import re
import shutil
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))
from approval_handlers import ALL_HANDLERS
from notification_sender import NotificationSender

logger = logging.getLogger("approval-manager")

# Default expiry warning threshold (hours before expiry to send "expiring soon")
EXPIRY_WARNING_HOURS = 4.0


class ApprovalManager:
    """
    Unified orchestrator for HITL approval workflows.

    Monitors vault approval folders, routes approved actions to handlers,
    processes rejections and expirations, sends notifications, and
    generates reports.
    """

    def __init__(self, vault_path: str) -> None:
        self.vault = Path(vault_path).resolve()
        self.pending_dir = self.vault / "pending-approval"
        self.approved_dir = self.vault / "Approved"
        self.rejected_dir = self.vault / "Rejected"
        self.done_dir = self.vault / "Done"
        self.logs_dir = self.vault / "Logs"
        self.reports_dir = self.vault / "Reports"

        # Ensure directories exist
        for d in [self.pending_dir, self.approved_dir, self.rejected_dir,
                  self.done_dir, self.logs_dir, self.reports_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.handlers = ALL_HANDLERS
        self.notifier = NotificationSender(str(self.vault))

        # Track what we've already processed to avoid duplicates in poll loop
        self._seen_approved: set = set()
        self._seen_rejected: set = set()

        # Graceful shutdown
        self.running = False

    # ------------------------------------------------------------------
    # Core: single poll cycle
    # ------------------------------------------------------------------
    def process_once(self) -> Dict[str, Any]:
        """Run a single poll cycle: check all folders and process."""
        results = {
            "pending": 0,
            "approved_processed": 0,
            "rejected_processed": 0,
            "expired": 0,
            "notifications_sent": 0,
            "errors": [],
        }

        # 1. Check expired approvals first
        expired = self.check_expired()
        results["expired"] = len(expired)

        # 2. Process approved files
        approved = self.check_approved()
        results["approved_processed"] = len(approved)

        # 3. Process rejected files
        rejected = self.check_rejected()
        results["rejected_processed"] = len(rejected)

        # 4. Check pending and send notifications
        pending = self.check_pending()
        results["pending"] = len(pending)

        # 5. Update dashboard
        self.update_dashboard()

        return results

    # ------------------------------------------------------------------
    # Monitor: continuous poll loop
    # ------------------------------------------------------------------
    def monitor(self, poll_interval: int = 30) -> None:
        """Continuous monitoring loop."""
        self.running = True
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        print(f"Approval Manager monitoring started (poll every {poll_interval}s)")
        print(f"  Pending:  {self.pending_dir}")
        print(f"  Approved: {self.approved_dir}")
        print(f"  Rejected: {self.rejected_dir}")
        print(f"  Press Ctrl+C to stop\n")

        while self.running:
            try:
                results = self.process_once()
                activity = (
                    results["approved_processed"]
                    + results["rejected_processed"]
                    + results["expired"]
                )
                if activity > 0:
                    logger.info(
                        f"Cycle: {results['approved_processed']} approved, "
                        f"{results['rejected_processed']} rejected, "
                        f"{results['expired']} expired, "
                        f"{results['pending']} pending"
                    )

                time.sleep(poll_interval)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Poll cycle error: {e}")
                time.sleep(5)

        print("\nApproval Manager stopped")

    def _shutdown(self, signum, frame):
        self.running = False

    # ------------------------------------------------------------------
    # Check pending approvals
    # ------------------------------------------------------------------
    def check_pending(self) -> List[Dict[str, Any]]:
        """Scan pending-approval/ for all files and return with expiry status."""
        pending = []

        for f in self.pending_dir.glob("*.md"):
            data = self._parse_approval_file(f)
            if not data:
                continue

            meta = data["metadata"]
            expires_str = meta.get("expires", "")
            hours_remaining = None

            if expires_str:
                try:
                    expires_dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    hours_remaining = (expires_dt - now).total_seconds() / 3600
                except (ValueError, TypeError):
                    pass

            data["hours_remaining"] = hours_remaining
            data["file_path"] = str(f)
            pending.append(data)

            # Send expiring-soon notification
            if hours_remaining is not None and 0 < hours_remaining <= EXPIRY_WARNING_HOURS:
                self.notifier.notify_expiring_soon(data, hours_remaining)

        return pending

    # ------------------------------------------------------------------
    # Check and process approved files
    # ------------------------------------------------------------------
    def check_approved(self) -> List[Dict[str, Any]]:
        """Scan Approved/ for files, route to handlers, archive."""
        processed = []

        for f in self.approved_dir.glob("*.md"):
            if f.name in self._seen_approved:
                continue

            data = self._parse_approval_file(f)
            if not data:
                self._seen_approved.add(f.name)
                continue

            meta = data["metadata"]
            action_type = meta.get("action_type", meta.get("action", "unknown"))
            approval_id = meta.get("id", f.stem)

            logger.info(f"Processing approved: {f.name} (action: {action_type})")

            # Route to handler
            handler = self._route_to_handler(action_type)
            if handler:
                try:
                    result = handler.execute(data, self.vault)
                    result["approval_id"] = approval_id
                    result["action_type"] = action_type
                    result["decision"] = "approved"
                    processed.append(result)

                    self._log_event({
                        "event": "approval_executed",
                        "approval_id": approval_id,
                        "action_type": action_type,
                        "success": result.get("success", False),
                        "message": result.get("message", ""),
                        "action_file": result.get("action_file"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception as e:
                    logger.error(f"Handler error for {f.name}: {e}")
                    self._log_event({
                        "event": "approval_execution_error",
                        "approval_id": approval_id,
                        "action_type": action_type,
                        "error": str(e),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
            else:
                logger.warning(f"No handler for action type: {action_type}")
                self._log_event({
                    "event": "no_handler",
                    "approval_id": approval_id,
                    "action_type": action_type,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            # Archive to Done/
            self._archive_processed(f, {"decision": "approved", "action_type": action_type})
            self._seen_approved.add(f.name)

        return processed

    # ------------------------------------------------------------------
    # Check and process rejected files
    # ------------------------------------------------------------------
    def check_rejected(self) -> List[Dict[str, Any]]:
        """Scan Rejected/ for files, log reason, archive."""
        processed = []

        for f in self.rejected_dir.glob("*.md"):
            if f.name in self._seen_rejected:
                continue

            data = self._parse_approval_file(f)
            if not data:
                self._seen_rejected.add(f.name)
                continue

            meta = data["metadata"]
            approval_id = meta.get("id", f.stem)
            action_type = meta.get("action_type", meta.get("action", "unknown"))

            # Try to extract rejection reason from body
            reason = "No reason provided"
            body = data.get("body", "")
            reason_match = re.search(r"(?:reason|rejected because)[:\s]*(.+)", body, re.IGNORECASE)
            if reason_match:
                reason = reason_match.group(1).strip()

            logger.info(f"Processing rejected: {f.name} (reason: {reason[:50]})")

            self._log_event({
                "event": "approval_rejected",
                "approval_id": approval_id,
                "action_type": action_type,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            processed.append({
                "approval_id": approval_id,
                "action_type": action_type,
                "decision": "rejected",
                "reason": reason,
            })

            # Archive to Done/
            self._archive_processed(f, {"decision": "rejected", "reason": reason})
            self._seen_rejected.add(f.name)

        return processed

    # ------------------------------------------------------------------
    # Expiration handling
    # ------------------------------------------------------------------
    def check_expired(self) -> List[Dict[str, Any]]:
        """Find and process expired approvals in pending-approval/."""
        expired = []
        now = datetime.now(timezone.utc)

        for f in self.pending_dir.glob("*.md"):
            data = self._parse_approval_file(f)
            if not data:
                continue

            meta = data["metadata"]
            expires_str = meta.get("expires", "")
            if not expires_str:
                continue

            try:
                expires_dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            if now >= expires_dt:
                approval_id = meta.get("id", f.stem)
                action_type = meta.get("action_type", "unknown")

                logger.info(f"Expiring: {f.name}")

                # Move to Rejected/ with expiry annotation
                self._expire_approval(f, data)

                self.notifier.notify_expired(data)

                self._log_event({
                    "event": "approval_expired",
                    "approval_id": approval_id,
                    "action_type": action_type,
                    "expired_at": now.isoformat(),
                    "original_expiry": expires_str,
                    "timestamp": now.isoformat(),
                })

                expired.append({
                    "approval_id": approval_id,
                    "action_type": action_type,
                    "expired_at": now.isoformat(),
                })

        return expired

    def _expire_approval(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Move expired approval to Rejected/ with expiry annotation."""
        now = datetime.now(timezone.utc)
        content = file_path.read_text(encoding="utf-8")

        # Add expiry note to the file
        expiry_note = f"\n\n---\n**AUTO-EXPIRED** at {now.strftime('%Y-%m-%d %H:%M UTC')} — no decision within expiry window.\n"
        content += expiry_note

        dest = self.rejected_dir / file_path.name
        dest.write_text(content, encoding="utf-8")
        file_path.unlink()

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------
    def approve_bulk(self, approval_ids: List[str], approver: str = "bulk") -> List[Dict[str, Any]]:
        """Move multiple approval files to Approved/."""
        results = []
        for aid in approval_ids:
            file_path = self._find_approval_by_id(aid)
            if not file_path:
                results.append({"approval_id": aid, "success": False, "message": "Not found"})
                continue

            # Add approver annotation
            content = file_path.read_text(encoding="utf-8")
            content += f"\n\n---\n**Approved by:** {approver} at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"

            dest = self.approved_dir / file_path.name
            dest.write_text(content, encoding="utf-8")
            file_path.unlink()

            self._log_event({
                "event": "bulk_approved",
                "approval_id": aid,
                "approver": approver,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            results.append({"approval_id": aid, "success": True, "message": "Approved"})
            print(f"  Approved: {aid}")

        return results

    def reject_bulk(
        self, approval_ids: List[str], reason: str, approver: str = "bulk"
    ) -> List[Dict[str, Any]]:
        """Move multiple approval files to Rejected/."""
        results = []
        for aid in approval_ids:
            file_path = self._find_approval_by_id(aid)
            if not file_path:
                results.append({"approval_id": aid, "success": False, "message": "Not found"})
                continue

            content = file_path.read_text(encoding="utf-8")
            content += f"\n\n---\n**Rejected by:** {approver} at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n**Reason:** {reason}\n"

            dest = self.rejected_dir / file_path.name
            dest.write_text(content, encoding="utf-8")
            file_path.unlink()

            self._log_event({
                "event": "bulk_rejected",
                "approval_id": aid,
                "approver": approver,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            results.append({"approval_id": aid, "success": True, "message": "Rejected"})
            print(f"  Rejected: {aid}")

        return results

    # ------------------------------------------------------------------
    # Delegation
    # ------------------------------------------------------------------
    def delegate(self, approval_id: str, delegate_to: str) -> bool:
        """Add delegation to an approval file."""
        file_path = self._find_approval_by_id(approval_id)
        if not file_path:
            print(f"Approval {approval_id} not found")
            return False

        content = file_path.read_text(encoding="utf-8")

        # Add delegated_to to frontmatter
        if "---" in content:
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                frontmatter += f'\ndelegated_to: "{delegate_to}"\n'
                content = f"---{frontmatter}---{parts[2]}"

        content += f"\n\n---\n**Delegated to:** {delegate_to} at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"

        file_path.write_text(content, encoding="utf-8")

        # Create notification for delegate
        data = self._parse_approval_file(file_path)
        if data:
            self.notifier.notify_pending(data)

        self._log_event({
            "event": "approval_delegated",
            "approval_id": approval_id,
            "delegated_to": delegate_to,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        print(f"Approval {approval_id} delegated to {delegate_to}")
        return True

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------
    def generate_report(self, period: str = "week") -> str:
        """Generate approval summary report."""
        history = self._read_history()
        now = datetime.now(timezone.utc)

        # Filter by period
        if period == "week":
            cutoff = now - timedelta(days=7)
        elif period == "month":
            cutoff = now - timedelta(days=30)
        else:
            cutoff = datetime.min.replace(tzinfo=timezone.utc)

        filtered = []
        for event in history:
            try:
                ts = datetime.fromisoformat(event.get("timestamp", ""))
                if ts >= cutoff:
                    filtered.append(event)
            except (ValueError, TypeError):
                continue

        # Compute stats
        approved = [e for e in filtered if e.get("event") in ("approval_executed", "bulk_approved")]
        rejected = [e for e in filtered if e.get("event") in ("approval_rejected", "bulk_rejected")]
        expired = [e for e in filtered if e.get("event") == "approval_expired"]

        total_decisions = len(approved) + len(rejected) + len(expired)
        approval_rate = round(len(approved) / total_decisions * 100) if total_decisions > 0 else 0

        # Stats by action type
        type_stats: Dict[str, Dict[str, int]] = {}
        for e in filtered:
            at = e.get("action_type", "unknown")
            if at not in type_stats:
                type_stats[at] = {"approved": 0, "rejected": 0, "expired": 0}
            if e.get("event") in ("approval_executed", "bulk_approved"):
                type_stats[at]["approved"] += 1
            elif e.get("event") in ("approval_rejected", "bulk_rejected"):
                type_stats[at]["rejected"] += 1
            elif e.get("event") == "approval_expired":
                type_stats[at]["expired"] += 1

        type_rows = []
        for at, stats in sorted(type_stats.items()):
            total = stats["approved"] + stats["rejected"] + stats["expired"]
            rate = round(stats["approved"] / total * 100) if total > 0 else 0
            type_rows.append(
                f"| {at} | {stats['approved']} | {stats['rejected']} | {stats['expired']} | {rate}% |"
            )
        type_table = "\n".join(type_rows) if type_rows else "| (none) | - | - | - | - |"

        report_content = f"""---
type: approval_report
period: {period}
generated_at: {now.isoformat()}
total_decisions: {total_decisions}
approval_rate: {approval_rate}
---

# Approval Summary Report — {period.title()}

> Generated {now.strftime('%Y-%m-%d %H:%M UTC')} | Period: last {period}

## Overview

| Metric | Value |
|--------|-------|
| Total Decisions | {total_decisions} |
| Approved | {len(approved)} |
| Rejected | {len(rejected)} |
| Expired | {len(expired)} |
| Approval Rate | {approval_rate}% |

## By Action Type

| Action Type | Approved | Rejected | Expired | Rate |
|-------------|----------|----------|---------|------|
{type_table}

## Recent Activity

"""
        for event in filtered[-10:]:
            ts = event.get("timestamp", "?")[:19]
            evt = event.get("event", "?")
            aid = event.get("approval_id", "?")[:8]
            report_content += f"- `{ts}` **{evt}** — {aid}\n"

        report_content += f"\n---\n_Generated by Approval Manager_\n"

        filename = f"Approval_Summary_{now.strftime('%Y-%m-%d')}.md"
        report_path = self.reports_dir / filename
        report_path.write_text(report_content, encoding="utf-8")

        print(f"Report generated: {report_path}")
        return str(report_path)

    def show_history(
        self,
        action_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> None:
        """Query and display approval history."""
        history = self._read_history()

        if action_type:
            history = [e for e in history if e.get("action_type") == action_type]
        if status:
            event_map = {
                "approved": ("approval_executed", "bulk_approved"),
                "rejected": ("approval_rejected", "bulk_rejected"),
                "expired": ("approval_expired",),
            }
            events = event_map.get(status, ())
            history = [e for e in history if e.get("event") in events]

        history = history[-limit:]

        if not history:
            print("No matching history records")
            return

        print(f"\nApproval History ({len(history)} records):\n")
        print(f"  {'Timestamp':<20} {'Event':<25} {'ID':<10} {'Type':<15}")
        print(f"  {'─'*20} {'─'*25} {'─'*10} {'─'*15}")

        for e in history:
            ts = e.get("timestamp", "?")[:19]
            evt = e.get("event", "?")
            aid = e.get("approval_id", "?")[:8]
            at = e.get("action_type", "?")
            print(f"  {ts:<20} {evt:<25} {aid:<10} {at:<15}")

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def update_dashboard(self) -> None:
        """Write approval status section to Dashboard.md."""
        dashboard = self.vault / "Dashboard.md"
        now = datetime.now(timezone.utc)

        # Count pending
        pending_count = sum(1 for _ in self.pending_dir.glob("*.md"))

        # Count expiring soon
        expiring_soon = 0
        for f in self.pending_dir.glob("*.md"):
            data = self._parse_approval_file(f)
            if not data:
                continue
            meta = data.get("metadata", {})
            expires_str = meta.get("expires", "")
            if expires_str:
                try:
                    expires_dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                    hrs = (expires_dt - now).total_seconds() / 3600
                    if 0 < hrs <= EXPIRY_WARNING_HOURS:
                        expiring_soon += 1
                except (ValueError, TypeError):
                    pass

        # Recent decisions from history
        history = self._read_history()
        recent = history[-5:]
        recent_lines = []
        for e in recent:
            ts = e.get("timestamp", "?")[:16]
            evt = e.get("event", "?").replace("approval_", "").replace("bulk_", "")
            aid = e.get("approval_id", "?")[:8]
            recent_lines.append(f"- `{ts}` {evt}: {aid}")
        recent_text = "\n".join(recent_lines) if recent_lines else "- (none)"

        section = f"""
## Approval Manager Status

| Metric | Value |
|--------|-------|
| Pending Approvals | {pending_count} |
| Expiring Soon (<{EXPIRY_WARNING_HOURS:.0f}h) | {expiring_soon} |
| Last Updated | {now.strftime('%Y-%m-%d %H:%M')} UTC |

### Recent Decisions

{recent_text}

"""

        if dashboard.exists():
            content = dashboard.read_text(encoding="utf-8")
            marker = "## Approval Manager Status"
            if marker in content:
                start_idx = content.index(marker)
                rest = content[start_idx + len(marker):]
                next_heading = rest.find("\n## ")
                if next_heading >= 0:
                    end_idx = start_idx + len(marker) + next_heading
                    content = content[:start_idx] + section + content[end_idx:]
                else:
                    content = content[:start_idx] + section
            else:
                content = content.rstrip() + "\n\n" + section
        else:
            content = f"""---
type: dashboard
updated_at: {now.isoformat()}
---

# AI Employee Dashboard

{section}"""

        dashboard.write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------
    # CLI: list pending
    # ------------------------------------------------------------------
    def list_pending(self) -> None:
        """Print all pending approvals with expiry status."""
        pending = self.check_pending()

        if not pending:
            print("No pending approvals")
            return

        print(f"\nPending Approvals ({len(pending)}):\n")
        print(f"  {'ID':<10} {'Action':<18} {'Risk':<8} {'Expires In':<15} {'File'}")
        print(f"  {'─'*10} {'─'*18} {'─'*8} {'─'*15} {'─'*30}")

        for item in pending:
            meta = item.get("metadata", {})
            aid = meta.get("id", "?")[:8]
            action = meta.get("action_type", meta.get("action", "?"))
            risk = meta.get("risk_level", "?")
            hrs = item.get("hours_remaining")
            if hrs is not None:
                if hrs <= 0:
                    expires_str = "EXPIRED"
                elif hrs < 1:
                    expires_str = f"{hrs*60:.0f}min"
                else:
                    expires_str = f"{hrs:.1f}h"
            else:
                expires_str = "no expiry"
            fname = Path(item.get("file_path", "")).name

            risk_indicator = {"low": "low", "medium": "MEDIUM", "high": "HIGH"}.get(risk, risk)
            print(f"  {aid:<10} {action:<18} {risk_indicator:<8} {expires_str:<15} {fname}")

    # ------------------------------------------------------------------
    # CLI: send notification digest
    # ------------------------------------------------------------------
    def send_digest(self) -> None:
        """Send notification digest for all pending approvals."""
        pending = self.check_pending()
        if not pending:
            print("No pending approvals — no digest to send")
            return

        result = self.notifier.notify_bulk_summary(pending)
        if result:
            print(f"Digest notification created: {result}")
        else:
            print("Failed to create digest notification")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _parse_approval_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse a markdown approval file into metadata + body."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return None

        # Extract YAML frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    metadata = yaml.safe_load(parts[1]) or {}
                except yaml.YAMLError:
                    metadata = {}
                body = parts[2].strip()
                return {"metadata": metadata, "body": body}

        return {"metadata": {}, "body": content}

    def _route_to_handler(self, action_type: str):
        """Find the handler that can process this action type."""
        for handler in self.handlers:
            if handler.can_handle(action_type):
                return handler
        return None

    def _find_approval_by_id(self, approval_id: str) -> Optional[Path]:
        """Find an approval file by ID in pending-approval/."""
        for f in self.pending_dir.glob("*.md"):
            if approval_id in f.name:
                return f
            # Also check frontmatter
            data = self._parse_approval_file(f)
            if data and data.get("metadata", {}).get("id", "").startswith(approval_id):
                return f
        return None

    def _archive_processed(self, file_path: Path, result: Dict[str, Any]) -> None:
        """Move processed file to Done/ with result annotation."""
        now = datetime.now(timezone.utc)
        content = file_path.read_text(encoding="utf-8")
        annotation = f"\n\n---\n**Processed by Approval Manager** at {now.strftime('%Y-%m-%d %H:%M UTC')}\n"
        annotation += f"Decision: {result.get('decision', '?')}\n"
        if result.get("reason"):
            annotation += f"Reason: {result['reason']}\n"
        content += annotation

        dest = self.done_dir / file_path.name
        dest.write_text(content, encoding="utf-8")
        file_path.unlink()

    def _log_event(self, event: Dict[str, Any]) -> None:
        """Append event to Logs/approval_history.json."""
        log_file = self.logs_dir / "approval_history.json"
        events = []
        if log_file.exists():
            try:
                events = json.loads(log_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                events = []

        events.append(event)
        log_file.write_text(
            json.dumps(events, indent=2, default=str), encoding="utf-8"
        )

    def _read_history(self) -> list:
        """Read the approval history log."""
        log_file = self.logs_dir / "approval_history.json"
        if not log_file.exists():
            return []
        try:
            return json.loads(log_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Approval Manager — unified HITL approval workflow orchestrator"
    )
    parser.add_argument(
        "--vault-path",
        default="./obsidian-vault",
        help="Path to the Obsidian vault (default: ./obsidian-vault)",
    )

    # Modes
    parser.add_argument("--monitor", action="store_true", help="Continuous monitoring")
    parser.add_argument("--once", action="store_true", help="Single poll cycle")
    parser.add_argument("--pending", action="store_true", help="List pending approvals")
    parser.add_argument(
        "--approve",
        nargs="+",
        metavar="ID",
        help="Bulk approve by ID(s)",
    )
    parser.add_argument("--reject", type=str, metavar="ID", help="Reject by ID")
    parser.add_argument("--reason", type=str, help="Rejection reason (with --reject)")
    parser.add_argument("--delegate", type=str, metavar="ID", help="Delegate approval")
    parser.add_argument("--to", type=str, help="Delegate target (with --delegate)")
    parser.add_argument("--expire-check", action="store_true", help="Check/process expired")
    parser.add_argument(
        "--report",
        nargs="?",
        const="week",
        metavar="PERIOD",
        help="Generate report (week|month|all)",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show approval history",
    )
    parser.add_argument("--type", type=str, dest="action_type", help="Filter by action type")
    parser.add_argument("--status", type=str, help="Filter by status (approved|rejected|expired)")
    parser.add_argument("--notify", action="store_true", help="Send notification digest")
    parser.add_argument("--poll-interval", type=int, default=30, help="Poll interval in seconds")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    manager = ApprovalManager(args.vault_path)

    if args.monitor:
        manager.monitor(poll_interval=args.poll_interval)
    elif args.once:
        results = manager.process_once()
        print(f"Poll cycle complete: {json.dumps(results, indent=2)}")
    elif args.pending:
        manager.list_pending()
    elif args.approve:
        manager.approve_bulk(args.approve)
    elif args.reject:
        reason = args.reason or "No reason provided"
        manager.reject_bulk([args.reject], reason)
    elif args.delegate:
        if not args.to:
            print("Error: --to required with --delegate")
            sys.exit(1)
        manager.delegate(args.delegate, args.to)
    elif args.expire_check:
        expired = manager.check_expired()
        print(f"Expired: {len(expired)} approval(s)")
        for e in expired:
            print(f"  - {e['approval_id'][:8]} ({e['action_type']})")
    elif args.report is not None:
        manager.generate_report(args.report)
    elif args.history:
        manager.show_history(action_type=args.action_type, status=args.status)
    elif args.notify:
        manager.send_digest()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
