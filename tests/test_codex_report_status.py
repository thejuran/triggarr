"""Behavior tests for tests/codex_report_status.py (REVIEW-03, REVIEW-04, REVIEW-06).

Every test exercises `assess_report()` and, for the CLI cases, `main()`
directly against the schema at .claude/schemas/codex-review-findings.schema.json.
No case may ever report the review as anything other than "complete" or
"incomplete" -- the contract (D-09) forbids any other status word.
"""

from __future__ import annotations

import copy
import json

import pytest

from tests.codex_report_status import assess_report, main

H = "a" * 40  # inspected/expected head used by the valid fixture
B = "b" * 40  # inspected/expected base used by the valid fixture
WRONG_HEAD = "c" * 40
STALE_CURRENT = "d" * 40


def _finding_f001() -> dict:
    return {
        "id": "F001",
        "severity": "medium",
        "title": "Example reproduced defect",
        "file": "triggarr/example.py",
        "line_start": 10,
        "line_end": 12,
        "trigger": "Call with empty input",
        "execution_path": "handler -> validator -> crash",
        "consequence": "Unhandled exception on empty input",
        "evidence": "Traceback observed in a local run",
        "suggested_fix": "Add input validation before dereferencing",
        "reproduced": True,
        "reproduction_command": "uv run pytest tests/test_example.py::test_empty_input",
        "hypothesis": None,
    }


def _finding_f002() -> dict:
    return {
        "id": "F002",
        "severity": "low",
        "title": "Potential race condition",
        "file": "triggarr/other.py",
        "line_start": None,
        "line_end": None,
        "trigger": "Concurrent requests",
        "execution_path": "unknown -- not exercised",
        "consequence": "Possibly inconsistent state",
        "evidence": "Code inspection only",
        "suggested_fix": "Add locking around the shared write",
        "reproduced": False,
        "reproduction_command": None,
        "hypothesis": "Two concurrent writers could race on the same file",
    }


def _valid_report() -> dict:
    """A report dict with every schema field populated, head=H, base=B."""
    return {
        "schema_version": "1",
        "inspected_head_sha": H,
        "inspected_base_sha": B,
        "pr_url": "none (local checkpoint, not pushed)",
        "scope": "tests/codex_report_status.py",
        "verdict": "findings",
        "summary": "Two findings identified.",
        "coverage": ["full diff reviewed", "tests executed"],
        "exclusions": [],
        "commands_run": [
            {"command": "uv run pytest tests/ -x -q", "exit_code": 0, "purpose": "run full test suite"},
        ],
        "findings": [_finding_f001(), _finding_f002()],
        "limitations": ["No access to production data"],
    }


def _assess(report: dict, **overrides) -> object:
    """assess_report() on report, with sensible defaults for the SHA/attempt args."""
    kwargs = {
        "exit_code": 0,
        "expected_head": H,
        "expected_base": B,
        "current_head": H,
        "attempt": 1,
    }
    kwargs.update(overrides)
    return assess_report(json.dumps(report), **kwargs)


# --- Complete cases -----------------------------------------------------


def test_valid_report_is_complete() -> None:
    result = _assess(_valid_report())
    assert result.status == "complete"


def test_valid_report_reasons_empty() -> None:
    result = _assess(_valid_report())
    assert result.reasons == ()


def test_valid_report_qualified_ids() -> None:
    result = _assess(_valid_report())
    assert result.qualified_ids == (
        f"codex:{H[:12]}:a1:F001",
        f"codex:{H[:12]}:a1:F002",
    )


def test_valid_report_finding_count() -> None:
    result = _assess(_valid_report())
    assert result.finding_count == 2


def test_no_findings_is_complete() -> None:
    report = _valid_report()
    report["findings"] = []
    report["verdict"] = "no-findings"
    result = _assess(report)
    assert result.status == "complete"
    assert result.finding_count == 0
    assert result.qualified_ids == ()


# --- Missing / failed report ---------------------------------------------


