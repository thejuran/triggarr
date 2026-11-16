# Phase 88: Bounded Upgrade Backups & Telemetry Regression - Research

**Researched:** 2026-11-16
**Domain:** Filesystem backup pruning in an existing SQLite migration function; FastAPI lifespan/ASGI regression testing
**Confidence:** HIGH

## Summary

Both halves of this phase are small, already-scoped corrections to code that already exists — nothing here is new architecture. BKUP-01/02 add a prune step to `triggarr/db.py::run_migrations` (lines 172-236) right after it writes a new timestamped backup; the canonical `.v{current}-backup` file and parsed-filename ordering are already established conventions in that function, and `.planning/research/PITFALLS.md` Pitfall 9 already specifies the two hard constraints (never delete the canonical file; never sort by mtime because `shutil.copy2` preserves the source db's mtime, not copy time). TELEM-01/02 need no code change — FastAPI 0.162.4 already catches its own OTel auto-configure failure internally (verified by reading the installed `fastapi/telemetry/_runtime.py`) — only a permanent regression test and one README sentence.

The one genuinely new finding from this research session, not previously documented in `.planning/research/`: **the telemetry regression test must drive the app through a real ASGI lifespan dispatch (`with TestClient(app) as client:`), not the `async with lifespan_fn(app):` pattern `tests/test_scheduler.py` otherwise uses everywhere.** FastAPI's OTel auto-configure hook lives inside `FastAPI.__call__` itself (it intercepts `scope["type"] == "lifespan"` before delegating to Triggarr's own lifespan function) — calling Triggarr's lifespan context manager directly bypasses `FastAPI.__call__` entirely and never exercises the code this test exists to pin. This was verified directly by running both forms against the installed FastAPI 0.162.4 in this repo's venv (see Code Examples). Getting this wrong would produce a test that always passes regardless of whether the FastAPI-level fix is present — a false sense of coverage.

