"""Loguru logging setup with API key redaction via custom sink.

Uses a custom sink function (not a filter) so that the COMPLETE formatted
output -- including a raised exception's traceback -- is redacted.  A filter only
sees ``record["message"]`` and cannot redact secrets that appear in
stack traces (e.g. httpx exception messages containing API keys).
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import IO, Any

from loguru import logger

from triggarr.log_buffer import LogEntry, log_buffer


def _redact(text: str, secrets: list[str]) -> str:
    """Replace every configured secret value with [REDACTED] in text."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text


def create_redacting_sink(secrets: list[str], stream: IO[str] = sys.stderr) -> Callable[[str], None]:
    """Create a loguru sink that redacts secrets from the full formatted output.

    Unlike a filter (which only sees record["message"]), a custom sink
    receives the COMPLETE formatted string including a raised exception's traceback.
    This ensures API keys that appear in httpx exception messages or
    stack traces are also redacted.

    Args:
        secrets: List of secret values to redact.
        stream: Output stream (defaults to stderr).

    Returns:
        A loguru-compatible sink function.
    """

    def sink(message: Any) -> None:
        text = _redact(str(message), secrets)
        stream.write(text)
        stream.flush()

    return sink


def _exception_summary(exception: Any) -> str:
    """Return a one-line "<ExceptionType>: <first line>" summary for a loguru
    record's exception info, or "" when there is no exception.

    Never touches the exception's traceback attribute -- the owner's global rule
    forbids exposing stack traces to end users, so full tracebacks stay on the
    stderr redacting sink only. This only looks at the exception's type and
    the first line of its string form.
    """
    if exception is None:
        return ""
    name = exception.type.__name__ if exception.type is not None else "Exception"
    value_text = str(exception.value)
    first = value_text.splitlines()[0].strip() if value_text else ""
    return f"{name}: {first}" if first else name


def create_buffer_sink(secrets: list[str]) -> Callable[[Any], None]:
    """Create the web-UI log-buffer sink.

    Four things a future maintainer must know:

    1. When a log call binds "viewer_message" (via ``logger.bind(viewer_message=...)``),
       this sink reads ONLY that bound text for the viewer -- the real
       ``record["message"]`` is never read in that case. This is a structural
       guarantee, not post-hoc scrubbing: a value kept out of
       ``viewer_message`` can never reach this buffer (D-03).
    2. When the record carries an exception, it is reduced to a single
       redacted "<Type>: <first line>" summary, because the owner's global
       rule forbids exposing stack traces or internal error details to end
       users. Full tracebacks are emitted only by the stderr redacting sink
       (create_redacting_sink), never here.
    3. Every kwarg passed to a loguru call lands in ``record["extra"]``,
       independent of message formatting -- this sink reads only the single
       named "viewer_message" key and must never serialize or dump
       ``record["extra"]`` wholesale, since arbitrary kwargs (e.g. a bound
       "token") may live there.
    4. Secret redaction runs over the fully joined text (base message plus
       exception summary), so a secret appearing in either half is still
       caught.

    Args:
        secrets: List of secret values to redact.

    Returns:
        A loguru-compatible sink function.
    """

    def sink(message: Any) -> None:
        record = message.record
        viewer_message = record["extra"].get("viewer_message")
        base = str(viewer_message) if viewer_message is not None else record["message"]

        summary = _exception_summary(record["exception"])
        text = f"{base} | {summary}" if summary else base

        # Defensively collapse any remaining line breaks so a buffer entry is
        # always exactly one line, even if base or summary somehow contain one.
        text = " ".join(text.splitlines())

        text = _redact(text, secrets)

        entry = LogEntry(
            timestamp=record["time"].strftime("%Y-%m-%d %H:%M:%S"),
            level=record["level"].name,
            message=text,
        )
        log_buffer.add(entry)

    return sink


def setup_logging(level: str, secrets: list[str]) -> None:
    """Configure loguru with human-readable format and secret redaction.

    Removes the default handler and adds two sinks:

    - A redacting sink writing the full formatted output (including a
      raised exception's traceback) to stderr, for the operator channel
      (e.g. ``docker logs``).
    - A buffer sink feeding the web UI log viewer: entries are always a
      single redacted line -- either a bound "viewer_message" or the plain
      message, plus at most one redacted "<Type>: <first line>" exception
      summary. No raw tracebacks ever reach the buffer.

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

    logger.add(create_buffer_sink(secrets), level=level.upper(), format="{message}")
