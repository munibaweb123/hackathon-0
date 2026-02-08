"""
ApprovalRequest Model

A structured markdown file requesting human authorization for an action.
Based on data-model.md specification.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional
import uuid


class ApprovalStatus(str, Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalActionType(str, Enum):
    """Type of action requiring approval."""
    EMAIL_SEND = "email_send"
    LINKEDIN_POST = "linkedin_post"
    WHATSAPP_REPLY = "whatsapp_reply"
    ESCALATE = "escalate"


class ApprovalRiskLevel(str, Enum):
    """Risk level of the proposed action."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ApprovalRequest:
    """
    A structured markdown file requesting human authorization.

    Approval requests are created when the AI Employee proposes
    a sensitive action. Humans approve by moving the file to
    the /Approved folder, or reject by moving to /Rejected.
    """

    # Required fields
    id: str
    plan_id: str
    action_type: ApprovalActionType
    description: str
    context: str
    risk_level: ApprovalRiskLevel
    status: ApprovalStatus
    created_at: datetime
    expires_at: datetime
    file_path: str

    # Optional fields
    proposed_content: Optional[str] = None
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    rejection_reason: Optional[str] = None

    @classmethod
    def create(
        cls,
        plan_id: str,
        action_type: ApprovalActionType,
        description: str,
        context: str,
        file_path: str,
        risk_level: ApprovalRiskLevel = ApprovalRiskLevel.MEDIUM,
        proposed_content: Optional[str] = None,
        expires_in_hours: int = 24,
    ) -> "ApprovalRequest":
        """
        Factory method to create a new ApprovalRequest.

        Args:
            plan_id: ID of the parent plan
            action_type: Type of action being requested
            description: Human-readable action description
            context: Why this action is proposed
            file_path: Vault path for the approval file
            risk_level: Risk level of the action
            proposed_content: Draft content if applicable
            expires_in_hours: Hours until expiration (default: 24)

        Returns:
            New ApprovalRequest instance
        """
        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            plan_id=plan_id,
            action_type=action_type,
            description=description,
            context=context,
            risk_level=risk_level,
            status=ApprovalStatus.PENDING,
            created_at=now,
            expires_at=now + timedelta(hours=expires_in_hours),
            file_path=file_path,
            proposed_content=proposed_content,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert approval request to dictionary for serialization."""
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "action_type": self.action_type.value,
            "description": self.description,
            "context": self.context,
            "risk_level": self.risk_level.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "file_path": self.file_path,
            "proposed_content": self.proposed_content,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "decided_by": self.decided_by,
            "rejection_reason": self.rejection_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalRequest":
        """Create ApprovalRequest from dictionary."""
        decided_at = None
        if data.get("decided_at"):
            decided_at = datetime.fromisoformat(data["decided_at"])

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            plan_id=data.get("plan_id", ""),
            action_type=ApprovalActionType(data.get("action_type", "escalate")),
            description=data.get("description", ""),
            context=data.get("context", ""),
            risk_level=ApprovalRiskLevel(data.get("risk_level", "medium")),
            status=ApprovalStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.utcnow().isoformat())),
            expires_at=datetime.fromisoformat(data.get("expires_at", (datetime.utcnow() + timedelta(hours=24)).isoformat())),
            file_path=data.get("file_path", ""),
            proposed_content=data.get("proposed_content"),
            decided_at=decided_at,
            decided_by=data.get("decided_by"),
            rejection_reason=data.get("rejection_reason"),
        )

    def to_markdown(self) -> str:
        """Generate approval request markdown for vault storage."""
        risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}
        status_emoji = {
            "pending": "⏳",
            "approved": "✅",
            "rejected": "❌",
            "expired": "⏰",
        }

        proposed_section = ""
        if self.proposed_content:
            proposed_section = f"""
## Proposed Content

```
{self.proposed_content}
```
"""

        decision_section = ""
        if self.status == ApprovalStatus.PENDING:
            decision_section = """
## Decision

**Status**: ⏳ Pending

To approve: Move this file to the `/Approved` folder
To reject: Move this file to the `/Rejected` folder
"""
        else:
            decision_section = f"""
## Decision

**Status**: {status_emoji.get(self.status.value, '❓')} {self.status.value.title()}
"""
            if self.decided_at:
                decision_section += f"**Decided At**: {self.decided_at.isoformat()}\n"
            if self.decided_by:
                decision_section += f"**Decided By**: {self.decided_by}\n"
            if self.rejection_reason:
                decision_section += f"**Reason**: {self.rejection_reason}\n"

        markdown = f"""# Approval Request: {self.action_type.value.replace('_', ' ').title()}

**ID**: {self.id}
**Plan**: {self.plan_id}
**Created**: {self.created_at.isoformat()}
**Expires**: {self.expires_at.isoformat()}
**Risk Level**: {risk_emoji.get(self.risk_level.value, '🟡')} {self.risk_level.value.title()}

## Proposed Action

**Type**: {self.action_type.value.replace('_', ' ').title()}
**Description**: {self.description}

## Context

{self.context}
{proposed_section}
{decision_section}
---
_Requires human approval before execution_
"""
        return markdown

    def get_filename(self) -> str:
        """Generate filename for this approval request."""
        short_id = self.id[:8]
        return f"APPROVAL_REQUIRED_{self.action_type.value}_{short_id}.md"

    def is_expired(self) -> bool:
        """Check if the approval request has expired."""
        return datetime.utcnow() > self.expires_at

    def approve(self, decided_by: Optional[str] = None) -> None:
        """Mark the approval request as approved."""
        self.status = ApprovalStatus.APPROVED
        self.decided_at = datetime.utcnow()
        self.decided_by = decided_by

    def reject(self, reason: str, decided_by: Optional[str] = None) -> None:
        """Mark the approval request as rejected."""
        self.status = ApprovalStatus.REJECTED
        self.decided_at = datetime.utcnow()
        self.decided_by = decided_by
        self.rejection_reason = reason

    def check_expiry(self) -> bool:
        """Check and update status if expired. Returns True if expired."""
        if self.status == ApprovalStatus.PENDING and self.is_expired():
            self.status = ApprovalStatus.EXPIRED
            return True
        return False

    def time_remaining(self) -> timedelta:
        """Get time remaining until expiration."""
        remaining = self.expires_at - datetime.utcnow()
        return remaining if remaining.total_seconds() > 0 else timedelta(0)

    def is_pending_for_hours(self, hours: int) -> bool:
        """Check if request has been pending for more than specified hours."""
        if self.status != ApprovalStatus.PENDING:
            return False
        pending_duration = datetime.utcnow() - self.created_at
        return pending_duration.total_seconds() >= hours * 3600
