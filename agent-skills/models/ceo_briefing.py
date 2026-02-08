"""
CEO Briefing Model

Generated weekly briefing document with aggregated business intelligence.
Per data-model.md specification.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class BriefingStatus(str, Enum):
    """Status of CEO briefing generation."""
    GENERATING = "generating"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass
class CEOBriefing:
    """
    Weekly CEO briefing with aggregated business intelligence.

    Status transitions:
        generating -> complete | partial | failed
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    week_start: str = ""  # Monday of the briefing week (YYYY-MM-DD)
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    financial_data: Optional[Dict[str, Any]] = None
    social_metrics: Optional[Dict[str, Any]] = None
    pending_actions: List[Dict[str, Any]] = field(default_factory=list)
    ai_insights: Optional[str] = None
    data_sources: Dict[str, str] = field(default_factory=dict)
    status: BriefingStatus = BriefingStatus.GENERATING
    file_path: Optional[str] = None

    def mark_complete(self) -> None:
        """Mark briefing as complete."""
        self.status = BriefingStatus.COMPLETE

    def mark_partial(self, unavailable_sources: List[str]) -> None:
        """Mark briefing as partial due to unavailable sources."""
        self.status = BriefingStatus.PARTIAL
        for source in unavailable_sources:
            self.data_sources[source] = "unavailable"

    def mark_failed(self, reason: str) -> None:
        """Mark briefing as failed."""
        self.status = BriefingStatus.FAILED
        self.ai_insights = f"[GENERATION FAILED] {reason}"

    def has_financial_data(self) -> bool:
        """Check if financial data is available."""
        return self.financial_data is not None and bool(self.financial_data)

    def has_social_metrics(self) -> bool:
        """Check if social metrics are available."""
        return self.social_metrics is not None and bool(self.social_metrics)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "week_start": self.week_start,
            "generated_at": self.generated_at,
            "financial_data": self.financial_data,
            "social_metrics": self.social_metrics,
            "pending_actions": self.pending_actions,
            "ai_insights": self.ai_insights,
            "data_sources": self.data_sources,
            "status": self.status.value,
            "file_path": self.file_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CEOBriefing":
        """Create from dictionary."""
        status = data.get("status", "generating")
        if isinstance(status, str):
            status = BriefingStatus(status)
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            week_start=data.get("week_start", ""),
            generated_at=data.get("generated_at", datetime.utcnow().isoformat()),
            financial_data=data.get("financial_data"),
            social_metrics=data.get("social_metrics"),
            pending_actions=data.get("pending_actions", []),
            ai_insights=data.get("ai_insights"),
            data_sources=data.get("data_sources", {}),
            status=status,
            file_path=data.get("file_path"),
        )

    def to_markdown(self) -> str:
        """Render briefing as Markdown for vault storage."""
        lines = [
            "---",
            f"id: {self.id}",
            f"type: ceo_briefing",
            f"week_start: {self.week_start}",
            f"generated_at: {self.generated_at}",
            f"status: {self.status.value}",
            "---",
            "",
            f"# CEO Weekly Briefing - Week of {self.week_start}",
            "",
        ]

        # Financial section
        lines.append("## Financial Summary")
        if self.has_financial_data():
            fd = self.financial_data
            lines.append(f"- **Revenue**: ${fd.get('revenue', 0):,.2f}")
            lines.append(f"- **Expenses**: ${fd.get('expenses', 0):,.2f}")
            lines.append(f"- **Cash Flow**: ${fd.get('cashFlow', fd.get('cash_flow', 0)):,.2f}")

            invoices = fd.get("outstandingInvoices", fd.get("outstanding_invoices", []))
            if invoices:
                lines.append("")
                lines.append("### Outstanding Invoices")
                for inv in invoices:
                    contact = inv.get("contactName", inv.get("contact", "Unknown"))
                    amount = inv.get("amount", 0)
                    due = inv.get("dueDate", inv.get("due_date", "N/A"))
                    lines.append(f"- {contact}: ${amount:,.2f} (due {due})")

            alerts = fd.get("varianceAlerts", fd.get("variance_alerts", []))
            if alerts:
                lines.append("")
                lines.append("### Variance Alerts")
                for alert in alerts:
                    metric = alert.get("metric", "unknown")
                    change = alert.get("changePct", alert.get("change_pct", 0))
                    direction = alert.get("direction", "up")
                    emoji = "+" if direction == "up" else "-"
                    lines.append(f"- {metric}: {emoji}{abs(change):.1f}%")
        else:
            lines.append("[DATA UNAVAILABLE] Xero connection not active")

        lines.append("")

        # Social section
        lines.append("## Social Media Metrics")
        if self.has_social_metrics():
            for platform, metrics in self.social_metrics.items():
                if isinstance(metrics, dict):
                    lines.append(f"### {platform.title()}")
                    for k, v in metrics.items():
                        lines.append(f"- **{k}**: {v}")
                    lines.append("")
        else:
            lines.append("[DATA UNAVAILABLE] Social accounts not connected")

        lines.append("")

        # Pending actions
        lines.append("## Pending Actions")
        if self.pending_actions:
            for action in self.pending_actions:
                desc = action.get("description", "Unknown action")
                risk = action.get("risk_level", "medium")
                lines.append(f"- [{risk.upper()}] {desc}")
        else:
            lines.append("No pending actions.")

        lines.append("")

        # AI insights
        lines.append("## AI Insights & Recommendations")
        if self.ai_insights:
            lines.append(self.ai_insights)
        else:
            lines.append("No insights generated.")

        lines.append("")
        lines.append(f"---\n*Generated at {self.generated_at}*")

        return "\n".join(lines)
