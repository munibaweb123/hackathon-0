# Data Model: Silver Tier — Functional Assistant

**Branch**: `003-silver-tier-assistant` | **Date**: 2026-02-08 | **Plan**: [plan.md](./plan.md)

## Entity Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           SILVER TIER DATA MODEL                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────┐     creates     ┌─────────┐     generates    ┌─────────┐  │
│  │ Watcher │───────────────▶│  Event  │────────────────▶│  Plan   │  │
│  └─────────┘                 └─────────┘                  └─────────┘  │
│       │                           │                            │       │
│       │                           │                            │       │
│       ▼                           ▼                            ▼       │
│  ┌─────────┐               ┌─────────────┐              ┌──────────┐  │
│  │Schedule │               │  Approval   │◀─────────────│  Action  │  │
│  └─────────┘               │  Request    │   requires   └──────────┘  │
│                            └─────────────┘                     │       │
│                                   │                            │       │
│                                   │ authorizes                 │       │
│                                   ▼                            ▼       │
│                            ┌─────────────┐              ┌──────────┐  │
│                            │ MCP Action  │──────────────│   Post   │  │
│                            │   Result    │   produces   └──────────┘  │
│                            └─────────────┘                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Watcher

A background service that monitors an external platform and produces structured event files.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier (e.g., `gmail_watcher`, `linkedin_watcher`) |
| `type` | enum | Yes | `gmail` \| `linkedin` \| `whatsapp` |
| `status` | enum | Yes | `active` \| `paused` \| `error` \| `auth_required` |
| `polling_interval` | integer | Yes | Seconds between polls (default: 300 for 5 min) |
| `last_check_timestamp` | datetime | No | Last successful poll time |
| `last_history_id` | string | No | Gmail history ID / LinkedIn sync token |
| `auth_state` | object | No | OAuth token metadata (expiry, refresh status) |
| `error_message` | string | No | Last error if status is `error` |
| `created_at` | datetime | Yes | Watcher creation timestamp |
| `updated_at` | datetime | Yes | Last status update timestamp |

### State Transitions

```
                    ┌─────────────────┐
                    │   auth_required │◀──── OAuth expired
                    └────────┬────────┘
                             │
                    user authenticates
                             │
                             ▼
┌───────┐  start   ┌────────────────┐  pause   ┌────────┐
│ init  │─────────▶│     active     │◀─────────│ paused │
└───────┘          └───────┬────────┘          └────────┘
                           │                        ▲
                      error detected                │
                           │                   user resumes
                           ▼                        │
                    ┌─────────────┐                 │
                    │    error    │─────────────────┘
                    └─────────────┘   auto-recover
```

### Validation Rules

- `polling_interval` must be >= 30 seconds
- `type` must be one of the defined enum values
- `auth_state` must contain valid token if status is `active`

---

## 2. Event

A structured record of external activity captured by a watcher.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier (UUID v4) |
| `source_type` | enum | Yes | `gmail` \| `linkedin` \| `whatsapp` |
| `source_id` | string | No | External ID (Gmail message ID, etc.) |
| `event_type` | enum | Yes | `email_received` \| `linkedin_notification` \| `linkedin_message` \| `whatsapp_message` |
| `timestamp` | datetime | Yes | When the external event occurred |
| `detected_at` | datetime | Yes | When the watcher detected it |
| `priority` | enum | Yes | `low` \| `medium` \| `high` \| `urgent` |
| `processing_status` | enum | Yes | `new` \| `processing` \| `plan_generated` \| `archived` |
| `raw_data` | object | Yes | Original event data (JSON) |
| `normalized_data` | object | Yes | Standardized event representation |
| `file_path` | string | Yes | Vault path where event file is stored |
| `plan_id` | string | No | ID of generated Plan if applicable |

### File Naming Convention

```
inbox/
├── EMAIL_2026-02-08_143052_abc123.md      # Gmail event
├── LINKEDIN_2026-02-08_150000_def456.md   # LinkedIn event
└── WHATSAPP_2026-02-08_151530_ghi789.md   # WhatsApp event
```

### Normalized Data Schema

```typescript
interface NormalizedEvent {
  summary: string;          // One-line summary
  sender: {
    name: string;
    identifier: string;     // Email, LinkedIn ID, phone number
  };
  content: {
    subject?: string;       // Email subject, or message preview
    body: string;           // Full text content
    attachments?: string[]; // Attachment names if any
  };
  metadata: {
    thread_id?: string;     // For conversation threading
    is_reply: boolean;
    urgency_indicators: string[]; // Keywords suggesting urgency
  };
}
```

### Validation Rules

- `timestamp` must not be in the future
- `detected_at` must be >= `timestamp`
- `raw_data` must be valid JSON
- `file_path` must start with `inbox/`

---

## 3. Plan

