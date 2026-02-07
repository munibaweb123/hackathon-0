#!/usr/bin/env python3
"""
Test script to demonstrate real Gmail and LinkedIn API functionality
"""

import sys
import os
from pathlib import Path
import time

# Add the project root and agent-skills to the Python path
project_root = Path('.').resolve()
agent_skills_dir = project_root / 'agent-skills'

sys.path.insert(0, str(project_root))
sys.path.insert(0, str(agent_skills_dir))

# Add all subdirectories to the path to allow direct imports
subdirs = ['core', 'watchers', 'skills', 'mcp_server', 'scheduler', 'models', 'cli']
for subdir in subdirs:
    subdir_path = agent_skills_dir / subdir
    if subdir_path.exists():
        sys.path.insert(0, str(subdir_path))

from core.vault_interface import VaultInterface
from core.logger import Logger
from watchers.gmail_watcher import GmailWatcher
from watchers.linkedin_watcher import LinkedInWatcher

# Create vault interface and logger
vault_interface = VaultInterface(vault_path='./vault')
logger = Logger(log_dir='./logs')

print("Testing REAL Gmail and LinkedIn API integrations...")

print("\n" + "="*60)
print("INITIALIZING GMAIL WATCHER")
print("="*60)

# Initialize Gmail watcher (this will try to connect to real API if credentials exist)
gmail_watcher = GmailWatcher(vault_interface, logger)

print(f"Gmail watcher initialized with account: {gmail_watcher.email_account}")
print(f"Gmail service available: {gmail_watcher.gmail_service is not None}")

print("\n" + "-"*40)
print("GMAIL STATUS:")
print("-"*40)

if gmail_watcher.gmail_service:
    print("✅ Gmail API connected - REAL data will be fetched!")
    print("   - OAuth token available")
    print("   - Gmail service initialized")
    print("   - Ready to fetch real emails")
else:
    print("⚠️  Gmail API in mock mode - using simulated data")
    print("   - No OAuth token found")
    print("   - Will simulate Gmail activity every 10 minutes")

print("\n" + "="*60)
print("INITIALIZING LINKEDIN WATCHER")
print("="*60)

# Initialize LinkedIn watcher (this will try to connect to real API if credentials exist)
linkedin_watcher = LinkedInWatcher(vault_interface, logger)

print(f"LinkedIn watcher initialized with profile: {linkedin_watcher.profile_url}")
print(f"LinkedIn session available: {linkedin_watcher.linkedin_session is not None}")

print("\n" + "-"*40)
print("LINKEDIN STATUS:")
print("-"*40)

if linkedin_watcher.linkedin_session:
    print("✅ LinkedIn API connected - REAL data will be fetched!")
    print("   - API token available")
    print("   - LinkedIn session initialized")
    print("   - Ready to monitor profile views and activities")
else:
    print("⚠️  LinkedIn API in mock mode - using simulated data")
    print("   - No API token found")
    print("   - Will simulate LinkedIn activity every 15 minutes")

print("\n" + "="*60)
print("API INTEGRATION SUMMARY")
print("="*60)

print(f"• Gmail Integration: {'REAL' if gmail_watcher.gmail_service else 'MOCK'}")
print(f"• LinkedIn Integration: {'REAL' if linkedin_watcher.linkedin_session else 'MOCK'}")
print(f"• Vault Path: {vault_interface.vault_path}")
print(f"• Check Interval (Gmail): {gmail_watcher.check_interval}s")
print(f"• Check Interval (LinkedIn): {linkedin_watcher.check_interval}s")

print("\n" + "="*60)
print("TO ENABLE REAL API FUNCTIONALITY")
print("="*60)
print("For Gmail:")
print("  1. Place 'token.json' with valid OAuth token in root directory")
print("  2. Or set GMAIL_OAUTH_TOKEN environment variable")
print("  3. Or set GMAIL_ACCOUNT environment variable")
print()
print("For LinkedIn:")
print("  1. Set LINKEDIN_API_TOKEN environment variable")
print("  2. Set LINKEDIN_PROFILE_URL environment variable")
print()
print("Current environment variables:")
print(f"  - GMAIL_ACCOUNT: {os.getenv('GMAIL_ACCOUNT', 'Not set')}")
print(f"  - GMAIL_OAUTH_TOKEN: {'Set' if os.getenv('GMAIL_OAUTH_TOKEN') else 'Not set'}")
print(f"  - LINKEDIN_PROFILE_URL: {os.getenv('LINKEDIN_PROFILE_URL', 'Not set')}")
print(f"  - LINKEDIN_API_TOKEN: {'Set' if os.getenv('LINKEDIN_API_TOKEN') else 'Not set'}")

print("\n" + "="*60)
print("DEMONSTRATING DETECT_EVENTS METHOD")
print("="*60)

print("\nTesting Gmail detect_events()...")
gmail_event = gmail_watcher.detect_events()
if gmail_event:
    print(f"✅ Gmail event detected: {gmail_event.get('event_type', 'Unknown')} - {gmail_event.get('subject', 'No subject')}")
else:
    print("ℹ️  No Gmail events detected (or in mock mode)")

print("\nTesting LinkedIn detect_events()...")
linkedin_event = linkedin_watcher.detect_events()
if linkedin_event:
    print(f"✅ LinkedIn event detected: {linkedin_event.get('event_type', 'Unknown')} - {linkedin_event.get('message', 'No message')}")
else:
    print("ℹ️  No LinkedIn events detected (or in mock mode)")

print("\n" + "="*60)
print("RUNNING SINGLE POLL CYCLE")
print("="*60)

print("\nPolling Gmail...")
gmail_result = gmail_watcher.poll_gmail()
print(f"Gmail poll result: {'Success' if gmail_result else 'Failed'}")

print("\nPolling LinkedIn...")
linkedin_result = linkedin_watcher.poll_linkedin()
print(f"LinkedIn poll result: {'Success' if linkedin_result else 'Failed'}")

print("\nCheck the vault/inbox directory for any new event files that were created!")
print("Files will be created when events are detected by the watchers.")