#!/usr/bin/env bash
# ============================================================================
# Ralph Wiggum Loop — Claude Code Stop Hook
# ============================================================================
#
# This script is invoked by Claude Code when it finishes responding (Stop event).
# It checks whether the current task is complete and either:
#   - Allows Claude to stop (exit 0)
#   - Re-injects context for the next iteration (exit 2 + stderr message)
#
# Hook config goes in .claude/settings.local.json:
#   {
#     "hooks": {
#       "Stop": [{ "hooks": [{ "type": "command",
#         "command": ".claude/skills/ralph-wiggum-loop/stop_hook.sh" }] }]
#     }
#   }
#
# Input (stdin): JSON with session_id, stop_hook_active, cwd, transcript_path
# Output: exit 0 = allow stop; exit 2 = block stop (stderr = next instruction)
# ============================================================================

set -euo pipefail

# ---- Read hook input from stdin ----
INPUT=$(cat)

# ---- Extract fields from JSON ----
STOP_HOOK_ACTIVE=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(str(data.get('stop_hook_active', False)).lower())
" 2>/dev/null || echo "false")

CWD=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('cwd', '.'))
" 2>/dev/null || echo ".")

TRANSCRIPT_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('transcript_path', ''))
" 2>/dev/null || echo "")

# ---- Guard: prevent infinite hook nesting ----
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
    exit 0
fi

# ---- Locate state directory ----
# Try common vault locations relative to CWD
SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_DIR=""

# Check for state dir in known vault paths
for candidate in \
    "$CWD/obsidian-vault/Logs/ralph-loop" \
    "$CWD/../obsidian-vault/Logs/ralph-loop" \
    "$SKILL_DIR/../../../obsidian-vault/Logs/ralph-loop"; do
    if [ -d "$candidate" ]; then
        STATE_DIR="$candidate"
        break
    fi
done

# No state directory → no loop running → allow stop
if [ -z "$STATE_DIR" ]; then
    exit 0
fi

# ---- Find active session ----
ACTIVE_RESULT=$(python3 "$SKILL_DIR/state_tracker.py" \
    --state-dir "$STATE_DIR" \
    --find-active 2>/dev/null || echo '{"found": false}')

FOUND=$(echo "$ACTIVE_RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(str(data.get('found', False)).lower())
" 2>/dev/null || echo "false")

if [ "$FOUND" != "true" ]; then
    exit 0
fi

SESSION_ID=$(echo "$ACTIVE_RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('session_id', ''))
" 2>/dev/null || echo "")

if [ -z "$SESSION_ID" ]; then
    exit 0
fi

# ---- Increment iteration counter ----
python3 "$SKILL_DIR/state_tracker.py" \
    --state-dir "$STATE_DIR" \
    --increment "$SESSION_ID" >/dev/null 2>&1 || true

# ---- Check completion ----
CHECK_RESULT=$(python3 "$SKILL_DIR/state_tracker.py" \
    --state-dir "$STATE_DIR" \
    --check "$SESSION_ID" \
    --transcript "$TRANSCRIPT_PATH" 2>/dev/null || echo '{"complete": true, "reason": "check_error"}')

COMPLETE=$(echo "$CHECK_RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(str(data.get('complete', True)).lower())
" 2>/dev/null || echo "true")

REASON=$(echo "$CHECK_RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('reason', 'unknown'))
" 2>/dev/null || echo "unknown")

ITERATION=$(echo "$CHECK_RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('iteration', 0))
" 2>/dev/null || echo "0")

MAX_ITER=$(echo "$CHECK_RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('max', 10))
" 2>/dev/null || echo "10")

# ---- Update dashboard ----
# Resolve vault path from state dir (Logs/ralph-loop -> vault root)
VAULT_PATH=$(dirname "$(dirname "$STATE_DIR")")
python3 "$SKILL_DIR/state_tracker.py" \
    --state-dir "$STATE_DIR" \
    --dashboard "$SESSION_ID" "$VAULT_PATH" >/dev/null 2>&1 || true

# ---- Decision ----
if [ "$COMPLETE" = "true" ]; then
    # Task complete or limits reached — allow Claude to stop
    exit 0
fi

# ---- Read original prompt for context ----
ORIGINAL_PROMPT=$(python3 -c "
import json, sys
state_file = '$STATE_DIR/$SESSION_ID.json'
with open(state_file) as f:
    state = json.load(f)
prompt = state.get('prompt', 'Continue the task.')
# Truncate if very long
if len(prompt) > 500:
    prompt = prompt[:500] + '...'
print(prompt)
" 2>/dev/null || echo "Continue the task.")

PROMISE_TOKEN=$(python3 -c "
import json, sys
state_file = '$STATE_DIR/$SESSION_ID.json'
with open(state_file) as f:
    state = json.load(f)
print(state.get('promise_token', 'TASK_COMPLETE'))
" 2>/dev/null || echo "TASK_COMPLETE")

STRATEGY=$(python3 -c "
import json, sys
state_file = '$STATE_DIR/$SESSION_ID.json'
with open(state_file) as f:
    state = json.load(f)
print(state.get('completion_strategy', 'promise'))
" 2>/dev/null || echo "promise")

# ---- Build continuation message ----
CONTINUATION="[RALPH-LOOP:$SESSION_ID] Iteration $ITERATION/$MAX_ITER — task incomplete, continuing.

ORIGINAL TASK: $ORIGINAL_PROMPT
"

if [ "$STRATEGY" = "promise" ]; then
    CONTINUATION+="
COMPLETION: When you have fully completed the task, output exactly:
<promise>$PROMISE_TOKEN</promise>

If you cannot complete in this iteration, summarize your progress. The loop will continue automatically."
else
    CONTINUATION+="
COMPLETION: The loop will detect completion when the task file appears in the watch folder.

Continue working on the task. Summarize your progress at the end of each iteration."
fi

# ---- Re-inject via stderr + exit 2 ----
echo "$CONTINUATION" >&2
exit 2
