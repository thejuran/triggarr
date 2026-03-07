---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Closed-Loop Tracking
status: completed
stopped_at: Completed 21-02-PLAN.md
last_updated: "2026-03-07T02:40:54.551Z"
last_activity: 2026-03-06 -- Completed 21-02 dashboard stats UI (outcome badges, filter pills, settings form)
progress:
  total_phases: 8
  completed_phases: 5
  total_plans: 11
  completed_plans: 16
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** Reliably trigger searches in Radarr and Sonarr for missing and upgrade-eligible media on a schedule, without exposing credentials or expanding attack surface.
**Current focus:** Phase 20.2 - Deep Review — Code Quality (complete)

## Current Position

Phase: 21 of 21 (Dashboard & Stats)
Plan: 2 of 2 in current phase
Status: Plan 21-02 complete
Last activity: 2026-03-06 -- Completed 21-02 dashboard stats UI (outcome badges, filter pills, settings form)

Progress: [██████████] 100%

## Performance Metrics

**Overall:**
- Total plans completed: 44 (v1.0: 18, v1.1: 5, v1.2: 8, v2.0: 13)
- Milestones shipped: 3 (v1.0, v1.1, v1.2)

**By Phase (v2.0):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| Phase 17 P01 | 1min | 2 tasks | 3 files |
| Phase 17 P02 | 3min | 2 tasks | 2 files |
| Phase 17 P03 | 9min | 3 tasks | 9 files |
| Phase 18 P01 | 2min | 3 tasks | 4 files |
| Phase 18 P02 | 4min | 3 tasks | 3 files |
| Phase 19 P01 | 2min | 2 tasks | 4 files |
| Phase 19 P02 | 2min | 2 tasks | 2 files |
| Phase 20 P01 | 2min | 2 tasks | 2 files |
| Phase 20 P02 | 2min | 2 tasks | 3 files |
| Phase 20 P03 | 2min | 2 tasks | 2 files |
| Phase 20.1 P01 | 4min | 2 tasks | 2 files |
| Phase 20.1 P02 | 1min | 2 tasks | 6 files |
| Phase 20.2 P01 | 12min | 2 tasks | 7 files |
| Phase 20.2 P02 | 13min | 2 tasks | 10 files |
| Phase 21 P01 | 7min | 2 tasks | 6 files |
| Phase 21 P02 | 11min | 2 tasks | 5 files |

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
- [Phase 19-01]: GrabEvent uses extra=ignore to safely handle extra fields from *arr API responses
- [Phase 19-01]: eventType=1 integer enum passed in extra_params (serialized as string in URL)
- [Phase 19-02]: Most recent search claims grabs first via reverse-chronological processing order
- [Phase 19-02]: Inclusive boundary: grabs at exactly search_time + window are matched
- [Phase 19-02]: Claimed-set prevents double-attribution when multiple search windows overlap
- [Phase 20-01]: frozenset allowlist for stat column names prevents SQL injection in dynamic SET clause
- [Phase 20-01]: Single db.commit() after both UPDATE statements ensures atomic outcome+stats update
- [Phase 20-02]: Added outcome column to get_trackable_entries for Sonarr searched vs partial distinction
- [Phase 20-02]: missing_count=None treated as 0 expected -- any grab resolves to grabbed
- [Phase 20-02]: Partial entries only get stat increments at terminal state (window expiry or upgrade to grabbed)
- [Phase 20-03]: Tracking runs inside search_lock to prevent concurrent DB writes
- [Phase 20-03]: Tracking failure isolated with nested try/except -- does not affect state save
- [Phase 20-03]: Tracking checks ALL pending entries per cycle, not just current app
- [Phase 20.1-01]: Monkeypatched Path.exists() in fresh-install test (aiosqlite creates file before run_migrations)
- [Phase 20.1-02]: urlencode applied to ALL dynamic values in hx-get attributes for defense-in-depth
- [Phase 20.1-02]: _sanitize_exc dispatches on exception type to avoid leaking internal details
- [Phase 20.1-02]: Rate limiter uses optimistic pre-lock check plus authoritative re-check inside lock
- [Phase 20.2-01]: 0-based pass counter: default=0, first wrap sets to 1, template shows badge at > 0
- [Phase 20.2-01]: Restructured _sonarr_outcome: expected==0 handled at top as first branch, eliminating dead inner block
- [Phase 20.2-02]: OSError included in tracking exception tuple for filesystem error coverage
- [Phase 20.2-02]: model_validator raises ValueError wrapped in Pydantic ValidationError -- tests match accordingly
- [Phase 21-01]: SUM(CASE WHEN) for SQLite FILTER clause compatibility; resolved_at in update_outcome_and_stats
- [Phase 21-02]: request_timeout uses safe_int (int) -- Pydantic coerces to float for GeneralConfig
- [Phase 21-02]: tracking_delay_seconds remains preserved (not user-editable) per CONTEXT.md

### Pending Todos

None.

### Blockers/Concerns

- Radarr MovieHistoryEventType integers beyond grabbed=1 need live instance verification (Phase 19)
- Sonarr season pack grab counting assumptions need live verification (Phase 20)
- Tracking delay (90s default) interaction with short search intervals needs documentation (Phase 20)

## Session Continuity

Last session: 2026-03-07T02:35:43Z
Stopped at: Completed 21-02-PLAN.md
Resume file: .planning/phases/21-dashboard-stats/21-02-SUMMARY.md
