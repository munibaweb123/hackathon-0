# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
Briefing Aggregator — collects and aggregates revenue, task velocity,
subscription waste, and overdue items from the Obsidian vault for use
in the CEO Briefing Generator.

Part of Phase 6 (US4 — CEO Monday Briefing) of the Platinum Tier
AI Employee.  Produces structured dicts that the briefing_generator
templates consume.  Also calculates week-over-week and month-over-month
comparisons for revenue.

Covers tasks T035 and T037 from specs/005-platinum-tier-ai-employee/tasks.md.
"""

import json
import logging
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)


class BriefingAggregator:
    """
    Aggregates data from vault sources into structured dicts for the
    CEO briefing template.  Reads revenue from accounting/payment logs,
    task velocity from project files, subscription waste from audit
    results, and overdue items with owners.
    """

    def __init__(self, vault_path: str) -> None:
        self.vault = Path(vault_path).resolve()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def aggregate(
        self, week_start: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Collect all data sources and return a unified briefing payload.

        Args:
            week_start: Monday of the briefing week.  Defaults to this
                        week's Monday.

        Returns:
            Dict with keys: revenue, tasks, subscriptions, overdue,
            comparisons, generated_at.
        """
        ws, we = self._week_range(week_start)
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        revenue = self.collect_revenue(ws, we)
        tasks = self.collect_task_velocity(ws, we)
        subscriptions = self.collect_subscription_data()
        overdue = self.collect_overdue_items()
        comparisons = self._build_comparisons(revenue, tasks, ws, we)

        return {
            "week_start": ws.isoformat(),
            "week_end": we.isoformat(),
            "generated_at": generated_at,
            "revenue": revenue,
            "tasks": tasks,
            "subscriptions": subscriptions,
            "overdue": overdue,
            "comparisons": comparisons,
        }

    # ------------------------------------------------------------------
    # Revenue collection
    # ------------------------------------------------------------------

    def collect_revenue(self, week_start: date, week_end: date) -> Dict[str, Any]:
        """
        Read payment/accounting logs and compute weekly revenue.

        Sources:
            - Logs/payments/*.json
            - Done/payments/*.md (frontmatter amount)
            - Accounting data files
        """
        payments = self._load_json_dir(self.vault / "Logs" / "payments")
        done_payments = self._scan_frontmatter_amounts(
            self.vault / "Done" / "payments"
        )

        all_entries = payments + done_payments

        week_total = sum(
            float(e.get("amount", 0))
            for e in all_entries
            if self._in_range(
                e.get("date") or e.get("timestamp", ""), week_start, week_end
            )
            and e.get("status", "success") in ("success", "completed", "approved")
        )

        # Month-to-date
        month_start = week_start.replace(day=1)
        mtd_total = sum(
            float(e.get("amount", 0))
            for e in all_entries
            if self._in_range(
                e.get("date") or e.get("timestamp", ""), month_start, week_end
            )
            and e.get("status", "success") in ("success", "completed", "approved")
        )

        # Previous week for WoW
        prev_start = week_start - timedelta(days=7)
        prev_end = week_start - timedelta(days=1)
        prev_total = sum(
            float(e.get("amount", 0))
            for e in all_entries
            if self._in_range(
                e.get("date") or e.get("timestamp", ""), prev_start, prev_end
            )
            and e.get("status", "success") in ("success", "completed", "approved")
        )

        wow_change = (
            ((week_total - prev_total) / prev_total * 100) if prev_total > 0 else 0.0
        )

        # Previous month for MoM
        prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
        prev_month_end = month_start - timedelta(days=1)
        prev_month_total = sum(
            float(e.get("amount", 0))
            for e in all_entries
            if self._in_range(
                e.get("date") or e.get("timestamp", ""),
                prev_month_start,
                prev_month_end,
            )
            and e.get("status", "success") in ("success", "completed", "approved")
        )

        mom_change = (
            ((mtd_total - prev_month_total) / prev_month_total * 100)
            if prev_month_total > 0
            else 0.0
        )

        # Overdue invoices
        overdue_invoices = self._find_overdue_invoices()
        overdue_total = sum(float(i.get("amount", 0)) for i in overdue_invoices)

        return {
            "revenue_this_week": week_total,
            "revenue_mtd": mtd_total,
            "revenue_prev_week": prev_total,
            "revenue_prev_month": prev_month_total,
            "wow_change": round(wow_change, 1),
            "mom_change": round(mom_change, 1),
            "overdue_total": overdue_total,
            "overdue_invoices": overdue_invoices,
        }

    # ------------------------------------------------------------------
    # Task velocity
    # ------------------------------------------------------------------

    def collect_task_velocity(
        self, week_start: date, week_end: date
    ) -> Dict[str, Any]:
        """
        Compute task completion metrics from Done/ and Needs_Action/ dirs.

        Tracks tasks completed this week vs last week for velocity delta,
        plus pending items and bottlenecks (items >48h in approval).
        """
        done_dir = self.vault / "Done"
        pending_dir = self.vault / "Pending_Approval"
        needs_action_dir = self.vault / "Needs_Action"

        # Completed this week
        completed_this_week = self._count_files_in_range(done_dir, week_start, week_end)

        # Completed last week
        prev_start = week_start - timedelta(days=7)
        prev_end = week_start - timedelta(days=1)
        completed_last_week = self._count_files_in_range(done_dir, prev_start, prev_end)

        velocity_change = (
            ((completed_this_week - completed_last_week) / completed_last_week * 100)
            if completed_last_week > 0
            else 0.0
        )

        # Pending approval items
        pending_count = self._count_md_files(pending_dir)

        # Bottlenecks: items in Pending_Approval older than 48h
        bottlenecks = self._find_bottlenecks(pending_dir, hours_threshold=48)

        # Overdue tasks: items in Needs_Action with past due_date
        overdue_tasks = self._find_overdue_tasks(needs_action_dir)

        return {
            "tasks_completed_this_week": completed_this_week,
            "tasks_completed_prev_week": completed_last_week,
            "velocity_change": round(velocity_change, 1),
            "tasks_pending": pending_count,
            "bottlenecks": bottlenecks,
            "overdue_tasks": overdue_tasks,
        }

    # ------------------------------------------------------------------
    # Subscription data
    # ------------------------------------------------------------------

    def collect_subscription_data(self) -> Dict[str, Any]:
        """
        Read subscription audit results from audit/ or Logs/ dirs.

        Sources:
            - Logs/subscription_audit*.json
            - config/subscriptions.yaml
        """
        audit_files = sorted(
            (self.vault / "Logs").glob("subscription_audit*.json"), reverse=True
        ) if (self.vault / "Logs").exists() else []

        latest_audit: Dict[str, Any] = {}
        if audit_files:
            try:
                latest_audit = json.loads(
                    audit_files[0].read_text(encoding="utf-8")
                )
                if isinstance(latest_audit, list) and latest_audit:
                    latest_audit = latest_audit[-1]
            except (json.JSONDecodeError, OSError):
                pass

        total_monthly = float(latest_audit.get("total_monthly_cost", 0))
        waste_alerts = latest_audit.get("waste_alerts", [])
        active_count = int(latest_audit.get("active_subscriptions", 0))

        return {
            "total_monthly_subscriptions": total_monthly,
            "active_subscription_count": active_count,
            "waste_alerts": waste_alerts,
            "waste_total": sum(
                float(w.get("estimated_monthly", 0)) for w in waste_alerts
            ),
            "last_audit_date": latest_audit.get("audit_date", "unknown"),
        }

    # ------------------------------------------------------------------
    # Overdue items with owners  (T037)
    # ------------------------------------------------------------------

    def collect_overdue_items(self) -> List[Dict[str, Any]]:
        """
        Scan Needs_Action/ and Pending_Approval/ for items past due date.
        Returns list with item summary, owner, due_date, and age.
        """
        items: List[Dict[str, Any]] = []

        for search_dir in (
            self.vault / "Needs_Action",
            self.vault / "Pending_Approval",
        ):
            if not search_dir.exists():
                continue
            for md_file in search_dir.rglob("*.md"):
                fm = self._parse_frontmatter(md_file)
                due_str = fm.get("due_date") or fm.get("due") or fm.get("deadline")
                if not due_str:
                    continue

                try:
                    due = date.fromisoformat(str(due_str)[:10])
                except ValueError:
                    continue

                if due >= date.today():
                    continue  # not overdue

                owner = fm.get("owner") or fm.get("assigned_to") or "unassigned"
                summary = fm.get("subject") or fm.get("title") or md_file.stem
                age_days = (date.today() - due).days

                items.append(
                    {
                        "summary": summary,
                        "owner": owner,
                        "due_date": due.isoformat(),
                        "age_days": age_days,
                        "file": str(md_file.relative_to(self.vault)),
                        "type": fm.get("type", "unknown"),
                    }
                )

        # Sort by age descending (most overdue first)
        items.sort(key=lambda x: x["age_days"], reverse=True)
        return items

    # ------------------------------------------------------------------
    # Comparisons (T037 — WoW and MoM)
    # ------------------------------------------------------------------

    def _build_comparisons(
        self,
        revenue: Dict[str, Any],
        tasks: Dict[str, Any],
        week_start: date,
        week_end: date,
    ) -> Dict[str, Any]:
        """Build week-over-week and month-over-month comparison summaries."""
        return {
            "revenue_wow": {
                "current": revenue["revenue_this_week"],
                "previous": revenue["revenue_prev_week"],
                "change_pct": revenue["wow_change"],
                "direction": (
                    "up" if revenue["wow_change"] > 0
                    else "down" if revenue["wow_change"] < 0
                    else "flat"
                ),
            },
            "revenue_mom": {
                "current_mtd": revenue["revenue_mtd"],
                "previous_month": revenue["revenue_prev_month"],
                "change_pct": revenue["mom_change"],
                "direction": (
                    "up" if revenue["mom_change"] > 0
                    else "down" if revenue["mom_change"] < 0
                    else "flat"
                ),
            },
            "task_velocity_wow": {
                "current": tasks["tasks_completed_this_week"],
                "previous": tasks["tasks_completed_prev_week"],
                "change_pct": tasks["velocity_change"],
            },
        }

    # ------------------------------------------------------------------
    # Helpers — file scanning
    # ------------------------------------------------------------------

    def _week_range(self, week_start: Optional[date] = None) -> Tuple[date, date]:
        """Return (Monday, Sunday) for the briefing week."""
        if week_start is None:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
        return week_start, week_start + timedelta(days=6)

    def _load_json_dir(self, dir_path: Path) -> List[Dict[str, Any]]:
        """Load all JSON files from a directory into a flat list."""
        entries: List[Dict[str, Any]] = []
        if not dir_path.exists():
            return entries
        for fp in dir_path.glob("*.json"):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    entries.extend(data)
                elif isinstance(data, dict):
                    entries.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        return entries

    def _scan_frontmatter_amounts(self, dir_path: Path) -> List[Dict[str, Any]]:
        """Read markdown files and extract amount/date from YAML frontmatter."""
        results: List[Dict[str, Any]] = []
        if not dir_path.exists():
            return results
        for md in dir_path.rglob("*.md"):
            fm = self._parse_frontmatter(md)
            if "amount" in fm:
                results.append(fm)
        return results

    def _parse_frontmatter(self, file_path: Path) -> Dict[str, Any]:
        """Parse YAML frontmatter from a markdown file."""
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return {}

        if not text.startswith("---"):
            return {}

        end = text.find("---", 3)
        if end == -1:
            return {}

        try:
            fm = yaml.safe_load(text[3:end])
            return fm if isinstance(fm, dict) else {}
        except yaml.YAMLError:
            return {}

    def _in_range(
        self, date_str: str, start: date, end: date
    ) -> bool:
        """Check if a date string falls within [start, end]."""
        if not date_str:
            return False
        try:
            d = date.fromisoformat(str(date_str)[:10])
            return start <= d <= end
        except (ValueError, TypeError):
            return False

    def _count_files_in_range(
        self, dir_path: Path, start: date, end: date
    ) -> int:
        """Count markdown files whose frontmatter date is in range."""
        count = 0
        if not dir_path.exists():
            return count
        for md in dir_path.rglob("*.md"):
            fm = self._parse_frontmatter(md)
            date_str = (
                fm.get("completed_at")
                or fm.get("date")
                or fm.get("created_at")
                or ""
            )
            if self._in_range(date_str, start, end):
                count += 1
        return count

    def _count_md_files(self, dir_path: Path) -> int:
        """Count all .md files recursively."""
        if not dir_path.exists():
            return 0
        return sum(1 for _ in dir_path.rglob("*.md"))

    def _find_bottlenecks(
        self, dir_path: Path, hours_threshold: int = 48
    ) -> List[Dict[str, Any]]:
        """Find items stuck in a directory longer than threshold hours."""
        bottlenecks: List[Dict[str, Any]] = []
        if not dir_path.exists():
            return bottlenecks

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)

        for md in dir_path.rglob("*.md"):
            fm = self._parse_frontmatter(md)
            created_str = fm.get("created_at") or fm.get("date") or fm.get("created")
            if not created_str:
                continue
            try:
                created = datetime.fromisoformat(str(created_str).replace("Z", "+00:00"))
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            if created < cutoff:
                age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
                bottlenecks.append(
                    {
                        "summary": fm.get("subject") or fm.get("title") or md.stem,
                        "type": fm.get("type", "unknown"),
                        "age_hours": round(age_hours, 1),
                        "file": str(md.relative_to(self.vault)),
                    }
                )

        bottlenecks.sort(key=lambda x: x["age_hours"], reverse=True)
        return bottlenecks

    def _find_overdue_invoices(self) -> List[Dict[str, Any]]:
        """Find invoices past their due date in Drafts/payments/ or Needs_Action/."""
        overdue: List[Dict[str, Any]] = []
        today = date.today()

        for search_dir in (
            self.vault / "Drafts" / "payments",
            self.vault / "Needs_Action" / "cloud" / "invoices",
        ):
            if not search_dir.exists():
                continue
            for md in search_dir.rglob("*.md"):
                fm = self._parse_frontmatter(md)
                due_str = fm.get("due_date") or fm.get("due")
                if not due_str:
                    continue
                try:
                    due = date.fromisoformat(str(due_str)[:10])
                except ValueError:
                    continue
                if due < today:
                    overdue.append(
                        {
                            "summary": fm.get("subject") or fm.get("title") or md.stem,
                            "amount": float(fm.get("amount", 0)),
                            "due_date": due.isoformat(),
                            "days_overdue": (today - due).days,
                            "recipient": fm.get("recipient", "unknown"),
                        }
                    )

        overdue.sort(key=lambda x: x["days_overdue"], reverse=True)
        return overdue

    def _find_overdue_tasks(self, dir_path: Path) -> List[Dict[str, Any]]:
        """Find tasks past their deadline in a directory."""
        overdue: List[Dict[str, Any]] = []
        today = date.today()

        if not dir_path.exists():
            return overdue

        for md in dir_path.rglob("*.md"):
            fm = self._parse_frontmatter(md)
            due_str = fm.get("due_date") or fm.get("deadline") or fm.get("due")
            if not due_str:
                continue
            try:
                due = date.fromisoformat(str(due_str)[:10])
            except ValueError:
                continue
            if due < today:
                overdue.append(
                    {
                        "summary": fm.get("subject") or fm.get("title") or md.stem,
                        "owner": fm.get("owner") or fm.get("assigned_to") or "unassigned",
                        "due_date": due.isoformat(),
                        "days_overdue": (today - due).days,
                    }
                )

        overdue.sort(key=lambda x: x["days_overdue"], reverse=True)
        return overdue


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main() -> None:
    """CLI entry point for standalone testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Briefing Aggregator")
    parser.add_argument("--vault-path", default="./obsidian-vault")
    parser.add_argument("--week-start", default=None, help="YYYY-MM-DD")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    ws = date.fromisoformat(args.week_start) if args.week_start else None
    agg = BriefingAggregator(args.vault_path)
    result = agg.aggregate(ws)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
