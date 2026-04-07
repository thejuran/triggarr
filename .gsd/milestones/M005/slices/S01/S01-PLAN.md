# S01: Changelog Parser, Route & UI

**Goal:** Users can click "Changelog" in the nav bar to see a formatted, dark-themed modal with categorized release notes read from a local CHANGELOG.md file.
**Demo:** Click Changelog link in nav → modal opens showing version headers with categorized bullet lists for recent releases.

## Must-Haves

- CHANGELOG.md in repo root with entries for v1.0 through v2.6.1-dev
- Parser module that reads CHANGELOG.md and converts to styled HTML
- FastAPI route serving rendered changelog HTML partial
- htmx-powered modal in base template triggered from nav bar
- Dark theme styling consistent with existing UI
- Tests for parser and route

## Proof Level

- This slice proves: integration
- Real runtime required: yes (browser verification)
- Human/UAT required: yes (visual check of modal)

## Verification

- `pytest tests/test_changelog.py -x` — parser unit tests (headers, lists, categories, edge cases)
- `pytest tests/test_routes.py -x -k changelog` — route returns 200 with HTML content
- Browser: click Changelog in nav → modal opens with formatted content

## Observability / Diagnostics

- Runtime signals: warning log if CHANGELOG.md is missing or unreadable
- Inspection surfaces: GET /changelog returns HTML partial directly
- Failure visibility: graceful fallback message if file missing
- Redaction constraints: none (changelog is public content)

## Integration Closure

- Upstream surfaces consumed: `triggarr/templates/base.html` (nav bar), `triggarr/web/routes.py` (route registration)
- New wiring introduced in this slice: changelog route, modal partial, nav link
- What remains before the milestone is truly usable end-to-end: nothing — this is the only slice

## Tasks

- [x] **T01: Create CHANGELOG.md and parser module** `est:45m`
  - Why: Foundation — the changelog file and parser are the core of this feature
  - Files: `CHANGELOG.md`, `triggarr/changelog.py`, `tests/test_changelog.py`
  - Do: Write CHANGELOG.md with entries from v1.0 through current. Build parser that reads file, converts markdown headers to HTML headings, bullet lists to `<ul>/<li>`, supports category grouping (e.g. "Features:", "Fixes:"). Return full HTML or graceful fallback if file missing. Write tests covering: multi-version parsing, category grouping, empty file, missing file.
  - Verify: `pytest tests/test_changelog.py -x`
  - Done when: parser converts real CHANGELOG.md to well-structured HTML, all tests pass

- [x] **T02: Route, modal template & nav bar integration** `est:30m`
  - Why: Wire the parser into the web UI — route serves HTML, modal displays it, nav links to it
  - Files: `triggarr/web/routes.py`, `triggarr/templates/base.html`, `triggarr/templates/partials/changelog_modal.html`, `tests/test_routes.py`
  - Do: Add GET /changelog route that calls parser and returns HTML partial. Add modal markup to base.html (hidden by default). Add "Changelog" link in nav bar that uses hx-get="/changelog" hx-target to load content into modal and open it. Style modal for dark theme matching existing settings/history pages.
  - Verify: `pytest tests/test_routes.py -x -k changelog` and browser verification
  - Done when: clicking Changelog in nav opens styled modal with formatted release notes

## Files Likely Touched

- `CHANGELOG.md`
- `triggarr/changelog.py`
- `triggarr/web/routes.py`
- `triggarr/templates/base.html`
- `triggarr/templates/partials/changelog_modal.html`
- `tests/test_changelog.py`
- `tests/test_routes.py`
