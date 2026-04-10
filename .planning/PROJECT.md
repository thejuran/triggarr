# Triggarr

## What This Is

A lightweight Docker-based tool that automates searches in Radarr, Sonarr, and Lidarr for wanted and cutoff unmet items, with closed-loop download tracking and multi-instance support. Configurable round-robin searches at configurable intervals detect when searched items are actually grabbed, showing per-item outcome badges and aggregate effectiveness stats on a dark theme web UI. Supports multiple named Radarr/Sonarr/Lidarr instances with per-instance tag-based search filtering, instance health monitoring, and update notifications. Includes CI/CD pipeline, automated GHCR publishing, SQLite search history with tracking correlation, and comprehensive documentation. Built with Python/FastAPI and htmx/Jinja2. Zero credential exposure by design.

## Core Value

Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback showing what was actually grabbed — without exposing credentials or expanding attack surface.

## Current Milestone: v2.5 Dashboard UI Refresh

**Goal:** Refresh the web dashboard visual language without changing backend data shapes — tighter hierarchy, clearer instance health, and a sticky Recent Activity rail — using `.aidesigner/enhanced-mockup-v3.html` as the design contract.

**Target features:**
- Foundations: new elevation token, `focus-visible` rings, `prefers-reduced-motion`, Geist Mono, wider `max-w-7xl` container
- Sticky nav with active-tab underline and pulsing update-available dot
- Compact one-line health strip + hero Grab Rate card with per-app bar chart
- Tightened app cards: unified connection pill, schedule row, pass pills, hover elevation
- Diagonal danger stripes + Retry button on unreachable cards
- 3-column Services grid on `xl:` breakpoint
- Application Log: Geist Mono, TAILING indicator, level-colored rows, expandable bottom-terminal mode
- New sticky **Recent Activity** rail on the right (timeline view, replaces inline Search Log)
- Docs drift: move Lidarr out of Out of Scope, document existing Lidarr support

## Requirements

### Validated

- ✓ Connect to Radarr/Sonarr via API key + URL with startup validation — v1.0
- ✓ Fetch wanted (missing) and cutoff unmet items from both apps — v1.0
- ✓ Round-robin through items sequentially with persistent cursors — v1.0
- ✓ Sonarr searches at season level via SeasonSearch command — v1.0
- ✓ Configurable items per cycle and search interval per app — v1.0
- ✓ Web UI dashboard with htmx polling (status, search log, queue position, counts) — v1.0
- ✓ Web UI config editor with masked API keys — v1.0
- ✓ Search-now button for immediate per-app trigger — v1.0
- ✓ Connection health monitoring with "unreachable since" display — v1.0
- ✓ Per-app enable/disable toggle — v1.0
- ✓ API keys never exposed via any HTTP endpoint — v1.0
- ✓ CSRF protection via Origin/Referer middleware — v1.0
- ✓ SSRF validation, input clamping, config file permissions — v1.0
- ✓ Docker deployment with PUID/PGID, least-privilege, HEALTHCHECK — v1.0
- ✓ State recovery, schema migration, race condition serialization — v1.0
- ✓ 115 tests covering all async paths — v1.0
- ✓ README with install guide, config reference, and security model — v1.1
- ✓ GitHub Actions CI (pytest, lint, Docker build validation) — v1.1
- ✓ Docker release pipeline — dev tag on push, latest + version on release (ghcr.io) — v1.1
- ✓ Local deep code review convention (Claude offers /deep-review before push) — v1.1
- ✓ Configurable hard limit / safety ceiling on max items per cycle — v1.1
- ✓ Persistent search history beyond in-memory log (SQLite storage) — v1.1
- ✓ Search history UI with filtering and pagination — v1.2
- ✓ Sonarr v3/v4 API version detection and logging — v1.2
- ✓ pageSize ceiling logging for large libraries — v1.2
- ✓ CI workflow pushed to GitHub with caching for fast remote runs — v1.2
- ✓ Dashboard position labels show "X of Y" progress — v1.2
- ✓ Application logs visible in web dashboard (live log viewer) — v1.2
- ✓ Search detail log with outcome/detail info per entry — v1.2
- ✓ Deep code review: XSS, SSRF, cursor, atomic write, input validation fixes — v1.2
- ✓ Poll Radarr/Sonarr history endpoints after searches to detect grabs — v2.0
- ✓ Update search history entries with grabbed/partial/unresolved outcome badges — v2.0
- ✓ Aggregate stats on dashboard showing search effectiveness (searched-to-grabbed rate) — v2.0
- ✓ Lifetime stats cards: movies found/updated, episodes found/updated (triggarr-triggered only) — v2.0
- ✓ Time-to-grab metric on dashboard — v2.0
- ✓ Rate limiting on search-now endpoint — v2.0
- ✓ CSRF protection on settings POST verified/hardened — v2.0
- ✓ Bounded search history table growth (configurable max rows) — v2.0
- ✓ Persistent WAL-mode SQLite connection (replaces connection-per-op) — v2.0
- ✓ Health check endpoint for container orchestrators — v2.0
- ✓ Graceful shutdown handler — v2.0
- ✓ Request timeout on outbound HTTP calls — v2.0
- ✓ Configurable pageSize defaults — v2.0
- ✓ Deep security review: row_factory guards, XSS urlencode, rate limiter race fix, migration safety — v2.0
- ✓ Deep quality review: type annotations, pass counter, sorted migrations, model validators — v2.0
- ✓ Project renamed from Fetcharr to Triggarr across package, Docker, CI/CD, and docs — v2.0
- ✓ Configurable config directory via `TRIGGARR_CONFIG_DIR` env var — v2.1
- ✓ CSS and static assets work behind reverse proxy via ROOT_PATH — v2.1
- ✓ Config path validation rejects relative/traversal paths at startup — v2.1
- ✓ Temp file cleanup on os.replace failure during settings save — v2.1
- ✓ Module-level freeze constraint documented and tested — v2.1
- ✓ Consistent request.url_for across all templates for root_path awareness — v2.1
- ✓ Configurable toggle to skip unreleased Radarr movies via web UI checkbox — v2.2
- ✓ Skip movies until digital or physical release date has passed — v2.2
- ✓ Null/missing release dates pass through filter (not blackholed) — v2.2
- ✓ Cutoff-unmet items never filtered (already have files) — v2.2
- ✓ Dashboard eligible vs total counts per app with skip-count indicator — v2.2
- ✓ Skip badge math uses monitored count (not raw total) for accuracy — v2.2
- ✓ Multiple named Radarr/Sonarr instances with independent URL, API key, schedule, and batch sizes — v2.3
- ✓ Per-instance round-robin cursors that persist across restarts — v2.3
- ✓ Auto-migration from single-instance to multi-instance config on upgrade — v2.3
- ✓ Per-instance tag filtering for missing and cutoff queues — v2.3
- ✓ Tag autocomplete from *arr instances in settings UI — v2.3
- ✓ Instance CRUD (add/edit/remove/enable/disable) from web UI — v2.3
- ✓ Instance health summary card with connected/disconnected counts — v2.3
- ✓ Tag warning badges on app cards when configured tag not found — v2.3
- ✓ Per-instance effectiveness stats with instance filter dropdown — v2.3
- ✓ GitHub release update notification in nav bar — v2.3
- ✓ Dismissible migration banner for v2.2→v2.3 upgrade — v2.3
- ✓ Deep review: XSS, CSRF, version parsing, input validation hardening — v2.3
- ✓ CONTRIBUTING.md with fork/branch/PR workflow and dev setup instructions — v2.4
- ✓ SECURITY.md with vulnerability reporting and security model summary — v2.4
- ✓ GitHub issue templates (bug report + feature request as YAML forms) — v2.4
- ✓ Repo metadata (topics + GitHub Discussions) — v2.4
- ✓ Unhappy-path tests for connection failures (DNS, SSL, timeout, mid-cycle) — v2.4
- ✓ Unhappy-path tests for bad API responses (malformed JSON, 403/502, truncated pagination) — v2.4
- ✓ Unhappy-path tests for corrupt state/config (broken TOML, SQLite, JSON, migration) — v2.4
- ✓ Unhappy-path tests for search logic edge cases (empty queues, tag filtering, cursors) — v2.4

