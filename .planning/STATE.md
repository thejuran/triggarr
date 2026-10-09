---
gsd_state_version: 1.0
milestone: v2.12
milestone_name: Search Correctness & Trustworthy Feedback
status: executing
stopped_at: Completed 79-01-PLAN.md
last_updated: "2026-10-09T14:53:44.224Z"
last_activity: 2026-10-09 -- Phase 79 execution started
progress:
  total_phases: 18
  completed_phases: 2
  total_plans: 14
  completed_plans: 11
  percent: 11
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-08)

**Core value:** Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.
**Current focus:** Phase 79 — tag-scoped-searches-stay-in-scope

> **Release tags held locally, unpushed:** `v2.11.0` (prior milestone) and `v2.10.0` are tagged locally but NOT pushed to origin — no public GitHub Release cut for either. The `:main` image IS deployed to the NAS and walkthrough-verified. To cut the public releases: `git push origin v2.10.0 v2.11.0` (each triggers the Release workflow → `:latest` + `:vX.Y.Z` images + GitHub Release).

## Current Position

Phase: 79 (tag-scoped-searches-stay-in-scope) — EXECUTING
Plan: 2 of 4
Status: Executing Phase 79
Last activity: 2026-10-09 -- Phase 79 execution started

### v2.12 milestone shape

Five phases derived 1:1 from the approved design spec `docs/superpowers/specs/2026-10-08-search-correctness-design.md` §4, each phase matching one of the spec's five numbered subsections — a natural fit for Standard granularity (4-6 phases). Phase numbering continues from v2.11's Phase 76 (starts at 77, not reset to 1). 77 and 81 are independent fixes (77 sequenced first for risk reduction — isolated, small, highest-stakes; 81 last because it carries the only DB migration and config addition and is independent of 79/80 per spec §5); 78 defines the outcome-grading model that 79 and 80 both depend on. Flat phase layout (`.planning/phases/<N>-<slug>/`) per the v2.7+ convention.

| Phase | Goal | Requirements | Depends on |
|-------|------|--------------|------------|
| 77 — Secret & Reset-Token Log Hygiene | Redact the reset token from the in-app log viewer buffer permanently; route every *arr HTTP-error log line (incl. Sonarr `detect_api_version`) through the existing sanitizer | LOGSEC-01..03 | — (independent; sequenced first for risk reduction) |
| 78 — Honest Cycle Outcomes | Grade each instance's last cycle Success/Partial/Failed/Nothing-needed per §3.1; split "last successful search" from "last checked"; drive the SAFETY-03 counter off the grade; dashboard card shows grade+counts+relative time | OUTCOME-01..06 | — (independent of 77; defines the model 79/80 build on) |
| 79 — Tag-Scoped Searches Stay in Scope | An unresolved tag skips its queue (zero searches) instead of falling back to searching everything; persistent card warning; skipped queue counts as unevaluated for grading | TAGSCOPE-01..04 | Phase 78 (grading model) |
| 80 — Cycle Robustness & Sonarr Season Dedup | A malformed *arr record is skipped, not fatal; history-insert failures never abort a batch or flip an accepted command to failed; each Sonarr season gets ≤1 engine dispatch per cycle across missing+upgrade queues | ROBUST-01..04, DEDUP-01..02 | Phase 78 (grading model) |
| 81 — Correct Sonarr Grab Attribution | Grabs credit the matching series+season exactly once ever, keyed by (app, stable instance ID, grab ID); atomic ownership surviving restarts/pruning; pre-cutover rows frozen as "Legacy — tracking discontinued"; stats cutover note | ATTR-01..06 | — (independent of 79/80 per spec §5; carries the only DB migration + config addition) |

### Key v2.12 Phasing Rationale

