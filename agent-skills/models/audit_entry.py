"""
Audit Entry Model

Immutable audit log entry with hash chain integrity for tamper-evident logging.
Supports Gold Tier comprehensive audit logging requirements (FR-024 to FR-027).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum
import hashlib
import json
import uuid


class ActorType(str, Enum):
    """Actor who performed the action."""
    USER = "user"
    AI = "ai"
    SYSTEM = "system"


class ActionResult(str, Enum):
    """Result of the action."""
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"


@dataclass
class AuditEntry:
    """
    Immutable audit log entry with hash chain integrity.

    Each entry contains a hash of its contents plus the previous entry's hash,
    creating a tamper-evident chain that can be verified for integrity.

    Per FR-024: All MCP actions logged with tamper-evident hashes
    Per FR-025: Hash chain integrity maintained across entries
    Per FR-032: Credentials must never appear in details
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    action_type: str = ""  # e.g., "xero.invoice.create", "twitter.tweet.post"
    actor: ActorType = ActorType.SYSTEM
    server_id: str = ""  # MCP server that processed the action
    approval_ref: Optional[str] = None  # Reference to approval file
    details: Dict[str, Any] = field(default_factory=dict)
    result: ActionResult = ActionResult.PENDING
    error_message: Optional[str] = None
    latency_ms: Optional[int] = None  # API call latency
    prev_hash: str = "GENESIS"  # Hash of previous entry (GENESIS for first)
    hash: str = ""  # SHA-256 hash of this entry

    def __post_init__(self):
        """Compute hash after initialization if not provided."""
        if not self.hash:
            self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        """
        Compute SHA-256 hash of entry contents.

        Hash includes all fields except 'hash' itself.
        Fields are sorted for deterministic hashing.
        """
        entry_dict = {
            "id": self.id,
            "timestamp": self.timestamp,
            "action_type": self.action_type,
            "actor": self.actor.value if isinstance(self.actor, ActorType) else self.actor,
            "server_id": self.server_id,
            "approval_ref": self.approval_ref,
            "details": self.details,
            "result": self.result.value if isinstance(self.result, ActionResult) else self.result,
            "error_message": self.error_message,
            "latency_ms": self.latency_ms,
            "prev_hash": self.prev_hash,
        }
        json_str = json.dumps(entry_dict, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def verify_hash(self) -> bool:
        """Verify that the stored hash matches computed hash."""
        return self.hash == self.compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary for serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "action_type": self.action_type,
            "actor": self.actor.value if isinstance(self.actor, ActorType) else self.actor,
            "server_id": self.server_id,
            "approval_ref": self.approval_ref,
            "details": self.details,
            "result": self.result.value if isinstance(self.result, ActionResult) else self.result,
            "error_message": self.error_message,
            "latency_ms": self.latency_ms,
            "prev_hash": self.prev_hash,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEntry":
        """Create entry from dictionary."""
        # Convert string enums back to enum types
        if "actor" in data and isinstance(data["actor"], str):
            data["actor"] = ActorType(data["actor"])
        if "result" in data and isinstance(data["result"], str):
            data["result"] = ActionResult(data["result"])
        return cls(**data)

    @staticmethod
    def scrub_credentials(details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove sensitive information from details before logging.

        Per FR-032: Credentials must never appear in audit entries.
        """
        sensitive_keys = {"token", "secret", "password", "key", "credential", "auth"}
        scrubbed = {}

        for key, value in details.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                scrubbed[key] = "[REDACTED]"
            elif isinstance(value, dict):
                scrubbed[key] = AuditEntry.scrub_credentials(value)
            elif isinstance(value, str) and any(sensitive in key_lower for sensitive in sensitive_keys):
                scrubbed[key] = "[REDACTED]"
            else:
                scrubbed[key] = value

        return scrubbed
