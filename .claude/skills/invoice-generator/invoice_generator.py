# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "reportlab>=4.0",
#     "jinja2>=3.1.0",
#     "python-dotenv>=1.0.0",
#     "pyyaml>=6.0",
# ]
# ///
"""
Invoice Generator — creates professional invoices automatically with PDF
generation, HITL approval workflow, overdue reminders, and recurring support.

Usage with UV (recommended):
    uv run invoice_generator.py --vault-path ../../obsidian-vault --generate \
        --customer "ACME Corp" --items '[{"description":"Dev","quantity":10,"rate":150}]'

Usage with pip:
    pip install -r requirements.txt
    python invoice_generator.py --vault-path ../../obsidian-vault --generate ...

CLI modes:
    --generate          Create a new invoice
    --recurring         Process recurring invoices from Rates.md
    --detect            Scan Needs_Action/ for invoice requests
    --check-approvals   Process approved invoices
    --reminders         Check and create overdue reminders
    --status INV-XXX paid   Update invoice status
"""

import argparse
import json
import logging
import re
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure local imports work when run via UV
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv  # noqa: E402
from jinja2 import Environment, FileSystemLoader  # noqa: E402

import yaml  # noqa: E402

from pdf_creator import InvoicePDFCreator  # noqa: E402
from reminder_scheduler import ReminderScheduler  # noqa: E402

logger = logging.getLogger("invoice-generator")


