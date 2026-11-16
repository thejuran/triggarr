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
| **Quick run command** | `uv run pytest tests/test_db.py -x -q` (BKUP) / `uv run pytest <telemetry test file> -x -q` (TELEM) |
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
| TBD (planner fills) | — | — | BKUP-01 | T-88 (wrong-file delete) | At most canonical + 3 timestamped backups for `current` after 5+ failed attempts | unit | `uv run pytest tests/test_db.py -k backup -x -q` | ❌ W0 | ⬜ pending |
| TBD (planner fills) | — | — | BKUP-02 | T-88 (wrong-file delete) | Canonical and just-written never deleted; filename-stamp order; unlink `OSError` logged, startup continues; strict regex gate | unit | `uv run pytest tests/test_db.py -k backup -x -q` | ❌ W0 | ⬜ pending |
| TBD (planner fills) | — | — | TELEM-01 | — | Startup + `/health` 200 with `FASTAPI_OTEL_AUTO_CONFIGURE` and OTLP endpoint set; must use `with TestClient(app)` (real ASGI lifespan), env set before `FastAPI(...)` | integration | `uv run pytest <telemetry test> -x -q` | ❌ W0 | ⬜ pending |
| TBD (planner fills) | — | — | TELEM-02 | — | README states telemetry export unsupported, nothing exported | source assertion | `grep -n -i "telemetry" README.md` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_db.py` — new tests for BKUP-01/BKUP-02 (reuse `_init_test_db`, `tests/migration_faults.py`)
- [ ] Telemetry regression test (new `tests/test_telemetry.py` or section in an existing file) for TELEM-01

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
