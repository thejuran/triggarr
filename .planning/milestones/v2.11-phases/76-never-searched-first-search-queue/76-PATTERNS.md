# Phase 76: Never-Searched-First Search Queue - Pattern Map

**Mapped:** 2026-06-04
**Files analyzed:** 13 (2 source + 11 test files; 4 test files carry behavioral/invariant migration, 7 are incidental fixture strips)
**Analogs found:** 13 / 13 (every new/modified file has an exact in-repo analog — this is a like-for-like swap, not a greenfield surface)

> **Best analog for the central new function is the function it replaces.** `prioritize_batch` mirrors `slice_batch`'s shape (pure, generic, opaque inputs, tuple return, no I/O, no app branching) and its test style. The per-app `key_fn` mirrors the per-app identity already used at the six search call sites. Everything else is a field-swap on an existing TypedDict + a thin-caller rewire.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/search/engine.py` — ADD `prioritize_batch()` | utility (pure fn) | transform / batch | `slice_batch()` @ engine.py:133 (same module) | exact (the function it replaces) |
| `triggarr/search/engine.py` — REWIRE 6 call sites (408/457/647/702/898/948) | service (cycle orchestrator) | request-response (per-item search) | the existing `slice_batch` call + loop + wrap-detect at each site | exact (in-place edit of the analog) |
| `triggarr/search/engine.py` — REMOVE `slice_batch()` | utility | transform | n/a (deletion) | n/a |
| `triggarr/state.py` — `AppState` field swap + `_default_instance_state()` | model (TypedDict) / config | CRUD (state persistence) | existing `missing_cursor`/`cutoff_cursor` fields + `_default_instance_state()` @ state.py:43/77 | exact |
| `tests/test_search.py` — NEW `prioritize_batch` unit matrix | test | transform | existing `slice_batch` unit tests @ test_search.py:69-109 | exact (same shape) |
| `tests/test_search.py` — cold-start equivalence | test | transform (oracle) | `slice_batch` tests + `prioritize_batch` matrix | role-match |
| `tests/test_search.py` — migrate cycle cursor asserts | test | request-response (async cycle) | `test_run_radarr_cycle_cursor_advancement` @ :337, `_network_failure` @ :274 | exact |
| `tests/test_state.py` — round-trip / default-state / back-compat | test | CRUD | `test_nested_state_round_trip` @ :24, `test_default_state_with_settings` @ :141, `test_merge_defaults_nested` @ :156 | exact |
| `tests/test_refresh_counts.py` — re-express queue-independence | test (invariant) | CRUD invariant | `test_refresh_radarr_counts_does_not_advance_cursor` @ :129 | exact |
| `tests/test_web.py` *(NOT in CONTEXT — see RESEARCH Pitfall 6)* | test | incidental fixture | fixture cursor keys @ :46-69, :1070-1077; assert @ :1850 | incidental |
| `tests/test_app_cards.py` | test | incidental fixture | `AppState(missing_cursor=…)` fixtures | incidental |
| `tests/test_stats_health.py` | test | incidental fixture | same | incidental |
| `tests/test_ui_foundations.py` | test | incidental fixture | same | incidental |
| `tests/test_activity_rail.py` | test | incidental fixture | same | incidental |
| `tests/test_header_redesign.py` | test | incidental fixture | same | incidental |
| `tests/test_log_viewer.py` | test | incidental fixture | same | incidental |

**Full per-file ref counts (behavioral vs incidental) are already grep-verified in RESEARCH.md "Test Surface Classification" — do not re-grep; trust that table (it supersedes the CONTEXT D-05 prose list, which omitted `test_web.py`).**

---

## Pattern Assignments

### `triggarr/search/engine.py` :: NEW `prioritize_batch()` (utility, transform — purity analog = `slice_batch`)

**Analog:** `slice_batch()` @ `triggarr/search/engine.py:133-156`. Copy its *contract style* — pure, generic over opaque list items, returns a tuple, no I/O, no `app_type` branch, full docstring with Args/Returns.

**Analog signature/docstring shape to mirror** (engine.py:133-156):
```python
def slice_batch(items: list, cursor: int, batch_size: int) -> tuple[list, int]:
    """Slice a batch starting at cursor position with wrap-around.

    If cursor is past the end of the list, wraps to 0.
    Callers are responsible for logging wrap-around events.

    Args:
        items: Full list of items to batch from.
        cursor: Current position in the list.
        batch_size: Maximum number of items to return.

    Returns:
        Tuple of (batch, new_cursor). New cursor wraps to 0 ...
    """
    if not items:
        return [], 0
    ...
    return batch, new_cursor
```

