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
Bronze Tier Gmail Watcher — Simple email monitoring for beginners.

Checks Gmail for unread emails every 5 minutes and creates
action files in the Obsidian vault's Needs_Action/ folder.

This is the simplest possible watcher — no dedup, no backoff,
no complex features. Perfect for learning the basics.

Usage:
    uv run gmail_watcher.py --vault-path ../obsidian-vault
    uv run gmail_watcher.py --vault-path ../obsidian-vault --once
    uv run gmail_watcher.py --vault-path ../obsidian-vault --interval 120
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv()

# Gmail API scopes — read-only access
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service():
    """
    Connect to Gmail API using OAuth2.

    First run: opens a browser for you to log in.
    After that: uses saved token.json automatically.

    Returns:
        Gmail API service object, or None if auth fails.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds_path = os.getenv("GMAIL_CREDENTIALS_PATH", "./credentials.json")
    token_path = os.getenv("GMAIL_TOKEN_PATH", "./token.json")

    creds = None

    # Load existing token
    if Path(token_path).exists():
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Refresh or create new token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing Gmail token...")
            creds.refresh(Request())
        else:
            if not Path(creds_path).exists():
                print(f"ERROR: Gmail credentials not found at: {creds_path}")
                print("See Company_Handbook.md for setup instructions.")
                return None

            print("Opening browser for Gmail authentication...")
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for next time
        Path(token_path).write_text(creds.to_json())
        print(f"Token saved to: {token_path}")

    return build("gmail", "v1", credentials=creds)


def fetch_unread_emails(service, max_results=10):
    """
    Fetch unread emails from Gmail.

    Args:
        service: Gmail API service object.
        max_results: Maximum number of emails to fetch.

    Returns:
        List of email dicts: [{id, subject, sender, snippet, date}]
    """
    try:
        # Search for unread emails in inbox
        results = (
            service.users()
            .messages()
            .list(userId="me", q="is:unread in:inbox", maxResults=max_results)
            .execute()
        )

        messages = results.get("messages", [])
        if not messages:
            return []

        emails = []
        for msg_info in messages:
            # Get full message details
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_info["id"], format="metadata",
                     metadataHeaders=["From", "Subject", "Date"])
                .execute()
            )

            # Extract headers
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

            emails.append({
                "id": msg["id"],
                "subject": headers.get("Subject", "(no subject)"),
                "sender": headers.get("From", "(unknown)"),
                "date": headers.get("Date", ""),
                "snippet": msg.get("snippet", ""),
            })

        return emails

    except Exception as e:
        print(f"ERROR fetching emails: {e}")
        return []


def create_action_file(email, vault_path):
    """
    Create a markdown action file in Needs_Action/ for an email.

    The file has YAML frontmatter (metadata) and a markdown body.
    This is the format other tools (like the Claude processor) expect.

    Args:
        email: Email dict from fetch_unread_emails().
        vault_path: Path to the Obsidian vault.

    Returns:
        Path to the created file, or None on failure.
    """
    needs_action = Path(vault_path) / "Needs_Action"
    needs_action.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    safe_id = email["id"][:12]  # Shorten the Gmail message ID
    filename = f"EMAIL_{safe_id}_{timestamp}.md"
    filepath = needs_action / filename

    # Don't overwrite if file already exists (basic dedup)
    if filepath.exists():
        return None

    # Build the action file
    content = f"""---
type: email
source: gmail
message_id: {email['id']}
sender: "{email['sender']}"
subject: "{email['subject']}"
date_received: "{email['date']}"
created: {now.isoformat()}
priority: medium
status: new
---

# Email from {email['sender']}

**Subject:** {email['subject']}
**Date:** {email['date']}

## Preview

{email['snippet']}

## Suggested Actions

- [ ] Read full email
- [ ] Draft reply
- [ ] Archive if no action needed
"""

    filepath.write_text(content, encoding="utf-8")
    return filepath


def log_activity(vault_path, message):
    """
    Append a log entry to Logs/gmail_watcher.log.

    Simple text logging — one line per event.
    """
    logs_dir = Path(vault_path) / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_file = logs_dir / "gmail_watcher.log"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}\n"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line)


def update_dashboard(vault_path, emails_checked, actions_created):
    """
    Update the Dashboard.md with latest watcher stats.

    Replaces the 'Current Status' table values.
    """
    dashboard = Path(vault_path) / "Dashboard.md"
    if not dashboard.exists():
        return

    content = dashboard.read_text(encoding="utf-8")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Simple string replacements for the status table
    import re
    content = re.sub(
        r"\| Last Updated \| .* \|",
        f"| Last Updated | {now} |",
        content,
    )

    dashboard.write_text(content, encoding="utf-8")


def run_watcher(vault_path, interval=300, once=False):
    """
    Main watcher loop.

    Args:
        vault_path: Path to the Obsidian vault.
        interval: Seconds between checks (default: 300 = 5 minutes).
        once: If True, check once and exit.
    """
    print(f"Bronze Gmail Watcher")
    print(f"  Vault: {vault_path}")
    print(f"  Interval: {interval}s")
    print(f"  Mode: {'single check' if once else 'continuous'}")
    print()

    # Connect to Gmail
    print("Connecting to Gmail...")
    service = get_gmail_service()
    if service is None:
        print("Failed to connect to Gmail. Check your credentials.")
        sys.exit(1)

    print("Connected! Starting to watch for emails...\n")
    log_activity(vault_path, "Watcher started")

    try:
        while True:
            # Fetch unread emails
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking for unread emails...")
            emails = fetch_unread_emails(service)

            if emails:
                print(f"  Found {len(emails)} unread email(s)")
                created = 0

                for email in emails:
                    filepath = create_action_file(email, vault_path)
                    if filepath:
                        print(f"  Created: {filepath.name}")
                        log_activity(
                            vault_path,
                            f"Action created: {filepath.name} — {email['subject'][:50]}",
                        )
                        created += 1
                    else:
                        print(f"  Skipped (already exists): EMAIL_{email['id'][:12]}")

                if created > 0:
                    update_dashboard(vault_path, len(emails), created)
                    print(f"  {created} new action file(s) created!")
            else:
                print("  No unread emails.")

            if once:
                break

            print(f"  Next check in {interval}s...\n")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nWatcher stopped by user.")
        log_activity(vault_path, "Watcher stopped (user interrupt)")


def main():
    parser = argparse.ArgumentParser(
        description="Bronze Tier Gmail Watcher — monitors Gmail for unread emails"
    )
    parser.add_argument(
        "--vault-path",
        default="./obsidian-vault",
        help="Path to Obsidian vault (default: ./obsidian-vault)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Check interval in seconds (default: 300 = 5 minutes)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Check once and exit (good for testing)",
    )

    args = parser.parse_args()
    run_watcher(args.vault_path, args.interval, args.once)


if __name__ == "__main__":
    main()
