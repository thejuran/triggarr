"""Contract tests for the Dependabot configuration (CIMAINT-02, D-04..D-07)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
DEPENDABOT_CONFIG_PATH = REPO_ROOT / ".github" / "dependabot.yml"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

EXPECTED_ECOSYSTEMS = {"uv", "github-actions", "docker"}
ALLOWED_COOLDOWN_KEYS = {"default-days"}
COOLDOWN_RESTRICTED_ECOSYSTEMS = {"docker", "github-actions"}

# Mirrors tests/test_github_workflows.py's USES_SHA_RE -- kept local so this file has
# no dependency on another test module's internals.
USES_SHA_RE = re.compile(r"^[^@]+@[0-9a-f]{40}$")

# No file under .github/workflows may contain any of these -- each one is a way to
# merge a Dependabot PR (or any PR) outside of exact-commit owner acceptance (D-05).
FORBIDDEN_AUTO_MERGE_SUBSTRINGS = (
    "gh pr merge",
    "--auto",
    "enable-auto-merge",
    "dependabot/fetch-metadata",
    "pull_request_review",
)


def _load_config() -> dict:
    return yaml.safe_load(DEPENDABOT_CONFIG_PATH.read_text())


def _updates() -> list[dict]:
    return _load_config()["updates"]


def _workflow_files() -> list[Path]:
    return sorted(WORKFLOWS_DIR.glob("*.yml"))


def test_dependabot_version_2() -> None:
    """The config declares the only schema version Dependabot's YAML format supports."""
    assert _load_config()["version"] == 2


EXPECTED_ENTRIES = {
    ("uv", "/"),
    ("github-actions", "/"),
    ("docker", "/"),
    # Phase 85.1 WR-10: the digest-pinned review image that holds the Codex sign-in copy.
    ("docker", "/docker/codex-review"),
}


def test_exactly_the_expected_ecosystems_and_directories() -> None:
    """uv, github-actions and docker at "/", plus docker for the review image at /docker/codex-review."""
    updates = _updates()
    entries = [(update["package-ecosystem"], update["directory"]) for update in updates]
    assert len(entries) == len(set(entries))
    assert set(entries) == EXPECTED_ENTRIES
    assert {ecosystem for ecosystem, _directory in entries} == EXPECTED_ECOSYSTEMS


def test_codex_review_image_entry_matches_root_docker_conventions() -> None:
    """WR-10: the review image's docker entry uses the same monthly schedule, cooldown and grouping as root docker."""
    by_entry = {(u["package-ecosystem"], u["directory"]): u for u in _updates()}
    root = by_entry[("docker", "/")]
    review = by_entry[("docker", "/docker/codex-review")]
    assert review["schedule"] == root["schedule"]
    assert review["cooldown"] == root["cooldown"]
    assert review["open-pull-requests-limit"] == root["open-pull-requests-limit"]
    (root_group,) = root["groups"].values()
    (review_group,) = review["groups"].values()
    assert review_group == root_group
    assert set(review["groups"]).isdisjoint(root["groups"])


def test_group_names_are_unique() -> None:
    names = [name for update in _updates() for name in update.get("groups", {})]
    assert len(names) == len(set(names))


def test_monthly_schedule() -> None:
    """Every ecosystem runs on the monthly schedule (D-04)."""
    for update in _updates():
        assert update["schedule"]["interval"] == "monthly"


def test_open_pr_limit_is_bounded() -> None:
    """Each ecosystem caps its open PR count so a backlog can't pile up (D-05)."""
    for update in _updates():
        limit = update["open-pull-requests-limit"]
        assert isinstance(limit, int)
        assert 1 <= limit <= 5


def test_one_minor_patch_group_per_ecosystem() -> None:
    """Each ecosystem groups exactly minor+patch version updates; majors stay ungrouped (D-05)."""
    for update in _updates():
        groups = update.get("groups")
        assert groups is not None
        assert len(groups) == 1
        (group,) = groups.values()
        assert group["applies-to"] == "version-updates"
        assert group["update-types"] == ["minor", "patch"]


def test_no_semver_cooldown_for_docker_or_actions() -> None:
    """docker/github-actions only honor cooldown.default-days -- semver-*-days breaks the whole file (Pitfall 5)."""
    for update in _updates():
        if update["package-ecosystem"] not in COOLDOWN_RESTRICTED_ECOSYSTEMS:
            continue
        cooldown = update.get("cooldown")
        if cooldown is None:
            continue
        assert set(cooldown) <= ALLOWED_COOLDOWN_KEYS


def test_no_auto_merge_in_workflows() -> None:
    """No workflow approves or merges a Dependabot (or any) PR automatically (D-05)."""
    violations = []
    for path in _workflow_files():
        text = path.read_text()
        for substring in FORBIDDEN_AUTO_MERGE_SUBSTRINGS:
            if substring in text:
                violations.append(f"{path.name}: contains {substring!r}")
    assert violations == []


def test_actions_remain_sha_pinned_repo_wide() -> None:
    """Every uses: across every workflow stays pinned to a 40-hex commit SHA, not a tag or branch."""
    for path in _workflow_files():
        workflow = yaml.safe_load(path.read_text())
        for job_id, job in workflow.get("jobs", {}).items():
            for step in job.get("steps", []):
                uses = step.get("uses")
                if uses is None:
                    continue
                assert USES_SHA_RE.match(uses), f"{path.name}:{job_id}: {uses!r} is not pinned to a 40-hex sha"
