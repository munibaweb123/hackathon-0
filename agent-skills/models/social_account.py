"""
SocialAccount Model

Stores OAuth credentials and metadata for social media platforms.
Per data-model.md specification.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import uuid


class SocialPlatform(str, Enum):
    """Supported social media platforms."""
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TWITTER = "twitter"


class SocialAccountStatus(str, Enum):
    """Social account connection status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    AUTH_REQUIRED = "auth_required"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


@dataclass
class SocialAccount:
    """
    OAuth credentials and metadata for a social media platform account.

    Status transitions:
        auth_required -> active <-> expired -> auth_required
                          |-> rate_limited -> active
                          |-> error -> auth_required
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    platform: SocialPlatform = SocialPlatform.FACEBOOK
    account_id: str = ""
    page_id: Optional[str] = None  # Facebook Page ID (required for FB/IG)
    access_token: str = ""
    token_expiry: Optional[str] = None
    follower_count: Optional[int] = None
    status: SocialAccountStatus = SocialAccountStatus.AUTH_REQUIRED
    last_sync: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def is_active(self) -> bool:
        return self.status == SocialAccountStatus.ACTIVE

    def is_token_expired(self) -> bool:
        if not self.token_expiry:
            return True
        try:
            expiry = datetime.fromisoformat(self.token_expiry)
            return datetime.utcnow() >= expiry
        except ValueError:
            return True

    def mark_active(self) -> None:
        self.status = SocialAccountStatus.ACTIVE
        self.updated_at = datetime.utcnow().isoformat()

    def mark_expired(self) -> None:
        self.status = SocialAccountStatus.EXPIRED
        self.updated_at = datetime.utcnow().isoformat()

    def mark_rate_limited(self) -> None:
        self.status = SocialAccountStatus.RATE_LIMITED
        self.updated_at = datetime.utcnow().isoformat()

    def mark_error(self) -> None:
        self.status = SocialAccountStatus.ERROR
        self.updated_at = datetime.utcnow().isoformat()

    def record_sync(self) -> None:
        self.last_sync = datetime.utcnow().isoformat()
        self.updated_at = self.last_sync

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "platform": self.platform.value,
            "account_id": self.account_id,
            "page_id": self.page_id,
            "access_token": self.access_token,
            "token_expiry": self.token_expiry,
            "follower_count": self.follower_count,
            "status": self.status.value,
            "last_sync": self.last_sync,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_safe_dict(self) -> Dict[str, Any]:
        """Dictionary without sensitive tokens."""
        return {
            "id": self.id,
            "platform": self.platform.value,
            "account_id": self.account_id,
            "page_id": self.page_id,
            "follower_count": self.follower_count,
            "status": self.status.value,
            "last_sync": self.last_sync,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SocialAccount":
        platform = data.get("platform", "facebook")
        if isinstance(platform, str):
            platform = SocialPlatform(platform)
        status = data.get("status", "auth_required")
        if isinstance(status, str):
            status = SocialAccountStatus(status)
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            platform=platform,
            account_id=data.get("account_id", ""),
            page_id=data.get("page_id"),
            access_token=data.get("access_token", ""),
            token_expiry=data.get("token_expiry"),
            follower_count=data.get("follower_count"),
            status=status,
            last_sync=data.get("last_sync"),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat()),
        )
