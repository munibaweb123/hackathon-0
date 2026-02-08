"""
MCP Server Model

Tracks health and status of each domain MCP server.
Supports Gold Tier multi-MCP architecture requirements (FR-016 to FR-019).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum


class MCPDomain(str, Enum):
    """Domain categories for MCP servers."""
    COORDINATOR = "coordinator"
    FINANCIAL = "financial"
    SOCIAL = "social"
    COMMUNICATION = "communication"


class MCPStatus(str, Enum):
    """Health status of MCP server."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    STOPPED = "stopped"


# Circuit breaker threshold - mark unhealthy after this many consecutive errors
UNHEALTHY_THRESHOLD = 3
# Health check interval in seconds
HEALTH_CHECK_INTERVAL = 30


@dataclass
class MCPServer:
    """
    MCP Server status and health tracking.

    Per FR-016: Operate separate MCP servers for different domains
    Per FR-018: Track health status independently
    Per FR-019: Prevent routing to unhealthy servers
    """

    id: str = ""  # e.g., "financial", "social", "communication"
    domain: MCPDomain = MCPDomain.COMMUNICATION
    endpoint: str = ""  # HTTP endpoint URL
    status: MCPStatus = MCPStatus.STOPPED
    last_health_at: Optional[str] = None  # Last successful health check
    error_count: int = 0  # Consecutive error count
    version: Optional[str] = None  # Server version
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def record_success(self) -> None:
        """Record successful health check or action."""
        self.status = MCPStatus.HEALTHY
        self.error_count = 0
        self.last_health_at = datetime.utcnow().isoformat()
        self.updated_at = self.last_health_at

    def record_error(self) -> bool:
        """
        Record health check or action error.

        Returns True if server is now unhealthy (exceeded threshold).
        """
        self.error_count += 1
        self.updated_at = datetime.utcnow().isoformat()

        if self.error_count >= UNHEALTHY_THRESHOLD:
            self.status = MCPStatus.UNHEALTHY
            return True

        return False

    def is_available(self) -> bool:
        """Check if server is available for routing."""
        return self.status == MCPStatus.HEALTHY

    def mark_starting(self) -> None:
        """Mark server as starting up."""
        self.status = MCPStatus.STARTING
        self.error_count = 0
        self.updated_at = datetime.utcnow().isoformat()

    def mark_stopped(self) -> None:
        """Mark server as stopped."""
        self.status = MCPStatus.STOPPED
        self.updated_at = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "domain": self.domain.value if isinstance(self.domain, MCPDomain) else self.domain,
            "endpoint": self.endpoint,
            "status": self.status.value if isinstance(self.status, MCPStatus) else self.status,
            "last_health_at": self.last_health_at,
            "error_count": self.error_count,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPServer":
        """Create from dictionary."""
        if "domain" in data and isinstance(data["domain"], str):
            data["domain"] = MCPDomain(data["domain"])
        if "status" in data and isinstance(data["status"], str):
            data["status"] = MCPStatus(data["status"])
        return cls(**data)

    @classmethod
    def create_financial_server(cls, port: int = 8001) -> "MCPServer":
        """Create Financial MCP server configuration."""
        return cls(
            id="financial",
            domain=MCPDomain.FINANCIAL,
            endpoint=f"http://localhost:{port}",
            status=MCPStatus.STOPPED,
        )

    @classmethod
    def create_social_server(cls, port: int = 8002) -> "MCPServer":
        """Create Social MCP server configuration."""
        return cls(
            id="social",
            domain=MCPDomain.SOCIAL,
            endpoint=f"http://localhost:{port}",
            status=MCPStatus.STOPPED,
        )

    @classmethod
    def create_communication_server(cls, port: int = 8003) -> "MCPServer":
        """Create Communication MCP server configuration."""
        return cls(
            id="communication",
            domain=MCPDomain.COMMUNICATION,
            endpoint=f"http://localhost:{port}",
            status=MCPStatus.STOPPED,
        )

    @classmethod
    def create_coordinator_server(cls, port: int = 8000) -> "MCPServer":
        """Create Coordinator MCP server configuration."""
        return cls(
            id="coordinator",
            domain=MCPDomain.COORDINATOR,
            endpoint=f"http://localhost:{port}",
            status=MCPStatus.STOPPED,
        )
