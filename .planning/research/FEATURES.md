# Feature Landscape: v2.2 Skip Unreleased Media

**Domain:** Skip-unreleased-media filtering for Radarr/Sonarr search automation
**Researched:** 2026-03-09
**Confidence:** HIGH -- feature is narrow in scope, Radarr API fields verified, existing codebase pattern is clear

## Context

Triggarr v2.1 searches for all wanted/missing and cutoff-unmet items in Radarr/Sonarr. For Sonarr, `filter_sonarr_episodes()` already skips unaired episodes (engine.py:145-173). For Radarr, there is **no equivalent filter** -- movies still in theaters (with only `inCinemas` dates) get searched, which can result in cam recordings being grabbed.

v2.2 adds a configurable toggle to skip unreleased media, primarily targeting Radarr movies without a past digital or physical release date.

---

## Table Stakes

Features users expect. Missing = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Global `skip_unreleased` toggle in settings | Users expect a single on/off switch matching existing toggle pattern (per-app enable/disable, hard max, etc.) | Low | Add `skip_unreleased: bool = True` to `GeneralConfig`. Follows existing checkbox UI pattern in settings.html |
| Skip Radarr movies without a past digital/physical release date | Core problem: searching movies only in theaters yields cam recordings. This is the entire point of the feature | Med | New `filter_radarr_movies()` function parallel to existing `filter_sonarr_episodes()`. Check `digitalRelease` and `physicalRelease` fields on movie dicts from wanted/missing API response |
| Sonarr unaired-episode filtering (already exists) | Users expect unaired episodes to be skipped | None | **Already built.** `filter_sonarr_episodes()` at engine.py:145-173 checks `airDateUtc` against current UTC time. Skips episodes with no air date or future air date. Zero work needed |
| Log skipped items so users understand why counts changed | Users will be confused if item counts drop without explanation | Low | Add unreleased-skip count to existing cycle diagnostic log line. Pattern: `"{searched} searched, {skipped} skipped"` becomes `"{searched} searched, {unreleased} unreleased-skipped, {skipped} failed"` |
| Settings UI toggle for the feature | Must be configurable from the web UI, not just TOML editing | Low | Add checkbox in General section of settings.html. Wire through `save_settings()` form handling in routes.py |
| TOML config persistence for the toggle | Setting must survive restarts | Low | Automatic -- existing `save_settings()` writes all `GeneralConfig` fields to TOML. Just add the field |

## Differentiators

Features that set product apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Dashboard indicator showing unreleased-skip counts | "3 unreleased skipped" on app cards shows the feature is actively working | Low | Add `unreleased_skipped` to app_state dict alongside existing `missing_count`/`cutoff_count`. Display in `app_card.html` partial. **Recommendation: build this.** Low effort, high visibility |
| Per-app skip-unreleased override | Allow Radarr skip but Sonarr pass-through (or vice versa) | Low | Add `skip_unreleased` to `ArrConfig`. **Recommendation: do NOT build.** Sonarr already filters by air date unconditionally. The global toggle only controls Radarr in practice. Per-app adds config noise for zero real benefit |
| Configurable release-date offset (skip until N days after release) | Buffer period to wait for higher-quality rips after digital release | Med | `skip_unreleased_delay_days: int = 0` in config. **Recommendation: defer.** Radarr's own quality profiles and availability delays handle this already. Triggarr should not duplicate Radarr's job |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Fetching release dates from TMDB directly | Radarr already syncs dates from TMDB and exposes them via API. Adding TMDB calls duplicates work, adds an API key requirement, and creates data consistency problems | Use date fields already present in Radarr's API response (`digitalRelease`, `physicalRelease`, `inCinemas`) |
| Per-movie override (force-search specific unreleased movie) | Adds per-item state management, a new UI surface, and complexity far beyond a simple toggle | Users can disable the toggle globally, trigger a manual search, then re-enable. Or set the movie's minimum availability in Radarr itself |
| Separate "skip cam" vs "skip unreleased" modes | These are the same problem. A movie without a digital/physical release date that is "in cinemas" is exactly the cam-risk scenario | Single toggle covers both cases |
| Querying Radarr's `minimumAvailability` per movie | Radarr has its own per-movie availability setting (announced/inCinemas/released/preDB). Its wanted/missing endpoint already filters based on this. Triggarr's filter is an additional safety layer, not a replacement | Filter purely on date fields. Radarr's `minimumAvailability` is Radarr's concern |
| Making Sonarr's air-date filter conditional on the toggle | `filter_sonarr_episodes()` already runs unconditionally. Searching for literally-unaired episodes is always wrong (the file cannot exist yet). This is not a preference | Keep Sonarr air-date filtering unconditional. The toggle only controls the new Radarr release-date filter |

