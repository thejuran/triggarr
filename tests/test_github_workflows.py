"""Regression tests for GitHub workflow contracts."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
RELEASE_WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text()


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
