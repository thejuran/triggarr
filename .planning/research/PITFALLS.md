# Domain Pitfalls

**Domain:** Adding release-date filtering to existing search automation pipeline (v2.2)
**Researched:** 2026-03-09
**Confidence:** HIGH (pitfalls derived from direct codebase analysis of engine.py, state.py, and app_card.html; Radarr API fields verified against OpenAPI spec and community sources; Sonarr filtering verified against existing filter_sonarr_episodes implementation)

---

## Critical Pitfalls

Mistakes that cause incorrect filtering, cursor corruption, or silent data loss.

### Pitfall 1: Null/Missing Release Date Fields in Radarr API -- Silent Search Blackhole

**What goes wrong:** Radarr movie objects have three nullable date fields: `digitalRelease`, `physicalRelease`, and `inCinemas`. Any or all can be `null`. A movie might have `inCinemas` set but `digitalRelease` and `physicalRelease` both null (theatrical-only, no home release date announced yet). If the filter treats "no date" as "unreleased," those movies NEVER get searched -- even if they have been released for months and Radarr simply lacks the metadata.

**Why it happens:** Radarr sources release dates from TMDb/external metadata. New, obscure, or independent movies frequently have incomplete data. A movie can sit in "announced" status with zero date fields populated. Direct-to-streaming movies may have only `digitalRelease` set. Foreign films may have only `inCinemas`. The developer tests with well-known movies (complete metadata) and misses the null-date edge case.

**Consequences:** The worst failure mode: invisible data loss. The user adds a movie, Radarr lacks metadata, and Triggarr silently never searches for it. The user has no way to know why the movie is not being searched. It does not appear in any log or error -- it is simply filtered out.

**Prevention:** Treat "no release date available" as "eligible for search" (do NOT skip). The filter should only skip items where a date IS present AND is in the future. The safe default: if we cannot determine the release status, search anyway. This matches the principle of least surprise -- the filter should prevent searching for things we KNOW are unreleased, not things we are uncertain about.

**Detection:** Log a debug-level count per cycle: `"Radarr: 5 items with no release date (searched anyway)"`. If this number is consistently high, it is a metadata issue in Radarr, not a Triggarr problem.

**Phase:** Core implementation phase -- the filter function must handle this from day one.

---

### Pitfall 2: Radarr `status` Field vs. Actual Release Dates Disagree

**What goes wrong:** Radarr has a `status` field with enum values `announced`, `inCinemas`, and `released`. It also has three date fields (`inCinemas`, `digitalRelease`, `physicalRelease`). These can disagree. A movie might have `status: "released"` but `digitalRelease: null` and `physicalRelease: null` (only `inCinemas` in the past). Filtering on dates alone would incorrectly skip this movie. Filtering on status alone might search movies that are "inCinemas" but have no digital/physical release (cam risk -- the whole point of the feature).

