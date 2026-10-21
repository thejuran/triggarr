"""Session scaffolding for the browser regression suite (D-25, D-27, D-30, D-33).

Starts the exact shipped image (``TRIGGARR_E2E_IMAGE``/``EXPECTED_IMAGE_ID``,
D-30) and a stub *arr service on a session-isolated Docker network (reusing
``tests.harness.stack``), hands tests a fresh container per test via
:func:`triggarr_container`/:func:`admin_container`, and tracks every value a
browser step exposes (disposable password, API key, session cookies) in a
:class:`SensitiveRegistry` so :func:`pytest_sessionfinish` can byte-scan the
``--output`` directory before any artifact could be uploaded (D-27 -- an
extra defence for text/binary artifacts, not proof screenshots are safe).

Capture policy (D-33): screenshot/trace/video safety for pages that render a
credential or API key comes from *prevention*, not detection. Tests that
render such a page are marked ``credential_pages``; ``pytest_collection_finish``
inspects the final test selection (after ``-m``/``-k`` deselection, before any
fixture or browser starts -- see its docstring for why this hook, not
``pytest_collection_modifyitems``) and refuses to run a ``credential_pages``
test with any capture flag enabled.
"""

from __future__ import annotations

import itertools
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from loguru import logger

from tests.harness import checks, stack
from tests.harness.artifact_scan import scrub
from tests.harness.stack import HarnessSession

CREDENTIAL_PAGES_MARKER = "credential_pages"

# Shared with any out-of-process invocation of the credential_pages suite
# (Plan 07's CI wiring, this plan's own subprocess probes) so there is one
# source of truth for "capture fully off."
CREDENTIAL_RUN_FLAGS: tuple[str, ...] = ("--tracing", "off", "--screenshot", "off", "--video", "off")

_STUB_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "harness" / "arr_stub.py"
_CI_FIXTURE_PATH = Path(__file__).resolve().parent.parent / "harness" / "fixtures" / "triggarr-ci.toml"


@dataclass
class SensitiveRegistry:
    """Tracks every value a browser step has exposed, for redaction and the D-27 byte scan.

    Never logs or raises with the value itself -- only :meth:`register` ever
    sees it, and :meth:`redact` only ever emits ``***`` in its place.
    """

    values: list[str] = field(default_factory=list)

    def register(self, value: str | None) -> None:
        """Record a sensitive value, ignoring an empty/missing one. Idempotent."""
        if value and value not in self.values:
            self.values.append(value)

    def redact(self, text: str) -> str:
        """Replace every registered value's occurrences in ``text`` with ``***``."""
        redacted = text
        for value in self.values:
            redacted = redacted.replace(value, "***")
        return redacted


@dataclass(frozen=True)
class Credentials:
    """The suite's one disposable admin account (D-27: never a real credential)."""

    username: str
    password: str


@dataclass(frozen=True)
class E2EStack:
    """The session-scoped network + stub *arr service every test container joins."""

    session: HarnessSession
    network: str
    stub_name: str
    stub_port: int


@dataclass(frozen=True)
class TriggarrContainer:
    """A single fresh container of the image under test, ready to receive browser traffic."""

    url: str
    name: str


