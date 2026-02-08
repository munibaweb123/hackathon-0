"""
Base Skill Module

This module defines the base class for all agent skills.
All AI functionality must be implemented as Agent Skills that inherit
from this base class.

Silver Tier Extensions:
- Async execute pattern for non-blocking operations
- Input/output schema validation
- Error handling with graceful degradation
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import asyncio
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SkillResult:
    """Result of a skill execution."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class BaseSkill(ABC):
    """
    Base class for all agent skills.
    All AI functionality must be implemented as Agent Skills that inherit
    from this class, ensuring a consistent interface and behavior.

    Silver Tier features:
    - Async execution support
    - Schema-based input/output validation
    - Graceful error handling
    """

    def __init__(
        self,
        name: str,
        vault_interface: Optional[Any] = None,
        logger: Optional[Any] = None
    ):
        """
        Initialize the base skill with required interfaces.

        Args:
            name: Name of the skill
            vault_interface: Interface for vault operations (optional)
            logger: Logger instance for auditability (optional)
        """
        self.name = name
        self.vault_interface = vault_interface
        self.logger = logger
        self._enabled = True
        self._version = "1.0.0"

    @property
    @abstractmethod
    def id(self) -> str:
        """Unique identifier for this skill."""
        pass

    @property
    def description(self) -> str:
        """Human-readable description of what this skill does."""
        return f"Skill: {self.name}"

    @property
    def input_schema(self) -> dict:
        """JSON Schema for input validation. Override in subclasses."""
        return {"type": "object"}

    @property
    def output_schema(self) -> dict:
        """JSON Schema for output validation. Override in subclasses."""
        return {"type": "object"}

    @property
    def dependencies(self) -> List[str]:
        """List of skill IDs this skill depends on. Override if needed."""
        return []

    @property
    def enabled(self) -> bool:
        """Whether this skill is currently enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    @property
    def version(self) -> str:
        """Version of this skill."""
        return self._version

    # Synchronous execute (for backward compatibility)
    def execute(self, input_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Execute the skill synchronously.

        Args:
            input_data: Input data for the skill

        Returns:
            Output data from the skill execution or None if failed
        """
        result = asyncio.run(self.execute_async(input_data))
        return result.data if result.success else None

    @abstractmethod
    async def execute_async(self, input_data: Dict[str, Any]) -> SkillResult:
        """
        Execute the skill asynchronously.

        Args:
            input_data: Input data for the skill

        Returns:
            SkillResult with execution outcome
        """
        pass

    async def safe_execute(self, input_data: Dict[str, Any]) -> SkillResult:
        """
        Execute with error handling and graceful degradation.

        Args:
            input_data: Input data for the skill

        Returns:
            SkillResult, never raises exceptions
        """
        start_time = datetime.utcnow()

        try:
            # Validate input
            if not self.validate_input(input_data):
                return SkillResult(
                    success=False,
                    error="Input validation failed",
                    execution_time_ms=self._elapsed_ms(start_time)
                )

            # Check if enabled
            if not self.enabled:
                return SkillResult(
                    success=False,
                    error=f"Skill {self.name} is disabled",
                    execution_time_ms=self._elapsed_ms(start_time)
                )

            # Execute the skill
            result = await self.execute_async(input_data)
            result.execution_time_ms = self._elapsed_ms(start_time)

            # Validate output
            if result.success and result.data:
                if not self.validate_output(result.data):
                    result.warnings.append("Output validation failed")

            # Log execution
            self.log_execution(input_data, result)

            return result

        except Exception as e:
            error_msg = f"Skill execution failed: {str(e)}"
            self._log_error(error_msg, input_data)
            return SkillResult(
                success=False,
                error=error_msg,
                execution_time_ms=self._elapsed_ms(start_time)
            )

    def log_execution(
        self,
        input_data: Dict[str, Any],
        result: SkillResult
    ):
        """
        Log the skill execution for auditability.

        Args:
            input_data: Input data to the skill
            result: Result of the execution
        """
        if self.logger:
            self.logger.log_system_event(
                event_type="skill_execution",
                component=f"{self.name}_skill",
                message=f"Skill {self.name} executed: {'success' if result.success else 'failed'}",
                details={
                    "skill_id": self.id,
                    "success": result.success,
                    "execution_time_ms": result.execution_time_ms,
                    "error": result.error,
                    "warnings": result.warnings
                }
            )

    def _log_error(self, error: str, input_data: Dict[str, Any]):
        """Log an error during skill execution."""
        if self.logger:
            self.logger.log_system_event(
                event_type="skill_error",
                component=f"{self.name}_skill",
                message=error,
                details={"input_keys": list(input_data.keys()) if input_data else []}
            )

    def _elapsed_ms(self, start_time: datetime) -> float:
        """Calculate elapsed time in milliseconds."""
        return (datetime.utcnow() - start_time).total_seconds() * 1000

    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """
        Validate the input data against input_schema.

        Args:
            input_data: Input data to validate

        Returns:
            True if input is valid, False otherwise
        """
        if not isinstance(input_data, dict):
            return False

        # If jsonschema is available, use it for validation
        try:
            from jsonschema import validate, ValidationError
            validate(instance=input_data, schema=self.input_schema)
            return True
        except ImportError:
            # Fall back to basic validation
            return True
        except ValidationError:
            return False

    def validate_output(self, output_data: Dict[str, Any]) -> bool:
        """
        Validate the output data against output_schema.

        Args:
            output_data: Output data to validate

        Returns:
            True if output is valid, False otherwise
        """
        if not isinstance(output_data, dict):
            return False

        try:
            from jsonschema import validate, ValidationError
            validate(instance=output_data, schema=self.output_schema)
            return True
        except ImportError:
            return True
        except ValidationError:
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize skill metadata to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "enabled": self.enabled,
            "dependencies": self.dependencies,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema
        }