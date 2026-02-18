"""
Base Watcher Module

Standalone abstract base class for watcher implementations.
Provides polling loop, rotating file logging, exponential backoff
with jitter for API rate limits, and JSON-based deduplication.

No external dependencies — uses Python stdlib only.
"""

import json
import logging
import logging.handlers
import random
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, List, Dict


class BaseWatcher(ABC):
    """
    Abstract base class for all standalone watcher implementations.

    Subclasses must implement:
        - detect_events() -> list[dict]
        - process_event(event: dict) -> bool
    """

    def __init__(self, name: str, vault_path: str, poll_interval: int = 120):
        self.name = name
        self.vault_path = Path(vault_path)
        self.poll_interval = poll_interval
        self.is_running = False

        # Setup logging and dedup
        self.logger = self._setup_logging()
        self.processed_ids_path = self.vault_path / "Logs" / "processed_ids.json"
        self.processed_ids: set = self._load_processed_ids()

    def _setup_logging(self) -> logging.Logger:
        """Configure rotating file + console logging."""
        logs_dir = self.vault_path / "Logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger(f"watcher.{self.name}")
        logger.setLevel(logging.DEBUG)

        # Avoid adding duplicate handlers on re-init
        if logger.handlers:
            return logger

        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

        # Rotating file handler — 5 MB, keep 3 backups
        fh = logging.handlers.RotatingFileHandler(
            logs_dir / f"{self.name}_watcher.log",
            maxBytes=5_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

        return logger

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _load_processed_ids(self) -> set:
        """Load previously processed IDs from JSON file."""
        try:
            if self.processed_ids_path.exists():
                data = json.loads(self.processed_ids_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return set(data)
        except (json.JSONDecodeError, OSError) as exc:
            self.logger.warning("Could not load processed IDs: %s — starting fresh", exc)
        return set()

    def _save_processed_ids(self) -> None:
        """Persist processed IDs to JSON file."""
        try:
            self.processed_ids_path.parent.mkdir(parents=True, exist_ok=True)
            self.processed_ids_path.write_text(
                json.dumps(sorted(self.processed_ids), indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            self.logger.error("Failed to save processed IDs: %s", exc)

    def _is_processed(self, item_id: str) -> bool:
        return item_id in self.processed_ids

    def _mark_processed(self, item_id: str) -> None:
        self.processed_ids.add(item_id)
        self._save_processed_ids()

    # ------------------------------------------------------------------
    # Exponential backoff
    # ------------------------------------------------------------------

    def execute_with_backoff(
        self,
        func: Callable[..., Any],
        *args: Any,
        max_retries: int = 5,
        base_delay: float = 2.0,
        max_delay: float = 64.0,
    ) -> Any:
        """
        Execute *func* with exponential backoff on retryable errors.

        Retries on HTTP 429 (rate limit) and 5xx (server error).
        All other exceptions are re-raised immediately.
        """
        last_exc: Exception | None = None

        for attempt in range(max_retries):
            try:
                return func(*args)
            except Exception as exc:
                last_exc = exc
                status = getattr(exc, "status_code", None) or getattr(exc, "resp", {}).get("status")

                # Convert to int for comparison
                try:
                    status = int(status) if status is not None else None
                except (ValueError, TypeError):
                    status = None

                if status is not None and (status == 429 or status >= 500):
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                    self.logger.warning(
                        "Retryable error (HTTP %s), retrying in %.1fs (attempt %d/%d): %s",
                        status, delay, attempt + 1, max_retries, exc,
                    )
                    time.sleep(delay)
                else:
                    raise

        self.logger.error("All %d retries exhausted", max_retries)
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def detect_events(self) -> List[Dict[str, Any]]:
        """Return a list of new event dicts (empty list if none)."""
        ...

    @abstractmethod
    def process_event(self, event: Dict[str, Any]) -> bool:
        """Process a single event. Return True on success."""
        ...

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the polling loop."""
        self.is_running = True
        self.logger.info(
            "Starting %s watcher (polling every %ds)", self.name, self.poll_interval
        )

        try:
            while self.is_running:
                try:
                    events = self.detect_events()
                    for event in events:
                        eid = event.get("id", "")
                        if not eid or self._is_processed(eid):
                            continue
                        if self.process_event(event):
                            self._mark_processed(eid)
                except Exception as exc:
                    self.logger.error("Error during poll cycle: %s", exc, exc_info=True)

                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            self.logger.info("Interrupted — shutting down")
        finally:
            self.is_running = False
            self.logger.info("%s watcher stopped", self.name)

    def stop(self) -> None:
        """Signal the polling loop to stop."""
        self.is_running = False
