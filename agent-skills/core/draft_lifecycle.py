# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
Draft Lifecycle — creation, expiration, and archival for the AI Employee.

Manages Draft entities per the data model:
- Created by cloud agent in Drafts/{type}/
- 48-hour expiration window
- Status transitions: pending -> approved | rejected | expired
- Expired drafts archived to Done/expired/
"""

import argparse
import logging
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger("draft-lifecycle")

DRAFT_TYPES = ("email-reply", "social-post", "payment", "briefing")
DRAFT_TYPE_DIRS = {"email-reply": "email", "social-post": "social", "payment": "payments", "briefing": "briefings"}
EXPIRATION_HOURS = 48


class Draft:
    """Represents a single draft file."""

    def __init__(self, path: Path, frontmatter: Dict[str, Any], content: str) -> None:
        self.path = path
        self.frontmatter = frontmatter
        self.content = content

    @property
    def draft_id(self) -> str:
        return self.frontmatter.get("draft-id", "")

    @property
    def draft_type(self) -> str:
        return self.frontmatter.get("type", "")

    @property
    def status(self) -> str:
        return self.frontmatter.get("status", "pending")

    @property
    def created_at(self) -> Optional[datetime]:
        val = self.frontmatter.get("created-at")
        if isinstance(val, str):
            return datetime.fromisoformat(val)
        if isinstance(val, datetime):
            return val
        return None

    @property
    def expires_at(self) -> Optional[datetime]:
        val = self.frontmatter.get("expires-at")
        if isinstance(val, str):
            return datetime.fromisoformat(val)
        if isinstance(val, datetime):
            return val
        return None

    @property
    def is_expired(self) -> bool:
        if self.status != "pending":
            return False
        exp = self.expires_at
        if exp is None:
            return False
        return datetime.now(timezone.utc) > exp


class DraftLifecycle:
    """Manages the lifecycle of draft files in the Obsidian vault."""

    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).resolve()
        self.drafts_dir = self.vault_path / "Drafts"
        self.done_dir = self.vault_path / "Done"
        self.expired_dir = self.done_dir / "expired"
        self.expired_dir.mkdir(parents=True, exist_ok=True)

    def create_draft(
        self,
        draft_type: str,
        content: str,
        priority: str = "medium",
        source: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Create a new draft file in the appropriate Drafts/ subdirectory.

        Returns the path to the created draft file.
        """
        if draft_type not in DRAFT_TYPES:
            raise ValueError(f"Invalid draft type: {draft_type!r} — must be one of {DRAFT_TYPES}")

        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=EXPIRATION_HOURS)

        # Generate sequential ID
        type_dir = self.drafts_dir / DRAFT_TYPE_DIRS[draft_type]
        type_dir.mkdir(parents=True, exist_ok=True)
        seq = self._next_sequence(type_dir, draft_type)
        draft_id = f"draft-{draft_type}-{now.strftime('%Y-%m-%d')}-{seq:03d}"

        # Build frontmatter
        fm: Dict[str, Any] = {
            "draft-id": draft_id,
            "type": draft_type,
            "priority": priority,
            "created-at": now.isoformat(),
            "expires-at": expires.isoformat(),
            "status": "pending",
        }
        if source:
            fm["source"] = source
        if context:
            fm["context"] = context

        # Write file
        filename = f"{draft_id}.md"
        file_path = type_dir / filename
        file_content = f"---\n{yaml.dump(fm, default_flow_style=False, sort_keys=False)}---\n\n{content}\n"
        file_path.write_text(file_content, encoding="utf-8")
        logger.info("Created draft: %s (%s, priority=%s)", draft_id, draft_type, priority)
        return file_path

    def sweep_expired(self) -> List[str]:
        """
        Find and archive all expired drafts.

        Returns list of archived draft IDs.
        """
        archived = []
        for draft in self.list_drafts(status="pending"):
            if draft.is_expired:
                self._archive_expired(draft)
                archived.append(draft.draft_id)

        if archived:
            logger.info("Archived %d expired drafts", len(archived))
        return archived

    def list_drafts(self, status: Optional[str] = None, draft_type: Optional[str] = None) -> List[Draft]:
        """List all drafts, optionally filtered by status and/or type."""
        drafts = []
        for md_file in self.drafts_dir.rglob("*.md"):
            fm, content = self._parse_file(md_file)
            if not fm.get("draft-id"):
                continue
            draft = Draft(md_file, fm, content)
            if status and draft.status != status:
                continue
            if draft_type and draft.draft_type != draft_type:
                continue
            drafts.append(draft)
        return sorted(drafts, key=lambda d: d.frontmatter.get("created-at", ""))

    def get_draft(self, draft_id: str) -> Optional[Draft]:
        """Find a draft by its ID."""
        for md_file in self.drafts_dir.rglob("*.md"):
            fm, content = self._parse_file(md_file)
            if fm.get("draft-id") == draft_id:
                return Draft(md_file, fm, content)
        return None

    def update_status(self, draft_id: str, new_status: str) -> bool:
        """Update a draft's status in its frontmatter."""
        draft = self.get_draft(draft_id)
        if not draft:
            logger.warning("Draft not found: %s", draft_id)
            return False

        # Validate transition
        valid_transitions = {
            "pending": {"approved", "rejected", "expired"},
        }
        allowed = valid_transitions.get(draft.status, set())
        if new_status not in allowed:
            logger.warning(
                "Invalid transition: %s -> %s for draft %s",
                draft.status, new_status, draft_id,
            )
            return False

        # Update frontmatter in file
        text = draft.path.read_text(encoding="utf-8")
        text = re.sub(
            r"(status:\s*)(\S+)",
            f"\\g<1>{new_status}",
            text,
            count=1,
        )
        draft.path.write_text(text, encoding="utf-8")
        logger.info("Draft %s: %s -> %s", draft_id, draft.status, new_status)
        return True

    def _archive_expired(self, draft: Draft) -> None:
        """Move an expired draft to Done/expired/."""
        self.update_status(draft.draft_id, "expired")
        dest = self.expired_dir / draft.path.name
        shutil.move(str(draft.path), str(dest))
        logger.info("Archived expired draft: %s -> %s", draft.draft_id, dest)

    def _next_sequence(self, type_dir: Path, draft_type: str) -> int:
        """Find the next sequence number for a draft type on today's date."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        prefix = f"draft-{draft_type}-{today}-"
        max_seq = 0
        for f in type_dir.glob(f"{prefix}*.md"):
            try:
                seq = int(f.stem.split("-")[-1])
                max_seq = max(max_seq, seq)
            except (ValueError, IndexError):
                pass
        return max_seq + 1

    @staticmethod
    def _parse_file(file_path: Path) -> tuple:
        """Parse YAML frontmatter and body from a markdown file."""
        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception:
            return {}, ""

        match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", text, re.DOTALL)
        if not match:
            return {}, text

        try:
            fm = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            fm = {}
        return fm, match.group(2).strip()

    def reject_draft(
        self,
        draft_id: str,
        feedback: str,
        reviewer: str = "local-001",
    ) -> Optional[Path]:
        """
        Reject a draft and record feedback for cloud agent revision (T057).

        The rejected draft is moved to Done/rejected/ with rejection metadata
        appended.  A feedback file is also written to Signals/feedback/ so
        the cloud agent can detect it and generate a revised draft.

        Args:
            draft_id: ID of the draft to reject.
            feedback: Human-readable rejection reason / revision instructions.
            reviewer: ID of the reviewing agent/user.

        Returns:
            Path to the feedback signal file, or None if draft not found.
        """
        draft = self.get_draft(draft_id)
        if not draft:
            logger.warning("Cannot reject — draft not found: %s", draft_id)
            return None

        # Update status to rejected
        self.update_status(draft_id, "rejected")

        # Append rejection metadata to the file
        now = datetime.now(timezone.utc)
        rejection_block = (
            f"\n\n---\n\n"
            f"## Rejection\n\n"
            f"- **Rejected by:** {reviewer}\n"
            f"- **Rejected at:** {now.isoformat()}\n"
            f"- **Feedback:** {feedback}\n"
        )
        text = draft.path.read_text(encoding="utf-8")
        draft.path.write_text(text + rejection_block, encoding="utf-8")

        # Move to Done/rejected/
        rejected_dir = self.done_dir / "rejected"
        rejected_dir.mkdir(parents=True, exist_ok=True)
        dest = rejected_dir / draft.path.name
        shutil.move(str(draft.path), str(dest))

        # Write feedback signal for cloud agent
        feedback_dir = self.vault_path / "Signals" / "feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)

        feedback_data = {
            "type": "draft-rejection",
            "draft-id": draft_id,
            "draft-type": draft.draft_type,
            "original-file": draft.path.name,
            "rejected-at": now.isoformat(),
            "reviewer": reviewer,
            "feedback": feedback,
            "status": "pending-revision",
            "original-frontmatter": draft.frontmatter,
        }
        feedback_file = feedback_dir / f"rejection-{draft_id}.yaml"
        feedback_file.write_text(
            yaml.dump(feedback_data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        logger.info(
            "Draft %s rejected by %s — feedback at %s",
            draft_id, reviewer, feedback_file,
        )
        return feedback_file

    def check_rejection_feedback(self) -> List[Dict[str, Any]]:
        """
        Check for pending rejection feedback signals (cloud agent reads this).

        Returns list of feedback entries that need revision.
        """
        feedback_dir = self.vault_path / "Signals" / "feedback"
        if not feedback_dir.exists():
            return []

        pending = []
        for f in feedback_dir.glob("rejection-*.yaml"):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if data and data.get("status") == "pending-revision":
                    data["_file"] = str(f)
                    pending.append(data)
            except Exception:
                continue
        return pending

    def mark_revision_complete(self, draft_id: str, new_draft_id: str) -> bool:
        """
        Mark a rejection feedback as addressed with a new draft ID.

        Called by cloud agent after generating a revised draft.
        """
        feedback_dir = self.vault_path / "Signals" / "feedback"
        feedback_file = feedback_dir / f"rejection-{draft_id}.yaml"
        if not feedback_file.exists():
            return False

        try:
            data = yaml.safe_load(feedback_file.read_text(encoding="utf-8"))
            data["status"] = "revised"
            data["revised-draft-id"] = new_draft_id
            data["revised-at"] = datetime.now(timezone.utc).isoformat()
            feedback_file.write_text(
                yaml.dump(data, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            logger.info("Feedback for %s marked as revised → %s", draft_id, new_draft_id)
            return True
        except Exception as e:
            logger.error("Failed to update feedback for %s: %s", draft_id, e)
            return False

    def summary(self) -> Dict[str, Any]:
        """Return a summary of draft counts by status and type."""
        counts: Dict[str, int] = {}
        type_counts: Dict[str, int] = {}
        for draft in self.list_drafts():
            counts[draft.status] = counts.get(draft.status, 0) + 1
            type_counts[draft.draft_type] = type_counts.get(draft.draft_type, 0) + 1
        return {"by_status": counts, "by_type": type_counts}


# ======================================================================
# CLI
# ======================================================================
def main() -> None:
    parser = argparse.ArgumentParser(description="Draft Lifecycle Manager")
    parser.add_argument("--vault-path", required=True, help="Obsidian vault path")
    parser.add_argument("--sweep", action="store_true", help="Sweep and archive expired drafts")
    parser.add_argument("--list", action="store_true", help="List all drafts")
    parser.add_argument("--summary", action="store_true", help="Show draft summary")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    lifecycle = DraftLifecycle(args.vault_path)

    if args.sweep:
        archived = lifecycle.sweep_expired()
        print(f"Archived {len(archived)} expired drafts")
        for d in archived:
            print(f"  - {d}")
        return

    if args.list:
        drafts = lifecycle.list_drafts()
        if not drafts:
            print("No drafts found.")
            return
        print(f"\nDrafts ({len(drafts)}):\n")
        for d in drafts:
            exp = "EXPIRED" if d.is_expired else ""
            print(f"  [{d.status:>8}] {d.draft_id} ({d.draft_type}, {d.frontmatter.get('priority', '?')}) {exp}")
        return

    if args.summary:
        s = lifecycle.summary()
        print("\nDraft Summary:")
        print(f"  By status: {s['by_status']}")
        print(f"  By type:   {s['by_type']}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
