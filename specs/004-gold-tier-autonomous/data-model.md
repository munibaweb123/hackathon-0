# Data Model: Gold Tier — Autonomous Employee

**Feature Branch**: `004-gold-tier-autonomous`
**Date**: 2026-02-08

---

## Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ XeroConnection  │       │  SocialAccount  │       │  UnifiedContact │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ tenant_id       │       │ platform        │       │ primary_email   │
│ access_token    │◄──────┤ account_id      │──────►│ created_at      │
│ refresh_token   │       │ access_token    │       │ updated_at      │
│ token_expiry    │       │ token_expiry    │       └────────┬────────┘
│ status          │       │ follower_count  │                │
│ last_sync       │       │ status          │                │ 1:N
└─────────────────┘       │ last_sync       │                │
                          └─────────────────┘       ┌────────▼────────┐
                                                    │ PlatformIdentity│
┌─────────────────┐       ┌─────────────────┐       ├─────────────────┤
│   CEOBriefing   │       │   AuditEntry    │       │ id (PK)         │
├─────────────────┤       ├─────────────────┤       │ contact_id (FK) │
│ id (PK)         │       │ id (PK)         │       │ platform        │
│ week_start      │       │ timestamp       │       │ platform_id     │
│ generated_at    │       │ action_type     │       │ display_name    │
│ financial_data  │       │ actor           │       │ profile_url     │
│ social_metrics  │       │ server_id       │       └─────────────────┘
│ pending_actions │       │ details         │
│ ai_insights     │       │ result          │       ┌─────────────────┐
│ status          │       │ prev_hash       │       │    MCPServer    │
└─────────────────┘       │ hash            │       ├─────────────────┤
                          └─────────────────┘       │ id (PK)         │
                                                    │ domain          │
