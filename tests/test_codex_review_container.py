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
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests import codex_review_run
from tests.codex_review_run import (
    CANARY_CHECK_SCRIPT,
    CANARY_RUNTIME_ENV,
    CONTAINER_BASE_ENV,
    CONTAINER_TMPFS,
    CONTAINER_USER,
    KNOWN_TOOL_ITEM_TYPES,
    PROBE_PROMPT_TEMPLATE,
    REVIEW_CODEX_VERSION,
    REVIEW_IMAGE_BUILD_ARGV,
    REVIEW_IMAGE_LABEL,
    REVIEW_IMAGE_REF,
    SCHEMA_IN_CONTAINER,
    SCHEMA_PATH,
    ContainerLedger,
    ExpectedCanary,
    ExpectedContainer,
    ReviewRun,
    RunnerError,
    UnsafeOutputError,
    _probe_tool_use_reasons,
    canary_paths,
    container_check_argv,
    container_create_argv,
    credential_outcome,
    credential_preflight,
    docker_env,
    execute,
    host_credential_path,
    host_exposure_problems,
    inspection_codex_argv,
    main,
    parse_canary_check,
    prepare_codex_home,
    remove_container_confirmed,
    run_boundary_probe,
    run_untrusted_codex,
    safe_read_regular_file,
    stage_output_schema,
    verify_boundary_main,
    verify_container_config,
    verify_isolation_boundary,
)

# A fixed "now" for the credential-preflight tests below, so every test's
# last_refresh offset is exact and independent of wall-clock time.
_NOW = datetime(2026, 10, 28, 12, 0, 0, tzinfo=UTC)
_FIXTURE_REFRESH_TOKEN = "refresh-token-fixture-must-never-leak"  # noqa: S105 -- test fixture, not a real secret


def _auth_bytes(*, last_refresh: str, auth_mode: str = "chatgpt", refresh_token: str = _FIXTURE_REFRESH_TOKEN) -> bytes:
    return json.dumps(
        {
            "auth_mode": auth_mode,
            "OPENAI_API_KEY": None,
            "tokens": {
                "id_token": "id-token-fixture",
                "access_token": "access-token-fixture",
                "refresh_token": refresh_token,
                "account_id": "11111111-1111-1111-1111-111111111111",
            },
            "last_refresh": last_refresh,
        }
    ).encode("utf-8")

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
# Deliberately not nested under _HOST_HOME, so a mount source mutation can
# unambiguously target exactly one protected path at a time.
_REPO_ROOT_FAKE = Path("/opt/build/triggarr-checkout")
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


def test_host_exposure_review_positional_rejected_dotdot_into_repo_root() -> None:
    # A non-tilde absolute path using ".." that still resolves (via
    # os.path.realpath) underneath the protected repo root must be
    # caught exactly like a plain absolute path would be.
    sneaky = str(_REPO_ROOT_FAKE / "sub" / ".." / "other")
    argv = [*_golden_review_argv(), sneaky]
    reasons = host_exposure_problems(argv, kind="review", **_exposure_kwargs())
    assert any("review argv references a protected host path: <REPO_ROOT>" in r for r in reasons)


# --- WR-04: exact allowlist of docker create options -------------------------


def _insert_options(argv: list[str], *options: str) -> list[str]:
    """Insert *options* into the docker option section, just before the image ref."""
    idx = argv.index(REVIEW_IMAGE_REF)
    return [*argv[:idx], *options, *argv[idx:]]


_HOME = str(_HOST_HOME)

_OFF_ALLOWLIST_OPTIONS = [
    pytest.param((f"--mount=type=bind,src={_HOME},dst=/x",), id="mount-equals-form"),
    pytest.param((f"--volume={_HOME}:/h",), id="volume-equals-form"),
    pytest.param(("--volume", f"{_HOME}:/h"), id="volume"),
    pytest.param(("-v", f"{_HOME}:/h"), id="v-home-colon"),
    pytest.param(("--env", "X=Y"), id="env"),
    pytest.param(("--env=X=Y",), id="env-equals-form"),
    pytest.param(("-eX=Y",), id="e-attached"),
    pytest.param(("--env-file=/tmp/x",), id="env-file-equals-form"),
    pytest.param(("--privileged",), id="privileged"),
    pytest.param(("--network=host",), id="network-equals-host"),
    pytest.param(("--pid=host",), id="pid-host"),
    pytest.param(("--cap-add", "SYS_ADMIN"), id="cap-add"),
    pytest.param(("--device", "/dev/null"), id="device"),
    pytest.param(("-p", "8080:8080"), id="publish"),
    pytest.param(("--mount", "type=bind,src=/tmp/x,dst=/y"), id="extra-mount"),
    pytest.param(("--read-only",), id="duplicate-option"),
]


@pytest.mark.parametrize("kind", ["review", "canary"])
@pytest.mark.parametrize("options", _OFF_ALLOWLIST_OPTIONS)
def test_host_exposure_rejects_option_not_on_allowlist(kind: str, options: tuple[str, ...]) -> None:
    mutated = _insert_options(_argv_for_kind(kind), *options)
    reasons = host_exposure_problems(mutated, kind=kind, **_exposure_kwargs())
    assert reasons, f"{options!r} passed the {kind} host-exposure check"
    for reason in reasons:
        assert _HOME not in reason


@pytest.mark.parametrize("kind", ["review", "canary"])
@pytest.mark.parametrize(
    "flag,value",
    [("--network", "host"), ("--user", "0:0"), ("--cap-drop", "NET_RAW"), ("--memory", "64g"), ("-w", "/tmp")],
)
def test_host_exposure_rejects_changed_option_value(kind: str, flag: str, value: str) -> None:
    mutated = _replace_option_value(_argv_for_kind(kind), flag, value)
    assert host_exposure_problems(mutated, kind=kind, **_exposure_kwargs())


@pytest.mark.parametrize("kind", ["review", "canary"])
def test_host_exposure_rejects_mount_source_spelled_source(kind: str) -> None:
    argv = _argv_for_kind(kind)
    idx = argv.index(f"type=bind,src={_CODEX_HOME_DIR},dst=/codex-home")
    mutated = [*argv[:idx], f"type=bind,source={_HOME},dst=/codex-home", *argv[idx + 1 :]]
    reasons = host_exposure_problems(mutated, kind=kind, **_exposure_kwargs())
    assert reasons
    assert all(_HOME not in reason for reason in reasons)


@pytest.mark.parametrize("kind", ["review", "canary"])
def test_host_exposure_rejects_sourceless_mount(kind: str) -> None:
    argv = _argv_for_kind(kind)
    idx = argv.index(f"type=bind,src={_CODEX_HOME_DIR},dst=/codex-home")
    mutated = [*argv[:idx], "type=volume,dst=/codex-home", *argv[idx + 1 :]]
    assert host_exposure_problems(mutated, kind=kind, **_exposure_kwargs())


@pytest.mark.parametrize("kind", ["review", "canary"])
def test_host_exposure_rejects_missing_option(kind: str) -> None:
    argv = _argv_for_kind(kind)
    mutated = list(argv)
    mutated.remove("--read-only")
    assert host_exposure_problems(mutated, kind=kind, **_exposure_kwargs())


@pytest.mark.parametrize("kind", ["review", "canary"])
def test_host_exposure_rejects_other_image(kind: str) -> None:
    argv = _argv_for_kind(kind)
    mutated = [("someone/else:latest" if token == REVIEW_IMAGE_REF else token) for token in argv]
    assert host_exposure_problems(mutated, kind=kind, **_exposure_kwargs())


def test_host_exposure_canary_requires_its_entrypoint() -> None:
    argv = _golden_canary_argv()
    assert argv[2:4] == ["--entrypoint", "/bin/sh"]
    assert host_exposure_problems([*argv[:2], *argv[4:]], kind="canary", **_exposure_kwargs())


def test_host_exposure_review_rejects_entrypoint_override() -> None:
    argv = _golden_review_argv()
    mutated = [*argv[:2], "--entrypoint", "/bin/sh", *argv[2:]]
    assert host_exposure_problems(mutated, kind="review", **_exposure_kwargs())


def test_host_exposure_review_argv_clean_when_cwd_is_repo_root(tmp_path_factory, monkeypatch) -> None:
    """Regression for the 2026-10-29 live run (--verify-boundary always
    unverified): host_exposure_problems() used to call os.path.realpath()
    on every pre-boundary argv token, including fixed non-path literals
    such as "ALL", "bridge", "256" and "no-new-privileges". realpath()
    resolves a relative string against the process's current working
    directory, and since the real runner is always invoked from the
    repository root, every one of those literals resolved underneath
    repo_root and was wrongly flagged. Existing fixtures never caught
    this because they used a fake repo_root distinct from the test
    process's actual cwd (CLAUDE.md), this test reproduces the real
    condition instead: cwd == repo_root, with the per-run scratch
    directories kept outside of it (as they are in real usage) so only
    the cwd/repo_root collision is exercised.
    """
    repo_root = tmp_path_factory.mktemp("repo-root")
    scratch = tmp_path_factory.mktemp("scratch")
    monkeypatch.chdir(repo_root)

    codex_home_dir = scratch / "codex-home"
    out_dir = scratch / "out"
    schema_dir = scratch / "schema"

    review_argv = container_create_argv(
        REVIEW_IMAGE_REF,
        codex_home_dir=codex_home_dir,
        out_dir=out_dir,
        schema_dir=schema_dir,
        inner_argv=inspection_codex_argv(),
    )
    reasons = host_exposure_problems(
        review_argv,
        kind="review",
        per_run_dirs=(codex_home_dir, out_dir, schema_dir),
        host_home=_HOST_HOME,
        repo_root=repo_root,
        host_codex_home=_HOST_CODEX_HOME,
    )
    assert reasons == []


def test_host_exposure_canary_argv_clean_when_cwd_is_repo_root(tmp_path_factory, monkeypatch) -> None:
    """Same regression as the review-argv case above, for the canary argv."""
    repo_root = tmp_path_factory.mktemp("repo-root")
    scratch = tmp_path_factory.mktemp("scratch")
    monkeypatch.chdir(repo_root)

    codex_home_dir = scratch / "codex-home"
    out_dir = scratch / "out"
    schema_dir = scratch / "schema"

    canary_pairs = canary_paths(
        host_home=_HOST_HOME,
        repo_root=repo_root,
        host_codex_home=_HOST_CODEX_HOME,
        ssh_auth_sock=_SSH_AUTH_SOCK,
        host_canary_file=scratch / "host-canary-marker",
    )
    canary_argv = container_check_argv(
        REVIEW_IMAGE_REF,
        codex_home_dir,
        out_dir,
        schema_dir,
        canary_paths=[path for path, _marker in canary_pairs],
    )
    reasons = host_exposure_problems(
        canary_argv,
        kind="canary",
        per_run_dirs=(codex_home_dir, out_dir, schema_dir),
        host_home=_HOST_HOME,
        repo_root=repo_root,
        host_codex_home=_HOST_CODEX_HOME,
    )
    assert reasons == []


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


# --- verify_container_config -------------------------------------------------

_EXPECTED_IMAGE_ID = "sha256:" + "a" * 64
_EXPECTED_ENTRYPOINT = ["codex"]
_EXPECTED_CMD = inspection_codex_argv()[1:]


def _base_mounts() -> list[dict[str, object]]:
    return [
        {"Type": "bind", "Source": str(_CODEX_HOME_DIR), "Destination": "/codex-home", "RW": True},
        {"Type": "bind", "Source": str(_OUT_DIR), "Destination": "/out", "RW": True},
        {"Type": "bind", "Source": str(_SCHEMA_DIR), "Destination": "/schema", "RW": False},
    ]


def _mounts_with_extra(destination: str, *, source: str = "/irrelevant") -> list[dict[str, object]]:
    return [*_base_mounts(), {"Type": "bind", "Source": source, "Destination": destination, "RW": True}]


def _mounts_without(destination: str) -> list[dict[str, object]]:
    return [m for m in _base_mounts() if m["Destination"] != destination]


def _mounts_with_source(destination: str, new_source: str) -> list[dict[str, object]]:
    return [{**m, "Source": new_source} if m["Destination"] == destination else m for m in _base_mounts()]


def _mounts_with_rw(destination: str, rw: bool) -> list[dict[str, object]]:
    return [{**m, "RW": rw} if m["Destination"] == destination else m for m in _base_mounts()]


def _inspect_json(
    *,
    user: str = CONTAINER_USER,
    env: list[str] | None = None,
    entrypoint: list[str] | None = None,
    cmd: list[str] | None = None,
    image: str | None = None,
    labels: dict[str, str] | None = None,
    binds: list[str] | None = None,
    readonly_rootfs: bool = True,
    cap_drop: list[str] | None = None,
    cap_add: list[str] | None = None,
    security_opt: list[str] | None = None,
    privileged: bool = False,
    network_mode: str = "bridge",
    pid_mode: str = "",
    ipc_mode: str = "private",
    uts_mode: str = "",
    userns_mode: str = "",
    devices: list[object] | None = None,
    port_bindings: dict[str, object] | None = None,
    tmpfs: dict[str, str] | None = None,
    mounts: list[dict[str, object]] | None = None,
) -> str:
    """Build a one-element `docker inspect` JSON array for a created (not
    started) review container, with every security-relevant field at its
    expected value unless overridden by a keyword argument -- one mutation
    axis per keyword, so a single-field override exercises exactly one
    verify_container_config() check at a time."""
    container = {
        "Id": "d" * 64,
        "Config": {
            "User": user,
            "Env": [
                "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "HOME=/home/review",
                "LANG=C.UTF-8",
                "CODEX_HOME=/codex-home",
                *(env or []),
            ],
            "Entrypoint": entrypoint if entrypoint is not None else list(_EXPECTED_ENTRYPOINT),
            "Cmd": cmd if cmd is not None else list(_EXPECTED_CMD),
            "Labels": labels if labels is not None else {REVIEW_IMAGE_LABEL: REVIEW_CODEX_VERSION},
        },
        "Image": image if image is not None else _EXPECTED_IMAGE_ID,
        "HostConfig": {
            "Binds": binds,
            "ReadonlyRootfs": readonly_rootfs,
            "CapDrop": cap_drop if cap_drop is not None else ["ALL"],
            "CapAdd": cap_add,
            "SecurityOpt": security_opt if security_opt is not None else ["no-new-privileges"],
            "Privileged": privileged,
            "NetworkMode": network_mode,
            "PidMode": pid_mode,
            "IpcMode": ipc_mode,
            "UTSMode": uts_mode,
            "UsernsMode": userns_mode,
            "Devices": devices if devices is not None else [],
            "PortBindings": port_bindings if port_bindings is not None else {},
            "Tmpfs": tmpfs if tmpfs is not None else dict(CONTAINER_TMPFS),
        },
        "Mounts": mounts if mounts is not None else _base_mounts(),
    }
    return json.dumps([container])


