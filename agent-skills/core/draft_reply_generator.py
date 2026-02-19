# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
Draft Reply Generator — reads email content + Company_Handbook.md context
and generates a suggested reply template with placeholders for the CEO.

Part of the Platinum Tier AI Employee. Produces professional draft replies
that reference handbook context (pricing, services, contacts) and leave
clear placeholders ([SPECIFIC_DETAILS], [DECISION], [TIMELINE], [YOUR_NAME])
for human review before sending.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class DraftReplyGenerator:
    """Generates draft email reply templates using Company Handbook context."""

    # Keywords that map to handbook sections for context extraction
    _SECTION_KEYWORDS: Dict[str, List[str]] = {
        "Communication Rules": [
            "email", "reply", "response", "priority", "urgent",
        ],
        "Key Contacts": [
            "contact", "client", "supplier", "team", "vendor",
        ],
        "Business Hours": [
            "hours", "schedule", "availability", "timezone", "meeting",
        ],
        "About the Company": [
            "company", "service", "pricing", "product", "industry",
            "plan", "subscription", "quote", "proposal", "offer",
        ],
    }

    def __init__(self, vault_path: str) -> None:
        """
        Load Company_Handbook.md from the vault if it exists.

        Args:
            vault_path: Path to the Obsidian vault directory.
        """
        self.vault_path = Path(vault_path).resolve()
        self.handbook_content: str = ""
        self._handbook_sections: Dict[str, str] = {}

        handbook_path = self.vault_path / "Company_Handbook.md"
        if handbook_path.exists():
            try:
                self.handbook_content = handbook_path.read_text(encoding="utf-8")
                self._handbook_sections = self._parse_sections(self.handbook_content)
                logger.info("Loaded Company Handbook from %s", handbook_path)
            except OSError as exc:
                logger.warning("Could not read Company Handbook: %s", exc)
        else:
            logger.info("No Company_Handbook.md found at %s — proceeding without context", handbook_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_reply(self, email_data: dict) -> str:
        """
        Generate a complete draft reply for the given email.

        Args:
            email_data: Dict with keys: from_email, from_name, subject,
                        body_snippet, priority, thread_id.

        Returns:
            A multi-line draft reply string with placeholders.
        """
        from_name: str = email_data.get("from_name", "")
        subject: str = email_data.get("subject", "")
        body_snippet: str = email_data.get("body_snippet", "")
        priority: str = email_data.get("priority", "medium").lower()

        context = self._extract_context(subject, body_snippet)

        parts: List[str] = []
        parts.append(self._build_greeting(from_name))

        if priority == "high":
            parts.append(
                "I wanted to acknowledge your message right away — "
                "I understand this is urgent and I am treating it as a top priority.\n"
            )

        parts.append(self._build_reply_body(email_data, context))
        parts.append(self._build_closing())

        draft = "\n".join(parts)

        logger.debug(
            "Generated draft reply for thread_id=%s subject=%r",
            email_data.get("thread_id", "?"),
            subject,
        )
        return draft

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_context(self, subject: str, body: str) -> str:
        """
        Extract relevant sections from the Company Handbook by matching
        keywords found in the email subject and body.

        Args:
            subject: The email subject line.
            body: The email body snippet.

        Returns:
            A string with relevant handbook excerpts, or empty string.
        """
        if not self._handbook_sections:
            return ""

        combined_text = f"{subject} {body}".lower()
        matched_sections: List[str] = []

        for section_name, keywords in self._SECTION_KEYWORDS.items():
            if section_name not in self._handbook_sections:
                continue
            if any(kw in combined_text for kw in keywords):
                matched_sections.append(self._handbook_sections[section_name])

        if not matched_sections:
            return ""

        return "\n\n".join(matched_sections)

    def _build_greeting(self, from_name: str) -> str:
        """
        Generate an appropriate greeting addressing the sender by name.

        Args:
            from_name: The sender's display name.

        Returns:
            A greeting line.
        """
        if from_name and from_name.strip():
            # Use first name only for a friendlier tone
            first_name = from_name.strip().split()[0]
            return f"Hi {first_name},\n"
        return "Hello,\n"

    def _build_reply_body(self, email_data: dict, context: str) -> str:
        """
        Build the main body of the reply, referencing the email topic and
        including handbook context where applicable.

        Args:
            email_data: The full email data dict.
            context: Relevant handbook excerpts (may be empty).

        Returns:
            The reply body with placeholders.
        """
        subject: str = email_data.get("subject", "your recent email")
        body_snippet: str = email_data.get("body_snippet", "")
        priority: str = email_data.get("priority", "medium").lower()

        lines: List[str] = []

        # Acknowledge the topic
        lines.append(
            f'Thank you for reaching out regarding "{subject}". '
            "I have reviewed the details you shared.\n"
        )

        # Include handbook context when relevant
        if context:
            lines.append(
                "For reference, here is some relevant information from our records:\n"
            )
            # Indent the context block so it reads like a quote
            for ctx_line in context.splitlines():
                lines.append(f"> {ctx_line}")
            lines.append("")  # blank line after the quote block

        # Pricing / services detection — add a specific note
        pricing_keywords = {"pricing", "price", "quote", "proposal", "cost", "rate", "service", "plan"}
        combined = f"{subject} {body_snippet}".lower()
        if any(kw in combined for kw in pricing_keywords):
            lines.append(
                "Regarding pricing and services: [SPECIFIC_DETAILS]\n"
            )

        # Core placeholder section
        lines.append("Here is my update on this matter:\n")
        lines.append("- Decision: [DECISION]")
        lines.append("- Details: [SPECIFIC_DETAILS]")
        lines.append("- Expected timeline: [TIMELINE]\n")

        # For high-priority, reinforce commitment
        if priority == "high":
            lines.append(
                "Given the urgency, I will follow up again by [TIMELINE] "
                "with a concrete update.\n"
            )

        lines.append(
            "Please let me know if you need any additional information "
            "or if you would like to discuss this further.\n"
        )

        return "\n".join(lines)

    def _build_closing(self) -> str:
        """
        Return a standard professional closing with a name placeholder.

        Returns:
            The closing lines.
        """
        return (
            "Best regards,\n"
            "[YOUR_NAME]"
        )

    # ------------------------------------------------------------------
    # Handbook parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_sections(markdown: str) -> Dict[str, str]:
        """
        Split a markdown document into sections keyed by heading text.
        Only considers level-2 (``##``) headings as section boundaries.

        Args:
            markdown: The raw markdown text.

        Returns:
            Dict mapping section heading text to the section body.
        """
        sections: Dict[str, str] = {}
        current_heading: Optional[str] = None
        current_lines: List[str] = []

        for line in markdown.splitlines():
            heading_match = re.match(r"^##\s+(.+)$", line)
            if heading_match:
                # Save previous section
                if current_heading is not None:
                    sections[current_heading] = "\n".join(current_lines).strip()
                current_heading = heading_match.group(1).strip()
                current_lines = []
            else:
                current_lines.append(line)

        # Save last section
        if current_heading is not None:
            sections[current_heading] = "\n".join(current_lines).strip()

        return sections
