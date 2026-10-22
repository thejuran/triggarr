"""Regression tests for GitHub workflow contracts."""

from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
RELEASE_WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text()
CI_WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
RELEASE_POLICY_TEXT = (REPO_ROOT / ".github" / "scripts" / "release-policy.cjs").read_text()
CONFTEST_E2E = (REPO_ROOT / "tests" / "e2e" / "conftest.py").read_text()

TAG_ONLY_IF = "github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')"

GATE_STEP_NAMES = (
    "Validate release tag format",
    "Read audited image version label",
    "Verify release version identity",
)

# Steps that perform or trigger publication: pushing to a registry, creating/
# uploading a GitHub Release, or any equivalent promotion action/command.
PUBLICATION_USES_PREFIXES = (
    "docker/login-action",
    "docker/build-push-action",
    "softprops/action-gh-release",
    "ncipollo/release-action",
)
PUBLICATION_RUN_SUBSTRINGS = (
    "docker push",
    "gh release",
    "docker buildx imagetools",
    "skopeo copy",
    "crane ",
    "oras push",
    "twine upload",
    "uv publish",
)
# A bare status-check function call anywhere in an `if:` bypasses the normal
# success-only gating GitHub Actions applies by default.
STATUS_BYPASS_SUBSTRINGS = ("always(", "cancelled(", "failure(")


def _workflow() -> dict:
    return yaml.safe_load(RELEASE_WORKFLOW)


def _normalize_expression(value: str) -> str:
    return " ".join(value.split())


def test_release_workflow_run_requires_same_repo_push_ci() -> None:
    """workflow_run releases must only follow successful same-repo push CI runs."""
    release_job = _workflow()["jobs"]["release"]

    assert _normalize_expression(release_job["if"]) == _normalize_expression(
        """
        (github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')) ||
        (github.event_name == 'workflow_run' &&
         github.event.workflow_run.conclusion == 'success' &&
         github.event.workflow_run.event == 'push' &&
         github.event.workflow_run.head_branch == 'main' &&
         github.event.workflow_run.head_repository.full_name == github.repository)
        """
    )


def test_release_dockerhub_mirror_requires_username_and_token() -> None:
    """Docker Hub image metadata/login must be gated by the detection step."""
    release_job = _workflow()["jobs"]["release"]
    steps = {step.get("name"): step for step in release_job["steps"] if "name" in step}

    detection_step = steps["Detect Docker Hub mirror"]
    assert detection_step["id"] == "dockerhub"
    assert detection_step["env"]["DOCKERHUB_USERNAME"] == "${{ vars.DOCKERHUB_USERNAME }}"
    assert detection_step["env"]["DOCKERHUB_TOKEN"] == "${{ secrets.DOCKERHUB_TOKEN }}"
    assert '[ -n "$DOCKERHUB_USERNAME" ] && [ -n "$DOCKERHUB_TOKEN" ]' in detection_step["run"]

    assert steps["Login to Docker Hub"]["if"] == "steps.dockerhub.outputs.enabled == 'true'"
    assert "${{ steps.dockerhub.outputs.image }}" in steps["Extract metadata"]["with"]["images"]


def test_release_identity_steps_are_tag_only() -> None:
    """The three release-identity steps only run on an actual release tag push."""
    release_job = _workflow()["jobs"]["release"]
    steps = {step.get("name"): step for step in release_job["steps"] if "name" in step}
    for name in GATE_STEP_NAMES:
        assert name in steps, f"missing gate step: {name}"
        assert _normalize_expression(steps[name]["if"]) == _normalize_expression(TAG_ONLY_IF)


def test_identity_step_passes_values_through_env_not_interpolation() -> None:
    """IMAGE_VERSION/RELEASE_SHA must reach the script via env, never `${{ }}` in the body."""
    release_job = _workflow()["jobs"]["release"]
    steps = {step.get("name"): step for step in release_job["steps"] if "name" in step}
    identity_step = steps["Verify release version identity"]
    assert identity_step["env"]["IMAGE_VERSION"] == "${{ steps.image-version.outputs.version }}"
    assert identity_step["env"]["RELEASE_SHA"] == "${{ steps.recheck.outputs.sha }}"
    assert "${{" not in identity_step["with"]["script"]