@dataclass(frozen=True)
class StubControl:
    """A control handle for this session's stub *arr service, on its Docker-assigned host port.

    No fixed port anywhere in this class (D-33 amendment B) -- ``base_url`` is
    built from :attr:`E2EStack.stub_port`, which ``tests.harness.stack`` reads
    back from Docker after the stub container starts.
    """

    base_url: str

    def set_up(self, up: bool) -> None:
        """POST ``{"up": up}`` to the stub's control endpoint."""
        request = urllib.request.Request(
            f"{self.base_url}/__control/state",
            data=json.dumps({"up": up}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5):
            pass

    def state(self) -> dict[str, Any]:
        """GET the stub's current ``{"up", "api_requests"}`` state."""
        with urllib.request.urlopen(f"{self.base_url}/__control/state", timeout=5) as response:
            return json.loads(response.read())


def _record_session(session: HarnessSession, network: str | None) -> None:
    """Write {session_id, network, containers, volumes} to $E2E_SESSION_RECORD, if set.

    Called after every resource this session creates so the isolation test
    (D-33 amendment B) can read a probe subprocess's own resource names from
    outside that subprocess, at any point after it exits. No-op when the env
    var is unset (the normal, non-probe case).
    """
    record_path = os.environ.get("E2E_SESSION_RECORD")
    if not record_path:
        return
    containers = [name for kind, name in session.created if kind == "container"]
    volumes = [name for kind, name in session.created if kind == "volume"]
    payload = {
        "session_id": session.session_id,
        "network": network,
        "containers": containers,
        "volumes": volumes,
    }
    Path(record_path).write_text(json.dumps(payload, indent=2))


def _wait_for_stub(base_url: str, timeout: float, *, poll_interval: float = 0.5) -> None:
    """Poll the stub's control endpoint (no auth required) until it answers or timeout elapses."""
    deadline = time.monotonic() + timeout
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/__control/state", timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError) as exc:
            last_exc = exc
        time.sleep(poll_interval)
    raise RuntimeError(f"stub did not become ready within {timeout}s: {last_exc}")


# ---------------------------------------------------------------------------
# pytest hooks
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Register the credential_pages marker and create this session's SensitiveRegistry.

    The registry lives on ``config`` (not only as a fixture) so
    :func:`pytest_sessionfinish` -- a hook, with no fixture access -- can
    reach the same instance every fixture in this session registered into.
    """
    config.addinivalue_line(
        "markers",
        f"{CREDENTIAL_PAGES_MARKER}: renders credentials or an API key; captures forbidden",
    )
    config._e2e_sensitive_registry = SensitiveRegistry()  # type: ignore[attr-defined]


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Record each phase's report on the item so a fixture teardown can check rep_call.failed."""
    report = yield
    setattr(item, f"rep_{report.when}", report)
    return report


def pytest_collection_finish(session: pytest.Session) -> None:
    """Refuse the final selection if it mixes a credential_pages test with any capture flag (D-33 amendment A).

    Why this hook and not ``pytest_collection_modifyitems``: in pytest 9.0.3
    (the locked version), ``Session.perform_collect`` calls
    ``pytest_collection_modifyitems`` -- where the mark plugin deselects
    ``-m``/``-k`` items, with no ordering guarantee relative to a conftest
    implementation of that same hook -- and only then calls
    ``pytest_collection_finish(session)``; the runtest loop, and with it
    every fixture and browser launch, starts only after collection returns.
    So ``session.items`` here is the final selection and nothing has run
    yet. A ``trylast`` ``modifyitems`` hook would also see the final
    selection but depends on hook-ordering guarantees this does not.

    A ``pytest.UsageError`` raised here makes pytest exit with code 4
    (``wrap_session`` maps ``UsageError`` to ``ExitCode.USAGE_ERROR``).
    """
    config = session.config
    has_credential_page = any(item.get_closest_marker(CREDENTIAL_PAGES_MARKER) is not None for item in session.items)
    if not has_credential_page:
        return
    capture_on = any(
        config.getoption(flag, default="off") not in (None, "off")
        for flag in ("--tracing", "--screenshot", "--video")
    )
    if capture_on:
        raise pytest.UsageError(
            "capture is disabled for credential pages: run them with --tracing off --screenshot off --video off"
        )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Byte-scan the --output directory with this session's registered sensitive values (D-27)."""
    del exitstatus
    registry: SensitiveRegistry | None = getattr(session.config, "_e2e_sensitive_registry", None)
    if registry is None:
        return
    output_dir = session.config.getoption("--output", default=None)
    if not output_dir:
        return
    scrub(Path(output_dir), registry.values)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sensitive_registry(pytestconfig: pytest.Config) -> SensitiveRegistry:
    """Return this session's SensitiveRegistry (created in pytest_configure)."""
    return pytestconfig._e2e_sensitive_registry  # type: ignore[attr-defined]


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any]) -> dict[str, Any]:
    """Pass pytest-playwright's defaults through unchanged -- this suite never records a HAR file (D-27)."""
    return dict(browser_context_args)


