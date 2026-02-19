# Data Model: Platinum Tier AI Employee

**Feature**: 005-platinum-tier-ai-employee
**Date**: 2026-02-18
**Storage**: File-based (Obsidian vault — YAML frontmatter + Markdown body)

## Entities

### Agent

Represents a running agent instance (cloud or local).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| agent-id | string | yes | Unique identifier (e.g., `cloud-001`, `local-001`) |
| zone | enum | yes | `cloud` or `local` |
| status | enum | yes | `running`, `stopped`, `degraded` |
| started-at | ISO 8601 datetime | yes | When the agent was started |
| last-heartbeat | ISO 8601 datetime | yes | Last heartbeat timestamp (updated every sync cycle) |
| capabilities | string[] | yes | List of skill names this agent can run |
| sync-interval | integer | yes | Vault sync interval in seconds (default: 300) |
| version | string | yes | Agent software version |

**File location**: `Signals/agents/{agent-id}.yaml`
**Writer**: The agent itself (each agent writes its own identity file)
**Lifecycle**: Created on startup → updated every sync cycle → removed on clean shutdown

### Draft

A proposed action created by the cloud agent awaiting CEO approval.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| draft-id | string | yes | Unique ID: `draft-{type}-{date}-{seq}` |
| type | enum | yes | `email-reply`, `social-post`, `payment`, `briefing` |
| priority | enum | yes | `high`, `medium`, `low` |
| created-at | ISO 8601 datetime | yes | Creation timestamp |
| expires-at | ISO 8601 datetime | yes | created-at + 48 hours |
| status | enum | yes | `pending`, `approved`, `rejected`, `expired` |
| source | object | conditional | Source context (email-id, from, subject for emails; calendar-entry for social; invoice-id for payments) |
| context | object | no | Handbook references, contact history, reasoning |
| content | markdown body | yes | The actual draft content (reply text, post text, payment instructions, briefing) |

**File location**: `Drafts/{type}/{draft-id}.md` (YAML frontmatter + Markdown body)
**Writer**: Cloud agent only
**Lifecycle**: Created (pending) → Approved/Rejected by local agent → Moved to `Done/` or `Done/expired/`

**State transitions**:
```
pending → approved    (local agent moves to Approved/)
pending → rejected    (local agent moves to Done/ with rejection feedback)
pending → expired     (cloud agent moves to Done/expired/ after 48h)
```

### Approval

A decision record created by the local agent when reviewing a draft.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| approval-id | string | yes | Unique ID: `approval-{date}-{seq}` |
| draft-id | string | yes | Reference to the draft being approved/rejected |
| decision | enum | yes | `approved`, `rejected` |
| feedback | string | no | CEO feedback/edits (required for rejections) |
| decided-at | ISO 8601 datetime | yes | When the decision was made |
| decided-by | string | yes | CEO identifier |
| edits | object | no | Any modifications made to the draft content before approval |

**File location**: `Approved/{approval-id}.md` or `Done/{approval-id}.md`
**Writer**: Local agent only
**Lifecycle**: Created on decision → execution attempted → moved to Done/

### Lead

A potential business opportunity extracted from incoming email.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| lead-id | string | yes | Unique ID: `lead-{date}-{seq}` |
| source-email | string | yes | Original email message ID |
| company | string | yes | Extracted company name |
| contact | object | yes | `{name, email, phone?}` |
| request-type | enum | yes | `inquiry`, `rfp`, `partnership`, `support`, `other` |
| urgency | enum | yes | `high`, `medium`, `low` |
| summary | string | yes | Brief summary of the request |
| status | enum | yes | `new`, `reviewed`, `contacted`, `qualified`, `closed` |
| created-at | ISO 8601 datetime | yes | When the lead was captured |

**File location**: `Needs_Action/cloud/leads/{lead-id}.md`
**Writer**: Cloud agent creates; local agent updates status
**Lifecycle**: new → reviewed (local agent reads) → contacted → qualified/closed

### SyncEvent