A Plan.md file generated by the Claude reasoning loop with recommended actions.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier (UUID v4) |
| `title` | string | Yes | Brief plan title |
| `created_at` | datetime | Yes | Plan generation timestamp |
| `source_events` | string[] | Yes | IDs of events that triggered this plan |
| `context` | string | Yes | Background and situation analysis |
| `analysis` | string | Yes | Claude's reasoning about the events |
| `recommended_actions` | Action[] | Yes | List of proposed actions |
| `status` | enum | Yes | `draft` \| `pending_approval` \| `partially_approved` \| `approved` \| `rejected` \| `executed` |
| `risk_level` | enum | Yes | `low` \| `medium` \| `high` |
| `file_path` | string | Yes | Vault path where Plan.md is stored |
| `expires_at` | datetime | No | When plan becomes stale |

### Plan.md File Format

```markdown
# Plan: [title]

**ID**: [id]
**Created**: [created_at]
**Risk Level**: [risk_level]
**Status**: [status]
**Source Events**: [comma-separated event IDs]

## Context

[Background information and situation summary]

## Analysis

[Claude's reasoning about what happened and what it means]

## Recommended Actions

- [ ] **Action 1**: [description]
  - Type: [action_type]
  - Risk: [risk_level]
  - Approval Required: Yes/No

- [ ] **Action 2**: [description]
  - Type: [action_type]
  - Risk: [risk_level]
  - Approval Required: Yes/No

## Expected Outcome

[What will happen if actions are approved and executed]

---
_Generated by Claude Reasoning Loop at [timestamp]_
```

### Validation Rules

- Must have at least one `recommended_action`
- `source_events` must contain valid event IDs
- `expires_at` (if set) must be in the future

---

## 4. Approval Request

A structured markdown file requesting human authorization for an action.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier (UUID v4) |
| `plan_id` | string | Yes | Parent plan ID |
| `action_type` | enum | Yes | `email_send` \| `linkedin_post` \| `whatsapp_reply` \| `escalate` |
| `description` | string | Yes | Human-readable action description |
| `context` | string | Yes | Why this action is proposed |
| `risk_level` | enum | Yes | `low` \| `medium` \| `high` |
| `proposed_content` | string | No | Draft content if applicable (email body, post text) |
| `status` | enum | Yes | `pending` \| `approved` \| `rejected` \| `expired` |
| `created_at` | datetime | Yes | Request creation timestamp |
| `decided_at` | datetime | No | When human made decision |
| `decided_by` | string | No | Operator who approved/rejected |
| `rejection_reason` | string | No | Why rejected (if status is `rejected`) |
| `expires_at` | datetime | Yes | When approval expires (24h default) |
| `file_path` | string | Yes | Vault path to approval file |

### File Naming Convention

```
pending-approval/
└── APPROVAL_REQUIRED_linkedin_post_abc123.md

# When approved, moved to:
Approved/
└── APPROVAL_REQUIRED_linkedin_post_abc123.md

# When rejected, moved to:
Rejected/
└── APPROVAL_REQUIRED_linkedin_post_abc123.md
```

### Approval File Format

```markdown
# Approval Request: [action_type]

**ID**: [id]
**Plan**: [plan_id]
**Created**: [created_at]
**Expires**: [expires_at]
**Risk Level**: 🟢 Low / 🟡 Medium / 🔴 High

## Proposed Action

**Type**: [action_type]
**Description**: [description]

## Context

[Why this action is recommended]

## Proposed Content

```
[proposed_content if applicable]
```

## Decision

**Status**: ⏳ Pending / ✅ Approved / ❌ Rejected

To approve: Move this file to the `/Approved` folder
To reject: Move this file to the `/Rejected` folder

---
_Requires human approval before execution_
```

### State Transitions

```
┌─────────┐
│ pending │
└────┬────┘
     │
     ├──────────────────────────────────────┐
     │                                      │
     ▼                                      ▼
┌──────────┐                         ┌──────────┐
│ approved │──────────┐              │ rejected │
└──────────┘          │              └──────────┘
     │                │
     │                │  24h timeout
     ▼                │
┌──────────┐          │
│ executed │          │
└──────────┘          │
                      ▼
               ┌──────────┐
               │ expired  │
               └──────────┘
```

### Validation Rules

- `expires_at` must be in the future when status is `pending`
- `decided_at` must be set if status is `approved` or `rejected`
- `rejection_reason` must be set if status is `rejected`

---

## 5. Agent Skill

A modular capability unit following a common interface.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier (e.g., `reasoning_skill`) |
| `name` | string | Yes | Human-readable name |
| `version` | string | Yes | Semantic version |
| `description` | string | Yes | What this skill does |
| `input_schema` | object | Yes | JSON Schema for input validation |
| `output_schema` | object | Yes | JSON Schema for output validation |
| `dependencies` | string[] | No | Other skills this skill requires |
| `enabled` | boolean | Yes | Whether skill is active |
| `config` | object | No | Skill-specific configuration |

### Skill Interface

```python
from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseSkill(ABC):
    @property
    @abstractmethod
    def id(self) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def input_schema(self) -> dict: ...

    @property
    @abstractmethod
    def output_schema(self) -> dict: ...

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the skill with validated input, return validated output."""
        pass

    def validate_input(self, data: dict) -> bool:
        """Validate input against input_schema."""
        pass

    def validate_output(self, data: dict) -> bool:
        """Validate output against output_schema."""
        pass
```

