# Project

## What This Is

A lightweight Docker-based Python automation daemon that triggers searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a configurable schedule, with closed-loop download tracking and a dark theme web UI. Built with FastAPI + htmx + Tailwind CSS v4. Docker-first deployment to ghcr.io/thejuran/triggarr.

## Core Value

Reliably trigger searches in configured *arr instances for missing and upgrade-eligible media on a schedule, with closed-loop feedback showing what was actually grabbed — without exposing credentials or expanding attack surface.

## Current State

~10,000 Python LOC with 873 tests passing in the current S05 closure run. 8 historical milestones shipped (v1.0–v2.6.1-dev). All 18 tracked requirements are validated, with 2 deferred and 3 explicit anti-features/out-of-scope items.

Current active milestone: Portable Config Directory & Documentation Refresh. S01 verified the portable config/data directory contract: `TRIGGARR_CONFIG_DIR` must be absolute, controls `triggarr.toml`, `state.json`, and derived `triggarr.db` when set before process import/startup, and `/config` remains the env-unset Docker/default fallback. S02 refreshed README/TODO/SECURITY-facing documentation for nested multi-instance config, standalone config directories, Docker behavior, and auth/security posture. S03 completed integrated verification evidence for the original documentation refresh, but validation found auth/proxy documentation and evidence-artifact gaps. S04 remediated those gaps: session-cookie Secure decisions now rely on ASGI `request.url.scheme`, Uvicorn remains the sole forwarded-proto trust boundary through `TRUSTED_PROXY_IPS`, README/SECURITY External-auth guidance requires upstream authentication/authorization plus blocked direct access, docs-accuracy tests guard those claims, and S04 evidence supersedes the stale S02 placeholder summary. S05 added the final documentation-UAT/release-gate evidence trail: a cold-reader review packet for `README.md`, `SECURITY.md`, and `TODO.md`, an explicit unresolved human UAT/deep-review gate note for auto-mode, and a release-gate evidence index with passing mechanical diagnostics.

Release-readiness caveat after S05: mechanical verification passes, but human documentation UAT and the `/deep-review` release decision remain unresolved because auto-mode had no human approval, change request, or explicit deferral. Milestone validation should remain needs-attention until a human resolves that gate. Existing Starlette TestClient per-request cookie deprecation warnings are still present in auth tests but do not fail verification.

Key capabilities delivered:
- Round-robin search engine with per-app and per-instance cursors and season-level Sonarr search
- Closed-loop tracking pipeline: polls *arr history after searches, correlates grabs, updates outcomes
- Dashboard with connection health, queue sizes, position labels, outcome badges, grab effectiveness stats
- Settings editor with masked API keys, skip-unreleased toggle, hard max cap, and per-instance configuration
- Search history with filtering, pagination, SQLite persistence, and per-instance scoping
- Multi-instance config model with v2.2 auto-migration (Phase 33)
- Per-instance state with independent round-robin cursors (Phase 34)
- Tag name → ID resolution via *arr API and tag-based search filtering (Phases 35–36)
- Portable config/data directory behavior via absolute `TRIGGARR_CONFIG_DIR`, with Docker-compatible `/config` default
- Application authentication modes (`Forms`, `Basic`, `External`, `Disabled`), setup flow, API-key access, CSRF protection, security headers, and ASGI-scheme-based secure-cookie handling
- CI/CD pipeline, GHCR publishing, Docker multi-stage build with PUID/PGID

## Architecture / Key Patterns

- **Stack:** Python 3.13, FastAPI, httpx, Pydantic, APScheduler 3.x, aiosqlite, Jinja2, htmx, Tailwind CSS v4, loguru, ruff
- **Config:** TOML-based with pydantic-settings, atomic file writes (tempfile + fsync + os.replace); `TRIGGARR_CONFIG_DIR` must be absolute and defaults to `/config`
- **Security:** SecretStr for API keys and auth secrets, loguru redacting sink, signed session cookies, setup/auth middleware, CSRF via Origin checking, SSRF validation, secure deployment documentation, secure cookies based on ASGI scheme, and forwarded-proto trust constrained to Uvicorn proxy-header handling via `TRUSTED_PROXY_IPS`
- **State:** JSON state file with per-instance round-robin cursors; SQLite for search history/tracking is derived beside `state.json`
- **Docker:** Multi-stage build (pytailwindcss builder + python slim runtime), PUID/PGID entrypoint, least-privilege defaults, `/config` volume default
- **Testing:** pytest-asyncio with asyncio_mode=auto, ruff linting (E,F,I,UP,B,SIM), line-length 120; docs-accuracy tests guard security/operator documentation claims and README TOML examples
- **Evidence/Gates:** S05 artifacts separate human documentation UAT from agent-side verification. `S05-UAT-GATE.md` is the source for human gate status, and `S05-RELEASE-GATE-EVIDENCE.md` indexes mechanical diagnostics and release-readiness recommendation.
- **Key modules:** `triggarr/models/config.py` (InstanceConfig, Settings, config-dir contract), `triggarr/state.py` (state path and cursor persistence), `triggarr/search/engine.py` (cycle functions), `triggarr/clients/` (base + radarr/sonarr/lidarr), `triggarr/web/routes.py`, `triggarr/web/middleware.py`, and `triggarr/web/security.py` (FastAPI routes/auth/security), `triggarr/tracking.py` (grab detection), `triggarr/db.py` (SQLite)

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [x] M-v1.0: MVP — Search engine, web UI, Docker, security, tests (shipped 2026-02-24)
- [x] M-v1.1: Ship & Document — CI/CD, GHCR publishing, hard max, SQLite history, README (shipped 2026-02-24)
- [x] M-v1.2: Polish & Harden — Search diagnostics, dashboard observability, history UI, deep review (shipped 2026-02-24)
- [x] M-v2.0: Closed-Loop Tracking — Grab detection, outcome badges, effectiveness stats, rename (shipped 2026-03-09)
- [x] M-v2.1: Harden & Fix — Config dir, reverse proxy, path validation, temp file safety (shipped 2026-03-09)
- [x] M-v2.2: Skip Unreleased Media — Unreleased filter, eligible counts, dashboard skip badges (shipped 2026-03-09)
- [x] M001: Multi-Instance & Tag Filtering — Multiple *arr instances, per-instance tags, scoped observability, version display (shipped 2026-03-11)
- [x] M004: Version Bump & Release Tag Cleanup — deleted dev tags, version already correct (shipped 2026-04-07)
- [x] M005: In-App Changelog — Local CHANGELOG.md, regex parser, htmx modal in nav bar (shipped 2026-04-07)
- [ ] M001: Portable Config Directory & Documentation Refresh — S01/S02/S03/S04 complete; S05 produced review/gate evidence with human docs UAT and `/deep-review` still unresolved for final milestone validation
