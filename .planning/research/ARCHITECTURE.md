# Architecture Research — v2.14 Reliability (integration with existing code)

**Domain:** Hardening an existing, shipped single-process FastAPI/APScheduler daemon (Triggarr v2.12.1)
**Researched:** 2026-11-15
**Confidence:** HIGH for all six capabilities — every finding below is traced to exact file:line in the current tree (not training-data recall) and, where relevant, to an existing test that demonstrates the behavior. No web research was needed or used; this is a read-only code investigation.

This file supersedes the previous (stale, 2026-05-era) `.planning/research/ARCHITECTURE.md`. It does not describe a new system — it maps the **current control/data flow for each of the six v2.14 target capabilities**, states whether the described defect is still present, and identifies exactly what a fix would touch.

---

## 0. Orientation: the five subsystems this milestone touches

```
┌───────────────────────────────────────────────────────────────────────┐
│  triggarr/__main__.py — process entry: startup() then FastAPI(lifespan)│
├───────────────────────────────────────────────────────────────────────┤
│  triggarr/search/scheduler.py — create_lifespan() owns:               │
│    state.json load → db connect → migrations → clients → jobs → yield│
│    on exit: scheduler.shutdown → drain lock → close clients → db.close│
├───────────────────────────────────────────────────────────────────────┤
│  triggarr/web/routes.py — settings/instance CRUD, all under           │
│    app.state.search_lock; each handler: mutate settings → write TOML  │
│    → update scheduler job / client registry / state dict             │
├───────────────────────────────────────────────────────────────────────┤
│  triggarr/clients/base.py (+radarr/sonarr/lidarr.py) — one httpx      │
│    AsyncClient per instance; _request_with_retry wraps GET and POST   │
│    identically                                                        │
├───────────────────────────────────────────────────────────────────────┤
│  triggarr/db.py + triggarr/tracking.py — aiosqlite WAL connection,    │
│    migrations with backup-before-migrate, search_history pending-row │
│    tracking scoped by instance_stable_id (Sonarr) or instance_id      │
└───────────────────────────────────────────────────────────────────────┘
```

`triggarr/state.py` (state.json) and `triggarr/config.py` (triggarr.toml) are the two persisted stores; `triggarr/search/outcome.py` is the pure grading layer that both the engine and the scheduler read.

---

## 1. State/config consistency (999.9)

### 1a. Instance-removal ordering — `remove_instance`

**What the code does today** (`triggarr/web/routes.py:937-995`):

```
949  settings = request.app.state.settings          # same object app.state holds
950  instances = getattr(settings, app_name)          # the LIVE dict, not a copy
...
956  async with request.app.state.search_lock:
958      del instances[instance_name]                 # <-- mutates settings.radarr IN PLACE
960      config_path = request.app.state.config_path
962      config_dict = _settings_to_dict(settings)     # built FROM the already-mutated object
963-965  await ...run_in_executor(None, _atomic_toml_write, config_path, config_dict)
967-971  scheduler.remove_job(job_id)                  # only reached if the write didn't raise
973-975  client = clients_dict.pop(instance_name, None) # only reached if the write didn't raise
977-980  triggarr_state[app_name].pop(instance_name, None)
983      request.app.state.tag_cache.pop(...)
986-987  await client.close()                          # outside the lock
```

