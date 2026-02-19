# Silver Tier — AI Employee with Approval Workflows

Builds on Bronze by adding WhatsApp monitoring, email sending, human-in-the-loop approval, scheduled tasks, and multi-step planning.

## Architecture

```
┌──────────┐     ┌──────────────┐
│  Gmail   │────→│ gmail-watcher │──→ Needs_Action/EMAIL_*.md
│  Inbox   │     └──────────────┘
└──────────┘
┌──────────┐     ┌──────────────────┐
│ WhatsApp │────→│ whatsapp-watcher  │──→ Needs_Action/WHATSAPP_*.md
│  Web     │     └──────────────────┘
└──────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  main-orchestrator   │
              │  (priority queue +   │
              │   cron scheduler)    │
              └──────────┬───────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    ┌──────────┐  ┌────────────┐  ┌──────────────┐
    │Claude CLI│  │ Scheduler  │  │ Task Planner │
    │(analyze) │  │(cron jobs) │  │(decompose)   │
    └────┬─────┘  └────────────┘  └──────┬───────┘
         │                               │
         ▼                               ▼
    plans/PLAN_*.md              pending-approval/
                                 APPROVAL_REQUIRED_*.md
                                         │
                                         ▼
                              ┌──────────────────────┐
                              │  approval-manager     │
                              │  (human-in-the-loop)  │
                              └──────────┬────────────┘
                                         │
                          ┌──────────────┼──────────┐
                          ▼              ▼          ▼
                     Approved/      Rejected/   (expired)
                          │
                          ▼
                    Handler routing:
                    SEND_EMAIL_*    → email-sender-mcp
                    EXECUTE_PAYMENT → payment handler
                    POST_SOCIAL_*   → social poster
```

## What Each Skill Does

### 1. gmail-watcher
Polls Gmail every 5 minutes for unread emails. Creates `EMAIL_*.md` files in `Needs_Action/` with YAML frontmatter (sender, subject, date, priority).

### 2. whatsapp-watcher
Uses Playwright to monitor WhatsApp Web for urgent messages (keywords: urgent, emergency, invoice, payment, asap, help). Creates `WHATSAPP_*.md` files in `Needs_Action/`.

### 3. main-orchestrator
Central coordinator with two engines:
- **Priority Queue**: Scans `Needs_Action/`, classifies by prefix (ALERT > WHATSAPP > EMAIL > FILE > TASK > NOTIFY), routes to Claude CLI for analysis or marks complete for downstream handlers.
- **Cron Scheduler**: Runs timed jobs — morning briefings, CEO reports, subscription audits, health checks.

### 4. approval-manager (Human-in-the-Loop)
Monitors `pending-approval/` for approval requests. When a human moves a file to `Approved/` or `Rejected/`, the appropriate handler executes:
- **PaymentHandler** → Creates `EXECUTE_PAYMENT_*.md`
- **EmailHandler** → Creates `SEND_EMAIL_*.md`
- **SocialHandler** → Creates `POST_SOCIAL_*.md`
- **InvoiceHandler** → Creates `SEND_INVOICE_*.md`

### 5. task-planner
Decomposes complex requests into structured task plans with:
- Phase classification (Setup → Core → Test → Deploy → Communicate)
- Dependency resolution (topological sort)
- Time estimates and risk assessment
- Approval checkpoints for high-risk tasks

### 6. email-sender-mcp (Node.js — separate process)
MCP server exposing `send_email`, `draft_email`, `reply_to_email` tools via Gmail API. Runs as a standalone Node.js process or Claude Desktop MCP integration.

## Prerequisites

