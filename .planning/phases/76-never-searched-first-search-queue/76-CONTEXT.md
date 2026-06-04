# Phase 76: Never-Searched-First Search Queue - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning

<domain>
## Phase Boundary

The search scheduler gains per-item memory: an ordered "searched-log" of *arr item IDs on `AppState` (per instance, per queue — missing/cutoff). Each cycle prioritizes never-searched items first, then tops up oldest-searched-first. Replaces the integer-cursor walk (`missing_cursor`/`cutoff_cursor` + `slice_batch`). Behavior-identical to today on a cold start (empty log = everything unsearched = same batch as the prior first cycle).

**The algorithm, data model, marking semantics, and removals are LOCKED by the design spec** `docs/superpowers/specs/2026-06-04-search-queue-priority-design.md` (10 decisions D-1..D-10) and the 11 QUEUE requirements in `.planning/REQUIREMENTS.md`. This discussion captured only the remaining HOW-to-implement choices. Out of scope (spec §9 YAGNI): retry counters/backoff, timestamp maps, a `SearchQueue` class, UI queue inspector, per-instance parallelism, and any change to fetch/filter, count-only refresh, scheduling, rate limits, or the SAFETY-03 failure counter.
</domain>

<decisions>
## Implementation Decisions

### prioritize_batch placement & signature (Area 1)
- **D-01:** The new pure function lives in `triggarr/search/engine.py`, replacing `slice_batch` for the search path. Signature: `prioritize_batch(eligible_items, searched_log, batch_size, key_fn) -> (batch, new_searched_log, pass_completed)`.
- **D-02:** Per-app ID normalization is passed in as a `key_fn` parameter (NOT an `app_type` string branched inside, NOT a module helper that takes `app_type`). `prioritize_batch` stays fully generic, app-agnostic, and pure — it only does set-membership and ordering over opaque string keys. Each of the three cycle functions passes its own small `key_fn`, co-located with the search call that already references `movie["id"]` / `season["seriesId"]` / `album["id"]`. Mirrors how the old `slice_batch` was generic.
- **D-03:** The function returns the **already-updated** searched-log (appends applied inside, mark-on-attempt) plus `pass_completed`. ALL log lifecycle — prune-to-eligible → partition unsearched/searched → assemble batch → append batched keys → detect pass-completion — is concentrated in this one pure function. The three callers stay thin: `ist["<q>_searched"] = [] if pass_completed else new_searched_log`, and `if pass_completed: ist["<q>_pass"] = ist.get("<q>_pass", 0) + 1`. Do NOT spread log-append logic across the call sites.
- **D-04:** Marking happens inside `prioritize_batch` (before the search loop runs). This is correct for mark-on-attempt (D-7 in spec): if the process crashes mid-loop, the cycle-end `save_state()` never runs, nothing commits, and those items replay next cycle — identical to today's cursor (at-least-once, never lost).

### Test-migration strategy for cursor removal (Area 2)
- **D-05:** Classify every cursor reference in `tests/` by role, then migrate-or-strip (do NOT blanket find-and-replace, do NOT tombstone the cursor fields to dodge churn):
  - **Behavioral assertions** (engine/dispatch tests — primarily `tests/test_search.py` ~28 refs, `tests/test_state.py` ~65 refs) that assert specific cursor **values** after a cycle → migrate to assert searched-log contents and/or `pass_completed` / `*_pass` instead. These are the real coverage to preserve.
  - **Incidental fixture setup** (UI/dashboard tests — `tests/test_app_cards.py`, `tests/test_stats_health.py`, `tests/test_ui_foundations.py`, `tests/test_activity_rail.py`, `tests/test_header_redesign.py`, `tests/test_log_viewer.py`, ~4–6 refs each) that just populate an `AppState` with a cursor field incidentally → strip the now-removed keys from the fixture; assert nothing about them.
- **D-06:** The **refresh-counts queue-independence invariant** (`tests/test_refresh_counts.py` ~23 refs, which today assert "cursor unchanged after refresh") is re-expressed, NOT deleted: assert the count-only path neither reads nor writes `missing_searched`/`cutoff_searched` (i.e. searched-log unchanged after a refresh-counts call). This preserves the v2.10 invariant that `refresh_*_counts()` is queue-independent.
- **D-07:** The planner enumerates the per-file classification (which refs are behavioral vs incidental) as part of the plan.

### Sonarr season-key edge cases (Area 3)
- **D-08:** Key string format is exactly `f"{seriesId}:{seasonNumber}"` (e.g. `"1234:2"`). Radarr/Lidarr keys are `str(item["id"])`. This keeps EVERY queue's searched-log a uniform `list[str]` (D-5/QUEUE-01), so `prioritize_batch` membership/ordering is identical across all three apps and `key_fn` is the only per-app difference. The key is opaque to `prioritize_batch` — it only needs to be stable and collision-free, which integer:integer is.
- **D-09:** Sonarr Specials (`seasonNumber == 0` → `"1234:0"`) are treated as an ordinary distinct key (Specials are searchable). No special-casing.
- **D-10:** `deduplicate_to_seasons()` is unchanged and still runs at filter time, preserving first-occurrence order. The season dicts therefore reach `prioritize_batch` already in stable fetch order, so the "never-searched-first, in fetched API order" partition operates on that order with no extra sorting.

