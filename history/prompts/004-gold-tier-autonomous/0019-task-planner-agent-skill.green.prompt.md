---
id: "0019"
title: Task Planner Agent Skill
stage: green
date: 2026-02-17
surface: agent
model: claude-opus-4-6
feature: 004-gold-tier-autonomous
branch: 004-gold-tier-autonomous
user: developer
command: create-skill
labels: ["planning", "tasks", "python", "dependencies", "approval"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .claude/skills/task-planner/SKILL.md
  - .claude/skills/task-planner/task_planner.py
  - .claude/skills/task-planner/dependency_resolver.py
  - .claude/skills/task-planner/templates/plan_template.md
  - .claude/skills/task-planner/requirements.txt
tests:
  - "uv run task_planner.py --vault-path ../../../obsidian-vault --plan 'Build landing page with contact form, deploy to production, and send announcement email'"
---

## Prompt

Create an Agent Skill called "task-planner" that breaks complex requests into actionable steps.

Requirements: Analyze Needs_Action/ requests or CLI input, decompose into sub-tasks, create TASKPLAN.md files in /plans/, checkbox format, dependency resolution with topological sort, time/resource estimates, HITL approval flagging for high-risk actions, phase-based grouping (Setup → Core → Test → Deploy → Communicate), progress tracking, archive to /Done/.

File structure: SKILL.md, task_planner.py, dependency_resolver.py, templates/plan_template.md, requirements.txt.

## Response snapshot

Created 5 files in `.claude/skills/task-planner/`:

1. **dependency_resolver.py** — `DependencyResolver` class using Kahn's algorithm for topological sort. Validates dependency graphs (cycle detection, missing deps, self-references). `get_parallel_groups()` identifies concurrent task levels. `get_critical_path(time_estimates)` finds the longest dependency chain with cumulative time.

2. **task_planner.py** — Main UV-runnable orchestrator (PEP 723: jinja2, python-dotenv, pyyaml). `TaskPlanner` class with 6 CLI modes: `--plan` (decompose request text), `--plan-file` (read from file), `--detect` (scan Needs_Action/), `--progress` (check completion), `--update` (mark task done), `--archive` (move to Done/). Heuristic decomposition: splits on sentence boundaries/commas/conjunctions, classifies into 5 phases, auto-assigns inter-phase dependencies, keyword-based time estimates and risk assessment. Renders ASCII dependency graph and Gantt-like timeline.

3. **templates/plan_template.md** — Jinja2 template with YAML frontmatter (progress tracking fields), phase-grouped task checkboxes with dependency annotations, inline time/risk indicators, dependency graph, timeline, approval checkpoints, progress summary table.

4. **requirements.txt** — jinja2, python-dotenv, pyyaml.

5. **SKILL.md** — Full documentation with workflow diagram, CLI modes, phase classification table, risk assessment matrix, time estimation defaults, dependency resolution explanation, vault data sources.

## Outcome

- ✅ Impact: Complete task decomposition engine with dependency ordering, time estimates, risk assessment, HITL approval, progress tracking, and archival
- 🧪 Tests: `uv run task_planner.py --vault-path ../../../obsidian-vault --plan "Build landing page with contact form, deploy to production, and send announcement email"`
- 📁 Files: 5 files created in .claude/skills/task-planner/
- 🔁 Next prompts: None specified
- 🧠 Reflection: Kahn's algorithm provides clean parallel group identification as a free byproduct of topological sort; heuristic decomposition is deterministic and API-free unlike LLM-based approaches

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): Manual verification PASS
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Add configurable time estimates via vault config file; test with complex multi-paragraph requests
