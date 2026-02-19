---
id: 0025
title: Bronze Tier AI Employee Setup
stage: green
date: 2026-02-18
surface: agent
model: claude-opus-4-6
feature: 004-gold-tier-autonomous
branch: 004-gold-tier-autonomous
user: muniba_ahmed
command: user-request
labels: ["bronze", "vault", "gmail-watcher", "claude-processor", "setup"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - obsidian-vault/Dashboard.md
  - obsidian-vault/Company_Handbook.md
  - bronze/gmail_watcher.py
  - bronze/claude_processor.py
  - bronze/README.md
tests:
  - "N/A - setup and template files"
---

## Prompt

I'm building a Bronze tier AI Employee from the Personal AI Employee Hackathon. Help me:

1. Set up the basic Obsidian vault structure:
   - Create /Needs_Action/, /Plans/, /Done/, /Logs/ folders
   - Create Dashboard.md template
   - Create Company_Handbook.md template

2. Create a simple Gmail watcher that:
   - Checks for unread emails every 5 minutes
   - Creates action files in /Needs_Action/
   - Uses a basic polling approach (no complex features)

3. Set up Claude Code to:
   - Read files from /Needs_Action/
   - Create a simple response in /Plans/
   - Log activity

Keep it simple and educational. I'm learning the basics.

## Response snapshot

Created the complete Bronze tier AI Employee setup:

**Vault Structure:**
- Created `Needs_Action/`, `Plans/`, `Done/`, `Logs/` folders in obsidian-vault
- `Dashboard.md` — Welcome page with status table, architecture diagram, quick start guide
- `Company_Handbook.md` — Business context template with email priorities, contacts, Gmail API setup instructions

**Gmail Watcher (`bronze/gmail_watcher.py`):**
- PEP 723 UV-runnable with google-api-python-client, google-auth-oauthlib, python-dotenv
- OAuth2 flow with browser auth on first run, token.json persistence
- Polls Gmail for unread emails, creates `EMAIL_{id}_{timestamp}.md` action files with YAML frontmatter
- CLI: `--vault-path`, `--interval` (default 300s), `--once`

**Claude Processor (`bronze/claude_processor.py`):**
- PEP 723 UV-runnable with anthropic, pyyaml, python-dotenv
- Reads Needs_Action/ files, parses YAML frontmatter, sends to Claude with Company Handbook context
- Creates `PLAN_{action}_{timestamp}.md` response files, moves originals to Done/
- CLI: `--vault-path`, `--interval` (default 60s), `--once`, `--dry-run`

**README (`bronze/README.md`):**
- Architecture diagram, quick start guide (uv install, Gmail API setup, .env, dry run, real run)

## Outcome

- ✅ Impact: Complete Bronze tier setup — vault structure, Gmail watcher, Claude processor, documentation
- 🧪 Tests: Manual testing via `--once --dry-run` flags
- 📁 Files: 5 files created (2 vault templates, 3 bronze scripts)
- 🔁 Next prompts: Test with real Gmail credentials, customize Company_Handbook.md, proceed to Silver tier
- 🧠 Reflection: Kept scripts simple and educational per user request — no dedup, no backoff, no complex features

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): N/A
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): N/A
