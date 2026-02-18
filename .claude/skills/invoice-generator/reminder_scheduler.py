"""
Reminder Scheduler — detects overdue invoices and creates reminder action
files in the vault.  Supports escalating reminder types based on how many
days past due.
"""

import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class ReminderScheduler:
    """Scans invoice records for overdue items and creates reminder files."""

    def __init__(self, vault_path: str) -> None:
        self.vault = Path(vault_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_overdue(self) -> List[Dict[str, Any]]:
        """Return all overdue invoices."""
        invoices = self._scan_invoices()
        return [inv for inv in invoices if self._is_overdue(inv)]

    def generate_reminders(self) -> List[Dict[str, Any]]:
        """
        Create reminder files for overdue invoices.

        Returns list of created reminders with paths.
        """
        overdue = self.check_overdue()
        created = []

        for inv in overdue:
            days = inv.get("days_overdue", 0)
            reminder_type = self._get_reminder_schedule(days)
            inv_number = inv.get("invoice_number", "UNKNOWN")

            # Skip if already reminded at this level
            if self._already_reminded(inv_number, reminder_type):
                continue

            path = self._create_reminder(inv, reminder_type)
            if path:
                self._log_reminder(inv_number, reminder_type, str(path))
                created.append({
                    "invoice_number": inv_number,
                    "reminder_type": reminder_type,
                    "days_overdue": days,
                    "path": str(path),
                })

        return created

    # ------------------------------------------------------------------
    # Invoice scanning
    # ------------------------------------------------------------------

    def _scan_invoices(self) -> List[Dict[str, Any]]:
        """Read all invoice markdown files from Accounting/invoices/."""
        folder = self.vault / "Accounting" / "invoices"
        if not folder.exists():
            return []

        invoices = []
        for md_file in folder.glob("*.md"):
            meta = self._parse_frontmatter(md_file)
            if meta:
                meta.setdefault("invoice_number", md_file.stem)
                meta["_file_path"] = str(md_file)
                invoices.append(meta)
        return invoices

    def _is_overdue(self, invoice: Dict[str, Any]) -> bool:
        """Check if an invoice is past its due date and not paid."""
        status = str(invoice.get("status", "")).lower()
        if status in ("paid", "cancelled", "void"):
            return False

        due_date_str = invoice.get("due_date", "")
        if not due_date_str:
            return False

        try:
            due = date.fromisoformat(str(due_date_str)[:10])
            today = date.today()
            if today > due:
                invoice["days_overdue"] = (today - due).days
                return True
        except (ValueError, TypeError):
            pass

        return False

    # ------------------------------------------------------------------
    # Reminder creation
    # ------------------------------------------------------------------

    def _get_reminder_schedule(self, days_overdue: int) -> str:
        """Determine reminder type based on days overdue."""
        if days_overdue <= 7:
            return "gentle"
        elif days_overdue <= 14:
            return "firm"
        elif days_overdue <= 30:
            return "final"
        else:
            return "escalation"

    def _create_reminder(
        self, invoice: Dict[str, Any], reminder_type: str
    ) -> Optional[Path]:
        """Create a reminder action file in Needs_Action/."""
        needs_action_dir = self.vault / "Needs_Action"
        needs_action_dir.mkdir(parents=True, exist_ok=True)

        inv_number = invoice.get("invoice_number", "UNKNOWN")
        customer = invoice.get("customer", "Unknown Client")
        total = invoice.get("total", 0)
        due_date = invoice.get("due_date", "N/A")
        days_overdue = invoice.get("days_overdue", 0)
        customer_email = invoice.get("customer_email", "")

        filename = f"REMINDER_OVERDUE_{inv_number}_{reminder_type}.md"
        file_path = needs_action_dir / filename

        # Don't overwrite if already exists
        if file_path.exists():
            return None

        # Build email template based on reminder type
        email_subject, email_body = self._get_reminder_template(
            reminder_type, inv_number, customer, total, due_date, days_overdue
        )

        content = (
            f"---\n"
            f"type: invoice_reminder\n"
            f"invoice_number: {inv_number}\n"
            f"customer: \"{customer}\"\n"
            f"customer_email: \"{customer_email}\"\n"
            f"total: {total}\n"
            f"due_date: {due_date}\n"
            f"days_overdue: {days_overdue}\n"
            f"reminder_type: {reminder_type}\n"
            f"status: needs_action\n"
            f"created: {datetime.now(timezone.utc).isoformat()}\n"
            f"---\n"
            f"\n"
            f"# Overdue Invoice Reminder: {inv_number}\n"
            f"\n"
            f"**Customer:** {customer}\n"
            f"**Amount:** ${float(total):,.2f}\n"
            f"**Due Date:** {due_date}\n"
            f"**Days Overdue:** {days_overdue}\n"
            f"**Reminder Level:** {reminder_type.upper()}\n"
            f"\n"
            f"## Suggested Action\n"
            f"\n"
            f"Send a {reminder_type} payment reminder to {customer}.\n"
            f"\n"
            f"### Suggested Email\n"
            f"\n"
            f"**To:** {customer_email}\n"
            f"**Subject:** {email_subject}\n"
            f"\n"
            f"{email_body}\n"
            f"\n"
            f"## Actions\n"
            f"\n"
            f"- [ ] Send reminder email\n"
            f"- [ ] Call customer if no response in 3 days\n"
            f"- [ ] Update invoice status\n"
        )

        try:
            file_path.write_text(content, encoding="utf-8")
            return file_path
        except OSError:
            return None

    def _get_reminder_template(
        self,
        reminder_type: str,
        inv_number: str,
        customer: str,
        total: Any,
        due_date: str,
        days_overdue: int,
    ) -> tuple:
        """Return (subject, body) for the reminder email."""
        amount_str = f"${float(total):,.2f}"

        if reminder_type == "gentle":
            subject = f"Friendly Reminder: Invoice {inv_number} Payment Due"
            body = (
                f"Hi,\n\n"
                f"I hope this message finds you well. This is a friendly reminder that "
                f"invoice {inv_number} for {amount_str} was due on {due_date} "
                f"({days_overdue} days ago).\n\n"
                f"If you've already sent the payment, please disregard this message. "
                f"Otherwise, we'd appreciate if you could process the payment at your "
                f"earliest convenience.\n\n"
                f"Please let us know if you have any questions.\n\n"
                f"Best regards"
            )
        elif reminder_type == "firm":
            subject = f"Payment Reminder: Invoice {inv_number} - {days_overdue} Days Overdue"
            body = (
                f"Hi,\n\n"
                f"We're writing to follow up on invoice {inv_number} for {amount_str}, "
                f"which was due on {due_date} and is now {days_overdue} days overdue.\n\n"
                f"We kindly request that you arrange payment within the next 7 days. "
                f"If there are any issues with the invoice or payment process, please "
                f"reach out so we can resolve them promptly.\n\n"
                f"Thank you for your attention to this matter.\n\n"
                f"Best regards"
            )
        elif reminder_type == "final":
            subject = f"URGENT: Final Notice - Invoice {inv_number} ({days_overdue} Days Overdue)"
            body = (
                f"Hi,\n\n"
                f"This is a final notice regarding invoice {inv_number} for {amount_str}, "
                f"which was due on {due_date} and is now {days_overdue} days overdue.\n\n"
                f"We have not received payment or a response to our previous reminders. "
                f"We request immediate payment to avoid any further action.\n\n"
                f"If you are experiencing difficulties, please contact us immediately "
                f"to discuss payment arrangements.\n\n"
                f"Regards"
            )
        else:  # escalation
            subject = f"OVERDUE ACCOUNT: Invoice {inv_number} - Immediate Action Required"
            body = (
                f"Hi,\n\n"
                f"Invoice {inv_number} for {amount_str} has been outstanding for "
                f"{days_overdue} days (due {due_date}). Despite multiple reminders, "
                f"we have not received payment.\n\n"
                f"Please treat this as urgent and arrange immediate payment. "
                f"Continued non-payment may result in suspension of services and "
                f"referral to our collections process.\n\n"
                f"Contact us immediately to resolve this matter.\n\n"
                f"Regards"
            )

        return subject, body

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _already_reminded(self, invoice_number: str, reminder_type: str) -> bool:
        """Check if we've already sent this reminder level for this invoice."""
        log_file = self.vault / "Logs" / "invoice_reminders.json"
        if not log_file.exists():
            return False
        try:
            data = json.loads(log_file.read_text(encoding="utf-8"))
            entries = data if isinstance(data, list) else data.get("entries", [])
            for entry in entries:
                if (
                    entry.get("invoice_number") == invoice_number
                    and entry.get("reminder_type") == reminder_type
                ):
                    return True
        except (json.JSONDecodeError, OSError):
            pass
        return False

    def _log_reminder(self, invoice_number: str, reminder_type: str, path: str) -> None:
        """Log the reminder to prevent duplicates."""
        logs_dir = self.vault / "Logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / "invoice_reminders.json"

        entries: List[Dict[str, Any]] = []
        if log_file.exists():
            try:
                data = json.loads(log_file.read_text(encoding="utf-8"))
                entries = data if isinstance(data, list) else data.get("entries", [])
            except (json.JSONDecodeError, OSError):
                pass

        entries.append({
            "invoice_number": invoice_number,
            "reminder_type": reminder_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "path": path,
        })

        log_file.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_frontmatter(md_file: Path) -> Optional[Dict[str, Any]]:
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            return None
        if not text.startswith("---"):
            return None
        parts = text.split("---", 2)
        if len(parts) < 3:
            return None
        result: Dict[str, Any] = {}
        for line in parts[1].strip().splitlines():
            match = re.match(r"^(\w[\w_]*)\s*:\s*(.+)$", line)
            if match:
                key = match.group(1)
                val = match.group(2).strip().strip('"').strip("'")
                try:
                    val = float(val)
                    if val == int(val):
                        val = int(val)
                except (ValueError, TypeError):
                    pass
                result[key] = val
        return result if result else None
