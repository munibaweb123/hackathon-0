"""
Unified Contact & Platform Identity Models

Aggregates contact information across platforms using email as primary key.
Per data-model.md specification.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class ContactPlatform(str, Enum):
    """Platforms a contact can be linked to."""
    XERO = "xero"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class LinkedBy(str, Enum):
    """How a platform identity was linked to a contact."""
    EMAIL_MATCH = "email_match"
    MANUAL = "manual"
    AI_SUGGESTED = "ai_suggested"


@dataclass
class PlatformIdentity:
    """Links a unified contact to a platform-specific identity."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    contact_id: str = ""
    platform: ContactPlatform = ContactPlatform.EMAIL
    platform_id: str = ""
    display_name: Optional[str] = None
    profile_url: Optional[str] = None
    linked_by: LinkedBy = LinkedBy.EMAIL_MATCH
    confidence: Optional[float] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "contact_id": self.contact_id,
            "platform": self.platform.value,
            "platform_id": self.platform_id,
            "display_name": self.display_name,
            "profile_url": self.profile_url,
            "linked_by": self.linked_by.value,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlatformIdentity":
        platform = data.get("platform", "email")
        if isinstance(platform, str):
            platform = ContactPlatform(platform)
        linked_by = data.get("linked_by", "email_match")
        if isinstance(linked_by, str):
            linked_by = LinkedBy(linked_by)
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            contact_id=data.get("contact_id", ""),
            platform=platform,
            platform_id=data.get("platform_id", ""),
            display_name=data.get("display_name"),
            profile_url=data.get("profile_url"),
            linked_by=linked_by,
            confidence=data.get("confidence"),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
        )


@dataclass
class UnifiedContact:
    """
    Aggregates contact information across platforms.
    Uses email as the primary matching key.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    primary_email: str = ""
    display_name: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None
    identities: List[PlatformIdentity] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def add_identity(self, identity: PlatformIdentity) -> None:
        """Add a platform identity to this contact."""
        identity.contact_id = self.id
        self.identities.append(identity)
        self.updated_at = datetime.utcnow().isoformat()

    def get_platforms(self) -> List[str]:
        """Get list of platforms this contact is linked to."""
        return [i.platform.value for i in self.identities]

    def get_identity(self, platform: ContactPlatform) -> Optional[PlatformIdentity]:
        """Get identity for a specific platform."""
        for identity in self.identities:
            if identity.platform == platform:
                return identity
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "primary_email": self.primary_email,
            "display_name": self.display_name,
            "company": self.company,
            "notes": self.notes,
            "identities": [i.to_dict() for i in self.identities],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnifiedContact":
        identities = [
            PlatformIdentity.from_dict(i)
            for i in data.get("identities", [])
        ]
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            primary_email=data.get("primary_email", ""),
            display_name=data.get("display_name"),
            company=data.get("company"),
            notes=data.get("notes"),
            identities=identities,
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat()),
        )