def test_missing_report_none() -> None:
    result = assess_report(
        None, exit_code=0, expected_head=H, expected_base=B, current_head=H, attempt=1
    )
    assert result.status == "incomplete"
    assert any("missing report" in r for r in result.reasons)


def test_missing_report_empty_string() -> None:
    result = assess_report(
        "", exit_code=0, expected_head=H, expected_base=B, current_head=H, attempt=1
    )
    assert result.status == "incomplete"
    assert any("missing report" in r for r in result.reasons)


def test_missing_report_whitespace() -> None:
    result = assess_report(
        "   \n", exit_code=0, expected_head=H, expected_base=B, current_head=H, attempt=1
    )
    assert result.status == "incomplete"
    assert any("missing report" in r for r in result.reasons)


def test_exit_code_timeout_incomplete() -> None:
    result = _assess(_valid_report(), exit_code=124)
    assert result.status == "incomplete"
    assert any("codex exited 124" in r for r in result.reasons)


def test_exit_code_one_incomplete() -> None:
    result = _assess(_valid_report(), exit_code=1)
    assert result.status == "incomplete"
    assert any("codex exited 1" in r for r in result.reasons)


def test_exit_code_none_incomplete() -> None:
    result = _assess(_valid_report(), exit_code=None)
    assert result.status == "incomplete"
    assert any("codex exit status unknown" in r for r in result.reasons)


def test_truncated_json_incomplete() -> None:
    text = json.dumps(_valid_report())[:-5]
    result = assess_report(
        text, exit_code=0, expected_head=H, expected_base=B, current_head=H, attempt=1
    )
    assert result.status == "incomplete"
    assert any("unparseable" in r for r in result.reasons)


# --- Schema violations -----------------------------------------------------


def test_missing_top_level_field_incomplete() -> None:
    report = _valid_report()
    del report["limitations"]
    result = _assess(report)
    assert result.status == "incomplete"
    assert any("schema: missing limitations" in r for r in result.reasons)


def test_unexpected_top_level_field_incomplete() -> None:
    report = _valid_report()
    report["extra_field"] = "not part of the schema"
    result = _assess(report)
    assert result.status == "incomplete"
    assert any("schema: unexpected" in r for r in result.reasons)


def test_missing_finding_field_incomplete() -> None:
    report = _valid_report()
    del report["findings"][0]["evidence"]
    result = _assess(report)
    assert result.status == "incomplete"
    assert any("schema: finding F001 missing evidence" in r for r in result.reasons)


def test_invalid_severity_incomplete() -> None:
    report = _valid_report()
    report["findings"][0]["severity"] = "urgent"
    result = _assess(report)
    assert result.status == "incomplete"
    assert any("schema: finding F001 severity" in r for r in result.reasons)


# --- Head/base binding and staleness ---------------------------------------


def test_wrong_head_incomplete() -> None:
    report = _valid_report()
    result = _assess(report, expected_head=WRONG_HEAD, current_head=WRONG_HEAD)
    assert result.status == "incomplete"
    assert any(
        r == f"wrong commit: report inspected {H[:12]} but review was requested for {WRONG_HEAD[:12]}"
        for r in result.reasons
    )


def test_invalid_head_format_incomplete() -> None:
    report = _valid_report()
    report["inspected_head_sha"] = "not-a-real-sha"
    result = _assess(report)
    assert result.status == "incomplete"
    assert any("wrong commit" in r for r in result.reasons)


def test_wrong_base_incomplete() -> None:
    report = _valid_report()
    result = _assess(report, expected_base=WRONG_HEAD)
    assert result.status == "incomplete"
    assert any("wrong base" in r for r in result.reasons)


def test_stale_report_incomplete() -> None:
    report = _valid_report()
    result = _assess(report, current_head=STALE_CURRENT)
    assert result.status == "incomplete"
    assert any(
        r == f"stale: report is for {H[:12]}, current head is {STALE_CURRENT[:12]}" for r in result.reasons
    )


# --- Finding consistency rules ----------------------------------------------


def test_reproduced_without_command_incomplete() -> None:
    report = _valid_report()
    report["findings"][0]["reproduction_command"] = None
    result = _assess(report)
    assert result.status == "incomplete"
    assert any("F001 marked reproduced without a reproduction command" in r for r in result.reasons)


