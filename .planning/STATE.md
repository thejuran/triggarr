# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** Reliably trigger searches in Radarr and Sonarr for missing and upgrade-eligible media on a schedule, without exposing credentials or expanding attack surface.
**Current focus:** Phase 18 - Security & Operations

## Current Position

Phase: 18 of 21 (Security & Operations)
Plan: 2 of 2 in current phase
Status: Phase Complete
Last activity: 2026-02-25 -- Completed 18-02 (Graceful Shutdown & CSRF Integration)

Progress: [██████████] 100%

## Performance Metrics

**Overall:**
- Total plans completed: 36 (v1.0: 18, v1.1: 5, v1.2: 8, v2.0: 5)
- Milestones shipped: 3 (v1.0, v1.1, v1.2)

**By Phase (v2.0):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| Phase 17 P01 | 1min | 2 tasks | 3 files |
| Phase 17 P02 | 3min | 2 tasks | 2 files |
| Phase 17 P03 | 9min | 3 tasks | 9 files |
| Phase 18 P01 | 2min | 3 tasks | 4 files |
| Phase 18 P02 | 4min | 3 tasks | 3 files |

*Updated after each plan completion*

## Accumulated Context

### Decisions

Full decision log in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v1.2]: Connection-per-op SQLite pattern identified as tech debt (DEBT-04)
- [v1.2]: Auto-prune at 500 rows needs tracking-awareness (DEBT-03)
- [v2.0 research]: Post-search tracking integrates inside cycle functions, not as separate scheduler job
- [v2.0 research]: Zero new PyPI dependencies -- all features achievable with existing stack + stdlib
- [v2.0 research]: Grab attribution is probabilistic (timestamp window), not deterministic (no commandId link)
- [Phase 17-01]: No validators on new GeneralConfig fields -- Pydantic type coercion sufficient
- [Phase 17-01]: New TOML entries commented out to match existing convention
- [Phase 17-02]: Backup file uses Path.with_suffix() replacing .db extension
- [Phase 17-02]: MIGRATIONS dict declared empty at top, reassigned after function definitions
- [Phase 17-02]: Row factory set/reset around queries to avoid shared connection side effects
- [Phase 17-03]: Lifespan sets WAL mode + synchronous=NORMAL on shared connection
- [Phase 17-03]: Settings save preserves new config values from current_settings (form UI deferred)
- [Phase 17-03]: RadarrClient/SonarrClient updated to pass through page_size parameter
- [Phase 18-01]: Rate limit state on app.state (not module-level) for test isolation
- [Phase 18-01]: Health endpoint returns 200 when no apps enabled (valid awaiting-setup state)
- [Phase 18-01]: Dockerfile start-period increased to 30s for first search cycle latency
- [Phase 18-02]: Task 1 scheduler changes already committed in 18-01 -- no duplicate commit needed
- [Phase 18-02]: Used builtin TimeoutError instead of asyncio.TimeoutError per ruff UP041
- [Phase 18-02]: CSRF integration split into cross-origin rejected and same-origin passes tests

### Pending Todos

None.

### Blockers/Concerns

- Radarr MovieHistoryEventType integers beyond grabbed=1 need live instance verification (Phase 19)
- Sonarr season pack grab counting assumptions need live verification (Phase 20)
- Tracking delay (90s default) interaction with short search intervals needs documentation (Phase 20)

## Session Continuity

Last session: 2026-02-25
Stopped at: Completed 18-02-PLAN.md (Phase 18 complete)
Resume file: None
