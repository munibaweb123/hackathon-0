# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
#     "python-dotenv>=1.0.0",
# ]
# ///
"""
Gold Tier Startup Script — Full AI Employee System (Silver + Gold).

Manages process lifecycle for ALL Gold tier components:
  Silver tier (Python UV scripts):
    1. gmail-watcher       (polls Gmail → Needs_Action/EMAIL_*)
    2. whatsapp-watcher    (monitors WhatsApp → Needs_Action/WHATSAPP_*)
    3. approval-manager    (monitors pending-approval/ → routes approved actions)
    4. main-orchestrator   (priority queue + cron scheduler)

  Gold tier (Node.js MCP servers):
    5. odoo-accounting-mcp (Odoo JSON-RPC → create invoices, record payments)
    6. social-poster-mcp   (Facebook, Instagram, Twitter posting)
    7. payment-handler-mcp (Stripe, PayPal, bank transfer execution)

  Gold tier (Python UV scripts):
    8. ralph-wiggum-loop   (optional — continuous task completion via stop hooks)

  Installs Ralph Wiggum stop hook into .claude/settings.local.json on first run.
  Runs npm install in each MCP skill dir if node_modules/ is absent.

Usage:
    uv run gold/start_gold.py                   # Start all (Silver + Gold)
    uv run gold/start_gold.py --status          # Check all process status
    uv run gold/start_gold.py --stop            # Graceful shutdown all
    uv run gold/start_gold.py --dry-run         # Validate config + env
    uv run gold/start_gold.py --gold-only       # Start only Gold MCP servers
    uv run gold/start_gold.py --verbose         # Debug logging
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# PID tracking
PID_DIR = Path("/tmp/ai-employee-gold")

# Startup order — Silver watchers first, then orchestration, then Gold MCPs
SILVER_ORDER = [
    "gmail-watcher",
    "whatsapp-watcher",
    "approval-manager",
    "main-orchestrator",
]

GOLD_MCP_ORDER = [
    "odoo-accounting-mcp",
    "social-poster-mcp",
    "payment-handler-mcp",
]

# Gold tier MCP server skill directories (relative to repo root)
MCP_SKILL_DIRS = {
    "odoo-accounting-mcp":  ".claude/skills/odoo-accounting-mcp",
    "social-poster-mcp":    ".claude/skills/social-poster-mcp",
    "payment-handler-mcp":  ".claude/skills/payment-handler-mcp",
}

# Required env vars per component
REQUIRED_ENV = {
    "gmail-watcher":       ["ANTHROPIC_API_KEY"],
    "whatsapp-watcher":    [],
    "approval-manager":    [],
    "main-orchestrator":   [],
    "odoo-accounting-mcp": ["ODOO_URL", "ODOO_DB", "ODOO_USERNAME", "ODOO_PASSWORD"],
    "social-poster-mcp":   ["META_APP_ID", "META_APP_SECRET",
                            "TWITTER_CLIENT_ID", "TWITTER_CLIENT_SECRET"],
    "payment-handler-mcp": ["STRIPE_SECRET_KEY"],
}

# Gold tier additional vault folders
GOLD_VAULT_FOLDERS = [
    "Accounting/invoices",
    "Briefings",
    "Logs/ralph-loop",
]

MAX_START_RETRIES = 3
RETRY_DELAY = 5


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        print(f"ERROR: Config not found: {config_path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_vault_path(config: dict, override: str | None = None) -> Path:
    vault = override or os.getenv("VAULT_PATH") or config.get("vault_path", "./obsidian-vault")
    return Path(vault).resolve()


def ensure_vault_folders(vault_path: Path) -> list[str]:
    """Create all required vault folders (Silver + Gold)."""
    silver_folders = [
        "Needs_Action", "Plans", "Done", "Logs",
        "pending-approval", "Approved", "Rejected",
        "Attachments", "Reports", "In_Progress",
        "plans", "error",
    ]
    gold_folders = GOLD_VAULT_FOLDERS
    created = []
    for folder in silver_folders + gold_folders:
        full = vault_path / folder
        if not full.exists():
            full.mkdir(parents=True, exist_ok=True)
            created.append(folder)
    return created


def write_pid(name: str, pid: int):
    PID_DIR.mkdir(parents=True, exist_ok=True)
    (PID_DIR / f"{name}.pid").write_text(str(pid))


def read_pid(name: str) -> int | None:
    pid_file = PID_DIR / f"{name}.pid"
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return None


def clear_pid(name: str):
    pid_file = PID_DIR / f"{name}.pid"
    if pid_file.exists():
        pid_file.unlink()


def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def log_event(vault_path: Path, message: str, level: str = "INFO"):
    logs_dir = vault_path / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "gold_startup.log"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] [{level}] {message}\n")


# ── npm install helper ────────────────────────────────────────────────────────

def ensure_npm_installed(name: str, repo_root: Path, verbose: bool = False) -> bool:
    """Run npm install in an MCP skill dir if node_modules/ is absent."""
    skill_dir_rel = MCP_SKILL_DIRS.get(name)
    if not skill_dir_rel:
        return True
    skill_dir = repo_root / skill_dir_rel
    node_modules = skill_dir / "node_modules"
    package_json = skill_dir / "package.json"

    if not package_json.exists():
        print(f"  [{name}] WARNING: package.json not found at {skill_dir}")
        return False

    if node_modules.exists():
        if verbose:
            print(f"  [{name}] node_modules already present")
        return True

    print(f"  [{name}] Running npm install...")
    try:
        result = subprocess.run(
            ["npm", "install", "--silent"],
            cwd=skill_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print(f"  [{name}] npm install complete")
            return True
        else:
            print(f"  [{name}] npm install failed: {result.stderr[:200]}")
            return False
    except FileNotFoundError:
        print(f"  [{name}] ERROR: npm not found — install Node.js 18+")
        return False
    except subprocess.TimeoutExpired:
        print(f"  [{name}] ERROR: npm install timed out")
        return False


# ── Process start/stop ────────────────────────────────────────────────────────

def start_process(
    name: str, command: str, vault_path: Path,
    is_node: bool = False, verbose: bool = False
) -> "subprocess.Popen | None":
    cmd = command.replace("{vault}", str(vault_path))

    for attempt in range(1, MAX_START_RETRIES + 1):
        try:
            if verbose:
                print(f"  [{name}] Attempt {attempt}/{MAX_START_RETRIES}: {cmd[:80]}")

            log_dir = vault_path / "Logs"
            log_dir.mkdir(parents=True, exist_ok=True)

            proc = subprocess.Popen(
                cmd.split(),
                stdout=open(log_dir / f"{name}.stdout.log", "a"),
                stderr=open(log_dir / f"{name}.stderr.log", "a"),
                start_new_session=True,
            )

            time.sleep(2 if not is_node else 3)

            if proc.poll() is not None:
                print(f"  [{name}] WARNING: exited immediately (code {proc.returncode})")
                if attempt < MAX_START_RETRIES:
                    print(f"  Retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                    continue
                return None

            write_pid(name, proc.pid)
            return proc

        except FileNotFoundError:
            print(f"  [{name}] ERROR: command not found — {cmd.split()[0]}")
            return None
        except Exception as e:
            print(f"  [{name}] ERROR: {e}")
            if attempt < MAX_START_RETRIES:
                time.sleep(RETRY_DELAY)

    return None


def stop_process(name: str, vault_path: Path, verbose: bool = False) -> bool:
    pid = read_pid(name)
    if pid is None:
        return False
    if not is_running(pid):
        clear_pid(name)
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            if not is_running(pid):
                break
            time.sleep(0.5)
        else:
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)
        clear_pid(name)
        log_event(vault_path, f"{name} stopped (PID {pid})")
        return True
    except (OSError, ProcessLookupError):
        clear_pid(name)
        return False


# ── Ralph Wiggum hook installation ───────────────────────────────────────────

def install_ralph_hook(repo_root: Path, vault_path: Path, verbose: bool = False) -> bool:
    """Install or verify Ralph Wiggum stop hook in .claude/settings.local.json."""
    settings_path = repo_root / ".claude" / "settings.local.json"
    ralph_hook = str(repo_root / ".claude/skills/ralph-wiggum-loop/stop_hook.sh")

    # Load or create settings
    if settings_path.exists():
        try:
            with open(settings_path, encoding="utf-8") as f:
                settings = json.load(f)
        except json.JSONDecodeError:
            settings = {}
    else:
        settings = {}

    # Check if hook already installed
    hooks = settings.get("hooks", {})
    stop_hooks = hooks.get("Stop", [])
    for hook in stop_hooks:
        if ralph_hook in str(hook):
            if verbose:
                print("  [ralph-wiggum-loop] Stop hook already installed")
            return True

    # Add the hook
    if "Stop" not in hooks:
        hooks["Stop"] = []
    hooks["Stop"].append({"matcher": "", "hooks": [{"type": "command", "command": ralph_hook}]})
    settings["hooks"] = hooks

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

    print("  [ralph-wiggum-loop] Stop hook installed in .claude/settings.local.json")
    log_event(vault_path, "Ralph Wiggum stop hook installed")
    return True


# ── Status ────────────────────────────────────────────────────────────────────

def check_status(config: dict) -> dict:
    all_names = SILVER_ORDER + GOLD_MCP_ORDER
    processes = config.get("processes", {})
    status = {}

    for name in all_names:
        proc_config = processes.get(name, {})
        pid = read_pid(name)
        running = pid is not None and is_running(pid)
        if pid is not None and not running:
            clear_pid(name)
        status[name] = {
            "enabled": proc_config.get("enabled", name in GOLD_MCP_ORDER),
            "pid": pid if running else None,
            "running": running,
            "tier": "silver" if name in SILVER_ORDER else "gold",
        }
    return status


def print_status(status: dict):
    print("\nGold Tier AI Employee — Process Status")
    print("=" * 62)
    print(f"  {'Process':<24} {'Tier':<8} {'Status':<10} {'PID'}")
    print("-" * 62)
    for name, info in status.items():
        state = "RUNNING" if info["running"] else "STOPPED"
        pid_str = str(info["pid"]) if info["pid"] else "-"
        tier = info["tier"].upper()
        icon = "+" if info["running"] else "x"
        print(f"  [{icon}] {name:<22} {tier:<8} {state:<10} {pid_str}")

    running = sum(1 for s in status.values() if s["running"])
    total = len(status)
    print("-" * 62)
    print(f"  {running}/{total} processes running\n")


# ── Actions ───────────────────────────────────────────────────────────────────

def do_start(config: dict, vault_path: Path, repo_root: Path,
             gold_only: bool = False, verbose: bool = False):
    processes = config.get("processes", {})

    print("Starting Gold Tier AI Employee (Full System)...")
    print(f"  Vault: {vault_path}")
    print(f"  Repo:  {repo_root}")
    print()

    created = ensure_vault_folders(vault_path)
    if created:
        print(f"  Created vault folders: {', '.join(created)}")

    log_event(vault_path, "Gold tier startup initiated")

    # Phase 1: Silver tier (if not gold-only)
    if not gold_only:
        print("Phase 1: Silver tier processes")
        print("-" * 40)
        for name in SILVER_ORDER:
            proc_config = processes.get(name)
            if not proc_config or not proc_config.get("enabled", True):
                print(f"  [{name}] Disabled — skipping")
                continue

            existing_pid = read_pid(name)
            if existing_pid and is_running(existing_pid):
                print(f"  [{name}] Already running (PID {existing_pid})")
                continue

            print(f"  Starting {name}...")
            proc = start_process(name, proc_config["command"], vault_path,
                                 is_node=False, verbose=verbose)
            if proc:
                print(f"  [{name}] Started (PID {proc.pid})")
                log_event(vault_path, f"{name} started (PID {proc.pid})")
            else:
                print(f"  [{name}] FAILED — check Logs/{name}.stderr.log")

    # Phase 2: Gold MCP servers — npm install + start
    print()
    print("Phase 2: Gold tier MCP servers (Node.js)")
    print("-" * 40)
    for name in GOLD_MCP_ORDER:
        existing_pid = read_pid(name)
        if existing_pid and is_running(existing_pid):
            print(f"  [{name}] Already running (PID {existing_pid})")
            continue

        # Ensure npm install
        if not ensure_npm_installed(name, repo_root, verbose):
            print(f"  [{name}] Skipping (npm install failed)")
            continue

        # Build start command for Node.js MCP server
        skill_dir = repo_root / MCP_SKILL_DIRS[name]
        server_js = skill_dir / "mcp_server.js"
        if not server_js.exists():
            print(f"  [{name}] ERROR: mcp_server.js not found at {server_js}")
            continue

        command = f"node {server_js}"
        print(f"  Starting {name}...")
        proc = start_process(name, command, vault_path, is_node=True, verbose=verbose)
        if proc:
            print(f"  [{name}] Started (PID {proc.pid})")
            log_event(vault_path, f"{name} started (PID {proc.pid})")
        else:
            print(f"  [{name}] FAILED — check Logs/{name}.stderr.log")

    # Phase 3: Ralph Wiggum hook (one-time install)
    print()
    print("Phase 3: Ralph Wiggum loop")
    print("-" * 40)
    install_ralph_hook(repo_root, vault_path, verbose)

    print()
    print("Gold tier startup complete.")
    print()
    print("Note: email-sender-mcp not auto-started (configure in Claude Desktop MCP settings).")
    print("      See .claude/skills/email-sender-mcp/SKILL.md for setup.")


def do_stop(config: dict, vault_path: Path, verbose: bool = False):
    print("Stopping Gold Tier AI Employee...")
    log_event(vault_path, "Gold tier shutdown initiated")

    all_names = list(reversed(GOLD_MCP_ORDER)) + list(reversed(SILVER_ORDER))
    stopped = 0
    for name in all_names:
        result = stop_process(name, vault_path, verbose)
        if result:
            print(f"  [{name}] Stopped")
            stopped += 1
        else:
            pid = read_pid(name)
            print(f"  [{name}] {'Not running' if pid is None else f'Failed to stop (PID {pid})'}")

    print(f"\n{stopped} process(es) stopped.")
    log_event(vault_path, f"Shutdown complete — {stopped} processes stopped")


def do_dry_run(config: dict, vault_path: Path, repo_root: Path, verbose: bool = False):
    print("Gold Tier — Dry Run Validation")
    print("=" * 60)
    issues = []

    # Vault
    print(f"  {'[OK]' if vault_path.exists() else '[FAIL]'} Vault: {vault_path}")
    if not vault_path.exists():
        issues.append("Vault path missing")

    # Environment
    print("\n  Environment:")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    print(f"  {'[OK]' if api_key and 'your_' not in api_key else '[WARN]'} ANTHROPIC_API_KEY")
    for name, required in REQUIRED_ENV.items():
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            print(f"  [WARN] {name}: missing {', '.join(missing)}")
        elif required:
            print(f"  [OK]   {name}: all env vars set")

    # Silver processes
    print("\n  Silver tier processes:")
    processes = config.get("processes", {})
    for name in SILVER_ORDER:
        proc = processes.get(name, {})
        enabled = proc.get("enabled", False)
        cmd = proc.get("command", "(not in config)")
        script = next((p for p in cmd.split() if p.endswith(".py") or p.endswith(".js")), None)
        script_exists = script and Path(script.replace("{vault}", str(vault_path))).exists()
        icon = "OK" if (script_exists or not enabled) else "WARN"
        print(f"  [{icon}] {name} ({'enabled' if enabled else 'disabled'})")

    # Gold MCP servers
    print("\n  Gold tier MCP servers:")
    for name in GOLD_MCP_ORDER:
        skill_dir = repo_root / MCP_SKILL_DIRS.get(name, "")
        server_js = skill_dir / "mcp_server.js"
        pkg = skill_dir / "package.json"
        node_mods = skill_dir / "node_modules"
        ok = server_js.exists() and pkg.exists()
        npm_icon = "OK" if node_mods.exists() else "WARN (run npm install)"
        print(f"  {'[OK]' if ok else '[FAIL]'} {name} — server.js {'found' if ok else 'missing'} | npm: {npm_icon}")
        if not ok:
            issues.append(f"{name}: mcp_server.js not found")

    # Summary
    print()
    if issues:
        print(f"  {len(issues)} issue(s) found:")
        for i in issues:
            print(f"  - {i}")
    else:
        print("  All checks passed. Ready to start with:")
        print("    uv run gold/start_gold.py")


def main():
    parser = argparse.ArgumentParser(
        description="Gold Tier Startup — full AI Employee system (Silver + Gold)"
    )
    parser.add_argument("--config", default=".claude/skills/main-orchestrator/config.yaml")
    parser.add_argument("--vault-path", default=None)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--gold-only", action="store_true",
                        help="Start only Gold MCP servers (skip Silver processes)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    vault_path = get_vault_path(config, args.vault_path)
    repo_root = Path(__file__).parent.parent.resolve()

    if args.status:
        status = check_status(config)
        print_status(status)
    elif args.stop:
        do_stop(config, vault_path, args.verbose)
    elif args.dry_run:
        do_dry_run(config, vault_path, repo_root, args.verbose)
    else:
        do_start(config, vault_path, repo_root, args.gold_only, args.verbose)


if __name__ == "__main__":
    main()
