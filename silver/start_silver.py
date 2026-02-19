# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
#     "python-dotenv>=1.0.0",
# ]
# ///
"""
Silver Tier Startup Script — Launches all Silver tier skills in order.

Manages process lifecycle for:
  1. gmail-watcher     (polls Gmail → Needs_Action/EMAIL_*)
  2. whatsapp-watcher  (monitors WhatsApp → Needs_Action/WHATSAPP_*)
  3. approval-manager  (monitors pending-approval/ → routes approved actions)
  4. main-orchestrator (priority queue + cron scheduler)

Email-sender-mcp (Node.js) is NOT auto-started — run it separately or
configure it in Claude Desktop's MCP settings.

Usage:
    uv run silver/start_silver.py                  # Start all
    uv run silver/start_silver.py --status         # Check running processes
    uv run silver/start_silver.py --stop           # Stop all
    uv run silver/start_silver.py --dry-run        # Validate config only
    uv run silver/start_silver.py --verbose        # Debug logging
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Load .env from project root
load_dotenv()

# Where we track PIDs for managed processes
PID_DIR = Path("/tmp/ai-employee-silver")

# Startup order — watchers first, then orchestration
STARTUP_ORDER = [
    "gmail-watcher",
    "whatsapp-watcher",
    "approval-manager",
    "main-orchestrator",
]

# Max retries per process during startup
MAX_START_RETRIES = 3
RETRY_DELAY = 5  # seconds between retries


def load_config(config_path: str) -> dict:
    """Load main-orchestrator config.yaml for process definitions."""
    path = Path(config_path)
    if not path.exists():
        print(f"ERROR: Config not found: {config_path}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_vault_path(config: dict, override: str | None = None) -> Path:
    """Resolve vault path from config or CLI override."""
    vault = override or config.get("vault_path", "./obsidian-vault")
    return Path(vault).resolve()


def ensure_vault_folders(vault_path: Path) -> list[str]:
    """Create all required vault folders. Returns list of created folders."""
    required = [
        "Needs_Action", "Plans", "Done", "Logs",
        "pending-approval", "Approved", "Rejected",
        "Attachments", "Reports", "In_Progress",
        "plans", "error",
    ]
    created = []
    for folder in required:
        full = vault_path / folder
        if not full.exists():
            full.mkdir(parents=True, exist_ok=True)
            created.append(folder)
    return created


def write_pid(name: str, pid: int):
    """Save process PID to file."""
    PID_DIR.mkdir(parents=True, exist_ok=True)
    (PID_DIR / f"{name}.pid").write_text(str(pid))


def read_pid(name: str) -> int | None:
    """Read process PID from file. Returns None if not found."""
    pid_file = PID_DIR / f"{name}.pid"
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return None


def clear_pid(name: str):
    """Remove PID file."""
    pid_file = PID_DIR / f"{name}.pid"
    if pid_file.exists():
        pid_file.unlink()


def is_running(pid: int) -> bool:
    """Check if a process is still alive."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def log_event(vault_path: Path, message: str, level: str = "INFO"):
    """Append to Logs/silver_startup.log."""
    logs_dir = vault_path / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "silver_startup.log"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {message}\n"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line)


