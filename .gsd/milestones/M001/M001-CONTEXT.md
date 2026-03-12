# M001 Context: Multi-Instance & Tag Filtering

## Background

Triggarr v2.2 supports a single Radarr and single Sonarr instance. Users with multiple *arr servers (e.g., 4K + 1080p Radarr, anime + TV Sonarr) need independent management per instance. Additionally, users with large libraries want to scope searches using *arr tags to target specific subsets of their media.

## Prior Art

- v2.2 config uses flat `[radarr]` and `[sonarr]` TOML sections with direct fields
- State uses flat `AppState` per app type in JSON
- Search engine has single `run_radarr_cycle` and `run_sonarr_cycle` functions
- Dashboard shows one status card per app type
- Search history has no instance attribution

## Constraints

- Must auto-migrate v2.2 configs without user intervention
- Must not break existing single-instance setups
- Tag filtering must fail open (misconfigured tag = search everything)
- No new Python dependencies beyond existing stack

## Research Notes

- pydantic-settings with TOML `[[array]]` syntax: validated in Phase 33, works with dict[str, InstanceConfig]
- Radarr tags are on movie objects, Sonarr tags are on series objects (not episodes) — requires different accessor patterns
- Sonarr tag filter must be placed before deduplicate_to_seasons because deduped dicts lose series.tags

## Migrated from

This milestone was previously tracked as `.planning/` phases 33-39 in the v2.3 milestone. Phases map to GSD slices:
- Phase 33 → S01, Phase 34 → S02, Phase 35 → S03, Phase 36 → S04
- Phase 37 → S05, Phase 38 → S06, Phase 39 → S07
