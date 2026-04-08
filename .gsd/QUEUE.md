# Queued Milestones

## Someday/Maybe: Cross-Instance Dedup

**Problem:** When multiple instances of the same app type (e.g. Radarr + Radarr 4K) have overlapping libraries, Triggarr searches the same item independently in both instances, wasting search slots and potentially triggering duplicate grabs.

**Approach:** Record external IDs (tmdbId/tvdbId/foreignAlbumId) of searched items with timestamps. Before searching, check if another instance already searched the same item within a configurable window. Skip and log "skipped (already searched by <other instance>)".

**Complexity:** Medium-high. Instances run on independent schedules, Sonarr searches at season level (need series+season matching), external ID availability in wanted-list responses needs confirmation.

**Tabled:** 2026-04-07 — not personally needed, revisit if users request it.
