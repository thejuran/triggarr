# Search Queue Priority — Never-Searched-First Dispatch

**Date:** 2026-06-04
**Status:** Approved design (brainstorming) — ready for roadmapping
**Topic:** Replace the blind integer-cursor search walk with per-item memory that prioritizes never-searched items.

---

## 1. Problem

Today the search scheduler has **no per-item memory**. Each instance tracks only an integer
cursor position (`missing_cursor` / `cutoff_cursor` in `triggarr/state.py`) and walks the
wanted/missing and cutoff-unmet lists round-robin via `slice_batch()` in
`triggarr/search/engine.py`. The wanted lists are re-fetched fresh from the
Radarr/Sonarr/Lidarr API every cycle, and items are processed in **raw API order** from the
cursor position with wrap-around.

Consequences:

- Items are searched in arbitrary API return order, not by whether they've ever been tried.
- A brand-new wanted item does not jump ahead of items already searched this pass — it waits
  for the cursor to reach its list position.
- The integer cursor is fragile under list churn: when the list reorders or changes length
  between cycles (items grabbed, added, unmonitored), the cursor can skip or re-hit items
  because it indexes a *position*, not an *identity*.

`POST /api/refresh-counts` (count-only refresh, v2.10 Phase 74) is a separate read-only
operation that does not touch the queue, and stays that way.

## 2. Goal

The search scheduler **prioritizes items it has never searched before** when deciding what to
search next. Concretely, within each cycle's batch: fill with never-searched items first (in
fetched API order), then — if the batch is not full — top up with already-searched items
**oldest-searched-first**. This is strictly additive to throughput: on a cold start (nothing
searched yet) the behavior is identical to today's first cycle.

## 3. Locked Decisions

These were resolved during brainstorming and are not open for re-litigation during planning:

| # | Decision | Choice |
|---|----------|--------|
| D-1 | Unit of "have I searched this" | **Per-item stable *arr ID**, scoped per instance per queue (missing vs cutoff). Radarr = `movie id`; Lidarr = `album id`; Sonarr = composite `"{seriesId}:{seasonNumber}"`. |
| D-2 | What happens when everything eligible has been searched once | **Reset the searched memory and start a fresh pass.** Bump the existing `missing_pass` / `cutoff_pass` counter on reset. |
| D-3 | Within-batch fill policy | **Unsearched-first, then top up** with already-searched so the batch is never artificially small. Throughput unchanged from today. |
| D-4 | Top-up ordering among already-searched | **Oldest-searched-first.** This requires recency, which the data structure encodes (see D-6). |
| D-5 | Storage location | **New fields on the existing `AppState`** in `state.json`. No sidecar file. Committed at cycle end via the existing atomic `save_state()`. |
| D-6 | Memory representation | **Ordered searched-log**: a list of IDs in the order they were searched (oldest at the front). Provides both membership ("searched?") and recency ("oldest = front"). **Replaces** the integer cursor for dispatch. |
| D-7 | Mark on attempt vs. success | **Mark on attempt** (success OR failure). The literal reading of "never searched before" = never *attempted*. Starvation-free: a persistently-failing item cannot sit permanently at the front. |
| D-8 | Commit timing | **At cycle end**, in the same atomic `save_state()` that persists the rest of the cycle's state. At-least-once semantics; the searched-log and `*_pass` can never disagree. |
| D-9 | Old cursor keys | **Removed outright** from the `AppState` TypedDict (no tombstone, no separate versioned migration function). **CORRECTION (found during Phase 76 planning, codex HIGH-1 — supersedes the original wording):** pre-upgrade `state.json` files do NOT "tolerate the leftover keys harmlessly until the next save overwrites them" — `_merge_defaults` uses `{**default, **instance_data}`, which PRESERVES unknown keys, and `save_state` writes them back, so they would persist indefinitely. The fix is an inline strip in `_merge_defaults` on load: `for legacy_key in ("missing_cursor","cutoff_cursor"): merged.pop(legacy_key, None)`, with a load→save round-trip test asserting the keys are ABSENT from the written JSON. Still no separate migration function (matches the v2.2→v2.3 transform-and-drop precedent, not the still-live `search_log` carry-forward). |
| D-10 | `slice_batch` | **Removed** along with its tests once all 6 callers move to `prioritize_batch`. No dead code left. |

