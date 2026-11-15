# Stack Research

**Domain:** Reliability hardening of an existing, shipped single-process app (Triggarr v2.12.1 → v2.14 Reliability)
**Researched:** 2026-11-15
**Confidence:** HIGH — every version claim below is read from `uv.lock`/`pyproject.toml`; every behavioral claim about httpx, Starlette's lifespan, `contextlib.AsyncExitStack`, and `aiosqlite` is verified against the exact installed source in `.venv/` (versions below) or the matching official docs, not training-data recall.

## Bottom line

**No new runtime or dev dependency is needed for any of the six v2.14 capabilities.** Every one is a gap in how the existing stack's own facilities are *used* (ordering, exception-type discrimination, cleanup registration), not a missing library. This matches the milestone's "zero new runtime dependencies" constraint exactly, and in two cases (connect-retry transport, exception hierarchy) the library already ships the exact tool needed — it's just not wired up yet.

| # | Capability | Facility to use | New dependency? |
|---|------------|------------------|------------------|
| 1 | Settings-write failure during instance removal | Reorder to validate→write→mutate (pattern already used in `save_settings`/`add_instance`) | No |
| 2a | Failed startup closes what it opened | `contextlib.AsyncExitStack` wrapping the lifespan body | No (stdlib) |
| 2b | One client's close failure doesn't block the rest | Per-resource `try`/`except` (or the same `AsyncExitStack`) in the shutdown loop | No (stdlib) |
| 3 | Search command timeout isn't blindly retried | httpx's own exception hierarchy + `httpx.AsyncHTTPTransport(retries=N)` | No |
| 4 | Unbounded pre-migration DB backups | `pathlib.Path.glob` + `sorted()` + `Path.unlink()` (same pattern as `max_history_rows` trim in `db.py`) | No (stdlib) |
| 5 | Removed Sonarr instance's pending searches | Same "frozen by id-boundary" SQL pattern already used for `_LEGACY_PENDING_SQL` | No |
| 6 | `FASTAPI_OTEL_AUTO_CONFIGURE` regression + doc note | FastAPI's own built-in OTel hook (already present via `opentelemetry-api`, pulled in transitively) | No |

## Pinned versions in use (verified against `uv.lock`)

| Package | Version | Relevant to |
|---|---|---|
| httpx | 0.28.1 | #3 (exception hierarchy, transport retries) |
| starlette | 1.10.0 | #2a (lifespan startup-failure semantics) |
| fastapi | 0.162.4 | #6 (native OTel auto-configure gate), #2a (lifespan wiring) |
| aiosqlite | 0.22.1 | #2b (`Connection.close()` can raise and re-raises), #4/#5 (migration backup, query shape) |
| apscheduler | 3.11.3 | #1 (job store locking semantics) |
| anyio | 4.15.1 | transitive (httpx/starlette); not directly touched |
| pydantic | 2.14.1 | transitive; `SettingsModel(**config_dict)` validation already gates #1's write |
| pydantic-settings | 2.16.1 | unchanged |
| tomlkit | 0.15.2 | unchanged (only used by the comment-preserving instance-ID backfill, not `_atomic_toml_write`) |
| python-multipart | 0.0.33 | unrelated to this milestone |
| uvicorn | 0.54.0 | unrelated to this milestone (ASGI server, drives the lifespan protocol Starlette implements) |

No version bump is required for any of these to deliver v2.14 — all facilities used below exist at the pinned versions.

---

## Capability 1 — Settings-write failure during instance removal

**Current bug, located:** `triggarr/web/routes.py::remove_instance` (lines ~938-995).

```python
async with request.app.state.search_lock:
    del instances[instance_name]            # mutates the LIVE settings object first
    config_dict = _settings_to_dict(settings)
    await ... _atomic_toml_write(config_path, config_dict)   # if this raises...
    # scheduler.remove_job / client pop / state pop never run
```

