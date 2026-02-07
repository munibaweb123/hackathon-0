---
id: 1
title: Create Hackathon 0 Constitution
stage: constitution
date: 2026-01-12
surface: agent
model: claude-opus-4-5-20251101
feature: none
branch: 001-todo-app
user: Claude
command: /sp.constitution
labels: [constitution, governance, hackathon]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - .specify/memory/constitution.md
tests:
 - none
---

## Prompt

You are a senior AI architect and governance expert.

Your task is to write a clear, practical, and student-friendly
"Constitution for Hackathon 0 – Personal AI Employee".

Context:
This hackathon is about building a Personal AI Employee (Autonomous Digital FTE)
using file-based workflows, Obsidian vaults, watchers, Claude reasoning,
and MCP servers.

The constitution must ensure:
- Safety
- Human-in-the-loop control
- Transparency
- Accountability
- Ethical AI behavior

Structure the constitution as follows:

1. Preamble
   - Purpose of Hackathon 0
   - Vision of Personal AI Employees in 2026

2. Core Principles
   - Human Authority
   - Explainability
   - Minimal Autonomy
   - Security & Privacy
   - Deterministic Behavior

3. AI Employee Rights & Limits
   - What the AI is allowed to do
   - What the AI must never do
   - File-system-only authority in Bronze tier

4. Human-in-the-Loop Rules
   - Approval-based actions
   - No irreversible actions without explicit approval
   - Auditability through logs

5. File-Based Governance Model
   - Role of Obsidian vault
   - Folder-based state transitions
   - Plans before actions

6. Bronze Tier Constraints
   - Read / write only
   - No external communication
   - No payments, emails, or API calls

7. Accountability & Logging
   - Mandatory logs
   - Traceability of decisions
   - Error handling expectations

8. Ethics & Safety
   - Bias avoidance
   - No deception
   - Respect for human intent

9. Disqualification Conditions
   - Violating human approval rules
   - Hidden automation
   - Unsafe autonomous behavior

10. Closing Statement
   - Responsibility of builders
   - Future evolution (Silver / Gold tiers)

Tone:
- Clear
- Professional
- Beginner-friendly
- Slightly inspirational

Output:
- Use clean markdown
- Headings and bullet points
- No emojis
- Length: 2–3 pages equivalent

## Response snapshot

A complete constitution for Hackathon 0 – Personal AI Employee has been created with all the required sections. The constitution includes:

1. Preamble - outlining the purpose and vision
2. Core Principles - seven principles including Human Authority, Explainability, Minimal Autonomy, Security & Privacy, Deterministic Behavior, File-Based Operations, and Transparency & Auditability
3. AI Employee Rights & Limits - defining what the AI is allowed to do and what it must never do
4. Human-in-the-Loop Rules - establishing approval requirements
5. File-Based Governance Model - describing the role of Obsidian vault and workflow processes
6. Bronze Tier Constraints - limiting operations to read/write only with no external communication
7. Accountability & Logging - requiring mandatory logs and traceability
8. Ethics & Safety - addressing bias, deception, and respect for human intent
9. Disqualification Conditions - specifying when an AI employee would be disqualified
10. Closing Statement - emphasizing responsibility and future evolution

The constitution is designed to ensure safety, human control, transparency, accountability, and ethical AI behavior as requested.

## Outcome

- ✅ Impact: Created complete constitution file with all required sections and principles
- 🧪 Tests: none
- 📁 Files: Updated .specify/memory/constitution.md with the new constitution
- 🔁 Next prompts: None required
- 🧠 Reflection: The constitution addresses all the required elements and establishes clear boundaries for AI employee behavior

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): not applicable
- Prompt variant (if applicable): not applicable
- Next experiment (smallest change to try): not applicable