- Python 3.10+
- Node.js 18+ (for email-sender-mcp)
- [uv](https://docs.astral.sh/uv/) package manager
- Gmail API credentials (OAuth 2.0)
- Anthropic API key

## Quick Start

### 1. Set up environment

```bash
# Copy the Silver tier env template
cp silver/.env.example .env

# Edit with your actual keys
# - ANTHROPIC_API_KEY
# - GMAIL_CREDENTIALS_PATH (download from Google Cloud Console)
```

### 2. Gmail OAuth (first time only)

```bash
# Run the Bronze watcher once to trigger OAuth flow
uv run bronze/gmail_watcher.py --vault-path ./obsidian-vault --once
# This opens a browser → approve → token.json is created
```

### 3. WhatsApp setup (first time only)

```bash
# Run in non-headless mode to scan QR code
uv run .claude/skills/whatsapp-watcher/whatsapp_watcher.py \
  --vault-path ./obsidian-vault --once
# Scan the QR code with your phone → session is saved
```

### 4. Validate configuration

```bash
# Dry run — checks config, vault folders, credentials
uv run silver/start_silver.py --dry-run
```

### 5. Start Silver tier

```bash
# Start all skills
uv run silver/start_silver.py

# Or with debug output
uv run silver/start_silver.py --verbose
```

### 6. Start email sender (separate terminal)

```bash
cd .claude/skills/email-sender-mcp
npm install
npm start
```

### 7. Check status

```bash
uv run silver/start_silver.py --status
```

### 8. Stop everything

```bash
uv run silver/start_silver.py --stop
```

## Testing Individual Skills

```bash
# Gmail watcher — single check
uv run .claude/skills/gmail-watcher/gmail_watcher.py \
  --vault-path ./obsidian-vault --once

# WhatsApp watcher — single check
uv run .claude/skills/whatsapp-watcher/whatsapp_watcher.py \
  --vault-path ./obsidian-vault --once

# Orchestrator — show queue
uv run .claude/skills/main-orchestrator/main_orchestrator.py --queue

# Orchestrator — single cycle
uv run .claude/skills/main-orchestrator/main_orchestrator.py --once

# Approval manager — show pending
uv run .claude/skills/approval-manager/approval_manager.py --pending

# Task planner — detect complex tasks
uv run .claude/skills/task-planner/task_planner.py \
  --vault-path ./obsidian-vault --detect
```

## Approval Workflow

The human-in-the-loop flow works through the Obsidian vault:

1. A skill creates `pending-approval/APPROVAL_REQUIRED_*.md`
2. You review it in Obsidian (or any text editor)
3. **To approve:** Move the file to `Approved/`
4. **To reject:** Move the file to `Rejected/`
5. The approval-manager detects the move and routes to the appropriate handler
6. The handler creates an action file in `Needs_Action/` for the downstream MCP skill

## Scheduled Jobs

Configured in `.claude/skills/main-orchestrator/config.yaml`:

| Job | Schedule | Description |
|-----|----------|-------------|
| morning-briefing | 8:00 AM daily | Quick summary of overnight activity |
| ceo-briefing | 11:00 PM Sundays | Full weekly CEO briefing |
| subscription-audit | 9:00 AM 1st of month | Monthly subscription waste check |
| health-check | Every 2 hours | System health verification |
| task-detection | Every 15 minutes | Scan for complex tasks needing decomposition |

## Vault Folder Structure

```
obsidian-vault/
├── Dashboard.md          ← System status overview
├── Company_Handbook.md   ← Business context for AI
├── Needs_Action/         ← Incoming events (watchers write here)
├── In_Progress/          ← Orchestrator claims (processing)
├── pending-approval/     ← Awaiting human decision
├── Approved/             ← Human approved (triggers handler)
├── Rejected/             ← Human rejected (archived)
├── Plans/                ← Bronze-style plans (uppercase)
├── plans/                ← Gold-style task plans (lowercase)
├── Done/                 ← Completed tasks archive
├── Logs/                 ← Activity logs per skill
├── Reports/              ← Generated reports (audits, briefings)
├── Attachments/          ← Email attachments
└── error/                ← Failed tasks with annotations
```

## Troubleshooting

**Process won't start:**
Check logs in `obsidian-vault/Logs/{process-name}.stderr.log`

**Gmail auth expired:**
Delete `token.json` and re-run the Bronze gmail_watcher with `--once` to re-authenticate.

**WhatsApp session lost:**
Delete the `whatsapp-session/` directory and re-scan the QR code.

**Approval not detected:**
Make sure you're moving files to the exact `Approved/` or `Rejected/` folder (case-sensitive).

**Orchestrator not processing:**
Check `uv run .claude/skills/main-orchestrator/main_orchestrator.py --status` for queue depth and errors.
