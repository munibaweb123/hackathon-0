"""Configuration parser for the Personal AI Employee."""

import yaml
from pathlib import Path
from typing import Dict, Any


class Config:
    """Configuration parser for config.yaml."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.settings = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def get(self, key: str, default=None):
        """Get a configuration value."""
        return self.settings.get(key, default)

    @property
    def vault_path(self) -> str:
        """Get the vault path from configuration."""
        return self.settings.get('vault_path', './obsidian-vault')

    @property
    def input_folder(self) -> str:
        """Get the input folder from configuration."""
        return self.settings.get('input_folder', 'inbox')

    @property
    def processing_folder(self) -> str:
        """Get the processing folder from configuration."""
        return self.settings.get('processing_folder', 'processing')

    @property
    def pending_approval_folder(self) -> str:
        """Get the pending approval folder from configuration."""
        return self.settings.get('pending_approval_folder', 'pending-approval')

    @property
    def completed_folder(self) -> str:
        """Get the completed folder from configuration."""
        return self.settings.get('completed_folder', 'completed')

    @property
    def rejected_folder(self) -> str:
        """Get the rejected folder from configuration."""
        return self.settings.get('rejected_folder', 'rejected')

    @property
    def archive_folder(self) -> str:
        """Get the archive folder from configuration."""
        return self.settings.get('archive_folder', 'archive')

    @property
    def error_folder(self) -> str:
        """Get the error folder from configuration."""
        return self.settings.get('error_folder', 'error')

    @property
    def log_directory(self) -> str:
        """Get the log directory from configuration."""
        return self.settings.get('log_directory', './logs')

    @property
    def watcher_interval(self) -> int:
        """Get the watcher interval from configuration."""
        return self.settings.get('watcher_interval', 5)