@pytest.fixture(scope="session")
def e2e_image() -> str:
    """Resolve and identity-verify the exact image under test (D-30). Fails, never skips, if unset."""
    image = os.environ.get("TRIGGARR_E2E_IMAGE")
    expected_id = os.environ.get("EXPECTED_IMAGE_ID")
    if not image or not expected_id:
        pytest.fail(
            "TRIGGARR_E2E_IMAGE and EXPECTED_IMAGE_ID must both be set to run the browser suite "
            "(D-30: the suite runs against the shipped image, never a rebuild)"
        )
    stack.assert_image_identity(image, expected_id)
    return image


@pytest.fixture(scope="session")
def e2e_stack(e2e_image: str) -> Iterator[E2EStack]:
    """Start this session's isolated network + stub *arr service; tear down only this session's resources."""
    session = stack.new_session("e2e")
    try:
        network_name = stack.create_network(session, "net")
        _record_session(session, network_name)
        stub_name, stub_port = stack.start_stub(
            session,
            role="stub",
            image=e2e_image,
            network=network_name,
            api_key=stack.STUB_API_KEY,
            stub_script_path=str(_STUB_SCRIPT_PATH),
        )
        _record_session(session, network_name)
        _wait_for_stub(f"http://127.0.0.1:{stub_port}", timeout=30)
        yield E2EStack(session=session, network=network_name, stub_name=stub_name, stub_port=stub_port)
    finally:
        session.teardown()


@pytest.fixture(scope="session")
def credentials(sensitive_registry: SensitiveRegistry) -> Credentials:
    """This suite's one disposable admin account; its password and the stub's API key are pre-registered."""
    password = secrets.token_urlsafe(18)
    sensitive_registry.register(password)
    sensitive_registry.register(stack.STUB_API_KEY)
    return Credentials(username="e2e-admin", password=password)


@pytest.fixture
def stub_control(e2e_stack: E2EStack) -> Iterator[StubControl]:
    """A handle to flip this session's stub *arr service up/down mid-test; resets to up=True at teardown."""
    control = StubControl(base_url=f"http://127.0.0.1:{e2e_stack.stub_port}")
    yield control
    control.set_up(True)


_container_counter = itertools.count(1)


@pytest.fixture
def triggarr_container(
    e2e_image: str,
    e2e_stack: E2EStack,
    sensitive_registry: SensitiveRegistry,
    request: pytest.FixtureRequest,
) -> Iterator[TriggarrContainer]:
    """Start a fresh, seeded container of the image under test for exactly one test.

    Primary teardown stops and removes this container and its volume by
    exact name immediately; both are also recorded on the shared session
    (via stack.py's own session.record calls) as a fallback the session
    teardown will still clean up if this teardown is itself interrupted.
    """
    n = next(_container_counter)
    session = e2e_stack.session

    volume_name = stack.create_volume(session, f"config-{n}")
    _record_session(session, e2e_stack.network)
    stack.seed_volume(session, f"config-{n}", image=e2e_image, volume=volume_name, config_file=_CI_FIXTURE_PATH)

    container_name, port = stack.start_triggarr(
        session, role=f"app-{n}", image=e2e_image, volume=volume_name, network=e2e_stack.network
    )
    _record_session(session, e2e_stack.network)
    base_url = f"http://127.0.0.1:{port}"
    stack.wait_for_http_health(base_url, timeout=30)

    yield TriggarrContainer(url=base_url, name=container_name)

    rep_call = getattr(request.node, "rep_call", None)
    if rep_call is not None and rep_call.failed:
        output_dir = request.config.getoption("--output", default=None)
        if output_dir:
            logs = stack.container_logs(container_name)
            redacted = sensitive_registry.redact(logs)
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            (out_path / f"{container_name}-logs.txt").write_text(redacted)

    stack.stop_and_remove(container_name)
    result = stack.run_docker(["docker", "volume", "rm", "-f", volume_name], check=False)
    if result.returncode != 0 and "No such" not in (result.stderr or ""):
        logger.warning("triggarr_container: failed to remove volume {name}: {err}", name=volume_name, err=result.stderr)


@pytest.fixture
def admin_container(
    triggarr_container: TriggarrContainer,
    credentials: Credentials,
    sensitive_registry: SensitiveRegistry,
) -> TriggarrContainer:
    """A triggarr_container with setup already completed over HTTP (D-25's login/logout flows need this)."""
    cookie = checks.complete_setup(triggarr_container.url, credentials.username, credentials.password)
    sensitive_registry.register(cookie)
    del cookie
    return triggarr_container