`instances = getattr(settings, app_name)` is the *same dict object* referenced by `request.app.state.settings`, so `del instances[instance_name]` mutates live state before the write is attempted. If `_atomic_toml_write` raises (disk full, permission error, serialization error — all already handled *inside* `_atomic_toml_write` by re-raising after cleanup, per `config.py:129-197`), the exception propagates out of the `async with` block: the in-memory settings object is left missing the instance, but the scheduler job, the HTTP client, and the state entry are all still there and now orphaned (the job becomes a permanent no-op because `make_search_job`'s closure re-reads `app.state.settings.get_enabled_instances(...)` and gets `None`), and the on-disk TOML still lists the instance (so a restart reintroduces a settings object that disagrees with what was in memory before the crash).

**Facility to use — no new library, just existing ordering already used elsewhere in the same file.** `save_settings` (routes.py:636-851) and `add_instance` (routes.py:882-934) both already follow the correct sequence: build a *new* validated `Settings` object off to the side (`SettingsModel(**config_dict)`), write it to disk first, and only then mutate `request.app.state.settings`/scheduler/clients/state. `remove_instance` is the one call site that does it backwards. Fixing it means copying that same three-step shape (validate-off-to-the-side → write → mutate-live-state-only-on-success), not introducing a transaction library or a settings-versioning scheme.

**APScheduler 3.11.3 note (verified from installed source, `apscheduler/schedulers/base.py`):** `add_job`/`remove_job`/`reschedule_job` each acquire `self._jobstores_lock` for the duration of that single call, so each call is individually atomic (no torn state within one `remove_job`). APScheduler provides **no** cross-call transaction — it cannot "undo" a `remove_job` if a later step fails. The ordering fix above is what has to provide that guarantee; APScheduler's locking is not a substitute for it and nothing about it needs to change.

**Integration point for capability 5 (Sonarr pending-search lifecycle) and this capability overlap here too:** the same `remove_instance` route is where a removed Sonarr instance's still-pending `search_history` rows become orphaned (see Capability 5 below) — both fixes land in the same function.

---

## Capability 2 — Resource lifecycle (startup/shutdown), narrow scope

**2a. A failed startup must close what it opened.**

Verified against Starlette 1.10.0's actual lifespan driver (`.venv/lib/python3.11/site-packages/starlette/routing.py:652-677`):

```python
async def lifespan(self, scope, receive, send) -> None:
    started = False
    await receive()
    try:
        async with self.lifespan_context(app) as maybe_state:
            ...
            await send({"type": "lifespan.startup.complete"})
            started = True
            await receive()
    except BaseException:
        ...
        if started:
            await send({"type": "lifespan.shutdown.failed", ...})
        else:
            await send({"type": "lifespan.startup.failed", ...})
        raise
```

`self.lifespan_context(app)` is exactly the `@asynccontextmanager`-wrapped generator from `create_lifespan()` in `triggarr/search/scheduler.py`. If that generator raises **anywhere before its `yield`**, the `async with` statement's `__aenter__` raises — which means `__aexit__` (the generator's `finally:` block after `yield`, where today's client-close/db-close/scheduler-shutdown teardown lives, `scheduler.py:669-755`) **never runs**, because the context was never successfully entered. This is standard `contextlib.asynccontextmanager` semantics, not a Starlette quirk, and it is directly observable in the current code: the lifespan body opens `aiosqlite.connect(db_path)` (line 496), runs `init_db`/migrations (line 509), records the attribution cutover (line 526, deliberately uncaught), and creates one `httpx.AsyncClient` per enabled instance (lines 534-544) — all *before* `yield` (line 670). A failure in any of these (a migration error, a cutover-recording error, a client constructor issue) leaks the already-opened `aiosqlite.Connection` and every already-constructed `httpx.AsyncClient` — none of them are closed, because the `finally:` after `yield` is unreachable from an exception raised before `yield`.

**Facility to use: `contextlib.AsyncExitStack` (stdlib, no new dependency).** Verified against the official docs and the CPython 3.14/3.15 source for `AsyncExitStack.__aexit__` (same unwind loop as `ExitStack.__exit__`, confirmed by direct source inspection): resources are registered as they are acquired (`stack.push_async_callback(client.close)` for each `ArrClient`, `stack.push_async_callback(db.close)` for the `aiosqlite.Connection`) inside a single `async with AsyncExitStack() as stack:` that wraps the entire lifespan body including the `yield`. Two properties make this the right tool, not a generic cleanup helper:
- If an exception is raised anywhere *before* `yield` (migration, client construction, etc.), `AsyncExitStack.__aexit__` fires and calls every callback registered *so far*, in LIFO order, before the exception propagates — this is the official documented pattern for exactly this ("All opened connections will automatically be released... even if attempts to open a connection later in the list raise an exception").
- When setup fully succeeds, execution reaches `yield` with the stack still open; resuming after shutdown and falling off the end of the `async with` block runs the same unwind — so the *existing* ordered shutdown steps (drain lock → close clients → close db) can either be expressed as `AsyncExitStack` callbacks or left as explicit code after `yield`, as long as capability 2b (below) is respected.

No `atexit`, no `anyio.CancelScope`, no third-party resource-manager library is needed — `AsyncExitStack` is designed for precisely this "acquire N things, if any later one fails release everything acquired so far" shape and has been in the stdlib since Python 3.7 (project floor is 3.11).

**2b. One client's close failure must not stop the other clients or the database from closing.**

Current code (`scheduler.py:747-753`):

```python
for app_type in APP_TYPES:
    for client in getattr(app.state, f"{app_type}_clients", {}).values():
        await client.close()          # ArrClient.close() -> self._client.aclose()
await app.state.db.close()
```

Verified from the installed `httpx` 0.28.1 source (`_client.py:1978-1988`): `AsyncClient.aclose()` calls `self._transport.aclose()` (and each mounted proxy's `aclose()`), which can raise — it is not a guaranteed-no-throw method. Verified from the installed `aiosqlite` 0.22.1 source (`core.py:199-214`): `Connection.close()` explicitly logs and **re-raises** any exception from the underlying `sqlite3.Connection.close()` rather than swallowing it. So today, if any one client's `close()` raises, the `for` loop stops immediately: every other client in that app-type's dict, every client in the remaining app types, and the final `await app.state.db.close()` are all skipped — exactly the bug this capability targets.

**Facility to use:** either (a) a `try`/`except Exception` around each `client.close()` call inside the loop, logging and continuing (matches the repo's existing "log then continue" convention used throughout `db.py`'s rollback handlers), or (b) register every client's `close` and the db's `close` with the same `AsyncExitStack` from 2a via `push_async_callback` — the CPython unwind loop (confirmed by reading `AsyncExitStack.__aexit__`'s source directly) calls **every** registered callback even when an earlier one raises, chaining exceptions via `__context__` rather than aborting the unwind. Either approach is stdlib-only; (b) is preferable if 2a's `AsyncExitStack` is already in play, since it gives both failure-tolerant startup *and* failure-tolerant shutdown from one mechanism instead of two.

---

## Capability 3 — Search-command delivery: distinguish confirmed acceptance from unknown delivery

**Current code, the actual retry bug:** `triggarr/clients/base.py::ArrClient._request_with_retry` (lines 64-99) is used for **both** `get()` and `post()` with identical logic: on `(httpx.HTTPStatusError, httpx.TransportError)`, sleep 2s and retry once, unconditionally. `post()` (line 105-107) is what every search command goes through — `RadarrClient.search_movies`, `SonarrClient.search_season`, `LidarrClient.search_albums` all call `self.post("/api/v3/command", ...)` (or `/api/v1/command` for Lidarr), which calls `_request_with_retry("POST", ...)`. `httpx.TransportError` is the parent of `httpx.TimeoutException` (which includes `ReadTimeout` and `WriteTimeout`), so a search command that times out **waiting for the response** is retried by the client itself — i.e. the exact "duplicate search" bug the milestone describes already happens inside the current retry helper, before `triggarr/search/engine.py::_search_and_record` (line 510) even gets a chance to classify the outcome. `_search_and_record` today only has two outcomes: no exception from `command()` → `tally.record_accepted()` (line 569, with the comment "the *arr committed to the search regardless of what happens next"), or any exception → `tally.record_failed(...)` (line 546) and `outcome="failed"` in `search_history`. There is no third state for "we don't know."

**Verified httpx 0.28.1 exception hierarchy** (read directly from the installed package's `_exceptions.py` docstring, which is the hierarchy httpx itself documents):

```
HTTPError
  RequestError
    TransportError
      TimeoutException
        ConnectTimeout   -- failed before the socket connected
        ReadTimeout      -- request already sent in full; waiting for response
        WriteTimeout      -- failed while sending the request body/headers
        PoolTimeout       -- failed waiting for a pooled connection; never left the pool
      NetworkError
        ConnectError      -- failed before the socket connected
        ReadError         -- failed while reading the response
        WriteError        -- failed while sending the request body/headers
        CloseError
      ProtocolError
        RemoteProtocolError  -- server violated HTTP after receiving (some of) the request
  HTTPStatusError            -- a response WAS received (confirmed, not ambiguous)
```

This maps directly onto the three states the capability asks for:

| httpx exception | Meaning for a POST to `/command` | Safe to retry? |
|---|---|---|
| `ConnectError`, `ConnectTimeout`, `PoolTimeout` | Failed before the request left the client — the body was never transmitted | **Yes** — cannot produce a duplicate |
| `WriteTimeout`, `WriteError` | Failed while sending — the server may have received a partial or complete request before the write failed | **No** — unknown delivery |
| `ReadTimeout`, `ReadError`, `RemoteProtocolError`, `CloseError` | The request was fully sent; the response was lost or malformed | **No** — unknown delivery (command may already be queued in Radarr/Sonarr) |
| `HTTPStatusError` | A response was actually received (even if 4xx/5xx) | N/A — this is a **confirmed** outcome, not ambiguous; it is not a delivery question at all |

**Facility to use — httpx's own documentation explicitly names the right tool and explicitly declines to build the alternative.** Verified from the official httpx docs (`docs/advanced/transports.md`, fetched via Context7 `/encode/httpx`):

> "Connection retries are also available via this interface. Requests will be retried the given number of times in case an `httpx.ConnectError` or an `httpx.ConnectTimeout` occurs, allowing smoother operation under flaky networks. If you need other forms of retry behaviors, such as handling read/write errors or reacting to `503 Service Unavailable`, consider general-purpose tools such as [tenacity](https://github.com/jd/tenacity)."

So httpx ships exactly the primitive this capability needs, pre-built: `httpx.AsyncHTTPTransport(retries=N)` passed as `transport=` to `httpx.AsyncClient(...)` retries **only** `ConnectError`/`ConnectTimeout` — i.e. only the pre-send failures that can never produce a duplicate POST — at the transport layer, before `_request_with_retry` ever sees an exception. That can replace part of today's hand-rolled retry for the connect-only case, for both GET and POST, with zero behavior risk.

For the remaining ambiguous cases (`WriteTimeout`/`WriteError`/`ReadTimeout`/`ReadError`/`RemoteProtocolError`/`CloseError`), the fix is a plain `isinstance` branch in `ArrClient` — no retry at all, just a distinct return/raise so `_search_and_record` can record a third outcome (e.g. `outcome="unknown"` or similar, a product/schema decision for the phase plan, not a stack question) instead of `"failed"`. `PoolTimeout` is pre-send by definition (never acquired a connection) so it is also safe alongside `ConnectError`/`ConnectTimeout`.

**GET requests keep today's broader retry.** Reads (`get_json_list`, `get_paginated`, `get_tags`, `get_total_records` — all the *fetch* side of a cycle) are idempotent; retrying them on any `TransportError` or `HTTPStatusError` carries no duplicate-mutation risk, so `_request_with_retry`'s existing behavior is correct and should be left alone for `get()`. The milestone's own framing — "keep safe retries for reads" — matches this exactly; the fix is to make `post()` use a narrower, delivery-aware path rather than sharing `_request_with_retry` unchanged with `get()`.

**Testing facility already in the repo, no new dependency:** `tests/test_clients.py` already uses `httpx.MockTransport(handler)` extensively (20+ call sites) to simulate client behavior, including handlers that raise. The same tool — a `MockTransport` handler that raises `httpx.ReadTimeout(...)` vs `httpx.ConnectError(...)` — is sufficient to test the pre-send/post-send split without `respx` or `pytest-httpx`.

---

## Capability 4 — Bound/prune timestamped pre-migration SQLite backups

**Current code:** `triggarr/db.py::run_migrations` (lines 198-219). On a crash-looping failed upgrade, every retry that finds `backup_path.exists()` (the canonical `.v{N}-backup`) writes a *new* timestamped file (`.v{N}-backup-{stamp}`) via `shutil.copy2` and never deletes any of them — intentionally, so the error message can always "point at the earliest backup taken before any failed attempt" (line 161-168, `_apply_atomic_migration`'s error log). Unbounded by design today.

**Facility to use — stdlib only, same shape already used for `max_history_rows`.** `db.py` already has a bounded-retention pattern for a different kind of accumulation: `insert_search_entry`'s resolved-row trim (`db.py:797-812`, a `DELETE ... WHERE id NOT IN (SELECT ... ORDER BY id DESC LIMIT ?)`). The filesystem equivalent needs no new library:

- `Path(db_path).parent.glob(f"{db_path.stem}.v{current}-backup*")` (or a slightly stricter pattern that also matches the canonical un-timestamped name) to enumerate candidates — `pathlib.Path.glob` is stdlib.
- Sort by the embedded timestamp (already `%Y%m%dT%H%M%S%fZ`, lexicographically sortable) or by `Path.stat().st_mtime`, keep the earliest N (the capability wants the *earliest* backup retained, per the existing error-message guarantee — so prune from the *newest* end, not oldest) and the canonical un-timestamped one.
- `Path.unlink(missing_ok=True)` (stdlib, Python 3.8+) for the ones beyond the bound, wrapped in the same `try/except OSError: logger.warning(...)` convention `db.py` already uses everywhere else for filesystem cleanup (e.g. `_atomic_toml_write`'s temp-file cleanup).

No archival/rotation library (`logrotate`-style Python packages, `tarfile` bundling, etc.) is proportionate here — this is a handful of same-directory files, and the existing code already copies with `shutil.copy2` (stdlib), so pruning with `glob`/`sorted`/`unlink` keeps the same dependency footprint.

---

## Capability 5 — Lifecycle for pending searches of a removed Sonarr instance, with identity isolation

**Where identity isolation already exists:** `triggarr/db.py::get_trackable_entries` and `get_owned_grabs` already select strictly by `instance_stable_id` (added in v2.12/schema v10, `db.py:991-1061`, `1232-1247`), and `triggarr/tracking.py::_run_sonarr_tracking_check` refuses to track at all when `instance_stable_id` is falsy (`tracking.py:541-552`, "Never share ownership between instances"). This is the correct pattern and is **already in place** — row selection and grab crediting are both scoped by the stable ID, never by display name or any other instance's ID. Nothing here needs to change to satisfy "no row selected or credited by an ID other than its own"; it already holds.

**The actual gap:** when `remove_instance` (routes.py:937-995) removes a Sonarr instance, it pops the client and the scheduler job (so no cycle, and no `run_tracking_check`, will ever run for that `instance_stable_id` again) but does nothing to the instance's pending `search_history` rows (`outcome IN ('searched', 'partial')`). Those rows are explicitly *never pruned* by `insert_search_entry`'s trim logic ("Pending rows... are never pruned; their owned grabs would otherwise be stranded uncredited," `db.py:797-800`), so they persist forever with no process that will ever resolve them — an orphan, not a leak of the SQLite file (bytes), but a leak of state that influences `get_dashboard_stats`'s pending-adjacent counts and `insert_search_entry`'s per-instance pending cap (`PendingCapExceeded`, `db.py:37-61`) for as long as the stable ID string is reused by anything (it won't be, since stable IDs are never reused — but the rows themselves sit there unresolved, visible in history UI, forever).

**Facility to use — the same SQL pattern the codebase already has for exactly this shape of problem.** `_LEGACY_PENDING_SQL` (`db.py:670-675`) already freezes a class of unresolvable pending rows by comparing `id` against a boundary recorded once in a small table (`attribution_cutover`), rather than by writing a flag onto every row — chosen specifically because "ids are AUTOINCREMENT and never reused, so this holds forever... unlike an ISO timestamp comparison." The same idiom — record `instance_stable_id` + a timestamp (or just existence) in a small table the moment an instance is removed, then exclude/relabel rows matching that `instance_stable_id` from `get_trackable_entries`'s selection and from the pending-cap count, the same way `_LEGACY_PENDING_SQL` is excluded today — needs no new library. It's a product decision (freeze-and-label vs. force-resolve-as-unresolved-at-removal-time vs. delete) that belongs in the phase plan, not in STACK.md; the mechanism is `aiosqlite` + plain SQL, already in hand.

---

## Capability 6 — `FASTAPI_OTEL_AUTO_CONFIGURE` regression + "telemetry export unsupported" doc note

**What's actually there today:** Triggarr's own source has **zero** references to OpenTelemetry or `OTEL_*` anywhere in `triggarr/`. `opentelemetry-api` 1.45.2 (the version named in the v2.12.1 CHANGELOG security fix) is a **transitive** dependency of `fastapi` itself (`uv.lock` line 300: `fastapi` → `opentelemetry-api`), not something Triggarr chose or configures. Confirmed via web search against FastAPI's own release notes: starting with FastAPI 0.143.0 (8 Oct 2026, PR #16476, "Require opt-in for automatic OpenTelemetry exporter setup"), FastAPI ships native, built-in OTel instrumentation that only attaches an *exporter* to already-configured providers when `FASTAPI_OTEL_AUTO_CONFIGURE=true` is set (or the equivalent `FastAPI(telemetry={"auto_configure": True})` code path) — the pinned 0.162.4 is well past that opt-in change. Because Triggarr's lockfile does **not** include `opentelemetry-sdk` or any `opentelemetry-exporter-otlp-*` package, FastAPI's auto-configure path has no SDK/exporter to attach even if the env var is set — only the no-op API is present.

**Facility to use — none new; this is a regression test against FastAPI's own feature plus one documentation sentence.** No library changes. The regression test is: set `FASTAPI_OTEL_AUTO_CONFIGURE=true` (and optionally `OTEL_EXPORTER_OTLP_ENDPOINT`) in the test environment, drive `create_lifespan`/the full app through startup the same way `tests/test_scheduler.py` already does (`async with lifespan_fn(app): ...`, or `fastapi.testclient.TestClient(app)` for a full ASGI-level check — both already used in-repo, no new tool), and assert startup completes without raising. PROJECT.md records that this already passes as of the 2026-11-14 correction; the work here is pinning that down as a permanent regression test, plus a one-line doc note (e.g. in `docs/operations/` or `SECURITY.md`) that Triggarr does not install or support an OTel SDK/exporter, so operators should not expect telemetry data to actually leave the process even with the env var set.

---

## What NOT to Add

| Avoid | Why | Use instead |
|---|---|---|
| `tenacity` / `backoff` / `stamina` / any generic retry framework | Milestone constraint is explicit ("no generic retry framework"); httpx's own docs point to `tenacity` specifically for the broader cases (read/write errors, 503 handling) this project is deliberately *not* trying to solve generically — Triggarr needs a narrow, delivery-aware decision for one endpoint shape (`/command` POST), not a configurable retry policy engine | `httpx.AsyncHTTPTransport(retries=N)` (connect-only, built into httpx) + explicit `isinstance` branching on httpx's own exception hierarchy |
| `respx` / `pytest-httpx` | Zero-dependency constraint; the repo already has a working, extensively-used pattern (`httpx.MockTransport`) that covers raising arbitrary httpx exceptions from a handler, which is all these capabilities' tests need | `httpx.MockTransport(handler)`, already used 20+ times in `tests/test_clients.py` |
| A Python logrotate/backup-rotation package for the pre-migration DB backups | A handful of same-directory `.v{N}-backup*` files is not a log-rotation problem; `shutil.copy2` is already how they're created | `pathlib.Path.glob` + sort + `Path.unlink(missing_ok=True)`, mirroring the existing `max_history_rows` DELETE-trim pattern in `db.py` |
| `opentelemetry-sdk` / `opentelemetry-exporter-otlp-*` | Out of scope — the milestone explicitly wants telemetry export documented as *unsupported*, not wired up; adding the SDK/exporter would be the opposite of this capability's intent | Doc note only; leave `opentelemetry-api` as the transitive, inert dependency it already is |
| `anyio.CancelScope`/`TaskGroup`-based rewrite of the shutdown sequence | Milestone explicitly scopes out "a blanket I/O or offloading rewrite" — `asyncio.timeout()` is already used correctly for the shutdown drain (`scheduler.py:715`, chosen specifically over `asyncio.wait_for` for its `CancelledError` safety) | Keep `asyncio.timeout()` / plain `try`/`except`/`finally`; add `contextlib.AsyncExitStack` only around the resource-acquisition/release bracket (2a/2b), not the whole shutdown control flow |
| A settings-versioning or transactional-config library (e.g. a diff/rollback framework) for capability 1 | The fix is pure ordering (validate → write → mutate), already the pattern in two of three call sites in the same file | Match `save_settings`/`add_instance`'s existing sequence in `remove_instance` |

## Version Compatibility

| Package @ version | Compatible with | Notes |
|---|---|---|
| httpx 0.28.1 | `httpx.AsyncHTTPTransport(retries=N)` constructor arg | Present since httpx 0.21; unchanged shape in 0.28.1, confirmed in installed `_transports/default.py` behavior described by the official docs fetched above |
| httpx 0.28.1 exception hierarchy | Used throughout `triggarr/clients/base.py`, `triggarr/search/engine.py`, `triggarr/tracking.py` today | The hierarchy quoted above is read from the *installed* `_exceptions.py` module docstring, not assumed from memory — it is the authoritative, version-matched source |
| starlette 1.10.0 lifespan driver | fastapi 0.162.4 (FastAPI delegates lifespan entirely to Starlette's `Router.lifespan`) | The `started`/`lifespan.startup.failed` logic quoted above is this exact installed version, not a generic description of "ASGI lifespan" |
| aiosqlite 0.22.1 `Connection.close()` | Python 3.11+ (project floor) | Re-raise-after-log behavior confirmed in installed `core.py`; no version-specific difference expected for 3.11 vs the Docker image's 3.13 |
| `contextlib.AsyncExitStack` | Python 3.7+ (project floor 3.11, Docker 3.13) | No behavior difference across 3.11–3.13 relevant here; unwind-loop semantics (all callbacks run even if one raises) confirmed by reading the loop in a locally installed CPython build, matching the documented `ExitStack`/`AsyncExitStack` contract |

## Sources

- `.venv/lib/python3.11/site-packages/httpx/_exceptions.py` (installed httpx 0.28.1) — exception hierarchy, read directly, HIGH confidence
- Context7 `/encode/httpx`, topic "exception hierarchy... retry safety... transport-level retries" — `docs/exceptions.md`, `docs/advanced/timeouts.md`, `docs/advanced/transports.md` — confirms `AsyncHTTPTransport(retries=N)` only retries `ConnectError`/`ConnectTimeout`, and that httpx itself recommends `tenacity` only for the broader cases this project declines, HIGH confidence
- `.venv/lib/python3.11/site-packages/starlette/routing.py:652-677` (installed starlette 1.10.0) — `Router.lifespan` startup-failure behavior, read directly, HIGH confidence
- [python docs.python.org contextlib — `AsyncExitStack`](https://docs.python.org/3/library/contextlib.html#contextlib.AsyncExitStack) (fetched 2026-11-15) — API and unwind-on-exception contract, HIGH confidence
- Locally installed CPython `contextlib.py` (`ExitStack.__exit__` / `AsyncExitStack.__aexit__` source, read directly) — confirms all registered callbacks run even when one raises mid-unwind, HIGH confidence
- `.venv/lib/python3.11/site-packages/aiosqlite/core.py:199-214` (installed aiosqlite 0.22.1) — `Connection.close()` re-raise behavior, read directly, HIGH confidence
- `.venv/lib/python3.11/site-packages/httpx/_client.py:1978-1988` (installed httpx 0.28.1) — `AsyncClient.aclose()` can raise, read directly, HIGH confidence
- `.venv/.../apscheduler/schedulers/base.py` (installed apscheduler 3.11.3) — `add_job`/`remove_job`/`reschedule_job` per-call locking, read directly, HIGH confidence
- WebSearch, "FASTAPI_OTEL_AUTO_CONFIGURE environment variable" → FastAPI release 0.143.0 notes and PR #16476 — MEDIUM confidence (web search, not Context7, but corroborated by the lockfile actually containing `opentelemetry-api` as a `fastapi` dependency and by PROJECT.md's own 2026-11-14 record that startup already survives the variable)
- Triggarr source read directly: `triggarr/clients/base.py`, `triggarr/search/scheduler.py`, `triggarr/search/engine.py`, `triggarr/web/routes.py`, `triggarr/config.py`, `triggarr/db.py`, `triggarr/state.py`, `triggarr/tracking.py`, `tests/test_clients.py`, `tests/test_scheduler.py` — current-behavior claims about retries, lifespan, instance removal, backups, and pending-search handling are all cited to exact line ranges above, HIGH confidence
- `pyproject.toml`, `uv.lock` — all pinned versions, HIGH confidence

---
*Stack research for: Triggarr v2.14 Reliability milestone*
*Researched: 2026-11-15*
