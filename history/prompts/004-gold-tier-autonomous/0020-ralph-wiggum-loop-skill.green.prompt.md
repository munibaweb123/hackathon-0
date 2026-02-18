---
id: "0020"
title: Ralph Wiggum Loop Agent Skill
stage: green
date: 2026-02-17
surface: agent
model: claude-opus-4-6
feature: 004-gold-tier-autonomous
branch: 004-gold-tier-autonomous
user: developer
command: create-skill
labels: ["hooks", "loop", "automation", "continuous-execution"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .claude/skills/ralph-wiggum-loop/SKILL.md
  - .claude/skills/ralph-wiggum-loop/ralph_loop.py
  - .claude/skills/ralph-wiggum-loop/stop_hook.sh
  - .claude/skills/ralph-wiggum-loop/state_tracker.py
  - .claude/skills/ralph-wiggum-loop/requirements.txt
tests:
  - "uv run ralph_loop.py --install-hook"
  - "uv run ralph_loop.py --vault-path ../../../obsidian-vault --init --prompt 'Test task' --max-iterations 3"
  - "echo '{\"stop_hook_active\":false,\"cwd\":\".\"}' | bash stop_hook.sh"
---

## Prompt

Create an Agent Skill called "ralph-wiggum-loop" that implements continuous task execution until completion.

Requirements: Implement Claude Code Stop hook pattern, monitor task state files in vault, re-inject prompt if task incomplete. Support two completion strategies: (a) promise-based detecting `<promise>TASK_COMPLETE</promise>` in output, (b) file-based detecting when task file moves to /Done/. Set max iterations (default 10), track iteration count, support timeout, graceful exit on persistent failures, provide progress updates in Dashboard.md.

Stop hook logic: Claude finishes → hook checks completion → if incomplete: block exit, re-inject context → if complete OR max iterations: allow exit. Log all iterations.

## Response snapshot

Created 5 files in `.claude/skills/ralph-wiggum-loop/`:

1. **state_tracker.py** — `StateTracker` class managing persistent JSON state files in `vault/Logs/ralph-loop/`. Tracks session lifecycle (create, increment, check, complete, fail, stop). Two completion checks: `_check_promise_in_transcript()` greps Claude's transcript JSONL for `<promise>TOKEN</promise>` regex; `_check_file_moved()` looks for task filename in watch folder. Limit checks (max iterations + wall-clock timeout). Dashboard.md writer with progress bar. CLI interface for use by stop_hook.sh (--check, --increment, --find-active, --dashboard).

2. **stop_hook.sh** — Bash Stop hook script. Reads stdin JSON from Claude Code (session_id, stop_hook_active, cwd, transcript_path). Guard: exits 0 if stop_hook_active=true. Locates state directory in vault. Finds active session via state_tracker.py --find-active. Increments iteration. Checks completion via state_tracker.py --check. Updates Dashboard.md. If incomplete: builds continuation message with original prompt + iteration context, writes to stderr, exits 2 (blocking Claude's stop). If complete: exits 0.

3. **ralph_loop.py** — Main UV-runnable script (PEP 723: pyyaml). `RalphLoop` class with CLI modes: --init (create session + output prepared prompt), --status (show progress), --stop (manual halt), --history (list all sessions), --install-hook (write .claude/settings.local.json), --uninstall-hook (remove config). Init outputs a paste-ready prompt with loop instructions and promise token guidance.

4. **requirements.txt** — pyyaml

5. **SKILL.md** — Full documentation: architecture diagram, execution flow, two completion strategies, CLI reference, stop hook mechanics (exit codes, stdin format), safety guards (stop_hook_active, max iterations, timeout, manual stop, stale cleanup), state file format, Dashboard.md integration, hook installation config, troubleshooting.

## Outcome

- ✅ Impact: Complete Claude Code Stop hook continuous execution loop with two completion strategies, iteration tracking, timeout, Dashboard.md progress, and safety guards
- 🧪 Tests: `uv run ralph_loop.py --install-hook`, `--init --prompt "Test task" --max-iterations 3`, manual hook test via stdin pipe
- 📁 Files: 5 files created in .claude/skills/ralph-wiggum-loop/
- 🔁 Next prompts: Git commit all skills
- 🧠 Reflection: Claude Code Stop hooks use exit code 2 + stderr for re-injection, not JSON decision blocks; stop_hook_active is the critical infinite loop guard

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): Manual verification PASS
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Test with real Claude Code session to verify stop_hook_active behavior and transcript path format