- **One phase per spec subsection, not split further:** The approved design spec §4 already groups the 25 requirements into exactly five behaviorally-coherent clusters (log hygiene; grading; tag scope; robustness+dedup; attribution), each independently testable and each matching a real delivery boundary.
- **OUTCOME-06 stays in 78, not 80:** OUTCOME-06 (an accepted command whose history write fails still counts as accepted and updates "last successful search") is a grading rule — it defines what "accepted" means for §3.1 — so it rides with the rest of the grading model in Phase 78. Phase 80's ROBUST-02 covers the mechanical guarantee (the insert-failure code path doesn't abort the batch); the two requirements describe the same scenario from two different layers (policy vs. mechanism) and are deliberately kept in separate phases.
- **80 bundles robustness + dedup because they share code:** Both touch the same Sonarr cycle loop (malformed-record guards and season-claim bookkeeping sit in the same call sites), and 80's malformed-record counts feed into 78's grading model — splitting them would fracture one code path across two phases.
- **81 is last and fully independent:** Per spec §5, it carries the only DB migration (ownership table + cutover marker) and the only config-schema addition (stable per-instance ID), and doesn't depend on 79 or 80's behavior.
- **Backlog promotions:** 999.3 (reset-token log-viewer exposure) and 999.6 (secret-redaction gaps across log paths) promoted into Phase 77; 999.5 (cycle-wedge robustness) promoted into Phase 80. 999.4, 999.7-999.13, and POST-retry semantics stay deferred (spec §2).

### v2.11 milestone shape

A single-phase milestone. v2.11 is a tightly-coupled internal refactor of the search dispatch path — NOT independent tracks. The state-model change (QUEUE-01/02/03), the never-searched-first dispatch (QUEUE-04..07), and the searched-log lifecycle (QUEUE-08..11) are realized by the SAME pure function (`prioritize_batch`) wired into the SAME 6 cycle call sites (Radarr/Sonarr/Lidarr × missing/cutoff). `prioritize_batch` reads the searched-log fields, partitions unsearched-first, marks on attempt, returns a pass-complete signal, and the call sites commit the log + `*_pass` in the single atomic `save_state()` at cycle end. Splitting state vs. dispatch vs. lifecycle would fracture one function across phases and produce thin, task-shaped phases — so the honest decomposition is one coherent, independently-verifiable phase (Phase 76). Phase numbering continues from v2.10's Phase 75 (starts at 76, not reset to 1). Source of truth: `docs/superpowers/specs/2026-06-04-search-queue-priority-design.md` (10 locked decisions §3, YAGNI fence §9, affected files §10). Flat phase layout (`.planning/phases/76-<slug>/`) per the v2.7–v2.10 convention.

| Phase | Goal | Requirements | Depends on |
|-------|------|--------------|------------|
| 76 — Never-Searched-First Search Queue | Replace the integer cursor with an ordered per-instance searched-log on `AppState` + a pure `prioritize_batch()` (never-searched-first, top-up oldest-first, mark-on-attempt, prune-to-eligible, pass-reset, commit-at-cycle-end) swapped into all 6 cycle call sites; remove `missing_cursor`/`cutoff_cursor` and `slice_batch`. Behavior-identical on cold start. | QUEUE-01..11 | — (builds on shipped v2.10 state/engine) |

### Key v2.11 Phasing Rationale

- **One phase, not three:** The design spec §1/§6 and the milestone instructions both confirm the three requirement clusters share code. `prioritize_batch` is a single pure function that simultaneously implements dispatch (QUEUE-04/05/06), mark-on-attempt (QUEUE-08), and prune-to-eligible (QUEUE-10); the call-site wiring (QUEUE-07) realizes pass-reset (QUEUE-09) and commit-at-cycle-end (QUEUE-11); and the state-model change (QUEUE-01/02/03) is the substrate all of that reads/writes. None of these is independently verifiable without the others (you cannot drive real cycles through `prioritize_batch` without the `AppState` fields, nor verify the lifecycle without the call sites). A single phase keeps the function whole and the phase independently testable.
- **Behavior-preserving constraints encoded as success criteria:** cold-start dispatch (empty searched-log) must produce the same batch as today's first cycle; existing cycle tests asserting search counts / history rows must stay green; count-only refresh (`refresh_*_counts`) must remain queue-independent (never reads/writes the searched-log). These are pinned in Phase 76's criteria 3 and 5.
- **Removals are part of the same phase:** dropping the cursor fields and deleting `slice_batch` (with its tests) happen as the 6 callers migrate to `prioritize_batch` — no dead code, no tombstone, no migration step (D-9/D-10). Cursor-value test assertions migrate to searched-log assertions in the same phase.

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

- Total plans completed: 179 across 15 shipped milestones (through v2.9)
- Milestones shipped: 15 (v1.0, v1.1, v1.2, v2.0, v2.1, v2.2, v2.3, v2.4, v2.5, v2.6, v2.7, v2.8, v2.9)
- Tests passing: 1097 (post Phase 77 Plan 01)
- Phases completed: 71 (through v2.9)

