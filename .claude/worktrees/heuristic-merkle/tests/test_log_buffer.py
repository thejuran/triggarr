"""Test suite for the in-memory log buffer.

Covers add/get, maxlen eviction, clear, limit, and thread safety.
"""

from __future__ import annotations

import threading

from fetcharr.log_buffer import LogBuffer, LogEntry


def _make_entry(n: int, level: str = "INFO") -> LogEntry:
    """Helper to create a LogEntry with a numbered message."""
    return LogEntry(timestamp=f"2026-01-01 00:00:{n:02d}", level=level, message=f"msg-{n}")


def test_log_buffer_add_and_get():
    """Adding entries and retrieving them returns newest-first order."""
    buf = LogBuffer(maxlen=10)
    buf.add(_make_entry(1))
    buf.add(_make_entry(2))
    buf.add(_make_entry(3))

    entries = buf.get_recent()
    assert len(entries) == 3
    assert entries[0].message == "msg-3"  # newest first
    assert entries[1].message == "msg-2"
    assert entries[2].message == "msg-1"


def test_log_buffer_maxlen_evicts_oldest():
    """Buffer with maxlen=3 evicts oldest entries when full."""
    buf = LogBuffer(maxlen=3)
    for i in range(5):
        buf.add(_make_entry(i))

    entries = buf.get_recent()
    assert len(entries) == 3
    # Only entries 2, 3, 4 remain (0 and 1 evicted)
    assert entries[0].message == "msg-4"
    assert entries[1].message == "msg-3"
    assert entries[2].message == "msg-2"


def test_log_buffer_clear():
    """Clearing the buffer removes all entries."""
    buf = LogBuffer(maxlen=10)
    buf.add(_make_entry(1))
    buf.add(_make_entry(2))
    buf.clear()

    entries = buf.get_recent()
    assert entries == []


def test_log_buffer_get_recent_limit():
    """get_recent with limit returns only that many entries."""
    buf = LogBuffer(maxlen=20)
    for i in range(10):
        buf.add(_make_entry(i))

    entries = buf.get_recent(limit=3)
    assert len(entries) == 3
    assert entries[0].message == "msg-9"  # newest first


def test_log_buffer_thread_safe():
    """Adding entries from multiple threads does not raise exceptions."""
    buf = LogBuffer(maxlen=500)
    errors: list[Exception] = []

    def add_entries(start: int) -> None:
        try:
            for i in range(100):
                buf.add(_make_entry(start + i))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=add_entries, args=(i * 100,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread safety errors: {errors}"
    entries = buf.get_recent(limit=500)
    assert len(entries) == 500  # 5 threads x 100 entries each


def test_log_entry_frozen():
    """LogEntry is immutable (frozen dataclass)."""
    entry = LogEntry(timestamp="2026-01-01", level="INFO", message="test")
    try:
        entry.message = "changed"  # type: ignore[misc]
        raise AssertionError("LogEntry should be frozen")
    except AttributeError:
        pass  # Expected -- frozen dataclass


def test_log_buffer_empty_get_recent():
    """get_recent on empty buffer returns empty list."""
    buf = LogBuffer(maxlen=10)
    assert buf.get_recent() == []
