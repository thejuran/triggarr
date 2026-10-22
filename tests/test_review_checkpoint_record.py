"""Drift guards for docs/review-checkpoint-record.md (REVIEW-06, IN-06, Codex F002)."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORD = REPO_ROOT / "docs" / "review-checkpoint-record.md"

_GH_API_PATCH_RE = re.compile(r"gh api --method PATCH[^\n`]*")


def _read() -> str:
    return RECORD.read_text(encoding="utf-8")


# Codex F002: `gh api --method PATCH ... --field body@FILE` fails argument
# parsing with "invalid key" -- `--field`/`-F` needs `key=value` syntax, so
# a file reference must be `body=@FILE`, never `body@FILE`.
def test_comment_update_command_uses_valid_field_syntax() -> None:
    text = _read()
    match = _GH_API_PATCH_RE.search(text)
    assert match, "no `gh api --method PATCH ...` command found in the checkpoint record"
    command = match.group(0)
    assert "body@FILE" not in command, f"invalid --field syntax (missing '='): {command!r}"
    assert re.search(r"(-F|--field)\s+body=@FILE", command), f"expected 'body=@FILE' syntax, got: {command!r}"


# IN-06: the contract's failure rule allows an owner-approved attempt beyond 2
# ("retry later"), but the template's Attempts row implied only 1 or 2 ever occur.
def test_attempts_row_allows_owner_approved_retry() -> None:
    text = _read()
    assert "| Attempts |" in text
    attempts_line = next(line for line in text.splitlines() if line.strip().startswith("| Attempts |"))
    assert "owner-approved" in attempts_line, f"Attempts row must mention an owner-approved retry: {attempts_line!r}"


# Durable Codex completeness (owner 2026-10-22): the record carries the v2
# completeness fields and the harness test-evidence file.
def _codex_table_line(label: str) -> str:
    return next(line for line in _read().splitlines() if line.strip().startswith(f"| {label} |"))


def test_raw_output_paths_include_pytest_evidence() -> None:
    assert "`.pytest.txt`" in _codex_table_line("Raw output paths")


def test_codex_table_records_structured_completeness() -> None:
    line = _codex_table_line("Review complete")
    assert "review_complete" in line and "incomplete_reasons" in line
