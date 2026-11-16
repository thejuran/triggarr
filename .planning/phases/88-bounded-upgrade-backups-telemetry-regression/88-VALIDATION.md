---
phase: 88
slug: bounded-upgrade-backups-telemetry-regression
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-11-16
---

# Phase 88 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_db.py -x -q` (BKUP) / `uv run pytest tests/test_telemetry.py -x -q` (TELEM) |
| **Full suite command** | `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run the quick run command for the file just touched
- **After every plan wave:** Run the full suite command
- **Before `/bm:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 88-01-01 | 01 | 1 | BKUP-01 | T-88-01, T-88-02, T-88-03, T-88-04 | Canonical + at most 3 timestamped backups for `current` after 5 failed attempts; 5 fail + 1 success leaves 4 files; filename-stamp order; just-written kept; other versions and non-matching names untouched; one INFO line per deletion | unit (TDD) | `uv run pytest tests/test_db.py -x -q -k "backup or prune"` | ❌ W0 (created in task RED step) | ⬜ pending |
| 88-01-02 | 01 | 1 | BKUP-02 | T-88-05, T-88-06 | `OSError` on listing or unlink logs one WARNING (path + exception type), other deletions continue even when the first deletion fails, no exception escapes, migration still applies | unit (TDD) | `uv run pytest tests/test_db.py -q -k "prune or pruning" && uv run ruff check triggarr/db.py tests/test_db.py` (full suite once at plan completion) | ❌ W0 (created in task RED step) | ⬜ pending |
| 88-02-01 | 02 | 2 | TELEM-01 | T-88-07, T-88-08 | Startup + `/health` 200 with `FASTAPI_OTEL_AUTO_CONFIGURE` and `OTEL_EXPORTER_OTLP_ENDPOINT` set; `with TestClient(app)`; env set before `FastAPI(...)`; uncommitted negative control recorded (regression pin, RED cannot fail) | integration | `uv run pytest tests/test_telemetry.py -x -q` | ❌ W0 (new file) | ⬜ pending |
| 88-02-02 | 02 | 2 | TELEM-02 | T-88-09 | README states telemetry export is unsupported, nothing exported, placed after the startup env-var paragraph | source assertion | `grep -n "does not support OpenTelemetry export" README.md` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_db.py` — new tests for BKUP-01/BKUP-02 (reuse `_init_test_db`, `tests/migration_faults.py`)
- [ ] Telemetry regression test `tests/test_telemetry.py` (new file) for TELEM-01

*No framework install needed — pytest, pytest-asyncio and `fastapi.testclient.TestClient` already present.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| README wording is plain and accurate | TELEM-02 | Documentation tone/clarity | Read the inserted sentence in the PR diff (a grep assertion covers presence) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
