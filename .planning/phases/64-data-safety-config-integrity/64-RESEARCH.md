# Phase 64: Data Safety & Config Integrity - Research

**Researched:** 2026-05-25
**Domain:** Python async / SQLite / TOML / FastAPI safety hardening
**Confidence:** HIGH

## Summary

This is a tightly-scoped hardening pass on three pre-existing code paths: `_atomic_toml_write` (config.py), `insert_search_entry` (db.py), and the startup TOML-load sequence in `ensure_config` / `load_settings` (config.py). The codebase already has solid foundations — atomic write-then-rename with fsync, an `asyncio.Lock` (`app.state.search_lock`) acquired by every config-save route, pre-write Pydantic validation, the trim-on-insert SQL inside `insert_search_entry`, and `tomllib` from the 3.11 stdlib. The work is targeted refinement, not new infrastructure.

The five success criteria translate directly to:
1. **SAFETY-01 trim guarantee** — the existing trim SQL in `db.py:339-350` only prunes resolved rows. Verify it bounds the table when *all* rows are resolved; recommend tightening or simply confirming the existing guarantee is sufficient. Pending rows (`outcome='searched'`) are intentionally exempt and not part of the cap.
2. **SAFETY-04 OSError logging** — add `logger.error(...)` inside the `contextlib.suppress(OSError)` block in `_atomic_toml_write` so a failed cleanup is at least observable; the outer `raise` already propagates `os.replace` failures, but a top-level log there is also worthwhile.
3. **SAFETY-05 config-save lock** — `app.state.search_lock` already serializes every `_atomic_toml_write` call from web routes (verified in routes.py at 8 call sites). The lock is the right primitive; the missing piece is a dedicated *test* that proves two concurrent PUTs cannot interleave (TEST-03).
4. **Corrupted TOML UX** — `ensure_config` currently lets `tomllib.TOMLDecodeError` and `UnicodeDecodeError` propagate uncaught, surfacing as an unhelpful traceback. Wrap both `tomllib.load` call sites in `config.py:144-145` and `config.py:182-184` to log a clear error mentioning the existing `triggarr.toml.bak` backup path (already produced by `detect_and_migrate_v22` for v2.2→v2.3 migrations).
5. **TEST-02 / TEST-03** — new pytest cases. TEST-03 needs `httpx.AsyncClient + ASGITransport` because `TestClient` is synchronous and cannot fire two truly concurrent requests on the same event loop.

**Primary recommendation:** Keep the existing `app.state.search_lock` as the SAFETY-05 lock — do not introduce a separate `config_save_lock`. It is already wired through all 8 config-mutating endpoints and the scheduler. Add an OSError log to `_atomic_toml_write`, wrap startup TOML loads with a friendly error that names the backup path, and add the two missing tests.

## User Constraints (from CONTEXT.md)

No CONTEXT.md exists for phase 64 — this is the initial research pass. Constraints are inherited from `.planning/REQUIREMENTS.md` and project conventions in `./CLAUDE.md`.

### Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SAFETY-01 | Search history trims to `max_history_rows` after each insert | Trim SQL already exists at `db.py:339-350`; verify edge case where ALL rows are resolved still caps |
| SAFETY-04 | `_atomic_toml_write` logs OSError before suppress; re-raises non-`FileNotFoundError` OSError from `os.replace` | Patch `config.py:113-115`; cleanup suppression must filter on `FileNotFoundError`, not bare `OSError` |
| SAFETY-05 | Config-write lock serializes web UI saves | Already implemented via `app.state.search_lock` (routes.py 8 call sites); needs test |
| TEST-02 | Corrupted TOML startup test produces actionable error with backup path | New test in `tests/test_config.py`; wrap `tomllib.load` calls with friendly handler |
| TEST-03 | Two concurrent PUT requests test verifies SAFETY-05 lock | New test in `tests/test_web.py` using `httpx.AsyncClient + ASGITransport + asyncio.gather` |

## Project Constraints (from CLAUDE.md)

Directives from `./CLAUDE.md` and `~/.claude/CLAUDE.md` that bound this work:

- **Loguru only.** No `print()`, no `logging` module. Every new log line uses `loguru.logger.{info,warning,error}` with `{}` placeholders.
- **SecretStr discipline.** API keys are SecretStr; `.get_secret_value()` is called only at HTTP client init. None of the SAFETY-04/05 work touches secrets — keep that boundary.
- **Atomic file writes.** `_atomic_toml_write` is the canonical pattern; do not introduce a second write path. There's a near-duplicate inline tempfile dance in `generate_default_config` (config.py:187-211) — leave it alone unless explicitly in scope.
- **ruff (E, F, I, UP, B, SIM), line length 120.** New code must pass.
- **pytest-asyncio with `asyncio_mode = "auto"`** (pyproject.toml:38). New `async def test_...` functions need no `@pytest.mark.asyncio` decorator.
- **No bare `except:`.** Catch specific exceptions. Existing pattern in routes.py/scheduler.py is `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)`.
- **Never log sensitive data.** OSError messages from `_atomic_toml_write` can mention `path` (the config file path) — fine. They must not include config *contents* (which would contain SecretStr api keys).

## Current State (file:line citations)

### A. Config save path

**`_atomic_toml_write`** at `triggarr/config.py:92-119`

```python
def _atomic_toml_write(path: Path, data: dict) -> None:
    dir_fd = None
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            tomli_w.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)              # <-- atomic rename
        dir_fd = os.open(path.parent, os.O_RDONLY)
        os.fsync(dir_fd)                        # <-- directory fsync
    except Exception:                           # <-- BUG-06 / HARDEN-03 baseline
        with contextlib.suppress(OSError):      # <-- SAFETY-04 target (too broad)
            os.unlink(tmp_path)
        raise                                   # <-- os.replace failure does propagate
    finally:
        if dir_fd is not None:
            os.close(dir_fd)
```

