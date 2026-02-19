---
id: "0003"
title: Platinum Tier Architecture Plan
stage: plan
date: 2026-02-18
surface: agent
model: claude-opus-4-6
feature: 005-platinum-tier-ai-employee
branch: 005-platinum-tier-ai-employee
user: muniba_ahmed
command: /sp.plan
labels: ["plan", "architecture", "cloud-local", "split-agent", "vault-sync", "trust-boundary"]
links:
  spec: specs/005-platinum-tier-ai-employee/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/005-platinum-tier-ai-employee/plan.md
  - specs/005-platinum-tier-ai-employee/research.md
  - specs/005-platinum-tier-ai-employee/data-model.md
  - specs/005-platinum-tier-ai-employee/quickstart.md
  - specs/005-platinum-tier-ai-employee/contracts/vault-file-schema.yaml
  - specs/005-platinum-tier-ai-employee/contracts/agent-config-schema.yaml
  - CLAUDE.md
tests:
  - none
---

## Prompt

/sp.plan

Generate the implementation plan for the Platinum Tier AI Employee feature (005-platinum-tier-ai-employee). Execute Phase 0 (research) and Phase 1 (design & contracts) following the plan template structure.

## Response snapshot

Completed full Phase 0 + Phase 1 planning:

**Phase 0 — Research (research.md):** Resolved 7 research topics: cloud VM deployment strategy (Oracle Cloud Always-Free ARM), Git sync implementation (reuse vault-sync with enhanced conflict rules), read-only OAuth scope configuration (gmail.readonly + platform read scopes), agent identity protocol (file-based in Signals/agents/), draft file format (YAML frontmatter + Markdown), security boundary enforcement (application-level path validation), and dashboard extension strategy (4 new Next.js pages).

**Phase 1 — Design (plan.md, data-model.md, contracts/, quickstart.md):**
- Plan: Technical context, constitution check (all 8 gates PASS), project structure (cloud/ + local/ split with symlinked skills), 5 architecture decisions (AD-1 through AD-5)
- Data model: 7 entities (Agent, Draft, Approval, Lead, SyncEvent, HealthCheck, AuditEntry) with full field definitions, file locations, writers, lifecycles, and validation rules
- Contracts: vault-file-schema.yaml (6 file type schemas + write permissions matrix) and agent-config-schema.yaml (cloud config, local config, topology config)
- Quickstart: Step-by-step setup guide for both agents + dashboard + architecture diagram
- Agent context: Updated CLAUDE.md with Platinum Tier tech stack

**Key architecture decisions:**
1. Symlink-based skill assignment (no code duplication)
2. Zone-scoped vault write paths (application-level enforcement)
3. 48-hour draft expiration with archival
4. Read-only credential scope for cloud agent
5. Git sync as sole inter-agent transport (5-min polling)

~70% of Gold Tier codebase is reusable. New work: agent identity, topology, draft lifecycle, security boundary, deployment automation, 4 dashboard pages.

## Outcome

- ✅ Impact: Complete architecture plan with all Phase 0+1 artifacts — ready for task generation
- 🧪 Tests: Constitution check PASS (all 8 gates), post-design re-check PASS
- 📁 Files: 6 files created (plan.md, research.md, data-model.md, quickstart.md, 2 contracts), CLAUDE.md updated
- 🔁 Next prompts: /sp.tasks to generate implementation tasks
- 🧠 Reflection: The existing Gold Tier vault-sync skill is the linchpin — it already implements the Git-based claim-by-move pattern needed for multi-agent coordination. The main new work is the security boundary and agent topology, not the sync mechanism itself.

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): Constitution gate PASS (pre-design), Constitution re-check PASS (post-design)
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): N/A
