# Phase 90: Removed-Instance Pending-Search Lifecycle - Pattern Map

**Mapped:** 2026-11-18
**Files analyzed:** 12 (6 source/template modified, 5 test files, 1 planning-docs group)
**Analogs found:** 12 / 12 (all in-repo; line numbers are at HEAD 409d57ae, re-check before editing)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `triggarr/db.py` (shared pending predicate + constants) | model/utility | transform (SQL fragments) | `_LEGACY_MAX_ID_SQL` / `_LEGACY_PENDING_SQL` (db.py 815-827) | exact |
| `triggarr/db.py` `close_out_removed_instance_searches` | service | CRUD (batch UPDATE) | `update_outcome_and_stats` (db.py ~1306-1380) | exact |
| `triggarr/db.py` `close_out_orphaned_pending_searches` | service | batch | `update_outcome_and_stats` + `ensure_cutover_recorded` (`triggarr/attribution.py`) | role-match |
| `triggarr/db.py` cap, prune, `get_trackable_entries`, `get_dashboard_stats` edits | model | CRUD | the same functions (replace copies with shared constant); `NOT _LEGACY_PENDING_SQL` use | exact |
| `triggarr/tracking.py` Radarr/Lidarr stable-ID selection | service | request-response | `_run_sonarr_tracking_check` (tracking.py 522-560) | exact |
| `triggarr/web/routes.py` `remove_instance` close-out step | controller | request-response | scheduler-job isolated try/except in the same function (routes.py ~1206-1216) | exact |
| `triggarr/search/scheduler.py` `create_lifespan` sweep call | provider | event-driven (startup) | `ensure_cutover_recorded` call (scheduler.py ~720-728) | exact |
| `triggarr/templates/partials/history_results.html` | component | request-response | the `is_legacy` branches in the same file (82-104, 145-158) | exact |
| `triggarr/templates/partials/activity_rail.html` | component | request-response | `is_legacy` dot/pill branches (32-44, 77-89) | exact |
| `tests/test_db.py` | test | CRUD | `_insert_cutover` + legacy tests (test_db.py ~1925-1950) | exact |
| `tests/test_tracking.py` | test | CRUD | `_insert_entry` (64-95) + 5 name-reuse tests (1304-1420) to rewrite | exact |
| `tests/test_web.py` (remove route + History/rail) | test | request-response | `multi_instance_app` fixture (1061) and remove tests (1484-1923) | exact |
| `tests/test_scheduler.py` (sweep ordering/failure) | test | event-driven | `test_lifespan_records_attribution_cutover_once` (1975) and `test_lifespan_cutover_after_init_db` (~2008) | exact |
| `.planning/REQUIREMENTS.md`, `ROADMAP.md`, `CHANGELOG.md` | config/docs | n/a | follow `docs/PLANNING-FORMAT.md`; check `tests/test_changelog.py` rules | role-match |

## Pattern Assignments

### `triggarr/db.py` shared pending predicate (model/utility)

**Analog:** `_LEGACY_PENDING_SQL`, db.py 822-827. The existing precedent builds SQL fragments as module constants and composes them with string concatenation:
```python
_LEGACY_MAX_ID_SQL = "COALESCE((SELECT legacy_max_history_id FROM attribution_cutover WHERE id = 1), 0)"
_LEGACY_PENDING_SQL = (
    "(app = 'Sonarr' AND COALESCE(outcome, 'searched') IN ('searched', 'partial') AND id <= "
    + _LEGACY_MAX_ID_SQL
    + ")"
)
```
Copies to replace with the one shared constant (all currently different NULL treatment, RESEARCH section 1):
- line ~824 (inside `_LEGACY_PENDING_SQL`, COALESCE)
- cap queries 904 and 911 (`outcome IN ('searched', 'partial')`, bare, NULL not pending)
- prune DELETE 956 and 959 (`COALESCE(outcome, 'searched') NOT IN (...)`, twice)
- `get_trackable_entries` base query 1183 (bare)

Cap query pattern to keep, only swapping the predicate (db.py 902-915):
```python
cap_query = (
    "SELECT COUNT(*) FROM search_history "
    "WHERE outcome IN ('searched', 'partial') AND app = ? AND instance_stable_id = ? "
    "AND NOT " + _LEGACY_PENDING_SQL
)
```
Note `_LEGACY_PENDING_SQL` must be defined after `_PENDING_SQL`. The `instance_id = ?` (name-mode) cap branch at 911 stays as-is apart from the predicate (insert fallback when ID is falsy; not a selection path).

Stats (D-06): `get_dashboard_stats` effectiveness query ~1503-1511 and historical-flag query ~1585-1590 both use `AND NOT {_LEGACY_PENDING_SQL}`; add `AND outcome != 'instance_removed'` (use the constant) next to it in both, since `outcome != 'failed'` currently counts closed rows as misses.