**Primary recommendation:** Add a private pruning helper to `triggarr/db.py` that runs immediately after the timestamped-backup branch in `run_migrations`, keyed on `current` and matched by a strict filename regex (never a loose glob) so it can never touch the canonical backup or an unrelated file; write the telemetry regression test using `create_lifespan` + `app.include_router(router)` + `with TestClient(app) as client: client.get("/health")`, with `monkeypatch.setenv("FASTAPI_OTEL_AUTO_CONFIGURE", "true")` called *before* `FastAPI(lifespan=...)` is constructed.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BKUP-01 | Pre-upgrade backups bounded: original always kept, plus at most 3 most recent later ones | `run_migrations` code read at `triggarr/db.py:172-236`; exact file-naming/pruning mechanics below; worked 5-fail/6th-succeeds example reconciled file-for-file against CONTEXT.md's own example |
| BKUP-02 | Pruning never removes original or just-written backup, orders by filename timestamp (never mtime), pruning failure logged without blocking startup | Existing `backup_path`/`timestamped_path` naming already in code; `state.py::_recover_from_bad_state_file`'s try/except/warning-and-continue pattern (Phase 87, merged) is the directly reusable precedent for the failed-delete warning |
| TELEM-01 | Automated test pins that Triggarr starts and serves requests with `FASTAPI_OTEL_AUTO_CONFIGURE` + OTLP endpoint set | Verified by reading `fastapi/telemetry/_runtime.py` and `applications.py` directly in the installed venv, and by running a real experiment against both test-construction styles (see Code Examples) |
| TELEM-02 | Documentation states telemetry export is unsupported and nothing is exported | Exact README insertion point confirmed (`README.md:213`, directly after the existing startup-env-vars paragraph, before `## Screenshots`) |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Carried forward (milestone standing rules and locked requirements, not re-asked)**
- **D-01:** No new runtime dependency (no backup-rotation package, no OpenTelemetry SDK/exporter). Use stdlib `pathlib`/`os`. Each fix lands with a regression test that fails on the unfixed code.
- **D-02:** Cap shape (BKUP-01, locked): the canonical original backup `<db>.v{current}-backup` is always kept, plus at most the 3 most recent timestamped retry backups `<db>.v{current}-backup-{stamp}` for the same `current` version.
- **D-03:** (BKUP-02, locked) Pruning never removes the canonical original or the backup just written. Order is decided by the `%Y%m%dT%H%M%S%fZ` timestamp parsed from the file name, never by file mtime (`shutil.copy2` copies the source db's mtime; research PITFALLS.md Pitfall 9). Pruning runs after the new backup is written, so `earliest_backup` (used in the "restore from ..." recovery log line) is never invalidated.
- **D-04:** (BKUP-02, locked) A pruning failure is logged and never blocks startup or the migration attempt.
- **D-05:** The bound is proven by a test with three or more (e.g. 5+) consecutive failed attempts from the same `current` version, not just one extra attempt.

**After the upgrade succeeds**
- **D-06:** Nothing is deleted when an upgrade finally succeeds. The original plus up to 3 retry copies stay on disk; the cap only acts while attempts keep failing. No new delete step on the success path.
- **D-07:** Backups from earlier, already-completed upgrades (other `v{N}` versions) are never touched. Pruning is scoped to the timestamped siblings of the current `v{current}` only. Files whose names don't match the exact timestamped pattern (e.g. user-made copies) are never deleted.

**Logging**
- **D-08:** Each deleted retry backup gets one info-level log line naming the file, stating that the original and the 3 most recent are kept.
- **D-09:** A failed deletion logs one warning-level line naming the backup file and the system reason (exception type / OS reason, redacted by the existing sink); startup continues. Not error level, so it is not mistaken for the migration failure that caused the crash loop.

**Telemetry documentation**
- **D-10:** The note goes in README.md, Configuration Reference, directly after the existing "Startup-level environment variables such as `TRIGGARR_CONFIG_DIR`..." paragraph. No new section.
- **D-11:** Wording conveys both points: Triggarr does not support OpenTelemetry export; setting `FASTAPI_OTEL_AUTO_CONFIGURE` or an OTLP endpoint does not stop Triggarr from starting, but nothing is exported.

**Telemetry regression test**
- **D-12:** An in-process pytest test in this phase only: start the real app (lifespan) with `FASTAPI_OTEL_AUTO_CONFIGURE` and an OTLP endpoint set via `monkeypatch.setenv` (never raw `os.environ`), assert startup completes and `/health` responds. Assert the outcome, never FastAPI's internal warning wording (Pitfall 11). No built-image check in this phase.

### Claude's Discretion
- Where the pruning helper lives (inside `run_migrations` or a small private helper in `db.py`) and how timestamps are parsed.
- Exact wording of the D-08/D-09 log lines and D-11 README sentence, within the constraints above.
- Which OTLP endpoint variable(s) the test sets (e.g. `OTEL_EXPORTER_OTLP_ENDPOINT`) and what value the variable takes, as long as the configuration that originally crashed (SA-12) is reproduced.
- Test structure and fixtures, following existing patterns in `tests/test_db.py` and `tests/test_scheduler.py`.

### Deferred Ideas (OUT OF SCOPE)
- Cleaning up backups from earlier, already-completed upgrades (one file per past schema upgrade, never deleted today). Owner chose to leave them alone; not added to the backlog.
- Built-image proof that the telemetry variables don't break startup: Phase 92's built-image smoke checks could set these variables too, if wanted then (not committed scope).
</user_constraints>

## Project Constraints (from CLAUDE.md)

- Python 3.11+ (Docker image runs 3.13); ruff `select = ["E", "F", "I", "UP", "B", "SIM"]`, line length 120.
- Loguru only for logging, through the project's existing redacting sink — never `print`/stdlib `logging`.
- Atomic file writes (write-then-rename) for config and state. (Not directly applicable to backup *deletion*, but the existing temp-file-then-`os.replace` pattern in `state.py`/`config.py` is the project's house style for any new filesystem-mutation code in this area.)
- `pytest-asyncio` with `asyncio_mode = "auto"` (`pyproject.toml:43`) — async test functions need no `@pytest.mark.asyncio` decorator.
- Each fix lands with a regression test that fails on the unfixed code (repeated as D-01 above and as a milestone-wide rule in `REQUIREMENTS.md`).
- One PR per phase, paired BM + Codex review; no docs-only PRs (README change rides in this phase's PR, not separately).
- `/deep-review` offered before pushing to main or tagging a release (not before this phase's own PR, which follows the standard per-PR review classification).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Backup pruning (BKUP-01/02) | Database / Storage | — | Pure filesystem + SQLite-schema-version logic inside `db.py::run_migrations`; no HTTP, no UI |
| Telemetry regression test (TELEM-01) | API / Backend | Browser/Client (none) | Exercises FastAPI's own ASGI lifespan dispatch and ships-with-the-process behavior; no new endpoint, no UI surface |
| Telemetry documentation (TELEM-02) | Docs (N/A tier) | — | README.md text only; no code tier owns it |

This phase touches no browser/client code, no SSR, no CDN/static tier, and adds no new route. Both capabilities are single-tier, backend-only changes — there is no cross-tier task-assignment risk to flag here.

## Standard Stack

No new dependency, runtime or dev. Per D-01 and `.planning/research/STACK.md` ("What NOT to Add"), this phase explicitly must not add a backup-rotation package or any OpenTelemetry SDK/exporter package. Everything needed is already in the stdlib or already a transitive dependency:

| Facility | Already present? | Purpose in this phase |
|----------|-------------------|------------------------|
| `pathlib.Path` (stdlib) | Yes — used throughout `db.py` | Enumerate and delete backup files |
| `re` (stdlib) | Yes — already imported in `db.py:13` | Strict filename-pattern match before deletion (never a loose glob) |
| `shutil` (stdlib) | Yes — already imported in `db.py:14`, used for `copy2` | Unchanged; backups are still written the same way |
| `loguru` (`from loguru import logger`) | Yes — already imported in `db.py:23` | D-08/D-09 log lines |
| `fastapi.testclient.TestClient` | Yes — already used 10+ places across `tests/test_web.py`, `tests/test_attribution_disclosure.py` | Drives the real ASGI lifespan for the TELEM-01 regression test |
| `pytest.monkeypatch` | Yes — already the project's env-var-test convention (`tests/test_scheduler.py`'s drain-timeout tests) | Sets `FASTAPI_OTEL_AUTO_CONFIGURE`/OTLP env vars without leaking into later tests |
| `opentelemetry-api` | Already present, transitively, via `fastapi` (not chosen by Triggarr) | Nothing to do — this stays the inert, non-exporting package it already is; do not add `opentelemetry-sdk` or any `opentelemetry-exporter-otlp-*` package |

**Installation:** none — no `uv add`/`pip install` step for this phase.

**Version verification:**
```
$ uv run python -c "import fastapi; print(fastapi.__version__)"
0.162.4
```
Confirmed against the installed venv (matches `.planning/research/STACK.md`'s pinned-version table; no version bump needed or proposed by this phase).

### Alternatives Considered

| Instead of | Could use | Tradeoff |
|------------|-----------|----------|
| stdlib `pathlib.Path.glob` + regex filter + `Path.unlink` | A Python log-rotation package | Rejected per D-01/STACK.md — a handful of same-directory files is not a log-rotation problem, and the project already copies backups with stdlib `shutil.copy2` |
| Assert `/health` responds (outcome-based) | Assert FastAPI's internal log string (`"FastAPI automatic telemetry configuration failed: ..."`) | Rejected per D-12/Pitfall 11 — couples the test to third-party wording that can change on a FastAPI patch bump for reasons unrelated to Triggarr |

## Package Legitimacy Audit

Not applicable. This phase installs no new package (runtime or dev) per D-01 and the milestone standing rule in `REQUIREMENTS.md` ("No new runtime dependency"). The Package Legitimacy Gate protocol (slopcheck, registry verification) is skipped because there is nothing to verify — every facility used is already in `uv.lock` or the stdlib, confirmed by direct inspection above.

## Architecture Patterns

### System Architecture Diagram

```
Container restart (crash-looping failed upgrade)
        |
        v
triggarr/__main__.py::_run()  -->  startup()  -->  create_lifespan(settings, state_path, config_path)
        |
        v
create_lifespan's async generator (triggarr/search/scheduler.py:479+)
        |
        v
aiosqlite.connect(db_path)  -->  init_db(db, db_path)  -->  run_migrations(db, db_path)
                                                                   |
                                               current = get_schema_version(db)   [e.g. v9, target v10]
                                                                   |
                                        backup_path = db_path.with_suffix(".v9-backup")
                                                                   |
                                  +---- backup_path missing? ----+----- backup_path exists? -----+
                                  |  (first attempt from v9)     |   (2nd+ attempt from v9)      |
                                  v                               v                                |
                     shutil.copy2 -> canonical backup      shutil.copy2 -> NEW timestamped backup
                     earliest_backup = backup_path         earliest_backup = backup_path (unchanged)
                                                                   |
                                                    [NEW] prune_timestamped_backups(db_path, current)
                                                     - glob siblings matching the current version only
                                                     - regex-validate the exact %Y%m%dT%H%M%S%fZ pattern
                                                     - keep newest 3, delete the rest
                                                     - log one info line per deletion (D-08)
                                                     - on OSError: log one warning, continue (D-09)
                                                                   |
                                                                   v
                                        migration fn(db) runs for v10  --(raises)-->  rollback, re-raise,
                                                                                        logger.error cites
                                                                                        earliest_backup
                                                                   |
                                                       process exits  -->  restart policy calls run_migrations again
                                                       (loop repeats; backup count stays bounded at <= 4 files)

Startup regression test (TELEM-01), no container involved:
monkeypatch.setenv(FASTAPI_OTEL_AUTO_CONFIGURE=true, OTLP endpoint)   [BEFORE FastAPI() is constructed]
        |
        v
app = FastAPI(lifespan=create_lifespan(...))   # reads env var into self._telemetry HERE
app.include_router(router)                      # so /health exists
        |
        v
with TestClient(app) as client:                 # drives REAL ASGI "lifespan" scope
        |                                         # FastAPI.__call__ intercepts scope["type"]=="lifespan"
        v                                         # BEFORE delegating to our lifespan function
fastapi/telemetry/_runtime.py::lifespan()        # tries _configure_from_environment(); catches
        |                                         # its own exception; logs a warning; never raises
        v
Starlette's Router.lifespan  -->  our create_lifespan's async generator runs normally
        |
        v
client.get("/health")  -->  200 {"status": "ok"}   # proves startup + request-serving both survived
```

### Recommended Project Structure

No new files or directories. Both changes land inside existing modules:
```
triggarr/
├── db.py                  # add a private pruning helper near run_migrations (~line 172-236)
tests/
├── test_db.py             # extend with the multi-attempt bound test (near test_backup_created_on_migration, line 383)
└── test_scheduler.py (or a new tests/test_telemetry.py)  # TELEM-01 regression test
README.md                  # one sentence after line 213, before "## Screenshots"
```

### Pattern 1: Scoped, pattern-strict filename pruning (BKUP-01/02)

**What:** Enumerate only the timestamped siblings of the *current* schema version, validate each candidate against the exact timestamp format before treating it as prunable, sort by the parsed/embedded timestamp (never mtime), delete all but the newest 3.

**When to use:** Immediately after the `shutil.copy2(db_path, timestamped_path)` call in `run_migrations`'s "already exists" branch — never in the canonical-backup branch (there is nothing to prune there), and never after the migration loop (pruning must happen before `earliest_backup`'s value could be invalidated by the very same call that's using it for the error-log line — but since `earliest_backup` is always the canonical path, which is never prunable, this ordering constraint is satisfied by construction as long as the canonical file is never a deletion candidate).

**Example (new code, not yet in `db.py`):**
```python
# Source: pattern derived from the existing stamp format already in run_migrations
# (db.py:207, "%Y%m%dT%H%M%S%fZ") and the existing try/except-log-continue
# convention used for filesystem cleanup elsewhere in this project
# (triggarr/state.py:254-271, triggarr/config.py's temp-file unlink sites).

_BACKUP_STAMP_RE = re.compile(r"^\d{8}T\d{6}\d{6}Z$")  # matches datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
_MAX_RETAINED_TIMESTAMPED_BACKUPS = 3


def _prune_timestamped_backups(db_path: Path, current: int) -> None:
    """Keep only the N most recent timestamped retry backups for `current` (D-01..D-09).

    Never touches the canonical ``.v{current}-backup`` file (no suffix) --
    only files matching the exact ``.v{current}-backup-{stamp}`` pattern are
    even considered, so a user-made copy or a backup from a different
    schema version is never a candidate (D-07). A failed deletion is
    logged at warning level and does not stop the migration attempt (D-04/D-09).
    """
    prefix = f"{db_path.stem}.v{current}-backup-"
    candidates: list[tuple[str, Path]] = []
    for candidate in db_path.parent.glob(f"{db_path.stem}.v{current}-backup-*"):
        stamp = candidate.name.removeprefix(prefix)
        if _BACKUP_STAMP_RE.match(stamp):
            candidates.append((stamp, candidate))

    # Lexicographic sort on the stamp string is chronological: the format is
    # fixed-width (%Y%m%dT%H%M%S%fZ), so string order == time order. This is
    # the "order by parsed filename timestamp" D-03 requires -- never
    # Path.stat().st_mtime, which shutil.copy2 sets to the *source db's*
    # mtime, not the backup's creation time (research PITFALLS.md Pitfall 9).
    candidates.sort(key=lambda pair: pair[0], reverse=True)

    for _stamp, stale_path in candidates[_MAX_RETAINED_TIMESTAMPED_BACKUPS:]:
        try:
            stale_path.unlink(missing_ok=True)
            logger.info(
                "Pruned old retry backup {path} (keeping the original and the "
                "{n} most recent)",
                path=stale_path,
                n=_MAX_RETAINED_TIMESTAMPED_BACKUPS,
            )
        except OSError as exc:
            logger.warning(
                "Could not prune retry backup {path}: {exc}",
                path=stale_path,
                exc=f"{type(exc).__name__}: {exc}",
            )
```

Call site (inside `run_migrations`, right after the existing `logger.info("Database backed up to {path} ...")` line in the "already exists" branch, ~`db.py:214`):
```python
            logger.info(
                "Database backed up to {path} (earlier backup preserved at {earlier})",
                path=timestamped_path,
                earlier=backup_path,
            )
            earliest_backup = backup_path
            _prune_timestamped_backups(db_path, current)
```

### Pattern 2: Real ASGI lifespan dispatch for a FastAPI-internal-behavior regression test (TELEM-01)

**What:** Build the app with `create_lifespan`, include the router so `/health` resolves, set the env vars via `monkeypatch.setenv` *before* constructing `FastAPI(...)`, then drive it with `with TestClient(app) as client:` so the real ASGI `"lifespan"` protocol scope runs (not a direct call to the lifespan context manager).

**When to use:** Any regression test whose subject is behavior FastAPI itself wires into `FastAPI.__call__` (telemetry auto-configure, and by extension anything else FastAPI intercepts at the ASGI layer before delegating to the app's own `lifespan=`) — `async with lifespan_fn(app):`, the pattern `tests/test_scheduler.py` otherwise uses pervasively, is correct for testing *Triggarr's own* startup/shutdown code, but provably wrong for this specific regression.

**Verified by direct experiment** (run against this repo's installed `fastapi==0.162.4`, 2026-11-16):
```python
# Source: experiment run directly against the installed fastapi/telemetry/_runtime.py
# and fastapi/applications.py in .venv/lib/python3.11/site-packages/fastapi/

# Form A -- calling the lifespan context manager directly (test_scheduler.py's
# usual pattern). This does NOT exercise FastAPI's telemetry wrapper at all,
# because FastAPI.__call__ -- not the lifespan function itself -- is what
# intercepts scope["type"] == "lifespan" and runs
# fastapi/telemetry/_runtime.py::lifespan() before delegating onward.
async def direct():
    async with noop_lifespan(app):
        pass  # completes silently; FASTAPI_OTEL_AUTO_CONFIGURE is never read here

# Form B -- the real ASGI dispatch. This DOES exercise it:
with TestClient(app) as client:
    r = client.get("/health")
# Observed stderr: "FastAPI automatic telemetry configuration failed:
# Automatic OpenTelemetry export requires fastapi[opentelemetry] or
# fastapi[standard]. ..." -- proving the real code path ran, caught its own
# error, logged a warning, and did NOT crash startup. r.status_code == 200.
```

**Critical ordering detail, also verified by reading `fastapi/applications.py:1011-1023` directly:** `auto_configure` is computed from `os.getenv("FASTAPI_OTEL_AUTO_CONFIGURE", "")` inside `FastAPI.__init__` itself, not at request time or at lifespan-startup time. If the env var is set *after* `app = FastAPI(lifespan=...)` has already run, the test proves nothing — the `TelemetryConfig` dict was already frozen with `auto_configure=False`. `OTEL_EXPORTER_OTLP_ENDPOINT` (read inside `_configure_from_environment`, which runs at actual lifespan-startup time) does not have this constraint, but for test clarity and robustness against future FastAPI versions, set both env vars before constructing `FastAPI(...)`.

**Example test shape:**
```python
# Source: pattern combining tests/test_scheduler.py's create_lifespan usage
# (e.g. test_shutdown_drains_search_lock, line ~974) with
# tests/test_attribution_disclosure.py's TestClient-as-context-manager usage
# (line ~111), adapted for this capability.

async def test_telemetry_env_vars_do_not_crash_startup(tmp_path, monkeypatch):
    """TELEM-01: FASTAPI_OTEL_AUTO_CONFIGURE + an OTLP endpoint must never crash startup."""
    # Must be set BEFORE FastAPI(...) is constructed -- auto_configure is
    # read from the environment at __init__ time, not at request time.
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

### Anti-Patterns to Avoid

- **Asserting FastAPI's internal warning string as the pass condition** (Pitfall 11): couples the test to wording FastAPI can change on a patch release for reasons unrelated to Triggarr. Assert the outcome (`/health` responds, no exception) instead.
- **Using `async with lifespan_fn(app):` for the telemetry test**: silently tests nothing — see Pattern 2 above. This is new, verified-in-this-session information not present in `.planning/research/PITFALLS.md`'s existing Pitfall 11, which focuses on wording/env-leakage, not on which invocation form actually reaches the FastAPI code under test.
- **Loose glob + oldest-by-mtime pruning** (Pitfall 9, already documented): `shutil.copy2` preserves the *source* db's mtime on every backup copy, so backups taken seconds apart during a crash loop can have colliding or non-monotonic mtimes. Always sort by the embedded filename timestamp.
- **A glob pattern without the trailing regex validation**: `db_path.parent.glob(f"{db_path.stem}.v{current}-backup-*")` alone would also match a hypothetical future naming variant or a manually renamed file ending in the right prefix but an unexpected suffix. The regex check on the extracted stamp is what satisfies D-07's "never delete a file that doesn't match the exact pattern."

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bounding a small set of same-directory backup files | A rotation/retention library | `pathlib.Path.glob` + regex filter + sort + `Path.unlink(missing_ok=True)` | A handful of files in one directory is not a log-rotation problem; the project already has an equivalent bounded-retention pattern for DB rows (`insert_search_entry`'s `DELETE ... WHERE id NOT IN (... ORDER BY id DESC LIMIT ?)`, `db.py:797-812`) to mirror in spirit |
| Proving telemetry doesn't crash startup | A hand-rolled OTel SDK/exporter stub, or mocking `fastapi.telemetry` internals | The real `FastAPI()` + real env vars + `TestClient` | FastAPI 0.162.4 already handles this correctly; the test's job is to pin that behavior against regression, not to simulate it |

**Key insight:** Both halves of this phase are "add a guard around behavior that's already correct in its happy path" — not new mechanisms. The temptation to over-build (a backup-rotation abstraction, a telemetry test harness) would be strictly more code than the problem needs, and would risk missing the one real constraint in each case (never delete the canonical backup; exercise the real ASGI lifespan, not a shortcut).

## Common Pitfalls

### Pitfall 1 (project research: PITFALLS.md Pitfall 9): Pruning by mtime, or pruning across versions
**What goes wrong:** A prune implementation that globs `*.v{N}-backup*` across all `N` and deletes oldest-by-`os.path.getmtime` can delete the canonical backup for an in-progress recovery, because `shutil.copy2` makes every backup's mtime equal to the *source database's* mtime at copy time, not the copy's own creation time.
**Why it happens:** `Path.stat().st_mtime` looks like the obvious sort key and is shorter to write than a regex-filtered, filename-based sort.
**How to avoid:** Sort on the stamp embedded in the filename (lexicographic sort on the fixed-width `%Y%m%dT%H%M%S%fZ` string is already chronological); scope the glob to the current version only; never touch the no-suffix canonical file.
**Warning signs:** Any `key=os.path.getmtime` or `key=lambda p: p.stat().st_mtime` near backup-pruning code.

### Pitfall 2 (new to this session): Telemetry test invoking the wrong lifespan entry point
**What goes wrong:** A test using `async with lifespan_fn(app):` directly (the pattern used throughout `tests/test_scheduler.py` for Triggarr's own lifespan behavior) never reaches `fastapi/telemetry/_runtime.py::lifespan()`, because that function is invoked from inside `FastAPI.__call__` when it sees `scope["type"] == "lifespan"` — not from inside Triggarr's own `create_lifespan` generator. The test passes unconditionally, proving nothing about the FastAPI-level behavior it's meant to pin.
**Why it happens:** It's the existing, idiomatic pattern everywhere else in this test suite for lifespan-related tests, and it reads as "drives the lifespan" even though it bypasses the ASGI dispatch layer where the regression actually lives.
**How to avoid:** Use `with TestClient(app) as client:` (or an equivalent full ASGI dispatch, e.g. a real `uvicorn.Server`) so `FastAPI.__call__` itself runs. See Pattern 2 above, including the direct-experiment evidence.
**Warning signs:** A new telemetry test that imports `create_lifespan` but never imports or uses `TestClient`.

### Pitfall 3 (new to this session): Setting the env var after `FastAPI()` is already constructed
**What goes wrong:** `auto_configure` is computed once, inside `FastAPI.__init__`, from `os.getenv("FASTAPI_OTEL_AUTO_CONFIGURE", "")`. If a fixture builds `app = FastAPI(...)` before the test's `monkeypatch.setenv(...)` call runs (e.g. a module-scoped or earlier-constructed app fixture reused across tests), the env var has no effect and the test silently validates nothing.
**Why it happens:** Most of this project's other env-var tests (e.g. `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT`) are read at call-time inside Triggarr's own code, not at FastAPI-construction time, so the "set env var, then act" ordering is usually safe without needing to think about it. FastAPI's `auto_configure` default is the exception.
**How to avoid:** Call `monkeypatch.setenv` before `FastAPI(lifespan=...)` is constructed, inside the test function itself — don't rely on a shared app fixture built outside the test.
**Warning signs:** A test-level `app` parameter coming from a `@pytest.fixture` that constructs `FastAPI(...)` without taking `monkeypatch` as a dependency.

### Pitfall 4 (carried from project research: PITFALLS.md Pitfall 11): Pinning FastAPI's internal wording or leaking env state
**What goes wrong:** Asserting on the literal string `"FastAPI automatic telemetry configuration failed: ..."` ties the test to third-party wording; a raw `os.environ[...] = ...` assignment instead of `monkeypatch.setenv` leaks into later tests in the same pytest process.
**How to avoid:** Already covered by D-12 and Pattern 2/the example test above — assert the outcome, use `monkeypatch`.

## Code Examples

### Existing precedent for the warning-on-failed-cleanup, try/except/continue shape (Phase 87, merged, directly reusable style)
```python
# Source: triggarr/state.py:254-271 (merged Phase 87 code, read directly from
# the current working tree) -- the closest existing precedent named in
# 88-CONTEXT.md's canonical_refs for D-08/D-09's "set-aside" pattern.
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
The new `_prune_timestamped_backups` helper (Pattern 1 above) follows the same shape: try the filesystem operation, catch `OSError` specifically, log at `warning` level with the path and `f"{type(exc).__name__}: {exc}"`, and continue (never re-raise, never block the caller).

### Existing precedent for bounded-retention-by-count (different resource, same shape)
```python
# Source: triggarr/db.py:797-812 (existing, unmodified by this phase) --
# the DB-row equivalent of what this phase builds for files.
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

### Simulating a multi-attempt crash loop for the BKUP test (D-05)
```python
# Source: pattern adapted from tests/migration_faults.py's existing
# monkeypatch.delitem(MIGRATIONS, 10) / restore convention (lines ~41-58),
# which already proves MIGRATIONS is a plain module-level dict safe to
# monkeypatch per-test.

async def test_backup_bound_holds_through_repeated_failed_attempts(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)  # migrates to the latest version cleanly first
    current = await get_schema_version(db)

    def _always_fails(db):
        raise RuntimeError("simulated migration failure")

    next_version = current + 1
    monkeypatch.setitem(MIGRATIONS, next_version, ("simulated failure", _always_fails))
    # ... extend MIGRATIONS' effective target past `current` for this test,
    # or seed a fresh db at a known version and patch its very next migration.
    # (Exact harness shape is Claude's discretion per 88-CONTEXT.md; the
    # constraint to prove is: after 5+ consecutive calls to run_migrations
    # that each raise, exactly 1 canonical + <=3 timestamped backups exist,
    # and the canonical file is byte-identical to the pre-migration db.)
    for _ in range(5):
        with pytest.raises(RuntimeError):
            await run_migrations(db, db_path)

    canonical = db_path.with_suffix(f".v{current}-backup")
    timestamped = sorted(db_path.parent.glob(f"{db_path.stem}.v{current}-backup-*"))
    assert canonical.exists()
    assert len(timestamped) <= 3
```
Note: the worked numeric example in `88-CONTEXT.md` ("fails 5 times, succeeds on try 6" -> 4 files total) was reconciled against the actual code path in this research session: `run_migrations` takes a backup (canonical or timestamped) on *every* call where `current < target`, including the call that goes on to succeed — so the 6th (successful) attempt also writes and prunes a backup before its migration function runs. Final state: canonical + the 3 most recent timestamped backups = 4 files, matching the context doc exactly.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| FastAPI silently crashing (or being assumed to crash) on `FASTAPI_OTEL_AUTO_CONFIGURE` + a missing OTel SDK/exporter | FastAPI 0.143.0+ (confirmed still true at the pinned 0.162.4) catches its own auto-configure failure and logs a warning instead of raising | FastAPI PR #16476, 8 Oct 2026 per `.planning/research/STACK.md`; independently re-confirmed in this session by reading the installed `fastapi/telemetry/_runtime.py` source directly | SA-12 (the original concern that motivated TELEM-01/02) was already fixed upstream before this milestone started; this phase adds only a regression test and a doc note, no code fix |

**Deprecated/outdated:** None relevant to this phase — the backup-pruning gap and the telemetry concern are both freshly-scoped, not legacy code being replaced.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | No existing test or fixture currently sets `FASTAPI_OTEL_AUTO_CONFIGURE` or any `OTEL_*` variable anywhere in the test suite (confirmed by `grep` across `triggarr/`, `README.md`, `docs/` returning zero hits before this phase) | Standard Stack, Code Examples | Low — grep is exhaustive for this; if wrong, the new test would collide with an existing one, which pytest would surface immediately as a failure, not a silent gap |
| A2 | The `update_check` APScheduler job (`scheduler.py:654-667`, `next_run_time=datetime.now(UTC)`) firing an immediate, real DNS/network lookup during any lifespan-based test (including the new TELEM-01 test) is pre-existing, already-tolerated noise, not a new problem this phase introduces | Architecture Patterns, Code Examples | Low — verified directly by running the real lifespan in this session; the resulting `CancelledError` is logged via the existing `_on_job_error` handler and does not fail the test or need silencing for this phase to pass. If a future reviewer wants it silenced, that's a pre-existing, cross-cutting test-noise cleanup, not a BKUP/TELEM-01 scope item |

**If this table is empty:** N/A — both entries above are informational/low-risk confirmations verified directly in this session (by grep and by running real code against the installed dependencies), not unverified guesses. Nothing in this research needs owner confirmation before planning proceeds.

## Open Questions

None blocking. Both capabilities are fully scoped by `88-CONTEXT.md`'s locked decisions plus this research's verification of the exact FastAPI internals. The only latitude left is explicitly delegated to "Claude's Discretion" in CONTEXT.md (helper placement, exact log/README wording, which OTLP variable(s), test file placement) and does not require research to resolve further.

## Environment Availability

No external tool, service, or runtime dependency beyond what's already installed is needed for this phase (no Docker build, no network service, no new CLI). Skipping this section's table per the stated skip condition — this is a code/config-only phase (filesystem + an in-process pytest regression test).

## Validation Architecture

`workflow.nyquist_validation` is absent from `.planning/config.json` (treated as enabled); `workflow.tdd_mode` is explicitly `true`.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (`asyncio_mode = "auto"`), per `pyproject.toml:42-43` |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, line 42) |
| Quick run command | `uv run pytest tests/test_db.py -x -q` (BKUP), `uv run pytest tests/test_scheduler.py -k telemetry -x -q` or the new telemetry test file, once named |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|-------------|
| BKUP-01 | After 5+ consecutive failed upgrade attempts from the same `current`, at most 4 backup files exist (1 canonical + <=3 timestamped) | unit | `uv run pytest tests/test_db.py::test_backup_bound_holds_through_repeated_failed_attempts -x` | ❌ Wave 0 — new test, extends `tests/test_db.py` |
| BKUP-02 | Pruning never deletes the canonical file or the just-written backup; order is by filename timestamp; a failed delete logs a warning and does not block startup | unit | same test as above, plus a dedicated failed-delete test (e.g. `monkeypatch`-ing `Path.unlink` to raise `OSError` once) | ❌ Wave 0 — new, same file |
| TELEM-01 | Startup completes and `/health` responds with `FASTAPI_OTEL_AUTO_CONFIGURE` + an OTLP endpoint set | integration (real ASGI lifespan via `TestClient`) | `uv run pytest tests/test_scheduler.py::test_telemetry_env_vars_do_not_crash_startup -x` (or the chosen new file) | ❌ Wave 0 — new test |
| TELEM-02 | README states telemetry export is unsupported | manual-only (documentation) | N/A — reviewed as part of the phase's PR diff, not an automated test | ✅ README.md exists; one sentence inserted |

### Sampling Rate
- **Per task commit:** the quick run command for the file just touched (`tests/test_db.py` or the telemetry test file).
- **Per wave merge:** `uv run pytest tests/ -x -q` (full suite) plus `uv run ruff check triggarr/ tests/`.
- **Phase gate:** Full suite green before `/bm:verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_db.py` — new test(s) covering BKUP-01/BKUP-02 (extends existing `test_backup_created_on_migration`, line 383, and `test_run_migrations_fresh_install`, line 1082 — no new fixture file needed, `_init_test_db` at line 38 is reusable).
- [ ] A telemetry regression test file or section — either a new `tests/test_telemetry.py` or a new section appended to `tests/test_scheduler.py` (Claude's Discretion per CONTEXT.md). No shared fixture gap: `make_settings` (`tests/conftest.py:39`) and `router`/`STATIC_DIR` (`triggarr/web/routes.py`) are already importable and already used together in `tests/test_attribution_disclosure.py`.
- [ ] No framework install needed — pytest, pytest-asyncio, and `fastapi.testclient.TestClient` are all already present and already used in this exact combination elsewhere in the suite.

## Security Domain

`security_enforcement` is absent from config (treated as enabled).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V7 Error Handling and Logging | Yes | D-08/D-09 log lines name the file and `type(exc).__name__: exc` only, through the project's existing loguru redacting sink — matches the established `state.py`/`config.py` convention of never logging raw internal paths differently from what's already logged elsewhere, and never logging secrets (none are present in this code path) |
| V12 File and Resource Handling | Yes | All paths pruned are derived internally from `db_path` (a trusted, process-configured path) and an `int` schema version read from `schema_version` in the app's own SQLite database — never from user/HTTP input. The strict regex match before any `unlink()` call (Pattern 1) prevents the helper from ever deleting a file outside the exact `<db>.v{current}-backup-{stamp}` shape, which is the relevant control here (no path traversal surface exists, since nothing is interpolated from untrusted input, but the regex gate is still the correct defense-in-depth per D-07) |
| V2/V3/V4 Authentication/Session/Access Control | No | This phase touches no auth, session, or request-authorization code path |
| V5 Input Validation | No (not in the HTTP-input sense) | No new HTTP input is accepted by either capability; the only "input" is internally-generated filenames, handled per V12 above |
| V6 Cryptography | No | No cryptographic operation is introduced or changed |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Deleting the wrong file via an overly permissive glob (here: accidentally matching a different version's backup or a user-made copy) | Tampering (of backup/recovery data, self-inflicted) | Strict regex validation of the parsed stamp before any `unlink()` (Pattern 1); scope the glob to `current` only (D-07) |
| A telemetry test that passes without proving anything (Pitfall 2 above) | Not STRIDE — a test-integrity gap, not a security vulnerability, but it directly undermines TELEM-01's purpose as a regression guard | Use the real ASGI dispatch (`TestClient` context manager), confirmed necessary by direct experiment in this session |

## Sources

### Primary (HIGH confidence)
- `triggarr/db.py:172-236` (current working tree) — `run_migrations`, the existing canonical/timestamped backup logic this phase extends
- `triggarr/state.py:229-281` (current working tree, Phase 87, merged) — the set-aside/warning-and-continue precedent named in `88-CONTEXT.md`'s canonical_refs
- `tests/test_db.py:38-44, 383-388, 1082-1107`, `tests/migration_faults.py:1-58` (current working tree) — existing backup test and `MIGRATIONS`-monkeypatching conventions
- `tests/test_scheduler.py:974-1177` (current working tree) — `create_lifespan` + `async with lifespan_fn(app):` convention, and the `monkeypatch.setenv` env-var-test convention
- `tests/test_attribution_disclosure.py:1-92, 111` (current working tree) — `TestClient(app) as client:` + `router` + `create_lifespan`-adjacent fixture convention
- `.venv/lib/python3.11/site-packages/fastapi/telemetry/_runtime.py` (installed fastapi 0.162.4, read directly in full) — confirms the try/except/log-warning-never-raise behavior and exactly where `_configure_from_environment` is invoked relative to the ASGI lifespan protocol
- `.venv/lib/python3.11/site-packages/fastapi/applications.py:1011-1023, 1175-1199` (installed fastapi 0.162.4, read directly) — confirms `auto_configure` is read from the environment at `FastAPI.__init__` time, and confirms `FastAPI.__call__` (not the user's own `lifespan=`) is what intercepts `scope["type"] == "lifespan"` and invokes the telemetry wrapper
- Direct experiment run in this session against the installed venv (two scripts, both executed via `uv run python`): confirmed (a) `async with lifespan_fn(app):` never triggers the telemetry warning, (b) `with TestClient(app) as client:` does, (c) the full `create_lifespan` + `router` + `TestClient` + `/health` combination returns 200 with both env vars set
- `README.md:145-215` (current working tree) — exact insertion point for TELEM-02's documentation sentence
- `pyproject.toml:42-50` — pytest/ruff configuration confirmed directly

### Secondary (MEDIUM confidence)
- None needed beyond primary sources for this phase — every claim was verifiable directly against the current working tree or the installed dependency, so no WebSearch-sourced claim is carried into this document.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependency; every facility's presence confirmed by direct source read.
- Architecture: HIGH — both call sites and the exact FastAPI internals were read directly from the working tree and the installed venv, not inferred.
- Pitfalls: HIGH — Pitfall 1 inherited from existing, already-verified project research; Pitfalls 2-3 are new findings in this session, verified by running real code against the pinned dependency versions, not by inference.

**Research date:** 2026-11-16
**Valid until:** 30 days (stable domain: internal filesystem logic and a pinned, already-fixed third-party dependency; re-verify if `fastapi` or `aiosqlite` versions bump before this phase executes)
