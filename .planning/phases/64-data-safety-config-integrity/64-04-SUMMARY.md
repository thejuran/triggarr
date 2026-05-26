---
phase: 64-data-safety-config-integrity
plan: 04
subsystem: database
tags:
  - python
  - sqlite
  - aiosqlite
  - retention
  - safety
  - tdd
  - loguru

# Dependency graph
requires:
  - phase: prior plans in phase 64
    provides: existing search_history schema + DEBT-03 trim SQL
provides:
  - SAFETY-01 closed (resolved-row trim verified at 2x scale)
  - SAFETY-01b closed (pending-row cap rejects inserts >= 2 * max_rows with WARNING log)
  - PendingCapExceeded exception class (new, structured attributes for operator correlation)
  - PENDING_CAP_MULTIPLIER module constant
affects:
  - phase 65 (scheduler hardening — tracking layer may catch PendingCapExceeded in future plans)
  - phase 66 (config save lock — separate concern; this plan adds no config-write paths)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD triple: RED test commit (test) -> GREEN implementation commit (feat) -> REFACTOR (no code change needed; verification-only)."
    - "Module-level Exception class with structured attributes (app/instance_id/item_name/pending_count/cap) for callers that want to handle the exception programmatically."
    - "Module-level safety constant with rationale comment block (PENDING_CAP_MULTIPLIER) rather than config field — operator-tunable would be a foot-gun."

key-files:
  created: []
  modified:
    - "triggarr/db.py — added PENDING_CAP_MULTIPLIER constant, PendingCapExceeded class, pending-cap guard in insert_search_entry, expanded docstring with Bounds/Raises sections"
    - "tests/test_db.py — added test_insert_caps_at_max_rows_over_large_soak (SAFETY-01 soak) and test_pending_inserts_rejected_when_cap_reached (SAFETY-01b TDD); added io and loguru.logger imports"

key-decisions:
  - "Reject rather than evict when pending cap is hit (User Decision Path A). Eviction would lose tracking semantics for already-in-flight entries; rejection logs a WARNING the operator can correlate to a specific stalled tracker."
  - "Cap multiplier (2x max_rows) as a module constant, not a config field. Operator-tunable would create a foot-gun (raise cap -> disk fills)."
  - "Custom PendingCapExceeded subclassing Exception (not RuntimeError/ValueError). Domain-specific type makes log lines and stack traces self-describing to operators."
  - "Guard runs BEFORE the INSERT (the rejected row never lands). Confirmed by the test assertion that pending_count remains exactly 2*max_rows after the failed insert."

patterns-established:
  - "Two-bound contract for search_history: resolved rows trimmed inline (transactional with insert); pending rows guarded by pre-INSERT count (raises domain exception on cap)."
  - "Loguru kwargs idiom for structured WARNING logs (no f-string templates) so operators see app/instance_id/item_name as parseable fields."

requirements-completed:
  - SAFETY-01
  - SAFETY-01b

# Metrics
duration: 5min
completed: 2026-05-26
---

# Phase 64-04: Search History Bounded Growth Summary

**SQLite search_history now has a two-bound contract: resolved rows trimmed inline (SAFETY-01, verified at 2x scale via soak test), and pending rows capped at 2 × max_rows with PendingCapExceeded + WARNING log (SAFETY-01b, NEW per Codex F1 / User Decision Path A).**

## Performance

- **Duration:** 5 min (279 seconds)
- **Started:** 2026-05-26T00:10:44Z
- **Completed:** 2026-05-26T00:15:23Z
- **Tasks:** 5 (4 with code/doc commits; Task 5 was verification-only — no diff)
- **Files modified:** 2 (triggarr/db.py, tests/test_db.py)

## Accomplishments

- **SAFETY-01 closed:** insert_search_entry docstring now documents the resolved-row trim as an explicit bound with transactional semantics. Soak test test_insert_caps_at_max_rows_over_large_soak proves the cap holds at 2x scale (2000 inserts -> 1000 resolved rows, completes in 0.88s).
- **SAFETY-01b closed:** New PendingCapExceeded exception + pending-row guard rejects pending inserts when pending count >= 2 × max_rows, emits a structured WARNING log naming the rejected entry's identifiers, and preserves tracking semantics for already-in-flight rows (no eviction).
- **Full pytest suite green at 881 passing** (up from 857 baseline + ongoing v2.8 additions). Ruff clean across triggarr/ and tests/.
- **Zero new dependencies.** Implementation is stdlib + existing loguru/aiosqlite stack.

## Task Commits

Each task was committed atomically:

1. **Task 1: Expand insert_search_entry docstring** — `52bdadb` (docs)
2. **Task 2: SAFETY-01 soak test** — `5bbdfff` (test)
3. **Task 3 (RED): Failing test for pending cap** — `797ac3f` (test)
4. **Task 4 (GREEN): PendingCapExceeded + guard** — `e41690a` (feat)
5. **Task 5 (REFACTOR): Verification-only — no code changes required** — _(no commit; see "Deviations" below)_