def test_unreproduced_without_hypothesis_incomplete() -> None:
    report = _valid_report()
    report["findings"][1]["hypothesis"] = None
    result = _assess(report)
    assert result.status == "incomplete"
    assert any("F002 unreproduced without a hypothesis" in r for r in result.reasons)


def test_empty_coverage_incomplete() -> None:
    report = _valid_report()
    report["coverage"] = []
    result = _assess(report)
    assert result.status == "incomplete"
    assert any("no coverage stated" in r for r in result.reasons)


def test_duplicate_finding_id_incomplete() -> None:
    report = _valid_report()
    report["findings"][1]["id"] = "F001"
    result = _assess(report)
    assert result.status == "incomplete"
    assert any("duplicate finding id" in r for r in result.reasons)


# --- Multiple simultaneous failures -----------------------------------------


def test_multiple_failures_all_reasons_listed_and_stable() -> None:
    report = _valid_report()
    del report["limitations"]
    report["inspected_head_sha"] = WRONG_HEAD
    text = json.dumps(report)

    result = assess_report(
        text, exit_code=1, expected_head=H, expected_base=B, current_head=H, attempt=1
    )
    assert result.status == "incomplete"
    assert result.reasons[0] == "codex exited 1"
    assert any("schema: missing limitations" in r for r in result.reasons)
    assert any(r.startswith("wrong commit:") for r in result.reasons)

    # Re-running on the identical input must produce the identical reason order.
    result_again = assess_report(
        text, exit_code=1, expected_head=H, expected_base=B, current_head=H, attempt=1
    )
    assert result.reasons == result_again.reasons


# --- Never "clean" -----------------------------------------------------------


def test_never_reports_clean() -> None:
    scenarios = [
        (None, {}),
        (json.dumps(_valid_report())[:-5], {}),
        (json.dumps(_valid_report()), {"exit_code": 124}),
        (json.dumps(_valid_report()), {"expected_head": WRONG_HEAD, "current_head": WRONG_HEAD}),
        (json.dumps(_valid_report()), {"current_head": STALE_CURRENT}),
        (json.dumps(_valid_report()), {}),
    ]
    for report_text, overrides in scenarios:
        kwargs = {
            "exit_code": 0,
            "expected_head": H,
            "expected_base": B,
            "current_head": H,
            "attempt": 1,
        }
        kwargs.update(overrides)
        result = assess_report(report_text, **kwargs)
        combined = result.status + " " + " ".join(result.reasons)
        assert "clean" not in combined.lower()


# --- CLI ----------------------------------------------------------------


def test_cli_complete_exits_zero(tmp_path, capsys) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(_valid_report()), encoding="utf-8")

    exit_code = main(
        [
            "--report",
            str(report_path),
            "--exit-code",
            "0",
            "--expected-head",
            H,
            "--expected-base",
            B,
            "--current-head",
            H,
            "--attempt",
            "1",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "complete"


def test_cli_missing_report_exits_one(tmp_path, capsys) -> None:
    missing_path = tmp_path / "does-not-exist.json"

    exit_code = main(
        [
            "--report",
            str(missing_path),
            "--exit-code",
            "0",
            "--expected-head",
            H,
            "--expected-base",
            B,
            "--current-head",
            H,
            "--attempt",
            "1",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "missing report" in captured.out


def test_cli_invalid_expected_head_exits_two() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--report",
                "/nonexistent",
                "--exit-code",
                "0",
                "--expected-head",
                "abc",
                "--expected-base",
                B,
                "--current-head",
                H,
                "--attempt",
                "1",
            ]
        )
    assert exc_info.value.code == 2


def test_fixture_is_independent_per_call() -> None:
    """Guard against accidental fixture-sharing bugs in these tests themselves."""
    a = _valid_report()
    b = _valid_report()
    a["findings"][0]["severity"] = "urgent"
    assert b["findings"][0]["severity"] == "medium"
    assert copy.deepcopy(a) == a
