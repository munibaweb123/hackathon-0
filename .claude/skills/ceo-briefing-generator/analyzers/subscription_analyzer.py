"""
Subscription Analyzer — detects recurring payments in vault logs, estimates
monthly subscription spend, and flags potential waste.
"""

import json
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


class SubscriptionAnalyzer:
    """Detects recurring payment patterns and flags subscription waste."""

    # Tolerance for "similar amount" matching (within 5%)
    AMOUNT_TOLERANCE = 0.05
    # Minimum occurrences to consider a payment recurring
    MIN_OCCURRENCES = 2

    def __init__(self, vault_path: str) -> None:
        self.vault = Path(vault_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, week_start: date, week_end: date) -> Dict[str, Any]:
        """Return subscription metrics for the given week."""
        payments = self._load_payments()
        expenses = self._scan_expenses()
        all_transactions = payments + expenses

        recurring = self._detect_recurring(all_transactions)

        total_monthly = sum(sub["estimated_monthly"] for sub in recurring)

        # Waste alerts — no activity in last 30 days for this vendor
        waste_alerts = [sub for sub in recurring if self._check_waste(sub)]

        # Upcoming renewals — next payment expected within 7 days of week_end
        upcoming = [
            sub for sub in recurring
            if sub.get("next_expected")
            and week_end <= self._parse_date(sub["next_expected"]) <= week_end + timedelta(days=7)
        ]

        # Cost trend — monthly totals for last 3 months
        cost_trend = self._compute_cost_trend(all_transactions, week_start)

        return {
            "active_subscriptions": [
                {
                    "recipient": sub["recipient"],
                    "estimated_monthly": round(sub["estimated_monthly"], 2),
                    "frequency": sub["frequency"],
                    "last_payment": sub["last_payment"],
                    "occurrences": sub["occurrences"],
                }
                for sub in recurring
            ],
            "total_monthly_subscriptions": round(total_monthly, 2),
            "waste_alerts": [
                {
                    "recipient": sub["recipient"],
                    "estimated_monthly": round(sub["estimated_monthly"], 2),
                    "last_activity": sub.get("last_activity", "unknown"),
                    "reason": "No corresponding activity detected in vault",
                }
                for sub in waste_alerts
            ],
            "upcoming_renewals": [
                {
                    "recipient": sub["recipient"],
                    "amount": round(sub["estimated_monthly"], 2),
                    "expected_date": sub["next_expected"],
                }
                for sub in upcoming
            ],
            "cost_trend": cost_trend,
        }

    # ------------------------------------------------------------------
    # Recurring detection
    # ------------------------------------------------------------------

    def _detect_recurring(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group transactions by recipient and detect monthly/weekly patterns."""
        by_recipient: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for tx in transactions:
            recipient = (
                tx.get("recipient")
                or tx.get("vendor")
                or tx.get("category")
                or tx.get("source", "Unknown")
            )
            amount = float(tx.get("amount", 0))
            date_str = tx.get("date") or tx.get("timestamp", "")
            if amount > 0 and date_str:
                by_recipient[recipient].append({
                    "amount": amount,
                    "date": date_str[:10],
                })

        recurring = []
        for recipient, txs in by_recipient.items():
            if len(txs) < self.MIN_OCCURRENCES:
                continue

            # Sort by date
            txs.sort(key=lambda t: t["date"])

            # Check amount similarity — group by similar amounts
            amount_groups = self._group_by_amount(txs)

            for amount_key, group in amount_groups.items():
                if len(group) < self.MIN_OCCURRENCES:
                    continue

                # Detect frequency
                freq = self._detect_frequency(group)
                if freq is None:
                    continue

                avg_amount = sum(t["amount"] for t in group) / len(group)
                last_date = group[-1]["date"]

                # Estimate monthly cost
                if freq == "weekly":
                    estimated_monthly = avg_amount * 4.33
                elif freq == "biweekly":
                    estimated_monthly = avg_amount * 2.17
                elif freq == "monthly":
                    estimated_monthly = avg_amount
                elif freq == "quarterly":
                    estimated_monthly = avg_amount / 3
                else:
                    estimated_monthly = avg_amount

                # Predict next payment
                next_expected = self._predict_next(last_date, freq)

                recurring.append({
                    "recipient": recipient,
                    "estimated_monthly": estimated_monthly,
                    "frequency": freq,
                    "last_payment": last_date,
                    "occurrences": len(group),
                    "next_expected": next_expected,
                    "last_activity": last_date,
                })

        return recurring

    def _group_by_amount(self, txs: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group transactions by similar amounts (within tolerance)."""
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for tx in txs:
            amount = tx["amount"]
            placed = False
            for key, group in groups.items():
                ref_amount = group[0]["amount"]
                if abs(amount - ref_amount) / max(ref_amount, 0.01) <= self.AMOUNT_TOLERANCE:
                    group.append(tx)
                    placed = True
                    break
            if not placed:
                groups[f"{amount:.2f}"] = [tx]
        return groups

    def _detect_frequency(self, txs: List[Dict[str, Any]]) -> Optional[str]:
        """Determine payment frequency from date intervals."""
        if len(txs) < 2:
            return None

        intervals = []
        for i in range(1, len(txs)):
            d1 = self._parse_date(txs[i - 1]["date"])
            d2 = self._parse_date(txs[i]["date"])
            intervals.append((d2 - d1).days)

        if not intervals:
            return None

        avg_interval = sum(intervals) / len(intervals)

        if 5 <= avg_interval <= 10:
            return "weekly"
        elif 12 <= avg_interval <= 18:
            return "biweekly"
        elif 25 <= avg_interval <= 35:
            return "monthly"
        elif 80 <= avg_interval <= 100:
            return "quarterly"

        return None

    # ------------------------------------------------------------------
    # Waste detection
    # ------------------------------------------------------------------

    def _check_waste(self, subscription: Dict[str, Any]) -> bool:
        """
        A subscription is flagged as potential waste if there's been no
        vault activity (completed tasks, logs) mentioning this vendor
        in the last 30 days.
        """
        recipient = subscription["recipient"].lower()
        cutoff = (date.today() - timedelta(days=30)).isoformat()

        # Check completed/ and Done/ for any mention
        for folder_name in ("completed", "Done"):
            folder = self.vault / folder_name
            if not folder.exists():
                continue
            for md_file in folder.glob("*.md"):
                try:
                    text = md_file.read_text(encoding="utf-8")
                    if recipient in text.lower():
                        # Check if recent
                        meta = self._parse_frontmatter_date(text)
                        if meta and meta >= cutoff:
                            return False
                except OSError:
                    continue

        # Check Logs/ for recent mentions
        logs_dir = self.vault / "Logs"
        if logs_dir.exists():
            for log_file in logs_dir.glob("*.json"):
                try:
                    data = json.loads(log_file.read_text(encoding="utf-8"))
                    entries = data if isinstance(data, list) else data.get("entries", [])
                    for entry in entries:
                        entry_str = json.dumps(entry).lower()
                        if recipient in entry_str:
                            entry_date = (
                                entry.get("date") or entry.get("timestamp", "")
                            )[:10]
                            if entry_date >= cutoff:
                                return False
                except (json.JSONDecodeError, OSError):
                    continue

        return True

    # ------------------------------------------------------------------
    # Cost trend
    # ------------------------------------------------------------------

    def _compute_cost_trend(
        self, transactions: List[Dict[str, Any]], reference: date
    ) -> List[Dict[str, Any]]:
        """Monthly subscription spend for the last 3 months."""
        trend = []
        for months_ago in range(3, 0, -1):
            # Approximate month boundaries
            m_start = reference.replace(day=1) - timedelta(days=30 * months_ago)
            m_start = m_start.replace(day=1)
            if m_start.month == 12:
                m_end = m_start.replace(year=m_start.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                m_end = m_start.replace(month=m_start.month + 1, day=1) - timedelta(days=1)

            total = sum(
                float(tx.get("amount", 0))
                for tx in transactions
                if self._in_range(tx.get("date") or tx.get("timestamp", ""), m_start, m_end)
            )
            trend.append({
                "month": m_start.strftime("%Y-%m"),
                "total": round(total, 2),
            })
        return trend

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_payments(self) -> List[Dict[str, Any]]:
        path = self.vault / "Logs" / "payments.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else data.get("entries", [])
        except (json.JSONDecodeError, OSError):
            return []

    def _scan_expenses(self) -> List[Dict[str, Any]]:
        folder = self.vault / "Accounting" / "expenses"
        if not folder.exists():
            return []
        results = []
        for md_file in folder.glob("*.md"):
            meta = self._parse_frontmatter(md_file)
            if meta:
                results.append(meta)
        return results

    @staticmethod
    def _predict_next(last_date_str: str, frequency: str) -> str:
        try:
            last = date.fromisoformat(last_date_str[:10])
        except (ValueError, TypeError):
            return "unknown"
        deltas = {
            "weekly": timedelta(days=7),
            "biweekly": timedelta(days=14),
            "monthly": timedelta(days=30),
            "quarterly": timedelta(days=91),
        }
        delta = deltas.get(frequency, timedelta(days=30))
        return (last + delta).isoformat()

    @staticmethod
    def _parse_date(date_str: str) -> date:
        try:
            return date.fromisoformat(date_str[:10])
        except (ValueError, TypeError):
            return date.max

    @staticmethod
    def _in_range(date_str: str, start: date, end: date) -> bool:
        if not date_str:
            return False
        try:
            d = date.fromisoformat(date_str[:10])
            return start <= d <= end
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _parse_frontmatter(md_file: Path) -> Optional[Dict[str, Any]]:
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            return None
        if not text.startswith("---"):
            return None
        parts = text.split("---", 2)
        if len(parts) < 3:
            return None
        result: Dict[str, Any] = {}
        for line in parts[1].strip().splitlines():
            match = re.match(r"^(\w[\w_]*)\s*:\s*(.+)$", line)
            if match:
                key = match.group(1)
                val = match.group(2).strip().strip('"').strip("'")
                try:
                    val = float(val)
                    if val == int(val):
                        val = int(val)
                except (ValueError, TypeError):
                    pass
                result[key] = val
        return result if result else None

    @staticmethod
    def _parse_frontmatter_date(text: str) -> Optional[str]:
        """Extract the most recent date from frontmatter."""
        if not text.startswith("---"):
            return None
        parts = text.split("---", 2)
        if len(parts) < 3:
            return None
        for line in parts[1].strip().splitlines():
            match = re.match(r"^(?:date|completed_at|completed_date|approved_at)\s*:\s*(.+)$", line)
            if match:
                return match.group(1).strip().strip('"').strip("'")[:10]
        return None
