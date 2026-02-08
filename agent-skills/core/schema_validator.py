"""
Schema Validator for Silver Tier Events

Validates watcher events against the JSON Schema defined in
specs/003-silver-tier-assistant/contracts/watcher-events.schema.json
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

try:
    from jsonschema import validate, ValidationError, Draft202012Validator
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    ValidationError = Exception


@dataclass
class ValidationResult:
    """Result of schema validation."""
    valid: bool
    errors: List[str]
    warnings: List[str]


class SchemaValidator:
    """Validates data against JSON schemas."""

    def __init__(self, schema_path: Optional[Path] = None):
        """
        Initialize the schema validator.

        Args:
            schema_path: Path to the schema file. If None, uses default location.
        """
        if not JSONSCHEMA_AVAILABLE:
            raise ImportError(
                "jsonschema package is required for schema validation. "
                "Install it with: pip install jsonschema"
            )

        self._schemas: Dict[str, dict] = {}
        self._default_schema_dir = Path(__file__).parent.parent.parent / "specs" / "003-silver-tier-assistant" / "contracts"

        if schema_path:
            self.load_schema("custom", schema_path)

    def load_schema(self, name: str, path: Path) -> None:
        """
        Load a JSON schema from a file.

        Args:
            name: Name to reference this schema
            path: Path to the schema file
        """
        with open(path, 'r') as f:
            self._schemas[name] = json.load(f)

    def load_watcher_events_schema(self) -> None:
        """Load the watcher events schema from the default location."""
        schema_path = self._default_schema_dir / "watcher-events.schema.json"
        if schema_path.exists():
            self.load_schema("watcher_events", schema_path)
        else:
            raise FileNotFoundError(f"Watcher events schema not found at {schema_path}")

    def validate_event(self, event_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate an event against the watcher events schema.

        Args:
            event_data: The event data to validate

        Returns:
            ValidationResult with validation status and any errors
        """
        if "watcher_events" not in self._schemas:
            self.load_watcher_events_schema()

        return self.validate(event_data, "watcher_events")

    def validate(self, data: Dict[str, Any], schema_name: str) -> ValidationResult:
        """
        Validate data against a named schema.

        Args:
            data: The data to validate
            schema_name: Name of the schema to validate against

        Returns:
            ValidationResult with validation status and any errors
        """
        if schema_name not in self._schemas:
            return ValidationResult(
                valid=False,
                errors=[f"Schema '{schema_name}' not loaded"],
                warnings=[]
            )

        schema = self._schemas[schema_name]
        errors = []
        warnings = []

        try:
            validate(instance=data, schema=schema)
            return ValidationResult(valid=True, errors=[], warnings=warnings)
        except ValidationError as e:
            errors.append(f"Validation error at {'.'.join(str(p) for p in e.path)}: {e.message}")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

    def validate_metadata(self, metadata: Dict[str, Any]) -> ValidationResult:
        """
        Validate event metadata fields.

        Args:
            metadata: The metadata portion of an event

        Returns:
            ValidationResult with validation status
        """
        required_fields = ["id", "source_type", "event_type", "timestamp", "detected_at", "priority", "processing_status"]
        errors = []
        warnings = []

        for field in required_fields:
            if field not in metadata:
                errors.append(f"Missing required field: {field}")

        # Validate enums
        if "source_type" in metadata:
            valid_sources = ["gmail", "linkedin", "whatsapp"]
            if metadata["source_type"] not in valid_sources:
                errors.append(f"Invalid source_type: {metadata['source_type']}. Must be one of {valid_sources}")

        if "priority" in metadata:
            valid_priorities = ["low", "medium", "high", "urgent"]
            if metadata["priority"] not in valid_priorities:
                errors.append(f"Invalid priority: {metadata['priority']}. Must be one of {valid_priorities}")

        if "processing_status" in metadata:
            valid_statuses = ["new", "processing", "plan_generated", "archived"]
            if metadata["processing_status"] not in valid_statuses:
                errors.append(f"Invalid processing_status: {metadata['processing_status']}. Must be one of {valid_statuses}")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


def validate_event_file(file_path: Path) -> Tuple[bool, List[str]]:
    """
    Validate an event file from the vault.

    Args:
        file_path: Path to the event file

    Returns:
        Tuple of (is_valid, list of errors)
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Parse YAML frontmatter if present
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                import yaml
                metadata = yaml.safe_load(parts[1])
                validator = SchemaValidator()
                result = validator.validate_metadata(metadata)
                return result.valid, result.errors

        # Try as JSON
        data = json.loads(content)
        validator = SchemaValidator()
        result = validator.validate_event(data)
        return result.valid, result.errors

    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    except Exception as e:
        return False, [f"Error validating file: {e}"]