### Empty/partial-pass logging & observability (Area 4)
- **D-11:** Minimal logging. Keep the existing per-cycle INFO diagnostic (elapsed / fetched / searched / skipped) exactly as-is. On pass-completion, emit ONE INFO line analogous to today's wrap-around log — naming the app/instance, queue (missing/cutoff), the completed pass number, and items-searched-this-pass — then the log clears. No per-cycle searched-log dumps, no unsearched-count spam.
- **D-12:** No new dashboard/UI surface. The `*_pass` counter remains the only dashboard-facing signal (unchanged from today). Failed individual searches still log a WARNING + write a `failed` search-history row exactly as today.

### Claude's Discretion
- Exact wording of log lines (within D-11's content requirements).
- Internal structure of `prioritize_batch` (helper locals, comprehension vs loop) as long as it's pure and returns the D-01 tuple.
- Test file/function naming for the new `prioritize_batch` unit tests (follow existing `tests/` conventions).
</decisions>

<specifics>
## Specific Ideas

- `prioritize_batch` should be as generic and unit-testable as the old `slice_batch` was — fake items + a fake `key_fn`, no app coupling.
- The behavior-preserving cold-start guarantee is the load-bearing safety property: empty searched-log must produce the same batch the prior first-cycle cursor walk produced. This is an explicit success criterion and should have a dedicated test.
</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design spec (source of truth — read first)
- `docs/superpowers/specs/2026-06-04-search-queue-priority-design.md` — The full design. §3 = 10 locked decisions (D-1..D-10: identity, pass-reset, fill policy, ordering, storage, representation, mark-on-attempt, commit timing, cursor removal, slice_batch removal). §6 = the `prioritize_batch` algorithm (prune → partition → batch → mark → pass-detect). §7 = error/edge cases. §8 = exhaustive test list. §9 = YAGNI scope fence. §10 = anticipated affected files.

### Requirements
- `.planning/REQUIREMENTS.md` — QUEUE-01..11 (the 11 requirements this phase delivers) + the Out-of-Scope table. All 11 map to this phase.

### Roadmap
- `.planning/ROADMAP.md` §"v2.11 ... Phase 76" — goal + 5 success criteria (encode cold-start equivalence, existing tests green, count-only queue-independence).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `triggarr/search/engine.py:133` `slice_batch(items, cursor, batch_size) -> (batch, new_cursor)` — the function `prioritize_batch` REPLACES. Six call sites to rewire: missing+cutoff in each of `run_radarr_cycle` (~408/457), `run_sonarr_cycle` (~647/702), `run_lidarr_cycle` (~898/948). Remove `slice_batch` after.
- `triggarr/search/engine.py` `deduplicate_to_seasons()` — Sonarr episode→season collapse, preserves first-occurrence order; unchanged. Season dicts carry `seriesId`, `seasonNumber`, `display_name`, `episode_count`.
- `triggarr/state.py:43` `AppState` TypedDict (`total=False`) — add `missing_searched: list[str]` / `cutoff_searched: list[str]`; remove `missing_cursor` / `cutoff_cursor`; keep `missing_pass` / `cutoff_pass`.
- `triggarr/state.py:77` `_default_instance_state()` — return empty searched-logs, no cursors.
- `triggarr/state.py:185` `save_state()` — atomic write-then-rename; the searched-log + pass commit in this single existing cycle-end call (D-8). No new write path.

### Established Patterns
- Per-item identity already used at the search call sites: Radarr/Lidarr `item["id"]`, Sonarr `season["seriesId"]` + `season["seasonNumber"]` — exactly the fields `key_fn` consumes.
- Cycle abort on fetch failure happens BEFORE batch assembly (cursor/log untouched on failure) — preserve: only mutate the searched-log after a successful fetch.
- `hard_max_per_cycle` proportional cap (`cap_batch_sizes`, engine.py:~92) computes the per-queue limit BEFORE batching — `prioritize_batch` receives the already-capped `batch_size`. No interaction to change.
- Count-only path (`refresh_radarr_counts`/`refresh_sonarr_counts`/`refresh_lidarr_counts`, engine.py ~1014+) does NOT call `slice_batch` and must NOT call `prioritize_batch` or touch the searched-log — queue-independence preserved.

### Integration Points
- `tests/` — cursor references span many files (see D-05/D-06 classification): `test_search.py`, `test_state.py` (behavioral → migrate), `test_refresh_counts.py` (invariant → re-express against searched-log), and several UI/dashboard test fixtures (incidental → strip). New `prioritize_batch` unit tests + cycle-integration + cold-start-equivalence + back-compat-load tests per spec §8.
- `.planning/codebase/TESTING.md`, `CONVENTIONS.md` — follow existing pytest-asyncio (`asyncio_mode=auto`) and ruff conventions; no new test deps.
</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (All scope-creep candidates — retry/backoff, timestamps, UI queue inspector, per-instance parallelism — are already explicitly fenced out in the design spec §9 and `.planning/REQUIREMENTS.md` Out-of-Scope table.)
</deferred>

---

*Phase: 76-never-searched-first-search-queue*
*Context gathered: 2026-06-04*
