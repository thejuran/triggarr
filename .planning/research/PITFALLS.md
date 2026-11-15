# Domain Pitfalls: v2.14 Reliability

**Domain:** Hardening fixes layered onto a running single-process FastAPI/APScheduler/aiosqlite daemon (Triggarr v2.12.1, ~3300 tests)
**Researched:** 2026-11-15
**Confidence:** HIGH for all pitfalls grounded in current `triggarr/` source (cited by file:line) and library source/docs (cited below); MEDIUM where the fix design itself is still open and the pitfall is about a class of design mistake rather than an existing line of code.

This file is written against the actual v2.14 target capabilities in `.planning/PROJECT.md` ("Current Milestone: v2.14 Reliability") and `.planning/ROADMAP.md`. Capabilities are referenced by their PROJECT.md id/name since phase numbers are assigned at roadmap-writing time, not yet known. Every pitfall below was verified by reading the current implementation, not inferred from the capability description alone — "read the code first" is itself the top-level lesson of this research pass, because several of these bugs are *already present and already uncovered by the current test suite*, not hypothetical regressions a fix might introduce.

## Critical Pitfalls

### Pitfall 1: Blind POST retry conflates "never sent" with "maybe sent"

**What goes wrong:**
`ArrClient._request_with_retry` (`triggarr/clients/base.py:64-99`) is the single retry path shared by **every** HTTP verb, including the three search-command POSTs: `RadarrClient.search_movies` (`clients/radarr.py:61-64`), `SonarrClient.search_season` (`clients/sonarr.py:172-175`), `LidarrClient.search_albums` (`clients/lidarr.py:93-96`) — all three call `self.post(...)` which calls `_request_with_retry`. On the first failure it catches `(httpx.HTTPStatusError, httpx.TransportError)`, sleeps 2s, and **resends the identical POST**. `httpx.TransportError` is the base class for `ConnectTimeout`, `ReadTimeout`, `WriteTimeout`, `PoolTimeout`, `ConnectError`, `ReadError`, `WriteError`, `CloseError`, `ProtocolError` (incl. `RemoteProtocolError`), `ProxyError`, and `UnsupportedProtocol` ([httpx exception hierarchy](https://www.python-httpx.org/exceptions/)). A `ConnectError`/`ConnectTimeout` means the TCP/TLS handshake never completed — the *arr server never saw the request, so resending is safe. A `ReadTimeout`, `WriteTimeout`, `RemoteProtocolError`, or `PoolTimeout` on a **pooled, reused connection** (Triggarr's clients are long-lived `httpx.AsyncClient` instances created once in the lifespan, `search/scheduler.py:538-543`, and reused for the life of the process) means the request body may already be on the wire and the *arr server may already have accepted and started the `SeasonSearch`/`MoviesSearch`/`AlbumSearch` command — resending creates a second, real search command. On a hot connection pool, `PoolTimeout` specifically means the client never even got a connection to send on (a true "never sent" case, like `ConnectTimeout`), but it is handled identically to `ReadTimeout` today — i.e. the current code does not just fail to distinguish "safe" from "unsafe" retries, it does not distinguish within the unsafe bucket either in a way future code could reuse.

**Why it happens:**
`_request_with_retry` was written as one generic retry-on-transient-failure helper for GETs (pagination, tag lists, status checks) where retrying is always safe, and POST commands were added later by reusing the same helper rather than writing a POST-specific path. Nothing in the method signature or call site distinguishes "idempotent read" from "non-idempotent command" — the risk is invisible unless you read the exception hierarchy and ask "could the first attempt have reached the server?"

**How to avoid:**
Split the retry policy by HTTP verb and by exception class, not just by exception base class. For GET (`get`, `get_json_list`, `get_paginated`, `get_total_records`, `get_tags`) keep the existing blind-retry — reads are idempotent and this is correct. For the three search-command POSTs, only retry (or treat as "safe to resend") on exceptions that are structurally guaranteed never-sent: `httpx.ConnectError`, `httpx.ConnectTimeout`. Every other `TransportError` subtype on a POST command must be treated as "delivery unknown" (see Pitfall 2), not retried, and not silently equated with either success or failure. Triggarr's own `tracking.py` already models this instinct correctly in a different spot: `_get_episode_cached` and `_get_series_episode_map` (`triggarr/tracking.py:309-376`) catch `httpx.TransportError` specifically (not the blanket `httpx.HTTPError`) and open a circuit breaker rather than retrying blindly — follow that existing in-repo precedent for the POST path rather than inventing a new style.

**Warning signs:**
- A fix that changes only the *log message* for a timeout ("request timeout" vs "connect timeout") without changing retry behavior has not actually fixed anything.
- A fix that keeps `search_movies`/`search_season`/`search_albums` routed through the shared `_request_with_retry` with no verb- or exception-class branch has not fixed anything — retries still duplicate ambiguous-delivery commands.
- Grep for `httpx.TransportError` and `httpx.HTTPError` in `clients/base.py` after the fix: if the POST path still catches the same tuple as the GET path, the distinction was not implemented.

**Test that catches it:** Extend `tests/test_clients.py`'s existing `httpx.MockTransport`-based retry tests (`test_request_with_retry_retries_on_failure`, `test_request_with_retry_reraises_when_retry_fails`, `clients/base.py:130-168`) with a new POST-specific suite: a handler that raises `httpx.ConnectError` once then succeeds (expect retry → one real command sent) and a parallel case that raises `httpx.ReadTimeout` once then would succeed (expect **no** second POST — assert the handler's call count is 1, or that the retry path raises/returns an "unknown" result instead of resending). `httpx.MockTransport`'s handler can raise any exception class directly, so this does not require network simulation.

**Phase to address:** Search-command delivery (target capability: "A timed-out search command is not blindly retried into a duplicate search").

---

### Pitfall 2: Unknown delivery gets forced into "failure" or "success," corrupting the counter it was supposed to protect

**What goes wrong:**
`_search_and_record` (`triggarr/search/engine.py:510-599`) wraps every search command in exactly two outcomes: `except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)` → `tally.record_failed(reason)` (line 546), or no exception → `tally.record_accepted()` (line 569, with the comment "Command accepted — the *arr committed to the search regardless of what happens next"). `httpx.HTTPError` is the base of *every* httpx exception including the ambiguous-delivery `TransportError` subtypes from Pitfall 1. So today, a `ReadTimeout` on a search POST — where the *arr may have already started the search — is recorded as a hard failure. That failure count feeds `CycleTally.to_record()` → `ist["last_cycle"]["grade"]` (`_finalize_cycle`, `engine.py:602-619`), and `_evaluate_cycle_outcome` (`search/scheduler.py:303-342`) reads exactly that grade to decide whether to call `_record_cycle_failure`, which increments `app.state.search_failures[job_id]` — the counter CLAUDE.md and the SAFETY-03 history describe as "counts Failed only." A run of ambiguous timeouts (e.g. a slow Sonarr instance under load) will therefore escalate the consecutive-failure counter to ERROR and, eventually, the dashboard's Failed grade — even on cycles where every command may well have succeeded. The inverse mistake — treating unknown delivery as success — is just as real a risk for a fix that goes the other way: crediting `tally.record_accepted()` whenever the retry path can't prove the command failed would inflate `last_successful_search`, the dashboard's accepted count, and (for Sonarr) eventually look like fodder for grab-ownership credit it never earned.

**Why it happens:**
The existing code (correctly, per OUTCOME-06/R-04 from v2.12) has exactly two buckets because historically every path into this function really was binary: either the HTTP call raised or it didn't. Introducing a third, genuinely ambiguous outcome ("sent, but we don't know if it landed") does not fit `CycleTally`'s two-counter model (`accepted`/`failed`) without a deliberate decision about which existing counter — or a new one — an "unknown" result feeds, and that decision has real consequences for SAFETY-03, for the dashboard's Success/Partial/Failed/Nothing-needed grading (locked in the v2.12 design spec), and for whether a "Partial" grade (already an existing grade value) is the right place for "unknown," rather than inventing a new grade.

**How to avoid:**
Treat "unknown delivery" as its own outcome bucket from the exception class onward (don't let it fall through to the `httpx.HTTPError` catch-all). Decide, explicitly and in the design doc, whether an unknown-delivery result: (a) counts toward neither `accepted` nor `failed` (safest — it changes neither SAFETY-03 nor the "last successful search" timestamp, but still needs a surfaced reason so the cycle doesn't silently look like "nothing needed"), or (b) is folded into an existing bucket with a documented justification. Whichever is chosen, it must be visible in `ist["last_cycle"]["failure_reasons"]` or a new field so an operator can tell "0 failed, but 2 unknown" from "0 failed, 0 unknown." Do not let SAFETY-03's `max_consecutive_failures` escalate on ambiguous-delivery results the way it already correctly does *not* escalate on a count-only refresh (`search_now`'s sibling endpoint never touches `search_failures` — that existing asymmetry is the right model to imitate: a new category of result should get a similarly deliberate decision about which counters it touches, not an accidental one by falling through a catch-all).

