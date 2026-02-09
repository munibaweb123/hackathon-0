"""
Audit Skill

Extends BaseSkill to provide audit log operations:
export, verify chain integrity, and archive rotation.

Supports Gold Tier requirements:
- FR-024: Log all MCP actions with tamper-evident hashes
- FR-025: Maintain hash chain integrity across entries
- FR-026: Support audit log export for date ranges
- FR-027a/b: 90-day active retention, then archive
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from core.base_skill import BaseSkill, SkillResult
from core.audit_logger import AuditLogger, ChainIntegrityError


class AuditSkill(BaseSkill):
    """
    Skill for audit log management operations.

    Provides export, verification, and archival of the
    tamper-evident hash chain audit log.
    """

    def __init__(self, vault_path: Optional[str] = None):
        self._id = "audit"
        self._name = "Audit Log Manager"
        self._description = "Export, verify, and archive tamper-evident audit logs"
        self._version = "1.0.0"
        self._enabled = True
        self._dependencies = []
        self._audit_logger = AuditLogger(vault_path=vault_path)

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def version(self) -> str:
        return self._version

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def dependencies(self) -> list:
        return self._dependencies

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "enabled": self.enabled,
        }

    async def execute_async(self, input_data: Dict[str, Any]) -> SkillResult:
        """
        Execute an audit operation.

        Supported operations:
        - export: Export audit entries for a date range
        - verify: Verify hash chain integrity
        - archive: Archive old logs
        - stats: Get audit statistics

        Args:
            input_data: {
                "operation": "export|verify|archive|stats",
                "start_date": "YYYY-MM-DD" (for export),
                "end_date": "YYYY-MM-DD" (for export),
                "action_types": ["type1"] (optional filter for export),
                "date": "YYYY-MM-DD" (for verify, defaults to today)
            }

        Returns:
            SkillResult with operation results
        """
        operation = input_data.get("operation", "stats")

        try:
            if operation == "export":
                return await self._export(input_data)
            elif operation == "verify":
                return await self._verify(input_data)
            elif operation == "archive":
                return await self._archive()
            elif operation == "stats":
                return self._stats()
            else:
                return SkillResult(
                    success=False,
                    data={"error": f"Unknown operation: {operation}"},
                )
        except Exception as e:
            return SkillResult(
                success=False,
                data={"error": str(e)},
            )

    async def _export(self, input_data: Dict[str, Any]) -> SkillResult:
        """Export audit entries for a date range."""
        start_str = input_data.get("start_date")
        end_str = input_data.get("end_date")

        if not start_str or not end_str:
            return SkillResult(
                success=False,
                data={"error": "start_date and end_date required for export"},
            )

        start_date = datetime.strptime(start_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_str, "%Y-%m-%d")
        action_types = input_data.get("action_types")

        entries = self._audit_logger.export(
            start_date=start_date,
            end_date=end_date,
            action_types=action_types,
        )

        return SkillResult(
            success=True,
            data={
                "entries": entries,
                "count": len(entries),
                "start_date": start_str,
                "end_date": end_str,
            },
        )

    async def _verify(self, input_data: Dict[str, Any]) -> SkillResult:
        """Verify hash chain integrity."""
        date_str = input_data.get("date")
        date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else None

        try:
            valid = self._audit_logger.verify_chain(date=date)
            return SkillResult(
                success=True,
                data={
                    "valid": valid,
                    "date": date_str or datetime.utcnow().strftime("%Y-%m-%d"),
                    "message": "Hash chain integrity verified",
                },
            )
        except ChainIntegrityError as e:
            return SkillResult(
                success=False,
                data={
                    "valid": False,
                    "date": date_str or datetime.utcnow().strftime("%Y-%m-%d"),
                    "error": str(e),
                },
            )

    async def _archive(self) -> SkillResult:
        """Archive old audit logs."""
        archived_count = self._audit_logger.archive_old_logs()

        return SkillResult(
            success=True,
            data={
                "archived_files": archived_count,
                "retention_days": AuditLogger.ACTIVE_RETENTION_DAYS,
                "message": f"Archived {archived_count} log files",
            },
        )

    def _stats(self) -> SkillResult:
        """Get audit log statistics."""
        stats = self._audit_logger.get_stats()

        return SkillResult(
            success=True,
            data=stats,
        )
