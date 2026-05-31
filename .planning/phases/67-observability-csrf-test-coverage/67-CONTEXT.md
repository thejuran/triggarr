# Phase 67: Observability & CSRF Test Coverage - Context

**Gathered:** 2026-05-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Three independent fronts, all within the existing single-process daemon — no new
dependencies, no new routes, no new config keys:

1. **RES-02 (Observability):** Surface a "last successful search" timestamp on the
   dashboard, stale-flagged when older than 2× the configured search interval.
2. **RES-03 (Performance):** Cache `*arr` tag-list responses in `app.state` with a
   1-hour TTL, invalidated on instance config save — eliminating the per-cycle
   `get_tags()` round-trip for tag-filtered instances.
3. **TEST-01 (Test coverage):** Extend the `OriginCheckMiddleware` test suite to cover
   the ROADMAP-named CSRF scenarios (missing Origin, missing Referer, both absent,
   scheme mismatch, spoofed host).

Scope is fixed by ROADMAP Phase 67 + REQUIREMENTS.md RES-02/RES-03/TEST-01. Discussion
locked HOW to implement within that boundary. The three items are independent and can
be planned as parallel waves.

</domain>

<decisions>
## Implementation Decisions

### RES-02 — Last successful search (observability)
- **D-01:** **Per-instance success timestamp**, rendered on each app card. Add a new
  `last_success: str | None` (ISO-8601, `…Z`) field to the per-`(app, instance)`
  `AppState` TypedDict in `triggarr/state.py:48-51` (alongside the existing `last_run`
  and `connected`). ROADMAP's "per app type" is satisfied because each dashboard card
  IS an app-type instance; per-instance is strictly more informative for multi-instance
  setups and matches the existing card-per-instance UI.
  - **Rejected:** per-app-type aggregate (coarser — hides which instance is stale);
    per-instance + rollup (larger surface, deferred — see Deferred Ideas).
- **D-02:** **Write the timestamp in the engine, beside `last_run`.** In each cycle fn
  (`run_radarr_cycle`, `run_sonarr_cycle`, `run_lidarr_cycle`) set
  `ist["last_success"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")` at the
  same success point where `ist["connected"] = True` and `ist["last_run"] = …` are set
  (engine.py:331/505, 567/748, 812/984). Single source of truth; persists to
  `state.json` automatically; survives restart; manual `search_now` (which calls the
  cycle fn directly) updates it too.
  - **Rejected:** writing it in `scheduler._evaluate_cycle_outcome` — manual
    `search_now` bypasses that helper (per the existing TODO at scheduler.py:288-297),
    so manual successes would not refresh the timestamp.
  - **Semantics note for planner:** `last_run` is "last *attempt* (any outcome)";
    `last_success` is "last cycle that reached the connected-True end of the cycle fn".
    Distinct fields, both rendered.
- **D-03:** **Stale flag computed at render time**, not stored. In
  `_build_app_context` (`triggarr/web/routes.py:242-290`) compute
  `last_success_stale = (last_success is None) OR (now - last_success > 2 ×
  search_interval_minutes)`. Expose `last_success` and `last_success_stale` in the
  app-card context dict. The per-instance `search_interval` is on `instance_config`
  (used at scheduler.py:479) — read it from settings, not a global.
- **D-04:** **Render on the app card schedule row** (`partials/app_card.html:50-53`,
  the existing "Last run / Next" flex row). Add a "Last OK" entry showing
  `last_success[11:19]` (HH:MM:SS, matching the existing `last_run[11:19]` slice) or
  "Never" when null. When `last_success_stale` is true and a value exists, apply an
  amber treatment consistent with the existing tag-warning amber
  (`text-amber-400` / `bg-amber-500/15`) — reuse, don't invent a new color token.
  Card already auto-refreshes every 5s via htmx (`hx-trigger="every 5s"`), so no new
  polling wiring is needed.