def start_process(
    name: str, command: str, vault_path: Path, verbose: bool = False
) -> subprocess.Popen | None:
    """
    Start a single process with retry logic.

    Args:
        name: Process name (e.g. "gmail-watcher").
        command: Shell command with {vault} placeholder.
        vault_path: Resolved vault path for substitution.
        verbose: Print debug output.

    Returns:
        Popen object if started, None on failure after retries.
    """
    cmd = command.replace("{vault}", str(vault_path))

    for attempt in range(1, MAX_START_RETRIES + 1):
        try:
            if verbose:
                print(f"  [{name}] Attempt {attempt}/{MAX_START_RETRIES}: {cmd}")

            # Start as subprocess, redirect output to log files
            log_dir = vault_path / "Logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            stdout_log = open(log_dir / f"{name}.stdout.log", "a")
            stderr_log = open(log_dir / f"{name}.stderr.log", "a")

            proc = subprocess.Popen(
                cmd.split(),
                stdout=stdout_log,
                stderr=stderr_log,
                start_new_session=True,  # Detach from parent
            )

            # Give it a moment to crash or stabilize
            time.sleep(2)

            if proc.poll() is not None:
                # Process already exited — failure
                exit_code = proc.returncode
                msg = f"{name} exited immediately (code {exit_code})"
                print(f"  WARNING: {msg}")
                log_event(vault_path, msg, "WARN")

                if attempt < MAX_START_RETRIES:
                    print(f"  Retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                    continue
                else:
                    log_event(vault_path, f"{name} failed after {MAX_START_RETRIES} attempts", "ERROR")
                    return None

            # Process is running
            write_pid(name, proc.pid)
            log_event(vault_path, f"{name} started (PID {proc.pid})")
            return proc

        except FileNotFoundError:
            msg = f"{name}: command not found — {cmd.split()[0]}"
            print(f"  ERROR: {msg}")
            log_event(vault_path, msg, "ERROR")
            return None

        except Exception as e:
            msg = f"{name}: start failed — {e}"
            print(f"  ERROR: {msg}")
            log_event(vault_path, msg, "ERROR")

            if attempt < MAX_START_RETRIES:
                print(f"  Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                return None

    return None


def stop_process(name: str, vault_path: Path, verbose: bool = False) -> bool:
    """Stop a managed process by PID. Returns True if stopped."""
    pid = read_pid(name)
    if pid is None:
        if verbose:
            print(f"  [{name}] No PID file found")
        return False

    if not is_running(pid):
        if verbose:
            print(f"  [{name}] PID {pid} not running (stale)")
        clear_pid(name)
        return False

    try:
        # Graceful shutdown first
        os.kill(pid, signal.SIGTERM)
        if verbose:
            print(f"  [{name}] Sent SIGTERM to PID {pid}")

        # Wait up to 10s for graceful shutdown
        for _ in range(20):
            if not is_running(pid):
                break
            time.sleep(0.5)
        else:
            # Force kill if still running
            os.kill(pid, signal.SIGKILL)
            if verbose:
                print(f"  [{name}] Sent SIGKILL to PID {pid}")
            time.sleep(1)

        clear_pid(name)
        log_event(vault_path, f"{name} stopped (PID {pid})")
        return True

    except (OSError, ProcessLookupError):
        clear_pid(name)
        return False


def check_status(config: dict, vault_path: Path) -> dict:
    """
    Check status of all managed processes.

    Returns dict: {name: {running: bool, pid: int|None}}
    """
    processes = config.get("processes", {})
    status = {}

    for name in STARTUP_ORDER:
        proc_config = processes.get(name, {})
        enabled = proc_config.get("enabled", False)
        pid = read_pid(name)
        running = pid is not None and is_running(pid)

        # Clean up stale PID
        if pid is not None and not running:
            clear_pid(name)

        status[name] = {
            "enabled": enabled,
            "pid": pid if running else None,
            "running": running,
            "command": proc_config.get("command", "(not configured)"),
        }

    return status


def print_status(status: dict):
    """Pretty-print process status table."""
    print("\nSilver Tier Process Status")
    print("=" * 60)
    print(f"{'Process':<22} {'Status':<12} {'PID':<8} {'Enabled'}")
    print("-" * 60)

    for name, info in status.items():
        state = "RUNNING" if info["running"] else "STOPPED"
        pid_str = str(info["pid"]) if info["pid"] else "-"
        enabled = "yes" if info["enabled"] else "no"
        indicator = "+" if info["running"] else "x"
        print(f"  [{indicator}] {name:<18} {state:<12} {pid_str:<8} {enabled}")

    running = sum(1 for s in status.values() if s["running"])
    total = len(status)
    print("-" * 60)
    print(f"  {running}/{total} processes running\n")


def do_start(config: dict, vault_path: Path, verbose: bool = False):
    """Start all Silver tier processes in order."""
    processes = config.get("processes", {})

    print("Starting Silver Tier AI Employee...")
    print(f"  Vault: {vault_path}")
    print()

    # Ensure vault folders exist
    created = ensure_vault_folders(vault_path)
    if created:
        print(f"  Created vault folders: {', '.join(created)}")

    log_event(vault_path, "Silver tier startup initiated")

    started = 0
    failed = []

    for name in STARTUP_ORDER:
        proc_config = processes.get(name)
        if not proc_config:
            print(f"  [{name}] Not configured in config.yaml — skipping")
            continue

        if not proc_config.get("enabled", False):
            print(f"  [{name}] Disabled — skipping")
            continue

        # Check if already running
        existing_pid = read_pid(name)
        if existing_pid and is_running(existing_pid):
            print(f"  [{name}] Already running (PID {existing_pid})")
            started += 1
            continue

        print(f"  Starting {name}...")
        proc = start_process(name, proc_config["command"], vault_path, verbose)

        if proc:
            print(f"  [{name}] Started (PID {proc.pid})")
            started += 1
        else:
            print(f"  [{name}] FAILED to start")
            failed.append(name)

    print()
    if failed:
        print(f"WARNING: {len(failed)} process(es) failed to start: {', '.join(failed)}")
        log_event(vault_path, f"Startup partial — failed: {', '.join(failed)}", "WARN")
    else:
        print(f"All {started} processes started successfully!")
        log_event(vault_path, f"Startup complete — {started} processes running")

    # Note about email-sender-mcp
    print()
    print("NOTE: email-sender-mcp (Node.js MCP server) is not auto-started.")
    print("  To run it manually:")
    print("    cd .claude/skills/email-sender-mcp && npm start")
    print("  Or configure it in Claude Desktop's MCP settings.")


def do_stop(config: dict, vault_path: Path, verbose: bool = False):
    """Stop all Silver tier processes."""
    print("Stopping Silver Tier AI Employee...")
    log_event(vault_path, "Silver tier shutdown initiated")

    stopped = 0
    # Stop in reverse order (orchestrator first, watchers last)
    for name in reversed(STARTUP_ORDER):
        result = stop_process(name, vault_path, verbose)
        if result:
            print(f"  [{name}] Stopped")
            stopped += 1
        else:
            pid = read_pid(name)
            if pid is None:
                print(f"  [{name}] Not running")
            else:
                print(f"  [{name}] Failed to stop (PID {pid})")

    print(f"\n{stopped} process(es) stopped.")
    log_event(vault_path, f"Shutdown complete — {stopped} processes stopped")


def do_dry_run(config: dict, vault_path: Path, verbose: bool = False):
    """Validate configuration without starting anything."""
    print("Silver Tier — Dry Run Validation")
    print("=" * 50)

    issues = []

    # Check vault path
    if vault_path.exists():
        print(f"  [OK] Vault path: {vault_path}")
    else:
        print(f"  [FAIL] Vault path not found: {vault_path}")
        issues.append("Vault path missing")

    # Check vault folders
    required_folders = [
        "Needs_Action", "Plans", "Done", "Logs",
        "pending-approval", "Approved", "Rejected",
        "In_Progress", "plans", "error",
    ]
    missing = [f for f in required_folders if not (vault_path / f).exists()]
    if missing:
        print(f"  [WARN] Missing vault folders: {', '.join(missing)}")
        print(f"         These will be created on startup.")
    else:
        print(f"  [OK] All {len(required_folders)} vault folders present")

    # Check processes
    processes = config.get("processes", {})
    print(f"\n  Configured processes ({len(processes)}):")
    for name, proc in processes.items():
        enabled = proc.get("enabled", False)
        cmd = proc.get("command", "(missing)")
        status = "enabled" if enabled else "disabled"
        # Check if the script file exists
        parts = cmd.split()
        script = None
        for p in parts:
            if p.endswith(".py") or p.endswith(".js"):
                script = p.replace("{vault}", str(vault_path))
                break
        script_ok = script and Path(script).exists()
        icon = "OK" if script_ok or not enabled else "WARN"
        print(f"    [{icon}] {name} ({status})")
        if verbose:
            print(f"         cmd: {cmd}")
        if not script_ok and enabled:
            issues.append(f"{name}: script not found at {script}")

    # Check schedules
    schedules = config.get("schedules", {})
    print(f"\n  Configured schedules ({len(schedules)}):")
    for name, sched in schedules.items():
        enabled = sched.get("enabled", False)
        cron = sched.get("cron", "?")
        desc = sched.get("description", "")
        status = "enabled" if enabled else "disabled"
        print(f"    [{status}] {name}: {cron} — {desc}")

    # Check environment
    print("\n  Environment:")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        print(f"    [OK] ANTHROPIC_API_KEY set ({api_key[:12]}...)")
    else:
        print("    [WARN] ANTHROPIC_API_KEY not set")

    creds = os.getenv("GMAIL_CREDENTIALS_PATH", "./credentials.json")
    if Path(creds).exists():
        print(f"    [OK] Gmail credentials: {creds}")
    else:
        print(f"    [WARN] Gmail credentials not found: {creds}")

    token = os.getenv("GMAIL_TOKEN_PATH", "./token.json")
    if Path(token).exists():
        print(f"    [OK] Gmail token: {token}")
    else:
        print("    [WARN] Gmail token not found (will need OAuth flow on first run)")

    # Summary
    print()
    if issues:
        print(f"Found {len(issues)} issue(s):")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("All checks passed! Ready to start with:")
        print("  uv run silver/start_silver.py")


def main():
    parser = argparse.ArgumentParser(
        description="Silver Tier Startup — manage all Silver tier skills"
    )
    parser.add_argument(
        "--config",
        default=".claude/skills/main-orchestrator/config.yaml",
        help="Path to config.yaml (default: .claude/skills/main-orchestrator/config.yaml)",
    )
    parser.add_argument(
        "--vault-path",
        default=None,
        help="Override vault path from config",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show status of all managed processes",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop all managed processes",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without starting",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug output",
    )

    args = parser.parse_args()

    config = load_config(args.config)
    vault_path = get_vault_path(config, args.vault_path)

    if args.status:
        status = check_status(config, vault_path)
        print_status(status)
    elif args.stop:
        do_stop(config, vault_path, args.verbose)
    elif args.dry_run:
        do_dry_run(config, vault_path, args.verbose)
    else:
        do_start(config, vault_path, args.verbose)


if __name__ == "__main__":
    main()