Current state of SAFETY-04:
- `os.replace()` failure IS re-raised via the outer `raise` (line 116) — verified by `tests/test_web.py:772-799` (`test_save_settings_propagates_write_failure`).
- The bare `contextlib.suppress(OSError)` at 114 **does** swallow non-`FileNotFoundError` OSError during temp cleanup with no log line. This is the SAFETY-04 fix target.
- No log emission anywhere in the function. Even on a real OSError from `os.replace()`, the only log is whatever the route handler emits when it catches the exception (typically nothing — routes let the error propagate to FastAPI's 500 handler).

**Web route call sites** — `triggarr/web/routes.py` calls `_atomic_toml_write` in 8 places, all of them wrapped in `async with request.app.state.search_lock`:

| Line | Endpoint | Mutation |
|------|----------|----------|
| 575 | `POST /settings` | Full settings form save |
| 736 | `POST /api/instance/add` | Add new arr instance |
| 775 | `POST /api/instance/remove/{app}/{inst}` | Remove instance |
| 1097 | `POST /setup` | First-run auth setup |
| 1350 | `POST /settings/password` | Password change |
| 1384 | `POST /settings/security` | Security settings (method, secret) |
| 1408 | `POST /settings/api-key/regenerate` | Regen API key |

All call sites use the same pattern (verified routes.py:573-577 as representative):

```python
async with request.app.state.search_lock:
    await asyncio.get_running_loop().run_in_executor(
        None, _atomic_toml_write, config_path, _settings_to_dict(new_settings)
    )
    os.chmod(config_path, 0o600)
    request.app.state.settings = new_settings
```

**`search_lock` definition** — `triggarr/search/scheduler.py:210`:

```python
app.state.search_lock = asyncio.Lock()
```

Acquired by:
- All 8 config-mutating routes (above)
- `make_search_job` at `scheduler.py:80` — wraps the full search cycle including state writes
- Shutdown drain at `scheduler.py:270` — `asyncio.wait_for(...acquire(), timeout=35.0)` (RES-01 will extend this in Phase 65, not here)
- Rate-limit re-check inside `/api/search-now/{app}/{inst}` at `routes.py:829` (verified by `tests/test_web.py:584-598`)

**Verdict:** SAFETY-05 lock infrastructure is already in place. Two simultaneous PUTs to `POST /settings` go through the same `app.state.search_lock`, so the second awaits the first. The remaining work is the TEST-03 proof.

### B. SQLite history insert path

**`insert_search_entry`** at `triggarr/db.py:302-351`. Schema:

```sql
CREATE TABLE search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    app TEXT NOT NULL,
    queue_type TEXT NOT NULL,
    item_name TEXT NOT NULL,
    outcome TEXT DEFAULT 'searched',     -- migrated v1
    detail TEXT DEFAULT NULL,            -- migrated v1
    item_id INTEGER DEFAULT NULL,        -- migrated v2
    season_number INTEGER DEFAULT NULL,  -- migrated v2
    missing_count INTEGER DEFAULT NULL,  -- migrated v2
    resolved_at TEXT DEFAULT NULL,       -- migrated v5
    instance_id TEXT DEFAULT 'Default'   -- migrated v6
);
CREATE INDEX idx_search_history_timestamp ON search_history(timestamp DESC);
CREATE INDEX idx_search_history_instance_id ON search_history(instance_id, timestamp DESC);
```

Insert + trim is already two `await db.execute()` calls + a `await db.commit()` (db.py:332-351):

```python
await db.execute("INSERT INTO search_history ...")
await db.execute("""
    DELETE FROM search_history
    WHERE COALESCE(outcome, 'searched') != 'searched'
      AND id NOT IN (
        SELECT id FROM search_history
        WHERE COALESCE(outcome, 'searched') != 'searched'
        ORDER BY id DESC LIMIT ?
      )
""", (max_rows,))
await db.commit()
```

**Connection management:** A single long-lived `aiosqlite.connect(db_path)` is opened in `scheduler.py:170` during the lifespan, with `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`. It's shared via `app.state.db`. Confirmed by `db.py` docstring: "callers share a single long-lived connection opened during the application lifespan."

**`max_history_rows` wiring:**
- Defined in `triggarr/models/config.py:79`: `max_history_rows: int = 1000`
- Passed at every `insert_search_entry` call in `triggarr/search/engine.py` (6 call sites, lines 407-466 and 619-671) as `max_rows=settings.general.max_history_rows`
- Saved via form at `routes.py:500`: `safe_int(form.get("max_history_rows"), 1000, 0, 100_000)`

**Current trim semantics — important nuance:**

The trim SQL **only deletes rows where `outcome != 'searched'`** (lines 342-348). Pending rows (where outcome is still `'searched'`) are deliberately preserved so the tracking subsystem can resolve them later. This is correct behavior — the SAFETY-01 goal of "never exceeds `max_history_rows`" is technically about *resolved* rows, not the absolute table size. Pending rows are bounded in practice by the search-cycle interval × outstanding-grab window (tracking_window_minutes default 60), so the table cannot grow unboundedly.

Verified by `tests/test_db.py:95-106` (test_insert_prunes_old_entries) and `tests/test_db.py:412-426` (pending rows exempt). The trim is already correct; SAFETY-01 in Phase 64 may only require *documentation* of this guarantee, not new code. **Open question for the planner — see Open Questions.**

### C. TOML load path on startup

**`load_settings`** at `triggarr/config.py:170-184`:

```python
def load_settings(config_path: Path) -> Settings:
    with open(config_path, "rb") as f:
        data = tomllib.load(f)            # <-- raises TOMLDecodeError, UnicodeDecodeError
    return Settings(**data)               # <-- raises pydantic.ValidationError
```

**`detect_and_migrate_v22`** at `triggarr/config.py:144-145` does the same uncaught `tomllib.load`.

**`ensure_config`** at `triggarr/config.py:214-241`:
- If file missing: writes default template, logs warning, `sys.exit(1)` (line 234)
- If present: calls `detect_and_migrate_v22(config_path)` then `load_settings(config_path)`
- **No try/except** wrapping either call. A `tomllib.TOMLDecodeError` or `UnicodeDecodeError` propagates uncaught all the way up through `_run()` in `__main__.py:49`, where `asyncio.run(_run())` re-raises it as an unhandled exception with a Python traceback. The user sees no actionable error.

**Backup file scheme exists** — `triggarr/config.py:151`:

```python
backup_path = config_path.with_suffix(".toml.bak")  # produced by v2.2→v2.3 migration
```

This is `/config/triggarr.toml.bak`. It is only created during a v2.2→v2.3 migration; it does NOT exist for the general first-run user. So the "include backup file path" requirement in success criterion #4 should be conditional — mention the backup path **if it exists**, otherwise direct the user to restore from their own backup.

There's also a v9-migration database backup pattern at `db.py:64`: `db_path.with_suffix(f".v{current}-backup")` — note as precedent.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Atomic config persistence | Service (config.py) | — | `_atomic_toml_write` is the single canonical write path; no second layer should write TOML |
| Concurrency serialization | Application state (app.state.search_lock) | — | One `asyncio.Lock` already serializes both search cycles and config saves |
| Search history retention | Data layer (db.py) | — | Trim SQL is colocated with the insert; no application-level cap enforcement needed |
| Startup config validation | Startup layer (config.py + __main__.py) | — | `ensure_config` is the single entry point that loads and validates TOML before anything else runs |
| Error surfacing to operator | Loguru (logging.py sink) | — | All user-facing errors go through loguru; never stderr/print |

## Standard Stack

This phase introduces **no new dependencies**. All required libraries are already in `pyproject.toml`:

| Library | Version (from pyproject) | Purpose | Already Used? |
|---------|-------------------------|---------|---------------|
| `tomllib` | stdlib (3.11+) | TOML parse on load | Yes — config.py:10 |
| `tomli-w` | (pinned via `pydantic-settings[toml]` plus direct dep) | TOML write | Yes — config.py:13 |
| `aiosqlite` | unpinned | Async SQLite | Yes — db.py |
| `httpx` | unpinned (via `pydantic-settings[toml]` and direct) | HTTP client used by tests with ASGITransport | Yes — tests/test_clients.py |
| `pytest`, `pytest-asyncio` | dev | Test framework with `asyncio_mode=auto` | Yes |
| `loguru` | unpinned | Logging | Yes — everywhere |

No `pip install` lines required. No `npm install`. This phase is pure refactor + tests inside the existing codebase.

## Package Legitimacy Audit

Not applicable — this phase adds zero new packages. All work is inside `triggarr/config.py`, `triggarr/db.py`, `triggarr/web/routes.py`, and `tests/`.

## Recommended Approach (per success criterion)

### Success #1: SAFETY-01 — history table never exceeds `max_history_rows`

**Current state:** Trim SQL exists in `insert_search_entry` (db.py:339-350). It prunes resolved rows beyond `max_rows` immediately after every insert, in the same `await db.commit()` transaction. Confirmed by test at `tests/test_db.py:95-106`.

**Recommendation: confirm and document, no code change required.**

The existing implementation already satisfies the success-criterion phrasing "trimmed immediately after each insert without blocking the search cycle":
- Trim runs in the same `await` chain as the insert, before `commit()` — same transaction, atomic with the insert.
- `aiosqlite` defers actual SQLite work to a worker thread, so the trim does not block the event loop (does not block other async tasks; the search cycle is awaiting this same call).
- The trim is `DELETE ... WHERE ... NOT IN (SELECT ... LIMIT ?)`, which on the `(outcome, id)` access path is cheap. SQLite handles 1000-row LIMIT cleanly with the existing `idx_search_history_timestamp` index ordering by id DESC.

**What remains for this requirement:**
- Add a test that proves the cap holds across a long insert sequence (the existing test inserts 510 with limit 500 — extend to ≥2000 with limit 1000 to verify steady-state). Likely deferrable to existing test coverage.
- Optionally: document in a comment that pending rows are exempt and bounded by the tracking window. This is operator-relevant.

**Rationale for not changing the SQL:**
- Background-trim breaks the "immediately" guarantee.
- Trigger-based trim is invisible behavior and harder to reason about during migration.
- Modulo-counter trim adds state to the connection and amortizes incorrectly under low-rate workloads.
- The existing inline trim is the simplest correct implementation. SQLite's WAL mode + `synchronous=NORMAL` means the cost is bounded.

### Success #2: SAFETY-04 — log OSError before suppress; re-raise non-FileNotFoundError

**Current state:** `_atomic_toml_write` at `config.py:113-115`:

```python
except Exception:
    with contextlib.suppress(OSError):       # too broad
        os.unlink(tmp_path)
    raise
```

**Recommended patch:**

```python
except Exception:
    try:
        os.unlink(tmp_path)
    except FileNotFoundError:
        pass                                  # expected: temp already gone
    except OSError as cleanup_exc:
        logger.error(
            "Failed to clean up temp file {tmp} during config write: {exc}",
            tmp=tmp_path,
            exc=cleanup_exc,
        )
    raise                                     # always propagate original failure
```

Verification:
- Existing test `tests/test_config.py:670-680` (`test_atomic_toml_write_cleans_temp_on_failure`) still passes — TypeError from `tomli_w.dump` triggers the cleanup, no temp remains, exception propagates.
- Existing test `tests/test_web.py:772-799` (`test_save_settings_propagates_write_failure`) still passes — OSError from a mocked `_atomic_toml_write` causes a 500.
- New test required: a permission-error scenario during cleanup (mock `os.unlink` to raise `PermissionError`) — verify the log line is emitted and the original exception still propagates.

**Important:** The success-criterion phrasing says "a `FileNotFoundError` during temp file cleanup continues to be suppressed." The patch above preserves that — `except FileNotFoundError: pass`. Other OSErrors (PermissionError, OSError with ENOSPC, etc.) get logged.

The phrasing also says "A failed `os.replace()` during config save produces a logged OSError." The current code already re-raises an `os.replace` failure via the outer `raise`. To get a *logged* OSError specifically for the replace case, either (a) the route handler that calls `_atomic_toml_write` adds a `try/except OSError` and logs, or (b) `_atomic_toml_write` itself logs before re-raise. Recommend (b) for symmetry and simplicity:

```python
except OSError as exc:
    logger.error("Config write failed: {path} — {exc}", path=path, exc=exc)
    # cleanup branch as above
    raise
except Exception:
    # cleanup-only branch for non-OSError (tomli_w.dump TypeError, etc.)
    try:
        os.unlink(tmp_path)
    except FileNotFoundError:
        pass
    except OSError as cleanup_exc:
        logger.error("...", ...)
    raise
```

The planner can decide on the exact branching structure. The key invariants:
- `FileNotFoundError` from `os.unlink(tmp_path)` cleanup → silently suppressed (criterion #2).
- Any other `OSError` from cleanup → logged then suppressed.
- Any `OSError` from `os.replace()` or fsync → logged then re-raised.
- All other exceptions (TypeError from `tomli_w.dump`, etc.) → cleanup attempted, propagated.

### Success #3: SAFETY-05 — config-save lock serializes concurrent PUTs

**Current state:** `app.state.search_lock = asyncio.Lock()` (scheduler.py:210) is acquired by all 8 config-mutating routes. This already serializes the writes.

**Recommendation: no production code change. Add TEST-03.**

The lock is the right primitive because:
- The app runs as a single uvicorn worker (confirmed: `__main__.py:75-83` constructs `uvicorn.Config(...)` with no `workers=N`; Dockerfile has no `--workers` flag).
- `asyncio.Lock` is correct for single-process async serialization.
- It already coordinates with search cycles in `make_search_job` (scheduler.py:80), so a config save cannot interleave with a search cycle either — that's a bonus property worth preserving.
- File-level `fcntl.flock` is not needed; would only matter for multi-process and adds executor-offload complexity for zero benefit here.

**Caveat to document in code comment:** If `--workers > 1` is ever introduced, this lock will silently degrade. Add a comment near `app.state.search_lock = asyncio.Lock()` saying so. Trigarr's Docker is explicitly single-worker.

### Success #4: Corrupted-TOML startup produces actionable error

**Current state:** `ensure_config` → `detect_and_migrate_v22` / `load_settings` lets `tomllib.TOMLDecodeError` and `UnicodeDecodeError` propagate uncaught, surfacing as a raw Python traceback from `asyncio.run(_run())`.

**Recommendation:** Wrap the load sequence in `ensure_config` with a typed handler that logs a friendly message via loguru and exits cleanly. Mention the `triggarr.toml.bak` path if it exists.

```python
def ensure_config(config_path: Path) -> Settings:
    if not config_path.exists():
        generate_default_config(config_path)
        logger.warning("Default config written to {path} ...", path=config_path)
        sys.exit(1)

    try:
        migrated = detect_and_migrate_v22(config_path)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        _log_corrupt_config_and_exit(config_path, exc)

    if migrated:
        backup_path = config_path.with_suffix(".toml.bak")
        logger.info("v2.2 config backed up to {path}", path=backup_path)

    try:
        return load_settings(config_path)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        _log_corrupt_config_and_exit(config_path, exc)


def _log_corrupt_config_and_exit(config_path: Path, exc: Exception) -> None:
    backup_path = config_path.with_suffix(".toml.bak")
    logger.error(
        "Failed to parse config file {path}: {exc}",
        path=config_path, exc=exc,
    )
    if backup_path.exists():
        logger.error(
            "A backup is available at {backup} — to restore: "
            "cp {backup} {path}",
            backup=backup_path, path=config_path,
        )
    else:
        logger.error(
            "No automatic backup exists. Restore from your own backup or "
            "delete {path} to regenerate the default template.",
            path=config_path,
        )
    sys.exit(1)
```

**Notes:**
- `UnicodeDecodeError` is raised by `tomllib.load` when the file contains invalid UTF-8 bytes (tomllib opens in binary mode and decodes internally).
- `tomllib.TOMLDecodeError` is a subclass of `ValueError` — catch it specifically, not `ValueError`.
- Exit code 1 matches the existing "no config file" exit behavior at config.py:234.
- Do NOT use `print()` or `sys.stderr.write()` — must go through loguru, even before `setup_logging()` is called. Loguru's default handler prints to stderr; that's fine for pre-`setup_logging` errors. (Verify: `from loguru import logger` and `logger.error(...)` works before `setup_logging()`.)

**Auto-backup-on-load consideration (out of scope):** A future hardening pass could copy `triggarr.toml` to `triggarr.toml.last-good` after every successful load, so the recovery path is always populated. Flag this for a future milestone — not in v2.8.

### Success #5: TEST-03 — concurrent PUT request test

**Pattern:** `TestClient` is synchronous and cannot fire two truly concurrent requests on one event loop. Must use `httpx.AsyncClient` with `ASGITransport`.

**Sketch (to be refined by planner):**

```python
import asyncio
import httpx
from httpx import ASGITransport

async def test_concurrent_settings_save_serialized(test_app, tmp_path):
    """Two concurrent POST /settings cannot interleave: SAFETY-05."""
    # Track call order on the atomic write
    call_order: list[str] = []
    real_write = _atomic_toml_write

    def slow_write(path, data):
        call_order.append("enter")
        time.sleep(0.05)                 # force overlap window
        call_order.append("exit")
        return real_write(path, data)

    with patch("triggarr.web.routes._atomic_toml_write", side_effect=slow_write):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
        ) as ac:
            form_a = {...}              # valid form data, e.g. log_level=info
            form_b = {...}              # valid form data, e.g. log_level=debug
            r1, r2 = await asyncio.gather(
                ac.post("/settings", data=form_a, follow_redirects=False),
                ac.post("/settings", data=form_b, follow_redirects=False),
            )

    # Both requests succeeded
    assert r1.status_code in (200, 303)
    assert r2.status_code in (200, 303)
    # Calls did not interleave
    assert call_order == ["enter", "exit", "enter", "exit"]
    # Final config reflects ONE of the two saves (not a mix)
    final = tomllib.loads(test_app.state.config_path.read_text())
    assert final["general"]["log_level"] in ("info", "debug")
```

**Why `time.sleep` not `await asyncio.sleep`:** `_atomic_toml_write` is sync and is dispatched via `run_in_executor(None, ...)`, so it runs in a thread pool. A `time.sleep` blocks that thread, simulating real I/O. This forces the second call to wait at the lock acquisition point. If we used `asyncio.sleep`, it wouldn't model the offload realistically.

**Pitfall:** The `test_app` fixture uses `aiosqlite.connect` inside an `async with` block (test_web.py:35) — make sure the test runs inside the same `async with` scope so the db connection is still open. The fixture is already `async def test_app(tmp_path)`, so this works.

### Test #6: TEST-02 — corrupted TOML startup test

**Two cases required by the success criterion:**

1. Syntax error in TOML — already exists at `tests/test_config.py:688-694` (`test_toml_syntax_error_raises_decode_error`), but only checks that `load_settings` raises. **Needs upgrade** to call `ensure_config` and assert:
   - Loguru output contains the path of the corrupt file
   - Loguru output contains the backup-restore instruction (conditionally on backup existence)
   - `SystemExit` is raised with code 1

2. Invalid UTF-8 — **new test**. Write `b"\xff\xfe\x00invalid\x00bytes"` to `triggarr.toml`, call `ensure_config`, assert same friendly behavior.

**Loguru capture pattern (already used in this repo):** `tests/test_startup.py:261-267` uses:

```python
sink = io.StringIO()
handler_id = logger.add(sink, format="{message}", level="WARNING")
try:
    ...
finally:
    logger.remove(handler_id)
assert "expected text" in sink.getvalue()
```

Use this pattern for asserting log lines in the new tests.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file write | Custom write-then-rename | Existing `_atomic_toml_write` | Already handles fsync, dir fsync, temp cleanup |
| Async serialization | `threading.Lock`, `multiprocessing.Lock`, `fcntl.flock` | `asyncio.Lock` (already there) | Single-process app; other primitives add complexity |
| Concurrent HTTP test driver | Multiple `TestClient` instances + threads | `httpx.AsyncClient + ASGITransport + asyncio.gather` | TestClient is sync; real concurrency requires the async client |
| Trim policy | Cron-style background task, AFTER INSERT trigger | The existing inline DELETE SQL | Inline trim is observable, testable, transactional with the insert |
| Loguru error formatting | `print(..., file=sys.stderr)` or `traceback.print_exc()` | `logger.error("{} ...", x, exc=exc)` | Project convention is loguru everywhere |
| TOML parse error wrapping | Custom exception hierarchy | Catch `tomllib.TOMLDecodeError, UnicodeDecodeError` directly + `sys.exit(1)` | Two-line handler, no new abstractions |

## Common Pitfalls

### Pitfall 1: `asyncio.Lock` re-entrancy
**What goes wrong:** `asyncio.Lock` is **not** reentrant. If code inside `async with search_lock:` calls another function that also tries to acquire `search_lock`, it deadlocks.
**Why it happens:** Adding "just one more" config save inside a search cycle without realizing the lock is held.
**How to avoid:** Audit during code review. Currently `_atomic_toml_write` itself does not try to acquire the lock; only the route handlers do. The new test should not introduce re-acquisition.
**Warning signs:** `pytest` test hangs indefinitely. Existing 35s drain timeout would also fire.

### Pitfall 2: `TestClient` cannot test concurrency
**What goes wrong:** Writing `client.post(...)` twice from a sync test does not produce true concurrency — `TestClient` serializes through the test thread's event loop.
**Why it happens:** Habit from existing test style.
**How to avoid:** Use `httpx.AsyncClient(transport=ASGITransport(app=...))` for TEST-03. The codebase has `ASGITransport` examples in `tests/test_clients.py` using mocked transports, but no examples driving the full app via ASGI yet — this would be a new pattern. Document it in code comment for future tests.
**Warning signs:** Test passes but doesn't actually exercise the lock.

### Pitfall 3: `os.replace` on Windows
**What goes wrong:** Windows historically required the destination not to exist for atomic rename.
**Why it happens:** Cross-platform code.
**How to avoid:** Triggarr is Linux-only (Docker `python:3.13-slim`). Confirmed: Dockerfile has `RUN useradd ...` and no Windows-specific paths. `os.replace` on POSIX is atomic by spec. No action needed; just document this assumption in code.

### Pitfall 4: aiosqlite + asyncio cancellation
**What goes wrong:** If a coroutine awaiting `db.execute()` is cancelled mid-call, the underlying SQLite worker thread may still complete the operation, but the connection state may be inconsistent.
**Why it happens:** Shutdown timeout fires while a search cycle is mid-insert.
**How to avoid:** This is RES-01 territory (Phase 65), not Phase 64. Note the dependency — the search cycle holds the lock during the insert, and shutdown waits for the lock. Existing behavior. No change needed in this phase.

### Pitfall 5: Loguru before `setup_logging()`
**What goes wrong:** Calling `logger.error(...)` before `setup_logging` configures the redacting sink means the default stderr handler is used.
**Why it happens:** Startup-time errors fire before line `setup_logging(...)` runs.
**How to avoid:** Acceptable for SAFETY-04/TEST-02 — TOML parse errors fire before secrets are loaded, so there are no secrets to redact. Default loguru sink → stderr → user sees the message. Confirm by manual test.
**Warning signs:** Log message appears with default format instead of the project's custom format. Cosmetic only.

### Pitfall 6: `contextlib.suppress` masks unrelated bugs
**What goes wrong:** `with contextlib.suppress(OSError): os.unlink(tmp_path)` swallows PermissionError, ENOSPC, EROFS, OSError(EIO), etc. — not just FileNotFoundError.
**Why it happens:** Original BUG-06 patch was too broad.
**How to avoid:** Replace with `try/except FileNotFoundError: pass` + `except OSError as exc: logger.error(...)`. This is the SAFETY-04 fix.

### Pitfall 7: Test data pollution between concurrent tests
**What goes wrong:** TEST-03's `asyncio.gather` runs two saves into the same `config_path`. Both writes must use the same valid form data shape, else one validation-fails silently and the test "passes" trivially.
**How to avoid:** Both form payloads in the TEST-03 sketch must be schema-complete. Use the same fixture data as `test_save_settings_writes_toml` at `tests/test_web.py:180-213` as a template.

## Code Examples (verified patterns from this repo)

### Loguru log + exit on startup error
```python
# Source: triggarr/config.py:230-234 (extend this pattern)
logger.warning(
    "Default config written to {path} -- edit the config file and restart Triggarr",
    path=config_path,
)
sys.exit(1)
```

### Loguru capture in tests
```python
# Source: tests/test_startup.py:261-267
sink = io.StringIO()
handler_id = logger.add(sink, format="{message}", level="WARNING")
try:
    result = await sonarr.detect_api_version()
finally:
    logger.remove(handler_id)
assert "version detection failed" in sink.getvalue()
```

### Atomic write with cleanup
```python
# Source: triggarr/config.py:92-119 (current state, to be patched)
fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
try:
    with os.fdopen(fd, "wb") as f:
        tomli_w.dump(data, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)
    dir_fd = os.open(path.parent, os.O_RDONLY)
    os.fsync(dir_fd)
except Exception:
    with contextlib.suppress(OSError):
        os.unlink(tmp_path)
    raise
finally:
    if dir_fd is not None:
        os.close(dir_fd)
```

### asyncio.Lock pattern around config write
```python
# Source: triggarr/web/routes.py:572-577
async with request.app.state.search_lock:
    await asyncio.get_running_loop().run_in_executor(
        None, _atomic_toml_write, config_path, _settings_to_dict(new_settings)
    )
    os.chmod(config_path, 0o600)
    request.app.state.settings = new_settings
```

### Trim SQL inside insert
```python
# Source: triggarr/db.py:332-351 (already correct)
await db.execute("INSERT INTO search_history ...", (...))
await db.execute("""
    DELETE FROM search_history
    WHERE COALESCE(outcome, 'searched') != 'searched'
    AND id NOT IN (
        SELECT id FROM search_history
        WHERE COALESCE(outcome, 'searched') != 'searched'
        ORDER BY id DESC LIMIT ?
    )
""", (max_rows,))
await db.commit()
```

## Test Strategy

### TEST-03: two concurrent PUT requests

**Fixtures:** Reuse `test_app` from `tests/test_web.py:25-118`. It already provides `app.state.search_lock = asyncio.Lock()` and a real `aiosqlite` connection on `tmp_path`.

**Driver:** `httpx.AsyncClient(transport=ASGITransport(app=test_app))`. This is a **new pattern** for this repo's web tests (existing pattern is `TestClient`). Document in a comment.

**Forcing the overlap:** Wrap `_atomic_toml_write` with `time.sleep(0.05)` via `patch(..., side_effect=...)`. The sleep blocks the thread-pool worker that the route's `run_in_executor` dispatches to, so the second route handler reaches `await ... run_in_executor(...)` before the first releases the lock — exactly the contention scenario.

**Assertions:**
1. Both requests return 303 (redirect — the success status from `POST /settings`).
2. The temporal interleave (recorded by a side-effect spy on `_atomic_toml_write`) is `[enter, exit, enter, exit]`, never `[enter, enter, exit, exit]`.
3. The final config file contains exactly one of the two distinguishable payloads (e.g., `log_level=info` OR `log_level=debug`), not a hybrid.

**Edge case to test (optional):** If the lock is replaced with a no-op `contextlib.nullcontext()` (mutation test), the assertion in step 2 should fail — proving the test actually exercises the lock.

### TEST-02: corrupted TOML startup

**Two cases (covering criterion phrasing "syntax error or invalid UTF-8"):**

1. **Syntax error**
   ```python
   def test_ensure_config_logs_friendly_error_on_toml_syntax_error(tmp_path, caplog_loguru):
       config = tmp_path / "triggarr.toml"
       config.write_text('[general\nlog_level = "info"')  # missing ]
       with pytest.raises(SystemExit) as exc_info:
           ensure_config(config)
       assert exc_info.value.code == 1
       assert str(config) in caplog_loguru.text
       assert "parse" in caplog_loguru.text.lower() or "decode" in caplog_loguru.text.lower()
   ```

2. **Invalid UTF-8**
   ```python
   def test_ensure_config_logs_friendly_error_on_invalid_utf8(tmp_path, caplog_loguru):
       config = tmp_path / "triggarr.toml"
       config.write_bytes(b"\xff\xfe\x00garbage")
       with pytest.raises(SystemExit) as exc_info:
           ensure_config(config)
       assert exc_info.value.code == 1
       assert str(config) in caplog_loguru.text
   ```

3. **Backup-path mentioned when backup exists**
   ```python
   def test_ensure_config_mentions_backup_path_when_backup_exists(tmp_path, caplog_loguru):
       config = tmp_path / "triggarr.toml"
       backup = tmp_path / "triggarr.toml.bak"
       backup.write_text('log_level = "info"\n')
       config.write_text('[general\nlog_level = "info"')  # corrupt
       with pytest.raises(SystemExit):
           ensure_config(config)
       assert str(backup) in caplog_loguru.text
   ```

**`caplog_loguru` fixture:** Does not exist in this repo. Create as a small conftest fixture using the loguru sink pattern from test_startup.py:261-267:

```python
@pytest.fixture
def caplog_loguru():
    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="DEBUG")
    yield type("CapturedLog", (), {"text": property(lambda _: sink.getvalue())})()
    logger.remove(handler_id)
```

Or just inline the pattern in each test — the planner can choose.

### SAFETY-04 unit tests

Already covered by existing tests for the success-case paths. New test required:

```python
def test_atomic_toml_write_logs_cleanup_oserror(tmp_path, caplog_loguru):
    """A non-FileNotFoundError OSError during cleanup is logged, not silently swallowed."""
    config_file = tmp_path / "test.toml"
    with patch("triggarr.config.tomli_w.dump", side_effect=TypeError("fail")), \
         patch("triggarr.config.os.unlink", side_effect=PermissionError("denied")), \
         pytest.raises(TypeError):
        _atomic_toml_write(config_file, {"k": "v"})
    assert "Failed to clean up temp file" in caplog_loguru.text
    assert "denied" in caplog_loguru.text
```

```python
def test_atomic_toml_write_suppresses_filenotfound_silently(tmp_path, caplog_loguru):
    """FileNotFoundError during cleanup is suppressed and NOT logged (criterion phrasing)."""
    config_file = tmp_path / "test.toml"
    with patch("triggarr.config.tomli_w.dump", side_effect=TypeError("fail")), \
         patch("triggarr.config.os.unlink", side_effect=FileNotFoundError), \
         pytest.raises(TypeError):
        _atomic_toml_write(config_file, {"k": "v"})
    assert "Failed to clean up" not in caplog_loguru.text
```

```python
def test_atomic_toml_write_logs_os_replace_failure(tmp_path, caplog_loguru):
    """OSError raised from os.replace is logged before propagating."""
    config_file = tmp_path / "test.toml"
    with patch("triggarr.config.os.replace", side_effect=OSError("EROFS")), \
         pytest.raises(OSError):
        _atomic_toml_write(config_file, {"k": "v"})
    assert "Config write failed" in caplog_loguru.text
    assert "EROFS" in caplog_loguru.text
```

## Runtime State Inventory

Not a rename/refactor/migration phase. The only state that lives outside source code is:
- **`/config/triggarr.toml`** — config file the patches operate on. No data migration required; existing files load identically after the patches (the friendly-error path only activates on already-corrupt files).
- **`/config/triggarr.db`** — SQLite database. Schema unchanged. No migration. The trim SQL is already running in production.
- **Loguru sink configuration** — `setup_logging` is unchanged. Pre-`setup_logging` errors use the default loguru handler (stderr), which is acceptable for the friendly-TOML-error case.
- **Nothing else.** No env vars renamed, no secret keys touched, no installed-package layout changes, no Docker registry tag changes.

## Environment Availability

This phase has no new external dependencies. All libraries are already declared in `pyproject.toml` and installed by `uv sync --extra dev` per `./CLAUDE.md`. No tool, service, or runtime probe is required.

## Validation Architecture

This phase is correctness/safety hardening, not behavioral validation. Nyquist analysis does not apply — there is no "behavior to sample at 2× cadence" because all five success criteria are deterministic invariants (a lock holds or it doesn't; a log line is emitted or it isn't; a row trim happens or it doesn't). Standard pytest assertions cover them fully.

Skipping the formal Nyquist section per the additional-context guidance.

## Open Questions (RESOLVED)

1. **SAFETY-01 — is the existing trim sufficient, or does the planner want stricter enforcement?**
   - What we know: `insert_search_entry` already trims resolved rows to `max_rows` immediately after each insert. Pending rows (`outcome='searched'`) are exempt and bounded by tracking window.
   - What's unclear: Does "never exceeds `max_history_rows`" in the ROADMAP mean *resolved rows* (current behavior) or *all rows* (would need to also bound pending)?
   - RESOLVED: Treat as already-implemented. Add a comment in db.py documenting that pending rows are exempt, and add a soak-test (insert 2× max_rows resolved entries, verify cap). Implemented by Plan 64-04. If a stricter interpretation is required, a second trim that caps total rows including pending could be added — but this risks deleting tracking-eligible rows before they resolve. Deferred to a follow-up if needed.

2. **Should the friendly TOML-error handler also auto-create `triggarr.toml.last-good` after every successful load?**
   - What we know: The only backup file currently produced is `triggarr.toml.bak` from the v2.2→v2.3 migration — it does not exist for users who installed at v2.3+.
   - What's unclear: Whether to introduce a "last-good copy" pattern in this phase.
   - RESOLVED: Out of scope for v2.8. The success criterion only requires the message to *mention* the backup path if it exists; it does not require a new backup mechanism. Plan 64-02 conditionally mentions `triggarr.toml.bak` only when it is present on disk. Auto-last-good deferred to a future hardening pass.

3. **Are `tomllib.TOMLDecodeError` raised types and `UnicodeDecodeError` the complete set of TOML-load failure modes?**
   - What we know: `tomllib.load(f)` opens in binary mode and decodes internally. The two relevant exceptions per the cpython docs are `tomllib.TOMLDecodeError` (subclass of `ValueError`) for syntax errors and `UnicodeDecodeError` for non-UTF-8 bytes. `OSError` is also possible if the file is unreadable (permission denied), but that case is distinct from "corrupted."
   - RESOLVED: Plan 64-02 catches `(tomllib.TOMLDecodeError, UnicodeDecodeError)` for the friendly handler and lets `OSError` propagate (a permission error at startup is fatal and the user needs the traceback).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Triggarr Docker always runs single-worker uvicorn | SAFETY-05 / Recommended Approach | If a future Dockerfile change adds `--workers 2`, `asyncio.Lock` silently fails to serialize. **Mitigation:** add a comment near `search_lock` definition warning against this. |
| A2 | `tomllib.load` raises `UnicodeDecodeError` (not `TOMLDecodeError`) for invalid UTF-8 bytes | Recommended Approach #4 / Test Strategy | If wrong, the friendly handler misses some bad-bytes cases. **Mitigation:** add `(OSError, Exception)` outer catch with a generic fallback log line. Or just catch both and verify in TEST-02. |
| A3 | `loguru.logger.error(...)` works before `setup_logging()` is called | Pitfall 5 | If wrong, the corrupted-TOML message goes nowhere. **Mitigation:** explicitly test by running `python -c "from loguru import logger; logger.error('test')"` — loguru ships with a default stderr handler. Verified by import semantics. HIGH confidence. |
| A4 | `httpx.AsyncClient + ASGITransport` works against a real FastAPI app instance with the existing `test_app` fixture | TEST-03 / Test Strategy | If wrong, TEST-03 cannot be written this way. **Mitigation:** Fall back to a manual `asyncio.gather` of two coroutines that each call `_atomic_toml_write` through `run_in_executor` directly, bypassing HTTP — less faithful but proves the lock works. HIGH confidence the ASGITransport approach works; it's the documented FastAPI/Starlette pattern. |
| A5 | The 8 call sites of `_atomic_toml_write` in routes.py all already acquire `search_lock` | SAFETY-05 / Current State B | Verified by grep — all 8 are inside `async with request.app.state.search_lock:` blocks. HIGH confidence. |
| A6 | The trim SQL in `insert_search_entry` is correct under WAL+synchronous=NORMAL | SAFETY-01 / Recommended Approach #1 | If wrong, a crash mid-trim could leave the table over-cap until next insert — acceptable. HIGH confidence. |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `tomli` library | `tomllib` stdlib (read), `tomli-w` (write) | Python 3.11 (Oct 2021) | Already in use; nothing to migrate |
| `aiofiles` for SQLite | `aiosqlite` | Project decision pre-v2.0 | Already in use; do not introduce mixed model |
| File-level locks (fcntl) | `asyncio.Lock` | N/A — never used here | Stay with asyncio.Lock; single-worker constraint makes it sufficient |
| `unittest.mock` decorators | `unittest.mock.patch` context manager | Project convention | Tests in this repo use `with patch(...)`, not `@patch(...)` decorators |

**Deprecated/outdated:**
- Nothing being removed or replaced in this phase. Pure additive hardening.

## Sources

### Primary (HIGH confidence)
- `triggarr/config.py` (read in full) — `_atomic_toml_write`, `load_settings`, `ensure_config`
- `triggarr/db.py:302-351` — `insert_search_entry` with trim SQL
- `triggarr/search/scheduler.py:80, 200-273` — `search_lock` lifecycle and lifespan
- `triggarr/web/routes.py:486-577, 736, 775, 1097, 1350, 1384, 1408` — config-save call sites
- `triggarr/__main__.py` — single-worker uvicorn config
- `triggarr/models/config.py:79` — `max_history_rows` default
- `pyproject.toml` — Python 3.11+, ruff config, pytest-asyncio mode
- `Dockerfile` — confirms `python:3.13-slim` (Linux), single ENTRYPOINT
- `tests/test_config.py:653-726` — existing atomic-write and TOML-error tests
- `tests/test_db.py:95-106, 412-426` — existing trim tests
- `tests/test_web.py:25-124, 584-598, 772-799` — existing fixture, concurrent rate-limit test, OSError-propagation test
- `tests/test_startup.py:261-267` — loguru-capture pattern
- `.planning/codebase/CONCERNS.md` — DEBT-03, BUG-06, SAFETY-04 audit findings

### Secondary (MEDIUM confidence)
- Python stdlib documentation — `tomllib.TOMLDecodeError`, `os.replace` atomicity guarantees (POSIX)
- FastAPI / Starlette documentation — `httpx.AsyncClient(transport=ASGITransport(...))` pattern

### Tertiary (LOW confidence)
- None — all claims tied to either codebase grep or stdlib semantics.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages
- Current state of all three paths: HIGH — full read of config.py + db.py + scheduler.py + relevant routes.py sections
- Recommended approach per criterion: HIGH — refinements to existing code, not new architecture
- Test strategy: HIGH for TEST-02 (existing patterns suffice), MEDIUM for TEST-03 (new ASGITransport pattern; needs validation in implementation)
- Pitfalls: HIGH — codebase-specific issues identified by direct inspection

**Research date:** 2026-05-25
**Valid until:** 2026-06-24 (30 days — stable internal hardening, no fast-moving dependencies)
