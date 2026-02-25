# AI Employee Dashboard

Welcome to your Personal AI Employee! This dashboard shows what's happening.

## How It Works

```
Gmail Inbox → Watcher detects email → Needs_Action/EMAIL_*.md
                                            ↓
                              Claude reads the file
                                            ↓
                              Plans/PLAN_*.md (response)
                                            ↓
                              You review → Done/
```

## Current Status

| Metric | Value |
|--------|-------|
| Emails Checked | 0 |
| Actions Created | 0 |
| Plans Generated | 0 |
| Last Updated | Not yet |

## Recent Activity

No activity yet. Start the Gmail watcher to begin!

## Quick Start

```bash
# 1. Set up Gmail credentials (see Company_Handbook.md)
# 2. Start the Gmail watcher:
uv run bronze/gmail_watcher.py --vault-path ./obsidian-vault

# 3. Start the Claude processor:
uv run bronze/claude_processor.py --vault-path ./obsidian-vault

# 4. Watch this dashboard update!
```

## Pending Actions

*No pending actions — Needs_Action/ is empty.*

## Recent Plans

*No plans yet — Plans/ is empty.*

---

## Silver Tier Status

**Mode:** STANDBY | **Processes:** 0/4 | **Last Check:** Not yet

### Managed Processes

| Process | Status | PID |
|---------|--------|-----|
| gmail-watcher | Stopped | - |
| whatsapp-watcher | Stopped | - |
| approval-manager | Stopped | - |
| main-orchestrator | Stopped | - |

### Approval Queue

| Pending | Approved | Rejected |
|---------|----------|----------|
| 0 | 0 | 0 |

### Scheduled Jobs

| Job | Schedule | Last Run |
|-----|----------|----------|
| morning-briefing | 8:00 AM daily | Never |
| ceo-briefing | 11:00 PM Sundays | Never |
| subscription-audit | 9:00 AM 1st of month | Never |
| health-check | Every 2 hours | Never |
| task-detection | Every 15 minutes | Never |

### Quick Commands

```bash
# Start Silver tier
uv run silver/start_silver.py

# Check status
uv run silver/start_silver.py --status

# Stop all
uv run silver/start_silver.py --stop
```

## Orchestrator Status

**Mode:** DRY RUN | **Last Cycle:** 2026-02-25 20:08 UTC | **Total Cycles:** 0

| Metric | Value |
|--------|-------|
| Queue Depth | 8 |
| Tasks Processed | 3 |
| Tasks Failed | 0 |
| Schedules | 5 |
| Poll Interval | 10s |
## System Health

**Status:** UNHEALTHY | **Last Check:** 2026-02-25 20:08 UTC

| Component | Status | Uptime | Last Check |
|-----------|--------|--------|------------|
| gmail-watcher | DOWN | not running | 2026-02-25 20:08 UTC |
| whatsapp-watcher | DOWN | not running | 2026-02-25 20:08 UTC |
| filesystem-watcher | DOWN | not running | 2026-02-25 20:08 UTC |
| approval-manager | DOWN | not running | 2026-02-25 20:08 UTC |
| vault-sync | DOWN | not running | 2026-02-25 20:08 UTC |

**Resources:** Disk 3.6% | Memory 22.4% | CPU 19.6%

**Alerts:** 2 active