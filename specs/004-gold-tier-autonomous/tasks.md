# Tasks: Gold Tier — Autonomous Employee

**Input**: Design documents from `/specs/004-gold-tier-autonomous/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `agent-skills/` (Python 3.8+)
- **Dashboard**: `dashboard/src/` (Next.js 16)
- **Vault**: `obsidian-vault/` (file-based storage)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependencies, and vault structure

- [x] T001 Add Gold Tier dependencies to requirements.txt (xero-python, tweepy, cryptography, prometheus-client, httpx)
- [x] T002 [P] Create vault directory structure per plan.md in obsidian-vault/ (config/, contacts/unified/, briefings/, audit/active/, audit/archive/, retry-queue/, metrics/)
- [x] T003 [P] Add Gold Tier environment variables to .env.example (GOLD_MASTER_KEY, XERO_*, META_*, TWITTER_*, MCP ports)
- [x] T004 [P] Update dashboard package.json with any new dependencies for Gold Tier components

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Core Models

- [x] T005 [P] Create AuditEntry model in agent-skills/models/audit_entry.py (id, timestamp, action_type, actor, server_id, details, result, prev_hash, hash)
- [x] T006 [P] Create RetryItem model in agent-skills/models/retry_item.py (id, action_type, action_payload, failure_reason, retry_count, next_retry_at, status)
- [x] T007 [P] Create MCPServer model in agent-skills/models/mcp_server.py (id, domain, endpoint, status, last_health_at, error_count)
- [x] T008 Update agent-skills/models/__init__.py to export new models

### Core Infrastructure

- [x] T009 Implement CredentialManager in agent-skills/core/credential_manager.py (Fernet encryption, encrypt/decrypt tokens, load/save to vault)
- [x] T010 Implement AuditLogger in agent-skills/core/audit_logger.py (hash chain, append entry, verify chain, daily log rotation)
- [x] T011 [P] Implement MetricsCollector in agent-skills/core/metrics_collector.py (Prometheus counters/histograms, api_call_latency, api_error_total, retry_queue_depth)
- [x] T012 Implement RetryQueue in agent-skills/core/retry_queue.py (add failed action, get pending retries, calculate exponential backoff, mark succeeded/failed)

### MCP Server Foundation

- [x] T013 Create Coordinator MCP server base in agent-skills/mcp_server/coordinator.py (FastAPI app, /health, /metrics, /servers endpoints per contracts/coordinator-api.yaml)
- [x] T014 Add action routing logic to coordinator in agent-skills/mcp_server/coordinator.py (/action/route endpoint, server health checks, circuit breaker)
- [x] T015 Update existing MCP server in agent-skills/mcp_server/server.py to register with coordinator as "communication" domain

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Xero Accounting Integration (Priority: P1) 🎯 MVP

**Goal**: Connect to Xero, retrieve financial data, create invoices with approval

**Independent Test**: Connect Xero account via OAuth, query current invoices, create a test invoice draft, verify data appears correctly

### Models for US1

- [x] T016 [P] [US1] Create XeroConnection model in agent-skills/models/xero_connection.py (id, tenant_id, access_token, refresh_token, token_expiry, status, last_sync)

### Financial MCP Server

- [x] T017 [US1] Create Financial MCP server in agent-skills/mcp_server/financial.py (FastAPI app on port 8001, /health endpoint)
- [x] T018 [US1] Implement Xero OAuth endpoints in agent-skills/mcp_server/financial.py (/xero/connect, /xero/callback per contracts/financial-api.yaml)
- [x] T019 [US1] Implement Xero data endpoints in agent-skills/mcp_server/financial.py (/xero/status, /xero/invoices, /xero/contacts, /xero/bank-transactions)
- [x] T020 [US1] Implement Xero write endpoints in agent-skills/mcp_server/financial.py (/xero/invoices/create, /xero/bank-transactions/{id}/categorize with approval validation)
- [x] T021 [US1] Implement /xero/summary endpoint in agent-skills/mcp_server/financial.py (financial summary for CEO briefing)

### XeroSkill Implementation

- [x] T022 [US1] Create XeroSkill in agent-skills/skills/xero_skill.py (extends BaseSkill, id="xero", input/output schemas)
- [x] T023 [US1] Implement XeroSkill.execute() for invoice operations in agent-skills/skills/xero_skill.py (list, create, categorize)
- [x] T024 [US1] Add rate limit handling to XeroSkill in agent-skills/skills/xero_skill.py (60 calls/min queue)
- [x] T025 [US1] Register XeroSkill in agent-skills/core/skill_registry.py

### Dashboard Integration for US1

- [x] T026 [P] [US1] Create Xero connection component in dashboard/src/components/xero-connection.tsx (OAuth flow, connection status)
- [x] T027 [P] [US1] Create Xero API routes in dashboard/src/app/api/xero/route.ts (proxy to Financial MCP)
- [x] T028 [US1] Create Xero dashboard page in dashboard/src/app/xero/page.tsx (connection, invoices list, create invoice form)
- [x] T029 [US1] Update dashboard home page in dashboard/src/app/page.tsx with Xero status widget

**Checkpoint**: Xero integration complete - can connect, view invoices, create invoices with approval

---

## Phase 4: User Story 2 - Weekly CEO Briefing Generation (Priority: P1) 🎯 MVP

**Goal**: Generate weekly business intelligence reports on schedule

**Independent Test**: Trigger briefing generation manually, verify it includes financial summary, pending approvals, and AI recommendations

### Models for US2

- [x] T030 [P] [US2] Create CEOBriefing model in agent-skills/models/ceo_briefing.py (id, week_start, generated_at, financial_data, social_metrics, pending_actions, ai_insights, status, file_path)

### CEOBriefingSkill Implementation

- [x] T031 [US2] Create CEOBriefingSkill in agent-skills/skills/ceo_briefing_skill.py (extends BaseSkill, id="ceo_briefing")
- [x] T032 [US2] Implement data aggregation in CEOBriefingSkill (collect from Xero, pending approvals, social when available)
- [x] T033 [US2] Implement AI insight generation in CEOBriefingSkill (variance detection, recommendations)
- [x] T034 [US2] Implement Markdown template rendering in CEOBriefingSkill (output to vault/briefings/{year}/week-{num}.md)
- [x] T035 [US2] Register CEOBriefingSkill in agent-skills/core/skill_registry.py

### Scheduler Integration

- [x] T036 [US2] Extend scheduler in agent-skills/scheduler/task_scheduler.py with CEO briefing cron job (default Sunday 8AM)
- [x] T037 [US2] Add briefing schedule configuration to obsidian-vault/config/schedules.yaml

### Dashboard Integration for US2

- [x] T038 [P] [US2] Create CEO briefing card component in dashboard/src/components/ceo-briefing-card.tsx (latest briefing preview, link to full)
- [x] T039 [US2] Create briefings list page in dashboard/src/app/briefings/page.tsx (list all briefings, view details)
- [x] T040 [US2] Add briefing status widget to dashboard home in dashboard/src/app/page.tsx

**Checkpoint**: CEO briefing generation complete - scheduled generation works, includes Xero data

---

## Phase 5: User Story 3 - Facebook & Instagram Integration (Priority: P2)

**Goal**: Monitor Meta platforms, create posts with approval, track engagement

**Independent Test**: Connect Facebook/Instagram via OAuth, monitor for messages, create test post draft, verify approval workflow

### Models for US3

- [x] T041 [P] [US3] Create SocialAccount model in agent-skills/models/social_account.py (id, platform, account_id, page_id, access_token, token_expiry, follower_count, status)

### Social MCP Server - Meta

- [x] T042 [US3] Create Social MCP server in agent-skills/mcp_server/social.py (FastAPI app on port 8002, /health endpoint)
- [x] T043 [US3] Implement Meta OAuth endpoints in agent-skills/mcp_server/social.py (/meta/connect, /meta/callback, /meta/status per contracts/social-api.yaml)
- [x] T044 [US3] Implement Meta data endpoints in agent-skills/mcp_server/social.py (/meta/messages, /meta/posts, /meta/insights)
- [x] T045 [US3] Implement Meta write endpoints in agent-skills/mcp_server/social.py (/meta/posts/create, /meta/messages/reply with approval validation)

### Meta Skills Implementation

- [x] T046 [P] [US3] Create FacebookSkill in agent-skills/skills/facebook_skill.py (extends BaseSkill, FB-specific operations)
- [x] T047 [P] [US3] Create InstagramSkill in agent-skills/skills/instagram_skill.py (extends BaseSkill, IG-specific operations)
- [x] T048 [US3] Register Facebook and Instagram skills in agent-skills/core/skill_registry.py

### Meta Watchers

- [x] T049 [P] [US3] Create FacebookWatcher in agent-skills/watchers/facebook_watcher.py (poll messages, create event files)
- [x] T050 [P] [US3] Create InstagramWatcher in agent-skills/watchers/instagram_watcher.py (poll messages, create event files)

### Dashboard Integration for US3

- [x] T051 [P] [US3] Create social accounts component in dashboard/src/components/social-accounts.tsx (connection status, follower counts)
- [x] T052 [US3] Create social dashboard page in dashboard/src/app/social/page.tsx (accounts, recent posts, engagement)
- [x] T053 [US3] Add social API routes in dashboard/src/app/api/social/route.ts (proxy to Social MCP)

**Checkpoint**: Meta integration complete - can connect FB/IG, monitor messages, create posts

---

## Phase 6: User Story 4 - Twitter (X) Integration (Priority: P2)

**Goal**: Monitor Twitter mentions/DMs, compose tweets, track engagement

**Independent Test**: Connect Twitter via OAuth, monitor mentions, create test tweet draft, verify rate limit handling

### Social MCP Server - Twitter

- [x] T054 [US4] Implement Twitter OAuth endpoints in agent-skills/mcp_server/social.py (/twitter/connect, /twitter/callback, /twitter/status)
- [x] T055 [US4] Implement Twitter data endpoints in agent-skills/mcp_server/social.py (/twitter/mentions, /twitter/dms, /twitter/tweets, /twitter/insights)
- [x] T056 [US4] Implement Twitter write endpoints in agent-skills/mcp_server/social.py (/twitter/tweets/create, /twitter/dms/reply with approval validation)

### TwitterSkill Implementation

- [x] T057 [US4] Create TwitterSkill in agent-skills/skills/twitter_skill.py (extends BaseSkill, tweet operations, rate limit handling)
- [x] T058 [US4] Register TwitterSkill in agent-skills/core/skill_registry.py

### Twitter Watcher

- [x] T059 [US4] Create TwitterWatcher in agent-skills/watchers/twitter_watcher.py (poll mentions/DMs, create event files)

### Dashboard Updates for US4

- [x] T060 [US4] Update social dashboard in dashboard/src/app/social/page.tsx to include Twitter account and metrics
- [x] T061 [US4] Update social-accounts component to show Twitter in dashboard/src/components/social-accounts.tsx

**Checkpoint**: Twitter integration complete - can connect, monitor, tweet with approval

---

## Phase 7: User Story 5 - Multi-MCP Server Architecture (Priority: P2)

**Goal**: Coordinate multiple domain MCP servers with health monitoring

**Independent Test**: Start all MCP servers, verify health checks pass, execute action through coordinator, confirm routing

### Coordinator Enhancements

- [x] T062 [US5] Implement server registration in coordinator in agent-skills/mcp_server/coordinator.py (Financial, Social, Communication servers)
- [x] T063 [US5] Implement health check polling in coordinator in agent-skills/mcp_server/coordinator.py (30-second interval, error counting)
- [x] T064 [US5] Implement circuit breaker pattern in coordinator in agent-skills/mcp_server/coordinator.py (unhealthy after 3 failures, recovery)
- [x] T065 [US5] Add audit logging to action routing in agent-skills/mcp_server/coordinator.py (log server_id with each action)

### Dashboard Integration for US5

- [x] T066 [P] [US5] Create MCP health grid component in dashboard/src/components/mcp-health-grid.tsx (server status, last check, error counts)
- [x] T067 [US5] Add metrics API route in dashboard/src/app/api/metrics/route.ts (proxy to coordinator /metrics)
- [x] T068 [US5] Update dashboard home with MCP health grid in dashboard/src/app/page.tsx

### CLI Updates

- [x] T069 [US5] Add verify-gold command to CLI in agent-skills/cli/main.py (check all servers, connections, audit chain)

**Checkpoint**: Multi-MCP architecture complete - coordinator routes actions, monitors health

---

## Phase 8: User Story 6 - Error Recovery & Graceful Degradation (Priority: P3)

**Goal**: Queue failed actions, retry with backoff, continue operating when services fail

**Independent Test**: Simulate API failure, verify action queued, retry succeeds on recovery, other platforms unaffected

### Retry Queue Integration

- [ ] T070 [US6] Integrate RetryQueue with all MCP action handlers in agent-skills/mcp_server/financial.py
- [ ] T071 [US6] Integrate RetryQueue with Social MCP action handlers in agent-skills/mcp_server/social.py
- [ ] T072 [US6] Implement retry worker in agent-skills/scheduler/task_scheduler.py (process pending retries, exponential backoff)
- [ ] T073 [US6] Add user notification on permanent failure in agent-skills/core/retry_queue.py (after 5 retries)

### Graceful Degradation

- [ ] T074 [US6] Update CEOBriefingSkill to handle unavailable sources in agent-skills/skills/ceo_briefing_skill.py ([DATA UNAVAILABLE] markers)
- [ ] T075 [US6] Implement OAuth token refresh monitoring in agent-skills/core/credential_manager.py (24-hour expiry warning)
- [ ] T076 [US6] Add degraded mode status to coordinator health in agent-skills/mcp_server/coordinator.py

**Checkpoint**: Error recovery complete - actions retry, system degrades gracefully

---

## Phase 9: User Story 7 - Cross-Domain Context Integration (Priority: P3)

**Goal**: Link contacts across platforms, provide unified context

**Independent Test**: Create contact in multiple systems, verify AI response includes context from all sources

### Contact Models

- [ ] T077 [P] [US7] Create UnifiedContact model in agent-skills/models/unified_contact.py (id, primary_email, display_name, company, notes)
- [ ] T078 [P] [US7] Create PlatformIdentity model in agent-skills/models/unified_contact.py (id, contact_id, platform, platform_id, linked_by, confidence)

### Contact Matcher

- [ ] T079 [US7] Implement ContactMatcher in agent-skills/core/contact_matcher.py (email-based matching, manual linking API)
- [ ] T080 [US7] Integrate contact matching with XeroSkill in agent-skills/skills/xero_skill.py (link Xero contacts)
- [ ] T081 [US7] Integrate contact matching with social skills in agent-skills/skills/facebook_skill.py, twitter_skill.py
- [ ] T082 [US7] Add cross-domain context to reasoning loop in agent-skills/core/reasoning_loop.py

### Dashboard Integration for US7

- [ ] T083 [US7] Create contacts page in dashboard/src/app/contacts/page.tsx (unified view, manual linking)

**Checkpoint**: Cross-domain context complete - contacts linked, context appears in AI reasoning

---

## Phase 10: User Story 8 - Comprehensive Audit Logging (Priority: P3)

**Goal**: Tamper-evident logging with hash chain, export capability

**Independent Test**: Execute actions, export audit log, verify hash chain integrity

### AuditSkill Implementation

- [ ] T084 [US8] Create AuditSkill in agent-skills/skills/audit_skill.py (extends BaseSkill, export, verify chain)
- [ ] T085 [US8] Implement audit log export in agent-skills/skills/audit_skill.py (date range filter, JSONL format)
- [ ] T086 [US8] Implement 90-day archive rotation in agent-skills/core/audit_logger.py (move to archive/, gzip)
- [ ] T087 [US8] Register AuditSkill in agent-skills/core/skill_registry.py

### Dashboard Integration for US8

- [ ] T088 [P] [US8] Create audit log viewer component in dashboard/src/components/audit-log-viewer.tsx (filter, search, export)
- [ ] T089 [US8] Create audit page in dashboard/src/app/audit/page.tsx (log viewer, chain status)

### Audit Integration

- [ ] T090 [US8] Ensure all MCP actions call AuditLogger in agent-skills/mcp_server/coordinator.py (via middleware)
- [ ] T091 [US8] Add audit verification to verify-gold CLI command in agent-skills/cli/main.py

**Checkpoint**: Audit logging complete - all actions logged, chain verifiable, export works

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, testing, documentation

### Integration

- [ ] T092 Update dashboard navigation in dashboard/src/app/layout.tsx to include all Gold Tier pages
- [ ] T093 Add Gold Tier watcher status to watcher-status-grid in dashboard/src/components/watcher-status-grid.tsx
- [ ] T094 Update orchestrator to coordinate all Gold Tier skills in agent-skills/orchestrator.py

### Configuration

- [ ] T095 Create .env.example with all Gold Tier variables documented
- [ ] T096 Update obsidian-vault/config/schedules.yaml with all Gold Tier schedules

### Final Verification

- [ ] T097 Run verify-gold CLI command and fix any issues
- [ ] T098 Manual end-to-end test: OAuth all platforms, generate CEO briefing, verify audit chain

---

## Dependencies Graph

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (Foundation) ─────────────────────────────────┐
    │                                                  │
    ├──► Phase 3 (US1: Xero) ──► Phase 4 (US2: Briefing)
    │         │                        │
    │         └────────────────────────┘
    │
    ├──► Phase 5 (US3: Meta) ──► Phase 6 (US4: Twitter)
    │         │                        │
    │         └───────┬────────────────┘
    │                 │
    │         Phase 7 (US5: Multi-MCP)
    │                 │
    ├─────────────────┴────────────────────────────────┤
    │                                                  │
    ▼                                                  ▼
Phase 8 (US6: Error Recovery) ◄─────── Phase 9 (US7: Contacts)
    │                                        │
    └──────────────────┬─────────────────────┘
                       │
               Phase 10 (US8: Audit)
                       │
               Phase 11 (Polish)
```

