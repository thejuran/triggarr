"""Changelog parser — reads CHANGELOG.md and converts to HTML.

Follows the Tautulli model: a local CHANGELOG.md shipped in the repo
is read from disk at runtime and rendered to styled HTML.  No external
API calls, no rate limits, works offline.

The expected format is:

    # Changelog

    ## v2.6.0 (2026-04-06)

    * Features:

      * First feature
      * Second feature

    * Fixes:

      * First fix
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from loguru import logger

# Default location: repo root (one level up from this file's package dir).
_DEFAULT_CHANGELOG_PATH = Path(__file__).resolve().parent.parent / "CHANGELOG.md"

# Patterns
_VERSION_HEADER = re.compile(r"^##\s+(.+)$")
_CATEGORY_ITEM = re.compile(r"^\*\s+([^:]+):\s*$")
_BULLET_ITEM = re.compile(r"^\s+\*\s+(.+)$")


def read_changelog(
    path: Path | None = None,
    latest_only: bool = False,
) -> str:
    """Read CHANGELOG.md and return rendered HTML.

    Args:
        path: Path to CHANGELOG.md.  Defaults to repo root.
        latest_only: If True, return only the first version section.

    Returns:
        HTML string with version sections, category headings, and
        bullet lists.  Returns a graceful fallback message if the
        file is missing or unreadable.
    """
    changelog_path = path or _DEFAULT_CHANGELOG_PATH

    if not changelog_path.is_file():
        logger.warning("Changelog file not found: {path}", path=changelog_path)
        return '<p class="text-triggarr-muted">Changelog not available.</p>'

    try:
        text = changelog_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to read changelog: {exc}", exc=exc)
        return '<p class="text-triggarr-muted">Changelog not available.</p>'

    return parse_changelog(text, latest_only=latest_only)


def parse_changelog(text: str, *, latest_only: bool = False) -> str:
    """Parse changelog markdown text into HTML.

    Handles:
    - ``## vX.Y.Z (date)`` → version header
    - ``* Category:`` → category subheading
    - ``  * Item text`` → bullet list item
    """
    lines = text.splitlines()
    parts: list[str] = []
    in_list = False
    version_count = 0

    for line in lines:
        # Skip top-level "# Changelog" header
        if line.strip().startswith("# ") and "changelog" in line.lower():
            continue

        # Version header: ## v2.6.0 (2026-04-06)
        version_match = _VERSION_HEADER.match(line)
        if version_match:
            if latest_only and version_count >= 1:
                break
            # Close any open list
            if in_list:
                parts.append("</ul>")
                in_list = False
            if version_count > 0:
                # Add separator between versions
                parts.append("</div>")
            version_count += 1
            header_text = html.escape(version_match.group(1))
            parts.append('<div class="changelog-version mb-6">')
            parts.append(f'<h3 class="text-lg font-semibold text-white mb-3">{header_text}</h3>')
            continue

        # Category line: * Features:
        category_match = _CATEGORY_ITEM.match(line)
        if category_match:
            if in_list:
                parts.append("</ul>")
                in_list = False
            cat_text = html.escape(category_match.group(1))
            parts.append(
                f'<h4 class="text-sm font-medium text-triggarr-green mt-3 mb-1">{cat_text}</h4>'
            )
            continue

        # Bullet item:   * Some change description
        bullet_match = _BULLET_ITEM.match(line)
        if bullet_match:
            if not in_list:
                parts.append('<ul class="list-disc list-inside text-sm text-triggarr-muted space-y-1 ml-2">')
                in_list = True
            item_text = html.escape(bullet_match.group(1))
            parts.append(f"<li>{item_text}</li>")
            continue

    # Close any trailing open tags
    if in_list:
        parts.append("</ul>")
    if version_count > 0:
        parts.append("</div>")

    if not parts:
        return '<p class="text-triggarr-muted">No changelog entries found.</p>'

    return "\n".join(parts)
