# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "jinja2>=3.1.0",
#     "python-dotenv>=1.0.0",
#     "pyyaml>=6.0",
# ]
# ///
"""
CEO Briefing Generator — creates comprehensive Monday morning business
reports by reading the Obsidian vault directly.  Zero API dependencies.

Usage with UV (recommended):
    uv run briefing_generator.py --vault-path ../../obsidian-vault --once

Usage with pip:
    pip install -r requirements.txt
    python briefing_generator.py --vault-path ../../obsidian-vault --once
"""

import argparse
import json
import logging
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure local imports work when run via UV
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv  # noqa: E402
from jinja2 import Environment, FileSystemLoader  # noqa: E402

from analyzers import RevenueAnalyzer, SubscriptionAnalyzer, TaskAnalyzer  # noqa: E402

logger = logging.getLogger("ceo-briefing")


class BriefingGenerator:
    """Generates comprehensive CEO Monday morning briefings from vault data."""

    def __init__(self, vault_path: str) -> None:
        self.vault = Path(vault_path).resolve()
        self.revenue_analyzer = RevenueAnalyzer(str(self.vault))
        self.task_analyzer = TaskAnalyzer(str(self.vault))
        self.subscription_analyzer = SubscriptionAnalyzer(str(self.vault))

        # Jinja2 environment — templates/ directory next to this script
        template_dir = Path(__file__).resolve().parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, week_start: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a full CEO briefing.

        Args:
            week_start: Monday date as YYYY-MM-DD. Defaults to this week's Monday.

        Returns:
            Dict with all analysis data, rendered markdown, and output path.
        """
        ws, we = self._determine_week_range(week_start)
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        logger.info("Generating briefing for week %s to %s", ws, we)

        # Run all analyzers
        revenue = self.revenue_analyzer.analyze(ws, we)
        tasks = self.task_analyzer.analyze(ws, we)
        subscriptions = self.subscription_analyzer.analyze(ws, we)
        goals = self._load_business_goals()

        # Pending items (from task analyzer data)
        pending_items = self._build_pending_items(tasks)

        # Generate recommendations
        recommendations = self._generate_recommendations(revenue, tasks, subscriptions)

        # Executive summary
        executive_summary = self._generate_executive_summary(revenue, tasks, subscriptions)

        # Determine status
        status = "complete"
        if revenue["revenue_this_week"] == 0 and tasks["tasks_completed_this_week"] == 0:
            status = "partial"

        # Template data
        data = {
            "week_start": ws.isoformat(),
            "generated_at": generated_at,
            "status": status,
            "executive_summary": executive_summary,
            "revenue": revenue,
            "tasks": tasks,
            "subscriptions": subscriptions,
            "pending_items": pending_items,
            "recommendations": recommendations,
            "goals": goals,
        }

        # Render
        rendered = self._render_briefing(data)

        # Save
        output_path = self._save_briefing(rendered, ws)

        # Log generation
        self._log_generation(ws, status, output_path)

        logger.info("Briefing saved to %s", output_path)

        return {
            "week_start": ws.isoformat(),
            "status": status,
            "output_path": str(output_path),
            "revenue_summary": revenue,
            "task_summary": tasks,
            "subscription_summary": subscriptions,
        }

    # ------------------------------------------------------------------
    # Week range
    # ------------------------------------------------------------------

    def _determine_week_range(self, week_start: Optional[str] = None) -> tuple:
        """Return (Monday date, Sunday date) for the briefing week."""
        if week_start:
            ws = date.fromisoformat(week_start)
        else:
            today = date.today()
            ws = today - timedelta(days=today.weekday())  # Monday
        we = ws + timedelta(days=6)  # Sunday
        return ws, we

    # ------------------------------------------------------------------
    # Business goals
    # ------------------------------------------------------------------

    def _load_business_goals(self) -> List[Dict[str, Any]]:
        """Parse config/Business_Goals.md for goal entries."""
        goals_file = self.vault / "config" / "Business_Goals.md"
        if not goals_file.exists():
            return []

        try:
            text = goals_file.read_text(encoding="utf-8")
        except OSError:
            return []

        goals: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None

        for line in text.splitlines():
            # Detect goal headers (## or ###)
            header_match = re.match(r"^#{2,3}\s+(.+)$", line)
            if header_match:
                if current:
                    goals.append(current)
                current = {"name": header_match.group(1).strip(), "target": "", "status": "active"}
                continue

            if current:
                # Look for target/status in bullet points
                target_match = re.match(r"^[-*]\s*\*?\*?[Tt]arget\*?\*?\s*:\s*(.+)$", line)
                if target_match:
                    current["target"] = target_match.group(1).strip()
                status_match = re.match(r"^[-*]\s*\*?\*?[Ss]tatus\*?\*?\s*:\s*(.+)$", line)
                if status_match:
                    current["status"] = status_match.group(1).strip()

        if current:
            goals.append(current)

        return goals

    # ------------------------------------------------------------------
    # Pending items
    # ------------------------------------------------------------------

    def _build_pending_items(self, tasks: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format bottlenecks/pending items for the template."""
        items = []
        for b in tasks.get("bottlenecks", []):
            age_hours = b.get("age_hours", 0)
            if age_hours >= 24:
                age_str = f"{age_hours / 24:.1f} days"
            else:
                age_str = f"{age_hours:.0f}h"
            items.append({
                "summary": b.get("summary", "Unknown"),
                "type": b.get("type", "unknown"),
                "age": age_str,
            })
        return items

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def _generate_recommendations(
        self,
        revenue: Dict[str, Any],
        tasks: Dict[str, Any],
        subscriptions: Dict[str, Any],
    ) -> List[str]:
        """Generate 3-5 actionable recommendations based on analysis."""
        recs: List[str] = []

        # Revenue-based
        if revenue["wow_change"] < -10:
            recs.append(
                f"Revenue declined {revenue['wow_change']:.1f}% week-over-week. "
                "Review pipeline and follow up on outstanding proposals."
            )
        elif revenue["wow_change"] > 20:
            recs.append(
                f"Strong revenue growth ({revenue['wow_change']:+.1f}% WoW). "
                "Identify the drivers and replicate across other channels."
            )

        if revenue["overdue_total"] > 0:
            recs.append(
                f"${revenue['overdue_total']:,.2f} in overdue invoices. "
                "Prioritize follow-up on the top outstanding accounts."
            )

        # Task-based
        if tasks["velocity_change"] < -15:
            recs.append(
                f"Task velocity dropped {tasks['velocity_change']:.1f}%. "
                "Check for blockers or resource constraints."
            )

        if len(tasks.get("bottlenecks", [])) > 3:
            recs.append(
                f"{len(tasks['bottlenecks'])} items stuck in approval for >48h. "
                "Clear the approval queue to unblock downstream work."
            )

        # Subscription-based
        if subscriptions.get("waste_alerts"):
            waste_total = sum(a["estimated_monthly"] for a in subscriptions["waste_alerts"])
            recs.append(
                f"${waste_total:,.2f}/mo in potentially unused subscriptions detected. "
                "Review and cancel inactive services."
            )

        # Ensure at least 3 recommendations
        if not recs:
            recs.append("Operations are stable. Continue current trajectory.")
        if len(recs) < 2:
            recs.append("Review business goals alignment during this week's planning session.")
        if len(recs) < 3:
            recs.append("Consider scheduling 1:1s with key stakeholders for Q1 alignment.")

        return recs[:5]

    # ------------------------------------------------------------------
    # Executive summary
    # ------------------------------------------------------------------

    def _generate_executive_summary(
        self,
        revenue: Dict[str, Any],
        tasks: Dict[str, Any],
        subscriptions: Dict[str, Any],
    ) -> str:
        """Generate a 1-paragraph executive summary."""
        parts = []

        # Revenue headline
        if revenue["revenue_this_week"] > 0:
            parts.append(
                f"Revenue this week was ${revenue['revenue_this_week']:,.2f} "
                f"({revenue['wow_change']:+.1f}% WoW), "
                f"with MTD totaling ${revenue['revenue_mtd']:,.2f}."
            )
        else:
            parts.append("No revenue recorded this week.")

        # Task headline
        parts.append(
            f"The team completed {tasks['tasks_completed_this_week']} tasks "
            f"({tasks['velocity_change']:+.1f}% velocity change) "
            f"with {tasks['tasks_pending']} items awaiting approval."
        )

        # Subscription headline
        if subscriptions["total_monthly_subscriptions"] > 0:
            parts.append(
                f"Estimated monthly subscription spend is "
                f"${subscriptions['total_monthly_subscriptions']:,.2f}."
            )

        # Alerts
        alerts = []
        if revenue["overdue_total"] > 0:
            alerts.append(f"${revenue['overdue_total']:,.2f} overdue")
        if subscriptions.get("waste_alerts"):
            alerts.append(f"{len(subscriptions['waste_alerts'])} potential subscription waste")
        if tasks.get("bottlenecks"):
            alerts.append(f"{len(tasks['bottlenecks'])} approval bottlenecks")

        if alerts:
            parts.append("Attention needed: " + ", ".join(alerts) + ".")

        return " ".join(parts)

    # ------------------------------------------------------------------
    # Rendering and saving
    # ------------------------------------------------------------------

    def _render_briefing(self, data: Dict[str, Any]) -> str:
        """Render the Jinja2 briefing template."""
        template = self.jinja_env.get_template("briefing_template.md")
        return template.render(**data)

    def _save_briefing(self, rendered: str, week_start: date) -> Path:
        """
        Save rendered briefing.

        When running in draft mode (--output-drafts), writes to
        Drafts/briefings/ with draft_schema frontmatter so the approval
        workflow can review before delivery.  Otherwise writes directly
        to Briefings/.
        """
        if getattr(self, "_output_drafts", False):
            return self._save_as_draft(rendered, week_start)

        briefings_dir = self.vault / "Briefings"
        briefings_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{week_start.isoformat()}_Monday_Briefing.md"
        output_path = briefings_dir / filename
        output_path.write_text(rendered, encoding="utf-8")
        return output_path

    def _save_as_draft(self, rendered: str, week_start: date) -> Path:
        """Save briefing as a draft in Drafts/briefings/ with frontmatter."""
        import uuid

        drafts_dir = self.vault / "Drafts" / "briefings"
        drafts_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        draft_id = f"draft-briefing-{week_start.isoformat()}-{uuid.uuid4().hex[:8]}"
        expires = now + timedelta(hours=48)

        frontmatter = (
            "---\n"
            f"draft-id: {draft_id}\n"
            f"type: briefing\n"
            f"priority: medium\n"
            f"created-at: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
            f"expires-at: {expires.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
            f"status: pending\n"
            f"week-start: {week_start.isoformat()}\n"
            f"approval_required: true\n"
            f"source:\n"
            f"  agent: cloud-001\n"
            f"  skill: ceo-briefing-generator\n"
            "---\n\n"
        )

        filename = f"{week_start.isoformat()}_Monday_Briefing.md"
        output_path = drafts_dir / filename
        output_path.write_text(frontmatter + rendered, encoding="utf-8")
        return output_path

    def _log_generation(self, week_start: date, status: str, output_path: Path) -> None:
        """Append generation record to Logs/briefings.json."""
        logs_dir = self.vault / "Logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / "briefings.json"

        entries: List[Dict[str, Any]] = []
        if log_file.exists():
            try:
                data = json.loads(log_file.read_text(encoding="utf-8"))
                entries = data if isinstance(data, list) else data.get("entries", [])
            except (json.JSONDecodeError, OSError):
                pass

        entries.append({
            "week_start": week_start.isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "output_path": str(output_path),
        })

        log_file.write_text(json.dumps(entries, indent=2), encoding="utf-8")


