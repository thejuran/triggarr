# Milestones

## v1.0 MVP (Shipped: 2026-02-24)

**Phases completed:** 8 phases, 18 plans
**Timeline:** 2 days (Feb 23–24, 2026)
**LOC:** ~3,672 Python + ~213 HTML | 115 tests
**Git range:** e56ced3..b4e59ae

**Delivered:** A lightweight Docker-based search automation daemon for Radarr and Sonarr with a dark theme web UI, round-robin scheduling, and zero credential exposure.

**Key accomplishments:**
- Config, state, and API clients with Pydantic models, SecretStr API keys, loguru redaction, and atomic JSON state
- Round-robin search engine with per-app cursors, season-level Sonarr search, and APScheduler integration
- Dark theme web UI with htmx polling dashboard, config editor, and search-now trigger
- Multi-stage Docker packaging with PUID/PGID privilege dropping, HEALTHCHECK, and localhost detection
- Security hardening — CSRF middleware, SSRF validation, input clamping, Docker least-privilege, vendored htmx
- Comprehensive resilience and test coverage — 115 tests, state recovery, schema migration, race condition fix

---


## v1.1 Ship & Document (Shipped: 2026-02-24)

**Phases completed:** 4 phases, 5 plans
**Timeline:** 2026-02-24 (same day as v1.0)
**Git range:** v1.0..HEAD (30 commits)
**Files:** 49 files changed, +4,192 -173 lines

**Delivered:** CI/CD pipeline, automated Docker releases to GHCR, search enhancements (hard max cap + SQLite history), and comprehensive README documentation.

**Key accomplishments:**
- GitHub Actions CI with pytest, ruff linting, and Docker build validation in three parallel jobs
- Automated GHCR publishing — `:dev` on push to main, `:latest` + version tag on release
- Hard max items per cycle with proportional batch capping and settings UI integration
- SQLite persistent search history with auto-migration from JSON and 500-row auto-pruning
- Complete README with Docker install guide, TOML config reference, security model, and screenshot placeholders

---


## v1.2 Polish & Harden (Shipped: 2026-02-24)

**Phases completed:** 4 phases, 8 plans
**Timeline:** 2026-02-24 (same day)
**LOC:** ~5,225 Python | 174 tests
**Git range:** 913d6b2..34b75ee (39 commits, 47 files changed, +4,998 -88 lines)

**Delivered:** Search diagnostics, dashboard observability (position labels, log viewer, outcome badges), browsable search history with filtering/pagination, and a deep code review with security fixes.

**Key accomplishments:**
- CI workflow hardened with uv package caching and Docker BuildKit GHA cache for fast remote runs
- Sonarr v3/v4 API version detection at startup with per-cycle diagnostic summary logging
- Dashboard enhanced with "X of Y" position labels, colored outcome badges, and live application log viewer with secret redaction
- Search history page with toggle-pill filters (app/queue/outcome), text search with debounce, and paginated results
- Deep code review: 7 warning-level fixes (XSS tojson, SSRF blocklist, cursor leaks, atomic config writes, input validation) with 7 regression tests
- 8 medium-severity issues documented and deferred (rate limiting, CSRF, history growth, connection pooling, health check, graceful shutdown, request timeouts, configurable pageSize)

**Tech debt deferred to next milestone:**
- M1: No rate limiting on search-now endpoint
- M2: No CSRF protection on settings POST
- M3: Unbounded search history table growth
- M4: No connection pooling for aiosqlite
- M5: Hardcoded pageSize defaults not configurable
- M6: No health check endpoint
- M7: No graceful shutdown handler
- M8: No request timeout on outbound HTTP calls

---

