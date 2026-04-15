"""Input validation helpers for the Triggarr web UI.

Provides URL scheme + SSRF validation, integer clamping with safe bounds,
log level allowlisting, and instance name validation for the settings form.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

# Instance name validation pattern: starts with alphanumeric, then allows
# alphanumeric, spaces, single underscores, dots, and hyphens.
_INSTANCE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9 _.\-]*$")

# Hostnames explicitly blocked to prevent SSRF against cloud metadata services.
BLOCKED_HOSTS: set[str] = {"169.254.169.254", "metadata.google.internal", "metadata.azure.com", "100.100.100.200"}

# Only these log levels are accepted; anything else defaults to "info".
ALLOWED_LOG_LEVELS: set[str] = {"debug", "info", "warning", "error"}


def validate_instance_name(name: str) -> tuple[bool, str]:
    """Validate a user-supplied instance name.

    Names must be 1-32 chars, start with an alphanumeric character,
    and may contain letters, digits, spaces, single underscores, dots,
    and hyphens.  Double underscores are forbidden because they serve
    as the form-field separator in the settings UI.

    Args:
        name: The raw instance name string.

    Returns:
        A ``(valid, error_message)`` tuple.
    """
    stripped = name.strip()
    if not stripped:
        return (False, "Instance name cannot be empty")
    if len(stripped) > 32:
        return (False, "Instance name too long (max 32 characters)")
    if "__" in stripped:
        return (False, "Instance name cannot contain double underscores")
    if not _INSTANCE_NAME_RE.match(stripped):
        return (False, "Instance name must start with alphanumeric character and use valid characters only")
    return (True, "")


def validate_arr_url(url: str) -> tuple[bool, str]:
    """Validate a user-supplied *arr application URL.

    Empty URLs are allowed (app is disabled). Otherwise the URL must use
    http or https, have a hostname, and not point at cloud metadata or
    link-local addresses. Private-network IPs (10.x, 192.168.x, etc.)
    are intentionally allowed because *arr apps run on local networks.

    Args:
        url: The URL string from the settings form.

    Returns:
        A ``(valid, error_message)`` tuple. ``valid`` is True when the URL
        is acceptable; ``error_message`` is empty on success.
    """
    if not url or not url.strip():
        return (True, "")

    parsed = urlparse(url.strip())

    if parsed.scheme not in {"http", "https"}:
        return (False, "URL scheme must be http or https")

    hostname = parsed.hostname
    if hostname is None:
        return (False, "URL has no hostname")

    if hostname in BLOCKED_HOSTS:
        return (False, "Blocked hostname")

    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_link_local or addr.is_loopback or addr.is_unspecified or addr.is_multicast:
            return (False, "Blocked address")
        # Check IPv4-mapped IPv6 addresses (e.g., ::ffff:127.0.0.1) per D-10
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
            mapped = addr.ipv4_mapped
            if mapped.is_link_local or mapped.is_loopback or mapped.is_unspecified or mapped.is_multicast:
                return (False, "Blocked address")
    except ValueError:
        # Not an IP literal (e.g. "radarr") -- perfectly fine.
        pass

    return (True, "")


def safe_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    """Parse a form value as an integer, clamped to ``[minimum, maximum]``.

    Returns *default* when the value is None, empty, or unparseable.

    Args:
        value: Raw form string (may be None).
        default: Fallback when *value* is missing or invalid.
        minimum: Lower bound (inclusive).
        maximum: Upper bound (inclusive).

    Returns:
        An integer guaranteed to be within ``[minimum, maximum]``.
    """
    if value is None or value == "":
        return default
    try:
        n = int(value)
    except (ValueError, TypeError):
        return default
    return max(minimum, min(maximum, n))


def safe_log_level(value: str | None) -> str:
    """Return *value* if it is a recognised log level, otherwise ``"info"``.

    The check is case-insensitive and strips surrounding whitespace.

    Args:
        value: Raw form string (may be None).

    Returns:
        A lowercase log-level string from :data:`ALLOWED_LOG_LEVELS`.
    """
    if value is None:
        return "info"
    cleaned = value.strip().lower()
    if cleaned in ALLOWED_LOG_LEVELS:
        return cleaned
    return "info"
