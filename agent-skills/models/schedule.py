"""
Schedule Model

A configuration defining when tasks execute.
Based on data-model.md specification.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import uuid


class TaskType(str, Enum):
    """Type of scheduled task."""
    WATCHER_POLL = "watcher_poll"
    CONTENT_GENERATION = "content_generation"
    CLEANUP = "cleanup"
    HEALTH_CHECK = "health_check"


class ScheduleType(str, Enum):
    """Type of schedule."""
    INTERVAL = "interval"
    CRON = "cron"


@dataclass
class Schedule:
    """
    A configuration defining when tasks execute.

    Schedules can be interval-based (every N seconds) or
    cron-based (specific times).
    """

    # Required fields
    id: str
    task_type: TaskType
    schedule_type: ScheduleType
    enabled: bool
    created_at: datetime

    # Conditional fields (one must be set based on schedule_type)
    interval_seconds: Optional[int] = None
    cron_expression: Optional[str] = None

    # Optional fields
    target_id: Optional[str] = None  # Watcher ID or skill ID
    description: Optional[str] = None
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    config: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create_interval(
        cls,
        task_type: TaskType,
        interval_seconds: int,
        target_id: Optional[str] = None,
        description: Optional[str] = None,
        enabled: bool = True,
        config: Optional[Dict[str, Any]] = None,
    ) -> "Schedule":
        """
        Factory method to create an interval-based schedule.

        Args:
            task_type: Type of task to schedule
            interval_seconds: Seconds between executions (min: 30)
            target_id: ID of watcher or skill to execute
            description: Human-readable description
            enabled: Whether schedule is active
            config: Additional configuration

        Returns:
            New Schedule instance
        """
        if interval_seconds < 30:
            raise ValueError("interval_seconds must be >= 30")

        return cls(
            id=str(uuid.uuid4()),
            task_type=task_type,
            schedule_type=ScheduleType.INTERVAL,
            enabled=enabled,
            created_at=datetime.utcnow(),
            interval_seconds=interval_seconds,
            target_id=target_id,
            description=description,
            config=config or {},
        )

    @classmethod
    def create_cron(
        cls,
        task_type: TaskType,
        cron_expression: str,
        target_id: Optional[str] = None,
        description: Optional[str] = None,
        enabled: bool = True,
        config: Optional[Dict[str, Any]] = None,
    ) -> "Schedule":
        """
        Factory method to create a cron-based schedule.

        Args:
            task_type: Type of task to schedule
            cron_expression: Cron expression (e.g., "0 9 * * *")
            target_id: ID of watcher or skill to execute
            description: Human-readable description
            enabled: Whether schedule is active
            config: Additional configuration

        Returns:
            New Schedule instance
        """
        # Basic cron validation
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError("cron_expression must have 5 parts: minute hour day month weekday")

        return cls(
            id=str(uuid.uuid4()),
            task_type=task_type,
            schedule_type=ScheduleType.CRON,
            enabled=enabled,
            created_at=datetime.utcnow(),
            cron_expression=cron_expression,
            target_id=target_id,
            description=description,
            config=config or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert schedule to dictionary for serialization."""
        return {
            "id": self.id,
            "task_type": self.task_type.value,
            "schedule_type": self.schedule_type.value,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "interval_seconds": self.interval_seconds,
            "cron_expression": self.cron_expression,
            "target_id": self.target_id,
            "description": self.description,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Schedule":
        """Create Schedule from dictionary."""
        last_run = None
        next_run = None
        if data.get("last_run"):
            last_run = datetime.fromisoformat(data["last_run"])
        if data.get("next_run"):
            next_run = datetime.fromisoformat(data["next_run"])

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            task_type=TaskType(data.get("task_type", "watcher_poll")),
            schedule_type=ScheduleType(data.get("schedule_type", "interval")),
            enabled=data.get("enabled", True),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.utcnow().isoformat())),
            interval_seconds=data.get("interval_seconds"),
            cron_expression=data.get("cron_expression"),
            target_id=data.get("target_id"),
            description=data.get("description"),
            last_run=last_run,
            next_run=next_run,
            config=data.get("config", {}),
        )

    def mark_executed(self) -> None:
        """Mark schedule as just executed."""
        self.last_run = datetime.utcnow()

    def is_due(self) -> bool:
        """Check if schedule is due to run."""
        if not self.enabled:
            return False

        if self.next_run:
            return datetime.utcnow() >= self.next_run

        # If no next_run set, check based on last_run and interval
        if self.schedule_type == ScheduleType.INTERVAL:
            if not self.last_run:
                return True
            elapsed = (datetime.utcnow() - self.last_run).total_seconds()
            return elapsed >= (self.interval_seconds or 0)

        return False

    def get_schedule_description(self) -> str:
        """Get human-readable schedule description."""
        if self.schedule_type == ScheduleType.INTERVAL:
            seconds = self.interval_seconds or 0
            if seconds < 60:
                return f"Every {seconds} seconds"
            elif seconds < 3600:
                return f"Every {seconds // 60} minutes"
            else:
                return f"Every {seconds // 3600} hours"
        else:
            return f"Cron: {self.cron_expression}"

    def validate(self) -> bool:
        """Validate the schedule configuration."""
        if self.schedule_type == ScheduleType.INTERVAL:
            return self.interval_seconds is not None and self.interval_seconds >= 30
        else:
            return self.cron_expression is not None and len(self.cron_expression.split()) == 5