**Target signature (D-01, typed per ~/.claude Python rules — `Callable`, no `Any`, NO mutable default on `searched_log`):**
```python
def prioritize_batch(
    eligible_items: list,
    searched_log: list[str],
    batch_size: int,
    key_fn: Callable[[dict], str],
) -> tuple[list, list[str], bool]:
    """Assemble a batch: never-searched first (fetch order), then top up
    already-searched oldest-first. Returns (batch, new_searched_log, pass_completed)."""
```
- `Callable` is already imported at `engine.py:13` (`from collections.abc import Awaitable, Callable`) — and `filter_by_tag` @ engine.py:59 already takes a `Callable[[dict], list[int]]` param, so the `key_fn` parameter style is an established in-module precedent. **Mirror `filter_by_tag`'s parameter convention exactly.**
- Empty-input early return matches `slice_batch`'s `if not items: return [], 0` → here `if not eligible_items: return [], [], False` (covers the empty-eligible edge case). The pass-completion guard is `bool(batch) and eligible_ids.issubset(set(new_log))` (MED-1) — keyed on a non-empty BATCH, not on `bool(eligible_ids)`, so a zero-search batch (batch_size<=0 or a zero-cap queue whose pruned log already covers the eligible set) never completes a pass.

**Core algorithm (RESEARCH §"Pattern 2", verbatim from spec §6 — internal structure is Claude's discretion, the tuple contract + semantics are not):**
```python
eligible_ids = {key_fn(it) for it in eligible_items}
log = [i for i in searched_log if i in eligible_ids]           # 2. prune (QUEUE-10)
logset = set(log)
unsearched = [it for it in eligible_items if key_fn(it) not in logset]   # 3. partition
searched   = [it for it in eligible_items if key_fn(it) in logset]
batch = unsearched[:batch_size]                                 # 4. unsearched first
if len(batch) < batch_size:
    order = {key_fn(it): it for it in searched}
    for sid in log:                                             #    top up oldest-first
        if len(batch) >= batch_size: break
        if sid in order: batch.append(order[sid])
batched_keys = {key_fn(it) for it in batch}                    # 5. MARK on attempt
new_log = [i for i in log if i not in batched_keys] + [key_fn(it) for it in batch]
pass_completed = bool(batch) and eligible_ids.issubset(set(new_log))  # 6. MED-1: bool(batch), NOT bool(eligible_ids) — a zero-search batch (batch_size<=0 / zero-cap after prune) must NOT complete a pass
return batch, new_log, pass_completed
```

**Ruff note (RESEARCH constraints):** `UP`/`SIM` may flag the loop — prefer comprehensions where clean, keep line length ≤ 120, target py311. No `Any`.

---

### `triggarr/search/engine.py` :: REWIRE 6 call sites (service, request-response)

**Analog = the code being replaced at each site.** All six are structurally identical: read cursor → `slice_batch` → loop → write cursor → wrap-detect. Replace the cursor mechanics with the thin-caller pattern (D-03); **leave the `for … in batch:` loop body byte-for-byte unchanged.**

**Verified Radarr-missing analog (engine.py:406-449) — the migration template:**
```python
ist["missing_eligible"] = len(missing)
cursor = ist["missing_cursor"]                                 # ← DELETE
batch, new_cursor = slice_batch(missing, cursor, missing_limit)  # ← REPLACE
for movie in batch:
    try:
        await client.search_movies([movie["id"]])              # ← UNCHANGED loop body
        await insert_search_entry(db, "Radarr", "missing", movie["title"], ...)
        searched_count += 1
    except PendingCapExceeded as cap_exc: ...
    except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc: ...
ist["missing_cursor"] = new_cursor                             # ← REPLACE
if new_cursor == 0 and batch:                                  # ← REPLACE wrap-detect
    ist["missing_pass"] = ist.get("missing_pass", 0) + 1
    logger.info("Radarr: Missing queue wrapped around — starting pass {p}", p=...)
```

**Target shape (RESEARCH §"Pattern 1", thin caller — D-03/D-11):**
```python
ist["missing_eligible"] = len(missing)
batch, new_log, pass_done = prioritize_batch(
    missing, ist.get("missing_searched", []), missing_limit,
    key_fn=lambda m: str(m["id"]),
)
for movie in batch:
    ...  # UNCHANGED loop body (search_movies / insert_search_entry / except blocks)
ist["missing_searched"] = [] if pass_done else new_log
if pass_done:
    ist["missing_pass"] = ist.get("missing_pass", 0) + 1
    logger.info(
        "Radarr: Missing pass {p} complete ({n} searched)",
        p=ist["missing_pass"], n=len(new_log),
    )
```

**Per-app `key_fn` (co-located, the ONLY per-app difference — D-02/D-08; identity already used at each loop body):**

| Site | Line | Loop var | Identity used in body today | `key_fn` |
|------|------|----------|-----------------------------|----------|
| Radarr missing | engine.py:408 | `movie` | `movie["id"]` (:411) | `lambda m: str(m["id"])` |
| Radarr cutoff | engine.py:457 | `movie` | `movie["id"]` (:460) | `lambda m: str(m["id"])` |
| Sonarr missing | engine.py:647 | `season` | `season["seriesId"]`, `season["seasonNumber"]` (:650) | `lambda s: f'{s["seriesId"]}:{s["seasonNumber"]}'` |
| Sonarr cutoff | engine.py:702 | `season` | `season["seriesId"]`, `season["seasonNumber"]` (:705) | `lambda s: f'{s["seriesId"]}:{s["seasonNumber"]}'` |
| Lidarr missing | engine.py:898 | `album` | `album["id"]` (:902) | `lambda a: str(a["id"])` |
| Lidarr cutoff | engine.py:948 | `album` | `album["id"]` (:952) | `lambda a: str(a["id"])` |

- Sonarr passes `deduplicate_to_seasons()` output (engine.py:643/699) — unchanged (D-10); season dicts already carry `seriesId`/`seasonNumber` in stable fetch order. **Do NOT add any sort** (RESEARCH Pitfall 4 — breaks cold-start equivalence QUEUE-06).
- **Placement constraint (RESEARCH Pitfall 5):** `prioritize_batch` must stay *below* the fetch-failure return at engine.py:315-323 — it already is at all 6 sites; do not hoist it. Log only mutated after successful fetch.
- **Write-back substitution:** every `ist["<q>_cursor"]` read/write and every `if new_cursor == 0 and batch:` wrap-detect block is replaced; do NOT leave a tombstoned cursor field (D-09/QUEUE-03).
- **Pass-complete INFO line (D-11):** one line on `pass_done`, naming app/queue/pass-number/items-searched. Reuse the existing `logger.info` field-binding style (loguru, never f-string into the message — see engine.py:419/449). Exact wording is Claude's discretion.

---

### `triggarr/state.py` :: `AppState` field swap + `_default_instance_state()` (model / config, CRUD)

**Analog:** the existing cursor fields and their default init, same file.

**Current (state.py:43-49):**
```python
class AppState(TypedDict, total=False):
    """Per-instance cursor and timing state."""
    missing_cursor: int          # ← REMOVE
    cutoff_cursor: int           # ← REMOVE
    missing_pass: int            # KEEP (now bumped on log-reset, not cursor-wrap)
    cutoff_pass: int             # KEEP
    ...
```
**Target (spec §5):** drop the two `*_cursor` fields; add (mirror the existing field-comment style, `list[dict]` precedent already exists at state.py:61 `tag_warnings`):
```python
    missing_searched: list[str]   # NEW — ordered searched-log (oldest first), missing queue
    cutoff_searched: list[str]    # NEW — ordered searched-log (oldest first), cutoff queue
```

**Current (state.py:77-79):**
```python
def _default_instance_state() -> AppState:
    """Return a fresh AppState for a single instance at cursor 0."""
    return AppState(missing_cursor=0, cutoff_cursor=0, last_run=None, last_success=None)
```
**Target:** return empty searched-logs, no cursors:
```python
def _default_instance_state() -> AppState:
    """Return a fresh AppState for a single instance with empty searched-logs."""
    return AppState(missing_searched=[], cutoff_searched=[], last_run=None, last_success=None)
```

**Minimal write/load path (RESEARCH "Don't Hand-Roll") — CORRECTED per codex round-1 HIGH-1:**
- `_merge_defaults` @ state.py:129-151 already two-level-deep merges each instance against `_default_instance_state()` — new `*_searched` fields flow through automatically. **CORRECTION (this supersedes the original round-1 assumption below):** leftover `*_cursor` keys are NOT harmless / NOT auto-overwritten — `{**_default_instance_state(), **instance_data}` (state.py:143) PRESERVES unknown keys, and `save_state` (`json.dump`) writes them back, so they persist indefinitely. **Plan 02 therefore adds an explicit one-line strip in `_merge_defaults`** right after the merge: `for legacy_key in ("missing_cursor", "cutoff_cursor"): merged.pop(legacy_key, None)` (idempotent; no version bump / no separate migrate function — still within spec §9 YAGNI and D-09's "no migration STEP"). A load→save round-trip test (test_state.py) asserts the keys are ABSENT from the written JSON (QUEUE-03). `load_state` / `save_state` themselves are unchanged.
- `save_state` @ state.py:185 is the single atomic write-then-rename commit point, called once from `scheduler.py:377-379` after the cycle returns (QUEUE-11). No change.
- **Leave the v2.2 migration (`_is_v22_state_format` :98 / `_migrate_v22_state` :113) untouched** — those keep their v2.2 fixture shape; only the *merged-output* assertions in their tests change (RESEARCH test table, test_state.py l.53-128).
- Update the module docstring's "round-robin cursor positions" wording (state.py:3-9, :44) if convenient — cosmetic, not load-bearing.

---

### `tests/test_search.py` :: NEW `prioritize_batch` unit matrix (test, transform)

**Analog:** the `slice_batch` unit tests @ test_search.py:69-109 — synchronous, fake int/dict items, direct tuple-unpack assert, one behavior per test. **Delete those 5 `slice_batch` tests** (fns @ :69/76/83/90/105) and the `slice_batch` import (:38) when `slice_batch` is removed (QUEUE-07).

**Analog test shape to mirror (test_search.py:69-87):**
```python
def test_slice_batch_normal():
    items = list(range(10))
    batch, new_cursor = slice_batch(items, cursor=3, batch_size=2)
    assert batch == [3, 4]
    assert new_cursor == 5

def test_slice_batch_empty_list():
    batch, new_cursor = slice_batch([], cursor=0, batch_size=5)
    assert batch == []
    assert new_cursor == 0
```

**New matrix (spec §8 / RESEARCH Validation Strategy #1 — same fake-item + tuple-unpack style, fake `key_fn=lambda it: str(it["id"])`):** cold-start; unsearched-first; top-up oldest-first; pass-completion (`pass_completed=True`, full log); mid-pass (`pass_completed=False`); prune (departed IDs dropped, survivor order kept); re-search recency (re-batched item → log tail); empty eligible → `([], [], False)`; eligible < N → all searched + pass completes; `key_fn` correctness (Sonarr `"1:1"`/`"1:2"` distinct via `lambda s: f'{s["seriesId"]}:{s["seasonNumber"]}'`; Radarr int→str). Test naming is Claude's discretion (follow `test_<fn>_<behavior>` convention).

**Cold-start equivalence (QUEUE-06, LOAD-BEARING — RESEARCH Pitfall 4 / Validation #2):** dedicated test asserting `prioritize_batch(items, [], N, key_fn)[0] == slice_batch(items, 0, N)[0]` *while `slice_batch` still exists* (oracle), PLUS a post-deletion fixed-expectation variant so the guarantee survives `slice_batch`'s removal. Author the oracle test before deleting `slice_batch`.

---

### `tests/test_search.py` :: migrate cycle cursor assertions (test, request-response async)

**Analogs (exact):**
- `test_run_radarr_cycle_cursor_advancement` @ :337 — multi-run cursor walk. **Migrate** `assert result["radarr"]["Default"]["missing_cursor"] == 2/4/0` → assert `missing_searched` contents (e.g. `["1","2"]` after run 1, growing across runs) and `*_pass`/log-clear on the cycle that completes the pass.
- `test_run_radarr_cycle_network_failure` @ :274 — fetch-failure abort. **Migrate** `state[...]["missing_cursor"] = 5` / `assert … == 5` → seed `missing_searched=["1","2"]`, assert it is **unchanged** after abort (+ existing `connected is False`, `unreachable_since is not None` assertions stay — RESEARCH Pitfall 5). Mirror the seed-then-assert-unchanged shape.
- Sonarr equivalents @ :432/:494 — same migration. Run for all three apps.

**New cycle-integration extensions (RESEARCH Validation #3):** two-cycle no-re-search-within-pass; new-item-jumps-line; mark-on-attempt (a `search_*`-raising item still in `*_searched` next cycle — extend the per-item-skip analog `test_run_radarr_cycle_per_item_skip` @ :298, which already drives `search_movies = AsyncMock(side_effect=[ConnectError, None])`); pass-reset clears log + bumps `*_pass`. Use the existing fixtures `_make_test_state()` @ :230, `_cycle_settings()` @ :211, `_cycle_instance_config()` @ :219 unchanged.

---

### `tests/test_state.py` :: round-trip / default-state / back-compat (test, CRUD)

**Analogs (exact, same file):**
- `test_nested_state_round_trip` @ :24 + `test_state_round_trip` @ :184 — save→load preserves cursor values. **Migrate** every `AppState(missing_cursor=42, cutoff_cursor=7, …)` fixture + `assert loaded[...]["missing_cursor"] == 42` → `missing_searched=["1","2"]` round-trip asserts. Same `tmp_path / "state.json"` + `save_state`/`load_state` shape:
  ```python
  state = TriggarrState(radarr={"Default": AppState(missing_searched=["1","2"], cutoff_searched=["9"], last_run="…")}, …)
  save_state(state, state_file); loaded = load_state(state_file)
  assert loaded["radarr"]["Default"]["missing_searched"] == ["1", "2"]
  ```
- `test_default_state_with_settings` @ :141 — **migrate** `assert state["radarr"]["Default"]["missing_cursor"] == 0` → `assert state["radarr"]["Default"]["missing_searched"] == []`.
- `test_merge_defaults_nested` @ :156 — **migrate** partial-fill asserts to searched-log defaults (`cutoff_searched == []`).
- v2.2 migration tests @ :49/:68 (`test_v22_state_migration`, `test_is_v22_state_format_detection`) — **keep the v2.2 fixture shape** (still uses `missing_cursor` — that's a real on-disk v2.2 file), update only the *merged-output* asserts.

**NEW back-compat-load test (QUEUE-03, RESEARCH Validation #4)** — model on `test_merge_defaults_nested` @ :156 (writes raw JSON via `state_file.write_text(json.dumps(...))`, then `load_state`):
```python
pre_upgrade = {"radarr": {"Default": {"missing_cursor": 7, "cutoff_cursor": 3, "missing_pass": 2}}}
state_file.write_text(json.dumps(pre_upgrade))
loaded = load_state(state_file)
assert loaded["radarr"]["Default"]["missing_searched"] == []   # treated as everything-unsearched
assert loaded["radarr"]["Default"]["missing_pass"] == 2        # KEPT, carries forward
# leftover cursor key is actively STRIPPED on load by _merge_defaults (merged.pop) — NOT left to be overwritten
```

---

### `tests/test_refresh_counts.py` :: re-express queue-independence invariant (test, CRUD invariant — D-06)

**Analog (exact):** `test_refresh_radarr_counts_does_not_advance_cursor` @ :129 (+ Sonarr/Lidarr equivalents @ ~244/~303). Today: set cursor=N → refresh → assert cursor==N. **Re-express** to the searched-log:
```python
state["radarr"]["Default"]["missing_searched"] = ["1", "2", "3"]   # was: missing_cursor = 5
state["radarr"]["Default"]["cutoff_searched"] = ["9"]              # was: cutoff_cursor = 3
await refresh_radarr_counts(client, state, "Default", instance_config, settings)
assert state["radarr"]["Default"]["missing_searched"] == ["1", "2", "3"]  # unchanged
assert state["radarr"]["Default"]["cutoff_searched"] == ["9"]             # unchanged
```
Proves `refresh_*_counts()` neither reads nor writes the searched-log (the v2.10 CNT-02 invariant under the new model). `_make_test_state()` @ test_refresh_counts.py:48 already uses `_default_instance_state()`, so it auto-picks-up the new fields — strip any literal cursor keys in route fixtures (l.754-781 per RESEARCH table). **Keep the `*_pass` refs** (×4) — pass semantics preserved. Do NOT touch `_does_not_stamp_last_run` / `_sets_connected_true` tests.

---

### Incidental fixture strips (7 files — test, incidental)

**Analog:** any `AppState(missing_cursor=…, cutoff_cursor=…)` fixture literal. **Action: delete the `missing_cursor=`/`cutoff_cursor=` keyword args** from the fixture; assert nothing about them (they were never the subject under test). Files: `test_web.py` (+ l.1850 `== 0` → empty/absent-log assertion, RESEARCH A1; doc-comment l.385-387), `test_app_cards.py` (KEEP its 5 `*_pass` refs), `test_stats_health.py`, `test_ui_foundations.py`, `test_activity_rail.py`, `test_header_redesign.py`, `test_log_viewer.py`. Exact ref lines are in the RESEARCH classification table — do not re-grep.

---

## Shared Patterns

### Pure-function contract (apply to `prioritize_batch`)
**Source:** `slice_batch` @ engine.py:133-156 and `filter_by_tag` @ engine.py:59-74.
**Apply to:** the one new function.
- No I/O, no `app_type` branch, opaque list items, tuple return, full Args/Returns docstring, empty-input guard returning the empty tuple. `Callable` param convention copied from `filter_by_tag` (`get_tags: Callable[[dict], list[int]]` → `key_fn: Callable[[dict], str]`).

### Error handling — UNCHANGED per-item loop (apply to all 6 call sites)
**Source:** engine.py:421-444 (Radarr missing).
**Apply to:** every rewired call site — copy nothing new; *preserve* the existing two `except` arms verbatim:
```python
except PendingCapExceeded as cap_exc:
    logger.warning("Skipping search history insert -- pending-row cap reached ...")
    skipped_count += 1
    continue
except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
    logger.warning("<App>: Failed to search {title}: {exc}", ..., exc=_sanitize_exc(exc))
    await insert_search_entry(db, "<App>", "<queue>", ..., outcome="failed", detail=_sanitize_exc(exc), ...)
    skipped_count += 1
```
No bare `except:` (project rule). Mark-on-attempt means the failed item's key is already in `new_log` — the `except` arm needs no log mutation (RESEARCH Pitfall 1: never write the log inside `try`).

### Logging (apply to pass-complete line, D-11)
**Source:** loguru field-binding style at engine.py:419/449/502.
**Apply to:** the pass-complete INFO line at all 6 sites. Use `logger.info("…{p}… {n}…", p=…, n=…)` field binding (never f-string into the message — redacting sink + project loguru rule). Keep the existing per-cycle diagnostic summary (engine.py:500-508) exactly as-is. No per-cycle log dumps.

### Atomic state commit (apply to state changes)
**Source:** `save_state` @ state.py:185 (write-temp → fsync → `os.replace` → dir-fsync), invoked once at scheduler.py:377-379.
**Apply to:** nothing new — the searched-log rides the existing single cycle-end commit. Do not add a write path (QUEUE-11 / "Don't Hand-Roll").

### Back-compat via TypedDict `total=False` (apply to cursor removal)
**Source:** `_merge_defaults` @ state.py:129-151 + `total=False` on `AppState`.
**Apply to:** cursor removal — no separate migration function, but `_merge_defaults` ACTIVELY STRIPS old `*_cursor` keys on load (`for legacy_key in ("missing_cursor","cutoff_cursor"): merged.pop(legacy_key, None)`), so they never get written back; new `*_searched` read via `.get("<q>_searched", [])` at the call sites (QUEUE-03/D-09). The load→save round-trip test asserts the keys are ABSENT from the written JSON.

### Test fixtures (apply to all new/migrated tests)
**Source:** `_make_test_state()` @ test_search.py:230 & test_refresh_counts.py:48 (both build on `_default_instance_state()` → auto-inherit the new fields), `_cycle_settings()`/`_cycle_instance_config()` @ test_search.py:211/219, `tmp_path / "state.json"` round-trip idiom @ test_state.py:24.
**Apply to:** all new/migrated tests. pytest-asyncio auto mode — async cycle tests need no `@pytest.mark.asyncio` (RESEARCH). No new test deps.

---

## No Analog Found

None. Every file in this phase has an exact in-repo analog (the swap is like-for-like). The only genuinely novel logic is `prioritize_batch`'s never-searched-first partition, and even that mirrors `slice_batch`'s purity/shape/test-style — the planner should anchor to `slice_batch` (engine.py:133) and spec §6, not to RESEARCH.md's generic examples (the spec excerpt IS the algorithm).

---

## Metadata

**Analog search scope:** `triggarr/search/engine.py`, `triggarr/state.py`, `triggarr/search/scheduler.py`, `tests/test_search.py`, `tests/test_state.py`, `tests/test_refresh_counts.py` (all anchors already verified in RESEARCH.md against live code 2026-06-04 — re-read here, not re-grepped).
**Files scanned (read):** 6 source/test files (targeted, non-overlapping ranges).
**Pattern extraction date:** 2026-06-04
**Caveat for planner:** line numbers are valid as of 2026-06-04; if `engine.py`/`state.py` are edited mid-plan, re-anchor the 6 call sites by the `slice_batch(` / `*_cursor` markers, not by absolute line (RESEARCH "Valid until" note).
