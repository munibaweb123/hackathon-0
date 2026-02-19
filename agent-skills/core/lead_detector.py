# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
Lead Detector -- Phase 7 (US5 -- Lead Capture) of the Platinum Tier AI Employee.

Scans incoming email data for lead signals (inquiry, RFP, partnership, quote
request keywords) and, when a lead is detected, creates a structured lead file
inside the vault at ``Needs_Action/cloud/leads/`` with YAML frontmatter.

Lead Signals (keywords):
    inquiry, quote, proposal, RFP, partnership, collaborate,
    interested in, pricing, demo, trial

Self-contained: depends only on the Python stdlib and PyYAML.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lead-signal keywords (lowercase)
# ---------------------------------------------------------------------------
_LEAD_KEYWORDS: set[str] = {
    "inquiry",
    "quote",
    "proposal",
    "rfp",
    "partnership",
    "collaborate",
    "interested in",
    "pricing",
    "demo",
    "trial",
}

# Mapping keywords -> request type classification
_REQUEST_TYPE_KEYWORDS: dict[str, list[str]] = {
    "rfp": ["rfp", "request for proposal"],
    "quote": ["quote", "pricing", "cost", "estimate"],
    "partnership": ["partnership", "collaborate", "collaboration", "joint venture"],
    "inquiry": ["inquiry", "interested in", "demo", "trial", "proposal", "information"],
}

# Urgency signals for priority scoring
_URGENCY_SIGNALS: set[str] = {
    "urgent",
    "asap",
    "immediately",
    "deadline",
    "time sensitive",
    "critical",
    "rush",
    "expedite",
}


