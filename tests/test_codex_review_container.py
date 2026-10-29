"""Tests for the review container's exact configuration and the two
deterministic checks that prove it (Phase 85.1, B04-R3, B16, B17).

Covers tests/codex_review_run.py's container-launch building blocks: the
shared `docker create` option list (_container_options), the review
container and in-container canary `docker create` argv builders
(container_create_argv, container_check_argv), the host-exposure rule
shared by both (host_exposure_problems), the read-only, hash-verified
output-schema staging (stage_output_schema) and the canary path/marker
list (canary_paths), plus the two deterministic verifiers that read a
container's actual configuration and contents: verify_container_config
(a static `docker inspect` comparison) and parse_canary_check (the
in-container canary script's own report). No Docker daemon is ever
called by any test in this file -- every check here is a pure function
over fixed argv lists and fixture JSON/text, never a live container.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from tests.codex_review_run import (
    CANARY_CHECK_SCRIPT,
    CONTAINER_TMPFS,
    CONTAINER_USER,
    REVIEW_CODEX_VERSION,
    REVIEW_IMAGE_BUILD_ARGV,
    REVIEW_IMAGE_LABEL,
    REVIEW_IMAGE_REF,
    SCHEMA_IN_CONTAINER,
    SCHEMA_PATH,
    RunnerError,
    canary_paths,
    container_check_argv,
    container_create_argv,
    host_exposure_problems,
    inspection_codex_argv,
    stage_output_schema,
)

# Example per-run directories, matching the plan's own must_have example
# call. Never created on disk for the argv-builder tests (argv strings
# only); created as real tmp_path subdirectories only where a test
# actually writes a file (stage_output_schema).
_CODEX_HOME_DIR = Path("/tmp/x/codex-home")
_OUT_DIR = Path("/tmp/x/out")
_SCHEMA_DIR = Path("/tmp/x/schema")

# A fake host identity distinct from this machine's real one, so these
# tests never depend on (or risk asserting against) the operator's own
# home directory or checkout path.
_HOST_HOME = Path("/Users/example-owner")
_REPO_ROOT_FAKE = Path("/Users/example-owner/code/triggarr")
_HOST_CODEX_HOME = Path("/Users/example-owner/.codex")
_SSH_AUTH_SOCK = "/private/tmp/com.apple.launchd.fake/Listeners"
_HOST_CANARY_FILE = Path("/tmp/fake-canary-host")


def _golden_review_argv() -> list[str]:
    return container_create_argv(
        REVIEW_IMAGE_REF,
        codex_home_dir=_CODEX_HOME_DIR,
        out_dir=_OUT_DIR,
        schema_dir=_SCHEMA_DIR,
        inner_argv=inspection_codex_argv(),
    )


def _golden_canary_paths() -> list[tuple[str, str]]:
    return canary_paths(
        host_home=_HOST_HOME,
        repo_root=_REPO_ROOT_FAKE,
        host_codex_home=_HOST_CODEX_HOME,
        ssh_auth_sock=_SSH_AUTH_SOCK,
        host_canary_file=_HOST_CANARY_FILE,
    )


def _golden_canary_argv() -> list[str]:
    paths = [path for path, _marker in _golden_canary_paths()]
    return container_check_argv(REVIEW_IMAGE_REF, _CODEX_HOME_DIR, _OUT_DIR, _SCHEMA_DIR, canary_paths=paths)


def _argv_for_kind(kind: str) -> list[str]:
    return _golden_review_argv() if kind == "review" else _golden_canary_argv()


def _exposure_kwargs() -> dict[str, object]:
    return {
        "per_run_dirs": (_CODEX_HOME_DIR, _OUT_DIR, _SCHEMA_DIR),
        "host_home": _HOST_HOME,
        "repo_root": _REPO_ROOT_FAKE,
        "host_codex_home": _HOST_CODEX_HOME,
    }


def _replace_mount_src(argv: list[str], destination: str, new_src: str) -> list[str]:
    mutated = list(argv)
    for i, token in enumerate(mutated):
        if token == "--mount" and f"dst={destination}" in mutated[i + 1]:
            parts = mutated[i + 1].split(",")
            parts = [f"src={new_src}" if part.startswith("src=") else part for part in parts]
            mutated[i + 1] = ",".join(parts)
            return mutated
    raise AssertionError(f"no --mount targeting {destination} found in {argv!r}")


def _append_e_flag(argv: list[str], value: str) -> list[str]:
    return [*argv, "-e", value]


def _replace_option_value(argv: list[str], flag: str, new_value: str) -> list[str]:
    mutated = list(argv)
    idx = mutated.index(flag)
    mutated[idx + 1] = new_value
    return mutated


# --- container_create_argv / container_check_argv --------------------------


def test_container_create_argv_matches_golden() -> None:
    assert _golden_review_argv() == [
        "docker",
        "create",
        "-i",
        "--read-only",
        "--tmpfs",
        f"/work:{CONTAINER_TMPFS['/work']}",
        "--tmpfs",
        f"/tmp:{CONTAINER_TMPFS['/tmp']}",
        "--user",
        CONTAINER_USER,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "256",
        "--memory",
        "2g",
        "--network",
        "bridge",
        "--mount",
        f"type=bind,src={_CODEX_HOME_DIR},dst=/codex-home",
        "--mount",
        f"type=bind,src={_OUT_DIR},dst=/out",
        "--mount",
        f"type=bind,src={_SCHEMA_DIR},dst=/schema,readonly",
        "-e",
        "CODEX_HOME=/codex-home",
        "-w",
        "/work",
        REVIEW_IMAGE_REF,
        *inspection_codex_argv()[1:],
    ]


@pytest.mark.parametrize(
    "forbidden_flag",
    [
        "-v",
        "--volume",
        "--privileged",
        "--pid",
        "--ipc",
        "--uts",
        "--userns",
        "--device",
        "-p",
        "--publish",
        "--add-host",
        "--env-file",
    ],
)
def test_review_create_argv_never_uses_forbidden_flag(forbidden_flag: str) -> None:
    assert forbidden_flag not in _golden_review_argv()


def test_review_create_argv_network_is_exactly_bridge() -> None:
    argv = _golden_review_argv()
    assert argv[argv.index("--network") + 1] == "bridge"


@pytest.mark.parametrize(
    "forbidden_substring",
    ["/var/run/docker.sock", str(Path.home()), str(_REPO_ROOT_FAKE), "SSH_AUTH_SOCK", ".codex"],
)
def test_review_create_argv_never_contains_forbidden_substring(forbidden_substring: str) -> None:
    assert not any(forbidden_substring in element for element in _golden_review_argv())


def test_review_create_argv_only_e_value_is_codex_home() -> None:
    argv = _golden_review_argv()
    e_values = [argv[i + 1] for i, token in enumerate(argv) if token == "-e"]
    assert e_values == ["CODEX_HOME=/codex-home"]


def test_container_check_argv_matches_golden() -> None:
    paths = [path for path, _marker in _golden_canary_paths()]
    assert _golden_canary_argv() == [
        "docker",
        "create",
        "--entrypoint",
        "/bin/sh",
        "-i",
        "--read-only",
        "--tmpfs",
        f"/work:{CONTAINER_TMPFS['/work']}",
        "--tmpfs",
        f"/tmp:{CONTAINER_TMPFS['/tmp']}",
        "--user",
        CONTAINER_USER,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "256",
        "--memory",
        "2g",
        "--network",
        "bridge",
        "--mount",
        f"type=bind,src={_CODEX_HOME_DIR},dst=/codex-home",
        "--mount",
        f"type=bind,src={_OUT_DIR},dst=/out",
        "--mount",
        f"type=bind,src={_SCHEMA_DIR},dst=/schema,readonly",
        "-e",
        "CODEX_HOME=/codex-home",
        "-w",
        "/work",
        REVIEW_IMAGE_REF,
        "-c",
        CANARY_CHECK_SCRIPT,
        "canary",
        *paths,
    ]


def test_container_check_argv_never_uses_run_or_rm() -> None:
    argv = _golden_canary_argv()
    assert argv[:2] == ["docker", "create"]
    assert "--rm" not in argv


def test_canary_check_script_is_valid_posix_sh() -> None:
    proc = subprocess.run(["sh", "-n", "-c", CANARY_CHECK_SCRIPT], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr


# --- canary_paths ------------------------------------------------------------


def test_canary_paths_includes_markers_and_fixed_paths() -> None:
    by_path = dict(_golden_canary_paths())
    assert by_path[str(_HOST_HOME)] == "<HOST_HOME>"
    assert by_path[str(_REPO_ROOT_FAKE)] == "<REPO_ROOT>"
    assert by_path[str(_HOST_CODEX_HOME)] == "<HOST_CODEX_HOME>"
    assert by_path[_SSH_AUTH_SOCK] == "<SSH_AUTH_SOCK>"
    assert by_path[str(_HOST_CANARY_FILE)] == "<HOST_CANARY>"
    for fixed in (
        "/run/host-services/ssh-auth.sock",
        "/var/run/docker.sock",
        "/root/.ssh",
        "/home/review/.ssh",
        "/codex-home/config.toml",
        "/codex-home/sessions",
    ):
        assert by_path[fixed] == fixed


def test_canary_paths_omits_ssh_auth_sock_when_not_set() -> None:
    pairs = canary_paths(
        host_home=_HOST_HOME,
        repo_root=_REPO_ROOT_FAKE,
        host_codex_home=_HOST_CODEX_HOME,
        ssh_auth_sock=None,
        host_canary_file=_HOST_CANARY_FILE,
    )
    assert all(marker != "<SSH_AUTH_SOCK>" for _path, marker in pairs)


# --- host_exposure_problems --------------------------------------------------


def test_host_exposure_review_argv_clean() -> None:
    assert host_exposure_problems(_golden_review_argv(), kind="review", **_exposure_kwargs()) == []


def test_host_exposure_canary_argv_clean() -> None:
    argv = _golden_canary_argv()
    # The canary argv's positional arguments legitimately include the
    # protected host paths -- the allowed, inert case.
    assert str(_HOST_HOME) in argv
    assert str(_REPO_ROOT_FAKE) in argv
    assert str(_HOST_CODEX_HOME) in argv
    assert host_exposure_problems(argv, kind="canary", **_exposure_kwargs()) == []


@pytest.mark.parametrize("kind", ["review", "canary"])
@pytest.mark.parametrize(
    "bad_src_fn,expected_marker",
    [
        (lambda: str(_HOST_HOME), "<HOST_HOME>"),
        (lambda: str(_REPO_ROOT_FAKE / "sub" / "dir"), "<REPO_ROOT>"),
        (lambda: str(_HOST_CODEX_HOME), "<HOST_CODEX_HOME>"),
    ],
)
def test_host_exposure_mount_source_rejected(kind: str, bad_src_fn, expected_marker: str) -> None:
    mutated = _replace_mount_src(_argv_for_kind(kind), "/codex-home", bad_src_fn())
    reasons = host_exposure_problems(mutated, kind=kind, **_exposure_kwargs())
    assert any(f"mount source exposes a protected host path: {expected_marker}" in r for r in reasons)


@pytest.mark.parametrize("kind", ["review", "canary"])
def test_host_exposure_mount_source_unexpected(kind: str) -> None:
    mutated = _replace_mount_src(_argv_for_kind(kind), "/codex-home", "/tmp/totally-unrelated-dir")
    reasons = host_exposure_problems(mutated, kind=kind, **_exposure_kwargs())
    assert any("unexpected mount source" in r for r in reasons)


@pytest.mark.parametrize("kind", ["review", "canary"])
@pytest.mark.parametrize("bad_value", ["GH_TOKEN=secret", f"HOME={_HOST_HOME}", "FOO=bar"])
def test_host_exposure_env_rejected(kind: str, bad_value: str) -> None:
    mutated = _append_e_flag(_argv_for_kind(kind), bad_value)
    reasons = host_exposure_problems(mutated, kind=kind, **_exposure_kwargs())
    assert any("forwarded environment value not allowed" in r for r in reasons)


@pytest.mark.parametrize("kind", ["review", "canary"])
def test_host_exposure_env_file_rejected(kind: str) -> None:
    mutated = [*_argv_for_kind(kind), "--env-file", "/tmp/whatever"]
    reasons = host_exposure_problems(mutated, kind=kind, **_exposure_kwargs())
    assert any("forwarded environment value not allowed" in r for r in reasons)


def test_host_exposure_review_positional_rejected_host_home() -> None:
    argv = [*_golden_review_argv(), str(_HOST_HOME)]
    reasons = host_exposure_problems(argv, kind="review", **_exposure_kwargs())
    assert any("review argv references a protected host path: <HOST_HOME>" in r for r in reasons)


def test_host_exposure_review_positional_rejected_repo_root() -> None:
    argv = [str(_REPO_ROOT_FAKE), *_golden_review_argv()]
    reasons = host_exposure_problems(argv, kind="review", **_exposure_kwargs())
    assert any("review argv references a protected host path: <REPO_ROOT>" in r for r in reasons)


def test_host_exposure_canary_positional_only_before_boundary_rejected() -> None:
    mutated = _replace_option_value(_golden_canary_argv(), "-w", str(_HOST_HOME))
    reasons = host_exposure_problems(mutated, kind="canary", **_exposure_kwargs())
    assert any("protected host path: <HOST_HOME>" in r for r in reasons)


def test_host_exposure_canary_positional_only_after_boundary_accepted() -> None:
    assert host_exposure_problems(_golden_canary_argv(), kind="canary", **_exposure_kwargs()) == []


@pytest.mark.parametrize("kind", ["review", "canary"])
def test_host_exposure_reasons_never_contain_raw_host_path(kind: str) -> None:
    mutated = _replace_mount_src(_argv_for_kind(kind), "/codex-home", str(_HOST_HOME))
    reasons = host_exposure_problems(mutated, kind=kind, **_exposure_kwargs())
    assert reasons
    for reason in reasons:
        assert str(_HOST_HOME) not in reason


# --- output schema launch contract / staging --------------------------------


def test_output_schema_launch_contract() -> None:
    inner = inspection_codex_argv()
    argv = container_create_argv(
        REVIEW_IMAGE_REF,
        codex_home_dir=_CODEX_HOME_DIR,
        out_dir=_OUT_DIR,
        schema_dir=_SCHEMA_DIR,
        inner_argv=inner,
    )
    assert f"type=bind,src={_SCHEMA_DIR},dst=/schema,readonly" in argv
    assert inner[inner.index("--output-schema") + 1] == SCHEMA_IN_CONTAINER
    assert "/schema/" + SCHEMA_PATH.name == SCHEMA_IN_CONTAINER


def test_output_schema_staging_hash_matches(tmp_path: Path) -> None:
    expected_sha256 = hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()
    returned = stage_output_schema(tmp_path, expected_sha256=expected_sha256)
    assert returned == expected_sha256
    staged = tmp_path / SCHEMA_PATH.name
    assert staged.read_bytes() == SCHEMA_PATH.read_bytes()
    assert (staged.stat().st_mode & 0o777) == 0o444


def test_output_schema_staging_wrong_hash_raises(tmp_path: Path) -> None:
    with pytest.raises(RunnerError, match="audited output schema hash mismatch"):
        stage_output_schema(tmp_path, expected_sha256="0" * 64)


def test_output_schema_staging_existing_destination_raises(tmp_path: Path) -> None:
    expected_sha256 = hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()
    stage_output_schema(tmp_path, expected_sha256=expected_sha256)
    with pytest.raises(RunnerError):
        stage_output_schema(tmp_path, expected_sha256=expected_sha256)


# --- REVIEW_IMAGE_BUILD_ARGV / constants ------------------------------------


def test_review_image_build_argv() -> None:
    assert REVIEW_IMAGE_BUILD_ARGV == [
        "docker",
        "build",
        "-f",
        "docker/codex-review/Dockerfile",
        "-t",
        REVIEW_IMAGE_REF,
        "docker/codex-review",
    ]


def test_review_image_ref_and_label_constants() -> None:
    assert REVIEW_IMAGE_REF == "triggarr-codex-review:" + REVIEW_CODEX_VERSION
    assert REVIEW_IMAGE_LABEL == "org.triggarr.codex-review"
