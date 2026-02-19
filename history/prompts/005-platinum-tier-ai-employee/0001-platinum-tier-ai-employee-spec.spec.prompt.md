---
id: "0001"
title: Platinum Tier AI Employee Spec
stage: spec
date: 2026-02-18
surface: agent
model: claude-opus-4-6
feature: 005-platinum-tier-ai-employee
branch: 005-platinum-tier-ai-employee
user: muniba_ahmed
command: /sp.specify
labels: ["spec", "platinum-tier", "cloud-local", "split-architecture", "ai-employee"]
links:
  spec: specs/005-platinum-tier-ai-employee/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/005-platinum-tier-ai-employee/spec.md
  - specs/005-platinum-tier-ai-employee/checklists/requirements.md
tests:
  - none
---

## Prompt

/sp.specify # Personal AI Employee - Platinum Tier Specification

## Project Overview
Build a production-grade, always-on AI Employee system with Cloud + Local split architecture. The system runs 24/7 with a cloud agent handling drafts and monitoring, while a local agent handles approvals and sensitive operations.

## Core Architecture Principles

### 1. Trust Boundary
- Cloud Agent: Untrusted zone - handles public data, creates drafts only
- Local Agent: Trusted zone - executes sensitive actions, holds secrets
- Rule: Cloud NEVER has access to WhatsApp sessions, banking credentials, or payment tokens

### 2. Work-Zone Specialization
Cloud Responsibilities (Always-On): Email monitoring, social media drafting, lead capture, report generation, health monitoring.
Local Responsibilities (When Available): All approvals, WhatsApp, payments, banking, secret management.

### 3. Communication Pattern
Agents communicate via synced Obsidian vault using file-based handoffs.

## Response snapshot

Created comprehensive feature specification for the Platinum Tier AI Employee with Cloud+Local split architecture. Generated branch `005-platinum-tier-ai-employee`, wrote spec.md with 7 user stories (P1: email monitoring + vault sync, P2: social media + briefings + leads, P3: payments + health), 15 functional requirements, 6 key entities, 10 measurable success criteria, 5 edge cases, plus assumptions/constraints/dependencies. Created and passed requirements quality checklist (all items green). No clarification markers needed — user description was comprehensive.

## Outcome

- ✅ Impact: Full feature spec created with 7 user stories, 15 FRs, 10 SCs covering Cloud+Local split architecture
- 🧪 Tests: Quality checklist passed all items on first iteration
- 📁 Files: spec.md, checklists/requirements.md created
- 🔁 Next prompts: /sp.clarify or /sp.plan to proceed to planning phase
- 🧠 Reflection: User description was detailed enough to avoid clarification markers. Trust boundary and work-zone specialization map cleanly to user stories.

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): Quality checklist — PASS (all items)
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): N/A
