"""
WhatsApp Session Manager

Handles Playwright browser lifecycle, persistent session storage,
QR code authentication, and screenshot capture for the WhatsApp watcher.

Session data is stored outside the Obsidian vault for security.
Default location: ~/.whatsapp-watcher/
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("watcher.whatsapp.session")

# WhatsApp Web selectors
SELECTORS = {
    "chat_list": '[data-testid="chat-list"]',
    "qr_canvas": "canvas",
    "qr_container": '[data-testid="qrcode"]',
    "search_box": '[data-testid="chat-list-search"]',
    "unread_badge": '[data-testid="icon-unread-count"]',
    "chat_row": '[data-testid="cell-frame-container"]',
    "message_text": '[data-testid="msg-container"]',
    "chat_title": "header span[dir='auto']",
    "last_message": "span[dir='auto'].matched-text, span[dir='auto']",
}


class SessionManager:
    """
    Manages Playwright browser sessions for WhatsApp Web.

    Stores session state outside the vault (default ~/.whatsapp-watcher/)
    to keep authentication tokens secure.
    """

    def __init__(
        self,
        session_dir: Optional[str] = None,
        screenshots_dir: Optional[Path] = None,
    ):
        self.session_dir = Path(
            session_dir or Path.home() / ".whatsapp-watcher"
        )
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.session_dir / "session.json"

        self.screenshots_dir = screenshots_dir
        if self.screenshots_dir:
            self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    async def launch_browser(self, headless: bool = False) -> "Page":
        """
        Launch Chromium and restore session if available.

        Args:
            headless: Run without GUI (only works after QR auth is done).

        Returns:
            The main Playwright Page object.
        """
        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()

        # Restore previous session if it exists
        storage_state = str(self.session_file) if self.session_file.exists() else None

        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        self.context = await self.browser.new_context(
            storage_state=storage_state,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        self.page = await self.context.new_page()

        # Navigate to WhatsApp Web
        await self.page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
        logger.info("Browser launched — navigated to WhatsApp Web")

        return self.page

    async def is_authenticated(self) -> bool:
        """Check if WhatsApp Web is logged in by looking for the chat list."""
        if not self.page:
            return False
        try:
            await self.page.wait_for_selector(
                SELECTORS["chat_list"], timeout=5000
            )
            return True
        except Exception:
            return False

    async def wait_for_qr_scan(self, timeout: int = 120) -> bool:
        """
        Wait for the user to scan the QR code.

        Prints instructions to the console and blocks until
        the chat list appears or the timeout is reached.

        Args:
            timeout: Max seconds to wait for QR scan.

        Returns:
            True if authenticated, False if timed out.
        """
        if not self.page:
            logger.error("No page available — call launch_browser() first")
            return False

        print("\n" + "=" * 50)
        print("  WHATSAPP QR CODE AUTHENTICATION")
        print("=" * 50)
        print("  1. Open WhatsApp on your phone")
        print("  2. Go to Settings > Linked Devices")
        print("  3. Tap 'Link a Device'")
        print("  4. Scan the QR code shown in the browser")
        print(f"  Waiting up to {timeout} seconds ...")
        print("=" * 50 + "\n")

        try:
            await self.page.wait_for_selector(
                SELECTORS["chat_list"], timeout=timeout * 1000
            )
            logger.info("QR code scanned — authenticated successfully")
            await self.save_session()
            return True
        except Exception:
            logger.warning("QR scan timed out after %ds", timeout)
            return False

    # ------------------------------------------------------------------
    # Session persistence
    # ------------------------------------------------------------------

    async def save_session(self) -> None:
        """Save browser storage state for future runs."""
        if not self.context:
            return
        try:
            await self.context.storage_state(path=str(self.session_file))
            logger.info("Session saved to %s", self.session_file)
        except Exception as exc:
            logger.error("Failed to save session: %s", exc)

    def has_session(self) -> bool:
        """Check if a saved session file exists."""
        return self.session_file.exists()

    def clear_session(self) -> None:
        """Delete the saved session (force re-authentication)."""
        if self.session_file.exists():
            self.session_file.unlink()
            logger.info("Session cleared — will require QR scan on next launch")

    # ------------------------------------------------------------------
    # Screenshots
    # ------------------------------------------------------------------

    async def take_screenshot(self, name: Optional[str] = None) -> Optional[Path]:
        """
        Capture a screenshot of the current page.

        Args:
            name: Optional filename (without extension). Defaults to timestamp.

        Returns:
            Path to the saved screenshot, or None on failure.
        """
        if not self.page or not self.screenshots_dir:
            return None

        try:
            if not name:
                name = datetime.now().strftime("whatsapp_%Y%m%d_%H%M%S")
            path = self.screenshots_dir / f"{name}.png"
            await self.page.screenshot(path=str(path))
            logger.debug("Screenshot saved: %s", path)
            return path
        except Exception as exc:
            logger.warning("Screenshot failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close browser and release resources."""
        try:
            if self.context:
                await self.save_session()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Browser closed")
        except Exception as exc:
            logger.warning("Error during cleanup: %s", exc)
        finally:
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