def test_release_job_permissions_unchanged() -> None:
    """Adding the identity gate must not widen the release job's permissions."""
    release_job = _workflow()["jobs"]["release"]
    assert release_job["permissions"] == {"packages": "write", "contents": "write", "actions": "read"}


def _is_publication_step(step: dict) -> bool:
    uses = str(step.get("uses") or "")
    if any(uses.startswith(prefix) for prefix in PUBLICATION_USES_PREFIXES):
        return True
    run = str(step.get("run") or "")
    return any(substring in run for substring in PUBLICATION_RUN_SUBSTRINGS)


def _has_status_bypass(if_expr: object) -> bool:
    if not if_expr:
        return False
    normalized = _normalize_expression(str(if_expr))
    return any(substring in normalized for substring in STATUS_BYPASS_SUBSTRINGS)


def _job_needs_release(jobs: dict, job_name: str, visited: set[str] | None = None) -> bool:
    if visited is None:
        visited = set()
    if job_name in visited:
        return False
    visited.add(job_name)
    needs = jobs.get(job_name, {}).get("needs")
    if not needs:
        return False
    needs_list = [needs] if isinstance(needs, str) else list(needs)
    if "release" in needs_list:
        return True
    return any(_job_needs_release(jobs, dep, visited) for dep in needs_list)


def publication_bypass_violations(workflow: dict) -> list[str]:
    """Return every way a publication step could run without the release-identity gate.

    A rejection must block every publication path (registry login, image push,
    GitHub Release creation) -- not merely appear earlier in the file (D-31b).
    """
    violations: list[str] = []
    jobs = workflow.get("jobs", {})
    release_job = jobs.get("release", {})
    release_steps = release_job.get("steps", [])

    step_index_by_name = {step.get("name"): idx for idx, step in enumerate(release_steps) if "name" in step}
    gate_index = step_index_by_name.get("Verify release version identity")

    for idx, step in enumerate(release_steps):
        label = step.get("name") or step.get("uses") or step.get("run") or f"step {idx}"
        if _is_publication_step(step):
            if gate_index is None or idx < gate_index:
                violations.append(f"release.{label}: publication step runs before the version identity gate")
            if _has_status_bypass(step.get("if")):
                violations.append(f"release.{label}: publication step if-condition has a status-function bypass")
        if step.get("continue-on-error"):
            violations.append(f"release.{label}: continue-on-error set on a release-job step")

    if release_job.get("continue-on-error"):
        violations.append("release: continue-on-error set on the release job")

    for gate_name in GATE_STEP_NAMES:
        idx = step_index_by_name.get(gate_name)
        if idx is None:
            violations.append(f"release.{gate_name}: gate step is missing")
            continue
        gate_if = _normalize_expression(str(release_steps[idx].get("if", "")))
        if gate_if != _normalize_expression(TAG_ONLY_IF):
            violations.append(f"release.{gate_name}: gate step if-condition is not tag-only")

    for job_name, job in jobs.items():
        if job_name == "release":
            continue
        for step in job.get("steps", []):
            if not _is_publication_step(step):
                continue
            label = step.get("name") or step.get("uses") or step.get("run") or "step"
            needs_release = _job_needs_release(jobs, job_name)
            job_bypass = _has_status_bypass(job.get("if"))
            if not needs_release or job_bypass:
                violations.append(f"{job_name}.{label}: publication step reachable without the release gate")

    on_triggers = workflow.get(True, workflow.get("on"))
    expected_on = {
        "workflow_run": {"workflows": ["CI"], "types": ["completed"], "branches": ["main"]},
        "push": {"tags": ["v*"]},
    }
    if on_triggers != expected_on:
        violations.append("on: workflow triggers differ from the expected workflow_run/push set")

    create_release_idx = step_index_by_name.get("Create GitHub Release")
    if create_release_idx is not None:
        create_release_if = _normalize_expression(str(release_steps[create_release_idx].get("if", "")))
        if create_release_if != _normalize_expression(TAG_ONLY_IF):
            violations.append("release.Create GitHub Release: if-condition is not tag-only")

    meta_idx = step_index_by_name.get("Extract metadata")
    if meta_idx is not None:
        tags_value = release_steps[meta_idx].get("with", {}).get("tags", "")
        latest_lines = [line for line in tags_value.splitlines() if "value=latest" in line]
        if not latest_lines or not all(
            "enable=${{ startsWith(github.ref, 'refs/tags/v') }}" in line for line in latest_lines
        ):
            violations.append("release.Extract metadata: latest tag is not restricted to refs/tags/v")

    return violations


