---
id: S01
parent: M005
milestone: M005
provides:
  - In-app changelog modal with dark-themed UI
  - CHANGELOG.md parser converting markdown to styled HTML
  - GET /changelog route serving HTML partial via htmx
requires: []
affects: []
key_files:
  - CHANGELOG.md
  - triggarr/changelog.py
  - triggarr/web/routes.py
  - triggarr/templates/base.html
key_decisions:
  - Custom regex parser (like Tautulli) instead of a markdown library — keeps dependencies minimal
  - Modal overlay triggered by clicking version string in nav bar, not a separate page
  - htmx hx-get with client-side caching — modal content fetched once, reused on subsequent opens
  - CHANGELOG.md copied into Docker image via Dockerfile COPY
patterns_established:
  - Modal pattern with htmx fetch + Escape-to-close for future in-app overlays
observability_surfaces:
  - GET /changelog returns HTML partial directly (inspectable via curl)
  - Warning log if CHANGELOG.md is missing or unreadable
drill_down_paths: []
duration: ~1 session
verification_result: passed
completed_at: 2026-04-07
---

# S01: Changelog Parser, Route & UI

**Users can click the version string in the nav bar to see a dark-themed modal with categorized release notes read from a local CHANGELOG.md — no GitHub API, works offline.**

## What Happened

Created a CHANGELOG.md in the repo root with entries from v1.0 through v2.6.1-dev. Built a custom regex-based parser in `triggarr/changelog.py` that converts markdown headers to HTML headings and bullet lists to `<ul>/<li>`, with category grouping (Features, Fixes, etc.). Added a GET `/changelog` route that calls the parser and returns an HTML partial. Integrated a modal in `base.html` triggered by clicking the version string in the nav bar, fetched via htmx with client-side caching. Styled for the existing dark theme. Added a Dockerfile COPY for CHANGELOG.md.

## Verification

- 22 new tests added (parser unit tests + route tests + escaping)
- 520 total tests passing
- Route returns 200 with rendered HTML
- Browser: clicking version in nav opens styled modal with formatted changelog

## Requirements Advanced

- In-app changelog — new capability fully delivered

## Requirements Validated

- In-app changelog — proven by parser tests, route tests, and browser verification

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

none

## Known Limitations

- CHANGELOG.md is manually maintained — no auto-generation from git history
- No "since your version" filtering (was listed as optional in context, not implemented)

## Follow-ups

- none

## Files Created/Modified

- `CHANGELOG.md` — release history from v1.0 through v2.6.1-dev
- `triggarr/changelog.py` — regex parser converting markdown to styled HTML
- `triggarr/web/routes.py` — GET /changelog route
- `triggarr/templates/base.html` — nav bar version click → modal with htmx fetch
- `tests/test_changelog.py` — 22 parser and escaping tests
- `tests/test_web.py` — route integration tests for /changelog
- `Dockerfile` — COPY CHANGELOG.md into image

## Forward Intelligence

### What the next slice should know
- M005 is complete with this single slice — no further slices needed

### What's fragile
- CHANGELOG.md format — the regex parser expects `## [vX.Y.Z]` headers and `- ` bullet lists; unusual formatting will silently produce wrong output

### Authoritative diagnostics
- `curl http://localhost:8080/changelog` — returns the rendered HTML partial directly

### What assumptions changed
- Originally considered using a markdown library (mistune/markdown) but went with custom regex like Tautulli — simpler, no new dependency
