---
phase: 65-scheduler-hardening-resilience
plan: 03
subsystem: scheduler
tags: [scheduler, shutdown, observability, async, docker, res-01]

# Dependency graph
requires:
  - phase: 65-scheduler-hardening-resilience
    plan: 02
    provides: app.state.search_failures + app.state.persistence_degraded inits in create_lifespan (anchor for app.state.search_lock_holder); make_search_job split into cycle/persistence branches (anchor for outer try/finally that clears holder); job_id assignment inside async-with-search-lock (anchor for holder set)
provides:
  - _SHUTDOWN_DRAIN_TIMEOUT module-level constant (env-overridable via TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT, default 60.0, clamped >= 1.0)
  - _read_shutdown_drain_timeout() helper (testable env-var parsing with safe fallback)
  - app.state.search_lock_holder: tuple[str, float] | None init in create_lifespan
  - holder set/clear lifecycle in make_search_job (set inside async-with-lock, cleared in outer finally that runs on ALL exit paths)
  - Shutdown drain rewrite: INFO-on-entry log naming holder + elapsed (Codex finding 3) + configurable timeout + WARNING-on-timeout naming holder
  - docker-compose.yml stop_grace_period: 90s on triggarr service
  - README.md Docker + systemd documentation for stop-timeout requirement
  - 3 new tests (default constant value, env var override + clamp, holder-identity dual log)
affects: [65-04-PLAN.md]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-level constant read at import time, monkeypatch-testable via setattr"
    - "time.monotonic() for elapsed measurement (NTP-correction-safe, per RESEARCH Pitfall 3)"
    - "Defensive getattr(app.state, '<attr>', None) read for state attrs that may be missing if lifespan init failed early"
    - "Outer try/finally inside async-with-lock so holder is cleared on success, narrow-tuple swallow + return, propagated unexpected exc, AND re-raised OSError/aiosqlite.Error"

key-files:
  created: []
  modified:
    - triggarr/search/scheduler.py
    - tests/test_scheduler.py
    - docker-compose.yml
    - README.md

key-decisions:
  - "Codex finding 3 closed via four-part fix: (a) configurable env var; (b) docker-compose stop_grace_period: 90s; (c) README docs for docker run/systemd; (d) INFO-on-entry holder log so SIGKILL race still produces operator-visible context."
  - "Codex finding 5 honoured: import time and import os live HERE in 65-03 (their first use site) — NOT in 65-01 where they would have been F401 unused."
  - "Clamp env-var value to >= 1.0 so misconfig (e.g. TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT=0) cannot disable the shutdown drain."
  - "Malformed env-var value falls back to 60.0 (try/except ValueError/TypeError) rather than crashing module import."
  - "Holder assignment lives INSIDE async-with-search-lock (T-65-08 mitigation): the lock guarantees mutual exclusion so only one writer at a time."
  - "Outer try/finally encloses BOTH the cycle except branch's `return` AND the persistence branch's `raise` — Python semantics: finally runs in both cases, so holder is cleared on all four exit paths (success, narrow-tuple swallow, persistence re-raise, propagated unexpected exception)."
  - "Defensive getattr() in the shutdown drain reads the holder so a lifespan init that fails before the holder attr is set does not crash the shutdown path with AttributeError."

patterns-established:
  - "Configurable timeout via env-var-read-at-import + max(value, FLOOR) clamp pattern (reusable for future RES-* settings)."
  - "Holder-identity observability: tuple[job_id, time.monotonic()] on app.state, written inside the lock, read at observability checkpoints."

requirements-completed: [RES-01]

# Metrics
duration: 8min6s
completed: 2026-05-25
---

# Phase 65 Plan 03: RES-01 Configurable Shutdown Drain + Holder Identity Logging Summary

**Extended the graceful-shutdown lock-drain timeout from a hardcoded 35s to a configurable `_SHUTDOWN_DRAIN_TIMEOUT` module constant (default 60.0s, env-overridable via `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT`, clamped `>= 1.0`); replaced the non-actionable single-line warning with structured INFO-on-entry and WARNING-on-timeout logs that name the stuck cycle (`job_id` + `elapsed`); and aligned Docker/systemd stop-timeouts with `stop_grace_period: 90s` and `TimeoutStopSec=90s` so the in-process drain has time to complete before SIGKILL.**

