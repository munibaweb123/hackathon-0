"""
Watcher Output File Model

This module represents structured data files created by watcher scripts.
These files contain normalized information about external events detected by the system.
"""

from datetime import datetime
from typing import Dict, Any, Optional


class WatcherOutputFile:
    """
    Represents structured data files created by watcher scripts in the vault inbox.
    Contains normalized information about external events detected by the system.
    """

    def __init__(self, id: str, source: str, event_type: str, timestamp: str,
                 normalized_data: Dict[str, Any], file_path: str, status: str = "new"):
        """
        Initialize a WatcherOutputFile instance.

        Args:
            id: Unique identifier for the file
            source: Source of the event (Gmail, LinkedIn, etc.)
            event_type: Type of event detected
            timestamp: When the event was detected
            normalized_data: Normalized information about the event
            file_path: Path to the structured file in the vault
            status: Processing status (new, processed, error)
        """
        self.id = id
        self.source = source
        self.event_type = event_type
        self.timestamp = timestamp
        self.normalized_data = normalized_data
        self.file_path = file_path
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the WatcherOutputFile instance to a dictionary.

        Returns:
            Dictionary representation of the WatcherOutputFile
        """
        return {
            "id": self.id,
            "source": self.source,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "normalized_data": self.normalized_data,
            "file_path": self.file_path,
            "status": self.status
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WatcherOutputFile':
        """
        Create a WatcherOutputFile instance from a dictionary.

        Args:
            data: Dictionary containing WatcherOutputFile data

        Returns:
            WatcherOutputFile instance
        """
        return cls(
            id=data.get('id', ''),
            source=data.get('source', ''),
            event_type=data.get('event_type', ''),
            timestamp=data.get('timestamp', ''),
            normalized_data=data.get('normalized_data', {}),
            file_path=data.get('file_path', ''),
            status=data.get('status', 'new')
        )

    def validate(self) -> bool:
        """
        Validate the WatcherOutputFile instance.

        Returns:
            True if the instance is valid, False otherwise
        """
        # Check for required fields
        if not self.id or not self.source or not self.event_type or not self.timestamp:
            return False

        # Validate timestamp format (ISO format)
        try:
            from datetime import datetime, timedelta
            timestamp = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        except ValueError:
            return False

        # Check if timestamp is within last 24 hours (as per data model)
        if timestamp < datetime.now() - timedelta(hours=24):
            return False

        # Validate source
        if not isinstance(self.source, str) or len(self.source.strip()) == 0:
            return False

        # Validate normalized_data
        if not isinstance(self.normalized_data, dict):
            return False

        # Validate status
        if self.status not in ['new', 'processed', 'error']:
            return False

        return True

    def mark_processed(self):
        """
        Mark the file as processed.
        """
        self.status = "processed"

    def mark_error(self):
        """
        Mark the file as having an error.
        """
        self.status = "error"