---

### `triggarr/db.py` `close_out_removed_instance_searches` and `close_out_orphaned_pending_searches` (service, batch UPDATE)

**Analog:** `update_outcome_and_stats` (db.py ~1306-1380). Transaction/rollback shape to copy (single commit, guarded rollback, re-raise, then log):
```python
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")   # same ISO-Z format used elsewhere
    try:
        await db.execute(
            "UPDATE search_history SET outcome = ?, detail = ?, resolved_at = ? WHERE id = ?",
            (outcome, detail, now, history_id),
        )
        ...
        await db.commit()
    except Exception as exc:
        try:
            await db.rollback()
        except Exception as rollback_exc:
            logger.error(
                "update_outcome_and_stats rollback failed for history_id={hid}: {rollback_exc} "
                "(original: {exc_type})",
                hid=history_id, rollback_exc=rollback_exc, exc_type=type(exc).__name__,
            )
        raise
    logger.debug("Updated history_id={hid} ...", ...)
```
Why guarded rollback: shared aiosqlite connection; an open transaction would be flushed by another request's commit (R-08).

Parameterized, Legacy-excluding WHERE to use (from RESEARCH Code Examples, built on the existing `NOT _LEGACY_PENDING_SQL` idiom):
`WHERE app = ? AND instance_stable_id = ? AND {_PENDING_SQL} AND NOT {_LEGACY_PENDING_SQL}`.
Rules: return 0 on falsy stable ID (never by name, D-00c); stored app is title-case (`app_name.title()`); NULL equality needs `IS NULL` / `IS ?`, never `= NULL`.

Sweep: one transaction, single commit; select distinct pending non-Legacy `(app, instance_stable_id, instance_id)` groups, decide orphan-ness in Python against the configured `{(App, id)}` set (NULL id always orphan, RESEARCH A1), UPDATE per group; one info line with the total.

**Placement analog for the sweep's failure policy:** `ensure_cutover_recorded` is deliberately uncaught (security-relevant). The sweep is repair, so wrap `except Exception` (not BaseException), log one error, continue (RESEARCH A2).

---

### `triggarr/tracking.py` Radarr/Lidarr selection (service, request-response)

**Analog:** `_run_sonarr_tracking_check` (tracking.py 522-560): empty-ID guard then stable-ID selection.
```python
    if not instance_stable_id:
        # Never share ownership between instances: refuse to track rather
        # than risk crediting the wrong server's searches.
        pending_entries = await get_trackable_entries(db, instance_id=instance_id)
        pending_count = sum(1 for e in pending_entries if e["app"] == "Sonarr")
        logger.error(
            "Tracking[{inst}]: Sonarr instance has no stable ID yet -- skipping {count} pending entries",
            inst=instance_id, count=pending_count,
        )
        counts["errors"] += pending_count
        return counts

    entries = await get_trackable_entries(db, instance_stable_id=instance_stable_id)
    if not entries:
        logger.debug("Tracking[{inst}]: no pending entries", inst=instance_id)
        return counts
```
**Target to change (tracking.py ~123):** `entries = await get_trackable_entries(db, instance_id=instance_id)` becomes the guard above (with the app name in the log and the `e["app"] == app_name` filter) plus `get_trackable_entries(db, instance_stable_id=instance_stable_id)`.
**Crediting line ~200:** `instance_stable_id=entry["instance_stable_id"] or instance_stable_id or None` (with its "falls back to the current instance's ID" comment) simplifies to `instance_stable_id=instance_stable_id`. Update docstring at ~84-95 and `get_trackable_entries` docstring (db.py ~1154-1157).

---

### `triggarr/web/routes.py` `remove_instance` close-out (controller, request-response)

**Analog:** the isolated scheduler-job step in the same function (routes.py ~1195-1216). Copy this structure exactly, inside the `async with search_lock` block, after `request.app.state.settings = new_settings`:
```python
        # Once the write has succeeded the removal is real (D-15): every
        # remaining tidy-up step below runs regardless ... (D-16).
        request.app.state.settings = new_settings

        scheduler = request.app.state.scheduler
        job_id = f"{app_name}_{instance_name}_search"
        try:
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
        except Exception as exc:  # error boundary for post-commit cleanup (D-15, D-16)
            logger.error(
                "Removed {app}/{inst} but its scheduler job could not be removed: {exc_type}: {exc}",
                app=app_name, inst=instance_name, exc_type=type(exc).__name__, exc=exc,
            )
```
Notes for the new step: capture `removed_cfg = instances[instance_name]` before the `del updated_instances[instance_name]` at ~1080 (that builds a copy, so `instances[...]` stays readable, but capture explicitly); skip with a warning if `removed_cfg.id` is empty; call with `app=app_name.title()`; keep inside the lock (also required by `tests/audit_lock_coverage.py`); add a code comment about the known `job()` race (RESEARCH P7). Imports at routes.py top use absolute `from triggarr.db import ...` style; add the new function to that existing import.

