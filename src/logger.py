"""Logging system for the Personal AI Employee."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from .entities import LogEntryEntity


class Logger:
    """Basic logging system with configurable levels."""

    def __init__(self, log_directory: str = "./logs"):
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(exist_ok=True)

    def _write_log_entry(self, entry: LogEntryEntity):
        """Write a log entry to the appropriate log file."""
        # Create filename based on date
        date_str = entry.timestamp.strftime("%Y-%m-%d")
        log_file = self.log_directory / f"log_{date_str}.log"

        # Format the log entry as JSON
        log_dict = {
            "id": entry.id,
            "timestamp": entry.timestamp.isoformat(),
            "level": entry.level,
            "actor": entry.actor,
            "action": entry.action,
            "details": entry.details,
            "file_ref": entry.file_ref,
            "operation_ref": entry.operation_ref
        }

        # Write to log file
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_dict) + "\n")

    def log(self, level: str, actor: str, action: str, details: str,
            file_ref: str = None, operation_ref: str = None):
        """Log an event with the specified parameters."""
        entry = LogEntryEntity(
            level=level,
            actor=actor,
            action=action,
            details=details,
            file_ref=file_ref,
            operation_ref=operation_ref
        )
        self._write_log_entry(entry)

    def info(self, actor: str, action: str, details: str = "",
             file_ref: str = None, operation_ref: str = None):
        """Log an info level event."""
        self.log("info", actor, action, details, file_ref, operation_ref)

    def warn(self, actor: str, action: str, details: str = "",
             file_ref: str = None, operation_ref: str = None):
        """Log a warning level event."""
        self.log("warn", actor, action, details, file_ref, operation_ref)

    def error(self, actor: str, action: str, details: str = "",
              file_ref: str = None, operation_ref: str = None):
        """Log an error level event."""
        self.log("error", actor, action, details, file_ref, operation_ref)

    def audit(self, actor: str, action: str, details: str = "",
              file_ref: str = None, operation_ref: str = None):
        """Log an audit level event."""
        self.log("audit", actor, action, details, file_ref, operation_ref)