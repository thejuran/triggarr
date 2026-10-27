"""Guard tests for Phase 85 D-16/D-19/D-20 acceptance-doc wording.

These pin the owner-approved Codex fallback definition, the verified-origin
trusted mode, the interim untrusted-head rule, the pre-grading redaction
stage, the keyed-register serialization rule, the acceptance-readiness
check, and the coverage-evidence procedure for vibe-check -- so the
acceptance and review docs cannot silently drift from what the code in this
phase enforces.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT = REPO_ROOT / "docs" / "codex-adversarial-review-contract.md"
RECORD = REPO_ROOT / "docs" / "review-checkpoint-record.md"
PILOT = REPO_ROOT / "docs" / "buildomator-greptile-pilot.md"
ACCEPTANCE = REPO_ROOT / "docs" / "owner-cli-acceptance.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+", text)


def _fallback_schema_fields() -> dict[str, list[str]]:
    """Read FALLBACK_FIELDS/OWNER_DECISIONS from the validator itself, never duplicated by hand."""
    result = subprocess.run(
        [
            "node",
            "-e",
            "const m=require('./.github/scripts/codex-fallback.cjs'); "
            "console.log(JSON.stringify({f: m.FALLBACK_FIELDS, d: m.OWNER_DECISIONS}));",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


# --- Task 1: D-16 fallback definition, interim untrusted rule, redaction ----


def test_contract_defines_owner_approved_fallback() -> None:
    text = _read(CONTRACT)
    assert "### Owner-approved fallback" in text
    section = text.split("### Owner-approved fallback", 1)[1]
    section = section.split("\n## ", 1)[0]
    assert ".github/scripts/codex-fallback.cjs" in section
    fields = _fallback_schema_fields()
    for field in fields["f"]:
        assert field in section, f"Owner-approved fallback section must name field {field!r}"
    for decision in fields["d"]:
        assert decision in section, f"Owner-approved fallback section must name owner decision {decision!r}"
    assert "INCOMPLETE/PENDING" in section
    assert "retry" in section.lower()


def test_contract_wait_and_retry_later_block_acceptance() -> None:
    text = _read(CONTRACT)
    assert any(
        "wait" in s.lower() and "retry later" in s.lower() and "block acceptance" in s.lower()
        for s in _sentences(text)
    ), "contract must state in one sentence that wait and retry later block acceptance"


def test_vibe_check_rule_consistent() -> None:
    text = _read(RECORD)
    assert "Vibe-check never substitutes for Codex or Greptile, never waives" not in text
    assert "never substitutes for a complete Codex pass" in text
    assert "owner may approve vibe-check" in text


def test_no_doc_says_harness_hardening_pending() -> None:
    for path in (CONTRACT, RECORD):
        text = _read(path)
        assert "until the harness is hardened" not in text, f"{path.name} must drop the stale harness-hardening wording"
        assert "Codex is not run for" not in text, f"{path.name} must drop the stale 'Codex is not run for' wording"


def test_contract_states_interim_untrusted_rule() -> None:
    sentence = (
        "Until Phase 85.1 delivers the isolated review, untrusted heads (bot and fork PRs) "
        "get an INCOMPLETE Codex result plus a per-PR owner-approved fallback review (D-16); "
        "CI still runs."
    )
    for path in (CONTRACT, RECORD):
        text = _read(path)
        assert sentence in text, f"{path.name} must state the interim untrusted rule verbatim"
        assert "--untrusted" in text
        assert "untrusted-refused" in text
        assert "--head-trust untrusted" in text
        assert "runs nothing" in text
        assert "never clean" in text


def test_no_doc_overclaims_untrusted_review() -> None:
    banned_phrases = (
        "inspection-only",
        "review container",
        "disposable container",
        "isolation boundary",
        ".boundary.json",
    )
    overclaim_re = re.compile(r"bot (and fork )?PRs? (get|receive)s? (a |the )?(complete|normal paired)", re.IGNORECASE)
    egress_re = re.compile(r"(?<![a-z])egress(?![a-z])", re.IGNORECASE)
    for path in (CONTRACT, RECORD):
        text = _read(path)
        lowered = text.lower()
        for term in banned_phrases:
            assert term not in lowered, f"{path.name} must not claim {term!r}"
        assert not egress_re.search(text), f"{path.name} must not claim 'egress' isolation"
        assert not overclaim_re.search(text), f"{path.name} must not claim bot PRs get a complete/normal paired review"


def test_contract_trusted_requires_verified_origin() -> None:
    text = _read(CONTRACT)
    assert "TRUSTED_AUTHORS" in text or "owner-authored" in text
    assert "reflog" in text
    assert "origin/main" in text
    assert "fails closed" in text


def test_raw_output_redaction_stage_documented() -> None:
    text = _read(CONTRACT)
    assert "full, unedited" not in text
    assert "None of these files are ever edited after being written." not in text
    assert "pre-grading redaction" in text
    assert "immutable" in text
    assert "Historical evidence committed before Phase 85" in text


def test_pilot_approval_precondition_includes_codex() -> None:
    text = _read(PILOT)
    workflow_section = text.split("### Routine BM workflow", 1)[1]
    step = next(line for line in workflow_section.splitlines() if line.strip().startswith("4. "))
    assert "paired Codex review" in step
    assert "codex-fallback.cjs" in step


# --- Task 2: D-19/D-20 acceptance procedure, register docs, coverage evidence ----


def _acceptance_step(number: int) -> str:
    prefix = f"{number}. "
    return next(line for line in _read(ACCEPTANCE).splitlines() if line.startswith(prefix))


def test_owner_procedure_runs_readiness_check() -> None:
    step1 = _acceptance_step(1)
    step5 = _acceptance_step(5)
    assert "acceptance-readiness.cjs" in step1
    assert "acceptance-readiness.cjs" in step5


def test_owner_procedure_serializes_register_updates() -> None:
    text = _read(ACCEPTANCE)
    assert any(
        "serialized" in s.lower() and "compare-and-swap" in s.lower() and "one pr" in s.lower()
        for s in _sentences(text)
    ), "owner-cli-acceptance.md must state in one sentence that final acceptance updates are serialized"
    assert "review-register.cjs" in text


def test_pilot_register_shape_is_schema_two() -> None:
    text = _read(PILOT)
    section = text.split("### Register shape", 1)[1]
    assert section.count('"schema":2') == 2
    assert section.count("by_pr_head") >= 2
    assert "global_open" in section
    assert "migrate --kind" in section


def test_pilot_no_python_distributions() -> None:
    text = _read(PILOT)
    assert "and distributions" not in text
    assert "built Python distributions" not in text


def test_pilot_mentions_os_scan() -> None:
    text = _read(PILOT)
    assert "is not an OS image vulnerability scan" not in text
    assert "os-scan-policy.md" in text


def test_record_documents_coverage_evidence() -> None:
    text = _read(RECORD)
    heading = "## Coverage evidence for vibe-check"
    assert heading in text
    section = text.split(heading, 1)[1]
    section = section.split("\n## ", 1)[0]
    assert "coverage-provenance.cjs check" in section
    assert "write-local" in section
    assert "--expected-head" in section
    assert "coverage-<run_id>-<run_attempt>" in section
    assert "measured-source equivalence" in section
    assert "worktree root" in section
    assert "only after" in section.lower()
    assert "evidence is never added to a review that has already run" in section


def test_checklist_names_readiness_output() -> None:
    text = _read(RECORD)
    heading = "## Owner acceptance checklist"
    assert heading in text
    section = text.split(heading, 1)[1]
    assert "acceptance-readiness.cjs" in section
