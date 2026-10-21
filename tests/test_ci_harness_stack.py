"""Unit tests for tests/harness/stack.py: pure argv builders and lifecycle helpers.

These tests never touch a real Docker daemon -- every function that executes a
docker command is exercised against a stubbed ``stack.run_docker`` (or a
monkeypatched docker-resolution hook), so this module stays in the fast
default `pytest tests/` collection. Plan 04's local proof against a real
image lives in Task 2's verification run, not here.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from tests.harness import stack
from triggarr.models.config import Settings

_FIXTURE_PATH = Path(__file__).resolve().parent / "harness" / "fixtures" / "triggarr-ci.toml"


# ---------------------------------------------------------------------------
# triggarr_run_args
# ---------------------------------------------------------------------------


def test_triggarr_run_args_shape() -> None:
    args = stack.triggarr_run_args(
        image="triggarr:ci-test",
        name="triggarr-ci-smoke-abc123-app",
        volume="triggarr-ci-smoke-abc123-config",
        network="triggarr-ci-smoke-abc123-net",
        session_id="abc123",
    )
    assert args[:3] == ["docker", "run", "-d"]
    assert args[-1] == "triggarr:ci-test"
    assert "--label" in args
    assert f"{stack.SESSION_LABEL}=abc123" in args
    assert "--cap-drop" in args
    cap_drop_index = args.index("--cap-drop")
    assert args[cap_drop_index + 1] == "ALL"
    for cap in stack.CAP_ADD:
        cap_add_indices = [i for i, value in enumerate(args) if value == "--cap-add"]
        assert any(args[i + 1] == cap for i in cap_add_indices), f"missing --cap-add {cap}"
    assert "127.0.0.1::8484" in args
    assert "triggarr-ci-smoke-abc123-config:/config" in args
    assert "PUID=1000" in args
    assert "PGID=1000" in args


def test_triggarr_run_args_never_has_entrypoint_or_privileged() -> None:
    args = stack.triggarr_run_args(
        image="triggarr:ci-test",
        name="triggarr-ci-smoke-abc123-app",
        volume="triggarr-ci-smoke-abc123-config",
        network=None,
        session_id="abc123",
    )
    assert "--entrypoint" not in args
    assert "--privileged" not in args


def test_triggarr_run_args_never_mounts_a_filesystem_path() -> None:
    args = stack.triggarr_run_args(
        image="triggarr:ci-test",
        name="triggarr-ci-smoke-abc123-app",
        volume="triggarr-ci-smoke-abc123-config",
        network=None,
        session_id="abc123",
    )
    for index, value in enumerate(args):
        if value == "-v":
            source = args[index + 1].split(":", 1)[0]
            assert not source.startswith("/"), f"-v source looks like a filesystem path: {source}"


def test_triggarr_run_args_no_network_omits_network_flag() -> None:
    args = stack.triggarr_run_args(
        image="triggarr:ci-test",
        name="triggarr-ci-smoke-abc123-firstrun",
        volume="triggarr-ci-smoke-abc123-firstrun-config",
        network=None,
        session_id="abc123",
    )
    assert "--network" not in args


def test_triggarr_run_args_no_fixed_host_port() -> None:
    args = stack.triggarr_run_args(
        image="triggarr:ci-test",
        name="triggarr-ci-smoke-abc123-app",
        volume="v",
        network=None,
        session_id="abc123",
    )
    publish_values = [value for value in args if value.startswith("127.0.0.1:")]
    assert publish_values == ["127.0.0.1::8484"]


# ---------------------------------------------------------------------------
# stub_run_args
# ---------------------------------------------------------------------------


def test_stub_run_args_shape() -> None:
    args = stack.stub_run_args(
        image="triggarr:ci-test",
        name="triggarr-ci-smoke-abc123-stub",
        network="triggarr-ci-smoke-abc123-net",
        session_id="abc123",
        api_key="test-stub-key",
        stub_script_path="/host/path/arr_stub.py",
    )
    assert args[:3] == ["docker", "run", "-d"]
    assert "--entrypoint" in args
    entrypoint_index = args.index("--entrypoint")
    assert args[entrypoint_index + 1] == "python"
    assert "--network-alias" in args
    alias_index = args.index("--network-alias")
    assert args[alias_index + 1] == stack.STUB_ALIAS
    assert "/host/path/arr_stub.py:/stub/arr_stub.py:ro" in args
    assert "STUB_API_KEY=test-stub-key" in args
    assert f"{stack.SESSION_LABEL}=abc123" in args
    assert "127.0.0.1::9696" in args
    assert "triggarr-ci-smoke-abc123-net" in args


def test_stub_run_args_uses_the_given_image() -> None:
    args = stack.stub_run_args(
        image="triggarr:ci-test",
        name="n",
        network="net",
        session_id="abc123",
        api_key="k",
        stub_script_path="/x/arr_stub.py",
    )
    assert "triggarr:ci-test" in args


# ---------------------------------------------------------------------------
# HarnessSession / new_session
# ---------------------------------------------------------------------------


def test_new_session_ids_are_disjoint() -> None:
    first = stack.new_session("smoke")
    second = stack.new_session("smoke")
    assert first.session_id != second.session_id
    assert first.name("app") != second.name("app")


def test_session_name_format() -> None:
    session = stack.new_session("smoke")
    session.session_id = "deadbeef0000"
    assert session.name("app") == f"{stack.NAME_PREFIX}-smoke-deadbeef0000-app"


def test_session_record_and_teardown_removes_only_its_own_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    issued: list[list[str]] = []

    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        issued.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)

    session = stack.new_session("smoke")
    session.record("container", session.name("app"))
    session.record("volume", session.name("config"))
    session.record("network", session.name("net"))

    # A foreign resource this session never created -- teardown must never reference it.
    foreign_name = "triggarr-ci-smoke-deadbeefcafe-app"

    session.teardown()

    all_args = [arg for call in issued for arg in call]
    assert foreign_name not in all_args
    for call in issued:
        joined = " ".join(call)
        assert "--filter" not in joined
        assert "*" not in joined

    # Reverse-creation order: network, volume, container (network recorded last, removed first).
    kinds_in_order = []
    for call in issued:
        if "rm" in call and "volume" in call:
            kinds_in_order.append("volume")
        elif "rm" in call and "network" in call:
            kinds_in_order.append("network")
        elif "rm" in call:
            kinds_in_order.append("container")
    assert kinds_in_order == ["network", "volume", "container"]


def test_teardown_ignores_already_removed_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="Error: No such container: x")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)

    session = stack.new_session("smoke")
    session.record("container", session.name("app"))
    session.teardown()  # Must not raise.


# ---------------------------------------------------------------------------
# create_network / create_volume
# ---------------------------------------------------------------------------


def test_create_network_includes_session_label_and_records_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    issued: list[list[str]] = []

    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        issued.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    session = stack.new_session("smoke")

    name = stack.create_network(session, "net")

    assert name == session.name("net")
    assert any(f"{stack.SESSION_LABEL}={session.session_id}" in call for call in issued)
    assert ("network", name) in session.created


def test_create_volume_includes_session_label_and_records_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    issued: list[list[str]] = []

    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        issued.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    session = stack.new_session("smoke")

    name = stack.create_volume(session, "config")

    assert name == session.name("config")
    assert any(f"{stack.SESSION_LABEL}={session.session_id}" in call for call in issued)
    assert ("volume", name) in session.created


def test_create_network_does_not_record_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        raise subprocess.CalledProcessError(1, args, "", "boom")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    session = stack.new_session("smoke")

    with pytest.raises(subprocess.CalledProcessError):
        stack.create_network(session, "net")
    assert session.created == []


# ---------------------------------------------------------------------------
# published_port
# ---------------------------------------------------------------------------


def test_published_port_parses_docker_port_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        return subprocess.CompletedProcess(args, 0, stdout="0.0.0.0:54321\n", stderr="")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    assert stack.published_port("some-name", 8484) == 54321


def test_published_port_handles_loopback_host(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        return subprocess.CompletedProcess(args, 0, stdout="127.0.0.1:49999\n", stderr="")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    assert stack.published_port("some-name", 9696) == 49999


# ---------------------------------------------------------------------------
# seed_volume
# ---------------------------------------------------------------------------


def test_seed_volume_creates_copies_and_removes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    issued: list[list[str]] = []

    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        issued.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    session = stack.new_session("smoke")
    config_file = tmp_path / "triggarr-ci.toml"
    config_file.write_text("[general]\n")

    stack.seed_volume(
        session,
        "config-seed",
        image="triggarr:ci-test",
        volume=session.name("config"),
        config_file=config_file,
    )

    flattened = [" ".join(call) for call in issued]
    assert any("container create" in call for call in flattened)
    assert any(call.startswith("docker cp ") for call in flattened)
    assert any("docker rm " in call for call in flattened)
    # Every issued argv is a plain list of strings -- never a shell string.
    for call in issued:
        assert isinstance(call, list)
        assert all(isinstance(part, str) for part in call)
    assert ("container", session.name("config-seed")) in session.created


# ---------------------------------------------------------------------------
# start_stub / start_triggarr
# ---------------------------------------------------------------------------


def test_start_triggarr_records_container_and_returns_port(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        if args[:2] == ["docker", "port"]:
            return subprocess.CompletedProcess(args, 0, stdout="0.0.0.0:40000\n", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    session = stack.new_session("smoke")

    name, port = stack.start_triggarr(
        session, role="app", image="triggarr:ci-test", volume=session.name("config"), network=None
    )

    assert name == session.name("app")
    assert port == 40000
    assert ("container", name) in session.created


def test_start_stub_records_container_and_returns_port(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        if args[:2] == ["docker", "port"]:
            return subprocess.CompletedProcess(args, 0, stdout="0.0.0.0:41000\n", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    session = stack.new_session("smoke")

    name, port = stack.start_stub(
        session,
        role="stub",
        image="triggarr:ci-test",
        network=session.name("net"),
        api_key=stack.STUB_API_KEY,
        stub_script_path="/x/arr_stub.py",
    )

    assert name == session.name("stub")
    assert port == 41000
    assert ("container", name) in session.created


# ---------------------------------------------------------------------------
# assert_image_identity
# ---------------------------------------------------------------------------


def test_assert_image_identity_passes_on_match(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        return subprocess.CompletedProcess(args, 0, stdout="sha256:abc123\n", stderr="")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    stack.assert_image_identity("triggarr:ci-test", "sha256:abc123")  # Does not raise.


def test_assert_image_identity_fails_on_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        return subprocess.CompletedProcess(args, 0, stdout="sha256:different\n", stderr="")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    with pytest.raises(stack.SmokeCheckError) as excinfo:
        stack.assert_image_identity("triggarr:ci-test", "sha256:abc123")
    assert excinfo.value.reason == "image-identity"


# ---------------------------------------------------------------------------
# wait_for_http_health / wait_for_docker_health / wait_for_exit
# ---------------------------------------------------------------------------


def test_wait_for_http_health_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    def always_fail(base: str) -> None:
        raise stack.checks.SmokeCheckError("health", "not ready")

    monkeypatch.setattr(stack.checks, "check_health", always_fail)
    monkeypatch.setattr(stack.time, "sleep", lambda _seconds: None)

    with pytest.raises(stack.SmokeCheckError):
        stack.wait_for_http_health("http://127.0.0.1:1", 0.05)


def test_wait_for_http_health_retries_past_a_connection_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    """A transient connection-refused/reset OSError (e.g. mid-restart) is retried, not raised."""
    calls = {"count": 0}

    def refused_then_ok(base: str) -> None:
        calls["count"] += 1
        if calls["count"] < 2:
            raise ConnectionResetError("Connection reset by peer")

    monkeypatch.setattr(stack.checks, "check_health", refused_then_ok)
    monkeypatch.setattr(stack.time, "sleep", lambda _seconds: None)

    stack.wait_for_http_health("http://127.0.0.1:1", 5.0)  # Does not raise.
    assert calls["count"] >= 2


def test_wait_for_http_health_times_out_on_repeated_connection_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    def always_refused(base: str) -> None:
        raise ConnectionResetError("Connection reset by peer")

    monkeypatch.setattr(stack.checks, "check_health", always_refused)
    monkeypatch.setattr(stack.time, "sleep", lambda _seconds: None)

    with pytest.raises(stack.SmokeCheckError) as excinfo:
        stack.wait_for_http_health("http://127.0.0.1:1", 0.05)
    assert excinfo.value.reason == "health-timeout"


def test_wait_for_http_health_succeeds_once_check_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def flaky_then_ok(base: str) -> None:
        calls["count"] += 1
        if calls["count"] < 2:
            raise stack.checks.SmokeCheckError("health", "not ready")

    monkeypatch.setattr(stack.checks, "check_health", flaky_then_ok)
    monkeypatch.setattr(stack.time, "sleep", lambda _seconds: None)

    stack.wait_for_http_health("http://127.0.0.1:1", 5.0)  # Does not raise.
    assert calls["count"] >= 2


def test_wait_for_docker_health_reports_unhealthy(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        return subprocess.CompletedProcess(args, 0, stdout="unhealthy\n", stderr="")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    monkeypatch.setattr(stack.time, "sleep", lambda _seconds: None)

    with pytest.raises(stack.SmokeCheckError) as excinfo:
        stack.wait_for_docker_health("app", 1.0)
    assert excinfo.value.reason == "docker-health"


def test_wait_for_docker_health_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        return subprocess.CompletedProcess(args, 0, stdout="healthy\n", stderr="")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    stack.wait_for_docker_health("app", 1.0)  # Does not raise.


def test_wait_for_exit_returns_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        if "{{.State.Running}}" in args:
            return subprocess.CompletedProcess(args, 0, stdout="false\n", stderr="")
        if "{{.State.ExitCode}}" in args:
            return subprocess.CompletedProcess(args, 0, stdout="1\n", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    monkeypatch.setattr(stack.time, "sleep", lambda _seconds: None)

    assert stack.wait_for_exit("firstrun", 1.0) == 1


def test_wait_for_exit_times_out_while_running(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        return subprocess.CompletedProcess(args, 0, stdout="true\n", stderr="")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    monkeypatch.setattr(stack.time, "sleep", lambda _seconds: None)

    with pytest.raises(stack.SmokeCheckError):
        stack.wait_for_exit("firstrun", 0.05)


# ---------------------------------------------------------------------------
# exec_in / container_logs / stop_and_remove
# ---------------------------------------------------------------------------


def test_exec_in_builds_argv_with_user(monkeypatch: pytest.MonkeyPatch) -> None:
    issued: list[list[str]] = []

    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        issued.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    stack.exec_in("app", ["rm", "/app/triggarr/static/css/output.css"], user="0")

    assert issued[0] == ["docker", "exec", "--user", "0", "app", "rm", "/app/triggarr/static/css/output.css"]


def test_exec_in_no_user_omits_user_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    issued: list[list[str]] = []

    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        issued.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    stack.exec_in("app", ["cat", "/config/triggarr.toml"])

    assert issued[0] == ["docker", "exec", "app", "cat", "/config/triggarr.toml"]
    assert "--user" not in issued[0]


def test_container_logs_combines_stdout_and_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        return subprocess.CompletedProcess(args, 0, stdout="out-line\n", stderr="err-line\n")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    logs = stack.container_logs("app")
    assert "out-line" in logs
    assert "err-line" in logs


def test_stop_and_remove_issues_stop_then_rm(monkeypatch: pytest.MonkeyPatch) -> None:
    issued: list[list[str]] = []

    def fake_run_docker(args: list[str], *, check: bool = True, timeout: float | None = None) -> Any:
        issued.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(stack, "run_docker", fake_run_docker)
    stack.stop_and_remove("app")

    assert issued[0] == ["docker", "stop", "--time", "90", "app"]
    assert issued[1] == ["docker", "rm", "app"]


# ---------------------------------------------------------------------------
# run_docker / docker resolution
# ---------------------------------------------------------------------------


def test_run_docker_raises_docker_missing_when_not_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stack, "_DOCKER_BIN", None)
    monkeypatch.setattr(stack.shutil, "which", lambda _name: None)

    with pytest.raises(stack.SmokeCheckError) as excinfo:
        stack.run_docker(["docker", "ps"])
    assert excinfo.value.reason == "docker-missing"


def test_run_docker_raises_called_process_error_on_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stack, "_DOCKER_BIN", "/usr/bin/docker")

    def fake_subprocess_run(args: list[str], **kwargs: Any) -> Any:
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="boom")

    monkeypatch.setattr(stack.subprocess, "run", fake_subprocess_run)

    with pytest.raises(subprocess.CalledProcessError):
        stack.run_docker(["docker", "ps"])


def test_run_docker_check_false_does_not_raise_on_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stack, "_DOCKER_BIN", "/usr/bin/docker")

    def fake_subprocess_run(args: list[str], **kwargs: Any) -> Any:
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="boom")

    monkeypatch.setattr(stack.subprocess, "run", fake_subprocess_run)

    result = stack.run_docker(["docker", "ps"], check=False)
    assert result.returncode == 1


def test_no_shell_true_anywhere_in_stack_module() -> None:
    source = Path(stack.__file__).read_text(encoding="utf-8")
    assert "shell=True" not in source


# ---------------------------------------------------------------------------
# Fixture: parses and validates as Settings, setup still required
# ---------------------------------------------------------------------------


def test_fixture_parses_as_toml_and_validates_as_settings() -> None:
    data = tomllib.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    try:
        settings = Settings.model_validate(data)
    except ValidationError as exc:
        pytest.fail(f"fixture does not validate as Settings: {exc}")

    assert list(settings.radarr.keys()) == ["ci-stub"]
    instance = settings.radarr["ci-stub"]
    assert instance.enabled is True
    assert instance.url == "http://arr-stub:9696"
    assert instance.api_key.get_secret_value() != ""
    assert settings.auth.needs_setup is True
    assert settings.sonarr == {}
    assert settings.lidarr == {}
