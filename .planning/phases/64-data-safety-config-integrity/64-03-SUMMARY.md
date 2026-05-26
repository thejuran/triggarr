---
phase: 64-data-safety-config-integrity
plan: 03
subsystem: config-integrity / concurrency
tags:
  - python
  - async
  - concurrency
  - fastapi
  - testing
  - ast-audit
requirements_closed:
  - SAFETY-05
  - TEST-03
dependency_graph:
  requires:
    - "triggarr.web.routes._atomic_toml_write (existing — call sites unchanged)"
    - "triggarr.search.scheduler app.state.search_lock = asyncio.Lock() (existing line)"
  provides:
    - "tests/audit_lock_coverage.py audit_lock_coverage() — runnable script + importable function"
    - "tests/test_audit_lock_coverage.py::test_all_config_writes_locked — pytest gate on lock coverage"
    - "tests/test_web.py::test_concurrent_settings_save_serialized — dynamic proof of asyncio.Lock serialization"
    - "triggarr/search/scheduler.py inline comment block warning against multi-worker uvicorn"
  affects:
    - "Future PRs adding config-mutating routes — AST audit auto-detects bypass"
    - "Future uvicorn config changes — comment block warns against --workers >1"
tech_stack:
  added: []
  patterns:
    - "httpx.AsyncClient + ASGITransport + asyncio.gather for concurrent ASGI tests"
    - "ast.parse + parent-link map for lexical-dominance static analysis"
key_files:
  created:
    - "tests/audit_lock_coverage.py"
    - "tests/test_audit_lock_coverage.py"
  modified:
    - "tests/test_web.py"
    - "triggarr/search/scheduler.py"
decisions:
  - "Use AST parent-walk over line-distance grep (Codex F3): a grep with a fixed line window is both over- and under-inclusive (silently passes early-return out of lock blocks; mis-counts when the lock acquisition does N lines of unrelated work)."
  - "Skip ImportFrom occurrences explicitly: the `from triggarr.config import _atomic_toml_write` line at routes.py:42 produces an ast.alias node whose `.name` matches but is not a runtime call site; otherwise the audit would falsely report 8 references with line 42 uncovered."
  - "Retain the cheap `grep -c 'async with request.app.state.search_lock' == 8` redundancy gate alongside the AST audit, per User Decisions in 64-REVIEWS.md."
  - "Use time.sleep (not asyncio.sleep) in the slow_atomic_write spy: _atomic_toml_write is dispatched via run_in_executor on a thread pool; blocking the thread (not the event loop) is what produces realistic lock contention."
  - "Place the comment block above the lock definition rather than embedding a runtime check, because there is no portable cheap way to detect uvicorn worker count from inside the ASGI app, and a runtime check would either lie or duplicate state."
metrics:
  duration_seconds: 360
  tasks_completed: 3
  files_changed: 4
  tests_added: 2
  commits: 3
---

# Phase 64 Plan 03: Concurrent Settings Lock — TEST-03 + SAFETY-05 Static Audit Summary

Prove that `app.state.search_lock` (`asyncio.Lock()` defined at `triggarr/search/scheduler.py:210`) genuinely serializes concurrent `POST /settings` requests, AND prove statically that no future contributor can silently drop the lock by adding a new config-mutating route that bypasses it. Three things shipped: (1) dynamic concurrency test, (2) AST audit script + pytest wrapper that asserts every `_atomic_toml_write` reference in `triggarr/web/routes.py` is lexically dominated by `async with ... search_lock:`, (3) a documentation comment above the lock definition warning against multi-worker uvicorn.

## What Was Built

### 1. AST audit script — `tests/audit_lock_coverage.py` (175 lines)

A static check that parses `triggarr/web/routes.py` with `ast.parse`, builds a parent-link map via a single-pass walker over `ast.iter_child_nodes`, and for every reference to `_atomic_toml_write` (as `ast.Name` OR `ast.Attribute`, in any position — call-target, argument to `run_in_executor`, etc.) walks the lexical ancestor chain looking for an `ast.AsyncWith` whose `.items[*].context_expr` resolves to `request.app.state.search_lock` OR `app.state.search_lock`.

