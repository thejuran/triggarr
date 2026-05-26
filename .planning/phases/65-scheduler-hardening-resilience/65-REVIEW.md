---
phase: 65-scheduler-hardening-resilience
reviewed: 2026-05-25T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - triggarr/search/scheduler.py
  - triggarr/models/config.py
  - triggarr/config.py
  - triggarr/web/routes.py
  - triggarr/templates/settings.html
  - tests/test_scheduler.py
  - tests/test_config.py
  - tests/test_config_dir.py
  - tests/test_clients.py
findings:
  critical: 1
  warning: 9
  info: 5
  total: 15
status: issues_found
---

# Phase 65: Code Review Report

**Reviewed:** 2026-05-25
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 65 layers three hardening changes onto the existing scheduler: SAFETY-02 (narrow-tuple cycle catch + EVENT_JOB_ERROR listener), SAFETY-03 (per-job consecutive-failure counter + split persistence branch + `persistence_degraded` flag), and RES-01 (configurable shutdown drain + holder identity logging). The implementation matches the plans, has reasonably good test coverage, and the failure-counter tests exercise the real engine outage path via `httpx.MockTransport` (not mock-only shortcuts).

Notable concerns surfaced during review:

- **One Critical**: `tracking_exc` (httpx.HTTPError, etc.) is logged with raw `str(exc)` rather than `_sanitize_exc(exc)`, in direct violation of the secret-discipline pattern that the same module applies to `_on_job_error`. This is a real secret-disclosure regression because the cycle-error path the same file (line 152-154) and the EVENT_JOB_ERROR listener (lines 307-318) both sanitize, but the tracking branch added in this phase does not — the file is internally inconsistent on a security-sensitive convention.
- **Multiple Warnings**: shutdown-sequence robustness gaps (no-cancel between `shutdown(wait=False)` and `db.close()`), `secrets` stdlib module shadowed by a local variable, `wait_for(acquire(), ...)` cancel-without-release lock leak, `_evaluate_cycle_outcome` treats `connected=None` as success (which masks a legitimate engine-bug signal), `app.state.search_lock_holder` declared with `var: type = value` (which the FastAPI/Starlette `State` object stores as the value but the type annotation is meaningless — operator may misread it), and test-quality issues (use of private `scheduler._dispatch_event`, `time.monotonic() - 100.0` synthesis in test).
- **Info**: dead comment duplication, magic strings in log messages, minor naming.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Tracking exception logged without sanitization — leaks raw exception representation

**File:** `triggarr/search/scheduler.py:212-215`

**Issue:**
The tracking-check exception handler logs the raw exception object:

```python
except (
    httpx.HTTPError,
    pydantic.ValidationError,
    aiosqlite.Error,
    OSError,
) as tracking_exc:
    logger.warning(
        "Tracking: check failed -- {exc}",
        exc=tracking_exc,
    )
```

In the same file, the cycle-error path (line 153) and `_on_job_error` (lines 307-312) both correctly route httpx/pydantic exceptions through `_sanitize_exc(...)` to strip credentials from `request.url`. The justification in the `_on_job_error` docstring is explicit:

> "Sanitization split: httpx/pydantic exceptions route through `_sanitize_exc` (engine.py) to strip `request.url` credentials that may contain `apikey=` query parameters."

