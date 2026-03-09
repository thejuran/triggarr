# Triggarr

## What This Is

A lightweight Docker-based tool that automates searches in Radarr and Sonarr for wanted and cutoff unmet items, with closed-loop download tracking. Configurable round-robin searches at configurable intervals detect when searched items are actually grabbed, showing per-item outcome badges and aggregate effectiveness stats on a dark theme web UI. Includes CI/CD pipeline, automated GHCR publishing, SQLite search history with tracking correlation, and comprehensive documentation. Built with Python/FastAPI and htmx/Jinja2. Zero credential exposure by design.

## Core Value

Reliably trigger searches in Radarr and Sonarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback showing what was actually grabbed — without exposing credentials or expanding attack surface.

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

### Active

## Current Milestone: v2.3 Multi-Instance & Tag Filtering

**Goal:** Support multiple Radarr/Sonarr instances with per-instance tag-based search filtering.

**Target features:**
- Multiple Radarr/Sonarr instances (named, each with own URL/API key/schedule)
- Instance management via both TOML config and web UI
- Per-instance tag filtering for missing queue (e.g. `triggarr-missing` tag)
- Per-instance tag filtering for cutoff queue (e.g. `triggarr-upgrade` tag)
- Default behavior unchanged: all monitored items searched when no tag configured
- Dashboard and search history scoped per instance

### Out of Scope

- User accounts / authentication — local network tool, no auth needed
- Lidarr / Readarr / other *arr support — Radarr + Sonarr only
- ~~Multi-instance support~~ — now in scope for v2.3 (GitHub #8)
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

Shipped v2.2 with ~8,964 Python LOC (3,389 source + 5,575 test). 302 tests passing. 28 phases, 56 plans completed across 6 milestones.
Tech stack: Python 3.13, FastAPI, httpx, Pydantic, APScheduler, aiosqlite, Jinja2, htmx, Tailwind CSS v4, loguru, ruff.
Docker: multi-stage build with pytailwindcss builder, python:3.13-slim production, PUID/PGID entrypoint.
CI/CD: GitHub Actions (pytest, ruff, Docker build validation) with uv caching + GHCR release workflow with BuildKit cache.
Registry: ghcr.io/thejuran/triggarr
Repo: github.com/thejuran/triggarr

Known tech debt: missing_monitored not in AppState TypedDict (cosmetic); Sonarr eligible/total mixes units (accepted).

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

---
*Last updated: 2026-03-09 after v2.3 milestone start*