Public surface:
- `audit_lock_coverage(routes_path) -> (covered, uncovered_count, uncovered_linenos)` — importable
- `main()` — CLI entry that prints `covered: N / M, uncovered: ...` to stdout (stderr on failure) and returns exit code 0/1
- Runnable directly: `uv run python tests/audit_lock_coverage.py` exits 0 with `covered: 7 / 7, uncovered: 0`

Notable: the walker skips ast.Name occurrences that descend from an `ast.ImportFrom` (the `from triggarr.config import _atomic_toml_write, load_settings` line at routes.py:42 is not a runtime call site). Without this filter the audit would falsely report 8 references with line 42 marked uncovered.

### 2. Pytest wrapper — `tests/test_audit_lock_coverage.py` (30 lines)

In-process pytest gate. Imports `audit_lock_coverage` from `tests.audit_lock_coverage` and calls it directly (no subprocess) so pytest captures assertion details cleanly:

```python
tests/test_audit_lock_coverage.py::test_all_config_writes_locked PASSED [100%]
```

Asserts `uncovered_count == 0` AND `covered >= 7` (structural sanity floor — if a future PR legitimately removes a config-mutating route, the floor must be updated, which is the desired forcing function).

### 3. Concurrent settings save test — `tests/test_web.py::test_concurrent_settings_save_serialized` (≈75 new lines + 2 new imports)

Async test (pytest-asyncio asyncio_mode=auto, no decorator). Patches `triggarr.web.routes._atomic_toml_write` with a spy that records `"enter"`, `time.sleep(0.05)` (thread-blocking; correct because the call is dispatched via `run_in_executor` on a thread pool — RESEARCH 64-RESEARCH.md Pitfall 5), then `"exit"`. Fires two concurrent `POST /settings` requests with schema-complete form payloads (differing only in `log_level`) via:

```python
async with httpx.AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
    r1, r2 = await asyncio.gather(
        ac.post("/settings", data=form_a, follow_redirects=False),
        ac.post("/settings", data=form_b, follow_redirects=False),
    )
```

Assertions:
- Both responses are 303 (POST /settings redirects on success)
- `call_order == ["enter", "exit", "enter", "exit"]` — proves the second request **waited** for the first to release the lock

If the lock were missing or no-op, the order would be `["enter", "enter", "exit", "exit"]` (interleaved). Confirmed by the mutation sanity check below.

### 4. Scheduler comment block — `triggarr/search/scheduler.py:210` (10 new comment lines)

```python
# search_lock serializes (a) search cycles in scheduler.make_search_job and
# (b) every config-save call to _atomic_toml_write in triggarr.web.routes.
# SAFETY-05 (Assumption A1): this asyncio.Lock is correct only because
# Triggarr runs a single uvicorn worker (__main__.py constructs uvicorn.Config
# without workers=N). Adding --workers >1 would silently break serialization
# because asyncio.Lock is per-event-loop. If you ever introduce multi-worker
# uvicorn, replace this with a file-level lock (fcntl.flock) or a process-level
# primitive. Verified statically by tests/audit_lock_coverage.py (AST audit of
# routes.py) and dynamically by
# tests/test_web.py::test_concurrent_settings_save_serialized.
app.state.search_lock = asyncio.Lock()
```

All four required markers present: `single uvicorn worker`, `SAFETY-05`, `audit_lock_coverage`, `test_concurrent_settings_save_serialized`. All lines ≤120 chars.

## Verification Results

| Gate | Command | Result |
|------|---------|--------|
| AST audit (CLI) | `uv run python tests/audit_lock_coverage.py` | exit 0, stdout `covered: 7 / 7, uncovered: 0` |
| AST audit (pytest) | `uv run pytest tests/test_audit_lock_coverage.py -x` | PASSED, 0.02s |
| Dynamic concurrency | `uv run pytest tests/test_web.py::test_concurrent_settings_save_serialized -x` | PASSED, 0.12s call |
| Existing concurrent test | `uv run pytest tests/test_web.py::test_search_now_rate_limit_concurrent_protection -x` | PASSED (no regression) |
| Full web suite | `uv run pytest tests/test_web.py -x -q` | PASSED |
| Full pytest suite | `uv run pytest tests/ -x -q` | **881 passed, 27 warnings, 19.10s** |
| Ruff | `uv run ruff check triggarr/ tests/` | All checks passed |
| Grep redundancy | `grep -c "async with request.app.state.search_lock" triggarr/web/routes.py` | 8 |
| Audit script not pytest-collected | `uv run pytest tests/audit_lock_coverage.py --collect-only -q` | no tests collected |
| Audit script collection floor | `uv run pytest tests/test_audit_lock_coverage.py --collect-only -q` | exactly 1 test collected |
| Idempotency | Re-run concurrency test twice | both PASSED, no leaked async resources |