### Silver Tier Skills

| Skill ID | Name | Input | Output |
|----------|------|-------|--------|
| `reasoning_skill` | Reasoning | Event data | Analysis + recommendations |
| `planning_skill` | Planning | Analysis | Plan.md structure |
| `communication_skill` | Communication | Plan + context | Draft content |
| `execution_skill` | Execution | Approved action | Execution result |
| `linkedin_content_skill` | LinkedIn Content | Business context | Post draft |
| `event_triage_skill` | Event Triage | Raw event | Priority + routing |
| `approval_monitor_skill` | Approval Monitor | Approval folder | Status changes |

---

## 6. Schedule

A configuration defining when tasks execute.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier |
| `task_type` | enum | Yes | `watcher_poll` \| `content_generation` \| `cleanup` \| `health_check` |
| `target_id` | string | No | Watcher ID or skill ID if applicable |
| `schedule_type` | enum | Yes | `interval` \| `cron` |
| `interval_seconds` | integer | Cond. | Required if `schedule_type` is `interval` |
| `cron_expression` | string | Cond. | Required if `schedule_type` is `cron` |
| `enabled` | boolean | Yes | Whether schedule is active |
| `last_run` | datetime | No | Last execution timestamp |
| `next_run` | datetime | No | Calculated next execution |
| `created_at` | datetime | Yes | Schedule creation timestamp |

### Default Schedules

| Task | Type | Expression | Description |
|------|------|------------|-------------|
| Gmail poll | interval | 300s | Check Gmail every 5 minutes |
| LinkedIn poll | interval | 900s | Check LinkedIn every 15 minutes |
| WhatsApp poll | interval | 30s | Check WhatsApp every 30 seconds |
| Daily post | cron | `0 9 * * *` | Generate LinkedIn post at 9 AM |
| Stale approval check | interval | 3600s | Check for 24h+ pending approvals |
| Health check | interval | 60s | Verify all watchers healthy |

### Validation Rules

- `interval_seconds` must be >= 30 if set
- `cron_expression` must be valid cron syntax
- One of `interval_seconds` or `cron_expression` must be set

---

## 7. Post

A LinkedIn content item created by the system.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Internal unique identifier (UUID v4) |
| `linkedin_post_id` | string | No | LinkedIn's post URN after publishing |
| `content` | string | Yes | Post text content |
| `status` | enum | Yes | `draft` \| `pending_approval` \| `approved` \| `published` \| `failed` |
| `created_at` | datetime | Yes | Draft creation timestamp |
| `approved_at` | datetime | No | Approval timestamp |
| `published_at` | datetime | No | Publication timestamp |
| `approval_id` | string | No | Related approval request ID |
| `generation_context` | object | No | Business context used for generation |
| `error_message` | string | No | Error details if status is `failed` |
| `metrics` | object | No | Engagement metrics after publishing |

### State Transitions

```
┌───────┐
│ draft │
└───┬───┘
    │
    ▼
┌──────────────────┐
│ pending_approval │
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐  ┌──────────┐
│approved│  │(rejected)│ → deleted or archived
└───┬────┘  └──────────┘
    │
    ▼
┌───────────┐
│ published │──────┐
└───────────┘      │
                   │ API error
                   ▼
               ┌────────┐
               │ failed │
               └────────┘
```

### Validation Rules

- `content` must be 1-3000 characters (LinkedIn limit)
- `published_at` must be set if status is `published`
- `linkedin_post_id` must be set if status is `published`

---

## Entity Relationships

```
Watcher (1) ──────creates────────▶ (n) Event
Event (n) ◀──────source_events───── (1) Plan
Plan (1) ──────recommended_actions──▶ (n) Action
Action (1) ──────requires──────────▶ (1) Approval Request
Approval Request (1) ──authorizes──▶ (1) MCP Action Result
MCP Action Result (1) ──produces───▶ (0..1) Post
Schedule (1) ──────triggers────────▶ (n) Watcher
Schedule (1) ──────triggers────────▶ (n) Post (generation)
Agent Skill (n) ◀────────────────── (1) Plan (uses)
```

---

## File-Based Storage Mapping

All entities are stored as files in the Obsidian vault:

| Entity | Storage Location | Format |
|--------|------------------|--------|
| Watcher | `config/watchers.yaml` | YAML config file |
| Event | `inbox/[TYPE]_[timestamp]_[id].md` | Markdown with YAML frontmatter |
| Plan | `plans/PLAN_[timestamp]_[id].md` | Markdown (Plan.md format) |
| Approval Request | `pending-approval/APPROVAL_REQUIRED_[action]_[id].md` | Markdown |
| Schedule | `config/schedules.yaml` | YAML config file |
| Post | `posts/POST_[timestamp]_[id].md` | Markdown with YAML frontmatter |
| Audit Log | `logs/audit_[date].jsonl` | JSON Lines |