def _step_by_name(steps: list[dict], name: str) -> dict:
    for step in steps:
        if step.get("name") == name:
            return step
    raise AssertionError(f"step not found: {name}")


def _mutate_publish_always(wf: dict) -> None:
    _step_by_name(wf["jobs"]["release"]["steps"], "Publish audited image without rebuilding")["if"] = "always()"


def _mutate_create_release_not_cancelled(wf: dict) -> None:
    _step_by_name(wf["jobs"]["release"]["steps"], "Create GitHub Release")["if"] = "!cancelled()"


def _mutate_dockerhub_login_bypass(wf: dict) -> None:
    _step_by_name(wf["jobs"]["release"]["steps"], "Login to Docker Hub")["if"] = (
        "failure() || steps.dockerhub.outputs.enabled == 'true'"
    )


def _mutate_identity_continue_on_error(wf: dict) -> None:
    _step_by_name(wf["jobs"]["release"]["steps"], "Verify release version identity")["continue-on-error"] = True


def _mutate_release_job_continue_on_error(wf: dict) -> None:
    wf["jobs"]["release"]["continue-on-error"] = True


def _move_identity_step_after_login(wf: dict) -> None:
    steps = wf["jobs"]["release"]["steps"]
    identity_step = next(s for s in steps if s.get("name") == "Verify release version identity")
    steps.remove(identity_step)
    login_idx = next(i for i, s in enumerate(steps) if str(s.get("uses") or "").startswith("docker/login-action"))
    steps.insert(login_idx + 1, identity_step)


def _mutate_identity_if_false(wf: dict) -> None:
    _step_by_name(wf["jobs"]["release"]["steps"], "Verify release version identity")["if"] = "false"


def _mutate_ungated_mirror_job(wf: dict) -> None:
    wf["jobs"]["mirror"] = {
        "runs-on": "ubuntu-latest",
        "steps": [{"run": "docker push ghcr.io/thejuran/triggarr:latest"}],
    }


def _mutate_mirror_job_needs_release_but_always(wf: dict) -> None:
    wf["jobs"]["mirror"] = {
        "runs-on": "ubuntu-latest",
        "needs": ["release"],
        "if": "always()",
        "steps": [{"run": "docker push ghcr.io/thejuran/triggarr:latest"}],
    }


def _mutate_workflow_dispatch_added(wf: dict) -> None:
    triggers = wf[True]
    triggers["workflow_dispatch"] = None


def _enable_latest_unconditionally(wf: dict) -> None:
    meta_step = _step_by_name(wf["jobs"]["release"]["steps"], "Extract metadata")
    tags = meta_step["with"]["tags"]
    meta_step["with"]["tags"] = tags.replace(
        "type=raw,value=latest,enable=${{ startsWith(github.ref, 'refs/tags/v') }}",
        "type=raw,value=latest",
    )


BYPASS_MUTATIONS = [
    ("publish-step-always", _mutate_publish_always),
    ("create-release-not-cancelled", _mutate_create_release_not_cancelled),
    ("dockerhub-login-failure-bypass", _mutate_dockerhub_login_bypass),
    ("identity-step-continue-on-error", _mutate_identity_continue_on_error),
    ("release-job-continue-on-error", _mutate_release_job_continue_on_error),
    ("identity-step-moved-after-login", _move_identity_step_after_login),
    ("identity-step-if-false", _mutate_identity_if_false),
    ("ungated-mirror-job-no-needs", _mutate_ungated_mirror_job),
    ("mirror-job-needs-release-but-always", _mutate_mirror_job_needs_release_but_always),
    ("workflow-dispatch-trigger-added", _mutate_workflow_dispatch_added),
    ("latest-tag-enabled-unconditionally", _enable_latest_unconditionally),
]