class InvoiceGenerator:
    """Orchestrates the full invoice lifecycle."""

    def __init__(self, vault_path: str) -> None:
        self.vault = Path(vault_path).resolve()
        self._seed_config()

        self.company_info = self._load_company_info()
        self.rates_config = self._load_rates()
        self.pdf_creator = InvoicePDFCreator(self.company_info)
        self.reminder_scheduler = ReminderScheduler(str(self.vault))

        # Jinja2 for email template
        template_dir = Path(__file__).resolve().parent
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    # ------------------------------------------------------------------
    # Generate invoice
    # ------------------------------------------------------------------

    def generate(
        self,
        customer: str,
        line_items: List[Dict[str, Any]],
        due_days: int = 30,
        tax_rate: Optional[float] = None,
        notes: Optional[str] = None,
        customer_email: str = "",
    ) -> Dict[str, Any]:
        """
        Generate a new invoice with PDF and create approval request.

        Args:
            customer: Customer/company name.
            line_items: List of {description, quantity, rate} dicts.
            due_days: Days until due (default 30).
            tax_rate: Tax rate as decimal (e.g., 0.08 for 8%). None uses config default.
            notes: Optional notes for the invoice.
            customer_email: Customer email for delivery.

        Returns:
            Dict with invoice_number, total, pdf_path, approval_id.
        """
        inv_number = self._next_invoice_number()
        inv_date = date.today()
        due_date = inv_date + timedelta(days=due_days)

        if tax_rate is None:
            tax_rate = float(self.rates_config.get("default_tax_rate", 0.0))

        currency = self.rates_config.get(
            "default_currency", self.company_info.get("default_currency", "USD")
        )

        # Calculate amounts
        for item in line_items:
            item["quantity"] = float(item.get("quantity", 1))
            item["rate"] = float(item.get("rate", 0))
            item["amount"] = round(item["quantity"] * item["rate"], 2)

        subtotal = round(sum(item["amount"] for item in line_items), 2)
        tax_amount = round(subtotal * tax_rate, 2)
        total = round(subtotal + tax_amount, 2)

        payment_terms = self.company_info.get("default_payment_terms", "Net 30")

        invoice_data = {
            "invoice_number": inv_number,
            "date": inv_date.isoformat(),
            "due_date": due_date.isoformat(),
            "customer": customer,
            "customer_email": customer_email,
            "line_items": line_items,
            "subtotal": subtotal,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "total": total,
            "currency": currency,
            "notes": notes,
            "payment_terms": payment_terms,
            "status": "draft",
        }

        # Generate PDF
        invoices_dir = self.vault / "Accounting" / "invoices"
        invoices_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = invoices_dir / f"{inv_number}.pdf"
        self.pdf_creator.create_pdf(invoice_data, str(pdf_path))
        logger.info("PDF generated: %s", pdf_path)

        # Copy PDF to Attachments/ for email-sender-mcp
        attachments_dir = self.vault / "Attachments"
        attachments_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdf_path, attachments_dir / f"{inv_number}.pdf")

        # Save invoice record (markdown)
        record_path = self._save_invoice_record(invoice_data)
        logger.info("Invoice record: %s", record_path)

        # Create approval request
        approval_id = self._create_approval(invoice_data)
        logger.info("Approval request created: %s", approval_id)

        # Log event
        self._log_event({
            "action": "invoice_generated",
            "invoice_number": inv_number,
            "customer": customer,
            "total": total,
            "pdf_path": str(pdf_path),
            "approval_id": approval_id,
        })

        return {
            "invoice_number": inv_number,
            "total": total,
            "pdf_path": str(pdf_path),
            "record_path": str(record_path),
            "approval_id": approval_id,
            "status": "draft",
        }

    # ------------------------------------------------------------------
    # Generate from rates
    # ------------------------------------------------------------------

    def generate_from_rates(
        self,
        customer: str,
        rate_names: List[str],
        quantities: List[float],
        due_days: int = 30,
        customer_email: str = "",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate invoice using predefined rates from Rates.md."""
        rates = self.rates_config.get("rates", [])
        rate_map = {r["name"]: r for r in rates}

        line_items = []
        for name, qty in zip(rate_names, quantities):
            rate_entry = rate_map.get(name)
            if not rate_entry:
                raise ValueError(f"Rate not found: {name}. Available: {list(rate_map.keys())}")
            line_items.append({
                "description": rate_entry.get("description", name),
                "quantity": qty,
                "rate": float(rate_entry["rate"]),
            })

        return self.generate(
            customer=customer,
            line_items=line_items,
            due_days=due_days,
            customer_email=customer_email,
            notes=notes,
        )

    # ------------------------------------------------------------------
    # Recurring invoices
    # ------------------------------------------------------------------

    def generate_recurring(self) -> List[Dict[str, Any]]:
        """Process recurring invoices from Rates.md config."""
        recurring_clients = self.rates_config.get("recurring_clients", [])
        if not recurring_clients:
            logger.info("No recurring clients configured in Rates.md")
            return []

        rates = self.rates_config.get("rates", [])
        rate_map = {r["name"]: r for r in rates}
        results = []

        for client in recurring_clients:
            customer = client.get("customer", "")
            email = client.get("email", "")
            rate_name = client.get("rate_name", "")
            start_date_str = client.get("start_date", "")

            if not customer or not rate_name:
                continue

            rate_entry = rate_map.get(rate_name)
            if not rate_entry:
                logger.warning("Rate %s not found for recurring client %s", rate_name, customer)
                continue

            # Check if already invoiced this month
            if self._already_invoiced_this_month(customer, rate_name):
                logger.debug("Already invoiced %s for %s this month", customer, rate_name)
                continue

            result = self.generate(
                customer=customer,
                line_items=[{
                    "description": rate_entry.get("description", rate_name),
                    "quantity": 1,
                    "rate": float(rate_entry["rate"]),
                }],
                customer_email=email,
                notes=f"Recurring monthly invoice for {rate_name}",
            )
            results.append(result)
            logger.info("Recurring invoice %s for %s", result["invoice_number"], customer)

        return results

    # ------------------------------------------------------------------
    # Detect needs
    # ------------------------------------------------------------------

    def detect_needs(self) -> List[Dict[str, Any]]:
        """Scan Needs_Action/ for invoice request files."""
        needs_dir = self.vault / "Needs_Action"
        if not needs_dir.exists():
            return []

        requests = []
        for md_file in needs_dir.glob("*.md"):
            meta = self._parse_frontmatter(md_file)
            if not meta:
                continue
            file_type = str(meta.get("type", "")).lower()
            subject = str(meta.get("subject", "")).lower()

            if file_type == "invoice_request" or "invoice" in subject:
                requests.append({
                    "file": str(md_file),
                    "customer": meta.get("customer") or meta.get("from_name", "Unknown"),
                    "email": meta.get("customer_email") or meta.get("from_email", ""),
                    "metadata": meta,
                })

        if requests:
            logger.info("Found %d invoice request(s) in Needs_Action/", len(requests))
        return requests

    # ------------------------------------------------------------------
    # Approval handling
    # ------------------------------------------------------------------

    def check_approvals(self) -> List[Dict[str, Any]]:
        """Check for approved invoice files and update status."""
        approved_dir = self.vault / "Approved"
        if not approved_dir.exists():
            return []

        results = []
        for md_file in approved_dir.glob("APPROVAL_REQUIRED_invoice_*.md"):
            meta = self._parse_frontmatter(md_file)
            if not meta:
                continue

            inv_number = meta.get("invoice_number", "")
            if not inv_number:
                continue

            # Update invoice status to "approved"
            self.update_status(inv_number, "approved")

            # Prepare email action
            email_action = self._prepare_email_action(meta)

            results.append({
                "invoice_number": inv_number,
                "customer": meta.get("customer", ""),
                "total": meta.get("total", 0),
                "email_action": email_action,
            })

            self._log_event({
                "action": "invoice_approved",
                "invoice_number": inv_number,
                "customer": meta.get("customer", ""),
            })

            logger.info("Invoice %s approved", inv_number)

        return results

    # ------------------------------------------------------------------
    # Status management
    # ------------------------------------------------------------------

    def update_status(self, invoice_number: str, new_status: str) -> bool:
        """Update the status in an invoice markdown file's frontmatter."""
        valid_statuses = {"draft", "approved", "sent", "paid", "overdue", "cancelled", "void"}
        if new_status not in valid_statuses:
            logger.error("Invalid status: %s. Valid: %s", new_status, valid_statuses)
            return False

        invoices_dir = self.vault / "Accounting" / "invoices"
        record_path = invoices_dir / f"{invoice_number}.md"

        if not record_path.exists():
            logger.error("Invoice record not found: %s", record_path)
            return False

        try:
            text = record_path.read_text(encoding="utf-8")
            # Replace status in frontmatter
            updated = re.sub(
                r"^(status:\s*).+$",
                rf"\g<1>{new_status}",
                text,
                count=1,
                flags=re.MULTILINE,
            )
            record_path.write_text(updated, encoding="utf-8")
            logger.info("Updated %s status to %s", invoice_number, new_status)

            self._log_event({
                "action": "status_updated",
                "invoice_number": invoice_number,
                "new_status": new_status,
            })
            return True
        except OSError as e:
            logger.error("Failed to update status: %s", e)
            return False

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def _seed_config(self) -> None:
        """Copy seed config files to vault/config/ if they don't exist."""
        seed_dir = Path(__file__).resolve().parent / "seed"
        config_dir = self.vault / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        for filename in ("Company_Info.md", "Rates.md"):
            dest = config_dir / filename
            src = seed_dir / filename
            if not dest.exists() and src.exists():
                shutil.copy2(src, dest)
                logger.info("Seeded config: %s", dest)

    def _load_company_info(self) -> Dict[str, Any]:
        """Parse config/Company_Info.md YAML frontmatter."""
        path = self.vault / "config" / "Company_Info.md"
        return self._parse_yaml_frontmatter(path) or {}

    def _load_rates(self) -> Dict[str, Any]:
        """Parse config/Rates.md YAML frontmatter."""
        path = self.vault / "config" / "Rates.md"
        return self._parse_yaml_frontmatter(path) or {}

    def _parse_yaml_frontmatter(self, path: Path) -> Optional[Dict[str, Any]]:
        """Parse YAML frontmatter using PyYAML (supports complex structures)."""
        if not path.exists():
            return None
        try:
            text = path.read_text(encoding="utf-8")
            if not text.startswith("---"):
                return None
            parts = text.split("---", 2)
            if len(parts) < 3:
                return None
            return yaml.safe_load(parts[1])
        except (yaml.YAMLError, OSError) as e:
            logger.warning("Failed to parse %s: %s", path, e)
            return None

    # ------------------------------------------------------------------
    # Invoice record
    # ------------------------------------------------------------------

    def _save_invoice_record(self, invoice_data: Dict[str, Any]) -> Path:
        """Save invoice metadata as markdown in Accounting/invoices/."""
        invoices_dir = self.vault / "Accounting" / "invoices"
        invoices_dir.mkdir(parents=True, exist_ok=True)

        inv_number = invoice_data["invoice_number"]
        record_path = invoices_dir / f"{inv_number}.md"

        items_text = ""
        for item in invoice_data.get("line_items", []):
            desc = item.get("description", "")
            qty = item.get("quantity", 1)
            rate = item.get("rate", 0)
            amount = item.get("amount", qty * rate)
            items_text += f"| {desc} | {qty} | ${rate:,.2f} | ${amount:,.2f} |\n"

        currency_symbol = "$" if invoice_data.get("currency", "USD") == "USD" else invoice_data.get("currency", "") + " "

        content = (
            f"---\n"
            f"type: invoice\n"
            f"invoice_number: {inv_number}\n"
            f"customer: \"{invoice_data['customer']}\"\n"
            f"customer_email: \"{invoice_data.get('customer_email', '')}\"\n"
            f"date: {invoice_data['date']}\n"
            f"due_date: {invoice_data['due_date']}\n"
            f"subtotal: {invoice_data['subtotal']}\n"
            f"tax_rate: {invoice_data['tax_rate']}\n"
            f"tax_amount: {invoice_data['tax_amount']}\n"
            f"total: {invoice_data['total']}\n"
            f"currency: {invoice_data.get('currency', 'USD')}\n"
            f"status: {invoice_data['status']}\n"
            f"created_at: {datetime.now(timezone.utc).isoformat()}\n"
            f"---\n"
            f"\n"
            f"# Invoice {inv_number}\n"
            f"\n"
            f"**Customer:** {invoice_data['customer']}\n"
            f"**Date:** {invoice_data['date']}\n"
            f"**Due Date:** {invoice_data['due_date']}\n"
            f"**Status:** {invoice_data['status']}\n"
            f"\n"
            f"## Line Items\n"
            f"\n"
            f"| Description | Qty | Rate | Amount |\n"
            f"|-------------|-----|------|--------|\n"
            f"{items_text}\n"
            f"## Totals\n"
            f"\n"
            f"- **Subtotal:** {currency_symbol}{invoice_data['subtotal']:,.2f}\n"
        )

        if invoice_data["tax_rate"] > 0:
            content += f"- **Tax ({invoice_data['tax_rate'] * 100:.1f}%):** {currency_symbol}{invoice_data['tax_amount']:,.2f}\n"

        content += (
            f"- **Total:** {currency_symbol}{invoice_data['total']:,.2f}\n"
            f"\n"
            f"## Payment Terms\n"
            f"\n"
            f"{invoice_data.get('payment_terms', 'Net 30')}\n"
        )

        if invoice_data.get("notes"):
            content += f"\n## Notes\n\n{invoice_data['notes']}\n"

        record_path.write_text(content, encoding="utf-8")
        return record_path

    # ------------------------------------------------------------------
    # Approval file
    # ------------------------------------------------------------------

    def _create_approval(self, invoice_data: Dict[str, Any]) -> str:
        """Create HITL approval file in pending-approval/."""
        pending_dir = self.vault / "pending-approval"
        pending_dir.mkdir(parents=True, exist_ok=True)

        inv_number = invoice_data["invoice_number"]
        approval_id = inv_number.lower().replace("-", "")
        filename = f"APPROVAL_REQUIRED_invoice_{inv_number}.md"
        file_path = pending_dir / filename

        items_preview = ""
        for item in invoice_data.get("line_items", []):
            desc = item.get("description", "")
            amount = item.get("amount", 0)
            items_preview += f"  - {desc}: ${amount:,.2f}\n"

        content = (
            f"---\n"
            f"id: {approval_id}\n"
            f"type: approval_request\n"
            f"action_type: send_invoice\n"
            f"platform: invoice\n"
            f"action: send_invoice\n"
            f"invoice_number: {inv_number}\n"
            f"customer: \"{invoice_data['customer']}\"\n"
            f"customer_email: \"{invoice_data.get('customer_email', '')}\"\n"
            f"total: {invoice_data['total']}\n"
            f"due_date: {invoice_data['due_date']}\n"
            f"created: {datetime.now(timezone.utc).isoformat()}\n"
            f"expires: {(datetime.now(timezone.utc) + timedelta(hours=72)).isoformat()}\n"
            f"risk_level: high\n"
            f"status: pending\n"
            f"---\n"
            f"\n"
            f"# Invoice Approval Required: {inv_number}\n"
            f"\n"
            f"**Customer:** {invoice_data['customer']}\n"
            f"**Total:** ${invoice_data['total']:,.2f}\n"
            f"**Due Date:** {invoice_data['due_date']}\n"
            f"**Payment Terms:** {invoice_data.get('payment_terms', 'Net 30')}\n"
            f"\n"
            f"## Line Items\n"
            f"\n"
            f"{items_preview}\n"
            f"## Action Required\n"
            f"\n"
            f"Review this invoice and move this file to:\n"
            f"- `Approved/` — to send the invoice to the customer\n"
            f"- `Rejected/` — to cancel the invoice\n"
            f"\n"
            f"PDF attached at: `Accounting/invoices/{inv_number}.pdf`\n"
        )

        file_path.write_text(content, encoding="utf-8")
        return approval_id

    # ------------------------------------------------------------------
    # Email action
    # ------------------------------------------------------------------

    def _prepare_email_action(self, approval_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create an email action file for email-sender-mcp pickup.
        The email-sender-mcp reads from Needs_Action/ for pending sends.
        """
        customer_email = approval_meta.get("customer_email", "")
        if not customer_email:
            return None

        inv_number = approval_meta.get("invoice_number", "")
        customer = approval_meta.get("customer", "")
        total = approval_meta.get("total", 0)

        # Render HTML email body
        try:
            template = self.jinja_env.get_template("invoice_template.html")
            # Load invoice record for full data
            record = self._parse_yaml_frontmatter(
                self.vault / "Accounting" / "invoices" / f"{inv_number}.md"
            )
            if not record:
                record = dict(approval_meta)

            html_body = template.render(
                invoice_number=inv_number,
                invoice_date=record.get("date", date.today().isoformat()),
                due_date=record.get("due_date", ""),
                customer=customer,
                customer_email=customer_email,
                company_name=self.company_info.get("company_name", "Company"),
                tagline=self.company_info.get("tagline", ""),
                company_email=self.company_info.get("email", ""),
                website=self.company_info.get("website", ""),
                line_items=record.get("line_items", []),
                subtotal=float(record.get("subtotal", 0)),
                tax_rate=float(record.get("tax_rate", 0)),
                tax_amount=float(record.get("tax_amount", 0)),
                total=float(total),
                currency_symbol="$",
                payment_terms=self.company_info.get("default_payment_terms", "Net 30"),
                bank_name=self.company_info.get("bank_name", ""),
                bank_account=self.company_info.get("bank_account", ""),
            )
        except Exception:
            html_body = None

        # Create email action file
        needs_dir = self.vault / "Needs_Action"
        needs_dir.mkdir(parents=True, exist_ok=True)
        email_file = needs_dir / f"SEND_INVOICE_{inv_number}.md"

        content = (
            f"---\n"
            f"type: send_email\n"
            f"to: \"{customer_email}\"\n"
            f"subject: \"Invoice {inv_number} from {self.company_info.get('company_name', 'Company')}\"\n"
            f"attachments:\n"
            f"  - \"{inv_number}.pdf\"\n"
            f"html: true\n"
            f"invoice_number: {inv_number}\n"
            f"status: pending\n"
            f"created: {datetime.now(timezone.utc).isoformat()}\n"
            f"---\n"
            f"\n"
            f"# Send Invoice {inv_number}\n"
            f"\n"
            f"**To:** {customer_email}\n"
            f"**Attachment:** {inv_number}.pdf\n"
            f"\n"
            f"Please process this email send via email-sender-mcp.\n"
        )

        email_file.write_text(content, encoding="utf-8")

        return {
            "to": customer_email,
            "subject": f"Invoice {inv_number}",
            "attachment": f"{inv_number}.pdf",
            "action_file": str(email_file),
        }

    # ------------------------------------------------------------------
    # Invoice numbering
    # ------------------------------------------------------------------

    def _next_invoice_number(self) -> str:
        """Allocate the next invoice number (thread-safe via JSON counter)."""
        logs_dir = self.vault / "Logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        counter_file = logs_dir / "invoice_counter.json"

        prefix = self.rates_config.get("invoice_prefix", "INV")
        counter = 0

        if counter_file.exists():
            try:
                data = json.loads(counter_file.read_text(encoding="utf-8"))
                counter = int(data.get("last_number", 0))
            except (json.JSONDecodeError, OSError, ValueError):
                pass

        counter += 1
        counter_file.write_text(
            json.dumps({"last_number": counter, "prefix": prefix}, indent=2),
            encoding="utf-8",
        )

        return f"{prefix}-{counter:04d}"

    # ------------------------------------------------------------------
    # Recurring dedup
    # ------------------------------------------------------------------

    def _already_invoiced_this_month(self, customer: str, rate_name: str) -> bool:
        """Check if a recurring invoice was already generated this month."""
        month_prefix = date.today().strftime("%Y-%m")
        log_file = self.vault / "Logs" / "invoices.json"
        if not log_file.exists():
            return False
        try:
            data = json.loads(log_file.read_text(encoding="utf-8"))
            entries = data if isinstance(data, list) else data.get("entries", [])
            for entry in entries:
                if (
                    entry.get("customer") == customer
                    and entry.get("action") == "invoice_generated"
                    and str(entry.get("timestamp", "")).startswith(month_prefix)
                ):
                    return True
        except (json.JSONDecodeError, OSError):
            pass
        return False

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log_event(self, event: Dict[str, Any]) -> None:
        """Append event to Logs/invoices.json."""
        logs_dir = self.vault / "Logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / "invoices.json"

        entries: List[Dict[str, Any]] = []
        if log_file.exists():
            try:
                data = json.loads(log_file.read_text(encoding="utf-8"))
                entries = data if isinstance(data, list) else data.get("entries", [])
            except (json.JSONDecodeError, OSError):
                pass

        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        entries.append(event)

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
            match = re.match(r'^(\w[\w_]*)\s*:\s*(.+)$', line)
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


# ------------------------------------------------------------------
# CLI entry-point
# ------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Invoice Generator — creates professional invoices automatically"
    )
    parser.add_argument(
        "--vault-path",
        default="./obsidian-vault",
        help="Path to the Obsidian vault (default: ./obsidian-vault)",
    )
    parser.add_argument("--generate", action="store_true", help="Generate a new invoice")
    parser.add_argument("--customer", help="Customer name (with --generate)")
    parser.add_argument("--customer-email", default="", help="Customer email (with --generate)")
    parser.add_argument("--items", help="Line items as JSON array (with --generate)")
    parser.add_argument("--due-days", type=int, default=30, help="Days until due (default: 30)")
    parser.add_argument("--notes", help="Invoice notes (with --generate)")
    parser.add_argument("--rate-names", help="Comma-separated rate names from Rates.md")
    parser.add_argument("--quantities", help="Comma-separated quantities (with --rate-names)")
    parser.add_argument("--recurring", action="store_true", help="Process recurring invoices")
    parser.add_argument("--detect", action="store_true", help="Scan Needs_Action/ for requests")
    parser.add_argument("--check-approvals", action="store_true", help="Process approved invoices")
    parser.add_argument("--reminders", action="store_true", help="Check overdue and create reminders")
    parser.add_argument("--status", nargs=2, metavar=("INV-NUM", "STATUS"), help="Update invoice status")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    # Load .env
    for search in (Path(args.vault_path).resolve().parent, Path.cwd()):
        env_file = search / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break

    # Logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    gen = InvoiceGenerator(vault_path=args.vault_path)

    if args.generate:
        if args.rate_names:
            # Generate from predefined rates
            names = [n.strip() for n in args.rate_names.split(",")]
            qtys = [float(q.strip()) for q in (args.quantities or "1").split(",")]
            # Pad quantities to match rate names
            while len(qtys) < len(names):
                qtys.append(1.0)
            result = gen.generate_from_rates(
                customer=args.customer or "Customer",
                rate_names=names,
                quantities=qtys,
                due_days=args.due_days,
                customer_email=args.customer_email,
                notes=args.notes,
            )
        elif args.items:
            items = json.loads(args.items)
            result = gen.generate(
                customer=args.customer or "Customer",
                line_items=items,
                due_days=args.due_days,
                customer_email=args.customer_email,
                notes=args.notes,
            )
        else:
            print("Error: --generate requires --items (JSON) or --rate-names")
            sys.exit(1)

        print(f"\nInvoice generated!")
        print(f"  Number:   {result['invoice_number']}")
        print(f"  Total:    ${result['total']:,.2f}")
        print(f"  PDF:      {result['pdf_path']}")
        print(f"  Approval: pending-approval/APPROVAL_REQUIRED_invoice_{result['invoice_number']}.md")

    elif args.recurring:
        results = gen.generate_recurring()
        print(f"\nProcessed {len(results)} recurring invoice(s)")
        for r in results:
            print(f"  {r['invoice_number']}: ${r['total']:,.2f}")

    elif args.detect:
        requests = gen.detect_needs()
        print(f"\nFound {len(requests)} invoice request(s) in Needs_Action/")
        for req in requests:
            print(f"  Customer: {req['customer']} — {req['file']}")

    elif args.check_approvals:
        results = gen.check_approvals()
        print(f"\nProcessed {len(results)} approved invoice(s)")
        for r in results:
            print(f"  {r['invoice_number']}: {r['customer']} — ${r['total']:,.2f}")

    elif args.reminders:
        reminders = gen.reminder_scheduler.generate_reminders()
        print(f"\nCreated {len(reminders)} overdue reminder(s)")
        for rem in reminders:
            print(f"  {rem['invoice_number']}: {rem['reminder_type']} ({rem['days_overdue']}d overdue)")

    elif args.status:
        inv_num, new_status = args.status
        success = gen.update_status(inv_num, new_status)
        if success:
            print(f"\nUpdated {inv_num} → {new_status}")
        else:
            print(f"\nFailed to update {inv_num}")
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
