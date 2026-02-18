"""
Pattern Matcher — vendor name normalization, fuzzy matching against a curated
database, price increase detection, and duplicate subscription identification.

No external fuzzy-matching libraries; uses a simple character-overlap ratio.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class PatternMatcher:
    """Matches raw transaction vendor strings to canonical subscription names."""

    # Suffixes to strip during normalization
    _SUFFIXES = re.compile(
        r"\b(inc|llc|ltd|corp|corporation|co|company|pty|bv|gmbh|sa|srl|ag)\b\.?",
        re.IGNORECASE,
    )
    # Domain suffixes to strip
    _DOMAINS = re.compile(r"\.(com|io|co|org|net|ai|app|dev|us|so)\b", re.IGNORECASE)
    # Whitespace collapse
    _WHITESPACE = re.compile(r"\s+")

    # Minimum similarity score to consider a match (0-1)
    MATCH_THRESHOLD = 0.65

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            db_path = str(Path(__file__).resolve().parent / "subscription_database.json")
        self.db_path = Path(db_path)
        self.vendors: List[Dict[str, Any]] = []
        self.duplicate_groups: Dict[str, List[str]] = {}
        self._custom_vendors: List[Dict[str, Any]] = []
        self._load_database()

    # ------------------------------------------------------------------
    # Database loading
    # ------------------------------------------------------------------

    def _load_database(self) -> None:
        """Load the vendor pattern database from JSON."""
        if not self.db_path.exists():
            return
        try:
            data = json.loads(self.db_path.read_text(encoding="utf-8"))
            self.vendors = data.get("vendors", [])
            self.duplicate_groups = data.get("duplicate_groups", {})
        except (json.JSONDecodeError, OSError):
            pass

    # ------------------------------------------------------------------
    # Public API — matching
    # ------------------------------------------------------------------

    def match(self, vendor_string: str) -> Optional[Dict[str, Any]]:
        """
        Match a raw vendor string to a canonical subscription.

        Returns:
            Dict with {canonical, category, confidence, typical_monthly} or None.
        """
        if not vendor_string or not vendor_string.strip():
            return None

        normalized = self._normalize(vendor_string)
        all_vendors = self.vendors + self._custom_vendors

        best_match: Optional[Dict[str, Any]] = None
        best_score = 0.0

        for vendor in all_vendors:
            patterns = vendor.get("patterns", [])
            score = self._best_pattern_score(normalized, patterns)

            if score > best_score:
                best_score = score
                best_match = vendor

        if best_match and best_score >= self.MATCH_THRESHOLD:
            return {
                "canonical": best_match["canonical"],
                "category": best_match.get("category", "other"),
                "confidence": round(best_score, 3),
                "typical_monthly": best_match.get("typical_monthly", []),
            }

        return None

    def add_custom_pattern(
        self, canonical: str, patterns: List[str], category: str = "other"
    ) -> None:
        """Add a custom vendor pattern at runtime."""
        self._custom_vendors.append({
            "canonical": canonical,
            "patterns": [p.lower() for p in patterns],
            "category": category,
            "typical_monthly": [],
        })

    # ------------------------------------------------------------------
    # Public API — price increase detection
    # ------------------------------------------------------------------

    def detect_price_increase(
        self, vendor_canonical: str, amounts: List[float]
    ) -> Dict[str, Any]:
        """
        Detect if the most recent charge is higher than previous charges.

        Args:
            vendor_canonical: Canonical vendor name.
            amounts: List of charge amounts sorted chronologically (oldest first).

        Returns:
            Dict with {increased, old_amount, new_amount, pct_change, above_typical}.
        """
        if len(amounts) < 2:
            return {"increased": False}

        # Compare last two charges
        old_amount = amounts[-2]
        new_amount = amounts[-1]

        if old_amount <= 0:
            return {"increased": False}

        pct_change = ((new_amount - old_amount) / old_amount) * 100

        # Check against typical pricing from database
        above_typical = False
        vendor_info = self._find_vendor(vendor_canonical)
        if vendor_info and vendor_info.get("typical_monthly"):
            max_typical = max(vendor_info["typical_monthly"])
            if new_amount > max_typical * 1.1:  # 10% above highest known tier
                above_typical = True

        return {
            "increased": pct_change > 1.0,  # >1% change considered an increase
            "old_amount": round(old_amount, 2),
            "new_amount": round(new_amount, 2),
            "pct_change": round(pct_change, 1),
            "above_typical": above_typical,
        }

    # ------------------------------------------------------------------
    # Public API — duplicate detection
    # ------------------------------------------------------------------

    def detect_duplicates(
        self, subscriptions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Identify subscriptions that may be duplicates (overlapping functionality).

        Args:
            subscriptions: List of dicts with at least {canonical, category}.

        Returns:
            List of duplicate group dicts: {group_name, vendors, combined_monthly}.
        """
        active_canonicals = {s["canonical"] for s in subscriptions}
        duplicates = []

        for group_name, group_vendors in self.duplicate_groups.items():
            overlap = [v for v in group_vendors if v in active_canonicals]
            if len(overlap) >= 2:
                combined = sum(
                    s.get("estimated_monthly", 0)
                    for s in subscriptions
                    if s.get("canonical") in overlap
                )
                duplicates.append({
                    "group_name": group_name.replace("_", " ").title(),
                    "vendors": overlap,
                    "combined_monthly": round(combined, 2),
                    "recommendation": (
                        f"You have {len(overlap)} overlapping {group_name.replace('_', ' ')} "
                        f"subscriptions. Consider consolidating to save "
                        f"${round(combined - min(s.get('estimated_monthly', 0) for s in subscriptions if s.get('canonical') in overlap), 2)}/mo."
                    ),
                })

        return duplicates

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize(self, text: str) -> str:
        """Normalize a vendor string for matching."""
        result = text.lower().strip()
        # Strip domain suffixes
        result = self._DOMAINS.sub("", result)
        # Strip corporate suffixes
        result = self._SUFFIXES.sub("", result)
        # Remove special characters except spaces and alphanumerics
        result = re.sub(r"[^a-z0-9\s+]", " ", result)
        # Collapse whitespace
        result = self._WHITESPACE.sub(" ", result).strip()
        return result

    # ------------------------------------------------------------------
    # Matching internals
    # ------------------------------------------------------------------

    def _best_pattern_score(self, normalized: str, patterns: List[str]) -> float:
        """Return the best match score across all patterns for a vendor."""
        best = 0.0
        for pattern in patterns:
            norm_pattern = self._normalize(pattern)

            # Exact match
            if normalized == norm_pattern:
                return 1.0

            # Substring containment (high confidence)
            if norm_pattern in normalized or normalized in norm_pattern:
                score = min(len(norm_pattern), len(normalized)) / max(
                    len(norm_pattern), len(normalized), 1
                )
                score = max(score, 0.8)  # substring match is at least 0.8
                best = max(best, score)
                continue

            # Character overlap ratio (simple fuzzy)
            score = self._similarity_ratio(normalized, norm_pattern)
            best = max(best, score)

        return best

    @staticmethod
    def _similarity_ratio(a: str, b: str) -> float:
        """
        Simple similarity ratio based on longest common subsequence length.
        Returns 0.0-1.0. No external dependencies.
        """
        if not a or not b:
            return 0.0

        # Use shorter string for efficiency
        if len(a) > len(b):
            a, b = b, a

        # Count matching characters (order-aware bigram overlap)
        a_bigrams = {a[i : i + 2] for i in range(len(a) - 1)} if len(a) > 1 else {a}
        b_bigrams = {b[i : i + 2] for i in range(len(b) - 1)} if len(b) > 1 else {b}

        if not a_bigrams or not b_bigrams:
            return 1.0 if a == b else 0.0

        overlap = len(a_bigrams & b_bigrams)
        total = len(a_bigrams | b_bigrams)

        return overlap / total if total > 0 else 0.0

    def _find_vendor(self, canonical: str) -> Optional[Dict[str, Any]]:
        """Find a vendor entry by canonical name."""
        for vendor in self.vendors + self._custom_vendors:
            if vendor["canonical"] == canonical:
                return vendor
        return None
