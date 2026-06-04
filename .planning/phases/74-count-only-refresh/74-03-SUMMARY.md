---
phase: 74-count-only-refresh
plan: "03"
subsystem: ui-template
tags: [template, button, htmx, count-only, tdd, flex-layout]
dependency_graph:
  requires: [74-02]
  provides: [Refresh counts button in connected app-card footer]
  affects:
    - triggarr/templates/partials/app_card.html
    - tests/test_refresh_counts.py
tech_stack:
  added: []
  patterns:
    - flex-gap-2 side-by-side flex-1 buttons (D-09)
    - hx-disabled-elt dim-only in-flight (mirroring Search Now)
    - connected/disconnected branch split (D-10)
key_files:
  created: []
  modified:
    - triggarr/templates/partials/app_card.html
    - tests/test_refresh_counts.py
decisions:
  - "Connected footer: single w-full Search Now → flex gap-2 wrapper + two flex-1 buttons; Search Now primary (bg-triggarr-elevated), Refresh counts secondary (bg-triggarr-card/text-triggarr-muted)"
  - "Disconnected footer (Retry Connection) left exactly unchanged (D-10)"
  - "Refresh counts htmx attrs mirror Search Now exactly: hx-post refresh_counts url_for, hx-target card, hx-swap outerHTML, hx-disabled-elt this; no spinner, no success cue, no sibling-disable (D-12/D-13)"
metrics:
  duration: ~8 minutes
  completed: 2026-06-04T01:23:28Z
  tasks_completed: 1
  files_modified: 2
---

# Phase 74 Plan 03: app_card.html Footer Split Summary

Connected app-card footer split into two side-by-side `flex-1` buttons — Search Now (primary) and Refresh counts (secondary, `ph-arrows-clockwise`) — with the disconnected Retry Connection footer left exactly unchanged.

## What Was Built

### Template change (`triggarr/templates/partials/app_card.html`)

Only the `{% else %}` connected branch (lines 118-135) was modified:

**Before:** single `w-full` Search Now button.

**After:** `<div class="flex gap-2">` wrapping two `flex-1` buttons:

1. **Search Now** (primary): `w-full` → `flex-1`, all other classes/attrs identical — same `bg-triggarr-elevated`, app-colored `group-hover` magnifying-glass, same htmx attrs.
2. **Refresh counts** (secondary): `flex-1 flex items-center justify-center gap-2 py-2 rounded-md bg-triggarr-card hover:bg-triggarr-elevated border border-triggarr-border text-xs font-semibold transition-colors text-triggarr-muted disabled:opacity-50 disabled:cursor-not-allowed`; icon `ph ph-arrows-clockwise`; htmx mirrors Search Now exactly (`hx-post` to `refresh_counts` via `request.url_for`, `hx-target`, `hx-swap="outerHTML"`, `hx-disabled-elt="this"`).

The `{% if app.connected == false %}` disconnected branch (Retry Connection button) is entirely untouched — `git diff` shows changes only within the `{% else %}` block.

### Button tests (`tests/test_refresh_counts.py`)

Two new tests appended (lines 1021-1040):

| Test | What it proves |
|------|---------------|
| `test_app_card_connected_has_refresh_counts_button` | GET /partials/app-card/radarr/Default → 200, body contains "Refresh counts" (CNT-05/D-09/D-11) |
| `test_app_card_disconnected_no_refresh_counts_button` | connected=False → 200, body NOT contains "Refresh counts", DOES contain "Retry Connection" (D-10) |

Both tests use the existing `refresh_client`/`refresh_test_app` fixtures from Plan 02.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 (RED+GREEN) | ee110c2 | feat(74-03): split connected footer into Search Now + Refresh counts buttons |

## Verification Results

- `uv run pytest tests/test_refresh_counts.py -k "button or disconnected_no" -x -q`: 2 passed
- `uv run pytest tests/ -x -q`: **1044 passed** (1042 Plan 02 baseline + 2 new button tests)
- `uv run ruff check triggarr/ tests/`: clean (no Python modified)
- `git diff triggarr/templates/partials/app_card.html`: changes confined to connected `{% else %}` branch; disconnected Retry Connection branch untouched

### Source-level assertions

- `grep -c "url_for('refresh_counts'" triggarr/templates/partials/app_card.html` → 1
- `grep -c 'flex gap-2' triggarr/templates/partials/app_card.html` → 1 (in connected branch)
- `grep -c 'flex-1' triggarr/templates/partials/app_card.html` → 4 (2 per button × 2 occurrences in class strings)
- `grep -c 'ph-arrows-clockwise' triggarr/templates/partials/app_card.html` → 2 (Retry Connection + Refresh counts)
- `grep -c 'hx-disabled-elt' triggarr/templates/partials/app_card.html` → 2 (Search Now + Refresh counts)
- `grep -c 'Refresh counts' triggarr/templates/partials/app_card.html` → 1
- No `w-full` in connected branch (only in disconnected Retry Connection)
- `hx-target="#{{ app.card_id }}-card"`, `hx-swap="outerHTML"`, `hx-disabled-elt="this"` all present on Refresh counts button

## Deviations from Plan

None — plan executed exactly as written. Template edit matches the exact target markup from 74-PATTERNS.md lines 415-434.

## Known Stubs

None. The Refresh counts button posts to the live `refresh_counts` endpoint (Plan 02); no hardcoded values flow to UI.

## Threat Flags

None. Per threat model T-74-10: the Refresh counts button swaps `partials/app_card.html` via `_build_app_context` (same context as Search Now and the periodic poll) — no new template variable, no `api_key`/secret field in card context. T-74-11: mirrors Search Now's hardened `hx-disabled-elt="this"` dim-only pattern verbatim.

## Self-Check: PASSED

- triggarr/templates/partials/app_card.html (Refresh counts button in connected branch): FOUND
- tests/test_refresh_counts.py (2 new button tests at lines 1021-1040): FOUND
- Commit ee110c2: verified in git log
- 1044 tests passing, ruff clean
- git diff confined to connected {% else %} branch: CONFIRMED