---

## Feature Dependencies

```
Existing: filter_sonarr_episodes() -- already skips unaired episodes (NO CHANGE NEEDED)
Existing: filter_monitored() -- filters unmonitored items (NO CHANGE NEEDED)

New: GeneralConfig.skip_unreleased (bool, default True)
    |
    +-- Required by: settings.html toggle (UI)
    +-- Required by: save_settings() form handling (routes.py)
    +-- Required by: filter_radarr_movies() conditional call
    |
New: filter_radarr_movies(movies: list[dict]) -> list[dict]
    |   - Parallel to existing filter_sonarr_episodes()
    |   - Checks digitalRelease and physicalRelease date fields
    |   - Returns only movies where at least one release date is in the past
    |
    +-- Required by: run_radarr_cycle() -- conditional call after filter_monitored()
    +-- Required by: Dashboard skip-count logging
```

**Critical dependency:** The Radarr wanted/missing API must return `digitalRelease` and `physicalRelease` fields in its movie records. Verified: the Radarr `/api/v3/wanted/missing` endpoint returns full movie resource objects which include these nullable datetime fields.

---

## Edge Cases and Design Decisions

### Edge Case 1: Movie with no release dates at all (all three null)
**Scenario:** Movie added to Radarr from a list or manual add, TMDB has no date info.
**Decision:** Skip it when `skip_unreleased=True`. No dates = no evidence it is released.
**Confidence:** HIGH -- safe default. User can disable toggle temporarily if needed.

### Edge Case 2: Movie with only `inCinemas` date in the past
**Scenario:** Movie is in theaters, no digital/physical date set yet in TMDB.
**Decision:** Skip it. This is exactly the cam-risk scenario and the primary use case for the feature.
**Confidence:** HIGH -- the whole point of the feature.

### Edge Case 3: Movie with `digitalRelease` date that just passed (today)
**Scenario:** Digital release today. Streaming platforms often go live at midnight PT/ET, not UTC.
**Decision:** Use simple UTC `date <= now` comparison. Do NOT add timezone sophistication. Radarr stores dates in UTC. A few hours of discrepancy is irrelevant -- Triggarr cycles every 30 minutes by default, so the movie will be picked up on the next cycle.
**Confidence:** HIGH -- same approach as existing `filter_sonarr_episodes()`.

### Edge Case 4: Movie becomes released mid-cycle
**Scenario:** Between fetching the wanted list and triggering searches, a movie's release date passes.
**Decision:** Not a real problem. Filter runs on fetched data. Movie gets skipped this cycle, picked up next cycle (30 min). Round-robin self-heals.
**Confidence:** HIGH.

### Edge Case 5: Only one of `digitalRelease`/`physicalRelease` is set
**Scenario:** Streaming-first releases often have no physical date (common).
**Decision:** If either `digitalRelease` or `physicalRelease` is in the past, the movie is released. Only skip when both are null or both are in the future. This matches how Radarr itself handles availability since the issue #4460 fix.
**Confidence:** HIGH.

### Edge Case 6: User has `skip_unreleased=True` but Radarr's minimumAvailability is "announced"
**Scenario:** User told Radarr "grab anything announced" but Triggarr skips unreleased.
**Decision:** Triggarr's filter wins. The user explicitly enabled `skip_unreleased` in Triggarr. If they want to search announced movies, they disable the toggle. Triggarr is an independent filter layer, not a proxy for Radarr settings.
**Confidence:** HIGH.

### Edge Case 7: Toggle changed while a cycle is running
**Scenario:** User disables `skip_unreleased` via settings UI mid-cycle.
**Decision:** No special handling needed. Settings are read at cycle start. Next cycle uses new setting. This matches existing behavior for all other settings changes.
**Confidence:** HIGH -- follows established pattern.

### Edge Case 8: Cutoff-unmet items that are unreleased
**Scenario:** A movie is in the cutoff-unmet list (has a file but below quality cutoff) but is technically unreleased (only in cinemas). Rare but possible if user grabbed a cam.
**Decision:** Apply the same filter to cutoff-unmet items. If the movie is unreleased, do not search for an upgrade -- a better version is not available yet either.
**Confidence:** HIGH.

---

## Radarr API Date Fields (Research Findings)

