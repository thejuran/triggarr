# Triggarr maintenance

Updated 2026-10-18. Small ongoing work and change-time rules; not a separate development milestone. Confirm existing implementation and current need before acting.

## Change-time rules

- **Atomic writes (former 999.8):** preserve atomic replacement, secret-file permissions, cleanup and durability. Fix demonstrated defects with focused tests; no mandatory consolidation of all writers/public APIs.
- **URL validation (former 999.11):** ship migration/recovery and a regression test alongside any future rule that rejects a previously supported configuration. Do not prebuild a generic migration framework or weaken validation.
- Preserve changelog escaping and its tests, and ordinary login/setup/settings usability and accessibility checks.

## Small follow-ups

- Revalidate the README screenshot and CI action-runtime tasks in [TODO.md](../../TODO.md). Close already-delivered work rather than repeating it; update only remaining discrepancies.
- Recheck the old v2.9 Retry-Connection button behavior and bug-report version options; fix confirmed user-facing problems while touching those areas. URL-validation deduplication is optional local cleanup, not its own plan.
- **Card reasons label (found in the Phase 80 walkthrough, 2026-10-18):** the dashboard card's expandable list reads "Show N failure reasons" even when nothing failed (e.g. a Partial cycle with "0 failed" whose only rows are malformed-record skips). Reword the label so skip-only rows are not called failures; keep the row text and grade colors unchanged.
- **Refresh counts vs. scheduled cycles on a malformed record (kept out of PR #28 on 2026-10-18):** one malformed record (e.g. Sonarr `"series": null`) makes "Refresh counts" mark the instance disconnected and blank its counts, because `refresh_sonarr_counts`/`refresh_lidarr_counts` keep the coarse whole-instance guard, while a scheduled cycle now skips that record per item (per-item screening remains deferred; the shared release-date fix also benefits refresh). Decide whether refresh should skip per item too; if so, add a regression test for each app.

## Operator planning follow-up

After v2.12 closes, present [the review-workflow proposal](../../docs/bm-greptile-codex-blueprint.md) for owner confirmation. Do not enable the pilot, update BM for it, remove vibe-check, or change current acceptance requirements as part of this organization. It is not a v2.12 blocker or a product milestone.

After v2.12 also present [the CI reference-baseline plan](../../docs/ci-reference-baseline-plan.md) alongside the review blueprint. Goal: make Triggarr the model for other repositories, starting with tests of the shipped image, browser regressions, and version consistency. Owner-approved CLI submission was separately activated on 2026-10-18; follow [the active procedure](../../docs/owner-cli-acceptance.md), requiring explicit approval of the exact commit. All CI and reviewer changes remain deferred; preserve current checks and protected acceptance.