## Mutation Sanity Check (executed and reverted; NOT committed)

The plan mandates a mutation sanity check to prove the gates actually fail when the lock is removed. Procedure:

1. Temporarily added `import contextlib` to `triggarr/web/routes.py`.
2. Temporarily replaced `async with request.app.state.search_lock:` at `routes.py:573` with `async with contextlib.nullcontext():`.
3. Re-ran both gates:
   - `uv run python tests/audit_lock_coverage.py` → exit 1, stderr `covered: 6 / 7, uncovered: [576]`
   - `uv run pytest tests/test_audit_lock_coverage.py -x` → FAILED with `AssertionError: SAFETY-05 violation: 1 _atomic_toml_write reference(s) in triggarr/web/routes.py are not lexically dominated by 'async with request.app.state.search_lock:'. Uncovered linenos: [576].`
   - `uv run pytest tests/test_web.py::test_concurrent_settings_save_serialized -x` → FAILED with `AssertionError: Lock did not serialize writes; call_order=['enter', 'enter', 'exit', 'exit']. If [enter, enter, exit, exit], the asyncio.Lock is missing or no-op.`
   - `grep -c "async with request.app.state.search_lock" triggarr/web/routes.py` → **7** (was 8)
4. Reverted both edits (lock restored, contextlib import removed).
5. Verified clean revert: `git diff triggarr/web/routes.py` empty; grep count back to **8**; AST audit `covered: 7 / 7, uncovered: 0`; dynamic test PASSED; pytest wrapper PASSED.

Both gates (static AST audit + dynamic concurrency test) fail clearly and independently when the lock is removed. The mutation was NOT committed.

## Deviations from Plan

None — plan executed exactly as written.

One micro-fixup during Task 1 execution: when adding the new test at the end of `tests/test_web.py`, the initial `Edit` old_string did not capture the third assertion of the prior `test_changelog_link_in_nav` (`assert "changelog-modal" in response.text`), which left it as an orphan after my new test. Detected immediately by the first test run (`NameError: name 'response' is not defined` at line 2020) and fixed with two follow-up Edits (re-add the assertion to `test_changelog_link_in_nav`, delete the orphan). No semantic change; the original file content was restored and the new test appended cleanly. Not a deviation from the plan; a transient editor mistake corrected before commit.

Three ruff SIM103 violations on `audit_lock_coverage.py` (inline-condition style) were fixed before commit by collapsing `if ... return True / return False` patterns into single-line `return isinstance(...)` expressions.

## Threat Flags

None — no new security-relevant surface introduced. The new test uses fake form data (no real API keys; `api_key=""`). The audit script reads `triggarr/web/routes.py` only.

## Known Stubs

None.

## Commits

| # | Hash | Type | Message |
|---|------|------|---------|
| 1 | 238da29 | test | `test(64-03): add AST audit + concurrent settings test for SAFETY-05 / TEST-03` |
| 2 | 4a67288 | docs | `docs(64-03): warn against multi-worker uvicorn at search_lock definition` |

## Self-Check: PASSED

- tests/audit_lock_coverage.py — FOUND
- tests/test_audit_lock_coverage.py — FOUND
- tests/test_web.py::test_concurrent_settings_save_serialized — FOUND (grep returns 1 hit)
- triggarr/search/scheduler.py comment block — FOUND (all 4 markers present)
- Commit 238da29 — FOUND in git log
- Commit 4a67288 — FOUND in git log
- Grep redundancy gate `grep -c 'async with request.app.state.search_lock' triggarr/web/routes.py == 8` — PASSING
- Full pytest suite — 881 passed
- Ruff — clean
