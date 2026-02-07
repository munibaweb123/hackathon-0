"""
Watcher Base Module

This module provides a base class for all watcher implementations.
All watcher scripts must inherit from this base class, ensuring consistent behavior.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from core.vault_interface import VaultInterface
from core.logger import Logger


class WatcherBase(ABC):
    """
    Base class for all watcher implementations.
    All watcher scripts must inherit from this base class, ensuring consistent behavior.
    """

    def __init__(self, name: str, vault_interface: VaultInterface, logger: Logger):
        """
        Initialize the base watcher with required interfaces.

        Args:
            name: Name of the watcher (e.g., 'gmail', 'linkedin')
            vault_interface: Interface for vault operations
            logger: Logger instance for auditability
        """
        self.name = name
        self.vault_interface = vault_interface
        self.logger = logger
        self.is_running = False

    @abstractmethod
    def detect_events(self) -> Optional[Dict[str, Any]]:
        """
        Detect external events and return structured data.

        Returns:
            Dictionary with event data or None if no events detected
        """
        pass

    @abstractmethod
    def normalize_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize raw event data to a consistent format.

        Args:
            raw_data: Raw data from the external source

        Returns:
            Normalized data dictionary
        """
        pass

    def create_structured_file(self, event_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a structured file in the vault from event data.

        Args:
            event_data: Event data to store

        Returns:
            Path to the created file or None if creation failed
        """
        try:
            # Add metadata to the event data
            structured_data = {
                "source": self.name,
                "event_type": event_data.get('event_type', 'generic'),
                "raw_data": event_data,
                "normalized_data": self.normalize_data(event_data)
            }

            # Create filename with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.name}_event_{timestamp}.json"

            # Write to vault inbox
            file_path = self.vault_interface.create_structured_file(
                filename=filename,
                data=structured_data,
                destination_folder="inbox"
            )

            # Log the watcher event
            self.logger.log_watcher_event(
                event_type=event_data.get('event_type', 'generic'),
                source=self.name,
                details={"file_created": str(file_path)}
            )

            return str(file_path)
        except Exception as e:
            self.logger.log_system_event(
                event_type="error",
                component=f"{self.name}_watcher",
                message=f"Failed to create structured file: {e}",
                details={"event_data": event_data}
            )
            return None

    def validate_raw_data(self, raw_data: Dict[str, Any]) -> bool:
        """
        Validate raw data from the external source.

        Args:
            raw_data: Raw data to validate

        Returns:
            True if data is valid, False otherwise
        """
        # Default validation - check if input is a dictionary
        if not isinstance(raw_data, dict):
            return False
        return True

    def start_monitoring(self):
        """
        Start monitoring for events.
        """
        self.is_running = True
        self.logger.log_system_event(
            event_type="watcher_started",
            component=f"{self.name}_watcher",
            message=f"{self.name.capitalize()} watcher started monitoring"
        )

    def stop_monitoring(self):
        """
        Stop monitoring for events.
        """
        self.is_running = False
        self.logger.log_system_event(
            event_type="watcher_stopped",
            component=f"{self.name}_watcher",
            message=f"{self.name.capitalize()} watcher stopped monitoring"
        )