# Phase 88: Bounded Upgrade Backups & Telemetry Regression - Pattern Map

**Mapped:** 2026-11-16
**Files analyzed:** 4 (2 modified source/test, 1 new/extended test, 1 doc)
**Analogs found:** 4 / 4 (2 exact in-file, 1 composite, 1 direct-anchor)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|---------------|
| `triggarr/db.py` (add `_prune_timestamped_backups` + call site in `run_migrations`) | utility/model (persistence module) | file-I/O (filesystem prune) inside a CRUD/migration flow | `triggarr/state.py::_recover_from_bad_state_file` (lines 229-281) for the try/except/log shape; `triggarr/db.py::insert_search_entry` (lines 797-812) for bounded-retention-by-count; both already in the same codebase area this phase touches | exact (same-file precedent) + role-match (cross-file precedent) |
| `tests/test_db.py` (extend: multi-attempt bound test + failed-delete warning test) | test | file-I/O / CRUD regression test | `tests/test_db.py::test_backup_created_on_migration` (383-388), `test_run_migrations_fresh_install` (1082-1108), `tests/migration_faults.py::seed_v9_db` + `MIGRATIONS` monkeypatch convention (32-60) | exact |
| `tests/test_telemetry.py` (new) **or** a new section in `tests/test_scheduler.py` (Claude's discretion) | test | request-response (real ASGI lifespan dispatch) | Composite: `tests/test_scheduler.py` (`create_lifespan` usage 974-1000, `FastAPI`/`monkeypatch.setenv` conventions 1-42, 1046-1072) + `tests/test_attribution_disclosure.py` (`TestClient(app) as client:` + `router` usage, 17-27, 48-53, 111-113) | role-match (no single existing file combines `create_lifespan` with `TestClient`; this phase is the first to need both) |
| `README.md` (one sentence, Configuration Reference section) | config/doc | N/A (static text) | The existing startup-env-vars paragraph it follows (`README.md:213`), immediately before `## Screenshots` (`README.md:215`) | exact (anchor point is explicit in CONTEXT.md D-10) |

## Pattern Assignments

### `triggarr/db.py` (utility/model, file-I/O inside migration flow)

**Analog:** same file — `run_migrations` (172-236) is the function being extended; `insert_search_entry` (797-812) and `triggarr/state.py::_recover_from_bad_state_file` (229-281) are the two closest precedents for the new helper's internal shape.

**Imports pattern** — nothing new needed; everything the helper requires is already imported at the top of `db.py` (lines 9-23):
```python
import re
import shutil
...
from datetime import UTC, datetime
from pathlib import Path
...
from loguru import logger
```

**Existing call site to extend** (`db.py:203-219`, inside `run_migrations`):
```python
    backup_path = db_path.with_suffix(f".v{current}-backup")
    earliest_backup: Path | None = None
    if db_path.exists():
        if backup_path.exists():
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            timestamped_path = db_path.with_suffix(f".v{current}-backup-{stamp}")
            shutil.copy2(db_path, timestamped_path)
            logger.info(
                "Database backed up to {path} (earlier backup preserved at {earlier})",
                path=timestamped_path,
                earlier=backup_path,
            )
            earliest_backup = backup_path
        else:
            shutil.copy2(db_path, backup_path)
            logger.info("Database backed up to {path}", path=backup_path)
            earliest_backup = backup_path
```
Per D-03, the new `_prune_timestamped_backups(db_path, current)` call goes right after the `earliest_backup = backup_path` line in the **timestamped** branch only (never in the canonical-backup `else` branch — nothing to prune there, and `earliest_backup` always points at the canonical file, which is never a deletion candidate, so the ordering constraint is satisfied by construction).

**Error-handling / failure-logged-never-blocks pattern** (copy this shape exactly) — `triggarr/state.py:254-271`:
```python
    try:
        fd, tmp = tempfile.mkstemp(dir=state_path.parent, prefix=state_path.name + ".corrupt.", suffix=".tmp")
        os.close(fd)
        shutil.copy2(state_path, tmp)
        os.replace(tmp, set_aside)
        tmp = None
        copy_succeeded = True
    except OSError as exc:
        logger.warning(
            "Could not set aside the bad state file {path}: {exc}",
            path=state_path,
            exc=f"{type(exc).__name__}: {exc}",
        )
```
This is the exact log-message shape D-09 asks for: name the path, then `f"{type(exc).__name__}: {exc}"` — never the raw traceback, never error level (state.py uses `logger.warning`, same as D-09 requires). Catch `OSError` specifically (not bare `Exception`), matching this precedent and `_apply_atomic_migration`'s own `except Exception` (for the *migration* failure, a different and intentionally broader case) — the narrower `OSError` catch here is correct because the only operation inside the `try` is a filesystem delete.

**Bounded-retention-by-count precedent** (same shape, different resource) — `triggarr/db.py:797-812`:
```python
        await db.execute(
            """
            DELETE FROM search_history
            WHERE COALESCE(outcome, 'searched') NOT IN ('searched', 'partial')
            AND id NOT IN (
                SELECT id FROM search_history
                WHERE COALESCE(outcome, 'searched') NOT IN ('searched', 'partial')
                ORDER BY id DESC LIMIT ?
            )
            """,
            (max_rows,),
        )
```
Mirror this "keep newest N, prune the rest" intent for files: glob only the current version's timestamped siblings (never cross-version, D-07), regex-validate the stamp before treating a file as prunable (never a loose glob alone — this is the filesystem equivalent of the `WHERE` clause's exact-match scoping above), sort newest-first by the embedded filename stamp (never `Path.stat().st_mtime` — Pitfall 9: `shutil.copy2` sets the backup's mtime to the *source db's* mtime, not copy time), and `unlink(missing_ok=True)` everything past index 3.

