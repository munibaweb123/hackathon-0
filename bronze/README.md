# Bronze Tier — Personal AI Employee

The simplest version of the AI Employee. Two scripts, one vault.

## How It Works

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│  Gmail   │────→│ gmail_watcher │────→│ Needs_Action/ │
│  Inbox   │     │  (polls 5min) │     │  EMAIL_*.md   │
└──────────┘     └──────────────┘     └──────┬───────┘
                                              │
                                              ▼
                                     ┌──────────────────┐
                                     │ claude_processor  │
                                     │ (reads + analyzes)│
                                     └──────┬───────────┘
                                              │
                              ┌───────────────┼──────────────┐
                              ▼               ▼              ▼
                        ┌──────────┐   ┌──────────┐   ┌──────────┐
                        │ Plans/   │   │  Done/   │   │  Logs/   │
                        │ PLAN_*.md│   │ (archive)│   │ activity │
                        └──────────┘   └──────────┘   └──────────┘
```

## Quick Start

### 1. Install uv (if you don't have it)

```bash
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Mac/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Set up Gmail API

Follow the instructions in `obsidian-vault/Company_Handbook.md`.

### 3. Create .env file

```bash
# In the project root (Hackathon_0/)
echo 'ANTHROPIC_API_KEY=sk-ant-your-key-here' > .env
```

### 4. Test with dry run (no API calls)

```bash
# Create a test action file
uv run bronze/gmail_watcher.py --vault-path ./obsidian-vault --once

# Process it (dry run — no Claude calls)
uv run bronze/claude_processor.py --vault-path ./obsidian-vault --once --dry-run
```

### 5. Run for real

```bash
# Terminal 1: Watch Gmail
uv run bronze/gmail_watcher.py --vault-path ./obsidian-vault

# Terminal 2: Process with Claude
uv run bronze/claude_processor.py --vault-path ./obsidian-vault
```

## Files

| File | Purpose |
|------|---------|
| `gmail_watcher.py` | Polls Gmail for unread emails, creates Needs_Action/ files |
| `claude_processor.py` | Reads Needs_Action/ files, calls Claude, creates Plans/ |
| `README.md` | You're reading it! |

## What Each Script Does

### gmail_watcher.py
1. Connects to Gmail using OAuth2
2. Checks for unread emails every 5 minutes
3. For each email, creates a markdown file in `Needs_Action/`
4. The file has YAML metadata (sender, subject, date) and a preview

### claude_processor.py
1. Scans `Needs_Action/` for `.md` files
2. Reads each file's metadata and content
3. Sends it to Claude with the Company Handbook as context
4. Saves Claude's response as a plan in `Plans/`
5. Moves the original file to `Done/`

## Next Steps (Silver Tier)

Once you're comfortable with Bronze:
- Add WhatsApp monitoring
- Add approval workflows (human-in-the-loop)
- Add a Next.js dashboard
- See the `agent-skills/` folder for the Silver tier implementation