@pytest.mark.parametrize("name,mutate", BYPASS_MUTATIONS, ids=[m[0] for m in BYPASS_MUTATIONS])
def test_publication_bypass_violations_detects_bypass(name: str, mutate) -> None:
    """Each named mutation must trip publication_bypass_violations (D-31b)."""
    wf = copy.deepcopy(_workflow())
    mutate(wf)
    violations = publication_bypass_violations(wf)
    assert violations, f"expected a violation for mutation: {name}"


def test_publication_bypass_violations_real_workflow_is_clean() -> None:
    """The real, unmutated release.yml must report no publication bypasses."""
    assert publication_bypass_violations(_workflow()) == []


# ---------------------------------------------------------------------------
# CI workflow wiring tests (D-05, D-11..D-13, D-15, D-18, D-30) -- Plan 82-07
# ---------------------------------------------------------------------------

USES_SHA_RE = re.compile(r"^[^@]+@[0-9a-f]{40}$")
IMAGE_VERSION_FORMAT_RE = re.compile(r"docker image inspect triggarr:ci-test --format\s+'([^']+)'")


def _ci_workflow() -> dict:
    return yaml.safe_load(CI_WORKFLOW)


def _step_text(step: dict) -> str:
    """Concatenate every scalar field on a step so a substring search covers run/uses/name/env."""
    return " ".join(str(step.get(key, "")) for key in ("run", "uses", "name", "env"))


def _step_run_text_by_name(steps: list[dict], name: str) -> str:
    for step in steps:
        if step.get("name") == name:
            return str(step.get("run", ""))
    raise AssertionError(f"step not found: {name}")


def _credential_run_flags() -> list[str]:
    """Read CREDENTIAL_RUN_FLAGS straight out of tests/e2e/conftest.py -- one source of truth."""
    match = re.search(r"CREDENTIAL_RUN_FLAGS[^=]*=\s*\((.*?)\)\n", CONFTEST_E2E, re.DOTALL)
    assert match, "CREDENTIAL_RUN_FLAGS not found in tests/e2e/conftest.py"
    flags = re.findall(r'"([^"]+)"', match.group(1))
    assert flags, "no flags parsed from CREDENTIAL_RUN_FLAGS"
    return flags


def _browser_suite_run_text(job: dict) -> str:
    return _step_run_text_by_name(job["steps"], "Run browser regression suite")


def _pytest_invocation_line(run_text: str, marker: str) -> str:
    lines = [line for line in run_text.splitlines() if "pytest tests/e2e" in line and marker in line]
    assert len(lines) == 1, f"expected exactly one pytest invocation containing {marker!r}, found {len(lines)}"
    return lines[0]


def _image_version_format_strings(text: str) -> list[str]:
    return [m.group(1) for m in IMAGE_VERSION_FORMAT_RE.finditer(text) if "image.version" in m.group(1)]


def image_version_format_matches(ci_run_text: str, release_run_text: str) -> bool:
    """True iff the IMAGE_VERSION docker-inspect --format string matches release.yml's (D-31a).

    A pure comparison function (not a reimplementation of the inspect call
    itself) so a mutated copy of either run block can be fed in directly to
    prove this actually detects drift, not just incidentally agrees.
    """
    ci_formats = _image_version_format_strings(ci_run_text)
    release_formats = _image_version_format_strings(release_run_text)
    return bool(ci_formats) and bool(release_formats) and ci_formats[0] == release_formats[0]


@pytest.mark.parametrize("job_id", ["image-smoke", "browser-e2e"])
def test_new_ci_jobs_depend_only_on_docker_with_no_if(job_id: str) -> None:
    """image-smoke/browser-e2e: needs == ['docker'], no if:, timeout-minutes present and <= 20."""
    job = _ci_workflow()["jobs"][job_id]
    assert job["needs"] == ["docker"]
    assert "if" not in job
    assert "timeout-minutes" in job
    assert job["timeout-minutes"] <= 20


