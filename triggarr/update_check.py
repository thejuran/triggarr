"""GitHub release update check for Triggarr.

Checks the latest GitHub release and compares against the current version.
Designed to run periodically via APScheduler (once at startup, then every 24h).
Failures are silent (debug-logged) to avoid disrupting normal operation.
"""

from __future__ import annotations

import re

import httpx
from loguru import logger

from triggarr import __version__

GITHUB_RELEASES_URL = "https://api.github.com/repos/thejuran/triggarr/releases/latest"


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of integers for comparison.

    Strips a leading 'v' if present and splits on '.'.
    Returns (0,) on any parse error.

    Args:
        version_str: Version string like "v2.3.0" or "0.1.0".

    Returns:
        Tuple of integers, e.g. (2, 3, 0).
    """
    try:
        cleaned = version_str.lstrip("v")
        if not cleaned:
            return (0,)
        # Strip pre-release suffix (e.g., "2.3.0-rc.1" -> "2.3.0")
        cleaned = cleaned.split("-", 1)[0]
        parts = []
        for part in cleaned.split("."):
            m = re.match(r"^(\d+)", part)
            if m:
                parts.append(int(m.group(1)))
        return tuple(parts) if parts else (0,)
    except (ValueError, AttributeError):
        return (0,)


async def check_for_update() -> dict | None:
    """Check GitHub for the latest release and compare against current version.

    Returns:
        Dict with latest_version, update_available, html_url on success.
        None on any error (HTTP, timeout, parse).
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                GITHUB_RELEASES_URL,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            response.raise_for_status()
            data = response.json()

            tag_name = data["tag_name"]
            html_url = data["html_url"]

            if not isinstance(html_url, str) or not html_url.startswith("https://github.com/"):
                logger.debug("Update check: unexpected html_url: {url}", url=html_url)
                return None

            latest_version = tag_name.lstrip("v")

            # Skip pre-release tags (dev, rc, alpha, beta) — only show
            # stable releases as available updates.
            if data.get("prerelease") or re.search(r"-(dev|rc|alpha|beta)", tag_name, re.IGNORECASE):
                logger.debug("Update check: skipping pre-release {tag}", tag=tag_name)
                return {
                    "latest_version": latest_version,
                    "update_available": False,
                    "html_url": html_url,
                }

            remote = _parse_version(tag_name)
            current = _parse_version(__version__)

            return {
                "latest_version": latest_version,
                "update_available": remote > current,
                "html_url": html_url,
            }
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.debug("Update check failed: {exc}", exc=exc)
        return None