# ------------------------------------------------------------------
# CLI entry-point
# ------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CEO Briefing Generator — creates Monday morning business reports"
    )
    parser.add_argument(
        "--vault-path",
        default="./obsidian-vault",
        help="Path to the Obsidian vault (default: ./obsidian-vault)",
    )
    parser.add_argument(
        "--week-start",
        default=None,
        help="Monday date for the briefing (YYYY-MM-DD). Default: current week's Monday.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Generate a single briefing and exit (default behavior)",
    )
    parser.add_argument(
        "--output-drafts",
        action="store_true",
        help="Write output to Drafts/briefings/ with draft_schema frontmatter",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    # Load .env
    for search in (Path(args.vault_path).resolve().parent, Path.cwd()):
        env_file = search / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break

    # Logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    generator = BriefingGenerator(vault_path=args.vault_path)
    generator._output_drafts = args.output_drafts
    result = generator.generate(week_start=args.week_start)

    print(f"\nCEO Briefing generated successfully!")
    print(f"  Week:   {result['week_start']}")
    print(f"  Status: {result['status']}")
    print(f"  Output: {result['output_path']}")
    print(f"  Revenue: ${result['revenue_summary']['revenue_this_week']:,.2f}")
    print(f"  Tasks:   {result['task_summary']['tasks_completed_this_week']} completed")


if __name__ == "__main__":
    main()
