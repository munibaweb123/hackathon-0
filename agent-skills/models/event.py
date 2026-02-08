"""
Event Model

A structured record of external activity captured by a watcher.
Based on data-model.md specification.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class SourceType(str, Enum):
    """Type of external platform source."""
    GMAIL = "gmail"
    LINKEDIN = "linkedin"
    WHATSAPP = "whatsapp"


class EventType(str, Enum):
    """Type of external event."""
    EMAIL_RECEIVED = "email_received"
    LINKEDIN_NOTIFICATION = "linkedin_notification"
    LINKEDIN_MESSAGE = "linkedin_message"
    WHATSAPP_MESSAGE = "whatsapp_message"


class Priority(str, Enum):
    """Event priority level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ProcessingStatus(str, Enum):
    """Event processing status."""
    NEW = "new"
    PROCESSING = "processing"
    PLAN_GENERATED = "plan_generated"
    ARCHIVED = "archived"


@dataclass
class Sender:
    """Information about who sent the event."""
    name: str
    identifier: str  # Email, LinkedIn ID, or phone number
    profile_url: Optional[str] = None


@dataclass
class EventContent:
    """Normalized content of an event."""
    summary: str
    body: str
    subject: Optional[str] = None
    attachments: List[str] = field(default_factory=list)


@dataclass
class EventContext:
    """Additional context for an event."""
    thread_id: Optional[str] = None
    is_reply: bool = False
    reply_to_id: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    urgency_indicators: List[str] = field(default_factory=list)


@dataclass
class NormalizedEvent:
    """Standardized event representation across all platforms."""
    summary: str
    sender: Sender
    content: EventContent
    metadata: EventContext


@dataclass
class Event:
    """
    A structured record of external activity captured by a watcher.

    Events are created by watchers when they detect activity on external
    platforms (Gmail, LinkedIn, WhatsApp). They are stored as files in
    the vault inbox folder.
    """

    # Required fields
    id: str
    source_type: SourceType
    event_type: EventType
    timestamp: datetime
    detected_at: datetime
    priority: Priority
    processing_status: ProcessingStatus
    raw_data: Dict[str, Any]
    normalized_data: NormalizedEvent
    file_path: str

    # Optional fields
    source_id: Optional[str] = None
    plan_id: Optional[str] = None

    @classmethod
    def create(
        cls,
        source_type: SourceType,
        event_type: EventType,
        raw_data: Dict[str, Any],
        normalized_data: NormalizedEvent,
        file_path: str,
        priority: Priority = Priority.MEDIUM,
        source_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> "Event":
        """
        Factory method to create a new Event.

        Args:
            source_type: Platform that generated the event
            event_type: Type of event
            raw_data: Original event data
            normalized_data: Standardized event representation
            file_path: Vault path for the event file
            priority: Event priority (default: MEDIUM)
            source_id: External platform's ID
            timestamp: When event occurred (default: now)

        Returns:
            New Event instance
        """
        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            source_type=source_type,
            event_type=event_type,
            timestamp=timestamp or now,
            detected_at=now,
            priority=priority,
            processing_status=ProcessingStatus.NEW,
            raw_data=raw_data,
            normalized_data=normalized_data,
            file_path=file_path,
            source_id=source_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "id": self.id,
            "source_type": self.source_type.value,
            "source_id": self.source_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "detected_at": self.detected_at.isoformat(),
            "priority": self.priority.value,
            "processing_status": self.processing_status.value,
            "raw_data": self.raw_data,
            "normalized_data": {
                "summary": self.normalized_data.summary,
                "sender": {
                    "name": self.normalized_data.sender.name,
                    "identifier": self.normalized_data.sender.identifier,
                    "profile_url": self.normalized_data.sender.profile_url,
                },
                "content": {
                    "summary": self.normalized_data.content.summary,
                    "subject": self.normalized_data.content.subject,
                    "body": self.normalized_data.content.body,
                    "attachments": self.normalized_data.content.attachments,
                },
                "metadata": {
                    "thread_id": self.normalized_data.metadata.thread_id,
                    "is_reply": self.normalized_data.metadata.is_reply,
                    "reply_to_id": self.normalized_data.metadata.reply_to_id,
                    "labels": self.normalized_data.metadata.labels,
                    "urgency_indicators": self.normalized_data.metadata.urgency_indicators,
                },
            },
            "file_path": self.file_path,
            "plan_id": self.plan_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Create Event from dictionary."""
        normalized = data.get("normalized_data", {})
        sender_data = normalized.get("sender", {})
        content_data = normalized.get("content", {})
        metadata_data = normalized.get("metadata", {})

        sender = Sender(
            name=sender_data.get("name", "Unknown"),
            identifier=sender_data.get("identifier", ""),
            profile_url=sender_data.get("profile_url"),
        )

        content = EventContent(
            summary=content_data.get("summary", ""),
            body=content_data.get("body", ""),
            subject=content_data.get("subject"),
            attachments=content_data.get("attachments", []),
        )

        context = EventContext(
            thread_id=metadata_data.get("thread_id"),
            is_reply=metadata_data.get("is_reply", False),
            reply_to_id=metadata_data.get("reply_to_id"),
            labels=metadata_data.get("labels", []),
            urgency_indicators=metadata_data.get("urgency_indicators", []),
        )

        normalized_event = NormalizedEvent(
            summary=normalized.get("summary", content.summary),
            sender=sender,
            content=content,
            metadata=context,
        )

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            source_type=SourceType(data.get("source_type", "gmail")),
            source_id=data.get("source_id"),
            event_type=EventType(data.get("event_type", "email_received")),
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat())),
            detected_at=datetime.fromisoformat(data.get("detected_at", datetime.utcnow().isoformat())),
            priority=Priority(data.get("priority", "medium")),
            processing_status=ProcessingStatus(data.get("processing_status", "new")),
            raw_data=data.get("raw_data", {}),
            normalized_data=normalized_event,
            file_path=data.get("file_path", ""),
            plan_id=data.get("plan_id"),
        )

    def to_markdown(self) -> str:
        """Generate markdown representation for vault storage."""
        frontmatter = f"""---
id: {self.id}
source_type: {self.source_type.value}
source_id: {self.source_id or 'null'}
event_type: {self.event_type.value}
timestamp: {self.timestamp.isoformat()}
detected_at: {self.detected_at.isoformat()}
priority: {self.priority.value}
processing_status: {self.processing_status.value}
plan_id: {self.plan_id or 'null'}
---

# {self.event_type.value.replace('_', ' ').title()}

**From**: {self.normalized_data.sender.name} ({self.normalized_data.sender.identifier})
**Subject**: {self.normalized_data.content.subject or 'N/A'}
**Priority**: {self.priority.value.upper()}

## Summary

{self.normalized_data.summary}

## Content

{self.normalized_data.content.body}
"""
        return frontmatter

    def get_filename(self) -> str:
        """Generate filename for this event."""
        type_prefix = self.source_type.value.upper()
        timestamp_str = self.timestamp.strftime("%Y-%m-%d_%H%M%S")
        short_id = self.id[:8]
        return f"{type_prefix}_{timestamp_str}_{short_id}.md"