A record of vault synchronization activity.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| sync-id | string | yes | Unique ID: `sync-{agent-id}-{timestamp}` |
| agent-id | string | yes | Which agent initiated the sync |
| direction | enum | yes | `push`, `pull`, `both` |
| trigger | enum | yes | `scheduled-poll`, `manual`, `startup` |
| files-changed | integer | yes | Number of files modified |
| files-added | integer | yes | Number of new files |
| files-deleted | integer | yes | Number of deleted files |
| conflicts-detected | integer | yes | Number of merge conflicts encountered |
| conflicts-resolved | integer | yes | Number of conflicts auto-resolved |
| conflicts-flagged | integer | yes | Number of conflicts requiring manual intervention |
| started-at | ISO 8601 datetime | yes | Sync start time |
| completed-at | ISO 8601 datetime | yes | Sync completion time |
| duration-ms | integer | yes | Duration in milliseconds |
| status | enum | yes | `success`, `partial`, `failed` |
| error | string | no | Error message if failed |

**File location**: `Logs/sync/{sync-id}.json` (JSON, not Markdown — high-volume append log)
**Writer**: The agent running the sync
**Lifecycle**: Created on sync completion, rotated/archived monthly

### HealthCheck

A system health snapshot from the health monitor.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| check-id | string | yes | Unique ID: `health-{agent-id}-{timestamp}` |
| agent-id | string | yes | Which agent performed the check |
| service-name | string | yes | Service being checked (e.g., `gmail-watcher`, `vault-sync`) |
| status | enum | yes | `healthy`, `degraded`, `down` |
| cpu-percent | float | no | CPU usage percentage |
| memory-mb | float | no | Memory usage in MB |
| disk-percent | float | no | Disk usage percentage |
| api-reachable | boolean | no | Whether the external API is reachable |
| last-success | ISO 8601 datetime | no | Last successful operation time |
| action-taken | string | no | What recovery action was taken (e.g., `restarted`, `alert-created`) |
| timestamp | ISO 8601 datetime | yes | When the check was performed |

**File location**: `Signals/health/{check-id}.yaml` (alerts only; routine checks go to `Logs/health/`)
**Writer**: Health monitor on each agent
**Lifecycle**: Alert files persist until acknowledged; routine log entries are rotated

### AuditEntry

A tamper-evident record of agent actions (extends existing Gold Tier audit logger).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| entry-id | string | yes | Sequential audit entry ID |
| agent-id | string | yes | Which agent performed the action |
| zone | enum | yes | `cloud` or `local` |
| action | string | yes | Action performed (e.g., `draft-created`, `approval-granted`, `payment-executed`) |
| target | string | yes | What was acted on (file path, email ID, etc.) |
| timestamp | ISO 8601 datetime | yes | When the action occurred |
| details | object | no | Additional context |
| prev-hash | string | yes | SHA-256 hash of previous entry (hash chain) |
| hash | string | yes | SHA-256 hash of this entry |

**File location**: `audit/{agent-id}-audit.jsonl` (JSON Lines, one entry per line)
**Writer**: Each agent writes its own audit log
**Lifecycle**: Append-only; archived/rotated monthly; both agent logs merged for complete audit view

## Relationships

```
Agent 1──* Draft          (cloud agent creates drafts)
Agent 1──* Approval       (local agent creates approvals)
Draft 1──1 Approval       (each draft gets at most one approval)
Agent 1──* Lead           (cloud agent creates leads)
Agent 1──* SyncEvent      (each agent logs its own sync events)
Agent 1──* HealthCheck    (each agent monitors its own health)
Agent 1──* AuditEntry     (each agent writes its own audit log)
```

## Validation Rules

- `draft-id` must be globally unique across all draft types
- `expires-at` must equal `created-at` + 48 hours exactly
- `approval.draft-id` must reference an existing draft
- A draft can only transition to `approved` or `rejected` from `pending` status
- A draft can only transition to `expired` from `pending` status (not from approved/rejected)
- `prev-hash` in AuditEntry must match the `hash` of the previous entry in the same agent's log
- Agent heartbeat (`last-heartbeat`) must be within 2x the `sync-interval` to be considered alive
- Cloud agent write paths must match: `Needs_Action/cloud/**`, `Drafts/**`, `Signals/**`, `Updates/**`
- Local agent write paths must match: `Pending_Approval/local/**`, `Approved/**`, `Done/**`, `Dashboard.md`
