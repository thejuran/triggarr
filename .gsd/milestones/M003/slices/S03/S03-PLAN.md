# S03: Web UI & Templates

**Goal:** Lidarr is fully visible in the dashboard, settings, history, and stats templates — completing end-to-end UI support.
**Demo:** Dashboard shows Lidarr instance cards, stats row includes Albums card with Lidarr rate, history filter bar includes Lidarr pill with green color, settings URL placeholder shows port 8686, empty-state text mentions Lidarr.

## Must-Haves

- History filter bar includes "Lidarr" app pill with distinctive color
- History entry badge shows Lidarr with its own color (not falling through to Sonarr blue)
- Stats row includes Albums card (shown when not filtered to Radarr/Sonarr only)
- Stats row grab rate shows L: alongside R: and S:
- Settings URL placeholder shows correct port per app type (8686 for Lidarr)
- Dashboard empty-state text mentions Lidarr
- All existing tests still pass

## Proof Level

- This slice proves: final-assembly
- Real runtime required: no (template changes verified via test client)
- Human/UAT required: yes (visual check in browser)

## Verification

- `uv run pytest tests/ -x -q` — full suite green
- `uv run ruff check triggarr/ tests/` — lint clean
- Template inspection: all hardcoded Radarr/Sonarr references updated

## Tasks

- [ ] **T01: Update templates for Lidarr support** `est:30m`
  - Why: Templates have hardcoded Radarr/Sonarr references that exclude Lidarr
  - Files: `triggarr/templates/partials/history_results.html`, `triggarr/templates/partials/stats_row.html`, `triggarr/templates/settings.html`, `triggarr/templates/dashboard.html`
  - Do:
    1. history_results.html: Add 'Lidarr' to app filter loop, add green color for Lidarr entry badge
    2. stats_row.html: Add Albums card (like Movies/Episodes), show L: rate, fix grid cols logic
    3. settings.html: Fix URL placeholder to show 8686 for lidarr
    4. dashboard.html: Update empty-state text to mention Lidarr
  - Verify: `uv run pytest tests/ -x -q`, visual inspection of template changes
  - Done when: All templates include Lidarr, no hardcoded Radarr/Sonarr-only references remain

- [ ] **T02: Add template-level tests and final verification** `est:15m`
  - Why: Ensure Lidarr content renders correctly via test client
  - Files: `tests/test_web.py`
  - Do: Add test that Lidarr appears in history filter bar, stats mock includes album fields, settings placeholder shows 8686
  - Verify: `uv run pytest tests/ -x -q`
  - Done when: New tests pass, full suite green

## Files Likely Touched

- `triggarr/templates/partials/history_results.html`
- `triggarr/templates/partials/stats_row.html`
- `triggarr/templates/settings.html`
- `triggarr/templates/dashboard.html`
- `tests/test_web.py`
