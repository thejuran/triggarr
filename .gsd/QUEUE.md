# Queued Milestones

## Next Release: Update Check Interval 24h → 6h

**Change:** Reduce update check frequency from 24h to 6h (industry standard: Sonarr/Radarr use 6h, Tautulli uses 12h).

**Files:** `triggarr/search/scheduler.py` (line ~250, `hours=24` → `hours=6`), `triggarr/update_check.py` (docstring)

**Status:** Already implemented and stashed — `git stash pop` to apply. 520 tests passing.

**Queued:** 2026-04-07

---

## Someday/Maybe: Cross-Instance Dedup

**Problem:** When multiple instances of the same app type (e.g. Radarr + Radarr 4K) have overlapping libraries, Triggarr searches the same item independently in both instances, wasting search slots and potentially triggering duplicate grabs.

**Approach:** Record external IDs (tmdbId/tvdbId/foreignAlbumId) of searched items with timestamps. Before searching, check if another instance already searched the same item within a configurable window. Skip and log "skipped (already searched by <other instance>)".

**Complexity:** Medium-high. Instances run on independent schedules, Sonarr searches at season level (need series+season matching), external ID availability in wanted-list responses needs confirmation.

**Tabled:** 2026-04-07 — not personally needed, revisit if users request it.
