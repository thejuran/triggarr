"""Wiring tests for Phase 85 CI changes (Phase 82 D-05: wiring is tested separately from function behavior)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
CI_WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
UV_LOCK = (REPO_ROOT / "uv.lock").read_text()
TOOL_PINS_PATH = REPO_ROOT / ".github" / "tool-pins.env"


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


def _tool_pin(name: str) -> str:
    """Reads a pinned version/checksum from .github/tool-pins.env, so a value
    change there (or in ci.yml) without touching the other fails this test.

    Read lazily, and from a tracked non-planning file, so archiving a phase's
    planning directory can never break collection of this required suite."""
    match = re.search(rf"^{name}=(\S+)$", TOOL_PINS_PATH.read_text(), re.MULTILINE)
    assert match, f"{name} not found in {TOOL_PINS_PATH.relative_to(REPO_ROOT)}"
    return match.group(1)


def _job_raw_block(workflow_text: str, job_id: str) -> str:
    """Raw text of a top-level job's block, from its `  <job_id>:` line up to (but
    excluding) the next top-level job key -- mirrors ci-job-consistency.cjs's parseJobs,
    so continue-on-error can be scanned anywhere in the job (job- or step-level)."""
    lines = workflow_text.split("\n")
    jobs_idx = next(i for i, line in enumerate(lines) if re.match(r"^jobs:\s*$", line))
    start = None
    end = len(lines)
    for i in range(jobs_idx + 1, len(lines)):
        line = lines[i]
        if re.match(r"^\S", line):
            end = i
            break
        if start is None and re.match(rf"^  {re.escape(job_id)}:\s*$", line):
            start = i
            continue
        if start is not None and re.match(r"^  [A-Za-z0-9_.-]+:\s*$", line):
            end = i
            break
    assert start is not None, f"job {job_id!r} not found in workflow text"
    return "\n".join(lines[start:end])


def test_os_scan_job_shape() -> None:
    """D-08/D-09/D-11: os-scan runs right after docker, bounded, never silently skipped."""
    job = _ci_workflow()["jobs"]["os-scan"]

    assert job.get("needs") == ["docker"]
    assert "if" not in job
    assert job["timeout-minutes"] <= 15

    block = _job_raw_block(CI_WORKFLOW, "os-scan")
    assert "continue-on-error" not in block


def test_os_scan_scans_verified_audited_artifact() -> None:
    """The scan runs against the exact audited-image artifact, verified before use, never a rebuild."""
    job = _ci_workflow()["jobs"]["os-scan"]
    steps = job["steps"]

    download_idx = next(
        i
        for i, step in enumerate(steps)
        if str(step.get("uses", "")).startswith("actions/download-artifact")
        and step.get("with", {}).get("name") == "audited-image"
    )
    checksum_idx = next(
        i for i, step in enumerate(steps) if "sha256sum -c image.tar.sha256" in str(step.get("run", ""))
    )
    scan_idx = next(i for i, step in enumerate(steps) if "--pkg-types os" in str(step.get("run", "")))

    assert download_idx < checksum_idx < scan_idx

    for step in steps:
        assert "docker build" not in str(step.get("run", ""))
        assert not str(step.get("uses", "")).startswith("docker/build-push-action")


def test_os_scan_installs_pinned_checksummed_trivy() -> None:
    """CIMAINT-03/T-85-46: Trivy is a pinned, checksum-verified binary, never a wrapper Action."""
    job = _ci_workflow()["jobs"]["os-scan"]
    env = job.get("env", {})

    assert env.get("TRIVY_VERSION") == _tool_pin("TRIVY_VERSION")
    trivy_sha256 = env.get("TRIVY_SHA256")
    assert re.fullmatch(r"[0-9a-f]{64}", str(trivy_sha256))
    assert trivy_sha256 == _tool_pin("TRIVY_LINUX_64BIT_SHA256")

    steps = job["steps"]
    assert any("sha256sum -c" in str(step.get("run", "")) for step in steps)
    for step in steps:
        assert "aquasecurity" not in str(step.get("uses", ""))


def test_os_scan_runs_unfiltered_os_scan() -> None:
    """D-09/Pitfall 2: no result-filtering flag may hide a finding from the classifier."""
    job = _ci_workflow()["jobs"]["os-scan"]
    steps = job["steps"]
    scan_run = next(str(step.get("run", "")) for step in steps if "--pkg-types os" in str(step.get("run", "")))

    assert "image --input" in scan_run
    assert "--pkg-types os" in scan_run
    assert "--format json" in scan_run
    for forbidden in (
        "--ignore-unfixed",
        "--severity",
        "--ignore-status",
        "--skip-db-update",
        "--offline-scan",
        "--exit-code 0",
        "|| true",
    ):
        assert forbidden not in scan_run, f"forbidden flag {forbidden!r} found in the scan step"


def test_os_scan_gate_step_uses_exceptions_file_and_summary() -> None:
    """D-10: the gate consults the owner-approved exceptions file and writes the job summary."""
    job = _ci_workflow()["jobs"]["os-scan"]
    steps = job["steps"]
    gate_run = next(
        str(step.get("run", "")) for step in steps if "os-scan-gate.cjs --report" in str(step.get("run", ""))
    )

    assert "--exceptions .github/os-scan-exceptions.json" in gate_run
    assert '--summary "$GITHUB_STEP_SUMMARY"' in gate_run


def test_actionlint_job_is_unconditional() -> None:
    """CIMAINT-04: a skip can never fake a pass -- the job always runs."""
    job = _ci_workflow()["jobs"]["actionlint"]

    assert "needs" not in job
    assert "if" not in job
    assert job["timeout-minutes"] <= 5

    block = _job_raw_block(CI_WORKFLOW, "actionlint")
    assert "continue-on-error" not in block


def test_actionlint_installs_pinned_checksummed_binary() -> None:
    """actionlint is a pinned, checksum-verified binary, never a wrapper Action."""
    job = _ci_workflow()["jobs"]["actionlint"]
    env = job.get("env", {})

    assert env.get("ACTIONLINT_VERSION") == _tool_pin("ACTIONLINT_VERSION")
    actionlint_sha256 = env.get("ACTIONLINT_SHA256")
    assert re.fullmatch(r"[0-9a-f]{64}", str(actionlint_sha256))
    assert actionlint_sha256 == _tool_pin("ACTIONLINT_SHA256")

    steps = job["steps"]
    assert any("sha256sum -c" in str(step.get("run", "")) for step in steps)
    for step in steps:
        assert "actionlint" not in str(step.get("uses", ""))


def test_actionlint_requires_shellcheck_and_lints_all_workflows() -> None:
    """A missing shellcheck fails the job rather than silently skipping run-step checks."""
    job = _ci_workflow()["jobs"]["actionlint"]
    steps = job["steps"]

    shellcheck_step = next(step for step in steps if "command -v shellcheck" in str(step.get("run", "")))
    shellcheck_run = str(shellcheck_step.get("run", ""))
    assert "exit 1" in shellcheck_run

    lint_step = next(step for step in steps if re.search(r"(^|\s)\./actionlint(\s|$)", str(step.get("run", ""))))
    lint_run = str(lint_step.get("run", "")).strip()
    assert "-ignore" not in lint_run
    assert ".yml" not in lint_run
    assert ".yaml" not in lint_run


def test_new_required_jobs_in_all_three_lists() -> None:
    """os-scan and actionlint join ci-ready's needs, its Python required set, and REQUIRED_JOBS together."""
    ci_ready = _ci_workflow()["jobs"]["ci-ready"]
    needs = ci_ready["needs"]
    assert "os-scan" in needs
    assert "actionlint" in needs

    block = _job_raw_block(CI_WORKFLOW, "ci-ready")
    required_match = re.search(r"required = \{([^}]*)\}", block)
    assert required_match, "ci-ready's Python required set not found"
    required_set = required_match.group(1)
    assert '"os-scan"' in required_set
    assert '"actionlint"' in required_set

    release_policy_text = (REPO_ROOT / ".github" / "scripts" / "release-policy.cjs").read_text()
    match = re.search(r"const REQUIRED_JOBS = \[(.*?)\];", release_policy_text)
    assert match, "REQUIRED_JOBS not found in release-policy.cjs"
    jobs_list = [item.strip().strip("'\"") for item in match.group(1).split(",")]
    assert "os-scan" in jobs_list
    assert "actionlint" in jobs_list
    assert jobs_list[-1] == "CI ready"


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
