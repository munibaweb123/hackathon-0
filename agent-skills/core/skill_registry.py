"""
Skill Registry Module

Dynamic skill loading and registration for the Agent Skills framework.
Provides a central registry for discovering and invoking skills.

Task T069: Create skill registry for dynamic skill loading
"""

from typing import Any, Dict, List, Optional, Type
from core.base_skill import BaseSkill
from core.logger import Logger


class SkillRegistry:
    """
    Central registry for Agent Skills.
    Supports dynamic registration, discovery, and invocation.
    """

    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill):
        """
        Register a skill instance.

        Args:
            skill: BaseSkill instance to register
        """
        self._skills[skill.id] = skill

        if self.logger:
            self.logger.log_system_event(
                event_type="skill_registered",
                component="skill_registry",
                message=f"Skill registered: {skill.id} ({skill.name})",
                details={"skill_id": skill.id, "version": skill.version},
            )

    def unregister(self, skill_id: str) -> bool:
        """
        Unregister a skill by ID.

        Returns:
            True if skill was found and removed
        """
        if skill_id in self._skills:
            del self._skills[skill_id]
            return True
        return False

    def get(self, skill_id: str) -> Optional[BaseSkill]:
        """Get a skill by ID."""
        return self._skills.get(skill_id)

    def list_skills(self) -> List[Dict[str, Any]]:
        """List all registered skills with metadata."""
        return [skill.to_dict() for skill in self._skills.values()]

    def list_enabled(self) -> List[str]:
        """List IDs of all enabled skills."""
        return [sid for sid, skill in self._skills.items() if skill.enabled]

    def get_by_name(self, name: str) -> Optional[BaseSkill]:
        """Find a skill by name."""
        for skill in self._skills.values():
            if skill.name == name:
                return skill
        return None

    async def execute_skill(
        self, skill_id: str, input_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Execute a skill by ID with safe error handling.

        Args:
            skill_id: Skill ID
            input_data: Input data for the skill

        Returns:
            SkillResult data or None
        """
        skill = self.get(skill_id)
        if not skill:
            if self.logger:
                self.logger.log_system_event(
                    event_type="skill_not_found",
                    component="skill_registry",
                    message=f"Skill not found: {skill_id}",
                )
            return None

        result = await skill.safe_execute(input_data)
        return result.data if result.success else None

    def check_dependencies(self, skill_id: str) -> Dict[str, bool]:
        """
        Check if all dependencies for a skill are registered and enabled.

        Returns:
            Dict mapping dependency IDs to their availability status
        """
        skill = self.get(skill_id)
        if not skill:
            return {}

        status = {}
        for dep_id in skill.dependencies:
            dep = self.get(dep_id)
            status[dep_id] = dep is not None and dep.enabled

        return status

    def get_status(self) -> Dict[str, Any]:
        """Get registry status summary."""
        return {
            "total": len(self._skills),
            "enabled": len(self.list_enabled()),
            "disabled": len(self._skills) - len(self.list_enabled()),
            "skills": {
                sid: {
                    "name": s.name,
                    "enabled": s.enabled,
                    "version": s.version,
                }
                for sid, s in self._skills.items()
            },
        }