**D-08 success-path log line** — same `logger.info` call style already used two lines above the insertion point (`db.py:210-214`); state one line per deleted file naming the path and that the original + 3 most recent are kept.

---

### `tests/test_db.py` (test, file-I/O / CRUD regression)

**Analog:** `tests/test_db.py::test_backup_created_on_migration` (383-388), `test_run_migrations_fresh_install` (1082-1108), plus the shared `_init_test_db` helper (38-43) and `tests/migration_faults.py`'s `MIGRATIONS` monkeypatch convention (32-60).

**Imports pattern** (`test_db.py:1-35`) — no async marker needed anywhere (`asyncio_mode = "auto"`, CLAUDE.md):
```python
from __future__ import annotations

import io
from pathlib import Path

import aiosqlite
import pytest
from loguru import logger

from tests.migration_faults import STANDARD_MAPPING, original_projection, seed_v9_db, snapshot
from triggarr.db import (
    OwnedGrab,
    OwnedGrabRecord,
    PendingCapExceeded,
    _apply_atomic_migration,
    _migrate_v1,
    _migrate_v10,
    get_dashboard_stats,
    get_owned_grabs,
    get_recent_searches,
    get_schema_version,
    get_search_history,
    get_trackable_entries,
    init_db,
    insert_search_entry,
    migrate_from_state,
    update_outcome_and_stats,
)
```
Add `MIGRATIONS`, `run_migrations`, and the new `_prune_timestamped_backups` (if it needs direct testing) to this same import block rather than a local `from triggarr.db import ...` inside the test function — note `test_migration_loop_tolerates_gaps` (line 1113 area) does a local import; either style is tolerated in this file, but prefer the top-level block for consistency with the majority of this file's imports.

**Shared fixture helper** (`test_db.py:38-43`) — reuse directly, do not duplicate:
```python
async def _init_test_db(tmp_path):
    """Create a test database with migrations applied, return (db, db_path)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    return db, db_path
```

**Existing backup-presence assertion to extend** (`test_db.py:383-388`):
```python
async def test_backup_created_on_migration(tmp_path):
    """Database backup file is created before migration runs."""
    db, db_path = await _init_test_db(tmp_path)
    backup = db_path.with_suffix(".v0-backup")
    assert backup.exists()
    await db.close()
```