┌─────────────────┐       ┌─────────────────┐       │ endpoint        │
│   RetryQueue    │       │   Metrics       │       │ status          │
├─────────────────┤       ├─────────────────┤       │ last_health_at  │
│ id (PK)         │       │ timestamp       │       │ error_count     │
│ action_type     │       │ integration     │       └─────────────────┘
│ action_payload  │       │ metric_name     │
│ failure_reason  │       │ metric_value    │
│ retry_count     │       │ labels          │
│ next_retry_at   │       └─────────────────┘
│ created_at      │
│ status          │
└─────────────────┘
```

---

## Entity Definitions

### XeroConnection

Stores OAuth credentials and connection status for Xero integration.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK | Unique connection identifier |
| `tenant_id` | string | Required, unique | Xero organization ID |
| `access_token` | string (encrypted) | Required | OAuth access token |
| `refresh_token` | string (encrypted) | Required | OAuth refresh token |
| `token_expiry` | datetime | Required | Token expiration timestamp |
| `status` | enum | Required | `active`, `expired`, `auth_required`, `error` |
| `last_sync` | datetime | Optional | Last successful data sync |
| `created_at` | datetime | Required | Connection creation time |
| `updated_at` | datetime | Required | Last modification time |

**Validation Rules**:
- `tenant_id` must be valid Xero tenant ID format
- `status` transitions: `auth_required` → `active` → `expired` → `auth_required`
- Tokens must be encrypted at rest (FR-031)

---

### SocialAccount

Stores OAuth credentials and metadata for social media platforms.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK | Unique account identifier |
| `platform` | enum | Required | `facebook`, `instagram`, `twitter` |
| `account_id` | string | Required | Platform-specific account ID |
| `page_id` | string | Optional | Facebook Page ID (for FB/IG) |
| `access_token` | string (encrypted) | Required | OAuth access token |
| `token_expiry` | datetime | Required | Token expiration timestamp |
| `follower_count` | integer | Optional | Last known follower count |
| `status` | enum | Required | `active`, `expired`, `auth_required`, `rate_limited`, `error` |
| `last_sync` | datetime | Optional | Last successful API sync |
| `created_at` | datetime | Required | Account connection time |
| `updated_at` | datetime | Required | Last modification time |

**Validation Rules**:
- `platform` determines which API client to use
- Instagram requires linked Facebook Page (`page_id` required)
- Tokens must be encrypted at rest (FR-031)

---

### UnifiedContact

Aggregates contact information across platforms using email as primary key.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK | Internal contact identifier |
| `primary_email` | string | Required, unique | Primary email for matching |
| `display_name` | string | Optional | Preferred display name |
| `company` | string | Optional | Company affiliation |
| `notes` | text | Optional | User-added notes |
| `created_at` | datetime | Required | First seen timestamp |
| `updated_at` | datetime | Required | Last update timestamp |

**Validation Rules**:
- `primary_email` must be valid email format
- Automatic deduplication on email (FR-033)

---

### PlatformIdentity

Links a unified contact to their platform-specific identities.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK | Identity identifier |
| `contact_id` | UUID | FK → UnifiedContact | Parent contact |
| `platform` | enum | Required | `xero`, `linkedin`, `twitter`, `facebook`, `instagram`, `email`, `whatsapp` |
| `platform_id` | string | Required | Platform-specific user ID |
| `display_name` | string | Optional | Name on this platform |
| `profile_url` | string | Optional | Profile link |
| `linked_by` | enum | Required | `email_match`, `manual`, `ai_suggested` |
| `confidence` | float | Optional | Match confidence (0-1) |
| `created_at` | datetime | Required | Link creation time |

**Validation Rules**:
- Unique constraint on (`contact_id`, `platform`, `platform_id`)
- `confidence` required when `linked_by` = `ai_suggested`

---

### CEOBriefing

Generated weekly briefing document with aggregated business intelligence.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK | Briefing identifier |
| `week_start` | date | Required, unique | Monday of the briefing week |
| `generated_at` | datetime | Required | Generation timestamp |
| `financial_data` | JSON | Optional | Xero summary data |
| `social_metrics` | JSON | Optional | Social platform metrics |
| `pending_actions` | JSON | Required | List of pending approvals |
| `ai_insights` | text | Optional | AI-generated recommendations |
| `data_sources` | JSON | Required | Availability status of each source |
| `status` | enum | Required | `generating`, `complete`, `partial`, `failed` |
| `file_path` | string | Optional | Vault path to generated .md file |

**JSON Schemas**:

`financial_data`:
```json
{
  "revenue": 12500.00,
  "expenses": 8200.00,
  "cash_flow": 4300.00,
  "outstanding_invoices": [
    {"id": "INV-001", "amount": 1500.00, "due_date": "2026-02-15", "contact": "Acme Corp"}
  ],
  "variance_alerts": [
    {"metric": "revenue", "change_pct": 25.5, "direction": "up"}
  ]
}
```

`social_metrics`:
```json
{
  "facebook": {"posts": 5, "reach": 12000, "engagement_rate": 3.2},
  "instagram": {"posts": 8, "reach": 8500, "engagement_rate": 4.1},
  "twitter": {"tweets": 12, "impressions": 25000, "follower_delta": 45}
}
```

---

### AuditEntry

Immutable audit log entry with hash chain integrity.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK | Entry identifier |
| `timestamp` | datetime | Required | Action timestamp (UTC) |
| `action_type` | string | Required | Action category (e.g., `xero.invoice.create`) |
| `actor` | enum | Required | `user`, `ai`, `system` |
| `server_id` | string | Required | MCP server that processed action |
| `approval_ref` | string | Optional | Reference to approval file |
| `details` | JSON | Required | Action-specific details |
| `result` | enum | Required | `success`, `failure`, `pending` |
| `error_message` | string | Optional | Error details if failed |
| `latency_ms` | integer | Optional | API call latency |
| `prev_hash` | string | Required | Hash of previous entry |
| `hash` | string | Required | SHA-256 hash of this entry |

**Validation Rules**:
- `hash` computed from all fields except `hash` itself
- `prev_hash` must match previous entry's `hash` (chain integrity)
- First entry uses `prev_hash` = "GENESIS"
- Credentials must never appear in `details` (FR-032)

---

### MCPServer

Tracks health and status of each domain MCP server.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | string | PK | Server identifier (e.g., `financial`, `social`) |
| `domain` | enum | Required | `financial`, `social`, `communication`, `coordinator` |
| `endpoint` | string | Required | HTTP endpoint URL |
| `status` | enum | Required | `healthy`, `unhealthy`, `starting`, `stopped` |
| `last_health_at` | datetime | Optional | Last successful health check |
| `error_count` | integer | Default: 0 | Consecutive error count |
| `version` | string | Optional | Server version |

**Validation Rules**:
- `status` = `unhealthy` when `error_count` >= 3
- Health check interval: 30 seconds
- Circuit breaker: No routing when `status` != `healthy`

---

### RetryQueue

Queue for failed actions awaiting retry.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK | Queue entry identifier |
| `action_type` | string | Required | Action to retry |
| `action_payload` | JSON | Required | Full action parameters |
| `approval_ref` | string | Optional | Original approval reference |
| `failure_reason` | string | Required | Why the action failed |
| `error_code` | string | Optional | API error code |
| `retry_count` | integer | Default: 0 | Number of retries attempted |
| `max_retries` | integer | Default: 5 | Maximum retry attempts |
| `next_retry_at` | datetime | Required | Scheduled retry time |
| `status` | enum | Required | `pending`, `retrying`, `succeeded`, `failed` |
| `created_at` | datetime | Required | First failure time |
| `updated_at` | datetime | Required | Last status change |

**Validation Rules**:
- `status` = `failed` when `retry_count` >= `max_retries`
- `next_retry_at` computed via exponential backoff (FR-020a)
- User notified when `status` transitions to `failed` (FR-020b)

---

### Metrics (Time-Series)

Observability metrics for monitoring.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `timestamp` | datetime | Required | Metric timestamp |
| `integration` | string | Required | Service name (e.g., `xero`, `twitter`) |
| `metric_name` | string | Required | Metric identifier |
| `metric_value` | float | Required | Numeric value |
| `labels` | JSON | Optional | Additional dimensions |

**Standard Metrics** (FR-029):
- `api_call_latency_seconds`: Histogram with buckets
- `api_error_total`: Counter per integration and error type
- `retry_queue_depth`: Current queue size gauge

---

## File Storage Locations

All entities stored as JSON/YAML files in the Obsidian vault:

```
obsidian-vault/
├── config/
│   ├── xero-connection.yaml       # XeroConnection
│   └── social-accounts.yaml       # SocialAccount[]
├── contacts/
│   └── unified/
│       └── {email-hash}.yaml      # UnifiedContact + PlatformIdentity[]
├── briefings/
│   └── {year}/
│       └── week-{week-num}.md     # CEOBriefing
├── audit/
│   ├── active/
│   │   └── {date}.jsonl           # AuditEntry[] (< 90 days)
│   └── archive/
│       └── {year-month}.jsonl.gz  # Archived entries
├── retry-queue/
│   └── pending.yaml               # RetryQueue[]
└── metrics/
    └── {date}.jsonl               # Metrics time-series
