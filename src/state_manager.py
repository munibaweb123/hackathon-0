"""State management for folder transitions."""

from pathlib import Path
from typing import Optional
from .entities import FileEntity
from .vault_manager import VaultManager
from .logger import Logger


class StateManager:
    """Manages file state transitions between folders."""

    def __init__(self, vault_manager: VaultManager, logger: Logger):
        self.vault_manager = vault_manager
        self.logger = logger

    def transition_file(self, file_path: Path, new_state: str) -> bool:
        """Transition a file to a new state by moving it to the appropriate folder."""
        # Map state to folder
        state_to_folder = {
            'new': 'inbox',
            'processing': 'processing',
            'pending_approval': 'pending-approval',
            'completed': 'completed',
            'rejected': 'rejected',
            'archived': 'archive',
            'error': 'error'
        }

        if new_state not in state_to_folder:
            self.logger.error("system", "invalid_state",
                             f"Invalid state: {new_state}")
            return False

        destination_folder = state_to_folder[new_state]

        # Move the file to the new folder
        result = self.vault_manager.move_file(file_path, destination_folder)

        if result:
            self.logger.info("system", "state_transition",
                            f"File {file_path.name} transitioned to {new_state}",
                            file_ref=str(result))
            return True
        else:
            return False

    def get_file_state(self, file_path: Path) -> Optional[str]:
        """Get the current state of a file."""
        return self.vault_manager.get_file_status(file_path)

    def get_files_by_state(self, state: str) -> list:
        """Get all files in a specific state."""
        # Map state to folder
        state_to_folder = {
            'new': 'inbox',
            'processing': 'processing',
            'pending_approval': 'pending-approval',
            'completed': 'completed',
            'rejected': 'rejected',
            'archived': 'archive',
            'error': 'error'
        }

        if state not in state_to_folder:
            self.logger.error("system", "invalid_state",
                             f"Invalid state: {state}")
            return []

        folder = state_to_folder[state]
        return self.vault_manager.get_files_in_folder(folder)