### Active

**v2.5 Dashboard UI Refresh** — see Current Milestone section above. Requirements in `.planning/REQUIREMENTS.md`.

### Undocumented shipped capability (discovered during v2.5 planning)

- ✓ Lidarr support across search engine, settings UI, stats row, app cards, and history filters — shipped in v2.3 multi-instance work but never documented as a first-class requirement

## Current State

Starting v2.5 Dashboard UI Refresh. Previous milestone v2.4 shipped open-source community health files and comprehensive unhappy-path test coverage.

### Out of Scope

- User accounts / authentication — local network tool, no auth needed
- Readarr / other *arr support — Radarr + Sonarr + Lidarr only
- Notifications (Discord, Telegram, Apprise) — web UI log sufficient
- Prowlarr / indexer management — uses existing *arr search infrastructure
- Download queue management — *arr apps handle this
- Media discovery / TMDB browsing — Overseerr's job
- OAuth / SSO — no accounts means no auth flows
- Mobile app — web UI sufficient
- Download client integration (qBit/SAB polling) — *arr apps manage download clients
- Webhook receiver for *arr grab notifications — adds coupling, network config, and attack surface
- Full import tracking (downloadFolderImported) — two-phase tracking for marginal value
- Per-indexer effectiveness stats — Prowlarr's job
- Automated re-search of unresolved items — round-robin handles naturally
- Historical backfill of pre-triggarr grabs — impossible to attribute correctly
- Cookie-based CSRF tokens — sessionless app; Origin/Referer validation is correct approach
- slowapi/Redis for rate limiting — single-user local tool; in-memory check sufficient

## Context