### RES-03 — Tag list caching (performance)
- **D-05:** **Cache in `app.state`, keyed per-instance**: `app.state.tag_cache:
  dict[tuple[str, str], tuple[list[Tag], float]]` mapping `(app_name, instance_name)`
  → `(tags, fetched_at_monotonic)`. Initialize to `{}` in the lifespan `app.state`
  block (scheduler.py:409-457, next to `search_failures` / `last_search_time`).
  - **Why monotonic:** TTL comparison should use `time.monotonic()` (already imported
    in scheduler.py and used for `search_lock_holder`), not wall-clock, so a system
    clock adjustment cannot make a cache entry look fresh forever or expire instantly.
- **D-06:** **1-hour TTL.** A helper resolves tags: on call, if a cache entry exists
  and `monotonic() - fetched_at < 3600`, return cached tags; otherwise call
  `client.get_tags()`, store `(tags, monotonic())`, return. TTL constant lives as a
  module-level `_TAG_CACHE_TTL_SECONDS = 3600.0` (mirrors the `_SHUTDOWN_DRAIN_TIMEOUT`
  module-constant pattern in scheduler.py).
- **D-07:** **The cache wraps the existing `await client.get_tags()` call sites in
  `engine.py`** (radarr ≈360, sonarr ≈596, lidarr equivalent). The engine cycle fns
  must reach the cache without coupling to `app.state` directly — the planner decides
  the threading mechanism (e.g. pass a `get_tags` resolver callable / cache handle into
  the cycle fn, OR pass `app.state` through). Preserve the existing
  fetch-failure behavior exactly: on `get_tags()` error the current code logs a warning,
  sets `tags = []`, and `tag_fetch_ok = False` so tag warnings are suppressed — caching
  must NOT cache an empty-list failure result as if it were a successful fetch (only
  cache successful non-error fetches).
- **D-08:** **Targeted invalidation on instance config save.** In the settings-save
  path in `triggarr/web/routes.py` (already serialized under `app.state.search_lock`),
  after the config write succeeds, delete `app.state.tag_cache` entries only for
  instances whose relevant config changed — i.e. `url`, `api_key`, `missing_tag`, or
  `cutoff_tag`. ROADMAP wording: "saving instance config… immediately invalidates the
  cache for that instance." If diffing changed-instances is awkward in the save handler,
  the acceptable fallback is to invalidate every entry for any instance present in the
  new config (still per-instance keyed, just less surgical) — but prefer the targeted
  diff.
  - **Rejected:** blanket "clear entire tag_cache on any save" — simpler but refetches
    untouched instances' tags on the next cycle for no reason.

### TEST-01 — OriginCheckMiddleware CSRF tests (test coverage)
- **D-09:** **Pure test work — add the ROADMAP-named gaps, do NOT modify middleware.**
  Existing `tests/test_middleware.py` already covers: matching Origin, mismatched Origin
  (403), matching Referer, mismatched Referer (403), neither-header pass, GET-with-
  mismatched-Origin pass, and a wired-route integration test. Add tests for the
  remaining named scenarios: **missing Origin (Referer present), missing Referer (Origin
  present)** [partially implied by existing but assert explicitly], **both absent**
  [exists — keep], **scheme mismatch**, and **spoofed host**.
- **D-10:** **Scheme-mismatch test PINS current behavior with an explanatory comment.**
  Verified 2026-05-31: the middleware compares `urlparse(origin).netloc` against the raw
  `Host` header, so **scheme is ignored** — `Origin: https://testserver` with
  `Host: testserver` is ALLOWED. In Triggarr's single-origin threat model this is not a
  bypass (an attacker cannot cause the browser to emit a same-host Origin under a scheme
  they control), so the test asserts ALLOW and a comment documents that scheme is
  intentionally not part of the comparison. **Do not "fix" this** — it is the chosen,
  understood behavior (TEST-01 is test-only).
  - **Rejected:** hardening the middleware to compare scheme — no real vuln exists in
    the single-origin model; would expand TEST-01 beyond its test-only scope.
