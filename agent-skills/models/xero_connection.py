"""
Xero Connection Model

Stores OAuth credentials and connection status for Xero integration.
Supports Gold Tier requirements FR-001 to FR-005.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum
import uuid


class XeroConnectionStatus(str, Enum):
    """Status of Xero connection."""
    ACTIVE = "active"
    EXPIRED = "expired"
    AUTH_REQUIRED = "auth_required"
    ERROR = "error"


@dataclass
class XeroConnection:
    """
    OAuth credentials and connection status for Xero integration.

    Per FR-001: Authenticate with Xero using OAuth 2.0
    Per FR-031: Tokens stored encrypted (handled by CredentialManager)
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""  # Xero organization ID
    tenant_name: str = ""  # Organization name for display
    access_token: str = ""  # OAuth access token (stored encrypted)
    refresh_token: str = ""  # OAuth refresh token (stored encrypted)
    token_expiry: Optional[str] = None  # ISO timestamp of token expiration
    status: XeroConnectionStatus = XeroConnectionStatus.AUTH_REQUIRED
    last_sync: Optional[str] = None  # Last successful data sync
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def is_token_valid(self, buffer_minutes: int = 5) -> bool:
        """
        Check if the access token is still valid.

        Args:
            buffer_minutes: Consider expired if within this many minutes

        Returns:
            True if token is valid and not expiring soon
        """
        if not self.token_expiry:
            return False

        from datetime import timedelta
        expiry = datetime.fromisoformat(self.token_expiry)
        buffer = timedelta(minutes=buffer_minutes)
        return datetime.utcnow() + buffer < expiry

    def mark_active(self) -> None:
        """Mark connection as active after successful auth."""
        self.status = XeroConnectionStatus.ACTIVE
        self.updated_at = datetime.utcnow().isoformat()

    def mark_expired(self) -> None:
        """Mark connection as expired."""
        self.status = XeroConnectionStatus.EXPIRED
        self.updated_at = datetime.utcnow().isoformat()

    def mark_error(self) -> None:
        """Mark connection as having an error."""
        self.status = XeroConnectionStatus.ERROR
        self.updated_at = datetime.utcnow().isoformat()

    def mark_auth_required(self) -> None:
        """Mark connection as requiring re-authentication."""
        self.status = XeroConnectionStatus.AUTH_REQUIRED
        self.updated_at = datetime.utcnow().isoformat()

    def update_tokens(
        self,
        access_token: str,
        refresh_token: str,
        expires_in_seconds: int,
    ) -> None:
        """
        Update OAuth tokens after refresh or initial auth.

        Args:
            access_token: New access token
            refresh_token: New refresh token
            expires_in_seconds: Token lifetime in seconds
        """
        from datetime import timedelta

        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expiry = (
            datetime.utcnow() + timedelta(seconds=expires_in_seconds)
        ).isoformat()
        self.status = XeroConnectionStatus.ACTIVE
        self.updated_at = datetime.utcnow().isoformat()

    def record_sync(self) -> None:
        """Record successful data sync."""
        self.last_sync = datetime.utcnow().isoformat()
        self.updated_at = self.last_sync

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "tenant_name": self.tenant_name,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_expiry": self.token_expiry,
            "status": self.status.value if isinstance(self.status, XeroConnectionStatus) else self.status,
            "last_sync": self.last_sync,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_safe_dict(self) -> Dict[str, Any]:
        """Convert to dictionary without sensitive tokens."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "tenant_name": self.tenant_name,
            "token_expiry": self.token_expiry,
            "status": self.status.value if isinstance(self.status, XeroConnectionStatus) else self.status,
            "last_sync": self.last_sync,
            "is_valid": self.is_token_valid(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "XeroConnection":
        """Create from dictionary."""
        if "status" in data and isinstance(data["status"], str):
            data["status"] = XeroConnectionStatus(data["status"])
        return cls(**data)
