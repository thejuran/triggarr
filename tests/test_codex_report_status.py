"""Behavior tests for tests/codex_report_status.py (REVIEW-03, REVIEW-04, REVIEW-06).

Every test exercises `assess_report()` and, for the CLI cases, `main()`
directly against the schema at .claude/schemas/codex-review-findings.schema.json.
No case may ever report the review as anything other than "complete" or
"incomplete" -- the contract (D-09) forbids any other status word.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

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
    """A schema v2 report with every field populated, head=H, base=B."""
    return {
        "schema_version": "2",
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
        "review_complete": True,
        "incomplete_reasons": [],
    }


def _valid_v1_report() -> dict:
    """A schema v1 report: no review_complete / incomplete_reasons fields."""
    report = _valid_report()
    report["schema_version"] = "1"
    del report["review_complete"]
    del report["incomplete_reasons"]
    return report


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


# bm:322afc50367d:IN-04 (owner-approved round 2): pathological JSON never
# raises and never resolves silently.
def test_deeply_nested_json_incomplete_without_raising() -> None:
    text = "[" * 100_000 + "]" * 100_000
    result = assess_report(text, exit_code=0, expected_head=H, expected_base=B, current_head=H, attempt=1)
    assert result.status == "incomplete"
    assert "unparseable: report is nested too deeply" in result.reasons


def test_duplicate_key_json_incomplete() -> None:
    text = json.dumps(_valid_report())
    text = text[:-1] + ', "review_complete": false}'
    result = assess_report(text, exit_code=0, expected_head=H, expected_base=B, current_head=H, attempt=1)
    assert result.status == "incomplete"
    assert "unparseable: duplicate key review_complete" in result.reasons


def test_nested_duplicate_key_json_incomplete() -> None:
    text = json.dumps(_valid_report()).replace('"id": "F001"', '"id": "F001", "id": "F009"', 1)
    result = assess_report(text, exit_code=0, expected_head=H, expected_base=B, current_head=H, attempt=1)
    assert result.status == "incomplete"
    assert "unparseable: duplicate key id" in result.reasons



# bm:dbe1b7f56bdd:IN-04 (owner-approved round 3): an integer longer than
# Python's int-string conversion limit raises a plain ValueError in json.loads.
def test_over_long_integer_json_incomplete_without_raising() -> None:
    text = '{"a": 1' + "0" * 5000 + "}"
    result = assess_report(text, exit_code=0, expected_head=H, expected_base=B, current_head=H, attempt=1)
    assert result.status == "incomplete"
    assert "unparseable: report is not valid JSON" in result.reasons

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


def _set_path(report: dict, path: tuple, value) -> None:
    node = report
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


# CR-01 / Codex F001: every wrong-typed or wrong-enum value must make the
# report incomplete -- a type violation is never a complete review.
@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("findings",), None),
        (("findings",), "none"),
        (("coverage",), None),
        (("coverage",), "all"),
        (("exclusions",), None),
        (("limitations",), "none"),
        (("commands_run",), None),
        (("schema_version",), "3"),
        (("schema_version",), 1),
        (("review_complete",), None),
        (("review_complete",), "true"),
        (("review_complete",), 1),
        (("incomplete_reasons",), None),
        (("incomplete_reasons",), "none"),
        (("summary",), 5),
        (("scope",), None),
        (("pr_url",), None),
        (("verdict",), None),
        (("coverage", 0), 3),
        (("findings", 0, "line_start"), True),
        (("findings", 0, "title"), None),
        (("findings", 0, "reproduced"), None),
        (("findings", 0, "severity"), None),
        (("findings", 0, "reproduction_command"), 7),
        (("commands_run", 0, "exit_code"), True),
        (("commands_run", 0, "command"), None),
    ],
)
def test_wrong_type_or_enum_incomplete(path: tuple, value) -> None:
    report = _valid_report()
    _set_path(report, path, value)
    result = _assess(report)
    assert result.status == "incomplete", f"{path}={value!r} was accepted as complete"
    assert any(r.startswith("schema:") for r in result.reasons)


def test_all_required_fields_null_incomplete() -> None:
    """Codex F001 reproduction: every required key present, all non-SHA values null."""
    report = {field: None for field in _valid_report()}
    report["inspected_head_sha"] = H
    report["inspected_base_sha"] = B
    result = _assess(report)
    assert result.status == "incomplete"
    assert len(result.reasons) > 1


# Owner decision 2026-10-22 (v1 rule, kept so recorded history does not
# change): a schema v1 report whose text says the review is incomplete is
# never counted as complete.
_SELF_DECLARED_TEXTS = [
    ("limitations", "This is an incomplete review, not a clean approval: output was truncated."),
    ("limitations", "Not a clean approval."),
    ("summary", "The review is incomplete because the diff was truncated."),
    ("summary", "INCOMPLETE REVIEW: tests could not run."),
]


@pytest.mark.parametrize(("field", "text"), _SELF_DECLARED_TEXTS)
def test_v1_self_declared_incomplete(field: str, text: str) -> None:
    report = _valid_v1_report()
    if field == "limitations":
        report["limitations"].append(text)
    else:
        report[field] = text
    result = _assess(report, legacy_v1=True)
    assert result.status == "incomplete"
    assert any(r.startswith("self-declared incomplete:") for r in result.reasons)


# --- Durable Codex completeness (owner 2026-10-22): schema v2 -------------


def test_v1_report_still_complete_under_v1_rules() -> None:
    result = _assess(_valid_v1_report(), legacy_v1=True)
    assert result.status == "complete"
    assert result.reasons == ()


def test_v1_report_rejects_v2_fields() -> None:
    """v1 stays strict: the v2 completeness fields are not part of v1."""
    report = _valid_v1_report()
    report["review_complete"] = True
    result = _assess(report, legacy_v1=True)
    assert result.status == "incomplete"
    assert any(r == "schema: unexpected field review_complete" for r in result.reasons)


# bm:49ded1e86444:WR-01 (owner-approved round 5): schema v1 exists only so
# recorded history keeps its assessment. A v1 label on a new report never
# skips the structured completeness check; the legacy path is opt-in.
V1_NOT_LEGACY = "schema: schema_version 1 is accepted only when re-assessing a recorded report (--legacy-v1)"


def test_v1_report_without_legacy_flag_incomplete() -> None:
    result = _assess(_valid_v1_report())
    assert result.status == "incomplete"
    assert V1_NOT_LEGACY in result.reasons
    assert "schema: missing review_complete" in result.reasons


def test_v1_label_cannot_hide_an_unfinished_review() -> None:
    """The reviewer's reproduction: a self-labelled v1 report that admits it is unfinished."""
    report = _valid_v1_report()
    report["summary"] = "Only read two files; could not finish."
    report["limitations"] = ["ran out of time before covering most files"]
    result = _assess(report)
    assert result.status == "incomplete"
    assert V1_NOT_LEGACY in result.reasons


