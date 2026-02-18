---
id: 0011
title: Filesystem Watcher Agent Skill
stage: green
date: 2026-02-15
surface: agent
model: claude-opus-4-6
feature: 004-gold-tier-autonomous
branch: 004-gold-tier-autonomous
user: muniba_ahmed
command: user-request
labels: ["filesystem-watcher", "agent-skill", "watchdog", "standalone"]
links:
  spec: specs/004-gold-tier-autonomous/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - .claude/skills/filesystem-watcher/file_handler.py
  - .claude/skills/filesystem-watcher/filesystem_watcher.py
  - .claude/skills/filesystem-watcher/requirements.txt
  - .claude/skills/filesystem-watcher/SKILL.md
tests:
  - Manual verification via --once flag
  - Drop file test in separate terminal
  - Dedup and log verification
---

## Prompt

Create an Agent Skill called "filesystem-watcher" that monitors a designated drop folder for new files and creates action items. Requirements: watchdog for real-time monitoring, configurable drop folder, immediate trigger on file add, markdown files in Needs_Action/, copy to Attachments/, support common file types, ignore temp/hidden files, handle duplicates, cleanup after processing, configurable size limits.

## Response snapshot

Created a self-contained Filesystem Watcher Agent Skill at `.claude/skills/filesystem-watcher/` with 4 files:

1. **file_handler.py** — File validation (rejects hidden/temp/zero-byte/oversized), MIME detection via mimetypes.guess_type(), safe copy to Attachments/ with duplicate suffix handling (_1, _2), source cleanup.

2. **filesystem_watcher.py** — UV-runnable script extending BaseWatcher. Overrides run() with watchdog Observer (event-driven, not polling). DropFolderHandler triggers on_created for instant detection. Startup catchup processes existing files. Creates FILE_{name}.md in Needs_Action/ with YAML frontmatter + Obsidian wikilink to attachment. CLI: --vault-path, --drop-folder, --max-size, --once.

3. **requirements.txt** — watchdog, python-dotenv.

4. **SKILL.md** — Comprehensive docs: quick start, architecture diagram, supported file types, ignored files, output format, duplicate handling, CLI options, comparison with other watchers.

## Outcome

- ✅ Impact: New event-driven filesystem watcher skill with all requirements implemented
- 🧪 Tests: Manual verification via --once flag and live file drop test
- 📁 Files: 4 new files created in .claude/skills/filesystem-watcher/
- 🔁 Next prompts: Push code, test with real drop folder
- 🧠 Reflection: Event-driven watchdog pattern required overriding BaseWatcher.run() — different from polling-based gmail/whatsapp watchers

## Evaluation notes (flywheel)

- Failure modes observed: None — clean implementation
- Graders run and results (PASS/FAIL): All requirements mapped — PASS
- Prompt variant (if applicable): standalone-skill
- Next experiment (smallest change to try): Test with large file drop and verify size limit enforcement
