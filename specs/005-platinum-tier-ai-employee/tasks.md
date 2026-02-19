# Tasks: Platinum Tier AI Employee — Cloud+Local Split Architecture

**Input**: Design documents from `/specs/005-platinum-tier-ai-employee/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested — test tasks omitted.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Cloud agent: `cloud/`
- Local agent: `local/`
- Shared core: `agent-skills/core/`
- Existing skills: `.claude/skills/`
- Dashboard: `dashboard/src/app/`
- Vault: `obsidian-vault/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, vault structure, and shared core modules

- [x] T001 Create vault directory structure for Platinum Tier per quickstart.md in `obsidian-vault/`
- [x] T002 [P] Create `cloud/` directory with `__init__.py`, `config.example.yaml`, and `requirements.txt`
- [x] T003 [P] Create `local/` directory with `__init__.py`, `config.example.yaml`, and `requirements.txt`
- [x] T004 [P] Create `agent-skills/core/__init__.py` package directory
- [x] T005 Create `topology.yaml` at repository root per agent-config-schema.yaml contract in `topology.yaml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Implement `agent_identity.py` — AgentIdentity class with id, zone, heartbeat, capabilities, and identity file I/O per data-model Agent entity in `agent-skills/core/agent_identity.py`
- [x] T007 [P] Implement `security_boundary.py` — SecurityBoundary class wrapping vault writes with zone-scoped path validation per vault-file-schema write_permissions in `agent-skills/core/security_boundary.py`
- [x] T008 [P] Implement `topology.py` — load `topology.yaml`, resolve skill-to-zone mapping, validate agent capabilities in `agent-skills/core/topology.py`
- [x] T009 Implement `draft_lifecycle.py` — Draft creation, 48h expiration check, archival to `Done/expired/`, status transitions per data-model Draft entity in `agent-skills/core/draft_lifecycle.py`
- [x] T010 [P] Implement `audit_logger.py` — Append-only JSONL audit log with SHA-256 hash chaining per data-model AuditEntry entity in `agent-skills/core/audit_logger.py`
- [x] T011 Implement `cloud/agent.py` — Cloud agent entry point that loads `cloud/config.yaml`, initializes AgentIdentity(zone='cloud'), starts assigned skills, writes heartbeat, runs main loop in `cloud/agent.py`
- [x] T012 Implement `local/agent.py` — Local agent entry point that loads `local/config.yaml`, initializes AgentIdentity(zone='local'), starts assigned skills, runs main loop in `local/agent.py`
- [x] T013 Create `cloud/config.yaml` from agent-config-schema cloud_agent_config with actual skill paths and vault path in `cloud/config.yaml`
- [x] T014 Create `local/config.yaml` from agent-config-schema local_agent_config with actual skill paths, MCP server ports, and approval settings in `local/config.yaml`
- [x] T015 [P] Create `cloud/Dockerfile` for Ubuntu 22.04 ARM with Python 3.10+, uv, and Git in `cloud/Dockerfile`
- [x] T016 [P] Create `cloud/systemd/cloud-agent.service` systemd unit file for auto-start and restart in `cloud/systemd/cloud-agent.service`

**Checkpoint**: Foundation ready — both agents can start, identify themselves, enforce security boundaries, and log actions. User story implementation can now begin.

---

## Phase 3: User Story 1 — Cloud Agent Monitors Email and Creates Draft Replies (Priority: P1) 🎯 MVP

**Goal**: Cloud agent monitors Gmail with read-only scope, classifies emails by priority, and creates draft reply files in `Drafts/email/` with context from Company Handbook.

**Independent Test**: Send test emails to the monitored inbox and verify draft files appear in the vault with correct metadata, priority classification, and suggested reply content.

### Implementation for User Story 1

- [x] T017 [US1] Extend gmail-watcher to output Draft files instead of Needs_Action when running in cloud zone — add `--output-drafts` flag that writes to `Drafts/email/` with draft_schema frontmatter in `.claude/skills/gmail-watcher/gmail_watcher.py`
- [x] T018 [US1] Implement email priority classifier — classify emails as high/medium/low based on sender (known contacts), subject keywords, and labels in `agent-skills/core/email_classifier.py`
- [x] T019 [US1] Implement draft reply generator — read email content + Company_Handbook.md context, generate suggested reply template with placeholders in `agent-skills/core/draft_reply_generator.py`
- [x] T020 [US1] Wire cloud agent's gmail-watcher process to use SecurityBoundary-wrapped vault writes, ensuring output goes to `Drafts/email/` only in `cloud/agent.py`
- [x] T021 [US1] Add draft expiration sweeper to cloud agent schedule — hourly cron that calls `draft_lifecycle.py` to archive expired drafts (>48h) to `Done/expired/` in `cloud/config.yaml`
- [x] T022 [US1] Implement Gmail read-only OAuth scope enforcement — validate cloud agent's token has only `gmail.readonly` scope, refuse to load if write scopes present in `agent-skills/core/security_boundary.py`

**Checkpoint**: Cloud agent creates draft email replies in `Drafts/email/` from incoming Gmail. Drafts expire after 48h.

---

## Phase 4: User Story 2 — Vault Sync Between Cloud and Local Agents (Priority: P1)

**Goal**: Reliable Git-based vault synchronization between cloud and local agents with 5-minute polling, conflict resolution rules, and offline resilience.

**Independent Test**: Write a file on the cloud vault, trigger sync, verify it appears on the local vault within 5 minutes (and vice versa).

### Implementation for User Story 2

- [x] T023 [US2] Extend vault-sync skill with Platinum Tier conflict resolution rules — add `Drafts/**` → cloud_wins, `Signals/**` → cloud_wins, `Approved/**` → local_wins, `Done/**` → local_wins per topology conflict_resolution config in `.claude/skills/vault-sync/vault_sync.py`
- [x] T024 [US2] Add SyncEvent logging — write `Logs/sync/{sync-id}.json` entries per data-model SyncEvent entity on each sync cycle in `.claude/skills/vault-sync/vault_sync.py`
- [x] T025 [P] [US2] Implement heartbeat writer — each agent writes `Signals/agents/{agent-id}.yaml` on every sync cycle per agent_identity_schema contract in `agent-skills/core/agent_identity.py`
- [x] T026 [US2] Add offline queue handling — detect accumulated changes during offline periods and process full queue on reconnection without data loss in `.claude/skills/vault-sync/vault_sync.py`
- [x] T027 [US2] Implement sync conflict flagging — write unresolvable conflicts to `Signals/sync/{conflict-id}.yaml` per sync_conflict_schema contract in `.claude/skills/vault-sync/vault_sync.py`
- [x] T028 [US2] Wire vault-sync into both `cloud/agent.py` and `local/agent.py` as a managed process with 5-minute interval in `cloud/agent.py` and `local/agent.py`

**Checkpoint**: Both agents sync their vault copies via Git. Conflicts are auto-resolved or flagged. Offline changes are queued and processed on reconnection.

---

## Phase 5: User Story 3 — Social Media Post Drafting and Approval Workflow (Priority: P2)

**Goal**: Cloud agent drafts social media posts based on business goals and content calendar. Local agent reviews, approves, and publishes.

**Independent Test**: Trigger a content generation cycle and verify drafts appear with correct platform formatting, then approve a draft and verify publication to a test/sandbox account.

### Implementation for User Story 3

- [x] T029 [US3] Implement social media draft generator — read Business_Goals.md + content calendar, create platform-formatted drafts in `Drafts/social/` with draft_schema frontmatter in `agent-skills/core/social_draft_generator.py`
- [x] T030 [P] [US3] Implement platform-specific formatters — LinkedIn (professional tone, hashtags), Twitter/X (280 char limit), Facebook (longer form) in `agent-skills/core/social_formatters.py`
- [x] T031 [US3] Add social draft generation to cloud agent schedule — configurable cron based on content calendar in `cloud/config.yaml`
- [x] T032 [US3] Extend local agent approval-manager to handle social-post draft type — approve moves to Approved/, reject syncs feedback to cloud for revision in `local/agent.py`
- [x] T033 [US3] Wire approved social posts to social-poster-mcp for publication via local agent in `local/agent.py`

**Checkpoint**: Cloud agent creates social media drafts. Local agent reviews, approves, and publishes to target platforms.

---

## Phase 6: User Story 4 — CEO Monday Morning Briefing (Priority: P2)

**Goal**: Cloud agent generates comprehensive Monday morning briefing documents covering revenue, task velocity, subscription analysis, and deadlines.

**Independent Test**: Trigger a briefing generation cycle and verify the output document contains all required sections.

### Implementation for User Story 4

- [x] T034 [US4] Extend ceo-briefing-generator to write output to `Drafts/briefings/` with draft_schema frontmatter and `type: briefing` in `.claude/skills/ceo-briefing-generator/briefing_generator.py`
- [x] T035 [US4] Add briefing data aggregator — collect revenue from accounting data, task velocity from project files, subscription waste from audit results in `agent-skills/core/briefing_aggregator.py`
- [x] T036 [US4] Configure Monday 7:00 AM schedule in cloud agent config with `cron: "0 7 * * 1"` in `cloud/config.yaml`
- [x] T037 [US4] Ensure briefing includes week-over-week and month-over-month comparisons for revenue, and highlights overdue tasks with owners in `agent-skills/core/briefing_aggregator.py`

**Checkpoint**: Briefings are auto-generated every Monday morning and placed in `Drafts/briefings/` for CEO review.

---

## Phase 7: User Story 5 — Lead Capture and Categorization (Priority: P2)

**Goal**: Cloud agent detects potential leads in emails, extracts key details, and creates structured lead files.

**Independent Test**: Send emails with lead-like content and verify categorized lead files appear with correct extracted details.

### Implementation for User Story 5

- [x] T038 [US5] Implement lead detector — analyze email content for lead signals (inquiry, RFP, partnership keywords), extract company/contact/request-type per data-model Lead entity in `agent-skills/core/lead_detector.py`
- [x] T039 [US5] Implement lead file writer — create structured files in `Needs_Action/cloud/leads/` with lead_schema frontmatter in `agent-skills/core/lead_detector.py`
- [x] T040 [US5] Wire lead detection into cloud agent's gmail-watcher pipeline — after email classification, check for lead signals before/alongside draft creation in `cloud/agent.py`
- [x] T041 [US5] Add lead status update handling in local agent — allow local agent to update lead status (new → reviewed → contacted → qualified → closed) in `local/agent.py`

**Checkpoint**: Leads are automatically captured from email, categorized, and surfaced for CEO review.

---

## Phase 8: User Story 6 — Payment and Banking Operations (Priority: P3)

**Goal**: Cloud agent prepares payment drafts from invoice data. Local agent approves and executes payments with mandatory approval and secondary confirmation for large amounts.

**Independent Test**: Create a payment draft, approve it, and verify execution against a sandbox payment endpoint.

### Implementation for User Story 6

- [x] T042 [US6] Implement payment draft creator — detect due invoices, create payment instruction drafts in `Drafts/payments/` with draft_schema frontmatter, amount, recipient, and context in `agent-skills/core/payment_draft_creator.py`
- [x] T043 [US6] Wire payment draft approval through local agent — approved payments route to payment-handler-mcp, receipts saved to `Done/payments/` in `local/agent.py`
- [x] T044 [US6] Implement secondary confirmation for payments exceeding threshold — configurable via `local/config.yaml` `approval.payment_secondary_threshold` in `agent-skills/core/payment_draft_creator.py`
- [x] T045 [US6] Add invoice due-date scanning to cloud agent schedule — periodic check for invoices due within 3 days in `cloud/config.yaml`

**Checkpoint**: Payment drafts are created from due invoices, approved by CEO with secondary confirmation for large amounts, and executed via local agent.

---

## Phase 9: User Story 7 — System Health Monitoring and Self-Healing (Priority: P3)

**Goal**: Cloud agent monitors its own health, auto-restarts crashed processes, and creates alerts for persistent failures.

**Independent Test**: Simulate a process crash and verify auto-restart, then simulate persistent failure and verify alert generation.

### Implementation for User Story 7

- [x] T046 [US7] Extend health-monitor to write alerts to `Signals/health/` with health_alert_schema frontmatter per contract in `.claude/skills/health-monitor/health_monitor.py`
- [x] T047 [US7] Wire health-monitor into cloud agent with configurable thresholds from `cloud/config.yaml` health section (CPU 80%, memory 80%, disk 90%) in `cloud/agent.py`
- [x] T048 [US7] Implement cloud VM resource monitoring — CPU, memory, disk usage checks specific to free-tier constraints (1 vCPU, 6GB RAM) in `.claude/skills/health-monitor/resource_checker.py`
- [x] T049 [US7] Add local agent health alert surfacing — read `Signals/health/` alerts after sync and display in dashboard in `local/agent.py`

**Checkpoint**: Cloud agent self-monitors, auto-restarts crashed processes, and alerts CEO for persistent failures.

---

## Phase 10: Dashboard Extensions

**Purpose**: Add new dashboard pages for Platinum Tier features

- [x] T050 [P] Create drafts review page — list pending drafts by type (email/social/payment/briefing), support approve/reject actions in `dashboard/src/app/drafts/page.tsx`
- [x] T051 [P] Create lead pipeline page — display leads by urgency and status, support status transitions in `dashboard/src/app/leads/page.tsx`
- [x] T052 [P] Create vault sync status page — show last sync times, file counts, conflicts, agent heartbeats in `dashboard/src/app/sync-status/page.tsx`
- [x] T053 [P] Create agent topology page — show cloud/local agent status, capabilities, uptime, heartbeat health in `dashboard/src/app/agent-topology/page.tsx`
- [x] T054 Add navigation links to all new pages in the dashboard sidebar layout in `dashboard/src/app/layout.tsx`

**Checkpoint**: Dashboard shows drafts, leads, sync status, and agent topology.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T055 [P] Add audit log hash-chain verification utility — validate integrity of `audit/{agent-id}-audit.jsonl` files in `agent-skills/core/audit_logger.py`
- [x] T056 [P] Create credential encryption helper — encrypt/decrypt `credentials/*.enc` files with configurable key in `agent-skills/core/credential_store.py`
- [x] T057 Implement draft rejection feedback loop — when local agent rejects a draft, cloud agent reads rejection feedback from `Done/` and can generate revised draft in `agent-skills/core/draft_lifecycle.py`
- [x] T058 Add configurable notification channels for critical alerts — vault file (default), optional email/push per FR-015 in `agent-skills/core/notification_router.py`
- [x] T059 [P] Create deployment guide with Docker Compose for cloud agent and setup script for local agent in `cloud/README.md` and `local/README.md`
- [x] T060 Run quickstart.md validation — execute all steps from quickstart.md and verify the system works end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1 Email Drafts (Phase 3)**: Depends on Foundational (Phase 2)
- **US2 Vault Sync (Phase 4)**: Depends on Foundational (Phase 2)
- **US3 Social Posts (Phase 5)**: Depends on Phase 2; integrates with US2 for sync
- **US4 CEO Briefing (Phase 6)**: Depends on Phase 2; benefits from US2 sync
- **US5 Lead Capture (Phase 7)**: Depends on Phase 2; extends US1 email pipeline
- **US6 Payments (Phase 8)**: Depends on Phase 2; integrates with US2 for sync
- **US7 Health Monitor (Phase 9)**: Depends on Phase 2
- **Dashboard (Phase 10)**: Can proceed in parallel with any user story after Phase 2
- **Polish (Phase 11)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1) Email Drafts**: No dependency on other stories — MVP story
- **US2 (P1) Vault Sync**: No dependency on other stories — foundational for cloud+local communication
- **US3 (P2) Social Posts**: Uses vault sync (US2) for draft delivery, but testable with manual file placement
- **US4 (P2) CEO Briefing**: Uses vault sync (US2) for briefing delivery, but testable locally
- **US5 (P2) Lead Capture**: Extends email pipeline (US1) with lead detection, but testable independently
- **US6 (P3) Payments**: Uses vault sync (US2) for draft/approval flow, but testable with manual files
- **US7 (P3) Health Monitor**: Fully independent — monitors processes regardless of other stories

### Within Each User Story

- Core modules before agent wiring
- Agent wiring before config updates
- Config updates before schedule integration

### Parallel Opportunities

- **Phase 1**: T002, T003, T004 can all run in parallel
- **Phase 2**: T007, T008, T010, T015, T016 can run in parallel; T011/T012 depend on T006-T009
- **Phase 3 & 4**: US1 and US2 can proceed in parallel after Phase 2
- **Phase 5-9**: US3, US4, US5, US6, US7 can all proceed in parallel after Phase 2
- **Phase 10**: All dashboard pages (T050-T053) can run in parallel

---

## Implementation Strategy

### MVP Scope

**User Story 1 (Email Drafts) + User Story 2 (Vault Sync)** — these two P1 stories together form the minimum viable product. With email monitoring and vault sync, the CEO gets the core value proposition: AI drafts responses to important emails, syncs them to the local machine, and the CEO approves before sending.

### Incremental Delivery

1. **Sprint 1 (MVP)**: Phase 1 + Phase 2 + US1 + US2 → Cloud monitors email, creates drafts, syncs to local
2. **Sprint 2**: US3 + US4 → Social media drafts and Monday briefings
3. **Sprint 3**: US5 + US6 → Lead capture and payment handling
4. **Sprint 4**: US7 + Dashboard + Polish → Health monitoring, full dashboard, production hardening

---

## Summary

| Metric | Value |
|--------|-------|
| **Total Tasks** | 60 |
| **Phase 1 (Setup)** | 5 tasks |
| **Phase 2 (Foundational)** | 11 tasks |
| **US1 — Email Drafts (P1)** | 6 tasks |
| **US2 — Vault Sync (P1)** | 6 tasks |
| **US3 — Social Posts (P2)** | 5 tasks |
| **US4 — CEO Briefing (P2)** | 4 tasks |
| **US5 — Lead Capture (P2)** | 4 tasks |
| **US6 — Payments (P3)** | 4 tasks |
| **US7 — Health Monitor (P3)** | 4 tasks |
| **Dashboard (Phase 10)** | 5 tasks |
| **Polish (Phase 11)** | 6 tasks |
| **Parallel Opportunities** | 23 tasks marked [P] |
| **MVP Scope** | US1 + US2 (22 tasks: Setup + Foundational + US1 + US2) |
