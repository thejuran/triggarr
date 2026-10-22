"""Unit-job proof of the D-33 amendment A capture-policy guard -- no Docker, no browser.

Every case here runs tests/e2e/probes as a standalone subprocess pytest
invocation (python_files/python_functions overridden so probe_*.py files are
collected). TRIGGARR_E2E_IMAGE is set to a dummy, never-used value: each case
either selects only the fixture-free probe (probe_capture_allowed) or is
rejected by the capture-policy guard in tests/e2e/conftest.py's
pytest_collection_finish before any fixture runs -- so no Docker container
and no browser ever starts in any of the five cases.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PROBES_DIR = _REPO_ROOT / "tests" / "e2e" / "probes"

_BASE_CMD = [
    sys.executable,
    "-m",
    "pytest",
    str(_PROBES_DIR),
    "-o",
    "python_files=probe_*.py",
    "-o",
    "python_functions=probe_*",
    "-p",
    "no:cacheprovider",
    "-p",
    "tests.e2e.probes.sentinel_plugin",
]

_REJECTION_MESSAGE = "capture is disabled for credential pages"


def _run(
    tmp_path: Path, extra_args: list[str], *, timeout: float = 30.0
) -> tuple[subprocess.CompletedProcess[str], Path]:
    sentinel_file = tmp_path / "sentinel.txt"
    output_dir = tmp_path / "out"
    env = {
        **os.environ,
        "TRIGGARR_E2E_IMAGE": "guard-test-dummy",
        "E2E_SENTINEL_FILE": str(sentinel_file),
    }
    cmd = [*_BASE_CMD, *extra_args, "--output", str(output_dir)]
    result = subprocess.run(
        cmd, capture_output=True, text=True, env=env, cwd=_REPO_ROOT, timeout=timeout
    )
    return result, sentinel_file


def test_non_credential_selection_with_capture_allowed(tmp_path: Path) -> None:
    """(1) -m 'not credential_pages' with full capture on: allowed; only the non-marked probe runs."""
    result, sentinel_file = _run(
        tmp_path,
        [
            "-m",
            "not credential_pages",
            "--browser",
            "chromium",
            "--tracing",
            "retain-on-failure",
            "--screenshot",
            "only-on-failure",
            "--video",
            "retain-on-failure",
        ],
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert _REJECTION_MESSAGE not in combined
    assert sentinel_file.exists()
    nodeids = [line for line in sentinel_file.read_text().splitlines() if line]
    assert nodeids
    assert all("probe_capture_allowed" in nodeid for nodeid in nodeids)


def test_mixed_selection_with_capture_rejected(tmp_path: Path) -> None:
    """(2) No -m (both probes selected) with full capture on: rejected, no sentinel (no fixture ran)."""
    result, sentinel_file = _run(
        tmp_path,
        [
            "--browser",
            "chromium",
            "--tracing",
            "retain-on-failure",
            "--screenshot",
            "only-on-failure",
            "--video",
            "retain-on-failure",
        ],
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 4
    assert _REJECTION_MESSAGE in combined
    assert not sentinel_file.exists()


def test_credential_only_selection_with_capture_rejected(tmp_path: Path) -> None:
    """(3) -m credential_pages with only --screenshot on: rejected, sentinel absent."""
    result, sentinel_file = _run(
        tmp_path,
        ["-m", "credential_pages", "--browser", "chromium", "--screenshot", "only-on-failure"],
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 4
    assert _REJECTION_MESSAGE in combined
    assert not sentinel_file.exists()


def test_dash_k_selection_with_capture_rejected(tmp_path: Path) -> None:
    """(4) -k selecting the credential probe with --video on: rejected, sentinel absent."""
    result, sentinel_file = _run(
        tmp_path,
        ["-k", "setup_fails_before_registration", "--browser", "chromium", "--video", "retain-on-failure"],
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 4
    assert _REJECTION_MESSAGE in combined
    assert not sentinel_file.exists()


def test_credential_selection_with_capture_off_allowed_collect_only(tmp_path: Path) -> None:
    """(5) -m credential_pages with all capture off, --collect-only: allowed, no test executed."""
    result, sentinel_file = _run(
        tmp_path,
        [
            "-m",
            "credential_pages",
            "--browser",
            "chromium",
            "--tracing",
            "off",
            "--screenshot",
            "off",
            "--video",
            "off",
            "--collect-only",
        ],
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert _REJECTION_MESSAGE not in combined
    del sentinel_file  # --collect-only never runs a test, so no sentinel assertion is meaningful here
