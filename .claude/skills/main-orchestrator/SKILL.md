---
name: main-orchestrator
description: Central orchestrator for the AI Employee. Processes tasks from Needs_Action/ via a priority queue, runs cron-scheduled jobs, and routes tasks to Claude CLI or downstream skills via subprocess.
tools: []
tags:
  - orchestrator
  - task-queue
  - scheduler
  - claude-cli
  - python
---

# Main Orchestrator

Central coordination skill for the AI Employee. Processes tasks from `Needs_Action/` via a priority queue, runs cron-scheduled jobs (briefings, audits, health checks), and routes tasks to Claude CLI for reasoning or to downstream skills for execution.

## Quick Start

```bash
# 1. Show current status
uv run main_orchestrator.py --status

# 2. Single orchestration cycle
uv run main_orchestrator.py --once

# 3. Continuous orchestration
uv run main_orchestrator.py --run

# 4. Show task queue
uv run main_orchestrator.py --queue

# 5. Show schedules
uv run main_orchestrator.py --schedules
```

## Architecture

```
                    ┌─────────────────────────┐
                    │    Main Orchestrator     │
                    └────────┬────────────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
    ┌──────────────┐ ┌─────────────┐ ┌──────────────┐
    │  Scheduler   │ │ Task Queue  │ │  Dashboard   │
    │  (cron jobs) │ │ (priority)  │ │  (status)    │
    └──────┬───────┘ └──────┬──────┘ └──────────────┘
           │                │
           ▼                ▼
    ┌──────────────┐ ┌─────────────────────────────┐
    │  subprocess  │ │        Task Router           │
    │  (uv run ..) │ │                              │
    └──────────────┘ │  ALERT_*  → Claude CLI       │
                     │  EMAIL_*  → Claude CLI       │
                     │  WHATSAPP_* → Claude CLI     │
                     │  EXECUTE_* → mark complete   │
                     │  SEND_*   → mark complete    │
                     │  POST_*   → mark complete    │
                     │  NOTIFY_* → log & complete   │
                     │  Default  → Claude CLI       │
                     └─────────────────────────────┘
```

## File Structure

```
main-orchestrator/
├── main_orchestrator.py       # Main UV-runnable script
├── task_queue.py              # Priority queue for Needs_Action/ files
├── scheduler.py               # Cron-based scheduled task runner
├── config.yaml                # Configuration (processes, schedules, etc.)
├── requirements.txt
└── SKILL.md
```

## Task Priority Queue

Tasks in `Needs_Action/` are classified by filename prefix:

| Priority | Prefix | Type | Description |
|----------|--------|------|-------------|
| 0 | `ALERT_*` | Alert | Health alerts, critical notifications |
| 1 | `WHATSAPP_*` | WhatsApp | Incoming WhatsApp messages |
| 2 | `EMAIL_*` | Email | Incoming email events |
| 3 | `FILE_*` | File | Filesystem watcher events |
| 4 | `EXECUTE_*`, `SEND_*`, `POST_*` | Task | Action execution requests |
| 5 | `NOTIFY_*` | Notify | Informational notifications |
| 99 | (other) | Default | Unclassified tasks |

**Processing cycle:**
1. Scan `Needs_Action/` for `.md` files
2. Classify by filename prefix (fast) or YAML frontmatter type (fallback)
3. Sort by priority (lower = higher priority)
4. Process up to `max_concurrent` (default: 3) per cycle
5. Claim → Route → Complete/Fail

**Task lifecycle:**
```
Needs_Action/task.md
  → claim → In_Progress/main-orchestrator/task.md
    → route → handler (Claude CLI / subprocess)
      → complete → Done/task.md
      → fail    → error/task.md (with failure annotation)
```

## Task Routing

| Prefix | Handler | Description |
|--------|---------|-------------|
| `ALERT_*` | Claude CLI | Urgent analysis with root cause + recommendations |
| `EMAIL_*` | Claude CLI | Reasoning: priority, action type, draft response |
| `WHATSAPP_*` | Claude CLI | Reasoning: priority, action type, draft response |
| `EXECUTE_PAYMENT_*` | Mark complete | Downstream payment-handler-mcp picks up |
| `SEND_EMAIL_*` | Mark complete | Downstream email-sender-mcp picks up |
| `POST_SOCIAL_*` | Mark complete | Downstream social-poster-mcp picks up |
| `SEND_INVOICE_*` | Mark complete | Downstream invoice-generator picks up |
| `NOTIFY_*` | Log only | Informational, no action needed |
| Default | Claude CLI | Generic task processing |