The Radarr `/api/v3/wanted/missing` and `/api/v3/wanted/cutoff` endpoints return full movie resource objects. Each movie includes these date fields:

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `inCinemas` | ISO 8601 datetime string | Yes | Theatrical release date. Can be null for direct-to-streaming titles |
| `digitalRelease` | ISO 8601 datetime string | Yes | Digital/streaming release date. Often null until close to release |
| `physicalRelease` | ISO 8601 datetime string | Yes | Physical media (Blu-ray/DVD) release date. Often null for streaming-first titles |
| `status` | string enum | No | One of: `tba`, `announced`, `inCinemas`, `released`, `deleted` |

**Key insight:** The `status` field reflects Radarr's own determination of release state, but it uses complex fallback logic (issue #9849) that sometimes marks movies as "released" prematurely when TMDB data is incomplete. Triggarr should filter on the actual date fields, not the `status` enum, because:
1. Date fields are objective (either set or null, either past or future)
2. The `status` field's fallback logic can produce surprising results
3. Filtering on dates is the same approach used by `filter_sonarr_episodes()` for consistency

**Confidence:** MEDIUM on exact field nullability behavior (verified from multiple API wrappers and GitHub issues, but not from a live API call). HIGH on the fields existing and being datetime strings.

---

## MVP Recommendation

Build in this order:

1. **Config model change** -- Add `skip_unreleased: bool = True` to `GeneralConfig` in `models/config.py`
2. **Settings UI** -- Add checkbox toggle in General section of `settings.html`, wire through `save_settings()` in `routes.py`
3. **Filter function** -- Add `filter_radarr_movies()` to `search/engine.py`, parallel to `filter_sonarr_episodes()`
4. **Wire into cycle** -- Call `filter_radarr_movies()` in `run_radarr_cycle()` when `settings.general.skip_unreleased` is True, after `filter_monitored()`. Add unreleased-skip count to log diagnostic
5. **Tests** -- Unit tests for `filter_radarr_movies()` covering all edge cases, integration test for cycle with toggle on/off
6. **Dashboard indicator** (stretch) -- Show unreleased-skip count on app cards

Defer:
- Per-app toggle: Sonarr already filters unconditionally; global toggle is sufficient
- Release-date offset: Radarr handles this natively
- Per-movie overrides: Too complex for the value

---

## Implementation Complexity Assessment

| Component | Complexity | Existing Pattern | Files Changed |
|-----------|-----------|-----------------|---------------|
| Config model (`skip_unreleased` field) | Low | Copy `hard_max_per_cycle` pattern | `models/config.py` |
| TOML persistence | Low | Automatic via existing `save_settings` | `web/routes.py` (add form field) |
| Settings UI toggle | Low | Copy existing checkbox pattern (enabled toggle) | `templates/settings.html` |
| `filter_radarr_movies()` function | Med | Parallel to `filter_sonarr_episodes()` | `search/engine.py` |
| Wire into `run_radarr_cycle()` | Low | Add conditional call after `filter_monitored()` | `search/engine.py` |
| Dashboard skip indicator | Low | Add to `_build_app_context()` and `app_card.html` | `web/routes.py`, template |
| Tests | Med | Follow `test_engine.py` patterns | `tests/test_engine.py` |
| **Total estimate** | **Med** | Well-precedented throughout | **~6 files** |

**Zero new dependencies.** All achievable with existing stack (datetime parsing, Pydantic config, Jinja2 templates).

---

## Sources

### HIGH Confidence
- Existing `filter_sonarr_episodes()` implementation: `triggarr/search/engine.py:145-173` -- verified by direct code reading
- Existing config model and settings UI patterns: `triggarr/models/config.py`, `triggarr/templates/settings.html` -- verified by direct code reading
- Radarr movie date fields (`inCinemas`, `digitalRelease`, `physicalRelease`): [ArrAPI documentation](https://arrapi.kometa.wiki/en/latest/radarr.html), [pycliarr API docs](https://pycliarr.readthedocs.io/en/stable/_modules/pycliarr/api/radarr.html)

### MEDIUM Confidence
- Radarr `status` enum values (tba/announced/inCinemas/released/deleted): [Radarr issue #5002](https://github.com/Radarr/Radarr/issues/5002)
- Radarr minimumAvailability options (announced/inCinemas/released/preDB): [Servarr Wiki - Radarr Settings](https://wiki.servarr.com/radarr/settings)
- Radarr digital-release-only movies fixed to show as "released": [Radarr issue #4460](https://github.com/Radarr/Radarr/issues/4460)
- Movies showing as "missing" before release due to fallback logic: [Radarr issue #9849](https://github.com/Radarr/Radarr/issues/9849)
- Radarr fallback to digital release date discussion: [Radarr issue #5647](https://github.com/Radarr/Radarr/issues/5647)

---
*Feature research for: Triggarr v2.2 skip-unreleased-media*
*Researched: 2026-03-09*
