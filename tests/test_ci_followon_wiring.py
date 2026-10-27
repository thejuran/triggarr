"""Wiring tests for Phase 85 CI changes (Phase 82 D-05: wiring is tested separately from function behavior)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
CI_WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
UV_LOCK = (REPO_ROOT / "uv.lock").read_text()


def _ci_workflow() -> dict:
    return yaml.safe_load(CI_WORKFLOW)


def _step_by_id(steps: list[dict], step_id: str) -> dict:
    for step in steps:
        if step.get("id") == step_id:
            return step
    raise AssertionError(f"step with id {step_id!r} not found")


def _step_by_name(steps: list[dict], name: str) -> dict:
    for step in steps:
        if step.get("name") == name:
            return step
    raise AssertionError(f"step not found: {name!r}")


def test_test_job_has_no_python_distribution_build() -> None:
    """D-14: the test job no longer builds or uploads a Python distribution; compileall stays."""
    job = _ci_workflow()["jobs"]["test"]
    steps = job["steps"]

    for step in steps:
        run_text = str(step.get("run", ""))
        assert "uv build" not in run_text, f"step {step.get('name')!r} still runs 'uv build'"
        if str(step.get("uses", "")).startswith("actions/upload-artifact"):
            assert step.get("with", {}).get("name") != "python-dist"

    compile_run_texts = [str(step.get("run", "")) for step in steps]
    assert any("compileall" in text for text in compile_run_texts), "compileall step is missing"


def test_test_job_collects_branch_coverage_without_threshold() -> None:
    """CIMAINT-06: branch coverage is collected, no percentage gate, no filtered run."""
    job = _ci_workflow()["jobs"]["test"]
    step = _step_by_id(job["steps"], "pytest")
    run_text = str(step.get("run", ""))

    assert "pytest tests/" in run_text
    assert "--cov=triggarr" in run_text
    assert "--cov-branch" in run_text
    assert "--cov-report=xml:coverage.xml" in run_text
    assert "set +e" in run_text
    assert "fail-under" not in run_text.lower()
    assert "--ignore" not in run_text
    assert " -k " not in run_text
    assert " -m " not in run_text


def test_test_job_reasserts_test_failure_after_coverage_upload() -> None:
    """T-85-32: coverage collection must never mask a real pytest failure."""
    job = _ci_workflow()["jobs"]["test"]
    steps = job["steps"]

    pytest_idx = next(i for i, s in enumerate(steps) if s.get("id") == "pytest")
    pytest_step = steps[pytest_idx]
    pytest_run = str(pytest_step.get("run", ""))
    assert pytest_run.strip().splitlines()[-1].strip() == "exit 0"

    provenance_idx = next(i for i, s in enumerate(steps) if s.get("name") == "Write coverage provenance")
    coverage_upload_idx = next(i for i, s in enumerate(steps) if s.get("name") == "Upload coverage evidence")
    fail_idx = next(i for i, s in enumerate(steps) if s.get("name") == "Fail if tests failed")

    assert pytest_idx < provenance_idx < fail_idx
    assert pytest_idx < coverage_upload_idx < fail_idx
    assert "if" not in steps[provenance_idx]
    assert "if" not in steps[coverage_upload_idx]
    assert "if" not in steps[fail_idx]

    fail_run = str(steps[fail_idx].get("run", ""))
    assert "test_exit" in fail_run.lower()


def test_coverage_artifact_bound_to_run() -> None:
    """CIMAINT-06: the coverage artifact name binds to the exact run id + attempt."""
    job = _ci_workflow()["jobs"]["test"]
    step = _step_by_name(job["steps"], "Upload coverage evidence")
    assert str(step.get("uses", "")).startswith("actions/upload-artifact")

    with_block = step["with"]
    assert "${{ github.run_id }}" in with_block["name"]
    assert "${{ github.run_attempt }}" in with_block["name"]
    assert "coverage.xml" in with_block["path"]
    assert "coverage-provenance.json" in with_block["path"]
    assert with_block["if-no-files-found"] == "error"


def test_provenance_receives_pr_head_and_base() -> None:
    """The provenance step must be able to record the PR head/base distinct from GITHUB_SHA."""
    job = _ci_workflow()["jobs"]["test"]
    step = _step_by_name(job["steps"], "Write coverage provenance")
    env = step.get("env", {})

    assert env.get("PR_HEAD_SHA") == "${{ github.event.pull_request.head.sha }}"
    assert env.get("PR_BASE_SHA") == "${{ github.event.pull_request.base.sha }}"


def test_node_tests_include_planchk_router_by_explicit_path() -> None:
    """D-13: planchk-router tests run by explicit path, gated on Node >= 20."""
    job = _ci_workflow()["jobs"]["test"]
    step = _step_by_name(job["steps"], "Test CI policy scripts and plugin hooks")
    run_text = str(step.get("run", ""))

    assert (
        "node --test .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs"
        in run_text
    )
    assert "process.versions.node" in run_text
    assert "20" in run_text


def _locked_packaging_version() -> str:
    match = re.search(r'name = "packaging"\nversion = "([^"]+)"', UV_LOCK)
    assert match, "packaging version not found in uv.lock"
    return match.group(1)


def test_docker_job_checks_lock_consistency_before_audit_and_save() -> None:
    """CIMAINT-01: the lock-consistency step runs after the audit export and before pip-audit/save."""
    job = _ci_workflow()["jobs"]["docker"]
    steps = job["steps"]
    names = [s.get("name") for s in steps]

    audit_idx = names.index("Audit actual image dependencies")
    consistency_idx = names.index("Check image dependencies match uv.lock")
    vuln_idx = names.index("Check image dependency vulnerabilities")
    save_idx = names.index("Save the audited image")

    assert audit_idx < consistency_idx < vuln_idx
    assert consistency_idx < save_idx


def test_lock_consistency_uses_image_environment_and_exact_export() -> None:
    """The consistency step exports uv.lock exactly, dumps the image's own environment, and compares them."""
    job = _ci_workflow()["jobs"]["docker"]
    step = _step_by_name(job["steps"], "Check image dependencies match uv.lock")
    run_text = str(step.get("run", ""))

    assert "uv export --locked --no-dev --no-emit-project --no-hashes" in run_text
    assert "--dump-environment" in run_text
    assert "triggarr:ci-test" in run_text
    assert "image_lock_consistency.py --locked" in run_text

    version = _locked_packaging_version()
    assert f"--with packaging=={version}" in run_text


def test_lock_consistency_step_has_no_if_or_continue_on_error() -> None:
    """A mismatched image must never be uploaded -- this step cannot be conditionally skipped."""
    job = _ci_workflow()["jobs"]["docker"]
    step = _step_by_name(job["steps"], "Check image dependencies match uv.lock")

    assert "if" not in step
    assert "continue-on-error" not in step
