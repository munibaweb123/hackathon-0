---
id: 2
title: Create AI Employee Spec
stage: spec
date: 2026-01-12
surface: agent
model: claude-opus-4-5-20251101
feature: ai-employee
branch: 001-ai-employee
user: Claude
command: /sp.specify
labels: [specification, ai-employee, bronze-tier]
links:
  spec: specs/001-ai-employee/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/001-ai-employee/spec.md
 - specs/001-ai-employee/system.md
 - specs/001-ai-employee/agent.md
 - specs/001-ai-employee/workflows.md
 - specs/001-ai-employee/constraints.md
 - specs/001-ai-employee/approval_model.md
 - specs/001-ai-employee/logging.md
 - specs/001-ai-employee/compliance.md
 - specs/001-ai-employee/checklists/requirements.md
tests:
 - none
---

## Prompt

You are a senior systems architect and specification engineer.

Your task is to write a complete, formal, and implementation-ready
SPECIFICATION for "Hackathon 0 - Personal AI Employee".

This specification will be used with a spec-driven development tool
(such as specifyplus) and must clearly define system behavior,
constraints, and workflows BEFORE any code is written.

CONTEXT:
The system is a Personal AI Employee (Digital FTE) that operates using:
- Local Obsidian vault (file-based memory and UI)
- Claude Code as the reasoning engine
- Python Watchers for perception
- Human-in-the-loop approval
- No autonomous external actions in Bronze tier

TARGET TIER:
Bronze Tier (Foundation)

REQUIREMENTS:
Write the specification in clean Markdown and organize it into the
following sections and files (as if they live inside a /specs folder).

------------------------------------------------
1. system.md
------------------------------------------------
Include:
- System purpose and scope
- Non-goals (explicit exclusions)
- High-level architecture
- Operating assumptions
- Definitions (Agent, Watcher, Vault, Human)

------------------------------------------------
2. agent.md
------------------------------------------------
Include:
- Agent identity and role
- Capabilities (what the agent can do)
- Limitations (what the agent must not do)
- Deterministic behavior rules
- Input and output formats (files only)

------------------------------------------------
3. workflows.md
------------------------------------------------
Include:
- File intake workflow
- Reasoning workflow
- Planning workflow
- Human review workflow
- State transitions between folders
- Error handling at spec level

------------------------------------------------
4. constraints.md
------------------------------------------------
Include:
- Bronze tier restrictions
- Security boundaries
- No-network and no-action guarantees
- Human authority overrides
- Failure-safe defaults

------------------------------------------------
5. approval_model.md
------------------------------------------------
Include:
- Human-in-the-loop philosophy
- Approval file format
- Explicit prohibition of auto-execution
- Review responsibility

------------------------------------------------
6. logging.md
------------------------------------------------
Include:
- What must be logged
- Where logs are stored
- Purpose of logs (audit, debugging)
- No hidden actions rule

------------------------------------------------
7. compliance.md
------------------------------------------------
Include:
- Ethical principles
- Transparency requirements
- Disqualification conditions
- Alignment with Hackathon 0 goals

------------------------------------------------
STYLE & TONE:
- Precise
- Unambiguous
- Judge-friendly
- Beginner-readable
- No emojis
- No marketing language

OUTPUT RULES:
- Use Markdown headings
- Bullet points where appropriate
- Each section must be explicit and testable
- Assume this spec will be reviewed before any code is allowed

Write the specification as if it will be enforced strictly.

## Response snapshot

A complete specification for the Personal AI Employee (Bronze Tier) has been created with all required sections. The specification includes:

1. system.md - System overview with purpose, scope, architecture, and definitions
2. agent.md - Agent capabilities, limitations, and behavior rules
3. workflows.md - Detailed workflows for file intake, reasoning, planning, and state transitions
4. constraints.md - Bronze tier restrictions and security boundaries
5. approval_model.md - Human-in-the-loop approval requirements and processes
6. logging.md - Comprehensive logging requirements and transparency rules
7. compliance.md - Ethical principles and disqualification conditions

The specification adheres to all requirements with precise, unambiguous language suitable for enforcement. All sections are explicit and testable as required.

## Outcome

- ✅ Impact: Created complete specification with all required components
- 🧪 Tests: none
- 📁 Files: Created specs/001-ai-employee/ directory with all specification files
- 🔁 Next prompts: Ready for planning phase (/sp.plan)
- 🧠 Reflection: The specification comprehensively covers all required aspects of the AI employee system

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): not applicable
- Prompt variant (if applicable): not applicable
- Next experiment (smallest change to try): not applicable