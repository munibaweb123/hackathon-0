"""
Task Analyzer — reads vault completed/, Done/, and pending-approval/ folders
to produce task velocity, bottleneck, and productivity metrics.
"""

import os
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class TaskAnalyzer:
    """Analyzes task completion rates, velocity trends, and bottlenecks."""

    def __init__(self, vault_path: str) -> None:
        self.vault = Path(vault_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, week_start: date, week_end: date) -> Dict[str, Any]:
        """Return task productivity metrics for the given week."""
        completed = self._scan_completed()
        done = self._scan_done()
        pending = self._scan_pending()

        all_finished = completed + done

        # Tasks completed this week (by file mtime or frontmatter date)
        week_finished = [
            t for t in all_finished
            if self._in_range(t.get("completed_date", ""), week_start, week_end)
        ]

        # Velocity trend — last 4 weeks
        velocity_trend = []
        for i in range(4, 0, -1):
            ws = week_start - timedelta(weeks=i)
            we = ws + timedelta(days=6)
            count = sum(
                1 for t in all_finished
                if self._in_range(t.get("completed_date", ""), ws, we)
            )
            velocity_trend.append({"week_start": ws.isoformat(), "count": count})

        # Current week count for trend
        current_count = len(week_finished)
        velocity_trend.append({"week_start": week_start.isoformat(), "count": current_count})

        # Velocity change vs previous week
        prev_count = velocity_trend[-2]["count"] if len(velocity_trend) >= 2 else 0
        velocity_change = (
            ((current_count - prev_count) / prev_count * 100)
            if prev_count > 0 else 0.0
        )

        # Bottlenecks — pending > 48 hours
        now = datetime.now(timezone.utc)
        bottlenecks = []
        for p in pending:
            created = p.get("created_at")
            if created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    age_hours = (now - created_dt).total_seconds() / 3600
                    if age_hours > 48:
                        bottlenecks.append({
                            "id": p.get("id", "unknown"),
                            "type": p.get("type", "unknown"),
                            "summary": p.get("summary", p.get("title", "Untitled")),
                            "age_hours": round(age_hours, 1),
                        })
                except (ValueError, TypeError):
                    pass

        # Completion rate
        total_in_play = len(week_finished) + len(pending)
        completion_rate = (
            (len(week_finished) / total_in_play * 100)
            if total_in_play > 0 else 0.0
        )

        # Top categories
        categories = Counter(
            t.get("type") or t.get("category", "uncategorized")
            for t in week_finished
        )
        top_categories = [
            {"category": cat, "count": cnt}
            for cat, cnt in categories.most_common(5)
        ]

        return {
            "tasks_completed_this_week": current_count,
            "tasks_pending": len(pending),
            "velocity_trend": velocity_trend,
            "velocity_change": round(velocity_change, 1),
            "bottlenecks": bottlenecks[:10],
            "completion_rate": round(completion_rate, 1),
            "top_categories": top_categories,
        }

    # ------------------------------------------------------------------
    # Scanners
    # ------------------------------------------------------------------

    def _scan_completed(self) -> List[Dict[str, Any]]:
        """Read files from completed/ folder."""
        return self._scan_folder(self.vault / "completed")

    def _scan_done(self) -> List[Dict[str, Any]]:
        """Read files from Done/ folder."""
        return self._scan_folder(self.vault / "Done")

    def _scan_pending(self) -> List[Dict[str, Any]]:
        """Read pending-approval/ files with age calculation."""
        folder = self.vault / "pending-approval"
        if not folder.exists():
            return []
        results = []
        for md_file in folder.glob("*.md"):
            meta = self._parse_frontmatter(md_file)
            if meta is None:
                meta = {}
            meta.setdefault("id", md_file.stem)
            meta.setdefault("summary", md_file.stem)
            # Use file mtime as fallback for created_at
            if "created_at" not in meta:
                mtime = os.path.getmtime(md_file)
                meta["created_at"] = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
            results.append(meta)
        return results

    def _scan_folder(self, folder: Path) -> List[Dict[str, Any]]:
        """Scan a folder of markdown files, extracting metadata + completed date."""
        if not folder.exists():
            return []
        results = []
        for md_file in folder.glob("*.md"):
            meta = self._parse_frontmatter(md_file)
            if meta is None:
                meta = {}
            meta.setdefault("id", md_file.stem)
            # Determine completed date from frontmatter or file mtime
            if "completed_date" not in meta:
                for key in ("completed_at", "date", "approved_at", "resolved_at"):
                    if key in meta:
                        meta["completed_date"] = str(meta[key])[:10]
                        break
                else:
                    mtime = os.path.getmtime(md_file)
                    meta["completed_date"] = date.fromtimestamp(mtime).isoformat()
            results.append(meta)
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _in_range(date_str: str, start: date, end: date) -> bool:
        if not date_str:
            return False
        try:
            d = date.fromisoformat(str(date_str)[:10])
            return start <= d <= end
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _parse_frontmatter(md_file: Path) -> Optional[Dict[str, Any]]:
        """Extract YAML frontmatter as a dict."""
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
                try:
                    val = float(val)
                    if val == int(val):
                        val = int(val)
                except (ValueError, TypeError):
                    pass
                result[key] = val
        return result if result else None
