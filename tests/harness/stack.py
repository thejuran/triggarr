"""Docker argv builders and lifecycle helpers for the shipped-image smoke driver.

Every helper that talks to the Docker CLI goes through :func:`run_docker`,
a single ``subprocess.run`` wrapper invoked with list arguments and
``shell=False`` -- never a shell string. Argv builders
(:func:`triggarr_run_args`, :func:`stub_run_args`) are pure functions with no
side effects, so Plan 04's unit tests exercise them without a Docker daemon.

Naming and isolation (D-33 amendment B): every resource a :class:`HarnessSession`
creates is named ``triggarr-ci-<kind>-<session_id>-<role>`` and labelled
``org.triggarr.ci.session=<session_id>``. There is no fixed network, container,
volume name or host port anywhere in this module -- every host port is
Docker-assigned on 127.0.0.1 and read back with :func:`published_port`.
Teardown removes only the exact names a session recorded as created, in
reverse creation order, and never deletes anything by a name prefix or a
broad selector.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from tests.harness import checks
from tests.harness.checks import SmokeCheckError

SESSION_LABEL = "org.triggarr.ci.session"
NAME_PREFIX = "triggarr-ci"
STUB_ALIAS = "arr-stub"
STUB_PORT = 9696
APP_PORT = 8484
CAP_ADD: tuple[str, ...] = ("CHOWN", "DAC_OVERRIDE", "FOWNER", "SETUID", "SETGID")
STUB_API_KEY = "ci-stub-key-not-a-secret"  # Disposable, never a real credential (D-27).
RUN_UID_GID = "1000:1000"

_DOCKER_BIN: str | None = None


def _resolve_docker() -> str:
    """Resolve the docker binary once via shutil.which; missing docker is a hard stop."""
    global _DOCKER_BIN
    if _DOCKER_BIN is None:
        resolved = shutil.which("docker")
        if not resolved:
            raise SmokeCheckError("docker-missing", "docker binary not found on PATH")
        _DOCKER_BIN = resolved
    return _DOCKER_BIN


def run_docker(
    args: list[str], *, check: bool = True, timeout: float | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a docker CLI command built as a plain argv list.

    ``args[0]`` is expected to be the literal string "docker" (what every argv
    builder in this module produces); it is swapped for the resolved absolute
    path before executing. Always ``subprocess.run`` with a list and
    ``shell=False`` -- never a shell string (T-82-16).
    """
    docker_bin = _resolve_docker()
    full_args = [docker_bin, *args[1:]] if args and args[0] == "docker" else args
    result = subprocess.run(full_args, capture_output=True, text=True, shell=False, timeout=timeout)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, full_args, result.stdout, result.stderr)
    return result


@dataclass
class HarnessSession:
    """Tracks every resource one harness run creates, for exact-name teardown.

    ``created`` only ever grows after a create command has actually
    succeeded -- a failed create is never recorded, so teardown can't be
    asked to remove something that was never made.
    """

    kind: str
    session_id: str
    created: list[tuple[str, str]] = field(default_factory=list)

    def name(self, role: str) -> str:
        """Return this session's unique name for a given role (network/container/volume)."""
        return f"{NAME_PREFIX}-{self.kind}-{self.session_id}-{role}"

    def record(self, resource_kind: str, name: str) -> None:
        """Record a resource this session created, for later exact-name removal."""
        self.created.append((resource_kind, name))

    def teardown(self) -> None:
        """Remove only the exact resources this session recorded, in reverse creation order.

        Never uses a name-prefix match or a broad selector to find what to
        delete -- an "already removed" result (no such container/volume/
        network) is expected and silently ignored; any other failure is
        logged as a warning so a leaked resource is still observable.
        """
        for resource_kind, name in reversed(self.created):
            if resource_kind == "container":
                cmd = ["docker", "rm", "-f", name]
            elif resource_kind == "volume":
                cmd = ["docker", "volume", "rm", "-f", name]
            elif resource_kind == "network":
                cmd = ["docker", "network", "rm", name]
            else:  # pragma: no cover - defensive, every caller uses a known kind
                logger.warning("teardown: unknown resource kind {kind} for {name}", kind=resource_kind, name=name)
                continue
            result = run_docker(cmd, check=False)
            if result.returncode != 0 and "No such" not in (result.stderr or ""):
                logger.warning(
                    "teardown: failed to remove {kind} {name}: {stderr}",
                    kind=resource_kind,
                    name=name,
                    stderr=(result.stderr or "").strip(),
                )


