"""
File Processor Module

This module provides methods to process structured files from watchers.
It handles reading, parsing, and validating the structured data files
created by the watcher scripts.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta


class FileProcessor:
    """
    Processor for structured files from watchers.
    Handles reading, parsing, and validation of structured data files.
    """

    def __init__(self):
        """Initialize the file processor."""
        pass

    def read_structured_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Read and parse a structured file from the watcher output.

        Args:
            file_path: Path to the structured file

        Returns:
            Parsed data dictionary or None if file cannot be parsed
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except (json.JSONDecodeError, FileNotFoundError, UnicodeDecodeError) as e:
            print(f"Error reading structured file {file_path}: {e}")
            return None

    def validate_watcher_output(self, data: Dict[str, Any]) -> bool:
        """
        Validate that the structured data conforms to expected schema.

        Args:
            data: Dictionary containing the structured data

        Returns:
            True if data is valid, False otherwise
        """
        # Check for required fields in watcher output
        required_fields = ['timestamp', 'filename', 'data']

        for field in required_fields:
            if field not in data:
                print(f"Missing required field '{field}' in watcher output")
                return False

        # Validate timestamp format (ISO format)
        try:
            timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        except ValueError:
            print(f"Invalid timestamp format in watcher output: {data['timestamp']}")
            return False

        # Check if timestamp is within last 24 hours (as per data model)
        if timestamp < datetime.now() - timedelta(hours=24):
            print(f"Timestamp is older than 24 hours: {data['timestamp']}")
            return False

        # Validate that the inner data field is a dictionary
        if not isinstance(data['data'], dict):
            print(f"Inner 'data' field is not a dictionary: {type(data['data'])}")
            return False

        return True

    def normalize_watcher_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Normalize the watcher data to a consistent format.

        Args:
            data: Raw watcher data dictionary

        Returns:
            Normalized data dictionary or None if validation fails
        """
        if not self.validate_watcher_output(data):
            return None

        # Extract normalized data
        normalized = {
            'id': data.get('filename', '').split('.')[0],  # Use filename as ID
            'source': data['data'].get('source', 'unknown'),
            'event_type': data['data'].get('event_type', 'generic'),
            'timestamp': data['timestamp'],
            'normalized_data': data['data'],
            'file_path': data.get('filename', ''),
            'status': 'new'
        }

        return normalized

    def get_recent_files(self, directory: str, hours: int = 24) -> List[Path]:
        """
        Get files from a directory that were modified within the specified hours.

        Args:
            directory: Directory path to scan
            hours: Number of hours to look back

        Returns:
            List of Path objects for recent files
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            return []

        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_files = []

        for file_path in dir_path.iterdir():
            if file_path.is_file():
                # Get file modification time
                mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mod_time >= cutoff_time:
                    recent_files.append(file_path)

        return recent_files

    def process_directory(self, directory: str) -> List[Dict[str, Any]]:
        """
        Process all structured files in a directory.

        Args:
            directory: Directory path to process

        Returns:
            List of normalized data dictionaries
        """
        results = []
        recent_files = self.get_recent_files(directory)

        for file_path in recent_files:
            # Only process JSON files
            if file_path.suffix.lower() != '.json':
                continue

            data = self.read_structured_file(str(file_path))
            if data:
                normalized = self.normalize_watcher_data(data)
                if normalized:
                    results.append(normalized)

        return results