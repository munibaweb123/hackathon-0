"""
Vault Interface Module

This module provides methods to read/write files in the vault structure.
The vault follows a file-based governance model where all state changes and
communications occur through file-based interactions within the established
vault structure.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Union
from datetime import datetime


class VaultInterface:
    """
    Interface for interacting with the Obsidian vault structure.
    Manages reading and writing of files within the designated vault directories.
    """

    def __init__(self, vault_path: str = "./vault"):
        """
        Initialize the vault interface with the base path.

        Args:
            vault_path: Base path to the vault directory
        """
        self.vault_path = Path(vault_path)
        self.inbox_path = self.vault_path / "inbox"
        self.processed_path = self.vault_path / "processed"
        self.pending_approval_path = self.vault_path / "pending-approval"
        self.completed_path = self.vault_path / "completed"

        # Create directories if they don't exist
        for path in [
            self.vault_path,
            self.inbox_path,
            self.processed_path,
            self.pending_approval_path,
            self.completed_path
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
            "pending-approval": self.pending_approval_path,
            "completed": self.completed_path
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
            "pending-approval": self.pending_approval_path,
            "completed": self.completed_path
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
            "pending-approval": self.pending_approval_path,
            "completed": self.completed_path
        }

        folder_path = folder_map.get(folder_name, self.inbox_path)
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