---

### `triggarr/search/scheduler.py` `create_lifespan` sweep (provider, startup)

**Analog:** the cutover call (scheduler.py ~705-728). The sweep goes immediately after `ensure_cutover_recorded` (line ~728) and before "Create long-lived clients". Reuse the configured-ID comprehension style at 705-710 but keyed over ALL instances (not `get_enabled_instances`) and as `(App, id)` pairs:
```python
instance_stable_ids = {
    (app_type.title(), name): cfg.id
    for app_type in APP_TYPES
    for name, cfg in getattr(settings, app_type).items()
    if cfg.id
}
...
await ensure_cutover_recorded(db, {name: cfg.id for name, cfg in settings.sonarr.items()})
```
The whole block is inside the `try:` whose `except BaseException` is the Phase 89 cleanup, so a cancellation raised by the sweep is cleaned up automatically; catch only `Exception` around the sweep. Skip and log if the configured set is empty (A3).

---

### `triggarr/templates/partials/history_results.html` (component)

**Analog:** same file, Legacy handling.
Filter pills (lines 82-104): extend the list `['searched', 'grabbed', 'partial', 'unresolved', 'failed']` with `'instance_removed'`; active colour chain add `{% elif o_val == 'instance_removed' %}bg-gray-500/20 text-gray-400` (mirrors the `unresolved` line); label `{{ o_val }}` (line ~101) needs a mapping so the pill reads "Instance removed" while the query value stays `instance_removed`.

Row badge (lines 145-158), insert one `elif` in each of the three chains, after the `is_legacy` branch so the two never merge:
```jinja
{% if entry.is_legacy %}bg-gray-500/20 text-gray-400
{% elif entry.outcome == 'instance_removed' %}bg-gray-500/20 text-gray-400
...
{% if entry.is_legacy %}title="Searched before the attribution fix; outcome no longer tracked"
{% elif entry.outcome == 'instance_removed' %}title="This instance was removed before the search finished; it will not be checked again."
...
{% if entry.is_legacy %}Legacy — tracking discontinued{% elif entry.outcome == 'instance_removed' %}Instance removed{% else %}{{ 'partial' if ... }}{% endif %}
```
Server side needs no change: `get_search_history` already parameterizes any outcome value.

### `triggarr/templates/partials/activity_rail.html` (component)

**Analog:** same file. Dot chain (lines 32-44) already falls to the gray `else`; optionally add an explicit branch. Pill chain (77-89): add after the Legacy pill:
```jinja
{% elif entry.outcome == 'instance_removed' %}
<span title="This instance was removed before the search finished; it will not be checked again." class="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase bg-gray-500/10 text-gray-500 border border-gray-500/20">Instance removed</span>
```
The existing `else` pill prints the raw outcome string, so this branch is required.

---

### Tests

**`tests/test_db.py`** (analog `_insert_cutover`, ~1930; DB helper `_init_test_db(tmp_path)`):
```python
async def _insert_cutover(db, legacy_max_history_id: int) -> None:
    await db.execute(
        "INSERT INTO attribution_cutover "
        "(id, cutover_at, legacy_max_history_id, any_pre_fix_sonarr_data, pre_fix_sonarr_lifetime) "
        "VALUES (1, ?, ?, 1, 0)", ("2026-01-01T00:00:00Z", legacy_max_history_id))
    await db.commit()
```
Tests are `async def test_*(tmp_path)`: `db, db_path = await _init_test_db(tmp_path)`, insert via `insert_search_entry(db, "Sonarr", "missing", "Show A", instance_id="Main", instance_stable_id="sid-a")`, assert by raw `SELECT`, `await db.close()`. Use raw SQL to insert NULL-outcome / NULL-stable-id rows.

**`tests/test_tracking.py`** (analog `_insert_entry`, 64-95; `_init_db`, `_get_outcome`, `_get_stat`, `_grab`): signature `_insert_entry(db, *, app="Radarr", item_id=1, outcome="searched", instance_id="Default", instance_stable_id="sid-test", timestamp=None) -> int`. Rewrite the five name-reuse tests (1304 radarr, 1322 lidarr, 1342 NULL-id fallback, 1359 and 1396 real-client) so the new ID never selects/credits the old row (row stays `searched`, both stats 0). Template of the old assertion style:
```python
await run_tracking_check(db, radarr, "Radarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-new")
assert await _get_outcome(db, row_id) == "grabbed"        # becomes "searched"
assert await _get_stat(db, "Radarr", "movies_found", instance_id="Main", instance_stable_id="sid-old") == 1  # becomes 0
```

