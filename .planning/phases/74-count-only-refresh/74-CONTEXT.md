# Phase 74: Count-Only Refresh - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a **count-only refresh**: a per-app-card "Refresh counts" button plus a documented `POST /api/refresh-counts/{app}/{instance}` endpoint that re-fetches missing/cutoff/eligible counts and connection health from the *arr instance **without launching a search and without advancing the search cursor**.

Implemented by extracting the shared fetch+raw-count+health+tag+filter+eligible-count prefix out of each `run_*_cycle` in `triggarr/search/engine.py` into a per-app helper; the search/slice/cursor-advance/`last_run` block stays in the cycle function. The count path calls only the helper. This is a **behavior-preserving refactor** of the search path (existing cycle tests must stay green) plus a thin new endpoint and UI button mirroring `search_now`.

Requirements: CNT-01..05. The spec source of truth is `docs/superpowers/specs/2026-06-02-recovery-counts-config-design.md` §3.

Disjoint from Track A (Phases 72-73, auth) and Track C (Phase 75, config) — no shared code.
</domain>

<decisions>
## Implementation Decisions

### Engine seam (locked by spec §3.2; structure decided here)
- **D-01:** Extract **per-app helpers** — `refresh_radarr_counts(...)`, `refresh_sonarr_counts(...)`, `refresh_lidarr_counts(...)` — NOT a single shared core with callbacks. Each helper extracts its own cycle's prefix: fetch → cache raw counts (`missing_count`/`cutoff_count`) → set connection health (`connected=True`, `unreachable_since=None`) → resolve tags → app-specific filter → cache eligible/searchable counts (`missing_eligible`, and for Sonarr/Lidarr the `*_searchable` season counts). Rationale: matches the existing per-app `run_*_cycle` structure → lowest-risk behavior-preserving extraction.
- **D-02:** **Reuse the existing shared filter primitives** inside the per-app helpers (`filter_monitored`, `filter_unreleased_movies`, `filter_sonarr_episodes`, `deduplicate_to_seasons`, `cap_batch_sizes`, `resolve_tag_id`/`filter_by_tag`) so the filter *sequence* cannot drift across the three helpers despite the per-app form. The helper must reproduce the cycle's current filter order exactly.
- **D-03:** **Slicing stays exclusively in the cycle function.** `slice_batch` and the search loop and cursor write (`ist["missing_cursor"]`/`ist["cutoff_cursor"]`) are NOT moved into the helper. This is the structural cursor guarantee (CNT-02): the count path, calling only the helper, *cannot* advance the cursor. No `count_only` flag in the hot loop.
- **D-04:** On fetch failure the helper sets `connected=False` + `unreachable_since` (mirroring the cycle's current abort branch) and returns — same as today's cycle behavior.

### Count-path state semantics (locked by spec §3.3)
- **D-05:** Count path **updates**: `connected`, `unreachable_since`, `missing_count`, `cutoff_count`, eligible/searchable counts. It **does NOT** stamp `last_run`/`last_success` (no search ran) and **does NOT** touch the SAFETY-03 failure counter `app.state.search_failures` (that governs *scheduled-search* escalation only). (CNT-03)
- **D-06:** The count path must NOT route through `_run_one_cycle` (scheduler.py) — that helper owns the SAFETY-03 failure-counter increment/reset and is the search path's wrapper. The count path calls the per-app `refresh_*_counts` helper directly. A count-refresh fetch failure flips the card to disconnected but does NOT escalate the scheduler.

### API endpoint (locked by spec §3.4 — mirrors `search_now`)
- **D-07:** `POST /api/refresh-counts/{app}/{instance}` is structurally identical to `search_now` (`routes.py:880`): same `len(instance_name) > 64` guard, `app_name not in APP_TYPES` check, enabled-instance + client lookup, optimistic-then-in-lock rate-limit check, `async with request.app.state.search_lock`, and `_build_app_context` → `partials/app_card.html` response — **minus** the search call and the `last_run`/failure-counter updates. Always returns 200 + the card partial on success; rate-limit returns 429; validation failures return 400 (same status codes/messages as `search_now`).
- **D-08:** Reuse the same tag-cache resolver shape as `search_now` (the `_get_tags_cached` closure reading `request.app.state.tag_cache` with `_TAG_CACHE_TTL_SECONDS`) so a count refresh populates/reads the tag cache exactly like a manual search (RES-03 parity). Rate-limit: reuse `SEARCH_RATE_LIMIT_SECONDS` (10s) keyed the same way (`{app}_{instance}`) — left to planner whether to share the existing `last_search_time` dict or use a sibling `last_refresh_time` dict; prefer a sibling so a count refresh and a search don't rate-limit each other. (Flag for planner; not user-blocking.)

### UI — button (locked by spec §3.4; layout decided here)
- **D-09:** In the **connected** app-card footer (`partials/app_card.html`), split the single full-width Search Now button into **two side-by-side buttons**: `flex gap-2`, each `flex-1`. **Search Now stays primary** (current `bg-triggarr-elevated` style, app-colored `group-hover` magnifying-glass icon). **"Refresh counts" is secondary** — lighter style (e.g. `bg-triggarr-card`/muted text) with the `ph-arrows-clockwise` icon, so Search Now still reads as the primary action.
- **D-10:** The **disconnected** footer is UNCHANGED — it keeps the single full-width "Retry Connection" button only. "Refresh counts" appears ONLY in the connected state. (A disconnected card has no counts to refresh; Retry already re-probes reachability.)
- **D-11:** Button label is exactly **"Refresh counts"**. Icon is `ph-arrows-clockwise` (the same icon Retry Connection uses — reads as "re-fetch").

### UI — interaction (locked here)
- **D-12:** "Refresh counts" mirrors Search Now's interaction **exactly**: `hx-post` to the new endpoint, `hx-target="#{{ app.card_id }}-card"`, `hx-swap="outerHTML"`, `hx-disabled-elt="this"` (disables + dims via `disabled:opacity-50 disabled:cursor-not-allowed` while in-flight), full-card partial swap on return. No spinner animation, no disabling of the sibling Search Now button (server-side `search_lock` serializes them).
- **D-13:** **No extra success cue** — the full-card swap is the confirmation, identical to Search Now. No "counts updated" flash, no refresh timestamp field. (Avoids new partial state / scope creep.)
- **D-14:** **No distinct failure signal** — a fetch failure renders the card's existing disconnected state (Retry Connection button + "unreachable since") on swap, same visual language as any connection loss. Mirrors `search_now`'s always-200+card pattern. No error banner / toast / OOB swap.

### Claude's Discretion
- Exact secondary-button Tailwind classes for "Refresh counts" (within "lighter than Search Now, uses `ph-arrows-clockwise`, `flex-1`").
- Whether the rate-limit uses a shared vs. sibling `last_*_time` dict (D-08 prefers sibling; planner confirms).
- Test fixture organization (new `test_refresh_counts.py` vs. extending existing engine/route test modules) — follow existing test layout conventions.
</decisions>

<specifics>
## Specific Ideas

- The "Search Now" button's in-flight/disabled affordance was hardened during the v2.9 walkthrough — reuse that exact pattern for "Refresh counts" rather than inventing a new one.
- Keep the count path's failure surface identical to the search path's: log + swallow the same `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)` tuple, always fall through to the 200 + card response (no 500s to the user).
</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design spec (source of truth)
- `docs/superpowers/specs/2026-06-02-recovery-counts-config-design.md` §3 — Track B full design: engine seam extraction (§3.2), count-path state semantics table (§3.3), endpoint+UI surface (§3.4), tests (§3.5).

### Requirements
- `.planning/REQUIREMENTS.md` — CNT-01..05 (the falsifiable acceptance criteria for this phase).
- `.planning/ROADMAP.md` Phase 74 — Goal + 4 Success Criteria (what must be TRUE).

### Code anchors (read to mirror, not re-derive)
- `triggarr/search/engine.py` — `run_radarr_cycle` (line 275), `run_sonarr_cycle` (517), `run_lidarr_cycle`; shared primitives `filter_monitored` (119), `slice_batch` (133), `filter_unreleased_movies` (225), `filter_sonarr_episodes` (194), `deduplicate_to_seasons` (159), `cap_batch_sizes` (92), `resolve_tag_id`/`filter_by_tag` (47/59). The seam to extract is everything BEFORE the first `slice_batch` call in each cycle.
- `triggarr/web/routes.py` — `search_now` (line 880) is the exact template for the new endpoint; `_build_app_context` (248), `SEARCH_RATE_LIMIT_SECONDS` (146), `partial_app_card` (975), the `_get_tags_cached` closure pattern (922).
- `triggarr/search/scheduler.py` — `_run_one_cycle` (290) and the SAFETY-03 failure-counter logic (`_record_failure`/reset around lines 239-290). The count path must NOT go through this. `make_search_job` cycle_fns map (113).
- `triggarr/templates/partials/app_card.html` — footer button block (lines ~109-127): connected "Search Now" + disconnected "Retry Connection" states.

### Pattern conventions
- `.planning/codebase/CONVENTIONS.md`, `.planning/codebase/TESTING.md` — established code + test patterns to follow.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`search_now` route (`routes.py:880`)** — copy its skeleton verbatim (guards, optimistic+in-lock rate-limit, `search_lock`, tag-cache resolver, `_build_app_context` → `app_card.html` response). Strip the `_run_one_cycle` call + replace with a direct `refresh_*_counts` helper call; drop the failure-counter/`last_run` semantics.
- **Shared engine filter primitives** (`engine.py`) — `filter_monitored`, `filter_unreleased_movies`, `filter_sonarr_episodes`, `deduplicate_to_seasons`, `cap_batch_sizes`, `resolve_tag_id`, `filter_by_tag` — call these from the extracted helpers so behavior matches the cycles exactly.
- **`_build_app_context` (`routes.py:248`)** — produces the `app` dict the card partial renders; reused unchanged for the refresh response.
- **`app_card.html` footer** — existing two-state (connected/disconnected) button block is the surface to modify; Search Now's `hx-*` attrs are the template for the new button.

### Established Patterns
- **Optimistic-then-in-lock rate-limit** (`routes.py:895-913`) — check before lock for fast-fail, re-check inside `search_lock` to prevent concurrent bypass (DRSEC-03). Mirror this.
- **Always 200 + card** — `search_now` logs+swallows the `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)` tuple and always returns the card partial. `_sanitize_exc` splits secret-bearing (httpx/pydantic) vs. safe (sqlite/OSError) messages. Mirror exactly.
- **Per-app cycle functions** mutate the per-instance state dict `ist` in place (`ist["missing_count"]`, `ist["connected"]`, `ist["missing_cursor"]`, etc.). The helper mutates the same fields EXCEPT cursor/`last_run`/`last_success`.
- **`_run_one_cycle` owns SAFETY-03** — it is the unified manual+scheduled failure-counter path (v2.9 CHARD work). Count path deliberately bypasses it.

### Integration Points
- New `refresh_*_counts` helpers live in `engine.py` alongside the cycle functions; `run_*_cycle` is refactored to call its helper then do slice+search+cursor+stamp.
- New `POST /api/refresh-counts/{app}/{instance}` route in `routes.py` (sibling to `search_now`).
- New button in `partials/app_card.html` connected-footer block.
- No new state fields required on `app.state` beyond an optional sibling `last_refresh_time` rate-limit dict (planner's call per D-08) — initialize alongside `last_search_time`/`search_failures` in app startup (`routes.py:~514` / app setup).
</code_context>

<deferred>
## Deferred Ideas

- "Counts as of HH:MM" refresh timestamp on the card — considered for the success cue, declined (D-13) as new partial state / arguably beyond the spec surface. Could revisit if users ask for staleness visibility.
- Refresh-failed toast / out-of-band notification pattern — declined (D-14); the app has no notification pattern today and adding one is scope creep.
- Animated spinning refresh icon — declined (D-12) in favor of mirroring Search Now's dim-only affordance.

None of these are in scope for Phase 74.
</deferred>

---

*Phase: 74-count-only-refresh*
*Context gathered: 2026-06-03*