`settings.radarr`/`.sonarr`/`.lidarr` are plain mutable `dict[str, InstanceConfig]` fields (`triggarr/models/config.py:200-202`, no `frozen` model_config) — `instances` at line 950 is the exact dict object `app.state.settings` holds, not a snapshot. `del instances[instance_name]` at line 958 is therefore visible to every other reader of `app.state.settings` (the scheduler's `make_search_job` closures read it at call time, `triggarr/search/scheduler.py:166`) **before** the TOML write is attempted.

**Compare to every other config-mutating route**, which all follow one consistent pattern instead: build a **new** `Settings` object via `model_copy`/`SettingsModel(**dict)`, write it to disk, and only then do `request.app.state.settings = new_settings`:
- `add_instance` (`routes.py:909-927`): builds `config_dict`, validates with `SettingsModel(**config_dict)` (915-919), writes (921-926), swaps `request.app.state.settings = new_settings` only at line 927.
- General settings save (`routes.py:715-731`): "Validate BEFORE writing to disk (QUAL-02)" comment at 715; write at 727-729; swap at 731.
- First-run setup (`routes.py:1447-1454`): `updated = current_settings.model_copy(...)`; write; swap at 1454.
- Password change (`routes.py:1707-1719`): identical `model_copy` → write → swap shape.

`remove_instance` is the one outlier that mutates the live object before the write is even attempted, and it also skips the `SettingsModel(**config_dict)` re-validation step that `add_instance` performs.

**Defect status: CONFIRMED PRESENT.** If `_atomic_toml_write` raises (it re-raises OSError/any Exception after cleaning up its temp file — `triggarr/config.py:155-194`), the exception propagates out of the route past the point where `instances` was already mutated. Settings are *not* preserved (the instance is already gone from the live object); jobs, clients and the state entry happen to be preserved only as a side effect of code order (lines 967+ are never reached) — not because anything guarantees it. There is no regression test for this path (`tests/test_web.py:1478-1545` only covers the happy path, nonexistent-instance 400, and the HX-Redirect/303 branching — none inject a write failure).

**New vs modified:** Modify `remove_instance` only. No new component — reuse the existing `model_copy`-then-write-then-swap convention already used by the four call sites above (e.g., `updated_instances = dict(instances); del updated_instances[instance_name]; updated = settings.model_copy(update={app_name: updated_instances}); new_settings = SettingsModel(**_settings_to_dict(updated))`-style validate, write, then swap `request.app.state.settings = new_settings`, *then* do job/client/state cleanup exactly as today).

**Control/data flow change:** reorder only — validate → write → swap-live-settings, then (unconditionally, now safe) remove job / pop client / pop state / pop tag cache, close client outside lock. No new state, no schema change.

### 1b. `_merge_defaults` / non-object `state.json`

**What the code does today** (`triggarr/state.py:210-245`, `140-152`, `171-207`):

```python
# load_state (state.py:227-239)
data = json.load(f)                       # succeeds for `[]`, `42`, `null` — all are valid JSON
except (json.JSONDecodeError, OSError):   # does NOT catch AttributeError
    ...
if _is_v22_state_format(data):            # state.py:140-152: data.get(section, {})
    ...
return _merge_defaults(data)              # state.py:179-180: loaded.get(app_key, {})
```

`_is_v22_state_format` and `_merge_defaults` both call `.get(...)` directly on the top-level parsed JSON. `json.load` happily returns a `list`, `int`, or `None` for `[1,2,3]`, `42`, or `null` — all are valid JSON, so `json.JSONDecodeError` is never raised, and `load_state`'s except clause (`json.JSONDecodeError, OSError`) does not catch the ensuing `AttributeError` from `[].get(...)` / `None.get(...)` / `(42).get(...)`.

**Defect status: CONFIRMED PRESENT**, and already self-documented as a known gap in the test suite: `tests/test_state.py:407-420`, `test_state_wrong_structure_list_crashes`, asserts `pytest.raises(AttributeError)` for `"[1, 2, 3]"` and says in its own docstring: *"This is a known gap... When load_state is hardened to handle non-dict roots, convert this test to assert recovery to defaults instead."* `42` and `null` hit the exact same `.get()` call and therefore the same crash (not independently tested, but mechanically identical). By contrast, a *wrong-shaped but still dict* root (`{"radarr": "not_a_dict", ...}`) already recovers cleanly today (`tests/test_state.py:423-437`, `test_state_wrong_nested_type_recovers`) because `_merge_defaults`'s `isinstance(loaded_section, dict)` guard (`state.py:181`) only runs once `loaded` itself is confirmed to support `.get`.

**New vs modified:** Modify `load_state` (and/or `_is_v22_state_format`/`_merge_defaults`) in `triggarr/state.py` only. No new file. The natural fix point is a single `isinstance(data, dict)` guard right after `json.load`, before `_is_v22_state_format(data)` is called, falling back to `_default_state()` exactly like the existing `JSONDecodeError`/`OSError` branch does.

**Control/data flow change:** none beyond widening the existing "corrupt → defaults" recovery path to cover non-dict-but-valid JSON. No callers of `load_state` need to change — `create_lifespan` (`triggarr/search/scheduler.py:481`) already treats whatever `load_state` returns as a `TriggarrState`.

---

## 2. Resource lifecycle (999.13, narrowed)

### 2a. Startup: resources opened before the generator reaches `yield`

**What the code does today** (`triggarr/search/scheduler.py:460-667`, `create_lifespan`):

The `@asynccontextmanager` generator opens, in order, *before* the `try: yield / finally:` block that begins at line 669:
- `db = await aiosqlite.connect(db_path)` — line 496
- `await db.execute("PRAGMA journal_mode=WAL")` / `synchronous=NORMAL"` — 497-498
- `await init_db(db, db_path, instance_stable_ids=...)` — 509 (runs migrations; can raise)
- `await migrate_from_state(...)` — 514 (conditional, can raise)
- `await ensure_cutover_recorded(db, ...)` — line 526, whose own comment states: *"Deliberately not caught -- a failed cutover must stop startup the same way a failed migration does"*
- the `all_clients` build loop — 534-544, one `httpx.AsyncClient`-backed `ArrClient` per enabled instance
- `scheduler.add_job(...)` per instance (630-646) and `scheduler.start()` (652)

Only *after* all of that does the function reach `try: yield / finally: ...` (669-671). Python's `@asynccontextmanager` machinery never runs the generator's `finally` block unless execution reaches the paired `yield` — if `__aenter__` (the pre-yield code) raises, `__aexit__` is never invoked at all. So any exception raised anywhere in lines 481-667 — a migration failure, a client-construction error, an APScheduler `add_job` error — leaks the already-opened `aiosqlite` connection and any already-constructed `httpx.AsyncClient` instances; none of the shutdown code at 747-753 ever runs for that failed startup attempt.

**Defect status: CONFIRMED PRESENT.** No existing test exercises this: every lifespan test in `tests/test_scheduler.py` (`test_lifespan_records_attribution_cutover_once`, `test_lifespan_cutover_after_init_db`, `test_lifespan_passes_stable_id_mapping_to_init_db`, `test_lifespan_associates_existing_rows_on_upgrade`, etc., lines 1968-2325) exercises the happy path only — none inject a failure partway through startup and assert that `db`/clients get closed. Contrast with `triggarr/startup.py:validate_connections` (142-171), which *already* does this correctly for its own (temporary, pre-lifespan) clients: `try: ... finally: await client.close()` per instance (168-169) — the pattern exists elsewhere in the codebase, just not in `create_lifespan`.

**New vs modified:** Modify `create_lifespan` only. No new module. The fix shape: wrap the resource-opening section (db connect through client construction) in a `try/except` that closes whatever was already opened (`db`, any clients already created) before re-raising, so a partial-startup failure still exits cleanly. This does not require moving the `try: yield` block — it requires a second, narrower cleanup path for the pre-yield section.

### 2b. Shutdown: one client-close failure blocks the rest

**What the code does today** (`triggarr/search/scheduler.py:747-753`):

```python
747  # 3. Close HTTP clients (all instances)
748  for app_type in APP_TYPES:
749      for client in getattr(app.state, f"{app_type}_clients", {}).values():
750          await client.close()          # ArrClient.close() -> self._client.aclose()
751
752  # 4. Close shared database connection (all writes complete per step 2)
753  await app.state.db.close()
```

`ArrClient.close()` (`triggarr/clients/base.py:306-308`) is `await self._client.aclose()` with no internal guard. If `aclose()` raises for *any* instance, the exception propagates out of the nested `for` loop, skipping every remaining client (including other instances of the same app type and all subsequent app types) and skipping `app.state.db.close()` entirely.

**Defect status: CONFIRMED PRESENT** — no `try/except` isolates one client's close from another's or from the db close. This is not purely theoretical: `tests/test_clients.py:330-394` (`test_aclose_with_real_asgi_transport_no_cancel_raises_specific_exception`) already demonstrates that `httpx.AsyncClient` close/in-flight interaction can surface a specific exception class under a real ASGI transport (that particular test shows the exception surfaces on the *in-flight request task*, not from `close()` itself, under the two transport scenarios it pins — i.e. the two currently-tested scenarios keep `close()` itself exception-free — but nothing in `scheduler.py`'s shutdown loop defends against a transport or future httpx version where `aclose()` itself raises). No test today asserts "one client failing to close still lets the rest close and the DB close" — that is precisely the gap PROJECT.md names.

**New vs modified:** Modify the shutdown `finally` block in `create_lifespan` only. Fix shape: wrap each `await client.close()` call in its own `try/except Exception: logger.warning(...)` so one failure is logged and swallowed rather than aborting the loop, and so `await app.state.db.close()` always runs afterward regardless.

---

## 3. Search-command delivery (POST-retry semantics)

**What the code does today:**

`ArrClient._request_with_retry` (`triggarr/clients/base.py:64-99`) wraps **every** HTTP verb identically:

```python
73   try:
74       response = await self._client.request(method, path, **kwargs)
75       response.raise_for_status()
...
77   except (httpx.HTTPStatusError, httpx.TransportError):
...
83       await asyncio.sleep(2)
84       try:
85           response = await self._client.request(method, path, **kwargs)   # same request, retried once
...
88       except (httpx.HTTPStatusError, httpx.TransportError) as exc:
...
            raise
```

`get()` (101-103) and `post()` (105-107) both call this same helper with no verb-specific branch. `httpx.TransportError` is the broad base for `ConnectError`, `ConnectTimeout`, `ReadTimeout`, `WriteTimeout`, `PoolTimeout`, `NetworkError`, `ProtocolError`, etc. — it does not distinguish "request never left the socket" (safe to retry) from "request was sent and a response was awaited but never arrived" (NOT safe to retry on a side-effecting command). Every search-trigger call goes through `post()`:
- `RadarrClient.search_movies` → `self.post("/api/v3/command", ...)` (`triggarr/clients/radarr.py:61-64`)
- `SonarrClient.search_season` → `self.post("/api/v3/command", ...)` (`triggarr/clients/sonarr.py:172-181`)
- `LidarrClient.search_albums` → `self.post("/api/v1/command", ...)` (`triggarr/clients/lidarr.py:93-96`)

So a `ReadTimeout` on the *first* POST attempt (the *arr instance received the command and is processing it, but the HTTP response never arrived at Triggarr) is caught by the same `(httpx.HTTPStatusError, httpx.TransportError)` tuple as a `ConnectError` (nothing was ever sent). `_request_with_retry` automatically re-sends the identical POST 2 seconds later with no idempotency key and no way to check whether the first command was accepted. The *arr `/command` endpoints return a JSON body (commonly including a command id) — Triggarr never reads or stores it; `_search_and_record`'s `command` parameter is `Callable[[], Awaitable[object]]` and its return value is discarded (`triggarr/search/engine.py:510-537`), so there is no hook today to poll "did my first command actually land" before deciding to retry.

**How the outcome flows into history/grading** (`triggarr/search/engine.py:510-599`, `triggarr/search/outcome.py`):
- `_search_and_record` calls `await command()` (536). If it raises `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)`, it's recorded as `tally.record_failed(reason)` (546) and an `insert_search_entry(..., outcome="failed", ...)` row is written (548-557).
- If `command()` returns without raising — which is exactly what happens when the automatic retry's *second* attempt succeeds, even though the *first* attempt may have already been accepted upstream — `tally.record_accepted()` fires unconditionally (569) and `insert_search_entry(..., outcome="searched", ...)` is written (571-580).
- `CycleTally.to_record` → `grade_cycle` (`triggarr/search/outcome.py:45-81, 158-204`) uses `accepted`/`failed` counts with no "unknown/ambiguous" category; a cycle with one such retry-masked double-dispatch reads as a normal `accepted=1` success, and a cycle where the retry *also* times out reads as `failed=1` even if the *arr instance actually queued two identical commands server-side.

**Defect status: CONFIRMED PRESENT.** No existing test treats POST differently from GET: `tests/test_clients.py:113-169` (`test_request_with_retry_first_attempt_success`, `test_request_with_retry_retries_on_failure`, `test_request_with_retry_reraises_when_retry_fails`) all call `_request_with_retry("GET", ...)` and assert the retry-and-succeed / retry-and-reraise behavior as the *intended* contract — there is no test asserting POST search commands behave differently, and no test for "a timeout after the server may have accepted the command is distinguished from a failure before anything was sent."

**New vs modified:** Modify `triggarr/clients/base.py` (retry policy — likely split into "safe to retry blindly" exceptions, e.g. `httpx.ConnectError`/DNS failures that happen before any bytes are sent, vs. exceptions that mean "response lost, delivery unknown," e.g. `httpx.ReadTimeout`/`httpx.WriteTimeout` after the request was dispatched) and `triggarr/search/engine.py` (`_search_and_record` needs a third outcome bucket distinct from accepted/failed so "delivery unknown" is never silently folded into either). Likely also touches `triggarr/search/outcome.py` (`CycleTally`/`grade_cycle`/`cycle_view`) to represent and render the new bucket without breaking the existing Success/Partial/Failed/Nothing-needed semantics (OUTCOME-06's "accepted is never retracted" invariant must still hold — an *unknown* outcome must not be reported as "accepted," nor silently counted as "failed" if that would misrepresent a possibly-real search as a problem). GET retries (`get()`, `get_paginated()`, tag/count fetches) are explicitly to stay as-is per the backlog scope ("keep safe read retries").

**Control/data flow change:** `_search_and_record`'s binary accepted/failed branch (`engine.py:536-599`) grows a third branch; `CycleTally` grows a counter/flag for it; `grade_cycle` must decide how "delivery unknown" affects the four-grade table without a UI redesign (this milestone explicitly excludes UI redesign — the existing `cycle_view`/`cycle_grade.html` rendering should absorb the new case with minimal new copy, not a new card layout). This is the highest-blast-radius item of the six: `clients/base.py` is shared by all three apps, and `_search_and_record` is called from all 6 cycle call sites (Radarr/Sonarr/Lidarr × missing/cutoff, `engine.py:1174-1202, 1482-1527, 1787-1815`).

---

## 4. Pre-migration DB backup bounding

**What the code does today** (`triggarr/db.py:172-236`, `run_migrations`):

```python
203  backup_path = db_path.with_suffix(f".v{current}-backup")      # canonical name, never overwritten
204  earliest_backup: Path | None = None
205  if db_path.exists():
206      if backup_path.exists():
207          stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
208          timestamped_path = db_path.with_suffix(f".v{current}-backup-{stamp}")
209          shutil.copy2(db_path, timestamped_path)                # NEW file every retry, no cap
...
217      shutil.copy2(db_path, backup_path)                          # first attempt only
```

Every subsequent startup attempt where the schema is still at `current` (i.e. a previous migration attempt failed and the process restarted — a crash loop) finds `backup_path.exists() == True` and writes one more `.v{current}-backup-{stamp}` file. There is no `glob`/`unlink`/retention logic anywhere in `db.py` (confirmed by grep — the only backup-related calls are the two `shutil.copy2` sites above and their log lines).

**Defect status: CONFIRMED PRESENT**, and this is the same gap PROJECT.md/STATE.md already name (originating from Phase 81 plan 81-03, flagged as a deferred follow-up at the time: `.planning/phases/81-correct-sonarr-grab-attribution/81-CONTEXT.md:116`). Existing coverage (`tests/test_migration_v10_atomic.py:430-448`, `test_v10_backup_never_overwrites_earlier_backup`) proves the *preserve-the-earliest-backup* half works for exactly one retry (asserts "exactly one timestamped backup" after one injected failure) but does not exercise — and therefore does not bound — a multi-retry crash loop; no test calls `init_db`/`run_migrations` in a loop to show N retries produce N backups.

**New vs modified:** Modify `run_migrations` in `triggarr/db.py` only. No schema change, no new table. Fix shape: after writing a new timestamped backup, prune older timestamped backups beyond some retained count (the canonical `.v{N}-backup` file, being the earliest, should likely always be kept per the existing "earliest_backup" semantics used in the recovery-pointer error message at `db.py:161-167`).

**Control/data flow change:** none beyond adding a bound/prune step immediately after line 209's `shutil.copy2`. Fully isolated to this one function; no caller (`init_db`, `create_lifespan`) needs to change.

---

## 5. Pending Sonarr searches of a removed instance

**What the code does today:**

- Every instance gets a permanent, random stable ID at creation time: `new_instance_id()` returns `secrets.token_hex(16)` (`triggarr/config.py:58-60`), called fresh in `add_instance` (`routes.py:914`) and in the settings-form instance-parsing path (`routes.py:689`, `new_instance_id()` only when `current_cfg` is `None`, i.e. for a brand-new name). **A re-added instance under the same display name always gets a brand-new stable ID** — there is no code path that reuses an old ID for a reused name.
- Sonarr tracking is scoped strictly by `instance_stable_id`: `_run_sonarr_tracking_check` (`triggarr/tracking.py:522-564`) calls `get_trackable_entries(db, instance_stable_id=instance_stable_id)` (line 554) for the **currently configured** instance's ID, passed in from `run_tracking_check(..., instance_stable_id=instance_config.id)` (`tracking.py:69-121`), which is itself called once per scheduled cycle from `make_search_job`'s `job()` closure (`triggarr/search/scheduler.py:214-221`) using `instance_config.id` read from `app.state.settings` at call time.
- `get_trackable_entries` (`triggarr/db.py:991-1061`) filters `WHERE ... instance_stable_id = ?` when given one (1034-1036) — rows written under a different (old/removed) stable ID are structurally invisible to this query.
- When an instance is removed, `remove_instance` (`routes.py:970-971`) calls `scheduler.remove_job(job_id)` — the per-instance scheduled job (the only thing that ever calls `run_tracking_check` for that instance) is deleted. **No code anywhere re-visits that instance's pending `search_history` rows afterward.**
- Pending rows (`outcome IN ('searched', 'partial')`) are explicitly exempt from the resolved-row pruning in `insert_search_entry` (`triggarr/db.py:797-812`, comment: *"Pending rows... are never pruned; their owned grabs would otherwise be stranded uncredited"*) — so they are not even garbage-collected by the existing history cap.

**Net effect, confirmed by tracing the code (not asserted from the backlog note alone):** once a Sonarr instance is removed, its still-pending `search_history` rows (under its now-orphaned `instance_stable_id`) are (a) never checked again — the only code path that reads them (`_run_sonarr_tracking_check`) only runs for a `instance_stable_id` that is currently attached to a live scheduled job; (b) never pruned — pending rows are permanently exempt from the row-count cap; (c) still visible in the History UI under the reused display name if a new instance is later added with the *same name* — `get_recent_searches`/`get_search_history` (`triggarr/db.py:840-882`, `935-985`) filter by `instance_id` (display name), not `instance_stable_id`, so a UI view scoped to that name would show the orphaned pending rows interleaved with the new instance's rows, both labeled "searched" with no visual distinction. Identity isolation for *crediting* grabs does hold — `get_owned_grabs`/`update_outcome_and_stats` are scoped by `instance_stable_id` (`db.py:598`, `1090+`) so a new instance can never be credited for, or re-check, an old instance's rows — but the rows themselves have no defined end state.

**Defect status: CONFIRMED PRESENT**, matching the backlog item (`bugs-005`, `.planning/backlog/MAINTENANCE.md:36`, "deferred 2026-10-20"). No test covers this lifecycle: no `test_tracking.py`/`test_db.py`/`test_web.py` test removes a Sonarr instance with pending rows and asserts anything about what happens to them afterward.

**New vs modified:** Likely a small modification to `triggarr/db.py` (a query/predicate to identify "pending rows whose `instance_stable_id` is no longer present in the live config" — the codebase already has a directly analogous precedent to reuse: `_LEGACY_PENDING_SQL` (`db.py:671`) already implements "frozen, excluded-from-cap, never-checked-again, visibly labeled" for the Phase 81 pre-cutover rows, and `is_legacy`/`get_trackable_entries`'s exclusion of it (`db.py:999, 1032`) is the existing pattern a fix would extend) plus a small addition to `remove_instance` (`routes.py`) to act on them at removal time (e.g., mark them closed-out in the same transaction/lock scope that already does the job/client/state cleanup, §1a above — this item depends on §1a's ordering fix landing in the same route). No new table is required if the existing `is_legacy`-style boolean/predicate pattern is reused; a schema migration would only be needed if a persisted new column is chosen over a derived predicate.

**Control/data flow change:** a new decision point at instance-removal time (what happens to that instance's pending Sonarr rows — document/exempt/mark, not "leave silently"), and a predicate addition wherever pending rows are selected/counted/rendered (`get_trackable_entries`, the pending-cap `cap_query` in `insert_search_entry`, and the History-page queries) so the orphaned rows are classified consistently with the existing legacy-row precedent rather than invented from scratch.

---

## 6. Telemetry variable and startup (SA-12)

**What the code does today:** Triggarr itself never references `FASTAPI_OTEL_AUTO_CONFIGURE` or any `OTEL_*` variable (confirmed: zero matches in `triggarr/`, `Dockerfile`, `docker-compose.yml`). The behavior is entirely owned by the installed FastAPI version. `uv.lock` pins `fastapi==0.162.4` (confirmed in the project venv at `.venv/lib/python3.11/site-packages/fastapi/telemetry/_runtime.py`), whose `lifespan()` wrapper (lines 210-225) already does:

```python
218  except Exception as exc:
219      # Optional telemetry setup must not prevent application startup.
...
```

**Defect status: ALREADY FIXED (upstream), confirmed on the exact installed version** — this matches the correction already recorded in `.planning/backlog/MAINTENANCE.md:146` (2026-11-14, BM WR-01 at `d06fab3`): the original SA-12 startup-failure claim was wrong; FastAPI 0.162.0+ catches the telemetry setup error and logs a warning, verified live on the built v2.12.1 image. **What remains per PROJECT.md's reduced scope is a regression test** (set `FASTAPI_OTEL_AUTO_CONFIGURE=true` [+ a dummy OTLP endpoint], start/exercise the lifespan, assert it still serves requests) and a documentation note that telemetry export is unsupported (Triggarr configures no exporters, so even though startup survives, nothing is actually exported if a user enables the variable).

**New vs modified:** No source change expected in `triggarr/`. Add one regression test (likely in `tests/test_scheduler.py` or `tests/test_startup.py`, using `monkeypatch.setenv` around a `create_lifespan`/app-startup exercise) plus a short "unsupported" note in docs (README or `docs/operations/`). This is the lowest-risk, fully independent item of the six — it can be slotted anywhere in the build order without touching any other component.

---

## Build order

Dependency-ordered, not risk-ordered-for-its-own-sake — later phases are sequenced where they genuinely need an earlier phase's result, not merely because they're "bigger."

1. **State/config consistency fixes (§1a + §1b) — `triggarr/web/routes.py::remove_instance`, `triggarr/state.py::load_state`.** Fully independent of everything else; smallest blast radius; establishes (or rather, extends to a holdout route) the validate-before-mutate convention already used everywhere else in `routes.py`. Doing this first means §5's fix (which needs to slot a new decision into `remove_instance`) is built on the *corrected* version of that route, not the buggy one.

2. **DB backup bounding (§4) — `triggarr/db.py::run_migrations`.** Fully independent, small, isolated to one function. No reason to sequence it relative to 1, but it's natural to batch with it as "narrow, low-risk, no cross-component coordination" work.

3. **SA-12 regression test + docs note (§6).** Independent and trivial; can be folded into phase 1 or 2's PR, or its own tiny phase — no dependency either direction.

4. **Resource lifecycle (§2a + §2b) — `triggarr/search/scheduler.py::create_lifespan`.** Self-contained to one function (both the pre-yield startup section and the post-yield shutdown section), independent of phases 1-3. Placed after the state/config phase mainly so the simpler "reorder + guard" pattern from phase 1 is already proven in this codebase before touching the more control-flow-heavy lifespan generator (which has more existing tests to keep green — `tests/test_scheduler.py:1968-2325`).

5. **Pending Sonarr searches of a removed instance (§5) — `triggarr/db.py` (new predicate, reusing the `_LEGACY_PENDING_SQL` precedent) + `triggarr/web/routes.py::remove_instance`.** Depends on phase 1's corrected `remove_instance` ordering, since the natural integration point for "decide the pending-row lifecycle" is inside that same lock-scoped block, right alongside the (now-fixed) job/client/state cleanup. Should not be attempted before phase 1 lands.

6. **Search-command delivery / POST-retry semantics (§3) — `triggarr/clients/base.py`, `triggarr/search/engine.py`, `triggarr/search/outcome.py`.** Largest blast radius (shared HTTP client base used by all three apps; `_search_and_record` called from all 6 cycle call sites; grading logic read by the scheduler's failure-counter and the dashboard template). Sequenced last so the team is applying the "add a narrow, well-tested behavior change without breaking existing grade semantics" pattern with the most practice behind it, and because it is the one item of the six with no dependency *forcing* it earlier — everything else can ship and be verified independently first.

7. **Built-image smoke-test extension (cross-cutting, do last).** See below — best done once the behavior it is demonstrating actually exists, so the smoke test is validating real fixes rather than being written speculatively ahead of them.

---

## CI built-image smoke test as a restart/recovery host

`tests/harness/image_smoke.py` (Phase 82's shipped-image smoke driver, started through the real Docker entrypoint, no source mounts) **already contains a directly reusable restart/recovery step**: `_step_c_restart` (`image_smoke.py:138-170`) stops the running app container (`stack.stop_and_remove`, `tests/harness/stack.py:390-394` — a graceful `docker stop --time 90` + `docker rm`), starts a fresh container on the **same config volume**, and asserts the account/config persisted (login still works, `triggarr.toml` still contains the admin username). This is exactly the right place to host a v2.14 demonstration, for two reasons: it already exercises the real published image end-to-end, and it already has the volume-reuse plumbing a recovery demo needs.

Two concrete, low-effort extensions would turn it into a direct demonstration of this milestone's fixes, using tooling already present in `stack.py`/`image_smoke.py`:
- **Malformed `state.json` before restart:** between `_step_b_seeded_run` and `_step_c_restart`, use `stack.exec_in(app_name, [...])` (already used at `image_smoke.py:80, 129-131, 166-167, 181` for reading/deleting files inside the container) to overwrite `/config/state.json` with `[]`, `42`, or `null` before stopping the container, then assert the restarted container still reaches `wait_for_http_health` and serves the dashboard — directly exercising §1b's fix against the real image/volume, not just the unit test.
- **Hard-kill instead of graceful stop:** `stop_and_remove` only issues `docker stop` (SIGTERM, 90s grace); there is no existing helper for an abrupt `docker kill` (SIGKILL, no grace period) restart. Adding one and using it as an alternate path into `_step_c_restart` would exercise the "partial/interrupted shutdown, resource state on disk is whatever a SIGKILL leaves behind" scenario that §2 is about, closer to a real crash than a graceful stop ever is.

Both fit the existing module's structure (sequential numbered `_step_*` helper functions, shared `known_names`/`collected_logs` bookkeeping, `checks.SmokeCheckError` for failures) without needing a new harness.

---

## Patterns already established in this codebase (reuse, don't reinvent)

- **Validate-then-write-then-swap for settings:** `model_copy`/`SettingsModel(**dict)` → `_atomic_toml_write` → `request.app.state.settings = new_settings`, always inside `search_lock`, client-close always deferred until *after* the lock is released (`routes.py:715-820` is the fullest example, with `clients_to_close` collected inside the lock and closed outside it).
- **Per-resource try/finally close, not a single bare loop:** `triggarr/startup.py:validate_connections` (142-171) already closes each temporary client in its own `try/finally`, which is the shape §2b's shutdown fix should match for the *persistent* clients too.
- **"Frozen/legacy, excluded-from-cap, visibly labeled" precedent for orphaned pending rows:** `_LEGACY_PENDING_SQL` (`db.py:671`) plus its use in `get_trackable_entries`, the pending-cap query, and `is_legacy` columns in `get_recent_searches`/`get_search_history` is the exact shape a fix for §5 should extend, rather than inventing a new mechanism.
- **Atomic write-then-rename with fsync, used identically in `state.py:save_state`, `config.py:_atomic_toml_write`, `config.py:_atomic_text_write`** — any new persisted artifact should match this three-file pattern (tempfile in the same dir → fsync → `os.replace` → fsync parent dir), not introduce a fourth variant.

## Anti-patterns found (the defects themselves)

- **Mutate-then-write instead of build-then-swap** (`remove_instance`, §1a) — the one place in `routes.py` that deviates from the rest of the file's own convention.
- **Resource acquisition with no matching cleanup scope** (`create_lifespan`'s pre-yield section, §2a) — opening `db`/clients outside the `try/finally` that is supposed to close them.
- **Uniform retry policy applied to a side-effecting verb** (`_request_with_retry` applied identically to GET and POST, §3) — retry safety depends on whether the operation is idempotent/side-effect-free, which `_request_with_retry` does not distinguish.
- **Unbounded accumulation on repeated failure** (`run_migrations`'s timestamped backups, §4) — a retry loop with no cap is a classic crash-loop disk-fill vector.
- **Selection-scoped-by-identity with no end-of-life path** (`instance_stable_id`-scoped pending rows, §5) — correctly preventing cross-instance leakage, but with no mechanism for what happens when the owning identity is deleted.

## Sources (file:line evidence index)

- `triggarr/web/routes.py:937-995` (remove_instance), `:882-934` (add_instance, comparison), `:650-820` (update_settings, comparison), `:1382-1470` (first-run setup, comparison), `:1660-1720` (password change, comparison)
- `triggarr/models/config.py:186-202` (mutable `dict[str, InstanceConfig]` fields, no frozen config)
- `triggarr/config.py:58-61` (new_instance_id), `:63-87` (_settings_to_dict), `:129-198` (_atomic_toml_write)
- `triggarr/state.py:140-152` (_is_v22_state_format), `:171-207` (_merge_defaults), `:210-245` (load_state), `:248-321` (save_state)
- `tests/test_state.py:383-437` (corrupt/wrong-structure/wrong-nested-type recovery tests, including the self-documented `test_state_wrong_structure_list_crashes`)
- `triggarr/search/scheduler.py:460-667` (create_lifespan startup), `:669-756` (shutdown), `:132-272` (make_search_job)
- `tests/test_scheduler.py:974-1292` (shutdown-drain tests), `:1968-2325` (lifespan happy-path tests — no partial-startup-failure test exists)
- `triggarr/startup.py:125-171` (validate_connections — existing correct per-resource cleanup pattern)
- `triggarr/clients/base.py:46-58` (ArrClient.__init__), `:64-99` (_request_with_retry), `:101-107` (get/post), `:306-314` (close/__aexit__)
- `triggarr/clients/radarr.py:61-64`, `triggarr/clients/sonarr.py:172-181`, `triggarr/clients/lidarr.py:93-96` (search-trigger methods, all via `post()`)
- `tests/test_clients.py:113-169` (retry tests, GET-only), `:247-394` (aclose-under-load contract tests)
- `triggarr/search/engine.py:510-599` (_search_and_record), `:602-620` (_finalize_cycle)
- `triggarr/search/outcome.py:45-81` (grade_cycle), `:90-204` (CycleTally), `:219-361` (cycle_view)
- `triggarr/db.py:172-236` (run_migrations backup-before-migrate), `:678-837` (insert_search_entry, pending cap + resolved-row pruning), `:840-882` (get_recent_searches), `:935-990` (get_search_history), `:991-1061` (get_trackable_entries), `:671` (_LEGACY_PENDING_SQL)
- `tests/test_migration_v10_atomic.py:430-462` (backup tests, single-retry only)
- `triggarr/tracking.py:69-121` (run_tracking_check), `:522-564` (_run_sonarr_tracking_check, instance_stable_id scoping)
- `.planning/backlog/MAINTENANCE.md:36` (bugs-005 narrative), `:146` (SA-12 correction)
- `.venv/lib/python3.11/site-packages/fastapi/telemetry/_runtime.py:210-225` (FastAPI 0.162.4, installed per `uv.lock`, already swallows telemetry setup errors)
- `tests/harness/image_smoke.py:138-170` (_step_c_restart, existing restart/persistence check), `tests/harness/stack.py:360-394` (wait_for_exit/exec_in/stop_and_remove primitives)

---
*Architecture research for: Triggarr v2.14 Reliability (integration with existing code)*
*Researched: 2026-11-15*
