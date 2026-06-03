---
gsd_state_version: 1.0
milestone: v2.10
milestone_name: Recovery, Counts & Config Parity
status: completed
stopped_at: Phase 73 context gathered
last_updated: "2026-06-03T21:58:59.767Z"
last_activity: 2026-06-03 -- Phase 72 marked complete
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 4
  completed_plans: 3
  percent: 17
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-02)

**Core value:** Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.
**Current focus:** Phase 72 — password-reset-backend-token-lifecycle

## Current Position

Phase: 72 — COMPLETE
Plan: 1 of 3
Status: Phase 72 complete
Last activity: 2026-06-03 -- Phase 72 marked complete

### v2.10 milestone shape

Three disjoint, independently-phaseable tracks (no shared code), per the approved design spec `docs/superpowers/specs/2026-06-02-recovery-counts-config-design.md`. Phase numbering continues from v2.9's Phase 71 (starts at 72, not reset to 1). Track A is the largest/riskiest (auth surface) and is split into a backend phase + a UI phase; Tracks B and C are each a single phase. A cross-track documentation deliverable (DOCS-01) corrects the stale deferred record (DEBT-07/08/03 already shipped; DEBT-06 now shipped) and rides in Phase 75. Milestone-end NAS walkthrough exercises all three tracks against the deployed build; release/tag handled by the orchestrator, not as a roadmap phase.

| Phase | Goal | Requirements | Depends on |
|-------|------|--------------|------------|
| 72 — Password Reset Backend & Token Lifecycle | Filesystem-token reset endpoints: in-memory single-use 15-min token (log + `0600` file, never in any response), confirm rotates `session_secret` + auto-login, both endpoints rate-limited, `/reset` exempt from auth middleware | RCOV-02..06 | — (builds on shipped v2.6 auth) |
| 73 — Password Reset UI | "Forgot password?" link on login (only when `not needs_setup`) + styled request/confirm reset pages mirroring login.html/setup.html, inline field errors, success → dashboard | RCOV-01 | Phase 72 |
| 74 — Count-Only Refresh | Extract fetch+count+filter helper from `run_*_cycle` (cursor-non-advance structural); `POST /api/refresh-counts/{app}/{instance}` mirrors `search_now` minus search; per-card "Refresh counts" button; updates health+counts but NOT `last_run`/`last_success` or the SAFETY-03 failure counter | CNT-01..05 | — (disjoint; sequenced after Track A) |
| 75 — Drain-Timeout Config Parity & Deferred-Record Correction | `shutdown_drain_timeout` GeneralConfig field (`ge=1.0`) + settings numeric input; config is default, `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` overrides, `>=1.0` clamp on both; DOCS-01 deferred-record correction | CFG-03, CFG-04, DOCS-01 | — (disjoint; smallest rider, sequenced last) |

### Key v2.10 Phasing Rationale

- **Track A split into 72 (backend) + 73 (UI):** Track A is the high-risk auth-surface track. The token lifecycle (mint/store/validate, single-use, 15-min TTL, supersession), the confirm path (bcrypt rehash under `search_lock`, `session_secret` rotation, atomic TOML write + `chmod 0600`, auto-login cookie, token-file delete), the rate-limit on both endpoints (mirroring the `search_now` monotonic-timestamp pattern), and the `/reset` middleware exemption are all backend invariants that carry the milestone's adversarial test weight (token redaction, session rotation, rate-limit, unauthenticated reachability) — Phase 72. The user-facing surface (conditional "Forgot password?" link, request/confirm pages styled like login/setup) is a coherent UI phase — Phase 73, depends on 72. Pattern anchors: mirror the existing `change_password` route and the `search_now` rate-limit. **Reset auth exemption (precise):** `EXEMPT_PREFIXES` stays exactly `("/health", "/static", "/login", "/setup")` — `/reset` is NOT added to it. Reset reachability comes only from the exact-or-`/reset/` dispatch predicate (`path == "/reset" or path.startswith("/reset/")`, middleware.py:118), deliberately tightened so a hypothetical `/resetXYZ` stays gated (gated requests get a 302→/login for browsers or 401 for API, never 404). Phase 73's `GET /reset/confirm` inherits the exemption via `startswith("/reset/")` with no middleware change (`git diff middleware.py` must stay empty).
- **Track B is one phase (74):** The engine seam extraction (shared fetch+count+filter helper), the structural cursor guarantee (slicing lives only in the cycle fn), the `POST /api/refresh-counts` endpoint mirroring `search_now`, and the app-card "Refresh counts" button are one tightly-coupled deliverable — splitting them would create thin phases. Key invariants: count path updates connection health + counts but never advances the cursor, never stamps `last_run`/`last_success`, and never touches `app.state.search_failures` (SAFETY-03); existing cycle tests must stay green (behavior-preserving refactor).
- **Track C is one small phase (75):** Drain-timeout knob (config field + settings input + scheduler precedence wiring) plus the DOCS-01 deferred-record correction. Smallest track; the docs correction is folded in here rather than spun into a standalone documentation phase (anti-thin-phase). Precedence decision: config value is the default, `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` env overrides when set, `>=1.0` clamp on both — preserves the documented env knob for existing deployments (no silent behavior change).