The tracking branch was added/touched in this phase (the narrow tuple identical to the outer cycle catch shows up in tests/test_scheduler.py:807-811's comment about "SAFETY-02 narrowed the outer except"), yet it bypasses the same sanitizer. `httpx.HTTPStatusError.__str__` includes the full request URL by default, so any legacy *arr install that uses `?apikey=...` query-string auth (still supported by Radarr/Sonarr/Lidarr) will leak the API key into WARNING-level logs. The loguru redacting sink (per CLAUDE.md) is best-effort and depends on `collect_secrets(...)` enumerating every secret — it is documented as defense-in-depth, not primary defense.

**Fix:**
```python
except (
    httpx.HTTPError,
    pydantic.ValidationError,
    aiosqlite.Error,
    OSError,
) as tracking_exc:
    logger.warning(
        "Tracking: check failed -- {exc}",
        exc=_sanitize_exc(tracking_exc) if isinstance(
            tracking_exc, httpx.HTTPError | pydantic.ValidationError
        ) else str(tracking_exc),
    )
```

(Apply the same split as `_on_job_error` to keep aiosqlite/OSError messages — which do not carry secrets — readable for debugging.) The pre-existing manual-search-now handler at `triggarr/web/routes.py:856-862` has the same defect and should be fixed in the same pass.

## Warnings

### WR-01: `wait_for(acquire(), ...)` cancellation can leave the lock held

**File:** `triggarr/search/scheduler.py:504-509`

**Issue:**
```python
try:
    await asyncio.wait_for(
        app.state.search_lock.acquire(), timeout=_SHUTDOWN_DRAIN_TIMEOUT
    )
    app.state.search_lock.release()
except TimeoutError:
    ...
```

`asyncio.wait_for(lock.acquire(), timeout=...)` has a well-known footgun (documented in the Python stdlib): if the wait_for is *cancelled* (not timed-out), the underlying `acquire()` task may complete after the wait_for has unwound, leaving the lock acquired with no matching release. The shutdown path is also where the event loop is winding down — `Lifespan` cleanup is more likely to be cancelled than ordinary code. While this is shutdown-only and the process is about to die, the lock holder logging downstream relies on the lock being in a coherent state, and if the lifespan is run inside a higher-level context (uvicorn reload, test re-entry) the leaked lock survives.

**Fix:** Use `asyncio.timeout()` context manager (Python 3.11+, allowed per project convention) which is cancellation-safe:
```python
try:
    async with asyncio.timeout(_SHUTDOWN_DRAIN_TIMEOUT):
        await app.state.search_lock.acquire()
    try:
        ...  # nothing to do
    finally:
        app.state.search_lock.release()
except TimeoutError:
    ...
```
or, simpler, use the recommended idiom:
```python
acquired = False
try:
    async with asyncio.timeout(_SHUTDOWN_DRAIN_TIMEOUT):
        await app.state.search_lock.acquire()
        acquired = True
finally:
    if acquired:
        app.state.search_lock.release()
```

### WR-02: `_evaluate_cycle_outcome` treats unknown `connected` as success, masking engine-bug signal

**File:** `triggarr/search/scheduler.py:279-291`

**Issue:**
```python
connected = (
    app.state.triggarr_state.get(app_name, {})
    .get(instance_name, {})
    .get("connected")
)
if connected is False:
    _record_cycle_failure(...)
    return False
# connected is True or unknown — treat as success...
app.state.search_failures[job_id] = 0
return True
```

The "unknown" case here covers two distinct situations: (a) genuine fresh install where the engine has not yet written the flag (legitimate), and (b) engine bug where the cycle returns normally but forgets to set the flag (silent failure mode). Lumping both into "success → reset counter" defeats the entire SAFETY-03 purpose: if an engine bug ever causes cycles to silently no-op while leaving `connected=None`, the counter will sit at 0 forever and no escalation log will ever fire.

The plan acknowledges this in the docstring ("Missing or None `connected` is treated as success (do not double-count first-ever cycle before the engine sets the flag).") but does not distinguish between "first-ever cycle, never run" and "Nth cycle, flag missing — engine bug".

**Fix:** Track a `cycle_count` per instance (or use the existing `last_run` field on state to know "engine has run before"). If the engine has previously written the connected flag and the current cycle did not refresh it, log at WARNING and do **not** reset the counter. Alternatively, the simpler defense: log INFO "{app}/{inst}: connected status unknown after cycle" when `connected is None` so the situation is at least observable.

### WR-03: `scheduler.shutdown(wait=False)` does not cancel in-flight async jobs — drain semantics drift

**File:** `triggarr/search/scheduler.py:478-509`

**Issue:**
The shutdown sequence is:
1. `scheduler.shutdown(wait=False)` — stops scheduling new jobs; for `AsyncIOScheduler`, this does **not** cancel coroutines that are already executing.
2. Drain `search_lock`.
3. Close HTTP clients.
4. Close DB.

If a search-cycle coroutine is currently `await`ing inside `cycle_fn(...)` (e.g., on a 30s httpx request), `scheduler.shutdown(wait=False)` returns immediately while that coroutine is still running. The drain at step 2 then waits up to 60s for the cycle to finish. But during steps 3 and 4, if drain *timed out*, we close the DB while the cycle still has an aiosqlite cursor open and the HTTP clients while httpx may still have a request in flight. The aiosqlite double-use will raise; httpx aclose-while-in-flight has known behavior (test_clients.py:302 onward documents `AssertionError` on httpx==0.28.1).

If drain succeeded, we still don't *cancel* the scheduler's wrapper task — APScheduler will retain the job in its event loop until the loop closes. This is the same gap the cancel-then-close pattern in tests/test_clients.py was added to verify the *client* against, but the lifespan does not actually apply that pattern.

**Fix:**
After drain timeout, explicitly cancel any tasks holding the lock (find them via the scheduler's job store), or extend the drain to *force-cancel and await CancelledError*. At minimum, document the contract: "On drain timeout, the process must be SIGKILL'd by the host" and surface that in the WARNING. Today the WARNING says "forcing close" but the code does not actually force anything — it just continues to db.close() and may crash.

### WR-04: `secrets` stdlib module shadowed by local variable in `save_settings`

**File:** `triggarr/web/routes.py:14` (import) and `triggarr/web/routes.py:584` (rebind)

**Issue:**
```python
import secrets                                # line 14 (module)
...
async def save_settings(request: Request) -> RedirectResponse:
    ...
    secrets = collect_secrets(new_settings)   # line 584 — shadows the module
    setup_logging(new_settings.general.log_level, secrets)
```

The stdlib `secrets` module is used at line 1248 in `login_post` (`secrets.compare_digest`), but that's a separate function so the rebinding is function-local and currently harmless. However, it is a `ruff A001` / readability landmine: any future refactor that moves a `secrets.compare_digest(...)` call into `save_settings` (e.g., during a CSRF check) will fail at runtime with `AttributeError: 'list' object has no attribute 'compare_digest'`.

**Fix:**
```python
new_secrets = collect_secrets(new_settings)   # match the naming used in 4 other endpoints
setup_logging(new_settings.general.log_level, new_secrets)
```
(`_new_secrets` is the convention at lines 1108, 1358, 1392, 1416 — `save_settings` is the lone outlier.)

### WR-05: `app.state.search_lock_holder: tuple[str, float] | None = None` annotation is meaningless on `State`

**File:** `triggarr/search/scheduler.py:424` (also lines 408, 414, 418)

**Issue:**
```python
app.state.search_lock_holder: tuple[str, float] | None = None
```

`fastapi.Request.app.state` is a `starlette.datastructures.State` object — a bare `SimpleNamespace`-like container that stores attributes in `__dict__`. There is no class definition that can attach a `__annotations__` slot for these names. The `: tuple[str, float] | None` annotation here is a *variable annotation statement* that mypy will type-check the assignment against, but at runtime it is discarded and not stored anywhere consultable. A reader may incorrectly conclude the type is enforced (it is not), and a typo here (`tuple[str, int]` etc.) will silently mismatch real assignments elsewhere in the file.

**Fix:** Either:
- Drop the annotations and use plain assignment (`app.state.search_lock_holder = None`) plus a top-of-file docstring or a `TypedDict`-style ref doc, or
- Define a `dataclass`/`TypedDict` for the lifespan state and assign instances of it, so the type is actually enforced.

Lines 408 (`app.state.last_search_time: dict[str, float] = {}`), 414, 418, and 424 all have the same issue.

### WR-06: `_record_cycle_failure` uses `>=` against threshold but the log message format hides the inequality

**File:** `triggarr/search/scheduler.py:241-249`

**Issue:**
```python
log_fn = logger.error if count >= threshold else logger.warning
log_fn(
    "{app}: search cycle failed ({count}/{threshold}) -- {reason}",
    ...
)
```

The `>=` semantics combined with the `(count/threshold)` log format means the operator sees lines like `(3/3)`, `(4/3)`, `(5/3)` — all at ERROR. This is correct behavior per the plan but the `(count/threshold)` notation is ambiguous and the test at `tests/test_scheduler.py:325` only asserts `(3/3)` appears, not what happens at `(4/3)`.

This is a latent observability issue: an SRE searching logs for "3/3" will find the first escalation but not the persistent failure. Consider `({count}/{threshold}, threshold-reached)` or escalating only at the *first* `count==threshold` boundary with later occurrences logged at WARNING with a "still failing" marker.

**Fix:** Either accept this as intentional (and document explicitly) or change the level escalation to `count == threshold` (boundary-only ERROR) plus a subsequent counter-reset on next success.

### WR-07: Race between `app.state.search_lock_holder` set and drain read

**File:** `triggarr/search/scheduler.py:131` and `triggarr/search/scheduler.py:489-498`

**Issue:**
The lifespan shutdown drain reads `app.state.search_lock_holder` BEFORE acquiring the lock for drain (lines 489-498). If a cycle is currently waiting to enter `async with app.state.search_lock:` but has not yet executed line 131 (`app.state.search_lock_holder = (job_id, ...)`), the drain logs "no current holder" — even though a cycle is queued and about to grab the lock. The drain's `wait_for(acquire, ...)` then queues behind the cycle, and the cycle gets the lock first, runs, releases — and only then drain acquires. From the operator's logs, the drain looks like it had no holder when in fact it had to wait for one.

This is benign in normal shutdown but misleading during incident triage. The defensive re-read inside the `except TimeoutError:` branch (line 513) is good but the entry-time read should also re-check post-acquire-attempt.

**Fix:** Move the holder log into the `except TimeoutError:` block only (it is already there) and replace the entry log with a generic "Shutdown: draining search lock (timeout={t}s)" plus a structured log of `_login_failures`-style "the next cycle waiting on the lock". Or accept the cosmetic gap and document.

### WR-08: Test uses private `scheduler._dispatch_event` API

**File:** `tests/test_scheduler.py:132`

**Issue:**
```python
scheduler._dispatch_event(event)
```

`_dispatch_event` is a private APScheduler API (leading underscore). Any APScheduler upgrade can rename or change its signature without warning, silently breaking this test. The test would fail at import / call time but the failure mode (AttributeError, signature mismatch) won't clearly point to "APScheduler upgrade required".

**Fix:** Either call the listener directly (`_on_job_error(event)`) — the test is verifying the *listener's behavior*, not APScheduler's dispatch — or use APScheduler's public `add_job(...)` with a synthetic raising job and let the real dispatcher fire EVENT_JOB_ERROR via `scheduler.start()` + `pause()` machinery.

### WR-09: `_evaluate_cycle_outcome` not called when persistence raises — counter state inconsistent

**File:** `triggarr/search/scheduler.py:152-178`

**Issue:**
The flow is:
1. Run cycle (line 136) — may raise narrow-tuple exception → counter incremented at line 153 → `return`.
2. `_evaluate_cycle_outcome(...)` at line 160 — counter reset if `connected is True`.
3. `save_state` at line 168 — may raise OSError/aiosqlite.Error → `persistence_degraded = True` and **re-raise**.

If step 2 reset the counter to 0 (engine reported success) and step 3 then raised (persistence failure), the re-raised exception propagates to `_on_job_error`, which logs at ERROR. The counter is correctly NOT touched (durability != *arr outage). But the next cycle starts with counter=0. From the operator's view: counter says everything is fine, but they have a persistent persistence outage and `persistence_degraded` is sticky `True` until... never. There is no code path that resets `persistence_degraded = False` after a successful save.

**Fix:** In the persistence-success path (after `await asyncio.get_running_loop().run_in_executor(...)` on line 168-170 does NOT raise), reset the flag:
```python
try:
    await asyncio.get_running_loop().run_in_executor(...)
    app.state.persistence_degraded = False  # clear on successful save
except (OSError, aiosqlite.Error) as persist_exc:
    app.state.persistence_degraded = True
    ...
```

## Info

### IN-01: `_evaluate_cycle_outcome` docstring duplicates inline comment

**File:** `triggarr/search/scheduler.py:277-278`

**Issue:** Lines 277-278 are a comment ("SAFETY-03 (Codex finding 1): cycle outcome derived from state[app][inst][connected], not from raised exceptions.") that restates the function-level docstring (lines 254-260). Pure duplication — remove the inline comment or strip the redundant docstring sentence.

**Fix:** Delete lines 277-278.

### IN-02: Test fixture `_build_outage_app` mutates `settings.general` after construction

**File:** `tests/test_scheduler.py:168-169`

**Issue:**
```python
settings = make_settings()
settings.general.max_consecutive_failures = max_consecutive_failures
```

This works (pydantic `BaseModel` allows attribute assignment unless `model_config` sets `frozen=True`), but it bypasses validation. If a future contributor adds `Field(..., gt=0)` constraints to `GeneralConfig` they will not fire here. Prefer:
```python
settings = make_settings()
settings.general = settings.general.model_copy(
    update={"max_consecutive_failures": max_consecutive_failures}
)
```

### IN-03: Synthetic holder timestamp in test relies on monotonic clock arithmetic

**File:** `tests/test_scheduler.py:682-685`

**Issue:**
```python
app.state.search_lock_holder = (
    "radarr_Default_search",
    time.monotonic() - 100.0,
)
```

`time.monotonic()` returns an arbitrary-origin float. Subtracting 100.0 to fake "started 100s ago" works because the production code only ever takes deltas (`time.monotonic() - started`), but if the production code is ever refactored to use `time.monotonic_ns()` or a different clock the test silently passes with a meaningless elapsed value. Add a comment noting the contract: "Production code must use `time.monotonic()` for `search_lock_holder[1]` — see test_shutdown_timeout_logs_holder_identity".

### IN-04: `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` parsing accepts `inf`/`nan`

**File:** `triggarr/search/scheduler.py:70-75`

**Issue:**
```python
raw = os.environ.get("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT", "60.0")
try:
    value = float(raw)
except (ValueError, TypeError):
    value = 60.0
return max(value, 1.0)
```

`float("inf")` and `float("nan")` are valid and pass through. `inf` becomes the drain timeout (asyncio.wait_for will wait forever — defeats the entire RES-01 plan). `nan` compared with `1.0` via `max()` returns `nan`, which silently breaks downstream `asyncio.wait_for(..., timeout=nan)` with `ValueError`.

**Fix:**
```python
import math
try:
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError("non-finite")
except (ValueError, TypeError):
    value = 60.0
return max(value, 1.0)
```

### IN-05: `app.state.search_failures.get(job_id, 0)` reads after dict mutation — not a bug but inefficient

**File:** `triggarr/search/scheduler.py:238`

**Issue:** Reads `app.state.search_failures.get(job_id, 0)`, then writes `app.state.search_failures[job_id] = count`. Two dict lookups for one logical "increment". Minor; suggest `count = app.state.search_failures[job_id] = app.state.search_failures.get(job_id, 0) + 1`.

---

_Reviewed: 2026-05-25_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
