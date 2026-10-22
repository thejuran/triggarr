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

Run as `uv run python tests/codex_report_status.py ...` (invoked by
docs/codex-adversarial-review-contract.md, Invocation step 6). This
module uses plain `print()` in main() because it is audit tooling run
from the CLI, not production code under the loguru-only convention
documented in CLAUDE.md -- the same exception tests/audit_lock_coverage.py
documents for itself.
"""

from __future__ import annotations

import argparse
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


def _check_schema(report: dict, schema: dict) -> list[str]:
    """Return one reason per required/unexpected/enum/type violation.

    Every list is read from *schema* at call time -- nothing here is a
    second, hand-maintained copy of the schema's field names.
    """
    reasons: list[str] = []
    top_properties = schema.get("properties", {})

    for field in schema.get("required", []):
        if field not in report:
            reasons.append(f"schema: missing {field}")

    for key in report:
        if key not in top_properties:
            reasons.append(f"schema: unexpected field {key}")

    verdict_enum = top_properties.get("verdict", {}).get("enum", [])
    verdict = report.get("verdict")
    if verdict is not None and verdict_enum and verdict not in verdict_enum:
        reasons.append(f"schema: verdict {verdict!r} not in {verdict_enum}")

    findings_item_schema = top_properties.get("findings", {}).get("items", {})
    finding_required = findings_item_schema.get("required", [])
    finding_properties = findings_item_schema.get("properties", {})
    severity_enum = finding_properties.get("severity", {}).get("enum", [])

    findings = report.get("findings")
    if isinstance(findings, list):
        for finding in findings:
            if not isinstance(finding, dict):
                reasons.append("schema: finding is not an object")
                continue
            fid = finding.get("id", "?")
            for field in finding_required:
                if field not in finding:
                    reasons.append(f"schema: finding {fid} missing {field}")
            for key in finding:
                if key not in finding_properties:
                    reasons.append(f"schema: finding {fid} unexpected field {key}")
            severity = finding.get("severity")
            if severity is not None and severity_enum and severity not in severity_enum:
                reasons.append(f"schema: finding {fid} severity {severity!r} not in {severity_enum}")
            reproduced = finding.get("reproduced")
            if reproduced is not None and not isinstance(reproduced, bool):
                reasons.append(f"schema: finding {fid} reproduced must be a boolean")
            for int_field in ("line_start", "line_end"):
                value = finding.get(int_field)
                if value is not None and not isinstance(value, int):
                    reasons.append(f"schema: finding {fid} {int_field} must be an integer or null")

    commands_item_schema = top_properties.get("commands_run", {}).get("items", {})
    cmd_required = commands_item_schema.get("required", [])
    cmd_properties = commands_item_schema.get("properties", {})

    commands_run = report.get("commands_run")
    if isinstance(commands_run, list):
        for cmd in commands_run:
            if not isinstance(cmd, dict):
                reasons.append("schema: commands_run entry is not an object")
                continue
            for field in cmd_required:
                if field not in cmd:
                    reasons.append(f"schema: commands_run entry missing {field}")
            for key in cmd:
                if key not in cmd_properties:
                    reasons.append(f"schema: commands_run entry unexpected field {key}")
            exit_code_value = cmd.get("exit_code")
            if exit_code_value is not None and not isinstance(exit_code_value, int):
                reasons.append("schema: commands_run entry exit_code must be an integer or null")

    return reasons


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

    for finding in findings:
        if not isinstance(finding, dict):
            continue
        fid = finding.get("id")
        if not isinstance(fid, str):
            continue

        if fid in seen_ids:
            reasons.append(f"duplicate finding id: {fid}")
        else:
            seen_ids.add(fid)

        reproduced = finding.get("reproduced")
        if reproduced is True and not finding.get("reproduction_command"):
            reasons.append(f"{fid} marked reproduced without a reproduction command")
        if reproduced is False and not finding.get("hypothesis"):
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
) -> Assessment:
    """Decide whether *report_text* is a complete, current Codex review.

    Collects every applicable reason rather than stopping at the first;
    never raises on malformed input -- malformed input always yields
    "incomplete" with a reason explaining why.
    """
    reasons: list[str] = []

    if exit_code is None:
        reasons.append("codex exit status unknown")
    elif exit_code != 0:
        reasons.append(f"codex exited {exit_code}")

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

    schema = _load_schema()
    reasons.extend(_check_schema(report, schema))

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

    coverage = report.get("coverage")
    if isinstance(coverage, list) and len(coverage) == 0:
        reasons.append("no coverage stated")

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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assess whether a Codex adversarial review report is a complete, current review."
    )
    parser.add_argument("--report", required=True, type=Path, help="Path to the report JSON file (may be absent)")
    parser.add_argument("--exit-code", type=int, default=None, help="Exit code of the codex exec invocation")
    parser.add_argument("--expected-head", required=True, type=_sha_type("--expected-head"))
    parser.add_argument("--expected-base", required=True, type=_sha_type("--expected-base"))
    parser.add_argument("--current-head", required=True, type=_sha_type("--current-head"))
    parser.add_argument("--attempt", type=int, required=True)
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
    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else None

    assessment = assess_report(
        report_text,
        exit_code=args.exit_code,
        expected_head=args.expected_head,
        expected_base=args.expected_base,
        current_head=args.current_head,
        attempt=args.attempt,
        source=args.source,
    )

    print(json.dumps(_assessment_to_dict(assessment)))
    return 0 if assessment.status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