## Files Created/Modified

- `triggarr/db.py` — added `PENDING_CAP_MULTIPLIER = 2` module constant (with 7-line rationale comment), `PendingCapExceeded` exception class (carries app/instance_id/item_name/pending_count/cap), and a pre-INSERT pending-cap guard in `insert_search_entry`. Expanded the function's docstring with a `Bounds:` section (SAFETY-01 + SAFETY-01b) and a `Raises:` section.
- `tests/test_db.py` — added `test_insert_caps_at_max_rows_over_large_soak` (SAFETY-01 soak, 2000 inserts) and `test_pending_inserts_rejected_when_cap_reached` (SAFETY-01b TDD with loguru sink capture). Added `import io` and `from loguru import logger` to support the WARNING-log assertion.

## Code Highlights

**The expanded docstring (Bounds + Raises sections):**

```
Bounds:
    * Resolved rows (outcome != 'searched') are trimmed inline after
      every insert to keep their count <= max_rows. The trim runs in
      the same transaction as the insert (single ``db.commit()`` at
      the end), so the cap holds immediately on the next read. Closes
      SAFETY-01.
    * Pending rows (outcome == 'searched') are bounded separately at
      ``PENDING_CAP_MULTIPLIER * max_rows`` (default 2x). If the
      pending count is already at or above this cap, a new pending
      insert is REJECTED with ``PendingCapExceeded`` and a WARNING
      log line identifying the rejected entry (app, instance_id,
      item_name). This bounds the stalled-tracker failure mode
      (Sonarr/Radarr unreachable for extended period). Pending rows
      are also bounded by ``tracking_window_minutes`` (their natural
      resolution timeout). Closes SAFETY-01b.

Raises:
    PendingCapExceeded: when ``outcome == 'searched'`` and the
        pending row count is already >= PENDING_CAP_MULTIPLIER *
        max_rows. The insert is rejected; existing pending rows are
        NOT evicted (eviction would lose tracking semantics).
```

**The new exception class (triggarr/db.py module scope, before MIGRATIONS dict):**

- `PendingCapExceeded(Exception)` with `__init__(app, instance_id, item_name, pending_count, cap)` storing each as an attribute; `super().__init__` formats a self-describing message including the rejected `item_name`.

**The new constant (triggarr/db.py module scope, with 7-line rationale comment):**

- `PENDING_CAP_MULTIPLIER: int = 2` — comment explains the 2x choice (transient tracking backlog headroom), the stalled-tracker failure mode being bounded, and why this is a constant rather than a config field (operator-tunable foot-gun).

**The new guard in insert_search_entry (BEFORE the existing INSERT):**

```python
if outcome == "searched":
    cap = PENDING_CAP_MULTIPLIER * max_rows
    async with db.execute(
        "SELECT COUNT(*) FROM search_history WHERE outcome = 'searched'"
    ) as cursor:
        row = await cursor.fetchone()
    pending_count = row[0] if row is not None else 0
    if pending_count >= cap:
        logger.warning(
            "Pending-row cap reached -- rejecting search_history insert "
            "for {app}/{instance_id} {item_name!r} (pending={pending_count}, cap={cap}). "
            "Tracker may be stalled; check app reachability.",
            app=app, instance_id=instance_id, item_name=item_name,
            pending_count=pending_count, cap=cap,
        )
        raise PendingCapExceeded(
            app=app, instance_id=instance_id, item_name=item_name,
            pending_count=pending_count, cap=cap,
        )
```

## Test Highlights

**SAFETY-01 soak — `test_insert_caps_at_max_rows_over_large_soak` (tests/test_db.py):**

- Drives `2 * max_rows = 2000` resolved inserts with `max_rows=1000`.
- Asserts `COUNT(*) WHERE outcome != 'searched' == 1000` AND `COUNT(*) == 1000`.
- Runtime: 0.88s on local hardware. Proves the trim runs after every insert (not just some).

**SAFETY-01b TDD — `test_pending_inserts_rejected_when_cap_reached` (tests/test_db.py):**

Three assertions, each proving a distinct contract:

1. **Cap boundary invariant.** After `2 * max_rows` (10) successful pending inserts, `COUNT(*) WHERE outcome = 'searched' == 10` — proves the cap allows the full 2x band before guarding.
2. **Rejection + WARNING.** The 11th pending insert raises `PendingCapExceeded` (via `pytest.raises`) AND the loguru sink captures a WARNING containing both `"Rejected entry"` (the rejected `item_name`) and `"Radarr"` (the app) — proves the operator-correlation contract.
3. **No-row-landed invariant.** After the failed insert, pending count is still exactly `2 * max_rows = 10` (not 11) — proves the guard runs BEFORE the INSERT.

## Verification Evidence

