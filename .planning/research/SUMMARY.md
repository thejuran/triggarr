# Project Research Summary

**Project:** Triggarr v2.2 -- Skip Unreleased Media
**Domain:** Release-date filtering for Radarr/Sonarr search automation
**Researched:** 2026-03-09
**Confidence:** HIGH

## Executive Summary

Triggarr v2.2 is a narrowly-scoped feature addition: a single boolean toggle (`skip_unreleased`) that prevents the search engine from triggering searches on Radarr movies that have no past digital or physical release date. This avoids grabbing cam recordings for movies still only in theaters. The Sonarr side already filters unaired episodes unconditionally via `filter_sonarr_episodes()`, so no Sonarr logic changes are needed -- the toggle controls Radarr filtering only. Zero new dependencies are required; the entire feature is built with Python stdlib `datetime`, existing Pydantic config patterns, and existing Jinja2/htmx UI patterns.

The recommended approach is a pure filter function (`filter_unreleased_movies()`) inserted into the Radarr search pipeline after `filter_monitored()` and before `slice_batch()`. This mirrors the existing Sonarr filter architecture. The filter checks `digitalRelease` and `physicalRelease` fields from the Radarr API response -- `inCinemas` is deliberately excluded because theatrical-only availability means only cam copies exist. The filter applies ONLY to the missing queue, NOT the cutoff-unmet queue (cutoff items already have a downloaded file and are provably released).

The primary risk is the null-date edge case: movies where both `digitalRelease` and `physicalRelease` are null. Research produced two conflicting recommendations. STACK.md and FEATURES.md recommend skipping null-date movies (assume unreleased). PITFALLS.md recommends searching null-date movies (assume released, safe default). **The correct answer is PITFALLS.md's approach: when dates are unknown, search anyway.** Silent filtering of movies with incomplete metadata creates invisible data loss -- the worst failure mode. The filter should only skip movies where a date IS present AND is in the future. A secondary risk is the dashboard "X of Y" display becoming misleading after filtering reduces the effective queue size; this should be addressed by tracking eligible counts separately.

## Key Findings

### Recommended Stack

No stack changes. Zero new dependencies. Everything needed is already present in the codebase.

**Core technologies (all existing):**
- Python stdlib `datetime` -- ISO 8601 parsing and UTC comparison, already used in `filter_sonarr_episodes()`
- Pydantic `GeneralConfig` -- one new `bool` field (`skip_unreleased = True`), follows existing pattern
- Jinja2/htmx -- checkbox toggle in settings UI, identical to existing enable/disable toggles

### Expected Features

**Must have (table stakes):**
- Global `skip_unreleased` toggle in settings UI and TOML config
- Filter Radarr movies without a past digital/physical release date (missing queue only)
- Log skipped-item counts so users understand why search counts changed
- Settings persistence through save/reload cycle (three-location update: model, template, route)

**Should have (differentiators):**
- Dashboard indicator showing unreleased-skip counts on app cards (low effort, high visibility)

**Defer:**
- Per-app skip-unreleased override (Sonarr already filters unconditionally; adds config noise for zero benefit)
- Configurable release-date offset/delay (Radarr handles this natively via quality profiles)
- Per-movie force-search overrides (too complex; users can toggle globally and use manual search)

### Architecture Approach

The filter is a pure function (`filter_unreleased_movies()`) that takes a list of movie dicts and returns only those with at least one past release date. It sits in the pipeline after `filter_monitored()` and before `slice_batch()`, ensuring batch sizes remain predictable and cursors operate on the filtered list. The existing `filter_sonarr_episodes()` remains unchanged and unconditional -- it already handles Sonarr's equivalent filtering. Config integration touches three files: `models/config.py` (field), `templates/settings.html` (checkbox), `web/routes.py` (form parsing).

**Major components:**
1. `filter_unreleased_movies()` + `_has_past_date()` in `search/engine.py` -- pure filter function, no side effects
2. `GeneralConfig.skip_unreleased` in `models/config.py` -- boolean toggle, default True
3. Settings UI checkbox in `settings.html` + form handling in `routes.py` -- three-location config pattern

### Critical Pitfalls

1. **Null dates treated as unreleased (silent data loss)** -- Movies with no metadata dates get silently filtered forever. Fix: search when dates are unknown, only skip when a date IS present AND is in the future. Log null-date items at debug level.
2. **Filter applied to cutoff-unmet queue** -- Cutoff items already have files (provably released). Applying release-date filter would incorrectly skip upgrades for movies with incomplete metadata. Fix: filter missing queue only.
3. **Dashboard "X of Y" becomes misleading** -- Raw `missing_count` stays at unfiltered total while cursor operates on filtered list. Fix: track and display eligible count separately.
4. **Settings save drops new field** -- The `save_settings` route manually picks form fields. Missing the new field causes it to silently revert to default on any settings save. Fix: update all three locations (model, template, route) and test the round-trip.
5. **Sonarr double-filtering risk** -- Adding a second Sonarr filter with different logic could cause subtle bugs. Fix: leave Sonarr filtering completely untouched; the toggle controls Radarr only.

