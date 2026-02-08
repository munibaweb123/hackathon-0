"""
Vault Interface Module

This module provides methods to read/write files in the vault structure.
The vault follows a file-based governance model where all state changes and
communications occur through file-based interactions within the established
vault structure.

Silver Tier Extensions:
- Support for plans, posts, config folders
- Event file reading with YAML frontmatter parsing
- Approval folder watching (Approved/Rejected)
"""

import os
import json
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import uuid


class VaultInterface:
    """
    Interface for interacting with the Obsidian vault structure.
    Manages reading and writing of files within the designated vault directories.

    Silver Tier additions:
    - plans/ folder for Plan.md files
    - posts/ folder for LinkedIn posts
    - config/ folder for watchers.yaml and schedules.yaml
    - Approved/ and Rejected/ folders for approval workflow
    """

    def __init__(self, vault_path: str = "./obsidian-vault"):
        """
        Initialize the vault interface with the base path.

        Args:
            vault_path: Base path to the vault directory
        """
        self.vault_path = Path(vault_path)
        self.inbox_path = self.vault_path / "inbox"
        self.processed_path = self.vault_path / "processed"
        self.processing_path = self.vault_path / "processing"
        self.pending_approval_path = self.vault_path / "pending-approval"
        self.completed_path = self.vault_path / "completed"

        # Silver Tier folders
        self.approved_path = self.vault_path / "Approved"
        self.rejected_path = self.vault_path / "Rejected"
        self.plans_path = self.vault_path / "plans"
        self.posts_path = self.vault_path / "posts"
        self.config_path = self.vault_path / "config"
        self.logs_path = self.vault_path / "logs"
        self.archive_path = self.vault_path / "archive"
        self.error_path = self.vault_path / "error"

        # Create directories if they don't exist
        for path in [
            self.vault_path,
            self.inbox_path,
            self.processed_path,
            self.processing_path,
            self.pending_approval_path,
            self.completed_path,
            self.approved_path,
            self.rejected_path,
            self.plans_path,
            self.posts_path,
            self.config_path,
            self.logs_path,
            self.archive_path,
            self.error_path,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def read_file(self, file_path: Union[str, Path]) -> str:
        """
        Read content from a file in the vault.

        Args:
            file_path: Path to the file to read

        Returns:
            Content of the file as string
        """
        full_path = Path(file_path)
        if not full_path.is_absolute():
            full_path = self.vault_path / full_path

        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()

    def write_file(self, file_path: Union[str, Path], content: str,
                   destination_folder: str = "inbox") -> Path:
        """
        Write content to a file in the vault.

        Args:
            file_path: Path to the file to write
            content: Content to write to the file
            destination_folder: Which vault folder to write to (inbox, processed, etc.)

        Returns:
            Path object of the written file
        """
        # Determine the destination folder
        folder_map = {
            "inbox": self.inbox_path,
            "processed": self.processed_path,
            "processing": self.processing_path,
            "pending-approval": self.pending_approval_path,
            "completed": self.completed_path,
            "approved": self.approved_path,
            "rejected": self.rejected_path,
            "plans": self.plans_path,
            "posts": self.posts_path,
            "config": self.config_path,
            "logs": self.logs_path,
            "archive": self.archive_path,
            "error": self.error_path,
        }

        dest_path = folder_map.get(destination_folder, self.inbox_path)
        full_path = dest_path / Path(file_path)

        # Create parent directories if they don't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return full_path

    def move_file(self, source_path: Union[str, Path],
                  destination_folder: str, new_filename: Optional[str] = None) -> Path:
        """
        Move a file from one location to another within the vault.

        Args:
            source_path: Path to the source file
            destination_folder: Destination folder (inbox, processed, etc.)
            new_filename: New name for the file (optional)

        Returns:
            Path object of the moved file
        """
        source = Path(source_path)
        if not source.is_absolute():
            source = self.vault_path / source

        # Determine destination folder
        folder_map = {
            "inbox": self.inbox_path,
            "processed": self.processed_path,
            "processing": self.processing_path,
            "pending-approval": self.pending_approval_path,
            "completed": self.completed_path,
            "approved": self.approved_path,
            "rejected": self.rejected_path,
            "plans": self.plans_path,
            "posts": self.posts_path,
            "config": self.config_path,
            "logs": self.logs_path,
            "archive": self.archive_path,
            "error": self.error_path,
        }

        dest_folder = folder_map.get(destination_folder, self.inbox_path)

        # Determine final filename
        if new_filename:
            dest_path = dest_folder / new_filename
        else:
            dest_path = dest_folder / source.name

        # Create destination folder if it doesn't exist
        dest_folder.mkdir(parents=True, exist_ok=True)

        # Move the file
        source.rename(dest_path)

        return dest_path

    def get_files_in_folder(self, folder_name: str = "inbox") -> List[Path]:
        """
        Get all files in a specific vault folder.

        Args:
            folder_name: Name of the folder (inbox, processed, etc.)

        Returns:
            List of Path objects for files in the folder, relative to the vault directory
        """
        folder_map = {
            "inbox": self.inbox_path,
            "processed": self.processed_path,
            "processing": self.processing_path,
            "pending-approval": self.pending_approval_path,
            "completed": self.completed_path,
            "approved": self.approved_path,
            "rejected": self.rejected_path,
            "plans": self.plans_path,
            "posts": self.posts_path,
            "config": self.config_path,
            "logs": self.logs_path,
            "archive": self.archive_path,
            "error": self.error_path,
        }

        folder_path = folder_map.get(folder_name, self.inbox_path)
        if not folder_path.exists():
            return []
        files = [f for f in folder_path.iterdir() if f.is_file()]

        # Convert paths to be relative to the vault directory for compatibility with read_file
        relative_files = []
        for file_path in files:
            # Get the path relative to the vault directory
            try:
                rel_path = file_path.relative_to(self.vault_path)
                relative_files.append(rel_path)
            except ValueError:
                # If the file is not within the vault path, keep the original path
                relative_files.append(file_path)

        return relative_files

    def create_structured_file(self, filename: str, data: Dict,
                              destination_folder: str = "inbox") -> Path:
        """
        Create a structured JSON file in the vault with timestamp and metadata.

        Args:
            filename: Name of the file to create
            data: Dictionary containing the structured data
            destination_folder: Which vault folder to write to

        Returns:
            Path object of the created file
        """
        # Add timestamp and metadata to the data
        structured_data = {
            "timestamp": datetime.now().isoformat(),
            "filename": filename,
            "data": data
        }

        content = json.dumps(structured_data, indent=2)
        return self.write_file(filename, content, destination_folder)

    # Silver Tier Methods

    def read_event_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Read an event file with YAML frontmatter.

        Args:
            file_path: Path to the event file

        Returns:
            Dictionary with 'metadata' and 'content' keys
        """
        content = self.read_file(file_path)

        # Parse YAML frontmatter
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                metadata = yaml.safe_load(parts[1])
                body = parts[2].strip()
                return {"metadata": metadata, "content": body}

        # No frontmatter, try JSON
        try:
            return {"metadata": json.loads(content), "content": ""}
        except json.JSONDecodeError:
            return {"metadata": {}, "content": content}

    def write_event_file(
        self,
        filename: str,
        metadata: Dict[str, Any],
        content: str,
        destination_folder: str = "inbox"
    ) -> Path:
        """
        Write an event file with YAML frontmatter.

        Args:
            filename: Name of the file
            metadata: YAML frontmatter data
            content: Markdown content
            destination_folder: Destination folder

        Returns:
            Path to the created file
        """
        yaml_content = yaml.dump(metadata, default_flow_style=False, allow_unicode=True)
        file_content = f"---\n{yaml_content}---\n\n{content}"
        return self.write_file(filename, file_content, destination_folder)

    def get_pending_approvals(self) -> List[Path]:
        """Get all files in the pending-approval folder."""
        return self.get_files_in_folder("pending-approval")

    def get_approved_files(self) -> List[Path]:
        """Get all files in the Approved folder."""
        return self.get_files_in_folder("approved")

    def get_rejected_files(self) -> List[Path]:
        """Get all files in the Rejected folder."""
        return self.get_files_in_folder("rejected")

    def get_plans(self) -> List[Path]:
        """Get all plan files."""
        return self.get_files_in_folder("plans")

    def get_posts(self) -> List[Path]:
        """Get all post files."""
        return self.get_files_in_folder("posts")

    def load_config(self, config_name: str) -> Dict[str, Any]:
        """
        Load a YAML config file from the config folder.

        Args:
            config_name: Name of config file (e.g., 'watchers.yaml')

        Returns:
            Parsed YAML as dictionary
        """
        config_path = self.config_path / config_name
        if not config_path.exists():
            return {}

        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def save_config(self, config_name: str, data: Dict[str, Any]) -> Path:
        """
        Save a YAML config file to the config folder.

        Args:
            config_name: Name of config file
            data: Data to save

        Returns:
            Path to saved file
        """
        config_path = self.config_path / config_name
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        return config_path

    def get_inbox_events_by_type(self, source_type: str) -> List[Path]:
        """
        Get inbox files filtered by source type.

        Args:
            source_type: Type prefix (e.g., 'EMAIL', 'LINKEDIN', 'WHATSAPP')

        Returns:
            List of matching file paths
        """
        all_files = self.get_files_in_folder("inbox")
        return [f for f in all_files if f.name.startswith(source_type.upper())]

    def file_exists(self, file_path: Union[str, Path]) -> bool:
        """Check if a file exists in the vault."""
        full_path = Path(file_path)
        if not full_path.is_absolute():
            full_path = self.vault_path / full_path
        return full_path.exists()

    def delete_file(self, file_path: Union[str, Path]) -> bool:
        """
        Delete a file from the vault.

        Args:
            file_path: Path to the file

        Returns:
            True if deleted, False if not found
        """
        full_path = Path(file_path)
        if not full_path.is_absolute():
            full_path = self.vault_path / full_path

        if full_path.exists():
            full_path.unlink()
            return True
        return False

    def create_event_file(self, event_data: Dict) -> Path:
        """
        Create a structured event file in the inbox with proper naming convention.

        Args:
            event_data: Dictionary containing event information following the data model

        Returns:
            Path object of the created file
        """
        # Create a filename based on event type and timestamp
        source_type = event_data.get('source_type', 'GENERIC')
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        event_id = event_data.get('id', str(uuid.uuid4()))

        filename = f"{source_type.upper()}_{timestamp}_{event_id}.md"

        # Handle datetime conversion for metadata
        timestamp_value = event_data.get('timestamp')
        detected_at_value = event_data.get('detected_at')

        if isinstance(timestamp_value, datetime):
            timestamp_str = timestamp_value.isoformat()
        elif isinstance(timestamp_value, str):
            timestamp_str = timestamp_value
        else:
            timestamp_str = datetime.now().isoformat()

        if isinstance(detected_at_value, datetime):
            detected_at_str = detected_at_value.isoformat()
        elif isinstance(detected_at_value, str):
            detected_at_str = detected_at_value
        else:
            detected_at_str = datetime.now().isoformat()

        # Create the event content with YAML frontmatter
        metadata = {
            'id': event_data.get('id', str(uuid.uuid4())),
            'source_type': event_data.get('source_type'),
            'source_id': event_data.get('source_id'),
            'event_type': event_data.get('event_type'),
            'timestamp': timestamp_str,
            'detected_at': detected_at_str,
            'priority': event_data.get('priority', 'medium'),
            'processing_status': event_data.get('processing_status', 'new'),
            'raw_data': event_data.get('raw_data', {}),
            'normalized_data': event_data.get('normalized_data', {}),
            'file_path': f"inbox/{filename}",
            'plan_id': event_data.get('plan_id')
        }

        # Create the content
        content_lines = []
        content_lines.append(f"# {source_type.title()} Event")
        content_lines.append("")
        content_lines.append(f"**Source Type**: {event_data.get('source_type', 'Unknown')}")
        content_lines.append(f"**Event Type**: {event_data.get('event_type', 'Unknown')}")
        content_lines.append(f"**Timestamp**: {timestamp_str}")
        content_lines.append("")
        content_lines.append("## Raw Data")
        content_lines.append("```json")
        content_lines.append(json.dumps(event_data.get('raw_data', {}), indent=2, default=str))
        content_lines.append("```")
        content_lines.append("")
        content_lines.append("## Normalized Data")
        content_lines.append(f"**Summary**: {event_data.get('normalized_data', {}).get('summary', '')}")
        content_lines.append("")

        content = "\n".join(content_lines)

        return self.write_event_file(filename, metadata, content, "inbox")