- `grep -c "Closes SAFETY-01" triggarr/db.py` = 1 (resolved-row clause)
- `grep -c "Closes SAFETY-01b" triggarr/db.py` = 1 (pending-row clause)
- `grep -c "^class PendingCapExceeded" triggarr/db.py` = 1
- `grep -c "^PENDING_CAP_MULTIPLIER" triggarr/db.py` = 1
- `grep -c "raise PendingCapExceeded" triggarr/db.py` = 1
- `grep -c "logger.warning" triggarr/db.py` = 1 (the new pending-cap WARNING)
- `grep -A12 "Tracking-aware pruning" triggarr/db.py | grep -c "ORDER BY id DESC LIMIT"` = 1 (the existing trim SQL is UNCHANGED — SAFETY-01 SQL invariant preserved)
- `uv run pytest tests/test_db.py -x -q` -> **57 passed**
- `uv run pytest tests/ -x -q` -> **881 passed, 27 warnings** (no regressions; warnings are pre-existing starlette test-client cookie deprecations)
- `uv run ruff check triggarr/ tests/` -> **All checks passed**

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Reject pending insert (not evict) | Eviction would discard in-flight tracking — the original concern that drove SAFETY-01 deferral. Rejection + WARNING preserves tracking semantics and gives the operator a correlation handle. (User Decision Path A) |
| Module constant for the 2x multiplier | A config field would let operators raise the cap and fill disk by accident. The cap is a safety bound, not a tuning knob. |
| `PendingCapExceeded(Exception)` subclassing `Exception` directly | Operators reading logs benefit from a domain-specific type; `RuntimeError`/`ValueError` would conflate with infrastructure errors. |
| Guard placed BEFORE the INSERT (not as a post-INSERT check + DELETE) | Cheaper (no INSERT then rollback), and the row literally never lands in the table — verified by the test's pending-count assertion. |
| Loguru kwargs idiom (no f-strings inside the message template) | Matches the existing style in `triggarr/config.py:230-233`; keeps `app`/`instance_id`/`item_name` as parseable structured fields. |

## Deviations from Plan

### REFACTOR phase completed with no code changes

**Task 5 — REFACTOR (verification-only, no commit)**

- **Issue:** The plan's Task 5 (REFACTOR) instructions called for verifying that `max_rows` is read fresh per call, the multiplier is well-documented, and that no tracking/search tests need updating due to the new guard.
- **Outcome:** All invariants were already satisfied by Task 4's implementation:
  - `grep -c "_max_rows_cache\|MAX_ROWS_CACHE" triggarr/db.py` returns 0 — no caching introduced.
  - The constant comment block (7 lines) explains the 2x choice and the foot-gun rationale; SAFETY-01b traceability tag is present.
  - The full suite (881 tests) passes — no pre-existing tracking/search test drives more than `2 * max_rows` pending inserts, so the new guard does not break any test.
  - Docstring matches implementation (`PendingCapExceeded` referenced in both the docstring and the raise site; no drift).
- **Action:** No code changes needed; no commit. Verification passed via grep + pytest + ruff.
- **Per TDD execution flow:** "REFACTOR (if needed): Clean up, run tests (MUST still pass), commit only if changes." This is the documented behavior.

**Total deviations:** 0 auto-fixes; 1 verification-only REFACTOR (planned per TDD).

**Impact on plan:** None. Plan executed exactly as written — Task 5 verification confirmed Tasks 1-4 were complete and clean. No tracking/search tests required modification.

## Issues Encountered

None. All tests passed on the first run after each commit. No auth gates, no checkpoints, no architectural questions.

## User Setup Required

None — no config changes, no environment variables, no external service configuration. The new guard is purely internal SQLite logic.

## Next Phase Readiness

- **Phase 65 (Scheduler Hardening):** `PendingCapExceeded` is now available for the tracking layer to catch if a future plan wants to surface stalled-tracker state via a different mechanism (e.g., a UI banner). Out of scope for this plan but the API shape enables it.
- **Phase 66 (Security Hardening):** Independent of this plan. No coupling.
- **No blockers, no carry-forward concerns.**

## Self-Check: PASSED

Verified files exist:
- FOUND: triggarr/db.py
- FOUND: tests/test_db.py
- FOUND: .planning/phases/64-data-safety-config-integrity/64-04-SUMMARY.md (this file)

Verified commits exist in git log:
- FOUND: 52bdadb — docs(64-04): expand insert_search_entry docstring to document both bounds
- FOUND: 5bbdfff — test(64-04): add SAFETY-01 soak test for resolved-row trim at 2x scale
- FOUND: 797ac3f — test(64-04): add failing test for SAFETY-01b pending-row cap (RED)
- FOUND: e41690a — feat(64-04): add PendingCapExceeded + pending-row guard (GREEN, SAFETY-01b)

---
*Phase: 64-data-safety-config-integrity*
*Plan: 04*
*Completed: 2026-05-26*
