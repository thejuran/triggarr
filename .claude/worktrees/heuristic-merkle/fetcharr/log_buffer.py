"""In-memory ring buffer for capturing recent loguru messages for the web UI.

Uses collections.deque with maxlen for automatic bounded storage.
Thread-safe via explicit locking around deque operations.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LogEntry:
    """A single captured log message."""

    timestamp: str  # ISO format string
    level: str  # e.g. "INFO", "WARNING", "ERROR"
    message: str  # The log message text (already formatted, no timestamp/level prefix)


class LogBuffer:
    """Bounded ring buffer that stores recent log entries for UI display.

    Uses a deque with maxlen for automatic eviction of oldest entries.
    """

    def __init__(self, maxlen: int = 100) -> None:
        self._entries: deque[LogEntry] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def add(self, entry: LogEntry) -> None:
        """Add a log entry to the buffer (thread-safe)."""
        with self._lock:
            self._entries.append(entry)

    def get_recent(self, limit: int = 50) -> list[LogEntry]:
        """Return the most recent log entries, newest first."""
        with self._lock:
            entries = list(self._entries)
        # Reverse to get newest first
        entries.reverse()
        return entries[:limit]

    def clear(self) -> None:
        """Clear all entries from the buffer."""
        with self._lock:
            self._entries.clear()


# Module-level singleton, created once at import time
log_buffer = LogBuffer(maxlen=200)
