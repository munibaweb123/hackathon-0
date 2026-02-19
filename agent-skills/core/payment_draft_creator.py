# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
Payment Draft Creator -- Phase 8 (US6 -- Payments) of the Platinum Tier AI Employee.

Creates payment draft files in the vault at ``Drafts/payments/`` with full YAML
frontmatter.  Drafts always require at least primary approval; amounts above a
configurable threshold additionally require secondary (dual-sign) approval.

Self-contained: depends only on the Python stdlib and PyYAML.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Default expiry window for payment drafts (hours)
_DEFAULT_EXPIRY_HOURS: int = 72


class PaymentDraftCreator:
    """Creates payment draft files that enter the file-based approval workflow."""

    def __init__(
        self,
        vault_path: str,
        secondary_threshold: float = 1000,
    ) -> None:
        """
        Initialise the payment draft creator.

        Args:
            vault_path: Absolute path to the Obsidian vault directory.
            secondary_threshold: Amounts **above** this value require
                secondary (dual-sign) approval.  Defaults to 1000.
        """
        self.vault_path = Path(vault_path).resolve()
        self.drafts_dir = self.vault_path / "Drafts" / "payments"
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        self.secondary_threshold = secondary_threshold
        logger.info(
            "PaymentDraftCreator initialised  drafts_dir=%s  secondary_threshold=%.2f",
            self.drafts_dir,
            self.secondary_threshold,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_payment_draft(self, invoice_data: dict) -> Path:
        """
        Create a payment draft file in ``Drafts/payments/``.

        Args:
            invoice_data: Dictionary containing at minimum:
                - ``amount`` (float): Payment amount.
                - ``currency`` (str): ISO 4217 code (e.g. ``"USD"``).
                - ``recipient`` (str): Payee name or identifier.
                - ``due_date`` (str): ISO-format due date.
                - ``invoice_ref`` (str): Reference number of the invoice.
                Optionally:
                - ``description`` (str): Freeform description.
                - ``expiry_hours`` (int): Custom expiry window.

        Returns:
            Path to the created draft file.

        Raises:
            ValueError: If required keys are missing from *invoice_data*.
        """
        # Validate required fields
        required_keys = ("amount", "currency", "recipient", "due_date", "invoice_ref")
        missing = [k for k in required_keys if k not in invoice_data]
        if missing:
            raise ValueError(f"Missing required invoice_data keys: {', '.join(missing)}")

        self.drafts_dir.mkdir(parents=True, exist_ok=True)

        draft_id = str(uuid.uuid4())
        short_id = draft_id[:8]
        now = datetime.now(timezone.utc)
        expiry_hours = invoice_data.get("expiry_hours", _DEFAULT_EXPIRY_HOURS)
        expires_at = now + timedelta(hours=expiry_hours)

        amount: float = float(invoice_data["amount"])
        currency: str = str(invoice_data["currency"]).upper()
        recipient: str = str(invoice_data["recipient"])
        due_date: str = str(invoice_data["due_date"])
        invoice_ref: str = str(invoice_data["invoice_ref"])
        description: str = str(invoice_data.get("description", ""))

        needs_secondary = self._check_secondary_approval(amount)

        # Determine priority based on due-date proximity
        priority = self._compute_priority(due_date, amount)

        # Build YAML frontmatter
        frontmatter: dict = {
            "draft-id": draft_id,
            "type": "payment",
            "amount": amount,
            "currency": currency,
            "recipient": recipient,
            "due-date": due_date,
            "invoice-ref": invoice_ref,
            "priority": priority,
            "created-at": now.isoformat(),
            "expires-at": expires_at.isoformat(),
            "status": "pending",
            "approval_required": True,
            "secondary_approval_required": needs_secondary,
        }

        yaml_block = yaml.dump(
            frontmatter,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

        # Build body
        secondary_note = " **[DUAL-SIGN REQUIRED]**" if needs_secondary else ""
        body_lines = [
            f"# Payment Draft: {invoice_ref}",
            "",
            f"**Recipient:** {recipient}",
            f"**Amount:** {currency} {amount:,.2f}{secondary_note}",
            f"**Due Date:** {due_date}",
            f"**Priority:** {priority}",
            f"**Invoice Ref:** {invoice_ref}",
            "",
        ]

        if description:
            body_lines.extend([
                "## Description",
                "",
                description,
                "",
            ])

        body_lines.extend([
            "## Approval Status",
            "",
            f"- [{'x' if False else ' '}] Primary approval",
        ])

        if needs_secondary:
            body_lines.extend([
                f"- [ ] Secondary approval (amount > {currency} {self.secondary_threshold:,.2f})",
            ])

        body_lines.extend([
            "",
            f"**Expires:** {expires_at.strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## Actions",
            "",
            "- To **approve**: move this file to `Approved/`",
            "- To **reject**: move this file to `Rejected/`",
            "",
            "---",
            "_Auto-generated by PaymentDraftCreator_",
        ])

        content = f"---\n{yaml_block}---\n\n" + "\n".join(body_lines) + "\n"

        # Filename
        recipient_slug = re.sub(r"[^a-z0-9]+", "-", recipient.lower()).strip("-")
        filename = f"PAYMENT_DRAFT_{recipient_slug}_{short_id}.md"
        file_path = self.drafts_dir / filename

        file_path.write_text(content, encoding="utf-8")
        logger.info(
            "Created payment draft  id=%s amount=%s %s recipient=%s secondary=%s path=%s",
            draft_id,
            currency,
            amount,
            recipient,
            needs_secondary,
            file_path,
        )
        return file_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_secondary_approval(self, amount: float) -> bool:
        """
        Determine whether secondary (dual-sign) approval is required.

        Args:
            amount: The payment amount.

        Returns:
            ``True`` if the amount exceeds :attr:`secondary_threshold`.
        """
        return amount > self.secondary_threshold

    def _compute_priority(self, due_date: str, amount: float) -> str:
        """
        Compute payment priority based on due-date proximity and amount.

        Rules:
        - **high**: due within 3 days, OR amount > 5x secondary threshold.
        - **medium**: due within 7 days, OR amount > secondary threshold.
        - **low**: everything else.

        Args:
            due_date: ISO-format date string (``YYYY-MM-DD``).
            amount:   Payment amount.

        Returns:
            Priority string: ``"high"``, ``"medium"``, or ``"low"``.
        """
        try:
            due = datetime.fromisoformat(due_date).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            # Cannot parse due date -- default to medium
            return "medium"

        now = datetime.now(timezone.utc)
        days_until_due = (due - now).days

        if days_until_due <= 3 or amount > self.secondary_threshold * 5:
            return "high"
        if days_until_due <= 7 or amount > self.secondary_threshold:
            return "medium"
        return "low"
