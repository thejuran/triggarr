# Requirements

This file is the explicit capability and coverage contract for the project.

## Active

### INST-01 — Multiple named Radarr instances
- Class: core-capability
- Status: active
- Description: User can configure multiple named Radarr instances with independent URL, API key, schedule, and batch sizes
- Why it matters: Users with multiple Radarr servers (4K, 1080p, anime) need independent management
- Source: user
- Primary owning slice: M001/S05
- Supporting slices: M001/S01
- Validation: partial
- Notes: Config model supports it (S01), but scheduler/UI not yet wired

### INST-02 — Multiple named Sonarr instances
- Class: core-capability
- Status: active
- Description: User can configure multiple named Sonarr instances with independent URL, API key, schedule, and batch sizes
- Why it matters: Same as INST-01 for Sonarr
- Source: user
- Primary owning slice: M001/S05
- Supporting slices: M001/S01
- Validation: partial
- Notes: Config model supports it (S01), but scheduler/UI not yet wired

### INST-05 — Instance management via web UI
- Class: primary-user-loop
- Status: active
- Description: User can add, edit, and remove instances from the web UI settings page
- Why it matters: Users shouldn't need to edit TOML by hand
- Source: user
- Primary owning slice: M001/S07
- Supporting slices: none
- Validation: unmapped
- Notes: Phase 39 work

### INST-06 — Per-instance enable/disable
- Class: primary-user-loop
- Status: active
- Description: User can enable/disable individual instances, disabled instances have scheduler jobs removed
- Why it matters: Temporary maintenance without removing config
- Source: user
- Primary owning slice: M001/S06
- Supporting slices: M001/S07
- Validation: unmapped
- Notes: Scheduler wiring needed

### INST-07 — Instance health summary
- Class: failure-visibility
- Status: active
- Description: Dashboard shows instance health summary card (connected/disconnected count with per-instance detail)
- Why it matters: At-a-glance multi-instance monitoring
- Source: user
- Primary owning slice: M001/S07
- Supporting slices: none
- Validation: unmapped
- Notes: Phase 39 UI work

### TAG-05 — Tag not-found warning badge
- Class: failure-visibility
- Status: active
- Description: Dashboard shows a warning badge when a configured tag name is not found in the *arr instance
- Why it matters: Misconfigured tags silently search everything — user needs visibility
- Source: inferred
- Primary owning slice: M001/S07
- Supporting slices: none
- Validation: unmapped
- Notes: Phase 39 UI work

### TAG-06 — Tag autocomplete in settings
- Class: primary-user-loop
- Status: active
- Description: Tag configuration fields in settings UI offer autocomplete populated from the *arr instance's tag list
- Why it matters: Prevents typos in tag names
- Source: inferred
- Primary owning slice: M001/S07
- Supporting slices: none
- Validation: unmapped
- Notes: Phase 39 UI work

### OBS-01 — Per-instance status cards
- Class: failure-visibility
- Status: active
- Description: Dashboard renders a status card per instance showing connection health, queue sizes, and last-run time
- Why it matters: Per-instance monitoring for multi-instance setups
- Source: user
- Primary owning slice: M001/S07
- Supporting slices: none
- Validation: unmapped
- Notes: Phase 39 UI work

### OBS-02 — Per-instance search history
- Class: primary-user-loop
- Status: active
- Description: Search history is scoped per instance with an instance filter on the history page
- Why it matters: History from different instances should not mix
- Source: inferred
- Primary owning slice: M001/S05
- Supporting slices: M001/S07
- Validation: unmapped
- Notes: DB schema change needed

### OBS-03 — Per-instance effectiveness stats
- Class: failure-visibility
- Status: active
- Description: Per-instance effectiveness stats (grab rate, lifetime counts) displayed on dashboard
- Why it matters: Users need to see which instances are effective
- Source: inferred
- Primary owning slice: M001/S07
- Supporting slices: M001/S05
- Validation: unmapped
- Notes: Phase 39 UI work

### VER-01 — Version display
- Class: operability
- Status: active
- Description: Dashboard displays the current Triggarr version
- Why it matters: Users need to know what version they're running
- Source: user
- Primary owning slice: M001/S07
- Supporting slices: none
- Validation: unmapped
- Notes: Phase 39 UI work

### VER-02 — Update notification
- Class: operability
- Status: active
- Description: Dashboard indicates when a newer release is available by checking GitHub/GHCR
- Why it matters: Users should know when to update
- Source: user
- Primary owning slice: M001/S07
- Supporting slices: none
- Validation: unmapped
- Notes: Phase 39 UI work

## Validated

### INST-03 — Independent round-robin cursors
- Class: core-capability
- Status: validated
- Description: Each instance maintains independent round-robin cursors that persist across restarts
- Why it matters: Two instances of the same app type must not share or corrupt each other's cursor positions
- Source: user
- Primary owning slice: M001/S02
- Supporting slices: none
- Validation: validated
- Notes: Proven by per-instance state model with v2.2 migration (Phase 34)

