# Phase 76: Never-Searched-First Search Queue - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in 76-CONTEXT.md — this log preserves the discussion.

**Date:** 2026-06-04
**Phase:** 76-never-searched-first-search-queue
**Mode:** discuss
**Areas analyzed:** prioritize_batch placement & signature; Test-migration strategy for cursor removal; Sonarr season-key edge cases; Empty/partial-pass logging & observability

**Framing:** The design spec (`docs/superpowers/specs/2026-06-04-search-queue-priority-design.md`) locks the algorithm, data model, marking, and removals (10 decisions). Discussion was scoped to the remaining HOW-to-implement choices only. The user selected all four gray areas.

## Area 1 — prioritize_batch placement & signature

**Q1a — How does `prioritize_batch` get the per-app ID function?**
- Options: A) `key_fn` parameter (generic/pure); B) `app_type` string branched inside; C) module helper taking `app_type`.
- **User chose: A** — `key_fn` parameter. Keeps the function app-agnostic and trivially unit-testable; per-app key construction stays co-located in the three cycle functions. → D-02.

**Q1b — Return tuple and where marking happens?**
- Options: A) function returns `(batch, new_searched_log, pass_completed)` with appends inside; B) returns `(batch, pass_completed)`, caller appends.
- **User chose: A** — all log lifecycle concentrated in the one pure function; callers stay thin. → D-01, D-03, D-04.

## Area 2 — Test-migration strategy for cursor removal

**Context surfaced:** cursor references span many test files — test_state.py ~65, test_search.py ~28, test_refresh_counts.py ~23, test_web.py ~13, plus UI/dashboard fixtures ~4–6 each.

**Q2a — How to handle the broad cursor footprint?**
- Options: A) classify then migrate-or-strip by role; B) blanket find-and-replace; C) keep cursor fields as tombstones to dodge churn.
- **User chose: A** — behavioral cursor-value assertions migrate to searched-log/pass assertions; incidental UI fixtures strip the removed keys; refresh-counts "cursor unchanged" invariant re-expressed as "searched-log unchanged" (count-only path neither reads nor writes the searched-log). → D-05, D-06, D-07.

## Area 3 — Sonarr season-key edge cases

**Q3a — Exact Sonarr key string format?**
- Options: A) `f"{seriesId}:{seasonNumber}"`; B) 2-element list (breaks uniform `list[str]`); C) padded/escaped (needless).
- **User chose: A** — uniform `list[str]` across all queues; key opaque to `prioritize_batch` (stable + collision-free suffices). Specials (`seasonNumber=0` → `"1234:0"`) treated as an ordinary distinct key. → D-08, D-09.
- **Folded without separate question:** `deduplicate_to_seasons()` preserves first-occurrence order at filter time, so season dicts reach the partition in stable fetch order — no extra sorting. → D-10.

## Area 4 — Empty/partial-pass logging & observability

**Q4a — Log verbosity for the new searched-log lifecycle?**
- Options: A) minimal (preserve per-cycle diagnostic; one INFO line on pass-completion; no UI); B) verbose (per-cycle unsearched-count); C) new dashboard surface (out of scope per spec §9).
- **User chose: A** — preserve today's diagnostic exactly; one INFO line on pass-completion replacing the old wrap-around log; no new UI; `*_pass` stays the only dashboard-facing signal; failed searches still log + write `failed` history rows. → D-11, D-12.

## Corrections Made

No corrections — all four areas resolved on first option (A) each, consistent with the locked spec.

## Deferred Ideas

None — discussion stayed within phase scope. All scope-creep candidates (retry/backoff, timestamp maps, UI queue inspector, per-instance parallelism) are already fenced out in spec §9 and the REQUIREMENTS.md Out-of-Scope table.
