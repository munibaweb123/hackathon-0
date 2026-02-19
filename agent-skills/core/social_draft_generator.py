# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
Social Draft Generator — reads Business_Goals.md from the Obsidian vault
and generates platform-specific social media post drafts.

Part of Phase 5 (US3 — Social Media Post Drafting) of the Platinum Tier
AI Employee.  Drafts are written to Drafts/social/ with DraftLifecycle-
compatible YAML frontmatter (draft-id, type, platform, priority,
created-at, expires-at, status, approval_required).
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

_EXPIRATION_HOURS = 48
_DEFAULT_PLATFORMS = ["linkedin", "twitter", "facebook"]


class SocialDraftGenerator:
    """Generates social-media post drafts from Business_Goals.md context."""

    def __init__(self, vault_path: str) -> None:
        """
        Initialise the generator and load Business_Goals.md if it exists.

        Args:
            vault_path: Absolute path to the Obsidian vault directory.
        """
        self.vault_path = Path(vault_path).resolve()
        self.goals_content: str = ""
        self._goals_sections: Dict[str, str] = {}

        goals_path = self.vault_path / "Business_Goals.md"
        if goals_path.exists():
            try:
                self.goals_content = goals_path.read_text(encoding="utf-8")
                self._goals_sections = self._parse_sections(self.goals_content)
                logger.info("Loaded Business_Goals.md from %s", goals_path)
            except OSError as exc:
                logger.warning("Could not read Business_Goals.md: %s", exc)
        else:
            logger.info(
                "No Business_Goals.md found at %s — proceeding without goals context",
                goals_path,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_drafts(
        self,
        platforms: Optional[List[str]] = None,
    ) -> List[Path]:
        """
        Generate draft files for each requested platform.

        Extracts topics from Business_Goals.md, then creates one draft per
        topic per platform in ``Drafts/social/``.

        Args:
            platforms: List of platform names (default: linkedin, twitter,
                       facebook).

        Returns:
            List of ``Path`` objects for every draft file written.
        """
        if platforms is None:
            platforms = list(_DEFAULT_PLATFORMS)

        topics = self._extract_topics()
        if not topics:
            logger.warning("No topics extracted — cannot generate drafts")
            return []

        created_paths: List[Path] = []
        for topic in topics:
            topic_name: str = topic.get("topic", "general update")
            context: str = topic.get("context", "")

            for platform in platforms:
                content = self._generate_for_platform(platform, topic_name, context)
                if content is None:
                    logger.warning("Unknown platform %r — skipping", platform)
                    continue
                path = self._write_draft(platform, topic_name, content)
                created_paths.append(path)
                logger.info(
                    "Created %s draft for topic %r -> %s",
                    platform,
                    topic_name,
                    path,
                )

        return created_paths

    # ------------------------------------------------------------------
    # Platform-specific generators
    # ------------------------------------------------------------------

    def _generate_linkedin_draft(self, topic: str, context: str) -> str:
        """
        Generate a LinkedIn post draft with a professional tone and hashtags.

        Args:
            topic: The post topic / headline.
            context: Supporting context from Business_Goals.md.

        Returns:
            Formatted LinkedIn post string.
        """
        hashtags = self._derive_hashtags(topic, context)
        hashtag_line = " ".join(f"#{tag}" for tag in hashtags) if hashtags else ""

        lines: List[str] = []
        lines.append(f"**{topic}**\n")

        if context:
            lines.append(
                "We are excited to share a key update from our strategic roadmap:\n"
            )
            lines.append(f"{context}\n")
        else:
            lines.append(
                "We are pleased to announce progress on an important business initiative.\n"
            )

        lines.append(
            "This reflects our ongoing commitment to delivering value to our "
            "clients and stakeholders.\n"
        )
        lines.append("Thoughts? We would love to hear from our network.\n")

        if hashtag_line:
            lines.append(hashtag_line)

        return "\n".join(lines)

    def _generate_twitter_draft(self, topic: str, context: str) -> str:
        """
        Generate a Twitter/X post draft respecting the 280-character limit.

        Args:
            topic: The post topic / headline.
            context: Supporting context from Business_Goals.md.

        Returns:
            Formatted tweet string (max 280 characters).
        """
        hashtags = self._derive_hashtags(topic, context, max_tags=2)
        hashtag_line = " ".join(f"#{tag}" for tag in hashtags) if hashtags else ""

        if context:
            core = f"{topic} — {context}"
        else:
            core = topic

        # Reserve space for hashtags (plus a leading space)
        reserved = len(hashtag_line) + 1 if hashtag_line else 0
        max_core = 280 - reserved

        if len(core) > max_core:
            core = core[: max_core - 1] + "\u2026"  # ellipsis

        if hashtag_line:
            return f"{core} {hashtag_line}"
        return core

    def _generate_facebook_draft(self, topic: str, context: str) -> str:
        """
        Generate a longer-form Facebook post draft.

        Args:
            topic: The post topic / headline.
            context: Supporting context from Business_Goals.md.

        Returns:
            Formatted Facebook post string.
        """
        lines: List[str] = []
        lines.append(f"{topic}\n")

        if context:
            lines.append(f"{context}\n")

        lines.append(
            "We believe in keeping our community informed about the direction "
            "we are heading.  Your support and feedback mean a great deal to us.\n"
        )
        lines.append(
            "Feel free to share your thoughts in the comments — "
            "we read every single one!"
        )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Topic extraction
    # ------------------------------------------------------------------

    def _extract_topics(self) -> List[Dict[str, str]]:
        """
        Extract topics from Business_Goals.md.

        Looks for Markdown headings (``## ...``) and gathers the body text
        under each heading as context.

        Returns:
            A list of dicts, each with ``topic`` and ``context`` keys.
        """
        if not self.goals_content:
            return []

        topics: List[Dict[str, str]] = []
        current_topic: Optional[str] = None
        current_lines: List[str] = []

        for line in self.goals_content.splitlines():
            heading_match = re.match(r"^##\s+(.+)$", line)
            if heading_match:
                # Flush the previous topic
                if current_topic is not None:
                    topics.append({
                        "topic": current_topic.strip(),
                        "context": "\n".join(current_lines).strip(),
                    })
                current_topic = heading_match.group(1)
                current_lines = []
            elif current_topic is not None:
                current_lines.append(line)

        # Flush the last topic
        if current_topic is not None:
            topics.append({
                "topic": current_topic.strip(),
                "context": "\n".join(current_lines).strip(),
            })

        logger.debug("Extracted %d topics from Business_Goals.md", len(topics))
        return topics

    # ------------------------------------------------------------------
    # Draft writing
    # ------------------------------------------------------------------

    def _write_draft(self, platform: str, topic: str, content: str) -> Path:
        """
        Write a single draft file to ``Drafts/social/`` with
        DraftLifecycle-compatible frontmatter.

        Args:
            platform: Target platform (linkedin, twitter, facebook).
            topic: Topic slug used in the draft-id.
            content: The formatted post content.

        Returns:
            Path to the created draft file.
        """
        drafts_dir = self.vault_path / "Drafts" / "social"
        drafts_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=_EXPIRATION_HOURS)

        seq = self._next_sequence(drafts_dir, platform)
        draft_id = f"draft-social-post-{platform}-{now.strftime('%Y-%m-%d')}-{seq:03d}"

        slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:40]

        frontmatter: Dict[str, Any] = {
            "draft-id": draft_id,
            "type": "social-post",
            "platform": platform,
            "priority": "medium",
            "created-at": now.isoformat(),
            "expires-at": expires.isoformat(),
            "status": "pending",
            "approval_required": True,
        }

        filename = f"{draft_id}-{slug}.md"
        file_path = drafts_dir / filename
        file_content = (
            f"---\n"
            f"{yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)}"
            f"---\n\n"
            f"{content}\n"
        )
        file_path.write_text(file_content, encoding="utf-8")
        logger.info(
            "Wrote draft %s (%s, platform=%s)",
            draft_id,
            "social-post",
            platform,
        )
        return file_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _generate_for_platform(
        self,
        platform: str,
        topic: str,
        context: str,
    ) -> Optional[str]:
        """Dispatch to the correct platform generator."""
        generators = {
            "linkedin": self._generate_linkedin_draft,
            "twitter": self._generate_twitter_draft,
            "facebook": self._generate_facebook_draft,
        }
        gen = generators.get(platform)
        if gen is None:
            return None
        return gen(topic, context)

    @staticmethod
    def _derive_hashtags(
        topic: str,
        context: str,
        max_tags: int = 5,
    ) -> List[str]:
        """
        Derive hashtags from topic and context by extracting prominent
        words (length >= 4, capitalised or frequent).

        Args:
            topic: Post topic string.
            context: Post context string.
            max_tags: Maximum number of hashtags to return.

        Returns:
            List of hashtag words (without the ``#`` prefix).
        """
        combined = f"{topic} {context}"
        words = re.findall(r"[A-Za-z]{4,}", combined)

        # Simple frequency-based selection; prefer capitalised words
        freq: Dict[str, int] = {}
        for w in words:
            key = w.capitalize()
            freq[key] = freq.get(key, 0) + 1

        sorted_words = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
        return [w for w, _ in sorted_words[:max_tags]]

    @staticmethod
    def _next_sequence(directory: Path, prefix: str) -> int:
        """
        Determine the next sequential number for drafts in *directory*
        whose filenames start with a draft-id containing *prefix*.

        Args:
            directory: The drafts subdirectory to scan.
            prefix: A platform or type prefix to filter on.

        Returns:
            The next available sequence number (starting at 1).
        """
        max_seq = 0
        pattern = re.compile(rf"draft-.*{re.escape(prefix)}.*-(\d{{3}})")
        for child in directory.iterdir():
            m = pattern.search(child.stem)
            if m:
                max_seq = max(max_seq, int(m.group(1)))
        return max_seq + 1

    @staticmethod
    def _parse_sections(text: str) -> Dict[str, str]:
        """
        Parse Markdown text into a dict mapping heading -> body text.

        Only ``##`` level headings are considered.

        Args:
            text: Raw Markdown content.

        Returns:
            Dict of section name to section body.
        """
        sections: Dict[str, str] = {}
        current_heading: Optional[str] = None
        current_lines: List[str] = []

        for line in text.splitlines():
            m = re.match(r"^##\s+(.+)$", line)
            if m:
                if current_heading is not None:
                    sections[current_heading] = "\n".join(current_lines).strip()
                current_heading = m.group(1).strip()
                current_lines = []
            elif current_heading is not None:
                current_lines.append(line)

        if current_heading is not None:
            sections[current_heading] = "\n".join(current_lines).strip()

        return sections