## Performance

- **Duration:** ~8 min 6 s
- **Started:** 2026-05-26T02:54:56Z
- **Completed:** 2026-05-26T03:03:02Z
- **Tasks:** 3 (RED → GREEN → REFACTOR)
- **Files modified:** 4 (1 source + 1 test + 1 docker + 1 docs)
- **Test delta:** 903 → 906 (+3 new RES-01 tests)

## Accomplishments

- **RES-01 closed:** Shutdown drain timeout is now a module-level `_SHUTDOWN_DRAIN_TIMEOUT` constant. Operators tune via the `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` env var; misconfig values (`<1.0`) are clamped to `1.0` and malformed values fall back to the 60.0 default.
- **Codex finding 3 closed (4 parts):**
  1. `docker-compose.yml` declares `stop_grace_period: 90s` (60s drain + 30s margin for client/db close).
  2. `README.md` documents the requirement for compose users, `docker run` users (`--stop-timeout 90`), and systemd users (`TimeoutStopSec=90s` added to the example unit file).
  3. Drain timeout is env-overridable so deployment operators can tune for CI/test (lower) or slow-network production (higher).
  4. **INFO-on-entry log fires immediately on drain entry** (not just on timeout) so the operator sees the holder identity even when Docker SIGKILLs the process before the drain completes.
- **Codex finding 5 honoured:** `import time` and `import os` live HERE in 65-03 — their first use site. 65-01 deliberately omitted them to avoid F401 unused-import errors.
- **Holder identity tracked on `app.state.search_lock_holder: tuple[str, float] | None`** — set inside `async with app.state.search_lock:` (after `job_id` is assigned) and cleared in an outer `finally` that runs on ALL exit paths: success, narrow-tuple cycle-except `return`, re-raised `OSError`/`aiosqlite.Error` from persistence (Codex finding 2), and propagated unexpected exceptions (SAFETY-02).
- **`time.monotonic()` chosen over `time.time()`** (RESEARCH Pitfall 3) — NTP correction cannot produce negative `elapsed`.
- **No regression:** Full project suite 906 passing (903 pre-plan + 3 new). Plan 65-01 tests (3) + 65-02 tests (6) still pass unchanged. `uv run ruff check triggarr/ tests/` clean.

## Task Commits

Each task was committed atomically as RED → GREEN → REFACTOR:

1. **Task 1 (RED): add failing tests** — `4103168` (test)
2. **Task 2 (GREEN): configurable drain + holder + docker stop_grace_period + README** — `41a9cb6` (feat)
3. **Task 3 (REFACTOR): module docstring inventory of Phase 65 layers** — `1ed2b96` (refactor)

## Files Created/Modified

- `triggarr/search/scheduler.py` (+260 / −79) — `import os` + `import time` added; `_read_shutdown_drain_timeout()` helper + `_SHUTDOWN_DRAIN_TIMEOUT` module constant; `app.state.search_lock_holder` init in `create_lifespan`; holder set/clear lifecycle inside `make_search_job` (outer try/finally wrapping cycle + persistence + tracking branches); rewritten shutdown drain (INFO-on-entry + configurable timeout + WARNING-on-timeout with holder identity); expanded module docstring to inventory SAFETY-02 / SAFETY-03 / RES-01 layers.
- `tests/test_scheduler.py` (+116) — 3 new tests (`test_shutdown_timeout_default_is_60s`, `test_shutdown_timeout_env_var_override`, `test_shutdown_timeout_logs_holder_identity`); new imports `importlib`, `re`, `time`.
- `docker-compose.yml` (+4) — `stop_grace_period: 90s` on the `triggarr` service with inline RES-01 comment.
- `README.md` (+6) — Docker section documents `stop_grace_period: 90s` and explains `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT`; `docker run` alternative `--stop-timeout 90`; systemd unit example adds `TimeoutStopSec=90s`.

## Decisions Made

