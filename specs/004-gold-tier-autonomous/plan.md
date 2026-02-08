# Implementation Plan: Gold Tier — Autonomous Employee

**Branch**: `004-gold-tier-autonomous` | **Date**: 2026-02-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-gold-tier-autonomous/spec.md`

---

## Summary

Gold Tier extends the Silver Tier AI Employee with enterprise-grade autonomous capabilities: Xero accounting integration, multi-platform social media management (Facebook, Instagram, Twitter), domain-separated MCP server architecture, weekly CEO briefings with cross-domain intelligence, and tamper-evident audit logging with hash chain integrity.

---

## Technical Context

**Language/Version**: Python 3.8+ (backend), TypeScript/Node.js (Next.js 16 dashboard)
**Primary Dependencies**:
- FastAPI (MCP servers)
- xero-python (Xero SDK)
- tweepy (Twitter API)
- httpx (async HTTP)
- cryptography (token encryption)
- prometheus-client (metrics)
- APScheduler (CEO briefing scheduler)

**Storage**: File-based (Obsidian vault YAML/JSON/Markdown)
**Testing**: pytest (Python), Jest (TypeScript)
**Target Platform**: Linux server / Windows WSL2
**Project Type**: Web application (Python backend + Next.js dashboard)
**Performance Goals**:
- API call latency < 2s p95
- CEO briefing generation < 5 minutes
- Social post publish < 60s from approval

**Constraints**:
- Xero rate limit: 60 calls/minute
- Twitter rate limit: 300 tweets/3 hours
- Meta rate limit: 200 calls/hour
- Audit log retention: 90 days active + cold archive

**Scale/Scope**: Single business entity, 4 MCP servers, ~100 API calls/day typical

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| **Human Authority** | ✅ PASS | All external actions require approval tokens (FR-003, FR-009, etc.) |
| **Explainability** | ✅ PASS | Audit logging captures reasoning and context (FR-024-027) |
| **Minimal Autonomy** | ✅ PASS | CEO briefing is informational; actions need human approval |
| **Security & Privacy** | ✅ PASS | OAuth tokens encrypted (FR-031), credentials never logged (FR-032) |
| **Deterministic Behavior** | ✅ PASS | Retry policy defined (5 retries, exponential backoff) |
| **File-Based Operations** | ✅ PASS | All state stored in vault YAML/JSON files |
| **Transparency & Auditability** | ✅ PASS | Hash chain audit log with export capability |

**Gold Tier Extensions Justified**:
- External API access (Xero, Meta, Twitter) is controlled through MCP servers with approval validation
- Multi-server architecture provides security isolation between financial and social domains
- Automated CEO briefing is read-only aggregation, not autonomous action

---

## Project Structure

### Documentation (this feature)

```text
specs/004-gold-tier-autonomous/
├── spec.md              # Feature specification (with clarifications)
├── plan.md              # This file
├── research.md          # Phase 0: Technical research
├── data-model.md        # Phase 1: Entity definitions
├── quickstart.md        # Phase 1: Setup guide
├── contracts/           # Phase 1: API schemas
│   ├── coordinator-api.yaml
│   ├── financial-api.yaml
│   └── social-api.yaml
└── tasks.md             # Phase 2: Implementation tasks (via /sp.tasks)
```

### Source Code (repository root)

```text
agent-skills/
├── __init__.py
├── orchestrator.py              # Extends for multi-MCP coordination
├── cli/
│   └── main.py                  # Add verify-gold command
├── core/
│   ├── base_skill.py            # Existing
│   ├── vault_interface.py       # Existing
│   ├── credential_manager.py    # NEW: Encrypted token storage
│   ├── audit_logger.py          # NEW: Hash chain audit logging
│   ├── metrics_collector.py     # NEW: Prometheus metrics
│   ├── retry_queue.py           # NEW: Failed action queue
│   └── contact_matcher.py       # NEW: Cross-domain contact linking
├── mcp_server/
│   ├── server.py                # Existing Communication MCP
│   ├── coordinator.py           # NEW: Multi-MCP coordinator
│   ├── financial.py             # NEW: Financial MCP (Xero)
│   └── social.py                # NEW: Social MCP (Meta, Twitter)
├── models/
│   ├── xero_connection.py       # NEW
│   ├── social_account.py        # NEW
│   ├── unified_contact.py       # NEW
│   ├── ceo_briefing.py          # NEW
│   ├── audit_entry.py           # NEW
│   └── retry_item.py            # NEW
├── skills/
│   ├── xero_skill.py            # NEW: Xero operations
│   ├── facebook_skill.py        # NEW: Facebook operations
│   ├── instagram_skill.py       # NEW: Instagram operations
│   ├── twitter_skill.py         # NEW: Twitter operations
│   ├── ceo_briefing_skill.py    # NEW: Briefing generation
│   └── audit_skill.py           # NEW: Audit log management
├── scheduler/
│   └── task_scheduler.py        # Extend for CEO briefing schedule
└── watchers/
    ├── gmail_watcher.py         # Existing
    ├── linkedin_watcher.py      # Existing
    ├── whatsapp_watcher.py      # Existing
    ├── facebook_watcher.py      # NEW: FB message monitoring
    ├── instagram_watcher.py     # NEW: IG message monitoring
    └── twitter_watcher.py       # NEW: Twitter mention monitoring

