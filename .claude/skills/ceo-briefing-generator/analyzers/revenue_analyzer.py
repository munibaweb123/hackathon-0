"""
Revenue Analyzer — reads vault payment/accounting logs and invoice/expense
markdown files to produce weekly financial metrics.
"""

import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


class RevenueAnalyzer:
    """Analyzes revenue, expenses, and financial health from vault data."""

    def __init__(self, vault_path: str) -> None:
        self.vault = Path(vault_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, week_start: date, week_end: date) -> Dict[str, Any]:
        """Return a dict of financial metrics for the given week."""
        payments = self._load_payment_logs()
        accounting = self._load_accounting_logs()
        invoices = self._scan_invoices()
        expenses = self._scan_expenses()

        # Filter to week range
        week_payments = [
            p for p in payments
            if self._in_range(p.get("date") or p.get("timestamp", ""), week_start, week_end)
            and p.get("status") in ("success", "completed", "approved", None)
        ]
        week_expenses = [
            e for e in expenses
            if self._in_range(e.get("date", ""), week_start, week_end)
        ]

        revenue_this_week = sum(float(p.get("amount", 0)) for p in week_payments)
        expenses_this_week = sum(float(e.get("amount", 0)) for e in week_expenses)

        # MTD
        month_start = week_start.replace(day=1)
        mtd_payments = [
            p for p in payments
            if self._in_range(p.get("date") or p.get("timestamp", ""), month_start, week_end)
            and p.get("status") in ("success", "completed", "approved", None)
        ]
        revenue_mtd = sum(float(p.get("amount", 0)) for p in mtd_payments)

        # Budget burn rate
        days_elapsed = max((week_end - month_start).days, 1)
        mtd_expenses = [
            e for e in expenses
            if self._in_range(e.get("date", ""), month_start, week_end)
        ]
        total_mtd_expenses = sum(float(e.get("amount", 0)) for e in mtd_expenses)
        daily_burn = total_mtd_expenses / days_elapsed
        days_remaining = (month_start.replace(month=month_start.month % 12 + 1, day=1) - week_end).days
        budget_burn_rate = daily_burn * days_remaining if days_remaining > 0 else 0

        # Top revenue sources
        source_totals: Dict[str, float] = defaultdict(float)
        for p in week_payments:
            source = p.get("recipient") or p.get("from") or p.get("source", "Unknown")
            source_totals[source] += float(p.get("amount", 0))
        top_sources = sorted(source_totals.items(), key=lambda x: x[1], reverse=True)[:3]

        # Overdue invoices
        today = date.today()
        overdue = [
            inv for inv in invoices
            if inv.get("due_date") and self._parse_date(inv["due_date"]) < today
            and inv.get("status") in ("unpaid", "overdue", "posted", None)
        ]

        # Week-over-week change
        prev_start = week_start - timedelta(days=7)
        prev_end = week_start - timedelta(days=1)
        prev_payments = [
            p for p in payments
            if self._in_range(p.get("date") or p.get("timestamp", ""), prev_start, prev_end)
            and p.get("status") in ("success", "completed", "approved", None)
        ]
        prev_revenue = sum(float(p.get("amount", 0)) for p in prev_payments)
        wow_change = (
            ((revenue_this_week - prev_revenue) / prev_revenue * 100)
            if prev_revenue > 0 else 0.0
        )

        # Forecast — simple moving average of last 4 weeks
        forecast = self._forecast_next_week(payments, week_start)

        return {
            "revenue_this_week": round(revenue_this_week, 2),
            "revenue_mtd": round(revenue_mtd, 2),
            "expenses_this_week": round(expenses_this_week, 2),
            "net_income": round(revenue_this_week - expenses_this_week, 2),
            "budget_burn_rate": round(budget_burn_rate, 2),
            "top_revenue_sources": [
                {"source": s, "amount": round(a, 2)} for s, a in top_sources
            ],
            "overdue_invoices": [
                {
                    "partner": inv.get("partner", "Unknown"),
                    "amount": float(inv.get("amount", 0)),
                    "due_date": inv.get("due_date", "N/A"),
                }
                for inv in overdue[:10]
            ],
            "overdue_total": round(sum(float(inv.get("amount", 0)) for inv in overdue), 2),
            "forecast_next_week": round(forecast, 2),
            "wow_change": round(wow_change, 1),
        }

    # ------------------------------------------------------------------
    # Data loaders
    # ------------------------------------------------------------------

    def _load_payment_logs(self) -> List[Dict[str, Any]]:
        """Read Logs/payments.json — array of payment log entries."""
        path = self.vault / "Logs" / "payments.json"
        return self._load_json_log(path)

    def _load_accounting_logs(self) -> List[Dict[str, Any]]:
        """Read Logs/accounting.json — array of accounting log entries."""
        path = self.vault / "Logs" / "accounting.json"
        return self._load_json_log(path)

    def _load_json_log(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "entries" in data:
                return data["entries"]
            return []
        except (json.JSONDecodeError, OSError):
            return []

    def _scan_invoices(self) -> List[Dict[str, Any]]:
        """Read YAML frontmatter from Accounting/invoices/*.md files."""
        folder = self.vault / "Accounting" / "invoices"
        return self._scan_markdown_folder(folder)

    def _scan_expenses(self) -> List[Dict[str, Any]]:
        """Read YAML frontmatter from Accounting/expenses/*.md files."""
        folder = self.vault / "Accounting" / "expenses"
        return self._scan_markdown_folder(folder)

    def _scan_markdown_folder(self, folder: Path) -> List[Dict[str, Any]]:
        if not folder.exists():
            return []
        results = []
        for md_file in folder.glob("*.md"):
            meta = self._parse_frontmatter(md_file)
            if meta:
                results.append(meta)
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _forecast_next_week(self, payments: List[Dict[str, Any]], week_start: date) -> float:
        """Simple moving average of the last 4 weeks' revenue."""
        weekly_totals = []
        for i in range(1, 5):
            ws = week_start - timedelta(weeks=i)
            we = ws + timedelta(days=6)
            total = sum(
                float(p.get("amount", 0))
                for p in payments
                if self._in_range(p.get("date") or p.get("timestamp", ""), ws, we)
                and p.get("status") in ("success", "completed", "approved", None)
            )
            weekly_totals.append(total)
        return sum(weekly_totals) / len(weekly_totals) if weekly_totals else 0.0

    @staticmethod
    def _in_range(date_str: str, start: date, end: date) -> bool:
        """Check if a date string falls within [start, end]."""
        if not date_str:
            return False
        try:
            d = date.fromisoformat(date_str[:10])
            return start <= d <= end
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _parse_date(date_str: str) -> date:
        try:
            return date.fromisoformat(date_str[:10])
        except (ValueError, TypeError):
            return date.max

    @staticmethod
    def _parse_frontmatter(md_file: Path) -> Optional[Dict[str, Any]]:
        """Extract YAML frontmatter as a dict from a markdown file."""
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            return None
        if not text.startswith("---"):
            return None
        parts = text.split("---", 2)
        if len(parts) < 3:
            return None
        fm = parts[1].strip()
        result: Dict[str, Any] = {}
        for line in fm.splitlines():
            match = re.match(r"^(\w[\w_]*)\s*:\s*(.+)$", line)
            if match:
                key = match.group(1)
                val = match.group(2).strip().strip('"').strip("'")
                # Try numeric conversion
                try:
                    val = float(val)
                    if val == int(val):
                        val = int(val)
                except (ValueError, TypeError):
                    pass
                result[key] = val
        return result if result else None
