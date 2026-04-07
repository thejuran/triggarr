# M005: In-App Changelog (Tautulli Model) — Context

**Gathered:** 2026-04-07
**Status:** Ready for planning

## Project Description

Triggarr is a Docker-based automation daemon that searches Radarr, Sonarr, and Lidarr for missing/upgrade media on a schedule. The nav bar shows the current version and an upgrade badge, but there's no way to see what changed without visiting GitHub.

## Why This Milestone

Users want to know what changed in each release without leaving the app. Following the Tautulli model: ship a CHANGELOG.md in the repo, read it from disk at runtime, render it in-app. No GitHub API calls, no rate limits, works offline.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Click "Changelog" in the nav bar or settings to see a formatted changelog
- See what's new since their last version after updating
- View the full release history in-app

### Entry point / environment

- Entry point: Changelog link in nav bar / modal or page in web UI
- Environment: Docker container on NAS
- Live dependencies involved: none (reads from local file)

## Completion Class

- Contract complete means: changelog parser tested with fixture CHANGELOG.md, route/partial renders HTML
- Integration complete means: real CHANGELOG.md renders correctly in running app
- Operational complete means: Docker build includes CHANGELOG.md, displays correctly

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- CHANGELOG.md exists in repo with entries for recent releases
- Changelog renders formatted in the web UI
- All existing tests pass, no regressions

## Risks and Unknowns

- Markdown parsing approach: Tautulli uses custom regex parser. We could use a lightweight lib (e.g. markdown, mistune) or keep it simple with regex. Leaning toward a small lib since we already have dependencies.
- XSS safety: changelog content is our own, but should still sanitize HTML output

## Existing Codebase / Prior Art

- Tautulli's `versioncheck.py:read_changelog()` — regex parser reads CHANGELOG.md, converts headers/lists to HTML, supports `latest_only` and `since_prev_release` filters
- Tautulli's settings page — modal triggered by "Changelog" link next to version, fetches via AJAX `get_changelog` endpoint
- `triggarr/update_check.py` — existing version check logic
- `triggarr/version.py` — display version logic
- `triggarr/templates/base.html` — nav bar with version + update badge

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions.

## Scope

### In Scope

- CHANGELOG.md file in repo root, maintained alongside releases
- Parser module to read CHANGELOG.md and convert to HTML
- Web route/partial to serve rendered changelog
- Nav bar link to changelog
- Optional: "since previous version" filter for post-update context

### Out of Scope / Non-Goals

- Fetching release notes from GitHub API (unnecessary with local file)
- Auto-generating changelog from git commits
- Cross-instance dedup (moved to someday/maybe in QUEUE.md)

## Technical Constraints

- CHANGELOG.md must be included in Docker image (already in build context)
- HTML output must be safe (sanitized or from trusted source only)
- Should work with htmx pattern (modal or inline partial)

## Integration Points

- New `triggarr/changelog.py` — parser module
- `triggarr/web/routes.py` — new route
- `triggarr/templates/base.html` — nav link
- `CHANGELOG.md` — new file in repo root