dashboard/src/
├── app/
│   ├── page.tsx                 # Extend with Gold Tier widgets
│   ├── xero/
│   │   └── page.tsx             # NEW: Xero connection & invoices
│   ├── social/
│   │   └── page.tsx             # NEW: Social accounts dashboard
│   ├── briefings/
│   │   └── page.tsx             # NEW: CEO briefing viewer
│   └── api/
│       ├── xero/                # NEW: Xero proxy endpoints
│       ├── social/              # NEW: Social proxy endpoints
│       └── metrics/             # NEW: Metrics endpoint
├── components/
│   ├── xero-connection.tsx      # NEW
│   ├── social-accounts.tsx      # NEW
│   ├── ceo-briefing-card.tsx    # NEW
│   ├── mcp-health-grid.tsx      # NEW
│   └── audit-log-viewer.tsx     # NEW
└── lib/
    └── api.ts                   # Extend with Gold Tier endpoints

obsidian-vault/
├── config/
│   ├── xero-connection.yaml     # Encrypted Xero credentials
│   ├── social-accounts.yaml     # Encrypted social credentials
│   └── schedules.yaml           # Extend with CEO briefing
├── contacts/
│   └── unified/                 # NEW: Cross-platform contacts
├── briefings/
│   └── {year}/                  # NEW: Generated CEO briefings
├── audit/
│   ├── active/                  # NEW: Recent audit logs
│   └── archive/                 # NEW: Archived logs
├── retry-queue/                 # NEW: Failed actions
└── metrics/                     # NEW: Time-series data
```

**Structure Decision**: Web application pattern with Python backend (4 MCP servers) and Next.js dashboard frontend. File-based storage in Obsidian vault maintains consistency with Bronze/Silver tiers.

---

## Complexity Tracking

| Complexity | Why Needed | Simpler Alternative Rejected Because |
|------------|------------|-------------------------------------|
| 4 MCP servers (coord, fin, social, comms) | Security isolation between financial and social domains per constitution | Single server would mix sensitive financial ops with social media, violating security principles |
| Hash chain audit log | Tamper-evidence required for compliance and trust | Simple append log doesn't prove integrity, can be modified undetected |
| Encrypted credential storage | OAuth tokens are high-value secrets | Plain text in vault files would violate security principle |

---

## Architecture Decisions

### ADR-001: Domain-Separated MCP Servers

**Context**: Gold Tier adds financial (Xero) and social media (Meta, Twitter) integrations with different security profiles.

**Decision**: Operate separate MCP servers for each domain with a coordinator for routing.

**Consequences**:
- (+) Security isolation: Financial server never processes social requests
- (+) Independent rate limiting per domain
- (+) Clear audit boundaries
- (+) Fault isolation
- (-) Operational complexity: 4 processes to manage
- (-) Inter-service communication overhead

### ADR-002: File-Based Credential Encryption

**Context**: OAuth tokens need secure storage without adding database dependencies.

**Decision**: Use Fernet symmetric encryption with master key in environment variable.

**Consequences**:
- (+) No new infrastructure dependencies
- (+) Consistent with file-based architecture
- (+) Key rotation supported via re-encryption
- (-) Master key management is user responsibility
- (-) No automatic key rotation

### ADR-003: Email-Based Contact Matching

**Context**: Cross-domain intelligence requires linking the same person across platforms.

**Decision**: Use email address as primary key with manual linking fallback.

**Consequences**:
- (+) Email is available in Xero and often in DMs
- (+) No false positives from fuzzy matching
- (+) Simple implementation
- (-) Won't match contacts without email
- (-) Manual linking required for some contacts

---

## Implementation Phases

### Phase 1: Core Infrastructure (P1 items)
1. Credential manager with encryption
2. Audit logger with hash chain
3. Retry queue implementation
4. Metrics collector

### Phase 2: Financial Integration (P1 items)
1. Financial MCP server
2. Xero OAuth flow
3. XeroSkill implementation
4. Invoice/transaction endpoints

### Phase 3: CEO Briefing (P1 items)
1. CEOBriefingSkill implementation
2. Scheduler integration
3. Briefing template and generation
4. Dashboard viewer

### Phase 4: Social Integration (P2 items)
1. Social MCP server
2. Meta OAuth and watchers
3. Twitter OAuth and watchers
4. Social Skills (FB, IG, Twitter)

### Phase 5: Multi-MCP Coordination (P2 items)
1. Coordinator server
2. Health check aggregation
3. Action routing
4. Dashboard integration

### Phase 6: Cross-Domain & Polish (P3 items)
1. Contact matcher
2. Error recovery enhancements
3. Audit log export
4. End-to-end testing

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| API rate limit exhaustion | Pre-emptive queue management, metrics alerting, per-domain tracking |
| OAuth token expiry during operation | Token refresh before scheduled jobs, 24-hour buffer |
| Hash chain corruption | Chain verification on write, daily backups, recovery procedure |
| Multi-MCP coordination failure | Health checks every 30s, circuit breaker pattern |
| Cross-domain matching errors | Conservative email-only matching, manual review option |

---

## Dependencies

### New Python Packages
```text
xero-python>=3.0.0         # Xero API SDK
tweepy>=4.14.0             # Twitter API v2
cryptography>=42.0.0       # Token encryption
prometheus-client>=0.19.0  # Metrics export
httpx>=0.27.0              # Async HTTP for multi-MCP
```

### External Services
- Xero Developer Account (OAuth app registration)
- Meta Developer Account (Business app with page permissions)
- Twitter Developer Account (API v2 access)

---

## Testing Strategy

### Unit Tests
- Credential encryption/decryption
- Hash chain integrity verification
- Contact email matching logic
- Retry backoff calculation

### Integration Tests
- MCP server health checks
- Coordinator routing logic
- OAuth token refresh flow
- Audit log export

### End-to-End Tests
- Full CEO briefing generation with mock data
- Social post approval and publish flow
- Xero invoice creation flow
- Error recovery and retry

---

## Generated Artifacts

| Artifact | Path | Purpose |
|----------|------|---------|
| Research | `specs/004-gold-tier-autonomous/research.md` | Technical decisions and patterns |
| Data Model | `specs/004-gold-tier-autonomous/data-model.md` | Entity definitions and relationships |
| Coordinator API | `specs/004-gold-tier-autonomous/contracts/coordinator-api.yaml` | OpenAPI schema |
| Financial API | `specs/004-gold-tier-autonomous/contracts/financial-api.yaml` | OpenAPI schema |
| Social API | `specs/004-gold-tier-autonomous/contracts/social-api.yaml` | OpenAPI schema |
| Quickstart | `specs/004-gold-tier-autonomous/quickstart.md` | Setup guide |

---

## Next Steps

Run `/sp.tasks` to generate the implementation task list with acceptance criteria and test cases.
