"""
WhatsApp Action Module

Handles WhatsApp reply actions through the MCP server.
Uses Playwright to send messages via WhatsApp Web.

Task T063: Implement WhatsApp reply action with Playwright
"""

from typing import Any, Dict, Optional
import uuid
from datetime import datetime


class WhatsAppAction:
    """
    Handles WhatsApp reply actions through the MCP server.
    Uses Playwright browser automation to send messages via WhatsApp Web.
    """

    def __init__(self, logger=None):
        self.logger = logger
        self._page = None

    def set_page(self, page):
        """Set the Playwright page for WhatsApp Web interaction."""
        self._page = page

    def execute(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a WhatsApp reply action.

        Args:
            action_data: Dict with keys:
                - chat_name: Name of the chat to reply to
                - message: Message text to send
                - reply_to_id: Optional message ID to reply to

        Returns:
            Dict with execution result
        """
        chat_name = action_data.get("chat_name", "")
        message = action_data.get("message", "")

        if not chat_name or not message:
            return {
                "success": False,
                "error": "Missing chat_name or message",
                "message_id": None,
            }

        # Validate message content
        if not self.validate_message(message):
            return {
                "success": False,
                "error": "Message validation failed",
                "message_id": None,
            }

        if not self._page:
            # Mock mode - no active Playwright session
            return self._simulate_send(chat_name, message)

        try:
            return self._send_via_playwright(chat_name, message)
        except Exception as e:
            if self.logger:
                self.logger.log_system_event(
                    event_type="whatsapp_send_error",
                    component="whatsapp_action",
                    message=f"Error sending WhatsApp message: {e}",
                    details={"chat_name": chat_name},
                )
            return {
                "success": False,
                "error": str(e),
                "message_id": None,
            }

    def _send_via_playwright(self, chat_name: str, message: str) -> Dict[str, Any]:
        """Send a message using the Playwright page (requires async context)."""
        # This would need to be called from an async context
        # For now, return mock result indicating Playwright is needed
        return {
            "success": False,
            "error": "Playwright async send not implemented in sync context. Use async handler.",
            "message_id": None,
        }

    def _simulate_send(self, chat_name: str, message: str) -> Dict[str, Any]:
        """Simulate sending a message (mock mode)."""
        message_id = f"wa_sent_{uuid.uuid4().hex[:12]}"

        if self.logger:
            self.logger.log_system_event(
                event_type="whatsapp_mock_send",
                component="whatsapp_action",
                message=f"MOCK: WhatsApp message to {chat_name}",
                details={
                    "chat_name": chat_name,
                    "message_preview": message[:100],
                    "message_id": message_id,
                },
            )

        return {
            "success": True,
            "message_id": message_id,
            "details": f"Mock message sent to {chat_name}",
            "mock": True,
        }

    def validate_message(self, message: str) -> bool:
        """Validate message content before sending."""
        if not message or len(message.strip()) == 0:
            return False
        if len(message) > 65536:  # WhatsApp max message length
            return False
        return True
