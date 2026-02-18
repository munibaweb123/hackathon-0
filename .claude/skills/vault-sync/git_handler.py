"""
Git Handler — wraps git CLI operations via subprocess.

Zero external dependencies — uses git CLI directly.
Handles init, stage, commit, pull, push, and conflict detection.
"""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("vault-sync.git")


class GitHandler:
    """
    Git operations wrapper using subprocess.

    All git commands run in the repo_path working directory.
    """

    def __init__(self, repo_path: str) -> None:
        self.repo_path = Path(repo_path).resolve()

        # Verify git is available
        if not shutil.which("git"):
            raise RuntimeError("git not found on PATH")

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------
    def init(self, gitignore_template: Optional[str] = None) -> bool:
        """Initialize as git repo if not already one. Copy .gitignore template."""
        if not self.is_repo():
            result = self._run_git(["init"])
            if result["returncode"] != 0:
                logger.error(f"git init failed: {result['stderr']}")
                return False
            logger.info("Initialized git repository")

        # Copy .gitignore template if provided and none exists
        gitignore_path = self.repo_path / ".gitignore"
        if gitignore_template and not gitignore_path.exists():
            template = Path(gitignore_template)
            if template.exists():
                shutil.copy2(str(template), str(gitignore_path))
                logger.info("Copied .gitignore template")

        return True

    def add_remote(self, url: str, name: str = "origin") -> bool:
        """Add a remote repository."""
        result = self._run_git(["remote", "add", name, url])
        if result["returncode"] != 0:
            # May already exist
            if "already exists" in result["stderr"]:
                logger.info(f"Remote '{name}' already exists")
                return True
            logger.error(f"Failed to add remote: {result['stderr']}")
            return False
        logger.info(f"Added remote '{name}': {url}")
        return True

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def is_repo(self) -> bool:
        """Check if repo_path is a git repository."""
        result = self._run_git(["rev-parse", "--is-inside-work-tree"])
        return result["returncode"] == 0

    def has_remote(self) -> bool:
        """Check if any remote is configured."""
        result = self._run_git(["remote"])
        return result["returncode"] == 0 and result["stdout"].strip() != ""

    def has_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        result = self._run_git(["status", "--porcelain"])
        return result["returncode"] == 0 and result["stdout"].strip() != ""

    def status(self) -> Dict[str, Any]:
        """
        Get detailed git status.

        Returns:
            {modified: [], added: [], deleted: [], untracked: [], conflicts: []}
        """
        result = self._run_git(["status", "--porcelain"])
        if result["returncode"] != 0:
            return {"error": result["stderr"]}

        status = {
            "modified": [],
            "added": [],
            "deleted": [],
            "untracked": [],
            "conflicts": [],
        }

        for line in result["stdout"].strip().split("\n"):
            if not line.strip():
                continue
            code = line[:2]
            filepath = line[3:].strip()

            if code == "UU" or code == "AA" or code == "DD":
                status["conflicts"].append(filepath)
            elif code.startswith("?"):
                status["untracked"].append(filepath)
            elif "D" in code:
                status["deleted"].append(filepath)
            elif "A" in code:
                status["added"].append(filepath)
            elif "M" in code or "R" in code:
                status["modified"].append(filepath)

        return status

    # ------------------------------------------------------------------
    # Stage, Commit
    # ------------------------------------------------------------------
    def stage_all(self) -> bool:
        """Stage all changes (respects .gitignore)."""
        result = self._run_git(["add", "-A"])
        return result["returncode"] == 0

    def commit(self, message: str = "") -> bool:
        """Create a commit with the given message."""
        if not message:
            message = self._auto_message()

        if not self.has_changes():
            # Check if there are staged changes
            result = self._run_git(["diff", "--cached", "--quiet"])
            if result["returncode"] == 0:
                logger.debug("Nothing to commit")
                return True  # Not an error — just nothing to do

        result = self._run_git(["commit", "-m", message])
        if result["returncode"] != 0:
            if "nothing to commit" in result["stdout"]:
                return True
            logger.error(f"Commit failed: {result['stderr']}")
            return False

        logger.info(f"Committed: {message[:60]}")
        return True

    # ------------------------------------------------------------------
    # Pull, Push
    # ------------------------------------------------------------------
    def pull(self, remote: str = "origin", branch: str = "main") -> Dict[str, Any]:
        """
        Pull from remote.

        Returns:
            {success: bool, conflicts: [], message: str}
        """
        if not self.has_remote():
            return {"success": True, "conflicts": [], "message": "No remote configured"}

        result = self._run_git(["pull", "--no-rebase", remote, branch])

        if result["returncode"] == 0:
            return {
                "success": True,
                "conflicts": [],
                "message": result["stdout"].strip(),
            }

        # Check for merge conflicts
        if "CONFLICT" in result["stdout"] or "Automatic merge failed" in result["stdout"]:
            conflicts = self.get_conflicts()
            return {
                "success": False,
                "conflicts": conflicts,
                "message": "Merge conflicts detected",
            }

        # Other error (network, auth, etc.)
        return {
            "success": False,
            "conflicts": [],
            "message": result["stderr"].strip() or result["stdout"].strip(),
        }

    def push(self, remote: str = "origin", branch: str = "main") -> bool:
        """Push to remote."""
        if not self.has_remote():
            logger.debug("No remote configured — skip push")
            return True

        result = self._run_git(["push", remote, branch])
        if result["returncode"] != 0:
            logger.error(f"Push failed: {result['stderr']}")
            return False

        logger.info(f"Pushed to {remote}/{branch}")
        return True

    # ------------------------------------------------------------------
    # Conflicts
    # ------------------------------------------------------------------
    def get_conflicts(self) -> List[str]:
        """List conflicted files after a failed merge."""
        result = self._run_git(["diff", "--name-only", "--diff-filter=U"])
        if result["returncode"] != 0:
            return []
        return [f.strip() for f in result["stdout"].strip().split("\n") if f.strip()]

    def resolve_conflicts(self, resolver, rules: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Use a ConflictResolver to resolve all conflicts.

        Args:
            resolver: ConflictResolver instance
            rules: Strategy rules dict (glob pattern → strategy)

        Returns:
            Resolution result dict
        """
        result = resolver.auto_resolve(str(self.repo_path), rules)

        # Stage resolved files
        for resolved_file in result.get("resolved", []):
            self._run_git(["add", resolved_file])

        return result

    def abort_merge(self) -> bool:
        """Abort an in-progress merge."""
        result = self._run_git(["merge", "--abort"])
        return result["returncode"] == 0

    # ------------------------------------------------------------------
    # Sync (full cycle)
    # ------------------------------------------------------------------
    def sync(self, resolver=None, rules=None) -> Dict[str, Any]:
        """
        Full sync cycle: stage → commit → pull → resolve → push.

        Returns:
            {success: bool, committed: bool, pulled: bool, pushed: bool,
             conflicts_resolved: int, message: str}
        """
        sync_result = {
            "success": False,
            "committed": False,
            "pulled": False,
            "pushed": False,
            "conflicts_resolved": 0,
            "message": "",
        }

        # 1. Stage and commit local changes
        if self.has_changes():
            self.stage_all()
            if self.commit():
                sync_result["committed"] = True

        # 2. Pull
        pull_result = self.pull()
        if pull_result["success"]:
            sync_result["pulled"] = True
        elif pull_result["conflicts"]:
            # 3. Resolve conflicts
            if resolver:
                resolution = self.resolve_conflicts(resolver, rules)
                resolved_count = len(resolution.get("resolved", []))
                sync_result["conflicts_resolved"] = resolved_count

                if resolution.get("failed"):
                    sync_result["message"] = (
                        f"Resolved {resolved_count} conflicts, "
                        f"{len(resolution['failed'])} failed"
                    )
                    return sync_result

                # Commit resolution
                self.commit("auto: resolve merge conflicts")
                sync_result["pulled"] = True
            else:
                sync_result["message"] = (
                    f"Merge conflicts: {', '.join(pull_result['conflicts'])}"
                )
                return sync_result
        else:
            sync_result["message"] = pull_result["message"]
            return sync_result

        # 4. Push
        if self.push():
            sync_result["pushed"] = True

        sync_result["success"] = True
        sync_result["message"] = "Sync complete"
        return sync_result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _run_git(self, args: List[str]) -> Dict[str, Any]:
        """Run a git command and return result."""
        cmd = ["git"] + args
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=60,
            )
            return {
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": "Command timed out (60s)",
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
            }

    def _auto_message(self) -> str:
        """Generate a descriptive commit message from current changes."""
        status = self.status()
        parts = []
        if status.get("added"):
            parts.append(f"add {len(status['added'])} file(s)")
        if status.get("modified"):
            parts.append(f"update {len(status['modified'])} file(s)")
        if status.get("deleted"):
            parts.append(f"remove {len(status['deleted'])} file(s)")

        if parts:
            return f"auto: {', '.join(parts)}"
        return "auto: sync"
