---
id: S07
parent: M001
milestone: M001
provides:
  - Per-instance dashboard cards for all enabled instances
  - Instance name in card headers (hidden for 'Default')
  - Per-instance search-now with per-instance rate limiting
  - Instance filter on history page with filter pills and entry badges
  - Version display in nav bar
requires:
  - slice: S02
    provides: "Per-instance state, clients, scheduler jobs"
  - slice: S05
    provides: "instance_id on all DB query functions, instance_filter on get_search_history"
  - slice: S06
    provides: "Per-instance tracking"
affects: []
key_files:
  - triggarr/web/routes.py
  - triggarr/templates/base.html
  - triggarr/templates/partials/app_card.html
  - triggarr/templates/partials/history_results.html
  - tests/test_web.py
key_decisions:
  - "card_id uses app_name-instance_name for unique htmx targets"
  - "Instance name hidden in card header when it's 'Default' (backward compat UI)"
  - "Rate limit key changed from app_name to app_name_instance_name for per-instance rate limiting"
  - "Version exposed as Jinja2 env global rather than per-route context"
  - "Instance filter pills only shown when multiple instances exist in results"
patterns_established:
  - "Per-instance route pattern: /partials/app-card/{app_name}/{instance_name}"
  - "Jinja2 env globals for cross-template constants"
observability_surfaces:
  - "Dashboard visually shows all instances with independent status cards"
  - "History entries show instance_id badge for non-Default instances"
drill_down_paths:
  - .gsd/milestones/M001/slices/S07/S07-PLAN.md
duration: 15min
verification_result: passed
completed_at: 2026-03-11
---

# S07: Web UI Integration

**Per-instance dashboard cards, history instance filter, and version display completing the multi-instance UI**

## What Happened

Updated `_build_app_context` to accept specific instance_name. Dashboard now iterates all enabled instances across both app types and renders a card per instance. App card template shows instance name in header (hidden for 'Default'). Updated partial_app_card and search_now routes to include instance_name in URL path. Per-instance rate limiting uses `app_name_instance_name` as rate key. History page now supports instance filter via query param, with filter pills rendered when multiple instances exist. Instance badges shown on entries for non-Default instances. Version displayed in nav bar via Jinja2 env global. 389 tests passing (3 new), lint clean.

## Verification

- 389 tests pass (3 new: instance filter, version display, card instance ID)
- ruff lint clean
- All existing web, search, tracking, db, scheduler tests pass with updated route paths

## Requirements Advanced

- OBS-01 — Per-instance status cards: dashboard renders one card per enabled instance
- OBS-02 — Per-instance search history: instance filter on history page works end-to-end
- VER-01 — Version display: shown in nav bar on every page

## Requirements Validated

- OBS-01 — Proven by test_app_card_shows_instance_name + all existing card tests updated
- OBS-02 — Proven by test_history_results_instance_filter
- VER-01 — Proven by test_dashboard_shows_version

## New Requirements Surfaced

- None

## Requirements Invalidated or Re-scoped

- None

## Deviations

None — both tasks executed as planned.

## Known Limitations

- Multi-instance settings form not yet built (INST-05) — users still edit TOML for multiple instances
- Tag autocomplete in settings not built (TAG-06)
- Tag not-found warning badge not built (TAG-05)
- Update notification not built (VER-02)
- Per-instance effectiveness stats not shown as separate dashboard cards (OBS-03 partially done — stats are per-instance in DB but dashboard stats row shows aggregate)

## Follow-ups

- Future milestone: Multi-instance settings form UI
- Future milestone: Tag autocomplete, tag not-found warning
- Future milestone: Update notification (GitHub release check)
- Future milestone: Per-instance stats cards on dashboard

## Files Created/Modified

- `triggarr/web/routes.py` — Per-instance routing, instance filter, version global
- `triggarr/templates/base.html` — Version in nav
- `triggarr/templates/partials/app_card.html` — Instance name in header, per-instance htmx targets
- `triggarr/templates/partials/history_results.html` — Instance filter pills, instance badges, propagated filter params
- `tests/test_web.py` — Updated all route paths for per-instance URLs, 3 new tests

## Forward Intelligence

### What the next slice should know
- All routes now use per-instance URLs (/partials/app-card/{app}/{instance}, /api/search-now/{app}/{instance})
- Version is a Jinja2 env global — accessible in all templates as `triggarr_version`
- History filter state propagation includes instance in all htmx links

### What's fragile
- Nothing — the pattern is clean and well-tested

### Authoritative diagnostics
- test_web.py is the source of truth for route behavior

### What assumptions changed
- None
