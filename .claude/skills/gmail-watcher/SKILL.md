---
name: gmail-watcher
description: Gmail monitoring skill for the AI Employee. Handles OAuth token sharing, Gmail API polling, incremental sync via History API, and event file creation in the Obsidian vault.
---

# Gmail Watcher Skill

Monitors Gmail for new emails and creates structured event files in the vault inbox.

## Architecture

```
Gmail API → gmail_watcher.py → VaultInterface → obsidian-vault/inbox/
```

- **Perception phase** of the Perception → Reasoning → Action pipeline
- Polls Gmail API at configurable intervals (default: 5 minutes)
- Creates `EMAIL_<timestamp>_<id>.md` event files with YAML frontmatter

## Key Files

| File | Purpose |
|------|---------|
| `agent-skills/watchers/gmail_watcher.py` | Gmail watcher implementation |
| `agent-skills/watchers/watcher_base.py` | Base watcher class |
| `agent-skills/core/vault_interface.py` | Vault file operations |
| `agent-skills/models/event.py` | Event data model |
| `dashboard/src/app/api/gmail/` | OAuth routes (auth, callback, status, emails) |
| `dashboard/gmail-token.json` | OAuth tokens (shared with Python backend) |

## OAuth Token Sharing

The Gmail watcher reads tokens created by the Next.js dashboard OAuth flow:

```python
# Token search order:
# 1. dashboard/gmail-token.json (primary - from Next.js OAuth)
# 2. gmail-token.json (fallback)
# 3. token.json (legacy fallback)
```

If tokens are expired, the watcher refreshes them using the refresh_token and saves back.

## Event File Format

```yaml
---
id: EMAIL_20260208_143022_abc123
source_type: email
source_id: gmail_user@gmail.com
event_type: new_email
timestamp: 2026-02-08T14:30:22Z
detected_at: 2026-02-08T14:30:25Z
priority: medium
processing_status: new
---
# Email Event
**From**: sender@example.com
**Subject**: Meeting tomorrow
```

## Incremental Sync

Uses Gmail History API for efficient polling:
1. First run: full query for recent emails
2. Subsequent runs: `_detect_via_history()` with stored `historyId`
3. Falls back to full query if history ID is stale (404)

## Mock Mode

When `mock_mode=True` or OAuth tokens are unavailable:
- Generates synthetic email events for testing
- Logs `[MOCK]` prefix in all messages
- Still creates valid event files in the vault

## Priority Detection

Urgency indicators checked in subject/sender:
- Keywords: urgent, asap, deadline, important, critical, action required
- High priority → `priority: high` in event metadata

## Error Handling

- OAuth failure → graceful fallback to mock mode
- Network error → retry on next poll cycle
- Invalid token → attempt refresh, then mock mode
