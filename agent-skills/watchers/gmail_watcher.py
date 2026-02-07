"""
Gmail Watcher Module

This module monitors Gmail for new emails and creates structured files in the vault inbox.
It follows the file-based approach without making external actions.
"""

import time
import os
from typing import Dict, Any, Optional
from watchers.watcher_base import WatcherBase
from core.vault_interface import VaultInterface
from core.logger import Logger
import base64
import json


class GmailWatcher(WatcherBase):
    """
    Watches Gmail for new emails and creates structured files in the vault inbox.
    Does not send emails or make other external actions - only monitors and creates files.
    """

    def __init__(self, vault_interface: VaultInterface, logger: Logger,
                 check_interval: int = 300):  # 5 minutes default
        """
        Initialize the Gmail watcher.

        Args:
            vault_interface: Interface for vault operations
            logger: Logger instance for auditability
            check_interval: Interval in seconds between checks
        """
        super().__init__("gmail", vault_interface, logger)
        self.check_interval = check_interval
        self.last_check_time = 0

        # Configuration from environment
        self.email_account = os.getenv('GMAIL_ACCOUNT', 'your-email@gmail.com')
        self.oauth_token = os.getenv('GMAIL_OAUTH_TOKEN', None)

        # Initialize Gmail API client if available
        self.gmail_service = None
        self._initialize_gmail_client()

    def _initialize_gmail_client(self):
        """Initialize the Gmail API client if credentials are available."""
        try:
            # Check if Google API libraries are installed
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build

            # Scopes for reading Gmail
            SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

            creds = None
            # The file token.json stores the user's access and refresh tokens.
            if os.path.exists('token.json'):
                creds = Credentials.from_authorized_user_file('token.json', SCOPES)

            # If there are no (valid) credentials available, let the user log in.
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # If credentials not available, we'll use mock mode
                    self.logger.log_system_event(
                        event_type="gmail_init_warning",
                        component="gmail_watcher",
                        message="Gmail credentials not found, running in mock mode",
                        details={"account": self.email_account}
                    )
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
                details={"missing_libraries": ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]}
            )
        except Exception as e:
            self.logger.log_system_event(
                event_type="gmail_init_error",
                component="gmail_watcher",
                message=f"Error initializing Gmail API client: {e}",
                details={"account": self.email_account}
            )

    def detect_events(self) -> Optional[Dict[str, Any]]:
        """
        Detect new emails in Gmail (real implementation if API is available).

        Returns:
            Dictionary with email data or None if no new emails
        """
        if self.gmail_service:
            return self._detect_events_real()
        else:
            return self._detect_events_mock()

    def _detect_events_real(self) -> Optional[Dict[str, Any]]:
        """
        Real implementation to detect new emails using Gmail API.

        Returns:
            Dictionary with email data or None if no new emails
        """
        try:
            import datetime
            from email.utils import parsedate_to_datetime

            # Calculate time threshold (5 minutes ago)
            time_threshold = (datetime.datetime.utcnow() - datetime.timedelta(minutes=5)).strftime('%Y/%m/%d %H:%M:%S')

            # Query for unread emails received in the last 5 minutes
            query = f'after:{time_threshold} newer_than:5m'
            results = self.gmail_service.users().messages().list(
                userId='me', q=query, maxResults=10).execute()
            messages = results.get('messages', [])

            if not messages:
                return None

            # Process the most recent message
            message_id = messages[0]['id']
            message = self.gmail_service.users().messages().get(
                userId='me', id=message_id, format='full').execute()

            # Extract email data
            headers = message['payload']['headers']
            subject = next((hdr['value'] for hdr in headers if hdr['name'] == 'Subject'), 'No Subject')
            sender = next((hdr['value'] for hdr in headers if hdr['name'] == 'From'), 'Unknown Sender')
            date = next((hdr['value'] for hdr in headers if hdr['name'] == 'Date'), '')

            # Try to get body preview
            body_preview = self._extract_email_body(message)

            # Determine priority based on subject keywords
            priority = self._determine_email_priority(subject, body_preview)

            email_data = {
                "event_type": "new_email",
                "timestamp": date,
                "subject": subject,
                "sender": sender,
                "recipient": self.email_account,
                "body_preview": body_preview,
                "has_attachments": len(message.get('payload', {}).get('parts', [])) > 1,
                "priority": priority,
                "message_id": message_id
            }

            return email_data

        except Exception as e:
            self.logger.log_system_event(
                event_type="gmail_detection_error",
                component="gmail_watcher",
                message=f"Error detecting emails via API: {e}",
                details={}
            )
            # Fall back to mock implementation
            return self._detect_events_mock()

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
        """
        Mock implementation for demonstration purposes.

        Returns:
            Dictionary with mock email data or None if no new emails
        """
        # Simulate checking for new emails
        current_time = time.time()

        # For demo purposes, let's say we find a new email every 10 minutes
        if current_time - self.last_check_time > 600:  # 10 minutes
            self.last_check_time = current_time

            # Mock email data
            email_data = {
                "event_type": "new_email",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(current_time)),
                "subject": "Meeting Reminder",
                "sender": "calendar-noreply@google.com",
                "recipient": self.email_account,
                "body_preview": "You have a meeting in 15 minutes...",
                "has_attachments": False,
                "priority": "medium"
            }

            return email_data

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
        Poll Gmail for new emails and create structured files.

        Returns:
            True if polling was successful, False otherwise
        """
        try:
            # Detect events
            event_data = self.detect_events()

            if event_data:
                # Create structured file in vault
                file_path = self.create_structured_file(event_data)

                if file_path:
                    self.logger.log_system_event(
                        event_type="gmail_poll_success",
                        component="gmail_watcher",
                        message="Successfully processed new email",
                        details={"file_path": file_path}
                    )
                    return True
                else:
                    self.logger.log_system_event(
                        event_type="gmail_processing_error",
                        component="gmail_watcher",
                        message="Failed to create structured file for email",
                        details={"email_data": event_data}
                    )
                    return False

            # No new emails detected
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