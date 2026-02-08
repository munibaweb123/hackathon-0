# Tasks: Silver Tier — Functional Assistant

**Input**: Design documents from `/specs/003-silver-tier-assistant/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Not explicitly requested in spec. Test tasks are omitted unless needed for acceptance criteria.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US7)
- Include exact file paths in descriptions

## Path Conventions

- **Python Backend**: `agent-skills/` (watchers, MCP server, skills, scheduler)
- **Bronze Foundation**: `src/` (existing, extend as needed)
- **Dashboard**: `dashboard/src/` (Next.js)
- **Vault**: `obsidian-vault/` (file storage)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and Silver Tier configuration

- [x] T001 Create vault folders for Silver Tier in obsidian-vault/config/, obsidian-vault/plans/, obsidian-vault/posts/
- [x] T002 Add Silver Tier dependencies to requirements.txt (playwright, apscheduler, anthropic)
- [x] T003 [P] Create .env.example with OAuth placeholders in repository root
- [x] T004 [P] Add watcher event JSON schema validation to agent-skills/core/schema_validator.py
- [x] T005 [P] Create config/watchers.yaml template in obsidian-vault/config/watchers.yaml
- [x] T006 [P] Create config/schedules.yaml template in obsidian-vault/config/schedules.yaml
- [x] T007 Update dashboard/.env.local with LinkedIn OAuth configuration

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T008 Extend BaseSkill class with async execute pattern in agent-skills/core/base_skill.py
- [x] T009 [P] Create Event model dataclass in agent-skills/models/event.py per data-model.md
- [x] T010 [P] Create Plan model dataclass in agent-skills/models/plan.py per data-model.md
- [x] T011 [P] Create ApprovalRequest model dataclass in agent-skills/models/approval_request.py per data-model.md
- [x] T012 [P] Create Schedule model dataclass in agent-skills/models/schedule.py per data-model.md
- [x] T013 [P] Create Post model dataclass in agent-skills/models/post.py per data-model.md
- [x] T014 Implement vault file reader/writer for structured events in agent-skills/core/vault_interface.py
- [x] T015 [P] Create TypeScript types for Event, Plan, ApprovalRequest in dashboard/src/lib/types.ts
- [x] T016 [P] Configure APScheduler base setup in agent-skills/scheduler/task_scheduler.py
- [x] T017 Add error handling middleware to MCP server in agent-skills/mcp_server/server.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Multi-Channel Monitoring via Watchers (Priority: P1) 🎯 MVP

**Goal**: Enable AI Employee to monitor Gmail, LinkedIn, and WhatsApp, creating structured event files in the vault

**Independent Test**: Connect Gmail/LinkedIn accounts, send a test email, verify event file appears in vault inbox within polling interval

### Implementation for User Story 1

- [x] T018 [P] [US1] Complete Gmail watcher OAuth integration in agent-skills/watchers/gmail_watcher.py
- [x] T019 [P] [US1] Complete LinkedIn watcher OAuth integration in agent-skills/watchers/linkedin_watcher.py
- [x] T020 [US1] Create WhatsApp watcher with Playwright automation in agent-skills/watchers/whatsapp_watcher.py
- [x] T021 [US1] Implement QR code session management for WhatsApp in agent-skills/watchers/whatsapp_watcher.py
- [x] T022 [P] [US1] Add mock mode to all watchers for testing without credentials
- [x] T023 [US1] Implement event file creation following contracts/watcher-events.schema.json in agent-skills/watchers/watcher_base.py
- [x] T024 [P] [US1] Add watcher error handling with graceful fallback to mock mode
- [x] T025 [US1] Implement incremental sync (history ID tracking) for Gmail watcher
- [x] T026 [P] [US1] Create dashboard Gmail status page in dashboard/src/app/gmail/page.tsx
- [x] T027 [P] [US1] Create dashboard LinkedIn status page in dashboard/src/app/linkedin/page.tsx
- [x] T028 [US1] Create dashboard WhatsApp status page with QR display in dashboard/src/app/whatsapp/page.tsx
- [x] T029 [P] [US1] Create WhatsApp live component in dashboard/src/components/whatsapp-live.tsx
- [x] T030 [US1] Add watcher status indicators to dashboard home in dashboard/src/app/page.tsx

**Checkpoint**: Watchers detect external events and create vault files. User Story 1 complete and testable.

---

## Phase 4: User Story 5 - Human-in-the-Loop Approval Workflow (Priority: P1)

**Goal**: Enable human review and approval/rejection of AI-proposed actions via file-based workflow

**Independent Test**: Trigger sensitive action, verify APPROVAL_REQUIRED file appears in pending-approval, move to Approved folder, confirm action state changes

### Implementation for User Story 5

- [x] T031 [US5] Implement approval file generator per data-model.md format in agent-skills/core/approval_generator.py
- [x] T032 [US5] Create approval folder watcher (Approved/Rejected detection) in agent-skills/watchers/approval_watcher.py
- [x] T033 [P] [US5] Add 24-hour expiry check for pending approvals in agent-skills/core/approval_validator.py
- [x] T034 [US5] Implement approval status change detection and action triggering in agent-skills/core/approval_processor.py
- [x] T035 [P] [US5] Create ApprovalMonitorSkill in agent-skills/skills/approval_monitor_skill.py
- [x] T036 [US5] Extend dashboard approvals page with file operations in dashboard/src/app/approvals/page.tsx
- [x] T037 [P] [US5] Add API route for approval actions (approve/reject) in dashboard/src/app/api/approvals/[id]/route.ts
- [x] T038 [US5] Implement reminder notification for 24h+ pending approvals
- [x] T039 [P] [US5] Add approval history logging to vault audit log

**Checkpoint**: Approval workflow operational. Actions require and respect human consent. User Story 5 complete.

---

## Phase 5: User Story 2 - Automated LinkedIn Posting for Business Sales (Priority: P1)

**Goal**: Generate business-relevant LinkedIn content and publish after human approval

**Independent Test**: Trigger post creation, verify content generated, approve via workflow, confirm post appears on LinkedIn

### Implementation for User Story 2

- [x] T040 [US2] Create LinkedInContentSkill for post generation in agent-skills/skills/linkedin_content_skill.py
- [x] T041 [P] [US2] Add business profile settings to dashboard in dashboard/src/app/settings/page.tsx
- [x] T042 [US2] Implement LinkedIn post action in MCP server per contracts/mcp-server-api.yaml in agent-skills/mcp_server/actions/linkedin_action.py
- [x] T043 [US2] Add /execute/linkedin_post endpoint to MCP server in agent-skills/mcp_server/server.py
- [x] T044 [P] [US2] Create Post entity file management in agent-skills/core/post_manager.py
- [x] T045 [US2] Implement post status tracking (draft→pending_approval→approved→published) in agent-skills/models/post.py
- [x] T046 [P] [US2] Add LinkedIn post creation UI to dashboard in dashboard/src/app/linkedin/page.tsx
- [x] T047 [US2] Implement rate limit handling for LinkedIn API (429 response) in agent-skills/mcp_server/actions/linkedin_action.py
- [x] T048 [P] [US2] Add post logging with LinkedIn post ID to vault audit log

**Checkpoint**: LinkedIn posting works end-to-end with approval. User Story 2 complete.

---

## Phase 6: User Story 3 - Claude Reasoning Loop with Plan.md Generation (Priority: P2)

**Goal**: Analyze incoming events via Claude and generate structured Plan.md files with recommended actions

**Independent Test**: Place test event file in vault inbox, verify Plan.md generated with context, analysis, and action checkboxes

### Implementation for User Story 3

- [x] T049 [US3] Implement ReasoningSkill with Claude tool use in agent-skills/skills/reasoning_skill.py
- [x] T050 [P] [US3] Create EventTriageSkill for priority/routing in agent-skills/skills/event_triage_skill.py
- [x] T051 [US3] Implement PlanningSkill for Plan.md generation in agent-skills/skills/planning_skill.py
- [x] T052 [US3] Create reasoning loop orchestrator in agent-skills/core/reasoning_loop.py
- [x] T053 [P] [US3] Add event grouping logic for related events in agent-skills/core/reasoning_loop.py
- [x] T054 [US3] Implement "request clarification" plan type for ambiguous events
- [x] T055 [P] [US3] Create Plan.md file writer following data-model.md format in agent-skills/core/plan_writer.py
- [x] T056 [US3] Connect reasoning loop to inbox watcher (event → plan pipeline) in agent-skills/core/reasoning_loop.py
- [x] T057 [P] [US3] Add plans folder view to dashboard in dashboard/src/app/plans/page.tsx
- [x] T058 [US3] Add Claude API timeout handling and retry logic

**Checkpoint**: Reasoning loop transforms events into actionable plans. User Story 3 complete.

---

## Phase 7: User Story 4 - MCP Server for External Actions (Priority: P2)

**Goal**: Execute approved external actions (email, LinkedIn, WhatsApp) through controlled MCP server

**Independent Test**: Submit approved email action to MCP server, verify email sent to recipient

### Implementation for User Story 4

- [x] T059 [US4] Implement approval validation middleware per contracts/mcp-server-api.yaml in agent-skills/mcp_server/approval_validator.py
- [x] T060 [P] [US4] Implement /execute/email_send endpoint in agent-skills/mcp_server/server.py
- [x] T061 [P] [US4] Implement /execute/whatsapp_reply endpoint in agent-skills/mcp_server/server.py
- [x] T062 [US4] Implement email send action with Gmail API in agent-skills/mcp_server/actions/email_action.py
- [x] T063 [US4] Implement WhatsApp reply action with Playwright in agent-skills/mcp_server/actions/whatsapp_action.py
- [x] T064 [P] [US4] Add /actions/{action_id} GET endpoint for result retrieval in agent-skills/mcp_server/server.py
- [x] T065 [P] [US4] Add /health and /status endpoints per contract in agent-skills/mcp_server/server.py
- [x] T066 [US4] Connect approval watcher to MCP execution (approved → execute) in agent-skills/core/approval_processor.py
- [x] T067 [P] [US4] Add MCP server status to dashboard home in dashboard/src/app/page.tsx
- [x] T068 [US4] Implement action result logging with tamper-evident hashes

**Checkpoint**: MCP server executes approved actions with full audit trail. User Story 4 complete.

---

## Phase 8: User Story 7 - Agent Skills Architecture (Priority: P2)

**Goal**: Implement all AI capabilities as modular, independently testable Agent Skills

**Independent Test**: Invoke single skill (e.g., ReasoningSkill) with test input, verify expected output without other skills

### Implementation for User Story 7

- [x] T069 [US7] Create skill registry for dynamic skill loading in agent-skills/core/skill_registry.py
- [x] T070 [P] [US7] Add input/output schema validation to BaseSkill in agent-skills/core/base_skill.py
- [x] T071 [US7] Implement CommunicationSkill for draft content in agent-skills/skills/communication_skill.py
- [x] T072 [P] [US7] Implement ExecutionSkill for action execution in agent-skills/skills/execution_skill.py
- [x] T073 [US7] Create skill composition utility for workflows in agent-skills/core/skill_composer.py
- [x] T074 [P] [US7] Add skill error handling with graceful degradation in agent-skills/core/base_skill.py
- [x] T075 [US7] Create CLI commands for skill invocation in agent-skills/cli/main.py
- [x] T076 [P] [US7] Document skill interface in agent-skills/README.md

**Checkpoint**: Skills are modular, independently testable, and composable. User Story 7 complete.

---

## Phase 9: User Story 6 - Task Scheduling (Priority: P3)

**Goal**: Enable scheduled execution of watchers and content generation

**Independent Test**: Configure Gmail polling every 5 minutes, wait two cycles, verify events created at expected intervals

### Implementation for User Story 6

- [x] T077 [US6] Implement interval-based scheduling in agent-skills/scheduler/task_scheduler.py
- [x] T078 [P] [US6] Implement cron-based scheduling in agent-skills/scheduler/task_scheduler.py
- [x] T079 [US6] Connect scheduler to watcher polling in agent-skills/scheduler/task_scheduler.py
- [x] T080 [US6] Connect scheduler to daily LinkedIn post generation
- [x] T081 [P] [US6] Add schedule persistence (resume after restart) in agent-skills/scheduler/task_scheduler.py
- [x] T082 [US6] Implement stale approval reminder job (24h+ pending)
- [x] T083 [P] [US6] Create scheduler configuration UI in dashboard/src/app/settings/page.tsx
- [x] T084 [US6] Add health check scheduled job (verify watcher status)
- [x] T085 [P] [US6] Add scheduler status to dashboard home in dashboard/src/app/page.tsx

**Checkpoint**: Scheduled tasks run autonomously. User Story 6 complete.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T086 [P] Add comprehensive error messages for OAuth failures
- [x] T087 [P] Add rate limit indicators to dashboard status
- [x] T088 Implement vault disk space monitoring and alerts
- [x] T089 [P] Add event processing metrics to dashboard
- [x] T090 Run quickstart.md validation end-to-end
- [x] T091 [P] Add dark mode support to dashboard
- [x] T092 Security review: verify no credentials stored in code
- [x] T093 [P] Add export functionality for audit logs

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup ─────────────────────────────────────────────────────────────────┐
                                                                                │
Phase 2: Foundational ◀────────────────────────────────────────────────────────┘
     │
     │ BLOCKS ALL USER STORIES
     ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                                                                                │
│   Phase 3: US1 Watchers (P1) ──────┬───────────────────────────────────────▶  │
│                                    │                                          │
│   Phase 4: US5 Approvals (P1) ◀────┘  (watchers create events that need       │
│        │                               approval workflow)                      │
│        │                                                                       │
│        ▼                                                                       │
│   Phase 5: US2 LinkedIn Posts (P1) ──▶ Depends on US5 (approval workflow)     │
│                                                                                │
│   Phase 6: US3 Reasoning (P2) ───────▶ Depends on US1 (events to reason about)│
│        │                                                                       │
│        ▼                                                                       │
│   Phase 7: US4 MCP Server (P2) ──────▶ Depends on US5 (approved actions)      │
│                                                                                │
│   Phase 8: US7 Skills (P2) ──────────▶ Can run in parallel with US3/US4       │
│                                                                                │
│   Phase 9: US6 Scheduling (P3) ──────▶ Depends on US1 (watchers to schedule)  │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
     │
     ▼
Phase 10: Polish ────────────────────────────────────────────────────────────────▶
```