**`tests/test_web.py`** (`multi_instance_app`, 1061): real SQLite file via `init_db(db, db_path)`, `app.state.db = db`, `Settings(general=GeneralConfig(), radarr={...InstanceConfig(...)}, ...)`, mock scheduler. Instances there have empty `id`; give explicit `id="..."` on the instances under test. Drive through the real remove route (P6 casing) and a patched-to-raise close-out for the D-00b test.

**`tests/test_scheduler.py`** (`test_lifespan_records_attribution_cutover_once`, 1975; ordering test `test_lifespan_cutover_after_init_db`, ~2008): pattern is `Settings(sonarr={"Default": InstanceConfig(url=..., api_key=..., enabled=True, id="sid-sonarr")})`, `with patch("triggarr.search.scheduler.AsyncIOScheduler", return_value=_FakeScheduler()):`, `lifespan_fn = create_lifespan(settings, state_path, config_path)`, `app = FastAPI(lifespan=lifespan_fn)`, `async with lifespan_fn(app): db = app.state.db`. For ordering, patch `triggarr.search.scheduler.init_db` / `ensure_cutover_recorded` with `AsyncMock(side_effect=...)` appending to `call_order`, and patch the new sweep name the same way. Run lifespan twice for idempotency.

## Shared Patterns

### Identity by stable ID, never display name
**Source:** `_run_sonarr_tracking_check` guard (tracking.py 543-560). **Apply to:** tracking change, close-out, sweep. Empty ID means refuse and count errors or return 0.

### Post-commit tidy-up isolation
**Source:** `remove_instance` scheduler step (routes.py ~1206-1216). **Apply to:** the close-out step and the lifespan sweep (`except Exception`, log `{exc_type}: {exc}`, continue).

### Transaction + guarded rollback on the shared connection
**Source:** `update_outcome_and_stats` (db.py ~1355-1376). **Apply to:** both new db functions.

### Legacy exclusion
**Source:** `AND NOT " + _LEGACY_PENDING_SQL`. **Apply to:** close-out and sweep UPDATEs; stats exclusion for `instance_removed` is separate and explicit.

### Logging
Loguru only, `{named}` placeholders with kwargs, one info line per close-out and one for the sweep; no secrets (neighbouring steps log `exc_type` plus `exc`).

## Conventions

Derived with `gsd-tools verify conventions --derive --scope triggarr` (Python source; the JS-oriented axes are mostly not meaningful here).

| Axis | Dominant | Share | Entropy | Status |
|---|---|---|---|---|
| File-name casing | camel (module names are lowercase single words, e.g. `tracking.py`, `db.py`) | 77% | 0.61 | named contract |
| Identifier casing | none (camel 96 / Pascal 94 / CONSTANT 22; tool counts snake_case as camel) | 43% | 0.78 | contested hotspot |
| Export style | insufficient data (Python) | n/a | n/a | n/a |
| Import style | insufficient data; Python axes: absolute imports 100%, explicit (no wildcard) 100% | 100% | 0 | named contract |

Practical reading for this phase: Python is snake_case functions, `UPPER_SNAKE` module constants (`PENDING_OUTCOMES`, `OUTCOME_INSTANCE_REMOVED`), leading-underscore private SQL fragments (`_PENDING_SQL`), `from __future__ import annotations`, absolute `triggarr.*` imports, ruff E/F/I/UP/B/SIM, line length 120.

**Contested hotspots (author's choice):** the CJS<->SDK dual resolver (`bin/lib/**` is CJS `module.exports`/`require`; `sdk/src/**` is ESM `export`/`import`) is the prototype intentional-contested split: each half is internally consistent per directory and contested only repo-wide. It does not exist in this Python repo; the equivalent rule here is to match the local style of the file being edited.

## No Analog Found

None. Everything has an in-repo analog. Closest to "new": the startup orphan-sweep (no existing recurring startup data repair), covered by `ensure_cutover_recorded` for placement and `update_outcome_and_stats` for transaction shape.

## Metadata

**Analog search scope:** `triggarr/db.py`, `triggarr/tracking.py`, `triggarr/web/routes.py`, `triggarr/search/scheduler.py`, `triggarr/templates/partials/`, `tests/test_db.py`, `tests/test_tracking.py`, `tests/test_web.py`, `tests/test_scheduler.py`
**Files scanned:** 12 (targeted line ranges; 90-RESEARCH.md line numbers cross-checked)
**Pattern extraction date:** 2026-11-18
