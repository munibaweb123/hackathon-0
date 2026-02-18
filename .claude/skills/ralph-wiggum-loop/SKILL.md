---
name: ralph-wiggum-loop
description: Continuous task execution loop using Claude Code Stop hooks. Keeps Claude running until a task is complete via promise tokens or file-based detection, with max iteration and timeout safeguards.
tools: []
tags:
  - hooks
  - loop
  - automation
  - python
  - continuous-execution
---

# Ralph Wiggum Loop

Continuous task execution skill that uses Claude Code's **Stop hook** to keep Claude running in a loop until a task is complete. When Claude finishes processing, the hook intercepts, checks completion criteria, and either allows exit or re-injects context for the next iteration.

## Quick Start

```bash
# 1. Install the stop hook (one-time)
uv run ralph_loop.py --install-hook

# 2. Initialize a loop session
uv run ralph_loop.py --vault-path ../../obsidian-vault \
  --init --prompt "Build a hello world app, test it, and verify output" \
  --completion-promise "TASK_COMPLETE" --max-iterations 5

# 3. Paste the output prompt into Claude Code — the loop runs automatically

# 4. Monitor progress
uv run ralph_loop.py --vault-path ../../obsidian-vault --status SESSION_ID
```

## Architecture

```
ralph-wiggum-loop/
├── ralph_loop.py          # Main UV-runnable script (initializer + manager)
├── stop_hook.sh           # Claude Code Stop hook (bash)
├── state_tracker.py       # State management (iterations, timing, completion)
├── requirements.txt
└── SKILL.md
```

## How It Works

```
┌──────────────────────────────────────────────────────┐
│  1. User runs: ralph_loop.py --init --prompt "..."   │
│  2. Creates state file in vault/Logs/ralph-loop/     │
│  3. Outputs prepared prompt for Claude Code          │
└──────────────────┬───────────────────────────────────┘
                   v
┌──────────────────────────────────────────────────────┐
│  4. User pastes prompt into Claude Code              │
│  5. Claude processes the task                        │
│  6. Claude finishes → Stop event fires               │
│  7. stop_hook.sh reads stdin JSON from Claude Code   │
└──────────────────┬───────────────────────────────────┘
                   v
┌──────────────────────────────────────────────────────┐
│  8. Hook checks:                                     │
│     a) stop_hook_active? → exit 0 (prevent nesting)  │
│     b) Find active session in state files            │
│     c) Increment iteration counter                   │
│     d) Check completion (promise token / file move)  │
│     e) Check limits (max iterations / timeout)       │
└──────────────────┬───────────────────────────────────┘
            ┌──────┴──────┐
            │  Complete?   │
            └──────┬──────┘
         yes ──────┼────── no
         │                 │
    exit 0            exit 2 + stderr
    (Claude stops)    (re-inject → Claude continues)
                           │
                      Back to step 5
```

## Completion Strategies

### Promise-Based (default)

Claude outputs a promise token when the task is done:

```
--init --prompt "Build feature X" --completion-promise "TASK_COMPLETE"
```

Claude must output `<promise>TASK_COMPLETE</promise>` in its response to signal completion. The hook greps the transcript file for this pattern.

### File-Based

The hook watches for a file to appear in a specific folder:

```
--init --task-file Needs_Action/task.md --watch-folder Done/
```

Completion is detected when the task file's name appears in the watch folder (e.g., when another skill or human moves it to Done/).

## CLI Reference

```
Initialization:
  --init                          Start a new loop session
  --prompt TEXT                   The task prompt for the loop
  --task-file PATH                Read task from file instead of --prompt
  --completion-promise TOKEN      Promise token (default: TASK_COMPLETE)
  --watch-folder PATH             Watch folder for file-based completion
  --max-iterations N              Max iterations (default: 10)
  --timeout SECONDS               Max total time (default: 3600)

Session Management:
  --status SESSION_ID             Show loop status
  --stop SESSION_ID               Manually stop a running loop
  --history                       Show all past sessions

Hook Management:
  --install-hook                  Install stop hook in .claude/settings.local.json
  --uninstall-hook                Remove stop hook

Common:
  --vault-path PATH               Obsidian vault path (default: ./obsidian-vault)
  --verbose, -v                   Debug logging
```