```

---

## State Transitions

### XeroConnection Status
```
[Created] → auth_required → active ⟷ expired → auth_required
                              ↓
                            error → auth_required
```

### SocialAccount Status
```
[Created] → auth_required → active ⟷ expired → auth_required
                              ↓         ↓
                        rate_limited   error
                              ↓         ↓
                            active ← ←─┘
```

### RetryQueue Status
```
[Created] → pending ⟷ retrying → succeeded
                 ↓
               failed (after max_retries)
```

### CEOBriefing Status
```
[Scheduled] → generating → complete
                   ↓
                partial (some sources unavailable)
                   ↓
                failed (critical error)
```

---

## Indexes and Query Patterns

| Entity | Index | Query Pattern |
|--------|-------|---------------|
| UnifiedContact | `primary_email` | Contact lookup by email |
| PlatformIdentity | `(platform, platform_id)` | Cross-platform matching |
| AuditEntry | `timestamp` | Date range export |
| AuditEntry | `action_type` | Filter by action category |
| RetryQueue | `(status, next_retry_at)` | Get pending retries |
| CEOBriefing | `week_start` | Weekly briefing lookup |
| Metrics | `(timestamp, integration)` | Time-series queries |

---

## Encryption Requirements

Per FR-031 and FR-032:

| Field | Encryption | Key Source |
|-------|------------|------------|
| `XeroConnection.access_token` | Fernet | `GOLD_MASTER_KEY` |
| `XeroConnection.refresh_token` | Fernet | `GOLD_MASTER_KEY` |
| `SocialAccount.access_token` | Fernet | `GOLD_MASTER_KEY` |
| `AuditEntry.details` | None (scrubbed) | N/A |

Scrubbing rules for audit details:
- Replace token values with `[REDACTED]`
- Remove query parameters containing `token`, `key`, `secret`
- Preserve action-relevant parameters only
