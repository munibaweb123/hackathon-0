# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
Ralph Wiggum Loop — continuous task execution until completion.

Uses Claude Code's Stop hook mechanism to keep Claude running in a loop
until a task is complete. Two completion strategies:
  1. Promise-based: detect <promise>TOKEN</promise> in output
  2. File-based: detect when task file moves to a watch folder

Usage with UV (recommended):
    # Install the stop hook (one-time setup)
    uv run ralph_loop.py --install-hook

    # Initialize a loop session
    uv run ralph_loop.py --vault-path ../../obsidian-vault \\
        --init --prompt "Build feature X and test it" \\
        --completion-promise "TASK_COMPLETE" --max-iterations 10

    # Check status
    uv run ralph_loop.py --vault-path ../../obsidian-vault --status SESSION_ID

    # Manual stop
    uv run ralph_loop.py --vault-path ../../obsidian-vault --stop SESSION_ID
"""

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Local import
sys.path.insert(0, str(Path(__file__).resolve().parent))
from state_tracker import StateTracker

logger = logging.getLogger("ralph-loop")

SKILL_DIR = Path(__file__).resolve().parent
HOOK_SCRIPT_REL = ".claude/skills/ralph-wiggum-loop/stop_hook.sh"


class RalphLoop:
    """
    Initializer and manager for continuous task execution loop sessions.
    """

    def __init__(self, vault_path: str) -> None:
        self.vault = Path(vault_path).resolve()
        state_dir = self.vault / "Logs" / "ralph-loop"
        self.tracker = StateTracker(str(state_dir))

    # ------------------------------------------------------------------
    # Initialize a new loop session
    # ------------------------------------------------------------------
    def init_session(
        self,
        prompt: str,
        completion_strategy: str = "promise",
        promise_token: str = "TASK_COMPLETE",
        task_file: Optional[str] = None,
        watch_folder: Optional[str] = None,
        max_iterations: int = 10,
        timeout_seconds: int = 3600,
    ) -> str:
        """
        Create a new loop session and output the prepared prompt.

        Returns:
            session_id
        """
        session_id = uuid.uuid4().hex[:8]

        # Resolve watch folder relative to vault if needed
        if watch_folder and not Path(watch_folder).is_absolute():
            watch_folder = str(self.vault / watch_folder)
        if task_file and not Path(task_file).is_absolute():
            task_file = str(self.vault / task_file)

        self.tracker.create_session(
            session_id=session_id,
            prompt=prompt,
            completion_strategy=completion_strategy,
            promise_token=promise_token,
            task_file=task_file,
            watch_folder=watch_folder,
            max_iterations=max_iterations,
            timeout_seconds=timeout_seconds,
        )

        # Update dashboard
        self.tracker.update_dashboard(session_id, str(self.vault))

        # Build the prepared prompt
        prepared = self._build_initial_prompt(
            session_id=session_id,
            prompt=prompt,
            completion_strategy=completion_strategy,
            promise_token=promise_token,
            max_iterations=max_iterations,
        )

        # Output
        print(f"\nRalph Wiggum Loop initialized!")
        print(f"  Session: {session_id}")
        print(f"  Strategy: {completion_strategy}-based", end="")
        if completion_strategy == "promise":
            print(f" (token: {promise_token})")
        else:
            print(f" (watch: {watch_folder})")
        print(f"  Max iterations: {max_iterations} | Timeout: {timeout_seconds}s")
        print()
        print("  Paste this prompt into Claude Code to start the loop:")
        print("  " + "─" * 60)
        print()
        print(prepared)
        print()
        print("  " + "─" * 60)
        print()
        print(f"  Monitor: uv run ralph_loop.py --vault-path {self.vault} --status {session_id}")
        print(f"  Stop:    uv run ralph_loop.py --vault-path {self.vault} --stop {session_id}")

        return session_id

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def show_status(self, session_id: str) -> None:
        """Display current status of a loop session."""
        state = self.tracker.get_session(session_id)
        if not state:
            print(f"Session {session_id} not found")
            return

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
        bar = "=" * filled + "-" * (bar_len - filled)

        print(f"\nRalph Wiggum Loop — Session {session_id}")
        print(f"  Status:     {status_emoji} {state['status']}")
        print(f"  Progress:   [{bar}] {pct}%")
        print(f"  Iteration:  {state['current_iteration']} / {state['max_iterations']}")
        print(f"  Strategy:   {state['completion_strategy']}")
        print(f"  Started:    {state['start_time'][:19]}")

        if state.get("last_iteration_time"):
            print(f"  Last iter:  {state['last_iteration_time'][:19]}")
        if state.get("end_time"):
            print(f"  Ended:      {state['end_time'][:19]}")
        if state.get("exit_reason"):
            print(f"  Exit:       {state['exit_reason']}")

        if state["iterations"]:
            print(f"\n  Iteration log:")
            for it in state["iterations"][-5:]:  # Last 5
                print(f"    #{it['iteration']} at {it['timestamp'][:19]} — {it.get('status', 'started')}")

    # ------------------------------------------------------------------
    # Stop
    # ------------------------------------------------------------------
    def stop_session(self, session_id: str) -> None:
        """Manually stop a running loop session."""
        success = self.tracker.stop_session(session_id)
        if success:
            self.tracker.update_dashboard(session_id, str(self.vault))
            print(f"Session {session_id} stopped")
        else:
            print(f"Session {session_id} not found or not running")

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------
    def show_history(self) -> None:
        """Show all past loop sessions."""
        sessions = self.tracker.list_sessions()
        if not sessions:
            print("No loop sessions found")
            return

        print(f"\nRalph Wiggum Loop — Session History ({len(sessions)} sessions)\n")
        print(f"  {'ID':<10} {'Status':<15} {'Iters':<8} {'Strategy':<10} {'Started':<20} {'Exit'}")
        print(f"  {'─'*10} {'─'*15} {'─'*8} {'─'*10} {'─'*20} {'─'*20}")

        for s in sessions:
            status_emoji = {
                "running": "🔄",
                "completed": "✅",
                "failed": "❌",
                "timeout": "⏰",
                "max_iterations": "🔢",
                "stopped": "⏹",
            }.get(s["status"], "❓")

            print(
                f"  {s['session_id']:<10} "
                f"{status_emoji} {s['status']:<12} "
                f"{s['iterations']}/{s['max']:<5} "
                f"{s['strategy']:<10} "
                f"{s['start_time'][:19]:<20} "
                f"{s.get('exit_reason', '—') or '—'}"
            )

    # ------------------------------------------------------------------
    # Hook management
    # ------------------------------------------------------------------
    def install_hook(self) -> None:
        """Write the Stop hook config to .claude/settings.local.json."""
        # Find the project .claude directory
        claude_dir = SKILL_DIR.parent.parent  # .claude/skills/ralph-wiggum-loop -> .claude
        settings_file = claude_dir / "settings.local.json"

        settings = {}
        if settings_file.exists():
            try:
                settings = json.loads(settings_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                settings = {}

        # Build hook config
        hook_entry = {
            "type": "command",
            "command": HOOK_SCRIPT_REL,
            "timeout": 30,
        }

        # Add to hooks.Stop array
        if "hooks" not in settings:
            settings["hooks"] = {}
        if "Stop" not in settings["hooks"]:
            settings["hooks"]["Stop"] = []

        # Check if already installed
        existing_commands = [
            h.get("hooks", [{}])[0].get("command", "")
            if isinstance(h, dict) and "hooks" in h
            else h.get("command", "")
            for h in settings["hooks"]["Stop"]
        ]

        if HOOK_SCRIPT_REL in existing_commands:
            print("Ralph Wiggum Loop stop hook is already installed")
            return

        settings["hooks"]["Stop"].append({
            "hooks": [hook_entry],
        })

        settings_file.write_text(
            json.dumps(settings, indent=2), encoding="utf-8"
        )

        print(f"Stop hook installed in {settings_file}")
        print(f"  Hook script: {HOOK_SCRIPT_REL}")
        print(f"\n  Restart Claude Code for the hook to take effect.")

    def uninstall_hook(self) -> None:
        """Remove the Stop hook config from .claude/settings.local.json."""
        claude_dir = SKILL_DIR.parent.parent
        settings_file = claude_dir / "settings.local.json"

        if not settings_file.exists():
            print("No settings.local.json found — nothing to uninstall")
            return

        try:
            settings = json.loads(settings_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            print("Invalid settings.local.json")
            return

        if "hooks" not in settings or "Stop" not in settings["hooks"]:
            print("No Stop hooks configured — nothing to uninstall")
            return

        original_len = len(settings["hooks"]["Stop"])
        settings["hooks"]["Stop"] = [
            h for h in settings["hooks"]["Stop"]
            if not self._hook_matches(h, HOOK_SCRIPT_REL)
        ]

        removed = original_len - len(settings["hooks"]["Stop"])
        if removed == 0:
            print("Ralph Wiggum Loop hook not found in config")
            return

        # Clean up empty structures
        if not settings["hooks"]["Stop"]:
            del settings["hooks"]["Stop"]
        if not settings["hooks"]:
            del settings["hooks"]

        settings_file.write_text(
            json.dumps(settings, indent=2), encoding="utf-8"
        )
        print(f"Stop hook removed from {settings_file}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _build_initial_prompt(
        self,
        session_id: str,
        prompt: str,
        completion_strategy: str,
        promise_token: str,
        max_iterations: int,
    ) -> str:
        """Build the initial prompt with loop instructions."""
        lines = [
            f"[RALPH-LOOP:{session_id}] You are in a continuous execution loop (iteration 1/{max_iterations}).",
            "",
            f"TASK: {prompt}",
            "",
        ]

        if completion_strategy == "promise":
            lines.extend([
                f"COMPLETION: When you have FULLY completed the task, output exactly:",
                f"<promise>{promise_token}</promise>",
                "",
                "If you cannot complete in this iteration, summarize your progress.",
                "The loop will automatically continue with context from this iteration.",
            ])
        else:
            lines.extend([
                "COMPLETION: The loop will detect completion when the task file appears",
                "in the watch folder. Continue working on the task.",
                "",
                "Summarize your progress at the end of each iteration.",
            ])

        return "\n".join(lines)

    def _hook_matches(self, hook_config: dict, script_path: str) -> bool:
        """Check if a hook config entry matches the given script path."""
        if isinstance(hook_config, dict):
            if "hooks" in hook_config:
                return any(
                    h.get("command", "") == script_path
                    for h in hook_config["hooks"]
                )
            return hook_config.get("command", "") == script_path
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ralph Wiggum Loop — continuous task execution until completion"
    )
    parser.add_argument(
        "--vault-path",
        default="./obsidian-vault",
        help="Path to the Obsidian vault (default: ./obsidian-vault)",
    )

    # Session initialization
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize a new loop session",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        help="The task prompt to execute in a loop",
    )
    parser.add_argument(
        "--task-file",
        type=str,
        help="Read task from a file (e.g., Needs_Action/task.md)",
    )
    parser.add_argument(
        "--completion-promise",
        type=str,
        default="TASK_COMPLETE",
        help="Promise token to detect in output (default: TASK_COMPLETE)",
    )
    parser.add_argument(
        "--watch-folder",
        type=str,
        help="Folder to watch for task file completion (enables file-based strategy)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum iterations (default: 10)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Maximum total execution time in seconds (default: 3600)",
    )

    # Session management
    parser.add_argument(
        "--status",
        type=str,
        metavar="SESSION_ID",
        help="Show status of a loop session",
    )
    parser.add_argument(
        "--stop",
        type=str,
        metavar="SESSION_ID",
        help="Manually stop a running loop session",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show all past loop sessions",
    )

    # Hook management
    parser.add_argument(
        "--install-hook",
        action="store_true",
        help="Install the Stop hook in .claude/settings.local.json",
    )
    parser.add_argument(
        "--uninstall-hook",
        action="store_true",
        help="Remove the Stop hook from .claude/settings.local.json",
    )

    # Common
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    loop = RalphLoop(args.vault_path)

    if args.install_hook:
        loop.install_hook()
    elif args.uninstall_hook:
        loop.uninstall_hook()
    elif args.init:
        # Determine prompt source
        prompt = args.prompt
        if not prompt and args.task_file:
            task_path = Path(args.task_file)
            if not task_path.exists():
                print(f"Error: task file not found: {args.task_file}")
                sys.exit(1)
            prompt = task_path.read_text(encoding="utf-8")
        if not prompt:
            print("Error: --prompt or --task-file required with --init")
            sys.exit(1)

        # Determine strategy
        strategy = "file" if args.watch_folder else "promise"

        loop.init_session(
            prompt=prompt,
            completion_strategy=strategy,
            promise_token=args.completion_promise,
            task_file=args.task_file,
            watch_folder=args.watch_folder,
            max_iterations=args.max_iterations,
            timeout_seconds=args.timeout,
        )
    elif args.status:
        loop.show_status(args.status)
    elif args.stop:
        loop.stop_session(args.stop)
    elif args.history:
        loop.show_history()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
