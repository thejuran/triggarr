---
id: M005
provides:
  - In-app changelog viewable from nav bar without leaving the app
  - CHANGELOG.md maintained in repo root, shipped in Docker image
key_decisions:
  - Custom regex parser instead of markdown library — matches Tautulli model, no new dependency
  - Modal overlay rather than dedicated page — keeps nav clean
  - htmx fetch with client-side caching — one network request per session
patterns_established:
  - Modal overlay pattern with htmx hx-get + Escape-to-close
observability_surfaces:
  - GET /changelog — returns rendered HTML partial (curl-inspectable)
requirement_outcomes:
  - id: in-app-changelog
    from_status: active
    to_status: validated
    proof: 22 tests passing, route returns 200, browser-verified modal rendering
duration: ~1 session
verification_result: passed
completed_at: 2026-04-07
---

# M005: In-App Changelog

**Users can view a formatted, dark-themed changelog directly in Triggarr by clicking the version string in the nav bar — no GitHub API calls, works offline.**

## What Happened

Single-slice milestone. Created a CHANGELOG.md with release history from v1.0 through v2.6.1-dev. Built a regex-based parser (`triggarr/changelog.py`) that converts markdown to styled HTML with version headers and categorized bullet lists. Wired it into the web UI via a GET `/changelog` route serving an HTML partial, triggered by an htmx-powered modal from the nav bar. The modal is dark-themed to match the existing UI, cached client-side after first load, and dismissible with Escape. Updated the Dockerfile to include CHANGELOG.md in the image.

## Cross-Slice Verification

- **Parser correctness:** 22 new tests covering multi-version parsing, category grouping, empty/missing file, HTML escaping
- **Route integration:** `/changelog` returns 200 with HTML content
- **Regression:** 520 total tests passing (up from 498)
- **Browser:** modal opens from nav bar click, displays formatted content, closes with Escape
- **Docker:** CHANGELOG.md included in image via Dockerfile COPY

## Requirement Changes

- in-app-changelog: new → validated — parser tests, route tests, and browser verification all confirm working feature

## Forward Intelligence

### What the next milestone should know
- CHANGELOG.md must be updated manually with each release — there is no auto-generation
- The modal pattern established here (htmx fetch + overlay div + Escape listener) can be reused for other in-app overlays

### What's fragile
- The regex parser expects `## [vX.Y.Z]` headers and `- ` bullet lists — non-standard formatting will parse incorrectly without errors

### Authoritative diagnostics
- `curl http://localhost:8080/changelog` — shows the raw HTML partial, useful for debugging rendering issues
- `pytest tests/test_changelog.py -x` — fastest way to validate parser behavior

### What assumptions changed
- Originally considered mistune/markdown libraries but custom regex was simpler and matched the Tautulli model exactly

## Files Created/Modified

- `CHANGELOG.md` — release history v1.0 through v2.6.1-dev
- `triggarr/changelog.py` — regex-based markdown-to-HTML parser
- `triggarr/web/routes.py` — GET /changelog route
- `triggarr/templates/base.html` — nav bar modal integration with htmx
- `tests/test_changelog.py` — 22 parser/escaping tests
- `tests/test_web.py` — route integration tests
- `Dockerfile` — COPY CHANGELOG.md into image
