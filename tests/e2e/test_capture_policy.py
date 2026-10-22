"""D-33 capture-policy proof: no capture survives a pre-registration setup failure, and the
guard refuses capture for credential pages -- both exercised against a live, isolated probe
session running beside this test's own live parent session (D-33 amendment B).

Every subprocess here inherits TRIGGARR_E2E_IMAGE/EXPECTED_IMAGE_ID from this process's own
environment so the probe runs against the same image identity this test file itself requires.
Subprocess output is checked for the generated API key and the admin password before either
value is used in any assertion message -- never echoed.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

from tests.e2e.conftest import (
    CREDENTIAL_RUN_FLAGS,
    PROBE_ADMIN_PASSWORD_ENV,
    PROBE_KEY_DIGEST_FILE_ENV,
    PROBE_KEY_SALT_ENV,
    Credentials,
    E2EStack,
    TriggarrContainer,
    secret_fingerprint,
)
from tests.harness import checks, stack

pytestmark = pytest.mark.credential_pages

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PROBE_PATH = Path(__file__).resolve().parent / "probes" / "probe_setup_fails_before_registration.py"
_CAPTURE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webm", ".zip")
_PROBE_SUBPROCESS_TIMEOUT = 180.0
# triggarr API keys are secrets.token_hex(16): 32 lowercase hex characters.
_KEY_LEN = 32
_HEX_RUN = re.compile(r"[0-9a-f]{32,}")


def _contains_key(text: str, key_digest: str, salt_hex: str) -> bool:
    """True when any 32-character window of any hex run in ``text`` has the fingerprint the probe handed over.

    Every window is tried, so a key embedded in a longer hex string is still found -- the same reach as a
    plain substring check, without the parent ever holding the key.
    """
    windows = {run[i : i + _KEY_LEN] for run in _HEX_RUN.findall(text) for i in range(len(run) - _KEY_LEN + 1)}
    return any(secret_fingerprint(window, salt_hex) == key_digest for window in windows)


def _probe_cmd(out_dir: Path, *capture_flags: str, sentinel_plugin: bool = False) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(_PROBE_PATH),
        "-o",
        "python_files=probe_*.py",
        "-o",
        "python_functions=probe_*",
        "-p",
        "no:cacheprovider",
    ]
    if sentinel_plugin:
        cmd += ["-p", "tests.e2e.probes.sentinel_plugin"]
    cmd += ["--browser", "chromium", *capture_flags, "--output", str(out_dir)]
    return cmd


def _labelled_resource_ids() -> dict[str, set[str]]:
    """Snapshot every Docker resource carrying the CI session label, across all sessions."""
    snapshot: dict[str, set[str]] = {}
    for kind, args in (
        ("containers", ["ps", "-a", "-q"]),
        ("volumes", ["volume", "ls", "-q"]),
        ("networks", ["network", "ls", "-q"]),
    ):
        result = stack.run_docker(["docker", *args, "--filter", f"label={stack.SESSION_LABEL}"])
        snapshot[kind] = set(result.stdout.split())
    return snapshot


def test_setup_failure_before_registration_leaves_no_capture(
    tmp_path: Path,
    e2e_stack: E2EStack,
    admin_container: TriggarrContainer,
    credentials: Credentials,
) -> None:
    parent_network = e2e_stack.network
    parent_stub_name = e2e_stack.stub_name
    parent_session_id = e2e_stack.session.session_id
    parent_app_name = admin_container.name
    parent_app_url = admin_container.url

    digest_file = tmp_path / "key.digest"
    session_record = tmp_path / "probe-session.json"
    out_dir = tmp_path / "out"
    salt_hex = secrets.token_hex(16)

    # The probe uses this process's password (no credential crosses on disk) and returns only a salted
    # fingerprint of the API key it generated; leaks are found by fingerprinting every key-shaped token.
    env = {
        **os.environ,
        PROBE_ADMIN_PASSWORD_ENV: credentials.password,
        PROBE_KEY_SALT_ENV: salt_hex,
        PROBE_KEY_DIGEST_FILE_ENV: str(digest_file),
        "E2E_SESSION_RECORD": str(session_record),
    }
    cmd = _probe_cmd(out_dir, *CREDENTIAL_RUN_FLAGS)
    result = subprocess.run(
        cmd, capture_output=True, text=True, env=env, cwd=_REPO_ROOT, timeout=_PROBE_SUBPROCESS_TIMEOUT
    )

    combined_output = result.stdout + result.stderr
    assert digest_file.exists(), "probe did not hand over the generated API key's fingerprint before failing"
    key_digest = digest_file.read_text()
    assert key_digest  # non-empty

    # Check subprocess output for the secrets before using either in any assertion message.
    api_key_leaked = _contains_key(combined_output, key_digest, salt_hex)
    password_leaked = credentials.password in combined_output
    assert not api_key_leaked, "subprocess output must never echo the generated API key"
    assert not password_leaked, "subprocess output must never echo the admin password"

    assert result.returncode == 1
    assert "probe: deliberate failure before registration" in combined_output

    out_files = [p for p in out_dir.rglob("*") if p.is_file()] if out_dir.exists() else []
    capture_files = [p for p in out_files if p.suffix in _CAPTURE_EXTENSIONS]
    assert capture_files == [], f"no capture files should exist, found: {[p.name for p in capture_files]}"
    for path in out_files:
        text = path.read_bytes().decode("latin-1")
        assert not _contains_key(text, key_digest, salt_hex), f"{path.name} must not contain the API key bytes"
    assert (out_dir / "scan-complete.json").exists()

    # --- Isolation (D-33 amendment B) ---
    probe_record = json.loads(session_record.read_text())
    probe_session_id = probe_record["session_id"]
    assert probe_session_id != parent_session_id
    assert probe_record["network"] != parent_network
    assert parent_app_name not in probe_record["containers"]
    assert parent_stub_name not in probe_record["containers"]

    for name in probe_record["containers"]:
        inspected = stack.run_docker(["docker", "inspect", name], check=False)
        assert inspected.returncode != 0, f"probe container {name} should have been torn down"
    for name in probe_record["volumes"]:
        inspected = stack.run_docker(["docker", "volume", "inspect", name], check=False)
        assert inspected.returncode != 0, f"probe volume {name} should have been torn down"
    if probe_record["network"]:
        inspected = stack.run_docker(["docker", "network", "inspect", probe_record["network"]], check=False)
        assert inspected.returncode != 0, "probe network should have been torn down"

    for kind_args in (["ps", "-a", "-q"], ["volume", "ls", "-q"], ["network", "ls", "-q"]):
        leftover = stack.run_docker(
            ["docker", *kind_args, "--filter", f"label={stack.SESSION_LABEL}={probe_session_id}"]
        )
        assert leftover.stdout.strip() == "", f"leftover probe-labelled resources: {leftover.stdout!r}"

    # Parent's own resources must still exist and be healthy.
    network_inspect = stack.run_docker(["docker", "network", "inspect", parent_network], check=False)
    assert network_inspect.returncode == 0
    stub_inspect = stack.run_docker(["docker", "inspect", parent_stub_name], check=False)
    assert stub_inspect.returncode == 0
    health = stack.run_docker(
        ["docker", "inspect", parent_app_name, "--format", "{{.State.Health.Status}}"], check=False
    )
    assert health.stdout.strip() == "healthy"
    checks.check_health(parent_app_url)


def test_capture_flags_refused_for_credential_pages(tmp_path: Path) -> None:
    sentinel_file = tmp_path / "sentinel.txt"
    out_dir = tmp_path / "out"

    before = _labelled_resource_ids()

    env = {**os.environ, "E2E_SENTINEL_FILE": str(sentinel_file)}
    cmd = _probe_cmd(
        out_dir, "--tracing", "retain-on-failure", "--screenshot", "only-on-failure", sentinel_plugin=True
    )
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=_REPO_ROOT, timeout=60)

    assert result.returncode == 4
    assert "capture is disabled for credential pages" in (result.stdout + result.stderr)
    assert not sentinel_file.exists(), "no fixture or browser should have started"

    out_files = [p for p in out_dir.rglob("*") if p.is_file()] if out_dir.exists() else []
    capture_files = [p for p in out_files if p.suffix in _CAPTURE_EXTENSIONS]
    assert capture_files == []

    after = _labelled_resource_ids()
    assert after == before, "a rejected selection must create no Docker resource"
