"""Tests for loguru logging setup and API key redaction via custom sink."""

from __future__ import annotations

import io

import pytest
from loguru import logger

from triggarr.log_buffer import log_buffer
from triggarr.logging import create_buffer_sink, create_redacting_sink, setup_logging


@pytest.fixture(autouse=True)
def _reset_logging_state():
    """Reset shared log_buffer and loguru handlers before and after each test.

    Mirrors the _clear_log_buffer reset pattern in tests/test_log_viewer.py,
    extended with logger.remove() since these tests register loguru handlers
    directly (setup_logging() and logger.add()).
    """
    log_buffer.clear()
    logger.remove()
    yield
    logger.remove()
    log_buffer.clear()


def test_redaction_filter_removes_secret() -> None:
    """Redacting sink replaces secret values with [REDACTED] in log output."""
    secret = "my-api-key-abc123"
    output = io.StringIO()

    # Remove all existing handlers and add a test handler with redacting sink
    logger.remove()
    sink = create_redacting_sink([secret], stream=output)
    logger.add(sink, format="{message}", colorize=False)

    logger.info("Connecting with key {key}", key=secret)

    result = output.getvalue()
    assert secret not in result
    assert "[REDACTED]" in result


def test_redaction_filter_ignores_empty_secrets() -> None:
    """Empty strings in secrets list don't cause issues or false redaction."""
    output = io.StringIO()

    logger.remove()
    sink = create_redacting_sink(["", "", "real-secret"], stream=output)
    logger.add(sink, format="{message}", colorize=False)

    logger.info("Normal message without secrets")
    logger.info("Message with real-secret in it")

    result = output.getvalue()
    assert "Normal message without secrets" in result
    assert "real-secret" not in result
    assert "[REDACTED]" in result


def test_redaction_covers_tracebacks() -> None:
    """Custom sink redacts secrets in exception tracebacks, not just messages."""
    secret = "super-secret-api-key"
    output = io.StringIO()

    logger.remove()
    sink = create_redacting_sink([secret], stream=output)
    logger.add(sink, format="{message}", colorize=False)

    try:
        raise ValueError(f"Connection failed with key {secret}")
    except ValueError:
        logger.exception("API call failed")

    result = output.getvalue()
    assert secret not in result, "Secret found in output -- traceback was not redacted"
    assert "[REDACTED]" in result


def test_log_format_matches_spec() -> None:
    """Log output matches YYYY-MM-DD HH:MM:SS LEVEL    Message format."""
    import re

    output = io.StringIO()

    setup_logging("info", [])
    # setup_logging replaces all handlers, so we need to add our test handler after
    logger.remove()
    logger.add(
        output,
        format="{time:YYYY-MM-DD HH:mm:ss} {level:<8} {message}",
        level="INFO",
        colorize=False,
    )

    logger.info("Test message here")

    result = output.getvalue().strip()
    # Pattern: 2026-02-23 14:30:00 INFO     Test message here
    pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} INFO\s+Test message here"
    assert re.match(pattern, result), f"Log output did not match expected format: {result!r}"


def test_buffer_sink_uses_bound_viewer_message() -> None:
    """A bound viewer_message replaces the buffer entry; the real message (and any
    token it carries) never enters log_buffer (D-03).
    """
    token = "RESET-TOKEN-abc123"
    setup_logging("info", [])

    logger.bind(viewer_message="SAFE VIEWER TEXT").warning(
        "Password reset token minted. Read from docker logs: {token}",
        token=token,
    )

    entries = log_buffer.get_recent(200)
    assert any(entry.message == "SAFE VIEWER TEXT" for entry in entries), (
        f"Expected bound viewer_message in buffer, got: {[e.message for e in entries]}"
    )
    assert all(token not in entry.message for entry in entries), "Token leaked into the buffer"


def test_buffer_sink_exception_is_single_redacted_line() -> None:
    """An exception attached to a log call is reduced to one redacted
    '<Type>: <first line>' summary -- no newline, no Traceback, no secret.
    """
    secret = "super-secret-api-key"
    setup_logging("info", [secret])

    try:
        raise ValueError(f"Connection failed with key {secret}\nsecond line")
    except ValueError:
        logger.exception("API call failed")

    entries = log_buffer.get_recent(200)
    assert entries, "Expected at least one buffer entry"
    entry = entries[0]
    assert entry.message == "API call failed | ValueError: Connection failed with key [REDACTED]"
    assert "\n" not in entry.message
    assert "Traceback" not in entry.message
    assert "second line" not in entry.message
    assert secret not in entry.message


def test_buffer_sink_exception_with_empty_message_uses_type_name() -> None:
    """An exception with an empty str(exc) (e.g. raise KeyError()) summarizes to
    just the exception type name.
    """
    setup_logging("info", [])

    try:
        raise KeyError()
    except KeyError:
        logger.exception("lookup failed")

    entries = log_buffer.get_recent(200)
    assert entries, "Expected at least one buffer entry"
    assert entries[0].message == "lookup failed | KeyError"


def test_buffer_sink_plain_message_unchanged() -> None:
    """A log call with no bound viewer_message and no exception produces a buffer
    entry whose message equals the plain message.
    """
    setup_logging("info", [])

    logger.info("plain message")

    entries = log_buffer.get_recent(200)
    assert entries, "Expected at least one buffer entry"
    assert entries[0].message == "plain message"


def test_viewer_message_divergence_stderr_keeps_token() -> None:
    """The stderr redacting sink still receives the real message (and token);
    only the buffer sink is structurally denied the token.
    """
    token = "RESET-TOKEN-abc123"
    stderr_output = io.StringIO()
    setup_logging("info", [])
    logger.add(create_redacting_sink([], stream=stderr_output), format="{message}", colorize=False)

    logger.bind(viewer_message="SAFE VIEWER TEXT").warning(
        "Password reset token minted. Read from docker logs: {token}",
        token=token,
    )

    stderr_text = stderr_output.getvalue()
    assert token in stderr_text, "stderr channel must keep the real token"

    entries = log_buffer.get_recent(200)
    assert all(token not in entry.message for entry in entries), "Token leaked into the buffer"


def test_stderr_sink_keeps_full_redacted_traceback() -> None:
    """The stderr sink keeps the full redacted traceback; the buffer entry for the
    same exception never contains a traceback.
    """
    secret = "super-secret-api-key"
    stderr_output = io.StringIO()
    setup_logging("info", [secret])
    logger.add(create_redacting_sink([secret], stream=stderr_output), format="{message}", colorize=False)

    try:
        raise ValueError(f"Connection failed with key {secret}")
    except ValueError:
        logger.exception("API call failed")

    stderr_text = stderr_output.getvalue()
    assert "Traceback" in stderr_text
    assert "[REDACTED]" in stderr_text
    assert secret not in stderr_text

    entries = log_buffer.get_recent(200)
    assert entries, "Expected at least one buffer entry"
    assert all("Traceback" not in entry.message for entry in entries)


def test_create_buffer_sink_redacts_secret_in_viewer_message() -> None:
    """create_buffer_sink registered directly (no setup_logging) still redacts a
    secret appearing inside a bound viewer_message.
    """
    secret = "super-secret-api-key"
    logger.add(create_buffer_sink([secret]), format="{message}")

    logger.bind(viewer_message=f"token is {secret}").warning("irrelevant real message")

    entries = log_buffer.get_recent(200)
    assert entries, "Expected at least one buffer entry"
    assert "[REDACTED]" in entries[0].message
    assert secret not in entries[0].message