- **D-11:** **Spoofed-host tests assert REJECT.** Verified 2026-05-31:
  `Origin: http://evil.com` (host `testserver`) → 403, and suffix spoof
  `Origin: https://testserver.evil.com` (host `testserver`) → 403. Port mismatch
  (`testserver:8080` vs `testserver`) → 403. Add these as explicit assertions so the
  netloc-equality guard is regression-locked.
- **D-12:** **Tests must not rely on internal middleware state** (ROADMAP criterion #3,
  "none rely on internal middleware state"). Drive everything through a `TestClient`
  with crafted `Origin`/`Referer`/`Host` headers and assert on response status only —
  matching the existing `test_middleware.py` harness shape (`app.add_middleware(...)` +
  `TestClient`).

### Claude's Discretion
- Exact threading mechanism for the tag cache into engine cycle fns (D-07) — resolver
  callable vs cache handle vs `app.state` passthrough. Planner picks the least-coupling
  option consistent with the existing `make_search_job` "read from app.state at call
  time" philosophy.
- Exact amber stale-flag markup on the card (D-04) — must reuse existing amber tokens.
- Whether the changed-instance diff for D-08 lives inline in the save handler or in a
  small helper.

</decisions>

<specifics>
## Specific Ideas

- No external product references named. The user delegated all four gray areas to the
  recommended (most code-faithful) options.
- Inherited preference: reuse existing design tokens and patterns rather than inventing
  new ones (amber tag-warning treatment for staleness; `[11:19]` time slice for the new
  timestamp; module-constant pattern for the TTL).

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 67: Observability & CSRF Test Coverage" — Goal,
  depends-on (Phase 65 scheduler timestamps; Phase 64 config lock), 3 success criteria
- `.planning/REQUIREMENTS.md` lines 29-34 — RES-02, RES-03, TEST-01 acceptance text
  (the authoritative wording for each item)
- `.planning/codebase/CONCERNS.md` — "Limited visibility into scheduler health"
  (RES-02 source), "Tag list fetched on every tag-filtering search" lines 97-101
  (RES-03 source), "Security middleware with origin spoofing" lines 185-189 (TEST-01
  source, marked Priority: High)

### Source files to modify (file:line pointers)
- `triggarr/state.py:48-51` + `:78` — `AppState` TypedDict + `_default_instance_state()`
  (RES-02: add `last_success` field + default `None`)
- `triggarr/search/engine.py:331,505 / 567,748 / 812,984` — per-cycle success points
  where `connected=True` and `last_run` are set (RES-02: add `last_success` write here)
- `triggarr/search/engine.py:357-385, 593-…` — `get_tags()` call sites for tag filtering
  (RES-03: wrap with cache)
- `triggarr/clients/base.py:119` + `triggarr/clients/lidarr.py:61` — `get_tags()` defs
  (RES-03: cached callers; defs themselves unchanged)
- `triggarr/search/scheduler.py:409-457` — lifespan `app.state` init block
  (RES-03: add `app.state.tag_cache = {}`; module constant near `_SHUTDOWN_DRAIN_TIMEOUT`)
- `triggarr/web/routes.py:242-290` — `_build_app_context` (RES-02: compute
  `last_success_stale`, expose to card context); settings-save handler (RES-03 D-08:
  targeted cache invalidation under `search_lock`)
- `triggarr/templates/partials/app_card.html:50-53` — schedule row (RES-02: add
  "Last OK" + amber stale flag)
- `triggarr/web/middleware.py:61-86` — `OriginCheckMiddleware` (TEST-01: behavior under
  test; NOT modified)

### Test files (extend existing patterns)
- `tests/test_middleware.py` — existing OriginCheck suite (TEST-01: add scheme-mismatch,
  spoofed-host, explicit missing-header assertions following the existing harness)
- `tests/test_scheduler.py` — scheduler/app.state test patterns (RES-03: tag_cache
  TTL/invalidation tests)
- `tests/test_search.py` / `tests/test_state.py` — engine cycle + state tests
  (RES-02: assert `last_success` written on success; RES-03: cache hit avoids
  second `get_tags()`)