### v2.9 ship record

Shipped 2026-06-03 (released as **v2.9.0**). Audit passed (19/19 requirements); cross-phase integration 8/8 wired; live NAS walkthrough passed (caught + fixed 2 UX bugs: version badge "vv2.8.1"→"v2.8.1"; Search Now in-flight feedback). 984 tests passing, ruff clean. 4 phases (68-71), 11 plans. Two disjoint tracks each gated by a discovery phase: code (68→69) and presentation (70→71). Archived roadmap: `.planning/milestones/v2.9-ROADMAP.md`.

### v2.8 ship record

Shipped 2026-06-01. Audit passed (16/16 requirements — `.planning/milestones/v2.8-MILESTONE-AUDIT.md`); deep-review APPROVED (`.turingmind/REVIEW.md`); live walkthrough passed (caught + fixed the settings-save form bug, `542d5dd`). Released as **v2.8.0** (pyproject + `__version__` bumped, git tag `v2.8.0`), pushed to origin/main. 961 tests passing, ruff clean.

### v2.8.1 patch (post-archive, 2026-06-01)

Out-of-cycle security patch on top of the archived v2.8 milestone (no full GSD phase — hotfix scope).

- **Fix:** `change_password` now rotates `session_secret`, invalidating all other sessions on password change while re-issuing the acting user's cookie (CWE-613). Supersedes v2.6 threat decision T-58-07/AR-58-02 (was *accept*, now *mitigate*). Deep-reviewed (APPROVED), docs + threat model reconciled. Commits `0866332` (fix) + `0e745ab` (tests). **Note:** Track A's reset-confirm session rotation deliberately mirrors this `change_password` pattern.
- **CI:** all workflow actions bumped to Node 24 majors (PR #20, squash `d538554`) ahead of GitHub's 2026-06-16 Node 20 forced cutover.
- Released as **v2.8.1** (git tag `v2.8.1`, container published); 965 tests passing, ruff clean.

## Performance Metrics

**Overall:**

- Total plans completed: 166 across 15 shipped milestones (through v2.9)
- Milestones shipped: 15 (v1.0, v1.1, v1.2, v2.0, v2.1, v2.2, v2.3, v2.4, v2.5, v2.6, v2.7, v2.8, v2.9)
- Tests passing: 984 (post v2.9.0)
- Phases completed: 71 (through v2.9)

## Accumulated Context

### Decisions

Full decision log in PROJECT.md Key Decisions table. v2.10 design decisions resolved in brainstorming and recorded in `docs/superpowers/specs/2026-06-02-recovery-counts-config-design.md` §7 (recovery trust model: filesystem-token; token lifecycle: in-memory/15-min/single-use/restart-invalidated; abuse defense: rate-limit both endpoints; engine seam: extract helper, no `count_only` flag; count-path state: health yes, `last_run`/failure-counter no; DEBT-06 precedence: config default, env overrides).

### Pending Todos

None.

### Roadmap Evolution

v2.8 roadmap created 2026-05-25 from codebase audit (CONCERNS.md). 16 v1 requirements across 4 phases (64-67). No deferred requirements.

v2.9 roadmap created 2026-06-02 from the launch-hardening design spec. 19 v1 requirements across 4 phases (68-71). Two disjoint tracks, each gated by a discovery phase. Shipped 2026-06-03 as v2.9.0.

v2.10 roadmap created 2026-06-03 from the recovery/counts/config design spec. 14 v1 requirements across 4 phases (72-75, continuing from v2.9's Phase 71 — not reset to 1). Three disjoint tracks: Track A (RCOV-01..06, Phases 72-73), Track B (CNT-01..05, Phase 74), Track C (CFG-03/CFG-04/DOCS-01, Phase 75). 100% coverage, no orphans. Track A split backend/UI given its auth-surface risk and adversarial test weight; Tracks B and C each a single phase; DOCS-01 deferred-record correction folded into Phase 75 (no standalone docs phase). Backlog phases 999.1 (password recovery) and 999.2 (count-only refresh) promoted into this milestone. Flat phase layout (`.planning/phases/<N>-<slug>/`) per the v2.7/v2.8/v2.9 convention.

### Cross-cutting thread

The three tracks share no code (confirmed in spec §1). The only cross-track coupling is the milestone-end NAS walkthrough and the security posture: Track A must add zero new network attack surface (token never in any HTTP response; rate-limited endpoints; SecretStr discipline on `password_hash`/`session_secret` maintained through the redacting sink). Track A's reset-confirm session rotation reuses the v2.8.1 `change_password` rotation pattern.

### Blockers/Concerns

None.

### Deferred Items

Items parked this milestone and carried forward. Note: DEBT-07/08/03/06 leave this table at v2.10 close — DEBT-07/08/03 were already shipped (DOCS-01 corrects the record) and DEBT-06 ships in Phase 75.

| Category | Item | Source Milestone | Status |
|----------|------|------------------|--------|
| record correction | DEBT-07/08/03 (request timeout / page size / search-history cap) | v2.9 (mis-recorded as parked) | already shipped — DOCS-01 corrects record in Phase 75 |
| shipping in v2.10 | DEBT-06: Surface graceful-shutdown drain timeout in settings UI | v2.9 (spec D-5) | in scope — Phase 75 (CFG-03/CFG-04) |
| requirement | UI-01: Login page pixel-exact visual verification | v2.6 | human_needed (behind first-run setup, not launch-visible) |
| requirement | UI-02: Setup page pixel-exact visual verification | v2.6 | human_needed (behind first-run setup, not launch-visible) |
| requirement | UI-03: Settings security pixel-exact visual verification | v2.6 | human_needed (behind first-run setup, not launch-visible) |
| tech-debt | `--color-triggarr-primaryDark` duplicate token (unused in templates) | v2.7 | cosmetic cleanup (unrelated to v2.10 tracks) |
| v2 requirement | PERF-01: Per-endpoint request timeout overrides | v2.8 audit | deferred |
| v2 requirement | PERF-02: Per-endpoint pagination page-size overrides | v2.8 audit | deferred |
| v2 requirement | PERF-03: State JSON streaming/compression | v2.8 audit | deferred |
| v2 requirement | SCALE-01: Lift 5-instance-per-app-type hard limit | v2.8 audit | deferred |
| v2 requirement | SCALE-02: Search history archival / PostgreSQL path | v2.8 audit | deferred |
| v2 requirement | AUDIT-01: Config change audit log | v2.8 audit | deferred |
| v2 requirement | OBS-01: Scheduler job dashboard | v2.8 audit | deferred |
| v2.9-audit follow-up | validate_arr_url dedup; Retry-Connection hx-disabled-elt; bug-report.yml v2.9 dropdown option | v2.9 | deferred |

### Quick Tasks Completed

| Date | Task | Outcome |
|------|------|---------|
| 2026-05-19 | Address Dependabot alerts and PR | Merged PR #19 (idna 3.11→3.15, squash cc61133). Closes alert #12 (CVE-2026-45409, IDNA encoding bypass, medium). |

### Reference Artifacts

- `docs/superpowers/specs/2026-06-02-recovery-counts-config-design.md` -- v2.10 design spec (source of truth for this milestone)
- `docs/superpowers/specs/2026-06-02-launch-hardening-design.md` -- v2.9 design spec
- `.planning/milestones/v2.9-ROADMAP.md` -- archived v2.9 roadmap
- `.planning/milestones/v2.8-ROADMAP.md` -- archived v2.8 roadmap
- `.planning/codebase/CONCERNS.md` -- v2.8 source audit (2026-05-25); file:line pointers
- **Note:** `.planning/research/SUMMARY.md` is STALE (prior milestone) — v2.10 skipped research because the design spec resolved all technical decisions against the live codebase. Do NOT treat that SUMMARY.md as current research for v2.10.

## Session Continuity

Last session: 2026-06-03T21:46:50.969Z
Stopped at: Phase 73 context gathered
Resume file: .planning/phases/73-password-reset-ui/73-CONTEXT.md

## Operator Next Steps

- Plan the first phase with /gsd:plan-phase 72
