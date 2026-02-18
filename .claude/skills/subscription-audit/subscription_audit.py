# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "jinja2>=3.1.0",
#     "python-dotenv>=1.0.0",
# ]
# ///
"""
Subscription Audit — identifies and analyzes recurring expenses from the
Obsidian vault.  Detects subscriptions via pattern matching, flags waste,
price increases, and duplicates, then generates a detailed audit report.

Usage with UV (recommended):
    uv run subscription_audit.py --vault-path ../../obsidian-vault

Usage with pip:
    pip install -r requirements.txt
    python subscription_audit.py --vault-path ../../obsidian-vault
"""

import argparse
import json
import logging
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure local imports work when run via UV
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv  # noqa: E402
from jinja2 import Environment, FileSystemLoader  # noqa: E402

from pattern_matcher import PatternMatcher  # noqa: E402

logger = logging.getLogger("subscription-audit")


class SubscriptionAuditor:
    """Identifies recurring expenses, flags issues, and generates audit reports."""

    # Minimum occurrences to consider a charge recurring
    MIN_OCCURRENCES = 2
    # Amount tolerance for grouping similar charges (5%)
    AMOUNT_TOLERANCE = 0.05

    def __init__(self, vault_path: str) -> None:
        self.vault = Path(vault_path).resolve()
        self.matcher = PatternMatcher()

        template_dir = Path(__file__).resolve().parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def audit(self, as_of_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Run a full subscription audit.

        Args:
            as_of_date: Date string YYYY-MM-DD. Defaults to today.

        Returns:
            Dict with audit results, report path, and all analysis data.
        """
        audit_date = date.fromisoformat(as_of_date) if as_of_date else date.today()
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        logger.info("Running subscription audit as of %s", audit_date)

        # 1. Load all transactions
        transactions = self._load_transactions()
        logger.info("Loaded %d transactions", len(transactions))

        # 2. Identify subscriptions
        subscriptions = self._identify_subscriptions(transactions)
        logger.info("Identified %d recurring subscriptions", len(subscriptions))

        # 3. Check activity for each subscription
        for sub in subscriptions:
            activity = self._check_activity(sub["canonical"])
            sub["has_recent_activity"] = activity["has_activity"]
            sub["last_activity"] = activity.get("last_activity")
            sub["days_inactive"] = activity.get("days_inactive")

        # 4. Flag issues
        flagged = self._flag_issues(subscriptions)

        # 5. Calculate savings
        savings = self._calculate_savings(flagged)

        # 6. Category breakdown
        category_breakdown = self._category_breakdown(subscriptions)

        # 7. Track changes vs last audit
        changes = self._track_changes(subscriptions)

        # 8. Build cancellation recommendations
        cancellation_recs = self._build_cancellation_recs(flagged, subscriptions)

        # 9. Summary
        total_monthly = sum(s.get("estimated_monthly", 0) for s in subscriptions)
        summary = {
            "active_count": len(subscriptions),
            "total_monthly": round(total_monthly, 2),
            "total_annual": round(total_monthly * 12, 2),
            "flagged_count": (
                len(flagged.get("no_activity", []))
                + len(flagged.get("price_increases", []))
                + len(flagged.get("duplicates", []))
            ),
            "potential_monthly_savings": round(savings["monthly"], 2),
            "potential_annual_savings": round(savings["annual"], 2),
        }

        # 10. Render report
        data = {
            "audit_date": audit_date.isoformat(),
            "generated_at": generated_at,
            "summary": summary,
            "subscriptions": subscriptions,
            "category_breakdown": category_breakdown,
            "flagged_issues": flagged,
            "cancellation_recommendations": cancellation_recs,
            "changes_since_last": changes,
        }

        rendered = self._render_report(data)
        output_path = self._save_report(rendered, audit_date)
        self._log_audit(audit_date, summary, subscriptions)

        logger.info("Audit report saved to %s", output_path)

        return {
            "audit_date": audit_date.isoformat(),
            "output_path": str(output_path),
            "summary": summary,
            "subscriptions": subscriptions,
        }

    # ------------------------------------------------------------------
    # Transaction loading
    # ------------------------------------------------------------------

    def _load_transactions(self) -> List[Dict[str, Any]]:
        """Load all transactions from vault sources."""
        transactions: List[Dict[str, Any]] = []

        # Source 1: Logs/payments.json
        transactions.extend(self._load_json_log(self.vault / "Logs" / "payments.json"))

        # Source 2: Logs/accounting.json
        transactions.extend(self._load_json_log(self.vault / "Logs" / "accounting.json"))

        # Source 3: Accounting/expenses/*.md
        transactions.extend(self._scan_markdown_folder(self.vault / "Accounting" / "expenses"))

        # Source 4: Accounting/payments/*.md
        transactions.extend(self._scan_markdown_folder(self.vault / "Accounting" / "payments"))

        # Source 5: Accounting/invoices/*.md (for received invoices / bills)
        transactions.extend(self._scan_markdown_folder(self.vault / "Accounting" / "invoices"))

        return transactions

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

    def _scan_markdown_folder(self, folder: Path) -> List[Dict[str, Any]]:
        if not folder.exists():
            return []
        results = []
        for md_file in folder.glob("*.md"):
            meta = self._parse_frontmatter(md_file)
            if meta and (meta.get("amount") or meta.get("total")):
                # Normalize amount field
                if "total" in meta and "amount" not in meta:
                    meta["amount"] = meta["total"]
                results.append(meta)
        return results

    # ------------------------------------------------------------------
    # Subscription identification
    # ------------------------------------------------------------------

    def _identify_subscriptions(
        self, transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Group transactions by vendor, detect recurring patterns."""
        # Group by vendor (using pattern matcher for normalization)
        vendor_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        vendor_info: Dict[str, Dict[str, Any]] = {}

        for tx in transactions:
            vendor_raw = (
                tx.get("recipient")
                or tx.get("vendor")
                or tx.get("partner")
                or tx.get("category")
                or tx.get("source", "")
            )
            if not vendor_raw:
                continue

            amount = self._safe_float(tx.get("amount", 0))
            if amount <= 0:
                continue

            date_str = (tx.get("date") or tx.get("timestamp", ""))[:10]
            if not date_str:
                continue

            # Try to match against known vendors
            match = self.matcher.match(str(vendor_raw))
            if match:
                canonical = match["canonical"]
                if canonical not in vendor_info:
                    vendor_info[canonical] = match
            else:
                canonical = str(vendor_raw).strip()
                if canonical not in vendor_info:
                    vendor_info[canonical] = {
                        "canonical": canonical,
                        "category": "other",
                        "confidence": 0.0,
                        "typical_monthly": [],
                    }

            vendor_groups[canonical].append({
                "amount": amount,
                "date": date_str,
            })

        # Detect recurring charges per vendor
        subscriptions = []
        for canonical, txs in vendor_groups.items():
            if len(txs) < self.MIN_OCCURRENCES:
                continue

            txs.sort(key=lambda t: t["date"])

            # Group by similar amounts
            amount_groups = self._group_by_amount(txs)
            for _, group in amount_groups.items():
                if len(group) < self.MIN_OCCURRENCES:
                    continue

                freq = self._detect_frequency(group)
                if freq is None:
                    continue

                avg_amount = sum(t["amount"] for t in group) / len(group)
                last_date = group[-1]["date"]
                amounts_sorted = [t["amount"] for t in group]

                # Estimate monthly cost
                estimated_monthly = self._estimate_monthly(avg_amount, freq)

                # Price increase check
                price_info = self.matcher.detect_price_increase(canonical, amounts_sorted)

                info = vendor_info.get(canonical, {})

                subscriptions.append({
                    "canonical": canonical,
                    "category": info.get("category", "other"),
                    "confidence": info.get("confidence", 0.0),
                    "estimated_monthly": round(estimated_monthly, 2),
                    "frequency": freq,
                    "occurrences": len(group),
                    "last_charge_date": last_date,
                    "last_charge_amount": round(amounts_sorted[-1], 2),
                    "amounts": amounts_sorted,
                    "price_increase": price_info,
                    "status": "active",
                    # Activity fields populated later
                    "has_recent_activity": True,
                    "last_activity": None,
                    "days_inactive": None,
                })

        # Sort by monthly cost descending
        subscriptions.sort(key=lambda s: s["estimated_monthly"], reverse=True)
        return subscriptions

    # ------------------------------------------------------------------
    # Activity checking
    # ------------------------------------------------------------------

    def _check_activity(self, vendor: str) -> Dict[str, Any]:
        """
        Check if there's been recent vault activity related to this vendor.
        Scans completed/, Done/, and Logs/ for mentions in the last 30 days.
        """
        vendor_lower = vendor.lower()
        cutoff = date.today() - timedelta(days=30)
        latest_activity: Optional[str] = None

        # Scan completed/ and Done/
        for folder_name in ("completed", "Done"):
            folder = self.vault / folder_name
            if not folder.exists():
                continue
            for md_file in folder.glob("*.md"):
                try:
                    text = md_file.read_text(encoding="utf-8")
                    if vendor_lower in text.lower():
                        file_date = self._extract_date_from_file(text, md_file)
                        if file_date and (not latest_activity or file_date > latest_activity):
                            latest_activity = file_date
                except OSError:
                    continue

        # Scan Logs/
        logs_dir = self.vault / "Logs"
        if logs_dir.exists():
            for log_file in logs_dir.glob("*.json"):
                try:
                    data = json.loads(log_file.read_text(encoding="utf-8"))
                    entries = data if isinstance(data, list) else data.get("entries", [])
                    for entry in entries:
                        entry_str = json.dumps(entry).lower()
                        if vendor_lower in entry_str:
                            entry_date = (
                                entry.get("date") or entry.get("timestamp", "")
                            )[:10]
                            if entry_date and (
                                not latest_activity or entry_date > latest_activity
                            ):
                                latest_activity = entry_date
                except (json.JSONDecodeError, OSError):
                    continue

        if latest_activity:
            try:
                activity_date = date.fromisoformat(latest_activity[:10])
                days_inactive = (date.today() - activity_date).days
                return {
                    "has_activity": activity_date >= cutoff,
                    "last_activity": latest_activity,
                    "days_inactive": days_inactive,
                }
            except (ValueError, TypeError):
                pass

        return {
            "has_activity": False,
            "last_activity": None,
            "days_inactive": None,
        }

    # ------------------------------------------------------------------
    # Issue flagging
    # ------------------------------------------------------------------

    def _flag_issues(
        self, subscriptions: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Flag subscriptions with issues: no activity, price increases, duplicates."""
        no_activity = []
        price_increases = []

        for sub in subscriptions:
            # No activity in 30+ days
            if not sub.get("has_recent_activity"):
                no_activity.append({
                    "canonical": sub["canonical"],
                    "estimated_monthly": sub["estimated_monthly"],
                    "last_activity": sub.get("last_activity"),
                    "days_inactive": sub.get("days_inactive"),
                })

            # Price increase
            pi = sub.get("price_increase", {})
            if pi.get("increased"):
                price_increases.append({
                    "canonical": sub["canonical"],
                    "estimated_monthly": sub["estimated_monthly"],
                    "old_amount": pi["old_amount"],
                    "new_amount": pi["new_amount"],
                    "pct_change": pi["pct_change"],
                    "above_typical": pi.get("above_typical", False),
                })

        # Duplicates
        duplicates = self.matcher.detect_duplicates(subscriptions)

        return {
            "no_activity": no_activity,
            "price_increases": price_increases,
            "duplicates": duplicates,
        }

    # ------------------------------------------------------------------
    # Savings calculation
    # ------------------------------------------------------------------

    def _calculate_savings(
        self, flagged: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, float]:
        """Estimate savings from cancelling flagged subscriptions."""
        monthly_savings = 0.0

        # Savings from cancelling inactive subscriptions
        for item in flagged.get("no_activity", []):
            monthly_savings += item.get("estimated_monthly", 0)

        # Savings from resolving duplicates (keep cheapest, cancel rest)
        for dup in flagged.get("duplicates", []):
            vendors = dup.get("vendors", [])
            combined = dup.get("combined_monthly", 0)
            if vendors:
                # Estimate: keep cheapest, save the rest
                monthly_savings += combined * 0.5  # Approximate: save ~half

        return {
            "monthly": round(monthly_savings, 2),
            "annual": round(monthly_savings * 12, 2),
        }

    # ------------------------------------------------------------------
    # Cancellation recommendations
    # ------------------------------------------------------------------

    def _build_cancellation_recs(
        self,
        flagged: Dict[str, List[Dict[str, Any]]],
        subscriptions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Build prioritized cancellation recommendations."""
        recs = []
        seen = set()

        # Inactive subscriptions — strongest signal
        for item in flagged.get("no_activity", []):
            canonical = item["canonical"]
            if canonical in seen:
                continue
            seen.add(canonical)
            monthly = item["estimated_monthly"]
            recs.append({
                "canonical": canonical,
                "monthly_cost": monthly,
                "annual_savings": round(monthly * 12, 2),
                "reason": f"No vault activity in {item.get('days_inactive', '30+')} days",
                "priority": "high",
            })

        # Price increases above typical — consider downgrade
        for item in flagged.get("price_increases", []):
            canonical = item["canonical"]
            if canonical in seen or not item.get("above_typical"):
                continue
            seen.add(canonical)
            monthly = item["estimated_monthly"]
            saving = item["new_amount"] - item["old_amount"]
            recs.append({
                "canonical": canonical,
                "monthly_cost": monthly,
                "annual_savings": round(saving * 12, 2),
                "reason": f"Price increased {item['pct_change']:+.1f}% above typical tier pricing",
                "priority": "medium",
            })

        # Sort by annual savings descending
        recs.sort(key=lambda r: r["annual_savings"], reverse=True)
        return recs

    # ------------------------------------------------------------------
    # Category breakdown
    # ------------------------------------------------------------------

    def _category_breakdown(
        self, subscriptions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Compute spend by category."""
        cat_totals: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "monthly": 0.0}
        )
        for sub in subscriptions:
            cat = sub.get("category", "other")
            cat_totals[cat]["count"] += 1
            cat_totals[cat]["monthly"] += sub.get("estimated_monthly", 0)

        total = sum(c["monthly"] for c in cat_totals.values())
        breakdown = []
        for cat, info in sorted(cat_totals.items(), key=lambda x: x[1]["monthly"], reverse=True):
            breakdown.append({
                "category": cat,
                "count": info["count"],
                "monthly": round(info["monthly"], 2),
                "pct": round(info["monthly"] / total * 100, 1) if total > 0 else 0,
            })
        return breakdown

    # ------------------------------------------------------------------
    # Historical tracking
    # ------------------------------------------------------------------

    def _track_changes(
        self, current_subs: List[Dict[str, Any]]
    ) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """Compare current subscriptions with the last audit to detect changes."""
        log_file = self.vault / "Logs" / "subscription_audits.json"
        if not log_file.exists():
            return None

        try:
            data = json.loads(log_file.read_text(encoding="utf-8"))
            entries = data if isinstance(data, list) else data.get("entries", [])
            if not entries:
                return None
        except (json.JSONDecodeError, OSError):
            return None

        # Get last audit's subscription list
        last_audit = entries[-1]
        prev_subs = last_audit.get("subscriptions", [])
        if not prev_subs:
            return None

        prev_map = {s["canonical"]: s for s in prev_subs}
        curr_map = {s["canonical"]: s for s in current_subs}

        new_subs = [
            {"canonical": c, "estimated_monthly": s["estimated_monthly"], "category": s["category"]}
            for c, s in curr_map.items()
            if c not in prev_map
        ]
        removed = [
            {"canonical": c, "estimated_monthly": s.get("estimated_monthly", 0)}
            for c, s in prev_map.items()
            if c not in curr_map
        ]
        price_changed = []
        for canonical, curr in curr_map.items():
            if canonical in prev_map:
                prev_monthly = prev_map[canonical].get("estimated_monthly", 0)
                curr_monthly = curr.get("estimated_monthly", 0)
                if prev_monthly > 0 and abs(curr_monthly - prev_monthly) / prev_monthly > 0.01:
                    pct = ((curr_monthly - prev_monthly) / prev_monthly) * 100
                    price_changed.append({
                        "canonical": canonical,
                        "old_monthly": round(prev_monthly, 2),
                        "new_monthly": round(curr_monthly, 2),
                        "pct_change": round(pct, 1),
                    })

        if not new_subs and not removed and not price_changed:
            return None

        return {
            "new": new_subs,
            "removed": removed,
            "price_changed": price_changed,
        }

    # ------------------------------------------------------------------
    # Rendering and saving
    # ------------------------------------------------------------------

    def _render_report(self, data: Dict[str, Any]) -> str:
        template = self.jinja_env.get_template("audit_report_template.md")
        return template.render(**data)

    def _save_report(self, rendered: str, audit_date: date) -> Path:
        reports_dir = self.vault / "Reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        filename = f"Subscription_Audit_{audit_date.isoformat()}.md"
        output_path = reports_dir / filename
        output_path.write_text(rendered, encoding="utf-8")
        return output_path

    def _log_audit(
        self,
        audit_date: date,
        summary: Dict[str, Any],
        subscriptions: List[Dict[str, Any]],
    ) -> None:
        """Append audit record to Logs/subscription_audits.json for tracking."""
        logs_dir = self.vault / "Logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / "subscription_audits.json"

        entries: List[Dict[str, Any]] = []
        if log_file.exists():
            try:
                data = json.loads(log_file.read_text(encoding="utf-8"))
                entries = data if isinstance(data, list) else data.get("entries", [])
            except (json.JSONDecodeError, OSError):
                pass

        # Store a slim snapshot for change tracking
        entries.append({
            "audit_date": audit_date.isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "subscriptions": [
                {
                    "canonical": s["canonical"],
                    "category": s["category"],
                    "estimated_monthly": s["estimated_monthly"],
                    "frequency": s["frequency"],
                }
                for s in subscriptions
            ],
        })

        log_file.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Frequency detection (adapted from ceo-briefing subscription_analyzer)
    # ------------------------------------------------------------------

    def _detect_frequency(self, txs: List[Dict[str, Any]]) -> Optional[str]:
        """Determine payment frequency from date intervals."""
        if len(txs) < 2:
            return None
        intervals = []
        for i in range(1, len(txs)):
            try:
                d1 = date.fromisoformat(txs[i - 1]["date"][:10])
                d2 = date.fromisoformat(txs[i]["date"][:10])
                intervals.append((d2 - d1).days)
            except (ValueError, TypeError):
                continue
        if not intervals:
            return None
        avg = sum(intervals) / len(intervals)
        if 5 <= avg <= 10:
            return "weekly"
        if 12 <= avg <= 18:
            return "biweekly"
        if 25 <= avg <= 35:
            return "monthly"
        if 80 <= avg <= 100:
            return "quarterly"
        if 340 <= avg <= 400:
            return "annual"
        return None

    @staticmethod
    def _estimate_monthly(amount: float, frequency: str) -> float:
        multipliers = {
            "weekly": 4.33,
            "biweekly": 2.17,
            "monthly": 1.0,
            "quarterly": 1.0 / 3,
            "annual": 1.0 / 12,
        }
        return amount * multipliers.get(frequency, 1.0)

    # ------------------------------------------------------------------
    # Amount grouping
    # ------------------------------------------------------------------

    def _group_by_amount(
        self, txs: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for tx in txs:
            amount = tx["amount"]
            placed = False
            for key, group in groups.items():
                ref = group[0]["amount"]
                if abs(amount - ref) / max(ref, 0.01) <= self.AMOUNT_TOLERANCE:
                    group.append(tx)
                    placed = True
                    break
            if not placed:
                groups[f"{amount:.2f}"] = [tx]
        return groups

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_float(val: Any) -> float:
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

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
    def _extract_date_from_file(text: str, md_file: Path) -> Optional[str]:
        """Extract the most relevant date from a file's frontmatter or mtime."""
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().splitlines():
                    match = re.match(
                        r"^(?:date|completed_at|completed_date|approved_at)\s*:\s*(.+)$",
                        line,
                    )
                    if match:
                        return match.group(1).strip().strip('"').strip("'")[:10]
        # Fallback to file mtime
        try:
            mtime = os.path.getmtime(md_file)
            return date.fromtimestamp(mtime).isoformat()
        except OSError:
            return None


# ------------------------------------------------------------------
# CLI entry-point
# ------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Subscription Audit — identifies and analyzes recurring expenses"
    )
    parser.add_argument(
        "--vault-path",
        default="./obsidian-vault",
        help="Path to the Obsidian vault (default: ./obsidian-vault)",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Audit date as YYYY-MM-DD (default: today)",
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

    auditor = SubscriptionAuditor(vault_path=args.vault_path)
    result = auditor.audit(as_of_date=args.date)

    summary = result["summary"]
    print(f"\nSubscription Audit Complete!")
    print(f"  Date:          {result['audit_date']}")
    print(f"  Subscriptions: {summary['active_count']} active")
    print(f"  Monthly cost:  ${summary['total_monthly']:,.2f}")
    print(f"  Flagged:       {summary['flagged_count']} issues")
    print(f"  Savings:       ${summary['potential_monthly_savings']:,.2f}/mo potential")
    print(f"  Report:        {result['output_path']}")


if __name__ == "__main__":
    main()
