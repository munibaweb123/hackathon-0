---
name: gmail-watcher
description: Standalone Gmail watcher agent skill that polls for important unread emails and creates markdown action files in the Obsidian vault.
---

# Gmail Watcher Agent Skill

Monitors Gmail for **unread emails marked as Important** and creates human-readable markdown action files in the Obsidian vault's `Needs_Action/` folder.

## Quick Start

### With UV (recommended)

```bash
uv run gmail_watcher.py --vault-path ../../obsidian-vault
```

### With pip

```bash
pip install -r requirements.txt
python gmail_watcher.py --vault-path ../../obsidian-vault
```

### Single poll (no loop)

```bash
uv run gmail_watcher.py --once
```

## Prerequisites

1. **Python 3.10+**
2. **Google Cloud project** with the Gmail API enabled
3. **OAuth2 credentials** — download `client-secret.json` from the Google Cloud Console and place it in the project root
4. **First-time auth** — on the first run the script opens a browser for OAuth consent and saves the token to `gmail-token.json`

## Configuration

Copy `.env.example` to `.env` (or set these in the project root `.env`):

| Variable | Description |
|----------|-------------|
| `GMAIL_CLIENT_ID` | OAuth2 client ID from Google Cloud Console |
| `GMAIL_CLIENT_SECRET` | OAuth2 client secret |
| `VAULT_PATH` | Path to the Obsidian vault (default `./obsidian-vault`) |

### Token file search order

The skill looks for an existing OAuth token in:

1. `{project_root}/dashboard/gmail-token.json` (shared with the Next.js dashboard)
2. `{project_root}/gmail-token.json`
3. `{project_root}/token.json`

If none are found and `client-secret.json` exists, an interactive OAuth flow runs automatically.

## Architecture

```
Gmail API (OAuth2)
       │
       ▼
  GmailWatcher.detect_events()
  query: is:unread label:IMPORTANT
       │
       ▼
  GmailWatcher.process_event()
       │
       ├──▶ Needs_Action/EMAIL_{message_id}.md   (action file)
       ├──▶ Logs/gmail_watcher.log                (rotating log)
       └──▶ Logs/processed_ids.json               (dedup state)
```

## Output Format

Each email produces a file like `Needs_Action/EMAIL_18f3a2b.md`:

```markdown
---
type: email
from: sender@example.com
subject: "Quarterly Report Ready"
received: 2026-02-15T10:30:00+05:00
priority: high
status: needs_action
---

## Email from John Doe

**Subject:** Quarterly Report Ready
**Received:** 2026-02-15 10:30 AM

### Body

Hi team, the quarterly report is now ready for review...

### Suggested Actions

- [ ] Reply to this email
- [ ] Forward to team
- [ ] Archive this email
```

## Deduplication

Two layers prevent duplicate processing:

1. **File check** — if `EMAIL_{id}.md` already exists, the event is skipped
2. **Processed IDs** — `Logs/processed_ids.json` persists every processed Gmail message ID across restarts

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| API rate limit (HTTP 429) | Exponential backoff: 2 s → 4 s → 8 s → 16 s → 32 s (max 64 s, 5 retries) |
| Server error (HTTP 5xx) | Same exponential backoff |
| Token expired | Auto-refresh using `refresh_token` |
| No credentials | Clear error message with setup instructions |
| Network failure | Logged, continues on next poll cycle |
| Corrupt state file | Starts with empty set, logs warning |

## Gmail API Rate Limits

- **Quota**: 250 quota units per user per second
- `messages.list` = 5 units, `messages.get` = 5 units
- With `maxResults=20`, a single poll uses at most ~105 units
- The 2-minute poll interval stays well within limits

## CLI Options

```
usage: gmail_watcher.py [-h] [--vault-path PATH] [--interval SECONDS] [--once]

--vault-path    Path to the Obsidian vault (default: $VAULT_PATH or ./obsidian-vault)
--interval      Polling interval in seconds (default: 120)
--once          Run a single poll cycle and exit
```

## File Structure

```
.claude/skills/gmail-watcher/
├── SKILL.md           # This documentation
├── gmail_watcher.py   # Main UV-runnable script
├── base_watcher.py    # Abstract base class (stdlib only)
├── requirements.txt   # pip dependencies
└── .env.example       # Credential template
```

## Integration with the AI Employee

This skill operates **independently** from the existing `agent-skills/watchers/gmail_watcher.py`. The two can run side-by-side without conflict:

| | Existing Watcher | This Skill |
|---|---|---|
| Output folder | `inbox/` | `Needs_Action/` |
| File format | JSON | Markdown with YAML frontmatter |
| Filter | All unread emails | Unread + Important only |
| Poll interval | 5 minutes | 2 minutes |
| Dedup | None | `processed_ids.json` + file check |
| Backoff | None | Exponential with jitter |
