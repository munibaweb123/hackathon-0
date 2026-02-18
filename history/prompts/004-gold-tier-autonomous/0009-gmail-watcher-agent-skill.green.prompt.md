---
id: 0009
title: Gmail Watcher Agent Skill
stage: green
date: 2026-02-15
surface: agent
model: claude-opus-4-6
feature: 004-gold-tier-autonomous
branch: 004-gold-tier-autonomous
user: muniba_ahmed
command: user-request
labels: ["gmail-watcher", "agent-skill", "oauth2", "standalone"]
links:
  spec: specs/004-gold-tier-autonomous/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - agent-skills/skills/gmail-watcher/base_watcher.py
  - agent-skills/skills/gmail-watcher/gmail_watcher.py
  - agent-skills/skills/gmail-watcher/.env.example
  - agent-skills/skills/gmail-watcher/requirements.txt
  - agent-skills/skills/gmail-watcher/SKILL.md
tests:
  - Manual verification via --once flag
  - Dedup check via processed_ids.json
  - Log output verification in Logs/gmail_watcher.log
---

## Prompt

Create an Agent Skill called "gmail-watcher" that monitors Gmail for important unread emails and creates action files in an Obsidian vault.

Requirements:
- Use Gmail API with OAuth2 authentication
- Poll every 2 minutes for unread emails marked as "important"
- Create markdown files in /Needs_Action/ folder with format: EMAIL_{message_id}.md
- Include frontmatter with: type, from, subject, received, priority, status
- Extract email body snippet
- Suggest actions as checkboxes (reply, forward, archive)
- Track processed email IDs to avoid duplicates
- Handle API rate limits with exponential backoff
- Log all activity to vault_path/Logs/gmail_watcher.log

The skill should follow the BaseWatcher pattern and be runnable as a standalone Python script using UV for dependency management.

File structure:
- SKILL.md (comprehensive documentation)
- gmail_watcher.py (main script)
- base_watcher.py (abstract base class)
- requirements.txt (dependencies)
- .env.example (credential template)

## Response snapshot

Created a self-contained Gmail Watcher Agent Skill at `agent-skills/skills/gmail-watcher/` with 5 files:

1. **base_watcher.py** — Standalone ABC with polling loop, RotatingFileHandler logging, JSON-based dedup (processed_ids.json), and exponential backoff with jitter for HTTP 429/5xx errors. Zero external dependencies (stdlib only).

2. **gmail_watcher.py** — UV-runnable script (with `/// script` header) that extends BaseWatcher. Authenticates via OAuth2 using shared `gmail-token.json`, queries `is:unread label:IMPORTANT`, creates `EMAIL_{message_id}.md` markdown files in `Needs_Action/` with YAML frontmatter (type, from, subject, received, priority, status), 500-char body snippets, and action checkboxes. CLI supports `--vault-path`, `--interval`, and `--once`.

3. **.env.example** — Minimal template with GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, VAULT_PATH.

4. **requirements.txt** — google-api-python-client, google-auth, google-auth-oauthlib, python-dotenv.

5. **SKILL.md** — Comprehensive documentation covering quick start (UV + pip), prerequisites, architecture diagram, output format, dedup mechanism, error handling, API rate limits, and comparison with existing watcher.

## Outcome

- ✅ Impact: New standalone Gmail watcher skill with all 9 requirements implemented
- 🧪 Tests: Manual verification via `--once` flag; dedup and logging verifiable via output files
- 📁 Files: 5 new files created in agent-skills/skills/gmail-watcher/
- 🔁 Next prompts: Push code, test with real Gmail credentials
- 🧠 Reflection: Self-contained design (own base class) avoids coupling to project internals while reusing proven OAuth token path resolution

## Evaluation notes (flywheel)

- Failure modes observed: None — clean implementation
- Graders run and results (PASS/FAIL): All requirements mapped to implementation — PASS
- Prompt variant (if applicable): standalone-skill
- Next experiment (smallest change to try): Test with real Gmail API credentials via --once flag
