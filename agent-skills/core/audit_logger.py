# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Audit Logger — append-only JSONL audit log with SHA-256 hash chaining.

Provides tamper-evident audit logging for Cloud and Local agents.
Each entry includes a SHA-256 hash of the previous entry, creating
an immutable chain that can be verified for integrity.

Writes to: audit/{agent-id}-audit.jsonl
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Append-only JSONL audit logger with SHA-256 hash chaining.

    Each entry contains:
    - timestamp (ISO 8601)
    - agent_id
    - zone (cloud/local)
    - action (what happened)
    - target (what was acted upon)
    - details (optional metadata dict)
    - prev_hash (SHA-256 of previous entry)
    - hash (SHA-256 of this entry)
    """

    def __init__(
        self,
        agent_id: str,
        zone: str,
        vault_path: str,
    ) -> None:
        self.agent_id = agent_id
        self.zone = zone
        self.vault_path = Path(vault_path).resolve()
        self.log_path = self.vault_path / "audit" / f"{agent_id}-audit.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash: Optional[str] = None
        self._init_chain()

    def _init_chain(self) -> None:
        """Initialize hash chain from existing log file."""
        if not self.log_path.exists() or self.log_path.stat().st_size == 0:
            self._last_hash = "GENESIS"
            return
        # Read last line to get previous hash
        last_line = ""
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    last_line = stripped
        if last_line:
            try:
                entry = json.loads(last_line)
                self._last_hash = entry.get("hash", "GENESIS")
            except json.JSONDecodeError:
                self._last_hash = "GENESIS"
        else:
            self._last_hash = "GENESIS"

    @staticmethod
    def _compute_hash(entry_data: Dict[str, Any], prev_hash: str) -> str:
        """Compute SHA-256 hash for an entry including the previous hash."""
        payload = json.dumps(
            {
                "timestamp": entry_data["timestamp"],
                "agent_id": entry_data["agent_id"],
                "zone": entry_data["zone"],
                "action": entry_data["action"],
                "target": entry_data["target"],
                "details": entry_data.get("details"),
                "prev_hash": prev_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def log(
        self,
        action: str,
        target: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Append an audit entry to the log.

        Args:
            action: What happened (e.g., "agent-started", "draft-created", "file-written").
            target: What was acted upon (e.g., file path, process name).
            details: Optional metadata dict.

        Returns:
            The complete entry dict that was written.
        """
        entry_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": self.agent_id,
            "zone": self.zone,
            "action": action,
            "target": target,
            "details": details,
            "prev_hash": self._last_hash,
        }
        entry_hash = self._compute_hash(entry_data, self._last_hash)
        entry_data["hash"] = entry_hash
        self._last_hash = entry_hash

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry_data, separators=(",", ":")) + "\n")

        logger.debug("Audit: %s %s → %s", action, target, entry_hash[:12])
        return entry_data

    def verify_chain(self) -> bool:
        """
        Verify the integrity of the entire hash chain.

        Returns:
            True if chain is valid.

        Raises:
            ValueError: If a hash mismatch is detected (tamper evidence).
        """
        if not self.log_path.exists():
            return True

        prev_hash = "GENESIS"
        line_num = 0

        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                line_num += 1
                try:
                    entry = json.loads(stripped)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Line {line_num}: invalid JSON — {e}")

                # Verify prev_hash links
                if entry.get("prev_hash") != prev_hash:
                    raise ValueError(
                        f"Line {line_num}: chain broken — "
                        f"expected prev_hash={prev_hash[:12]}..., "
                        f"got={entry.get('prev_hash', 'MISSING')[:12]}..."
                    )

                # Verify entry's own hash
                expected = self._compute_hash(entry, prev_hash)
                if entry.get("hash") != expected:
                    raise ValueError(
                        f"Line {line_num}: hash mismatch — "
                        f"expected={expected[:12]}..., got={entry.get('hash', 'MISSING')[:12]}..."
                    )

                prev_hash = entry["hash"]

        logger.info("Audit chain verified: %d entries, integrity OK", line_num)
        return True

    def query(
        self,
        action: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Query audit log entries with optional filters.

        Args:
            action: Filter by action type.
            since: ISO 8601 timestamp — return entries after this time.
            limit: Maximum number of entries to return.

        Returns:
            List of matching entry dicts (most recent first).
        """
        if not self.log_path.exists():
            return []

        entries: List[Dict[str, Any]] = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                except json.JSONDecodeError:
                    continue

                if action and entry.get("action") != action:
                    continue
                if since and entry.get("timestamp", "") < since:
                    continue

                entries.append(entry)

        # Most recent first, limited
        return list(reversed(entries[-limit:]))


# ------------------------------------------------------------------
# CLI — standalone chain verification utility (T055)
# ------------------------------------------------------------------

def verify_audit_files(vault_path: str) -> None:
    """
    Verify integrity of all audit JSONL files in the vault.

    Scans audit/*.jsonl and verifies SHA-256 hash chains.
    """
    vault = Path(vault_path).resolve()
    audit_dir = vault / "audit"
    if not audit_dir.exists():
        print(f"No audit directory found at {audit_dir}")
        return

    files = sorted(audit_dir.glob("*-audit.jsonl"))
    if not files:
        print("No audit log files found.")
        return

    all_ok = True
    for log_file in files:
        agent_id = log_file.stem.replace("-audit", "")
        print(f"\nVerifying: {log_file.name}")
        try:
            al = AuditLogger.__new__(AuditLogger)
            al.log_path = log_file
            al.vault_path = vault
            result = al.verify_chain()
            if result:
                # Count entries
                count = sum(1 for line in log_file.read_text().splitlines() if line.strip())
                print(f"  OK — {count} entries, chain intact")
        except ValueError as e:
            print(f"  FAIL — {e}")
            all_ok = False

    print(f"\n{'All chains verified OK' if all_ok else 'ERRORS DETECTED — see above'}")


def main() -> None:
    """CLI entry point for audit log operations."""
    import argparse

    parser = argparse.ArgumentParser(description="Audit Logger — verification utility")
    parser.add_argument("--vault-path", default="./obsidian-vault", help="Path to vault")
    parser.add_argument("--verify", action="store_true", help="Verify all audit log chains")
    parser.add_argument("--query", default=None, help="Query logs by action type")
    parser.add_argument("--agent-id", default=None, help="Agent ID for query")
    parser.add_argument("--limit", type=int, default=20, help="Max entries to show")
    args = parser.parse_args()

    if args.verify:
        verify_audit_files(args.vault_path)
    elif args.query and args.agent_id:
        al = AuditLogger(agent_id=args.agent_id, zone="unknown", vault_path=args.vault_path)
        entries = al.query(action=args.query, limit=args.limit)
        for e in entries:
            print(f"  [{e['timestamp']}] {e['action']} → {e['target']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
