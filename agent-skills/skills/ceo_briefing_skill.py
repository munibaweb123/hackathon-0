"""
CEO Briefing Skill

Agent skill for generating weekly CEO briefings with aggregated business intelligence.
Collects data from Xero, pending approvals, and social metrics (when available).

Supports Gold Tier requirements:
- FR-012 to FR-016: CEO Briefing generation
- FR-037: CEOBriefingSkill implementation
"""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.base_skill import BaseSkill, SkillResult
from models.ceo_briefing import CEOBriefing, BriefingStatus


class CEOBriefingSkill(BaseSkill):
    """
    CEO briefing generation skill.

    Provides:
    - Weekly briefing generation with financial data
    - AI insight generation based on variance detection
    - Markdown output for vault storage
    - Graceful handling of unavailable data sources

    Per FR-012-016: Generate weekly CEO briefings.
    """

    def __init__(
        self,
        vault_interface=None,
        logger=None,
        financial_mcp_url: str = None,
        social_mcp_url: str = None,
    ):
        """
        Initialize CEOBriefingSkill.

        Args:
            vault_interface: Interface for vault operations
            logger: Logger for auditability
            financial_mcp_url: URL of Financial MCP server
            social_mcp_url: URL of Social MCP server
        """
        super().__init__("CEOBriefingSkill", vault_interface, logger)
        self.financial_mcp_url = financial_mcp_url or os.getenv(
            "FINANCIAL_MCP_URL", "http://localhost:8001"
        )
        self.social_mcp_url = social_mcp_url or os.getenv(
            "SOCIAL_MCP_URL", "http://localhost:8002"
        )
        self.vault_path = os.getenv("VAULT_PATH", "./obsidian-vault")

    @property
    def id(self) -> str:
        return "ceo_briefing"

    @property
    def description(self) -> str:
        return "Generate weekly CEO briefings with financial and operational intelligence"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["generate", "list", "get", "get_latest"],
                    "description": "Operation to perform",
                },
                "week_start": {
                    "type": "string",
                    "description": "Monday date for the briefing (YYYY-MM-DD)",
                },
                "briefing_id": {
                    "type": "string",
                    "description": "Briefing ID for get operation",
                },
            },
            "required": ["operation"],
        }

    @property
    def output_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "briefing": {"type": "object"},
                "file_path": {"type": "string"},
                "error": {"type": "string"},
            },
        }

    async def execute(self, input_data: Dict[str, Any]) -> SkillResult:
        """
        Execute a CEO briefing operation.

        Args:
            input_data: Operation details

        Returns:
            SkillResult with operation outcome
        """
        start_time = time.time()

        try:
            operation = input_data.get("operation")

            if operation == "generate":
                week_start = input_data.get("week_start") or self._get_current_week_monday()
                result = await self._generate_briefing(week_start)
            elif operation == "list":
                result = await self._list_briefings()
            elif operation == "get":
                briefing_id = input_data.get("briefing_id")
                if not briefing_id:
                    return SkillResult(success=False, error="briefing_id required for get operation")
                result = await self._get_briefing(briefing_id)
            elif operation == "get_latest":
                result = await self._get_latest_briefing()
            else:
                return SkillResult(success=False, error=f"Unknown operation: {operation}")

            execution_time = (time.time() - start_time) * 1000
            return SkillResult(
                success=True,
                data=result,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return SkillResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
            )

    def _get_current_week_monday(self) -> str:
        """Get the Monday of the current week."""
        today = datetime.utcnow().date()
        monday = today - timedelta(days=today.weekday())
        return monday.isoformat()

    async def _make_request(self, url: str, method: str = "GET", params: dict = None) -> Optional[dict]:
        """Make HTTP request to MCP server."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if method == "GET":
                    response = await client.get(url, params=params)
                else:
                    response = await client.post(url, json=params)

                if response.status_code == 200:
                    return response.json()
                return None
        except Exception:
            return None

    async def _fetch_financial_data(self, week_start: str) -> Optional[Dict[str, Any]]:
        """
        Fetch financial summary from Xero.

        Per FR-074: Handle unavailable sources gracefully.
        """
        try:
            # Calculate period end (7 days from week start)
            start_date = datetime.fromisoformat(week_start)
            end_date = start_date + timedelta(days=6)

            url = f"{self.financial_mcp_url}/xero/summary"
            params = {
                "periodStart": week_start,
                "periodEnd": end_date.date().isoformat(),
            }

            return await self._make_request(url, params=params)
        except Exception:
            return None

    async def _fetch_pending_approvals(self) -> List[Dict[str, Any]]:
        """Fetch pending approval requests from vault."""
        pending = []
        try:
            pending_dir = Path(self.vault_path) / "Pending-Approval"
            if pending_dir.exists():
                import yaml
                for file in pending_dir.glob("*.md"):
                    try:
                        content = file.read_text()
                        if content.startswith("---"):
                            front_matter = content.split("---")[1]
                            data = yaml.safe_load(front_matter)
                            pending.append({
                                "id": file.stem,
                                "type": data.get("type", "unknown"),
                                "summary": data.get("title", file.stem),
                                "created_at": data.get("created_at"),
                            })
                    except Exception:
                        continue
        except Exception:
            pass
        return pending

    async def _fetch_social_metrics(self) -> Optional[Dict[str, Any]]:
        """
        Fetch social media metrics (when available).

        Returns None if social MCP is not available.
        """
        # Social metrics will be implemented in Phase 5 (US3)
        # For now, return None to indicate data unavailable
        return None

    def _generate_ai_insights(
        self,
        financial_data: Optional[Dict[str, Any]],
        pending_actions: List[Dict[str, Any]],
    ) -> str:
        """
        Generate AI insights based on collected data.

        Per FR-014: Include AI-generated recommendations.
        """
        insights = []

        # Analyze financial data for variance alerts
        if financial_data:
            alerts = financial_data.get("varianceAlerts", [])
            for alert in alerts:
                metric = alert.get("metric", "metric")
                change = alert.get("changePct", 0)
                direction = alert.get("direction", "up")

                if abs(change) >= 20:
                    if direction == "up":
                        insights.append(
                            f"Significant increase in {metric} ({change:+.1f}%). "
                            "Consider investigating the drivers behind this growth."
                        )
                    else:
                        insights.append(
                            f"Notable decrease in {metric} ({change:-.1f}%). "
                            "Review recent activities that may have contributed."
                        )

            # Check for overdue invoices
            invoices = financial_data.get("outstandingInvoices", [])
            overdue = [
                inv for inv in invoices
                if inv.get("dueDate") and inv["dueDate"] < datetime.utcnow().date().isoformat()
            ]
            if overdue:
                total_overdue = sum(inv.get("amount", 0) for inv in overdue)
                insights.append(
                    f"There are {len(overdue)} overdue invoices totaling ${total_overdue:,.2f}. "
                    "Consider following up with these clients."
                )

        # Pending approvals insight
        if len(pending_actions) > 5:
            insights.append(
                f"There are {len(pending_actions)} pending approval requests. "
                "Consider reviewing the approval queue to prevent bottlenecks."
            )

        if not insights:
            insights.append(
                "No significant variances or concerns detected this week. "
                "Operations appear stable."
            )

        return "\n\n".join(insights)

    async def _generate_briefing(self, week_start: str) -> Dict[str, Any]:
        """
        Generate a CEO briefing for the specified week.

        Per FR-012: Generate weekly CEO briefing automatically.
        Per FR-074: Mark unavailable data with [DATA UNAVAILABLE].
        """
        briefing = CEOBriefing(week_start=week_start)
        unavailable_sources = []

        # Fetch financial data
        financial_data = await self._fetch_financial_data(week_start)
        if financial_data:
            briefing.financial_data = financial_data
            briefing.data_sources["xero"] = "available"
        else:
            briefing.data_sources["xero"] = "unavailable"
            unavailable_sources.append("xero")

        # Fetch pending approvals
        pending_actions = await self._fetch_pending_approvals()
        briefing.pending_actions = pending_actions
        briefing.data_sources["approvals"] = "available"

        # Fetch social metrics (Phase 5)
        social_metrics = await self._fetch_social_metrics()
        if social_metrics:
            briefing.social_metrics = social_metrics
            briefing.data_sources["social"] = "available"
        else:
            briefing.data_sources["social"] = "unavailable"
            unavailable_sources.append("social")

        # Generate AI insights
        briefing.ai_insights = self._generate_ai_insights(financial_data, pending_actions)

        # Determine final status
        if unavailable_sources:
            briefing.mark_partial(unavailable_sources)
        else:
            briefing.mark_complete()

        # Save to vault
        file_path = self._save_briefing_to_vault(briefing)
        briefing.file_path = file_path

        return {
            "briefing": briefing.to_dict(),
            "file_path": file_path,
            "status": briefing.status.value,
            "unavailable_sources": unavailable_sources,
        }

    def _save_briefing_to_vault(self, briefing: CEOBriefing) -> str:
        """
        Save briefing to vault as Markdown file.

        Per FR-016: CEO briefing stored in vault/briefings/{year}/week-{num}.md
        """
        week_date = datetime.fromisoformat(briefing.week_start)
        year = week_date.year
        week_num = week_date.isocalendar()[1]

        briefings_dir = Path(self.vault_path) / "briefings" / str(year)
        briefings_dir.mkdir(parents=True, exist_ok=True)

        file_name = f"week-{week_num:02d}.md"
        file_path = briefings_dir / file_name

        markdown_content = briefing.to_markdown()
        file_path.write_text(markdown_content)

        return str(file_path)

    async def _list_briefings(self) -> Dict[str, Any]:
        """List all generated briefings."""
        briefings = []
        briefings_root = Path(self.vault_path) / "briefings"

        if briefings_root.exists():
            import yaml
            for year_dir in sorted(briefings_root.iterdir(), reverse=True):
                if year_dir.is_dir():
                    for file in sorted(year_dir.glob("week-*.md"), reverse=True):
                        try:
                            content = file.read_text()
                            if content.startswith("---"):
                                front_matter = content.split("---")[1]
                                data = yaml.safe_load(front_matter)
                                briefings.append({
                                    "id": data.get("id"),
                                    "week_start": data.get("week_start"),
                                    "generated_at": data.get("generated_at"),
                                    "status": data.get("status"),
                                    "file_path": str(file),
                                })
                        except Exception:
                            continue

        return {"briefings": briefings, "count": len(briefings)}

    async def _get_briefing(self, briefing_id: str) -> Dict[str, Any]:
        """Get a specific briefing by ID."""
        result = await self._list_briefings()
        for briefing in result.get("briefings", []):
            if briefing.get("id") == briefing_id:
                # Load full content
                file_path = briefing.get("file_path")
                if file_path:
                    content = Path(file_path).read_text()
                    briefing["content"] = content
                return {"briefing": briefing}

        return {"error": f"Briefing not found: {briefing_id}"}

    async def _get_latest_briefing(self) -> Dict[str, Any]:
        """Get the most recent briefing."""
        result = await self._list_briefings()
        briefings = result.get("briefings", [])

        if briefings:
            latest = briefings[0]
            file_path = latest.get("file_path")
            if file_path:
                latest["content"] = Path(file_path).read_text()
            return {"briefing": latest}

        return {"error": "No briefings found"}
