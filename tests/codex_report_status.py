"""Checker for whether a Codex adversarial review report counts as a
complete, current review of a specific commit (REVIEW-03, REVIEW-04,
REVIEW-06).

A missing report, a non-zero or unknown Codex exit code, unparseable
JSON, a schema violation, a wrong inspected head or base SHA, and a
report whose head is no longer the current head are each reported as a
distinct, plain-language reason. The only two status words this module
ever emits are "complete" and "incomplete" -- a missing, failed,
skipped, stale, or wrong-commit report is never described as anything
else (D-09). Required field names are loaded from
.claude/schemas/codex-review-findings.schema.json at runtime rather than
duplicated here, so the checker cannot silently drift from the schema.

Completeness by schema version (owner decision 2026-10-22):

- schema_version "2" (current): the report states completeness itself in
  the required ``review_complete`` boolean and ``incomplete_reasons``
  list. It is incomplete if ``review_complete`` is false OR its summary
  or limitations describe the review as incomplete (the phrase check is
  an additional signal; the structured fields stay required).
- schema_version "1" (recorded history): assessed under the v1 rules,
  which use the same phrase check, so an already recorded report keeps
  the assessment it had. The v1 schema is
  derived from the current schema by removing the two v2 fields, so it
  cannot drift into a second hand-maintained copy.

Run as `uv run python tests/codex_report_status.py ...` (invoked by
docs/codex-adversarial-review-contract.md, Invocation step 3.6, via
tests/codex_review_run.py). This
module uses plain `print()` in main() because it is audit tooling run
from the CLI, not production code under the loguru-only convention
documented in CLAUDE.md -- the same exception tests/audit_lock_coverage.py
documents for itself.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / ".claude" / "schemas" / "codex-review-findings.schema.json"

_SHA_RE = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class Assessment:
    status: Literal["complete", "incomplete"]
    reasons: tuple[str, ...]
    qualified_ids: tuple[str, ...]
    finding_count: int
    inspected_head: str | None
    inspected_base: str | None


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# Top-level fields that schema v2 added to v1 (durable Codex completeness).
_V2_ONLY_FIELDS = ("review_complete", "incomplete_reasons")


def _v1_schema(current: dict) -> dict:
    """Return the v1 report schema derived from the current (v2) schema."""
    schema = copy.deepcopy(current)
    for field in _V2_ONLY_FIELDS:
        schema["properties"].pop(field, None)
    schema["required"] = [field for field in schema["required"] if field not in _V2_ONLY_FIELDS]
    schema["properties"]["schema_version"]["enum"] = ["1"]
    return schema


def _schema_for(report: dict, current: dict) -> dict:
    """Pick the schema a report is judged against; unknown versions use the current one."""
    return _v1_schema(current) if report.get("schema_version") == "1" else current


# JSON Schema type names used by the report schema, mapped to Python types.
# A type name not listed here makes the value fail validation (fail closed).
_JSON_TYPES: dict[str, type] = {
    "string": str,
    "array": list,
    "object": dict,
    "boolean": bool,
    "integer": int,
    "null": type(None),
}

_JSON_TYPE_NAMES: dict[type, str] = {
    str: "string",
    list: "array",
    dict: "object",
    bool: "boolean",
    int: "integer",
    float: "number",
    type(None): "null",
}


def _declared_types(spec: dict) -> list[str] | None:
    declared = spec.get("type")
    if declared is None:
        return None
    return declared if isinstance(declared, list) else [declared]


def _type_matches(value: object, spec: dict) -> bool:
    names = _declared_types(spec)
    if names is None:
        return True
    for name in names:
        # bool is a subclass of int in Python; JSON true/false is never an integer.
        if name == "integer" and isinstance(value, bool):
            continue
        py_type = _JSON_TYPES.get(name)
        if py_type is not None and isinstance(value, py_type):
            return True
    return False


def _item_label(parent_label: str, index: int, item: object) -> str:
    if parent_label == "findings":
        fid = item.get("id") if isinstance(item, dict) else None
        return f"finding {fid}" if isinstance(fid, str) and fid.strip() else f"finding at index {index}"
    return f"{parent_label}[{index}]"


def _validate_node(value: object, spec: dict, label: str, reasons: list[str]) -> None:
    """Recursively check *value* against schema node *spec*.

    Checks type (nullable unions included), enum, required and unexpected
    object fields, and every array item. *label* is "" for the report
    itself so top-level reasons read "schema: missing <field>".
    """
    subject = f"{label} " if label else ""
    if not _type_matches(value, spec):
        expected = " or ".join(_declared_types(spec) or [])
        actual = _JSON_TYPE_NAMES.get(type(value), type(value).__name__)
        reasons.append(f"schema: {subject}must be {expected}, got {actual}")
        return

    enum = spec.get("enum")
    if enum is not None and value not in enum:
        reasons.append(f"schema: {subject}{value!r} not in {enum}")

    if isinstance(value, dict):
        properties = spec.get("properties", {})
        for field in spec.get("required", []):
            if field not in value:
                reasons.append(f"schema: {subject}missing {field}")
        for key, child in value.items():
            if key not in properties:
                reasons.append(f"schema: {subject}unexpected field {key}")
                continue
            child_label = f"{label} {key}" if label else key
            _validate_node(child, properties[key], child_label, reasons)
    elif isinstance(value, list) and "items" in spec:
        for index, item in enumerate(value):
            _validate_node(item, spec["items"], _item_label(label, index, item), reasons)


def _check_schema(report: dict, schema: dict) -> list[str]:
    """Return one reason per required/unexpected/enum/type violation.

    Walks *schema* recursively at call time -- nothing here is a second,
    hand-maintained copy of the schema's field names, types or enums.
    """
    reasons: list[str] = []
    _validate_node(report, schema, "", reasons)
    return reasons


# Phrases by which a report declares its own review incomplete (owner
# decisions 2026-10-22). Such a report is never counted as complete, in any
# schema version; v2 reports also state completeness structurally.
_SELF_DECLARED_INCOMPLETE_RE = re.compile(
    r"\bincomplete review\b|\breview (?:is|was) incomplete\b|\bnot a clean approval\b",
    re.IGNORECASE,
)


def _self_declared_incomplete(report: dict) -> list[str]:
    texts: list[tuple[str, object]] = [("summary", report.get("summary"))]
    limitations = report.get("limitations")
    if isinstance(limitations, list):
        texts.extend(("limitations", item) for item in limitations)

    reasons: list[str] = []
    for field, text in texts:
        if not isinstance(text, str):
            continue
        match = _SELF_DECLARED_INCOMPLETE_RE.search(text)
        if match:
            reasons.append(f"self-declared incomplete: {field} states '{match.group(0)}'")
    return reasons


def _non_blank(value: object) -> bool:
    """True if *value* is a string with non-whitespace content (IN-05)."""
    return isinstance(value, str) and bool(value.strip())


def _structural_completeness(report: dict) -> list[str]:
    """Schema v2: decide completeness from review_complete and incomplete_reasons.

    Wrong types are already reported by the schema walk, so only
    well-typed values are judged here.
    """
    complete = report.get("review_complete")
    stated = report.get("incomplete_reasons")
    if not isinstance(complete, bool) or not isinstance(stated, list):
        return []
    given = [reason.strip() for reason in stated if _non_blank(reason)]
    if complete:
        return ["review_complete is true but incomplete_reasons are listed"] if stated else []
    if not given:
        return ["review_complete is false but no incomplete_reasons are given"]
    return [f"self-declared incomplete: {reason}" for reason in given]


def _finding_consistency_and_ids(
    report: dict,
    inspected_head: str | None,
    attempt: int,
    source: str,
) -> tuple[list[str], list[str], int]:
    """Return (reasons, qualified_ids, finding_count) for report["findings"]."""
    findings = report.get("findings")
    if not isinstance(findings, list):
        return [], [], 0

    reasons: list[str] = []
    qualified_ids: list[str] = []
    seen_ids: set[str] = set()
    head_fragment = inspected_head[:12] if inspected_head else "unknown"

    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            # Already reported by the schema walk ("must be object").
            continue
        fid = finding.get("id")
        if not isinstance(fid, str) or not fid.strip():
            # Without a usable id the finding cannot be dispositioned, so it
            # must never silently drop out of the qualified IDs (CR-02).
            reasons.append(f"finding at index {index} has no valid id")
            continue

        if fid in seen_ids:
            reasons.append(f"duplicate finding id: {fid}")
        else:
            seen_ids.add(fid)

        reproduced = finding.get("reproduced")
        if reproduced is True and not _non_blank(finding.get("reproduction_command")):
            reasons.append(f"{fid} marked reproduced without a reproduction command")
        if reproduced is False and not _non_blank(finding.get("hypothesis")):
            reasons.append(f"{fid} unreproduced without a hypothesis")

        qualified_ids.append(f"{source}:{head_fragment}:a{attempt}:{fid}")

    return reasons, qualified_ids, len(findings)


def assess_report(
    report_text: str | None,
    *,
    exit_code: int | None,
    expected_head: str,
    expected_base: str,
    current_head: str,
    attempt: int,
    source: str = "codex",
    read_error: str | None = None,
) -> Assessment:
    """Decide whether *report_text* is a complete, current Codex review.

    Collects every applicable reason rather than stopping at the first;
    never raises on malformed input -- malformed input always yields
    "incomplete" with a reason explaining why. *read_error* is set by the
    CLI when the report file exists but could not be read.
    """
    reasons: list[str] = []

    if exit_code is None:
        reasons.append("codex exit status unknown")
    elif exit_code != 0:
        reasons.append(f"codex exited {exit_code}")

    if read_error is not None:
        reasons.append(f"unreadable report: {read_error}")
        return Assessment("incomplete", tuple(reasons), (), 0, None, None)

    if report_text is None or not report_text.strip():
        reasons.append("missing report")
        return Assessment("incomplete", tuple(reasons), (), 0, None, None)

    try:
        report = json.loads(report_text)
    except json.JSONDecodeError:
        reasons.append("unparseable: report is not valid JSON")
        return Assessment("incomplete", tuple(reasons), (), 0, None, None)

    if not isinstance(report, dict):
        reasons.append("unparseable: report is not a JSON object")
        return Assessment("incomplete", tuple(reasons), (), 0, None, None)

    reasons.extend(_check_schema(report, _schema_for(report, _load_schema())))
    # Every schema version: self-described incompleteness in the text is an
    # incomplete review. Version 2 additionally states it structurally.
    reasons.extend(_self_declared_incomplete(report))
    if report.get("schema_version") != "1":
        reasons.extend(_structural_completeness(report))

    inspected_head = report.get("inspected_head_sha")
    if not isinstance(inspected_head, str):
        inspected_head = None
    inspected_base = report.get("inspected_base_sha")
    if not isinstance(inspected_base, str):
        inspected_base = None

    if inspected_head is None or not _SHA_RE.fullmatch(inspected_head):
        reasons.append("wrong commit: report inspected head is not a valid commit SHA")
    elif inspected_head != expected_head:
        reasons.append(
            f"wrong commit: report inspected {inspected_head[:12]} "
            f"but review was requested for {expected_head[:12]}"
        )
    elif inspected_head != current_head:
        reasons.append(f"stale: report is for {inspected_head[:12]}, current head is {current_head[:12]}")

    if inspected_base is None or not _SHA_RE.fullmatch(inspected_base):
        reasons.append("wrong base: report inspected base is not a valid commit SHA")
    elif inspected_base != expected_base:
        reasons.append(
            f"wrong base: report inspected {inspected_base[:12]} "
            f"but review was requested for {expected_base[:12]}"
        )

    finding_reasons, qualified_ids, finding_count = _finding_consistency_and_ids(
        report, inspected_head, attempt, source
    )
    reasons.extend(finding_reasons)

    findings = report.get("findings")
    verdict = report.get("verdict")
    if isinstance(findings, list):
        if verdict == "no-findings" and findings:
            reasons.append("verdict says no-findings but findings are listed")
        elif verdict == "findings" and not findings:
            reasons.append("verdict says findings but none are listed")

    # Cheap evidence that Codex actually did the work: a report with no
    # commands or blank coverage is hollow, whatever it says about itself.
    coverage = report.get("coverage")
    if isinstance(coverage, list):
        if len(coverage) == 0:
            reasons.append("no coverage stated")
        elif not all(_non_blank(entry) for entry in coverage if isinstance(entry, str)):
            reasons.append("blank coverage entry")
    commands = report.get("commands_run")
    if isinstance(commands, list) and not commands:
        reasons.append("no commands run: the report gives no evidence the diff was inspected")

    status: Literal["complete", "incomplete"] = "incomplete" if reasons else "complete"
    return Assessment(
        status=status,
        reasons=tuple(reasons),
        qualified_ids=tuple(qualified_ids),
        finding_count=finding_count,
        inspected_head=inspected_head,
        inspected_base=inspected_base,
    )


def _sha_type(name: str):
    def _validate(value: str) -> str:
        if not _SHA_RE.fullmatch(value):
            raise argparse.ArgumentTypeError(f"{name} must be 40 lowercase hex characters, got {value!r}")
        return value

    return _validate


def _positive_int(value: str) -> int:
    """--attempt must be >= 1 (IN-04): a1/a2/... qualified IDs never use a0 or negative attempts."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"--attempt must be an integer >= 1, got {value!r}") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError(f"--attempt must be an integer >= 1, got {value!r}")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assess whether a Codex adversarial review report is a complete, current review."
    )
    parser.add_argument("--report", required=True, type=Path, help="Path to the report JSON file (may be absent)")
    parser.add_argument("--exit-code", type=int, default=None, help="Exit code of the codex exec invocation")
    parser.add_argument("--expected-head", required=True, type=_sha_type("--expected-head"))
    parser.add_argument("--expected-base", required=True, type=_sha_type("--expected-base"))
    parser.add_argument("--current-head", required=True, type=_sha_type("--current-head"))
    parser.add_argument("--attempt", type=_positive_int, required=True)
    parser.add_argument("--source", default="codex")
    return parser


def _assessment_to_dict(assessment: Assessment) -> dict:
    return {
        "status": assessment.status,
        "reasons": list(assessment.reasons),
        "qualified_ids": list(assessment.qualified_ids),
        "finding_count": assessment.finding_count,
        "inspected_head": assessment.inspected_head,
        "inspected_base": assessment.inspected_base,
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    report_path: Path = args.report
    report_text: str | None = None
    read_error: str | None = None
    if report_path.exists():
        try:
            report_text = report_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            read_error = type(exc).__name__

    assessment = assess_report(
        report_text,
        exit_code=args.exit_code,
        expected_head=args.expected_head,
        expected_base=args.expected_base,
        current_head=args.current_head,
        attempt=args.attempt,
        source=args.source,
        read_error=read_error,
    )

    print(json.dumps(_assessment_to_dict(assessment)))
    return 0 if assessment.status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
