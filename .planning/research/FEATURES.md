# Feature Research: v2.14 Reliability

**Domain:** Failure-mode correctness for a self-hosted *arr automation daemon (Triggarr) — no new user-facing features, only defined behavior under failed writes, ambiguous network responses, and partial startup/shutdown.
**Researched:** 2026-11-15
**Confidence:** HIGH overall (every behavioral claim below is grounded either in a direct read of `triggarr/` source at the cited line, or in a fetch of the official Radarr/Sonarr/Lidarr source/docs; a few comparable-tool and industry-pattern claims are MEDIUM and flagged individually)

This research reads as a gap analysis against the *current* Triggarr codebase, not a greenfield survey — this is a hardening milestone on a shipped app. Each category below states what Triggarr does **today** (with file:line evidence), what the Servarr apps and comparable tools do, and classifies the fix as table stakes / differentiator / anti-feature.

---

## Category: State & Config Consistency

### Current behavior (confirmed by reading the code)

- **Instance removal writes in the wrong order.** `remove_instance` (`triggarr/web/routes.py:937-991`) does `del instances[instance_name]` — which mutates the **live** `settings` object in place, since `instances = getattr(settings, app_name)` returns the real dict reference — and only *afterward* calls `_atomic_toml_write`. If that write raises (disk full, permission error, `OSError` from `os.replace`), the exception propagates out of the `async with search_lock` block with the instance already gone from live `settings`, while the scheduler job and the HTTP client for that instance are *still present* (their cleanup lines run after the write, in the same block). Today a failed write produces a worse partial state than doing nothing: settings says the instance is gone, but the job keeps firing against clients that still exist. `add_instance` (routes.py:899-934), by contrast, already does this correctly — it builds a candidate `config_dict`, validates it via `SettingsModel(**config_dict)`, and only mutates live state (`request.app.state.settings = new_settings`) after the write succeeds. The target behavior is simply applying `add_instance`'s validate-then-write-then-mutate ordering to removal.
- **Non-object state JSON crashes instead of recovering.** `load_state` (`triggarr/state.py:210-245`) catches `json.JSONDecodeError`/`OSError` from `json.load`, but a syntactically valid JSON document that isn't an object (`[]`, `42`, `null`) parses fine and is then handed to `_is_v22_state_format(data)` and `_merge_defaults(data)`, both of which call `data.get(section, {})` — `list`, `int`, and `NoneType` have no `.get`, so this raises `AttributeError` uncaught. This is a documented, named gap already: `.planning/PROJECT.md`'s tech-debt note cites `test_state_wrong_structure_list_crashes` as "a limitation in `_merge_defaults`."

### Classification

| Behavior | Class | Complexity | Notes |
|---|---|---|---|
| Validate-then-write-then-mutate ordering for instance removal | Table stakes | LOW | Mechanical reordering mirroring `add_instance`'s already-correct pattern in the same file; no new write primitive needed. |
| Non-object state JSON (`[]`, `42`, `null`) treated as corrupt → reset to defaults (same as JSON-decode-error path) | Table stakes | LOW | One `isinstance(data, dict)` guard before `_is_v22_state_format`/`_merge_defaults`, reusing the existing "corrupt state file -- resetting to defaults" warning log and `_default_state()` fallback at `state.py:239`. |
| A config migration/validation framework that handles arbitrary malformed shapes generically | Anti-feature | — | Out of scope per ROADMAP ("No blanket I/O or offloading rewrite"); the two gaps above are narrow and don't need generic infrastructure. |

**Dependency:** both fixes are independent of each other and of every other category; neither touches search delivery, backups, or the Sonarr lifecycle question. Low risk to parallelize in the same phase.

---

## Category: Resource Lifecycle (narrowed)

### Current behavior (confirmed by reading the code)