## Stop Hook Mechanics

The stop hook (`stop_hook.sh`) uses Claude Code's hook system:

| Input | Source | Purpose |
|-------|--------|---------|
| `stop_hook_active` | stdin JSON | If `true`, a hook already re-injected — exit immediately to prevent infinite nesting |
| `session_id` | stdin JSON | Current Claude Code session identifier |
| `transcript_path` | stdin JSON | Path to the session transcript (for promise token grep) |
| `cwd` | stdin JSON | Working directory |

| Exit Code | Meaning |
|-----------|---------|
| `0` | Allow Claude to stop (task complete, limits reached, or no active session) |
| `2` | Block stop — stderr content becomes Claude's next instruction |

## Safety Guards

1. **stop_hook_active check** — Claude Code sets this `true` when a hook already re-injected. The hook exits immediately to prevent infinite nesting.
2. **Max iterations** — Hard cap (default 10) prevents runaway loops.
3. **Timeout** — Wall-clock limit (default 3600s) stops stale sessions.
4. **Manual stop** — `--stop SESSION_ID` immediately marks session as stopped.
5. **Stale cleanup** — Sessions running >24h are auto-marked as failed.
6. **No active session = exit 0** — Hook is a no-op when no loop is running.

## State Files

State is persisted in `vault/Logs/ralph-loop/{session_id}.json`:

```json
{
  "session_id": "abc12345",
  "prompt": "original task prompt",
  "completion_strategy": "promise",
  "promise_token": "TASK_COMPLETE",
  "max_iterations": 10,
  "timeout_seconds": 3600,
  "current_iteration": 3,
  "status": "running",
  "iterations": [
    {"iteration": 1, "timestamp": "...", "status": "started"},
    {"iteration": 2, "timestamp": "...", "status": "started"},
    {"iteration": 3, "timestamp": "...", "status": "started"}
  ]
}
```

## Dashboard Integration

The loop updates `vault/Dashboard.md` with a progress table on each iteration:

```markdown
## Ralph Wiggum Loop Status

| Field | Value |
|-------|-------|
| Session | `abc12345` |
| Status | 🔄 running |
| Progress | `[████████░░░░░░░░░░░░]` 40% |
| Iteration | 4 / 10 |
| Strategy | promise |
```

## Hook Installation

The hook is configured in `.claude/settings.local.json` (not committed to repo):

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": ".claude/skills/ralph-wiggum-loop/stop_hook.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

Install automatically with `uv run ralph_loop.py --install-hook`.

## Vault Data Sources

| Source | Read/Write | Purpose |
|--------|------------|---------|
| `Logs/ralph-loop/*.json` | Read/Write | Session state files |
| `Dashboard.md` | Write | Progress updates |
| Claude transcript | Read | Promise token detection |
| `Done/` (or custom) | Read | File-based completion detection |

## Dependencies

- Python 3.10+
- `pyyaml` — YAML support
- `jq` — not required (Python used for JSON parsing in hook)
- Bash — for stop_hook.sh

All declared in PEP 723 script header for automatic UV resolution.

## Troubleshooting

**Hook not firing?**
- Run `--install-hook` and restart Claude Code
- Check `.claude/settings.local.json` exists with correct hook config
- Run with `claude --debug` to see hook execution

**Infinite loop?**
- The `stop_hook_active` guard should prevent this
- Use `--stop SESSION_ID` to manually stop
- Delete the state file from `vault/Logs/ralph-loop/`

**Hook errors?**
- Test manually: `echo '{"stop_hook_active":false,"cwd":"."}' | bash stop_hook.sh`
- Check that Python 3 is available on PATH
- Ensure stop_hook.sh is executable (`chmod +x`)
