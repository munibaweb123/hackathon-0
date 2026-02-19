---
id: 24
title: Main Orchestrator Skill Completion
stage: green
date: 2026-02-18
surface: agent
model: claude-opus-4-6
feature: 004-gold-tier-autonomous
branch: 004-gold-tier-autonomous
user: human
command: complete skill
labels: ["main-orchestrator", "task-queue", "scheduler", "claude-cli", "orchestration"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .claude/skills/main-orchestrator/SKILL.md
  - .claude/skills/main-orchestrator/main_orchestrator.py
  - .claude/skills/main-orchestrator/task_queue.py
  - .claude/skills/main-orchestrator/scheduler.py
tests:
  - Manual verification of file structure and CLI interface
---

## Prompt

Check main-orchestrator skill, if its correct or not. (Found incomplete — only config.yaml and requirements.txt existed. User requested: "ok complete it".)

## Response snapshot

Completed the main-orchestrator skill by creating 4 missing files (config.yaml and requirements.txt already existed):

1. **`task_queue.py`** — `TaskQueue` class backed by vault's `Needs_Action/` folder. Priority classification by filename prefix (ALERT=0, WHATSAPP=1, EMAIL=2, FILE=3, TASK=4, NOTIFY=5) with YAML frontmatter fallback. Full task lifecycle: `scan()` → `pop()` → `claim()` (move to In_Progress/) → `complete()` (Done/) or `fail()` (error/ with annotation). YAML frontmatter parsing via `yaml.safe_load()`.

2. **`scheduler.py`** — `Scheduler` class with lightweight cron parsing (no APScheduler). Parses standard 5-field cron expressions with `*` wildcard and `*/N` step support. `check_and_run()` called each cycle, tracks `last_run_minute` to prevent duplicate execution. Jobs run via `subprocess.run()` with `{vault}` placeholder substitution and 10-minute timeout.

3. **`main_orchestrator.py`** — Main UV-runnable script (PEP 723, pyyaml). `MainOrchestrator` reads `config.yaml` for all settings. Each cycle: check schedules → scan queue → process up to `max_concurrent` tasks → update Dashboard → log. Task routing by filename prefix: ALERT/EMAIL/WHATSAPP → Claude CLI reasoning, EXECUTE/SEND/POST → mark complete for downstream skills, NOTIFY → log only. Claude invocation via `subprocess.run(["claude", "-p", prompt])`. Responses saved as `plans/PLAN_*.md`. Dashboard.md `## Orchestrator Status` section with queue depth, task counts, schedule info.

4. **`SKILL.md`** — Full documentation: architecture diagram, priority queue table, task routing table, cron scheduling reference, config.yaml format, Dashboard section format, CLI reference (7 flags), vault data sources.

## Outcome

- ✅ Impact: Completes the central orchestrator that ties all AI Employee skills together — task queue + cron scheduling + Claude CLI reasoning
- 🧪 Tests: Manual verification of file structure and CLI interface
- 📁 Files: 4 files created (2 already existed: config.yaml, requirements.txt)
- 🔁 Next prompts: Git commit, integration testing with actual vault tasks
- 🧠 Reflection: Chose subprocess delegation over direct imports to keep the skill standalone and decoupled from agent-skills/ Python modules

## Evaluation notes (flywheel)

- Failure modes observed: None — investigated existing orchestrator.py to understand pipeline before implementing
- Graders run and results (PASS/FAIL): PASS — all files match plan, config.yaml properly consumed
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): End-to-end test: drop a test EMAIL_*.md into Needs_Action/, run --once, verify it's claimed, processed, and moved to Done/
