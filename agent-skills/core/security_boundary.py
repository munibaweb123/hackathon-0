# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///

"""
Security Boundary Module

Wraps vault file writes with zone-scoped path validation, ensuring that
cloud and local agents can only write to their permitted directories.

Implements the write_permissions contract from vault-file-schema.yaml:
- Cloud agent: Needs_Action/cloud/**, Drafts/**, Signals/**, Updates/**, Logs/**, audit/cloud-*
- Local agent: Pending_Approval/local/**, Approved/**, Done/**, Dashboard.md, Logs/**, audit/local-*, Needs_Action/cloud/leads/**
"""

import logging
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SecurityBoundaryViolation(Exception):
    """Raised when a write operation violates the zone-scoped security boundary."""

    def __init__(self, zone: str, path: str, message: str = ""):
        self.zone = zone
        self.path = path
        detail = message or f"Zone '{zone}' is not permitted to write to '{path}'"
        super().__init__(detail)


# Default write permission rules per zone, matching vault-file-schema.yaml
_DEFAULT_RULES: dict[str, dict[str, list[str]]] = {
    "cloud": {
        "allowed": [
            "Needs_Action/cloud/**",
            "Drafts/**",
            "Signals/**",
            "Updates/**",
            "Logs/**",
            "audit/cloud-*",
        ],
        "denied": [
            "Pending_Approval/**",
            "Approved/**",
            "Done/**",
            "Dashboard.md",
        ],
    },
    "local": {
        "allowed": [
            "Pending_Approval/local/**",
            "Approved/**",
            "Done/**",
            "Dashboard.md",
            "Logs/**",
            "audit/local-*",
            "Needs_Action/cloud/leads/**",
        ],
        "denied": [
            "Drafts/**",
            "Signals/**",
            "Updates/**",
            "Needs_Action/cloud/**",
        ],
    },
}

# OAuth scopes considered read-only (safe for cloud zone)
_READ_ONLY_SCOPES: set[str] = {
    # Gmail
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.metadata",
    "https://www.googleapis.com/auth/gmail.labels",
    # Calendar
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly",
    # Drive
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    # Contacts
    "https://www.googleapis.com/auth/contacts.readonly",
    # Generic
    "openid",
    "profile",
    "email",
}


