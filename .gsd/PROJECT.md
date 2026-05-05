# Project

## What This Is

A lightweight Docker-based Python automation daemon that triggers searches in Radarr and Sonarr for missing and upgrade-eligible media on a configurable schedule, with closed-loop download tracking and a dark theme web UI. Built with FastAPI + htmx + Tailwind CSS v4. Docker-first deployment to ghcr.io/thejuran/triggarr.

## Core Value

Reliably trigger searches in Radarr and Sonarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback showing what was actually grabbed — without exposing credentials or expanding attack surface.

## Current State

~10,000 Python LOC. 520+ tests in the broader project, with the current portable config-dir focused suite passing 52/52. 8 historical milestones shipped (v1.0–v2.6.1-dev). All 18 requirements validated, 0 active. 2 deferred (cross-instance dedup, dynamic hot-add).

Current active milestone: Portable Config Directory & Documentation Refresh. Slice S01 is complete: `TRIGGARR_CONFIG_DIR` has been verified as an absolute-path config/data directory controlling `triggarr.toml`, `state.json`, and derived `triggarr.db`; `/config` remains the env-unset Docker/default fallback; relative config-dir values fail early. S02 still needs to refresh README/TODO/project docs, and S03 still needs full-suite/lint/docs-UAT closure.

Key capabilities delivered:
- Round-robin search engine with per-app cursors and season-level Sonarr search
- Closed-loop tracking pipeline: polls *arr history after searches, correlates grabs, updates outcomes
- Dashboard with connection health, queue sizes, position labels, outcome badges, grab effectiveness stats
- Settings editor with masked API keys, skip-unreleased toggle, hard max cap
- Search history with filtering, pagination, SQLite persistence
- Multi-instance config model with v2.2 auto-migration (Phase 33)
- Per-instance state with independent round-robin cursors (Phase 34)
- Tag name → ID resolution via *arr API and tag-based search filtering (Phases 35–36)
- Portable config/data directory behavior via absolute `TRIGGARR_CONFIG_DIR`, with Docker-compatible `/config` default
- CI/CD pipeline, GHCR publishing, Docker multi-stage build with PUID/PGID

## Architecture / Key Patterns

- **Stack:** Python 3.13, FastAPI, httpx, Pydantic, APScheduler 3.x, aiosqlite, Jinja2, htmx, Tailwind CSS v4, loguru, ruff
- **Config:** TOML-based with pydantic-settings, atomic file writes (tempfile + fsync + os.replace); `TRIGGARR_CONFIG_DIR` must be absolute and defaults to `/config`
- **Security:** SecretStr for API keys, loguru redacting sink, CSRF via Origin checking, SSRF validation, no auth (intentional)
- **State:** JSON state file with per-instance round-robin cursors; SQLite for search history/tracking is derived beside `state.json`
- **Docker:** Multi-stage build (pytailwindcss builder + python:3.13-slim), PUID/PGID entrypoint, least-privilege, `/config` volume default
- **Testing:** pytest-asyncio with asyncio_mode=auto, ruff linting (E,F,I,UP,B,SIM), line-length 120
- **Key modules:** `triggarr/models/config.py` (InstanceConfig, Settings, config-dir contract), `triggarr/search/engine.py` (cycle functions), `triggarr/clients/` (base + radarr/sonarr), `triggarr/web/routes.py` (FastAPI routes), `triggarr/tracking.py` (grab detection), `triggarr/db.py` (SQLite)

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
- [ ] M001: Portable Config Directory & Documentation Refresh — S01 complete; S02/S03 remaining