| Phase | Duration | Tasks | Files |
|-------|----------|-------|-------|
| Phase 77 P01 | 25min | 2 tasks | 2 files |
| Phase 77 P02 | 12min | 2 tasks | 4 files |
| Phase 77 P03 | 8min | 2 tasks | 2 files |
| Phase 77 P04 | 10min | 2 tasks | 2 files |
| Phase 77 P05 | 11min | 2 tasks | 11 files |
| Phase 78 P01 | 10min | 3 tasks | 4 files |
| Phase 78 P02 | 38min | 4 tasks | 4 files |
| Phase 78 P04 | 13min | 3 tasks | 7 files |
| Phase 78 P03 | 18min | 2 tasks | 2 files |
| Phase 78 P05 | 25min | 3 tasks | 5 files |
| Phase 79 P01 | 15min | 3 tasks | 2 files |

## Accumulated Context

### Decisions

Full decision log in PROJECT.md Key Decisions table. v2.12 phasing decisions are recorded above in "v2.12 milestone shape" / "Key v2.12 Phasing Rationale", derived from the approved design spec `docs/superpowers/specs/2026-10-08-search-correctness-design.md` (locked grading definitions §3, per-phase behavior + acceptance §4, ordering rationale §5).

- [Phase 77]: 77-01: create_buffer_sink reads a bound extra['viewer_message'] before falling back to record['message'], structurally excluding a value from log_buffer (D-03) rather than scrubbing it after insertion — Enables Plan 04 to bind the exact D-01 viewer wording at the reset-token mint call site with no further sink-side changes
- [Phase 77]: 77-02: _sanitize_exc relocated from search/engine.py to clients/base.py (single definition, no upward import), closing the circular-import blocker so SonarrClient.detect_api_version can route its warning through it -- Sonarr detect_api_version failures now log a sanitized HTTP-status/timeout summary instead of the raw exception, so a legacy install's apikey-bearing URL never reaches a log sink
- [Phase 77]: 77-03: load_state's corrupt-file warning now binds the caught exception and logs type(exc).__name__ plus str(exc), naming the failure reason without ever touching exc.doc — Closes backlog 999.6(e)/D-09(R7); JSONDecodeError/OSError text carries only parser-position or errno info, never file contents
- [Phase 77]: 77-04: logger.bind(viewer_message=RESET_MINT_VIEWER_MESSAGE) on the reset-token mint warning lands LOGSEC-01/LOGSEC-02 end-to-end -- the token is absent from log_buffer/partials/log-viewer across live, consumed, expired, and replaced states, while docker logs and reset-token.txt keep it unchanged — Closes backlog 999.3; the viewer_sinks test fixture needed a catch-all logger.remove() in teardown because a successful /reset/confirm's own setup_logging() call replaces every loguru handler mid-test, orphaning the fixture's tracked ids and leaking duplicate buffer sinks into the next test
- [Phase 77]: 77-05: ArrClient.__init__ (and the three *arr subclasses) now require api_key: SecretStr with a value-free TypeError guard; .get_secret_value() unwraps exactly once, at the X-Api-Key header line; startup.py/scheduler.py/routes.py pass the SecretStr straight through; auth_api_key_set now uses bool(settings.auth.api_key) — Closes backlog 999.6(c)/(d); strict SecretStr contract chosen over str|SecretStr per RESEARCH.md's resolved Open Question 2, migrating all 64 test call sites in the same wave
- [Phase 78]: 78-01: grade_cycle's amended-R-01 backstop (accepted=0, failed=0, eligible_active>0) grades Failed, not Partial — the engine did no work while work existed, which should trip the SAFETY-03 alert; supersedes RESEARCH Open Question 1's Partial recommendation
- [Phase 78]: 78-01: AppState.last_successful_search is never derived from the legacy last_success field — last_success stays frozen verbatim for the Last success (legacy) label and the documented NAS downgrade fallback (R-05)
- [Phase 78]: 78-02: the cutoff filter chain, moved ahead of both dispatches so rebalance_batch_sizes sees both eligible counts, is guarded against malformed data (AttributeError/KeyError/TypeError) and degrades cutoff to empty for that cycle on fault — Preserves the pre-existing per-app guarantee that a cutoff-side data fault can never block the missing queue's dispatch, which the unguarded reordering broke
- [Phase 78]: 78-02: insert_search_entry rolls back on any failure after its INSERT (catching bare Exception, not just aiosqlite.Error, since a driver-thread OSError leaves the same open transaction) — Prevents a partial write from staying pending on the shared connection -- a later successful insert can no longer commit a phantom row alongside it, and the pending-cap check only ever counts committed rows (R-08)
- [Phase 78]: 78-04: Last successful search / Last success (legacy) row stays duplicated verbatim in both card bodies (connected and unreachable) rather than a second shared include, matching the plan's instruction and the file's existing per-body duplication convention for that row — cycle_grade.html's color dispatch collapses nothing_needed and any unexpected grade into one else branch since cycle_view() already restricts grade to exactly the four GRADE_LABELS keys
- [Phase 78]: 78-03: run_sonarr_cycle and run_lidarr_cycle route through the same CycleTally/_fetch_wanted_queues/_search_and_record/_finalize_cycle/rebalance_batch_sizes helpers as Radarr, with a matching malformed-data guard on each app's cutoff filter chain so the pre-existing cross-queue fault-isolation guarantee survives the R-01-amended filter-chain reordering — Mirrors run_radarr_cycle exactly per the plan; the guard was required (not optional) because per-app regression tests (test_run_sonarr_cycle_cutoff_fault_does_not_block_missing_search, test_run_lidarr_cycle_cutoff_fault_does_not_block_missing_search) already pinned that a cutoff-side data fault must never block the missing queue's dispatch, and moving the cutoff filter chain earlier would otherwise break that guarantee
- [Phase 78]: 78-05: _evaluate_cycle_outcome now derives the SAFETY-03 counter from state[app][inst]["last_cycle"]["grade"] instead of connected -- a reachable *arr that rejects every command now grades Failed and increments the counter — Previously connected=True reset the counter even when every search command was rejected, suppressing the alert; threshold/escalation logic in _record_cycle_failure is untouched
- [Phase 78]: 78-05: tests/test_outcome_upgrade.py drives the real engine end-to-end (load_state -> run_*_cycle -> actual app-card route) rather than fabricating last_cycle dicts — Proves the engine's _finalize_cycle output actually renders correctly through the real route, which the Plan 04 fabricated-dict template tests cannot prove; all 6 tests passed on first run against Plans 01-04 as already built
- [Phase 79]: 79-01: _resolve_tag_scope fires 'unresolved' on tag_id is None regardless of tag_fetch_ok, fixing a second pre-existing bug where a failed tag fetch produced no warning at all -- tag_fetch_ok now only selects which fixed reason string to use
- [Phase 79]: 79-01: the unresolved-scope marker (ist['unresolved_tag_scopes']) is recorded for an unresolved queue regardless of whether it is active, per owner-resolved OQ1 -- only the warning badge and CycleTally.mark_unevaluated are gated on the queue being active (D-04)

