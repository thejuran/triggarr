---
gsd_state_version: 1.0
milestone: v2.3
milestone_name: Multi-Instance & Tag Filtering
status: completed
stopped_at: Completed 41-01-PLAN.md
last_updated: "2026-03-12T02:40:26.440Z"
last_activity: 2026-03-12 — Completed Plan 01 (multi-instance settings UI with tag autocomplete)
progress:
  total_phases: 11
  completed_phases: 6
  total_plans: 11
  completed_plans: 11
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-09)

**Core value:** Reliably trigger searches in Radarr and Sonarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback -- without exposing credentials or expanding attack surface.
**Current focus:** Phase 41 — Multi-Instance Settings UI

## Current Position

Phase: 41 (9 of 9 in v2.3) — Multi-Instance Settings UI
Plan: 01 of 1 complete (phase complete)
Status: Complete
Last activity: 2026-03-12 — Completed Plan 01 (multi-instance settings UI with tag autocomplete)

Progress: [██████████] 100%

## Performance Metrics

**Overall:**
- Total plans completed: 56 (v1.0: 18, v1.1: 5, v1.2: 8, v2.0: 18, v2.1: 2, v2.2: 5)
- Milestones shipped: 6 (v1.0, v1.1, v1.2, v2.0, v2.1, v2.2)

**v2.3:**
- Plans completed: 11
- Phases: 9 (33-41)

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 33 | 01 | 3min | 1 | 2 |
| 33 | 02 | 11min | 2 | 3 |
| 34 | 01 | 2min | 1 | 3 |
| 34 | 02 | 18min | 2 | 8 |
| 35 | 01 | 3min | 2 | 5 |
| 36 | 01 | 1min | 1 | 5 |
| 36 | 02 | 9min | 2 | 2 |
| 40 | 01 | 19min | 2 | 6 |
| 40 | 02 | 25min | 2 | 4 |
| 40 | 03 | 25min | 2 | 5 |
| 41 | 01 | 11min | 2 | 5 |

## Accumulated Context

### Decisions

Full decision log in PROJECT.md Key Decisions table.

- Phase 33-01: Renamed ArrConfig to InstanceConfig with backward-compat alias
- Phase 33-01: Updated test TOML fixtures to v2.3 nested format
- Phase 33-02: Extracted _atomic_toml_write helper for reuse
- Phase 33-02: v2.2 detection uses flat key set intersection
- Phase 33-02: .migrated marker file for web UI banner (Phase 39)
- Phase 34-01: TriggarrState uses dict[str, AppState] for nested per-instance cursors
- Phase 34-01: _default_state without settings returns empty dicts for backward compat
- Phase 34-01: cleanup_orphaned_instances is standalone (not inside load_state)
- Phase 34-01: v2.2 migration wraps flat AppState into {"Default": AppState}
- Phase 34-02: Dashboard shows first enabled instance (Phase 39 for multi-instance UI)
- Phase 34-02: Tracking uses first available client per app type for grab checks
- Phase 34-02: search_now triggers first enabled instance (Phase 39 for per-instance)
- Phase 35-01: Tag model uses extra=ignore to match GrabEvent/SystemStatus pattern
- Phase 35-01: resolve_tag_id is a pure function following filter_monitored pattern
- Phase 36-01: Tag accessor pattern uses Callable[[dict], list[int]] for Radarr vs Sonarr tag location difference
- Phase 36-01: Tag fields default to empty string (search all) for backward compatibility
- Phase 36-02: Tag resolution happens once per cycle (single get_tags call) to minimize API calls
- Phase 36-02: Sonarr tag filter placed before deduplicate_to_seasons (deduped dicts lose series.tags)
- Phase 36-02: Radarr filter order: filter_monitored -> filter_by_tag -> filter_unreleased_movies
- [Phase 40]: setdefault with _default_instance_state() as guard pattern for missing state entries
- [Phase 40]: validate_connections keys results as app/instance for unique per-instance tracking
- [Phase 40]: save_settings persists state after adding new instance entries
- [Phase 40-02]: Preserve tag fields on both edited and non-edited instances during save
- [Phase 40-02]: _sanitize_card_id with re.sub for HTML id/CSS selector safety
- [Phase 40-02]: Temp file created before try block so except can always unlink
- [Phase 40-03]: tag_fetch_ok boolean replaces 'if tags:' guard for clearer fetch-failure semantics
- [Phase 40-03]: cleanup_orphaned_instances uses dict comprehension for immutability
- [Phase 40-03]: Test helper renamed to _make_test_state with direct import of production symbol
- [Phase 41-01]: Double-underscore separator for form fields ({app}__{inst}__{field}) to avoid collision with underscores in instance names
- [Phase 41-01]: validate_instance_name rejects __ to protect form field parsing regex
- [Phase 41-01]: Tag autocomplete uses htmx hx-get on focus with datalist
- [Phase 41-01]: response_model=None for endpoints returning mixed HTMLResponse/RedirectResponse
- [Phase 41-01]: _settings_to_dict helper for SecretStr-safe TOML serialization

### Pending Todos

None.

### Roadmap Evolution

- Phase 40 added: Fix Multi-Instance Bugs and Hardening

### Blockers/Concerns

- Research flag: Phase 33 — validate pydantic-settings behavior with TOML `[[array]]` syntax and `list[InstanceConfig]` early
- Research flag: Phase 39 — multi-instance settings form UI pattern (tabbed/accordion) needs design thought

## Session Continuity

Last session: 2026-03-12T02:36:10Z
Stopped at: Completed 41-01-PLAN.md
Resume file: None
