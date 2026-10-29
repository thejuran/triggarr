"""Tests for the per-attempt completion gate (Phase 85.1, B18, D-03).

completion_gate() decides whether a live inspection-only (untrusted-head)
Codex review counts as COMPLETE. It is bound to exactly one attempt's
output prefix -- never a glob over other attempts -- so an earlier failed
attempt for the same head can never block a later COMPLETE one, and a
COMPLETE-looking later attempt can never borrow an earlier attempt's
files. Every fixture here writes directly to a fake REPO_ROOT (never the
real one); no Docker, no Codex, no network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests import codex_review_run
from tests.codex_review_run import completion_gate, main

_GATE_PHASE_DIR = ".planning/phases/x"
_GATE_HEAD = "a" * 40
_GATE_BASE = "b" * 40
_GATE_LABEL = "untrusted-e2e"


def _gate_name(attempt: int) -> str:
    return f"{_GATE_HEAD[:12]}-{_GATE_LABEL}-a{attempt}"


def _gate_prefix(attempt: int) -> Path:
    return Path(f"{_GATE_PHASE_DIR}/codex/{_gate_name(attempt)}")


def _gate_setup(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(codex_review_run, "REPO_ROOT", tmp_path)
    codex_dir = tmp_path / _GATE_PHASE_DIR / "codex"
    codex_dir.mkdir(parents=True)
    return codex_dir


def _write(codex_dir: Path, name: str, suffix: str, data: object) -> None:
    (codex_dir / f"{name}{suffix}").write_text(json.dumps(data), encoding="utf-8")


def _valid_meta(attempt: int, *, audited_changed: list[str] | None = None) -> dict:
    return {
        "meta_version": 2,
        "head": _GATE_HEAD,
        "base": _GATE_BASE,
        "label": _GATE_LABEL,
        "attempt": attempt,
        "pr_url": "https://github.com/thejuran/triggarr/pull/1",
        "trusted": False,
        "review_mode": "inspection-only-ci-evidence",
        "inspection_template_version": "1",
        "harness_head": _GATE_BASE,
        "inputs": {},
        "test_evidence_source": "GitHub CI check runs",
        "audited_inputs_changed_in_diff": audited_changed or [],
        "base_grader_source": "trusted-origin-main",
        "inspection_input": {"bytes": 10, "files_included": 1, "files_omitted": 0},
    }


def _valid_status(*, complete: bool = True) -> dict:
    return {
        "status": "complete" if complete else "incomplete",
        "reasons": [] if complete else ["codex exited 1"],
        "qualified_ids": [],
        "finding_count": 0,
        "inspected_head": _GATE_HEAD if complete else None,
        "inspected_base": _GATE_BASE if complete else None,
    }


def _valid_boundary(attempt: int, *, verdict: str = "verified") -> dict:
    return {
        "boundary_version": 1,
        "verdict": verdict,
        "reasons": [] if verdict == "verified" else ["review image not built or not labelled"],
        "checked_at": "2026-10-28T00:00:00+00:00",
        "head": _GATE_HEAD,
        "label": _GATE_LABEL,
        "attempt": attempt,
    }


def _valid_provenance() -> dict:
    return {
        "established": True,
        "main_ref": "refs/remotes/origin/main",
        "main_sha": _GATE_BASE,
        "harness_head": _GATE_BASE,
        "base": _GATE_BASE,
        "base_on_main": True,
        "grader_ref": _GATE_BASE,
        "grader_source": "trusted-origin-main",
    }


def _write_full_attempt(codex_dir: Path, attempt: int, **overrides: object) -> None:
    """Write a fully valid, internally-bound attempt record set, unless overridden."""
    name = _gate_name(attempt)
    meta = overrides.get("meta", _valid_meta(attempt))
    status = overrides.get("status", _valid_status())
    boundary = overrides.get("boundary", _valid_boundary(attempt))
    provenance = overrides.get("provenance", _valid_provenance())
    _write(codex_dir, name, ".meta.json", meta)
    _write(codex_dir, name, ".status.json", status)
    _write(codex_dir, name, ".boundary.json", boundary)
    _write(codex_dir, name, ".grader-provenance.json", provenance)
    if "base_status" in overrides:
        _write(codex_dir, name, ".base-status.json", overrides["base_status"])


# --- Attempt isolation (B18) --------------------------------------------------


def test_completion_gate_ignores_earlier_failed_attempt(tmp_path: Path, monkeypatch) -> None:
    codex_dir = _gate_setup(tmp_path, monkeypatch)
    _write_full_attempt(
        codex_dir,
        1,
        status=_valid_status(complete=False),
        boundary=_valid_boundary(1, verdict="unverified"),
    )
    _write_full_attempt(codex_dir, 2)

    assert completion_gate(_gate_prefix(2)) == []
    assert completion_gate(_gate_prefix(1)) != []


def test_completion_gate_does_not_borrow_other_attempts(tmp_path: Path, monkeypatch) -> None:
    codex_dir = _gate_setup(tmp_path, monkeypatch)
    _write_full_attempt(codex_dir, 1)  # a1 has a verified boundary
    name2 = _gate_name(2)
    _write(codex_dir, name2, ".meta.json", _valid_meta(2))
    _write(codex_dir, name2, ".status.json", _valid_status())
    _write(codex_dir, name2, ".grader-provenance.json", _valid_provenance())
    # deliberately no a2.boundary.json

    assert completion_gate(_gate_prefix(2)) == [f"missing {_gate_prefix(2)}.boundary.json"]


# --- Cross-grade requirement (base-status) ------------------------------------


def test_completion_gate_requires_base_status_for_cross_grade(tmp_path: Path, monkeypatch) -> None:
    codex_dir = _gate_setup(tmp_path, monkeypatch)
    changed = ["tests/codex_report_status.py"]

    _write_full_attempt(codex_dir, 2, meta=_valid_meta(2, audited_changed=changed))
    assert completion_gate(_gate_prefix(2)) == [
        f"base-status required (grader changed in this diff) but {_gate_prefix(2)}.base-status.json is missing"
    ]

    _write_full_attempt(
        codex_dir,
        2,
        meta=_valid_meta(2, audited_changed=changed),
        base_status=_valid_status(complete=False),
    )
    assert completion_gate(_gate_prefix(2)) == ["base-status is not complete"]

    _write_full_attempt(
        codex_dir,
        2,
        meta=_valid_meta(2, audited_changed=changed),
        base_status={**_valid_status(), "inspected_head": "c" * 40},
    )
    assert completion_gate(_gate_prefix(2)) == ["base-status is not bound to this head and base"]


# --- Boundary binding ----------------------------------------------------------


def test_completion_gate_boundary_unverified(tmp_path: Path, monkeypatch) -> None:
    codex_dir = _gate_setup(tmp_path, monkeypatch)
    _write_full_attempt(codex_dir, 2, boundary=_valid_boundary(2, verdict="unverified"))
    assert completion_gate(_gate_prefix(2)) == ["isolation boundary not verified"]


def test_completion_gate_boundary_wrong_attempt(tmp_path: Path, monkeypatch) -> None:
    codex_dir = _gate_setup(tmp_path, monkeypatch)
    # attempt=1 embedded in a record filed under the a2 prefix.
    _write_full_attempt(codex_dir, 2, boundary=_valid_boundary(1))
    assert completion_gate(_gate_prefix(2)) == ["boundary record is for another head or attempt"]


# --- Status binding --------------------------------------------------------


def test_completion_gate_status_incomplete(tmp_path: Path, monkeypatch) -> None:
    codex_dir = _gate_setup(tmp_path, monkeypatch)
    _write_full_attempt(codex_dir, 2, status=_valid_status(complete=False))
    assert completion_gate(_gate_prefix(2)) == ["Codex status is not complete"]


def test_completion_gate_status_wrong_base(tmp_path: Path, monkeypatch) -> None:
    codex_dir = _gate_setup(tmp_path, monkeypatch)
    status = {**_valid_status(), "inspected_base": "c" * 40}
    _write_full_attempt(codex_dir, 2, status=status)
    assert completion_gate(_gate_prefix(2)) == ["status is not bound to this head and base"]


# --- Meta validity ------------------------------------------------------------


def test_completion_gate_meta_wrong_review_mode(tmp_path: Path, monkeypatch) -> None:
    codex_dir = _gate_setup(tmp_path, monkeypatch)
    meta = {**_valid_meta(2), "review_mode": "trusted-local-tests"}
    _write_full_attempt(codex_dir, 2, meta=meta)
    assert completion_gate(_gate_prefix(2)) == ["not an inspection-only record"]


def test_completion_gate_meta_wrong_head(tmp_path: Path, monkeypatch) -> None:
    codex_dir = _gate_setup(tmp_path, monkeypatch)
    wrong_head = "c" * 40
    # boundary/status stay internally bound to the (wrong) meta head, so only
    # the meta-vs-prefix comparison fails.
    meta = {**_valid_meta(2), "head": wrong_head}
    boundary = {**_valid_boundary(2), "head": wrong_head}
    status = {**_valid_status(), "inspected_head": wrong_head}
    _write_full_attempt(codex_dir, 2, meta=meta, boundary=boundary, status=status)
    assert completion_gate(_gate_prefix(2)) == ["meta does not match the output prefix"]


def test_completion_gate_meta_wrong_attempt(tmp_path: Path, monkeypatch) -> None:
    codex_dir = _gate_setup(tmp_path, monkeypatch)
    # boundary stays bound to the prefix's own attempt (2), so only the
    # meta-vs-prefix attempt comparison fails.
    meta = {**_valid_meta(2), "attempt": 1}
    _write_full_attempt(codex_dir, 2, meta=meta)
    assert completion_gate(_gate_prefix(2)) == ["meta does not match the output prefix"]


# --- Grader provenance ---------------------------------------------------------


def test_completion_gate_provenance_missing(tmp_path: Path, monkeypatch) -> None:
    codex_dir = _gate_setup(tmp_path, monkeypatch)
    name = _gate_name(2)
    _write(codex_dir, name, ".meta.json", _valid_meta(2))
    _write(codex_dir, name, ".status.json", _valid_status())
    _write(codex_dir, name, ".boundary.json", _valid_boundary(2))
    # deliberately no .grader-provenance.json
    assert completion_gate(_gate_prefix(2)) == ["grader provenance not established from origin/main"]


def test_completion_gate_provenance_base_on_main_false(tmp_path: Path, monkeypatch) -> None:
    codex_dir = _gate_setup(tmp_path, monkeypatch)
    provenance = {**_valid_provenance(), "base_on_main": False}
    _write_full_attempt(codex_dir, 2, provenance=provenance)
    assert completion_gate(_gate_prefix(2)) == ["grader provenance not established from origin/main"]


def test_completion_gate_provenance_wrong_source(tmp_path: Path, monkeypatch) -> None:
    codex_dir = _gate_setup(tmp_path, monkeypatch)
    provenance = {**_valid_provenance(), "grader_source": "base"}
    _write_full_attempt(codex_dir, 2, provenance=provenance)
    assert completion_gate(_gate_prefix(2)) == ["grader provenance not established from origin/main"]


# --- Symlink refusal (read through safe_read_regular_file) -------------------


def test_completion_gate_refuses_symlinked_file(tmp_path: Path, monkeypatch) -> None:
    codex_dir = _gate_setup(tmp_path, monkeypatch)
    _write_full_attempt(codex_dir, 2)
    name = _gate_name(2)
    boundary_path = codex_dir / f"{name}.boundary.json"
    target = tmp_path / "elsewhere.json"
    target.write_text(json.dumps(_valid_boundary(2)), encoding="utf-8")
    boundary_path.unlink()
    boundary_path.symlink_to(target)
    assert completion_gate(_gate_prefix(2)) == [f"refused: {name}.boundary.json is a symlink"]


# --- Output-prefix format -------------------------------------------------------


@pytest.mark.parametrize(
    "bad_prefix",
    [
        Path("/etc/passwd"),
        Path("../../etc/passwd"),
        Path(".planning/phases/x/codex/not-an-attempt"),
    ],
)
def test_completion_gate_rejects_bad_prefix(bad_prefix: Path) -> None:
    assert completion_gate(bad_prefix) == ["output prefix is not a phase codex output path"]


# --- CLI -----------------------------------------------------------------------


def test_completion_gate_cli_pass(tmp_path: Path, monkeypatch, capsys) -> None:
    codex_dir = _gate_setup(tmp_path, monkeypatch)
    _write_full_attempt(codex_dir, 2)
    prefix = str(_gate_prefix(2))

    exit_code = main(["--completion-gate", prefix])

    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"gate": "pass", "prefix": prefix, "reasons": []}


def test_completion_gate_cli_fail(tmp_path: Path, monkeypatch, capsys) -> None:
    codex_dir = _gate_setup(tmp_path, monkeypatch)
    _write_full_attempt(codex_dir, 2, boundary=_valid_boundary(2, verdict="unverified"))
    prefix = str(_gate_prefix(2))

    exit_code = main(["--completion-gate", prefix])

    assert exit_code == 3
    out = json.loads(capsys.readouterr().out)
    assert out == {"gate": "fail", "prefix": prefix, "reasons": ["isolation boundary not verified"]}


def test_completion_gate_cli_rejects_review_flag() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--completion-gate", "x", "--head", "a" * 40])
    assert exc_info.value.code == 2