### User Story Dependencies

| Story | Priority | Can Start After | Dependencies |
|-------|----------|-----------------|--------------|
| US1: Watchers | P1 | Foundational | None |
| US5: Approvals | P1 | Foundational | None (but integrates with US1 events) |
| US2: LinkedIn | P1 | US5 | Needs approval workflow |
| US3: Reasoning | P2 | US1 | Needs events to process |
| US4: MCP Server | P2 | US5 | Needs approval validation |
| US7: Skills | P2 | Foundational | None (architecture) |
| US6: Scheduling | P3 | US1 | Needs watchers to schedule |

### Within Each User Story

- Models/entities before services
- Services before endpoints/UI
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

**Setup Phase (T001-T007)**:
- T003, T004, T005, T006, T007 can all run in parallel

**Foundational Phase (T008-T017)**:
- T009, T010, T011, T012, T013 (all models) can run in parallel
- T015, T016, T017 can run in parallel after models

**User Story Phases**:
- All tasks marked [P] within a story can run in parallel
- US1 and US5 can start in parallel after Foundational
- US7 (Skills) can run in parallel with US3, US4

---

## Parallel Example: User Story 1 (Watchers)

```bash
# Launch all platform-specific watchers together:
Task: "Complete Gmail watcher OAuth integration in agent-skills/watchers/gmail_watcher.py"
Task: "Complete LinkedIn watcher OAuth integration in agent-skills/watchers/linkedin_watcher.py"

# After watchers are done, launch dashboard pages together:
Task: "Create dashboard Gmail status page in dashboard/src/app/gmail/page.tsx"
Task: "Create dashboard LinkedIn status page in dashboard/src/app/linkedin/page.tsx"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 5 + 2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: US1 Watchers → Test independently
4. Complete Phase 4: US5 Approvals → Test independently
5. Complete Phase 5: US2 LinkedIn → Test end-to-end
6. **STOP and VALIDATE**: Watchers detect events, approvals work, LinkedIn posts publish
7. Deploy/demo MVP

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 (Watchers) → Test → "AI can see external world"
3. US5 (Approvals) → Test → "Human oversight operational"
4. US2 (LinkedIn) → Test → **MVP Complete** (business value!)
5. US3 (Reasoning) → Test → "AI makes intelligent recommendations"
6. US4 (MCP Server) → Test → "AI can take approved actions"
7. US7 (Skills) → Test → "Modular architecture"
8. US6 (Scheduling) → Test → "Autonomous operation"
9. Polish → Production ready

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (Watchers) + US6 (Scheduling)
   - Developer B: US5 (Approvals) + US4 (MCP Server)
   - Developer C: US2 (LinkedIn) + US3 (Reasoning)
   - Developer D: US7 (Skills Architecture)
3. Stories integrate via file-based vault interface

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- File-based architecture enables parallel development without conflicts
