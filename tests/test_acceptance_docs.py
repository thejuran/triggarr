"""Guard tests for Phase 85 D-16/D-19/D-20 and Phase 85.1 D-04/D-06/D-07/D-11
acceptance-doc wording.

These pin the owner-approved Codex fallback definition, the verified-origin
trusted mode, the delivered Phase 85.1 untrusted-head rule (inspection-only
review, open egress, the credential copy and its accepted residual risk),
the pre-grading redaction stage, the keyed-register serialization rule, the
acceptance-readiness check, and the coverage-evidence procedure for
vibe-check -- so the acceptance and review docs cannot silently drift from
what the code in this phase enforces.
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


# --- Phase 85.1 (D-04/D-06/D-07/D-11/D-12): the delivered inspection-only rule ----

_SENTENCE_S1 = (
    "Untrusted heads (bot and fork PRs) get an inspection-only Codex review: the head is never "
    "checked out or executed, Codex runs in a disposable review container whose configuration is "
    "checked before every run, and the report is graded by the checker from a freshly fetched "
    "origin/main."
)
_SENTENCE_S2 = (
    "The review container is not network-isolated: it uses Docker's default bridge network with "
    "no published ports, and its egress is not restricted to the model endpoint."
)
_SENTENCE_S3 = (
    "Accepted residual risk (owner decision, 2026-10-28): the owner's Codex sign-in is inside the "
    "container and its egress is not restricted, so if both the container boundary and Codex's "
    "tool-disabling failed, the owner's main Codex session could leak."
)
_SENTENCE_S4 = (
    "OpenAI's guidance discourages copying the Codex sign-in file for public repositories; this "
    "repository is public, and the owner accepted this on 2026-10-28."
)
_SENTENCE_S5 = (
    "If Codex refreshed the sign-in during the run, the result is INCOMPLETE and the owner must "
    "re-login with `codex login`; the refreshed copy is deleted and never copied back."
)
_SENTENCE_S6 = (
    "An inspection-only result that stays INCOMPLETE after its one automatic retry still needs the "
    "owner-approved fallback (D-16); wait and retry later block acceptance."
)
_SENTENCE_S7 = (
    "The container receives a per-run copy of the owner's Codex sign-in file (`auth.json`) as its "
    "only secret; the host's `~/.codex` is never mounted, and the copy is deleted after every run."
)
_SENTENCE_S8 = (
    "The sign-in is copied only if its `last_refresh` is within the last 7 days; an older sign-in "
    "stops the run INCOMPLETE before any copy, with a message to run `codex login` (or use Codex on "
    "the host) first. There is no forced refresh before every run; the before-and-after comparison "
    "of the copied file is the backstop."
)


def test_docs_state_untrusted_inspection_only_rule() -> None:
    for path in (CONTRACT, RECORD):
        text = _read(path)
        for sentence in (_SENTENCE_S1, _SENTENCE_S2, _SENTENCE_S6):
            assert sentence in text, f"{path.name} must state verbatim: {sentence!r}"
        assert "delivers the isolated review" not in text, f"{path.name} must drop the interim rule"


def test_contract_states_credential_and_residual_risk() -> None:
    text = _read(CONTRACT)
    for sentence in (_SENTENCE_S3, _SENTENCE_S4, _SENTENCE_S5, _SENTENCE_S7, _SENTENCE_S8):
        assert sentence in text, f"contract must state verbatim: {sentence!r}"


def test_contract_has_no_24_hour_sign_in_rule() -> None:
    for path in (CONTRACT, RECORD):
        text = _read(path)
        lowered = text.lower()
        for banned in ("24 hours", "24-hour", "24h"):
            assert banned not in lowered, f"{path.name} must not state the superseded {banned!r} rule"
        assert "refreshed on the host right before" not in text, (
            f"{path.name} must not state the superseded forced-refresh-before-every-run rule"
        )


def test_no_doc_overclaims_untrusted_isolation() -> None:
    network_isolated_re = re.compile(r"(?<!not )network-isolated")
    egress_word_re = re.compile(r"(?<![a-z])egress(?![a-z])", re.IGNORECASE)
    for path in (CONTRACT, RECORD):
        text = _read(path)
        lowered = text.lower()
        for sentence in _sentences(text):
            if egress_word_re.search(sentence):
                assert "not restricted" in sentence, (
                    f"{path.name}: every sentence mentioning 'egress' must say 'not restricted': {sentence!r}"
                )
        assert not network_isolated_re.search(text), f"{path.name} must not claim unqualified network isolation"
        for banned in ("network isolation", "no network access", "air-gapped"):
            assert banned not in lowered, f"{path.name} must not claim {banned!r}"


def test_historical_untrusted_refused_still_documented() -> None:
    for path in (CONTRACT, RECORD):
        text = _read(path)
        assert "untrusted-refused" in text, f"{path.name} must still document historical untrusted-refused records"
        assert "--head-trust untrusted" in text


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
    assert "evidence is never added to a review that has already run" in section.lower()


def test_checklist_names_readiness_output() -> None:
    text = _read(RECORD)
    heading = "## Owner acceptance checklist"
    assert heading in text
    section = text.split(heading, 1)[1]
    assert "acceptance-readiness.cjs" in section