## 4. Architecture & Policy

**Policy summary:**

1. **Identity** — per-item stable *arr ID, per instance, per queue (missing vs cutoff).
   Radarr=`movie id`, Lidarr=`album id`, Sonarr=`"{seriesId}:{seasonNumber}"`. All stored as
   **strings** so the field has a single type.
2. **Priority** — never-searched items first (fetched API order); top up with already-searched
   **oldest-searched-first**.
3. **Memory = ordered searched-log** — list of IDs in search order, oldest at the front.
   Provides membership + recency. **Replaces** `missing_cursor`/`cutoff_cursor` for dispatch.
4. **Mark-on-attempt** — an ID joins the log once its search command is fired, regardless of
   per-item success/failure.
5. **Pass reset** — when every currently-eligible item is in the log, the pass is complete →
   clear the log for that queue and bump `missing_pass`/`cutoff_pass`.
6. **Prune-to-eligible** — each cycle, intersect the log with the currently-eligible IDs so
   departed items drop out and the log stays bounded (worst case = eligible-count, then resets).
7. **Commit at cycle end** — log + pass-counter persist in the single atomic `save_state()`
   already run at cycle end.

**Behavior-preserving on cold start:** empty log = everything unsearched = batch filled in API
order, exactly like today's first cycle.

**Explicitly unchanged:** fetch/filter phases; batch-size config (`search_missing_count`,
`search_cutoff_count`); `hard_max_per_cycle` proportional cap; the global `search_lock`;
scheduler intervals; the 10s manual-search rate limit; the SAFETY-03 consecutive-failure
counter; search-history SQLite writes; and the count-only refresh path (still never touches the
queue).

## 5. Data Model & State Migration

In `triggarr/state.py`, `AppState` (TypedDict, `total=False`):

```python
class AppState(TypedDict, total=False):
    # REMOVED: missing_cursor, cutoff_cursor  (dispatch no longer uses a positional cursor)
    missing_pass: int    # KEPT — now bumped on searched-log reset, not cursor wrap
    cutoff_pass: int     # KEPT — same
    missing_searched: list[str]   # NEW — ordered searched-log (oldest first), missing queue
    cutoff_searched: list[str]    # NEW — ordered searched-log (oldest first), cutoff queue
    # ... all timing/count/connectivity fields unchanged ...
```

- **ID normalization** — a small per-app `item_key(item) -> str` helper:
  Radarr/Lidarr `str(item["id"])`; Sonarr `f'{item["seriesId"]}:{item["seasonNumber"]}'`.
- **Migration** — no separate versioned migration function. Both new fields are `total=False`;
  existing `state.json` files simply lack them and dispatch reads them with
  `.get("<q>_searched", [])`. The first cycle after upgrade starts with an empty log → treats
  every item as unsearched → one rediscovery pass where everything gets searched once.
  **CORRECTION (Phase 76 planning, codex HIGH-1):** leftover `missing_cursor`/`cutoff_cursor`
  keys are NOT merely "ignored and overwritten on the next save" — `_merge_defaults`'
  `{**default, **instance_data}` preserves unknown keys, so they persist unless actively
  removed. `_merge_defaults` therefore performs an inline strip on load
  (`merged.pop("missing_cursor"/"cutoff_cursor", None)`); a load→save round-trip test asserts
  the keys are ABSENT from the written JSON.
- **`_default_instance_state()`** — returns empty searched-logs (and no cursors).
- **Bound** — pruning to eligible each cycle caps log size at the eligible-item count for that
  queue; reset-on-pass-complete returns it to empty. No unbounded growth.

## 6. Dispatch Flow

New **pure** function in `triggarr/search/engine.py`, replacing `slice_batch` for the search
path:

```python
def prioritize_batch(
    eligible_items: list,
    searched_log: list[str],
    batch_size: int,
    key_fn,                       # item -> str ID (per-app)
) -> tuple[list, list[str], bool]:
    """Assemble a batch: never-searched first (fetch order), then top up with
    already-searched oldest-first.

    Returns (batch, new_searched_log, pass_completed).
    """
```

**Algorithm (per queue, per cycle):**

1. `eligible_ids = {key_fn(it) for it in eligible_items}` — live set after fetch+filter.
2. **Prune:** `log = [id for id in searched_log if id in eligible_ids]` — drop departed items,
   preserve order.