**Warning signs:**
- The fix adds a new `httpx.TransportError`/ambiguous-timeout branch inside `_search_and_record` but still calls `tally.record_failed(...)` or `tally.record_accepted()` from it — that's the same bug with better logging.
- `CycleTally`'s dataclass gains no new field/counter and `to_record()` gains no new key, yet the capability claims to "distinguish confirmed acceptance from unknown delivery" — if nothing downstream can observe the distinction, it isn't implemented, it's just caught and discarded.
- Mark-on-attempt (Pitfall 3 below) already added the item to the searched-log by the time `_search_and_record` runs — if the fix also makes an "unknown" item eligible for immediate re-search (e.g. by trying to remove it from the log), it reintroduces the duplicate-search risk this whole capability exists to close.

**Test that catches it:** A scheduler-level test (pattern: `tests/test_scheduler.py`'s existing `test_failure_counter_increments_on_grade_failed` / `test_failure_counter_resets_on_grade_success_after_failed`, `search/scheduler.py:232-723`) that runs one cycle where the only command raises `httpx.ReadTimeout`, then asserts `app.state.search_failures[job_id]` is **unchanged** from its pre-cycle value (not incremented) and that `ist["last_cycle"]["grade"]` is not `"failed"` purely from that ambiguous result. Pair it with an engine-level test asserting `tally.accepted` was **not** incremented either, so neither counter silently absorbed the ambiguity.

**Phase to address:** Search-command delivery.

---

### Pitfall 3: Sanitizing the exception before deciding retry-safety erases the information the decision needs

**What goes wrong:**
`_sanitize_exc` (`triggarr/clients/base.py:17-33`) deliberately collapses every `httpx.TimeoutException` subtype — `ConnectTimeout`, `ReadTimeout`, `WriteTimeout`, `PoolTimeout` — into the single string `"request timeout"`, and only distinguishes `HTTPStatusError` and "other httpx error" beyond that. This is correct and intentional for *logging* (CLAUDE.md: never leak internals; a sanitized, type-collapsed string is exactly what should reach a log line or a stored `detail` column). But if a retry-safety or unknown-delivery decision is implemented by inspecting the *sanitized string* instead of the original exception object — e.g. a helper that takes `reason: str` and does `if "timeout" in reason` — it has already lost the ConnectTimeout-vs-ReadTimeout distinction that the whole fix depends on, because `_sanitize_exc` erased it by design before the string existed.

**Why it happens:**
`_sanitize_exc` is called early in most except blocks (`engine.py:539`, `base.py` retry-failure log at line 93-97) specifically so logging never touches raw exception internals. It's an easy, natural-looking move to reuse that same string for a second purpose (deciding what to do next) since it's already computed and "looks like" a classification.

**How to avoid:**
Keep the retry/unknown-delivery decision as an `isinstance()` check against the live exception object, at the point where it's still the real exception — inside `_request_with_retry`'s except clause or immediately in the POST wrapper — before any call to `_sanitize_exc`. `_sanitize_exc` stays purely a logging/storage concern downstream of that decision, exactly as it is today for every other call site.

**Warning signs:** A new retry/delivery-classification function whose signature takes `str` instead of `Exception`, or that is called after `_sanitize_exc` in the control flow.

**Test that catches it:** A unit test on the new classifier (whatever it's named) passing the actual exception instances `httpx.ConnectTimeout(...)`, `httpx.ConnectError(...)`, `httpx.ReadTimeout(...)`, `httpx.RemoteProtocolError(...)`, `httpx.PoolTimeout(...)` and asserting each maps to the intended bucket — if the classifier only accepts strings, this test can't even be written against real exception types, which is itself the signal.

**Phase to address:** Search-command delivery.

---

### Pitfall 4: Write-before-mutate gets the order backwards in `remove_instance` — settings are corrupted in memory before the disk write even runs

**What goes wrong:**
`remove_instance` (`triggarr/web/routes.py:937-995`) does:
```python
instances = getattr(settings, app_name)        # line 950 -- the LIVE dict object on settings
...
async with request.app.state.search_lock:
    del instances[instance_name]               # line 958 -- mutates settings in place, BEFORE any write
    config_path = request.app.state.config_path
    config_dict = _settings_to_dict(settings)   # line 962 -- built from the ALREADY-mutated settings
    await asyncio.get_running_loop().run_in_executor(
        None, _atomic_toml_write, config_path, config_dict
    )                                            # line 963-965 -- can still raise OSError
    # scheduler.remove_job, clients_dict.pop, triggarr_state.pop, tag_cache.pop all come AFTER this
```
`Settings.radarr`/`sonarr`/`lidarr` are plain mutable `dict[str, InstanceConfig]` fields (`triggarr/models/config.py:200-202`); `getattr(settings, app_name)` returns the same dict object stored on `request.app.state.settings`, not a copy. So `del instances[instance_name]` permanently removes the instance from the **live, in-memory, process-wide** settings object the instant it runs — before `_atomic_toml_write` has even been attempted. If that write then fails (disk full, permission error, read-only filesystem on a misconfigured volume — exactly the scenario `test_save_settings_propagates_write_failure`, `tests/test_web.py:856-883`, already proves `_atomic_toml_write` can raise via `OSError`), the exception propagates out of the `async with` block and the function returns with a 500, having never reached the scheduler-job-removal, client-pop, or state-pop lines. The result: the instance is gone from `request.app.state.settings` (so the UI stops showing it and a user could even try to re-add the same name), the on-disk `triggarr.toml` still lists it (since the write failed), and the **scheduler job and httpx client are still live** — but the job's closure (`search/scheduler.py:166-168`) reads `app.state.settings.get_enabled_instances(app_name).get(instance_name)`, which is now `None`, so the job silently no-ops forever instead of searching, while its `httpx.AsyncClient` stays open and leaked until something else happens to touch that instance name. This is precisely the "partial mutation of in-memory config, scheduler jobs, client registry" failure mode the milestone names, and it already exists in shipped code today — it is not a hypothetical regression.

Contrast this with the **correct** pattern already used two functions away in the same file: `save_settings` (`routes.py:635-851`) builds and validates `new_settings = SettingsModel(**new_config)` (line 717) *before* touching `request.app.state.settings`, writes to disk first (line 727-729), and only assigns `request.app.state.settings = new_settings` on line 731 — which is unreachable if the write on the previous line raised. `add_instance` (`routes.py:882-934`) follows the same order. `remove_instance` is the one outlier that mutates first.

**Why it happens:**
`remove_instance` predates the "validate and serialize before touching live state" discipline that `save_settings`/`add_instance` already follow, and removal "felt" simpler — there's no new data to validate, just a key to delete — so it was written as "delete, then persist" rather than "compute the replacement, persist it, then delete." The bug is invisible under every happy-path test because `_atomic_toml_write` almost always succeeds in CI and local dev.

**How to avoid:**
Reorder to compute the post-removal config from a **copy** (or from `settings.model_copy(deep=True)`/a freshly-built dict with the key omitted) without mutating `settings.radarr`/etc. in place, validate it if there's any validation step, write it to disk, and only *after* the write succeeds perform the in-memory `del`, scheduler-job removal, client pop, and state pop — mirroring `save_settings`'s existing order exactly. If any one of the in-memory cleanup steps (scheduler removal, client pop, state pop) can itself raise, decide and document what "partially cleaned up" means for that case too — `db.py`'s `_apply_atomic_migration` (`triggarr/db.py:114-169`) already has a precedent for this exact concern (rollback-might-itself-fail, logged distinctly from the original error) worth mirroring in spirit, not necessarily in code.

**Warning signs:**
- Any route handler that calls `del some_dict[key]`, `.pop(key)`, or otherwise mutates a `request.app.state.settings` sub-dict **before** the line that writes to disk.
- A diff to `remove_instance` that changes only the `_atomic_toml_write` error handling (e.g. wrapping it in try/except) without changing where the `del` happens — that masks the symptom (the 500 might go away) without fixing the actual inconsistency (settings/jobs/clients can still end up disagreeing).

**Test that catches it:** Reuse the exact existing pattern from `test_save_settings_propagates_write_failure` (`tests/test_web.py:856-883`): `patch("triggarr.web.routes._atomic_toml_write", side_effect=OSError("disk full"))`, call `POST /api/instance/remove/{app}/{instance}`, then assert — not just a 500 status, but the full postcondition the capability names — that `request.app.state.settings` (or a fresh `getattr(app.state.settings, app_name)`) **still contains** the instance, that `scheduler.get_job(job_id)` is **still present**, and that the instance's client is **still** in `{app_name}_clients`. Note that today's one existing negative test for `save_settings` only asserts the HTTP status, not these postconditions — the new tests for this capability should go further than that precedent, not just copy it.

**Phase to address:** State/config consistency (target capability 999.9).

---

### Pitfall 5: Non-dict state JSON (`[]`, `42`, `null`) crashes instead of recovering — and is already a **documented, accepted** crash today

**What goes wrong:**
`load_state` (`triggarr/state.py:210-245`) calls `json.load(f)` and only catches `(json.JSONDecodeError, OSError)` before handing the parsed `data` to `_is_v22_state_format(data)` (`state.py:140-152`), which immediately calls `data.get(section, {})`. If `state.json` contains valid JSON that isn't an object — `[1, 2, 3]`, `42`, `null`, `"a string"` — `json.load` succeeds, and `.get()` on a `list`/`int`/`NoneType`/`str` raises `AttributeError`, which is **not** in the caught tuple and propagates out of `load_state`, crashing startup. This is already proven and intentionally left unfixed: `tests/test_state.py:407-420`'s `test_state_wrong_structure_list_crashes` writes `"[1, 2, 3]"` and asserts `pytest.raises(AttributeError)`, with a docstring that says in full: *"This is a known gap (not ideal but acceptable for a single-user daemon). When load_state is hardened to handle non-dict roots, convert this test to assert recovery to defaults instead."* `_merge_defaults` (`state.py:171-207`) has the *same* exposure one level down — it already guards `isinstance(loaded_section, dict)` per app-key (which is why `test_state_wrong_nested_type_recovers` passes for `{"radarr": "not_a_dict"}`), but that guard only exists because `loaded` itself is already confirmed to be a dict by the time `_merge_defaults` runs; it does nothing for a non-dict *root*.

**Why it happens:**
The corrupt-JSON recovery path (`json.JSONDecodeError`) was built for the "file got truncated/corrupted mid-write" case, where the content literally fails to parse. Valid-but-wrong-shape JSON parses fine and only fails later, deeper in the call stack, in a function (`_is_v22_state_format`) that was written assuming its caller already guaranteed a dict — which was true until someone (or something — a bad `os.replace` source, a manual edit, a future serialization bug) writes a non-object root.

**How to avoid:**
Add an `isinstance(data, dict)` check in `load_state` immediately after `json.load` succeeds, before calling `_is_v22_state_format`/`_merge_defaults`, and treat a non-dict root exactly like the existing corrupt-JSON path: log a warning naming the type (never the contents — follow the existing `test_state_corrupt_warning_names_reason_without_contents` convention, `tests/test_state.py:440+`, which already asserts the warning never echoes raw file content) and return `_default_state()`. This is a small, localized fix — the two migration-detection helpers (`_is_v22_state_format`, `_migrate_v22_state`) do not need their own internal guards if the caller already guarantees a dict root.

**Warning signs:**
- A fix that adds `isinstance` checks deep inside `_is_v22_state_format` or `_merge_defaults` instead of once at the `load_state` entry point — redundant guards in multiple places are a sign the actual contract ("data is always a dict past this point") was never established centrally.
- `test_state_wrong_structure_list_crashes` still asserting `pytest.raises(AttributeError)` after the fix lands — the test's own docstring says explicitly to flip this assertion to "recovers to defaults" once hardened; leaving it as-is means the fix wasn't actually applied to the code path the test exercises.

**Test that catches it:** Flip `test_state_wrong_structure_list_crashes` per its own docstring instruction, and add siblings for `42`, `null`, and `"a string"` roots — all should recover to `_default_state()` with a warning logged, none should raise.

**Phase to address:** State/config consistency (999.9).

---

### Pitfall 6: A failed startup leaks what it opened — and a leaked `aiosqlite` connection isn't just "untidy," it can hang the whole process

**What goes wrong:**
`create_lifespan`'s `lifespan` function (`triggarr/search/scheduler.py:479-757`) has **no try/except around any of its setup code**. Everything from `db = await aiosqlite.connect(db_path)` (line 496) through `scheduler.start()` (line 652) and the `update_check_job` scheduling (line 661-667) runs with no protection; the `try: yield / finally: <cleanup>` block (line 669-755) only wraps the code *after* all of that setup already ran. If any step after the db connection opens — `init_db`/`run_migrations` failing on a bad migration, `ensure_cutover_recorded` raising, an `httpx.AsyncClient(...)` constructor raising (e.g. an invalid proxy env var), or `scheduler.add_job`/`scheduler.start()` raising — throws an exception, that exception propagates out of the async generator **before** it ever reaches its own `try:` statement. Starlette's lifespan handler (`starlette/routing.py:652-677`, confirmed from the installed package) treats any exception raised while inside `async with self.lifespan_context(app)` (i.e. before our generator's first `yield`) as `lifespan.startup.failed` and re-raises; uvicorn's `LifespanOn.startup()` (`uvicorn/lifespan/on.py:46-58`, confirmed from the installed package) sets `should_exit = True` and the process is expected to exit — but our generator's `finally:` block (the one that calls `scheduler.shutdown()`, closes every client, and calls `await app.state.db.close()`) is **never entered**, because the exception happened before the matching `try:`. Nothing we wrote runs `db.close()` or `client.close()` on this path.

This matters more than "a resource leak the OS will clean up on exit," because `aiosqlite.Connection.__await__` (`.venv/.../aiosqlite/core.py:176-178`) starts a plain `threading.Thread` with no `daemon=True` set (confirmed from the installed package: `Thread(target=_connection_worker_thread, args=(self._tx,))`, `core.py:90`), and that worker thread's loop (`_connection_worker_thread`, `core.py:48-76`) blocks on `tx.get()` **forever** until it processes the one special `_STOP_RUNNING_SENTINEL` job that only `Connection.close()`/`Connection.stop()` ever enqueue. Per the Python docs, the interpreter will not exit while any non-daemon thread is alive. So: a startup failure that leaves `db` connected and never calls `db.close()` does not just leak a file descriptor — it leaves a background thread that will never terminate, which means the Python process itself will not exit on its own. In a Docker deployment this converts "migration failed, log an error, exit cleanly, let the restart policy try again" into "process hangs until the container's stop/kill grace period elapses and Docker SIGKILLs it" — on every single restart attempt, for as long as the underlying failure (e.g. a bad migration) persists. Combined with Pitfall 9 (unbounded backup files on every failed migration attempt), a crash-looping upgrade failure becomes slow *and* disk-filling instead of fast and bounded.

**Why it happens:**
The lifespan function was written to assume its own setup code "can't really fail" in practice (it mostly hadn't, across 19 shipped milestones), so the only error-handling investment went into the shutdown path people actually exercise on every graceful restart. `yield`-based `@asynccontextmanager` generators make this an easy trap: code before `yield` and code in a `try/finally` wrapping the `yield` *look* similar in a diff but have completely different exception semantics, and nothing in the file's existing structure calls that out.

**How to avoid:**
Track what's been opened as the setup proceeds (the db connection, the list of constructed clients so far) and wrap the acquisition section in its own `try/except Exception`, closing whatever was opened so far (in reverse order) before re-raising the original exception un-mangled, so the operator still sees the real migration/config error rather than a close-time error. This does not need to be elaborate — even a single `except Exception: await db.close(); for c in already_created_clients: await c.close(); raise` around the setup block, built incrementally as each resource is created, closes the gap. Whatever shape it takes, verify by test that `db.close()` (or the stand-in mock) is actually called when a setup step after it raises — don't just verify the exception still propagates, since it already does today.

**Warning signs:**
- A fix that adds a try/except only around `init_db`/`run_migrations` specifically (since that's the "scary" step) but leaves client construction, `ensure_cutover_recorded`, or `scheduler.start()`/`scheduler.add_job()` unprotected — any of those can still leak the already-opened db connection.
- A fix that closes clients/db in the except handler but swallows the original exception instead of re-raising it — startup should still fail loudly; only the leak should be fixed.

**Test that catches it:** Using the existing in-repo pattern of calling the lifespan context manager directly in tests (`tests/test_scheduler.py:974-998`, `async with lifespan_fn(app): ...`), patch `init_db` (or any later setup call) to raise, assert the `async with` block raises, and assert — via a spy/mock on `aiosqlite.connect`'s return value or on the real connection object — that `.close()` was called on it despite the failure. This test should fail against the current code (proving the gap) and pass once the fix lands.

**Phase to address:** Resource lifecycle (999.13, narrowed — "a failed startup closes what it opened").

---

### Pitfall 7: Shutdown's client-close loop has no per-client isolation — one failure skips every client after it *and* skips closing the database

**What goes wrong:**
The shutdown half of the same lifespan (`search/scheduler.py:747-753`):
```python
for app_type in APP_TYPES:
    for client in getattr(app.state, f"{app_type}_clients", {}).values():
        await client.close()        # no try/except
await app.state.db.close()          # unreached if any close() above raises
```
has no exception handling at all. `ArrClient.close()` delegates to `httpx.AsyncClient.aclose()`, which the installed httpx source shows is state-guarded (`if self._state != ClientState.CLOSED: ...`, `httpx/_client.py:1978-1988`) and normally idempotent/quiet — but Triggarr's own test suite has already empirically proven `aclose()` is **not** always quiet when a request is in flight at close time. `tests/test_clients.py:171-278` (TEST-04, Codex finding 4) documents, against the real production transport (`httpx.ASGITransport`, not just `MockTransport`), that closing a client with an in-flight, non-cancelled request produces a deterministic `AssertionError` from inside `httpx/_transports/asgi.py` on the httpx version pinned today (0.28.1), with an explicit comment that "a future httpx release that intentionally changes this contract... will fail test 3 deliberately." The shutdown sequence in `scheduler.py` *does* try to drain the search lock first (step 2, lines 675-745) so in-flight cycles usually finish before step 3's close loop — but the drain itself is timeout-bounded and explicitly designed to give up and "force close" (`logger.warning("...forcing close")`, line 726-732) when the drain doesn't finish in time, meaning the close loop can absolutely run against a client with work still in flight, and can raise something that is not even an `httpx` exception type.

If any client's `close()` raises — for any reason, httpx-shaped or not — the `for` loop stops at that client: every subsequent client in that app type, and every client in the app types not yet reached in the outer loop, never gets `close()` called, **and** `await app.state.db.close()` on the next line never runs either. Per Pitfall 6's aiosqlite finding, that specifically means the db's worker thread is left running forever, with the same process-hang consequence.

**Why it happens:**
The loop was written assuming `close()` is best-effort cleanup that "can't really fail" in the graceful-shutdown case, with all the actual hardening investment going into the search-lock drain above it. The TEST-04 comment block already shows the project has previously discovered that this assumption is false for in-flight requests specifically — but that discovery was scoped to pinning the *exception class* for test purposes, not to making the shutdown close loop resilient to it.

**How to avoid:**
Wrap each `client.close()` call in its own `try/except Exception` (broad — per the TEST-04 finding, the exception is not guaranteed to be an `httpx.HTTPError` subclass, it can be `AssertionError` today and something else on a future httpx release), log the failure with which client/app/instance it was, and continue to the next client regardless. Move `await app.state.db.close()` into its own `try/except Exception` too (`aiosqlite.Connection.close()`'s own internals, `core.py:199-212`, can themselves raise and re-raise per the installed source), so a db-close failure is logged rather than silently swallowing whatever ran after it in a future edit. Do **not** reach for `asyncio.TaskGroup` to parallelize this "cleanly" — see Pitfall 8.

**Warning signs:**
- A fix that adds one `try/except` around the *entire* double `for` loop rather than around each individual `client.close()` call — that only prevents the exception from propagating further up, it does not prevent the loop from abandoning the remaining clients.
- A fix that narrows the except clause to `httpx.HTTPError` based on "that's what `close()` raises" — TEST-04 already proves that assumption false for this exact codebase on the httpx version it currently pins.

**Test that catches it:** A shutdown test with two (or three) clients registered where the first client's `.close()` is mocked to raise, asserting the second/third clients' `close()` were still called (`mock.assert_called()` style) and that `app.state.db.close()` was still called. Pair with a real in-flight-request variant reusing the TEST-04 `_build_slow_asgi_app` fixture (`tests/test_clients.py:206-244`) at the shutdown-sequence level, not just the single-client level, so the test exercises the production close path (per the TEST-04 comment's own stated rationale for why pure `MockTransport` tests weren't trusted for this).

**Phase to address:** Resource lifecycle (999.13, narrowed — "a client-close failure at shutdown does not prevent other clients or the database from closing").

---

### Pitfall 8: Reaching for `asyncio.TaskGroup` to "parallelize" shutdown closes imports `ExceptionGroup` semantics the rest of the codebase doesn't speak

**What goes wrong:**
A natural-looking "clean" fix for Pitfall 7 is to replace the sequential loop with `asyncio.gather(*(c.close() for c in all_clients), return_exceptions=True)` or, on Python 3.11+ (Triggarr targets 3.13 in production per `CLAUDE.md`/`PROJECT.md`), `async with asyncio.TaskGroup() as tg: for c in ...: tg.create_task(c.close())`. `gather(..., return_exceptions=True)` is fine and arguably simpler than per-client try/except. `TaskGroup`, however, collects every task failure into a single `ExceptionGroup`/`BaseExceptionGroup` raised from the `async with` block (per [PEP 654](https://docs.python.org/3/library/exceptions.html#exception-groups) and the `asyncio.TaskGroup` docs) — and Triggarr's exception-handling style everywhere else in this codebase is narrow-tuple `except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error)`-style catches (see `search/scheduler.py:402`, `engine.py:538`, `tracking.py:581`). None of that style know how to unwrap an `ExceptionGroup` — catching one requires the newer `except*` syntax, and a plain `except Exception` around a `TaskGroup` body still lets the group's own cancellation-propagation semantics (one task's failure cancels its siblings by default) run before your handler ever sees anything, which is the opposite of "every client gets a chance to close independently."

**Why it happens:**
`TaskGroup` is the modern, prominently-documented way to run concurrent coroutines in 3.11+, and "parallelize the N client closes" sounds like exactly its use case. The failure-aggregation and sibling-cancellation behavior is correct and intentional for `TaskGroup`'s actual design goal (structured concurrency with fail-fast), which is the opposite of this shutdown loop's actual goal (best-effort, keep-going-on-failure cleanup of independent resources).

**How to avoid:**
Don't introduce concurrency for this at all unless there's a measured reason to (closing 1-15 clients sequentially is not a performance problem); keep it as sequential per-client `try/except Exception: log; continue`, matching the existing style. If concurrency is wanted for some other reason, use `asyncio.gather(..., return_exceptions=True)` and iterate the returned list checking `isinstance(result, Exception)`, never `TaskGroup`, for this specific "independent best-effort cleanup" shape.

**Warning signs:** A shutdown-cleanup diff that imports `asyncio.TaskGroup` or introduces `except*`.

**Phase to address:** Resource lifecycle (999.13, narrowed) — a design-review item at plan time, not a runtime bug to catch with a test (though a test asserting all N clients' `close()` were called even when one raises, per Pitfall 7, would also catch a broken `TaskGroup` attempt, since sibling-cancellation would leave some clients' `close()` uncalled).

---

### Pitfall 9: Unbounded backup accumulation on a crash-looping upgrade — and the fix must never prune the *one* backup its own error message points to

**What goes wrong:**
`run_migrations` (`triggarr/db.py:172-236`) backs up the database before the first pending migration runs each time it's invoked. The canonical name, `db_path.with_suffix(f".v{current}-backup")`, is written once and "never overwritten" by design (per the function's own comment, `db.py:198-202`) — but if it **already exists** (because a previous migration attempt from this same `current` version already failed and left the schema version unchanged), every subsequent startup attempt takes a **new, uniquely-timestamped** backup instead: `db_path.with_suffix(f".v{current}-backup-{stamp}")` (`db.py:206-214`), with `stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")`. There is currently no cap, no pruning, and no deletion of any backup anywhere in this function. A crash-looping failed migration (container restart policy keeps retrying; each restart calls `run_migrations` again while `current < target`) will write a new multi-megabyte-or-larger copy of the database on **every single restart**, unbounded, until disk fills. This is exactly the capability's named scenario ("a crash-looping failed upgrade cannot pile up backup copies without limit").

**Why it happens:**
The backup-before-migrate design was built around "one attempt, one backup" and the timestamped-fallback branch was added later specifically so a *second* attempt's error message (`_apply_atomic_migration`'s `backup_desc`, `db.py:161-167`, surfaced in the "restore from {backup} if recovery is needed" log line) could still point at the *earliest* good backup even after a second attempt ran — which is correct and worth preserving — but nobody revisited "what if there's a third, fourth, hundredth attempt."

**How to avoid:**
Any pruning logic added here must satisfy two constraints simultaneously, both already implied by the existing code and docstrings:
1. **Never delete the canonical `backup_path`** (the no-suffix `.v{current}-backup` file). It is, by the existing docstring's own words, "the earliest backup taken before any failed attempt," it's the exact path `earliest_backup` points `_apply_atomic_migration`'s recovery-instruction log line at, and it is the *only* backup guaranteed to predate every failed attempt. A cap that prunes oldest-first across *all* backup files (canonical included) will eventually delete this one and leave the operator's restore instructions pointing at a file that no longer exists.
2. **Don't sort by filesystem mtime to decide prune order.** `shutil.copy2(db_path, timestamped_path)` (`db.py:209`, `db.py:217`) explicitly preserves `db_path`'s own metadata — including its `mtime` — onto the copy (that's what distinguishes `copy2` from `copy`). The backup file's mtime reflects when the **source database** was last modified, not when the backup copy was taken. Two backups taken seconds apart during a crash loop, if the live db file happened not to be rewritten in between, can carry colliding or non-monotonic mtimes relative to their actual creation order. The timestamp is already encoded, unambiguously and monotonically (per `datetime.now(UTC)`), in the filename itself (`stamp = ...strftime(...)`) — prune using that, or an explicit creation-order list built at write time, never `Path.stat().st_mtime`.

A reasonable shape: keep the canonical backup always; among the timestamped siblings for the current `current` version, keep the N most recent by parsed filename timestamp and delete the rest, pruning *after* the current attempt's new backup is written (so the error message's `earliest_backup` reference, computed before pruning, is never invalidated by the same call that created it).

**Warning signs:**
- A fix that globs `*.v{N}-backup*` and deletes oldest-by-`os.path.getmtime` — this is the mtime trap described above.
- A fix that caps "total backups across all versions" by deleting whichever file is oldest without special-casing the no-suffix canonical name — this can delete the one file the existing recovery-instructions log line is still pointing at for an *in-progress* multi-attempt recovery.
- No test exercises three-or-more consecutive failed attempts from the same `current` version — a cap that "happens to" work for one extra attempt but not an unbounded crash loop hasn't actually proven the bound.

**Test that catches it:** Simulate N consecutive failed migration attempts from the same starting version (patch the migration function to always raise) and assert: the canonical backup still exists and is byte-identical to the original pre-migration db; the number of timestamped sibling backups never exceeds the chosen cap no matter how large N is; and the error log's named recovery path still exists on disk after the Nth attempt.

**Phase to address:** Bounded pre-migration backups (folded capability, 2026-11-15).

---

### Pitfall 10: A removed Sonarr instance's pending rows already can't be mis-credited — the risk is a *new* lifecycle fix breaking that, or borrowing the wrong existing label for it

**What goes wrong:**
This is documented in `.planning/backlog/MAINTENANCE.md` as "Pending Sonarr searches of a removed instance (Phase 81 deep review bugs-005...)": when a Sonarr instance is removed and a different (or same-URL) instance is later added under the same display name, it is minted a brand-new stable ID via `new_instance_id()` (`triggarr/config.py:58-60`, a fresh CSPRNG token). Every Sonarr-specific pending-search selection and grab-crediting path already keys exclusively off that stable ID — `_run_sonarr_tracking_check` selects pending rows with `get_trackable_entries(db, instance_stable_id=instance_stable_id)` (`triggarr/tracking.py:554`, never falling back to display name the way the non-Sonarr path does at `tracking.py:123`), and `get_owned_grabs`/`update_outcome_and_stats` are likewise keyed by `(app, instance_stable_id, grab_id)` (`triggarr/db.py:501-505`, `1232-1250`). So identity isolation is **already correct today** — the new instance's tracking check structurally cannot select or credit the old instance's rows, because it never has the old stable ID to query with. The documented open problem isn't a crediting bug; it's that the old instance's pending ('searched'/'partial') rows, once its scheduler job is removed (`remove_instance`, `routes.py:969-971`), never get checked again by anything — `run_tracking_check` only ever runs from inside `make_search_job`'s closure for a *currently scheduled* job (`search/scheduler.py:161-272`), and a removed instance has none. Those rows sit in `search_history` forever in `'searched'`/`'partial'` state: `insert_search_entry`'s resolved-row pruning explicitly **never** prunes pending rows ("Pending rows... are never pruned; their owned grabs would otherwise be stranded uncredited," `db.py:797-800`), so they're not even bounded by the normal history trim.

The real risk for this capability is in how the *fix* is built, not in the currently-correct isolation:
- If the fix "closes out" orphaned rows by selecting on display name (`instance_id`) instead of the removed instance's stable ID — to make the closeout code simpler, say — it reopens exactly the cross-identity risk the isolation design was built to prevent, by acting on the wrong row set if a new instance has since reused the old display name.
- If the fix marks these rows with the **same** `is_legacy` flag / "Legacy — tracking discontinued" label the Phase 81 cutover already uses, it conflates two semantically different and already-tested concepts. `_LEGACY_PENDING_SQL` (`db.py:664-675`) is precisely defined as "pre-cutover Sonarr pending row, identified by `id <= legacy_max_history_id` from the one-time `attribution_cutover` record" — a row frozen because attribution *before* it is structurally untrustworthy. A row orphaned because its *instance was later removed* is a completely different reason (the instance just doesn't exist to check anymore) and conflating the two would make "Legacy" mean two different things in the UI/history filter, and would risk an existing legacy-semantics regression test passing or failing for the wrong reason if it's accidentally widened to also match orphaned-instance rows.
- Whatever new terminal state is chosen (e.g. an `"abandoned"` outcome) interacts with the resolved-row pruning predicate (`COALESCE(outcome, 'searched') NOT IN ('searched', 'partial')`, `db.py:804-811`) and the pending-cap counting query (same `IN` clause, `db.py:751-762`) — assigning a real terminal outcome value *correctly* removes these rows from both the "never prune" pending bucket and the pending-cap count (which is good — it's part of what "a defined lifecycle" should mean), but only if the new outcome string is actually distinct from `'searched'`/`'partial'` and is handled by every one of the (currently six, per the MAINTENANCE.md-documented tech debt) places that hand-write this predicate as a raw SQL literal rather than through one shared constant. Missing even one of those six call sites silently reintroduces "pending forever" for the exact rows this fix is meant to close out.

**Why it happens:**
The isolation design (stable IDs, Phase 81) and the lifecycle gap (this milestone) were deliberately separated in time — Phase 81 explicitly deferred "what happens to these rows" as an open question rather than guessing at an answer under deadline pressure. The risk now is time-pressure in the other direction: implementing the lifecycle fix without re-reading why the isolation design chose stable IDs over display names, and without noticing the already-existing (and already known-fragile, per the MAINTENANCE.md "Shared pending-outcome rule" deferred item) raw-SQL-literal duplication of the pending/terminal predicate.

**How to avoid:**
Select and act on orphaned rows by `instance_stable_id` exclusively (never by display name), matching the existing Sonarr tracking convention. Give the new "instance removed, tracking abandoned" state its own distinct label/flag, not the Phase 81 `is_legacy`/"Legacy — tracking discontinued" one — they answer different questions ("why will this never resolve") even though the symptom (stuck pending row) looks the same. Audit every one of the pending/terminal-outcome literal checks in `db.py` (the six call sites MAINTENANCE.md already names: the legacy rule, both pending-cap queries, both pruning predicates, and `get_trackable_entries`) when deciding the new outcome string, so it's excluded from "pending" and included in "prunable" everywhere, not just in the one query the fix happened to touch first.

**Warning signs:**
- The fix's row-selection SQL for "find this removed instance's pending rows" filters on `instance_id = ?` with a display name parameter instead of `instance_stable_id = ? `.
- The history UI change (if any) reuses the existing `is_legacy` boolean/column for the new state rather than adding a distinct one.
- A grep for the new outcome string shows it referenced in fewer than all the existing hand-written pending/terminal-predicate call sites.

**Test that catches it:** A regression reproducing the exact MAINTENANCE.md scenario: create a Sonarr instance, let a search go pending, remove the instance, add a **new** Sonarr instance under the **same display name**, run a tracking check for the new instance, and assert the old pending row is untouched by it (proves isolation holds) while also asserting the old row now resolves to whatever the new defined lifecycle is (proves the gap is closed) — and a second test confirming the new terminal state is excluded from the pending-cap count and included in resolved-row pruning.

**Phase to address:** Removed-instance Sonarr pending-row lifecycle (bugs-005, folded capability).

---

### Pitfall 11: `FASTAPI_OTEL_AUTO_CONFIGURE` regression test pins third-party wording or leaks env state across tests

**What goes wrong:**
The original SA-12 concern (startup fails when this env var plus an OTLP endpoint are set) was already corrected on 2026-11-14: FastAPI 0.162's `fastapi/telemetry/_runtime.py` (confirmed from the installed package, `lifespan()` at line ~209-224) wraps `_configure_from_environment(config)` in `try/except Exception` and logs `logger.warning("FastAPI automatic telemetry configuration failed: %s", exc)` rather than letting the error escape — "Optional telemetry setup must not prevent application startup" per the source's own comment. Startup already survives this env var; what remains is a regression test plus documentation that export is unsupported. The pitfall here is in how that regression test gets written: (a) asserting on the *exact* third-party warning string (`"FastAPI automatic telemetry configuration failed: ..."`) couples the test to FastAPI's own wording, which is not Triggarr's to control and can change on a FastAPI version bump with no behavioral change on Triggarr's side — the test would then fail for a reason that has nothing to do with the capability it's meant to protect; and (b) a test that does `os.environ["FASTAPI_OTEL_AUTO_CONFIGURE"] = "true"` directly (or via a `monkeypatch.setenv` without matching teardown — though `monkeypatch` fixtures auto-revert, a raw `os.environ[...] = ` assignment does not) can leak that env var into every test running after it in the same process, since pytest by default runs a whole file/session in one process.

**Why it happens:**
It's tempting to assert "the fix worked" by grepping for the exact log line that proves the warning path was taken, since that's the most direct evidence — but the thing actually under test ("startup completes successfully with this env var set") doesn't need that string at all; it only needs the lifespan/app to start without raising.

**How to avoid:**
Assert the outcome (app starts, `/health` or equivalent responds, no exception from the lifespan) rather than FastAPI's internal log wording — the capability's own "done when" criterion is a regression check and a documented limitation note, not a log-string pin. If a log assertion is wanted at all for extra confidence, assert on a substring stable enough to survive a patch-level FastAPI bump (e.g. that *some* warning was logged during startup, not the full sentence), and treat it as a secondary check, not the primary pass/fail signal. Use `monkeypatch.setenv(...)` (pytest's fixture, auto-reverting) for the env var, never a raw `os.environ[...]` assignment, consistent with the rest of the suite's env-handling convention (`tests/test_scheduler.py`'s drain-timeout tests already use `monkeypatch` for env-var tests, e.g. `test_drain_timeout_env_overrides_configured`, `scheduler.py:1096+` — follow that existing pattern).

**Warning signs:** A new test with `os.environ["FASTAPI_OTEL_AUTO_CONFIGURE"] = ...` and no corresponding cleanup, or an `assert "FastAPI automatic telemetry configuration failed" in caplog.text` as the sole pass condition.

**Phase to address:** Telemetry variable startup regression (SA-12, folded capability, reduced form).

---

### Pitfall 12: The built-image smoke test proves nothing if it reuses fixed ports/names, blind sleeps, or heavy mocking — and this milestone's "done when" depends on it proving something real

**What goes wrong:**
The milestone's done-when criterion explicitly requires "an isolated built-image smoke test demonstrates restart/recovery behavior," on top of (not instead of) the targeted unit/integration regressions for each fix. Triggarr already has a working, non-flaky pattern for exactly this kind of test: `tests/harness/image_smoke.py` + `tests/harness/stack.py` — every container gets a Docker-assigned ephemeral host port (`"127.0.0.1::8484"` style publish spec, read back after the fact via `published_port()`, `stack.py:232-237`, rather than a fixed port number), every resource name is namespaced by a fresh per-run `secrets.token_hex(6)` session id (`new_session`, `stack.py:122-126`) so concurrent or leftover runs can't collide, and every "wait for X" helper (`wait_for_http_health`, `wait_for_docker_health`, `wait_for_exit`, `stack.py:324-370`) polls against a `time.monotonic()` deadline rather than sleeping a fixed duration. The existing "step C: restart" (`image_smoke.py:138-170`) already demonstrates one restart/recovery scenario (config persists across a container restart on the same volume) and already had to specifically account for Docker reassigning a fresh ephemeral port on every `docker start` of a stopped container (`image_smoke.py:72-77`'s comment makes this exact gotcha explicit). Any new v2.14 smoke scenario (e.g. demonstrating recovery from a malformed state.json, or that a write-failure during instance removal doesn't corrupt a running container) that instead hardcodes a port, reuses a fixed container/volume name across runs, or inserts a bare `time.sleep(N)` instead of a polling helper will intermittently fail in CI for reasons unrelated to the behavior it's supposed to prove — exactly the kind of flakiness that erodes trust in the whole image-smoke gate (the same gate v2.13's "CI tests what we ship" capability made a required check).

A second, equally real risk for this milestone specifically: because several of these fixes (write-before-mutate ordering, startup/shutdown resource symmetry, aiosqlite thread-hang behavior) only manifest through real OS-level failure injection (actual disk-full conditions, actual process signals, actual non-daemon-thread hangs) or through the real httpx transport (per the TEST-04 precedent in Pitfall 7), a unit test that mocks `_atomic_toml_write` or `client.close()` can prove the *code path* was exercised without proving the *real* failure mode (a genuinely full disk, a genuinely hung thread) is handled — and conversely, a smoke test that mocks too much (e.g. a fake *arr stub that never produces a timeout/ambiguous-delivery condition at all) can "pass" while never touching the POST-retry logic this milestone is supposed to fix. The project's own TEST-04 history (Pitfall 7) is direct evidence this isn't hypothetical: a MockTransport-only version of that test previously accepted "any of {RuntimeError, cancellation, HTTPError, clean completion}" as passing, which the comment block explicitly says "can only prove the mock does not hang" — not that production behaves correctly.

**Why it happens:**
Smoke/integration tests for infrastructure-level failures are inherently harder to write than unit tests, and the unit-level mocks (`OSError` side effects, mocked `close()`) are faster and easier to reach for — but infrastructure-level claims ("closes what it opened," "doesn't hang the process," "doesn't fill the disk") are exactly the claims a mock can't actually validate, only gesture at.

**How to avoid:**
For the unit-level regressions (Pitfalls 1-11's individual test recommendations above), mocking is appropriate and matches existing project convention — those tests are about code-path correctness, not real OS behavior. Reserve the one required built-image smoke scenario for something only a real container can prove: e.g., that a container which crashes mid-migration and is restarted does not accumulate unbounded backup files and does not hang past its stop-grace-period before becoming healthy again, using the harness's existing polling/dynamic-port/unique-session conventions rather than introducing new ones. Treat "the smoke scenario passed" and "the unit tests passed" as two separate, both-required pieces of evidence, not substitutes for each other — consistent with how CI already treats image-smoke as its own required job distinct from `pytest`.

**Warning signs:**
- A new harness step with a literal port number, a fixed container/volume name without the session-id suffix, or a `time.sleep(N)` where an existing `wait_for_*` helper could be used instead.
- A smoke scenario whose stub *arr server (`tests/harness/arr_stub.py`) is modified to always respond instantly and successfully — if it can never produce a slow/ambiguous response, it cannot exercise the retry-safety fix at all.
- A PR description that cites "smoke test passed" as evidence for a capability (e.g. backup bounding) that the smoke scenario doesn't actually simulate (e.g. never runs more than one failed migration attempt).

**Phase to address:** Cross-cutting — applies to the "done when" verification step for every v2.14 capability, most directly the resource-lifecycle and backup-bounding ones where only a real container/process can demonstrate the claim.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|-----------------|-----------------|
| Folding the "unknown delivery" bucket into the existing `failed` counter rather than adding a third bucket | Smaller diff, no `CycleTally`/`LastCycleRecord` schema change | SAFETY-03 escalates on ambiguous network blips, not real failures; dashboard Failed grade becomes less trustworthy, re-opening the exact kind of honesty gap v2.12 closed | Never — this is the literal failure mode the capability exists to prevent |
| Pruning migration backups by mtime instead of parsed filename timestamp | Simpler code (`Path.stat().st_mtime` vs regex/parse) | `shutil.copy2` preserves the *source* db's mtime, not copy time — prune order can be wrong, risking deletion of the canonical backup | Never |
| Reusing `is_legacy` for orphaned-removed-instance rows instead of a new flag | No new column/predicate needed | Conflates two different "why will this never resolve" reasons in the UI and in any test asserting legacy semantics | Never |
| Mocking `client.close()`/`_atomic_toml_write` in all new regression tests, skipping a real-container smoke scenario | Fast, deterministic unit tests | Infrastructure-level claims (process hang, disk fill, real write failure) unproven; mirrors the exact gap TEST-04 (Pitfall 7) already found once | Only for the per-capability unit regressions; never as the *sole* evidence for resource-lifecycle or backup-bounding capabilities |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|-------------------|
| httpx `AsyncClient` retry on POST | Treating `httpx.TransportError` as one bucket for retry-safety | Branch on the concrete subclass: `ConnectError`/`ConnectTimeout` = never-sent (safe to retry); `ReadTimeout`/`WriteTimeout`/`PoolTimeout`/`RemoteProtocolError` = maybe-sent (never blindly retry) |
| httpx `AsyncClient.aclose()` at shutdown | Assuming `close()` only ever raises `httpx.HTTPError` subclasses | TEST-04 (`tests/test_clients.py`) already proves `AssertionError` is possible on an in-flight request with the pinned httpx version; catch broad `Exception` per client, log, continue |
| `aiosqlite.Connection` | Assuming an unclosed connection is a harmless leak cleaned up at process exit | Its worker thread is non-daemon (confirmed from `aiosqlite/core.py`) and blocks forever without an explicit `close()`/`stop()` — an unclosed connection can prevent the whole process from exiting |
| FastAPI's built-in OpenTelemetry auto-configure | Asserting on FastAPI's internal warning string as the regression signal | Assert the externally-observable outcome (startup completes, app answers requests) with the env var set; treat any log assertion as secondary |
| Docker container restart in the smoke harness | Assuming a container's published port is stable across `docker start` | `tests/harness/image_smoke.py`'s own step-C comment already documents that Docker reassigns a fresh ephemeral port on every `docker start` — always re-read via `published_port()` after a restart |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|-----------------|
| Unbounded migration backup copies on a crash-looping upgrade | Disk usage climbs on every container restart during a failed-migration loop | Bound timestamped backups, preserve the canonical one, prune using the filename-embedded timestamp | Immediately on the second failed attempt from the same schema version, worsening with every subsequent restart |
| A hung non-daemon aiosqlite thread after a leaked connection | Container appears "stuck" on shutdown/restart until Docker's stop/kill grace period elapses, every time the underlying startup failure recurs | Close `db` on every startup-failure exit path (Pitfall 6) | Any time a step after `aiosqlite.connect()` in the lifespan setup raises, which is exactly when it matters most (a bad migration under a restart policy) |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging the raw exception detail for a retry-safety or delivery-ambiguity decision instead of the existing `_sanitize_exc` output | Could leak request/response internals (URLs with `apikey=` query params on legacy *arr installs — already a known concern per `_on_job_error`'s docstring, `scheduler.py:441-444`) into logs the new code path touches | Keep the new classification logic working on the live exception object for *decisions*, but route anything that reaches a log line or stored `detail` column through the existing `_sanitize_exc`, unchanged |
| A new "abandoned instance" terminal row state exposing which instance (by old display name or stable ID) owned it, in a way a removed/renamed instance's identity could be inferred from history alone | Low severity (single-user local tool, no multi-tenant concern) but still worth matching existing `instance_stable_id`-over-display-name discipline | Follow the existing Sonarr tracking convention of keying by stable ID, not re-deriving anything from the removed instance's old display name |

## "Looks Done But Isn't" Checklist

- [ ] **Search-command delivery:** Often missing a test that actually asserts the *second* POST never happened (call-count assertion) — a test that only checks the function "didn't raise" or "logged something" doesn't prove no duplicate was sent.
- [ ] **State/config consistency (remove_instance):** Often missing the postcondition assertions (settings still contains the instance, scheduler job still present, client still registered) — a test that only checks the HTTP status code (mirroring the existing, weaker `save_settings` precedent) doesn't prove the fix.
- [ ] **Resource lifecycle (startup):** Often missing an assertion that the already-opened resource's `.close()` was actually called on the failure path — a test that only asserts the exception still propagates doesn't prove the leak was fixed, since the exception already propagates today.
- [ ] **Resource lifecycle (shutdown):** Often missing a multi-client scenario — a single-client failing-close test can't prove "other clients still close," only that the one client's failure didn't crash the test.
- [ ] **Bounded backups:** Often missing a 3+-consecutive-failure scenario — a test with only one or two failed attempts can "pass" a cap that's actually unbounded in practice.
- [ ] **Removed-instance Sonarr lifecycle:** Often missing the same-display-name-reuse scenario — a test that never reuses the old display name can't prove isolation was preserved, only that the new lifecycle exists in isolation.
- [ ] **Built-image smoke test:** Often missing any scenario that actually injects the real failure (a real disk-full-like condition, a real second failed migration) rather than just restarting a healthy container — a "restart still works" smoke test (which already exists, `image_smoke.py` step C) doesn't by itself demonstrate recovery from any of this milestone's specific failure modes.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|----------------|-----------------|
| Write-before-mutate already shipped and corrupted a running instance's in-memory state | LOW | No persistent damage — on-disk config is untouched by definition (the write failed); a process restart reloads correct settings from disk. Document as a known pre-fix gap, not a data-loss event. |
| Startup leaked a db connection and the process hung on shutdown | LOW | Docker's restart policy + stop_grace_period already recovers it (SIGKILL after grace period, then restart) — just slower and noisier than necessary until fixed; no data corruption, since the leak happens on a *failed* startup before any writes. |
| Unbounded backup files filled disk during a crash loop | MEDIUM | Manually delete the extra timestamped backups (never the canonical, no-suffix one) to reclaim space while the underlying migration failure is diagnosed; the canonical backup remains the safe restore point throughout. |
| A removed Sonarr instance's old pending rows sit stuck forever (pre-fix) | LOW | No crediting risk today (isolation already holds) — they're inert, just visually stuck in history; safe to leave until the lifecycle fix ships, or manually prune by direct SQL scoped to the exact old `instance_stable_id` if urgently needed. |

## Pitfall-to-Phase Mapping

| Pitfall | Target Capability (PROJECT.md) | Verification |
|---------|----------------------------------|----------------|
| 1, 2, 3 (retry taxonomy, unknown-delivery counting, sanitize-before-decide) | Search-command delivery | POST-specific `MockTransport` tests per exception subclass; scheduler-level test asserting SAFETY-03 counter and grade are unaffected by an ambiguous-delivery result |
| 4 (write-before-mutate in `remove_instance`) | State/config consistency (999.9) | `_atomic_toml_write` failure-injection test asserting settings/jobs/clients postconditions, not just HTTP status |
| 5 (non-dict state JSON crash) | State/config consistency (999.9) | Flip `test_state_wrong_structure_list_crashes` per its own docstring; add `42`/`null`/string-root siblings |
| 6 (startup resource leak) | Resource lifecycle (999.13) | Lifespan-context test patching a late setup step to raise, asserting earlier-opened resources were closed |
| 7 (shutdown close-loop isolation) | Resource lifecycle (999.13) | Multi-client shutdown test with one client's `close()` raising; assert others and db still close |
| 8 (TaskGroup/ExceptionGroup trap) | Resource lifecycle (999.13) | Design-time review; covered incidentally by Pitfall 7's test |
| 9 (unbounded backups) | Bounded pre-migration backups | 3+-consecutive-failed-migration test asserting cap holds and canonical backup survives |
| 10 (removed-instance Sonarr lifecycle) | Removed-instance Sonarr pending-row lifecycle (bugs-005) | Same-display-name-reuse isolation test + new-terminal-state pending/pruning predicate coverage |
| 11 (OTEL regression test fragility) | Telemetry variable startup regression (SA-12) | Outcome-based assertion (startup completes) with `monkeypatch.setenv`, not a log-string pin |
| 12 (smoke test quality) | Cross-cutting — "done when" verification for the whole milestone | Smoke scenario reuses `stack.py`'s dynamic-port/unique-session/polling conventions and injects a real failure, not just a restart |

## Sources

- `triggarr/clients/base.py`, `triggarr/search/engine.py`, `triggarr/search/scheduler.py`, `triggarr/web/routes.py`, `triggarr/state.py`, `triggarr/config.py`, `triggarr/db.py`, `triggarr/tracking.py`, `triggarr/models/config.py`, `triggarr/__main__.py` — read directly for this research (line numbers cited above reflect the repository at commit `53eb4a17`, 2026-11-15).
- `tests/test_clients.py` (TEST-04 in-flight-close contract tests, retry tests), `tests/test_state.py` (`test_state_wrong_structure_list_crashes` and siblings), `tests/test_web.py` (`test_save_settings_propagates_write_failure`, `test_remove_instance_*`), `tests/test_scheduler.py` (lifespan/shutdown/failure-counter tests), `tests/harness/stack.py` + `tests/harness/image_smoke.py` (smoke-harness conventions) — read directly.
- `.planning/backlog/MAINTENANCE.md` — source of the "bugs-005" removed-Sonarr-instance pending-row item and the SA-12 correction record; "Shared pending-outcome rule" deferred tech-debt item.
- httpx exception hierarchy: [https://www.python-httpx.org/exceptions/](https://www.python-httpx.org/exceptions/) (fetched 2026-11-15) — confirms `TransportError` → `TimeoutException` (`ConnectTimeout`/`ReadTimeout`/`WriteTimeout`/`PoolTimeout`) and `NetworkError` (`ConnectError`/`ReadError`/`WriteError`/`CloseError`) and `ProtocolError` (`RemoteProtocolError`/`LocalProtocolError`) as siblings under `RequestError`, with `HTTPStatusError` as a separate `HTTPError` child.
- `.venv/lib/python3.11/site-packages/httpx/_client.py` (installed httpx 0.28.1, `AsyncClient.aclose()`, lines ~1978-1988) — confirms `aclose()`'s idempotency guard and delegation to the transport.
- `.venv/lib/python3.11/site-packages/aiosqlite/core.py` (installed aiosqlite, `Connection.__init__`/`__await__`/`stop`/`close`, `_connection_worker_thread`, lines ~78-212) — confirms the non-daemon worker `Thread` and its blocking-until-sentinel loop.
- `.venv/lib/python3.11/site-packages/starlette/routing.py` (installed starlette 1.10.0, `Router.lifespan`, lines ~652-677) — confirms a pre-`yield` lifespan exception is reported as `lifespan.startup.failed` and re-raised, never reaching the generator's own `finally`.
- `.venv/lib/python3.11/site-packages/uvicorn/lifespan/on.py` (installed uvicorn 0.54.0, `LifespanOn.startup`/`main`, lines ~46-96) — confirms `should_exit = True` and "Application startup failed. Exiting." on a startup failure.
- `.venv/lib/python3.11/site-packages/fastapi/telemetry/_runtime.py` (installed fastapi 0.162.4, `lifespan` wrapper, lines ~209-224) — confirms the try/except around `_configure_from_environment` with the "must not prevent application startup" comment, corroborating the MAINTENANCE.md SA-12 correction.
- Python docs, `threading` module — non-daemon threads keep the interpreter alive until they exit (standard library behavior cited for the aiosqlite finding; no single stable URL cited per the "no single source for critical claims" discipline, corroborated directly by reading the aiosqlite source above).

---
*Pitfalls research for: Triggarr v2.14 Reliability milestone*
*Researched: 2026-11-15*
