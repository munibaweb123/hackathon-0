---
id: 22
title: Vault Sync Agent Skill
stage: green
date: 2026-02-18
surface: agent
model: claude-opus-4-6
feature: 004-gold-tier-autonomous
branch: 004-gold-tier-autonomous
user: human
command: create skill
labels: ["vault-sync", "git", "multi-agent", "conflict-resolution", "obsidian"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .claude/skills/vault-sync/SKILL.md
  - .claude/skills/vault-sync/vault_sync.py
  - .claude/skills/vault-sync/git_handler.py
  - .claude/skills/vault-sync/conflict_resolver.py
  - .claude/skills/vault-sync/.gitignore.template
  - .claude/skills/vault-sync/requirements.txt
tests:
  - Manual verification of file structure and CLI interface
---

## Prompt

Create an Agent Skill called 'vault-sync' that synchronizes Obsidian vault state between Cloud and Local agents. Requirements: Support two sync methods: Git (recommended) or Syncthing, Implement claim-by-move pattern to prevent duplicate work, Handle merge conflicts with defined strategies (local_wins, remote_wins, newest_wins, append_both), Dashboard.md single-writer rule (Local agent only), Cloud writes to /Updates/ which Local merges, Support offline operation with queue, Security: .gitignore template for secrets exclusion. Sync folder structure: Needs_Action/, In_Progress/{agent}/, Done/, Updates/, Signals/, pending-approval/, Approved/, Rejected/, Logs/, config/, Dashboard.md. Git sync implementation: commit + pull --no-rebase + resolve conflicts + push. Claim-by-move: first agent to move from Needs_Action/ to In_Progress/{agent}/ owns it, immediate commit+push prevents race conditions. File structure: SKILL.md, vault_sync.py, git_handler.py, conflict_resolver.py, .gitignore.template, requirements.txt.

## Response snapshot

Created the vault-sync skill with 6 files:

1. **`.gitignore.template`** — Template for vault security: excludes .env files, credentials, session data, keys, Obsidian workspace state, and transient processing folders.

2. **`conflict_resolver.py`** — `ConflictResolver` class with 4 strategies: `local_wins` (Dashboard.md), `remote_wins` (Cloud-written files), `newest_wins` (frontmatter timestamp comparison), `append_both` (log files with JSON array dedup). Uses regex-based conflict marker parsing and fnmatch glob-to-strategy rule mapping.

3. **`git_handler.py`** — `GitHandler` class wrapping git CLI via subprocess with 60s timeout. Operations: init, status (porcelain parsing), stage_all, commit (auto-message generation), pull (--no-rebase with conflict detection), push, full sync cycle, conflict resolution delegation.

4. **`vault_sync.py`** — Main UV-runnable script with PEP 723 header (pyyaml). `VaultSync` class: init (git repo + .gitignore + remote + folder structure), sync (full cycle + merge updates + dashboard), watch (continuous loop with SIGINT), claim-by-move (atomic move + commit + push), release (to Done/ or Needs_Action/), merge_updates (Cloud Updates/*.md → Dashboard.md), health_check, offline queue (Logs/sync_queue.json), dashboard status writer.

5. **`requirements.txt`** — pyyaml>=6.0

6. **`SKILL.md`** — Complete documentation: sync workflow diagram, claim-by-move pattern, conflict resolution rules table, folder structure, CLI reference (12 flags), offline operation, vault data sources, security (.gitignore contents).

## Outcome

- ✅ Impact: Enables multi-agent vault synchronization via Git with deterministic conflict resolution and race-condition-safe work claiming
- 🧪 Tests: Manual verification of file structure and CLI interface
- 📁 Files: 6 files created in .claude/skills/vault-sync/
- 🔁 Next prompts: Git commit of all new skills, integration testing with actual vault
- 🧠 Reflection: Chose subprocess over GitPython for zero extra deps; rules-based conflict resolution keeps sync deterministic without human intervention

## Evaluation notes (flywheel)

- Failure modes observed: None — all files created successfully. Explore agent hit rate limit during planning, worked around with direct tool calls.
- Graders run and results (PASS/FAIL): PASS — all 6 files match plan specification
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Add integration test that initializes a test vault, creates conflicts, and verifies resolution strategies