## Implications for Roadmap

Based on research, this is a 3-phase feature with clear dependency ordering.

### Phase 1: Config and Filter Function

**Rationale:** Everything depends on the config field existing and the filter function being correct. This is the foundation. Pure functions are fully testable without integration concerns.
**Delivers:** `skip_unreleased` config field, `filter_unreleased_movies()` function, `_has_past_date()` helper, comprehensive unit tests covering all edge cases (null dates, future dates, past dates, mixed, malformed).
**Addresses:** Core table-stakes feature (Radarr release-date filtering), config model addition, TOML template update.
**Avoids:** Null-date silent filtering (Pitfall 1), cutoff-queue misapplication (Pitfall 4).

### Phase 2: Engine Integration and Settings UI

**Rationale:** With the filter function tested, wire it into the search pipeline and make it configurable from the UI. These are coupled -- the filter must be conditional on the setting, and the setting must be saveable.
**Delivers:** Conditional filter call in `run_radarr_cycle()` (missing queue only), debug/info logging for filtered counts, settings UI checkbox, form save/load round-trip.
**Addresses:** Settings UI toggle (table stakes), log transparency (table stakes), three-location config pattern.
**Avoids:** Filter placed after `slice_batch()` (anti-pattern), settings save dropping the field (Pitfall 8), cursor reset temptation (Pitfall 11).

### Phase 3: Dashboard and Polish

**Rationale:** With the core feature working, address the UX gap in dashboard display and add the skip-count indicator.
**Delivers:** Eligible-count tracking in app state, updated "X of Y" display, unreleased-skip count on app cards, integration tests for full cycle with toggle on/off.
**Addresses:** Dashboard indicator (differentiator), "X of Y" confusion (Pitfall 3).
**Avoids:** Over-engineering performance (Pitfall 12).

### Phase Ordering Rationale

- Phase 1 before Phase 2 because the filter function must exist and be tested before it can be wired into the engine.
- Phase 2 before Phase 3 because the dashboard changes depend on the filter being active and producing skip counts.
- Sonarr is deliberately excluded from all phases -- its filtering is already implemented and unconditional.
- The cutoff queue is deliberately excluded from filtering in all phases -- cutoff items are provably released.

### Research Flags

Phases with standard patterns (skip phase research):
- **Phase 1:** Pure function, established date-parsing pattern from `filter_sonarr_episodes()`, well-documented Radarr API fields.
- **Phase 2:** Follows existing config/UI patterns exactly (checkbox toggle, form parsing, conditional filter call).
- **Phase 3:** Follows existing app-state and template patterns.

No phases need deeper research. This is a well-precedented feature addition following established codebase patterns throughout.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new dependencies; all patterns verified in existing codebase |
| Features | HIGH | Narrow scope, clear table stakes vs. defer decisions, edge cases thoroughly analyzed |
| Architecture | HIGH | Pipeline insertion point verified via direct codebase analysis; cursor behavior confirmed safe |
| Pitfalls | HIGH | Pitfalls derived from codebase analysis and Radarr API field verification; community issues confirm edge cases |

**Overall confidence:** HIGH

### Gaps to Address

- **Null-date behavior must be decided definitively at implementation time.** Research files disagree (STACK.md says skip, PITFALLS.md says search). Recommendation: follow PITFALLS.md (search when uncertain). Validate against a live Radarr instance to see how common null-date movies are in practice.
- **Radarr `status` field usage.** STACK.md says ignore it entirely; PITFALLS.md says use it as a fallback (if `status == "released"`, search even if dates are null). Recommendation: use dates only for simplicity, but log `status` at debug level for future analysis. Do not add `status` checks in v2.2.
- **Dashboard eligible-count display.** The exact UI treatment (replace "X of Y" vs. show both raw and eligible) should be decided during Phase 3 planning based on available template space.

## Sources

### Primary (HIGH confidence)
- Triggarr codebase (v2.1): `search/engine.py`, `models/config.py`, `web/routes.py`, `templates/settings.html`, `state.py` -- direct code analysis
- Radarr `MovieResource.cs`: https://github.com/Radarr/Radarr/blob/develop/src/Radarr.Api.V3/Movies/MovieResource.cs
- Sonarr `EpisodeResource.cs`: https://github.com/Sonarr/Sonarr/blob/develop/src/Sonarr.Api.V3/Episodes/EpisodeResource.cs
- Radarr API docs: https://radarr.video/docs/api/

### Secondary (MEDIUM confidence)
- Radarr status/date mismatches: GitHub issues #4460, #4920, #5647, #9849
- Radarr JSON naming convention: Go client struct tags (third-party confirmation)
- pyarr/pycliarr/ArrAPI documentation (third-party API wrappers confirming field names)

---
*Research completed: 2026-03-09*
*Ready for roadmap: yes*
