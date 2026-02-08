"""
Retry Item Model

Represents a failed action queued for retry with exponential backoff.
Supports Gold Tier error recovery requirements (FR-020 to FR-023).
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from enum import Enum
import uuid


class RetryStatus(str, Enum):
    """Status of retry queue item."""
    PENDING = "pending"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"  # Permanently failed after max retries


# Exponential backoff schedule (per FR-020a)
# Retry 1: 1 min, Retry 2: 5 min, Retry 3: 30 min, Retry 4: 2 hours, Retry 5: 4 hours
BACKOFF_DELAYS = [60, 300, 1800, 7200, 14400]  # seconds
MAX_RETRIES = 5  # Per FR-020a


@dataclass
class RetryItem:
    """
    Failed action queued for retry.

    Per FR-020: Queue failed actions for retry with exponential backoff
    Per FR-020a: 5 retries with exponential backoff, max delay 4 hours
    Per FR-020b: Mark as permanently failed after 5 unsuccessful attempts
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str = ""  # e.g., "xero.invoice.create"
    action_payload: Dict[str, Any] = field(default_factory=dict)
    approval_ref: Optional[str] = None  # Original approval reference
    failure_reason: str = ""
    error_code: Optional[str] = None  # API error code if available
    retry_count: int = 0
    max_retries: int = MAX_RETRIES
    next_retry_at: Optional[str] = None  # ISO timestamp
    status: RetryStatus = RetryStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def __post_init__(self):
        """Set initial next_retry_at if not provided."""
        if self.next_retry_at is None and self.status == RetryStatus.PENDING:
            self.calculate_next_retry()

    def calculate_next_retry(self) -> None:
        """
        Calculate next retry time using exponential backoff.

        Backoff schedule:
        - Retry 1: 1 minute
        - Retry 2: 5 minutes
        - Retry 3: 30 minutes
        - Retry 4: 2 hours
        - Retry 5: 4 hours (max)
        """
        if self.retry_count >= self.max_retries:
            self.status = RetryStatus.FAILED
            self.next_retry_at = None
            return

        delay_index = min(self.retry_count, len(BACKOFF_DELAYS) - 1)
        delay_seconds = BACKOFF_DELAYS[delay_index]

        next_time = datetime.utcnow() + timedelta(seconds=delay_seconds)
        self.next_retry_at = next_time.isoformat()

    def increment_retry(self) -> bool:
        """
        Increment retry count and recalculate next retry.

        Returns True if more retries available, False if permanently failed.
        """
        self.retry_count += 1
        self.updated_at = datetime.utcnow().isoformat()

        if self.retry_count >= self.max_retries:
            self.status = RetryStatus.FAILED
            self.next_retry_at = None
            return False

        self.calculate_next_retry()
        return True

    def mark_retrying(self) -> None:
        """Mark item as currently being retried."""
        self.status = RetryStatus.RETRYING
        self.updated_at = datetime.utcnow().isoformat()

    def mark_succeeded(self) -> None:
        """Mark item as successfully completed."""
        self.status = RetryStatus.SUCCEEDED
        self.next_retry_at = None
        self.updated_at = datetime.utcnow().isoformat()

    def mark_failed(self, reason: str, error_code: Optional[str] = None) -> bool:
        """
        Mark retry attempt as failed and schedule next retry.

        Returns True if more retries available, False if permanently failed.
        """
        self.failure_reason = reason
        self.error_code = error_code
        self.status = RetryStatus.PENDING
        return self.increment_retry()

    def is_ready_for_retry(self) -> bool:
        """Check if item is ready for retry (past next_retry_at time)."""
        if self.status != RetryStatus.PENDING:
            return False
        if self.next_retry_at is None:
            return False

        next_time = datetime.fromisoformat(self.next_retry_at)
        return datetime.utcnow() >= next_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "action_type": self.action_type,
            "action_payload": self.action_payload,
            "approval_ref": self.approval_ref,
            "failure_reason": self.failure_reason,
            "error_code": self.error_code,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "next_retry_at": self.next_retry_at,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetryItem":
        """Create from dictionary."""
        if "status" in data and isinstance(data["status"], str):
            data["status"] = RetryStatus(data["status"])
        return cls(**data)
