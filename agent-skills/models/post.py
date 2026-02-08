"""
Post Model

A LinkedIn content item created by the system.
Based on data-model.md specification.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import uuid


class PostStatus(str, Enum):
    """Status of a LinkedIn post."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass
class Post:
    """
    A LinkedIn content item created by the system.

    Posts go through a lifecycle: draft → pending_approval →
    approved → published (or failed).
    """

    # Required fields
    id: str
    content: str
    status: PostStatus
    created_at: datetime

    # Optional fields
    linkedin_post_id: Optional[str] = None
    approved_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    approval_id: Optional[str] = None
    generation_context: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    file_path: Optional[str] = None

    @classmethod
    def create(
        cls,
        content: str,
        generation_context: Optional[Dict[str, Any]] = None,
    ) -> "Post":
        """
        Factory method to create a new Post.

        Args:
            content: Post text content (1-3000 characters)
            generation_context: Business context used for generation

        Returns:
            New Post instance
        """
        if not content or len(content) > 3000:
            raise ValueError("Content must be 1-3000 characters")

        return cls(
            id=str(uuid.uuid4()),
            content=content,
            status=PostStatus.DRAFT,
            created_at=datetime.utcnow(),
            generation_context=generation_context or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert post to dictionary for serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "linkedin_post_id": self.linkedin_post_id,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "approval_id": self.approval_id,
            "generation_context": self.generation_context,
            "error_message": self.error_message,
            "metrics": self.metrics,
            "file_path": self.file_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Post":
        """Create Post from dictionary."""
        approved_at = None
        published_at = None
        if data.get("approved_at"):
            approved_at = datetime.fromisoformat(data["approved_at"])
        if data.get("published_at"):
            published_at = datetime.fromisoformat(data["published_at"])

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            content=data.get("content", ""),
            status=PostStatus(data.get("status", "draft")),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.utcnow().isoformat())),
            linkedin_post_id=data.get("linkedin_post_id"),
            approved_at=approved_at,
            published_at=published_at,
            approval_id=data.get("approval_id"),
            generation_context=data.get("generation_context", {}),
            error_message=data.get("error_message"),
            metrics=data.get("metrics", {}),
            file_path=data.get("file_path"),
        )

    def to_markdown(self) -> str:
        """Generate markdown representation for vault storage."""
        status_emoji = {
            "draft": "📝",
            "pending_approval": "⏳",
            "approved": "✅",
            "published": "🎉",
            "failed": "❌",
        }

        metrics_section = ""
        if self.metrics:
            metrics_section = f"""
## Metrics

- Likes: {self.metrics.get('likes', 0)}
- Comments: {self.metrics.get('comments', 0)}
- Shares: {self.metrics.get('shares', 0)}
- Views: {self.metrics.get('views', 0)}
"""

        error_section = ""
        if self.error_message:
            error_section = f"""
## Error

{self.error_message}
"""

        markdown = f"""---
id: {self.id}
status: {self.status.value}
created_at: {self.created_at.isoformat()}
linkedin_post_id: {self.linkedin_post_id or 'null'}
approved_at: {self.approved_at.isoformat() if self.approved_at else 'null'}
published_at: {self.published_at.isoformat() if self.published_at else 'null'}
approval_id: {self.approval_id or 'null'}
---

# LinkedIn Post

**Status**: {status_emoji.get(self.status.value, '📝')} {self.status.value.replace('_', ' ').title()}
**Created**: {self.created_at.strftime('%Y-%m-%d %H:%M UTC')}

## Content

{self.content}
{metrics_section}
{error_section}
---
_Generated by Silver Tier AI Employee_
"""
        return markdown

    def get_filename(self) -> str:
        """Generate filename for this post."""
        timestamp_str = self.created_at.strftime("%Y-%m-%d_%H%M%S")
        short_id = self.id[:8]
        return f"POST_{timestamp_str}_{short_id}.md"

    def submit_for_approval(self, approval_id: str) -> None:
        """Submit post for human approval."""
        self.status = PostStatus.PENDING_APPROVAL
        self.approval_id = approval_id

    def approve(self) -> None:
        """Mark post as approved."""
        self.status = PostStatus.APPROVED
        self.approved_at = datetime.utcnow()

    def mark_published(self, linkedin_post_id: str) -> None:
        """Mark post as successfully published."""
        self.status = PostStatus.PUBLISHED
        self.published_at = datetime.utcnow()
        self.linkedin_post_id = linkedin_post_id

    def mark_failed(self, error_message: str) -> None:
        """Mark post as failed to publish."""
        self.status = PostStatus.FAILED
        self.error_message = error_message

    def update_metrics(self, metrics: Dict[str, Any]) -> None:
        """Update engagement metrics."""
        self.metrics.update(metrics)

    def is_publishable(self) -> bool:
        """Check if post can be published."""
        return self.status == PostStatus.APPROVED

    def character_count(self) -> int:
        """Get character count of content."""
        return len(self.content)

    def validate_content(self) -> bool:
        """Validate content meets LinkedIn requirements."""
        return 1 <= len(self.content) <= 3000