- **Failed startup leaks what it opened.** `create_lifespan`'s inner `lifespan()` (`triggarr/search/scheduler.py:480-651`) opens the shared `aiosqlite` connection (`db = await aiosqlite.connect(db_path)`, line 496) and creates every enabled instance's long-lived `httpx.AsyncClient` (lines 534-544) *before* reaching `try: yield` (line 669). The `finally:` block that closes clients and the database (lines 747-753) is physically part of that `try/finally`, which only starts executing once `yield` is reached. Anything that raises between `db = await aiosqlite.connect(...)` and `try: yield` — `init_db` failing, `ensure_cutover_recorded` raising (explicitly documented as deliberately uncaught at line 522-526), a client constructor failing — skips the `finally` entirely. The db connection and any already-constructed httpx clients leak (open file descriptors / sockets) and the process typically exits via the uncaught exception, but under a supervisor that catches and retries without a fresh process (or in a test harness that reuses an event loop), those handles are never released.
- **One client's close failure stops every other close, including the database's.** The shutdown closing loop (`scheduler.py:747-750`) is:
  ```python
  for app_type in APP_TYPES:
      for client in getattr(app.state, f"{app_type}_clients", {}).values():
          await client.close()
  await app.state.db.close()
  ```
  `ArrClient.close()` (`triggarr/clients/base.py:306-308`) is just `await self._client.aclose()` with no internal try/except. If any one client's `aclose()` raises, the exception propagates out of the nested loop immediately — every other instance's client (including other apps) and the database connection are never closed. This is the literal opposite of the target behavior ("one client's close failure... does not stop other clients or the database from closing").

### Classification

| Behavior | Class | Complexity | Notes |
|---|---|---|---|
| Startup wraps resource acquisition (db connect, client construction) so a later startup failure closes what was already opened | Table stakes | MEDIUM | Needs either an explicit cleanup list threaded through the startup sequence or restructuring so `db`/clients are opened inside their own `try`/`except`-and-close-then-reraise, or an `AsyncExitStack`. Must not change the happy-path behavior (clients still end up on `app.state` for the lifetime of the app). |
| Shutdown closes every client independently (each wrapped so one failure is logged, not raised) and always attempts the database close afterward | Table stakes | LOW-MEDIUM | A `try/except` (or `asyncio.gather(..., return_exceptions=True)`) per client close, logging the sanitized exception via the existing `_sanitize_exc` helper, then unconditionally closing `db` in a `finally`. |
| "No blanket I/O or offloading rewrite" / generic resource-pool abstraction | Anti-feature | — | Explicit ROADMAP scope fence; the fix is narrow exception handling around existing acquire/release points, not a new resource-management layer. |
| "Correct cursor lifetime issues locally if confirmed" (ROADMAP wording) | Unclear — needs phase-time verification | — | No cursor-lifetime defect was found while reading `scheduler.py`/`state.py` for this research; this line item should be re-verified against the current code at phase-planning time rather than assumed. |

**Dependency:** the startup fix and the shutdown fix touch the same function (`create_lifespan`) but are otherwise independent of each other and of every other category. The shutdown fix has no dependency on the backup or search-delivery work.

---

## Category: Search-Command Delivery

### What Triggarr does today (confirmed by reading the code)

`ArrClient._request_with_retry` (`triggarr/clients/base.py:64-99`) is shared by **both** `get()` and `post()`:

```python
try:
    response = await self._client.request(method, path, **kwargs)
    response.raise_for_status()
    return response
except (httpx.HTTPStatusError, httpx.TransportError):
    await asyncio.sleep(2)
    try:
        response = await self._client.request(method, path, **kwargs)
        ...
```

