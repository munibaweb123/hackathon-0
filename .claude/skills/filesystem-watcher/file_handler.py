"""
File Handler Module

Provides file type detection, safe copying to the vault's Attachments/
folder, duplicate filename handling, and source cleanup.

Uses only Python stdlib — no external dependencies.
"""

import logging
import mimetypes
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("watcher.filesystem.handler")

# Ensure common office types are registered
mimetypes.add_type("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx")
mimetypes.add_type("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx")
mimetypes.add_type("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx")
mimetypes.add_type("application/vnd.ms-excel", ".xls")
mimetypes.add_type("application/msword", ".doc")

# Files to always ignore
_IGNORED_EXTENSIONS = {".tmp", ".swp", ".swo", ".part", ".crdownload", ".lock"}
_IGNORED_PREFIXES = (".", "~", "__")


def _human_size(size_bytes: int) -> str:
    """Convert bytes to a human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} TB"


class FileHandler:
    """
    Handles file validation, MIME detection, copying, and cleanup
    for the filesystem watcher skill.
    """

    def __init__(self, vault_path: str, max_size_mb: int = 100):
        self.vault_path = Path(vault_path)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.attachments_dir = self.vault_path / "Attachments"
        self.attachments_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def is_valid_file(self, path: Path) -> bool:
        """
        Check whether *path* should be processed.

        Rejects:
        - Directories
        - Hidden files (start with .)
        - Temp / partial download files
        - Zero-byte files
        - Files exceeding the size limit
        """
        if not path.is_file():
            return False

        name = path.name

        # Hidden or temp prefix
        if any(name.startswith(p) for p in _IGNORED_PREFIXES):
            logger.debug("Skipping hidden/temp file: %s", name)
            return False

        # Temp extension
        if path.suffix.lower() in _IGNORED_EXTENSIONS:
            logger.debug("Skipping temp extension: %s", name)
            return False

        # Zero-byte
        try:
            size = path.stat().st_size
        except OSError:
            return False

        if size == 0:
            logger.debug("Skipping zero-byte file: %s", name)
            return False

        # Size limit
        if size > self.max_size_bytes:
            logger.warning(
                "File too large (%s): %s (limit: %d MB)",
                _human_size(size), name, self.max_size_bytes // (1024 * 1024),
            )
            return False

        return True

    # ------------------------------------------------------------------
    # MIME detection
    # ------------------------------------------------------------------

    @staticmethod
    def detect_mime_type(path: Path) -> str:
        """
        Guess the MIME type from the file extension.

        Falls back to ``application/octet-stream`` for unknown types.
        """
        mime, _ = mimetypes.guess_type(str(path))
        return mime or "application/octet-stream"

    # ------------------------------------------------------------------
    # File info
    # ------------------------------------------------------------------

    def get_file_info(self, path: Path) -> Dict[str, Any]:
        """Return a metadata dict describing the file."""
        stat = path.stat()
        return {
            "original_name": path.name,
            "extension": path.suffix.lower(),
            "size_bytes": stat.st_size,
            "size_human": _human_size(stat.st_size),
            "mime_type": self.detect_mime_type(path),
            "created_at": datetime.fromtimestamp(
                stat.st_ctime, tz=timezone.utc
            ).isoformat(),
        }

    # ------------------------------------------------------------------
    # Copy to Attachments
    # ------------------------------------------------------------------

    def copy_to_attachments(self, source: Path) -> Optional[Path]:
        """
        Copy *source* into ``vault_path/Attachments/``.

        If a file with the same name already exists, appends ``_1``,
        ``_2``, etc. until a unique name is found.

        Returns:
            Destination path, or None on failure.
        """
        dest = self.attachments_dir / source.name

        # Handle duplicates
        if dest.exists():
            stem = source.stem
            suffix = source.suffix
            counter = 1
            while dest.exists():
                dest = self.attachments_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        try:
            shutil.copy2(str(source), str(dest))
            logger.info("Copied %s → %s", source.name, dest)
            return dest
        except OSError as exc:
            logger.error("Failed to copy %s: %s", source.name, exc)
            return None

    # ------------------------------------------------------------------
    # Source cleanup
    # ------------------------------------------------------------------

    @staticmethod
    def cleanup_source(path: Path) -> bool:
        """Delete the original file from the drop folder."""
        try:
            path.unlink()
            logger.info("Cleaned up source: %s", path.name)
            return True
        except OSError as exc:
            logger.warning("Could not delete source %s: %s", path.name, exc)
            return False
