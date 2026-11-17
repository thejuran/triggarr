---
phase: 88-bounded-upgrade-backups-telemetry-regression
plan: 02
subsystem: web
tags: [fastapi, testclient, opentelemetry, regression, docs]

# Dependency graph
requires: []
provides:
  - "tests/test_telemetry.py regression test pinning startup + /health 200 with FASTAPI_OTEL_AUTO_CONFIGURE and an OTLP endpoint set, driven through FastAPI's real ASGI lifespan dispatch"
  - "README.md statement that Triggarr does not support OpenTelemetry export"
affects: [92-built-image-recovery-demonstration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Real ASGI lifespan dispatch via `with TestClient(app) as client:` for any regression test whose subject is behavior FastAPI itself wires into FastAPI.__call__ (not `async with lifespan_fn(app):`, which never reaches it)"

key-files:
  created:
    - tests/test_telemetry.py
  modified:
    - README.md

key-decisions:
  - "No code change to triggarr/ and no new dependency (D-01) -- the original crash (SA-12) was already fixed upstream in FastAPI 0.143.0+ (installed 0.162.4); this plan adds only a regression guard and one README sentence"
  - "The committed test asserts only the outcome (status 200, {\"status\": \"ok\"}), never FastAPI's internal warning wording or private module names (D-12, Pitfall 11)"

patterns-established:
  - "Pattern 2 (TELEM-01): real-ASGI-dispatch regression test for FastAPI-internal behavior -- now the reference implementation for any future test whose subject lives inside FastAPI.__call__ rather than Triggarr's own lifespan"

requirements-completed: [TELEM-01, TELEM-02]

# Metrics
duration: 9min
completed: 2026-11-17
---

# Phase 88 Plan 02: Telemetry Regression Test & Documentation Summary

**A permanent test now pins that Triggarr's real startup survives `FASTAPI_OTEL_AUTO_CONFIGURE` and an OTLP endpoint via FastAPI's actual ASGI lifespan dispatch, and the README states that telemetry export itself is unsupported.**

## Performance

- **Duration:** 9 min
- **Completed:** 2026-11-17
- **Tasks:** 2 completed
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- `tests/test_telemetry.py` (new): `test_telemetry_env_vars_do_not_crash_startup` sets `FASTAPI_OTEL_AUTO_CONFIGURE=true` and `OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318` via `monkeypatch.setenv` before `FastAPI(lifespan=create_lifespan(...))` is constructed, wires in `router`, drives the app through `with TestClient(app) as client:` (the real ASGI `"lifespan"` scope dispatch, not the `async with lifespan_fn(app):` form used elsewhere in the suite for Triggarr's own lifespan), and asserts `GET /health` returns `200 {"status": "ok"}`.
- README.md Configuration Reference: one new sentence, directly after the existing "Startup-level environment variables..." paragraph and before "## Screenshots," with no new heading: "Triggarr does not support OpenTelemetry export. Setting `FASTAPI_OTEL_AUTO_CONFIGURE` or an OTLP endpoint such as `OTEL_EXPORTER_OTLP_ENDPOINT` does not stop Triggarr from starting, but nothing is exported."
- No code change to `triggarr/`; no new dependency.

## Task Commits

1. **Task 1: Telemetry-variable startup regression test with a recorded negative control**
   - `30008f89` test(88-02): pin startup with OpenTelemetry auto-configure variables set
2. **Task 2: README states telemetry export is unsupported**
   - `68aec226` docs(88-02): state that telemetry export is unsupported

**Plan metadata:** this commit, docs(88-02): complete plan.

## Files Created/Modified

- `tests/test_telemetry.py` -- new file, one test.
- `README.md` -- one sentence inserted in the Configuration Reference section.

## Honest TDD Note (D-12 / plan objective)

This plan's RED step cannot fail against the current code: the crash this test pins against was already fixed upstream in FastAPI 0.143.0+ (installed 0.162.4, which catches its own auto-configure failure internally and logs a warning instead of raising). Running `uv run pytest tests/test_telemetry.py -x -q` against the already-correct code passed immediately (`1 passed`) -- there is no fabricated failing commit.

## Negative Control (UNCOMMITTED, recorded per plan instructions)

To prove the test actually reaches FastAPI's real lifespan telemetry step (and isn't a test that would pass unconditionally, per research Pitfall 2), a temporary negative control was added to the test body, run, and then fully removed before committing.

**Control shape:** `import fastapi.telemetry._runtime as _telemetry_runtime`, capture its `lifespan` attribute, `monkeypatch.setattr` it with an async wrapper that raises `RuntimeError("simulated pre-fix telemetry crash")` when `config["auto_configure"]` is true, otherwise delegates to the original.

| Run | Env var state | Command | Observed result |
|-----|----------------|---------|------------------|
| 1 | `FASTAPI_OTEL_AUTO_CONFIGURE=true` (control active) | `uv run pytest tests/test_telemetry.py -x -q` | **FAILED** -- `RuntimeError: simulated pre-fix telemetry crash`, raised from inside `fastapi/applications.py:1181` (`FastAPI.__call__`) through the monkeypatched `fastapi.telemetry._runtime.lifespan`. Confirms the test reaches the real FastAPI-internal code path. |
| 2 | `FASTAPI_OTEL_AUTO_CONFIGURE` removed via `monkeypatch.delenv(..., raising=False)` (control still active, set before `FastAPI(lifespan=...)` is constructed) | `uv run pytest tests/test_telemetry.py -x -q` | **PASSED** -- `1 passed`. Confirms `auto_configure` is read from the environment at `FastAPI()` construction time and that the env var is what actually drives the simulated-crash path. |

All control edits were removed after Run 2; `git diff` against the committed file showed no residual control code (verified below), and the test was rerun green before committing.

## Post-Control Verification

- `uv run pytest tests/test_telemetry.py -x -q` -> `1 passed` (clean file, no control code).
- `uv run ruff check tests/test_telemetry.py` -> `All checks passed!`
- `grep -c "with TestClient(app) as client" tests/test_telemetry.py` -> `1`
- `grep -n "monkeypatch.setenv(\"FASTAPI_OTEL_AUTO_CONFIGURE\", \"true\")"` at line 25, `FastAPI(lifespan=` at line 30 (setenv precedes construction).
- `grep -c "_runtime\|telemetry configuration failed\|os.environ\|async with lifespan_fn\|delenv" tests/test_telemetry.py` -> `0` (no negative-control code committed).
- `git diff --quiet main -- pyproject.toml uv.lock` -> exit 0 (no dependency added).
- `git log --name-only --format= --grep "(88-02)"` touches only `tests/test_telemetry.py` and `README.md` (plus this SUMMARY and the plan-completion commit) -- no overlap with 88-01's `triggarr/db.py`/`tests/test_db.py`.
- README placement: `awk` anchor check (Startup-level env vars paragraph -> OpenTelemetry sentence -> `## Screenshots`) passes; `git diff main -- README.md | grep -c "^+#"` -> `0` (no new heading).
- Full suite: `uv run pytest tests/ -x -q` -> `3346 passed, 1 skipped` in 87.23s.
- `uv run ruff check triggarr/ tests/` -> `All checks passed!`

## Deviations from Plan

None - plan executed exactly as written. One docstring wording adjustment was needed mid-task: the first draft of the module docstring's explanatory prose happened to contain the literal substring `with TestClient(app) as client` a second time (inside a sentence explaining the pattern), which made the acceptance check `grep -c "with TestClient(app) as client" tests/test_telemetry.py` print 2 instead of the required 1. Reworded the docstring sentence to describe the same mechanism without repeating that exact phrase; re-verified the grep prints 1 and pytest/ruff still pass. This is editorial (docstring wording to satisfy a grep-based acceptance check), not a behavior or scope change, so it is not logged as a Rule 1-4 deviation.

## Assumption Drift (advisory)

None observed. The plan's `<action>` text and 88-RESEARCH.md's Pattern 2/experiment matched the installed FastAPI 0.162.4 source exactly (confirmed by reading `fastapi/applications.py` and `fastapi/telemetry/_runtime.py` directly before writing the test and the negative control).

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TELEM-01 and TELEM-02 are both complete; Phase 88 (BKUP-01/02 from plan 88-01, TELEM-01/02 from this plan) has all four requirements proven by test or documentation.
- Phase 92's built-image smoke test can, if wanted, additionally exercise these telemetry variables against the real built image (deferred, not committed scope per 88-CONTEXT.md).
- `.planning/config.json` carries an unrelated, uncommitted orchestrator `model_overrides` edit from outside this plan's scope; left untouched per this plan's execution instructions.

---
*Phase: 88-bounded-upgrade-backups-telemetry-regression*
*Completed: 2026-11-17*

## Self-Check: PASSED

- FOUND: tests/test_telemetry.py
- FOUND: README.md
- FOUND: .planning/phases/88-bounded-upgrade-backups-telemetry-regression/88-02-SUMMARY.md
- FOUND commit: 30008f89
- FOUND commit: 68aec226
