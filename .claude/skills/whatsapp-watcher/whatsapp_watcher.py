# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "playwright>=1.40.0",
#     "python-dotenv>=1.0.0",
# ]
# ///
"""
WhatsApp Watcher Agent Skill

Monitors WhatsApp Web for urgent messages using Playwright automation
and creates action files in an Obsidian vault.

    uv run whatsapp_watcher.py --vault-path ../../obsidian-vault

First run opens a browser for QR code scanning. Subsequent runs
restore the session automatically.
"""

import argparse
import asyncio
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure local + sibling skill imports work
_SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SKILL_DIR))
sys.path.insert(0, str(_SKILL_DIR.parent / "gmail-watcher"))

from dotenv import load_dotenv  # noqa: E402

from base_watcher import BaseWatcher  # noqa: E402
from session_manager import SessionManager, SELECTORS  # noqa: E402

# ---------------------------------------------------------------------------
# Keywords & priority mapping
# ---------------------------------------------------------------------------

URGENT_KEYWORDS = ["urgent", "asap", "invoice", "payment", "help", "emergency"]

_HIGH_PRIORITY_KEYWORDS = {"urgent", "emergency", "invoice", "payment"}
_MEDIUM_PRIORITY_KEYWORDS = {"asap", "help"}


class WhatsAppWatcher(BaseWatcher):
    """
    Polls WhatsApp Web for unread messages containing urgent keywords
    and creates ``WHATSAPP_{timestamp}.md`` files in ``Needs_Action/``.
    """

    def __init__(
        self,
        vault_path: str,
        poll_interval: int = 30,
        headless: bool = False,
        session_dir: Optional[str] = None,
    ):
        super().__init__("whatsapp", vault_path, poll_interval)

        # Load env
        self._load_env()

        # Output dir
        self.needs_action_dir = self.vault_path / "Needs_Action"
        self.needs_action_dir.mkdir(parents=True, exist_ok=True)

        # Session + browser
        screenshots_dir = self.vault_path / "Logs" / "screenshots"
        self.session = SessionManager(
            session_dir=session_dir, screenshots_dir=screenshots_dir
        )
        self.headless = headless
        self._browser_ready = False

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _load_env(self) -> None:
        """Walk up from script dir to find .env."""
        search = Path(__file__).resolve().parent
        for _ in range(6):
            env_file = search / ".env"
            if env_file.exists():
                load_dotenv(env_file)
                return
            search = search.parent
        load_dotenv()

    async def _ensure_browser(self) -> bool:
        """Launch browser and authenticate if needed."""
        if self._browser_ready and self.session.page:
            return True

        self.logger.info("Launching browser (headless=%s) …", self.headless)
        await self.session.launch_browser(headless=self.headless)

        if await self.session.is_authenticated():
            self.logger.info("Session restored — already authenticated")
            self._browser_ready = True
            return True

        # Need QR scan — headless won't work
        if self.headless:
            self.logger.error(
                "No saved session and running headless. "
                "Run once without --headless to scan the QR code."
            )
            return False

        if await self.session.wait_for_qr_scan(timeout=120):
            self._browser_ready = True
            return True

        self.logger.error("Authentication failed — QR code was not scanned")
        return False

    # ------------------------------------------------------------------
    # Event detection
    # ------------------------------------------------------------------

    def detect_events(self) -> List[Dict[str, Any]]:
        """Sync wrapper around the async detection logic."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(
                        lambda: asyncio.run(self._detect_events_async())
                    ).result()
            return loop.run_until_complete(self._detect_events_async())
        except RuntimeError:
            return asyncio.run(self._detect_events_async())

    async def _detect_events_async(self) -> List[Dict[str, Any]]:
        """Scan WhatsApp Web for unread messages with urgent keywords."""
        if not await self._ensure_browser():
            return []

        events: List[Dict[str, Any]] = []
        page = self.session.page

        try:
            # Wait for chat list to be ready
            await page.wait_for_selector(SELECTORS["chat_list"], timeout=10000)

            # Get all chat rows
            chat_rows = await page.query_selector_all(SELECTORS["chat_row"])
            self.logger.debug("Found %d chat rows", len(chat_rows))

            for row in chat_rows:
                # Check for unread indicator
                unread = await row.query_selector(
                    '[data-testid="icon-unread-count"], '
                    'span[aria-label*="unread"]'
                )
                if not unread:
                    continue

                # Extract contact name
                title_el = await row.query_selector(SELECTORS["chat_title"])
                contact = await title_el.inner_text() if title_el else "Unknown"

                # Extract last message preview
                msg_spans = await row.query_selector_all("span[dir='auto']")
                message_text = ""
                for span in msg_spans:
                    text = await span.inner_text()
                    # Skip the contact name itself
                    if text and text != contact:
                        message_text = text
                        break

                if not message_text:
                    continue

                # Keyword matching
                matched = self._match_keywords(message_text)
                if not matched:
                    continue

                # Build event
                ts = datetime.now(timezone.utc)
                event_id = f"wa_{ts.strftime('%Y%m%d_%H%M%S')}_{contact[:10]}"

                events.append({
                    "id": event_id,
                    "contact": contact,
                    "message": message_text,
                    "received": ts,
                    "keywords_matched": matched,
                    "priority": self._determine_priority(matched),
                })

                self.logger.info(
                    "Urgent message from %s — keywords: %s",
                    contact, ", ".join(matched),
                )

                # Rate limiting — random delay between chat reads
                await asyncio.sleep(random.uniform(2, 5))

            # Take a screenshot if we found urgent messages
            if events:
                await self.session.take_screenshot("urgent_detected")

        except Exception as exc:
            self.logger.error("Error scanning chats: %s", exc, exc_info=True)

        self.logger.info("Detected %d urgent message(s)", len(events))
        return events

    # ------------------------------------------------------------------
    # Keyword matching & priority
    # ------------------------------------------------------------------

    @staticmethod
    def _match_keywords(text: str) -> List[str]:
        """Return list of urgent keywords found in the message text."""
        lower = text.lower()
        return [kw for kw in URGENT_KEYWORDS if kw in lower]

    @staticmethod
    def _determine_priority(keywords: List[str]) -> str:
        """Map matched keywords to a priority level."""
        kw_set = set(keywords)
        if kw_set & _HIGH_PRIORITY_KEYWORDS:
            return "high"
        if kw_set & _MEDIUM_PRIORITY_KEYWORDS:
            return "medium"
        return "medium"

    # ------------------------------------------------------------------
    # Event processing — create markdown file
    # ------------------------------------------------------------------

    def process_event(self, event: Dict[str, Any]) -> bool:
        """Create a WHATSAPP_{timestamp}.md file in Needs_Action/."""
        received = event["received"]
        ts_str = received.strftime("%Y%m%d_%H%M%S") if isinstance(received, datetime) else str(received)
        filename = f"WHATSAPP_{ts_str}.md"
        file_path = self.needs_action_dir / filename

        if file_path.exists():
            self.logger.debug("File already exists, skipping: %s", filename)
            return True

        try:
            content = self._build_markdown(event)
            file_path.write_text(content, encoding="utf-8")
            self.logger.info(
                "Created %s — from: %s, priority: %s",
                filename, event["contact"], event["priority"],
            )
            return True
        except OSError as exc:
            self.logger.error("Failed to write %s: %s", filename, exc)
            return False

    @staticmethod
    def _build_markdown(event: Dict[str, Any]) -> str:
        """Render event as markdown with YAML frontmatter."""
        received = event["received"]
        if isinstance(received, datetime):
            received_iso = received.isoformat()
            received_display = received.strftime("%Y-%m-%d %I:%M %p")
        else:
            received_iso = str(received)
            received_display = str(received)

        keywords_str = ", ".join(event["keywords_matched"])
        contact_escaped = str(event["contact"]).replace('"', '\\"')

        return (
            f"---\n"
            f"type: whatsapp\n"
            f'contact: "{contact_escaped}"\n'
            f"received: {received_iso}\n"
            f"priority: {event['priority']}\n"
            f"keywords_matched: [{keywords_str}]\n"
            f"status: needs_action\n"
            f"---\n"
            f"\n"
            f"## WhatsApp Message from {event['contact']}\n"
            f"\n"
            f"**Received:** {received_display}\n"
            f"**Priority:** {event['priority']}\n"
            f"**Keywords:** {keywords_str}\n"
            f"\n"
            f"### Message\n"
            f"\n"
            f"{event['message']}\n"
            f"\n"
            f"### Suggested Actions\n"
            f"\n"
            f"- [ ] Reply to {event['contact']}\n"
            f"- [ ] Forward to team\n"
            f"- [ ] Mark as handled\n"
        )

    # ------------------------------------------------------------------
    # Lifecycle overrides
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Override to handle async cleanup on exit."""
        try:
            super().run()
        finally:
            try:
                asyncio.run(self.session.close())
            except Exception:
                pass


# ------------------------------------------------------------------
# CLI entry-point
# ------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="WhatsApp Watcher — monitors WhatsApp Web for urgent messages"
    )
    parser.add_argument(
        "--vault-path",
        default=os.getenv("VAULT_PATH", "./obsidian-vault"),
        help="Path to the Obsidian vault (default: $VAULT_PATH or ./obsidian-vault)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Polling interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll cycle and exit",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (requires existing session)",
    )
    parser.add_argument(
        "--session-dir",
        default=None,
        help="Directory for session storage (default: ~/.whatsapp-watcher/)",
    )
    args = parser.parse_args()

    watcher = WhatsAppWatcher(
        vault_path=args.vault_path,
        poll_interval=args.interval,
        headless=args.headless,
        session_dir=args.session_dir,
    )

    if args.once:
        events = watcher.detect_events()
        count = 0
        for event in events:
            if not watcher._is_processed(event["id"]):
                if watcher.process_event(event):
                    watcher._mark_processed(event["id"])
                    count += 1
        print(f"Processed {count} urgent message(s)")
        asyncio.run(watcher.session.close())
    else:
        watcher.run()


if __name__ == "__main__":
    main()
