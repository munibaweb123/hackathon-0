---
name: vault-sync
description: Synchronizes Obsidian vault state between Cloud and Local agents via Git. Implements claim-by-move pattern, rules-based conflict resolution, Dashboard.md single-writer enforcement, and offline queue support.
tools: []
tags:
  - sync
  - git
  - vault
  - python
  - multi-agent
---

# Vault Sync

Synchronizes the Obsidian vault between Cloud and Local agents using Git. Provides claim-by-move work assignment, rules-based conflict resolution, Dashboard.md single-writer enforcement, and offline queue support.

## Quick Start

```bash
# 1. Initialize vault as git repo
uv run vault_sync.py --vault-path ../../obsidian-vault --init --remote git@github.com:user/vault.git

# 2. One-shot sync
uv run vault_sync.py --vault-path ../../obsidian-vault --sync

# 3. Continuous sync (every 60s)
uv run vault_sync.py --vault-path ../../obsidian-vault --watch --interval 60
```

## Architecture

```
vault-sync/
├── vault_sync.py              # Main UV-runnable script (orchestrator)
├── git_handler.py             # Git CLI wrapper (subprocess)
├── conflict_resolver.py       # Rules-based merge conflict resolution
├── .gitignore.template        # Template .gitignore for vault
├── requirements.txt
└── SKILL.md
```

## Sync Workflow

```
LOCAL AGENT                                   CLOUD AGENT
     |                                             |
     |  1. File changes in vault                   |
     |  2. vault_sync --sync                       |
     |     a) git add -A                           |
     |     b) git commit "auto: ..."               |
     |     c) git pull origin main                 |
     |     d) Resolve conflicts (rules-based)      |
     |     e) git push origin main                 |
     |                                             |
     |  <------- Git Remote ------->               |
     |                                             |
     |                    1. git pull origin main   |
     |                    2. Process Needs_Action/  |
     |                    3. Write to Updates/      |
     |                    4. git add + commit + push|
     |                                             |
     |  3. Next sync pulls Cloud changes           |
     |  4. merge_updates() -> Dashboard.md         |
```

## Claim-by-Move Pattern

Prevents duplicate work across agents:

```bash
# Agent claims a task (atomic: move + commit + push)
uv run vault_sync.py --vault-path ../../obsidian-vault \
  --claim Needs_Action/task.md --agent cloud-1

# File is now at In_Progress/cloud-1/task.md
# Other agents see it there and skip it

# When done, release to Done/
uv run vault_sync.py --vault-path ../../obsidian-vault \
  --release In_Progress/cloud-1/task.md --agent cloud-1 --done
```

**Rule:** First agent to move from `Needs_Action/` to `In_Progress/{agent}/` owns it. Claim immediately commits + pushes to prevent race conditions.

## Folder Structure

```
obsidian-vault/
├── Needs_Action/<domain>/     # Unclaimed work items
├── In_Progress/<agent>/       # Claimed items (one subfolder per agent)
├── Done/                      # Completed items (globally visible)
├── Updates/                   # Cloud writes here; Local merges into Dashboard
├── Signals/                   # Cloud writes status updates here
├── pending-approval/          # HITL approval requests
├── Approved/                  # Human-approved items
├── Rejected/                  # Human-rejected items
├── Logs/                      # Sync logs, event history
├── config/                    # Shared configuration
└── Dashboard.md               # Single-writer: LOCAL only
```

## Conflict Resolution Rules

| Pattern | Strategy | Rationale |
|---------|----------|-----------|
| `Dashboard.md` | `local_wins` | Single-writer: Local agent owns Dashboard |
| `Logs/*.json` | `append_both` | Preserve log entries from both agents |
| `config/*` | `remote_wins` | Cloud pushes config updates |
| `Updates/*.md` | `remote_wins` | Cloud writes update files |
| `In_Progress/**` | `local_wins` | Claiming agent owns the file |
| `*` (default) | `newest_wins` | Compare frontmatter timestamps |

### Strategy Details

- **local_wins**: Keep LOCAL (ours) version, discard remote changes
- **remote_wins**: Keep REMOTE (theirs) version, discard local changes
- **newest_wins**: Compare frontmatter date fields, keep newer version
- **append_both**: Merge both versions (dedup JSON arrays, concatenate text)

## Dashboard.md Single-Writer Rule

- **Local agent** is the sole writer of `Dashboard.md`
- **Cloud agent** writes status updates to `Updates/*.md`
- During sync, `--merge-updates` reads `Updates/*.md` and merges sections into `Dashboard.md`
- Conflict resolution: `Dashboard.md` always uses `local_wins` strategy

```bash
# Merge Cloud updates into Dashboard.md
uv run vault_sync.py --vault-path ../../obsidian-vault --merge-updates
```

## Security: .gitignore

The `.gitignore.template` excludes sensitive files:

- `.env*` (secrets, API keys)
- `**/credentials*.json`, `**/token*.json`
- `**/*.key`, `**/*.pem` (certificates)
- `**/session.json`, `**/session_data/` (WhatsApp, browser sessions)
- `.obsidian/workspace.json` (Obsidian UI state — causes conflicts)
- `processing/`, `retry-queue/` (transient, agent-local)

Copied to vault root on `--init`. Customize as needed.

## CLI Reference

```
Initialization:
  --init                    Initialize vault as git repo
  --remote URL              Git remote URL (with --init)

Sync:
  --sync                    One-shot sync cycle (commit + pull + resolve + push)
  --watch                   Continuous sync loop
  --interval N              Seconds between syncs (default: 60)

Claim-by-Move:
  --claim FILE              Claim file (move to In_Progress/{agent}/)
  --release FILE            Release file
  --agent NAME              Agent name (required with --claim/--release)
  --done                    Release to Done/ (with --release)

Updates:
  --merge-updates           Merge Cloud Updates/*.md into Dashboard.md

Status:
  --status                  Show sync status summary
  --health                  Detailed health check

Common:
  --vault-path PATH         Obsidian vault path (default: ./obsidian-vault)
  --verbose, -v             Debug logging
```

## Offline Operation

Changes are queued in `Logs/sync_queue.json` when the remote is unreachable. The queue is flushed on the next successful sync. Local vault operations (claim, release, file edits) continue working offline — they just don't push until connectivity is restored.

## Vault Data Sources

| Source | Read/Write | Purpose |
|--------|------------|---------|
| `Needs_Action/` | Read | Work items to claim |
| `In_Progress/{agent}/` | Read/Write | Claimed items |
| `Done/` | Write | Completed items |
| `Updates/*.md` | Read | Cloud-written dashboard updates |
| `Signals/` | Read | Cloud status signals |
| `Dashboard.md` | Write | Single-writer (Local only) |
| `Logs/vault_sync.json` | Write | Sync event log |
| `Logs/sync_queue.json` | Read/Write | Offline queue |
| `.gitignore` | Write | Sensitive file exclusions |

## Dependencies

- Python 3.10+
- `pyyaml` — YAML support
- `git` — must be on PATH (no GitPython dependency)

All declared in PEP 723 script header for automatic UV resolution.