### INST-04 — Auto-migration from v2.2
- Class: continuity
- Status: validated
- Description: Existing single-instance v2.2 config files auto-migrate to multi-instance format on upgrade
- Why it matters: Users upgrading from v2.2 must not lose their config
- Source: inferred
- Primary owning slice: M001/S01
- Supporting slices: none
- Validation: validated
- Notes: Proven by detect_and_migrate_v22() with backup and .migrated marker (Phase 33)

### TAG-01 — Missing queue tag filter
- Class: core-capability
- Status: validated
- Description: User can configure a tag name per instance for the missing queue (only items with that tag are searched)
- Why it matters: Selective search targeting for large libraries
- Source: user
- Primary owning slice: M001/S04
- Supporting slices: M001/S03
- Validation: validated
- Notes: Proven by filter_by_tag in run_radarr_cycle and run_sonarr_cycle (Phase 36)

### TAG-02 — Cutoff queue tag filter
- Class: core-capability
- Status: validated
- Description: User can configure a tag name per instance for the cutoff queue (only items with that tag are searched)
- Why it matters: Selective upgrade targeting
- Source: user
- Primary owning slice: M001/S04
- Supporting slices: M001/S03
- Validation: validated
- Notes: Proven by filter_by_tag in cycle functions (Phase 36)

### TAG-03 — No-tag defaults to search all
- Class: core-capability
- Status: validated
- Description: When no tag is configured, all monitored items are searched (default behavior unchanged)
- Why it matters: Backward compatibility for users who don't use tags
- Source: inferred
- Primary owning slice: M001/S04
- Supporting slices: none
- Validation: validated
- Notes: Empty string tag fields = no filtering applied (Phase 36)

### TAG-04 — Tag name resolution via API
- Class: core-capability
- Status: validated
- Description: Tag names are resolved to numeric IDs via the *arr /api/v3/tag endpoint each cycle
- Why it matters: Tags must work by human-readable name, not opaque IDs
- Source: inferred
- Primary owning slice: M001/S03
- Supporting slices: none
- Validation: validated
- Notes: Proven by resolve_tag_id() and get_tags() client method (Phase 35)

## Deferred

### DEFER-01 — Cross-instance search deduplication
- Class: quality-attribute
- Status: deferred
- Description: Deduplicate searches across instances by TMDB/TVDB ID
- Why it matters: Prevents searching for the same media on multiple instances
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Low priority — independent instances searching the same item is harmless

### DEFER-02 — Dynamic instance hot-add
- Class: operability
- Status: deferred
- Description: Add instances without restart
- Why it matters: Convenience for power users
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Config reload on settings save handles most cases

## Out of Scope

### OOS-01 — Auto-discover *arr instances
- Class: anti-feature
- Status: out-of-scope
- Description: Network scanning to find Radarr/Sonarr instances
- Why it matters: SSRF risk, violates zero-credential-exposure principle
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Explicitly excluded

### OOS-02 — Tag management from Triggarr
- Class: anti-feature
- Status: out-of-scope
- Description: Create/assign tags in *arr from Triggarr
- Why it matters: Write operations expand attack surface; Triggarr is read+search-only
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Explicitly excluded

### OOS-03 — Tag-based exclusion
- Class: anti-feature
- Status: out-of-scope
- Description: Search everything EXCEPT items with a given tag
- Why it matters: Inverse logic is confusing; include-only filtering is clearer
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Explicitly excluded

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| INST-01 | core-capability | active | M001/S05 | M001/S01 | partial |
| INST-02 | core-capability | active | M001/S05 | M001/S01 | partial |
| INST-03 | core-capability | validated | M001/S02 | none | validated |
| INST-04 | continuity | validated | M001/S01 | none | validated |
| INST-05 | primary-user-loop | active | M001/S07 | none | unmapped |
| INST-06 | primary-user-loop | active | M001/S06 | M001/S07 | unmapped |
| INST-07 | failure-visibility | active | M001/S07 | none | unmapped |
| TAG-01 | core-capability | validated | M001/S04 | M001/S03 | validated |
| TAG-02 | core-capability | validated | M001/S04 | M001/S03 | validated |
| TAG-03 | core-capability | validated | M001/S04 | none | validated |
| TAG-04 | core-capability | validated | M001/S03 | none | validated |
| TAG-05 | failure-visibility | active | M001/S07 | none | unmapped |
| TAG-06 | primary-user-loop | active | M001/S07 | none | unmapped |
| OBS-01 | failure-visibility | active | M001/S07 | none | unmapped |
| OBS-02 | primary-user-loop | active | M001/S05 | M001/S07 | unmapped |
| OBS-03 | failure-visibility | active | M001/S07 | M001/S05 | unmapped |
| VER-01 | operability | active | M001/S07 | none | unmapped |
| VER-02 | operability | active | M001/S07 | none | unmapped |
| DEFER-01 | quality-attribute | deferred | none | none | unmapped |
| DEFER-02 | operability | deferred | none | none | unmapped |
| OOS-01 | anti-feature | out-of-scope | none | none | n/a |
| OOS-02 | anti-feature | out-of-scope | none | none | n/a |
| OOS-03 | anti-feature | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 12
- Mapped to slices: 12
- Validated: 6
- Unmapped active requirements: 0