- **Codex finding 3 — four-part fix.** A higher in-process drain timeout (60s) is necessary but not sufficient: the prior plan draft made the timeout configurable but left the docker-compose `stop_grace_period` at the 10s default. Docker would SIGKILL after 10s and the new WARNING (or INFO) log would never fire. The fix:
  1. **`stop_grace_period: 90s`** in `docker-compose.yml` — 90s = 60s drain + 30s margin for client + db close steps.
  2. **README docs** — `--stop-timeout 90` for `docker run` users, `TimeoutStopSec=90s` for systemd users.
  3. **Env-var configurable drain** (`TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT`) so operators can tune the in-process drain for their environment (lower for CI/test, higher for slow networks).
  4. **INFO-on-entry log** so the holder identity is in container logs even if SIGKILL races the timeout. The WARNING-on-timeout still fires when the drain completes in-process.

- **Codex finding 5 — `import time` belongs HERE, not 65-01.** Plan 65-01 deliberately avoided adding `import time` because RES-01 is the first user (`time.monotonic()` for elapsed measurement). Adding it in 65-01 would have triggered ruff F401 (unused import) and broken that plan's ruff gate. 65-03 adds both `import time` and `import os` (for the env var read) in the canonical sorted-imports block.

- **Module constant clamped to `>= 1.0`** — `max(value, 1.0)`. A misconfiguration setting `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT=0` (or negative) would otherwise disable the drain entirely and silently lose in-flight cycles. Per the threat model (T-65-14, DoS), the clamp is a hard floor.

- **Malformed env-var values fall back to 60.0** — `try/except (ValueError, TypeError)` around `float(raw)`. A typo like `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT="thirty"` falls back to the default rather than crashing module import. The clamp still runs on the fallback (so the floor is enforced even for the default).

- **Holder assignment INSIDE the lock (T-65-08 mitigation).** `app.state.search_lock_holder = (job_id, time.monotonic())` lives inside `async with app.state.search_lock:`. The lock guarantees mutual exclusion, so only one writer at a time — two jobs cannot race to overwrite each other.

- **Outer try/finally encloses cycle + persistence + tracking branches.** Python `try/finally` runs the finally on EVERY exit path, including `return` (cycle except branch) and re-raised exceptions (persistence branch). This ensures `app.state.search_lock_holder = None` even when:
  - the cycle succeeds and persistence + tracking complete normally;
  - the cycle except catches a narrow-tuple exception and returns;
  - persistence raises and re-raises (`OSError`, `aiosqlite.Error`);
  - an unexpected `RuntimeError`/`KeyError` etc. propagates through (SAFETY-02 path).

- **Defensive `getattr(app.state, "search_lock_holder", None)` in the shutdown drain.** If lifespan init crashes before the holder attribute is set (e.g. a DB connection error during the `init_db` call), the shutdown finally would otherwise raise `AttributeError`. `getattr` with a `None` default lets the drain proceed gracefully with the `no current holder` fallback log line.

- **`time.monotonic()` over `time.time()`** (RESEARCH Pitfall 3). NTP correction can move wall-clock time backwards, producing negative `elapsed`. `monotonic()` is guaranteed non-decreasing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Lint] Ruff SIM300 yoda-condition complaint on test C cleanup assertion**

- **Found during:** Task 1 (ruff check after writing the RED tests).
- **Issue:** The cleanup-restoration assertion in `test_shutdown_timeout_env_var_override` was `assert sched._SHUTDOWN_DRAIN_TIMEOUT == original_timeout`. Ruff SIM300 flagged this as a yoda condition because the constant (`sched._SHUTDOWN_DRAIN_TIMEOUT`) is on the left. SIM300 prefers the literal/captured value on the right of `==`.
- **Fix:** Swapped to `assert original_timeout == sched._SHUTDOWN_DRAIN_TIMEOUT`. Other equality assertions in the test against literal floats (`== 60.0`, `== 15.0`, `== 1.0`) are not flagged because they have the literal on the right already.
- **Files modified:** `tests/test_scheduler.py`.
- **Verification:** `uv run ruff check tests/test_scheduler.py` exits 0.
- **Committed in:** `4103168` (Task 1 RED commit).

