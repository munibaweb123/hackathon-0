"""
Conflict Resolver — handles Git merge conflicts with defined strategies.

Strategies:
  - local_wins:  keep LOCAL (ours) version
  - remote_wins: keep REMOTE (theirs) version
  - newest_wins: keep version with later frontmatter timestamp
  - append_both: concatenate both versions (for log files)
"""

import re
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Regex for Git conflict markers
CONFLICT_PATTERN = re.compile(
    r"<{7}\s*(\S*)\n(.*?)={7}\n(.*?)>{7}\s*(\S*)\n",
    re.DOTALL,
)

# Regex for frontmatter date fields
DATE_PATTERN = re.compile(
    r"(?:date|created|created_at|updated_at|generated_at|timestamp)"
    r"\s*:\s*[\"']?(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2})",
    re.IGNORECASE,
)


class ConflictResolver:
    """
    Resolves Git merge conflicts using configurable per-file strategies.
    """

    def __init__(self) -> None:
        self.default_rules: Dict[str, str] = {
            # Cloud-wins (cloud is authoritative)
            "Drafts/**": "cloud_wins",
            "Signals/**": "cloud_wins",
            "Needs_Action/cloud/**": "cloud_wins",
            "Updates/**": "remote_wins",
            # Local-wins (local is authoritative)
            "Approved/**": "local_wins",
            "Done/**": "local_wins",
            "Pending_Approval/**": "local_wins",
            "Dashboard.md": "local_wins",
            "In_Progress/**": "local_wins",
            # Shared paths
            "Logs/*.json": "append_both",
            "Logs/**/*.json": "append_both",
            "Logs/**/*.jsonl": "append_both",
            "audit/**": "append_both",
            "config/*": "remote_wins",
        }
        self.default_strategy = "newest_wins"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def detect_conflicts(self, repo_path: str) -> List[str]:
        """List all files with conflict markers in the repo."""
        repo = Path(repo_path)
        conflicted = []

        for f in repo.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix in (".pyc", ".pyo", ".so", ".dll"):
                continue
            if ".git" in f.parts:
                continue
            try:
                content = f.read_text(encoding="utf-8")
                if "<<<<<<<" in content and "=======" in content and ">>>>>>>" in content:
                    conflicted.append(str(f.relative_to(repo)))
            except (UnicodeDecodeError, PermissionError):
                continue

        return conflicted

    def auto_resolve(
        self,
        repo_path: str,
        rules: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Auto-resolve all conflicts using rules.

        Args:
            repo_path: Path to the git repo.
            rules: Dict mapping glob patterns to strategies.
                   Falls back to self.default_rules.

        Returns:
            {resolved: [files], failed: [files], strategies_used: {file: strategy}}
        """
        effective_rules = rules or self.default_rules
        conflicts = self.detect_conflicts(repo_path)

        resolved = []
        failed = []
        strategies_used = {}

        for file_rel in conflicts:
            strategy = self._match_strategy(file_rel, effective_rules)
            file_path = Path(repo_path) / file_rel

            try:
                self.resolve_file(str(file_path), strategy)
                resolved.append(file_rel)
                strategies_used[file_rel] = strategy
            except Exception as e:
                failed.append({"file": file_rel, "error": str(e)})

        return {
            "resolved": resolved,
            "failed": failed,
            "strategies_used": strategies_used,
        }

    def resolve_file(self, file_path: str, strategy: str) -> None:
        """
        Resolve conflicts in a single file using the given strategy.

        Args:
            file_path: Absolute path to the conflicted file.
            strategy: One of: local_wins, remote_wins, newest_wins, append_both
        """
        fp = Path(file_path)
        content = fp.read_text(encoding="utf-8")

        if "<<<<<<<" not in content:
            return  # No conflicts

        if strategy == "local_wins":
            resolved = self._resolve_local_wins(content)
        elif strategy in ("remote_wins", "cloud_wins"):
            resolved = self._resolve_remote_wins(content)
        elif strategy == "newest_wins":
            resolved = self._resolve_newest_wins(content)
        elif strategy == "append_both":
            resolved = self._resolve_append_both(content)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        fp.write_text(resolved, encoding="utf-8")

    # ------------------------------------------------------------------
    # Resolution strategies
    # ------------------------------------------------------------------
    def _resolve_local_wins(self, content: str) -> str:
        """Keep LOCAL (ours) version for all conflict blocks."""
        def replace(match):
            return match.group(2)  # ours
        return CONFLICT_PATTERN.sub(replace, content)

    def _resolve_remote_wins(self, content: str) -> str:
        """Keep REMOTE (theirs) version for all conflict blocks."""
        def replace(match):
            return match.group(3)  # theirs
        return CONFLICT_PATTERN.sub(replace, content)

    def _resolve_newest_wins(self, content: str) -> str:
        """Keep whichever version has a later timestamp in the conflict block."""
        def replace(match):
            ours = match.group(2)
            theirs = match.group(3)

            ours_date = self._extract_date(ours)
            theirs_date = self._extract_date(theirs)

            if ours_date and theirs_date:
                return ours if ours_date >= theirs_date else theirs
            elif theirs_date:
                return theirs
            else:
                return ours  # default to local if no dates found

        return CONFLICT_PATTERN.sub(replace, content)

    def _resolve_append_both(self, content: str) -> str:
        """Concatenate both versions (useful for log/JSON array files)."""
        def replace(match):
            ours = match.group(2).strip()
            theirs = match.group(3).strip()

            # For JSON arrays, try to merge entries
            if ours.startswith("[") and theirs.startswith("["):
                return self._merge_json_arrays(ours, theirs)

            return f"{ours}\n{theirs}\n"

        return CONFLICT_PATTERN.sub(replace, content)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _match_strategy(self, file_rel: str, rules: Dict[str, str]) -> str:
        """Find the matching strategy for a file path using glob rules."""
        for pattern, strategy in rules.items():
            if fnmatch(file_rel, pattern):
                return strategy
        return self.default_strategy

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract the latest date string from text."""
        matches = DATE_PATTERN.findall(text)
        if matches:
            return max(matches)
        return None

    def _merge_json_arrays(self, ours: str, theirs: str) -> str:
        """Attempt to merge two JSON arrays by combining entries."""
        import json

        try:
            ours_data = json.loads(ours)
            theirs_data = json.loads(theirs)

            if isinstance(ours_data, list) and isinstance(theirs_data, list):
                # Deduplicate by converting dicts to sorted JSON strings
                seen = set()
                merged = []
                for item in ours_data + theirs_data:
                    key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
                    if key not in seen:
                        seen.add(key)
                        merged.append(item)

                return json.dumps(merged, indent=2, default=str)
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: just concatenate
        return f"{ours}\n{theirs}\n"

    def _parse_conflict_markers(
        self, content: str
    ) -> List[Tuple[str, str, str, str]]:
        """
        Parse all conflict blocks.

        Returns list of (ours_label, ours_content, theirs_content, theirs_label).
        """
        return [
            (m.group(1), m.group(2), m.group(3), m.group(4))
            for m in CONFLICT_PATTERN.finditer(content)
        ]
