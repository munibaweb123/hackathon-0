"""
WhatsApp Watcher implementation using Playwright for WhatsApp Web automation.

Silver Tier: Perception layer — monitors WhatsApp Web for incoming messages,
creates structured event files in the vault inbox. Never sends messages autonomously.

Features:
- QR code session management with persistence
- Graceful fallback to mock mode when Playwright unavailable
- Event creation following watcher-events.schema.json contract
"""
import asyncio
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Handle relative imports for different execution contexts
try:
    from .watcher_base import WatcherBase
    from ..core.vault_interface import VaultInterface
    from ..core.logger import Logger
except ImportError:
    from watchers.watcher_base import WatcherBase
    from core.vault_interface import VaultInterface
    from core.logger import Logger


@dataclass
class WhatsAppMessage:
    """Structured WhatsApp message data."""
    id: str
    sender: str
    sender_identifier: str
    content: str
    timestamp: datetime
    chat_name: str
    message_type: str  # text, media, etc.


class WhatsAppWatcher(WatcherBase):
    """
    WhatsApp watcher that monitors WhatsApp Web for new messages using Playwright.

    Falls back to mock mode when:
    - Playwright is not installed
    - Browser initialization fails
    - Session expires and user doesn't scan QR
    """

    def __init__(self, vault_interface: VaultInterface, logger: Optional[Logger] = None,
                 polling_interval: int = 30, mock_mode: bool = False):
        super().__init__("whatsapp", vault_interface, logger)
        self.polling_interval = polling_interval
        self.mock_mode = mock_mode or not PLAYWRIGHT_AVAILABLE
        self.last_check_time = 0

        # Playwright state
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._initialized = False
        self._qr_code_ready = False

        # Session management
        self.session_file = "whatsapp_session.json"
        self.WHATSAPP_WEB_URL = "https://web.whatsapp.com"
        self.SESSION_FILE_PATH = Path(os.getcwd()) / self.session_file

        if not PLAYWRIGHT_AVAILABLE:
            self._log("Playwright not installed, running in mock mode")

    def _log(self, message: str, level: str = "info", details: Optional[Dict] = None):
        """Helper to log messages via logger if available."""
        if self.logger:
            self.logger.log_system_event(
                event_type=f"whatsapp_{level}",
                component="whatsapp_watcher",
                message=message,
                details=details or {}
            )
        else:
            print(f"[WhatsApp] {message}")

    def detect_events(self) -> Optional[Dict[str, Any]]:
        """
        Detect new WhatsApp messages. Uses mock mode if Playwright unavailable.

        Returns:
            Dictionary with event data following watcher-events.schema.json,
            or None if no new events detected.
        """
        if self.mock_mode:
            return self._detect_events_mock()

        # For sync context, use asyncio to run async detection
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in async context, return None and let async caller use detect_events_async
                return None
            events = loop.run_until_complete(self._detect_single_event_async())
            return events
        except RuntimeError:
            # No event loop, create one
            events = asyncio.run(self._detect_single_event_async())
            return events
        except Exception as e:
            self._log(f"Error detecting events: {e}", level="error")
            self.mock_mode = True
            return self._detect_events_mock()

    def normalize_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw event data to a consistent format per schema."""
        chat_name = raw_data.get('chat_name', 'Unknown')
        content = raw_data.get('content', '')

        return {
            'summary': f"WhatsApp message from {chat_name}: {content[:50]}..." if len(content) > 50 else f"WhatsApp message from {chat_name}: {content}",
            'sender': {
                'name': raw_data.get('sender', chat_name),
                'identifier': raw_data.get('phone_number', chat_name),
            },
            'content': {
                'subject': f"Message from {chat_name}",
                'body': content,
                'attachments': [],
            },
            'metadata': {
                'thread_id': raw_data.get('chat_id', f'wa_thread_{chat_name}'),
                'is_reply': raw_data.get('is_reply', False),
                'urgency_indicators': self._get_urgency_indicators(content),
            }
        }

    def _get_urgency_indicators(self, content: str) -> List[str]:
        """Extract urgency indicators from message content."""
        keywords = ['urgent', 'asap', 'important', 'emergency', 'help', 'now', 'immediately']
        content_lower = content.lower()
        return [k for k in keywords if k in content_lower]

    async def _detect_single_event_async(self) -> Optional[Dict[str, Any]]:
        """Async wrapper to detect a single event for sync callers."""
        if not self._initialized:
            success = await self.initialize_async()
            if not success:
                self.mock_mode = True
                return self._detect_events_mock()

        events = await self.detect_events_async()
        return events[0] if events else None

    def _detect_events_mock(self) -> Optional[Dict[str, Any]]:
        """Mock implementation for testing without Playwright."""
        current_time = time.time()

        # Simulate new message every 5 minutes in mock mode
        if current_time - self.last_check_time > 300:
            self.last_check_time = current_time
            event_id = str(uuid.uuid4())

            return {
                "id": event_id,
                "source_type": "whatsapp",
                "source_id": f"mock_wa_{event_id[:8]}",
                "event_type": "whatsapp_message",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "detected_at": datetime.utcnow().isoformat() + "Z",
                "priority": "medium",
                "processing_status": "new",
                "raw_data": {
                    "chat_id": "mock_chat_001",
                    "message_id": f"mock_msg_{event_id[:8]}",
                    "chat_name": "Test Contact",
                    "sender": "Test Contact",
                    "phone_number": "+1234567890",
                    "content": "Hello! This is a mock WhatsApp message for testing.",
                    "message_type": "text",
                    "is_group": False,
                },
                "normalized_data": {
                    "summary": "WhatsApp message from Test Contact: Hello! This is a mock WhatsApp message...",
                    "sender": {
                        "name": "Test Contact",
                        "identifier": "+1234567890",
                    },
                    "content": {
                        "subject": "Message from Test Contact",
                        "body": "Hello! This is a mock WhatsApp message for testing.",
                        "attachments": [],
                    },
                    "metadata": {
                        "thread_id": "wa_thread_mock_chat_001",
                        "is_reply": False,
                        "urgency_indicators": [],
                    }
                }
            }

        return None

    def get_qr_code_status(self) -> Dict[str, Any]:
        """
        Get QR code status for dashboard display.

        Returns:
            Dictionary with qr_ready, connected, session_exists flags
        """
        return {
            "qr_ready": self._qr_code_ready,
            "connected": self._initialized and self.page is not None,
            "session_exists": self.SESSION_FILE_PATH.exists(),
            "mock_mode": self.mock_mode,
        }

    async def initialize_async(self) -> bool:
        """
        Initialize the WhatsApp watcher with Playwright.

        Returns:
            True if initialization successful, False otherwise
        """
        if not PLAYWRIGHT_AVAILABLE:
            self._log("Playwright not available, cannot initialize")
            return False

        try:
            self.playwright = await async_playwright().start()

            # Create browser context with saved session if available
            storage_state = str(self.SESSION_FILE_PATH) if self.SESSION_FILE_PATH.exists() else None

            # Launch browser - keep visible for QR code scanning
            self.browser = await self.playwright.chromium.launch(
                headless=False,
                args=['--disable-blink-features=AutomationControlled']
            )
            self.context = await self.browser.new_context(
                storage_state=storage_state,
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            self.page = await self.context.new_page()

            # Navigate to WhatsApp Web
            await self.page.goto(self.WHATSAPP_WEB_URL)

            # Check if session exists and is valid
            if self.SESSION_FILE_PATH.exists():
                # Try to detect if already logged in
                try:
                    await self.page.wait_for_selector(
                        '[data-testid="chat-list"]',
                        state='visible',
                        timeout=10000  # 10 seconds to check
                    )
                    self._initialized = True
                    self._qr_code_ready = False
                    self._log("WhatsApp session restored successfully")
                    return True
                except:
                    # Session expired, need new QR scan
                    self._log("Session expired, QR code scan required")

            # No valid session, wait for QR code scan
            self._qr_code_ready = True
            self._log("WhatsApp session not found. Please scan the QR code in the browser.")
            await self.wait_for_qr_scan()

            self._initialized = True
            self._qr_code_ready = False
            self._log("WhatsApp watcher initialized successfully")
            return True

        except Exception as e:
            self._log(f"Failed to initialize WhatsApp watcher: {e}", level="error")
            await self.cleanup()
            return False

    async def wait_for_qr_scan(self, timeout_seconds: int = 120) -> bool:
        """
        Wait for user to scan QR code.

        Args:
            timeout_seconds: How long to wait for QR scan (default 2 minutes)

        Returns:
            True if QR code was scanned successfully
        """
        try:
            self._qr_code_ready = True
            self._log(f"Waiting for QR code scan (timeout: {timeout_seconds}s)")

            # Wait for chat list to appear (indicates successful login)
            await self.page.wait_for_selector(
                '[data-testid="chat-list"]',
                state='visible',
                timeout=timeout_seconds * 1000
            )

            self._qr_code_ready = False
            self._log("QR code scanned successfully")

            # Save session immediately after successful scan
            await self.save_session()
            return True

        except Exception as e:
            self._qr_code_ready = False
            self._log(f"QR scan timeout or error: {e}", level="error")
            raise

    async def save_session(self) -> bool:
        """
        Save current session to file for reuse.

        Returns:
            True if session saved successfully
        """
        try:
            if self.context:
                await self.context.storage_state(path=str(self.SESSION_FILE_PATH))
                self._log("WhatsApp session saved successfully")
                return True
            return False
        except Exception as e:
            self._log(f"Failed to save WhatsApp session: {e}", level="error")
            return False

    async def detect_events_async(self) -> List[Dict[str, Any]]:
        """
        Detect new WhatsApp messages and convert to event format.

        Returns:
            List of event dictionaries following watcher-events.schema.json
        """
        try:
            if not self.page or not self._initialized:
                return []

            # Wait for page to be stable
            await self.page.wait_for_load_state('networkidle')

            # Try different selectors for unread chats (WhatsApp Web changes frequently)
            unread_selectors = [
                '[data-testid="cell-frame-container"] span[data-testid="icon-unread-count"]',
                'div._1pJ9J[data-unread-count]:not([data-unread-count="0"])',
                'span.P6z4j',  # Unread badge
            ]

            events = []
            for selector in unread_selectors:
                try:
                    unread_elements = await self.page.query_selector_all(selector)
                    if unread_elements:
                        break
                except:
                    continue

            if not unread_elements:
                return []

            # Process each unread chat
            for unread_badge in unread_elements[:5]:  # Limit to 5 chats per poll
                try:
                    # Navigate to parent chat element and click
                    chat_container = await unread_badge.evaluate_handle(
                        'el => el.closest(\'[data-testid="cell-frame-container"]\') || el.closest("div._1pJ9J")'
                    )
                    if not chat_container:
                        continue

                    # Get chat name before clicking
                    chat_name_el = await chat_container.query_selector('span[title], span._21nHd')
                    chat_name = await chat_name_el.text_content() if chat_name_el else "Unknown"

                    # Click to open chat
                    await chat_container.click()
                    await asyncio.sleep(0.5)  # Brief pause for chat to load

                    # Wait for messages panel
                    await self.page.wait_for_selector(
                        '[data-testid="conversation-panel-messages"]',
                        timeout=5000
                    )

                    # Get incoming messages
                    message_elements = await self.page.query_selector_all(
                        '[data-testid="msg-container"].message-in'
                    )

                    for msg_element in message_elements[-5:]:  # Get last 5 messages
                        try:
                            # Extract message text
                            text_el = await msg_element.query_selector(
                                'span.selectable-text, span._ao3e'
                            )
                            if not text_el:
                                continue

                            message_text = await text_el.text_content()
                            if not message_text:
                                continue

                            # Generate event with proper UUID and ISO timestamps
                            event_id = str(uuid.uuid4())
                            now = datetime.utcnow()

                            event_data = {
                                "id": event_id,
                                "source_type": "whatsapp",
                                "source_id": f"wa_{chat_name}_{event_id[:8]}",
                                "event_type": "whatsapp_message",
                                "timestamp": now.isoformat() + "Z",
                                "detected_at": now.isoformat() + "Z",
                                "priority": self._determine_priority(message_text),
                                "processing_status": "new",
                                "raw_data": {
                                    "chat_id": f"wa_chat_{hash(chat_name) % 10000:04d}",
                                    "message_id": event_id[:8],
                                    "chat_name": chat_name,
                                    "sender": chat_name,
                                    "phone_number": chat_name,  # May be phone number or name
                                    "content": message_text,
                                    "message_type": "text",
                                    "is_group": "@" in chat_name,
                                },
                                "normalized_data": self.normalize_data({
                                    "chat_name": chat_name,
                                    "sender": chat_name,
                                    "content": message_text,
                                    "chat_id": f"wa_chat_{hash(chat_name) % 10000:04d}",
                                })
                            }
                            events.append(event_data)

                        except Exception as e:
                            self._log(f"Error processing message: {e}", level="warning")
                            continue

                except Exception as e:
                    self._log(f"Error processing chat: {e}", level="warning")
                    continue

            # Save session periodically
            if events:
                await self.save_session()

            return events

        except Exception as e:
            self._log(f"Error detecting WhatsApp events: {e}", level="error")
            return []

    def _determine_priority(self, content: str) -> str:
        """Determine message priority based on content."""
        content_lower = content.lower()
        high_keywords = ['urgent', 'emergency', 'help', 'asap', 'important', 'immediately']
        if any(k in content_lower for k in high_keywords):
            return "high"
        return "medium"

    async def cleanup(self):
        """Clean up resources gracefully."""
        self._initialized = False
        self._qr_code_ready = False

        if self.page:
            try:
                await self.save_session()
            except:
                pass
            try:
                await self.page.close()
            except:
                pass

        if self.context:
            try:
                await self.context.close()
            except:
                pass

        if self.browser:
            try:
                await self.browser.close()
            except:
                pass

        if self.playwright:
            try:
                await self.playwright.stop()
            except:
                pass

        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
        self._log("WhatsApp watcher cleanup complete")

    def poll_whatsapp(self) -> bool:
        """
        Poll WhatsApp for messages and create event files in vault.

        Returns:
            True if polling successful (even if no new messages)
        """
        try:
            event_data = self.detect_events()

            if event_data:
                file_path = self.vault_interface.create_event_file(event_data)

                if file_path:
                    self._log(
                        f"New WhatsApp event created: {event_data.get('normalized_data', {}).get('summary', '')}",
                        details={"file_path": str(file_path), "event_id": event_data.get("id")}
                    )
                    return True

            return True  # Success even without new events

        except Exception as e:
            self._log(f"Error polling WhatsApp: {e}", level="error")
            return False

    def run_continuous_monitoring(self):
        """Run continuous monitoring of WhatsApp (blocking)."""
        self.start_monitoring()

        try:
            while self.is_running:
                self.poll_whatsapp()
                time.sleep(self.polling_interval)
        except KeyboardInterrupt:
            self.stop_monitoring()
        except Exception as e:
            self._log(f"Unexpected error in monitoring: {e}", level="error")
            self.stop_monitoring()

    async def run_mock_mode_async(self) -> List[Dict[str, Any]]:
        """Generate mock WhatsApp events for testing (async version)."""
        mock_events = []
        now = datetime.utcnow()

        for i in range(2):
            event_id = str(uuid.uuid4())
            contact_name = f"Mock Contact {i + 1}"
            content = f"This is a mock WhatsApp message #{i + 1} for testing purposes."

            event_data = {
                "id": event_id,
                "source_type": "whatsapp",
                "source_id": f"mock_wa_{event_id[:8]}",
                "event_type": "whatsapp_message",
                "timestamp": now.isoformat() + "Z",
                "detected_at": now.isoformat() + "Z",
                "priority": "medium" if i == 0 else "high",
                "processing_status": "new",
                "raw_data": {
                    "chat_id": f"mock_chat_{i:03d}",
                    "message_id": f"mock_msg_{event_id[:8]}",
                    "chat_name": contact_name,
                    "sender": contact_name,
                    "phone_number": f"+1234567890{i}",
                    "content": content,
                    "message_type": "text",
                    "is_group": False,
                },
                "normalized_data": {
                    "summary": f"WhatsApp message from {contact_name}: {content[:50]}...",
                    "sender": {
                        "name": contact_name,
                        "identifier": f"+1234567890{i}",
                    },
                    "content": {
                        "subject": f"Message from {contact_name}",
                        "body": content,
                        "attachments": [],
                    },
                    "metadata": {
                        "thread_id": f"wa_thread_mock_{i:03d}",
                        "is_reply": False,
                        "urgency_indicators": ["testing"] if i == 1 else [],
                    }
                }
            }
            mock_events.append(event_data)

        return mock_events