# Phase 76: Never-Searched-First Search Queue - Research

**Researched:** 2026-06-04
**Domain:** Internal refactor of the search-dispatch path (pure-function + state-model swap) in an existing FastAPI/asyncio Python daemon
**Confidence:** HIGH (all anchors verified against live code; no external dependencies; all decisions pre-locked by spec + CONTEXT)

## Summary

This phase replaces the integer round-robin cursor (`missing_cursor`/`cutoff_cursor` + `slice_batch`) with a per-instance, per-queue ordered "searched-log" on `AppState` and a single pure function `prioritize_batch()` that picks never-searched items first (in fetch order), tops up oldest-searched-first, marks-on-attempt, prunes to eligible, and signals pass-completion. The entire WHAT/WHY/HOW is locked by the design spec (`docs/superpowers/specs/2026-06-04-search-queue-priority-design.md`, 10 decisions) and CONTEXT.md (12 implementation decisions D-01..D-12). This is **not** a research-the-options exercise — every anchor cited by the spec was confirmed against the live codebase, and this document hands the planner exact line numbers, a precise test-migration classification, the specific behavior-preservation pitfalls, and a Nyquist validation architecture.

**Verified anchors (live code, 2026-06-04):** `slice_batch` at `engine.py:133`; **exactly 6 call sites** at lines 408, 457 (Radarr missing/cutoff), 647, 702 (Sonarr), 898, 948 (Lidarr) — every other `slice_batch` mention in `engine.py` is a docstring comment, and there are **zero** call sites outside `engine.py`. The `AppState` TypedDict (`state.py:43`, `total=False`) carries `missing_cursor`/`cutoff_cursor`/`missing_pass`/`cutoff_pass`; `_default_instance_state()` (`state.py:77`) returns `missing_cursor=0, cutoff_cursor=0`. `save_state()` is invoked from the scheduler at `scheduler.py:377-379` **after** the cycle function returns — the single cycle-end commit point (D-08/QUEUE-11). `refresh_*_counts` (engine.py:1014/1149/1289) never call `slice_batch` and never touch cursors — confirmed (queue-independence preserved).