def test_legacy_flag_does_not_change_v2_assessment() -> None:
    assert _assess(_valid_report(), legacy_v1=True).status == "complete"
    report = _valid_report()
    report["review_complete"] = False
    report["incomplete_reasons"] = ["tests/ was not inspected"]
    assert _assess(report, legacy_v1=True).status == "incomplete"


def test_cli_v1_report_needs_legacy_flag(tmp_path, capsys) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(_valid_v1_report()), encoding="utf-8")

    assert main(_cli_args(report_path)) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "incomplete"
    assert V1_NOT_LEGACY in payload["reasons"]

    assert main([*_cli_args(report_path), "--legacy-v1"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "complete"


@pytest.mark.parametrize("field", ["review_complete", "incomplete_reasons"])
def test_v2_missing_completeness_field_incomplete(field: str) -> None:
    report = _valid_report()
    del report[field]
    result = _assess(report)
    assert result.status == "incomplete"
    assert any(r == f"schema: missing {field}" for r in result.reasons)


def test_v2_review_complete_false_with_reasons_incomplete() -> None:
    report = _valid_report()
    report["review_complete"] = False
    report["incomplete_reasons"] = ["Diff output was truncated; tests/ was not inspected."]
    result = _assess(report)
    assert result.status == "incomplete"
    assert (
        "self-declared incomplete: Diff output was truncated; tests/ was not inspected." in result.reasons
    )


@pytest.mark.parametrize("reasons", [[], ["   "], [""]])
def test_v2_review_complete_false_without_reasons_incomplete(reasons: list) -> None:
    report = _valid_report()
    report["review_complete"] = False
    report["incomplete_reasons"] = reasons
    result = _assess(report)
    assert result.status == "incomplete"
    assert "review_complete is false but no incomplete_reasons are given" in result.reasons


def test_v2_review_complete_true_with_reasons_incomplete() -> None:
    report = _valid_report()
    report["incomplete_reasons"] = ["Part of the diff was not inspected."]
    result = _assess(report)
    assert result.status == "incomplete"
    assert "review_complete is true but incomplete_reasons are listed" in result.reasons


# Owner decision 2026-10-22 (bm:322afc50367d:SA-02, owner-approved round 2):
# a v2 report is incomplete if review_complete is false OR its summary or
# limitations describe the review as incomplete. The structured fields stay
# required; the phrase check is an additional signal.
@pytest.mark.parametrize(("field", "text"), _SELF_DECLARED_TEXTS)
def test_v2_self_described_incomplete_text_is_incomplete(field: str, text: str) -> None:
    report = _valid_report()
    assert report["review_complete"] is True
    if field == "limitations":
        report["limitations"].append(text)
    else:
        report[field] = text
    result = _assess(report)
    assert result.status == "incomplete"
    assert any(r.startswith(f"self-declared incomplete: {field} states") for r in result.reasons)


def test_v2_text_check_does_not_replace_structured_fields() -> None:
    """Without the structured fields a v2 report stays a schema violation."""
    report = _valid_report()
    del report["review_complete"]
    report["summary"] = "Full review of the diff."
    result = _assess(report)
    assert result.status == "incomplete"
    assert "schema: missing review_complete" in result.reasons


def test_v2_limitation_alone_does_not_make_incomplete() -> None:
    """Being unable to run pytest inside the sandbox is a limitation, not incompleteness."""
    report = _valid_report()
    report["limitations"] = ["pytest could not run in the read-only sandbox; used the harness evidence file."]
    result = _assess(report)
    assert result.status == "complete"


# --- Recorded history keeps its v1 assessment ------------------------------

# Byte-identical copies of Phase 83's recorded reports
# (.planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/), kept
# under tests/ so archiving a milestone's phase folders cannot break this suite.
_CODEX_DIR = Path(__file__).resolve().parent / "fixtures" / "codex-recorded"


def _assess_recorded(name: str, *, legacy_v1: bool = False) -> object:
    text = (_CODEX_DIR / name).read_text(encoding="utf-8")
    report = json.loads(text)
    head = report["inspected_head_sha"]
    return assess_report(
        text,
        exit_code=0,
        expected_head=head,
        expected_base=report["inspected_base_sha"],
        current_head=head,
        attempt=1,
        legacy_v1=legacy_v1,
    )


def test_recorded_quick_v1_report_still_complete() -> None:
    result = _assess_recorded("a7995baf187e-quick-a1.last.json", legacy_v1=True)
    assert result.status == "complete"
    assert result.reasons == ()


@pytest.mark.parametrize(
    ("name", "status"),
    [
        ("d501a68316b2-explicit-a2.last.json", "complete"),
        ("322afc50367d-postfix-a1.last.json", "incomplete"),
        ("322afc50367d-postfix-a2.last.json", "complete"),
    ],
)
def test_recorded_v2_reports_keep_their_assessment(name: str, status: str) -> None:
    assert _assess_recorded(name).status == status


def test_recorded_explicit_v1_report_still_incomplete() -> None:
    result = _assess_recorded("d501a68316b2-explicit-a1.last.json", legacy_v1=True)
    assert result.status == "incomplete"
    assert result.reasons == ("self-declared incomplete: limitations states 'incomplete review'",)


@pytest.mark.parametrize("name", ["a7995baf187e-quick-a1.last.json", "d501a68316b2-explicit-a1.last.json"])
def test_recorded_v1_reports_need_the_legacy_path(name: str) -> None:
    result = _assess_recorded(name)
    assert result.status == "incomplete"
    assert V1_NOT_LEGACY in result.reasons


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


# IN-05: a whitespace-only hypothesis is not a usable hypothesis.
def test_unreproduced_with_whitespace_only_hypothesis_incomplete() -> None:
    report = _valid_report()
    report["findings"][1]["hypothesis"] = "   "
    result = _assess(report)
    assert result.status == "incomplete"
    assert any("F002 unreproduced without a hypothesis" in r for r in result.reasons)


def test_empty_coverage_incomplete() -> None:
    report = _valid_report()
    report["coverage"] = []
    result = _assess(report)
    assert result.status == "incomplete"
    assert any("no coverage stated" in r for r in result.reasons)


# A report that shows no sign Codex ran anything never counts as complete
# (bm:322afc50367d:WR-03, owner-approved round 2).
@pytest.mark.parametrize("report_factory", [_valid_report, _valid_v1_report])
def test_no_commands_run_incomplete(report_factory) -> None:
    report = report_factory()
    report["commands_run"] = []
    result = _assess(report, legacy_v1=report["schema_version"] == "1")
    assert result.status == "incomplete"
    assert "no commands run: the report gives no evidence the diff was inspected" in result.reasons


# A commands_run list whose every command is blank is no more evidence than an
# empty list (vibe-check #2, owner-approved round 6).
_BLANK_COMMAND_LISTS = [
    [{"command": "", "exit_code": None, "purpose": ""}],
    [{"command": "   ", "exit_code": None, "purpose": ""}],
    [{"command": "\n\t", "exit_code": 0, "purpose": "run tests"}],
    [{"command": " ", "exit_code": None, "purpose": ""}, {"command": "", "exit_code": None, "purpose": ""}],
]


@pytest.mark.parametrize("report_factory", [_valid_report, _valid_v1_report])
@pytest.mark.parametrize("commands", _BLANK_COMMAND_LISTS)
def test_only_blank_commands_run_incomplete(report_factory, commands: list) -> None:
    report = report_factory()
    report["commands_run"] = commands
    result = _assess(report, legacy_v1=report["schema_version"] == "1")
    assert result.status == "incomplete"
    assert "no commands run: the report gives no evidence the diff was inspected" in result.reasons


def test_blank_commands_mixed_with_a_real_command_stay_complete() -> None:
    report = _valid_report()
    report["commands_run"] = [
        {"command": "   ", "exit_code": None, "purpose": ""},
        {"command": "uv run pytest tests/ -x -q", "exit_code": 0, "purpose": "run full test suite"},
    ]
    result = _assess(report)
    assert result.status == "complete"
    assert result.reasons == ()


# D-18 hollow-report guard: a null exit code or a report whose only commands
# are trivially uninformative (echo/pwd/true and similar) is no evidence the
# diff was inspected, even though commands_run is non-empty and non-blank.
@pytest.mark.parametrize(
    ("commands", "expected_status", "reason_substring"),
    [
        (
            [{"command": "git diff A..B", "exit_code": None, "purpose": "diff the change"}],
            "incomplete",
            "no command with a recorded exit code",
        ),
        (
            [
                {"command": "echo reviewed", "exit_code": 0, "purpose": "announce"},
                {"command": "pwd", "exit_code": 0, "purpose": "locate"},
            ],
            "incomplete",
            "only trivial commands",
        ),
        (
            [{"command": "FOO=1 true", "exit_code": 0, "purpose": "noop with an env prefix"}],
            "incomplete",
            "only trivial commands",
        ),
        (
            [
                {"command": "echo x", "exit_code": 0, "purpose": "announce"},
                {"command": "git diff A..B -- .", "exit_code": 0, "purpose": "diff the change"},
            ],
            "complete",
            None,
        ),
        (
            [{"command": "uv run pytest tests/test_x.py", "exit_code": 1, "purpose": "run a failing test"}],
            "complete",
            None,
        ),
    ],
    ids=["null-exit", "trivial-only", "env-prefixed-true", "trivial-plus-real", "failing-real"],
)
def test_hollow_report_guard(commands: list, expected_status: str, reason_substring: str | None) -> None:
    report = _valid_report()
    report["commands_run"] = commands
    result = _assess(report)
    assert result.status == expected_status
    if reason_substring is None:
        assert result.reasons == ()
    else:
        assert any(reason_substring in r for r in result.reasons)


# --- Inspection-only review mode (D-07, B04-R2) -----------------------------
#
# The checker grades an inspection-only report -- no commands, no reproduced
# findings -- complete on its own terms only when the caller explicitly
# passes review_mode="inspection-only". Without it (the default "trusted"),
# the same report stays hollow and incomplete (no regression).


def _inspection_only_report() -> dict:
    """Derived from _valid_report(): empty commands_run and every finding
    unreproduced -- what an inspection-only review of inert, untrusted-head
    text produces when it behaves correctly."""
    report = _valid_report()
    report["commands_run"] = []
    for finding in report["findings"]:
        finding["reproduced"] = False
        finding["reproduction_command"] = None
        finding["hypothesis"] = finding.get("hypothesis") or "Not reproduced: inspection-only review runs no commands"
    return report


def test_inspection_only_empty_commands_and_unreproduced_findings_complete() -> None:
    result = _assess(_inspection_only_report(), review_mode="inspection-only")
    assert result.status == "complete"
    assert result.reasons == ()


def test_default_mode_keeps_hollow_report_guard() -> None:
    """Regression: without review_mode, the same inspection-only-shaped
    report is still graded under the trusted hollow-report guard."""
    result = _assess(_inspection_only_report())
    assert result.status == "incomplete"
    assert any(r.startswith("no commands run:") for r in result.reasons)


def test_inspection_only_commands_run_incomplete() -> None:
    report = _inspection_only_report()
    report["commands_run"] = [
        {"command": "git diff A..B", "exit_code": 0, "purpose": "diff the change"},
        {"command": "uv run pytest tests/", "exit_code": 0, "purpose": "run tests"},
    ]
    result = _assess(report, review_mode="inspection-only")
    assert result.status == "incomplete"
    assert "inspection-only review must not run commands: commands_run has 2 entries" in result.reasons


def test_inspection_only_reproduced_finding_incomplete() -> None:
    report = _inspection_only_report()
    report["findings"][1]["reproduced"] = True
    report["findings"][1]["reproduction_command"] = "uv run pytest tests/test_x.py"
    result = _assess(report, review_mode="inspection-only")
    assert result.status == "incomplete"
    assert "inspection-only review cannot reproduce findings: F002 claims reproduced" in result.reasons


def test_inspection_only_empty_coverage_incomplete() -> None:
    report = _inspection_only_report()
    report["coverage"] = []
    result = _assess(report, review_mode="inspection-only")
    assert result.status == "incomplete"
    assert "no coverage stated" in result.reasons


def test_inspection_only_review_complete_false_incomplete() -> None:
    report = _inspection_only_report()
    report["review_complete"] = False
    report["incomplete_reasons"] = ["inert text only; no reproduction is possible"]
    result = _assess(report, review_mode="inspection-only")
    assert result.status == "incomplete"
    assert "self-declared incomplete: inert text only; no reproduction is possible" in result.reasons


def test_inspection_only_bogus_mode_raises_value_error() -> None:
    with pytest.raises(ValueError, match="REVIEW_MODES"):
        _assess(_valid_report(), review_mode="bogus")


def test_cli_whitespace_only_commands_run_exits_one(tmp_path, capsys) -> None:
    report = _valid_report()
    report["commands_run"] = [{"command": "   ", "exit_code": None, "purpose": ""}]
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

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
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["status"] == "incomplete"


@pytest.mark.parametrize("coverage", [[""], ["   "], ["full diff reviewed", " "], ["\n\t"]])
def test_blank_coverage_entry_incomplete(coverage: list) -> None:
    report = _valid_report()
    report["coverage"] = coverage
    result = _assess(report)
    assert result.status == "incomplete"
    assert "blank coverage entry" in result.reasons


@pytest.mark.parametrize("command", ["", "   ", "\n"])
def test_reproduced_with_blank_command_incomplete(command: str) -> None:
    """IN-05 remainder (bm:322afc50367d:IN-02): a blank command is no reproduction."""
    report = _valid_report()
    report["findings"][0]["reproduction_command"] = command
    result = _assess(report)
    assert result.status == "incomplete"
    assert "F001 marked reproduced without a reproduction command" in result.reasons


# CR-02: a finding without a usable string id can never be dispositioned, so
# it must make the report incomplete rather than silently drop out of the IDs.
@pytest.mark.parametrize("bad_id", [7, None, "", "   "])
def test_finding_without_valid_id_incomplete(bad_id) -> None:
    report = _valid_report()
    report["findings"][0]["id"] = bad_id
    result = _assess(report)
    assert result.status == "incomplete"
    assert any(r == "finding at index 0 has no valid id" for r in result.reasons)


def test_complete_results_qualify_every_finding() -> None:
    """Invariant: a complete result has exactly one qualified ID per finding."""
    no_findings = _valid_report()
    no_findings["findings"] = []
    no_findings["verdict"] = "no-findings"
    for report in (_valid_report(), no_findings):
        result = _assess(report)
        assert result.status == "complete"
        assert result.finding_count == len(result.qualified_ids)


def test_no_findings_verdict_with_findings_incomplete() -> None:
    report = _valid_report()
    report["verdict"] = "no-findings"
    result = _assess(report)
    assert result.status == "incomplete"
    assert any(r == "verdict says no-findings but findings are listed" for r in result.reasons)


def test_findings_verdict_without_findings_incomplete() -> None:
    report = _valid_report()
    report["findings"] = []
    result = _assess(report)
    assert result.status == "incomplete"
    assert any(r == "verdict says findings but none are listed" for r in result.reasons)


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


def _cli_args(report_path) -> list[str]:
    return [
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


# WR-02: an unreadable report must still produce the JSON assessment.
def test_cli_non_utf8_report_prints_incomplete(tmp_path, capsys) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_bytes(b"\xff\xfe not utf-8")

    exit_code = main(_cli_args(report_path))
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["status"] == "incomplete"
    assert any(r.startswith("unreadable report:") for r in payload["reasons"])


def test_cli_directory_report_prints_incomplete(tmp_path, capsys) -> None:
    report_dir = tmp_path / "report.json"
    report_dir.mkdir()

    exit_code = main(_cli_args(report_dir))
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["status"] == "incomplete"
    assert any(r.startswith("unreadable report:") for r in payload["reasons"])


# IN-04: --attempt must be a positive integer, so qualified IDs always use
# the a1/a2 convention the checkpoint record expects.
def test_cli_attempt_zero_exits_two() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--report",
                "/nonexistent",
                "--exit-code",
                "0",
                "--expected-head",
                H,
                "--expected-base",
                B,
                "--current-head",
                H,
                "--attempt",
                "0",
            ]
        )
    assert exc_info.value.code == 2


def test_cli_attempt_negative_exits_two() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--report",
                "/nonexistent",
                "--exit-code",
                "0",
                "--expected-head",
                H,
                "--expected-base",
                B,
                "--current-head",
                H,
                "--attempt",
                "-3",
            ]
        )
    assert exc_info.value.code == 2


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