def new_session(kind: str) -> HarnessSession:
    """Create a fresh HarnessSession with a CSPRNG session id; two calls never collide."""
    import secrets as _secrets

    return HarnessSession(kind=kind, session_id=_secrets.token_hex(6))


def triggarr_run_args(
    *,
    image: str,
    name: str,
    volume: str,
    network: str | None,
    session_id: str,
) -> list[str]:
    """Build the argv that starts the shipped image through its real entrypoint.

    No explicit entrypoint override, no privileged flag, and the only mount is
    the named config volume -- never a filesystem path.
    """
    args: list[str] = [
        "docker",
        "run",
        "-d",
        "--name",
        name,
        "--label",
        f"{SESSION_LABEL}={session_id}",
        "--cap-drop",
        "ALL",
    ]
    for cap in CAP_ADD:
        args += ["--cap-add", cap]
    puid, pgid = RUN_UID_GID.split(":")
    args += [
        "-p",
        f"127.0.0.1::{APP_PORT}",
        "-v",
        f"{volume}:/config",
        "-e",
        f"PUID={puid}",
        "-e",
        f"PGID={pgid}",
    ]
    if network:
        args += ["--network", network]
    args.append(image)
    return args


def stub_run_args(
    *,
    image: str,
    name: str,
    network: str,
    session_id: str,
    api_key: str,
    stub_script_path: str,
) -> list[str]:
    """Build the argv that starts the stub *arr service on the session's network.

    Reuses the given (already stdlib-capable) image with its command replaced
    by the stub script, mounted read-only -- no package install needed since
    the stub is stdlib-only.
    """
    return [
        "docker",
        "run",
        "-d",
        "--name",
        name,
        "--label",
        f"{SESSION_LABEL}={session_id}",
        "--network",
        network,
        "--network-alias",
        STUB_ALIAS,
        "-v",
        f"{stub_script_path}:/stub/arr_stub.py:ro",
        "-e",
        f"STUB_API_KEY={api_key}",
        "-p",
        f"127.0.0.1::{STUB_PORT}",
        "--entrypoint",
        "python",
        image,
        "/stub/arr_stub.py",
        "--host",
        "0.0.0.0",
        "--port",
        str(STUB_PORT),
    ]


def create_network(session: HarnessSession, role: str) -> str:
    """Create a session-labelled Docker network and record it on success."""
    name = session.name(role)
    run_docker(["docker", "network", "create", "--label", f"{SESSION_LABEL}={session.session_id}", name])
    session.record("network", name)
    return name


def create_volume(session: HarnessSession, role: str) -> str:
    """Create a session-labelled Docker volume and record it on success."""
    name = session.name(role)
    run_docker(["docker", "volume", "create", "--label", f"{SESSION_LABEL}={session.session_id}", name])
    session.record("volume", name)
    return name


def published_port(name: str, container_port: int) -> int:
    """Read back the Docker-assigned host port for container_port/tcp on the named container."""
    result = run_docker(["docker", "port", name, f"{container_port}/tcp"])
    first_line = result.stdout.strip().splitlines()[0]
    return int(first_line.rsplit(":", 1)[-1])


def seed_volume(
    session: HarnessSession,
    role: str,
    *,
    image: str,
    volume: str,
    config_file: Path,
) -> None:
    """Seed an already-created, session-labelled volume via a throwaway, never-started container.

    docker container create (volume at /config) -> docker cp the file to
    /config/triggarr.toml -> docker rm. No entrypoint override is needed
    because the container is only created, never started.
    """
    name = session.name(role)
    run_docker(
        [
            "docker",
            "container",
            "create",
            "--name",
            name,
            "--label",
            f"{SESSION_LABEL}={session.session_id}",
            "-v",
            f"{volume}:/config",
            image,
        ]
    )
    session.record("container", name)
    run_docker(["docker", "cp", str(config_file), f"{name}:/config/triggarr.toml"])
    run_docker(["docker", "rm", name])


