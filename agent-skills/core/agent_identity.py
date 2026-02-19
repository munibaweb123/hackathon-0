# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
Agent Identity — registration, heartbeat, and capability tracking for Cloud/Local agents.

Each agent writes its identity file to Signals/agents/{agent-id}.yaml on startup
and updates it every sync cycle. Peers discover each other by reading this directory.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger("agent-identity")


class AgentIdentity:
    """
    Manages agent identity, heartbeat, and capability registration.

    Identity file location: {vault_path}/Signals/agents/{agent_id}.yaml
    """

    def __init__(
        self,
        agent_id: str,
        zone: str,
        vault_path: str,
        capabilities: Optional[List[str]] = None,
        sync_interval: int = 300,
        version: str = "1.0.0",
    ) -> None:
        if zone not in ("cloud", "local"):
            raise ValueError(f"Invalid zone: {zone!r} — must be 'cloud' or 'local'")

        self.agent_id = agent_id
        self.zone = zone
        self.vault_path = Path(vault_path).resolve()
        self.capabilities = capabilities or []
        self.sync_interval = sync_interval
        self.version = version
        self.status = "stopped"
        self.started_at: Optional[datetime] = None
        self.last_heartbeat: Optional[datetime] = None

        # Ensure directory exists
        self.agents_dir = self.vault_path / "Signals" / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.identity_path = self.agents_dir / f"{self.agent_id}.yaml"

    def start(self) -> None:
        """Mark agent as running and write initial identity file."""
        now = datetime.now(timezone.utc)
        self.status = "running"
        self.started_at = now
        self.last_heartbeat = now
        self._write_identity()
        logger.info("Agent %s (%s) started", self.agent_id, self.zone)

    def stop(self) -> None:
        """Mark agent as stopped and update identity file."""
        self.status = "stopped"
        self._write_identity()
        logger.info("Agent %s stopped", self.agent_id)

    def heartbeat(self) -> None:
        """Update the heartbeat timestamp."""
        self.last_heartbeat = datetime.now(timezone.utc)
        self._write_identity()
        logger.debug("Heartbeat: %s", self.agent_id)

    def set_degraded(self, reason: str = "") -> None:
        """Mark agent as degraded."""
        self.status = "degraded"
        self._write_identity()
        logger.warning("Agent %s degraded: %s", self.agent_id, reason)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize identity to dict matching agent_identity_schema."""
        return {
            "agent-id": self.agent_id,
            "zone": self.zone,
            "status": self.status,
            "started-at": self.started_at.isoformat() if self.started_at else None,
            "last-heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "capabilities": self.capabilities,
            "sync-interval": self.sync_interval,
            "version": self.version,
        }

    def _write_identity(self) -> None:
        """Write identity file to vault."""
        try:
            self.identity_path.write_text(
                yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to write identity file: %s", e)

    @classmethod
    def load(cls, identity_path: str) -> Optional["AgentIdentity"]:
        """Load an agent identity from a YAML file."""
        path = Path(identity_path)
        if not path.exists():
            return None

        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not data:
                return None

            vault_path = str(path.parent.parent.parent)  # Signals/agents/file.yaml -> vault root
            identity = cls(
                agent_id=data["agent-id"],
                zone=data["zone"],
                vault_path=vault_path,
                capabilities=data.get("capabilities", []),
                sync_interval=data.get("sync-interval", 300),
                version=data.get("version", "1.0.0"),
            )
            identity.status = data.get("status", "stopped")
            if data.get("started-at"):
                identity.started_at = datetime.fromisoformat(data["started-at"])
            if data.get("last-heartbeat"):
                identity.last_heartbeat = datetime.fromisoformat(data["last-heartbeat"])
            return identity
        except Exception as e:
            logger.error("Failed to load identity from %s: %s", path, e)
            return None

    @staticmethod
    def discover_peers(vault_path: str) -> List["AgentIdentity"]:
        """Discover all registered agents by reading Signals/agents/*.yaml."""
        agents_dir = Path(vault_path).resolve() / "Signals" / "agents"
        if not agents_dir.exists():
            return []

        peers = []
        for yaml_file in agents_dir.glob("*.yaml"):
            identity = AgentIdentity.load(str(yaml_file))
            if identity:
                peers.append(identity)
        return peers

    def is_alive(self) -> bool:
        """Check if agent heartbeat is within 2x sync_interval (considered alive)."""
        if not self.last_heartbeat or self.status == "stopped":
            return False
        now = datetime.now(timezone.utc)
        elapsed = (now - self.last_heartbeat).total_seconds()
        return elapsed <= self.sync_interval * 2

    def remove(self) -> None:
        """Remove identity file on clean shutdown."""
        try:
            if self.identity_path.exists():
                self.identity_path.unlink()
                logger.info("Removed identity file: %s", self.identity_path.name)
        except Exception as e:
            logger.error("Failed to remove identity file: %s", e)