_EXPECTED = ExpectedContainer(
    image_id=_EXPECTED_IMAGE_ID,
    mounts={
        "/codex-home": (str(_CODEX_HOME_DIR), True),
        "/out": (str(_OUT_DIR), True),
        "/schema": (str(_SCHEMA_DIR), False),
    },
    tmpfs=frozenset({"/work", "/tmp"}),
    user=CONTAINER_USER,
    env_names=CONTAINER_BASE_ENV,
    entrypoint=list(_EXPECTED_ENTRYPOINT),
    cmd=list(_EXPECTED_CMD),
)

_VCC_MUTATIONS = [
    pytest.param(
        {"mounts": _mounts_with_extra("/host", source=str(_HOST_HOME))},
        "unexpected mount: /host",
        id="extra_host_mount",
    ),
    pytest.param({"mounts": _mounts_without("/out")}, "missing mount: /out", id="missing_out_mount"),
    pytest.param(
        {"mounts": _mounts_with_source("/codex-home", "/elsewhere")},
        "mount source mismatch: /codex-home",
        id="codex_home_source_mismatch",
    ),
    pytest.param({"mounts": _mounts_with_rw("/schema", True)}, "schema mount is writable", id="schema_writable"),
    pytest.param(
        {"mounts": _mounts_with_extra("/var/run/docker.sock", source="/var/run/docker.sock")},
        "unexpected mount: /var/run/docker.sock",
        id="docker_socket_mounted",
    ),
    pytest.param({"binds": ["/x:/y"]}, "unexpected bind", id="binds_nonempty"),
    pytest.param({"tmpfs": {**CONTAINER_TMPFS, "/home": "rw"}}, "unexpected tmpfs", id="tmpfs_extra_home"),
    pytest.param({"user": ""}, "container user is not 10001:10001", id="user_empty"),
    pytest.param({"user": "0"}, "container user is not 10001:10001", id="user_zero"),
    pytest.param({"user": "root"}, "container user is not 10001:10001", id="user_root"),
    pytest.param({"privileged": True}, "privileged container", id="privileged"),
    pytest.param({"cap_drop": []}, "capabilities not dropped", id="cap_drop_empty"),
    pytest.param({"cap_add": ["NET_ADMIN"]}, "capabilities not dropped", id="cap_add_net_admin"),
    pytest.param({"readonly_rootfs": False}, "root filesystem is writable", id="rootfs_writable"),
    pytest.param({"security_opt": []}, "no-new-privileges not set", id="no_new_privileges_missing"),
    pytest.param(
        {"security_opt": ["no-new-privileges", "seccomp=unconfined"]},
        "security profile disabled",
        id="seccomp_unconfined",
    ),
    pytest.param(
        {"security_opt": ["no-new-privileges", "apparmor=unconfined"]},
        "security profile disabled",
        id="apparmor_unconfined",
    ),
    pytest.param({"network_mode": "host"}, "network mode is not bridge: host", id="network_host"),
    pytest.param({"port_bindings": {"8080/tcp": []}}, "published ports", id="port_bindings_nonempty"),
    pytest.param({"pid_mode": "host"}, "host namespace: pid", id="pid_host"),
    pytest.param({"ipc_mode": "host"}, "host namespace: ipc", id="ipc_host"),
    pytest.param({"uts_mode": "host"}, "host namespace: uts", id="uts_host"),
    pytest.param({"userns_mode": "host"}, "host namespace: userns", id="userns_host"),
    pytest.param({"devices": [{"PathOnHost": "/dev/sda"}]}, "host devices exposed", id="devices_nonempty"),
    pytest.param({"env": ["GH_TOKEN=secret"]}, "unexpected environment variable: GH_TOKEN", id="env_gh_token"),
    pytest.param({"env": ["HOSTNAME=abc123"]}, "unexpected environment variable: HOSTNAME", id="env_hostname"),
    pytest.param({"env": ["PWD=/work"]}, "unexpected environment variable: PWD", id="env_pwd"),
    pytest.param({"env": ["SHLVL=1"]}, "unexpected environment variable: SHLVL", id="env_shlvl"),
    pytest.param({"image": "sha256:" + "b" * 64}, "image mismatch", id="image_mismatch"),
    pytest.param({"entrypoint": ["sh"]}, "container command mismatch", id="entrypoint_mismatch"),
    pytest.param({"cmd": ["codex", "exec"]}, "container command mismatch", id="cmd_mismatch"),
]


@pytest.mark.parametrize("mutation,expected_substring", _VCC_MUTATIONS)
def test_verify_container_config_rejects(mutation: dict[str, object], expected_substring: str) -> None:
    reasons = verify_container_config(_inspect_json(**mutation), _EXPECTED)
    assert any(expected_substring in r for r in reasons), reasons


def test_verify_container_config_clean_fixture_passes() -> None:
    assert verify_container_config(_inspect_json(), _EXPECTED) == []


@pytest.mark.parametrize(
    "bad_json",
    [
        "not json at all",
        json.dumps([]),
        json.dumps([{"Config": {}, "Mounts": []}]),
    ],
    ids=["not_json", "empty_array", "missing_hostconfig_key"],
)
def test_verify_container_config_malformed_input(bad_json: str) -> None:
    assert verify_container_config(bad_json, _EXPECTED) == ["could not read docker inspect output"]


def test_verify_container_config_mount_source_realpath_equivalence(tmp_path: Path) -> None:
    # Docker Desktop may report /private/var/... for a source given as
    # /var/...; the comparison must survive that representational
    # difference for a source that is genuinely the same real path.
    real_dir = tmp_path / "codex-home"
    real_dir.mkdir()
    expected = ExpectedContainer(
        image_id=_EXPECTED.image_id,
        mounts={**_EXPECTED.mounts, "/codex-home": (str(real_dir), True)},
        tmpfs=_EXPECTED.tmpfs,
        user=_EXPECTED.user,
        env_names=_EXPECTED.env_names,
        entrypoint=_EXPECTED.entrypoint,
        cmd=_EXPECTED.cmd,
    )
    mounts = [
        {"Type": "bind", "Source": str(real_dir) + "/.", "Destination": "/codex-home", "RW": True},
        {"Type": "bind", "Source": str(_OUT_DIR), "Destination": "/out", "RW": True},
        {"Type": "bind", "Source": str(_SCHEMA_DIR), "Destination": "/schema", "RW": False},
    ]
    assert verify_container_config(_inspect_json(mounts=mounts), expected) == []


# --- parse_canary_check ------------------------------------------------------


def _clean_canary_expected() -> ExpectedCanary:
    return ExpectedCanary(
        paths=tuple(_golden_canary_paths()),
        schema_sha256=hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest(),
        env_names=CONTAINER_BASE_ENV | CANARY_RUNTIME_ENV,
    )


def _clean_canary_stdout(expected: ExpectedCanary) -> str:
    lines = [f"absent {path}" for path, _marker in expected.paths]
    lines.append("work-entries 0")
    lines.append("codex-home-entry auth.json")
    lines.append(f"schema-sha256 {expected.schema_sha256}")
    lines += [f"env {name}" for name in sorted(expected.env_names)]
    lines.append("canary-done")
    return "\n".join(lines)


def test_parse_canary_check_clean_fixture_passes() -> None:
    expected = _clean_canary_expected()
    assert parse_canary_check(_clean_canary_stdout(expected), expected) == []


def test_parse_canary_check_present_host_home_rejected() -> None:
    expected = _clean_canary_expected()
    text = _clean_canary_stdout(expected).replace(f"absent {_HOST_HOME}", f"present {_HOST_HOME}")
    reasons = parse_canary_check(text, expected)
    assert any("canary path visible in container: <HOST_HOME>" in r for r in reasons)


def test_parse_canary_check_present_docker_socket_rejected() -> None:
    expected = _clean_canary_expected()
    text = _clean_canary_stdout(expected).replace(
        "absent /var/run/docker.sock", "present /var/run/docker.sock"
    )
    reasons = parse_canary_check(text, expected)
    assert any("canary path visible in container: /var/run/docker.sock" in r for r in reasons)


def test_parse_canary_check_work_entries_nonzero_rejected() -> None:
    expected = _clean_canary_expected()
    text = _clean_canary_stdout(expected).replace("work-entries 0", "work-entries 1")
    reasons = parse_canary_check(text, expected)
    assert any("review working directory not empty" in r for r in reasons)


def test_parse_canary_check_extra_codex_home_entry_rejected() -> None:
    expected = _clean_canary_expected()
    text = _clean_canary_stdout(expected).replace(
        "codex-home-entry auth.json", "codex-home-entry auth.json\ncodex-home-entry config.toml"
    )
    reasons = parse_canary_check(text, expected)
    assert any("unexpected /codex-home contents" in r for r in reasons)


def test_parse_canary_check_no_codex_home_entry_rejected() -> None:
    expected = _clean_canary_expected()
    lines = [line for line in _clean_canary_stdout(expected).splitlines() if not line.startswith("codex-home-entry")]
    reasons = parse_canary_check("\n".join(lines), expected)
    assert any("unexpected /codex-home contents" in r for r in reasons)


def test_parse_canary_check_schema_hash_mismatch_rejected() -> None:
    expected = _clean_canary_expected()
    text = _clean_canary_stdout(expected).replace(expected.schema_sha256, "0" * 64)
    reasons = parse_canary_check(text, expected)
    assert any("output schema hash mismatch inside the container" in r for r in reasons)


def test_parse_canary_check_unexpected_env_var_rejected() -> None:
    expected = _clean_canary_expected()
    text = _clean_canary_stdout(expected).replace("canary-done", "env GH_TOKEN\ncanary-done")
    reasons = parse_canary_check(text, expected)
    assert any("unexpected environment variable in container: GH_TOKEN" in r for r in reasons)


def test_parse_canary_check_accepts_hostname_and_pwd() -> None:
    expected = _clean_canary_expected()
    assert "HOSTNAME" in expected.env_names
    assert "PWD" in expected.env_names
    assert parse_canary_check(_clean_canary_stdout(expected), expected) == []


def test_parse_canary_check_rejects_shlvl() -> None:
    expected = _clean_canary_expected()
    text = _clean_canary_stdout(expected).replace("canary-done", "env SHLVL\ncanary-done")
    reasons = parse_canary_check(text, expected)
    assert any("unexpected environment variable in container: SHLVL" in r for r in reasons)


def test_parse_canary_check_missing_canary_done_fails_closed() -> None:
    expected = _clean_canary_expected()
    lines = [line for line in _clean_canary_stdout(expected).splitlines() if line != "canary-done"]
    reasons = parse_canary_check("\n".join(lines), expected)
    assert reasons == ["could not parse canary check output"]


def test_parse_canary_check_missing_path_line_fails_closed() -> None:
    expected = _clean_canary_expected()
    lines = [line for line in _clean_canary_stdout(expected).splitlines() if line != f"absent {_HOST_HOME}"]
    reasons = parse_canary_check("\n".join(lines), expected)
    assert reasons == ["could not parse canary check output"]


def test_parse_canary_check_duplicate_line_fails_closed() -> None:
    expected = _clean_canary_expected()
    duplicated = _clean_canary_stdout(expected) + "\nwork-entries 0"
    reasons = parse_canary_check(duplicated, expected)
    assert reasons == ["could not parse canary check output"]


def test_parse_canary_check_unknown_line_fails_closed() -> None:
    expected = _clean_canary_expected()
    text = _clean_canary_stdout(expected).replace("canary-done", "mystery-data\ncanary-done")
    reasons = parse_canary_check(text, expected)
    assert reasons == ["could not parse canary check output"]


# --- CONTAINER_BASE_ENV / CANARY_RUNTIME_ENV constants -----------------------


def test_container_base_env_and_canary_runtime_env_constants() -> None:
    assert frozenset({"PATH", "HOME", "LANG", "CODEX_HOME"}) == CONTAINER_BASE_ENV
    assert frozenset({"HOSTNAME", "PWD"}) == CANARY_RUNTIME_ENV
    assert CONTAINER_BASE_ENV.isdisjoint(CANARY_RUNTIME_ENV)


# --- host_credential_path -----------------------------------------------


def test_host_credential_path_uses_codex_home_env() -> None:
    assert host_credential_path({"CODEX_HOME": "/x"}) == Path("/x/auth.json")