def start_triggarr(
    session: HarnessSession,
    *,
    role: str,
    image: str,
    volume: str,
    network: str | None,
) -> tuple[str, int]:
    """Start the shipped image under test; record the container and return (name, host_port)."""
    name = session.name(role)
    args = triggarr_run_args(image=image, name=name, volume=volume, network=network, session_id=session.session_id)
    run_docker(args)
    session.record("container", name)
    port = published_port(name, APP_PORT)
    return name, port


def start_stub(
    session: HarnessSession,
    *,
    role: str,
    image: str,
    network: str,
    api_key: str,
    stub_script_path: str,
) -> tuple[str, int]:
    """Start the stub *arr service on the session's network; record and return (name, host_port)."""
    name = session.name(role)
    args = stub_run_args(
        image=image,
        name=name,
        network=network,
        session_id=session.session_id,
        api_key=api_key,
        stub_script_path=stub_script_path,
    )
    run_docker(args)
    session.record("container", name)
    port = published_port(name, STUB_PORT)
    return name, port


def assert_image_identity(image: str, expected_id: str) -> None:
    """Refuse to continue unless the image under test has exactly the expected image ID (D-30)."""
    result = run_docker(["docker", "image", "inspect", image, "--format", "{{.Id}}"])
    actual = result.stdout.strip()
    expected = expected_id.strip()
    if actual != expected:
        raise SmokeCheckError("image-identity", f"expected {expected}, got {actual}")


def wait_for_http_health(base: str, timeout: float, *, poll_interval: float = 1.0) -> None:
    """Poll checks.check_health until it passes or timeout elapses.

    While the server is still starting up (or mid-restart, between the old
    process closing its socket and the new one binding it), a connection
    attempt can legitimately fail with a connection-refused/reset OSError
    (urllib.error.URLError is itself an OSError subclass) rather than a
    well-formed SmokeCheckError -- that is an expected transient condition
    during polling, not a terminal failure, so it is retried exactly like a
    SmokeCheckError until the deadline.
    """
    deadline = time.monotonic() + timeout
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            checks.check_health(base)
            return
        except (SmokeCheckError, OSError) as exc:
            last_exc = exc
            time.sleep(poll_interval)
    raise SmokeCheckError("health-timeout", f"did not become healthy within {timeout}s: {last_exc}")


def wait_for_docker_health(name: str, timeout: float, *, poll_interval: float = 2.0) -> None:
    """Poll docker inspect's State.Health.Status until "healthy", "unhealthy", or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = run_docker(["docker", "inspect", name, "--format", "{{.State.Health.Status}}"], check=False)
        status = result.stdout.strip()
        if status == "healthy":
            return
        if status == "unhealthy":
            raise SmokeCheckError("docker-health", f"{name} reported unhealthy")
        time.sleep(poll_interval)
    raise SmokeCheckError("docker-health", f"{name} did not become healthy within {timeout}s")


def wait_for_exit(name: str, timeout: float, *, poll_interval: float = 0.5) -> int:
    """Poll docker inspect until the container stops running, then return its exit code."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = run_docker(["docker", "inspect", name, "--format", "{{.State.Running}}"], check=False)
        if result.stdout.strip() == "false":
            code_result = run_docker(["docker", "inspect", name, "--format", "{{.State.ExitCode}}"])
            return int(code_result.stdout.strip())
        time.sleep(poll_interval)
    raise SmokeCheckError("exit-timeout", f"{name} did not exit within {timeout}s")


def exec_in(
    name: str, args: list[str], *, user: str | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run a command inside a running container via docker exec, as a plain argv list."""
    cmd = ["docker", "exec"]
    if user is not None:
        cmd += ["--user", user]
    cmd += [name, *args]
    return run_docker(cmd, check=check)


def container_logs(name: str) -> str:
    """Return a container's combined stdout+stderr logs (never raises; tolerant of a missing container)."""
    result = run_docker(["docker", "logs", name], check=False)
    return (result.stdout or "") + (result.stderr or "")


def stop_and_remove(name: str) -> None:
    """Stop a container with the README's 90s grace period, then remove it."""
    run_docker(["docker", "stop", "--time", "90", name])
    run_docker(["docker", "rm", name])
