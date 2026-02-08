"""
Audit Logger

Provides hash chain audit logging with tamper-evident integrity.
Supports daily log rotation and 90-day retention policy.

Supports Gold Tier requirements:
- FR-024: Log all MCP actions with tamper-evident hashes
- FR-025: Maintain hash chain integrity across entries
- FR-026: Support audit log export for date ranges
- FR-027: Log external API calls with request/response summaries
- FR-027a: Retain audit logs in active storage for 90 days
- FR-027b: Archive logs older than 90 days to cold storage
"""

import os
import json
import gzip
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from threading import Lock

from models.audit_entry import AuditEntry, ActorType, ActionResult


class AuditLoggerError(Exception):
    """Base exception for audit logger errors."""
    pass


class ChainIntegrityError(AuditLoggerError):
    """Raised when hash chain integrity check fails."""
    pass


class AuditLogger:
    """
    Hash chain audit logger with tamper-evident integrity.

    Maintains a chain of audit entries where each entry's hash
    includes the previous entry's hash, creating an immutable
    audit trail that can be verified for tampering.

    Per FR-024-027: Comprehensive audit logging with hash chain
    Per FR-027a/b: 90 days active, then archive
    """

    ACTIVE_RETENTION_DAYS = 90

    def __init__(self, vault_path: Optional[str] = None):
        """
        Initialize audit logger.

        Args:
            vault_path: Path to vault directory. Defaults to VAULT_PATH env var.
        """
        self.vault_path = vault_path or os.environ.get("VAULT_PATH", "./obsidian-vault")
        self._lock = Lock()
        self._last_hash: Optional[str] = None
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure audit directories exist."""
        active_dir = Path(self.vault_path) / "audit" / "active"
        archive_dir = Path(self.vault_path) / "audit" / "archive"
        active_dir.mkdir(parents=True, exist_ok=True)
        archive_dir.mkdir(parents=True, exist_ok=True)

    def _get_active_log_path(self, date: Optional[datetime] = None) -> Path:
        """Get path to active log file for a date."""
        if date is None:
            date = datetime.utcnow()
        filename = f"{date.strftime('%Y-%m-%d')}.jsonl"
        return Path(self.vault_path) / "audit" / "active" / filename

    def _get_archive_path(self, year_month: str) -> Path:
        """Get path to archive file for a year-month."""
        filename = f"{year_month}.jsonl.gz"
        return Path(self.vault_path) / "audit" / "archive" / filename

    def _get_last_hash(self, date: Optional[datetime] = None) -> str:
        """Get hash of the last entry in the chain."""
        if self._last_hash:
            return self._last_hash

        log_path = self._get_active_log_path(date)
        if not log_path.exists():
            return "GENESIS"

        # Read the last line
        with open(log_path, "r") as f:
            last_line = None
            for line in f:
                if line.strip():
                    last_line = line

        if last_line:
            entry_data = json.loads(last_line)
            return entry_data.get("hash", "GENESIS")

        return "GENESIS"

    def append(
        self,
        action_type: str,
        actor: ActorType,
        server_id: str,
        details: Dict[str, Any],
        result: ActionResult,
        approval_ref: Optional[str] = None,
        error_message: Optional[str] = None,
        latency_ms: Optional[int] = None,
    ) -> AuditEntry:
        """
        Append a new entry to the audit log.

        Args:
            action_type: Type of action (e.g., "xero.invoice.create")
            actor: Who performed the action
            server_id: MCP server that processed the action
            details: Action-specific details (will be scrubbed for credentials)
            result: Outcome of the action
            approval_ref: Reference to approval file if applicable
            error_message: Error details if failed
            latency_ms: API call latency if applicable

        Returns:
            The created AuditEntry
        """
        with self._lock:
            # Scrub credentials from details
            scrubbed_details = AuditEntry.scrub_credentials(details)

            # Get previous hash
            prev_hash = self._get_last_hash()

            # Create entry
            entry = AuditEntry(
                action_type=action_type,
                actor=actor,
                server_id=server_id,
                approval_ref=approval_ref,
                details=scrubbed_details,
                result=result,
                error_message=error_message,
                latency_ms=latency_ms,
                prev_hash=prev_hash,
            )

            # Write to log
            log_path = self._get_active_log_path()
            with open(log_path, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

            # Update cached last hash
            self._last_hash = entry.hash

            return entry

    def verify_chain(self, date: Optional[datetime] = None) -> bool:
        """
        Verify hash chain integrity for a log file.

        Args:
            date: Date of log to verify. Defaults to today.

        Returns:
            True if chain is valid, raises ChainIntegrityError otherwise
        """
        log_path = self._get_active_log_path(date)
        if not log_path.exists():
            return True  # Empty log is valid

        prev_hash = "GENESIS"

        with open(log_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue

                try:
                    entry_data = json.loads(line)
                    entry = AuditEntry.from_dict(entry_data)

                    # Verify entry's prev_hash matches
                    if entry.prev_hash != prev_hash:
                        raise ChainIntegrityError(
                            f"Chain broken at line {line_num}: "
                            f"expected prev_hash {prev_hash}, got {entry.prev_hash}"
                        )

                    # Verify entry's own hash
                    if not entry.verify_hash():
                        raise ChainIntegrityError(
                            f"Hash mismatch at line {line_num}: entry ID {entry.id}"
                        )

                    prev_hash = entry.hash

                except json.JSONDecodeError as e:
                    raise ChainIntegrityError(f"Invalid JSON at line {line_num}: {e}")

        return True

    def export(
        self,
        start_date: datetime,
        end_date: datetime,
        action_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Export audit entries for a date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            action_types: Optional filter for specific action types

        Returns:
            List of audit entry dictionaries
        """
        entries = []
        current = start_date

        while current <= end_date:
            log_path = self._get_active_log_path(current)

            if log_path.exists():
                with open(log_path, "r") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        entry_data = json.loads(line)

                        # Filter by action type if specified
                        if action_types:
                            if entry_data.get("action_type") not in action_types:
                                continue

                        entries.append(entry_data)

            current += timedelta(days=1)

        return entries

    def archive_old_logs(self) -> int:
        """
        Archive logs older than retention period.

        Per FR-027a/b: Move logs > 90 days to cold storage.

        Returns:
            Number of files archived
        """
        active_dir = Path(self.vault_path) / "audit" / "active"
        cutoff = datetime.utcnow() - timedelta(days=self.ACTIVE_RETENTION_DAYS)
        archived_count = 0

        # Group files by year-month for archiving
        files_by_month: Dict[str, List[Path]] = {}

        for log_file in active_dir.glob("*.jsonl"):
            try:
                # Parse date from filename
                date_str = log_file.stem
                file_date = datetime.strptime(date_str, "%Y-%m-%d")

                if file_date < cutoff:
                    year_month = file_date.strftime("%Y-%m")
                    if year_month not in files_by_month:
                        files_by_month[year_month] = []
                    files_by_month[year_month].append(log_file)

            except ValueError:
                continue

        # Archive each month
        for year_month, files in files_by_month.items():
            archive_path = self._get_archive_path(year_month)

            # Combine all entries for the month
            all_entries = []
            for log_file in sorted(files):
                with open(log_file, "r") as f:
                    for line in f:
                        if line.strip():
                            all_entries.append(line)

            # Write compressed archive
            with gzip.open(archive_path, "at") as f:
                for entry in all_entries:
                    f.write(entry)

            # Delete original files
            for log_file in files:
                log_file.unlink()
                archived_count += 1

        return archived_count

    def get_stats(self) -> Dict[str, Any]:
        """Get audit log statistics."""
        active_dir = Path(self.vault_path) / "audit" / "active"
        archive_dir = Path(self.vault_path) / "audit" / "archive"

        active_files = list(active_dir.glob("*.jsonl"))
        archive_files = list(archive_dir.glob("*.jsonl.gz"))

        # Count entries in today's log
        today_path = self._get_active_log_path()
        today_entries = 0
        if today_path.exists():
            with open(today_path, "r") as f:
                today_entries = sum(1 for line in f if line.strip())

        return {
            "active_log_files": len(active_files),
            "archive_files": len(archive_files),
            "entries_today": today_entries,
            "retention_days": self.ACTIVE_RETENTION_DAYS,
        }
