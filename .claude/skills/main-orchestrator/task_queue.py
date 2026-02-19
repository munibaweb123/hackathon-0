"""
Task Queue — priority-based task processing from Needs_Action/.

Scans vault Needs_Action/ folder, classifies files by priority
(from filename prefix or YAML frontmatter), and provides claim/complete/fail
lifecycle methods for processing.
"""

import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger("orchestrator.queue")

# Default priority map — lower number = higher priority
DEFAULT_PRIORITY_MAP: Dict[str, int] = {
    "ALERT": 0,
    "WHATSAPP": 1,
    "EMAIL": 2,
    "FILE": 3,
    "TASK": 4,
    "NOTIFY": 5,
}

# Filename prefix → priority key mapping
PREFIX_MAP: Dict[str, str] = {
    "ALERT_": "ALERT",
    "WHATSAPP_": "WHATSAPP",
    "EMAIL_": "EMAIL",
    "FILE_": "FILE",
    "EXECUTE_": "TASK",
    "SEND_": "TASK",
    "POST_": "TASK",
    "NOTIFY_": "NOTIFY",
    "APPROVAL_": "TASK",
    "TASKPLAN_": "TASK",
}


class TaskQueue:
    """
    Priority queue backed by the vault's Needs_Action/ folder.

    Tasks are classified by filename prefix or YAML frontmatter type.
    Provides claim-before-process semantics via In_Progress/ folder.
    """

    def __init__(
        self,
        vault_path: str,
        priority_map: Optional[Dict[str, int]] = None,
    ) -> None:
        self.vault_path = Path(vault_path).resolve()
        self.needs_action_dir = self.vault_path / "Needs_Action"
        self.in_progress_dir = self.vault_path / "In_Progress"
        self.done_dir = self.vault_path / "Done"
        self.error_dir = self.vault_path / "error"

        # Ensure directories exist
        for d in [self.needs_action_dir, self.in_progress_dir, self.done_dir, self.error_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.priority_map = priority_map or DEFAULT_PRIORITY_MAP
        self._queue: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Scan and classify
    # ------------------------------------------------------------------
    def scan(self) -> List[Dict[str, Any]]:
        """
        Scan Needs_Action/ for .md files and build priority queue.

        Returns:
            Sorted list of task dicts: {path, filename, priority, metadata, content}
        """
        self._queue = []

        if not self.needs_action_dir.exists():
            return self._queue

        for filepath in sorted(self.needs_action_dir.iterdir()):
            if not filepath.is_file() or filepath.suffix != ".md":
                continue

            try:
                metadata, content = self._parse_frontmatter(filepath)
                priority = self._classify(filepath.name, metadata)

                self._queue.append({
                    "path": str(filepath),
                    "filename": filepath.name,
                    "priority": priority,
                    "metadata": metadata,
                    "content": content,
                })
            except Exception as e:
                logger.warning("Failed to parse %s: %s", filepath.name, e)

        # Sort by priority (lower = higher priority), then by filename (alphabetical = oldest first)
        self._queue.sort(key=lambda t: (t["priority"], t["filename"]))

        return self._queue

    def _classify(self, filename: str, metadata: Dict[str, Any]) -> int:
        """
        Determine task priority from filename prefix or frontmatter type.

        Priority resolution order:
        1. Filename prefix match (fast, no file content needed)
        2. Frontmatter 'type' field
        3. Default: 99 (lowest priority)
        """
        # 1. Filename prefix
        upper_name = filename.upper()
        for prefix, key in PREFIX_MAP.items():
            if upper_name.startswith(prefix):
                return self.priority_map.get(key, 99)

        # 2. Frontmatter type
        fm_type = metadata.get("type", "").upper()
        if fm_type:
            # Try direct match
            if fm_type in self.priority_map:
                return self.priority_map[fm_type]
            # Try partial match (e.g., "health_alert" contains "ALERT")
            for key in self.priority_map:
                if key in fm_type:
                    return self.priority_map[key]

        # 3. Frontmatter severity (for alerts)
        severity = metadata.get("severity", "")
        if severity == "critical":
            return self.priority_map.get("ALERT", 0)
        elif severity == "warning":
            return self.priority_map.get("ALERT", 0) + 1

        return 99

    def _parse_frontmatter(self, filepath: Path) -> Tuple[Dict[str, Any], str]:
        """
        Parse YAML frontmatter from a markdown file.

        Returns:
            (metadata_dict, body_string)
        """
        content = filepath.read_text(encoding="utf-8")

        if not content.startswith("---"):
            return {}, content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content

        try:
            metadata = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            metadata = {}

        body = parts[2].strip()
        return metadata, body

    # ------------------------------------------------------------------
    # Queue operations
    # ------------------------------------------------------------------
    def pop(self) -> Optional[Dict[str, Any]]:
        """
        Get and remove the highest priority task from the queue.

        Returns:
            Task dict or None if queue is empty.
        """
        if not self._queue:
            return None
        return self._queue.pop(0)

    def peek(self) -> Optional[Dict[str, Any]]:
        """Look at the highest priority task without removing it."""
        if not self._queue:
            return None
        return self._queue[0]

    @property
    def size(self) -> int:
        """Number of tasks in the queue."""
        return len(self._queue)

    def get_queue(self) -> List[Dict[str, Any]]:
        """Get a copy of the current queue."""
        return list(self._queue)

    # ------------------------------------------------------------------
    # Task lifecycle: claim → complete | fail
    # ------------------------------------------------------------------
    def claim(self, filepath: str, agent: str = "main-orchestrator") -> Optional[str]:
        """
        Claim a task by moving from Needs_Action/ to In_Progress/{agent}/.

        Args:
            filepath: Path to the task file in Needs_Action/.
            agent: Agent name for the In_Progress subfolder.

        Returns:
            New file path in In_Progress/, or None on failure.
        """
        src = Path(filepath)
        if not src.exists():
            logger.warning("Cannot claim — file not found: %s", filepath)
            return None

        dest_dir = self.in_progress_dir / agent
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name

        try:
            shutil.move(str(src), str(dest))
            logger.info("Claimed: %s → %s", src.name, dest)
            return str(dest)
        except Exception as e:
            logger.error("Failed to claim %s: %s", src.name, e)
            return None

    def complete(self, filepath: str) -> bool:
        """
        Mark a task as complete by moving to Done/.

        Args:
            filepath: Path to the task file in In_Progress/.

        Returns:
            True on success.
        """
        src = Path(filepath)
        if not src.exists():
            logger.warning("Cannot complete — file not found: %s", filepath)
            return False

        dest = self.done_dir / src.name
        # Avoid name collision
        if dest.exists():
            stem = dest.stem
            suffix = dest.suffix
            dest = self.done_dir / f"{stem}_{int(time.time())}{suffix}"

        try:
            shutil.move(str(src), str(dest))
            logger.info("Completed: %s → Done/", src.name)
            return True
        except Exception as e:
            logger.error("Failed to complete %s: %s", src.name, e)
            return False

    def fail(self, filepath: str, reason: str = "unknown") -> bool:
        """
        Mark a task as failed by moving to error/ with failure annotation.

        Args:
            filepath: Path to the task file.
            reason: Failure reason.

        Returns:
            True on success.
        """
        src = Path(filepath)
        if not src.exists():
            logger.warning("Cannot fail — file not found: %s", filepath)
            return False

        dest = self.error_dir / src.name
        if dest.exists():
            stem = dest.stem
            suffix = dest.suffix
            dest = self.error_dir / f"{stem}_{int(time.time())}{suffix}"

        try:
            # Read and annotate with failure reason
            content = src.read_text(encoding="utf-8")
            now = datetime.now(timezone.utc).isoformat()
            annotation = f"\n\n---\n**FAILED:** {now}\n**Reason:** {reason}\n"
            content += annotation
            src.write_text(content, encoding="utf-8")

            shutil.move(str(src), str(dest))
            logger.info("Failed: %s → error/ (reason: %s)", src.name, reason[:50])
            return True
        except Exception as e:
            logger.error("Failed to move %s to error: %s", src.name, e)
            return False

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------
    def show_queue(self) -> None:
        """Print the current queue to stdout."""
        if not self._queue:
            print("  Queue is empty.")
            return

        print(f"\n  Task Queue ({self.size} items):\n")
        print(f"  {'#':>3}  {'Priority':>8}  {'Filename'}")
        print(f"  {'─' * 3}  {'─' * 8}  {'─' * 40}")

        for i, task in enumerate(self._queue, 1):
            print(f"  {i:>3}  {task['priority']:>8}  {task['filename']}")
