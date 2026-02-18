"""
State Tracker — manages loop session state for the Ralph Wiggum Loop.

Persists iteration counts, timing, completion status, and iteration logs
to JSON files in the vault Logs/ralph-loop/ directory.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class StateTracker:
    """
    Manages persistent loop state for continuous task execution sessions.

    State files are stored as JSON in {state_dir}/{session_id}.json.
    """

    def __init__(self, state_dir: str) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    def create_session(
        self,
        session_id: str,
        prompt: str,
        completion_strategy: str = "promise",
        promise_token: str = "TASK_COMPLETE",
        task_file: Optional[str] = None,
        watch_folder: Optional[str] = None,
        max_iterations: int = 10,
        timeout_seconds: int = 3600,
    ) -> Dict[str, Any]:
        """Create a new loop session state file."""
        now = datetime.now(timezone.utc)
        state = {
            "session_id": session_id,
            "prompt": prompt,
            "completion_strategy": completion_strategy,
            "promise_token": promise_token,
            "task_file": task_file,
            "watch_folder": watch_folder,
            "max_iterations": max_iterations,
            "timeout_seconds": timeout_seconds,
            "current_iteration": 0,
            "start_time": now.isoformat(),
            "last_iteration_time": None,
            "end_time": None,
            "status": "running",
            "exit_reason": None,
            "iterations": [],
        }

        self._write_state(session_id, state)
        return state

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Read session state file."""
        state_file = self.state_dir / f"{session_id}.json"
        if not state_file.exists():
            return None
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return None

    def find_active_session(self) -> Optional[Dict[str, Any]]:
        """Find the most recent running session."""
        active = None
        latest_time = None

        for f in self.state_dir.glob("*.json"):
            try:
                state = json.loads(f.read_text(encoding="utf-8"))
                if state.get("status") != "running":
                    continue
                start = state.get("start_time", "")
                if latest_time is None or start > latest_time:
                    latest_time = start
                    active = state
            except (json.JSONDecodeError, ValueError):
                continue

        return active

    # ------------------------------------------------------------------
    # Iteration management
    # ------------------------------------------------------------------
    def increment_iteration(self, session_id: str) -> Dict[str, Any]:
        """Increment iteration counter and log the attempt."""
        state = self.get_session(session_id)
        if not state:
            return {"error": f"Session {session_id} not found"}

        now = datetime.now(timezone.utc)
        state["current_iteration"] += 1
        state["last_iteration_time"] = now.isoformat()

        state["iterations"].append({
            "iteration": state["current_iteration"],
            "timestamp": now.isoformat(),
            "status": "started",
        })

        self._write_state(session_id, state)
        return state

    # ------------------------------------------------------------------
    # Completion checks
    # ------------------------------------------------------------------
    def check_completion(
        self, session_id: str, transcript_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate whether the task is complete.

        Returns:
            {complete: bool, reason: str, iteration: int, max: int, status: str}
        """
        state = self.get_session(session_id)
        if not state:
            return {
                "complete": True,
                "reason": "session_not_found",
                "iteration": 0,
                "max": 0,
                "status": "not_found",
            }

        if state["status"] != "running":
            return {
                "complete": True,
                "reason": state.get("exit_reason", state["status"]),
                "iteration": state["current_iteration"],
                "max": state["max_iterations"],
                "status": state["status"],
            }

        strategy = state["completion_strategy"]

        # Check promise-based completion
        if strategy == "promise" and transcript_path:
            token = state.get("promise_token", "TASK_COMPLETE")
            if self._check_promise_in_transcript(transcript_path, token):
                self.mark_complete(session_id, "promise_fulfilled")
                state = self.get_session(session_id)
                return {
                    "complete": True,
                    "reason": "promise_fulfilled",
                    "iteration": state["current_iteration"],
                    "max": state["max_iterations"],
                    "status": "completed",
                }

        # Check file-based completion
        if strategy == "file":
            task_file = state.get("task_file")
            watch_folder = state.get("watch_folder")
            if task_file and watch_folder:
                if self._check_file_moved(task_file, watch_folder):
                    self.mark_complete(session_id, "file_detected")
                    state = self.get_session(session_id)
                    return {
                        "complete": True,
                        "reason": "file_detected",
                        "iteration": state["current_iteration"],
                        "max": state["max_iterations"],
                        "status": "completed",
                    }

        # Check limits
        limits = self.check_limits(session_id)
        if limits.get("exceeded"):
            reason = limits["reason"]
            self.mark_failed(session_id, reason)
            state = self.get_session(session_id)
            return {
                "complete": True,
                "reason": reason,
                "iteration": state["current_iteration"],
                "max": state["max_iterations"],
                "status": state["status"],
            }

        # Not complete — continue
        return {
            "complete": False,
            "reason": "in_progress",
            "iteration": state["current_iteration"],
            "max": state["max_iterations"],
            "status": "running",
        }

    def check_limits(self, session_id: str) -> Dict[str, Any]:
        """Check if max iterations or timeout exceeded."""
        state = self.get_session(session_id)
        if not state:
            return {"exceeded": True, "reason": "session_not_found"}

        # Max iterations
        if state["current_iteration"] >= state["max_iterations"]:
            return {
                "exceeded": True,
                "reason": f"max_iterations_reached ({state['max_iterations']})",
            }

        # Timeout
        start = datetime.fromisoformat(state["start_time"])
        now = datetime.now(timezone.utc)
        elapsed = (now - start).total_seconds()
        if elapsed >= state["timeout_seconds"]:
            return {
                "exceeded": True,
                "reason": f"timeout ({state['timeout_seconds']}s elapsed: {elapsed:.0f}s)",
            }

        return {"exceeded": False, "remaining_iterations": state["max_iterations"] - state["current_iteration"]}

    # ------------------------------------------------------------------
    # Status updates
    # ------------------------------------------------------------------
    def mark_complete(self, session_id: str, reason: str) -> None:
        """Mark session as completed."""
        state = self.get_session(session_id)
        if not state:
            return
        state["status"] = "completed"
        state["exit_reason"] = reason
        state["end_time"] = datetime.now(timezone.utc).isoformat()
        self._write_state(session_id, state)

    def mark_failed(self, session_id: str, reason: str) -> None:
        """Mark session as failed."""
        state = self.get_session(session_id)
        if not state:
            return
        status = "timeout" if "timeout" in reason else "max_iterations" if "max_iterations" in reason else "failed"
        state["status"] = status
        state["exit_reason"] = reason
        state["end_time"] = datetime.now(timezone.utc).isoformat()
        self._write_state(session_id, state)

    def stop_session(self, session_id: str) -> bool:
        """Manually stop a running session."""
        state = self.get_session(session_id)
        if not state or state["status"] != "running":
            return False
        state["status"] = "stopped"
        state["exit_reason"] = "manual_stop"
        state["end_time"] = datetime.now(timezone.utc).isoformat()
        self._write_state(session_id, state)
        return True

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def update_dashboard(self, session_id: str, vault_path: str) -> None:
        """Write/update Dashboard.md in vault root with loop status."""
        vault = Path(vault_path)
        dashboard = vault / "Dashboard.md"
        state = self.get_session(session_id)
        if not state:
            return

        now = datetime.now(timezone.utc)
        status_emoji = {
            "running": "🔄",
            "completed": "✅",
            "failed": "❌",
            "timeout": "⏰",
            "max_iterations": "🔢",
            "stopped": "⏹",
        }.get(state["status"], "❓")

        pct = round(state["current_iteration"] / state["max_iterations"] * 100) if state["max_iterations"] > 0 else 0
        bar_len = 20
        filled = int(bar_len * pct / 100)
        bar = "█" * filled + "░" * (bar_len - filled)

        section = f"""
## Ralph Wiggum Loop Status

| Field | Value |
|-------|-------|
| Session | `{state['session_id']}` |
| Status | {status_emoji} {state['status']} |
| Progress | `[{bar}]` {pct}% |
| Iteration | {state['current_iteration']} / {state['max_iterations']} |
| Strategy | {state['completion_strategy']} |
| Started | {state['start_time'][:19]} |
| Last Update | {now.strftime('%Y-%m-%d %H:%M:%S')} UTC |

"""
        if state.get("exit_reason"):
            section += f"> Exit reason: {state['exit_reason']}\n\n"

        # Read existing dashboard or create new
        if dashboard.exists():
            content = dashboard.read_text(encoding="utf-8")
            # Replace existing section or append
            marker_start = "## Ralph Wiggum Loop Status"
            if marker_start in content:
                # Find next ## heading or end of file
                start_idx = content.index(marker_start)
                rest = content[start_idx + len(marker_start):]
                next_heading = rest.find("\n## ")
                if next_heading >= 0:
                    end_idx = start_idx + len(marker_start) + next_heading
                    content = content[:start_idx] + section + content[end_idx:]
                else:
                    content = content[:start_idx] + section
            else:
                content = content.rstrip() + "\n\n" + section
        else:
            content = f"""---
type: dashboard
updated_at: {now.isoformat()}
---

# AI Employee Dashboard

{section}"""

        dashboard.write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions with summary info."""
        sessions = []
        for f in sorted(self.state_dir.glob("*.json")):
            try:
                state = json.loads(f.read_text(encoding="utf-8"))
                sessions.append({
                    "session_id": state["session_id"],
                    "status": state["status"],
                    "iterations": state["current_iteration"],
                    "max": state["max_iterations"],
                    "strategy": state["completion_strategy"],
                    "start_time": state["start_time"],
                    "exit_reason": state.get("exit_reason"),
                })
            except (json.JSONDecodeError, ValueError):
                continue
        return sessions

    def cleanup_stale(self, max_age_hours: int = 24) -> int:
        """Clean up stale running sessions older than max_age_hours."""
        now = datetime.now(timezone.utc)
        cleaned = 0
        for f in self.state_dir.glob("*.json"):
            try:
                state = json.loads(f.read_text(encoding="utf-8"))
                if state.get("status") != "running":
                    continue
                start = datetime.fromisoformat(state["start_time"])
                elapsed_hours = (now - start).total_seconds() / 3600
                if elapsed_hours > max_age_hours:
                    state["status"] = "failed"
                    state["exit_reason"] = f"stale_cleanup (>{max_age_hours}h)"
                    state["end_time"] = now.isoformat()
                    f.write_text(json.dumps(state, indent=2), encoding="utf-8")
                    cleaned += 1
            except (json.JSONDecodeError, ValueError):
                continue
        return cleaned

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _write_state(self, session_id: str, state: Dict[str, Any]) -> None:
        """Write state to JSON file."""
        state_file = self.state_dir / f"{session_id}.json"
        state_file.write_text(
            json.dumps(state, indent=2, default=str), encoding="utf-8"
        )

    def _check_promise_in_transcript(
        self, transcript_path: str, token: str
    ) -> bool:
        """Check if promise token exists in the Claude transcript."""
        tp = Path(transcript_path)
        if not tp.exists():
            return False

        try:
            content = tp.read_text(encoding="utf-8")
            pattern = rf"<promise>\s*{re.escape(token)}\s*</promise>"
            return bool(re.search(pattern, content))
        except Exception:
            return False

    def _check_file_moved(self, task_file: str, watch_folder: str) -> bool:
        """Check if the task file has appeared in the watch folder."""
        task_name = Path(task_file).name
        watch = Path(watch_folder)

        if not watch.exists():
            return False

        # Check if file with same name exists in watch folder
        return (watch / task_name).exists()


# ---------------------------------------------------------------------------
# CLI interface (called by stop_hook.sh)
# ---------------------------------------------------------------------------
def main() -> None:
    """CLI for state_tracker.py — used by stop_hook.sh."""
    import argparse

    parser = argparse.ArgumentParser(description="Ralph Loop state tracker")
    parser.add_argument("--state-dir", required=True, help="State directory path")
    parser.add_argument("--check", metavar="SESSION_ID", help="Check completion")
    parser.add_argument("--transcript", help="Transcript path for promise checking")
    parser.add_argument("--increment", metavar="SESSION_ID", help="Increment iteration")
    parser.add_argument("--find-active", action="store_true", help="Find active session")
    parser.add_argument("--dashboard", nargs=2, metavar=("SESSION_ID", "VAULT_PATH"), help="Update dashboard")

    args = parser.parse_args()
    tracker = StateTracker(args.state_dir)

    if args.check:
        result = tracker.check_completion(args.check, args.transcript)
        print(json.dumps(result))
    elif args.increment:
        state = tracker.increment_iteration(args.increment)
        print(json.dumps({"iteration": state.get("current_iteration", 0)}))
    elif args.find_active:
        session = tracker.find_active_session()
        if session:
            print(json.dumps({"session_id": session["session_id"], "found": True}))
        else:
            print(json.dumps({"found": False}))
    elif args.dashboard:
        tracker.update_dashboard(args.dashboard[0], args.dashboard[1])
        print(json.dumps({"updated": True}))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
