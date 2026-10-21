"""Regression tests for GitHub workflow contracts."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
RELEASE_WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text()

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
