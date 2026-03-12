# S07: Web UI Integration

**Goal:** Dashboard shows per-instance status cards for all enabled instances, search history supports instance filtering, and version is displayed in the nav bar.
**Demo:** Multi-instance dashboard with separate cards per instance, history page with instance filter pills, version shown in nav.

## Must-Haves

- Dashboard renders one card per enabled instance (not just first-enabled)
- Each card shows instance name in header
- History entries show instance_id badge
- History filter bar includes instance filter pills
- History route passes instance_filter to DB
- Version displayed in nav bar
- All existing tests pass, new route tests for instance filtering

## Proof Level

- This slice proves: final-assembly
- Real runtime required: no (test client verification sufficient)
- Human/UAT required: yes (visual check of multi-instance dashboard recommended)

## Verification

- `pytest tests/test_web.py -v` — all tests pass including new instance-filter tests
- `pytest -x -q` — full suite green
- `ruff check triggarr/ tests/` — lint clean

## Observability / Diagnostics

- Runtime signals: none new (existing loguru logging)
- Inspection surfaces: dashboard visually shows all instances, history shows instance badges
- Failure visibility: none new
- Redaction constraints: none

## Integration Closure

- Upstream surfaces consumed: instance_id on all DB functions (S05), per-instance state (S02), per-instance clients/scheduler (S02/S06)
- New wiring introduced in this slice: per-instance dashboard cards, instance filter on history, version in nav
- What remains before the milestone is truly usable end-to-end: nothing — this completes M001

## Tasks

- [x] **T01: Per-instance dashboard cards** `est:20m`
  - Why: Dashboard currently shows only the first-enabled instance per app type. Users with multiple instances need to see all of them.
  - Files: `triggarr/web/routes.py`, `triggarr/templates/dashboard.html`, `triggarr/templates/partials/app_card.html`
  - Do:
    1. Modify `_build_app_context` to accept `instance_name` parameter instead of using first-enabled
    2. Update `dashboard` route to iterate ALL enabled instances (both app types × all instances) and build a context for each
    3. Add instance name to the card header (e.g., "Radarr / 4K")
    4. Update `partial_app_card` route to accept instance_name in URL
    5. Update `search_now` route to accept instance_name
    6. Ensure htmx polling targets are unique per instance (id="radarr-4K-card")
  - Verify: `pytest tests/test_web.py -v` — all pass
  - Done when: Dashboard renders one card per enabled instance with instance name visible

- [x] **T02: Instance filter on history page and version display** `est:20m`
  - Why: History entries need instance context, and users need a way to filter by instance. Version display is a quick win.
  - Files: `triggarr/web/routes.py`, `triggarr/templates/partials/history_results.html`, `triggarr/templates/base.html`, `tests/test_web.py`
  - Do:
    1. In `partial_history_results` route: parse `instance` query param via `_split_filter_param`, pass as `instance_filter` to `get_search_history`
    2. Pass `active_instances` list to template context
    3. In history_results.html: add instance filter pills (like app filter), show instance badge on each entry row
    4. In base.html: add version to nav bar (e.g., "Triggarr v0.1.0")
    5. Pass `triggarr_version` to all template contexts (or use a Jinja2 global)
    6. Add test: history endpoint with instance filter returns only matching entries
  - Verify: `pytest tests/test_web.py -v` — all pass
  - Done when: History page shows instance badges and filter pills, version in nav, tests green

## Files Likely Touched

- `triggarr/web/routes.py`
- `triggarr/templates/base.html`
- `triggarr/templates/dashboard.html`
- `triggarr/templates/partials/app_card.html`
- `triggarr/templates/partials/history_results.html`
- `tests/test_web.py`
