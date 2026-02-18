---
name: approval-manager
description: Unified HITL approval workflow orchestrator. Monitors pending-approval/, processes approved/rejected actions via per-type handlers, handles expiration, notifications, bulk operations, delegation, and generates reports.
tools: []
tags:
  - approval
  - hitl
  - workflow
  - python
  - monitoring
---

# Approval Manager

Unified orchestrator for all Human-in-the-Loop (HITL) approval workflows. Centralizes monitoring of `pending-approval/`, `Approved/`, and `Rejected/` folders, routes approved actions to per-type handlers, handles expiration, sends notifications, and generates reports.

## Quick Start

```bash
# List pending approvals
uv run approval_manager.py --vault-path ../../obsidian-vault --pending

# Single poll cycle (check all folders, process, update dashboard)
uv run approval_manager.py --vault-path ../../obsidian-vault --once

# Continuous monitoring
uv run approval_manager.py --vault-path ../../obsidian-vault --monitor
```

## Architecture

```
approval-manager/
├── approval_manager.py            # Main UV-runnable script (orchestrator)
├── approval_handlers/
│   ├── __init__.py                # Handler registry
│   ├── payment_handler.py         # Routes approved payments
│   ├── email_handler.py           # Routes approved emails
│   ├── social_handler.py          # Routes approved social posts
│   └── invoice_handler.py         # Routes approved invoices
├── notification_sender.py         # Notification file creator
├── requirements.txt
└── SKILL.md
```

## Approval Workflow

```
1. ANY SKILL creates APPROVAL_REQUIRED_*.md in pending-approval/
          |
          v
2. APPROVAL MANAGER detects it:
   - Logs to approval_history.json
   - Creates notification in Needs_Action/
   - Updates Dashboard.md
          |
          v
3. EXPIRY CHECK (each poll cycle):
   - Sends "expiring soon" at <4h remaining
   - Auto-expires at 0h -> moves to Rejected/
          |
          v
4. HUMAN DECISION:
   a) Move to Approved/ -> Manager routes to handler -> action file in Needs_Action/ -> archive to Done/
   b) Move to Rejected/ -> Manager logs reason -> archive to Done/
          |
          v
5. REPORT: --report generates summary with approval rates, response times
```

## Approval File Format (standardized)

```yaml
---
type: approval_request
id: "uuid-or-short-hash"
action_type: payment|email_send|social_post|send_invoice
status: pending
created: 2026-02-17T10:00:00Z
expires: 2026-02-18T10:00:00Z
risk_level: low|medium|high
# action-specific fields...
---

# Approval Required: [description]

[Human-readable details]
```

## Handler Routing

| Action Type | Handler | Output |
|-------------|---------|--------|
| `payment`, `payment_transfer` | PaymentHandler | `Needs_Action/EXECUTE_PAYMENT_*.md` |
| `email_send`, `email`, `email_reply` | EmailHandler | `Needs_Action/SEND_EMAIL_*.md` |
| `social_post`, `linkedin_post`, `facebook_post`, `twitter_post` | SocialHandler | `Needs_Action/POST_SOCIAL_*.md` |
| `send_invoice`, `invoice` | InvoiceHandler | `Needs_Action/SEND_INVOICE_*.md` |

Handlers create action files for downstream MCP skills to pick up (loose coupling).

## CLI Reference

```
Monitoring:
  --monitor                     Continuous poll loop (Ctrl+C to stop)
  --once                        Single poll cycle
  --poll-interval N             Seconds between polls (default: 30)

Listing:
  --pending                     List all pending approvals with expiry status
  --history                     Show approval history
  --history --type payment      Filter history by action type
  --history --status approved   Filter by status (approved|rejected|expired)

Actions:
  --approve ID [ID ...]         Bulk approve by ID(s)
  --reject ID --reason TEXT     Reject by ID with reason
  --delegate ID --to NAME       Delegate approval to another person
  --expire-check                Check and process expired approvals

Reporting:
  --report [week|month|all]     Generate summary report
  --notify                      Send notification digest for all pending

Common:
  --vault-path PATH             Obsidian vault path (default: ./obsidian-vault)
  --verbose, -v                 Debug logging
```

## Notification Types

| Type | Trigger | Priority |
|------|---------|----------|
| `NOTIFY_APPROVAL_PENDING_*` | New approval request detected | normal (high if risk=high) |
| `NOTIFY_APPROVAL_EXPIRING_*` | Approval <4h from expiry | high |
| `NOTIFY_APPROVAL_EXPIRED_*` | Approval expired without decision | normal |
| `NOTIFY_APPROVAL_DIGEST_*` | Manual digest via --notify | depends on content |

All notifications are deduplicated via `Logs/approval_notifications.json`.

## Delegation

Delegate an approval to another person:

```bash
uv run approval_manager.py --vault-path ../../obsidian-vault \
  --delegate abc123 --to "manager@company.com"
```

Adds `delegated_to` field to the approval file frontmatter and creates a notification for the delegate.

## Bulk Operations

Safely approve or reject multiple approvals at once:

```bash
# Approve multiple
uv run approval_manager.py --vault-path ../../obsidian-vault \
  --approve abc123 def456 ghi789

# Reject with reason
uv run approval_manager.py --vault-path ../../obsidian-vault \
  --reject abc123 --reason "Budget not approved for this quarter"
```

Each approval is logged individually even in bulk operations.

## Dashboard Integration

Updates `vault/Dashboard.md` with:

```markdown
## Approval Manager Status

| Metric | Value |
|--------|-------|
| Pending Approvals | 3 |
| Expiring Soon (<4h) | 1 |
| Last Updated | 2026-02-17 15:30 UTC |

### Recent Decisions

- `2026-02-17 14:22` executed: abc123
- `2026-02-17 13:15` rejected: def456
```

## Reports

Generate approval summary reports:

```bash
uv run approval_manager.py --vault-path ../../obsidian-vault --report week
```

Reports include:
- Total decisions, approval/rejection/expiry counts
- Approval rate percentage
- Breakdown by action type
- Recent activity log

Output: `Reports/Approval_Summary_{date}.md`

## Vault Data Sources

| Source | Read/Write | Purpose |
|--------|------------|---------|
| `pending-approval/` | Read | Detect new approval requests |
| `Approved/` | Read | Detect approved files |
| `Rejected/` | Read/Write | Detect rejected files; write expired |
| `Done/` | Write | Archive processed approvals |
| `Needs_Action/` | Write | Action files for handlers + notifications |
| `Logs/approval_history.json` | Read/Write | Event log |
| `Logs/approval_notifications.json` | Read/Write | Notification dedup |
| `Reports/` | Write | Summary reports |
| `Dashboard.md` | Write | Status section |

## Dependencies

- Python 3.10+
- `jinja2` — template rendering
- `python-dotenv` — .env loading
- `pyyaml` — YAML frontmatter parsing

All declared in PEP 723 script header for automatic UV resolution.
