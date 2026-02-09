"""
Retry Queue

Manages failed actions for retry with exponential backoff.

Supports Gold Tier requirements:
- FR-020: Queue failed actions for retry with exponential backoff
- FR-020a: 5 retries with exponential backoff, max delay 4 hours
- FR-020b: Mark as permanently failed after 5 unsuccessful attempts and notify user
- FR-021: Notify users of integration failures within 5 minutes
"""

import os
import yaml
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from threading import Lock

from models.retry_item import RetryItem, RetryStatus


class RetryQueueError(Exception):
    """Base exception for retry queue errors."""
    pass


class RetryQueue:
    """
    Manages failed actions for retry with exponential backoff.

    Stores queue state in vault for persistence across restarts.
    Supports callbacks for user notification on permanent failures.

    Per FR-020: Queue failed actions with exponential backoff
    Per FR-020a/b: 5 retries, max 4 hours, then permanent failure
    """

    def __init__(
        self,
        vault_path: Optional[str] = None,
        on_permanent_failure: Optional[Callable[[RetryItem], None]] = None,
    ):
        """
        Initialize retry queue.

        Args:
            vault_path: Path to vault directory. Defaults to VAULT_PATH env var.
            on_permanent_failure: Callback when action permanently fails
        """
        self.vault_path = vault_path or os.environ.get("VAULT_PATH", "./obsidian-vault")
        self.on_permanent_failure = on_permanent_failure
        self._lock = Lock()
        self._queue: Dict[str, RetryItem] = {}
        self._ensure_directory()
        self._load_queue()

    def _ensure_directory(self) -> None:
        """Ensure retry queue directory exists."""
        queue_dir = Path(self.vault_path) / "retry-queue"
        queue_dir.mkdir(parents=True, exist_ok=True)

    def _get_queue_file(self) -> Path:
        """Get path to queue file."""
        return Path(self.vault_path) / "retry-queue" / "pending.yaml"

    def _load_queue(self) -> None:
        """Load queue from disk."""
        queue_file = self._get_queue_file()
        if queue_file.exists():
            with open(queue_file, "r") as f:
                data = yaml.safe_load(f)
                if data and isinstance(data, dict):
                    for item_id, item_data in data.items():
                        self._queue[item_id] = RetryItem.from_dict(item_data)

    def _save_queue(self) -> None:
        """Save queue to disk."""
        queue_file = self._get_queue_file()
        data = {item_id: item.to_dict() for item_id, item in self._queue.items()}
        with open(queue_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def add(
        self,
        action_type: str,
        action_payload: Dict[str, Any],
        failure_reason: str,
        approval_ref: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> RetryItem:
        """
        Add a failed action to the retry queue.

        Args:
            action_type: Type of action that failed
            action_payload: Action parameters for retry
            failure_reason: Why the action failed
            approval_ref: Original approval reference if applicable
            error_code: API error code if available

        Returns:
            Created RetryItem
        """
        with self._lock:
            item = RetryItem(
                action_type=action_type,
                action_payload=action_payload,
                failure_reason=failure_reason,
                approval_ref=approval_ref,
                error_code=error_code,
            )
            self._queue[item.id] = item
            self._save_queue()
            return item

    def get_pending(self) -> List[RetryItem]:
        """
        Get all items ready for retry.

        Returns:
            List of items past their next_retry_at time
        """
        with self._lock:
            return [
                item for item in self._queue.values()
                if item.is_ready_for_retry()
            ]

    def get_all(self) -> List[RetryItem]:
        """Get all items in queue."""
        with self._lock:
            return list(self._queue.values())

    def get_by_status(self, status: RetryStatus) -> List[RetryItem]:
        """Get items by status."""
        with self._lock:
            return [
                item for item in self._queue.values()
                if item.status == status
            ]

    def mark_retrying(self, item_id: str) -> Optional[RetryItem]:
        """
        Mark an item as currently being retried.

        Args:
            item_id: Item to mark

        Returns:
            Updated item or None if not found
        """
        with self._lock:
            item = self._queue.get(item_id)
            if item:
                item.mark_retrying()
                self._save_queue()
            return item

    def mark_succeeded(self, item_id: str) -> Optional[RetryItem]:
        """
        Mark an item as successfully completed.

        Args:
            item_id: Item that succeeded

        Returns:
            Updated item or None if not found
        """
        with self._lock:
            item = self._queue.get(item_id)
            if item:
                item.mark_succeeded()
                self._save_queue()
            return item

    def mark_failed(
        self,
        item_id: str,
        reason: str,
        error_code: Optional[str] = None,
    ) -> Optional[RetryItem]:
        """
        Mark a retry attempt as failed.

        If max retries reached, calls on_permanent_failure callback.

        Args:
            item_id: Item that failed
            reason: Failure reason
            error_code: API error code if available

        Returns:
            Updated item or None if not found
        """
        with self._lock:
            item = self._queue.get(item_id)
            if item:
                has_more_retries = item.mark_failed(reason, error_code)
                self._save_queue()

                if not has_more_retries and self.on_permanent_failure:
                    # Notify about permanent failure
                    self.on_permanent_failure(item)

            return item

    def remove(self, item_id: str) -> bool:
        """
        Remove an item from the queue.

        Args:
            item_id: Item to remove

        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if item_id in self._queue:
                del self._queue[item_id]
                self._save_queue()
                return True
            return False

    def cleanup_completed(self) -> int:
        """
        Remove all succeeded items from queue.

        Returns:
            Number of items removed
        """
        with self._lock:
            to_remove = [
                item_id for item_id, item in self._queue.items()
                if item.status == RetryStatus.SUCCEEDED
            ]
            for item_id in to_remove:
                del self._queue[item_id]

            if to_remove:
                self._save_queue()

            return len(to_remove)

    def get_stats(self) -> Dict[str, int]:
        """
        Get queue statistics.

        Returns:
            Count of items by status
        """
        with self._lock:
            stats = {
                "pending": 0,
                "retrying": 0,
                "succeeded": 0,
                "failed": 0,
                "total": len(self._queue),
            }
            for item in self._queue.values():
                stats[item.status.value] += 1
            return stats

    def get_by_action_type(self, action_type: str) -> List[RetryItem]:
        """Get all items for a specific action type."""
        with self._lock:
            return [
                item for item in self._queue.values()
                if item.action_type == action_type
            ]


def notify_permanent_failure(item: "RetryItem") -> None:
    """
    Default notification handler for permanent failures.

    Creates a notification file in the vault inbox so the user
    is alerted about actions that could not be completed after
    max retries.

    Per FR-020b: Notify user after 5 unsuccessful retry attempts.
    Per FR-021: Notify users of integration failures within 5 minutes.
    """
    vault_path = os.environ.get("VAULT_PATH", "./obsidian-vault")
    inbox_dir = Path(vault_path) / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.utcnow()
    filename = f"FAILURE_{now.strftime('%Y-%m-%d_%H%M%S')}_{item.id[:8]}.md"

    content = f"""---
id: {item.id}
type: permanent_failure
action_type: {item.action_type}
retry_count: {item.retry_count}
created_at: {now.isoformat()}Z
priority: high
processing_status: new
source_type: system
---

# Action Permanently Failed

**Action**: {item.action_type}
**Failure Reason**: {item.failure_reason}
**Retries Attempted**: {item.retry_count}

## Recommended Actions

- Review the failure reason above
- Check the relevant service status
- Retry manually if the issue has been resolved
"""

    filepath = inbox_dir / filename
    filepath.write_text(content)


def create_retry_queue_with_notifications(vault_path: str = None) -> RetryQueue:
    """
    Factory function to create a RetryQueue with default notification handler.

    Returns:
        RetryQueue configured with permanent failure notifications
    """
    return RetryQueue(
        vault_path=vault_path,
        on_permanent_failure=notify_permanent_failure,
    )