**Primary recommendation:** Implement `prioritize_batch(eligible_items, searched_log, batch_size, key_fn) -> (batch, new_searched_log, pass_completed)` as a pure function in `engine.py` per spec §6; wire all 6 call sites with the thin caller pattern from CONTEXT D-03; swap the `AppState` fields and `_default_instance_state()` per spec §5; then migrate the test surface using the per-file classification table below. The load-bearing safety property is **cold-start behavior equivalence** (empty log ⇒ same batch as today's first-cycle cursor walk) — it gets a dedicated property test.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Searched-log storage (`missing_searched`/`cutoff_searched`) | State persistence (`state.py` AppState + `save_state`) | — | The log is just new fields on the existing per-instance state dict, committed via the existing atomic write (D-5/QUEUE-01/QUEUE-11) |
| Batch selection (never-searched-first, top-up, mark, pass-detect) | Search engine pure function (`engine.py::prioritize_batch`) | — | Pure, app-agnostic, fully unit-testable over opaque string keys (D-01/D-02) |
| Per-app ID normalization (`key_fn`) | Search engine cycle functions (call sites) | — | Co-located with the existing `movie["id"]`/`season[...]`/`album["id"]` search calls; the only per-app difference (D-02/D-08) |
| Log lifecycle wiring (write-back, pass-reset, `*_pass` bump) | Search engine cycle functions (6 call sites) | State persistence | Thin callers: `ist["<q>_searched"] = [] if pass_done else new_log`; commit at cycle end (D-03/QUEUE-09) |
| Commit timing | Scheduler (`scheduler.py:377`) | — | Existing single `save_state` after cycle returns; no new write path (D-08/QUEUE-11) |
| Count-only refresh (must stay queue-independent) | Search engine (`refresh_*_counts`) | — | Never reads/writes the searched-log; v2.10 invariant preserved (D-06/spec §7) |

## User Constraints (from CONTEXT.md)

### Locked Decisions

**prioritize_batch placement & signature (Area 1)**
- **D-01:** New pure function lives in `triggarr/search/engine.py`, replacing `slice_batch` for the search path. Signature: `prioritize_batch(eligible_items, searched_log, batch_size, key_fn) -> (batch, new_searched_log, pass_completed)`.
- **D-02:** Per-app ID normalization is passed in as a `key_fn` parameter (NOT an `app_type` string branched inside, NOT a module helper that takes `app_type`). `prioritize_batch` stays fully generic, app-agnostic, pure — set-membership and ordering over opaque string keys. Each cycle function passes its own small `key_fn`, co-located with the search call that already references `movie["id"]` / `season["seriesId"]` / `album["id"]`. Mirrors how `slice_batch` was generic.
- **D-03:** The function returns the **already-updated** searched-log (appends applied inside, mark-on-attempt) plus `pass_completed`. ALL log lifecycle — prune → partition → assemble → append → detect pass-completion — is concentrated in this one pure function. The three callers stay thin: `ist["<q>_searched"] = [] if pass_completed else new_searched_log`, and `if pass_completed: ist["<q>_pass"] = ist.get("<q>_pass", 0) + 1`. Do NOT spread log-append logic across the call sites.
- **D-04:** Marking happens inside `prioritize_batch` (before the search loop runs). Correct for mark-on-attempt: if the process crashes mid-loop, the cycle-end `save_state()` never runs, nothing commits, those items replay next cycle — identical to today's cursor (at-least-once, never lost).

**Test-migration strategy for cursor removal (Area 2)**
- **D-05:** Classify every cursor reference in `tests/` by role, then migrate-or-strip (do NOT blanket find-and-replace, do NOT tombstone the cursor fields). Behavioral assertions (engine/dispatch tests) → migrate to searched-log / `pass_completed` / `*_pass` assertions. Incidental fixture setup (UI/dashboard tests) → strip removed keys, assert nothing about them.
- **D-06:** The refresh-counts queue-independence invariant (`tests/test_refresh_counts.py`) is re-expressed, NOT deleted: assert the count-only path neither reads nor writes `missing_searched`/`cutoff_searched` (searched-log unchanged after a refresh-counts call). Preserves the v2.10 invariant that `refresh_*_counts()` is queue-independent.
- **D-07:** The planner enumerates the per-file classification (behavioral vs incidental) as part of the plan.

**Sonarr season-key edge cases (Area 3)**
- **D-08:** Key string format is exactly `f"{seriesId}:{seasonNumber}"` (e.g. `"1234:2"`). Radarr/Lidarr keys are `str(item["id"])`. Keeps every queue's searched-log a uniform `list[str]`, so membership/ordering is identical across all three apps and `key_fn` is the only per-app difference. Opaque to `prioritize_batch`.
- **D-09:** Sonarr Specials (`seasonNumber == 0` → `"1234:0"`) are an ordinary distinct key (Specials are searchable). No special-casing.
- **D-10:** `deduplicate_to_seasons()` is unchanged and still runs at filter time, preserving first-occurrence order. Season dicts reach `prioritize_batch` already in stable fetch order; the never-searched-first partition operates on that order with no extra sorting.

**Empty/partial-pass logging & observability (Area 4)**
- **D-11:** Minimal logging. Keep the existing per-cycle INFO diagnostic (elapsed / fetched / searched / skipped) exactly as-is. On pass-completion, emit ONE INFO line analogous to today's wrap-around log — naming the app/instance, queue (missing/cutoff), the completed pass number, and items-searched-this-pass — then the log clears. No per-cycle searched-log dumps, no unsearched-count spam.
- **D-12:** No new dashboard/UI surface. The `*_pass` counter remains the only dashboard-facing signal (unchanged). Failed individual searches still log a WARNING + write a `failed` search-history row exactly as today.

### Claude's Discretion
- Exact wording of log lines (within D-11's content requirements).
- Internal structure of `prioritize_batch` (helper locals, comprehension vs loop) as long as it's pure and returns the D-01 tuple.
- Test file/function naming for the new `prioritize_batch` unit tests (follow existing `tests/` conventions).

### Deferred Ideas (OUT OF SCOPE)
None new from discussion. Already fenced out by spec §9 + REQUIREMENTS.md Out-of-Scope: per-item retry/backoff, timestamp maps, a `SearchQueue` class/OO refactor, UI queue inspector/reorder/pin, per-instance parallelism/locks, and any change to fetch/filter, count-only refresh, scheduling intervals, rate limits, or the SAFETY-03 consecutive-failure counter.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QUEUE-01 | Ordered searched-log of *arr IDs per queue (oldest at front) in `state.json` | `AppState` (state.py:43) gains `missing_searched`/`cutoff_searched: list[str]`; committed by `save_state` (state.py:185 → called scheduler.py:377). Verified. |
| QUEUE-02 | IDs normalized to strings per app — Radarr/Lidarr `id`; Sonarr `seriesId:seasonNumber` | `key_fn` co-located at the 6 call sites; identity fields already used at search calls (engine.py:411 `movie["id"]`, 650/705 `season["seriesId"]`/`["seasonNumber"]`, 902/952 `album["id"]`). Verified (D-08). |
| QUEUE-03 | Remove `missing_cursor`/`cutoff_cursor`; pre-upgrade `state.json` loads clean, treated as everything-unsearched (no migration) | `total=False` TypedDict + `_merge_defaults` (state.py:129) preserves unknown keys harmlessly; dispatch reads `ist.get("<q>_searched", [])`. Verified — leftover cursor keys ignored, overwritten next save. |
| QUEUE-04 | Batch filled never-searched-first, fetched API order | `prioritize_batch` step 3-4 (spec §6); eligible items reach it in fetch order (dedup preserves order, engine.py:159/643/699). |
| QUEUE-05 | Top up remaining slots with already-searched, oldest-first | `prioritize_batch` step 4; recency encoded by log order (front = oldest). |
| QUEUE-06 | Cold start (empty log) ⇒ same batch as today's first-cycle cursor walk | Cold-start equivalence property test (Validation Architecture below); empty log ⇒ all unsearched ⇒ `unsearched[:batch_size]` == `slice_batch(items, 0, batch_size)[0]`. |
| QUEUE-07 | `slice_batch` replaced by `prioritize_batch` at all 6 sites; `slice_batch` removed | 6 sites confirmed (lines 408/457/647/702/898/948); zero external callers. Remove `slice_batch` (engine.py:133) + its 5 unit tests after wiring. |
| QUEUE-08 | Mark-on-attempt (success OR failure); persistently-failing item cannot starve | Marking inside `prioritize_batch` before the loop (D-04); the per-item `except` block (engine.py:431/480 etc.) is unchanged — key already appended. |
| QUEUE-09 | Pass-complete ⇒ clear that queue's log + increment `missing_pass`/`cutoff_pass` | `pass_completed` from `prioritize_batch` step 6; caller: `ist["<q>_searched"] = []`, `ist["<q>_pass"] += 1`. Replaces the `new_cursor == 0 and batch` wrap detection (engine.py:446/495 etc.). |
| QUEUE-10 | Prune searched-log to currently-eligible IDs each cycle | `prioritize_batch` step 2 (`log = [id for id in searched_log if id in eligible_ids]`). |
| QUEUE-11 | Log + pass-counter commit only at cycle end, in the same atomic `save_state()` | `save_state` at scheduler.py:377-379 runs once after `cycle_fn` returns. Verified single commit point. |

## Standard Stack

No new libraries. This is an internal refactor using the existing stack.

### Core (existing — verified in pyproject.toml)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.3+ | Test runner | Project standard; `asyncio_mode = "auto"` (pyproject `[tool.pytest.ini_options]`) [VERIFIED: pyproject.toml] |
| pytest-asyncio | (auto mode) | Async cycle tests | All `async def test_*` auto-wrapped [VERIFIED: pyproject.toml] |
| loguru | (existing) | Logging incl. redacting sink | Project mandates loguru, never `print`/stdlib logging (triggarr/CLAUDE.md) [VERIFIED: state.py:19 import] |
| ruff | py311, line-length 120 | Lint | `select = ["E", "F", "I", "UP", "B", "SIM"]` [VERIFIED: pyproject.toml:42-46] |

**Installation:** None. `uv sync --extra dev` is already the dev setup; no new test dependencies (spec §8).

## Package Legitimacy Audit

Not applicable — this phase installs **zero** external packages. All work uses the existing, already-vendored stack (pytest, pytest-asyncio, loguru, ruff). No registry interaction, no new imports. The slopcheck / registry-verification gate is satisfied vacuously (nothing to verify).

## Architecture Patterns

### System Architecture Diagram

```
                  Scheduler (scheduler.py)
                          │
            run_in_executor(save_state)  ← single cycle-end commit (QUEUE-11)
                          ▲
                          │ returns mutated state
        ┌─────────────────┴──────────────────┐
        │   run_<app>_cycle (engine.py)       │
        │                                     │
   fetch wanted/missing + cutoff              │
        │                                     │
   [FETCH FAILURE] ──► connected=False, RETURN (log untouched) ── spec §7
        │ success                             │
   filter (monitored / tag / unreleased /     │
           dedup_to_seasons for Sonarr)       │
        │  eligible_items (stable fetch order)│
   cap_batch_sizes(...) ──► missing_limit/cutoff_limit  (engine.py:346)
        │                                     │
        ▼                                     │
   ┌──────────────────────────────────────┐  │
   │ prioritize_batch(eligible_items,      │  │   PURE — no I/O
   │   ist.get("<q>_searched", []),        │  │
   │   limit, key_fn)                      │  │
   │   1. eligible_ids = {key_fn(it)...}   │  │
   │   2. prune log to eligible_ids        │  │ (QUEUE-10)
   │   3. partition unsearched/searched    │  │ (QUEUE-04)
   │   4. batch = unsearched[:N] + topup   │  │ (QUEUE-05)
   │   5. append batched keys (MARK)       │  │ (QUEUE-08, before loop)
   │   6. pass_completed if all in log     │  │ (QUEUE-09)
   │  -> (batch, new_log, pass_completed)  │  │
   └──────────────────────────────────────┘  │
        │ batch                               │
        ▼                                     │
   per-item search loop  (UNCHANGED body)     │
     try: search_*  / insert_search_entry     │
     except: WARNING + 'failed' history row   │
        │                                     │
   write-back (thin):                         │
     ist["<q>_searched"] = [] if pass_done    │
                          else new_log         │
     if pass_done: ist["<q>_pass"] += 1; log  │
        └─────────────────────────────────────┘

   refresh_<app>_counts (engine.py:1014/1149/1289) ── NEVER calls prioritize_batch,
        NEVER reads/writes searched-log (queue-independence, QUEUE-... preserved)
```

### Recommended Implementation Surface (verified files only)
```
triggarr/
├── state.py            # AppState fields swap; _default_instance_state()
└── search/
    └── engine.py       # add prioritize_batch (+ optional item_key helper);
                        #   remove slice_batch; rewire 6 call sites
tests/
├── test_search.py      # behavioral migrate + new prioritize_batch unit tests
├── test_state.py       # default-state/round-trip/merge migrate
├── test_refresh_counts.py  # re-express queue-independence invariant
├── test_web.py         # incidental fixture strip  (NOTE: CONTEXT omitted this file)
└── test_{app_cards,stats_health,ui_foundations,activity_rail,
        header_redesign,log_viewer}.py  # incidental fixture strip
```

### Pattern 1: The thin-caller write-back (the load-bearing wiring)
**What:** Every call site is reduced to exactly three responsibilities — define `key_fn`, call `prioritize_batch`, write-back. No log logic at the call site (D-03).
**When to use:** All 6 sites.
**Example (target shape, derived from spec §6 + the verified Radarr missing site at engine.py:407-449):**
```python
# Source: design spec §6 (verified against engine.py:407-449)
batch, new_log, pass_done = prioritize_batch(
    missing, ist.get("missing_searched", []), missing_limit,
    key_fn=lambda m: str(m["id"]),          # Radarr/Lidarr
    # key_fn=lambda s: f'{s["seriesId"]}:{s["seasonNumber"]}'  # Sonarr (D-08)
)
for movie in batch:
    ...  # UNCHANGED loop body: search_movies / insert_search_entry / except
ist["missing_searched"] = [] if pass_done else new_log
if pass_done:
    ist["missing_pass"] = ist.get("missing_pass", 0) + 1
    logger.info("Radarr: Missing pass {p} complete ({n} searched)", p=ist["missing_pass"], n=len(new_log))
```

### Pattern 2: prioritize_batch internal algorithm (spec §6, must be pure)
```python
# Source: design spec §6
def prioritize_batch(eligible_items, searched_log, batch_size, key_fn):
    eligible_ids = {key_fn(it) for it in eligible_items}
    log = [i for i in searched_log if i in eligible_ids]          # 2. prune (QUEUE-10)
    logset = set(log)
    unsearched = [it for it in eligible_items if key_fn(it) not in logset]   # 3. partition
    searched   = [it for it in eligible_items if key_fn(it) in logset]
    # 4. batch: unsearched first, top up oldest-searched-first (log front = oldest)
    batch = unsearched[:batch_size]
    if len(batch) < batch_size:
        order = {key_fn(it): it for it in searched}
        for sid in log:                      # log is oldest-first
            if len(batch) >= batch_size: break
            if sid in order: batch.append(order[sid])
    # 5. MARK on attempt: re-searched moves to tail (becomes most-recent)
    new_log = [i for i in log if i not in {key_fn(it) for it in batch}]
    new_log += [key_fn(it) for it in batch]
    # 6. pass-complete: every eligible id now in the log
    pass_completed = bool(eligible_ids) and eligible_ids.issubset(set(new_log))
    return batch, new_log, pass_completed
```
*(Internal structure is Claude's discretion per CONTEXT — this is one correct shape, not a mandate; the contract is the D-01 tuple + spec §6 semantics.)*

### Anti-Patterns to Avoid
- **Branching on `app_type` inside `prioritize_batch`:** Forbidden by D-02. Identity is `key_fn`'s job; the function must stay generic.
- **Spreading log-append across call sites:** Forbidden by D-03. All lifecycle lives in the pure function; callers only write back.
- **Mutating the searched-log before a successful fetch:** Breaks the fetch-failure contract (spec §7). The cycle already returns on fetch failure at engine.py:315-323 (Radarr), before any batch work — `prioritize_batch` must only ever be reached after a successful fetch. Verified.
- **Sorting eligible items:** Forbidden by D-10. Fetch order is already stable (dedup preserves first-occurrence). Adding a sort changes cold-start batch contents and breaks QUEUE-06.
- **Tombstoning the cursor fields:** Forbidden by D-09/QUEUE-03. Remove them outright; `total=False` handles old files.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic state persistence | A new write path for the log | Existing `save_state()` (state.py:185) called at scheduler.py:377 | Already does write-temp → fsync → `os.replace` → dir-fsync; D-08 mandates the single commit point |
| Back-compat state load | A migration step for the cursor removal | `total=False` TypedDict + `_merge_defaults` (state.py:129) | Spec D-9/QUEUE-03: pre-upgrade files tolerate leftover keys; no migration code |
| Sonarr episode→season collapse | New season-keying | Existing `deduplicate_to_seasons()` (engine.py:159) unchanged | D-10: already preserves first-occurrence order; produces the exact dict keys `key_fn` needs |
| Batch-size cap | Re-capping inside `prioritize_batch` | Existing `cap_batch_sizes()` (engine.py:92) runs first (engine.py:346) | Spec §7: `prioritize_batch` receives the already-capped `batch_size`; do not re-derive |

**Key insight:** Every piece of infrastructure this phase needs already exists and is verified. The only genuinely new code is one pure function and a per-app one-line `key_fn` at each of 6 sites. The risk is not in building — it is in **behavior preservation** (see Pitfalls) and **test migration** (see classification table).

## Runtime State Inventory

> Rename/refactor phase — this section is required. The refactor changes a persisted state schema (`AppState` in `state.json`), so runtime-state analysis applies.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `state.json` per-instance dicts carry `missing_cursor`/`cutoff_cursor` (int). After upgrade these keys are leftover until the next `save_state` overwrites the dict. NEW `missing_searched`/`cutoff_searched` start absent → read as `[]`. `missing_pass`/`cutoff_pass` are KEPT and carry forward. | **No migration step** (D-09/QUEUE-03). Code edit only: read `ist.get("<q>_searched", [])`; old cursor keys are harmless and overwritten on first post-upgrade save. Verified clean via `total=False` + `_merge_defaults` (state.py:129-151). |
| Live service config | None — Triggarr owns its own `state.json`; no external service stores these cursor values. | None — verified by grep (cursor keys appear only in `triggarr/` source and `tests/`). |
| OS-registered state | None — no OS scheduler/launchd/systemd embeds the cursor. The APScheduler jobs key off `f"{app_name}_{instance_name}_search"` (scheduler.py:339), not the cursor. | None — verified. |
| Secrets/env vars | None — the searched-log holds *arr item IDs (movie/album/series IDs), NOT secrets. SecretStr discipline (API keys) is untouched. No env var references the cursor. | None — verified. |
| Build artifacts | None — pure-Python, no compiled/egg-info artifact embeds the field name. `slice_batch` is removed from source + tests in the same phase (QUEUE-07). | None — verified. |

**The canonical question — after every file is updated, what runtime systems still have the old value?** Only an on-disk `state.json` from a pre-upgrade run, holding leftover `missing_cursor`/`cutoff_cursor` integer keys. By design (D-09) these are read-harmless and overwritten on the next cycle's `save_state`. This is the **one** runtime-state item and it is explicitly handled by the no-migration contract (QUEUE-03) — needs a dedicated back-compat load test (Validation Architecture).

## Common Pitfalls

### Pitfall 1: Mark-before-loop vs. cursor crash-replay semantics
**What goes wrong:** Marking is done inside `prioritize_batch` (step 5) *before* the search loop runs (D-04). If a reviewer "fixes" this to mark after a successful search, the crash-replay semantic diverges from today's cursor.
**Why it happens:** Intuition says "mark when searched," but mark-on-attempt (QUEUE-08) deliberately marks on *attempt*. The safety comes from the commit boundary: nothing persists until `save_state` at cycle end (scheduler.py:377), so a mid-loop crash drops the whole in-memory mutation and items replay — identical to the cursor (at-least-once).
**How to avoid:** Keep marking inside `prioritize_batch`, before the loop. Test: an item whose `search_*` raises is still in the log next cycle (spec §8 mark-on-attempt test). Do not move the append.
**Warning signs:** A test asserting a failed item is re-prioritized next cycle; a `new_log` write inside the `try` block.

### Pitfall 2: Pass-complete on an empty queue
**What goes wrong:** An empty eligible list falsely "completes" a pass, bumping `*_pass` every cycle and spamming the log.
**Why it happens:** `set().issubset(anything)` is `True`. A naive subset check fires on empty eligible.
**How to avoid:** Guard `pass_completed = bool(eligible_ids) and eligible_ids.issubset(...)`. Empty eligible ⇒ `([], [], False)` (spec §7). Test: empty-eligible returns `([], [], False)` (spec §8).
**Warning signs:** `*_pass` incrementing on cycles where `searched_count == 0`.

### Pitfall 3: Sonarr composite key collapsing distinct seasons
**What goes wrong:** Using `seriesId` alone as the key marks every season of a series "searched" after one season searches — and Specials (`seasonNumber == 0`) get folded in.
**Why it happens:** Copy-paste from Radarr/Lidarr (which legitimately use `str(item["id"])`).
**How to avoid:** Sonarr `key_fn` is exactly `f'{s["seriesId"]}:{s["seasonNumber"]}'` (D-08). Specials `"1234:0"` are an ordinary distinct key (D-09). Test: Sonarr composite distinguishes S1/S2 of one series (spec §8 key_fn correctness).
**Warning signs:** A two-season series where searching S1 prevents S2 from ever being picked.

### Pitfall 4: Cold-start batch divergence (the load-bearing property)
**What goes wrong:** Any reordering/sorting/dedup change makes the empty-log batch differ from `slice_batch(items, 0, N)`, silently breaking behavior-preservation (QUEUE-06) — the one explicit safety guarantee.
**Why it happens:** `slice_batch(items, 0, N)` returns `items[0:N]`. `prioritize_batch` with empty log returns `unsearched[:N]` == `eligible_items[:N]`. These are equal **only if** eligible-item order is unchanged. The dedup runs at the same point as today (engine.py:643/699 for Sonarr; Radarr/Lidarr filter in place), so order is preserved — but a refactor that sorts or re-dedups breaks it.
**How to avoid:** Do not touch fetch/filter/dedup order (out of scope, spec §9). Dedicated cold-start equivalence property test (Validation Architecture) that asserts `prioritize_batch(items, [], N, key_fn)[0] == slice_batch(items, 0, N)[0]` for representative inputs *before* `slice_batch` is deleted, plus a post-deletion fixed-expectation variant.
**Warning signs:** First-cycle search-count or first-item assertions in migrated cycle tests changing.

### Pitfall 5: Mutating the log before a successful fetch
**What goes wrong:** A fetch failure that has already touched the searched-log leaves the queue in a half-advanced state, diverging from today (cursor untouched on fetch failure).
**Why it happens:** Calling `prioritize_batch` (which appends keys) before the fetch-failure return path.
**How to avoid:** The fetch-failure return is at engine.py:315-323 (Radarr) — *before* any batch assembly. `prioritize_batch` must only ever be reached after a successful fetch. This is structurally already true (the call sites are well below the fetch). Do not move them above the fetch. Test: fetch failure ⇒ log untouched, `connected=False` (spec §8).
**Warning signs:** `git diff` showing `prioritize_batch` called before the `try/except` fetch block.

### Pitfall 6: test_web.py omitted from the CONTEXT classification
**What goes wrong:** CONTEXT D-05 lists the incidental fixture files but **omits `tests/test_web.py`**, which has 9 `missing_cursor` + 8 `cutoff_cursor` refs. If the planner trusts the CONTEXT list verbatim, these are missed and the suite breaks (or the fixtures retain dead keys).
**Why it happens:** CONTEXT's file list was illustrative, not exhaustive.
**How to avoid:** Use the verified per-file table below (grep-confirmed 2026-06-04), not the CONTEXT prose list. `test_web.py` is **incidental** (fixture cursors at lines 46-69, 1070-1077; one behavioral-looking assert at 1850 `missing_cursor == 0` and a comment-doc at 385-387) — strip the fixture keys; line 1850's assertion targets a default-state path and migrates to "no searched-log present / empty."
**Warning signs:** Post-refactor `pytest tests/test_web.py` failing on `KeyError: 'missing_cursor'` or stale fixture keys.

## Code Examples

### Verified current Radarr missing dispatch (the migration source)
```python
# Source: triggarr/search/engine.py:406-449 (verified live 2026-06-04)
ist["missing_eligible"] = len(missing)
cursor = ist["missing_cursor"]
batch, new_cursor = slice_batch(missing, cursor, missing_limit)
for movie in batch:
    try:
        await client.search_movies([movie["id"]])
        await insert_search_entry(db, "Radarr", "missing", movie["title"], outcome="searched", ...)
        searched_count += 1
    except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
        logger.warning("Radarr: Failed to search {title}: {exc}", ...)
        await insert_search_entry(db, "Radarr", "missing", ..., outcome="failed", ...)
        skipped_count += 1
ist["missing_cursor"] = new_cursor
if new_cursor == 0 and batch:                       # ← wrap detection, replaced by pass_done
    ist["missing_pass"] = ist.get("missing_pass", 0) + 1
    logger.info("Radarr: Missing queue wrapped around — starting pass {p}", p=ist["missing_pass"])
```

### Verified current refresh-counts queue-independence (the invariant to preserve)
```python
# Source: triggarr/search/engine.py:1023-1028 docstring (verified live)
# "...Does NOT call slice_batch, does NOT write missing_cursor/cutoff_cursor,
#  does NOT write last_run/last_success."
# After this phase the equivalent guarantee is: does NOT read/write missing_searched/cutoff_searched.
# tests/test_refresh_counts.py:130-148 / 244-262 / 303-321 currently set cursor=N, refresh, assert ==N.
# Migrate to: set <q>_searched=[known list], refresh, assert <q>_searched unchanged.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Integer positional cursor (`slice_batch`) | Identity-based ordered searched-log (`prioritize_batch`) | This phase (v2.11) | Items keyed by stable *arr ID, immune to list reorder/length churn; never-searched prioritized |
| Wrap-around detection (`new_cursor == 0 and batch`) | Pass-complete detection (`eligible_ids ⊆ log`) | This phase | `*_pass` semantics preserved (bump on full-coverage instead of cursor-wrap) |

**Deprecated/outdated:**
- `slice_batch` (engine.py:133) + its 5 unit tests (test_search.py:69-109): removed once all 6 callers migrate (QUEUE-07/D-10). No dead code, no tombstone.
- `missing_cursor`/`cutoff_cursor` (AppState, `_default_instance_state`): removed outright (QUEUE-03/D-09).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `test_web.py:1850` (`missing_cursor == 0`) targets a default-state path and migrates to an empty/absent-searched-log assertion (incidental, not a behavioral dispatch assertion) | Pitfall 6 / Test classification | LOW — if it is actually behavioral, it migrates to a searched-log-contents assertion instead of a strip; planner verifies by reading the surrounding test at edit time. Either disposition keeps the suite green. |

**Note:** Every other claim in this document is `[VERIFIED]` against live code (file:line quoted) or `[CITED]` from the design spec / CONTEXT / REQUIREMENTS. The single assumption above is bounded and low-risk.

## Open Questions

None blocking. The design spec + CONTEXT resolve all WHAT/WHY/HOW; this research confirmed every codebase anchor. The only judgment call (A1, `test_web.py:1850` disposition) is resolved at edit time by reading the surrounding test and does not affect the plan's shape.

## Test Surface Classification (grep-verified 2026-06-04)

> Fulfills D-07. Counts are exact greps of `tests/` for `missing_cursor` / `cutoff_cursor` / `slice_batch`. **This supersedes the CONTEXT D-05 prose list, which omitted `test_web.py`.**

| File | missing_cursor | cutoff_cursor | slice_batch | Role | Action |
|------|---------------:|--------------:|------------:|------|--------|
| `tests/test_search.py` | 25 | 6 | 16 | **Behavioral** (cursor-advancement + 5 `slice_batch` unit tests) | Migrate cursor-value asserts → searched-log/`*_pass`; **delete** the 5 `slice_batch` unit tests (test fns at lines 69, 76, 83, 90, 105) with `slice_batch`; add new `prioritize_batch` unit-test suite |
| `tests/test_state.py` | 47 | 41 | 0 | **Behavioral** (round-trip persistence + default-state + merge) | Round-trip tests (l.29-46,188-200) → assert `missing_searched`/`cutoff_searched` round-trip; default-state tests (l.132-178) → `_default_instance_state()` returns empty logs, no cursor; v2.2 migration tests (l.53-128) keep v2.2 fixture shape but update merged-output asserts; add back-compat-load test (pre-upgrade file with cursor keys, no logs) |
| `tests/test_refresh_counts.py` | 14 | 14 | 0 | **Invariant** (queue-independence, CNT-02) | Re-express (D-06): the 3 "cursor unchanged" tests (l.130-148 Radarr, 244-262 Sonarr, 303-321 Lidarr) → set `<q>_searched=[…]`, refresh, assert log unchanged; fixture cursor keys (l.754-781) → swap to searched-log fields or strip |
| `tests/test_web.py` | 9 | 8 | 0 | **Incidental** (route fixtures) — *CONTEXT omitted this file* | Strip fixture cursor keys (l.46-69, 1070-1077); l.1850 `== 0` → empty/absent-log assertion (see A1); doc-comment l.385-387 update |
| `tests/test_activity_rail.py` | 5 | 5 | 0 | Incidental | Strip fixture cursor keys |
| `tests/test_app_cards.py` | 3 | 3 | 0 | Incidental (+ 5 `*_pass` refs — KEEP, pass semantics preserved) | Strip cursor keys; leave `*_pass` |
| `tests/test_stats_health.py` | 3 | 3 | 0 | Incidental | Strip fixture cursor keys |
| `tests/test_ui_foundations.py` | 3 | 3 | 0 | Incidental | Strip fixture cursor keys |
| `tests/test_log_viewer.py` | 3 | 3 | 0 | Incidental | Strip fixture cursor keys |
| `tests/test_header_redesign.py` | 2 | 2 | 0 | Incidental | Strip fixture cursor keys |

**Totals:** 10 test files touched. Behavioral migration concentrated in `test_search.py` + `test_state.py` (the real coverage to preserve). Invariant re-expression in `test_refresh_counts.py` (3 tests). Incidental strips in 7 UI/route files. `*_pass` references (test_app_cards.py ×5, test_refresh_counts.py ×4) are **kept** — pass-counter semantics are preserved.

## Validation Architecture

> Nyquist Dimension 8 enabled (`workflow.nyquist_validation` absent from config.json → treated as enabled). This section keys VALIDATION.md.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3+ with pytest-asyncio (auto mode) [VERIFIED: pyproject.toml] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`) |
| Quick run command | `uv run pytest tests/test_search.py tests/test_state.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |
| Lint gate | `uv run ruff check triggarr/ tests/` (E,F,I,UP,B,SIM; line-length 120) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QUEUE-01 | Searched-log persists per queue, oldest-first | unit + round-trip | `uv run pytest tests/test_state.py -k searched -x` | ❌ Wave 0 |
| QUEUE-02 | Per-app key normalization; Sonarr composite distinguishes seasons | unit | `uv run pytest tests/test_search.py -k "prioritize and key" -x` | ❌ Wave 0 |
| QUEUE-03 | Cursor fields removed; pre-upgrade file loads clean as everything-unsearched | unit (back-compat) | `uv run pytest tests/test_state.py -k "back_compat or legacy_cursor" -x` | ❌ Wave 0 |
| QUEUE-04 | Never-searched-first in fetch order | unit | `uv run pytest tests/test_search.py -k "prioritize and unsearched_first" -x` | ❌ Wave 0 |
| QUEUE-05 | Top-up oldest-searched-first | unit | `uv run pytest tests/test_search.py -k "prioritize and topup" -x` | ❌ Wave 0 |
| QUEUE-06 | **Cold-start equivalence** (empty log == old slice_batch first cycle) | property/unit | `uv run pytest tests/test_search.py -k cold_start_equivalence -x` | ❌ Wave 0 (LOAD-BEARING) |
| QUEUE-07 | All 6 sites use prioritize_batch; slice_batch gone | integration + static | `uv run pytest tests/test_search.py -k cycle -x` then `! grep -rq "slice_batch" triggarr/ tests/` | ❌ Wave 0 |
| QUEUE-08 | Mark-on-attempt; failed search still logged | integration | `uv run pytest tests/test_search.py -k "mark_on_attempt" -x` | ❌ Wave 0 |
| QUEUE-09 | Pass-complete clears log + bumps `*_pass` | unit + integration | `uv run pytest tests/test_search.py -k "pass_complete" -x` | ❌ Wave 0 |
| QUEUE-10 | Prune-to-eligible drops departed items, preserves order | unit | `uv run pytest tests/test_search.py -k "prioritize and prune" -x` | ❌ Wave 0 |
| QUEUE-11 | Commit only at cycle-end (single save_state) | integration | `uv run pytest tests/test_search.py -k "commit_at_cycle_end" -x` | partial (cycle tests exist; assertion migrates) |
| (invariant) | refresh-counts never reads/writes searched-log | invariant | `uv run pytest tests/test_refresh_counts.py -x` | ⚠️ exists (re-express, D-06) |
| (regression) | Existing cycle search-counts + history rows stay green | regression | `uv run pytest tests/test_search.py -x` | ✅ exists (migrate cursor asserts only) |

### Validation Strategy by Surface

1. **Pure `prioritize_batch` unit matrix (spec §8 — exhaustive):** cold-start; unsearched-first; top-up oldest-first; pass-completion (last unsearched ⇒ `pass_completed=True`, full log); mid-pass no-completion; prune (departed IDs dropped, survivor order kept); re-search recency (re-batched item → log tail); empty eligible ⇒ `([], [], False)`; eligible < N ⇒ all searched + pass completes; `key_fn` correctness (Sonarr S1/S2 distinct, Radarr/Lidarr int→str). Fully synchronous, no I/O, no mocks — fastest feedback loop.

2. **Cold-start behavior-equivalence (the load-bearing property, QUEUE-06):** dedicated test asserting `prioritize_batch(items, [], N, key_fn)[0] == slice_batch(items, 0, N)[0]` across representative inputs **while `slice_batch` still exists** (oracle comparison), plus a post-removal fixed-expectation variant so the guarantee survives `slice_batch`'s deletion. This is the explicit success criterion (CONTEXT specifics, ROADMAP criteria).

3. **Per-app cycle integration (extend existing `run_*_cycle` tests):** two-cycle no-re-search-within-a-pass; new-item-jumps-the-line; mark-on-attempt (a `search_*`-raising item still in log next cycle); pass-reset bumps `*_pass` + clears log; fetch-failure ⇒ log untouched + `connected=False`; commit-at-cycle-end (state saved once, log + `*_pass` consistent). Run for all three apps (Radarr/Sonarr/Lidarr) since all 6 sites are wired.

4. **Back-compat state load (QUEUE-03):** load a pre-upgrade `state.json` with `missing_cursor`/`cutoff_cursor` and no searched-logs → loads clean via `_merge_defaults`, dispatch treats everything unsearched, leftover keys ignored + overwritten on next save. New test in `test_state.py`.

5. **Count-only queue-independence invariant (D-06):** re-express the 3 `test_refresh_counts.py` "cursor unchanged" tests as "searched-log unchanged after refresh-counts" for Radarr/Sonarr/Lidarr. Proves the v2.10 invariant holds under the new state model.

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_search.py tests/test_state.py -x -q` (the two behavioral hot files) + `uv run ruff check triggarr/ tests/`
- **Per wave merge:** `uv run pytest tests/ -x -q` (full suite — 924 test functions baseline; must stay green)
- **Phase gate:** Full suite green + `ruff check` clean + static check `! grep -rq "slice_batch" triggarr/ tests/` and `! grep -rq "_cursor" triggarr/state.py triggarr/search/engine.py` before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] New `prioritize_batch` unit-test suite in `tests/test_search.py` (10-case matrix per spec §8) — covers QUEUE-02/04/05/09/10 + key_fn
- [ ] Cold-start-equivalence test (oracle vs `slice_batch`, then fixed-expectation) — covers QUEUE-06
- [ ] Back-compat state-load test in `tests/test_state.py` — covers QUEUE-03
- [ ] Searched-log round-trip + default-state tests in `tests/test_state.py` — covers QUEUE-01
- [ ] Re-expressed queue-independence tests in `tests/test_refresh_counts.py` (×3 apps) — covers the invariant (D-06)
- [ ] Per-app cycle-integration extensions (mark-on-attempt, pass-reset, new-item-jumps-line, commit-at-cycle-end) — covers QUEUE-07/08/09/11
- [ ] Static guard: no `slice_batch` / no `*_cursor` survivors (CI-style grep assertion or verify-work check)

*Framework install: none needed — pytest-asyncio auto mode already configured. No new test dependencies (spec §8).*

## Project Constraints (from CLAUDE.md)

From `triggarr/CLAUDE.md` and `~/.claude/CLAUDE.md` — the planner must ensure tasks comply:
- **Logging:** loguru only (never `print`/stdlib logging), via the redacting sink. The pass-complete INFO line (D-11) uses `logger.info(...)`. [VERIFIED: triggarr/CLAUDE.md, state.py:19]
- **No secrets in logs:** the searched-log holds *arr item IDs only — no PII/keys; safe to log counts but D-11 says do NOT dump the log per cycle anyway.
- **Atomic writes:** the searched-log commits via the existing atomic `save_state()` (write-then-rename) — no new write path. [VERIFIED: state.py:185]
- **Ruff E,F,I,UP,B,SIM, line-length 120, py311:** new code must pass `ruff check`. `UP`/`SIM` may flag the algorithm — prefer clean comprehensions. [VERIFIED: pyproject.toml:42-46]
- **pytest-asyncio asyncio_mode=auto:** async cycle tests need no `@pytest.mark.asyncio`. [VERIFIED: pyproject.toml]
- **Type hints on public signatures, avoid `Any`:** `prioritize_batch` signature should be typed (`list`, `list[str]`, `int`, `Callable[[dict], str]` → `tuple[list, list[str], bool]`). [CITED: ~/.claude/CLAUDE.md Python-Specific]
- **No bare `except:`; specific exceptions:** the per-item loop already catches `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)` — unchanged. [VERIFIED: engine.py:431]
- **No mutable default arguments:** `prioritize_batch` takes `searched_log` explicitly (callers pass `ist.get("<q>_searched", [])`); do not default it to `[]`. [CITED: ~/.claude/CLAUDE.md]
- **Project deep-review gate:** before push/tag, offer `/deep-review` (security/correctness/resilience/docker/config). [VERIFIED: triggarr/CLAUDE.md]

## Environment Availability

Skipped — no external dependencies. This is a pure code/config/test change within the existing Python package; no new tools, services, runtimes, or registries are involved. (`uv` + the already-installed dev deps are the only tooling, already present per the standard dev setup.)

## Security Domain

`security_enforcement` not explicitly disabled, so noted — but this phase introduces **no new attack surface**: no new endpoints, no new network calls, no new user input, no new secrets. The searched-log stores internal *arr item IDs already present in fetched data.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | no | No new external/user input; eligible items come from already-fetched, already-validated *arr API responses |
| V6 Cryptography | no | No crypto involved; SecretStr discipline (API keys) untouched |
| V7 Error Handling & Logging | yes | loguru redacting sink unchanged; D-11 forbids dumping the log; failed searches log WARNING + `failed` history row as today |
| V9 Data Protection | no | Searched-log = item IDs, not PII/secrets; persisted via existing atomic write to the existing `state.json` |

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Log injection via item titles | Tampering | Unchanged — titles already logged today via loguru structured fields; the searched-log stores IDs, not titles |
| State-file corruption mid-write | Tampering/DoS | Existing atomic write-temp→fsync→`os.replace` (state.py:185), unchanged |
| Unbounded log growth (resource exhaustion) | DoS | Prune-to-eligible each cycle (QUEUE-10) bounds size at eligible-count; reset-on-pass returns to empty (spec §5 Bound) |

## Sources

### Primary (HIGH confidence — verified against live code/config 2026-06-04)
- `triggarr/search/engine.py` — `slice_batch` (l.133), 6 call sites (l.408/457/647/702/898/948), `cap_batch_sizes` (l.92), `deduplicate_to_seasons` (l.159), `refresh_*_counts` (l.1014/1149/1289), fetch-failure return (l.315-323)
- `triggarr/state.py` — `AppState` TypedDict (l.43), `_default_instance_state` (l.77), `_merge_defaults` (l.129), `save_state` (l.185)
- `triggarr/search/scheduler.py` — cycle dispatch + single `save_state` commit point (l.333-379)
- `pyproject.toml` — pytest-asyncio auto mode, ruff config (E,F,I,UP,B,SIM, line-length 120, py311)
- `tests/` — grep-verified per-file cursor/slice_batch counts (classification table)
- `docs/superpowers/specs/2026-06-04-search-queue-priority-design.md` — design spec (§3 decisions, §5 data model, §6 algorithm, §7 edge cases, §8 tests, §9 YAGNI, §10 files)
- `.planning/phases/76-.../76-CONTEXT.md` — D-01..D-12 implementation decisions
- `.planning/REQUIREMENTS.md` — QUEUE-01..11
- `triggarr/CLAUDE.md`, `~/.claude/CLAUDE.md` — project + global constraints

### Secondary (MEDIUM)
- `.planning/STATE.md`, `.planning/ROADMAP.md` — milestone shape, phasing rationale, success criteria
- `.planning/codebase/TESTING.md` — test conventions

### Tertiary (LOW)
None — no external/web sources needed for an internal refactor with all decisions pre-locked.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; existing stack verified in pyproject.toml
- Architecture/anchors: HIGH — every file:line confirmed against live code (6 call sites, save_state commit point, refresh-counts independence all verified)
- Test classification: HIGH — grep-verified per-file counts; one bounded LOW-risk assumption (A1, test_web.py:1850 disposition)
- Pitfalls: HIGH — derived from spec §7 + direct code reading (mark-before-loop, empty-pass, Sonarr key, cold-start, fetch-order)

**Research date:** 2026-06-04
**Valid until:** 2026-07-04 (stable — internal refactor of code that does not change underneath this research; re-confirm line numbers if engine.py/state.py are edited before planning)
