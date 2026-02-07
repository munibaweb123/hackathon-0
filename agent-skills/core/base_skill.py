"""
Base Skill Module

This module defines the base class for all agent skills.
All AI functionality must be implemented as Agent Skills that inherit
from this base class.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from core.logger import Logger
from core.vault_interface import VaultInterface


class BaseSkill(ABC):
    """
    Base class for all agent skills.
    All AI functionality must be implemented as Agent Skills that inherit
    from this class, ensuring a consistent interface and behavior.
    """

    def __init__(self, name: str, vault_interface: VaultInterface, logger: Logger):
        """
        Initialize the base skill with required interfaces.

        Args:
            name: Name of the skill
            vault_interface: Interface for vault operations
            logger: Logger instance for auditability
        """
        self.name = name
        self.vault_interface = vault_interface
        self.logger = logger

    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Execute the skill with the given input data.

        Args:
            input_data: Input data for the skill

        Returns:
            Output data from the skill execution or None if failed
        """
        pass

    def log_execution(self, input_data: Dict[str, Any], output_data: Optional[Dict[str, Any]]):
        """
        Log the skill execution for auditability.

        Args:
            input_data: Input data to the skill
            output_data: Output data from the skill
        """
        self.logger.log_system_event(
            event_type="skill_execution",
            component=f"{self.name}_skill",
            message=f"Skill {self.name} executed",
            details={
                "input": input_data,
                "output": output_data
            }
        )

    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """
        Validate the input data for the skill.

        Args:
            input_data: Input data to validate

        Returns:
            True if input is valid, False otherwise
        """
        # Default validation - check if input is a dictionary
        if not isinstance(input_data, dict):
            return False
        return True