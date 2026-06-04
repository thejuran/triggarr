# Phase 74 — Adversarial Review Notes (residual, accepted)

> Audit trail of the codex adversarial-review loop during planning. The plans were
> accepted after 3 rewrites; two residual edge-case findings remain, accepted by the
> user as non-blocking (pre-existing-pattern robustness, not phase-introduced regressions).
> **Executor + deep-review: address these opportunistically if cheap; they are the known
> open items for this phase.**

## Loop summary

| Round | Codex verdict | Finding(s) | Resolution |
|-------|---------------|-----------|------------|
| 1 | needs-attention | [high] Helper returning a filtered cutoff list reorders the scheduled search path (cutoff filter/dedup ahead of the missing search) — `test_search.py` would stay green while behavior drifted | Rewrite 1: helper returns 3-tuple `(filtered_missing, raw_cutoff, cutoff_tag_id)`; cycle re-filters raw cutoff inline after the missing search |
| 2 | needs-attention | [high] Sonarr/Lidarr helper still computed `cutoff_searchable` via dedup before the cycle's missing search; [medium] route tests mocked the obsolete 2-tuple | Rewrite 2: fully decoupled the count helper from `run_*_cycle` (cycle bodies byte-for-byte unchanged; helper standalone, endpoint-only); 3-tuple test mock + discard assertion |
| 3 | needs-attention | [high] Helper's filter/dedup/tag phase could raise `AttributeError/KeyError/TypeError` on malformed nested records (outside the route catch) → 500, not always-200 | Rewrite 3: helper wraps filter/dedup/tag in `except (AttributeError, KeyError, TypeError)` → connected=False + return None; helper + route malformed-data regressions |
| 4 | needs-attention | See residual findings below | **Accepted as-is** (user decision; diminishing returns — adjacent edge cases in the same malformed-JSON family, pre-existing in the scheduled cycle) |

## Residual findings (accepted — handle opportunistically)

### [high] Sonarr `get_library_count` is outside the helper's malformed-data fault boundary
The count helper calls `get_library_count` (best-effort, for `total_items`) BEFORE the protected
filter/dedup/tag phase. `SonarrClient.get_library_count` iterates unvalidated JSON and does
`s.get("statistics", {}).get("episodeCount", 0)` — a non-dict `statistics` (or non-dict series item)
raises `AttributeError`, which is NOT a fetch httpx/pydantic failure and NOT inside the narrow shape
catch added in rewrite 3, and the route catch intentionally excludes `AttributeError`. So a Sonarr
refresh against malformed `/api/v3/series` data can still return a 500, violating the always-200
malformed-data contract.

**Suggested fix (executor/follow-up):** make library count genuinely cosmetic — either harden
`SonarrClient.get_library_count` to validate/skip malformed `statistics`, or wrap ONLY the helper's
`get_library_count` call in `except (AttributeError, TypeError)` and keep the prior `total_items` on
fault. Add a regression with malformed `/api/v3/series` proving helper None/200 (or continued success
with stale `total_items`).

### [medium] No-partial-state contract still allows raw-count mutation on data faults
74-01 currently allows `missing_count`/`cutoff_count`/`total_items` to be set BEFORE filtering, deferring/
resetting only the eligible/searchable derived fields. So a malformed cutoff record can leave the card
`connected=False` with fresh raw counts from the bad payload + cleared derived counts. The planned
malformed-data tests only assert the eligible/searchable half and would not catch raw-count mutation.

**Suggested fix (executor/follow-up):** compute ALL count fields locally and commit them together only
after the data phase succeeds, OR reset every count field (raw + derived + total_items) on the data-fault
path. Strengthen the malformed-data tests to seed sentinel `missing_count`/`cutoff_count`/`total_items`/
derived fields and assert the FULL count set is unchanged-or-cleared after the helper returns None.

## Context for accepting

- The core design is sound and was hardened across 3 rounds: structural cursor guarantee (slicing/cursor
  only in the cycle), helper fully decoupled from `run_*_cycle` (cycle bodies byte-for-byte unchanged),
  endpoint mirrors `search_now` (guards, DRSEC-03 in-lock rate-limit, sibling `last_refresh_time`,
  always-200+card, no `_run_one_cycle`/`search_failures`/`last_run` touch), and the primary malformed-data
  vector (filter/dedup/tag) is caught.
- Both residual findings are in the "malformed/non-conforming *arr JSON" family. This exposure is
  **pre-existing in the shipped scheduled cycle** (which calls the same `get_library_count` and filter/dedup
  primitives without these guards) and real Radarr/Sonarr/Lidarr servers return well-formed, Pydantic-shaped
  responses. They are robustness hardening, not regressions this phase introduces.
- Accepted by the user at the adversarial cap rather than spending a 4th plan-rewrite on progressively
  narrower edge cases.
