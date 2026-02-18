# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "google-api-python-client>=2.100.0",
#     "google-auth>=2.23.0",
#     "google-auth-oauthlib>=1.1.0",
#     "python-dotenv>=1.0.0",
# ]
# ///
"""
Gmail Watcher Agent Skill

Monitors Gmail for important unread emails and creates action files
in an Obsidian vault.  Runnable standalone via UV:

    uv run gmail_watcher.py --vault-path ../../obsidian-vault

Or with pip:

    pip install -r requirements.txt
    python gmail_watcher.py --vault-path ../../obsidian-vault
"""

import argparse
import base64
import html as html_mod
import json
import os
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure local imports work when run via UV
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv  # noqa: E402

from base_watcher import BaseWatcher  # noqa: E402

# Google client imports — wrapped so the module can still be imported
# when the libraries are missing (for documentation / linting purposes).
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError  # noqa: F401
except ImportError:
    Request = None  # type: ignore[assignment,misc]
    Credentials = None  # type: ignore[assignment,misc]
    InstalledAppFlow = None  # type: ignore[assignment,misc]
    build = None  # type: ignore[assignment]

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailWatcher(BaseWatcher):
    """
    Polls Gmail for unread emails labelled IMPORTANT and creates
    ``EMAIL_{message_id}.md`` markdown files in the vault's
    ``Needs_Action/`` folder.
    """

    def __init__(self, vault_path: str, poll_interval: int = 120):
        super().__init__("gmail", vault_path, poll_interval)

        # Load environment
        self._load_env()

        self.client_id = os.getenv("GMAIL_CLIENT_ID", "")
        self.client_secret = os.getenv("GMAIL_CLIENT_SECRET", "")

        # Paths
        self.needs_action_dir = self.vault_path / "Needs_Action"
        self.needs_action_dir.mkdir(parents=True, exist_ok=True)

        self.token_path = self._find_token_file()
        self.client_secret_path = self._find_client_secret_file()

        # Authenticate
        self.gmail_service = None
        self._authenticate()

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _load_env(self) -> None:
        """Walk up from the script dir to find a .env file and load it."""
        search = Path(__file__).resolve().parent
        for _ in range(6):  # max 6 levels up
            env_file = search / ".env"
            if env_file.exists():
                load_dotenv(env_file)
                return
            search = search.parent
        load_dotenv()  # fall back to default behaviour

    def _project_root(self) -> Path:
        """Find the project root by looking for obsidian-vault/ or .env."""
        search = Path(__file__).resolve().parent
        for _ in range(6):
            if (search / "obsidian-vault").is_dir() or (search / ".env").exists():
                return search
            search = search.parent
        return Path(__file__).resolve().parent

    def _find_token_file(self) -> Optional[Path]:
        """Locate the Gmail OAuth token file (shared with the dashboard)."""
        root = self._project_root()
        candidates = [
            root / "dashboard" / "gmail-token.json",
            root / "gmail-token.json",
            root / "token.json",
        ]
        for p in candidates:
            if p.exists():
                self.logger.debug("Token file found: %s", p)
                return p
        self.logger.debug("No existing token file found")
        return None

    def _find_client_secret_file(self) -> Optional[Path]:
        """Locate the OAuth client-secret JSON for first-time auth."""
        root = self._project_root()
        for name in ("client-secret.json", "credentials.json", "client_secret.json"):
            p = root / name
            if p.exists():
                return p
        return None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _authenticate(self) -> None:
        """Build the Gmail API service using OAuth2 credentials."""
        if build is None:
            raise RuntimeError(
                "Google API libraries not installed. "
                "Run: pip install google-api-python-client google-auth google-auth-oauthlib"
            )

        creds: Optional[Credentials] = None  # type: ignore[assignment]

        # 1. Load existing token
        if self.token_path and self.token_path.exists():
            try:
                token_data = json.loads(self.token_path.read_text(encoding="utf-8"))
                creds = Credentials(
                    token=token_data.get("access_token") or token_data.get("token"),
                    refresh_token=token_data.get("refresh_token"),
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=self.client_id or token_data.get("client_id", ""),
                    client_secret=self.client_secret or token_data.get("client_secret", ""),
                    scopes=SCOPES,
                )
            except (json.JSONDecodeError, KeyError) as exc:
                self.logger.warning("Could not parse token file: %s", exc)

        # 2. Refresh if expired
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_token(creds)
                self.logger.info("OAuth token refreshed successfully")
            except Exception as exc:
                self.logger.warning("Token refresh failed: %s", exc)
                creds = None

        # 3. Run interactive flow if no valid creds
        if not creds or not creds.valid:
            if self.client_secret_path and self.client_secret_path.exists():
                self.logger.info("Starting OAuth consent flow …")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.client_secret_path), SCOPES
                )
                creds = flow.run_local_server(port=0)
                self._save_token(creds)
            else:
                raise RuntimeError(
                    "Gmail OAuth credentials not available.\n"
                    "Place a client-secret.json in the project root and re-run,\n"
                    "or complete the dashboard OAuth flow first."
                )

        self.gmail_service = build("gmail", "v1", credentials=creds)
        self.logger.info("Gmail API authenticated successfully")

    def _save_token(self, creds: Any) -> None:
        """Persist OAuth tokens for future runs."""
        if not self.token_path:
            self.token_path = self._project_root() / "gmail-token.json"
        token_data = {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "expiry": creds.expiry.isoformat() if creds.expiry else None,
        }
        self.token_path.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
        self.logger.debug("Token saved to %s", self.token_path)

    # ------------------------------------------------------------------
    # Event detection
    # ------------------------------------------------------------------

    def detect_events(self) -> List[Dict[str, Any]]:
        """Query Gmail for unread important emails."""
        events: List[Dict[str, Any]] = []
        try:
            result = self.execute_with_backoff(
                lambda: self.gmail_service.users()
                .messages()
                .list(userId="me", q="is:unread label:IMPORTANT", maxResults=20)
                .execute()
            )
            messages = result.get("messages", [])
            if not messages:
                self.logger.debug("No new important unread emails")
                return events

            for msg_stub in messages:
                mid = msg_stub["id"]
                if self._is_processed(mid):
                    continue

                msg = self.execute_with_backoff(
                    lambda m=mid: self.gmail_service.users()
                    .messages()
                    .get(userId="me", id=m, format="full")
                    .execute()
                )
                events.append(self._parse_message(msg))

        except Exception as exc:
            self.logger.error("Error detecting events: %s", exc, exc_info=True)

        self.logger.info("Detected %d new important email(s)", len(events))
        return events

    def _parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured data from a Gmail message object."""
        headers = {h["name"]: h["value"] for h in message["payload"].get("headers", [])}
        subject = headers.get("Subject", "No Subject")
        sender_raw = headers.get("From", "Unknown Sender")
        date_raw = headers.get("Date", "")

        # Parse sender
        if "<" in sender_raw:
            from_name = sender_raw.split("<")[0].strip().strip('"')
            from_email = sender_raw.split("<")[1].rstrip(">")
        else:
            from_name = sender_raw
            from_email = sender_raw

        # Parse date
        received = self._parse_date(date_raw)

        # Extract body
        body_snippet = self._extract_body(message)

        # Priority
        priority = self._determine_priority(subject, body_snippet)

        return {
            "id": message["id"],
            "from_email": from_email,
            "from_name": from_name,
            "subject": subject,
            "received": received,
            "body_snippet": body_snippet,
            "priority": priority,
            "labels": message.get("labelIds", []),
            "thread_id": message.get("threadId", ""),
        }

    # ------------------------------------------------------------------
    # Body extraction
    # ------------------------------------------------------------------

    def _extract_body(self, message: Dict[str, Any]) -> str:
        """Return the first 500 characters of the email body."""
        try:
            payload = message.get("payload", {})
            parts = payload.get("parts", [])

            if parts:
                # Prefer text/plain
                for part in parts:
                    if part.get("mimeType") == "text/plain":
                        data = part.get("body", {}).get("data", "")
                        if data:
                            decoded = base64.urlsafe_b64decode(data).decode("utf-8")
                            return decoded[:500]

                # Fall back to text/html (strip tags)
                for part in parts:
                    if part.get("mimeType") == "text/html":
                        data = part.get("body", {}).get("data", "")
                        if data:
                            decoded = html_mod.unescape(
                                base64.urlsafe_b64decode(data).decode("utf-8")
                            )
                            clean = re.sub(r"<[^>]+>", "", decoded)
                            return clean[:500]
            else:
                # Single-part message
                data = payload.get("body", {}).get("data", "")
                if data:
                    decoded = base64.urlsafe_b64decode(data).decode("utf-8")
                    return decoded[:500]

        except Exception as exc:
            self.logger.warning("Body extraction failed: %s", exc)

        # Last resort — Gmail snippet field
        return message.get("snippet", "Unable to extract email body")

    # ------------------------------------------------------------------
    # Priority
    # ------------------------------------------------------------------

    @staticmethod
    def _determine_priority(subject: str, body: str) -> str:
        """Keyword-based priority detection. Defaults to high (pre-filtered)."""
        content = (subject + " " + body).lower()

        high_kw = [
            "urgent", "asap", "immediate", "critical",
            "deadline", "emergency", "action required",
        ]
        medium_kw = [
            "meeting", "follow up", "reminder", "update",
            "report", "schedule", "review", "feedback",
        ]

        for kw in high_kw:
            if kw in content:
                return "high"
        for kw in medium_kw:
            if kw in content:
                return "medium"

        # Already filtered by label:IMPORTANT — default to high
        return "high"

    # ------------------------------------------------------------------
    # Date parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        """Parse an RFC-2822 email date header."""
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            return datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Event processing — create markdown file
    # ------------------------------------------------------------------

    def process_event(self, event: Dict[str, Any]) -> bool:
        """Create an EMAIL_{message_id}.md file in Needs_Action/."""
        filename = f"EMAIL_{event['id']}.md"
        file_path = self.needs_action_dir / filename

        # Idempotent — skip if file already exists
        if file_path.exists():
            self.logger.debug("File already exists, skipping: %s", filename)
            return True

        try:
            content = self._build_markdown(event)
            file_path.write_text(content, encoding="utf-8")
            self.logger.info(
                "Created %s — from: %s, subject: %s",
                filename,
                event["from_name"],
                event["subject"],
            )
            return True
        except OSError as exc:
            self.logger.error("Failed to write %s: %s", filename, exc)
            return False

    def _build_markdown(self, event: Dict[str, Any]) -> str:
        """Render an event dict as a markdown file with YAML frontmatter."""
        received = event["received"]
        if isinstance(received, datetime):
            received_iso = received.isoformat()
            received_display = received.strftime("%Y-%m-%d %I:%M %p")
        else:
            received_iso = str(received)
            received_display = str(received)

        subject_escaped = str(event["subject"]).replace('"', '\\"')

        return (
            f"---\n"
            f'type: email\n'
            f'from: {event["from_email"]}\n'
            f'subject: "{subject_escaped}"\n'
            f"received: {received_iso}\n"
            f'priority: {event["priority"]}\n'
            f"status: needs_action\n"
            f"---\n"
            f"\n"
            f'## Email from {event["from_name"]}\n'
            f"\n"
            f'**Subject:** {event["subject"]}\n'
            f"**Received:** {received_display}\n"
            f"\n"
            f"### Body\n"
            f"\n"
            f'{event["body_snippet"]}\n'
            f"\n"
            f"### Suggested Actions\n"
            f"\n"
            f"- [ ] Reply to this email\n"
            f"- [ ] Forward to team\n"
            f"- [ ] Archive this email\n"
        )


# ------------------------------------------------------------------
# CLI entry-point
# ------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gmail Watcher — monitors Gmail for important unread emails"
    )
    parser.add_argument(
        "--vault-path",
        default=os.getenv("VAULT_PATH", "./obsidian-vault"),
        help="Path to the Obsidian vault (default: $VAULT_PATH or ./obsidian-vault)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=120,
        help="Polling interval in seconds (default: 120)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll cycle and exit",
    )
    args = parser.parse_args()

    watcher = GmailWatcher(vault_path=args.vault_path, poll_interval=args.interval)

    if args.once:
        events = watcher.detect_events()
        count = 0
        for event in events:
            if not watcher._is_processed(event["id"]):
                if watcher.process_event(event):
                    watcher._mark_processed(event["id"])
                    count += 1
        print(f"Processed {count} email(s)")
    else:
        watcher.run()


if __name__ == "__main__":
    main()
