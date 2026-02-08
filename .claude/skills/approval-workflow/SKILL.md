---
name: approval-workflow
description: Human-in-the-loop approval workflow skill. Manages file-based approval requests where sensitive actions require human consent before execution.
---

# Approval Workflow Skill

File-based human-in-the-loop approval system. All sensitive actions MUST get human approval before execution.

## Architecture

```
Reasoning Loop → ApprovalGenerator → pending-approval/APPROVAL_REQUIRED_*.md
                                              ↓
                              Human moves to Approved/ or Rejected/
                                              ↓
                              ApprovalWatcher → ApprovalProcessor → MCP Action
```

## Key Files

| File | Purpose |
|------|---------|
| `agent-skills/core/approval_generator.py` | Creates APPROVAL_REQUIRED files |
| `agent-skills/watchers/approval_watcher.py` | Watches Approved/Rejected folders |
| `agent-skills/core/approval_validator.py` | Validates and checks expiry |
| `agent-skills/core/approval_processor.py` | Routes approved actions to handlers |
| `agent-skills/skills/approval_monitor_skill.py` | Orchestrates the full cycle |
| `dashboard/src/app/approvals/page.tsx` | Dashboard approval UI |
| `dashboard/src/app/api/approvals/[id]/route.ts` | Approve/reject API |

## Approval File Format

```markdown
---
id: <uuid>
type: approval_request
action_type: linkedin_post
plan_id: <plan-uuid>
created: 2026-02-08T14:30:00Z
expires: 2026-02-09T14:30:00Z
risk_level: medium
status: pending
---

# Approval Request: LinkedIn Post

**Risk Level**: 🟡 Medium

## Proposed Action
**Type**: linkedin_post
**Description**: Publish LinkedIn post about business insights

## Proposed Content
```
[Draft content here]
```

## Decision
**Status**: ⏳ Pending

To approve: Move this file to the `/Approved` folder
To reject: Move this file to the `/Rejected` folder
```

## Workflow Steps

1. **Create**: `ApprovalGenerator.create_approval_request()` creates file in `pending-approval/`
2. **Wait**: File sits in `pending-approval/` until human acts
3. **Decide**: Human moves file to `Approved/` or `Rejected/` (via Obsidian, file manager, or dashboard)
4. **Detect**: `ApprovalWatcher.poll()` detects the file move
5. **Process**: `ApprovalProcessor` executes (approved) or archives (rejected)
6. **Log**: Result logged to audit trail

## Risk Levels

| Level | Emoji | When to Use |
|-------|-------|------------|
| low | 🟢 | Internal logging, draft creation |
| medium | 🟡 | LinkedIn posts, email replies |
| high | 🔴 | Financial actions, bulk operations |

## Expiry Rules

- Default: 24 hours from creation
- Expired approvals → moved to `archive/`
- Dashboard shows "expiring soon" warning at < 2 hours remaining
- Expired actions are NOT executed

## Dashboard Integration

The dashboard provides approve/reject buttons that:
1. POST to `/api/approvals/[id]` with `{ decision, filename }`
2. API moves file from `pending-approval/` to `Approved/` or `Rejected/`
3. This triggers the approval watcher on next poll cycle

## Safety Rules

- NEVER auto-approve any action
- All external-facing actions require approval (email, LinkedIn, WhatsApp)
- DRY_RUN mode logs what WOULD happen without executing
- DEV_MODE adds extra safety checks