**Fresh-install no-backup-guard test** (`test_db.py:1082-1108`) — shows the project's `monkeypatch.setattr(Path, "exists", ...)` style for forcing a specific `run_migrations` branch:
```python
async def test_run_migrations_fresh_install(tmp_path, monkeypatch):
    """Fresh install: run_migrations skips backup when db_path.exists() is False."""
    db_path = tmp_path / "fresh.db"
    original_exists = Path.exists

    def _patched_exists(self):
        if self == db_path:
            return False
        return original_exists(self)

    monkeypatch.setattr(Path, "exists", _patched_exists)
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    version = await get_schema_version(db)
    assert version == 10
    backup = db_path.with_suffix(".v0-backup")
    assert not backup.exists(), "No backup should be created when db_path.exists() is False"
    await db.close()
```

**`MIGRATIONS` fault-injection convention** (`tests/migration_faults.py:32-60`, the proven, safe way to make a migration fail repeatedly for the D-05 5+-attempt test):
```python
async def seed_v9_db(tmp_path: Path, monkeypatch: Any) -> Path:
    db_path = tmp_path / "test.db"
    v10_entry = MIGRATIONS[10]
    monkeypatch.delitem(MIGRATIONS, 10)
    try:
        db = await aiosqlite.connect(db_path)
        try:
            await init_db(db, db_path)
            ...
        finally:
            await db.close()
    finally:
        MIGRATIONS[10] = v10_entry
    return db_path
```
Use `monkeypatch.setitem(MIGRATIONS, next_version, (desc, always_fails_fn))` (research's Code Examples section already sketches this exact shape) to force 5+ consecutive `run_migrations` failures from the same `current`, then assert: canonical `.v{current}-backup` exists, at most 3 timestamped siblings exist, and (for the dedicated BKUP-02 failed-delete test) monkeypatch `Path.unlink` to raise `OSError` once and assert startup/migration still proceeds (never raises) with a `caplog`/`logger` sink showing one `warning`-level line naming the file.

---

### `tests/test_telemetry.py` (new) or a new section in `tests/test_scheduler.py` (test, request-response / real ASGI lifespan)

**Analog (composite — no single existing file does both halves):**

**Half A — `create_lifespan` + `FastAPI` + `monkeypatch.setenv` conventions**, from `tests/test_scheduler.py`:

Imports (`test_scheduler.py:1-42`):
```python
from __future__ import annotations

import asyncio
...
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
...
from tests.conftest import make_settings
...
from triggarr.web.routes import STATIC_DIR, router
```

`create_lifespan` construction pattern (`test_scheduler.py:974-990`, **do not** use the `async with lifespan_fn(app):` form that follows it at line 993 — Pitfall 2 in research proves that bypasses the exact FastAPI-level code this test must exercise):
```python
    from triggarr.search.scheduler import create_lifespan

    settings = make_settings(radarr_enabled=False, sonarr_enabled=False)
    state_path = tmp_path / "state.json"
    config_path = tmp_path / "triggarr.toml"
    lifespan_fn = create_lifespan(settings, state_path, config_path)
    app = FastAPI(lifespan=lifespan_fn)
```

`monkeypatch.setenv` env-var-test convention (`test_scheduler.py:1046-1072`, env var set *before* the code under test reads it — same ordering constraint applies here, but for `FASTAPI_OTEL_AUTO_CONFIGURE` the read happens at `FastAPI(...)` construction time, not at module-import time, so no `importlib.reload` is needed — just call `monkeypatch.setenv(...)` before the `FastAPI(lifespan=...)` line above, not after):
```python
def test_shutdown_timeout_env_var_override(monkeypatch):
    ...
    monkeypatch.setenv("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT", "15.0")
    importlib.reload(sched)
    assert sched._SHUTDOWN_DRAIN_TIMEOUT == 15.0
    ...
    monkeypatch.delenv("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT", raising=False)
```

**Half B — `TestClient(app) as client:` + `router` wiring**, from `tests/test_attribution_disclosure.py` (lines 17-27, 48-53, 111-113):
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from triggarr.web.routes import STATIC_DIR, router
...
app = FastAPI()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(router)
...
with TestClient(app) as client:
    response = client.get("/")
assert response.status_code == 200
```
`/health` (the endpoint this test should call instead of `/`) is defined at `triggarr/web/routes.py:254` via `@router.get("/health")` on the same `router` object.

**Combined shape for the new test** (per research's Pattern 2 / D-12 — set env vars first, then build `FastAPI(lifespan=create_lifespan(...))`, `include_router(router)`, then dispatch through `TestClient`, then assert only the outcome):
```python
async def test_telemetry_env_vars_do_not_crash_startup(tmp_path, monkeypatch):
    """TELEM-01: FASTAPI_OTEL_AUTO_CONFIGURE + an OTLP endpoint must never crash startup."""
    monkeypatch.setenv("FASTAPI_OTEL_AUTO_CONFIGURE", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")

    settings = make_settings(radarr_enabled=False, sonarr_enabled=False, lidarr_enabled=False)
    lifespan_fn = create_lifespan(settings, tmp_path / "state.json", tmp_path / "triggarr.toml")
    app = FastAPI(lifespan=lifespan_fn)
    app.include_router(router)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
```
Never assert on FastAPI's internal warning string (Pitfall 4/11) — assert only `response.status_code == 200`.

---

### `README.md` (config/doc, static text)

**Analog:** the existing paragraph it is appended after (`README.md:213`, directly before `## Screenshots` at line 215). No code pattern to copy — this is prose, not source.

**Exact insertion context:**
```markdown
Startup-level environment variables such as `TRIGGARR_CONFIG_DIR`, `TRUSTED_PROXY_IPS`, and `ROOT_PATH` are read by the process before the TOML settings are loaded; they are not stored in `triggarr.toml`.

## Screenshots
```
Per D-10/D-11, insert one new sentence (or short paragraph) between those two lines, in the same prose register as the paragraph above it, conveying: (1) Triggarr does not support OpenTelemetry export, and (2) setting `FASTAPI_OTEL_AUTO_CONFIGURE` or an OTLP endpoint variable does not stop Triggarr from starting — nothing is exported either way. No new `##`/`###` heading (D-10 is explicit: "No new section").

---

## Shared Patterns

### Filesystem cleanup: try/except (narrow exception type) → log at warning → never re-raise, never block the caller
**Source:** `triggarr/state.py:254-271` (`_recover_from_bad_state_file`)
**Apply to:** `triggarr/db.py`'s new `_prune_timestamped_backups` helper (D-04/D-09)
```python
except OSError as exc:
    logger.warning(
        "Could not set aside the bad state file {path}: {exc}",
        path=state_path,
        exc=f"{type(exc).__name__}: {exc}",
    )
```
The `f"{type(exc).__name__}: {exc}"` formatting is the project's standard way of logging "the system reason" without a raw traceback or any risk of leaking more than intended through the redacting loguru sink (CLAUDE.md).

### Bounded retention by count, scoped and ordered correctly
**Source:** `triggarr/db.py:797-812` (`insert_search_entry`'s resolved-row trim)
**Apply to:** the new backup-pruning helper — same "keep newest N, delete the rest, scoped to the right subset" shape, translated from SQL `DELETE ... WHERE ... NOT IN (... ORDER BY id DESC LIMIT ?)` to `glob` + regex filter + sort-by-embedded-timestamp + `unlink()` past index 3.

### `monkeypatch.setenv`, never raw `os.environ`, for every env-var-driven test
**Source:** `tests/test_scheduler.py` (e.g. `test_shutdown_timeout_env_var_override`, 1046-1072) — the project-wide convention
**Apply to:** the new TELEM-01 test; set env vars *before* constructing the object that reads them (Pitfall 3: `FastAPI.__init__` reads `FASTAPI_OTEL_AUTO_CONFIGURE` once, at construction time, not at request time).

### Real ASGI dispatch via `TestClient(app) as client:` for anything FastAPI itself wires into `__call__`
**Source:** `tests/test_attribution_disclosure.py:111-113`
**Apply to:** the new TELEM-01 test only — Triggarr's own lifespan/shutdown tests correctly keep using `async with lifespan_fn(app):` (`tests/test_scheduler.py:993,1016`); do not change that pattern for any other test in this phase.

## No Analog Found

None. Every file in scope has at least a composite analog in the existing codebase (see table above); no file in this phase requires inventing a wholly new pattern family.

## Conventions

Derived via the shared deterministic module (`bin/gsd-tools.cjs verify conventions --derive`), scoped to `triggarr/` (the directory containing every source file this phase touches):

| Axis | Dominant | Share | Entropy | Status |
|------|----------|-------|---------|--------|
| File-name casing | camel | 77.4% | 0.609 | named contract |
| Identifier casing | (none) | 43.4% | 0.783 | contested hotspot |
| Export style | — | — (insufficient data) | — | insufficient-data |
| Import style | — | — (insufficient data) | — | insufficient-data |

Two Python-specific axes the tool also reports for this scope, both unanimous: `py-wildcard-import` → `explicit` (100%, 28/28 — no `from x import *` anywhere) and `py-import-relativity` → `absolute` (100%, 28/28 — every import is `from triggarr...`/`import triggarr...`, never a relative `from .`). Both new/modified files in this phase should follow these without exception, matching every excerpt quoted above.

The export-style/import-style axes read "insufficient-data" because this project is Python, not JS/TS/CJS/ESM — the generic tool has no signal to bucket here; `py-wildcard-import`/`py-import-relativity` above are this scope's real equivalent and are both unanimous, not contested.

**Contested hotspots (author's choice):** The tool's prototype intentional-contested split is the CJS<->SDK dual resolver in the GSD tooling's own repo (`bin/lib/**` is CJS `module.exports`/`require`; `sdk/src/**` is ESM `export`/`import`) — each half is internally consistent per-directory, contested only when measured repo-wide, and the correct call for a reviewer or planner is to match whichever directory's local style the file in question already lives in, not to "fix" the split. `triggarr/`'s own contested axis (identifier-casing, 43% dominant share) is the same shape for this repo: Python's own role-based split (PascalCase for classes, snake_case for functions/variables/module names, `CONSTANT_CASE` for module-level constants — e.g. `MigrationRecoveryError` vs `run_migrations` vs `PENDING_CAP_MULTIPLIER`, all in `triggarr/db.py`) is internally consistent *per identifier role* and only reads as "contested" when the tool's casing buckets are pooled across roles. Follow the role-based convention already visible in every excerpt above (`_prune_timestamped_backups` snake_case function, `_BACKUP_STAMP_RE`/`_MAX_RETAINED_TIMESTAMPED_BACKUPS` CONSTANT_CASE module constants) rather than treating the pooled contested score as license to pick a different style. The file-name-casing axis's 77% "camel" dominance is a tool-bucketing artifact for this scope, not a real convention: single-word, no-delimiter filenames like `db.py`/`state.py`/`config.py` fall into the same bucket as true camelCase by the heuristic; this repo's actual, unambiguous file-naming convention is `snake_case.py` (seen directly in `log_buffer.py`, `update_check.py`, and every `test_*.py` file), which is what both new/extended files in this phase (`test_db.py`, `test_telemetry.py`) already follow.

## Metadata

**Analog search scope:** `triggarr/db.py`, `triggarr/state.py`, `triggarr/search/scheduler.py`, `triggarr/web/routes.py`, `tests/test_db.py`, `tests/test_scheduler.py`, `tests/test_attribution_disclosure.py`, `tests/migration_faults.py`, `tests/conftest.py`, `README.md`
**Files scanned:** 10 read directly (targeted ranges, no full-file reads over ~300 lines except where the file itself was short)
**Pattern extraction date:** 2026-11-16