@pytest.mark.parametrize("job_id", ["image-smoke", "browser-e2e"])
def test_new_ci_jobs_verify_audited_image_before_first_use(job_id: str) -> None:
    """Each new job downloads + identity-verifies the audited image before its first real use, never rebuilds it."""
    job = _ci_workflow()["jobs"][job_id]
    steps = job["steps"]

    download_idx = next(
        i
        for i, step in enumerate(steps)
        if str(step.get("uses", "")).startswith("actions/download-artifact")
        and step.get("with", {}).get("name") == "audited-image"
    )
    verify_idx = next(
        i
        for i, step in enumerate(steps)
        if "sha256sum -c image.tar.sha256" in str(step.get("run", "")) and "image-id.txt" in str(step.get("run", ""))
    )
    first_use_idx = next(
        i for i, step in enumerate(steps) if i > verify_idx and "triggarr:ci-test" in _step_text(step)
    )
    assert download_idx < verify_idx < first_use_idx

    for step in steps:
        uses = str(step.get("uses", ""))
        run = str(step.get("run", ""))
        assert not uses.startswith("docker/build-push-action"), job_id
        assert not uses.startswith("docker/setup-buildx-action"), job_id
        assert "docker build" not in run, job_id


def test_every_uses_in_ci_workflow_is_sha_pinned() -> None:
    """Every uses: across every ci.yml job is pinned to a 40-hex commit SHA, not a tag or branch."""
    workflow = _ci_workflow()
    for job_id, job in workflow["jobs"].items():
        for step in job.get("steps", []):
            uses = step.get("uses")
            if uses is None:
                continue
            assert USES_SHA_RE.match(uses), f"{job_id}: {uses!r} is not pinned to a 40-hex sha"


def test_browser_e2e_credential_invocation_has_capture_off() -> None:
    """The credential_pages invocation uses every CREDENTIAL_RUN_FLAGS flag and no failure-only capture flags."""
    job = _ci_workflow()["jobs"]["browser-e2e"]
    run_text = _browser_suite_run_text(job)
    credential_line = _pytest_invocation_line(run_text, "-m credential_pages")
    for flag in _credential_run_flags():
        assert flag in credential_line
    assert "retain-on-failure" not in credential_line
    assert "only-on-failure" not in credential_line


def test_browser_e2e_pages_invocation_has_failure_only_capture() -> None:
    """The non-credential invocation uses failure-only tracing/screenshot capture (D-33)."""
    job = _ci_workflow()["jobs"]["browser-e2e"]
    run_text = _browser_suite_run_text(job)
    pages_line = _pytest_invocation_line(run_text, '-m "not credential_pages"')
    assert "--tracing retain-on-failure" in pages_line
    assert "--screenshot only-on-failure" in pages_line


def test_browser_e2e_no_retries_or_reruns() -> None:
    """D-15: browser tests get no automatic retries that turn a failure into a pass."""
    job = _ci_workflow()["jobs"]["browser-e2e"]
    run_text = _browser_suite_run_text(job)
    assert "reruns" not in run_text
    assert "retries" not in run_text


def test_browser_e2e_upload_step_gated_on_failure_and_scan_markers() -> None:
    """Failure evidence only uploads on failure() and only once both scan-complete.json markers exist."""
    job = _ci_workflow()["jobs"]["browser-e2e"]
    steps = {step.get("name"): step for step in job["steps"] if "name" in step}
    upload_step = steps["Upload browser failure evidence"]
    if_expr = str(upload_step.get("if", ""))
    assert "failure()" in if_expr
    assert "e2e-artifacts/credential/scan-complete.json" in if_expr
    assert "e2e-artifacts/pages/scan-complete.json" in if_expr


def test_browser_e2e_junit_gate_checks_skipped_in_both_files() -> None:
    """An unexplained skip never counts as success (D-12): the junit gate checks skipped in both files."""
    job = _ci_workflow()["jobs"]["browser-e2e"]
    steps = {step.get("name"): step for step in job["steps"] if "name" in step}
    gate_step = steps["Require a complete browser-suite result"]
    run_text = str(gate_step.get("run", ""))
    assert "e2e-credential.xml" in run_text
    assert "e2e-pages.xml" in run_text
    assert "skipped" in run_text