def test_host_credential_path_defaults_to_home_dot_codex(monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/fake-owner")))
    assert host_credential_path({}) == Path("/home/fake-owner/.codex/auth.json")


# --- credential_preflight (D-06, D-11 amendment) -------------------------


def test_credential_preflight_six_days_ok() -> None:
    last_refresh = (_NOW - timedelta(days=6)).isoformat()
    result = credential_preflight(_auth_bytes(last_refresh=last_refresh), now=_NOW)
    assert result == {"last_refresh": last_refresh, "age_seconds": 518400}


def test_credential_preflight_seven_day_boundary() -> None:
    last_refresh_ok = (_NOW - timedelta(days=7)).isoformat()
    result = credential_preflight(_auth_bytes(last_refresh=last_refresh_ok), now=_NOW)
    assert result["age_seconds"] == 7 * 86400

    last_refresh_over = (_NOW - timedelta(days=7, seconds=1)).isoformat()
    with pytest.raises(RunnerError):
        credential_preflight(_auth_bytes(last_refresh=last_refresh_over), now=_NOW)


def test_credential_preflight_eight_days_refused() -> None:
    last_refresh = (_NOW - timedelta(days=8)).isoformat()
    with pytest.raises(RunnerError) as exc_info:
        credential_preflight(_auth_bytes(last_refresh=last_refresh), now=_NOW)
    message = str(exc_info.value)
    assert "last refreshed 8.0 days ago (limit 7 days)" in message
    assert "run `codex login` (or use Codex on the host) first" in message
    assert _FIXTURE_REFRESH_TOKEN not in message


def test_credential_preflight_future_timestamp() -> None:
    last_refresh = (_NOW + timedelta(seconds=301)).isoformat()
    with pytest.raises(RunnerError, match="last_refresh is in the future"):
        credential_preflight(_auth_bytes(last_refresh=last_refresh), now=_NOW)


def test_credential_preflight_future_timestamp_within_skew_accepted() -> None:
    last_refresh = (_NOW + timedelta(seconds=300)).isoformat()
    result = credential_preflight(_auth_bytes(last_refresh=last_refresh), now=_NOW)
    assert result["age_seconds"] == -300


@pytest.mark.parametrize(
    "raw",
    [
        b"not json at all",
        _auth_bytes(last_refresh=(_NOW - timedelta(days=1)).isoformat(), auth_mode="apikey"),
        _auth_bytes(last_refresh=(_NOW - timedelta(days=1)).isoformat(), refresh_token=""),
        _auth_bytes(last_refresh="not-a-timestamp"),
    ],
    ids=["non_json", "wrong_auth_mode", "empty_refresh_token", "unparseable_last_refresh"],
)
def test_credential_preflight_malformed(raw: bytes) -> None:
    with pytest.raises(RunnerError) as exc_info:
        credential_preflight(raw, now=_NOW)
    message = str(exc_info.value)
    assert message.startswith("Codex sign-in not usable for an untrusted review:")
    assert _FIXTURE_REFRESH_TOKEN not in message


def test_credential_no_24_hour_rule() -> None:
    last_refresh = (_NOW - timedelta(hours=30)).isoformat()
    result = credential_preflight(_auth_bytes(last_refresh=last_refresh), now=_NOW)
    assert result["age_seconds"] == 30 * 3600


# --- prepare_codex_home ----------------------------------------------------


def test_prepare_codex_home_copies_exact_snapshot(tmp_path: Path, monkeypatch) -> None:
    host_dir = tmp_path / "host-codex"
    host_dir.mkdir()
    host_path = host_dir / "auth.json"
    last_refresh = (_NOW - timedelta(days=1)).isoformat()
    raw = _auth_bytes(last_refresh=last_refresh)
    host_path.write_bytes(raw)
    host_path.chmod(0o600)

    read_calls: list[tuple[Path, str]] = []
    real_safe_read = codex_review_run.safe_read_regular_file

    def _counting_safe_read(dir_path, name, *, max_bytes):
        read_calls.append((Path(dir_path), name))
        return real_safe_read(dir_path, name, max_bytes=max_bytes)

    monkeypatch.setattr(codex_review_run, "safe_read_regular_file", _counting_safe_read)

    dest = tmp_path / "codex-home"
    sha256, preflight_info = prepare_codex_home(host_path, dest, now=_NOW)

    host_reads = [c for c in read_calls if c == (host_dir, "auth.json")]
    assert len(host_reads) == 1
    assert sha256 == hashlib.sha256(raw).hexdigest()
    assert preflight_info["last_refresh"] == last_refresh
    assert (dest.stat().st_mode & 0o777) == 0o700
    copy_path = dest / "auth.json"
    assert sorted(p.name for p in dest.iterdir()) == ["auth.json"]
    assert (copy_path.stat().st_mode & 0o777) == 0o600
    assert copy_path.read_bytes() == raw

    host_path.write_bytes(_auth_bytes(last_refresh=(_NOW - timedelta(days=2)).isoformat()))
    assert copy_path.read_bytes() == raw
    assert sha256 == hashlib.sha256(raw).hexdigest()


def test_prepare_codex_home_refuses_before_copy(tmp_path: Path) -> None:
    dest = tmp_path / "codex-home"

    missing_host = tmp_path / "missing-dir" / "auth.json"
    with pytest.raises(RunnerError):
        prepare_codex_home(missing_host, dest, now=_NOW)
    assert not dest.exists()

    host_dir2 = tmp_path / "host2"
    host_dir2.mkdir()
    real_secret = tmp_path / "real-secret.json"
    real_secret.write_bytes(_auth_bytes(last_refresh=(_NOW - timedelta(days=1)).isoformat()))
    symlinked_host = host_dir2 / "auth.json"
    symlinked_host.symlink_to(real_secret)
    with pytest.raises(RunnerError):
        prepare_codex_home(symlinked_host, dest, now=_NOW)
    assert not dest.exists()

    host_dir3 = tmp_path / "host3"
    host_dir3.mkdir()
    stale_host = host_dir3 / "auth.json"
    stale_host.write_bytes(_auth_bytes(last_refresh=(_NOW - timedelta(days=8)).isoformat()))
    with pytest.raises(RunnerError):
        prepare_codex_home(stale_host, dest, now=_NOW)
    assert not dest.exists()

    host_dir4 = tmp_path / "host4"
    host_dir4.mkdir()
    good_host = host_dir4 / "auth.json"
    good_host.write_bytes(_auth_bytes(last_refresh=(_NOW - timedelta(days=1)).isoformat()))
    dest.mkdir()
    with pytest.raises(RunnerError):
        prepare_codex_home(good_host, dest, now=_NOW)


# --- credential_outcome ------------------------------------------------------


def test_credential_outcome_unchanged(tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    raw = _auth_bytes(last_refresh=(_NOW - timedelta(days=1)).isoformat())
    (codex_home / "auth.json").write_bytes(raw)
    before_sha256 = hashlib.sha256(raw).hexdigest()
    assert credential_outcome(codex_home, before_sha256=before_sha256) == []


def test_credential_outcome_refreshed(tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    raw = _auth_bytes(last_refresh=(_NOW - timedelta(days=1)).isoformat())
    before_sha256 = hashlib.sha256(raw).hexdigest()
    (codex_home / "auth.json").write_bytes(_auth_bytes(last_refresh=_NOW.isoformat()))
    problems = credential_outcome(codex_home, before_sha256=before_sha256)
    assert problems == [
        "Codex refreshed its sign-in inside the review container; the host login has likely been signed out."
        " Re-login needed: run `codex login` on the host (D-11). The refreshed copy was deleted and never"
        " copied back."
    ]


def test_credential_outcome_deleted(tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    problems = credential_outcome(codex_home, before_sha256="0" * 64)
    assert len(problems) == 1
    assert problems[0].startswith("could not confirm the Codex sign-in copy was unchanged")


def test_credential_outcome_symlinked(tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    target = tmp_path / "elsewhere.json"
    target.write_bytes(b"{}")
    (codex_home / "auth.json").symlink_to(target)
    problems = credential_outcome(codex_home, before_sha256="0" * 64)
    assert len(problems) == 1
    assert problems[0].startswith("could not confirm the Codex sign-in copy was unchanged")


def test_credential_outcome_fifo(tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    os.mkfifo(codex_home / "auth.json")
    problems = credential_outcome(codex_home, before_sha256="0" * 64)
    assert len(problems) == 1
    assert problems[0].startswith("could not confirm the Codex sign-in copy was unchanged")


def test_credential_outcome_never_writes_host_file(tmp_path: Path) -> None:
    host_dir = tmp_path / "host"
    host_dir.mkdir()
    host_path = host_dir / "auth.json"
    raw = _auth_bytes(last_refresh=(_NOW - timedelta(days=1)).isoformat())
    host_path.write_bytes(raw)
    before_mtime = host_path.stat().st_mtime_ns

    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    (codex_home / "auth.json").write_bytes(_auth_bytes(last_refresh=_NOW.isoformat()))
    credential_outcome(codex_home, before_sha256=hashlib.sha256(raw).hexdigest())

    assert host_path.stat().st_mtime_ns == before_mtime
    assert host_path.read_bytes() == raw


# --- safe_read_regular_file (B15) -------------------------------------------


def test_safe_read_refuses_symlink(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("do not leak")
    (out_dir / "last.json").symlink_to(secret)
    with pytest.raises(UnsafeOutputError, match="refused: last.json is a symlink"):
        safe_read_regular_file(out_dir, "last.json", max_bytes=1024)


def test_safe_read_refuses_fifo(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    os.mkfifo(out_dir / "last.json")
    start = time.monotonic()
    with pytest.raises(UnsafeOutputError, match="refused: last.json is not a regular file"):
        safe_read_regular_file(out_dir, "last.json", max_bytes=1024)
    assert time.monotonic() - start < 2


def test_safe_read_bounds_size(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    big = out_dir / "last.json"
    big.write_bytes(b"x" * 2048)
    with pytest.raises(UnsafeOutputError, match=r"refused: last\.json exceeds 1024 bytes"):
        safe_read_regular_file(out_dir, "last.json", max_bytes=1024)

    small = out_dir / "small.json"
    small.write_bytes(b"ok")
    assert safe_read_regular_file(out_dir, "small.json", max_bytes=1024) == b"ok"

    with pytest.raises(FileNotFoundError):
        safe_read_regular_file(out_dir, "missing.json", max_bytes=1024)


def test_safe_read_refuses_symlinked_directory(tmp_path: Path) -> None:
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "last.json").write_bytes(b"ok")
    linked_dir = tmp_path / "linked"
    linked_dir.symlink_to(real_dir)
    with pytest.raises(UnsafeOutputError):
        safe_read_regular_file(linked_dir, "last.json", max_bytes=1024)


# --- docker_env --------------------------------------------------------------


def test_docker_env_filters_to_allowed_names() -> None:
    environ = {
        "PATH": "p",
        "HOME": "h",
        "GH_TOKEN": "t",
        "SSH_AUTH_SOCK": "s",
        "DOCKER_HOST": "d",
        "OPENAI_API_KEY": "k",
        "CODEX_API_KEY": "c",
    }
    assert docker_env(environ) == {"PATH": "p", "HOME": "h", "DOCKER_HOST": "d"}


# --- Scripted docker runner for container-lifecycle tests -------------------


class _DockerRunner:
    """Scripted docker runner answering `docker rm -f`/`docker ps -a` for
    container-lifecycle tests (remove_container_confirmed, ContainerLedger).

    *live* is the set of container IDs `docker ps -a` reports present.
    *rm_breaks* is the set of IDs whose `docker rm -f` exits 1 without
    removing the ID from *live* (simulating a removal failure); every
    other ID is removed from *live* when `docker rm -f` runs, whatever
    exit code a real docker would report (the exit code is not what the
    caller trusts). *ps_breaks* is the set of IDs whose `docker ps -a`
    check exits non-zero (indeterminate) even if already absent from
    *live*. *raise_on* maps "rm" or "ps" to an exception class to raise
    instead of answering that command at all. Extended in Plan 85.1-08
    Task 3 to also answer `docker image inspect`/`docker create`/
    `docker inspect`/`docker start` for the boundary and launch tests.
    """

    def __init__(
        self,
        *,
        live: set[str] | None = None,
        rm_breaks: set[str] | None = None,
        ps_breaks: set[str] | None = None,
        raise_on: dict[str, type[BaseException]] | None = None,
        image_ok: bool = True,
        image_id: str = "sha256:" + "a" * 64,
        codex_version: str = REVIEW_CODEX_VERSION,
        canary_id: str = "c" * 64,
        canary_stdout: str | None = None,
        canary_start_raises: type[BaseException] | None = None,
        review_id: str = "d" * 64,
        review_inspect_json: str | None = None,
        review_start_raises: type[BaseException] | None = None,
        start_returncode: int = 0,
        host_home: Path | None = None,
        repo_root: Path | None = None,
        host_codex_home: Path | None = None,
        ssh_auth_sock: str | None = None,
        expected_schema_sha256: str | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self.envs: list[dict | None] = []
        self.live = set(live or ())
        self.rm_breaks = set(rm_breaks or ())
        self.ps_breaks = set(ps_breaks or ())
        self.raise_on = raise_on or {}
        self.image_ok = image_ok
        self.image_id = image_id
        self.codex_version = codex_version
        self.canary_id = canary_id
        self.canary_stdout = canary_stdout
        self.canary_start_raises = canary_start_raises
        self.review_id = review_id
        self.review_inspect_json = review_inspect_json
        self.review_start_raises = review_start_raises
        self.start_returncode = start_returncode
        # Supplied when canary_stdout/review_inspect_json are left None, so
        # a clean response can be generated from the *actual* --mount
        # sources a test's own docker-create call used (needed when the
        # caller creates its own per-run scratch dir via tempfile.mkdtemp,
        # whose path the test cannot predict in advance).
        self.host_home = host_home
        self.repo_root = repo_root
        self.host_codex_home = host_codex_home
        self.ssh_auth_sock = ssh_auth_sock
        self.expected_schema_sha256 = expected_schema_sha256
        self._last_mounts: dict[str, str] = {}

    def _record_mounts(self, argv: list[str]) -> None:
        mounts: dict[str, str] = {}
        for i, tok in enumerate(argv):
            if tok == "--mount":
                parts = dict(p.split("=", 1) for p in argv[i + 1].split(",") if "=" in p)
                if "dst" in parts and "src" in parts:
                    mounts[parts["dst"]] = parts["src"]
        self._last_mounts = mounts

    def _auto_canary_stdout(self) -> str:
        scratch = Path(self._last_mounts["/codex-home"]).parent
        pairs = canary_paths(
            host_home=self.host_home,
            repo_root=self.repo_root,
            host_codex_home=self.host_codex_home,
            ssh_auth_sock=self.ssh_auth_sock,
            host_canary_file=scratch / "host-canary-marker",
        )
        expected = ExpectedCanary(
            paths=tuple(pairs),
            schema_sha256=self.expected_schema_sha256,
            env_names=CONTAINER_BASE_ENV | CANARY_RUNTIME_ENV,
        )
        return _clean_canary_stdout(expected)

    def _auto_review_inspect_json(self) -> str:
        mounts = [
            {"Type": "bind", "Source": self._last_mounts["/codex-home"], "Destination": "/codex-home", "RW": True},
            {"Type": "bind", "Source": self._last_mounts["/out"], "Destination": "/out", "RW": True},
            {"Type": "bind", "Source": self._last_mounts["/schema"], "Destination": "/schema", "RW": False},
        ]
        return _inspect_json(mounts=mounts, image=self.image_id)

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        self.envs.append(kwargs.get("env"))
        if argv[:3] == ["docker", "image", "inspect"]:
            if not self.image_ok:
                return subprocess.CompletedProcess(argv, 1, stdout="")
            data = [{"Id": self.image_id, "Config": {"Labels": {REVIEW_IMAGE_LABEL: self.codex_version}}}]
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(data))
        if argv[:2] == ["docker", "create"] and "--entrypoint" in argv:
            self._record_mounts(argv)
            self.live.add(self.canary_id)
            return subprocess.CompletedProcess(argv, 0, stdout=self.canary_id + "\n")
        if argv[:2] == ["docker", "create"]:
            self._record_mounts(argv)
            self.live.add(self.review_id)
            return subprocess.CompletedProcess(argv, 0, stdout=self.review_id + "\n")
        if argv[:3] == ["docker", "start", "-a"] and len(argv) == 4:
            if self.canary_start_raises is not None:
                raise self.canary_start_raises("simulated canary start failure")
            stdout = self.canary_stdout if self.canary_stdout is not None else self._auto_canary_stdout()
            return subprocess.CompletedProcess(argv, 0, stdout=stdout)
        if argv[:2] == ["docker", "inspect"]:
            body = (
                self.review_inspect_json
                if self.review_inspect_json is not None
                else self._auto_review_inspect_json()
            )
            return subprocess.CompletedProcess(argv, 0, stdout=body)
        if argv[:4] == ["docker", "start", "-a", "-i"]:
            if self.review_start_raises is not None:
                raise self.review_start_raises("simulated review start failure")
            return subprocess.CompletedProcess(argv, self.start_returncode, stdout="")
        if argv[:2] == ["docker", "rm"]:
            if "rm" in self.raise_on:
                raise self.raise_on["rm"]("simulated docker rm failure")
            container_id = argv[3]
            if container_id in self.rm_breaks:
                return subprocess.CompletedProcess(argv, 1, stdout="")
            self.live.discard(container_id)
            return subprocess.CompletedProcess(argv, 0, stdout="")
        if argv[:2] == ["docker", "ps"]:
            if "ps" in self.raise_on:
                raise self.raise_on["ps"]("simulated docker ps failure")
            container_id = argv[-1].removeprefix("id=")
            if container_id in self.ps_breaks:
                return subprocess.CompletedProcess(argv, 1, stdout="")
            stdout = container_id + "\n" if container_id in self.live else ""
            return subprocess.CompletedProcess(argv, 0, stdout=stdout)
        raise AssertionError(f"unscripted command: {argv}")


_ID_A = "a" * 64
_ID_B = "b" * 64


# --- remove_container_confirmed ----------------------------------------------


def test_remove_container_confirmed_clean() -> None:
    runner = _DockerRunner(live={_ID_A})
    problems = remove_container_confirmed(_ID_A, runner, kind="review")
    assert problems == []
    assert runner.calls == [
        ["docker", "rm", "-f", _ID_A],
        ["docker", "ps", "-a", "-q", "--no-trunc", "--filter", f"id={_ID_A}"],
    ]
    assert all(env == docker_env(os.environ) for env in runner.envs)


@pytest.mark.parametrize("kind", ["review", "canary"])
def test_container_removal_failure(kind: str) -> None:
    runner = _DockerRunner(live={_ID_A}, rm_breaks={_ID_A})
    problems = remove_container_confirmed(_ID_A, runner, kind=kind)
    assert problems == [
        f"{kind} container {_ID_A[:12]} could not be confirmed removed; remove it manually with"
        f" `docker rm -f {_ID_A}` and check `docker ps -a` (escalate; this run is INCOMPLETE)"
    ]


def test_remove_container_confirmed_rm_nonzero_but_already_gone() -> None:
    # rm_breaks simulates `docker rm -f` exiting 1; the id was never in
    # `live` (already gone before this call), so `docker ps -a` still
    # reports absence -- confirms rm's own exit code is never trusted.
    runner = _DockerRunner(live=set(), rm_breaks={_ID_A})
    assert remove_container_confirmed(_ID_A, runner, kind="review") == []


def test_remove_container_confirmed_ps_nonzero_is_indeterminate() -> None:
    runner = _DockerRunner(live={_ID_A}, ps_breaks={_ID_A})
    problems = remove_container_confirmed(_ID_A, runner, kind="review")
    assert len(problems) == 1
    assert "could not be confirmed removed" in problems[0]


def test_remove_container_confirmed_ps_unexpected_output_is_indeterminate() -> None:
    def _runner(argv, **kwargs):
        if argv[:2] == ["docker", "rm"]:
            return subprocess.CompletedProcess(argv, 0, stdout="")
        if argv[:2] == ["docker", "ps"]:
            return subprocess.CompletedProcess(argv, 0, stdout="garbage-not-an-id\n")
        raise AssertionError(argv)

    problems = remove_container_confirmed(_ID_A, _runner, kind="review")
    assert len(problems) == 1
    assert "could not be confirmed removed" in problems[0]


def test_remove_container_confirmed_rm_raises_oserror() -> None:
    runner = _DockerRunner(live={_ID_A}, raise_on={"rm": OSError})
    problems = remove_container_confirmed(_ID_A, runner, kind="review")
    assert len(problems) == 1
    assert "could not be confirmed removed" in problems[0]


def test_remove_container_confirmed_ps_raises_oserror() -> None:
    runner = _DockerRunner(live={_ID_A}, raise_on={"ps": OSError})
    problems = remove_container_confirmed(_ID_A, runner, kind="review")
    assert len(problems) == 1
    assert "could not be confirmed removed" in problems[0]


def test_remove_container_confirmed_rejects_invalid_id() -> None:
    def _runner(argv, **kwargs):
        raise AssertionError("docker must not be called for an invalid id")

    with pytest.raises(RunnerError):
        remove_container_confirmed("not-a-valid-container-id", _runner, kind="review")


# --- ContainerLedger ----------------------------------------------------------


def test_ledger_removes_registered_container_on_close() -> None:
    runner = _DockerRunner(live={_ID_A})
    ledger = ContainerLedger(runner)
    ledger.register(_ID_A, "review")
    assert ledger.close() == []
    assert _ID_A not in runner.live


def test_ledger_release_prevents_double_removal() -> None:
    runner = _DockerRunner(live={_ID_A})
    ledger = ContainerLedger(runner)
    ledger.register(_ID_A, "review")
    ledger.release(_ID_A)
    assert ledger.close() == []
    assert runner.calls == []


def test_ledger_register_dir_removed_on_close(tmp_path: Path) -> None:
    runner = _DockerRunner()
    directory = tmp_path / "per-run"
    directory.mkdir()
    (directory / "f").write_text("x")
    ledger = ContainerLedger(runner)
    ledger.register_dir(directory)
    assert ledger.close() == []
    assert not directory.exists()


def test_ledger_close_is_idempotent() -> None:
    runner = _DockerRunner(live={_ID_A})
    ledger = ContainerLedger(runner)
    ledger.register(_ID_A, "review")
    assert ledger.close() == []
    assert ledger.close() == []


def test_ledger_cleans_up_on_keyboard_interrupt(tmp_path: Path) -> None:
    runner = _DockerRunner(live={_ID_A})
    directory = tmp_path / "per-run"
    directory.mkdir()
    (directory / "secret").write_text("x")
    with pytest.raises(KeyboardInterrupt), ContainerLedger(runner) as ledger:
        ledger.register(_ID_A, "review")
        ledger.register_dir(directory)
        raise KeyboardInterrupt
    assert any(call[:3] == ["docker", "rm", "-f"] for call in runner.calls)
    assert any(call[:2] == ["docker", "ps"] for call in runner.calls)
    assert not directory.exists()


def test_ledger_reports_every_failure() -> None:
    runner = _DockerRunner(live={_ID_A, _ID_B}, rm_breaks={_ID_A})
    ledger = ContainerLedger(runner)
    ledger.register(_ID_A, "review")
    ledger.register(_ID_B, "canary")
    problems = ledger.close()
    assert len(problems) == 1
    assert _ID_B not in runner.live


def test_ledger_finalizer_runs_before_reraise(capsys) -> None:
    runner = _DockerRunner(live={_ID_A}, rm_breaks={_ID_A})
    events: list[str] = []

    def _on_cleanup(problems, exc):
        events.append("finalizer")
        assert len(problems) == 1
        assert isinstance(exc, KeyboardInterrupt)

    with pytest.raises(KeyboardInterrupt), ContainerLedger(runner, on_cleanup_problems=_on_cleanup) as ledger:
        ledger.register(_ID_A, "review")
        events.append("before-raise")
        raise KeyboardInterrupt

    assert events == ["before-raise", "finalizer"]
    captured = capsys.readouterr()
    assert "ESCALATION: " in captured.err


@pytest.mark.parametrize("exc_type", [KeyboardInterrupt, SystemExit, RunnerError])
def test_ledger_finalizer_runs_before_reraise_various_exceptions(exc_type, capsys) -> None:
    runner = _DockerRunner(live={_ID_A}, rm_breaks={_ID_A})
    events: list[str] = []

    def _on_cleanup(problems, exc):
        events.append(type(exc).__name__)

    def _raise():
        raise exc_type(3) if exc_type is SystemExit else exc_type("boom")

    with pytest.raises(exc_type), ContainerLedger(runner, on_cleanup_problems=_on_cleanup) as ledger:
        ledger.register(_ID_A, "review")
        _raise()

    assert events == [exc_type.__name__]
    captured = capsys.readouterr()
    assert "ESCALATION: " in captured.err


def test_ledger_finalizer_failure_does_not_mask(capsys) -> None:
    runner = _DockerRunner(live={_ID_A}, rm_breaks={_ID_A})

    def _on_cleanup(problems, exc):
        raise OSError("finalizer boom")

    with pytest.raises(KeyboardInterrupt), ContainerLedger(runner, on_cleanup_problems=_on_cleanup) as ledger:
        ledger.register(_ID_A, "review")
        raise KeyboardInterrupt

    captured = capsys.readouterr()
    assert "ESCALATION: " in captured.err
    assert "could not be recorded" in captured.err


def test_ledger_finalizer_not_called_when_clean(capsys) -> None:
    runner = _DockerRunner(live={_ID_A})
    called = []

    def _on_cleanup(problems, exc):
        called.append((problems, exc))

    with ContainerLedger(runner, on_cleanup_problems=_on_cleanup) as ledger:
        ledger.register(_ID_A, "review")

    assert called == []
    captured = capsys.readouterr()
    assert captured.err == ""
    assert ledger.cleanup_problems == []


# --- verify_isolation_boundary / launch_in_verified_container / run_untrusted_codex ---
# (B04-R3, B15, D-06, D-11). Deterministic boundary verification and the
# container launch under one ContainerLedger.

_B_HEAD = "5" * 40
_B_BASE = "6" * 40
_B_LABEL = "codex-review"
_B_PHASE_DIR = ".planning/phases/85.1-isolated-codex-review-for-untrusted-prs"


def _boundary_run(**overrides) -> ReviewRun:
    kwargs = {
        "head": _B_HEAD,
        "base": _B_BASE,
        "label": _B_LABEL,
        "attempt": 1,
        "pr_url": "https://github.com/thejuran/triggarr/pull/1",
        "scope": "test",
        "phase_dir": _B_PHASE_DIR,
        "trusted": False,
    }
    kwargs.update(overrides)
    return ReviewRun(**kwargs)


class _BoundaryFixture:
    """A fake host identity + per-run scratch tree for verify_isolation_boundary tests."""

    def __init__(self, tmp_path: Path, monkeypatch) -> None:
        self.host_home = tmp_path / "fake-home"
        self.host_home.mkdir()
        self.host_codex_home = self.host_home / ".codex"
        self.host_codex_home.mkdir()
        self.auth_path = self.host_codex_home / "auth.json"
        self.auth_path.write_bytes(_auth_bytes(last_refresh=(_NOW - timedelta(days=1)).isoformat()))

        self.repo_root = tmp_path / "fake-repo"
        self.repo_root.mkdir()
        (self.repo_root / _B_PHASE_DIR).mkdir(parents=True)

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: self.host_home))
        monkeypatch.delenv("CODEX_HOME", raising=False)
        monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)
        monkeypatch.setattr(codex_review_run, "REPO_ROOT", self.repo_root)

        self.scratch = tmp_path / "scratch"
        self.scratch.mkdir()
        self.codex_home_dir = self.scratch / "codex-home"
        self.out_dir = self.scratch / "out"
        self.schema_dir = self.scratch / "schema"
        self.expected_schema_sha256 = hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()
        self.inner_argv = inspection_codex_argv()

    def canary_expected(self) -> ExpectedCanary:
        return ExpectedCanary(
            paths=tuple(self.canary_pairs()),
            schema_sha256=self.expected_schema_sha256,
            env_names=CONTAINER_BASE_ENV | CANARY_RUNTIME_ENV,
        )

    def canary_pairs(self) -> list[tuple[str, str]]:
        return canary_paths(
            host_home=self.host_home,
            repo_root=self.repo_root,
            host_codex_home=self.host_codex_home,
            ssh_auth_sock=None,
            host_canary_file=self.scratch / "host-canary-marker",
        )

    def clean_canary_stdout(self) -> str:
        return _clean_canary_stdout(self.canary_expected())

    def clean_review_inspect_json(self) -> str:
        mounts = [
            {"Type": "bind", "Source": str(self.codex_home_dir), "Destination": "/codex-home", "RW": True},
            {"Type": "bind", "Source": str(self.out_dir), "Destination": "/out", "RW": True},
            {"Type": "bind", "Source": str(self.schema_dir), "Destination": "/schema", "RW": False},
        ]
        return _inspect_json(mounts=mounts)


def _clean_docker_runner(fixture: _BoundaryFixture, **overrides) -> _DockerRunner:
    kwargs = {
        "canary_stdout": fixture.clean_canary_stdout(),
        "review_inspect_json": fixture.clean_review_inspect_json(),
    }
    kwargs.update(overrides)
    return _DockerRunner(**kwargs)


def test_verify_isolation_boundary_happy_path(tmp_path: Path, monkeypatch) -> None:
    fixture = _BoundaryFixture(tmp_path, monkeypatch)
    docker = _clean_docker_runner(fixture)
    ledger = ContainerLedger(docker)

    boundary = verify_isolation_boundary(
        _boundary_run(),
        docker,
        scratch=fixture.scratch,
        inner_argv=fixture.inner_argv,
        expected_schema_sha256=fixture.expected_schema_sha256,
        ledger=ledger,
        now=_NOW,
    )

    assert boundary["verdict"] == "verified"
    assert boundary["container_id"] == docker.review_id
    assert boundary["image_id"] == docker.image_id
    assert boundary["codex_version"] == REVIEW_CODEX_VERSION
    assert boundary["credential_mode"] == "auth.json copy"
    assert boundary["network"] == "bridge (egress not restricted)"
    assert boundary["mounts"] == [
        {"destination": "/codex-home", "rw": True},
        {"destination": "/out", "rw": True},
        {"destination": "/schema", "rw": False},
    ]
    assert "source" not in boundary["mounts"][0]
    assert set(boundary["env_names"]) == CONTAINER_BASE_ENV
    assert boundary["schema_sha256"] == fixture.expected_schema_sha256
    assert boundary["credential"]["age_days"] == 1.0

    # private launcher-only keys exist but are not meant for `.boundary.json`
    assert Path(boundary["_codex_home_dir"]) == fixture.codex_home_dir
    assert Path(boundary["_out_dir"]) == fixture.out_dir

    assert docker.calls[0][:3] == ["docker", "image", "inspect"]
    create_calls = [c for c in docker.calls if c[:2] == ["docker", "create"]]
    assert len(create_calls) == 2
    assert docker.calls.index(["docker", "start", "-a", docker.canary_id]) < docker.calls.index(
        ["docker", "rm", "-f", docker.canary_id]
    )
    assert ["docker", "inspect", docker.review_id] in docker.calls
    # canary removed and confirmed before the review container is created
    review_create_index = next(
        i for i, c in enumerate(docker.calls) if c[:2] == ["docker", "create"] and "--entrypoint" not in c
    )
    canary_rm_index = docker.calls.index(["docker", "rm", "-f", docker.canary_id])
    assert canary_rm_index < review_create_index

    for env in docker.envs:
        assert env == docker_env(os.environ)

    assert ledger.close() == []
    assert not fixture.scratch.exists()


def test_verify_isolation_boundary_image_not_ready() -> None:
    docker = _DockerRunner(image_ok=False)
    ledger = ContainerLedger(docker)
    boundary = verify_isolation_boundary(
        _boundary_run(),
        docker,
        scratch=Path("/tmp/does-not-matter-85-1-08"),
        inner_argv=inspection_codex_argv(),
        expected_schema_sha256="0" * 64,
        ledger=ledger,
        now=_NOW,
    )
    assert boundary["verdict"] == "unverified"
    assert any("review image not built or not labelled" in r for r in boundary["reasons"])
    assert not any(c[:2] == ["docker", "create"] for c in docker.calls)


def test_verify_isolation_boundary_image_label_mismatch() -> None:
    docker = _DockerRunner(codex_version="0.0.0-wrong")
    ledger = ContainerLedger(docker)
    boundary = verify_isolation_boundary(
        _boundary_run(),
        docker,
        scratch=Path("/tmp/does-not-matter-85-1-08"),
        inner_argv=inspection_codex_argv(),
        expected_schema_sha256="0" * 64,
        ledger=ledger,
        now=_NOW,
    )
    assert boundary["verdict"] == "unverified"
    assert any("review image not built or not labelled" in r for r in boundary["reasons"])


def test_verify_isolation_boundary_stale_sign_in(tmp_path: Path, monkeypatch) -> None:
    fixture = _BoundaryFixture(tmp_path, monkeypatch)
    fixture.auth_path.write_bytes(_auth_bytes(last_refresh=(_NOW - timedelta(days=8)).isoformat()))
    docker = _clean_docker_runner(fixture)
    ledger = ContainerLedger(docker)

    boundary = verify_isolation_boundary(
        _boundary_run(),
        docker,
        scratch=fixture.scratch,
        inner_argv=fixture.inner_argv,
        expected_schema_sha256=fixture.expected_schema_sha256,
        ledger=ledger,
        now=_NOW,
    )
    assert boundary["verdict"] == "unverified"
    assert any("re-login needed" in r for r in boundary["reasons"])
    assert not any(c[:2] == ["docker", "create"] for c in docker.calls)
    assert not fixture.codex_home_dir.exists()


def test_verify_isolation_boundary_per_run_dir_overlaps_protected_path(tmp_path: Path, monkeypatch) -> None:
    fixture = _BoundaryFixture(tmp_path, monkeypatch)
    # Force the scratch dir itself under the fake host home, so its
    # per-run subdirectories collide with a protected path.
    overlapping_scratch = fixture.host_home / "scratch"
    overlapping_scratch.mkdir()
    docker = _clean_docker_runner(fixture)
    ledger = ContainerLedger(docker)

    boundary = verify_isolation_boundary(
        _boundary_run(),
        docker,
        scratch=overlapping_scratch,
        inner_argv=fixture.inner_argv,
        expected_schema_sha256=fixture.expected_schema_sha256,
        ledger=ledger,
        now=_NOW,
    )
    assert boundary["verdict"] == "unverified"
    assert any("per-run directory overlaps a protected host path: <HOST_HOME>" in r for r in boundary["reasons"])
    assert not any(c[:2] == ["docker", "create"] for c in docker.calls)


def test_verify_isolation_boundary_host_exposure_failure_skips_credential_copy(tmp_path: Path, monkeypatch) -> None:
    """The host-exposure check on the canary/review argv must run before
    prepare_codex_home() ever copies the host's Codex sign-in to scratch
    disk (2026-10-29 live run: the copy was staged, then cleaned up
    unused, before the exposure check that should have run first failed).
    Forcing host_exposure_problems() to report a problem must mean the
    credential copy destination is never even created.
    """
    fixture = _BoundaryFixture(tmp_path, monkeypatch)
    docker = _clean_docker_runner(fixture)
    ledger = ContainerLedger(docker)
    monkeypatch.setattr(
        codex_review_run,
        "host_exposure_problems",
        lambda *args, **kwargs: ["canary argv references a protected host path: <REPO_ROOT>"],
    )

    boundary = verify_isolation_boundary(
        _boundary_run(),
        docker,
        scratch=fixture.scratch,
        inner_argv=fixture.inner_argv,
        expected_schema_sha256=fixture.expected_schema_sha256,
        ledger=ledger,
        now=_NOW,
    )

    assert boundary["verdict"] == "unverified"
    assert any("canary argv references a protected host path: <REPO_ROOT>" in r for r in boundary["reasons"])
    assert not fixture.codex_home_dir.exists()
    assert not any(c[:2] == ["docker", "create"] for c in docker.calls)


def test_verify_isolation_boundary_inner_argv_missing_disable(tmp_path: Path, monkeypatch) -> None:
    fixture = _BoundaryFixture(tmp_path, monkeypatch)
    docker = _clean_docker_runner(fixture)
    ledger = ContainerLedger(docker)
    bad_argv = [a for a in fixture.inner_argv if a != "shell_tool"]

    boundary = verify_isolation_boundary(
        _boundary_run(),
        docker,
        scratch=fixture.scratch,
        inner_argv=bad_argv,
        expected_schema_sha256=fixture.expected_schema_sha256,
        ledger=ledger,
        now=_NOW,
    )
    assert boundary["verdict"] == "unverified"
    assert any("does not disable every tool feature" in r for r in boundary["reasons"])
    assert docker.calls == []


def test_verify_isolation_boundary_inner_argv_wrong_schema(tmp_path: Path, monkeypatch) -> None:
    fixture = _BoundaryFixture(tmp_path, monkeypatch)
    docker = _clean_docker_runner(fixture)
    ledger = ContainerLedger(docker)
    bad_argv = list(fixture.inner_argv)
    bad_argv[bad_argv.index("--output-schema") + 1] = "/not/the/mounted/schema.json"

    boundary = verify_isolation_boundary(
        _boundary_run(),
        docker,
        scratch=fixture.scratch,
        inner_argv=bad_argv,
        expected_schema_sha256=fixture.expected_schema_sha256,
        ledger=ledger,
        now=_NOW,
    )
    assert boundary["verdict"] == "unverified"
    assert any("does not use the mounted output schema" in r for r in boundary["reasons"])
    assert docker.calls == []


def test_verify_isolation_boundary_canary_removal_unconfirmed(tmp_path: Path, monkeypatch) -> None:
    fixture = _BoundaryFixture(tmp_path, monkeypatch)
    docker = _clean_docker_runner(fixture)
    canary_id = docker.canary_id
    docker.rm_breaks.add(canary_id)
    ledger = ContainerLedger(docker)

    boundary = verify_isolation_boundary(
        _boundary_run(),
        docker,
        scratch=fixture.scratch,
        inner_argv=fixture.inner_argv,
        expected_schema_sha256=fixture.expected_schema_sha256,
        ledger=ledger,
        now=_NOW,
    )
    assert boundary["verdict"] == "unverified"
    assert any("could not be confirmed removed" in r for r in boundary["reasons"])
    # the review container must never be created once the canary cannot be confirmed removed
    assert not any(c[:2] == ["docker", "create"] and "--entrypoint" not in c for c in docker.calls)

    # the canary is still stuck in rm_breaks; a real operator would remove
    # it manually -- simulate that happening before the final cleanup.
    docker.rm_breaks.discard(canary_id)
    assert ledger.close() == []
    assert not fixture.scratch.exists()


def test_verify_isolation_boundary_canary_reports_present_path(tmp_path: Path, monkeypatch) -> None:
    fixture = _BoundaryFixture(tmp_path, monkeypatch)
    dirty_stdout = fixture.clean_canary_stdout().replace(
        f"absent {fixture.host_home}", f"present {fixture.host_home}"
    )
    docker = _clean_docker_runner(fixture, canary_stdout=dirty_stdout)
    ledger = ContainerLedger(docker)

    boundary = verify_isolation_boundary(
        _boundary_run(),
        docker,
        scratch=fixture.scratch,
        inner_argv=fixture.inner_argv,
        expected_schema_sha256=fixture.expected_schema_sha256,
        ledger=ledger,
        now=_NOW,
    )
    assert boundary["verdict"] == "unverified"
    assert any("canary path visible in container: <HOST_HOME>" in r for r in boundary["reasons"])


def test_verify_isolation_boundary_container_config_mismatch(tmp_path: Path, monkeypatch) -> None:
    fixture = _BoundaryFixture(tmp_path, monkeypatch)
    bad_mounts = [
        {"Type": "bind", "Source": str(fixture.codex_home_dir), "Destination": "/codex-home", "RW": True},
        {"Type": "bind", "Source": str(fixture.out_dir), "Destination": "/out", "RW": True},
        {"Type": "bind", "Source": str(fixture.schema_dir), "Destination": "/schema", "RW": True},
    ]
    docker = _clean_docker_runner(fixture, review_inspect_json=_inspect_json(mounts=bad_mounts))
    ledger = ContainerLedger(docker)

    boundary = verify_isolation_boundary(
        _boundary_run(),
        docker,
        scratch=fixture.scratch,
        inner_argv=fixture.inner_argv,
        expected_schema_sha256=fixture.expected_schema_sha256,
        ledger=ledger,
        now=_NOW,
    )
    assert boundary["verdict"] == "unverified"
    assert any("schema mount is writable" in r for r in boundary["reasons"])


def test_verify_isolation_boundary_docker_create_oserror(tmp_path: Path, monkeypatch) -> None:
    fixture = _BoundaryFixture(tmp_path, monkeypatch)

    def _runner(argv, **kwargs):
        if argv[:3] == ["docker", "image", "inspect"]:
            labels = {REVIEW_IMAGE_LABEL: REVIEW_CODEX_VERSION}
            image_data = [{"Id": "sha256:" + "a" * 64, "Config": {"Labels": labels}}]
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(image_data))
        if argv[:2] == ["docker", "create"]:
            raise OSError("simulated docker create failure")
        raise AssertionError(argv)

    ledger = ContainerLedger(_runner)
    boundary = verify_isolation_boundary(
        _boundary_run(),
        _runner,
        scratch=fixture.scratch,
        inner_argv=fixture.inner_argv,
        expected_schema_sha256=fixture.expected_schema_sha256,
        ledger=ledger,
        now=_NOW,
    )
    assert boundary["verdict"] == "unverified"
    assert any("canary container could not be created" in r for r in boundary["reasons"])


def test_canary_interrupted(tmp_path: Path, monkeypatch) -> None:
    fixture = _BoundaryFixture(tmp_path, monkeypatch)
    docker = _clean_docker_runner(fixture, canary_start_raises=KeyboardInterrupt)
    ledger = ContainerLedger(docker)

    with pytest.raises(KeyboardInterrupt), ledger:
        verify_isolation_boundary(
            _boundary_run(),
            docker,
            scratch=fixture.scratch,
            inner_argv=fixture.inner_argv,
            expected_schema_sha256=fixture.expected_schema_sha256,
            ledger=ledger,
            now=_NOW,
        )

    assert ["docker", "rm", "-f", docker.canary_id] in docker.calls
    assert ["docker", "ps", "-a", "-q", "--no-trunc", "--filter", f"id={docker.canary_id}"] in docker.calls
    assert not fixture.scratch.exists()
    assert not any(c[:2] == ["docker", "create"] and "--entrypoint" not in c for c in docker.calls)


# --- launch_in_verified_container / run_untrusted_codex -----------------------


def _verified_boundary(fixture: _BoundaryFixture, docker: _DockerRunner) -> dict[str, object]:
    return {
        "boundary_version": 1,
        "verdict": "verified",
        "reasons": [],
        "checked_at": _NOW.isoformat(),
        "head": _B_HEAD,
        "label": _B_LABEL,
        "attempt": 1,
        "container_id": docker.review_id,
        "image_id": docker.image_id,
        "codex_version": REVIEW_CODEX_VERSION,
        "credential_mode": "auth.json copy",
        "network": "bridge (egress not restricted)",
        "mounts": [
            {"destination": "/codex-home", "rw": True},
            {"destination": "/out", "rw": True},
            {"destination": "/schema", "rw": False},
        ],
        "env_names": sorted(CONTAINER_BASE_ENV),
        "canary": [marker for _path, marker in fixture.canary_pairs()],
        "schema_sha256": fixture.expected_schema_sha256,
        "credential": {"last_refresh": "x", "age_days": 1.0},
        "_codex_home_dir": str(fixture.codex_home_dir),
        "_out_dir": str(fixture.out_dir),
        "_schema_dir": str(fixture.schema_dir),
        "_credential_sha256": hashlib.sha256((fixture.codex_home_dir / "auth.json").read_bytes()).hexdigest(),
    }


def _prepared_fixture(tmp_path: Path, monkeypatch) -> tuple[_BoundaryFixture, _DockerRunner]:
    """A _BoundaryFixture whose codex-home/out/schema dirs already exist with a copied credential."""
    fixture = _BoundaryFixture(tmp_path, monkeypatch)
    fixture.codex_home_dir.mkdir(parents=True)
    fixture.out_dir.mkdir(parents=True)
    fixture.schema_dir.mkdir(parents=True)
    (fixture.codex_home_dir / "auth.json").write_bytes(fixture.auth_path.read_bytes())
    # run.output(...) writes under <REPO_ROOT>/<phase_dir>/codex/; the full
    # pipeline creates that directory before reserving outputs, but these
    # standalone launch tests call run_untrusted_codex() directly.
    _boundary_run().out_base.parent.mkdir(parents=True, exist_ok=True)
    docker = _clean_docker_runner(fixture)
    return fixture, docker


def test_run_untrusted_codex_seam_rejects_unverified_boundary() -> None:
    with pytest.raises(RunnerError, match="requires a verified container boundary"):
        run_untrusted_codex(
            _boundary_run(),
            inner_argv=inspection_codex_argv(),
            prompt="hello",
            boundary={"verdict": "unverified"},
            command_runner=lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not be called")),
            ledger=ContainerLedger(lambda *a, **k: None),
        )


def test_launch_happy_path(tmp_path: Path, monkeypatch) -> None:
    fixture, docker = _prepared_fixture(tmp_path, monkeypatch)
    docker.live.add(docker.review_id)
    (fixture.out_dir / "last.json").write_bytes(b'{"ok": true}')
    boundary = _verified_boundary(fixture, docker)
    ledger = ContainerLedger(docker)
    ledger.register(docker.review_id, "review")

    exit_code, problems = run_untrusted_codex(
        _boundary_run(), inner_argv=inspection_codex_argv(), prompt="hello", boundary=boundary,
        command_runner=docker, ledger=ledger,
    )

    assert exit_code == 0
    assert problems == []
    assert _boundary_run().output(".last.json").read_bytes() == b'{"ok": true}'
    assert not fixture.scratch.exists()
    assert docker.review_id not in ledger._containers
    _boundary_run().output(".last.json").unlink()
    _boundary_run().output(".jsonl").unlink(missing_ok=True)


def test_launch_removal_unconfirmed(tmp_path: Path, monkeypatch) -> None:
    fixture, docker = _prepared_fixture(tmp_path, monkeypatch)
    docker.live.add(docker.review_id)
    docker.rm_breaks.add(docker.review_id)
    (fixture.out_dir / "last.json").write_bytes(b'{"ok": true}')
    boundary = _verified_boundary(fixture, docker)
    ledger = ContainerLedger(docker)
    ledger.register(docker.review_id, "review")

    read_calls = []
    real_safe_read = codex_review_run.safe_read_regular_file

    def _spy(dir_path, name, *, max_bytes):
        read_calls.append((Path(dir_path), name))
        return real_safe_read(dir_path, name, max_bytes=max_bytes)

    monkeypatch.setattr(codex_review_run, "safe_read_regular_file", _spy)
    credential_calls = []
    monkeypatch.setattr(
        codex_review_run,
        "credential_outcome",
        lambda *a, **k: credential_calls.append((a, k)),
    )

    run = _boundary_run()
    last_json_before = run.output(".last.json").exists()
    exit_code, problems = run_untrusted_codex(
        run, inner_argv=inspection_codex_argv(), prompt="hello", boundary=boundary,
        command_runner=docker, ledger=ledger,
    )

    assert any("could not be confirmed removed" in p for p in problems)
    assert run.output(".last.json").exists() == last_json_before  # unchanged (not created)
    assert credential_calls == []
    assert read_calls == []
    assert docker.review_id in ledger._containers
    run.output(".jsonl").unlink(missing_ok=True)


def test_launch_symlinked_output_refused(tmp_path: Path, monkeypatch) -> None:
    fixture, docker = _prepared_fixture(tmp_path, monkeypatch)
    docker.live.add(docker.review_id)
    secret = tmp_path / "host-secret"
    secret.write_text("do not leak")
    (fixture.out_dir / "last.json").symlink_to(secret)
    boundary = _verified_boundary(fixture, docker)
    ledger = ContainerLedger(docker)
    ledger.register(docker.review_id, "review")

    run = _boundary_run()
    exit_code, problems = run_untrusted_codex(
        run, inner_argv=inspection_codex_argv(), prompt="hello", boundary=boundary,
        command_runner=docker, ledger=ledger,
    )
    assert problems == ["unsafe container output refused: last.json is a symlink"]
    assert not run.output(".last.json").exists()
    run.output(".jsonl").unlink(missing_ok=True)


def test_launch_fifo_output_refused_and_does_not_hang(tmp_path: Path, monkeypatch) -> None:
    fixture, docker = _prepared_fixture(tmp_path, monkeypatch)
    docker.live.add(docker.review_id)
    os.mkfifo(fixture.out_dir / "last.json")
    boundary = _verified_boundary(fixture, docker)
    ledger = ContainerLedger(docker)
    ledger.register(docker.review_id, "review")

    run = _boundary_run()
    start = time.monotonic()
    exit_code, problems = run_untrusted_codex(
        run, inner_argv=inspection_codex_argv(), prompt="hello", boundary=boundary,
        command_runner=docker, ledger=ledger,
    )
    assert time.monotonic() - start < 2
    assert problems == ["unsafe container output refused: last.json is not a regular file"]
    run.output(".jsonl").unlink(missing_ok=True)


def test_launch_sign_in_refreshed_mid_run(tmp_path: Path, monkeypatch) -> None:
    fixture, docker = _prepared_fixture(tmp_path, monkeypatch)
    docker.live.add(docker.review_id)
    # the boundary's recorded hash is of the snapshot copied in *before*
    # the run; only after that is the container's copy rewritten, as if
    # Codex refreshed it mid-run.
    boundary = _verified_boundary(fixture, docker)
    (fixture.codex_home_dir / "auth.json").write_bytes(_auth_bytes(last_refresh=_NOW.isoformat()))
    ledger = ContainerLedger(docker)
    ledger.register(docker.review_id, "review")

    run = _boundary_run()
    exit_code, problems = run_untrusted_codex(
        run, inner_argv=inspection_codex_argv(), prompt="hello", boundary=boundary,
        command_runner=docker, ledger=ledger,
    )
    assert any("Re-login needed: run `codex login` on the host (D-11)" in p for p in problems)
    run.output(".jsonl").unlink(missing_ok=True)


def test_launch_docker_start_nonzero_exit(tmp_path: Path, monkeypatch) -> None:
    fixture, docker = _prepared_fixture(tmp_path, monkeypatch)
    docker.live.add(docker.review_id)
    docker.start_returncode = 1
    boundary = _verified_boundary(fixture, docker)
    ledger = ContainerLedger(docker)
    ledger.register(docker.review_id, "review")

    run = _boundary_run()
    exit_code, problems = run_untrusted_codex(
        run, inner_argv=inspection_codex_argv(), prompt="hello", boundary=boundary,
        command_runner=docker, ledger=ledger,
    )
    assert (exit_code, problems) == (1, [])
    assert not fixture.scratch.exists()
    run.output(".jsonl").unlink(missing_ok=True)
    run.output(".last.json").unlink(missing_ok=True)


def test_launch_docker_start_oserror(tmp_path: Path, monkeypatch) -> None:
    fixture, docker = _prepared_fixture(tmp_path, monkeypatch)
    docker.live.add(docker.review_id)
    docker.review_start_raises = OSError
    boundary = _verified_boundary(fixture, docker)
    ledger = ContainerLedger(docker)
    ledger.register(docker.review_id, "review")

    run = _boundary_run()
    exit_code, problems = run_untrusted_codex(
        run, inner_argv=inspection_codex_argv(), prompt="hello", boundary=boundary,
        command_runner=docker, ledger=ledger,
    )
    assert exit_code is None
    assert problems == ["review container could not start: OSError"]
    assert not fixture.scratch.exists()
    run.output(".jsonl").unlink(missing_ok=True)


def test_launch_start_timeout(tmp_path: Path, monkeypatch) -> None:
    fixture, docker = _prepared_fixture(tmp_path, monkeypatch)
    docker.live.add(docker.review_id)

    def _timeout_runner(argv, **kwargs):
        if argv[:4] == ["docker", "start", "-a", "-i"]:
            raise subprocess.TimeoutExpired(argv, 1800)
        return docker(argv, **kwargs)

    boundary = _verified_boundary(fixture, docker)
    ledger = ContainerLedger(_timeout_runner)
    ledger.register(docker.review_id, "review")

    run = _boundary_run()
    exit_code, problems = run_untrusted_codex(
        run, inner_argv=inspection_codex_argv(), prompt="hello", boundary=boundary,
        command_runner=_timeout_runner, ledger=ledger,
    )
    assert exit_code == codex_review_run.CODEX_TIMEOUT_EXIT
    assert problems == []
    assert ["docker", "rm", "-f", docker.review_id] in docker.calls
    run.output(".jsonl").unlink(missing_ok=True)
    run.output(".last.json").unlink(missing_ok=True)


def test_launch_keyboard_interrupt_during_start_still_cleans_up(tmp_path: Path, monkeypatch) -> None:
    fixture, docker = _prepared_fixture(tmp_path, monkeypatch)
    docker.live.add(docker.review_id)
    docker.review_start_raises = KeyboardInterrupt
    boundary = _verified_boundary(fixture, docker)
    ledger = ContainerLedger(docker)
    ledger.register(docker.review_id, "review")

    run = _boundary_run()
    with pytest.raises(KeyboardInterrupt):
        run_untrusted_codex(
            run, inner_argv=inspection_codex_argv(), prompt="hello", boundary=boundary,
            command_runner=docker, ledger=ledger,
        )
    assert ["docker", "rm", "-f", docker.review_id] in docker.calls
    assert not fixture.scratch.exists()
    assert docker.review_id not in ledger._containers
    run.output(".jsonl").unlink(missing_ok=True)


# --- _execute_inspection / execute() integration -----------------------------


class _E2ERunner:
    """Combines a _DockerRunner with the handful of git/gh/checker calls
    _execute_untrusted()/_execute_inspection() still issue once
    inspect_untrusted_pr/ci_evidence/build_inspection_input/
    establish_trusted_main are monkeypatched (see _patch_untrusted_pipeline).
    """

    def __init__(
        self, docker: _DockerRunner, *, head_ref_oid: str, checker_stdout: str, checker_returncode: int = 0
    ) -> None:
        self.docker = docker
        self.head_ref_oid = head_ref_oid
        self.checker_stdout = checker_stdout
        self.checker_returncode = checker_returncode
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        if argv and argv[0] == "docker":
            return self.docker(argv, **kwargs)
        if argv[:2] == ["git", "status"]:
            return subprocess.CompletedProcess(argv, 0, stdout="")
        if argv == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(argv, 0, stdout=_B_HEAD + "\n")
        if argv[:2] == ["git", "diff"] and "--name-only" in argv:
            return subprocess.CompletedProcess(argv, 0, stdout="")
        if argv[:3] == ["gh", "pr", "view"]:
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({"headRefOid": self.head_ref_oid}))
        if argv and argv[0] == sys.executable and len(argv) > 1 and "codex_report_status.py" in str(argv[1]):
            return subprocess.CompletedProcess(argv, self.checker_returncode, stdout=self.checker_stdout)
        raise AssertionError(f"unscripted command: {argv}")


def _patch_untrusted_pipeline(monkeypatch, *, provenance: dict[str, object]) -> None:
    monkeypatch.setattr(
        codex_review_run,
        "inspect_untrusted_pr",
        lambda run, command_runner: {
            "number": 1,
            "author_login": "dependabot[bot]",
            "is_cross_repository": False,
            "head_ref_oid": run.head,
            "base_ref_oid": run.base,
            "merge_base": run.base,
        },
    )
    monkeypatch.setattr(
        codex_review_run,
        "ci_evidence",
        lambda run, command_runner: {
            "check_runs": [],
            "ci_ready": {"id": 1, "name": "CI ready", "head_sha": run.head, "conclusion": "success", "html_url": "x"},
        },
    )
    monkeypatch.setattr(
        codex_review_run,
        "build_inspection_input",
        lambda run, command_runner: (
            "### In-scope diff\nFAKE\n",
            {"bytes": 10, "files_included": 1, "files_omitted": 0, "oversize": False},
        ),
    )
    monkeypatch.setattr(codex_review_run, "establish_trusted_main", lambda run, command_runner: dict(provenance))


def _e2e_setup(tmp_path: Path, monkeypatch) -> tuple[ReviewRun, _BoundaryFixture]:
    # _BoundaryFixture already monkeypatches Path.home/REPO_ROOT to its own
    # fake_home/repo_root; reuse that same repo_root here (its own
    # scratch/per-run-dir fixtures are unused by this e2e test) so the
    # REPO_ROOT a _DockerRunner is told about always matches what
    # verify_isolation_boundary itself reads.
    fixture = _BoundaryFixture(tmp_path, monkeypatch)

    provenance = {
        "main_ref": "refs/remotes/origin/main",
        "main_sha": _B_BASE,
        "harness_head": _B_BASE,
        "base": _B_BASE,
        "base_on_main": True,
        "grader_ref": _B_BASE,
        "grader_source": "trusted-origin-main",
    }
    _patch_untrusted_pipeline(monkeypatch, provenance=provenance)

    run = _boundary_run()
    return run, fixture


_E2E_COMPLETE_STATUS = (
    json.dumps(
        {
            "status": "complete",
            "reasons": [],
            "qualified_ids": [],
            "finding_count": 0,
            "inspected_head": _B_HEAD,
            "inspected_base": _B_BASE,
        }
    )
    + "\n"
)


def test_untrusted_launch_sequence_end_to_end(tmp_path: Path, monkeypatch) -> None:
    run, fixture = _e2e_setup(tmp_path, monkeypatch)
    docker = _DockerRunner(
        host_home=fixture.host_home,
        repo_root=fixture.repo_root,
        host_codex_home=fixture.host_codex_home,
        expected_schema_sha256=fixture.expected_schema_sha256,
    )
    e2e = _E2ERunner(docker, head_ref_oid=run.head, checker_stdout=_E2E_COMPLETE_STATUS)

    exit_code = execute(run, command_runner=e2e)

    assert exit_code == 0
    boundary = json.loads(run.output(".boundary.json").read_text(encoding="utf-8"))
    assert boundary["verdict"] == "verified"
    assert "_codex_home_dir" not in boundary
    assert not any(c[0] == "codex" for c in e2e.calls)

    docker_calls = [c for c in e2e.calls if c and c[0] == "docker"]
    expected_order = [
        ["docker", "image", "inspect", REVIEW_IMAGE_REF],
    ]
    assert docker_calls[0] == expected_order[0]
    create_indices = [i for i, c in enumerate(docker_calls) if c[:2] == ["docker", "create"]]
    assert len(create_indices) == 2
    start_a_index = next(i for i, c in enumerate(docker_calls) if c[:3] == ["docker", "start", "-a"] and len(c) == 4)
    rm_indices = [i for i, c in enumerate(docker_calls) if c[:2] == ["docker", "rm"]]
    ps_indices = [i for i, c in enumerate(docker_calls) if c[:2] == ["docker", "ps"]]
    inspect_index = next(i for i, c in enumerate(docker_calls) if c[:2] == ["docker", "inspect"])
    start_ai_index = next(i for i, c in enumerate(docker_calls) if c[:4] == ["docker", "start", "-a", "-i"])
    assert create_indices[0] < start_a_index < rm_indices[0] < ps_indices[0] < create_indices[1] < inspect_index
    assert inspect_index < start_ai_index < rm_indices[1] < ps_indices[1]
    assert docker.review_id not in docker.live


def test_failure_after_verification_before_launch(tmp_path: Path, monkeypatch) -> None:
    run, fixture = _e2e_setup(tmp_path, monkeypatch)
    docker = _DockerRunner(
        host_home=fixture.host_home,
        repo_root=fixture.repo_root,
        host_codex_home=fixture.host_codex_home,
        expected_schema_sha256=fixture.expected_schema_sha256,
    )
    e2e = _E2ERunner(docker, head_ref_oid=run.head, checker_stdout=_E2E_COMPLETE_STATUS)

    def _raise(*args, **kwargs):
        raise RunnerError("simulated launch preparation failure")

    monkeypatch.setattr(codex_review_run, "run_untrusted_codex", _raise)

    exit_code = execute(run, command_runner=e2e)

    assert exit_code == 3
    status = json.loads(run.output(".status.json").read_text(encoding="utf-8"))
    assert status["status"] == "incomplete"
    docker_calls = [c for c in e2e.calls if c and c[0] == "docker"]
    assert any(c[:2] == ["docker", "create"] and "--entrypoint" not in c for c in docker_calls)
    review_id = docker.review_id
    assert ["docker", "rm", "-f", review_id] in docker_calls
    assert ["docker", "ps", "-a", "-q", "--no-trunc", "--filter", f"id={review_id}"] in docker_calls
    assert review_id not in docker.live


def test_cleanup_escalation_interrupt_execute_inspection(tmp_path: Path, monkeypatch) -> None:
    run, fixture = _e2e_setup(tmp_path, monkeypatch)
    docker = _DockerRunner(
        host_home=fixture.host_home,
        repo_root=fixture.repo_root,
        host_codex_home=fixture.host_codex_home,
        expected_schema_sha256=fixture.expected_schema_sha256,
        review_start_raises=KeyboardInterrupt,
    )
    docker.rm_breaks.add(docker.review_id)
    e2e = _E2ERunner(docker, head_ref_oid=run.head, checker_stdout=_E2E_COMPLETE_STATUS)

    read_calls = []
    real_safe_read = codex_review_run.safe_read_regular_file

    def _spy(dir_path, name, *, max_bytes):
        read_calls.append((Path(dir_path), name))
        return real_safe_read(dir_path, name, max_bytes=max_bytes)

    monkeypatch.setattr(codex_review_run, "safe_read_regular_file", _spy)
    credential_calls = []
    monkeypatch.setattr(
        codex_review_run, "credential_outcome", lambda *a, **k: credential_calls.append((a, k)) or []
    )

    with pytest.raises(KeyboardInterrupt):
        execute(run, command_runner=e2e)

    status = json.loads(run.output(".status.json").read_text(encoding="utf-8"))
    assert status["status"] == "incomplete"
    # _finalize_raw_outputs's own pre-existing interrupt handling (Plan
    # 85.1-06, unchanged) records the Codex-step failure; the ledger's
    # cleanup escalation (merged in afterwards) carries the manual
    # removal warning.
    assert any("KeyboardInterrupt" in r for r in status["reasons"])
    assert any(f"docker rm -f {docker.review_id}" in r for r in status["reasons"])
    assert not run.output(".last.json").exists()
    assert not any(name == "last.json" for _dir_path, name in read_calls)
    assert credential_calls == []


def test_cleanup_escalation_launch_prep_failure_execute_inspection(tmp_path: Path, monkeypatch) -> None:
    # "Launch preparation" here is the raw-output finalization step that
    # always runs in a `finally` around the launch (_finalize_raw_outputs):
    # the real launch succeeds, but something in that finalization step
    # fails (simulated here) after it has already recorded its own
    # reason, combined with the review container's removal being
    # unconfirmed -- exercising the same "RunnerError propagates, ledger
    # cleans up, escalation merges into the already-written status"
    # path PC-01-R2 describes, distinct from run_untrusted_codex's own
    # (separately caught) RunnerError path.
    run, fixture = _e2e_setup(tmp_path, monkeypatch)
    docker = _DockerRunner(
        host_home=fixture.host_home,
        repo_root=fixture.repo_root,
        host_codex_home=fixture.host_codex_home,
        expected_schema_sha256=fixture.expected_schema_sha256,
    )
    docker.rm_breaks.add(docker.review_id)
    e2e = _E2ERunner(docker, head_ref_oid=run.head, checker_stdout=_E2E_COMPLETE_STATUS)

    raised: dict[str, BaseException] = {}
    real_finalize = codex_review_run._finalize_raw_outputs

    def _fake_finalize(run_arg, *, worktree, scratch):
        real_finalize(run_arg, worktree=worktree, scratch=scratch)
        codex_review_run._write_status_stub(run_arg, "original launch-preparation reason")
        exc = RunnerError("simulated launch preparation failure")
        raised["exc"] = exc
        raise exc

    monkeypatch.setattr(codex_review_run, "_finalize_raw_outputs", _fake_finalize)

    read_calls = []
    real_safe_read = codex_review_run.safe_read_regular_file

    def _spy(dir_path, name, *, max_bytes):
        read_calls.append((Path(dir_path), name))
        return real_safe_read(dir_path, name, max_bytes=max_bytes)

    monkeypatch.setattr(codex_review_run, "safe_read_regular_file", _spy)

    # WR-01: an untrusted run returns 0 or 3 with a status always recorded;
    # the RunnerError no longer escapes as exit 2, and the status the failing
    # step already wrote is kept (not overwritten by a generic stub).
    assert execute(run, command_runner=e2e) == 3
    assert "exc" in raised

    status = json.loads(run.output(".status.json").read_text(encoding="utf-8"))
    assert status["status"] == "incomplete"
    assert any("original launch-preparation reason" in r for r in status["reasons"])
    assert any(f"docker rm -f {docker.review_id}" in r for r in status["reasons"])
    # the host credential (and its just-written copy) are legitimately
    # read during boundary setup; the container's own last.json is not,
    # since the review container's removal was never confirmed.
    assert not any(name == "last.json" for _dir_path, name in read_calls)


def test_cleanup_escalation_canary_interrupt_execute_inspection(tmp_path: Path, monkeypatch) -> None:
    run, fixture = _e2e_setup(tmp_path, monkeypatch)
    docker = _DockerRunner(
        host_home=fixture.host_home,
        repo_root=fixture.repo_root,
        host_codex_home=fixture.host_codex_home,
        expected_schema_sha256=fixture.expected_schema_sha256,
        canary_start_raises=KeyboardInterrupt,
    )
    docker.rm_breaks.add(docker.canary_id)
    e2e = _E2ERunner(docker, head_ref_oid=run.head, checker_stdout=_E2E_COMPLETE_STATUS)

    with pytest.raises(KeyboardInterrupt):
        execute(run, command_runner=e2e)

    status = json.loads(run.output(".status.json").read_text(encoding="utf-8"))
    assert status["status"] == "incomplete"
    canary_id12 = docker.canary_id[:12]
    assert any(f"canary container {canary_id12} could not be confirmed removed" in r for r in status["reasons"])
    assert any(f"docker rm -f {docker.canary_id}" in r for r in status["reasons"])
    docker_calls = [c for c in e2e.calls if c and c[0] == "docker"]
    assert not any(c[:2] == ["docker", "create"] and "--entrypoint" not in c for c in docker_calls)


# --- verify_boundary_main / --verify-boundary ---------------------------------
# (Plan 85.1-09, D-03). Pre-merge boundary evidence against the real built
# image, without reviewing a PR: the same deterministic checks
# verify_isolation_boundary() already performs, run with run=None.


def test_verify_boundary_main_verified(tmp_path: Path, monkeypatch, capsys) -> None:
    fixture = _BoundaryFixture(tmp_path, monkeypatch)
    docker = _DockerRunner(
        host_home=fixture.host_home,
        repo_root=fixture.repo_root,
        host_codex_home=fixture.host_codex_home,
        expected_schema_sha256=fixture.expected_schema_sha256,
    )

    exit_code = verify_boundary_main(with_probes=False, command_runner=docker)

    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "verified"
    assert out["reasons"] == []
    assert "_codex_home_dir" not in out
    assert "_out_dir" not in out
    assert "_schema_dir" not in out
    assert "_credential_sha256" not in out
    # the review container the deterministic check created is removed again
    # since it is never started without --with-probes
    assert docker.review_id not in docker.live
    assert docker.canary_id not in docker.live


def test_verify_boundary_main_unverified(tmp_path: Path, monkeypatch, capsys) -> None:
    docker = _DockerRunner(image_ok=False)

    exit_code = verify_boundary_main(with_probes=False, command_runner=docker)

    assert exit_code == 3
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "unverified"
    assert any("review image not built or not labelled" in r for r in out["reasons"])


def test_verify_boundary_main_redacts_scratch_path_in_reasons(tmp_path: Path, monkeypatch, capsys) -> None:
    fixture = _BoundaryFixture(tmp_path, monkeypatch)
    fixed_scratch = tmp_path / "fixed-scratch"
    fixed_scratch.mkdir()
    (fixed_scratch / "codex-home").mkdir()  # pre-exists -> prepare_codex_home refuses, leaking the path

    def _fake_mkdtemp(*, prefix: str | None = None, **_kwargs: object) -> str:
        return str(fixed_scratch)

    monkeypatch.setattr(codex_review_run.tempfile, "mkdtemp", _fake_mkdtemp)
    docker = _DockerRunner(
        host_home=fixture.host_home,
        repo_root=fixture.repo_root,
        host_codex_home=fixture.host_codex_home,
        expected_schema_sha256=fixture.expected_schema_sha256,
    )

    exit_code = verify_boundary_main(with_probes=False, command_runner=docker)

    assert exit_code == 3
    out = capsys.readouterr().out
    assert str(fixed_scratch) not in out
    assert "<SCRATCH>" in out


def test_verify_boundary_main_with_probes_clean(tmp_path: Path, monkeypatch, capsys) -> None:
    fixture = _BoundaryFixture(tmp_path, monkeypatch)
    docker = _DockerRunner(
        host_home=fixture.host_home,
        repo_root=fixture.repo_root,
        host_codex_home=fixture.host_codex_home,
        expected_schema_sha256=fixture.expected_schema_sha256,
    )

    exit_code = verify_boundary_main(with_probes=True, command_runner=docker)

    assert exit_code == 0
    # _stream_events prints its own "codex exit code: N" line before the
    # final JSON verdict; only the last line is the JSON this call prints.
    last_line = capsys.readouterr().out.strip().splitlines()[-1]
    out = json.loads(last_line)
    assert out["verdict"] == "verified"
    assert out["probe"] == "supplementary: no tool use or token observed (not proof)"
    assert docker.review_id not in docker.live


def test_verify_boundary_main_probe_not_run_when_boundary_unverified(monkeypatch) -> None:
    docker = _DockerRunner(image_ok=False)
    calls: list[tuple] = []
    monkeypatch.setattr(
        codex_review_run,
        "run_boundary_probe",
        lambda *a, **k: calls.append((a, k)) or {"reasons": [], "summary": None},
    )

    exit_code = verify_boundary_main(with_probes=True, command_runner=docker)

    assert exit_code == 3
    assert calls == []


def test_verify_boundary_cleanup_escalation_on_interrupt(tmp_path: Path, monkeypatch, capsys) -> None:
    fixture = _BoundaryFixture(tmp_path, monkeypatch)
    docker = _DockerRunner(
        host_home=fixture.host_home,
        repo_root=fixture.repo_root,
        host_codex_home=fixture.host_codex_home,
        expected_schema_sha256=fixture.expected_schema_sha256,
        canary_start_raises=KeyboardInterrupt,
    )
    docker.rm_breaks.add(docker.canary_id)

    before = sorted(str(p) for p in fixture.repo_root.rglob("*"))
    with pytest.raises(KeyboardInterrupt):
        verify_boundary_main(with_probes=False, command_runner=docker)
    after = sorted(str(p) for p in fixture.repo_root.rglob("*"))
    assert before == after  # nothing written under REPO_ROOT

    out, err = capsys.readouterr()
    result = json.loads(out)
    assert result["verdict"] == "unverified"
    canary_id12 = docker.canary_id[:12]
    assert any(
        f"canary container {canary_id12} could not be confirmed removed" in r
        and f"docker rm -f {docker.canary_id}" in r
        for r in result["reasons"]
    )
    assert "ESCALATION: " in err
    # the canary's own stdout (never produced, since the start call raised)
    # is never parsed
    assert not any(c[:2] == ["docker", "create"] and "--entrypoint" not in c for c in docker.calls)


def test_verify_boundary_cleanup_escalation_on_probe_prep_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    fixture, docker = _prepared_fixture(tmp_path, monkeypatch)
    docker.live.add(docker.review_id)
    docker.rm_breaks.add(docker.review_id)
    boundary = _verified_boundary(fixture, docker)

    boom = OSError("simulated probe planting failure")
    monkeypatch.setattr(codex_review_run.secrets, "token_hex", lambda *_a, **_k: (_ for _ in ()).throw(boom))

    read_calls: list[tuple[Path, str]] = []
    real_safe_read = codex_review_run.safe_read_regular_file

    def _spy(dir_path, name, *, max_bytes):
        read_calls.append((Path(dir_path), name))
        return real_safe_read(dir_path, name, max_bytes=max_bytes)

    monkeypatch.setattr(codex_review_run, "safe_read_regular_file", _spy)
    credential_calls = []
    monkeypatch.setattr(
        codex_review_run, "credential_outcome", lambda *a, **k: credential_calls.append((a, k)) or []
    )

    scratch = Path(tempfile.mkdtemp())
    ledger = ContainerLedger(docker, on_cleanup_problems=codex_review_run._print_boundary_cleanup_escalation)
    ledger.register(docker.review_id, "review")

    with pytest.raises(OSError) as exc_info, ledger:
        run_boundary_probe(boundary, scratch=scratch, command_runner=docker, ledger=ledger)
    assert exc_info.value is boom

    out, err = capsys.readouterr()
    result = json.loads(out)
    assert result["verdict"] == "unverified"
    review_id12 = docker.review_id[:12]
    assert any(
        f"review container {review_id12} could not be confirmed removed" in r
        and f"docker rm -f {docker.review_id}" in r
        for r in result["reasons"]
    )
    assert "ESCALATION: " in err
    assert not any(name == "last.json" for _dir_path, name in read_calls)
    assert credential_calls == []


def test_main_verify_boundary_routes_to_verify_boundary_main(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(codex_review_run, "verify_boundary_main", lambda **kwargs: calls.append(kwargs) or 0)

    assert main(["--verify-boundary"]) == 0
    assert calls == [{"with_probes": False}]


def test_main_verify_boundary_with_probes_routes(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(codex_review_run, "verify_boundary_main", lambda **kwargs: calls.append(kwargs) or 0)

    assert main(["--verify-boundary", "--with-probes"]) == 0
    assert calls == [{"with_probes": True}]


def test_main_with_probes_alone_is_argparse_error() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--with-probes"])
    assert exc_info.value.code == 2


def test_main_verify_boundary_with_completion_gate_is_argparse_error() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--verify-boundary", "--completion-gate", "x"])
    assert exc_info.value.code == 2


@pytest.mark.skipif(
    os.environ.get("TRIGGARR_CODEX_LIVE") != "1", reason="live Docker/Codex run against the real image; opt-in only"
)
def test_live_boundary_verified() -> None:
    exit_code = verify_boundary_main(with_probes=False)
    assert exit_code == 0


# --- run_boundary_probe (B04-R3, T-85.1-40/41) --------------------------------
# Supplementary regression evidence only: absence of findings is never
# proof, and a finding can only downgrade the verdict, never improve it.


def test_probe_prompt_template_has_required_placeholders() -> None:
    assert "{run_me_path}" in PROBE_PROMPT_TEMPLATE
    assert "{pre_commit_path}" in PROBE_PROMPT_TEMPLATE
    assert "{canary_path}" in PROBE_PROMPT_TEMPLATE


def test_probe_no_findings_is_supplementary_only(tmp_path: Path, monkeypatch) -> None:
    fixture, docker = _prepared_fixture(tmp_path, monkeypatch)
    docker.live.add(docker.review_id)
    boundary = _verified_boundary(fixture, docker)
    ledger = ContainerLedger(docker)
    ledger.register(docker.review_id, "review")
    scratch = tmp_path / "probe-scratch"
    scratch.mkdir()

    result = run_boundary_probe(boundary, scratch=scratch, command_runner=docker, ledger=ledger)

    assert result["reasons"] == []
    assert result["summary"] == "supplementary: no tool use or token observed (not proof)"
    assert ledger.close() == []
    assert not scratch.exists()


def test_probe_disallowed_item_type_downgrades_verdict(tmp_path: Path, monkeypatch) -> None:
    fixture, docker = _prepared_fixture(tmp_path, monkeypatch)
    docker.live.add(docker.review_id)
    boundary = _verified_boundary(fixture, docker)
    ledger = ContainerLedger(docker)
    ledger.register(docker.review_id, "review")
    scratch = tmp_path / "probe-scratch"
    scratch.mkdir()

    disallowed_event = json.dumps({"type": "item.completed", "item": {"type": "command_execution"}}) + "\n"

    def _runner(argv, **kwargs):
        if argv[:4] == ["docker", "start", "-a", "-i"]:
            kwargs["stdout"].write(disallowed_event)
            return subprocess.CompletedProcess(argv, 0)
        return docker(argv, **kwargs)

    result = run_boundary_probe(boundary, scratch=scratch, command_runner=_runner, ledger=ledger)

    assert any("probe used a tool: command_execution" in r for r in result["reasons"])
    assert result["summary"] is None


def test_probe_error_event_is_not_labelled_a_tool(tmp_path: Path, monkeypatch) -> None:
    """An `error`-typed item (e.g. a TLS/connectivity failure reaching the
    model backend) still downgrades the verdict -- the probe stays
    fail-closed -- but must not be reported as "probe used a tool", since no
    tool actually ran (the regression behind the run-2 "NOT verified" result).
    """
    fixture, docker = _prepared_fixture(tmp_path, monkeypatch)
    docker.live.add(docker.review_id)
    boundary = _verified_boundary(fixture, docker)
    ledger = ContainerLedger(docker)
    ledger.register(docker.review_id, "review")
    scratch = tmp_path / "probe-scratch"
    scratch.mkdir()

    error_event = json.dumps({"type": "item.completed", "item": {"type": "error"}}) + "\n"

    def _runner(argv, **kwargs):
        if argv[:4] == ["docker", "start", "-a", "-i"]:
            kwargs["stdout"].write(error_event)
            return subprocess.CompletedProcess(argv, 0)
        return docker(argv, **kwargs)

    result = run_boundary_probe(boundary, scratch=scratch, command_runner=_runner, ledger=ledger)

    assert any("probe produced an unexpected event: error" in r for r in result["reasons"])
    assert not any("probe used a tool" in r for r in result["reasons"])
    assert result["summary"] is None


@pytest.mark.parametrize("item_type", sorted(KNOWN_TOOL_ITEM_TYPES))
def test_probe_tool_use_reasons_labels_known_tool_types(tmp_path: Path, item_type: str) -> None:
    path = tmp_path / "probe.jsonl"
    path.write_text(json.dumps({"type": "item.completed", "item": {"type": item_type}}) + "\n", encoding="utf-8")
    assert _probe_tool_use_reasons(path) == [f"probe used a tool: {item_type}"]


@pytest.mark.parametrize("item_type", ["error", "something_unforeseen"])
def test_probe_tool_use_reasons_labels_non_tool_types_as_unexpected_events(tmp_path: Path, item_type: str) -> None:
    path = tmp_path / "probe.jsonl"
    path.write_text(json.dumps({"type": "item.completed", "item": {"type": item_type}}) + "\n", encoding="utf-8")
    assert _probe_tool_use_reasons(path) == [f"probe produced an unexpected event: {item_type}"]


def test_probe_tool_use_reasons_allowed_types_are_clean(tmp_path: Path) -> None:
    path = tmp_path / "probe.jsonl"
    events = [
        {"type": "item.completed", "item": {"type": "agent_message", "text": "hi"}},
        {"type": "item.completed", "item": {"type": "reasoning", "text": "..."}},
    ]
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    assert _probe_tool_use_reasons(path) == []


def test_probe_observed_token_downgrades_verdict(tmp_path: Path, monkeypatch) -> None:
    fixture, docker = _prepared_fixture(tmp_path, monkeypatch)
    docker.live.add(docker.review_id)
    boundary = _verified_boundary(fixture, docker)
    ledger = ContainerLedger(docker)
    ledger.register(docker.review_id, "review")
    scratch = tmp_path / "probe-scratch"
    scratch.mkdir()

    fixed_tokens = iter(["aaaa1111aaaa1111", "bbbb2222bbbb2222", "cccc3333cccc3333"])
    monkeypatch.setattr(codex_review_run.secrets, "token_hex", lambda _n: next(fixed_tokens))
    # Simulate the container reporting back one of the planted tokens, as if
    # Codex had actually read the canary and leaked it into its own report.
    (fixture.out_dir / "last.json").write_text(
        json.dumps({"message": "I found token bbbb2222bbbb2222 in the file"}), encoding="utf-8"
    )

    result = run_boundary_probe(boundary, scratch=scratch, command_runner=docker, ledger=ledger)

    assert any("probe observed host content: token B" in r for r in result["reasons"])
    assert result["summary"] is None


def test_probe_prompt_contains_paths_not_tokens(tmp_path: Path, monkeypatch) -> None:
    fixture, docker = _prepared_fixture(tmp_path, monkeypatch)
    docker.live.add(docker.review_id)
    boundary = _verified_boundary(fixture, docker)
    ledger = ContainerLedger(docker)
    ledger.register(docker.review_id, "review")
    scratch = tmp_path / "probe-scratch"
    scratch.mkdir()

    fixed_tokens = iter(["aaaa1111aaaa1111", "bbbb2222bbbb2222", "cccc3333cccc3333"])
    monkeypatch.setattr(codex_review_run.secrets, "token_hex", lambda _n: next(fixed_tokens))
    captured: dict[str, object] = {}

    def _runner(argv, **kwargs):
        if argv[:4] == ["docker", "start", "-a", "-i"]:
            captured["prompt"] = kwargs.get("input")
            return subprocess.CompletedProcess(argv, 0)
        return docker(argv, **kwargs)

    run_boundary_probe(boundary, scratch=scratch, command_runner=_runner, ledger=ledger)

    prompt = captured["prompt"]
    assert str(scratch / "planted" / "run-me.sh") in prompt
    assert str(scratch / "planted" / "hooks" / "pre-commit") in prompt
    assert str(scratch / "canary" / "canary.txt") in prompt
    assert "aaaa1111aaaa1111" not in prompt
    assert "bbbb2222bbbb2222" not in prompt
    assert "cccc3333cccc3333" not in prompt


def test_probe_plants_executable_fixture_files(tmp_path: Path, monkeypatch) -> None:
    fixture, docker = _prepared_fixture(tmp_path, monkeypatch)
    docker.live.add(docker.review_id)
    boundary = _verified_boundary(fixture, docker)
    ledger = ContainerLedger(docker)
    ledger.register(docker.review_id, "review")
    scratch = tmp_path / "probe-scratch"
    scratch.mkdir()

    planted: dict[str, object] = {}

    def _runner(argv, **kwargs):
        if argv[:4] == ["docker", "start", "-a", "-i"]:
            # inspect the planted files now, while run_boundary_probe's own
            # cleanup (which deletes *scratch* on return) hasn't run yet
            run_me = scratch / "planted" / "run-me.sh"
            pre_commit = scratch / "planted" / "hooks" / "pre-commit"
            canary = scratch / "canary" / "canary.txt"
            planted["run_me_mode"] = run_me.stat().st_mode & 0o777
            planted["pre_commit_mode"] = pre_commit.stat().st_mode & 0o777
            planted["canary_exists"] = canary.exists()
            planted["run_me_parents"] = set(run_me.parents)
            return subprocess.CompletedProcess(argv, 0)
        return docker(argv, **kwargs)

    run_boundary_probe(boundary, scratch=scratch, command_runner=_runner, ledger=ledger)

    assert planted["run_me_mode"] == 0o755
    assert planted["pre_commit_mode"] == 0o755
    assert planted["canary_exists"] is True
    # outside every mount: never inside the boundary's own codex-home/out dirs
    assert fixture.codex_home_dir not in planted["run_me_parents"]
    assert fixture.out_dir not in planted["run_me_parents"]
    # and the scratch dir is gone once the probe returns
    assert not scratch.exists()


def test_probe_sign_in_refreshed_mid_run(tmp_path: Path, monkeypatch) -> None:
    fixture, docker = _prepared_fixture(tmp_path, monkeypatch)
    docker.live.add(docker.review_id)
    boundary = _verified_boundary(fixture, docker)
    ledger = ContainerLedger(docker)
    ledger.register(docker.review_id, "review")
    scratch = tmp_path / "probe-scratch"
    scratch.mkdir()

    def _runner(argv, **kwargs):
        if argv[:4] == ["docker", "start", "-a", "-i"]:
            (fixture.codex_home_dir / "auth.json").write_bytes(_auth_bytes(last_refresh=_NOW.isoformat()))
            return subprocess.CompletedProcess(argv, 0)
        return docker(argv, **kwargs)

    result = run_boundary_probe(boundary, scratch=scratch, command_runner=_runner, ledger=ledger)

    assert any("Re-login needed: run `codex login` on the host (D-11)" in r for r in result["reasons"])