**Claude CLI invocation:**
```bash
claude -p "Analyze this EMAIL event and create an action plan: ..."
```

Response is saved as `plans/PLAN_{task}_{timestamp}.md` with YAML frontmatter.

## Cron Scheduling

Schedules from `config.yaml` are checked each cycle. Standard 5-field cron:

```
┌───────── minute (0-59)
│ ┌─────── hour (0-23)
│ │ ┌───── day of month (1-31)
│ │ │ ┌─── month (1-12)
│ │ │ │ ┌─ day of week (0-6, Mon=0)
│ │ │ │ │
* * * * *
```

**Default schedules from config.yaml:**

| Name | Cron | Description |
|------|------|-------------|
| morning-briefing | `0 8 * * *` | Morning briefing summary |
| ceo-briefing | `0 23 * * 0` | Full CEO briefing (Sunday night) |
| subscription-audit | `0 9 1 * *` | Monthly subscription audit |
| health-check | `0 */2 * * *` | Bi-hourly health check |

Supports `*` wildcard and `*/N` step syntax.

## config.yaml Reference

```yaml
vault_path: "./obsidian-vault"
dev_mode: true
dry_run: true

processes:                          # Managed by health-monitor skill
  gmail-watcher:
    command: "uv run .claude/skills/gmail-watcher/gmail_watcher.py --vault-path {vault} --monitor"
    enabled: true
  # ...

schedules:                          # Cron-scheduled jobs
  morning-briefing:
    description: "Morning briefing summary"
    cron: "0 8 * * *"
    command: "uv run .claude/skills/ceo-briefing-generator/briefing_generator.py ..."
    enabled: true
  # ...

task_processing:                    # Queue settings
  poll_interval: 10                 # Seconds between cycles
  max_concurrent: 3                 # Tasks per cycle
  priority_map:                     # Priority assignments
    ALERT: 0
    WHATSAPP: 1
    EMAIL: 2
    FILE: 3
    TASK: 4
    NOTIFY: 5

claude:                             # Claude CLI settings
  command: "claude"                 # CLI command
  timeout: 300                      # Seconds per invocation
  max_concurrent: 1                 # Concurrent Claude calls
```

## Dashboard.md Section

```markdown
## Orchestrator Status

**Mode:** DRY RUN | **Last Cycle:** 2026-02-18 10:00 UTC | **Total Cycles:** 42

| Metric | Value |
|--------|-------|
| Queue Depth | 3 |
| Tasks Processed | 128 |
| Tasks Failed | 2 |
| Schedules | 4 |
| Poll Interval | 10s |
```

## CLI Reference

```
Actions:
  --run                     Continuous orchestration loop
  --once                    Single orchestration cycle
  --status                  Show orchestrator status
  --queue                   Show current task queue
  --schedules               Show schedule status

Configuration:
  --config PATH             Config file path (default: config.yaml)
  --vault-path PATH         Override vault path from config
  --interval N              Override poll interval (seconds)
  --verbose, -v             Debug logging
```

## Vault Data Sources

| Source | Read/Write | Purpose |
|--------|------------|---------|
| `Needs_Action/*.md` | Read | Task queue source |
| `In_Progress/main-orchestrator/` | Read/Write | Claimed tasks |
| `Done/` | Write | Completed tasks |
| `error/` | Write | Failed tasks |
| `plans/PLAN_*.md` | Write | Claude response plans |
| `Dashboard.md` | Write | Orchestrator Status section |
| `Logs/orchestrator.json` | Write | Cycle event log |
| `Logs/orchestrator.log` | Write | Rotating text log |
| `config.yaml` | Read | Configuration |

## Dependencies

- Python 3.10+
- `pyyaml` — YAML config and frontmatter parsing
- `claude` CLI — for task reasoning (must be on PATH)

All declared in PEP 723 script header for automatic UV resolution.
