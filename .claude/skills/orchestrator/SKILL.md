---
name: orchestrator
description: Master orchestrator skill for the AI Employee. Coordinates the Perception → Reasoning → Action pipeline, manages watchers, and runs the main event loop.
---

# Orchestrator Skill

Master coordinator for the AI Employee's Perception → Reasoning → Action pipeline.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Orchestrator                    │
├─────────────┬──────────────┬───────────────────┤
│ PERCEPTION  │  REASONING   │     ACTION         │
│             │              │                    │
│ Gmail       │ Claude API   │ MCP Server         │
│ LinkedIn    │ Plan.md      │ Email Send         │
│ WhatsApp    │ Generation   │ LinkedIn Post      │
│ (Watchers)  │              │ WhatsApp Reply     │
├─────────────┴──────────────┴───────────────────┤
│           APPROVAL GATE (Human-in-the-Loop)     │
└─────────────────────────────────────────────────┘
```

## Key Files

| File | Purpose |
|------|---------|
| `agent-skills/orchestrator.py` | Main orchestrator script |
| `agent-skills/scheduler/task_scheduler.py` | APScheduler integration |
| `obsidian-vault/config/watchers.yaml` | Watcher configuration |
| `obsidian-vault/config/schedules.yaml` | Schedule configuration |

## Running the Orchestrator

```bash
# Full run with all watchers
python agent-skills/orchestrator.py --vault ./obsidian-vault

# Mock mode (no real API calls)
python agent-skills/orchestrator.py --vault ./obsidian-vault --mock

# Single cycle then exit
python agent-skills/orchestrator.py --vault ./obsidian-vault --once

# Custom polling interval
python agent-skills/orchestrator.py --vault ./obsidian-vault --interval 120

# Check status only
python agent-skills/orchestrator.py --status
```

## Pipeline Cycle

Each cycle:
1. **Load environment**: Read `.env` and `dashboard/.env.local`
2. **Poll watchers**: Gmail, LinkedIn, WhatsApp (in parallel)
3. **Process events**: New inbox files → reasoning loop
4. **Check approvals**: Poll Approved/Rejected folders
5. **Execute actions**: Run approved actions via MCP server
6. **Cleanup**: Archive expired approvals, log metrics
7. **Sleep**: Wait for next cycle interval

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `DEV_MODE` | Extra safety checks | `true` |
| `DRY_RUN` | Log but don't execute | `true` |
| `ANTHROPIC_API_KEY` | Claude API key | Required |
| `GMAIL_CHECK_INTERVAL` | Gmail poll seconds | `300` |
| `LINKEDIN_CHECK_INTERVAL` | LinkedIn poll seconds | `900` |
| `WHATSAPP_CHECK_INTERVAL` | WhatsApp poll seconds | `30` |

## Safety Flags

### DEV_MODE (default: true)
- Extra input validation
- Verbose logging
- Shorter expiry windows

### DRY_RUN (default: true)
- Logs all proposed actions
- Does NOT execute external API calls
- Perfect for testing the full pipeline

## Graceful Shutdown

Handles SIGINT/SIGTERM:
1. Set `running = False`
2. Wait for current cycle to finish
3. Save watcher state
4. Close browser sessions (WhatsApp)
5. Log shutdown event

## Error Recovery

- Watcher crash → log error, continue other watchers
- Claude API failure → skip reasoning, retry next cycle
- MCP server error → keep approval, retry execution
- Vault disk full → alert, pause processing
