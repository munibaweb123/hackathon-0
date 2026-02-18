---
name: whatsapp-watcher
description: Standalone WhatsApp Web watcher that monitors for urgent messages using Playwright and creates markdown action files in the Obsidian vault.
---

# WhatsApp Watcher Agent Skill

Monitors WhatsApp Web for **urgent messages** using Playwright browser automation and creates human-readable markdown action files in the Obsidian vault's `Needs_Action/` folder.

## Quick Start

### With UV (recommended)

```bash
# First run — opens browser for QR code scanning
uv run whatsapp_watcher.py --vault-path ../../obsidian-vault

# After session is established — headless mode
uv run whatsapp_watcher.py --headless
```

### With pip

```bash
pip install -r requirements.txt
playwright install chromium
python whatsapp_watcher.py --vault-path ../../obsidian-vault
```

### Single poll (no loop)

```bash
uv run whatsapp_watcher.py --once
```

## Prerequisites

1. **Python 3.10+**
2. **Playwright** with Chromium browser installed (`playwright install chromium`)
3. **WhatsApp account** linked to a phone

## QR Code Authentication

On the first run, the browser opens and displays a QR code:

```
==================================================
  WHATSAPP QR CODE AUTHENTICATION
==================================================
  1. Open WhatsApp on your phone
  2. Go to Settings > Linked Devices
  3. Tap 'Link a Device'
  4. Scan the QR code shown in the browser
  Waiting up to 120 seconds ...
==================================================
```

After scanning, the session is saved to `~/.whatsapp-watcher/session.json`. Future runs restore the session automatically — no QR scan needed.

## Architecture

```
WhatsApp Web (Playwright)
       │
       ▼
  WhatsAppWatcher.detect_events()
  filter: unread + keyword match
       │
       ▼
  WhatsAppWatcher.process_event()
       │
       ├──▶ Needs_Action/WHATSAPP_{timestamp}.md   (action file)
       ├──▶ Logs/whatsapp_watcher.log               (rotating log)
       ├──▶ Logs/processed_ids.json                  (dedup state)
       └──▶ Logs/screenshots/                        (on urgent detect)
```

## Monitored Keywords

Messages are only captured if they contain one of these keywords:

| Keyword | Priority |
|---------|----------|
| `urgent` | high |
| `emergency` | high |
| `invoice` | high |
| `payment` | high |
| `asap` | medium |
| `help` | medium |

## Output Format

Each urgent message produces a file like `Needs_Action/WHATSAPP_20260215_103000.md`:

```markdown
---
type: whatsapp
contact: "John Doe"
received: 2026-02-15T10:30:00+00:00
priority: high
keywords_matched: [urgent, payment]
status: needs_action
---

## WhatsApp Message from John Doe

**Received:** 2026-02-15 10:30 AM
**Priority:** high
**Keywords:** urgent, payment

### Message

Hi, this is urgent — please check the payment for invoice #1234

### Suggested Actions

- [ ] Reply to John Doe
- [ ] Forward to team
- [ ] Mark as handled
```

## Session Management

| Aspect | Details |
|--------|---------|
| Storage location | `~/.whatsapp-watcher/session.json` (outside vault) |
| Persistence | Playwright `storage_state` API |
| Expiry | When WhatsApp Web disconnects or phone unlinks |
| Re-auth | Run without `--headless` to scan a new QR code |
| Custom path | `--session-dir /path/to/dir` |

## Bot Detection Safeguards

- **Random delays** (2-5s) between reading different chats
- **Realistic user agent** (Chrome 120 on Windows 10)
- **Anti-automation flags** disabled (`--disable-blink-features=AutomationControlled`)
- **30-second minimum** polling interval (default)
- **Read-only** — never sends messages or modifies chats

## Rate Limiting

- Default poll interval: 30 seconds
- Random 2-5s delay between chat reads within a single poll
- No bulk operations — only reads visible unread indicators
- Respects WhatsApp's terms of service (monitoring only, no messaging)

## Screenshot Capture

When urgent messages are detected, a screenshot is automatically saved to `Logs/screenshots/urgent_detected.png`. This helps capture complex messages (images, voice notes, documents) that can't be extracted as text.

## CLI Options

```
usage: whatsapp_watcher.py [-h] [--vault-path PATH] [--interval SECONDS]
                           [--once] [--headless] [--session-dir DIR]

--vault-path    Path to the Obsidian vault (default: $VAULT_PATH or ./obsidian-vault)
--interval      Polling interval in seconds (default: 30)
--once          Run a single poll cycle and exit
--headless      Run browser without GUI (requires existing session)
--session-dir   Custom directory for session storage (default: ~/.whatsapp-watcher/)
```

## File Structure

```
.claude/skills/whatsapp-watcher/
├── SKILL.md              # This documentation
├── whatsapp_watcher.py   # Main UV-runnable script
├── session_manager.py    # Playwright session lifecycle
└── requirements.txt      # Dependencies
```

Uses `base_watcher.py` from the sibling `gmail-watcher` skill for the polling loop, dedup, logging, and exponential backoff.

## Important Notes

- WhatsApp Web selectors may change with updates — selectors are defined in `session_manager.py` for easy updating
- Browser must remain running for continuous monitoring
- First run **must** be non-headless for QR scanning
- Session tokens are stored outside the vault for security
- This skill is **read-only** — it never sends messages or interacts with chats
