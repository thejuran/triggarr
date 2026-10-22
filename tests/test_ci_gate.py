"""Executes the real ci-ready heredoc from ci.yml with synthetic needs results (D-05).

Extracts the Python script between the ci-ready job's "python3 - <<'PY'" line
and its closing "PY" line, then runs it with ``sys.executable`` -- proving the
real gate script rejects a skipped, failed, cancelled or missing mandatory
job, not a reimplementation of its logic.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

ALL_JOBS = ("test", "lint", "docker", "secrets", "dependencies", "image-smoke", "browser-e2e")


def _extract_ci_ready_script() -> str:
    """Pull the inline Python script out of ci.yml's ci-ready job heredoc.

    ci-ready is not the only job with a "python3 - <<'PY'" heredoc (browser-e2e
    has one too), so the search must start from the ci-ready job marker, never
    from the first heredoc found anywhere in the file.
    """
    lines = CI_WORKFLOW.read_text().splitlines()
    job_idx = next(i for i, line in enumerate(lines) if line == "  ci-ready:")
    start_idx = next(
        i for i in range(job_idx, len(lines)) if lines[i].strip() == "python3 - <<'PY'"
    )
    indent = lines[start_idx][: len(lines[start_idx]) - len(lines[start_idx].lstrip())]
    end_idx = next(i for i in range(start_idx + 1, len(lines)) if lines[i].strip() == "PY")
    body_lines = lines[start_idx + 1 : end_idx]
    dedented = [line[len(indent) :] if line.startswith(indent) else line for line in body_lines]
    return "\n".join(dedented) + "\n"


def _run(results: dict) -> subprocess.CompletedProcess:
    script = _extract_ci_ready_script()
    env = dict(os.environ)
    env["RESULTS"] = json.dumps(results)
    return subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )


def _success_results() -> dict:
    return {name: {"result": "success"} for name in ALL_JOBS}


def test_all_mandatory_jobs_succeed_passes() -> None:
    result = _run(_success_results())
    assert result.returncode == 0, result.stderr


def test_image_smoke_skipped_fails() -> None:
    results = _success_results()
    results["image-smoke"] = {"result": "skipped"}
    result = _run(results)
    assert result.returncode != 0
    assert "did not succeed" in (result.stdout + result.stderr)


def test_browser_e2e_failure_fails() -> None:
    results = _success_results()
    results["browser-e2e"] = {"result": "failure"}
    result = _run(results)
    assert result.returncode != 0
    assert "did not succeed" in (result.stdout + result.stderr)


def test_browser_e2e_cancelled_fails() -> None:
    results = _success_results()
    results["browser-e2e"] = {"result": "cancelled"}
    result = _run(results)
    assert result.returncode != 0
    assert "did not succeed" in (result.stdout + result.stderr)


def test_browser_e2e_key_absent_fails() -> None:
    results = _success_results()
    del results["browser-e2e"]
    result = _run(results)
    assert result.returncode != 0
    assert "Missing or unexpected" in (result.stdout + result.stderr)


def test_extra_unknown_key_present_fails() -> None:
    results = _success_results()
    results["extra"] = {"result": "success"}
    result = _run(results)
    assert result.returncode != 0
    assert "Missing or unexpected" in (result.stdout + result.stderr)
