---
id: 4
title: Platinum Tier Task Generation
stage: tasks
date: 2026-02-18
surface: agent
model: claude-opus-4-6
feature: 005-platinum-tier-ai-employee
branch: 004-gold-tier-autonomous
user: human
command: /sp.tasks
labels: ["tasks", "platinum-tier", "cloud-local-split", "task-generation"]
links:
  spec: specs/005-platinum-tier-ai-employee/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/005-platinum-tier-ai-employee/tasks.md
tests:
  - N/A — task generation, no tests
---

## Prompt

/sp.tasks — Generate an actionable, dependency-ordered tasks.md for the Platinum Tier AI Employee feature (005-platinum-tier-ai-employee) based on spec.md, plan.md, data-model.md, research.md, contracts/, and quickstart.md.

## Response snapshot

Generated `specs/005-platinum-tier-ai-employee/tasks.md` with 60 tasks organized across 11 phases:

- **Phase 1 (Setup)**: 5 tasks — vault structure, cloud/local dirs, topology.yaml
- **Phase 2 (Foundational)**: 11 tasks — agent_identity, security_boundary, topology, draft_lifecycle, audit_logger, agent entry points, configs, Docker, systemd
- **Phase 3 (US1 Email Drafts, P1)**: 6 tasks — gmail-watcher draft output, priority classifier, draft reply generator, scope enforcement, expiration sweeper
- **Phase 4 (US2 Vault Sync, P1)**: 6 tasks — conflict resolution rules, SyncEvent logging, heartbeat, offline queue, conflict flagging
- **Phase 5 (US3 Social Posts, P2)**: 5 tasks — social draft generator, platform formatters, approval flow, publication
- **Phase 6 (US4 CEO Briefing, P2)**: 4 tasks — briefing output to Drafts/, data aggregator, Monday schedule
- **Phase 7 (US5 Lead Capture, P2)**: 4 tasks — lead detector, lead file writer, pipeline wiring, status updates
- **Phase 8 (US6 Payments, P3)**: 4 tasks — payment draft creator, approval flow, secondary confirmation, due-date scanning
- **Phase 9 (US7 Health Monitor, P3)**: 4 tasks — Signals/health/ alerts, cloud resource monitoring, alert surfacing
- **Phase 10 (Dashboard)**: 5 tasks — drafts, leads, sync-status, agent-topology pages + nav
- **Phase 11 (Polish)**: 6 tasks — audit verification, credential encryption, rejection feedback, notifications, deployment guide, quickstart validation

MVP scope: US1 + US2 = 22 tasks. 23 tasks marked [P] for parallel execution.

## Outcome

- ✅ Impact: Complete task breakdown for Platinum Tier feature — ready for /sp.implement
- 🧪 Tests: Not requested — test tasks omitted per spec
- 📁 Files: 1 file created (tasks.md)
- 🔁 Next prompts: /sp.implement to begin execution, or /sp.analyze to validate consistency
- 🧠 Reflection: Organized by user story with clear phase dependencies. MVP defined as US1+US2 (email drafts + vault sync) — the minimum for demonstrating cloud+local split value.

## Evaluation notes (flywheel)

- Failure modes observed: None — all design documents were complete and consistent
- Graders run and results (PASS/FAIL): PASS — all 60 tasks have ID, [P] marker where applicable, [US] story label for story phases, and file paths
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Run /sp.analyze to validate spec-plan-tasks consistency before implementation