`httpx.TimeoutException` is a direct subclass of `httpx.TransportError` (confirmed from httpx's own exceptions documentation — `HTTPError → RequestError → TransportError → TimeoutException → {ConnectTimeout, ReadTimeout, WriteTimeout, PoolTimeout}`). So a POST to `/api/v3/command` (Radarr/Sonarr) or `/api/v1/command` (Lidarr) whose **response** times out is unconditionally retried after a 2-second sleep — identical body, identical endpoint, no idempotency key, no status check in between. `search_movies`, `search_season`, and `search_albums` (`triggarr/clients/radarr.py:61-66`, `sonarr.py:172-181`, `lidarr.py:93-98`) all call `post()` and inherit this behavior. `_search_and_record` (`triggarr/search/engine.py:510-599`) then treats the eventual outcome as a strict binary: any exception ⇒ `tally.record_failed()`; no exception ⇒ `tally.record_accepted()` (comment at line 568: "Command accepted -- the *arr committed to the search regardless of what happens next"). There is currently no third state.

### How Radarr/Sonarr/Lidarr actually handle a duplicate command — HIGH confidence, read directly from source

All three apps share the same `CommandQueueManager.Push<TCommand>` implementation (`src/NzbDrone.Core/Messaging/Commands/CommandQueueManager.cs` — fetched and confirmed byte-for-byte equivalent in `Radarr/Radarr`, `Sonarr/Sonarr`, and `Lidarr/Lidarr` `develop` branches):

1. Inside a `lock (_commandQueue)`, it looks up `QueuedOrStarted(command.Name)` — commands with the same `Name` that are still in status `Queued` or `Started` (i.e., not yet `Completed`/`Failed`/`Aborted`).
2. It compares bodies with `CommandEqualityComparer.Instance.Equals(c.Body, command)` (field-level equality — for `MoviesSearch` that's the `movieIds` list; for `SeasonSearch`, `seriesId`+`seasonNumber`; for `AlbumSearch`, `albumIds`).
3. **If a match is found, it returns the existing command object instead of inserting a new one**, logging `"Command is already in progress: {0}"` at Trace level. Only on no match does it `_repo.Insert(commandModel)` with `Status = Queued`.

**What this means for Triggarr's retry risk:** server-side dedup only protects a retry that arrives *while the original command is still `Queued` or `Started`*. Once a command transitions to `Completed` (the search ran, indexers were hit, it's removed from the active in-memory queue), that window closes — a later POST with an identical body is treated as a brand-new command and dispatched again, hitting indexers a second time. Triggarr's current 2-second retry sits squarely inside the risk window for any search that completes in under ~2 seconds (plausible for a fast indexer set) and is *not* protected for any search slower than that. The *arr apps cannot protect Triggarr from duplicating a command whose first attempt already finished before the retry fires — this is a real, bounded limitation, not a client bug to "fix away."

**Status/polling surface (HIGH confidence, GET endpoints exist; MEDIUM confidence on the full status enum):** `GET /api/v3/command` lists all tracked commands; `GET /api/v3/command/{id}` returns one by id. The response carries `status` (`queued`/`started`/`completed`, confirmed from a real Sonarr API payload in [Sonarr#4759](https://github.com/Sonarr/Sonarr/issues/4759); `failed`/`aborted`/`cancelled` also appear in community client libraries but were not independently confirmed from Sonarr's current source in this research — treat as MEDIUM confidence) plus `queued`/`started`/`ended` timestamps. Triggarr does not currently capture the command id from the POST response, so polling `GET /command/{id}` to confirm an ambiguous POST is new work, not a trivial addition — but it is read-only and idempotent, fitting squarely in "safe read retries stay."

### What comparable tools do for an ambiguous/unconfirmed outcome — MEDIUM confidence (community tools, not official docs)

- **Huntarr-Sonarr** (the now-retired community automation daemon closest in shape to Triggarr) exposed `API_TIMEOUT` (60s), `COMMAND_WAIT_DELAY`, and `COMMAND_WAIT_ATTEMPTS` as separate knobs — i.e., it polls the command's status after submitting it rather than resubmitting the command itself. This is the same "status lookup instead of blind replay" pattern GET `/command/{id}` would enable in Triggarr. Source: Unraid Community Apps template description for `Huntarr-Sonarr`; not verified against that project's own source (the upstream `plexguide/Huntarr.io` repository was taken down in 2026 after a credential-leak disclosure, so its current/successor code could not be checked directly).
- **General distributed-systems guidance** (several independent blog/engineering sources, converging but non-primary) frames a timed-out write as one of three states — confirmed success, confirmed failure, or **unknown** — and is explicit that collapsing "unknown" into "failed" (triggering a retry) is the mistake that causes duplicate side effects; the recommended remedy for a non-idempotent call without a server-side idempotency key is a status lookup by id, not blind replay.

### How this should interact with Triggarr's existing cycle grading (read from `triggarr/search/outcome.py` and `triggarr/search/scheduler.py`)

`CycleTally`/`grade_cycle` (`outcome.py:30-204`) already has a precedent for a third bucket that is neither "accepted" nor "failed": `mark_unevaluated()` (Phase 79, unresolved tags) and `record_malformed()` (Phase 80, bad records) both feed an `incomplete` flag that can turn an otherwise-Success cycle into Partial without touching `failed` or `accepted`. An "unconfirmed delivery" command fits the same shape: it is not a confirmed accept (don't call `record_accepted()` — that would overstate what happened and inflate "last successful search"), and it is not a confirmed failure either (don't call `record_failed()` — that's what the SAFETY-03 consecutive-failure counter reads: `if grade == GRADE_FAILED:` at `scheduler.py:326`). Routing it through a new additive tally field analogous to `unevaluated`/`malformed_by_queue` keeps it out of SAFETY-03 while still surfacing on the dashboard and the "Show N reasons" expander (`cycle_view`, `outcome.py:219+`), exactly like today's unresolved-tag and malformed-record rows.

One edge case the existing `grade_cycle` table does not cleanly resolve and should be settled at requirements/planning time, not assumed here: a cycle where **every** dispatched command is unconfirmed (zero accepted, zero definite-failed). Under the current formula (`incomplete` feeding the `failed > 0 or incomplete or eligible_active > 0 → Failed` branch), an all-unconfirmed cycle would grade Failed and *would* trip SAFETY-03 — which may be too aggressive for a single transient timeout on an otherwise-healthy instance. This is a genuine design choice, not a research gap.

### Classification

| Behavior | Class | Complexity | Notes |
|---|---|---|---|
| POST to `/command` (Radarr/Sonarr) or `/api/v1/command` (Lidarr) never blindly retries on a timed-out response | Table stakes | LOW-MEDIUM | Split retry behavior by HTTP method/idempotency instead of catching `TransportError` uniformly — e.g. GET keeps the existing retry, POST on `httpx.TimeoutException` (or all of `TransportError`) returns/raises a distinguishable "delivery unknown" result instead of resubmitting. |
| GET reads (wanted/missing, cutoff, tags, system status, grab history) keep their existing single-retry-on-failure behavior | Table stakes (already shipped, do not regress) | — | These are naturally idempotent; the milestone explicitly preserves this ("safe read retries stay"). |
| A distinguishable "unconfirmed/unknown delivery" outcome, fed into cycle grading via the existing additive-tally pattern (not folded into accepted or failed) | Table stakes | MEDIUM | Reuses `CycleTally`'s established extension point; needs a decision on whether an all-unconfirmed cycle should grade Partial or Failed, and whether it should count toward SAFETY-03 (see edge case above). |
| Capturing the *arr command id from the POST response and polling `GET /command/{id}` to resolve "unconfirmed" into a definite outcome after the fact | Differentiator | MEDIUM-HIGH | Genuinely useful (turns "unknown" into "confirmed" without ever re-POSTing), but it's new surface area: a response model, a follow-up poll with its own timeout/retry semantics, and a place to store the pending command id across a cycle boundary. Not required to meet the milestone's stated "Done when" (distinguish confirmed from unknown + stop blind retries); worth flagging as a clean follow-on, not assuming it ships in this milestone. |
| Claiming exactly-once delivery | Anti-feature | — | The server-side dedup window (queued/started only) cannot cover a retry arriving after the original command completed; Triggarr cannot observe the *arr's internal queue state without polling, and even polling has its own race window. Any "Done when" wording must say "distinguish confirmed vs. unknown," never "guarantee exactly-once." |
| A generic retry framework (configurable backoff/retry policies per endpoint, pluggable retry strategies) | Anti-feature | — | Explicit ROADMAP scope fence; the actual fix is a narrow behavior split on one function (`_request_with_retry`) for one specific call shape (POST to `/command`). |
| Auto-resending an unconfirmed command on the *next* scheduled cycle, treating "unknown" as "needs re-search" | Anti-feature | — | This reintroduces the exact duplicate-search risk the milestone exists to close, just moved from "immediate retry" to "next cycle retry." The round-robin queue already naturally revisits items that were never marked searched; auto-resending unconfirmed ones specifically would double-dip them ahead of schedule for no confirmed benefit. |

**Dependency:** the "unconfirmed" tally bucket depends on nothing else in this milestone but does touch the same code path (`_search_and_record`, `CycleTally`) across all three apps (Radarr/Sonarr/Lidarr cycle functions each call it), so it's one conceptual change applied in 3 call sites, not 3 independent changes. The GET/POST retry split is a prerequisite for the tally bucket to ever receive an unconfirmed signal (today, every POST either fully succeeds after retry or raises — there's no code path that currently distinguishes "the retry itself also timed out" from "the retry got a definite error").

---

## Category: Pre-Upgrade Database Backups

### Current behavior (confirmed by reading the code)

`run_migrations` (`triggarr/db.py:172-236`) backs up the database before the *first* pending migration:

```python
backup_path = db_path.with_suffix(f".v{current}-backup")
if backup_path.exists():
    stamp = ...
    timestamped_path = db_path.with_suffix(f".v{current}-backup-{stamp}")
    shutil.copy2(db_path, timestamped_path)
    ...
else:
    shutil.copy2(db_path, backup_path)
```

The canonical name is never overwritten — once it exists, every subsequent migration attempt at the same source version writes a *new*, uniquely timestamped file. A container that crash-loops partway through a migration (e.g. OOM-killed mid-transaction, repeatedly restarted by Docker's restart policy before the fix is deployed) will accumulate one new multi-megabyte-to-gigabyte backup file per restart, unbounded. There is no pruning, count cap, or age cap anywhere in this function or elsewhere in `db.py`.

### What the *arr apps themselves do — HIGH confidence, from the official Servarr documentation source

Fetched directly from `Servarr/Wiki`'s `sonarr/settings.md` (the documentation source repository backing wiki.servarr.com), General → Backups:

- **Interval:** "How often would you like Sonarr to make a backup (default: every 7 days)."
- **Retention:** "How long would you like Sonarr to hold on to each backup... After a new backup is made the oldest backup will be removed (default: 28 days)."

Radarr and Lidarr expose the identical three settings (Folder/Interval/Retention) under the same General section (cross-referenced via Buildarr's Radarr/Sonarr config schemas, which encode the same 7-day/28-day defaults and a 1–90-day allowed range for retention — MEDIUM confidence, third-party tool docs rather than the wiki source itself, but consistent with the Sonarr wiki source). The operative pattern worth borrowing is **time-boxed retention with pruning triggered on each new backup**, not an unbounded accumulation — the *arr apps' own scheduled backups and Triggarr's crash-loop backups aren't the same trigger (time vs. failure), but the bound should look the same: a small number of recent backups, oldest pruned automatically.

### Classification

| Behavior | Class | Complexity | Notes |
|---|---|---|---|
| A fixed cap (count-based, e.g. keep the N most recent pre-migration backups at a given source version, or a simple age cap) with oldest-first pruning when a new backup is about to be written | Table stakes | LOW | Mirrors the *arr apps' own "new backup triggers pruning of the oldest" behavior; implementable as a small addition to the existing `backup_path.exists()` branch in `run_migrations`, no new subsystem. |
| Keeping the *first* backup of a crash-loop (the one taken before any failed attempt) rather than always keeping only the *most recent* | Differentiator | LOW | Triggarr's comment already states the design intent ("earliest backup taken before any failed attempt") — the cap should be designed so pruning never discards that earliest-good backup, since it's the one actually safe to restore from if the current on-disk DB is now mid-migration-corrupt. A naive "keep last N by mtime" cap could accidentally prune the one backup that matters. |
| A general-purpose scheduled/periodic backup feature (unrelated to migrations) exposed in the UI, matching *arr's user-facing Backup settings page | Anti-feature (for this milestone) | — | Out of scope — ROADMAP's target is specifically pre-upgrade migration backups being *bounded*, not a new user-facing backup/restore feature. Don't let "the *arr apps have a Backups settings page" pull in UI scope that wasn't asked for. |

**Dependency:** none — purely additive to `run_migrations`, independent of every other category in this milestone.

---

## Category: Removed-Instance Sonarr Pending Searches (bugs-005)

### Current behavior (confirmed by reading the code, and by the project's own prior deep-review finding)

Sonarr tracking already scopes correctly by stable ID — this part is *not* broken. `get_trackable_entries(db, instance_stable_id=...)` (`triggarr/db.py:991-1060`) and the pending-row cap check (`db.py:744-759`) both filter `WHERE ... instance_stable_id = ?`. The per-cycle tracking call for Sonarr (`triggarr/tracking.py:554`) always passes the *current* instance's own stable ID. So when an instance is removed and a different instance is later added under the same display name, it gets a fresh stable ID (confirmed by `.planning/backlog/MAINTENANCE.md`'s own note on this exact finding), and the new instance's tracking cycle can never select or credit the old instance's rows — **identity isolation already holds.**

What's undefined is the **lifecycle of those orphaned rows**: nothing ever queries them again (no live instance's stable ID matches), so they sit in `search_history` forever with `outcome='searched'` (pending), never resolving, and — unless a consumer explicitly filters by currently-configured stable IDs — visible in the History UI/activity rail under whatever display name the row's `instance_id` text column holds, which looks identical to a legitimately still-pending search on a live instance of the same name. This is confusing for an operator (a search that will *never* be checked again looks indistinguishable from one still in flight) and leaves `search_history` holding rows with no possible future resolution.

### A directly analogous precedent already shipped in this codebase

The v2.12 attribution cutover faced a structurally identical problem — pre-fix Sonarr pending rows that must never be credited again — and solved it with a **computed, query-time "frozen" flag**, not a row mutation: `_LEGACY_PENDING_SQL` (`db.py:670`) compares a row's id against `attribution_cutover.legacy_max_history_id`; `get_trackable_entries` always excludes rows where that predicate is true (`db.py:999, 1032`); and the UI renders them distinctly ("Legacy — tracking discontinued," `activity_rail.html:78`, `history_results.html:157`) rather than as ordinary pending rows. This establishes Triggarr's own precedent for how to make an unresolvable-pending row *visibly* terminal instead of silently inert: compute a flag at query/render time (or, alternatively, write it once at removal time) and give it a distinct UI label — "not going to resolve, and here's why" — rather than leaving it looking like a normal in-flight search.

### Classification

| Behavior | Class | Complexity | Notes |
|---|---|---|---|
| Orphaned rows stop looking like live pending searches — labeled distinctly (e.g. "Instance removed," mirroring the existing "Legacy" treatment) in History/activity-rail rendering | Table stakes | LOW-MEDIUM | Can reuse the exact mechanism already in `db.py`/templates for legacy rows: a computed exclusion from `get_trackable_entries` plus a distinct render-time label. Needs a signal for "which stable IDs are no longer configured," which `cleanup_orphaned_instances` (`state.py:323-343`) already computes for `AppState` cleanup and could be extended to flag affected `search_history` rows, OR computed at render/query time by comparing against currently-configured stable IDs (no DB write needed — closer to how `is_legacy` already works). | 
| Explicit exclusion from `get_trackable_entries` for any stable ID no longer in the removed-instance's cleanup pass (defense in depth; today's scoping already prevents this, but an explicit "never select a stable ID that isn't currently configured" guard costs little and documents the invariant in code) | Differentiator | LOW | Belt-and-suspenders on top of an already-correct mechanism; worth doing because it makes the identity-isolation invariant visible/testable at the query layer rather than only "true because nothing calls it with that ID anymore." |
| Deleting orphaned rows outright on instance removal | Anti-feature (unless explicitly requested) | — | Throws away real search history a user might want to audit later ("did Triggarr actually search before I removed that instance?"); the "Legacy" precedent in this same codebase chose to keep and label rows rather than delete them, for exactly this reason. |
| Re-attributing orphaned rows to a new instance of the same name | Anti-feature | — | This is precisely the identity-isolation violation bugs-005 was raised to prevent; explicitly ruled out by the ROADMAP wording ("no row is selected or credited by an ID other than its own"). |
| An expiry/TTL sweep job that purges old orphaned rows after N days | Possible differentiator, not required | MEDIUM | Reasonable for long-term `search_history` growth control, but it's a new scheduled job plus a retention policy decision (how long is long enough to audit?) — heavier than just labeling, and the existing bounded-history trim (`max_history_rows`, `PendingCapExceeded`) already caps *resolved* rows; orphaned pending rows under a dead stable ID would need their own cap discussion. Treat as a stretch goal, not the minimum "defined lifecycle." |

**Dependency:** relies on `cleanup_orphaned_instances`' existing notion of "configured vs. not" (`state.py:323-343`) or an equivalent live comparison; otherwise independent of every other category. No dependency on the search-delivery or backup work.

---

## Category: Telemetry (FASTAPI_OTEL_AUTO_CONFIGURE)

### Current behavior (already investigated by this project, not re-litigated here)

`.planning/backlog/MAINTENANCE.md`'s SA-12 entry records a **correction** made during the v2.12.1 release review (2026-11-14): the originally-suspected startup-failure risk from `FASTAPI_OTEL_AUTO_CONFIGURE=true` was checked directly against a locally built v2.12.1 image with the variable and an OTLP endpoint both set. FastAPI 0.162.x catches its own telemetry-setup error internally (`fastapi/telemetry/_runtime.py`, logged as "Optional telemetry setup must not prevent application startup") and logs a warning; the web UI started and answered requests normally, exporting nothing. This is already HIGH confidence from the project's own live verification, not a claim being newly evaluated here.

### Classification

| Behavior | Class | Complexity | Notes |
|---|---|---|---|
| A regression test pinning "startup succeeds with `FASTAPI_OTEL_AUTO_CONFIGURE=true` set" so a future FastAPI upgrade can't silently reintroduce a startup failure | Table stakes | LOW | The behavior is already correct; what's missing is a test that fails loudly if a future FastAPI release changes it. |
| Documentation stating telemetry export is unsupported (no OTLP collector integration is tested, maintained, or recommended) | Table stakes | LOW | Pure documentation — a line in README/docs noting the variable is inert for Triggarr's purposes beyond "doesn't break startup." |
| Building out actual OpenTelemetry export support (traces/metrics to a collector) | Anti-feature (for this milestone, and arguably for this project generally) | — | Out of scope per ROADMAP's "reduced form" framing; would add an optional dependency and configuration surface for a single-user homelab tool with no stated observability requirement (OBS-01 is explicitly parked in STATE.md's deferred items, unrelated to this). |

**Dependency:** none; fully independent, smallest item in the milestone.

---

## Feature Dependencies

```
[Instance-removal write ordering]        (independent)
[Non-object state JSON recovery]         (independent)

[Startup resource cleanup on failure]    (independent, same function as ↓)
[Shutdown per-client close isolation]    (independent, same function as ↑ — both touch create_lifespan)

[POST/command retry split]  ──enables──> [Unconfirmed-delivery tally bucket]
[Unconfirmed-delivery tally bucket]      ──feeds──> [Cycle grading / SAFETY-03 interaction decision]

[Bounded pre-migration backups]          (independent)

[cleanup_orphaned_instances' configured-ID signal] ──enables──> [Orphaned-row labeling in History/activity-rail]
[Orphaned-row labeling]                  ──analogous-to──> [existing is_legacy / Legacy-row precedent]

[FASTAPI_OTEL_AUTO_CONFIGURE regression test]  (independent)
[Telemetry-unsupported documentation]          (independent)
```

### Dependency notes

- **POST/command retry split enables the unconfirmed-delivery tally bucket:** today no code path distinguishes "the retry also failed/timed out" from "a definite error occurred" — that distinction has to exist before `CycleTally` has anything new to record. Plan these in the same phase or sequence the retry-split work first.
- **Orphaned-row labeling is analogous to, and should reuse the pattern of, the existing Legacy-row mechanism** (`_LEGACY_PENDING_SQL`, `is_legacy` rendering) — not a new UI concept. Treat the Legacy precedent as the design reference, not a fresh design problem.
- **Startup-cleanup and shutdown-isolation share one function** (`create_lifespan` in `scheduler.py`) but are logically separable changes (acquire-time vs. release-time) and can be reviewed/tested independently even if landed in the same commit.
- **Nothing in this milestone depends on the backup-bounding or telemetry items**, and they depend on nothing else — safe to sequence last or in parallel without blocking the higher-stakes correctness items (state/config, resource lifecycle, search delivery).

---

## MVP Definition (this milestone's "Done when," restated as scope)

### In scope (table stakes — matches ROADMAP's stated Active requirements)

- [ ] Validate-then-write-then-mutate ordering for instance removal (settings/jobs/clients stay consistent on a failed write)
- [ ] Non-object state JSON treated as corrupt, not a crash
- [ ] Startup failure closes whatever it already opened (db connection, already-constructed clients)
- [ ] Shutdown closes every client independently; the database always gets closed regardless of any one client's close failure
- [ ] POST to `/command`/`/api/v1/command` never blindly retries on a timed-out response; GET retries are unaffected
- [ ] A distinguishable "unconfirmed delivery" outcome exists and is kept out of both "accepted" and SAFETY-03's Failed-only counter (exact grade/counter interaction is a requirements-time decision, not resolved here)
- [ ] Pre-migration backups are bounded (count or age cap, oldest pruned, earliest-pre-crash-loop backup protected from premature pruning)
- [ ] Orphaned Sonarr search rows from a removed instance get a defined, visible lifecycle (labeled, not silently pending forever) — identity isolation (already correct) must not regress
- [ ] A regression test pins startup success under `FASTAPI_OTEL_AUTO_CONFIGURE=true`; docs note telemetry export is unsupported

### Explicitly deferred / stretch (differentiators, not required for "Done when")

- [ ] Capturing the *arr command id and polling `GET /command/{id}` to resolve "unconfirmed" into a definite outcome after the fact
- [ ] An explicit "never select a stable ID that isn't currently configured" guard in `get_trackable_entries` (defense in depth on top of already-correct scoping)
- [ ] A TTL/expiry sweep that purges (not just labels) old orphaned rows

### Anti-features (do not build, named explicitly because they're easy to reach for)

- [ ] Claiming exactly-once search-command delivery
- [ ] A generic, configurable retry framework/policy engine
- [ ] Auto-resending an unconfirmed command (immediately or on a later cycle) as if "unknown" meant "needs re-search"
- [ ] A blanket I/O-handling or resource-pool rewrite in place of the narrow lifecycle fixes above
- [ ] A new user-facing scheduled-backup feature (beyond bounding the existing pre-migration backups)
- [ ] Deleting or silently re-attributing orphaned removed-instance rows

---

## Sources

**Triggarr source (read directly for this research — HIGH confidence, primary):**
- `triggarr/web/routes.py:899-991` (`add_instance`, `remove_instance`)
- `triggarr/state.py:140-245` (`_is_v22_state_format`, `_merge_defaults`, `load_state`)
- `triggarr/search/scheduler.py:460-757` (`create_lifespan`, SAFETY-03 wiring)
- `triggarr/clients/base.py:17-315` (`_sanitize_exc`, `_request_with_retry`, `ArrClient.close`)
- `triggarr/clients/radarr.py`, `triggarr/clients/sonarr.py`, `triggarr/clients/lidarr.py` (command endpoints)
- `triggarr/search/engine.py:510-599` (`_search_and_record`)
- `triggarr/search/outcome.py:1-230` (`CycleTally`, `grade_cycle`, `cycle_view`)
- `triggarr/db.py:172-236` (pre-migration backup), `triggarr/db.py:664-1060` (legacy-pending precedent, `get_trackable_entries`, pending cap)
- `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/backlog/MAINTENANCE.md` (bugs-005, SA-12 correction, tech-debt notes)

**Radarr/Sonarr/Lidarr official source and docs (HIGH confidence, fetched directly):**
- [Radarr `CommandQueueManager.cs`](https://github.com/Radarr/Radarr/blob/develop/src/NzbDrone.Core/Messaging/Commands/CommandQueueManager.cs) — `Push<TCommand>` duplicate check (`QueuedOrStarted` + `CommandEqualityComparer`)
- [Sonarr `CommandQueueManager.cs`](https://github.com/Sonarr/Sonarr/blob/develop/src/NzbDrone.Core/Messaging/Commands/CommandQueueManager.cs) — identical dedup logic
- [Lidarr `CommandQueueManager.cs`](https://github.com/Lidarr/Lidarr/blob/develop/src/NzbDrone.Core/Messaging/Commands/CommandQueueManager.cs) — identical dedup logic
- [Servarr Wiki source, `sonarr/settings.md`](https://github.com/Servarr/Wiki/blob/master/sonarr/settings.md) — official backup Interval (7 days) / Retention (28 days) defaults, oldest-pruned-on-new-backup behavior
- [Radarr Wiki, API:Command](https://github.com/Radarr/Radarr/wiki/API:Command) — `GET /api/command`, `GET /api/command/{id}`
- [Sonarr issue #4759](https://github.com/Sonarr/Sonarr/issues/4759) — real `queued`→`completed` command-status payloads, confirming result/success is not exposed via command status
- [python-httpx exceptions documentation](https://www.python-httpx.org/exceptions/) — confirms `TimeoutException` is a `TransportError` subclass

**Comparable tools and general patterns (MEDIUM confidence, community/secondary sources, used only to corroborate — not as the basis for any claim about Triggarr's own code or the *arr apps):**
- Unraid Community Apps template for the retired `Huntarr-Sonarr` — `API_TIMEOUT`/`COMMAND_WAIT_DELAY`/`COMMAND_WAIT_ATTEMPTS` poll-after-submit pattern
- [Buildarr Sonarr/Radarr General config schema](https://buildarr.github.io/plugins/sonarr/configuration/general/) — corroborates 7-day/28-day backup defaults and a 1–90-day retention range
- [OneUptime: Retry a Timed-Out POST Without Duplicate Side Effects](https://oneuptime.com/blog/post/2026-08-14-retry-timed-out-post-idempotency/view) and related industry write-ups — three-state (confirmed-success / confirmed-failure / unknown) framing for ambiguous network responses

---
*Feature research for: Triggarr v2.14 Reliability*
*Researched: 2026-11-15*
