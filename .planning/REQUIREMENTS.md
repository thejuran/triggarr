# Requirements: Triggarr

**Defined:** 2026-06-04
**Core Value:** Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.

**Milestone:** v2.11 Never-Searched-First Search Queue Priority
**Source of truth:** `docs/superpowers/specs/2026-06-04-search-queue-priority-design.md`

## v1 Requirements

Requirements for this milestone. Each maps to exactly one roadmap phase.

### Searched-Log State Model

- [ ] **QUEUE-01**: Each instance persists an ordered "searched-log" of *arr item IDs per queue (missing and cutoff) in `state.json`, recording the order items were searched (oldest at the front).
- [ ] **QUEUE-02**: Item IDs are normalized to strings per app type — Radarr and Lidarr use the item `id`; Sonarr uses the composite `seriesId:seasonNumber` — so marking one season searched never marks a different season of the same series.
- [ ] **QUEUE-03**: The integer `missing_cursor`/`cutoff_cursor` fields are removed from `AppState`, and a pre-upgrade `state.json` (containing cursor keys but no searched-logs) loads cleanly and is treated as everything-unsearched (no migration step).

### Never-Searched-First Dispatch

- [ ] **QUEUE-04**: Each cycle's batch is filled with never-searched eligible items first, in fetched API order.
- [ ] **QUEUE-05**: When unsearched items do not fill the batch, the remaining slots are topped up with already-searched items, oldest-searched-first.
- [ ] **QUEUE-06**: On a cold start (empty searched-log), dispatch produces the same batch the prior first-cycle cursor walk produced (behavior-preserving).
- [ ] **QUEUE-07**: `slice_batch` is replaced by a pure `prioritize_batch()` function at all six cycle call sites (Radarr, Sonarr, Lidarr × missing, cutoff), and `slice_batch` is removed.

### Searched-Log Lifecycle

- [ ] **QUEUE-08**: An item is marked searched on attempt (its search command is fired), whether the individual search succeeds or fails, so a persistently-failing item cannot starve the queue.
- [ ] **QUEUE-09**: When every currently-eligible item in a queue has been searched, that queue's searched-log is cleared and the existing `missing_pass`/`cutoff_pass` counter increments (a completed pass).
- [ ] **QUEUE-10**: Each cycle the searched-log is pruned to currently-eligible IDs, so items that left the list (grabbed, unmonitored, deleted) drop out and the log stays bounded.
- [ ] **QUEUE-11**: Searched-log and pass-counter updates commit only at cycle end, in the same atomic `save_state()` as the rest of the cycle's state, so the searched-log and pass counter can never disagree (at-least-once semantics).

## v2 Requirements

Deferred. Tracked but not in this milestone's roadmap.

(None for this milestone — see Out of Scope for the explicit YAGNI fence.)

## Out of Scope

Explicitly excluded for v2.11 (from the design spec §9 YAGNI fence). Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Per-item retry counters / backoff | Mark-on-attempt deliberately avoids retry machinery; out of scope for "prioritize never-searched". |
| Timestamp map of last-searched-at | The ordered searched-log gives recency ordering without per-item timestamps. |
| `SearchQueue` class / OO refactor | Kept as plain `AppState` fields + a pure function; no object-lifecycle layer. |
| UI queue inspector / reorder / pin | Could build on this later; not part of this mechanism change. |
| Per-instance parallelism / per-instance locks | The global `search_lock` is unchanged. |
| Changes to fetch, filtering, or count-only refresh | Untouched; the count-only path stays queue-independent. |
| Changes to scheduling intervals or rate limits | Untouched. |
| Changes to the SAFETY-03 consecutive-failure counter | Untouched. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| QUEUE-01 | TBD | Pending |
| QUEUE-02 | TBD | Pending |
| QUEUE-03 | TBD | Pending |
| QUEUE-04 | TBD | Pending |
| QUEUE-05 | TBD | Pending |
| QUEUE-06 | TBD | Pending |
| QUEUE-07 | TBD | Pending |
| QUEUE-08 | TBD | Pending |
| QUEUE-09 | TBD | Pending |
| QUEUE-10 | TBD | Pending |
| QUEUE-11 | TBD | Pending |

**Coverage:**
- v1 requirements: 11 total
- Mapped to phases: 0 (roadmap pending)
- Unmapped: 11 ⚠️ (filled by roadmapper)

---
*Requirements defined: 2026-06-04*
*Last updated: 2026-06-04 after initial definition*
