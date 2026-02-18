# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "watchdog>=4.0.0",
#     "python-dotenv>=1.0.0",
# ]
# ///
"""
Filesystem Watcher Agent Skill

Monitors a drop folder for new files using watchdog (event-driven)
and creates action files in an Obsidian vault.

    uv run filesystem_watcher.py --drop-folder ~/AI_Employee/Drop

Files are copied to vault's Attachments/ folder, a markdown action
file is created in Needs_Action/, and the source is cleaned up.
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Ensure local + sibling skill imports work
_SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SKILL_DIR))
sys.path.insert(0, str(_SKILL_DIR.parent / "gmail-watcher"))

from dotenv import load_dotenv  # noqa: E402
from watchdog.observers import Observer  # noqa: E402
from watchdog.events import FileSystemEventHandler, FileCreatedEvent  # noqa: E402

from base_watcher import BaseWatcher  # noqa: E402
from file_handler import FileHandler  # noqa: E402


class DropFolderHandler(FileSystemEventHandler):
    """Watchdog event handler that delegates to the FilesystemWatcher."""

    def __init__(self, watcher: "FilesystemWatcher"):
        super().__init__()
        self.watcher = watcher

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return

        path = Path(event.src_path)

        # Brief wait for file write to complete (e.g. copy in progress)
        time.sleep(0.5)

        self.watcher.handle_new_file(path)


class FilesystemWatcher(BaseWatcher):
    """
    Monitors a drop folder for new files using watchdog and creates
    ``FILE_{name}.md`` action files in ``Needs_Action/``.
    """

    def __init__(
        self,
        vault_path: str,
        drop_folder: str,
        max_size_mb: int = 100,
    ):
        # poll_interval isn't used (event-driven), but BaseWatcher requires it
        super().__init__("filesystem", vault_path, poll_interval=1)

        # Load env
        self._load_env()

        # Paths
        self.drop_folder = Path(drop_folder).expanduser().resolve()
        self.drop_folder.mkdir(parents=True, exist_ok=True)

        self.needs_action_dir = self.vault_path / "Needs_Action"
        self.needs_action_dir.mkdir(parents=True, exist_ok=True)

        # File handler
        self.handler = FileHandler(vault_path, max_size_mb)

        self.logger.info("Drop folder: %s", self.drop_folder)
        self.logger.info("Max file size: %d MB", max_size_mb)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _load_env(self) -> None:
        """Walk up from script dir to find .env."""
        search = Path(__file__).resolve().parent
        for _ in range(6):
            env_file = search / ".env"
            if env_file.exists():
                load_dotenv(env_file)
                return
            search = search.parent
        load_dotenv()

    # ------------------------------------------------------------------
    # Startup catchup — process files already in drop folder
    # ------------------------------------------------------------------

    def detect_events(self) -> List[Dict[str, Any]]:
        """Scan the drop folder for existing files (startup catchup)."""
        events: List[Dict[str, Any]] = []

        for path in sorted(self.drop_folder.iterdir()):
            if not self.handler.is_valid_file(path):
                continue
            if self._is_processed(path.name):
                continue

            info = self.handler.get_file_info(path)
            info["id"] = path.name
            info["source_path"] = str(path)
            events.append(info)

        if events:
            self.logger.info(
                "Catchup: found %d existing file(s) in drop folder", len(events)
            )

        return events

    # ------------------------------------------------------------------
    # Event processing
    # ------------------------------------------------------------------

    def handle_new_file(self, path: Path) -> None:
        """Called by the watchdog handler when a new file appears."""
        if not self.handler.is_valid_file(path):
            return

        if self._is_processed(path.name):
            self.logger.debug("Already processed: %s", path.name)
            return

        info = self.handler.get_file_info(path)
        info["id"] = path.name
        info["source_path"] = str(path)

        if self.process_event(info):
            self._mark_processed(path.name)

    def process_event(self, event: Dict[str, Any]) -> bool:
        """
        Create a FILE_{name}.md in Needs_Action/, copy to Attachments/,
        and clean up the source.
        """
        source = Path(event["source_path"])
        original_name = event["original_name"]

        # 1. Copy to Attachments/
        attachment_path = self.handler.copy_to_attachments(source)
        if not attachment_path:
            self.logger.error("Failed to copy %s — skipping", original_name)
            return False

        # 2. Create markdown action file
        safe_name = original_name.replace(" ", "_")
        filename = f"FILE_{safe_name}.md"
        file_path = self.needs_action_dir / filename

        # Handle duplicate action files
        if file_path.exists():
            stem = f"FILE_{Path(safe_name).stem}"
            suffix = ".md"
            counter = 1
            while file_path.exists():
                file_path = self.needs_action_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        try:
            content = self._build_markdown(event, attachment_path)
            file_path.write_text(content, encoding="utf-8")
            self.logger.info(
                "Created %s — file: %s (%s)",
                file_path.name, original_name, event["size_human"],
            )
        except OSError as exc:
            self.logger.error("Failed to write %s: %s", file_path.name, exc)
            return False

        # 3. Clean up source
        self.handler.cleanup_source(source)

        return True

    @staticmethod
    def _build_markdown(
        file_info: Dict[str, Any], attachment_path: Path
    ) -> str:
        """Render file info as markdown with YAML frontmatter."""
        name_escaped = str(file_info["original_name"]).replace('"', '\\"')
        rel_attachment = f"Attachments/{attachment_path.name}"

        return (
            f"---\n"
            f"type: file\n"
            f'original_name: "{name_escaped}"\n'
            f'size: "{file_info["size_human"]}"\n'
            f"mime_type: {file_info['mime_type']}\n"
            f"created_at: {file_info['created_at']}\n"
            f"status: needs_action\n"
            f"---\n"
            f"\n"
            f"## New File: {file_info['original_name']}\n"
            f"\n"
            f"**Size:** {file_info['size_human']}\n"
            f"**Type:** {file_info['mime_type']}\n"
            f"**Extension:** {file_info['extension']}\n"
            f"**Received:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %I:%M %p UTC')}\n"
            f"**Attachment:** [[{rel_attachment}]]\n"
            f"\n"
            f"### Suggested Actions\n"
            f"\n"
            f"- [ ] Review this file\n"
            f"- [ ] Forward to team\n"
            f"- [ ] Archive\n"
            f"- [ ] Delete\n"
        )

    # ------------------------------------------------------------------
    # Main loop — overrides BaseWatcher.run() with watchdog Observer
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Start the watchdog observer for real-time file monitoring.

        First processes any existing files in the drop folder (catchup),
        then watches for new files using watchdog events.
        """
        self.is_running = True

        # Catchup — process files already present
        existing = self.detect_events()
        for event in existing:
            if not self._is_processed(event["id"]):
                if self.process_event(event):
                    self._mark_processed(event["id"])

        # Start watchdog observer
        event_handler = DropFolderHandler(self)
        observer = Observer()
        observer.schedule(event_handler, str(self.drop_folder), recursive=False)
        observer.start()

        self.logger.info(
            "Watching %s for new files (Ctrl+C to stop)", self.drop_folder
        )

        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Interrupted — shutting down")
        finally:
            observer.stop()
            observer.join()
            self.is_running = False
            self.logger.info("Filesystem watcher stopped")


# ------------------------------------------------------------------
# CLI entry-point
# ------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Filesystem Watcher — monitors a drop folder for new files"
    )
    parser.add_argument(
        "--vault-path",
        default=os.getenv("VAULT_PATH", "./obsidian-vault"),
        help="Path to the Obsidian vault (default: $VAULT_PATH or ./obsidian-vault)",
    )
    parser.add_argument(
        "--drop-folder",
        default=os.getenv("DROP_FOLDER", os.path.expanduser("~/AI_Employee/Drop")),
        help="Folder to monitor for new files (default: ~/AI_Employee/Drop)",
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=100,
        help="Maximum file size in MB (default: 100)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process existing files and exit (no live monitoring)",
    )
    args = parser.parse_args()

    watcher = FilesystemWatcher(
        vault_path=args.vault_path,
        drop_folder=args.drop_folder,
        max_size_mb=args.max_size,
    )

    if args.once:
        events = watcher.detect_events()
        count = 0
        for event in events:
            if not watcher._is_processed(event["id"]):
                if watcher.process_event(event):
                    watcher._mark_processed(event["id"])
                    count += 1
        print(f"Processed {count} file(s)")
    else:
        watcher.run()


if __name__ == "__main__":
    main()