### Plan-text Imprecision (no behavioral impact)

**Acceptance criterion in Task 2 — `grep -c "logger.info(\"Shutdown: draining" triggarr/search/scheduler.py` ≥ 1.** The literal grep expects the call site `logger.info("Shutdown: draining` to appear on a single line. After applying the loguru-idiomatic multi-line layout (so format string + kwargs each get their own line, keeping each line under the project's 120-char limit), the format-string is on the line AFTER `logger.info(`. The grep literally matches 0 occurrences, but:
- `grep -c "Shutdown: draining" triggarr/search/scheduler.py` returns 2 (both branches present).
- The behavioral test `test_shutdown_timeout_logs_holder_identity` asserts the actual log output contains the INFO-on-entry line with the holder name — that test passes.
- The single-line variant was attempted first but required `# noqa: E501` markers that introduced an annotation pattern absent from the rest of the codebase. The multi-line variant is consistent with all other `logger.info(...)` and `logger.warning(...)` calls in this file (lines 161, 184, 200, 301, 438, 497, 505).

The spirit of the acceptance criterion (the INFO-on-entry log exists, fires, and is verified by a behavioral test) is satisfied.

---

**Total deviations:** 1 auto-fixed (1 lint), 1 plan-text imprecision.
**Impact on plan:** No scope creep. The auto-fix is a one-character swap to satisfy ruff; the plan-text imprecision is documented for future plans (single-line `logger.info("...")` is only feasible when the format string is short; with kwargs and longer messages, multi-line is the project norm).

## Issues Encountered

None beyond the deviations listed above.

## User Setup Required

**Existing Docker deployments** — operators running an older `docker-compose.yml` without `stop_grace_period` will continue to use Docker's 10s default until they pull the updated compose file. To take advantage of the 60s in-process drain, add `stop_grace_period: 90s` to the `triggarr` service in your local `docker-compose.yml` (the upstream example file is updated by this plan).

**Optional tuning** — operators can override the in-process drain via `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` in seconds (clamped `>= 1.0`):

```yaml
environment:
  - TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT=120
```

If you raise this above 60, also raise `stop_grace_period` accordingly so Docker waits long enough.

## Next Phase Readiness

- **65-04 (TEST-04 aclose):** Ready. RES-01 is independent of aclose; no cross-plan blockers.
- **No follow-up deferred items** introduced by this plan. (The SAFETY-03 manual-search-now deferral from 65-02 remains the outstanding follow-up for v2.8 Phase 67.)

## TDD Gate Compliance

Verified gate sequence in git log:
1. RED: `4103168` `test(65-03): add failing tests…` — failing tests committed before implementation (ImportError/AttributeError confirmed).
2. GREEN: `41a9cb6` `feat(65-03): configurable shutdown drain…` — implementation makes the 3 new tests pass; all 5 shutdown tests green; full suite 906; ruff clean.
3. REFACTOR: `1ed2b96` `refactor(65-03): document RES-01 shutdown drain constant…` — module docstring expansion only; no behavioral change.

All three gates present, in order.

## Self-Check: PASSED

- Verified files exist:
  - `triggarr/search/scheduler.py` — FOUND (_SHUTDOWN_DRAIN_TIMEOUT, search_lock_holder init/set/clear, INFO+WARNING shutdown logs)
  - `tests/test_scheduler.py` — FOUND (3 new RES-01 tests)
  - `docker-compose.yml` — FOUND (stop_grace_period: 90s)
  - `README.md` — FOUND (stop_grace_period, --stop-timeout, TimeoutStopSec docs)
- Verified commits exist:
  - `4103168` (Task 1 RED) — FOUND
  - `41a9cb6` (Task 2 GREEN) — FOUND
  - `1ed2b96` (Task 3 REFACTOR) — FOUND
- Verified tests pass: `uv run pytest tests/ -x -q` → 906 passed.
- Verified ruff clean: `uv run ruff check triggarr/ tests/` → All checks passed.

---
*Phase: 65-scheduler-hardening-resilience*
*Completed: 2026-05-25*