Shipped v2.4 with ~15,979 Python LOC (5,308 source + 10,671 test). 606 tests passing. 47 phases, 77 plans completed across 10 milestones.
Tech stack: Python 3.13, FastAPI, httpx, Pydantic, pydantic-settings, APScheduler, aiosqlite, Jinja2, htmx, Tailwind CSS v4, loguru, ruff.
Docker: multi-stage build with pytailwindcss builder, python:3.13-slim production, PUID/PGID entrypoint.
CI/CD: GitHub Actions (pytest, ruff, Docker build validation) with uv caching + GHCR release workflow with BuildKit cache.
Registry: ghcr.io/thejuran/triggarr
Repo: github.com/thejuran/triggarr

Known tech debt: _update_info as module-level mutable dict (should move to app.state); tag_warnings typed as list[dict] (should be list[TagWarning] TypedDict); Sonarr eligible/total mixes units (accepted); test_state_wrong_structure_list_crashes documents a limitation in _merge_defaults (list JSON).

## Constraints

- **Tech stack**: Python (FastAPI) + htmx/Jinja2 — matches user's existing project experience
- **Deployment**: Docker container with docker-compose support
- **Security**: API keys must never be exposed via any HTTP endpoint
- **Scope**: Search automation only — deliberately minimal to reduce attack surface

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python/FastAPI over Go | User familiarity, faster iteration | ✓ Good — built in 2 days |
| htmx/Jinja2 over React SPA | Lightweight, no build step, server-rendered | ✓ Good — simple, fast |
| Season-level Sonarr search | Avoids hammering indexers with full-show searches | ✓ Good |
| Round-robin over random | Ensures every item gets searched eventually | ✓ Good |
| No auth | No user accounts = no passwords to store | ✓ Good — core security decision |
| Single instance per app | Simpler config, matches user's setup | ✓ Good |
| APScheduler 3.x over 4.x | 4.x still alpha, 3.x stable with AsyncIOScheduler | ✓ Good |
| Origin/Referer CSRF over tokens | No auth/sessions means no cookies to protect | ✓ Good |
| Vendored htmx over CDN | Reproducible builds, no external dependency | ✓ Good |
| Custom loguru sink for redaction | Filter only sees message, sink sees full output including tracebacks | ✓ Good |
| Ruff rule sets E,F,I,UP,B,SIM | Comprehensive but non-noisy linting | ✓ Good |
| Proportional hard max split | floor(missing/total*max) for missing, remainder for cutoff | ✓ Good |
| Toggle-pill filter pattern for history | URL param manipulation in Jinja2, no JS framework needed | ✓ Good |
| Atomic config write (tempfile + fsync + os.replace) | Prevents partial writes | ✓ Good |
| Post-search tracking inside cycle functions | No separate scheduler job; tracks after each search cycle inside search_lock | ✓ Good — v2.0 |
| Probabilistic grab attribution (timestamp window) | No commandId link available; window matching sufficient | ✓ Good — v2.0 |
| Zero new dependencies for v2.0 | All features achievable with existing stack + stdlib | ✓ Good — v2.0 |
| frozenset allowlist for stat column names | Prevents SQL injection in dynamic SET clause | ✓ Good — v2.0 |
| Double-checked locking for rate limiter | Pre-check optimistic, re-check inside lock authoritative | ✓ Good — v2.0 |
| _sanitize_exc type-based dispatch | Avoids leaking internal details in exception messages | ✓ Good — v2.0 |
| SUM(CASE WHEN) for SQLite compatibility | FILTER clause not available in all SQLite versions | ✓ Good — v2.0 |
| get_config_dir() function for testable env var reading | Avoids module reload issues in tests | ✓ Good — v2.1 |
| url_for via request.url_for everywhere | Consistent root_path support for reverse proxies | ✓ Good — v2.1 |
| Absolute-path-only config dir validation | Prevents relative/traversal path misconfiguration | ✓ Good — v2.1 |
| Null release dates = pass through (not blackhole) | PITFALLS.md approach; unknown != unreleased | ✓ Good — v2.2 |
| Filter uses digitalRelease/physicalRelease only | inCinemas = cam quality; status field lags behind dates | ✓ Good — v2.2 |
| Filter after filter_monitored, before cursor/slice | Correct pipeline position: skip only monitored unreleased | ✓ Good — v2.2 |
| Cutoff-unmet never filtered | Already have files = proven released | ✓ Good — v2.2 |
| Skip badge uses missing_monitored not missing_count | Avoids inflating skip count with unmonitored items | ✓ Good — v2.2 |
| contextlib.suppress for date parsing | ruff SIM105 compliance; cleaner than try/except/pass | ✓ Good — v2.2 |
| Dict-based multi-instance config (nested TOML tables) | Natural TOML mapping, pydantic-settings compatible | ✓ Good — v2.3 |
| Auto-migration from v2.2 flat config to v2.3 nested format | Zero-downtime upgrade path | ✓ Good — v2.3 |
| Tag resolution per-cycle (not cached) | Tags may change in *arr; fresh resolution ensures correctness | ✓ Good — v2.3 |
| Mutable dict for _update_info Jinja2 global | In-place update avoids re-registration; no .clear() for atomicity | ✓ Good — v2.3 |
| HX-Request header check for CSRF on DELETE endpoints | Htmx sends custom header; cross-origin requests blocked by CORS preflight | ✓ Good — v2.3 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-10 — started v2.5 Dashboard UI Refresh milestone*
