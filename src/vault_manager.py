"""Vault manager for directory operations."""

import shutil
from pathlib import Path
from typing import List, Optional
from .entities import FileEntity
from .logger import Logger


class VaultManager:
    """Manages vault directory operations and file state transitions."""

    def __init__(self, vault_path: str, logger: Logger):
        self.vault_path = Path(vault_path)
        self.logger = logger
        self._ensure_vault_structure()

    def _ensure_vault_structure(self):
        """Ensure the vault directory structure exists."""
        folders = [
            'inbox',
            'processing',
            'pending-approval',
            'completed',
            'rejected',
            'archive',
            'error'
        ]

        for folder in folders:
            (self.vault_path / folder).mkdir(parents=True, exist_ok=True)

        self.logger.info("system", "vault_initialized",
                         f"Vault structure initialized at {self.vault_path}")

    def get_files_in_folder(self, folder: str) -> List[Path]:
        """Get all files in a specific folder."""
        folder_path = self.vault_path / folder
        if not folder_path.exists():
            return []

        files = []
        for item in folder_path.iterdir():
            if item.is_file():
                files.append(item)

        return files

    def move_file(self, file_path: Path, destination_folder: str) -> Optional[Path]:
        """Move a file to a specific folder."""
        try:
            destination_path = self.vault_path / destination_folder / file_path.name

            # Check if file exists and is within vault
            if not file_path.exists():
                self.logger.error("system", "move_file_failed",
                                 f"Source file does not exist: {file_path}")
                return None

            # Validate path is safe
            from .file_monitor import path_is_safe
            if not path_is_safe(str(file_path), str(self.vault_path)):
                self.logger.error("system", "security_violation",
                                 f"Attempted to access file outside vault: {file_path}")
                return None

            # Move the file
            shutil.move(str(file_path), str(destination_path))

            self.logger.audit("system", "file_moved",
                             f"Moved file from {file_path} to {destination_path}",
                             file_ref=str(destination_path))

            return destination_path

        except Exception as e:
            self.logger.error("system", "move_file_error",
                             f"Error moving file {file_path}: {str(e)}")
            return None

    def copy_file(self, file_path: Path, destination_folder: str) -> Optional[Path]:
        """Copy a file to a specific folder."""
        try:
            destination_path = self.vault_path / destination_folder / file_path.name

            # Validate path is safe
            from .file_monitor import path_is_safe
            if not path_is_safe(str(file_path), str(self.vault_path)):
                self.logger.error("system", "security_violation",
                                 f"Attempted to access file outside vault: {file_path}")
                return None

            # Copy the file
            shutil.copy2(str(file_path), str(destination_path))

            self.logger.audit("system", "file_copied",
                             f"Copied file from {file_path} to {destination_path}",
                             file_ref=str(destination_path))

            return destination_path

        except Exception as e:
            self.logger.error("system", "copy_file_error",
                             f"Error copying file {file_path}: {str(e)}")
            return None

    def create_file(self, folder: str, filename: str, content: str = "") -> Optional[Path]:
        """Create a new file in a specific folder."""
        try:
            file_path = self.vault_path / folder / filename

            # Write the content to the file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            self.logger.audit("system", "file_created",
                             f"Created file at {file_path}",
                             file_ref=str(file_path))

            return file_path

        except Exception as e:
            self.logger.error("system", "create_file_error",
                             f"Error creating file {filename} in {folder}: {str(e)}")
            return None

    def get_file_status(self, file_path: Path) -> Optional[str]:
        """Get the current status of a file based on its location."""
        try:
            # Resolve the file path to get the actual location
            resolved_path = file_path.resolve()
            vault_path = self.vault_path.resolve()

            # Check if file is in vault
            if not path_is_safe(str(resolved_path), str(vault_path)):
                return None

            # Determine the status based on the folder
            relative_path = resolved_path.relative_to(vault_path)
            folder = relative_path.parts[0]  # First part is the folder

            status_mapping = {
                'inbox': 'new',
                'processing': 'processing',
                'pending-approval': 'pending_approval',
                'completed': 'completed',
                'rejected': 'rejected',
                'archive': 'archived',
                'error': 'error'
            }

            return status_mapping.get(folder, 'unknown')

        except Exception as e:
            self.logger.error("system", "get_file_status_error",
                             f"Error getting status for file {file_path}: {str(e)}")
            return None