## Parallel Execution Opportunities

### Within Phase 2 (Foundation)
- T005, T006, T007 can run in parallel (independent models)
- T011 can run parallel to T009, T010 (independent metrics)

### Within Phase 3 (US1)
- T026, T027 can run parallel to backend work (frontend components)

### Within Phase 5 (US3)
- T046, T047 can run in parallel (FB and IG skills)
- T049, T050 can run in parallel (FB and IG watchers)

### Across Phases (after Foundation)
- Phase 3 (US1) and Phase 5 (US3) can start in parallel
- Phase 4 (US2) depends on Phase 3 (needs Xero data)
- Phase 6 (US4) depends on Phase 5 (extends Social MCP)

---

## Implementation Strategy

### MVP Scope (Recommended)
**Phase 1 + Phase 2 + Phase 3 + Phase 4** = Minimum viable Gold Tier

This delivers:
- Xero integration (connect, view, create invoices)
- CEO briefing generation (financial data + AI insights)
- Foundation for future social integration

### Full Feature Scope
All phases deliver the complete Gold Tier specification.

---

## Summary

| Phase | User Story | Task Count | Priority |
|-------|------------|------------|----------|
| 1 | Setup | 4 | - |
| 2 | Foundation | 11 | - |
| 3 | US1: Xero | 14 | P1 MVP |
| 4 | US2: CEO Briefing | 11 | P1 MVP |
| 5 | US3: Facebook/Instagram | 13 | P2 |
| 6 | US4: Twitter | 8 | P2 |
| 7 | US5: Multi-MCP | 8 | P2 |
| 8 | US6: Error Recovery | 7 | P3 |
| 9 | US7: Cross-Domain | 7 | P3 |
| 10 | US8: Audit Logging | 8 | P3 |
| 11 | Polish | 7 | - |
| **Total** | | **98** | |

### Independent Test Criteria Per Story

| Story | Independent Test |
|-------|-----------------|
| US1 | Connect Xero, query invoices, create draft invoice |
| US2 | Trigger briefing, verify financial summary + AI insights |
| US3 | Connect FB/IG, monitor messages, create post draft |
| US4 | Connect Twitter, monitor mentions, create tweet draft |
| US5 | Start all MCPs, verify health, route action through coordinator |
| US6 | Simulate failure, verify queue, retry on recovery |
| US7 | Contact in multiple systems, verify cross-context |
| US8 | Execute actions, export log, verify hash chain |
