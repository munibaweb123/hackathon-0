# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Social Media Formatters — platform-specific content formatting utilities.

Provides formatting functions for LinkedIn, Twitter/X, and Facebook posts
with platform-specific constraints (character limits, tone, hashtags).
"""

import re
from typing import List, Optional


def format_linkedin(content: str, hashtags: Optional[List[str]] = None) -> str:
    """
    Format content for LinkedIn with professional tone.

    Args:
        content: Raw post content.
        hashtags: Optional list of hashtag words (without #).

    Returns:
        Formatted LinkedIn post string.
    """
    lines = content.strip().splitlines()
    formatted = "\n".join(line.strip() for line in lines if line.strip())

    if hashtags:
        tag_line = " ".join(f"#{tag}" for tag in hashtags)
        formatted = f"{formatted}\n\n{tag_line}"

    return formatted


def format_twitter(content: str, max_chars: int = 280) -> str:
    """
    Format content for Twitter/X respecting character limit.

    Args:
        content: Raw post content.
        max_chars: Maximum character count (default 280).

    Returns:
        Formatted tweet string, truncated with ellipsis if needed.
    """
    # Collapse whitespace
    clean = re.sub(r"\s+", " ", content.strip())

    if len(clean) <= max_chars:
        return clean

    return clean[: max_chars - 1] + "\u2026"


def format_facebook(content: str) -> str:
    """
    Format content for Facebook (longer form, preserves paragraphs).

    Args:
        content: Raw post content.

    Returns:
        Formatted Facebook post string.
    """
    paragraphs = re.split(r"\n{2,}", content.strip())
    formatted = "\n\n".join(p.strip() for p in paragraphs if p.strip())
    return formatted
