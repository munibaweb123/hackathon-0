# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
#     "google-genai>=1.0.0",
# ]
# ///
"""
Main Orchestrator — central coordination for the AI Employee.

Processes tasks from Needs_Action/ via a priority queue, runs cron-scheduled
jobs, and routes tasks to Claude CLI or downstream skills via subprocess.

Usage:
    uv run main_orchestrator.py --once
    uv run main_orchestrator.py --run --interval 10
    uv run main_orchestrator.py --status
    uv run main_orchestrator.py --queue
    uv run main_orchestrator.py --schedules
"""

import argparse
import json
import logging
import logging.handlers
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Local imports
sys.path.insert(0, str(Path(__file__).parent))
from task_queue import TaskQueue
from scheduler import Scheduler

logger = logging.getLogger("orchestrator")


class MainOrchestrator:
    """
    Central orchestrator for the AI Employee.

    Each cycle:
    1. Check cron schedules and launch due jobs
    2. Scan Needs_Action/ for tasks and build priority queue
    3. Process up to max_concurrent tasks:
       - Claim (move to In_Progress/)
       - Route to handler (Claude CLI or skill subprocess)
       - Complete or fail
    4. Update Dashboard.md
    5. Log cycle results
    """

    def __init__(self, config_path: str, vault_path_override: Optional[str] = None) -> None:
        # Load config
        self.config_path = Path(config_path).resolve()
        self.config = self._load_config()

        # Vault path
        self.vault_path = Path(
            vault_path_override
            or self.config.get("vault_path", "./obsidian-vault")
        ).resolve()

        # Project root (3 levels up from skill dir)
        self.project_root = Path(__file__).parent.parent.parent.parent.resolve()

        self.running = False
        self.dev_mode = self.config.get("dev_mode", True)
        self.dry_run = self.config.get("dry_run", True)

        # Ensure directories
        self.logs_dir = self.vault_path / "Logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Setup logging
        self._setup_logging()

        # Task processing config
        task_config = self.config.get("task_processing", {})
        self.poll_interval = task_config.get("poll_interval", 10)
        self.max_concurrent = task_config.get("max_concurrent", 3)
        priority_map = task_config.get("priority_map", {})

        # Claude config
        claude_config = self.config.get("claude", {})
        self.claude_command = claude_config.get("command", "claude")
        self.claude_timeout = claude_config.get("timeout", 300)
        self.claude_max_concurrent = claude_config.get("max_concurrent", 1)

        # Initialize components
        self.task_queue = TaskQueue(
            vault_path=str(self.vault_path),
            priority_map=priority_map if priority_map else None,
        )
        self.scheduler = Scheduler(
            schedules_config=self.config.get("schedules", {}),
            vault_path=str(self.vault_path),
            project_root=str(self.project_root),
        )

        # Cycle log
        self.cycle_log_path = self.logs_dir / "orchestrator.json"

        # Stats
        self.total_cycles = 0
        self.total_tasks_processed = 0
        self.total_tasks_failed = 0
        self.start_time: Optional[str] = None

        logger.info(
            "Orchestrator initialized (vault=%s, interval=%ds, max_concurrent=%d, dry_run=%s)",
            self.vault_path,
            self.poll_interval,
            self.max_concurrent,
            self.dry_run,
        )

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            logger.warning("Config not found: %s — using defaults", self.config_path)
            return {}

        try:
            return yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            logger.error("Failed to load config: %s", e)
            return {}

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _setup_logging(self) -> None:
        """Configure rotating file + console logging."""
        if logger.handlers:
            return

        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

        fh = logging.handlers.RotatingFileHandler(
            self.logs_dir / "orchestrator.log",
            maxBytes=5_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    # ------------------------------------------------------------------
    # Main cycle
    # ------------------------------------------------------------------
    def run_once(self) -> Dict[str, Any]:
        """
        Execute a single orchestration cycle.

        Returns:
            Cycle result dict.
        """
        cycle_start = time.time()
        now = datetime.now(timezone.utc)

        result: Dict[str, Any] = {
            "timestamp": now.isoformat(),
            "schedules_launched": [],
            "tasks_processed": 0,
            "tasks_failed": 0,
            "tasks_skipped": 0,
            "queue_size": 0,
        }

        # 1. Check schedules
        try:
            launched = self.scheduler.check_and_run()
            result["schedules_launched"] = launched
        except Exception as e:
            logger.error("Scheduler error: %s", e)

        # 2. Scan task queue
        self.task_queue.scan()
        result["queue_size"] = self.task_queue.size

        if self.task_queue.size > 0:
            logger.info("Queue: %d tasks pending", self.task_queue.size)

        # 3. Process tasks (up to max_concurrent)
        processed = 0
        while processed < self.max_concurrent:
            task = self.task_queue.pop()
            if task is None:
                break

            # Claim
            claimed_path = self.task_queue.claim(task["path"])
            if claimed_path is None:
                result["tasks_skipped"] += 1
                continue

            # Route and execute
            try:
                success = self._route_task(task, claimed_path)
                if success:
                    self.task_queue.complete(claimed_path)
                    result["tasks_processed"] += 1
                    self.total_tasks_processed += 1
                else:
                    self.task_queue.fail(claimed_path, "Handler returned failure")
                    result["tasks_failed"] += 1
                    self.total_tasks_failed += 1
            except Exception as e:
                logger.error("Task processing error for %s: %s", task["filename"], e)
                self.task_queue.fail(claimed_path, str(e))
                result["tasks_failed"] += 1
                self.total_tasks_failed += 1

            processed += 1

        # 4. Update dashboard
        try:
            self.update_dashboard(result)
        except Exception as e:
            logger.error("Dashboard update error: %s", e)

        # 5. Log cycle
        elapsed = round(time.time() - cycle_start, 2)
        result["elapsed_seconds"] = elapsed
        self._log_cycle(result)
        self.total_cycles += 1

        if result["tasks_processed"] > 0 or result["tasks_failed"] > 0:
            logger.info(
                "Cycle complete: %d processed, %d failed, %d remaining (%.1fs)",
                result["tasks_processed"],
                result["tasks_failed"],
                self.task_queue.size,
                elapsed,
            )

        return result

    # ------------------------------------------------------------------
    # Continuous loop
    # ------------------------------------------------------------------
    def run(self, interval: Optional[int] = None) -> None:
        """
        Run the orchestrator in a continuous loop.

        Args:
            interval: Override poll interval from config.
        """
        poll = interval or self.poll_interval
        self.running = True
        self.start_time = datetime.now(timezone.utc).isoformat()

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        logger.info(
            "Main orchestrator started (interval=%ds, dry_run=%s)",
            poll,
            self.dry_run,
        )
        print(f"Main Orchestrator started (interval={poll}s, dry_run={self.dry_run})")
        print(f"Vault: {self.vault_path}")
        print(f"Schedules: {len(self.scheduler.schedules)}")
        print("Press Ctrl+C to stop.\n")

        while self.running:
            try:
                self.run_once()
            except Exception as e:
                logger.error("Cycle error: %s", e, exc_info=True)

            # Sleep in small increments for responsive shutdown
            for _ in range(poll * 10):
                if not self.running:
                    break
                time.sleep(0.1)

        logger.info("Main orchestrator stopped (cycles=%d, processed=%d, failed=%d)",
                     self.total_cycles, self.total_tasks_processed, self.total_tasks_failed)
        print("\nOrchestrator stopped.")

    def _shutdown(self, signum: int, frame: Any) -> None:
        """Signal handler for graceful shutdown."""
        logger.info("Shutdown signal received (%d)", signum)
        self.running = False

    # ------------------------------------------------------------------
    # Task routing
    # ------------------------------------------------------------------
    def _route_task(self, task: Dict[str, Any], claimed_path: str) -> bool:
        """
        Route a task to the appropriate handler.

        Routing by filename prefix:
        - ALERT_*         → Claude CLI (urgent analysis)
        - EMAIL_*, WHATSAPP_* → Claude CLI (reasoning + plan)
        - EXECUTE_PAYMENT_* → mark for payment-handler-mcp
        - SEND_EMAIL_*     → mark for email-sender-mcp
        - POST_SOCIAL_*    → mark for social-poster-mcp
        - SEND_INVOICE_*   → mark for invoice-generator
        - NOTIFY_*         → log and complete
        - Default          → Claude CLI

        Returns:
            True if handled successfully.
        """
        filename = task["filename"].upper()
        content = task.get("content", "")
        metadata = task.get("metadata", {})

        logger.info("Routing task: %s (priority=%d)", task["filename"], task["priority"])

        # Notification files — just log, no action needed
        if filename.startswith("NOTIFY_"):
            logger.info("Notification logged: %s", task["filename"])
            return True

        # Action execution files — these are picked up by downstream MCP skills
        # We just log them and mark complete; the MCP skill monitors Needs_Action/
        action_prefixes = [
            "EXECUTE_PAYMENT_",
            "SEND_EMAIL_",
            "POST_SOCIAL_",
            "SEND_INVOICE_",
        ]
        for prefix in action_prefixes:
            if filename.startswith(prefix):
                logger.info(
                    "Action task noted: %s (downstream skill will execute)",
                    task["filename"],
                )
                return True

        # Alert files — high priority, invoke Claude for analysis
        if filename.startswith("ALERT_"):
            prompt = self._build_alert_prompt(task)
            return self._invoke_claude(prompt, task)

        # Email/WhatsApp events — invoke Claude for reasoning
        if filename.startswith("EMAIL_") or filename.startswith("WHATSAPP_"):
            prompt = self._build_reasoning_prompt(task)
            return self._invoke_claude(prompt, task)

        # Default — invoke Claude with task content
        prompt = self._build_default_prompt(task)
        return self._invoke_claude(prompt, task)

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------
    def _build_alert_prompt(self, task: Dict[str, Any]) -> str:
        """Build an urgent analysis prompt for alert tasks."""
        return (
            f"URGENT ALERT — analyze and recommend immediate action:\n\n"
            f"File: {task['filename']}\n"
            f"Metadata: {json.dumps(task.get('metadata', {}), default=str)}\n\n"
            f"Content:\n{task.get('content', '')}\n\n"
            f"Provide: 1) Root cause assessment, 2) Recommended actions, "
            f"3) Whether human intervention is needed."
        )

    def _build_reasoning_prompt(self, task: Dict[str, Any]) -> str:
        """Build a reasoning prompt for email/message events."""
        source = task.get("metadata", {}).get("source_type", "unknown")
        return (
            f"Analyze this {source} event and create an action plan:\n\n"
            f"File: {task['filename']}\n"
            f"Metadata: {json.dumps(task.get('metadata', {}), default=str)}\n\n"
            f"Content:\n{task.get('content', '')}\n\n"
            f"Determine: 1) Priority and urgency, 2) Required action (reply, forward, "
            f"escalate, archive), 3) Draft response if reply needed, 4) Any approval required."
        )

    def _build_default_prompt(self, task: Dict[str, Any]) -> str:
        """Build a generic task processing prompt."""
        return (
            f"Process this task:\n\n"
            f"File: {task['filename']}\n"
            f"Metadata: {json.dumps(task.get('metadata', {}), default=str)}\n\n"
            f"Content:\n{task.get('content', '')}\n\n"
            f"Determine the appropriate action and execute or create an action plan."
        )

    # ------------------------------------------------------------------
    # AI invocation (Gemini API, with Anthropic fallback)
    # ------------------------------------------------------------------
    def _invoke_claude(self, prompt: str, task: Dict[str, Any]) -> bool:
        """
        Invoke Gemini API (or Anthropic fallback) to process a task.

        Priority: GEMINI_API_KEY → ANTHROPIC_API_KEY → dry_run log.

        Returns:
            True if successful.
        """
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

        # Load from .env file if not in environment
        if not gemini_key or not anthropic_key:
            env_path = self.project_root / ".env"
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if line.startswith("GEMINI_API_KEY=") and not gemini_key:
                        gemini_key = line.split("=", 1)[1].strip()
                    elif line.startswith("ANTHROPIC_API_KEY=") and not anthropic_key:
                        anthropic_key = line.split("=", 1)[1].strip()

        # Try Gemini first
        if gemini_key and gemini_key != "your_gemini_api_key_here":
            return self._invoke_gemini(prompt, task, gemini_key)

        # Try Anthropic fallback
        if anthropic_key and anthropic_key != "your_anthropic_api_key_here":
            return self._invoke_anthropic(prompt, task, anthropic_key)

        # No valid key — dry run log
        logger.info(
            "[DRY RUN] No AI key set. Would process: %s (prompt: %d chars)",
            task["filename"],
            len(prompt),
        )
        return True

    def _invoke_gemini(self, prompt: str, task: Dict[str, Any], api_key: str) -> bool:
        """Call Gemini API to process a task."""
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="models/gemini-flash-latest",
                contents=prompt,
            )
            text = response.text.strip()
            self._save_claude_response(task, text)
            logger.info("Gemini processed %s (%d chars)", task["filename"], len(text))
            return True
        except Exception as e:
            logger.error("Gemini invocation error for %s: %s", task["filename"], e)
            return False

    def _invoke_anthropic(self, prompt: str, task: Dict[str, Any], api_key: str) -> bool:
        """Call Anthropic API as fallback."""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text.strip()
            self._save_claude_response(task, text)
            logger.info("Anthropic processed %s (%d chars)", task["filename"], len(text))
            return True
        except Exception as e:
            logger.error("Anthropic invocation error for %s: %s", task["filename"], e)
            return False

    def _save_claude_response(self, task: Dict[str, Any], response: str) -> None:
        """Save Claude's response as a plan file in vault/plans/."""
        plans_dir = self.vault_path / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        filename = f"PLAN_{task['filename'].replace('.md', '')}_{timestamp}.md"

        content = (
            f"---\n"
            f"type: plan\n"
            f"source_task: {task['filename']}\n"
            f"created: {now.isoformat()}\n"
            f"status: pending_review\n"
            f"---\n\n"
            f"# Plan: {task['filename']}\n\n"
            f"{response}\n"
        )

        filepath = plans_dir / filename
        filepath.write_text(content, encoding="utf-8")
        logger.debug("Saved Claude response: %s", filename)

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def update_dashboard(self, cycle_result: Optional[Dict[str, Any]] = None) -> None:
        """Write Orchestrator Status section to Dashboard.md."""
        dashboard_path = self.vault_path / "Dashboard.md"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # Queue info
        queue_size = cycle_result.get("queue_size", 0) if cycle_result else self.task_queue.size

        # Schedule info
        sched_count = len(self.scheduler.schedules)
        launched = cycle_result.get("schedules_launched", []) if cycle_result else []

        section = (
            f"## Orchestrator Status\n\n"
            f"**Mode:** {'DRY RUN' if self.dry_run else 'LIVE'} | "
            f"**Last Cycle:** {now} | "
            f"**Total Cycles:** {self.total_cycles}\n\n"
            f"| Metric | Value |\n"
            f"|--------|-------|\n"
            f"| Queue Depth | {queue_size} |\n"
            f"| Tasks Processed | {self.total_tasks_processed} |\n"
            f"| Tasks Failed | {self.total_tasks_failed} |\n"
            f"| Schedules | {sched_count} |\n"
            f"| Poll Interval | {self.poll_interval}s |"
        )

        if launched:
            section += f"\n\n**Schedules fired:** {', '.join(launched)}"

        if dashboard_path.exists():
            content = dashboard_path.read_text(encoding="utf-8")
            pattern = r"## Orchestrator Status\n.*?(?=\n## |\Z)"
            if re.search(pattern, content, re.DOTALL):
                content = re.sub(pattern, section, content, flags=re.DOTALL)
            else:
                content = content.rstrip() + "\n\n" + section + "\n"
        else:
            content = f"# Dashboard\n\n{section}\n"

        dashboard_path.write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _log_cycle(self, result: Dict[str, Any]) -> None:
        """Append cycle result to orchestrator log."""
        entry = {
            "timestamp": result.get("timestamp"),
            "epoch": time.time(),
            "tasks_processed": result.get("tasks_processed", 0),
            "tasks_failed": result.get("tasks_failed", 0),
            "queue_size": result.get("queue_size", 0),
            "schedules_launched": result.get("schedules_launched", []),
            "elapsed_seconds": result.get("elapsed_seconds", 0),
        }

        logs = self._load_cycle_logs()
        logs.append(entry)
        logs = logs[-2000:]

        try:
            self.cycle_log_path.write_text(
                json.dumps(logs, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error("Failed to write cycle log: %s", e)

    def _load_cycle_logs(self) -> List[Dict[str, Any]]:
        """Load cycle logs."""
        if not self.cycle_log_path.exists():
            return []
        try:
            data = json.loads(self.cycle_log_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return []

    # ------------------------------------------------------------------
    # Status display
    # ------------------------------------------------------------------
    def show_status(self) -> None:
        """Print orchestrator status."""
        print(f"\n{'=' * 60}")
        print(f"  MAIN ORCHESTRATOR STATUS")
        print(f"{'=' * 60}")

        mode = "DRY RUN" if self.dry_run else "LIVE"
        print(f"\n  Mode:           {mode}")
        print(f"  Vault:          {self.vault_path}")
        print(f"  Poll Interval:  {self.poll_interval}s")
        print(f"  Max Concurrent: {self.max_concurrent}")
        print(f"  Claude:         {self.claude_command} (timeout: {self.claude_timeout}s)")

        # Queue
        self.task_queue.scan()
        print(f"\n  --- Task Queue ---")
        print(f"  Pending: {self.task_queue.size}")
        self.task_queue.show_queue()

        # Schedules
        print(f"\n  --- Schedules ---")
        self.scheduler.show_schedules()

        # Stats
        print(f"\n  --- Stats ---")
        print(f"  Total Cycles:    {self.total_cycles}")
        print(f"  Tasks Processed: {self.total_tasks_processed}")
        print(f"  Tasks Failed:    {self.total_tasks_failed}")

        print(f"\n{'=' * 60}")

    def show_queue(self) -> None:
        """Print current task queue."""
        self.task_queue.scan()
        self.task_queue.show_queue()

    def show_schedules(self) -> None:
        """Print schedule status."""
        self.scheduler.show_schedules()


# ======================================================================
# CLI
# ======================================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Main Orchestrator — central coordination for the AI Employee"
    )

    # Actions
    parser.add_argument("--run", action="store_true", help="Continuous orchestration loop")
    parser.add_argument("--once", action="store_true", help="Single orchestration cycle")
    parser.add_argument("--status", action="store_true", help="Show orchestrator status")
    parser.add_argument("--queue", action="store_true", help="Show current task queue")
    parser.add_argument("--schedules", action="store_true", help="Show schedule status")

    # Config
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Config file path (default: config.yaml in skill dir)",
    )
    parser.add_argument(
        "--vault-path",
        default=None,
        help="Override vault path from config",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Override poll interval from config",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    orchestrator = MainOrchestrator(
        config_path=args.config,
        vault_path_override=args.vault_path,
    )

    if args.queue:
        orchestrator.show_queue()
        return

    if args.schedules:
        orchestrator.show_schedules()
        return

    if args.status:
        orchestrator.show_status()
        return

    if args.once:
        result = orchestrator.run_once()
        print(f"\nCycle complete: {result['tasks_processed']} processed, "
              f"{result['tasks_failed']} failed, {result['queue_size']} remaining")
        return

    if args.run:
        orchestrator.run(interval=args.interval)
        return

    # Default: show status
    orchestrator.show_status()


if __name__ == "__main__":
    main()
