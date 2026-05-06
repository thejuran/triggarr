"""Repository hygiene checks for generated agent/runtime artifacts."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

GENERATED_RUNTIME_PATTERNS = (
    ".gsd/exec/",
    ".gsd/runtime/",
    ".gsd/worktrees/",
    ".gsd/audit/",
    ".gsd/journal/",
    ".gsd/turingmind-review/",
    ".gsd/graphs/",
    ".gsd/safety/",
    ".gsd/browser-state/",
    ".gsd/browser-baselines/",
    ".claude/worktrees/",
)

GENERATED_RUNTIME_FILES = {
    ".gsd/notifications.jsonl",
    ".gsd/last-snapshot.md",
    ".gsd/STATE.md",
    ".gsd/auto.lock",
    ".gsd/doctor-history.jsonl",
    ".gsd/event-log.jsonl",
    ".gsd/metrics.json",
    ".gsd/state-manifest.json",
}


def test_gitignore_excludes_agent_runtime_artifacts() -> None:
    """Generated GSD and agent worktree artifacts should not be re-added accidentally."""
    paths = [
        ".gsd/exec/example.stdout",
        ".gsd/runtime/state.json",
        ".gsd/worktrees/M001/file.py",
        ".gsd/audit/report.json",
        ".gsd/journal/2026-05-06.jsonl",
        ".gsd/turingmind-review/context.json",
        ".gsd/notifications.jsonl",
        ".gsd/graphs/graph.json",
        ".gsd/safety/evidence.json",
        ".gsd/last-snapshot.md",
        ".gsd/STATE.md",
        ".gsd/auto.lock",
        ".gsd/doctor-history.jsonl",
        ".gsd/event-log.jsonl",
        ".gsd/metrics.json",
        ".gsd/state-manifest.json",
        ".gsd/browser-state/default.json",
        ".gsd/browser-baselines/home.png",
        ".gsd/gsd.db",
        ".gsd/gsd.db-wal",
        ".claude/worktrees/agent-example/file.py",
    ]
    result = subprocess.run(
        ["git", "check-ignore", *paths],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert set(result.stdout.splitlines()) == set(paths)


def test_generated_runtime_artifacts_are_not_tracked() -> None:
    """Ignored generated artifacts must not be committed after ignore rules are added."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    tracked_paths = set(result.stdout.splitlines())
    offenders = sorted(
        path
        for path in tracked_paths
        if path in GENERATED_RUNTIME_FILES
        or path.startswith(GENERATED_RUNTIME_PATTERNS)
        or path.startswith(".gsd/gsd.db")
    )
    assert offenders == []


def test_dockerignore_excludes_agent_runtime_artifacts() -> None:
    """Docker build contexts should omit local GSD state and agent worktrees."""
    dockerignore = {
        line.strip()
        for line in (REPO_ROOT / ".dockerignore").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }

    assert ".gsd/" in dockerignore
    assert ".claude/worktrees/" in dockerignore
