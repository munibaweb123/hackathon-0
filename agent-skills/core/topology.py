# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
Topology — skill-to-zone mapping and conflict resolution for Cloud/Local agents.

Loads topology.yaml from the repository root and provides:
- Skill assignment per agent zone
- Credential scope enforcement
- Conflict resolution strategy lookup
"""

import fnmatch
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger("topology")


class Topology:
    """Loads and queries the agent topology configuration."""

    def __init__(self, topology_path: Optional[str] = None) -> None:
        if topology_path:
            self.path = Path(topology_path).resolve()
        else:
            self.path = self._find_topology()
        self.data: Dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        """Load or reload topology.yaml."""
        if not self.path.exists():
            logger.warning("Topology file not found: %s", self.path)
            self.data = {}
            return
        try:
            self.data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
            logger.info("Loaded topology from %s", self.path)
        except Exception as e:
            logger.error("Failed to load topology: %s", e)
            self.data = {}

    def get_zone_skills(self, zone: str) -> List[str]:
        """Return the list of skills assigned to a zone."""
        agents = self.data.get("agents", {})
        zone_data = agents.get(zone, {})
        return zone_data.get("skills", [])

    def get_skill_zone(self, skill_name: str) -> Optional[str]:
        """
        Return which zone a skill belongs to.

        Returns 'cloud', 'local', or 'both' if shared (e.g. vault-sync).
        Returns None if skill is not in any zone.
        """
        agents = self.data.get("agents", {})
        in_cloud = skill_name in agents.get("cloud", {}).get("skills", [])
        in_local = skill_name in agents.get("local", {}).get("skills", [])

        if in_cloud and in_local:
            return "both"
        if in_cloud:
            return "cloud"
        if in_local:
            return "local"
        return None

    def get_credential_scope(self, zone: str) -> str:
        """Return credential scope for a zone ('readonly' or 'full')."""
        agents = self.data.get("agents", {})
        return agents.get(zone, {}).get("credential_scope", "readonly")

    def validate_agent(self, agent_id: str, zone: str, capabilities: List[str]) -> bool:
        """Check that all capabilities are allowed in the given zone."""
        allowed = set(self.get_zone_skills(zone))
        for cap in capabilities:
            if cap not in allowed:
                logger.warning(
                    "Agent %s (%s): capability %r not allowed in zone",
                    agent_id, zone, cap,
                )
                return False
        return True

    def get_conflict_strategy(self, file_path: str) -> str:
        """
        Match a file path against conflict resolution rules.

        Returns the strategy string (e.g., 'cloud_wins', 'local_wins', 'append_both').
        Falls back to the default strategy if no rule matches.
        """
        resolution = self.data.get("conflict_resolution", {})
        rules = resolution.get("rules", [])
        default = resolution.get("default", "manual_required")

        for rule in rules:
            pattern = rule.get("path", "")
            if fnmatch.fnmatch(file_path, pattern):
                return rule.get("strategy", default)

        return default

    def _find_topology(self) -> Path:
        """Search upward from this file to find topology.yaml in the repo root."""
        current = Path(__file__).resolve().parent
        for _ in range(10):
            candidate = current / "topology.yaml"
            if candidate.exists():
                return candidate
            parent = current.parent
            if parent == current:
                break
            current = parent
        # Fallback: assume repo root is 3 levels up from agent-skills/core/
        return Path(__file__).resolve().parent.parent.parent / "topology.yaml"