### Pending Todos

None.

### Roadmap Evolution

v2.8 roadmap created 2026-05-25 from codebase audit (CONCERNS.md). 16 v1 requirements across 4 phases (64-67). No deferred requirements.

v2.9 roadmap created 2026-06-02 from the launch-hardening design spec. 19 v1 requirements across 4 phases (68-71). Two disjoint tracks, each gated by a discovery phase. Shipped 2026-06-03 as v2.9.0.

v2.10 roadmap created 2026-06-03 from the recovery/counts/config design spec. 14 v1 requirements across 4 phases (72-75, continuing from v2.9's Phase 71 — not reset to 1). Three disjoint tracks: Track A (RCOV-01..06, Phases 72-73), Track B (CNT-01..05, Phase 74), Track C (CFG-03/CFG-04/DOCS-01, Phase 75). 100% coverage, no orphans. Track A split backend/UI given its auth-surface risk and adversarial test weight; Tracks B and C each a single phase; DOCS-01 deferred-record correction folded into Phase 75 (no standalone docs phase). Backlog phases 999.1 (password recovery) and 999.2 (count-only refresh) promoted into this milestone. Flat phase layout (`.planning/phases/<N>-<slug>/`) per the v2.7/v2.8/v2.9 convention.

v2.11 roadmap created 2026-06-04 from the search-queue-priority design spec. 11 v1 requirements (QUEUE-01..11) mapped to a single phase (76, continuing from v2.10's Phase 75 — not reset to 1). 100% coverage, no orphans, no double-mapping. One coherent phase because the requirements are not independent tracks: a single pure `prioritize_batch()` + the same 6 cycle call sites realize the state model, the dispatch, and the lifecycle together. Flat phase layout (`.planning/phases/76-<slug>/`).

v2.12 roadmap created 2026-10-08 from the approved search-correctness design spec. 25 v1 requirements across 5 phases (77-81, continuing from v2.11's Phase 76 — not reset to 1). 100% coverage, no orphans, no double-mapping. Phases derived 1:1 from spec §4's five numbered subsections; 79 and 80 depend on 78 (grading model); 77 and 81 are independent of each other and of 79/80. Backlog phases 999.3 and 999.6 (log-hygiene findings) promoted into Phase 77; 999.5 (cycle-wedge robustness) promoted into Phase 80. Flat phase layout (`.planning/phases/<N>-<slug>/`) per the v2.7+ convention.

### Cross-cutting thread

77 and 81 are isolated fixes; 78 is the shared substrate for 79 and 80 (the grading model both consume). Every phase carries the same constraints from the project (spec §7): SecretStr discipline (`.get_secret_value()` only at HTTP client init), loguru-only logging through the redacting sink, atomic write-then-rename for config/state, and the established `httpx.HTTPError` + `pydantic.ValidationError` error-handling pattern, widened only where the spec says so (Phase 80's malformed-record guards). Phase 81's stable per-instance ID (backfilled via the atomic config write) is the only new config-schema addition this milestone, and its ownership-table migration is the only new DB migration.

### Blockers/Concerns

None.

### Deferred Items

Items parked this milestone and carried forward. Note: DEBT-07/08/03/06 leave this table at v2.10 close — DEBT-07/08/03 were already shipped (DOCS-01 corrects the record) and DEBT-06 ships in Phase 75.

| Category | Item | Source Milestone | Status |
|----------|------|------------------|--------|
| backlog | 999.4: Run bcrypt off the event loop | v2.9 deep-review | deferred — out of v2.12 scope per spec §2 |
| backlog | 999.7-999.13: client-dispatch registry, atomic-write helper consolidation, remove_instance rollback guard, auth/CSRF/cookie hardening, SSRF-validator startup brick, changelog XSS surface, lifecycle/blocking-I/O correctness | v2.9 deep-review | deferred — out of v2.12 scope per spec §2 |
| follow-up | HTTP client's automatic single POST retry can duplicate an accepted command after a timeout | v2.12 design spec §2 | deferred to next hardening milestone (explicitly out of scope) |
| shipped (record corrected) | DEBT-07/08/03 (request timeout / page size / search-history cap) | v2.9 (mis-recorded as parked) | shipped — config fields config.py:128-130 + settings inputs; DOCS-01 corrected the record in Phase 75 |
| shipped in v2.10 | DEBT-06: Surface graceful-shutdown drain timeout in settings UI | v2.9 (spec D-5) | shipped — Phase 75 (CFG-03/CFG-04); general.shutdown_drain_timeout config field + settings input + env-override precedence |
| requirement | UI-01: Login page pixel-exact visual verification | v2.6 | human_needed (behind first-run setup, not launch-visible) |
| requirement | UI-02: Setup page pixel-exact visual verification | v2.6 | human_needed (behind first-run setup, not launch-visible) |
| requirement | UI-03: Settings security pixel-exact visual verification | v2.6 | human_needed (behind first-run setup, not launch-visible) |
| tech-debt | `--color-triggarr-primaryDark` duplicate token (unused in templates) | v2.7 | cosmetic cleanup (unrelated to v2.12 phases) |
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

- `docs/superpowers/specs/2026-10-08-search-correctness-design.md` -- v2.12 design spec (source of truth for this milestone)
- `docs/superpowers/specs/2026-06-02-recovery-counts-config-design.md` -- v2.10 design spec
- `docs/superpowers/specs/2026-06-02-launch-hardening-design.md` -- v2.9 design spec
- `.planning/milestones/v2.9-ROADMAP.md` -- archived v2.9 roadmap
- `.planning/milestones/v2.8-ROADMAP.md` -- archived v2.8 roadmap
- `.planning/codebase/CONCERNS.md` -- v2.8 source audit (2026-05-25); file:line pointers
- **Note:** `.planning/research/SUMMARY.md` is STALE (prior milestone) — v2.12 skipped research because the approved design spec resolved all technical decisions against the live codebase. Do NOT treat that SUMMARY.md as current research for v2.12.

## Session Continuity

Last session: 2026-10-09T14:53:44.219Z
Stopped at: Completed 79-01-PLAN.md
Resume file: None

## Operator Next Steps

- Plan Phase 77 with `/bm:plan-phase 77`
