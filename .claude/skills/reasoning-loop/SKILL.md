---
name: reasoning-loop
description: Claude-powered reasoning loop skill for the AI Employee. Analyzes incoming events, generates Plan.md files with recommended actions, and routes to approval workflow.
---

# Reasoning Loop Skill

Analyzes inbox events using Claude and generates structured Plan.md files with recommended actions.

## Architecture

```
Perception (Watchers) → Reasoning (Claude API) → Action (Approval → MCP)
                              ↓
                    obsidian-vault/plans/Plan_<id>.md
```

- **Reasoning phase** of the Perception → Reasoning → Action pipeline
- Reads event files from vault inbox
- Generates Plan.md with context, analysis, and action checkboxes
- Routes sensitive actions through approval workflow

## Key Files

| File | Purpose |
|------|---------|
| `agent-skills/core/reasoning_loop.py` | Main reasoning orchestrator |
| `agent-skills/skills/reasoning_skill.py` | Claude reasoning integration |
| `agent-skills/skills/planning_skill.py` | Plan generation and annotation |
| `agent-skills/core/plan_writer.py` | Plan.md file writer |
| `agent-skills/models/plan.py` | Plan data model |
| `dashboard/src/app/plans/page.tsx` | Plans dashboard view |

## Reasoning Flow

1. **Pick up events**: Read new event files from `obsidian-vault/inbox/`
2. **Move to processing**: Move event to `processing/` folder
3. **Analyze with Claude**: Send event context to Claude API
4. **Generate plan**: Create Plan.md with recommended actions
5. **Annotate sensitivity**: Mark actions as safe or requiring approval
6. **Create approvals**: Generate APPROVAL_REQUIRED files for sensitive actions
7. **Move event**: Move to `completed/` after plan creation

## Plan.md Format

```markdown
---
id: <deterministic-hash>
title: Process email from sender@example.com
status: pending
risk_level: medium
created_at: 2026-02-08T14:30:00Z
source_events:
  - EMAIL_20260208_143022_abc123.md
---

# Plan: Process Email

## Objective
Respond to email from sender about meeting tomorrow.

## Actions

### Action 1: draft_response
- **ID**: action_0_abc12345
- **Description**: Draft reply confirming meeting attendance
- **APPROVAL REQUIRED**: This action requires human approval

## Required Approvals
- action_0_abc12345

## Expected Outcome
Email is responded to with meeting confirmation.
```

## Claude Integration

```python
# System prompt for reasoning:
"You are an AI assistant analyzing incoming events for a business.
Given the event data, determine:
1. What is happening (summary)
2. What actions should be taken
3. Which actions require human approval
4. Expected outcome"
```

## Deterministic Behavior

Plans are deterministic: same input → same plan ID (via SHA-256 hash of input).
This enables:
- Testing with predictable outputs
- Deduplication of identical events
- Audit trail consistency

## Event Grouping

Related events can be grouped into a single plan:
- Multiple emails in same thread → one plan
- Related LinkedIn + email events → one plan
- Time-windowed events (within 5 min) from same source → one plan

## Plan Types

| Type | When |
|------|------|
| `action_plan` | Normal event → actions |
| `request_clarification` | Ambiguous event → ask human |
| `information_only` | FYI event → log only |

## Error Handling

- Claude API timeout → retry with exponential backoff (max 3 retries)
- Invalid event data → move to `error/` folder
- Rate limit → queue for later processing
- Network error → keep in `processing/`, retry next cycle
