"""Tests for loguru logging setup and API key redaction via custom sink."""

from __future__ import annotations

import io

from loguru import logger

from fetcharr.logging import create_redacting_sink, setup_logging


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