**Why it happens:** Radarr calculates `status` from its "Minimum Availability" setting and available dates. The status transitions automatically. Direct-to-VOD movies are a known source of status/date mismatches (GitHub issues #4460, #4920). A movie can be `status: "released"` with no `digitalRelease` or `physicalRelease` if the only date that has passed is `inCinemas`.

**Consequences:** Using status alone: might search movies still only in cinemas (cam recordings). Using dates alone: might skip movies that Radarr considers released. Either approach alone has edge cases where the user gets exactly what the feature was designed to prevent.

**Prevention:** Use a combined check. A movie is "released enough to search" if ANY of: (a) `status == "released"`, (b) `digitalRelease` is in the past, (c) `physicalRelease` is in the past. Only skip when ALL available evidence says the movie is unreleased (no dates in the past AND status is not "released"). When in doubt, search. The feature is about preventing obvious cases (searching for a movie announced 6 months from now), not being a perfect release-date oracle.

**Phase:** Core implementation phase -- the filter logic design decision.

---

### Pitfall 3: "X of Y" Dashboard Counts Become Misleading

**What goes wrong:** The dashboard currently shows `{{ app.missing_cursor }} of {{ app.missing_count }}` where `missing_count` is the RAW count from the API (set at engine.py line 220 BEFORE `filter_monitored()` runs). After adding the release-date filter, the cursor indexes a shorter filtered list, but `missing_count` still reflects the unfiltered total. Users see "3 of 50" but 20 of those 50 are unreleased and will never be searched -- the effective queue is only 30 items.

**Why it happens:** `state["radarr"]["missing_count"] = len(missing)` is intentionally set before filtering to show the raw API count. With one filter layer (`filter_monitored`), the gap was small (most items are monitored). Adding a second filter layer for release dates makes the gap much larger and the display actively confusing.

**Consequences:** Users think progress is slower than it is. "3 of 50" suggests 10 cycles to complete a pass at batch_size=5, but it actually takes 6 (30 eligible items). Users may increase batch sizes or shorten intervals, hammering indexers unnecessarily.

**Prevention:** Track both raw and filtered counts in AppState. Add `missing_eligible` (or similar) that reflects the post-filter count. Update `app_card.html` to show cursor position relative to the eligible count. The raw count can remain as context (e.g., tooltip or secondary display). The cursor must be "X of eligible," not "X of total."

**Phase:** UI/dashboard update phase -- can follow core filter implementation but should not be deferred past the milestone.

---

### Pitfall 4: Applying the Release-Date Filter to the Cutoff Queue

**What goes wrong:** The cutoff-unmet queue contains movies that HAVE files but at insufficient quality. These movies are, by definition, already released (they have been downloaded at least once). Applying the "skip unreleased" filter to the cutoff queue would incorrectly skip movies whose date fields happen to be null despite already being released and downloaded.

**Why it happens:** The filter is implemented as a function and the developer applies it uniformly to both missing and cutoff processing. It feels consistent. But the cutoff queue has a fundamentally different semantic: these items have been found and downloaded; they just need better quality.

**Consequences:** Movies in the cutoff queue with incomplete metadata (null `digitalRelease`, `physicalRelease`) get filtered out and never upgraded. The user sees the cutoff count but progress stalls for those items.

**Prevention:** Only apply the release-date filter to the MISSING queue. The cutoff queue must NOT be filtered by release date. The `inCinemas` date check is also wrong for cutoff items -- a movie could be upgrading from a web-dl while still in cinemas. Cutoff items have proven they are available.

**Phase:** Core implementation phase -- must scope the filter correctly from the start.

---

## Moderate Pitfalls

### Pitfall 5: Sonarr Already Filters by Air Date -- Double-Filtering Risk

**What goes wrong:** The existing `filter_sonarr_episodes()` function (engine.py lines 145-173) already filters out episodes with future `airDateUtc` or no air date. Adding a separate "skip unreleased" filter for Sonarr would be redundant. The PROJECT.md says "skip Sonarr episodes that haven't aired yet" -- but this is already implemented.

**Why it happens:** The v2.2 feature spec was written without accounting for the existing filter. The feature request describes behavior that already exists for Sonarr.

**Consequences:** If a second filter is added with slightly different logic (e.g., different datetime comparison, different null handling), the two filters could disagree, causing subtle bugs. At best, it doubles the work with zero benefit.

**Prevention:** Recognize that Sonarr episode air-date filtering is ALREADY DONE and unconditional. The "skip unreleased" toggle should control ONLY the Radarr release-date filter. For Sonarr, the existing `filter_sonarr_episodes()` should remain unchanged and not gated behind the toggle. Document this in the code: the toggle is Radarr-specific because Sonarr already handles this.

**Phase:** Core implementation phase -- critical to recognize before writing code.

---

### Pitfall 6: Cursor Position Drift When Filtered List Changes Between Cycles

**What goes wrong:** The cursor is an index into the filtered list. Between cycle N and cycle N+1, a movie's release date gets added in Radarr (metadata refresh). The movie moves from "unreleased" to "released," changing the filtered list composition. The cursor still points to the same integer index, but that index now refers to a different movie. Some movies may be searched twice while others are skipped.

**Why it happens:** This is inherent to index-based cursors over volatile lists. It already happens today when users add/remove movies in Radarr between cycles. The release-date filter adds another source of list volatility.

**Consequences:** Minor fairness degradation. Some items get double-searched, others wait an extra cycle. The round-robin still guarantees eventual complete coverage.

**Prevention:** This does NOT need fixing. The existing `slice_batch()` wrap-around logic handles list changes gracefully. Items are never permanently skipped -- the cursor wraps and covers everything within one pass. The temptation to "fix" this by switching to ID-based cursors would be a major refactor with its own edge cases (deleted items, ID gaps). Resist.

**Phase:** N/A -- accept as existing behavior. Document in code comments.

---

### Pitfall 7: Timezone and Date Boundary Edge Cases

**What goes wrong:** Radarr stores dates as ISO 8601 UTC (e.g., `"2026-03-15T00:00:00Z"`). A movie "released March 15" means midnight UTC on March 15. For US users, this is 5pm-7pm on March 14 in their local time. The filter would consider this movie "released" when it is not yet March 15 locally. Conversely, a movie released "March 15" in Australia would be March 14 in UTC.

**Why it happens:** Release dates are inherently timezone-ambiguous. There is no single correct moment when a movie becomes "released."

**Consequences:** Minor: movies become searchable a few hours early or late relative to the user's local expectation. Not practically harmful -- the round-robin will get to them eventually regardless.

**Prevention:** Use the same simple comparison as the existing `filter_sonarr_episodes()`: compare `release_date > now` using UTC `datetime.now(UTC)`. Anything past midnight UTC is eligible. This is good enough -- a 24-hour ambiguity on release dates is irrelevant for a tool that searches on a 30-minute cycle. Do NOT add timezone configuration or local time handling.

**Phase:** Core implementation phase -- simple, just be deliberate about UTC.

---

### Pitfall 8: Config Toggle Not Round-Tripped Through Settings Save

**What goes wrong:** Adding `skip_unreleased: bool = True` to the Pydantic config model is straightforward (defaults handle missing TOML keys). But the `save_settings` route in routes.py manually constructs a config dict from form data (lines 270-300). If the new field is not read from the form and written to the dict, it gets silently dropped to its default value every time the user saves any settings.

**Why it happens:** The settings save route does not use a generic "serialize model" approach -- it manually picks form fields. Every new config field requires updates in THREE places: (1) the Pydantic model, (2) the settings.html template (form input), (3) the save_settings route (form parsing). Missing any one causes silent data loss.

**Consequences:** User enables skip_unreleased=False (they want to search everything). User changes an unrelated setting (e.g., search interval). The save route drops skip_unreleased, which reverts to the default (True). Now unreleased items are being skipped when the user explicitly disabled that behavior.

**Prevention:** Update all three locations: `GeneralConfig` model (add field with default), `settings.html` template (add toggle UI), `save_settings` route (read from form, write to config dict). Test the round-trip explicitly: change the toggle, save, reload the page, verify the value persisted.

**Phase:** Config/settings phase -- straightforward but the three-location pattern must not be overlooked.

---

### Pitfall 9: Items Transitioning from Unreleased to Released Between Cycles

**What goes wrong:** A movie is unreleased at cycle N and filtered out. At cycle N+1, its release date has passed and it enters the filtered list. But it enters at some position in the sorted list. If the cursor has already passed that position, the movie is not searched until the next full pass (cursor wrap-around).

**Why it happens:** The round-robin cursor only advances forward. New items entering behind the cursor wait for the next pass. This is existing behavior for newly-added movies, but the release-date filter makes it more visible -- the user knows exactly when the movie became eligible and notices the delay.

**Consequences:** For a library of 100 eligible items with batch_size=5 and 30-minute intervals, a full pass takes 10 hours. A movie that becomes eligible just after the cursor passes its position waits up to 10 hours.

**Prevention:** This is acceptable and should NOT be "fixed" with priority queuing. Priority logic would break the round-robin simplicity and create edge cases worse than the symptom. Document this behavior. Point users to the "Search Now" button for immediate coverage of newly-released items.

**Phase:** Documentation phase.

---

### Pitfall 10: Log Messages Do Not Explain Where Filtered Items Went

**What goes wrong:** The cycle diagnostic log says `"50 fetched, 3 searched, 0 skipped"` but the user wonders where the other 47 items went. The existing "skipped" counter counts search failures (exceptions), not filtered-out items. There is no indication that items were filtered due to release dates.

**Why it happens:** The filter runs silently. `filter_monitored()` does not log its effect. Adding another silent filter compounds the opacity.

**Prevention:** Add a single INFO-level log line per cycle when items are filtered: `"Radarr: 20 unreleased items filtered (skip_unreleased=true)"`. This appears once per cycle, not per item. Include the count in the diagnostic summary: `"50 fetched, 20 unreleased, 30 eligible, 3 searched, 0 failed"`.

**Phase:** Core implementation phase -- add alongside the filter logic.

---

## Minor Pitfalls

### Pitfall 11: Temptation to Reset Cursors When Toggle Changes

**What goes wrong:** User enables skip_unreleased. The developer thinks "the filtered list is now different, I should reset cursors to 0 to start fresh." But resetting cursors causes items at the beginning of the list to be re-searched immediately, even if they were just searched in the previous cycle.

**Prevention:** Do NOT reset cursors when the toggle changes. The cursor-pointing-to-a-different-item effect is identical to what happens when movies are added/removed from Radarr. The existing `slice_batch()` wrap-around handles this. Resetting cursors is always worse than letting the wrap-around handle it naturally.

**Phase:** Config/settings phase -- resist the urge.

---

### Pitfall 12: Performance Over-Engineering for Date Comparisons

**What goes wrong:** Developer adds caching, pre-computation, or a "released items cache" to avoid parsing dates on every cycle. This adds complexity (cache invalidation, stale cache bugs) for zero practical benefit.

**Prevention:** `datetime.fromisoformat()` in CPython 3.11+ is C-implemented and handles ~1M parses/second. Even 10,000 movies with 3 date fields = 30,000 parses = ~30ms. The HTTP fetch to Radarr takes 100-500ms. Keep the filter simple, stateless, and re-computed every cycle. No caching needed.

**Phase:** N/A -- just avoid over-engineering.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Filter function | Null dates treated as "unreleased" (Pitfall 1) | Default to "search" when dates missing |
| Filter function | Status vs. date disagreement (Pitfall 2) | Combined check: status OR dates |
| Filter function | Applied to cutoff queue (Pitfall 4) | Missing queue only |
| Filter function | Redundant Sonarr filtering (Pitfall 5) | Radarr-only; Sonarr already handled |
| Filter function | Silent operation (Pitfall 10) | Log filtered count per cycle |
| Dashboard UI | "X of Y" confusing (Pitfall 3) | Track eligible count separately |
| Config/settings | Save route drops new field (Pitfall 8) | Update model + template + route |
| Config/settings | Cursor reset temptation (Pitfall 11) | Do not reset |
| Testing | Incomplete null-date coverage | Test: all dates null, only inCinemas, status="released" with no dates, status="announced" with past digitalRelease |

---

## Integration Pitfalls with Existing Systems

| Integration Point | Pitfall | Prevention |
|-------------------|---------|------------|
| `filter_monitored()` pipeline | New filter placed AFTER `slice_batch()` instead of before | Insert filter between `filter_monitored()` and `slice_batch()` calls |
| `state["radarr"]["missing_count"]` | Raw count no longer meaningful as "queue size" | Add `missing_eligible` to AppState for post-filter count |
| `deduplicate_to_seasons()` (Sonarr) | Release filter applied to episodes AFTER deduplication (seasons have no air date) | Not needed -- Sonarr already filters by air date before this step |
| Search history `insert_search_entry()` | No record of WHY an item was not searched (filtered vs. not in batch) | Log filtered count; do NOT add history entries for filtered items |
| Tracking/correlation (`tracking.py`) | Filtered items still have old search history entries that get correlated | Not a problem -- correlation only looks at entries with outcome="searched" |
| `cap_batch_sizes()` hard max | Hard max calculated against pre-filter batch sizes | Hard max applies to requested batch size, not filtered list size -- no change needed |
| `app_card.html` template | Cursor shows position in filtered list but count shows unfiltered total | Update template to use eligible count for "of Y" |

---

## Sources

- Radarr API documentation: [Radarr API Docs](https://radarr.video/docs/api/)
- Radarr MovieStatusType enum: [pyarr Radarr models](https://docs.totaldebug.uk/pyarr/models/radarr.html) -- `announced`, `inCinemas`, `released` (HIGH confidence)
- Direct-to-VOD status/date mismatches: [Radarr Issue #4460](https://github.com/Radarr/Radarr/issues/4460), [Radarr Issue #4920](https://github.com/Radarr/Radarr/issues/4920) (HIGH confidence -- official issue tracker)
- Release date metadata gaps: [Radarr Issue #8944](https://github.com/Radarr/Radarr/issues/8944) (MEDIUM confidence)
- Radarr release date fallback behavior: [Radarr Issue #5647](https://github.com/Radarr/Radarr/issues/5647) (MEDIUM confidence)
- Sonarr TBA/air date handling: [Sonarr FAQ](https://wiki.servarr.com/sonarr/faq) (HIGH confidence)
- Codebase analysis (2026-03-09): Direct reading of `triggarr/search/engine.py` (filter pipeline, cursor logic, cycle functions), `triggarr/state.py` (AppState TypedDict), `triggarr/models/config.py` (Settings/GeneralConfig/ArrConfig), `triggarr/web/routes.py` (save_settings form parsing, _build_app_context), `triggarr/templates/partials/app_card.html` (X of Y display) (HIGH confidence -- primary source)
