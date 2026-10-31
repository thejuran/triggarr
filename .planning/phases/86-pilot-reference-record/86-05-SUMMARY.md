---
phase: 86-pilot-reference-record
plan: 05
subsystem: web
tags: [cycle-grade, outcome, jinja2, card-template, tdd]

# Dependency graph
requires:
  - phase: 86-pilot-reference-record (plan 04)
    provides: "Refresh-counts PR's batched revision and final-head review record completed before this plan's independent pilot-card-reason-kind branch was cut"
provides:
  - "pilot-card-reason-kind branch (cut from origin/main d5a4467), tip H1 = 46c39194249d1e7bcd2362a91d238d0997539f3f, holding the Card-template structured-reason-kind PR's product diff for the PILOT-01 new-PR slot (D-03)"
  - "cycle_view() reason dicts carry a structured kind (fetch_failed/failure/unevaluated/malformed/eligible_not_searched) and malformed rows carry a numeric skip_count, so cycle_grade.html classifies rows without matching outcome.py's display text"
affects: [86-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A render-ready dict's grouping discriminator (kind) is set once at each construction site in the producing function, never re-derived by the consuming template from the already-rendered display text"

key-files:
  created: []
  modified:
    - triggarr/search/outcome.py
    - triggarr/templates/partials/cycle_grade.html
    - tests/test_outcome.py

key-decisions:
  - "Divergence analysis (Task 1) concluded no reachable divergence exists between the old text-matching classifier and the new kind-based one: the three candidate inputs named in the plan (a failure-reason text ending in 'skipped'; a malformed row's text truncated past its identifying suffix; a non-unevaluated row starting with the unevaluated prefix) each require either text this application's real producers (_sanitize_exc, the fixed unevaluated-row prefix) never generate, or record values (70+ digit malformed/eligible counts) no real *arr library, or this codebase's own existing tampered-record test precedent, has ever produced. Task 2 (the conditional owner checkpoint) was therefore not needed."

requirements-completed: [PILOT-01]

# Metrics
duration: ~25min (including branch setup, the divergence analysis/evidence-gathering, and the full-suite + ruff gate run; RED to GREEN commit-to-commit was ~1min)
completed: 2026-10-30
---

# Phase 86 Plan 05: Card Reason-Row Structured Kind Summary

**`cycle_view()` now sets a constant `kind` (and `skip_count` on malformed rows) at each of its six reason-row construction sites, and `cycle_grade.html` groups rows by `r.kind`/`r.skip_count` instead of matching `outcome.py`'s rendered display text — with zero reachable visible difference (D-03).**

## Performance

- **Duration:** ~25 min total (branch setup, divergence analysis across `engine.py`/`clients/base.py`, test edits, implementation, full-suite gate, SUMMARY). Commit-to-commit RED (`1fb66b9`, 21:26:23-04:00) to GREEN (`46c3919`, 21:27:39-04:00) was ~1 min 16 s.
- **Tasks:** 2/3 executed (Task 2 was conditional and did not run; Task 1 concluded no visible divergence exists, so Task 3 proceeded directly per the plan's own branching rule)
- **Files modified:** 3 (1 product file, 1 template, 1 test file)

## Accomplishments

- Added `"kind"` at all six `cycle_view()` reason-row construction sites (`fetch_failed`, `failure`, `unevaluated`, `malformed` ×2 construction sites, `eligible_not_searched`) and `"skip_count"` on the two malformed sites, set as a constant at construction — never read back from the persisted record or re-derived from display text.
- Extended `cycle_view()`'s docstring (existing voice) to describe the structured `kind`/`skip_count` fields.
- Replaced `cycle_grade.html`'s three-way `r.text.startswith`/`r.text.endswith`/`r.text.split` classification with `r.kind == 'unevaluated'` / `r.kind == 'malformed'` (summing `r.skip_count`) / else `other`. The summary-label block and the rendering loop (`r.text`/`r.count`) are byte-for-byte unchanged.
- Divergence analysis (Task 1) worked through all three candidate inputs the plan named, tracing every real producer of `failure_reasons[].reason` (`_sanitize_exc`, one call site), every real producer of a malformed count (`tally.record_malformed(queue, len(skipped))`, bounded by realistic *arr library/page sizes), and the truncation-proof prefix match for unevaluated rows. Concluded **no reachable divergence** exists for any input this application's real code paths — or its own existing tampered-record test precedent — can produce. Full reasoning and evidence commands are below (transcribed from the deleted `/tmp/86-05-divergence.md`). Task 2 (the conditional owner checkpoint) was therefore not needed, and no equivalence test was required in `tests/test_app_cards.py` (it is untouched).
- Updated every expected reason-dict literal in `tests/test_outcome.py` to include `"kind"` (12 literals) and `"skip_count"` on the 6 malformed-literal occurrences; added `test_cycle_view_every_reason_has_kind`, which exercises all six construction sites across three `cycle_view()` calls and asserts every reason's `kind` is one of the five allowed values, with `skip_count` present only on malformed rows.
- Full suite (3271 passed, 1 pre-existing unrelated skip) and `ruff check triggarr/ tests/` both passed with `HEAD` asserted at the pilot branch tip (H1) before the checkout moved back to the phase branch.

## Task Commits

Each task was committed atomically on `pilot-card-reason-kind` (cut from `origin/main` at `d5a4467`):

1. **Task 1 (RED): Expected dicts gain kind/skip_count, plus divergence and guard tests** — `1fb66b9` (test)
2. **Task 2 (conditional): Owner scope decision on a visible divergence** — not run (Task 1 concluded no reachable divergence; recorded "Task 2 not needed: no visible divergence" and continued to Task 3 per the plan's branching rule)
3. **Task 3 (GREEN): Add kind/skip_count in cycle_view and switch the template** — `46c3919` (feat)

No `refactor(86-05):` commit was needed — tests and ruff were clean after Task 3's implementation with no follow-up cleanup required.

H1: 46c39194249d1e7bcd2362a91d238d0997539f3f

## Divergence Analysis (Task 1, full reasoning)

**Conclusion: no reachable divergence.**

**Candidate 1 — a failure-reason row whose text ends with "skipped":** the only producer of a `failure_reasons[].reason` string is `CycleTally.record_failed(reason)` (`outcome.py:116`), called from exactly one site, `triggarr/search/engine.py:546`, with `reason = _sanitize_exc(exc)` (`engine.py:539`). `record_failed`'s docstring requires pre-sanitized text, and `_sanitize_exc` (`triggarr/clients/base.py:17-33`) only ever returns `"HTTP {3-digit status}"`, `"request timeout"`, `"HTTP error: {ExceptionTypeName}"`, `"validation error ({N} issues)"`, or a bare exception type name — none end in "skipped", and the rendered text is always wrapped in a trailing `)` (`f"...({reason})"`). The only way the old `.endswith('skipped')` check could fire is if `_truncate()`'s 120-char limit stripped that trailing paren, which requires the untruncated text to exceed 120 chars; the longest real `_sanitize_exc` output is ~30 chars. Not reachable via any call site in the codebase.

**Candidate 2 — a malformed row whose text `_truncate` shortened:** both malformed-row text formats place their identifying suffix ("— malformed data" / "skipped") at the end of the string, so a sufficiently large count could in principle push that suffix past the 120-char limit (measured: the fixed per-queue suffix is 47 chars, so this needs a count with ~74+ digits). The count comes from `tally.record_malformed(queue, len(skipped))` (`engine.py:192`) — bounded by realistic `page_size`/library sizes (never more than low thousands, 4-5 digits) — or `sum(malformed_by_queue.values())` for the legacy aggregate, same bound. A 74-digit count is physically impossible from any real Radarr/Sonarr/Lidarr library, and this codebase's existing tampered-record tests (`test_cycle_view_malformed_by_queue_tampered_falls_back`, `test_card_skip_only_mismatched_count_falls_back_to_failure_label`) exercise type-confusion and small-number mismatches, never an astronomically large valid integer. Not reachable from any value this application, or its own adversarial-input test precedent, produces.

**Candidate 3 — a non-unevaluated row starting with "Missing queue not evaluated: " (or the Cutoff variant):** only the unevaluated-row construction site (`outcome.py` ~line 291) ever produces this literal prefix, and `_truncate()` only removes trailing characters, so it can never strip a leading prefix. Old (startswith, checked first) and new (`kind="unevaluated"`, set at this row's sole construction site) always agree. No divergence possible.

**Evidence commands run:**
```
grep -n "record_failure\|failure_reasons\|record_malformed\|mark_unevaluated\|malformed_skipped\b" triggarr/search/*.py triggarr/state.py
grep -n "\.record_failed(" triggarr/search/*.py
sed -n '500,550p' triggarr/search/engine.py   # _search_and_record / record_failed call site
sed -n '1,40p' triggarr/clients/base.py       # _sanitize_exc
grep -n '"x" \* \|truncat\|_MAX_REASON' tests/test_app_cards.py   # confirms no existing truncation-boundary test
```

The `/tmp/86-05-divergence.md` scratch note has been deleted; the above is its full content, transcribed.

## Files Created/Modified

- `triggarr/search/outcome.py` — `cycle_view()`'s six reason-row construction sites each add `"kind"`; the two malformed sites also add `"skip_count"`; docstring extended to describe the new fields.
- `triggarr/templates/partials/cycle_grade.html` — the namespace loop's three-way branch now reads `r.kind`/`r.skip_count` instead of `r.text.startswith`/`r.text.endswith`/`r.text.split`; summary-label block and rendering loop unchanged.
- `tests/test_outcome.py` — 12 expected reason-dict literals gained `"kind"` (6 of those also gained `"skip_count"`); added `test_cycle_view_every_reason_has_kind`.

## Decisions Made

- See `key-decisions` in frontmatter: no reachable divergence, Task 2 not needed.
- `tests/test_app_cards.py` was read (per `read_first`) but required zero changes — all 90 of its full-route rendering assertions passed unmodified both before (RED) and after (GREEN) the refactor, confirming D-03's "visible output identical" claim directly rather than by inference.

## Deviations from Plan

None — plan executed exactly as written. The divergence analysis concluded no reachable case exists, so Task 2 (conditional) correctly did not run, matching the plan's own branching instruction.

## Issues Encountered

None.

## Next Phase Readiness

- `pilot-card-reason-kind` branch exists locally (not pushed), tip at H1 (`46c3919`), ready for 86-06's paired BM+Codex review and owner acceptance.
- No PR opened yet — per the plan, this plan only produces the branch and H1.
- The branch's merge-base with `origin/main` is exactly `origin/main`'s tip at cut time (`d5a4467`), confirming clean branch provenance for the Codex trust check.

## Self-Check: PASSED

- FOUND: `triggarr/search/outcome.py`
- FOUND: `triggarr/templates/partials/cycle_grade.html`
- FOUND: `tests/test_outcome.py`
- FOUND: `.planning/phases/86-pilot-reference-record/86-05-SUMMARY.md`
- FOUND commit `1fb66b9` (Task 1, RED)
- FOUND commit `46c3919` (Task 3, GREEN, = H1)

---
*Phase: 86-pilot-reference-record*
*Completed: 2026-10-30*
