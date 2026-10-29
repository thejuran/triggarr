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


def _codex_section_table_line(label: str) -> str:
    """Like _codex_table_line, but scoped to the "### Codex" table.

    Needed for labels (e.g. "Status") that also appear in the earlier
    "### BM review" table, where the unscoped lookup would return the wrong row.
    """
    text = _read()
    start = text.index("### Codex")
    end = text.index("### Greptile", start)
    section = text[start:end]
    return next(line for line in section.splitlines() if line.strip().startswith(f"| {label} |"))


def test_raw_output_paths_include_pytest_evidence() -> None:
    assert "`.pytest.txt`" in _codex_table_line("Raw output paths")


def test_codex_table_records_structured_completeness() -> None:
    line = _codex_table_line("Review complete")
    assert "review_complete" in line and "incomplete_reasons" in line


# D-16 (Phase 85 round-7 WR-01/IN-01): the Codex table needs a Fallback row
# naming the validated owner-approved-fallback record format.
def test_codex_table_has_fallback_row() -> None:
    line = _codex_table_line("Fallback")
    assert "fallback.json" in line
    assert "codex-fallback.cjs" in line


# D-16/D-18/Phase 85.1 D-12: the Raw output paths row must include
# .base-status.json plus the Phase 85.1 inspection-only outputs
# (.ci-evidence.json, .grader-provenance.json, .boundary.json), now that
# those outputs are part of the delivered record.
def test_raw_output_paths_include_new_outputs() -> None:
    line = _codex_table_line("Raw output paths")
    for output in (".base-status.json", ".ci-evidence.json", ".grader-provenance.json", ".boundary.json"):
        assert output in line, f"Raw output paths row must list {output!r}"


# Phase 85.1 (D-12, B18): an inspection-only run is complete only when the
# boundary verdict for that exact head and attempt is "verified", on top of
# the existing .status.json/.base-status.json completeness rules.
def test_status_row_defines_inspection_only_completeness() -> None:
    line = _codex_section_table_line("Status")
    assert "inspection-only" in line
    assert "`.boundary.json`" in line
    assert "verified" in line
    assert "`.base-status.json`" in line


# D-16/IN-01: "wait" and "retry later" must be stated, in one sentence, as
# blocking acceptance -- not merely as options with no stated consequence.
def test_wait_and_retry_later_block_acceptance() -> None:
    text = _read()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    assert any(
        "wait" in s.lower() and "retry later" in s.lower() and "block acceptance" in s.lower() for s in sentences
    ), "record must state in one sentence that wait and retry later block acceptance"