class LeadDetector:
    """Detects potential leads from email data and creates structured lead files."""

    def __init__(self, vault_path: str) -> None:
        """
        Initialise the lead detector.

        Args:
            vault_path: Absolute path to the Obsidian vault directory.
        """
        self.vault_path = Path(vault_path).resolve()
        self.leads_dir = self.vault_path / "Needs_Action" / "cloud" / "leads"
        self.leads_dir.mkdir(parents=True, exist_ok=True)
        logger.info("LeadDetector initialised  leads_dir=%s", self.leads_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_lead(self, email_data: dict) -> Optional[dict]:
        """
        Analyse an email for lead signals.

        Args:
            email_data: Dictionary with keys ``from_email``, ``from_name``,
                        ``subject``, ``body``, ``message_id`` (and optionally
                        ``labels``).

        Returns:
            A lead dictionary if signals are detected, otherwise ``None``.
        """
        subject: str = email_data.get("subject", "")
        body: str = email_data.get("body", "")
        combined = f"{subject} {body}".lower()

        matched_keywords = [kw for kw in _LEAD_KEYWORDS if kw in combined]
        if not matched_keywords:
            logger.debug("No lead signals in email %s", email_data.get("message_id", "?"))
            return None

        from_email: str = email_data.get("from_email", "")
        from_name: str = email_data.get("from_name", "")
        request_type = self._classify_request(subject, body)
        priority = self._score_priority(request_type, body)
        company = self._extract_company(from_email, body)

        lead_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        lead: dict = {
            "lead_id": lead_id,
            "type": "lead",
            "status": "new",
            "company": company,
            "contact_name": from_name,
            "contact_email": from_email,
            "request_type": request_type,
            "source": "email",
            "priority": priority,
            "created_at": now.isoformat(),
            "original_email_id": email_data.get("message_id", ""),
            "matched_keywords": matched_keywords,
            "subject": subject,
        }

        logger.info(
            "Lead detected  id=%s company=%s type=%s priority=%s keywords=%s",
            lead_id,
            company,
            request_type,
            priority,
            matched_keywords,
        )
        return lead

    def create_lead_file(self, lead: dict) -> Path:
        """
        Create a structured Markdown file with YAML frontmatter for a lead.

        Args:
            lead: Lead dictionary as returned by :meth:`detect_lead`.

        Returns:
            Path to the created lead file.
        """
        self.leads_dir.mkdir(parents=True, exist_ok=True)

        lead_id: str = lead["lead_id"]
        short_id = lead_id[:8]
        company_slug = re.sub(r"[^a-z0-9]+", "-", lead.get("company", "unknown").lower()).strip("-")
        filename = f"LEAD_{company_slug}_{short_id}.md"
        file_path = self.leads_dir / filename

        # Build YAML frontmatter
        frontmatter: dict = {
            "lead-id": lead["lead_id"],
            "type": "lead",
            "status": "new",
            "company": lead.get("company", "unknown"),
            "contact-name": lead.get("contact_name", ""),
            "contact-email": lead.get("contact_email", ""),
            "request-type": lead.get("request_type", "inquiry"),
            "source": "email",
            "priority": lead.get("priority", "medium"),
            "created-at": lead.get("created_at", datetime.now(timezone.utc).isoformat()),
            "original-email-id": lead.get("original_email_id", ""),
        }

        yaml_block = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False, allow_unicode=True)

        body_lines = [
            f"# Lead: {lead.get('company', 'Unknown Company')}",
            "",
            f"**Contact:** {lead.get('contact_name', 'N/A')} <{lead.get('contact_email', '')}>",
            f"**Request Type:** {lead.get('request_type', 'inquiry')}",
            f"**Priority:** {lead.get('priority', 'medium')}",
            f"**Source:** email",
            f"**Detected Keywords:** {', '.join(lead.get('matched_keywords', []))}",
            "",
            "## Original Email Subject",
            "",
            f"> {lead.get('subject', 'N/A')}",
            "",
            "## Next Steps",
            "",
            "- [ ] Review lead details",
            "- [ ] Respond to inquiry",
            "- [ ] Add to CRM / pipeline",
            "",
            "---",
            "_Auto-generated by LeadDetector_",
        ]

        content = f"---\n{yaml_block}---\n\n" + "\n".join(body_lines) + "\n"
        file_path.write_text(content, encoding="utf-8")
        logger.info("Created lead file at %s", file_path)
        return file_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_company(self, email: str, body: str) -> str:
        """
        Extract a company name from the sender's email domain.

        Falls back to ``"unknown"`` when the domain is a common free-mail
        provider or cannot be parsed.

        Args:
            email: Sender email address.
            body:  Email body text (reserved for future NLP extraction).

        Returns:
            Best-guess company name string.
        """
        free_providers = {
            "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
            "aol.com", "icloud.com", "mail.com", "protonmail.com",
            "zoho.com", "yandex.com", "live.com",
        }

        match = re.search(r"@([\w.-]+)", email)
        if not match:
            return "unknown"

        domain = match.group(1).lower()
        if domain in free_providers:
            # Cannot reliably infer company from free-mail domain
            return "unknown"

        # Use the second-level domain as company name, capitalised
        parts = domain.split(".")
        if len(parts) >= 2:
            company = parts[-2].capitalize()
        else:
            company = parts[0].capitalize()

        return company

    def _classify_request(self, subject: str, body: str) -> str:
        """
        Classify the lead request type based on subject and body keywords.

        Returns one of: ``inquiry``, ``rfp``, ``partnership``, ``quote``.
        Defaults to ``inquiry`` when no stronger signal is found.

        Args:
            subject: Email subject line.
            body:    Email body text.
        """
        combined = f"{subject} {body}".lower()

        # Check in priority order: rfp > quote > partnership > inquiry
        for request_type in ("rfp", "quote", "partnership", "inquiry"):
            keywords = _REQUEST_TYPE_KEYWORDS.get(request_type, [])
            if any(kw in combined for kw in keywords):
                return request_type

        return "inquiry"

    def _score_priority(self, request_type: str, body: str) -> str:
        """
        Score the lead priority as ``high``, ``medium``, or ``low``.

        Scoring rules:
        - **high**: RFP request type, OR urgency signals present in body.
        - **medium**: quote or partnership request type.
        - **low**: everything else (generic inquiry).

        Args:
            request_type: The classified request type.
            body:         Email body text.
        """
        body_lower = body.lower()

        # Urgency signals always bump to high
        if any(signal in body_lower for signal in _URGENCY_SIGNALS):
            return "high"

        # RFP is inherently high-priority
        if request_type == "rfp":
            return "high"

        # Quote / partnership are medium
        if request_type in ("quote", "partnership"):
            return "medium"

        return "low"
