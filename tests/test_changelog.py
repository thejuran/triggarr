"""Tests for the changelog parser module."""

from __future__ import annotations

from pathlib import Path

from triggarr.changelog import parse_changelog, read_changelog

SAMPLE_CHANGELOG = """\
# Changelog

## v2.6.1 (Unreleased)

* Fixes:

  * Fix Lidarr tracking HTTP 400
  * Fix redundant instance badge

## v2.6.0 (2026-04-06)

* Features:

  * Add Lidarr support as third *arr app type
  * Dashboard shows Lidarr cards

* Fixes:

  * Fix badge color in search log

## v1.0.0 (2026-02-24)

* Features:

  * Initial release
"""


def test_parse_all_versions() -> None:
    """Parser renders all version sections."""
    result = parse_changelog(SAMPLE_CHANGELOG)
    assert "v2.6.1 (Unreleased)" in result
    assert "v2.6.0 (2026-04-06)" in result
    assert "v1.0.0 (2026-02-24)" in result


def test_parse_latest_only() -> None:
    """latest_only=True returns only the first version."""
    result = parse_changelog(SAMPLE_CHANGELOG, latest_only=True)
    assert "v2.6.1 (Unreleased)" in result
    assert "v2.6.0" not in result
    assert "v1.0.0" not in result


def test_parse_categories() -> None:
    """Parser renders category headings."""
    result = parse_changelog(SAMPLE_CHANGELOG)
    assert "Features" in result
    assert "Fixes" in result


def test_parse_bullet_items() -> None:
    """Parser renders bullet list items."""
    result = parse_changelog(SAMPLE_CHANGELOG)
    assert "Add Lidarr support" in result
    assert "Fix badge color" in result
    assert "Initial release" in result


def test_parse_html_structure() -> None:
    """Parser produces proper HTML list structure."""
    result = parse_changelog(SAMPLE_CHANGELOG)
    assert "<ul" in result
    assert "<li>" in result
    assert "</ul>" in result
    assert "</li>" in result


def test_parse_version_headers_are_h3() -> None:
    """Version headers render as h3 elements."""
    result = parse_changelog(SAMPLE_CHANGELOG)
    assert "<h3" in result
    assert "v2.6.1" in result


def test_parse_category_headers_are_h4() -> None:
    """Category headers render as h4 elements."""
    result = parse_changelog(SAMPLE_CHANGELOG)
    assert "<h4" in result


def test_parse_empty_text() -> None:
    """Empty changelog text returns fallback message."""
    result = parse_changelog("")
    assert "No changelog entries found" in result


def test_parse_only_title() -> None:
    """Changelog with only the top header returns fallback."""
    result = parse_changelog("# Changelog\n")
    assert "No changelog entries found" in result


def test_parse_html_escaping_in_bullets() -> None:
    """Special characters in bullet items are HTML-escaped."""
    text = "## v1.0.0\n\n* Notes:\n\n  * Use <script> & \"quotes\" safely\n"
    result = parse_changelog(text)
    assert "&lt;script&gt;" in result
    assert "&amp;" in result
    assert "&quot;" in result


def test_parse_html_escaping_in_version_headers() -> None:
    """Special characters in version headers are HTML-escaped."""
    text = '## v1.0.0 <img onerror="alert(1)">\n\n* Notes:\n\n  * Safe\n'
    result = parse_changelog(text)
    assert "&lt;img" in result
    assert 'onerror="alert' not in result


def test_parse_html_escaping_in_categories() -> None:
    """Special characters in category headings are HTML-escaped."""
    text = "## v1.0.0\n\n* <b>Bold</b>:\n\n  * Item\n"
    result = parse_changelog(text)
    assert "&lt;b&gt;" in result


def test_read_changelog_missing_file() -> None:
    """read_changelog returns fallback when file doesn't exist."""
    result = read_changelog(path=Path("/nonexistent/CHANGELOG.md"))
    assert "not available" in result


def test_read_changelog_from_file(tmp_path: Path) -> None:
    """read_changelog reads from a real file path."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(SAMPLE_CHANGELOG)
    result = read_changelog(path=changelog)
    assert "v2.6.1" in result
    assert "v2.6.0" in result


def test_read_changelog_latest_only_from_file(tmp_path: Path) -> None:
    """read_changelog with latest_only reads only first version."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(SAMPLE_CHANGELOG)
    result = read_changelog(path=changelog, latest_only=True)
    assert "v2.6.1" in result
    assert "v2.6.0" not in result


def test_read_changelog_default_path(tmp_path: Path, monkeypatch) -> None:
    """read_changelog with no path uses the monkeypatched default."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(SAMPLE_CHANGELOG)
    monkeypatch.setattr("triggarr.changelog._DEFAULT_CHANGELOG_PATH", changelog)
    result = read_changelog()
    assert "v2.6.1" in result


def test_parse_multiple_categories_in_one_version() -> None:
    """Parser handles multiple categories within a single version."""
    result = parse_changelog(SAMPLE_CHANGELOG)
    # v2.6.0 has both Features and Fixes
    # Count h4 tags — should have at least 3 (Fixes for 2.6.1, Features+Fixes for 2.6.0)
    assert result.count("<h4") >= 3


def test_parse_separators_between_versions() -> None:
    """Each version section is wrapped in a div."""
    result = parse_changelog(SAMPLE_CHANGELOG)
    assert result.count('class="changelog-version') == 3


def test_category_regex_rejects_colons_in_bullet_text() -> None:
    """Category regex does not match bullet items that contain colons."""
    text = "## v1.0.0\n\n* Note: breaking change:\n\n  * Real item\n"
    result = parse_changelog(text)
    # "Note: breaking change:" should NOT be treated as a category
    # It should not appear as an h4
    assert "<h4" not in result or "Note: breaking change" not in result
