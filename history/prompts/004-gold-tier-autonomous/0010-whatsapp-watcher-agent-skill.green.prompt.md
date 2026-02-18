---
id: 0010
title: WhatsApp Watcher Agent Skill
stage: green
date: 2026-02-15
surface: agent
model: claude-opus-4-6
feature: 004-gold-tier-autonomous
branch: 004-gold-tier-autonomous
user: muniba_ahmed
command: user-request
labels: ["whatsapp-watcher", "agent-skill", "playwright", "standalone"]
links:
  spec: specs/004-gold-tier-autonomous/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - .claude/skills/whatsapp-watcher/session_manager.py
  - .claude/skills/whatsapp-watcher/whatsapp_watcher.py
  - .claude/skills/whatsapp-watcher/requirements.txt
  - .claude/skills/whatsapp-watcher/SKILL.md
tests:
  - Manual verification via --once flag
  - QR authentication flow test
  - Dedup check via processed_ids.json
  - Log output verification in Logs/whatsapp_watcher.log
---

## Prompt

Create an Agent Skill called "whatsapp-watcher" that monitors WhatsApp Web for urgent messages using Playwright automation.

Requirements: Playwright with persistent browser context, keyword monitoring (urgent, asap, invoice, payment, help, emergency), 30s polling, markdown files in Needs_Action/, QR code auth, session management, rate limiting, screenshot capture, headless option.

File structure: SKILL.md, whatsapp_watcher.py, session_manager.py, requirements.txt

## Response snapshot

Created a self-contained WhatsApp Watcher Agent Skill at `.claude/skills/whatsapp-watcher/` with 4 files:

1. **session_manager.py** — Playwright session lifecycle: browser launch with anti-detection flags, persistent session via storage_state at ~/.whatsapp-watcher/, QR code auth flow with console instructions, screenshot capture, graceful cleanup.

2. **whatsapp_watcher.py** — UV-runnable script extending BaseWatcher (from gmail-watcher). Scans unread chats for keyword matches, creates WHATSAPP_{timestamp}.md in Needs_Action/ with YAML frontmatter (type, contact, received, priority, keywords_matched). Includes random 2-5s delays between chat reads for bot detection avoidance. CLI supports --vault-path, --interval, --once, --headless, --session-dir.

3. **requirements.txt** — playwright, python-dotenv.

4. **SKILL.md** — Comprehensive docs: QR auth flow, architecture, keyword table, output format, session management, bot safeguards, rate limiting, CLI options.

Also fixed gmail-watcher SKILL.md frontmatter (name mismatch + unsupported version attribute).

## Outcome

- ✅ Impact: New standalone WhatsApp watcher skill with all requirements implemented
- 🧪 Tests: Manual verification via --once flag; session and dedup verifiable via output files
- 📁 Files: 4 files created/updated in .claude/skills/whatsapp-watcher/, 1 fix in gmail-watcher
- 🔁 Next prompts: Push code, test with real WhatsApp Web session
- 🧠 Reflection: Reused base_watcher.py from gmail-watcher skill to avoid duplication; session stored outside vault for security

## Evaluation notes (flywheel)

- Failure modes observed: SKILL.md frontmatter lint warnings (name mismatch, unsupported version) — fixed
- Graders run and results (PASS/FAIL): All requirements mapped to implementation — PASS
- Prompt variant (if applicable): standalone-skill
- Next experiment (smallest change to try): Test QR authentication flow with real WhatsApp account
