"""
Gmail Watcher Module

This module monitors Gmail for new emails and creates structured event files
in the vault inbox. Uses OAuth tokens from the dashboard's gmail-token.json
for authentication. Falls back to mock mode if credentials unavailable.

Silver Tier: Perception layer — creates EVENT files, never sends emails.
"""

import time
import os
from typing import Dict, Any, List, Optional
from watchers.watcher_base import WatcherBase
from core.vault_interface import VaultInterface
from core.logger import Logger
import base64
import json
from pathlib import Path
from datetime import datetime, timedelta
import uuid


class GmailWatcher(WatcherBase):
    """
    Watches Gmail for new emails and creates structured event files in the vault inbox.
    Uses OAuth tokens shared with the Next.js dashboard (gmail-token.json).
    Falls back to mock mode when credentials are unavailable.
    """

    def __init__(self, vault_interface: VaultInterface, logger: Logger,
                 check_interval: int = 300, mock_mode: bool = False):
        super().__init__("gmail", vault_interface, logger)
        self.check_interval = check_interval
        self.last_check_time = 0
        self.mock_mode = mock_mode
        self.last_history_id = None

        # Configuration from environment
        self.email_account = os.getenv('GMAIL_USER_EMAIL', os.getenv('GMAIL_ACCOUNT', ''))
        self.client_id = os.getenv('GMAIL_CLIENT_ID', '')
        self.client_secret = os.getenv('GMAIL_CLIENT_SECRET', '')

        # Token file paths — shared with Next.js dashboard
        self.token_path = self._find_token_file()

        # Initialize Gmail API client
        self.gmail_service = None
        if not self.mock_mode:
            self._initialize_gmail_client()

    def _find_token_file(self) -> Optional[Path]:
        """Find the gmail-token.json file (shared with dashboard)."""
        search_paths = [
            Path(os.getcwd()) / "dashboard" / "gmail-token.json",
            Path(os.getcwd()) / "gmail-token.json",
            Path(os.getcwd()) / "token.json",
        ]
        for p in search_paths:
            if p.exists():
                return p
        return None

    def _initialize_gmail_client(self):
        """Initialize the Gmail API client using dashboard's OAuth tokens."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

            creds = None
            if self.token_path and self.token_path.exists():
                # Load tokens from dashboard's token file
                token_data = json.loads(self.token_path.read_text())
                creds = Credentials(
                    token=token_data.get('access_token') or token_data.get('token'),
                    refresh_token=token_data.get('refresh_token'),
                    token_uri='https://oauth2.googleapis.com/token',
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    scopes=SCOPES,
                )

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    # Save refreshed token back
                    if self.token_path:
                        token_data = {
                            'access_token': creds.token,
                            'refresh_token': creds.refresh_token,
                            'token_uri': creds.token_uri,
                            'expiry': creds.expiry.isoformat() if creds.expiry else None,
                        }
                        self.token_path.write_text(json.dumps(token_data, indent=2))
                else:
                    self.logger.log_system_event(
                        event_type="gmail_init_warning",
                        component="gmail_watcher",
                        message="Gmail credentials not found or invalid, running in mock mode",
                        details={"account": self.email_account, "token_path": str(self.token_path)}
                    )
                    self.mock_mode = True
                    return

            self.gmail_service = build('gmail', 'v1', credentials=creds)
            self.logger.log_system_event(
                event_type="gmail_init_success",
                component="gmail_watcher",
                message="Gmail API client initialized successfully",
                details={"account": self.email_account}
            )
        except ImportError:
            self.logger.log_system_event(
                event_type="gmail_init_error",
                component="gmail_watcher",
                message="Google API libraries not installed, running in mock mode",
                details={}
            )
            self.mock_mode = True
        except Exception as e:
            self.logger.log_system_event(
                event_type="gmail_init_error",
                component="gmail_watcher",
                message=f"Error initializing Gmail API client: {e}",
                details={"account": self.email_account}
            )
            self.mock_mode = True

    def detect_events(self) -> Optional[Dict[str, Any]]:
        """
        Detect new emails in Gmail. Uses real API if authenticated, mock otherwise.

        Returns:
            Dictionary with email data or None if no new emails
        """
        if self.mock_mode or not self.gmail_service:
            return self._detect_events_mock()
        return self._detect_events_real()

    def _detect_events_real(self) -> Optional[Dict[str, Any]]:
        """
        Detect new emails using Gmail API with incremental sync.

        Returns:
            Dictionary with email data or None if no new emails
        """
        try:
            # Use incremental sync if we have a history ID
            if self.last_history_id:
                return self._detect_via_history()

            # Otherwise, query for recent unread emails
            interval_mins = max(self.check_interval // 60, 1)
            query = f'is:unread newer_than:{interval_mins}m'
            results = self.gmail_service.users().messages().list(
                userId='me', q=query, maxResults=10).execute()
            messages = results.get('messages', [])

            if not messages:
                # Store current history ID for incremental sync
                profile = self.gmail_service.users().getProfile(userId='me').execute()
                self.last_history_id = profile.get('historyId')
                return None

            # Process the most recent message
            message_id = messages[0]['id']
            message = self.gmail_service.users().messages().get(
                userId='me', id=message_id, format='full').execute()

            # Store history ID for next poll
            self.last_history_id = message.get('historyId')

            # Extract email data
            headers = message['payload']['headers']
            subject = next((hdr['value'] for hdr in headers if hdr['name'] == 'Subject'), 'No Subject')
            sender = next((hdr['value'] for hdr in headers if hdr['name'] == 'From'), 'Unknown Sender')
            date = next((hdr['value'] for hdr in headers if hdr['name'] == 'Date'), '')
            thread_id = message.get('threadId', '')

            body_preview = self._extract_email_body(message)
            priority = self._determine_email_priority(subject, body_preview)

            # Parse sender name and email
            sender_name = sender.split('<')[0].strip().strip('"') if '<' in sender else sender
            sender_email = sender.split('<')[1].rstrip('>') if '<' in sender else sender

            email_data = {
                "id": str(uuid.uuid4()),
                "source_type": "gmail",
                "source_id": message_id,
                "event_type": "email_received",
                "timestamp": datetime.utcnow().isoformat(),
                "detected_at": datetime.utcnow().isoformat(),
                "priority": priority,
                "processing_status": "new",
                "raw_data": {
                    "subject": subject,
                    "sender": sender,
                    "date": date,
                    "body_preview": body_preview,
                    "has_attachments": len(message.get('payload', {}).get('parts', [])) > 1,
                    "message_id": message_id,
                    "thread_id": thread_id,
                    "labels": message.get('labelIds', []),
                },
                "normalized_data": {
                    "summary": f"Email from {sender_name}: {subject}",
                    "sender": {
                        "name": sender_name,
                        "identifier": sender_email,
                    },
                    "content": {
                        "subject": subject,
                        "body": body_preview,
                        "attachments": [],
                    },
                    "metadata": {
                        "thread_id": thread_id,
                        "is_reply": bool(thread_id and len(messages) > 1),
                        "urgency_indicators": self._get_urgency_indicators(subject, body_preview),
                    }
                }
            }

            return email_data

        except Exception as e:
            self.logger.log_system_event(
                event_type="gmail_detection_error",
                component="gmail_watcher",
                message=f"Error detecting emails via API: {e}",
                details={}
            )
            self.mock_mode = True
            return self._detect_events_mock()

    def _detect_via_history(self) -> Optional[Dict[str, Any]]:
        """Use Gmail history API for incremental sync."""
        try:
            history = self.gmail_service.users().history().list(
                userId='me',
                startHistoryId=self.last_history_id,
                historyTypes=['messageAdded'],
            ).execute()

            changes = history.get('history', [])
            if not changes:
                self.last_history_id = history.get('historyId', self.last_history_id)
                return None

            # Get the first new message
            for change in changes:
                for msg_added in change.get('messagesAdded', []):
                    msg = msg_added.get('message', {})
                    if 'INBOX' in msg.get('labelIds', []):
                        # Full fetch of this message
                        self.last_history_id = history.get('historyId')
                        message = self.gmail_service.users().messages().get(
                            userId='me', id=msg['id'], format='full').execute()

                        headers = message['payload']['headers']
                        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                        body_preview = self._extract_email_body(message)
                        priority = self._determine_email_priority(subject, body_preview)
                        sender_name = sender.split('<')[0].strip().strip('"') if '<' in sender else sender
                        sender_email = sender.split('<')[1].rstrip('>') if '<' in sender else sender

                        return {
                            "id": str(uuid.uuid4()),
                            "source_type": "gmail",
                            "source_id": msg['id'],
                            "event_type": "email_received",
                            "timestamp": datetime.utcnow().isoformat(),
                            "detected_at": datetime.utcnow().isoformat(),
                            "priority": priority,
                            "processing_status": "new",
                            "raw_data": {
                                "subject": subject, "sender": sender,
                                "body_preview": body_preview,
                                "message_id": msg['id'],
                                "thread_id": message.get('threadId', ''),
                                "labels": message.get('labelIds', []),
                            },
                            "normalized_data": {
                                "summary": f"Email from {sender_name}: {subject}",
                                "sender": {"name": sender_name, "identifier": sender_email},
                                "content": {"subject": subject, "body": body_preview, "attachments": []},
                                "metadata": {
                                    "thread_id": message.get('threadId', ''),
                                    "is_reply": False,
                                    "urgency_indicators": self._get_urgency_indicators(subject, body_preview),
                                }
                            }
                        }

            self.last_history_id = history.get('historyId', self.last_history_id)
            return None

        except Exception:
            # History ID might be too old, reset to full query
            self.last_history_id = None
            return self._detect_events_real()

    def _get_urgency_indicators(self, subject: str, body: str) -> list:
        """Extract urgency keyword indicators."""
        keywords = ['urgent', 'asap', 'important', 'immediate', 'critical', 'deadline', 'emergency']
        content = (subject + ' ' + body).lower()
        return [k for k in keywords if k in content]

    def _extract_email_body(self, message: Dict[str, Any]) -> str:
        """
        Extract body content from a Gmail message.

        Args:
            message: Gmail message object

        Returns:
            Email body preview as string
        """
        try:
            payload = message.get('payload', {})
            parts = payload.get('parts', [])

            if parts:
                # Look for text/plain part
                for part in parts:
                    if part.get('mimeType') == 'text/plain':
                        body_data = part.get('body', {}).get('data', '')
                        if body_data:
                            decoded_body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                            # Return first 200 characters as preview
                            return decoded_body[:200] + "..." if len(decoded_body) > 200 else decoded_body

                # If no plain text, try HTML
                for part in parts:
                    if part.get('mimeType') == 'text/html':
                        body_data = part.get('body', {}).get('data', '')
                        if body_data:
                            import html
                            decoded_body = html.unescape(base64.urlsafe_b64decode(body_data).decode('utf-8'))
                            # Strip HTML tags
                            import re
                            clean_body = re.sub('<[^<]+?>', '', decoded_body)
                            return clean_body[:200] + "..." if len(clean_body) > 200 else clean_body
            else:
                # Single part message
                body_data = payload.get('body', {}).get('data', '')
                if body_data:
                    decoded_body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                    return decoded_body[:200] + "..." if len(decoded_body) > 200 else decoded_body

        except Exception as e:
            self.logger.log_system_event(
                event_type="email_body_extraction_error",
                component="gmail_watcher",
                message=f"Error extracting email body: {e}",
                details={}
            )

        return "Unable to extract email body content"

    def _determine_email_priority(self, subject: str, body: str) -> str:
        """
        Determine email priority based on keywords.

        Args:
            subject: Email subject
            body: Email body content

        Returns:
            Priority level ('high', 'medium', 'low')
        """
        import datetime

        high_priority_keywords = [
            'urgent', 'asap', 'important', 'immediate', 'critical',
            'deadline', 'meeting', 'today', 'now', 'emergency'
        ]

        medium_priority_keywords = [
            'follow', 'remind', 'update', 'report', 'proposal',
            'schedule', 'appointment', 'review', 'feedback'
        ]

        content = (subject + ' ' + body).lower()

        for keyword in high_priority_keywords:
            if keyword in content:
                return 'high'

        for keyword in medium_priority_keywords:
            if keyword in content:
                return 'medium'

        return 'low'

    def _detect_events_mock(self) -> Optional[Dict[str, Any]]:
        """Mock implementation for testing without credentials."""
        current_time = time.time()

        # Simulate new email every 10 minutes in mock mode
        if current_time - self.last_check_time > 600:
            self.last_check_time = current_time
            event_id = str(uuid.uuid4())

            return {
                "id": event_id,
                "source_type": "gmail",
                "source_id": f"mock_msg_{event_id[:8]}",
                "event_type": "email_received",
                "timestamp": datetime.utcnow().isoformat(),
                "detected_at": datetime.utcnow().isoformat(),
                "priority": "medium",
                "processing_status": "new",
                "raw_data": {
                    "subject": "Meeting Reminder",
                    "sender": "calendar-noreply@google.com",
                    "body_preview": "You have a meeting in 15 minutes...",
                    "has_attachments": False,
                    "message_id": f"mock_{event_id[:8]}",
                    "thread_id": "",
                    "labels": ["INBOX"],
                },
                "normalized_data": {
                    "summary": "Email from Google Calendar: Meeting Reminder",
                    "sender": {"name": "Google Calendar", "identifier": "calendar-noreply@google.com"},
                    "content": {
                        "subject": "Meeting Reminder",
                        "body": "You have a meeting in 15 minutes...",
                        "attachments": [],
                    },
                    "metadata": {
                        "thread_id": "",
                        "is_reply": False,
                        "urgency_indicators": ["meeting"],
                    }
                }
            }

        return None

    def normalize_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize raw email data to a consistent format.

        Args:
            raw_data: Raw email data from Gmail

        Returns:
            Normalized email data dictionary
        """
        normalized = {
            "source_type": "gmail",
            "event_type": raw_data.get("event_type", "email_received"),
            "timestamp": raw_data.get("timestamp", ""),
            "subject": raw_data.get("subject", ""),
            "sender": raw_data.get("sender", ""),
            "recipient": raw_data.get("recipient", ""),
            "body_preview": raw_data.get("body_preview", ""),
            "has_attachments": raw_data.get("has_attachments", False),
            "priority": raw_data.get("priority", "normal"),
            "gmail_specific_data": {
                "thread_id": raw_data.get("thread_id", ""),
                "message_id": raw_data.get("message_id", ""),
                "labels": raw_data.get("labels", [])
            }
        }

        return normalized

    def validate_gmail_config(self) -> bool:
        """
        Validate Gmail configuration (mock implementation).

        Returns:
            True if configuration is valid, False otherwise
        """
        # In a real implementation, this would validate OAuth tokens and permissions
        # For mock implementation, we'll just check if account is set
        return bool(self.email_account)

    def poll_gmail(self) -> bool:
        """
        Poll Gmail for new emails and create structured event files in vault.

        Returns:
            True if polling was successful, False otherwise
        """
        try:
            event_data = self.detect_events()

            if event_data:
                # Write event file to vault inbox using vault interface
                file_path = self.vault_interface.create_event_file(event_data)

                if file_path:
                    self.logger.log_system_event(
                        event_type="gmail_poll_success",
                        component="gmail_watcher",
                        message=f"New email event created: {event_data.get('normalized_data', {}).get('summary', '')}",
                        details={"file_path": str(file_path), "event_id": event_data.get("id")}
                    )
                    return True

            # No new emails — still a successful poll
            return True

        except Exception as e:
            self.logger.log_system_event(
                event_type="gmail_poll_error",
                component="gmail_watcher",
                message=f"Error polling Gmail: {e}",
                details={}
            )
            return False

    def run_continuous_monitoring(self):
        """
        Run continuous monitoring of Gmail (would be run in a thread in real implementation).
        """
        if not self.validate_gmail_config():
            self.logger.log_system_event(
                event_type="configuration_error",
                component="gmail_watcher",
                message="Invalid Gmail configuration",
                details={"account": self.email_account}
            )
            return

        self.start_monitoring()

        try:
            while self.is_running:
                self.poll_gmail()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            self.stop_monitoring()
        except Exception as e:
            self.logger.log_system_event(
                event_type="monitoring_error",
                component="gmail_watcher",
                message=f"Unexpected error in monitoring: {e}",
                details={}
            )
            self.stop_monitoring()