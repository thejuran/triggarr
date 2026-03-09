"""Loguru logging setup with API key redaction via custom sink.

Uses a custom sink function (not a filter) so that the COMPLETE formatted
output -- including exception tracebacks -- is redacted.  A filter only
sees ``record["message"]`` and cannot redact secrets that appear in
stack traces (e.g. httpx exception messages containing API keys).
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from loguru import logger

from fetcharr.log_buffer import LogEntry, log_buffer


def create_redacting_sink(secrets: list[str], stream=sys.stderr) -> Callable:
    """Create a loguru sink that redacts secrets from the full formatted output.

    Unlike a filter (which only sees record["message"]), a custom sink
    receives the COMPLETE formatted string including exception tracebacks.
    This ensures API keys that appear in httpx exception messages or
    stack traces are also redacted.

    Args:
        secrets: List of secret values to redact.
        stream: Output stream (defaults to stderr).

    Returns:
        A loguru-compatible sink function.
    """

    def sink(message):
        text = str(message)
        for secret in secrets:
            if secret:
                text = text.replace(secret, "[REDACTED]")
        stream.write(text)
        stream.flush()

    return sink


def setup_logging(level: str, secrets: list[str]) -> None:
    """Configure loguru with human-readable format and secret redaction.

    Removes the default handler and adds a new handler using a custom
    redacting sink that processes the full formatted output including
    exception tracebacks.

    - Format: ``2026-02-23 14:30:00 INFO     Connected to Radarr``
    - Configurable log level
    - Automatic redaction of all secret values in messages AND tracebacks

    Args:
        level: Log level string (e.g. "info", "debug", "warning").
        secrets: List of secret values to redact from all log output.
    """
    logger.remove()
    logger.add(
        create_redacting_sink(secrets),
        format="{time:YYYY-MM-DD HH:mm:ss} {level:<8} {message}",
        level=level.upper(),
        colorize=False,  # Custom sink function, not a stream -- no ANSI auto-detect
    )

    # Buffer sink: captures log messages for the web UI log viewer.
    # Secrets are redacted before storing in the buffer.
    def buffer_sink(message) -> None:
        text = message.record["message"]
        for secret in secrets:
            if secret:
                text = text.replace(secret, "[REDACTED]")
        entry = LogEntry(
            timestamp=message.record["time"].strftime("%Y-%m-%d %H:%M:%S"),
            level=message.record["level"].name,
            message=text,
        )
        log_buffer.add(entry)

    logger.add(buffer_sink, level=level.upper(), format="{message}")
