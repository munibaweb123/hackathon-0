# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
Vault Sync — synchronizes Obsidian vault state between Cloud and Local agents.

Uses Git for sync with rules-based conflict resolution, claim-by-move pattern
for work assignment, and Dashboard.md single-writer enforcement.

Usage with UV (recommended):
    uv run vault_sync.py --vault-path ../../obsidian-vault --init
    uv run vault_sync.py --vault-path ../../obsidian-vault --sync
    uv run vault_sync.py --vault-path ../../obsidian-vault --watch --interval 60
"""

import argparse
import json
import logging
import re
import signal
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))
from git_handler import GitHandler
from conflict_resolver import ConflictResolver

logger = logging.getLogger("vault-sync")

SKILL_DIR = Path(__file__).resolve().parent

# Default conflict resolution rules
DEFAULT_RULES = {
    "Dashboard.md": "local_wins",
    "Logs/*.json": "append_both",
    "Logs/**/*.json": "append_both",
    "config/*": "remote_wins",
    "Updates/*.md": "remote_wins",
    "Updates/**": "remote_wins",
    "In_Progress/**": "local_wins",
}


class VaultSync:
    """
    Synchronizes Obsidian vault between Cloud and Local agents via Git.
    """

    def __init__(self, vault_path: str) -> None:
        self.vault = Path(vault_path).resolve()
        self.git = GitHandler(str(self.vault))
        self.resolver = ConflictResolver()
        self.running = False

        # Ensure sync-related directories exist
        for d in ["Needs_Action", "In_Progress", "Done", "Updates", "Logs", "Signals"]:
            (self.vault / d).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------
    def init(self, remote_url: Optional[str] = None) -> bool:
        """
        Initialize the vault as a git repo with .gitignore.

        Args:
            remote_url: Optional Git remote URL to add as origin.
        """
        template = SKILL_DIR / ".gitignore.template"

        success = self.git.init(
            gitignore_template=str(template) if template.exists() else None
        )
        if not success:
            print("Failed to initialize git repository")
            return False

        if remote_url:
            self.git.add_remote(remote_url)

        # Initial commit if new repo
        if self.git.has_changes():
            self.git.stage_all()
            self.git.commit("init: vault sync initialized")

        print(f"Vault sync initialized at {self.vault}")
        if remote_url:
            print(f"  Remote: {remote_url}")
        print(f"  .gitignore: {'copied' if (self.vault / '.gitignore').exists() else 'missing'}")

        self._log_sync({
            "event": "init",
            "remote": remote_url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return True

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------
    def sync(self) -> Dict[str, Any]:
        """Full sync cycle: commit local → pull → resolve → push."""
        if not self.git.is_repo():
            return {"success": False, "message": "Not a git repository. Run --init first."}

        result = self.git.sync(
            resolver=self.resolver,
            rules=DEFAULT_RULES,
        )

        self._log_sync({
            "event": "sync",
            "success": result["success"],
            "committed": result.get("committed", False),
            "pulled": result.get("pulled", False),
            "pushed": result.get("pushed", False),
            "conflicts_resolved": result.get("conflicts_resolved", 0),
            "message": result.get("message", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Merge any Cloud updates into Dashboard.md
        self.merge_updates()

        # Update dashboard with sync status
        self.update_dashboard()

        if result["success"]:
            print(f"Sync complete", end="")
            parts = []
            if result.get("committed"):
                parts.append("committed")
            if result.get("pulled"):
                parts.append("pulled")
            if result.get("pushed"):
                parts.append("pushed")
            if result.get("conflicts_resolved"):
                parts.append(f"{result['conflicts_resolved']} conflicts resolved")
            if parts:
                print(f" ({', '.join(parts)})")
            else:
                print(" (no changes)")
        else:
            print(f"Sync failed: {result.get('message', 'unknown error')}")

        return result

    # ------------------------------------------------------------------
    # Watch (continuous sync)
    # ------------------------------------------------------------------
    def watch(self, interval: int = 60) -> None:
        """Continuous sync loop."""
        self.running = True
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        print(f"Vault sync watching started (interval: {interval}s)")
        print(f"  Vault: {self.vault}")
        print(f"  Press Ctrl+C to stop\n")

        while self.running:
            try:
                if self.git.has_changes() or self.git.has_remote():
                    result = self.sync()
                    if not result["success"]:
                        logger.warning(f"Sync issue: {result.get('message')}")
                else:
                    logger.debug("No changes detected")

                time.sleep(interval)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Watch error: {e}")
                time.sleep(5)

        print("\nVault sync watching stopped")

    def _shutdown(self, signum, frame):
        self.running = False

    # ------------------------------------------------------------------
    # Claim-by-move
    # ------------------------------------------------------------------
    def claim(self, file_path: str, agent_name: str) -> bool:
        """
        Claim a file by moving it from Needs_Action/ to In_Progress/{agent}/.

        Immediately commits and pushes to prevent race conditions.
        """
        source = self.vault / file_path
        if not source.exists():
            print(f"File not found: {file_path}")
            return False

        agent_dir = self.vault / "In_Progress" / agent_name
        agent_dir.mkdir(parents=True, exist_ok=True)

        dest = agent_dir / source.name
        if dest.exists():
            print(f"Already claimed: {dest.name}")
            return False

        shutil.move(str(source), str(dest))

        # Immediate commit + push for claim atomicity
        self.git.stage_all()
        self.git.commit(f"claim: {source.name} -> In_Progress/{agent_name}/")
        if self.git.has_remote():
            self.git.push()

        self._log_sync({
            "event": "claim",
            "file": source.name,
            "agent": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        print(f"Claimed: {source.name} -> In_Progress/{agent_name}/")
        return True

    def release(self, file_path: str, agent_name: str, done: bool = True) -> bool:
        """
        Release a claimed file to Done/ or back to Needs_Action/.

        Args:
            file_path: Path relative to vault (e.g., In_Progress/cloud-1/task.md)
            agent_name: Agent releasing the file
            done: If True, move to Done/; if False, return to Needs_Action/
        """
        source = self.vault / file_path
        if not source.exists():
            print(f"File not found: {file_path}")
            return False

        if done:
            dest_dir = self.vault / "Done"
        else:
            dest_dir = self.vault / "Needs_Action"

        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / source.name

        shutil.move(str(source), str(dest))

        target = "Done" if done else "Needs_Action"
        self.git.stage_all()
        self.git.commit(f"release: {source.name} -> {target}/ (by {agent_name})")
        if self.git.has_remote():
            self.git.push()

        self._log_sync({
            "event": "release",
            "file": source.name,
            "agent": agent_name,
            "destination": target,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        print(f"Released: {source.name} -> {target}/")
        return True

    # ------------------------------------------------------------------
    # Merge Cloud updates into Dashboard.md
    # ------------------------------------------------------------------
    def merge_updates(self) -> int:
        """
        Read Updates/*.md files (Cloud-written) and merge into Dashboard.md.

        Dashboard.md is Local-only (single-writer rule). Cloud writes to
        Updates/ and Local merges when syncing.

        Returns:
            Number of updates merged.
        """
        updates_dir = self.vault / "Updates"
        if not updates_dir.exists():
            return 0

        update_files = sorted(updates_dir.glob("*.md"))
        if not update_files:
            return 0

        dashboard = self.vault / "Dashboard.md"
        now = datetime.now(timezone.utc)

        # Read existing dashboard or create stub
        if dashboard.exists():
            content = dashboard.read_text(encoding="utf-8")
        else:
            content = f"""---
type: dashboard
updated_at: {now.isoformat()}
---

# AI Employee Dashboard

"""

        # Merge each update
        for update_file in update_files:
            update_content = update_file.read_text(encoding="utf-8")

            # Strip frontmatter from update
            if update_content.startswith("---"):
                parts = update_content.split("---", 2)
                if len(parts) >= 3:
                    update_body = parts[2].strip()
                else:
                    update_body = update_content
            else:
                update_body = update_content

            # Check if update has a section header we should replace
            section_match = re.match(r"^##\s+(.+)$", update_body, re.MULTILINE)
            if section_match:
                section_title = section_match.group(0)
                if section_title in content:
                    # Replace existing section
                    start_idx = content.index(section_title)
                    rest = content[start_idx + len(section_title):]
                    next_heading = rest.find("\n## ")
                    if next_heading >= 0:
                        end_idx = start_idx + len(section_title) + next_heading
                        content = content[:start_idx] + update_body + "\n\n" + content[end_idx:]
                    else:
                        content = content[:start_idx] + update_body + "\n"
                else:
                    content = content.rstrip() + "\n\n" + update_body + "\n"
            else:
                content = content.rstrip() + "\n\n" + update_body + "\n"

            # Move update to Done/
            done_dir = self.vault / "Done"
            done_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(update_file), str(done_dir / update_file.name))

        # Update timestamp in frontmatter
        content = re.sub(
            r"^updated_at:\s*.+$",
            f"updated_at: {now.isoformat()}",
            content,
            flags=re.MULTILINE,
        )

        dashboard.write_text(content, encoding="utf-8")

        if update_files:
            logger.info(f"Merged {len(update_files)} update(s) into Dashboard.md")

        return len(update_files)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    def health_check(self) -> Dict[str, Any]:
        """Check sync health."""
        health = {
            "is_repo": self.git.is_repo(),
            "has_remote": False,
            "pending_changes": False,
            "conflicts": [],
            "last_sync": None,
            "in_progress_count": 0,
            "needs_action_count": 0,
        }

        if not health["is_repo"]:
            return health

        health["has_remote"] = self.git.has_remote()
        health["pending_changes"] = self.git.has_changes()

        status = self.git.status()
        health["conflicts"] = status.get("conflicts", [])

        # Count active items
        in_progress = self.vault / "In_Progress"
        if in_progress.exists():
            health["in_progress_count"] = sum(
                1 for _ in in_progress.rglob("*.md")
            )

        needs_action = self.vault / "Needs_Action"
        if needs_action.exists():
            health["needs_action_count"] = sum(
                1 for _ in needs_action.rglob("*.md")
            )

        # Last sync from log
        log = self._read_log()
        sync_events = [e for e in log if e.get("event") == "sync"]
        if sync_events:
            health["last_sync"] = sync_events[-1].get("timestamp")

        return health

    def show_status(self) -> None:
        """Display sync status."""
        health = self.health_check()

        print(f"\nVault Sync Status")
        print(f"  Vault:          {self.vault}")
        print(f"  Git repo:       {'yes' if health['is_repo'] else 'NO — run --init'}")
        print(f"  Remote:         {'configured' if health['has_remote'] else 'none'}")
        print(f"  Pending changes:{' yes' if health['pending_changes'] else ' none'}")
        print(f"  Conflicts:      {len(health['conflicts']) or 'none'}")
        print(f"  In Progress:    {health['in_progress_count']} item(s)")
        print(f"  Needs Action:   {health['needs_action_count']} item(s)")

        if health.get("last_sync"):
            print(f"  Last sync:      {health['last_sync'][:19]}")

        if health["conflicts"]:
            print(f"\n  Conflicted files:")
            for f in health["conflicts"]:
                print(f"    - {f}")

    def show_health(self) -> None:
        """Detailed health check output."""
        health = self.health_check()
        self.show_status()

        # Check gitignore
        gitignore = self.vault / ".gitignore"
        print(f"\n  .gitignore:     {'present' if gitignore.exists() else 'MISSING — run --init'}")

        # Check sync folders
        for folder in ["Needs_Action", "In_Progress", "Done", "Updates", "Signals"]:
            path = self.vault / folder
            count = sum(1 for _ in path.rglob("*.md")) if path.exists() else 0
            exists = "ok" if path.exists() else "missing"
            print(f"  {folder + '/':16s} {exists} ({count} files)")

        # Log stats
        log = self._read_log()
        print(f"\n  Total sync events: {len(log)}")
        claims = sum(1 for e in log if e.get("event") == "claim")
        releases = sum(1 for e in log if e.get("event") == "release")
        print(f"  Claims: {claims} | Releases: {releases}")

    # ------------------------------------------------------------------
    # Offline queue
    # ------------------------------------------------------------------
    def queue_change(self, event: Dict[str, Any]) -> None:
        """Queue a change for later sync (offline mode)."""
        queue_file = self.vault / "Logs" / "sync_queue.json"
        queue = []
        if queue_file.exists():
            try:
                queue = json.loads(queue_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                queue = []

        event["queued_at"] = datetime.now(timezone.utc).isoformat()
        queue.append(event)
        queue_file.write_text(json.dumps(queue, indent=2, default=str), encoding="utf-8")

    def flush_queue(self) -> int:
        """Process queued changes."""
        queue_file = self.vault / "Logs" / "sync_queue.json"
        if not queue_file.exists():
            return 0

        try:
            queue = json.loads(queue_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return 0

        if not queue:
            return 0

        # Just sync — queued changes are already on disk
        result = self.sync()
        if result["success"]:
            # Clear queue
            queue_file.write_text("[]", encoding="utf-8")
            logger.info(f"Flushed {len(queue)} queued change(s)")
            return len(queue)

        return 0

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def update_dashboard(self) -> None:
        """Write sync health section to Dashboard.md."""
        dashboard = self.vault / "Dashboard.md"
        now = datetime.now(timezone.utc)
        health = self.health_check()

        in_progress = health["in_progress_count"]
        needs_action = health["needs_action_count"]
        last_sync = health.get("last_sync", "never")
        if isinstance(last_sync, str) and len(last_sync) > 19:
            last_sync = last_sync[:19]

        section = f"""
## Vault Sync Status

| Metric | Value |
|--------|-------|
| Last Sync | {last_sync} |
| Pending Changes | {'yes' if health['pending_changes'] else 'none'} |
| In Progress | {in_progress} item(s) |
| Needs Action | {needs_action} item(s) |
| Conflicts | {len(health.get('conflicts', []))} |
| Updated | {now.strftime('%Y-%m-%d %H:%M')} UTC |

"""

        if dashboard.exists():
            content = dashboard.read_text(encoding="utf-8")
            marker = "## Vault Sync Status"
            if marker in content:
                start_idx = content.index(marker)
                rest = content[start_idx + len(marker):]
                next_heading = rest.find("\n## ")
                if next_heading >= 0:
                    end_idx = start_idx + len(marker) + next_heading
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
    # Internal helpers
    # ------------------------------------------------------------------
    def _log_sync(self, event: Dict[str, Any]) -> None:
        """Append to Logs/vault_sync.json."""
        log_file = self.vault / "Logs" / "vault_sync.json"
        log = self._read_log()
        log.append(event)
        log_file.write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")

    def _read_log(self) -> list:
        """Read sync log."""
        log_file = self.vault / "Logs" / "vault_sync.json"
        if not log_file.exists():
            return []
        try:
            return json.loads(log_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return []

    def _notify_conflict(self, files: List[str]) -> None:
        """Create notification for unresolved conflicts."""
        now = datetime.now(timezone.utc)
        needs_dir = self.vault / "Needs_Action"
        needs_dir.mkdir(parents=True, exist_ok=True)

        file_list = "\n".join(f"- `{f}`" for f in files)
        content = f"""---
type: notification
category: sync_conflict
created: {now.isoformat()}
priority: high
---

# Vault Sync: Unresolved Conflicts

The following files have merge conflicts that could not be auto-resolved:

{file_list}

Please resolve manually and commit.

---
_Generated by Vault Sync at {now.strftime('%Y-%m-%d %H:%M UTC')}_
"""

        filename = f"NOTIFY_SYNC_CONFLICT_{now.strftime('%Y%m%d_%H%M')}.md"
        (needs_dir / filename).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Vault Sync — synchronize Obsidian vault between Cloud and Local agents"
    )
    parser.add_argument(
        "--vault-path",
        default="./obsidian-vault",
        help="Path to the Obsidian vault (default: ./obsidian-vault)",
    )

    # Modes
    parser.add_argument("--init", action="store_true", help="Initialize vault as git repo")
    parser.add_argument("--remote", type=str, help="Git remote URL (with --init)")
    parser.add_argument("--sync", action="store_true", help="One-shot sync cycle")
    parser.add_argument("--watch", action="store_true", help="Continuous sync loop")
    parser.add_argument("--interval", type=int, default=60, help="Watch interval in seconds")
    parser.add_argument("--claim", type=str, metavar="FILE", help="Claim a file")
    parser.add_argument("--release", type=str, metavar="FILE", help="Release a claimed file")
    parser.add_argument("--agent", type=str, help="Agent name (with --claim/--release)")
    parser.add_argument("--done", action="store_true", help="Release to Done/ (with --release)")
    parser.add_argument("--merge-updates", action="store_true", help="Merge Cloud updates into Dashboard.md")
    parser.add_argument("--status", action="store_true", help="Show sync status")
    parser.add_argument("--health", action="store_true", help="Detailed health check")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    vs = VaultSync(args.vault_path)

    if args.init:
        vs.init(remote_url=args.remote)
    elif args.sync:
        vs.sync()
    elif args.watch:
        vs.watch(interval=args.interval)
    elif args.claim:
        if not args.agent:
            print("Error: --agent required with --claim")
            sys.exit(1)
        vs.claim(args.claim, args.agent)
    elif args.release:
        if not args.agent:
            print("Error: --agent required with --release")
            sys.exit(1)
        vs.release(args.release, args.agent, done=args.done)
    elif args.merge_updates:
        count = vs.merge_updates()
        print(f"Merged {count} update(s) into Dashboard.md")
    elif args.status:
        vs.show_status()
    elif args.health:
        vs.show_health()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
