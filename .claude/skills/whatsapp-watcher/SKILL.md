---
name: whatsapp-watcher
description: WhatsApp Web monitoring skill using Playwright browser automation. Handles QR code authentication, session persistence, and message detection.
---

# WhatsApp Watcher Skill

Monitors WhatsApp Web for new messages using Playwright browser automation.

## Architecture

```
WhatsApp Web (Browser) → Playwright → whatsapp_watcher.py → VaultInterface → obsidian-vault/inbox/
```

- Uses Playwright (NOT Meta Business Cloud API)
- Requires one-time QR code scan for authentication
- Session persisted in `whatsapp_session.json`
- Headless=False for initial QR scan, can switch to headless after

## Key Files

| File | Purpose |
|------|---------|
| `agent-skills/watchers/whatsapp_watcher.py` | Playwright automation |
| `agent-skills/mcp_server/actions/whatsapp_action.py` | Reply action handler |
| `dashboard/src/app/whatsapp/page.tsx` | WhatsApp dashboard page |
| `dashboard/src/components/whatsapp-live.tsx` | Live status component |
| `dashboard/src/app/api/whatsapp/` | Status and events API |

## QR Code Authentication

```python
# First run:
1. Launch Chromium (headless=False)
2. Navigate to https://web.whatsapp.com
3. User scans QR code in browser
4. Wait for chat-list selector (2 min timeout)
5. Save session to whatsapp_session.json

# Subsequent runs:
1. Launch with storage_state=whatsapp_session.json
2. Skip QR scan (session restored)
```

## Message Detection

```python
# Async detection flow:
1. Wait for page networkidle
2. Query unread chats: div.chat[data-unread-count]
3. Click each chat to open
4. Extract message content from div.message-in
5. Create event file per message
```

## Event File Format

```yaml
---
id: wa_msg_20260208_143022_abc123
source_type: whatsapp
source_id: wa_chat_ContactName
event_type: whatsapp_message
timestamp: 2026-02-08T14:30:22Z
priority: medium
---
# Whatsapp Event
**From**: ContactName
**Content**: Message text here
```

## Mock Mode

When Playwright is unavailable or no session exists:
- Generates synthetic WhatsApp events
- Returns mock messages with realistic structure
- Useful for testing without WhatsApp Web access

## Session Management

- Session file: `whatsapp_session.json`
- Saved after successful QR scan
- Loaded on subsequent runs via `storage_state`
- Session expires when WhatsApp Web disconnects (requires re-scan)

## Important Notes

- WhatsApp Web selectors may change — selectors need periodic updates
- Rate limit: don't poll too frequently (30 second minimum interval)
- Browser must remain open for continuous monitoring
- Cleanup resources on shutdown (browser.close(), playwright.stop())