def test_image_smoke_runs_harness_and_rehearsal() -> None:
    """image-smoke runs the real shipped-image smoke driver and the release-identity rehearsal script."""
    job = _ci_workflow()["jobs"]["image-smoke"]
    combined = "\n".join(str(step.get("run", "")) for step in job["steps"])
    assert "tests.harness.image_smoke run --image triggarr:ci-test" in combined
    assert "release-identity-rehearsal.cjs" in combined


def test_image_smoke_rehearsal_step_fidelity() -> None:
    """D-31a: the rehearsal step runs after image verification, with no if/continue-on-error, re-checking identity."""
    job = _ci_workflow()["jobs"]["image-smoke"]
    steps = job["steps"]
    step_names = [step.get("name") for step in steps]
    verify_idx = step_names.index("Verify and load audited image")
    rehearsal_idx = step_names.index("Rehearse release identity against audited image")
    assert rehearsal_idx > verify_idx

    rehearsal_step = steps[rehearsal_idx]
    assert "if" not in rehearsal_step
    assert "continue-on-error" not in rehearsal_step

    run_text = str(rehearsal_step.get("run", ""))
    assert "image/image-id.txt" in run_text
    assert "IMAGE_ID" in run_text
    assert "IMAGE_VERSION" in run_text
    assert "REHEARSAL_SHA" in run_text


def test_image_version_format_matches_real_files() -> None:
    """The rehearsal step's docker-inspect --format string for IMAGE_VERSION matches release.yml's byte-for-byte.

    Both are extracted with the same regex and compared via the pure
    image_version_format_matches() helper -- see
    release.yml's "Read audited image version label" step, which this
    compares against (D-31a).
    """
    job = _ci_workflow()["jobs"]["image-smoke"]
    run_text = _step_run_text_by_name(job["steps"], "Rehearse release identity against audited image")
    release_run_text = _step_run_text_by_name(
        _workflow()["jobs"]["release"]["steps"], "Read audited image version label"
    )
    assert image_version_format_matches(run_text, release_run_text)


def test_image_version_format_mismatch_detected() -> None:
    """A mutated copy with a different format string makes the comparison helper report a mismatch."""
    mutated_run_text = (
        "docker image inspect triggarr:ci-test --format "
        "'{{ index .Config.Labels \"org.opencontainers.image.version.MUTATED\" }}'"
    )
    release_run_text = _step_run_text_by_name(
        _workflow()["jobs"]["release"]["steps"], "Read audited image version label"
    )
    assert not image_version_format_matches(mutated_run_text, release_run_text)


def test_ci_workflow_on_triggers_have_no_path_filters() -> None:
    """D-12: ci.yml runs on push/pull_request to main with no paths/paths-ignore filter."""
    workflow = _ci_workflow()
    on_triggers = workflow.get(True, workflow.get("on"))
    assert on_triggers == {"push": {"branches": ["main"]}, "pull_request": {"branches": ["main"]}}


def test_test_job_runs_full_suite_with_no_filters_and_version_test_exists() -> None:
    """D-18: the test job runs the full suite unfiltered; test_version.py exists; REQUIRED_JOBS requires 'test'."""
    job = _ci_workflow()["jobs"]["test"]
    run_texts = [str(step.get("run", "")) for step in job["steps"]]
    test_run = next(text for text in run_texts if "pytest tests/" in text)
    assert "--ignore" not in test_run
    assert " -k " not in test_run
    assert " -m " not in test_run
    assert (REPO_ROOT / "tests" / "test_version.py").exists()

    required_jobs_match = re.search(r"REQUIRED_JOBS\s*=\s*\[(.*?)\]", RELEASE_POLICY_TEXT)
    assert required_jobs_match, "REQUIRED_JOBS not found in release-policy.cjs"
    assert "'test'" in required_jobs_match.group(1)


def test_ci_ready_if_is_always() -> None:
    """ci-ready keeps its if: always() so the aggregate gate still evaluates even if an upstream job fails."""
    job = _ci_workflow()["jobs"]["ci-ready"]
    assert job["if"] == "always()"
