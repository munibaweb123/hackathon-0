"""File monitoring system using python-watchdog."""

import os
import time
from pathlib import Path
from typing import Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class VaultEventHandler(FileSystemEventHandler):
    """Handles file system events in the vault."""

    def __init__(self, callback: Optional[Callable] = None):
        super().__init__()
        self.callback = callback

    def on_created(self, event):
        if not event.is_directory:
            if self.callback:
                self.callback(event.src_path, 'created')

    def on_modified(self, event):
        if not event.is_directory:
            if self.callback:
                self.callback(event.src_path, 'modified')


class FileMonitor:
    """Monitors file system changes in the vault."""

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.observer = Observer()
        self.event_handler = VaultEventHandler()
        self.callbacks = []

    def add_callback(self, callback: Callable[[str, str], None]):
        """Add a callback to be called when a file event occurs."""
        self.event_handler.callback = callback

    def start_monitoring(self):
        """Start monitoring the vault directory."""
        self.observer.schedule(
            self.event_handler,
            str(self.vault_path),
            recursive=True
        )
        self.observer.start()
        print(f"Started monitoring vault at {self.vault_path}")

    def stop_monitoring(self):
        """Stop monitoring the vault directory."""
        self.observer.stop()
        self.observer.join()
        print("Stopped monitoring vault")


def path_is_safe(file_path: str, allowed_base_path: str) -> bool:
    """Validate that the file path is within the allowed base path."""
    try:
        # Resolve the paths to absolute paths
        file_abs = Path(file_path).resolve()
        base_abs = Path(allowed_base_path).resolve()

        # Check if the file path is within the base path
        file_abs.relative_to(base_abs)
        return True
    except ValueError:
        # If the file path is not within the base path, relative_to raises ValueError
        return False