class SecurityBoundary:
    """
    Zone-scoped security boundary for vault file operations.

    Validates that write operations are permitted for the given zone
    (cloud or local) before allowing them to proceed. Read operations
    are unrestricted for both zones.

    Rules are loaded from the provided config dict or fall back to the
    defaults derived from the vault-file-schema.yaml contract.
    """

    VALID_ZONES = ("cloud", "local")

    def __init__(
        self,
        zone: str,
        vault_path: str,
        config: Optional[dict] = None,
    ) -> None:
        """
        Initialize the security boundary for a specific zone.

        Args:
            zone: Agent zone, either "cloud" or "local".
            vault_path: Absolute or relative path to the vault root directory.
            config: Optional dict with zone rules. Expected shape:
                    {"cloud": {"allowed": [...], "denied": [...]},
                     "local": {"allowed": [...], "denied": [...]}}
                    Falls back to _DEFAULT_RULES when not provided.

        Raises:
            ValueError: If zone is not "cloud" or "local".
        """
        if zone not in self.VALID_ZONES:
            raise ValueError(
                f"Invalid zone '{zone}'. Must be one of: {self.VALID_ZONES}"
            )

        self.zone = zone
        self.vault_path = Path(vault_path).resolve()
        self._rules = (config or _DEFAULT_RULES).get(zone, _DEFAULT_RULES[zone])
        self._allowed: list[str] = self._rules.get("allowed", [])
        self._denied: list[str] = self._rules.get("denied", [])
        self._violation_count = 0

        logger.info(
            "SecurityBoundary initialized: zone=%s, vault=%s, allowed=%d rules, denied=%d rules",
            self.zone,
            self.vault_path,
            len(self._allowed),
            len(self._denied),
        )

    # ------------------------------------------------------------------
    # Path validation
    # ------------------------------------------------------------------

    def _normalize_path(self, relative_path: str) -> str:
        """
        Normalize a relative path for consistent matching.

        Strips leading slashes/dots and resolves to a clean forward-slash
        relative path. Prevents path-traversal attacks via '..' components.

        Args:
            relative_path: The path relative to vault root.

        Returns:
            Cleaned relative path string.

        Raises:
            SecurityBoundaryViolation: If path attempts directory traversal.
        """
        cleaned = relative_path.replace("\\", "/").strip("/")

        # Block path traversal attempts
        if ".." in cleaned.split("/"):
            logger.warning(
                "SECURITY: Path traversal attempt blocked: zone=%s, path=%s",
                self.zone,
                relative_path,
            )
            self._violation_count += 1
            raise SecurityBoundaryViolation(
                self.zone,
                relative_path,
                f"Path traversal detected in '{relative_path}'",
            )

        return cleaned

    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """
        Check if a path matches a glob-style pattern.

        Supports:
        - ** for recursive directory matching
        - * for single-level wildcard
        - Exact filename matching (e.g. "Dashboard.md")

        Args:
            path: Normalized relative path.
            pattern: Glob pattern from the rules.

        Returns:
            True if the path matches the pattern.
        """
        # fnmatch doesn't natively handle ** well for multi-level matching,
        # so we handle the common cases explicitly.

        # Exact match (no wildcards)
        if "*" not in pattern and "?" not in pattern:
            return path == pattern

        # Pattern ends with /** — match anything under that prefix
        if pattern.endswith("/**"):
            prefix = pattern[:-3]  # strip /**
            if path.startswith(prefix + "/") or path == prefix:
                return True

        # Pattern with * but not ** — use fnmatch for single-level globs
        # e.g. "audit/cloud-*" matches "audit/cloud-2026-02-18.jsonl"
        if "**" not in pattern:
            return fnmatch(path, pattern)

        # General ** handling: convert ** to match any number of path segments
        # Split pattern on /** or **/ and check prefix/suffix
        parts = pattern.split("**")
        if len(parts) == 2:
            prefix_pat = parts[0].rstrip("/")
            suffix_pat = parts[1].lstrip("/")
            if prefix_pat and not path.startswith(prefix_pat):
                return False
            if suffix_pat and not fnmatch(path.split("/")[-1], suffix_pat):
                return False
            return True

        return fnmatch(path, pattern)

    def validate_write(self, relative_path: str) -> bool:
        """
        Check if a write to the given path is allowed for this zone.

        The validation logic:
        1. Normalize and sanitize the path (block traversal).
        2. Check denied patterns first — if any denied pattern matches
           AND no more-specific allowed pattern overrides it, deny.
        3. Check allowed patterns — at least one must match.

        The "local" zone has a special case: Needs_Action/cloud/leads/**
        is allowed even though Needs_Action/cloud/** is denied.

        Args:
            relative_path: Path relative to the vault root.

        Returns:
            True if the write is permitted, False otherwise.
        """
        path = self._normalize_path(relative_path)

        # Check if any allowed pattern matches
        allowed_match = any(
            self._matches_pattern(path, pattern) for pattern in self._allowed
        )

        # Check if any denied pattern matches
        denied_match = any(
            self._matches_pattern(path, pattern) for pattern in self._denied
        )

        if denied_match and allowed_match:
            # When both match, the more specific rule wins.
            # Specificity: count non-wildcard path segments.
            best_allowed_specificity = max(
                (
                    len(p.replace("**", "").replace("*", "").split("/"))
                    for p in self._allowed
                    if self._matches_pattern(path, p)
                ),
                default=0,
            )
            best_denied_specificity = max(
                (
                    len(p.replace("**", "").replace("*", "").split("/"))
                    for p in self._denied
                    if self._matches_pattern(path, p)
                ),
                default=0,
            )
            # More specific rule wins; on tie, deny wins (secure default)
            if best_allowed_specificity > best_denied_specificity:
                return True
            logger.warning(
                "SECURITY: Write denied by specificity tie-break: zone=%s, path=%s",
                self.zone,
                path,
            )
            return False

        if not allowed_match:
            logger.debug(
                "Write not allowed (no matching allow rule): zone=%s, path=%s",
                self.zone,
                path,
            )
            return False

        return True

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def write_file(self, relative_path: str, content: str) -> Path:
        """
        Validate the path and write content to the vault.

        Args:
            relative_path: Path relative to the vault root.
            content: String content to write.

        Returns:
            The absolute Path of the written file.

        Raises:
            SecurityBoundaryViolation: If the zone is not allowed to write here.
        """
        if not self.validate_write(relative_path):
            self._violation_count += 1
            logger.warning(
                "SECURITY VIOLATION #%d: zone=%s attempted write to denied path: %s",
                self._violation_count,
                self.zone,
                relative_path,
            )
            raise SecurityBoundaryViolation(self.zone, relative_path)

        target = self.vault_path / self._normalize_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        logger.info(
            "File written: zone=%s, path=%s (%d bytes)",
            self.zone,
            relative_path,
            len(content),
        )
        return target

    def read_file(self, relative_path: str) -> str:
        """
        Read a file from the vault. Reads are unrestricted for both zones.

        Args:
            relative_path: Path relative to the vault root.

        Returns:
            The file content as a string.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        path = self._normalize_path(relative_path)
        target = self.vault_path / path

        if not target.exists():
            raise FileNotFoundError(f"File not found in vault: {path}")

        content = target.read_text(encoding="utf-8")
        logger.debug(
            "File read: zone=%s, path=%s (%d bytes)",
            self.zone,
            relative_path,
            len(content),
        )
        return content

    # ------------------------------------------------------------------
    # Credential scope validation
    # ------------------------------------------------------------------

    def validate_credential_scope(self, scope: str) -> bool:
        """
        Check if a given OAuth scope is read-only.

        For the cloud zone, all OAuth scopes should be read-only to prevent
        the cloud agent from performing write actions through external APIs
        without going through the approval workflow.

        Args:
            scope: An OAuth scope string (e.g. "https://www.googleapis.com/auth/gmail.readonly").

        Returns:
            True if the scope is read-only, False if it grants write access.
        """
        is_readonly = scope in _READ_ONLY_SCOPES

        if not is_readonly and self.zone == "cloud":
            logger.warning(
                "SECURITY: Cloud zone using non-read-only OAuth scope: %s",
                scope,
            )

        return is_readonly

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def violation_count(self) -> int:
        """Number of security violations recorded since initialization."""
        return self._violation_count

    def get_rules_summary(self) -> dict:
        """Return a summary of the active rules for this zone."""
        return {
            "zone": self.zone,
            "vault_path": str(self.vault_path),
            "allowed_patterns": list(self._allowed),
            "denied_patterns": list(self._denied),
            "violation_count": self._violation_count,
        }
