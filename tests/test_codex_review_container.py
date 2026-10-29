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
    REVIEW_CODEX_VERSION,
    REVIEW_IMAGE_BUILD_ARGV,
    REVIEW_IMAGE_LABEL,
    REVIEW_IMAGE_REF,
    SCHEMA_IN_CONTAINER,
    SCHEMA_PATH,
    ContainerLedger,
    ExpectedCanary,
    ExpectedContainer,
    RunnerError,
    UnsafeOutputError,
    canary_paths,
    container_check_argv,
    container_create_argv,
    credential_outcome,
    credential_preflight,
    docker_env,
    host_credential_path,
    host_exposure_problems,
    inspection_codex_argv,
    parse_canary_check,
    prepare_codex_home,
    remove_container_confirmed,
    safe_read_regular_file,
    stage_output_schema,
    verify_container_config,
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
    ) -> None:
        self.calls: list[list[str]] = []
        self.envs: list[dict | None] = []
        self.live = set(live or ())
        self.rm_breaks = set(rm_breaks or ())
        self.ps_breaks = set(ps_breaks or ())
        self.raise_on = raise_on or {}

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        self.envs.append(kwargs.get("env"))
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