3. **Partition** eligible items into `unsearched` (key ∉ log, in fetch order) and `searched`
   (key ∈ log).
4. **Batch:** take `unsearched[:batch_size]`; if short, top up from `searched` ordered by the
   log (front = oldest-searched) until full or exhausted.
5. **Mark (mark-on-attempt):** append each batched item's key to `log`. New unsearched keys
   append to the end; a re-searched key moves to the end (becomes most-recent).
6. **Pass-complete check (CORRECTED — codex MED-1):** `pass_completed = bool(batch) and
   eligible_ids.issubset(set(new_log))`. The `bool(batch)` term is MANDATORY (matching the old
   wrap semantic `if new_cursor == 0 and batch`): a pass completes only when this cycle actually
   searched something AND every eligible id is now in the log. This prevents a **zero-search**
   pass reset — with `batch_size <= 0` (reachable via `hard_max` proportional capping) or a
   zero-cap queue whose pruned log already covers a now-tiny eligible set, the batch can be empty
   while `eligible_ids.issubset(...)` is `True`; without `bool(batch)` that would clear the log
   and bump `*_pass` having searched nothing. (Empty eligible list → `([], [], False)` falls out
   of the same guard: no batch ⇒ no completion.)

**Caller changes — 6 sites** (missing + cutoff in each of Radarr/Sonarr/Lidarr cycle fns).
Replace:

```python
batch, new_cursor = slice_batch(items, cursor, limit)
```

with:

```python
batch, new_log, pass_done = prioritize_batch(
    items, ist.get("<q>_searched", []), limit, key_fn
)
```

The per-item search loop body is **unchanged** (same `try` / `search_*` / `insert_search_entry`
/ count). After the loop:

```python
ist["<q>_searched"] = [] if pass_done else new_log
if pass_done:
    ist["<q>_pass"] = ist.get("<q>_pass", 0) + 1
```

**Marking happens inside `prioritize_batch` (step 5), before the search loop runs.** This is
intentional and correct for mark-on-attempt. If the process crashes mid-loop, the cycle-end
`save_state()` never runs, so nothing commits and those items replay next cycle — identical to
today's cursor semantic (at-least-once, never lost).

## 7. Error Handling, Edge Cases & Interactions

- **Fetch failure (cycle aborts):** unchanged. The cycle aborts before `prioritize_batch` is
  called; the searched-log is untouched, `connected=False`, `unreachable_since` set. The log is
  only ever mutated after a successful fetch — exactly where the cursor was.
- **Per-item search failure:** unchanged behavior. The key was already appended in
  `prioritize_batch` (mark-on-attempt), so a failed search still counts as "searched" for
  prioritization. The existing `except` block still logs, writes a `failed` history row, and
  increments `skipped_count`. No starvation.
- **Empty eligible list:** `([], [], False)` — nothing to do, pass not falsely completed.
- **Zero-search batch (`batch_size <= 0`, or zero-cap queue whose pruned log already covers the
  eligible set) — codex MED-1:** `batch == []` ⇒ `pass_completed = False` (the `bool(batch)`
  guard), and the log is NOT cleared and `*_pass` is NOT bumped. A cycle that searches nothing
  never completes a pass.
- **Eligible smaller than batch size:** all eligible searched (non-empty batch),
  `pass_completed=True`, log clears, `*_pass` bumps.
- **`hard_max_per_cycle`:** unchanged. The proportional cap (`cap_batch_sizes`) still computes
  `missing_limit`/`cutoff_limit` before `prioritize_batch`, which receives the already-capped
  `batch_size`.
- **Multi-cycle pass:** with eligible=100, batch=5, a pass spans ~20 cycles. `pass_completed`
  fires only on the cycle where the last unsearched items enter the log; the log grows until
  then, then clears.
- **Sonarr dedup:** `deduplicate_to_seasons()` runs at filter time and preserves first-occurrence
  order, so `eligible_items` are season dicts in stable order. `key_fn` =
  `f'{s["seriesId"]}:{s["seasonNumber"]}'` distinguishes seasons of the same series.
- **Count-only refresh:** untouched. `refresh_*_counts()` does not call `prioritize_batch` and
  never reads/writes the searched-log. The v2.10 queue-independence invariant is preserved.
