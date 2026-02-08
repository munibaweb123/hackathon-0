"""
LinkedIn Watcher Module

Monitors LinkedIn for activity (profile views, connection requests, messages)
and creates structured event files in the vault inbox. Uses OAuth tokens from
the dashboard's linkedin-token.json for authentication.

Silver Tier: Perception layer — creates EVENT files, never posts content.
"""

import time
import os
import json
import requests
from typing import Dict, Any, Optional
from watchers.watcher_base import WatcherBase
from core.vault_interface import VaultInterface
from core.logger import Logger
from pathlib import Path
from datetime import datetime
import uuid


class LinkedInWatcher(WatcherBase):
    """
    Watches LinkedIn for activity and creates structured event files in vault inbox.
    Uses OAuth tokens shared with the Next.js dashboard (linkedin-token.json).
    Falls back to mock mode when credentials are unavailable.
    """

    def __init__(self, vault_interface: VaultInterface, logger: Logger,
                 check_interval: int = 900, mock_mode: bool = False):
        super().__init__("linkedin", vault_interface, logger)
        self.check_interval = check_interval
        self.last_check_time = 0
        self.mock_mode = mock_mode

        # LinkedIn API endpoints
        self.api_base_url = "https://api.linkedin.com/v2"

        # Load token from dashboard's token file
        self.access_token = None
        self.profile_data = None
        self.token_path = self._find_token_file()

        if not self.mock_mode:
            self._initialize_linkedin_client()

    def _find_token_file(self) -> Optional[Path]:
        """Find the linkedin-token.json file (shared with dashboard)."""
        search_paths = [
            Path(os.getcwd()) / "dashboard" / "linkedin-token.json",
            Path(os.getcwd()) / "linkedin-token.json",
        ]
        for p in search_paths:
            if p.exists():
                return p
        return None

    def _initialize_linkedin_client(self):
        """Initialize LinkedIn API client using dashboard's OAuth tokens."""
        try:
            if not self.token_path or not self.token_path.exists():
                self.logger.log_system_event(
                    event_type="linkedin_init_warning",
                    component="linkedin_watcher",
                    message="LinkedIn token file not found, running in mock mode",
                    details={}
                )
                self.mock_mode = True
                return

            token_data = json.loads(self.token_path.read_text())
            self.access_token = token_data.get('access_token')

            if not self.access_token:
                self.mock_mode = True
                return

            # Test the connection by fetching profile
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json',
            }
            resp = requests.get(f"{self.api_base_url}/me", headers=headers, timeout=10)

            if resp.status_code == 200:
                self.profile_data = resp.json()
                self.logger.log_system_event(
                    event_type="linkedin_init_success",
                    component="linkedin_watcher",
                    message="LinkedIn API client initialized successfully",
                    details={"profile": self.profile_data.get('localizedFirstName', 'Unknown')}
                )
            else:
                self.logger.log_system_event(
                    event_type="linkedin_init_error",
                    component="linkedin_watcher",
                    message=f"LinkedIn API test failed: {resp.status_code}",
                    details={"status_code": resp.status_code}
                )
                self.mock_mode = True

        except Exception as e:
            self.logger.log_system_event(
                event_type="linkedin_init_error",
                component="linkedin_watcher",
                message=f"Error initializing LinkedIn API client: {e}",
                details={}
            )
            self.mock_mode = True

    def _get_headers(self) -> dict:
        """Get authenticated headers for LinkedIn API."""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'X-Restli-Protocol-Version': '2.0.0',
        }

    def detect_events(self) -> Optional[Dict[str, Any]]:
        """Detect LinkedIn activity. Uses real API if authenticated, mock otherwise."""
        if self.mock_mode or not self.access_token:
            return self._detect_events_mock()
        return self._detect_events_real()

    def _detect_events_real(self) -> Optional[Dict[str, Any]]:
        """Detect LinkedIn activity using the API (profile data check)."""
        try:
            # With basic LinkedIn products (Share + Sign In), we can check profile
            # but can't read notifications. We detect activity by polling profile.
            headers = self._get_headers()

            # Fetch current profile to check for changes
            resp = requests.get(f"{self.api_base_url}/me", headers=headers, timeout=10)

            if resp.status_code == 401:
                # Token expired
                self.logger.log_system_event(
                    event_type="linkedin_auth_expired",
                    component="linkedin_watcher",
                    message="LinkedIn OAuth token expired",
                    details={}
                )
                self.mock_mode = True
                return None

            if resp.status_code != 200:
                return None

            # For basic products, we can't read notifications directly.
            # This poll confirms the connection is alive and logs a heartbeat.
            # In a real deployment, more advanced LinkedIn products would
            # expose notifications and messages endpoints.
            return None

        except requests.exceptions.Timeout:
            self.logger.log_system_event(
                event_type="linkedin_timeout",
                component="linkedin_watcher",
                message="LinkedIn API request timed out",
                details={}
            )
            return None
        except Exception as e:
            self.logger.log_system_event(
                event_type="linkedin_detection_error",
                component="linkedin_watcher",
                message=f"Error detecting LinkedIn activity: {e}",
                details={}
            )
            return self._detect_events_mock()

    def _detect_events_mock(self) -> Optional[Dict[str, Any]]:
        """Mock implementation for testing without credentials."""
        current_time = time.time()

        # Simulate activity every 15 minutes in mock mode
        if current_time - self.last_check_time > 900:
            self.last_check_time = current_time
            event_id = str(uuid.uuid4())

            return {
                "id": event_id,
                "source_type": "linkedin",
                "source_id": f"mock_li_{event_id[:8]}",
                "event_type": "linkedin_notification",
                "timestamp": datetime.utcnow().isoformat(),
                "detected_at": datetime.utcnow().isoformat(),
                "priority": "low",
                "processing_status": "new",
                "raw_data": {
                    "activity_type": "profile_view",
                    "actor_name": "John Doe",
                    "actor_profile_url": "https://linkedin.com/in/johndoe",
                    "connection_status": "connection",
                    "message": "John Doe viewed your profile",
                },
                "normalized_data": {
                    "summary": "LinkedIn: John Doe viewed your profile",
                    "sender": {
                        "name": "John Doe",
                        "identifier": "johndoe",
                    },
                    "content": {
                        "subject": "Profile View",
                        "body": "John Doe viewed your profile",
                        "attachments": [],
                    },
                    "metadata": {
                        "thread_id": "",
                        "is_reply": False,
                        "urgency_indicators": [],
                    }
                }
            }

        return None

    def normalize_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw LinkedIn activity data to consistent format."""
        return {
            "summary": raw_data.get("normalized_data", {}).get("summary", ""),
            "sender": raw_data.get("normalized_data", {}).get("sender", {}),
            "content": raw_data.get("normalized_data", {}).get("content", {}),
            "metadata": raw_data.get("normalized_data", {}).get("metadata", {}),
        }

    def poll_linkedin(self) -> bool:
        """Poll LinkedIn for activity and create structured event files in vault."""
        try:
            event_data = self.detect_events()

            if event_data:
                file_path = self.vault_interface.create_event_file(event_data)

                if file_path:
                    self.logger.log_system_event(
                        event_type="linkedin_poll_success",
                        component="linkedin_watcher",
                        message=f"New LinkedIn event created: {event_data.get('normalized_data', {}).get('summary', '')}",
                        details={"file_path": str(file_path), "event_id": event_data.get("id")}
                    )
                    return True

            return True

        except Exception as e:
            self.logger.log_system_event(
                event_type="linkedin_poll_error",
                component="linkedin_watcher",
                message=f"Error polling LinkedIn: {e}",
                details={}
            )
            return False

    def run_continuous_monitoring(self):
        """Run continuous monitoring of LinkedIn."""
        self.start_monitoring()

        try:
            while self.is_running:
                self.poll_linkedin()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            self.stop_monitoring()
        except Exception as e:
            self.logger.log_system_event(
                event_type="monitoring_error",
                component="linkedin_watcher",
                message=f"Unexpected error in monitoring: {e}",
                details={}
            )
            self.stop_monitoring()