- `tests/test_web.py` — route/template tests (RES-02: card renders Last OK + stale flag)

### Project conventions
- `CLAUDE.md` — Python 3.11+, ruff (E,F,I,UP,B,SIM), 120 line length, SecretStr
  discipline, loguru redacting sink, pytest-asyncio (`asyncio_mode=auto`)
- `.planning/PROJECT.md` §"Key Decisions" — established patterns (atomic writes,
  app.state read-at-call-time job philosophy)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`last_run` / `connected` plumbing** (engine.py + state.py + `_build_app_context` +
  `app_card.html`) is the exact template RES-02 follows. `last_success` is a parallel
  field threaded through the same four layers.
- **`app.state` scratch dicts** (`search_failures`, `last_search_time`,
  `search_lock_holder`) initialized in the lifespan block (scheduler.py:438-457) are the
  model for `tag_cache`. They are documented-by-comment (State has no runtime
  annotations — see WR-05 note at scheduler.py:430-436); follow that comment style.
- **`_SHUTDOWN_DRAIN_TIMEOUT` module constant** (scheduler.py:81) is the model for
  `_TAG_CACHE_TTL_SECONDS`.
- **`search_lock` serialization** already guards every config save
  (`_atomic_toml_write`, AST-audited in Phase 64). RES-03 D-08 invalidation runs inside
  that existing lock — no new locking.
- **Existing OriginCheck test harness** in `test_middleware.py` (`app.add_middleware`
  + `TestClient` + header crafting) is directly extensible for TEST-01.
- **Amber tag-warning treatment** in `app_card.html` (`bg-amber-500/15 text-amber-400`)
  is the reuse target for the RES-02 stale flag.

### Established Patterns
- **`time.monotonic()` for elapsed-time logic** (scheduler.py `search_lock_holder`) —
  RES-03 TTL uses the same, not wall-clock.
- **ISO `…Z` timestamps** (`datetime.now(UTC).isoformat().replace("+00:00", "Z")`) for
  all state timestamps — RES-02 `last_success` matches.
- **`[11:19]` Jinja slice** to render HH:MM:SS from an ISO string in the card — RES-02
  reuses for "Last OK".
- **Tag-fetch failure path** (engine.py:362-367) logs warning + `tags=[]` +
  `tag_fetch_ok=False` — RES-03 caching must preserve this and only cache successful
  fetches.
- **htmx `hx-trigger="every 5s"`** auto-refresh on the card — RES-02 needs no new poll.

### Integration Points
- **RES-02 engine → state.json → card:** engine writes `ist["last_success"]`; state
  save persists it; `_build_app_context` reads it + computes staleness vs per-instance
  `search_interval`; `app_card.html` renders it. All four layers already exist for
  `last_run`.
- **RES-03 engine ↔ app.state.tag_cache:** cycle fn resolves tags through the cache
  (TTL check) instead of unconditional `get_tags()`; settings-save handler invalidates
  changed instances' entries under `search_lock`.
- **TEST-01 TestClient → OriginCheckMiddleware:** crafted headers, assert status only,
  no internal-state coupling.

</code_context>

<deferred>
## Deferred Ideas

- **Per-app-type rollup of last-successful-search** (e.g. in the stats/health strip, in
  addition to per-card) — rejected for this phase in favor of per-instance only (D-01).
  Reasonable future observability enhancement.
- **Scheduler job dashboard** (next-run/last-duration table) — listed as OBS-01 in
  STATE.md deferred items; explicitly out of Phase 67 scope.
- **Hardening OriginCheck to compare scheme** — rejected (D-10); no real vuln in the
  single-origin threat model. If Triggarr ever supports multiple trusted origins, revisit.
- **Caching `get_tags()` failure results / negative caching** — explicitly out (D-07
  caches only successful fetches), to avoid pinning a transient *arr outage into a 1h
  stale "no tags" window.

</deferred>

---

*Phase: 67-observability-csrf-test-coverage*
*Context gathered: 2026-05-31*