- **Concurrency:** unchanged. The single global `search_lock` serializes all cycles, so the
  searched-log read-modify-write is never concurrent for an instance. No new locking.
- **Dashboard / `*_pass`:** the pass counters keep incrementing (now on log-reset rather than
  cursor-wrap), so any dashboard element showing pass count behaves the same. Count fields are
  computed in fetch/filter and unaffected.

## 8. Testing Strategy

**Unit tests — `prioritize_batch` (pure, exhaustive):**

- Cold start (empty log) → batch = first `N` in fetch order; identical to old `slice_batch`.
- Unsearched-first → batch takes all unsearched before any searched.
- Top-up oldest-first → fewer unsearched than `N`; remaining slots fill from log front.
- Pass completion → batch covers the last unsearched → `pass_completed=True`, returned log is
  the full set (caller clears).
- Mid-pass no-completion → unsearched remain → `pass_completed=False`, log grew correctly.
- Prune → log holds no-longer-eligible IDs → dropped, survivor order preserved.
- Re-search recency → a re-batched already-searched item moves to the log tail.
- Empty eligible → `([], [], False)`.
- **Zero-search batch (codex MED-1)** → `batch_size <= 0`, AND a zero-cap queue whose pruned log
  already covers a non-empty eligible set → both return `batch == []`, `pass_completed == False`,
  and do NOT mutate/grow the log (the `bool(batch)` guard).
- Eligible < `N` → all searched (non-empty batch), pass completes.
- `key_fn` correctness → Sonarr composite distinguishes S1/S2 of one series; Radarr/Lidarr
  int→str.

**Cycle-integration tests (per app, extend existing cycle tests):**

- Two-cycle sequence: cycle 1 searches A–E, cycle 2 (same fetch) searches F–J — no re-search
  within a pass.
- New item jumps the line: cycle 2's fetch adds a new item → searched ahead of any
  already-searched top-up.
- Mark-on-attempt: an item whose `search_*` raises is still in the log next cycle (not
  re-prioritized).
- Pass reset bumps `*_pass` and clears the log; the next cycle re-searches everything.
- Fetch failure → log untouched, `connected=False` (existing assertions hold).
- Commit-at-cycle-end → state saved once at end; log + `*_pass` consistent.

**Migration / back-compat:**

- Load a pre-upgrade `state.json` containing `missing_cursor`/`cutoff_cursor` but no
  searched-logs → loads clean, dispatch treats everything as unsearched. **CORRECTION (Phase 76
  planning, codex HIGH-1):** the leftover cursor keys are NOT "ignored and overwritten on next
  save" — they are actively STRIPPED by `_merge_defaults` on load (`merged.pop(...)`); the test
  loads → saves → reloads and asserts the keys are ABSENT from the written JSON.

**Regression / preservation:**

- Existing cycle tests asserting search *counts* and history rows stay green (search loop body
  unchanged).
- Tests asserting specific `missing_cursor` *values* are migrated to assert searched-log
  contents instead (the cursor no longer exists). The plan enumerates these.
- Count-only refresh tests untouched and green (proves queue-independence).

**Tooling:** `pytest tests/ -x -q` (pytest-asyncio, `asyncio_mode=auto`), `ruff check`. No new
test dependencies.

## 9. Scope Boundaries (YAGNI)

Explicitly **out of scope** for this milestone:

- No per-item retry counters / backoff (mark-on-attempt deliberately avoids retry machinery).
- No timestamp map (the ordered searched-log gives recency without per-item timestamps).
- No `SearchQueue` class / OO refactor (kept as plain `AppState` fields + a pure function).
- No UI queue inspector / reorder / pin (could build on this later; not now).
- No per-instance parallelism / per-instance locks (global `search_lock` unchanged).
- No change to fetch, filtering, count-only refresh, scheduling intervals, or rate limits.

## 10. Affected Files (anticipated)

- `triggarr/state.py` — `AppState` field changes; `_default_instance_state()`.
- `triggarr/search/engine.py` — add `prioritize_batch` + `item_key` helper; remove
  `slice_batch`; update 6 call sites in the three cycle functions.
- `tests/` — new `prioritize_batch` unit tests; updated cycle-integration tests; migrated
  cursor-value assertions; back-compat load test.
