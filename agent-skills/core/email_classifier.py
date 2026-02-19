# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///

"""
Email Priority Classifier

Classifies incoming emails as high, medium, or low priority based on
sender reputation (known contacts), subject/body keywords, and Gmail
labels.  Designed for the Platinum Tier AI Employee pipeline.

Priority rules
--------------
HIGH:   urgent/asap/critical/emergency/deadline keywords,
        OR sender is a VIP contact,
        OR email has STARRED label.
MEDIUM: meeting/review/update/report/reminder/follow-up keywords,
        OR sender is a known (non-VIP) contact.
LOW:    everything else (newsletters, marketing, generic notifications).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword sets
# ---------------------------------------------------------------------------
_HIGH_KEYWORDS: set[str] = {
    "urgent",
    "asap",
    "critical",
    "emergency",
    "deadline",
    "immediately",
    "action required",
    "time sensitive",
    "escalation",
    "blocker",
}

_MEDIUM_KEYWORDS: set[str] = {
    "meeting",
    "review",
    "update",
    "report",
    "reminder",
    "follow-up",
    "follow up",
    "followup",
    "agenda",
    "schedule",
    "proposal",
    "feedback",
    "discussion",
    "sync",
}

_LOW_SIGNALS: set[str] = {
    "unsubscribe",
    "newsletter",
    "marketing",
    "notification",
    "no-reply",
    "noreply",
    "promo",
    "advertisement",
}

# Gmail labels that signal priority
_HIGH_LABELS: set[str] = {"STARRED"}
_MEDIUM_LABELS: set[str] = {"IMPORTANT"}


class EmailClassifier:
    """Classify an email dict into ``high``, ``medium``, or ``low`` priority."""

    def __init__(self, vault_path: str) -> None:
        self._vault_path = Path(vault_path)
        self._contacts: dict[str, str] = {}  # email -> priority ("vip" | "known")
        self._load_contacts()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, email_data: dict) -> str:
        """Return ``"high"``, ``"medium"``, or ``"low"`` for *email_data*.

        Expected keys in *email_data*:
            - ``from``  (str): sender email address
            - ``subject`` (str): email subject line
            - ``body`` (str, optional): plain-text body
            - ``labels`` (list[str], optional): Gmail label IDs
        """
        from_email: str = email_data.get("from", "")
        subject: str = email_data.get("subject", "")
        body: str = email_data.get("body", "")
        labels: list[str] = email_data.get("labels", [])

        # Collect signals -- highest priority wins.
        sender_priority = self._check_sender(from_email)
        keyword_priority = self._check_keywords(subject, body)
        label_priority = self._check_labels(labels)

        signals: list[str] = [
            s for s in (sender_priority, keyword_priority, label_priority) if s is not None
        ]

        if not signals:
            logger.debug("No priority signals found for email from=%s subject=%r", from_email, subject)
            return "low"

        # Rank: high > medium > low
        rank = {"high": 0, "medium": 1, "low": 2}
        best = min(signals, key=lambda s: rank.get(s, 3))
        logger.info(
            "Classified email from=%s subject=%r as %s (signals=%s)",
            from_email,
            subject,
            best,
            signals,
        )
        return best

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_sender(self, from_email: str) -> Optional[str]:
        """Return priority level if *from_email* is a known contact."""
        if not from_email:
            return None

        email_lower = from_email.strip().lower()
        # Handle "Name <email>" format
        match = re.search(r"<([^>]+)>", email_lower)
        if match:
            email_lower = match.group(1)

        level = self._contacts.get(email_lower)
        if level == "vip":
            return "high"
        if level == "known":
            return "medium"
        return None

    def _check_keywords(self, subject: str, body: str) -> str:
        """Return keyword-based classification of subject + body text."""
        text = f"{subject} {body}".lower()

        for kw in _HIGH_KEYWORDS:
            if kw in text:
                return "high"

        for kw in _MEDIUM_KEYWORDS:
            if kw in text:
                return "medium"

        return "low"

    def _check_labels(self, labels: list) -> Optional[str]:
        """Return priority signal from Gmail labels, or ``None``."""
        if not labels:
            return None

        label_set = {str(lbl).upper() for lbl in labels}

        if label_set & _HIGH_LABELS:
            return "high"
        if label_set & _MEDIUM_LABELS:
            return "medium"

        return None

    # ------------------------------------------------------------------
    # Contact loading
    # ------------------------------------------------------------------

    def _load_contacts(self) -> None:
        """Load known contacts from ``obsidian-vault/contacts.yaml``.

        Expected YAML structure::

            contacts:
              - email: alice@example.com
                priority: vip        # or "known"
              - email: bob@example.com
                priority: known
        """
        contacts_file = self._vault_path / "contacts.yaml"
        if not contacts_file.exists():
            logger.debug("No contacts file found at %s; skipping contact loading.", contacts_file)
            return

        try:
            with open(contacts_file, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except Exception:
            logger.warning("Failed to parse contacts file at %s", contacts_file, exc_info=True)
            return

        if not isinstance(data, dict):
            logger.warning("Contacts file has unexpected format (expected mapping).")
            return

        entries = data.get("contacts", [])
        if not isinstance(entries, list):
            logger.warning("'contacts' key should be a list; got %s.", type(entries).__name__)
            return

        for entry in entries:
            email = str(entry.get("email", "")).strip().lower()
            priority = str(entry.get("priority", "known")).strip().lower()
            if email:
                self._contacts[email] = priority if priority in ("vip", "known") else "known"

        logger.info("Loaded %d contacts from %s", len(self._contacts), contacts_file)
