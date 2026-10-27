---
gsd_state_version: 1.0
milestone: v2.13
milestone_name: CI & Review Workflow
status: executing
stopped_at: "Phase 85 planned; next: /bm:execute-phase 85"
last_updated: "2026-10-27T12:39:15.139Z"
last_activity: 2026-10-27 -- Phase 85 execution started
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 45
  completed_plans: 26
  percent: 43
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-21)

**Core value:** Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.
**Current focus:** Phase 85 — Follow-on CI improvements & acceptance usability

> **Releases:** v2.10.0, v2.11.0 and v2.11.1 are pushed and published as GitHub Releases (2026-09-20). v2.12 work so far: Phases 77–79 merged via PR #26 (`c914cbc`) and deployed to production as `:main` on 2026-10-18; connection-pill polling fix merged via PR #27 (`d41b484`); Phase 80 merged via PR #28 (`dee25df`) and deployed to production on 2026-10-18. v2.12 shipped 2026-10-21 as v2.12.0 (tag on `dbb38fa`).

**Published-history note (2026-10-21):** before the first push, this unpushed branch's history was rewritten to remove private infrastructure and credential details from planning text and commit messages. Code, tests and config are byte-identical in every commit (checked commit by commit). Planning docs still cite pre-rewrite hashes; map them as follows: `b35470b` (sandbox build, revision label on `triggarr:phase81-b35470b66f`) → `69f5733`; `a2b8c1c` (full deep review) → `1915a7d`; `d14b71e` → `06519aa`; `9a1d423` (frozen deep-review commit) → `3e19e48`; `363060e` → `c2fb07a`; `b498475` → `91b7992`. The review and live evidence apply unchanged, because the code trees are identical.

## Current Position

Phase: 85 (Follow-on CI improvements & acceptance usability) — EXECUTING
Plan: 1 of 19
Status: Executing Phase 85
Last activity: 2026-10-27 -- Phase 85 execution started

### v2.13 milestone shape

Five phases derived from this milestone's 28 requirements (CISHIP, CIMAINT, ACCEPT, REVIEW, RISK, PLANCHK, PILOT), continuing phase numbering from v2.12's Phase 81 (starts at 82, not reset to 1). Owner-mandated sequencing (2026-10-21) drove the order, not a template: start with the shipped-artifact CI checks; put the gated BM update (REVIEW-01) early, folded into the start of the review-pairing phase rather than a standalone single-requirement phase; keep the Codex plan-checker investigation (PLANCHK) in its own phase so it cannot block or bundle into the review-pairing or CI phases; group the follow-on CI hardening with acceptance-register usability since both extend the Phase 82 baseline and one (CIMAINT-06's coverage artifact) directly feeds Phase 83's risk-based vibe-check test-sufficiency lane; and put the pilot last because it needs the paired workflow in place and draws its PRs from this milestone's own authorized work. Flat phase layout (`.planning/phases/<N>-<slug>/`) per the v2.7+ convention.

| Phase | Goal | Requirements | Depends on |
|-------|------|--------------|------------|
| 82 — CI Tests What We Ship | Shipped-image startup, browser regression, and release-version checks join the required gate, each proven by a deliberately broken case that fails | CISHIP-01..04 | — (first phase) |
| 83 — Paired BM + Codex Review & Risk-Based Depth | A recorded, owner-approved BM baseline and update gates the start; then every BM review path gets an independent exact-commit Codex pass, and BM explicitly recommends depth and vibe-check at high-risk checkpoints; defines the content-based review classification for docs/planning changes | REVIEW-01..08, RISK-01..02 | Phase 82 (sequenced immediately after per owner instruction; no technical coupling) |
| 84 — Codex Plan-Checker Investigation | Record whether a narrowly scoped `agent.spawn` hook can route only the plan checker through model-gateway, and how it compares against manual Codex review on the original Phase 81 plans | PLANCHK-01..03 | — (independent; separately gated; requires the preserved Phase 81 phase directories) |
| 85 — Follow-on CI Improvements & Acceptance Usability | Lockfile-matched Docker deps, grouped dependency updates, OS-image audit, workflow lint, exact-commit coverage evidence, least-privilege publish permissions, and an acceptance register usable under concurrent PRs; GitHub checks that honor the review classification without weakening code/control protection | CIMAINT-01..07, ACCEPT-01..03 | Phase 82 (extends the CI baseline); Phase 83 for ACCEPT-03 (the classification policy); CIMAINT-06's coverage feeds the vibe-check test-sufficiency lane |
| 86 — Pilot & Reference Record | 3-5 representative PRs run under the paired workflow; the owner records the routine-vibe-check retirement decision and reusable adoption guidance is written | PILOT-01..04 | Phases 82, 83 and 85 (needs the paired workflow in place; pilot evidence collected from PRs after Phase 83 while later authorized work proceeds). Not Phase 84 |

### Key v2.13 Phasing Rationale

- **CISHIP is first, unconditionally:** the owner's instruction was explicit — start implementation with the shipped-image/browser/release-version checks before anything else, so Phase 82 carries no dependency.
- **REVIEW-01 is a gate, not a standalone phase:** a single-requirement phase would be the kind of thin, task-shaped phase the granularity rule warns against. Folding it into the start of Phase 83 keeps it early (immediately after CISHIP) and keeps its owner-approval gate as this phase's first, explicit success criterion — nothing in REVIEW-02..06/RISK-01..02 can start until REVIEW-01's gate passes.
- **PLANCHK is isolated on purpose:** the owner's instruction requires it to be a separately gated investigation that cannot block or bundle into the review-pairing (83) or CI (82, 85) phases. It has no dependency edge from or to those phases; it only needs the Phase 81 phase directories, which are explicitly preserved (not cleared) for its blind comparison.
- **85 groups CIMAINT + ACCEPT because they're both "extend the baseline" work:** neither follow-on CI hardening nor acceptance-register usability is independently a full milestone phase on its own (would be thin), and CIMAINT-06 (coverage artifact) is explicit cross-phase plumbing for Phase 83's RISK-based vibe-check test-sufficiency lane — grouping keeps that dependency visible instead of splitting it across two phases.
- **Pilot is last, but starts collecting after Phase 83:** PILOT-01 draws its PRs from "this milestone's own PRs" plus owner-authorized maintenance/backlog work, and needs the paired BM+Codex workflow (Phase 83) actually operating, not just specified. Pilot evidence is collected from PRs after Phase 83 (e.g. Phase 85's PRs) while later authorized work proceeds; the phase closes after 82, 83 and 85. It does not depend on Phase 84, which is separately gated.
- **Phase 84 closeout:** the phase record separates investigated results (with evidence) from deferred or not-run work (with the reason).
- **Standing rules carried into every phase:** per REQUIREMENTS.md, the current review process (Greptile, routine vibe-check, exact-commit owner acceptance) stays in force for code and control changes until the owner explicitly retires a part of it in Phase 86 (PILOT-03); no phase waives or substitutes any part of it early. Ordinary docs/planning-only changes follow the content-based classification policy once Phase 83 defines it (REVIEW-07/08). Until Phase 85's GitHub mechanism (ACCEPT-03) is verified, existing GitHub protections are preserved and any review still running automatically on docs-only PRs (currently Greptile) is disclosed. Exact-commit owner acceptance applies to every PR.

### v2.12 milestone shape

Five phases derived 1:1 from the approved design spec `docs/superpowers/specs/2026-10-08-search-correctness-design.md` §4, each phase matching one of the spec's five numbered subsections — a natural fit for Standard granularity (4-6 phases). Phase numbering continues from v2.11's Phase 76 (starts at 77, not reset to 1). 77 and 81 are independent fixes (77 sequenced first for risk reduction — isolated, small, highest-stakes; 81 last because it carries the only DB migration and config addition and is independent of 79/80 per spec §5); 78 defines the outcome-grading model that 79 and 80 both depend on. Flat phase layout (`.planning/phases/<N>-<slug>/`) per the v2.7+ convention.

| Phase | Goal | Requirements | Depends on |
|-------|------|--------------|------------|
| 77 — Secret & Reset-Token Log Hygiene | Redact the reset token from the in-app log viewer buffer permanently; route every *arr HTTP-error log line (incl. Sonarr `detect_api_version`) through the existing sanitizer | LOGSEC-01..03 | — (independent; sequenced first for risk reduction) |
| 78 — Honest Cycle Outcomes | Grade each instance's last cycle Success/Partial/Failed/Nothing-needed per §3.1; split "last successful search" from "last checked"; drive the SAFETY-03 counter off the grade; dashboard card shows grade+counts+relative time | OUTCOME-01..06 | — (independent of 77; defines the model 79/80 build on) |
| 79 — Tag-Scoped Searches Stay in Scope | An unresolved tag skips its queue (zero searches) instead of falling back to searching everything; persistent card warning; skipped queue counts as unevaluated for grading | TAGSCOPE-01..04 | Phase 78 (grading model) |
| 80 — Cycle Robustness & Sonarr Season Dedup | A malformed *arr record is skipped, not fatal; history-insert failures never abort a batch or flip an accepted command to failed; each Sonarr season gets ≤1 engine dispatch per cycle across missing+upgrade queues | ROBUST-01..04, DEDUP-01..02 | Phase 78 (grading model) |
| 81 — Correct Sonarr Grab Attribution | Grabs credit the matching series+season exactly once ever, keyed by (app, stable instance ID, grab ID); atomic ownership surviving restarts/pruning; pre-cutover rows frozen as "Legacy — tracking discontinued"; stats cutover note | ATTR-01..06, SONARRV5-01..03 | — (independent of 79/80 per spec §5; carries the only DB migration + config addition) |

### Key v2.12 Phasing Rationale

- **One phase per spec subsection, not split further:** The approved design spec §4 already groups the 25 requirements into exactly five behaviorally-coherent clusters (log hygiene; grading; tag scope; robustness+dedup; attribution), each independently testable and each matching a real delivery boundary.
- **OUTCOME-06 stays in 78, not 80:** OUTCOME-06 (an accepted command whose history write fails still counts as accepted and updates "last successful search") is a grading rule — it defines what "accepted" means for §3.1 — so it rides with the rest of the grading model in Phase 78. Phase 80's ROBUST-02 covers the mechanical guarantee (the insert-failure code path doesn't abort the batch); the two requirements describe the same scenario from two different layers (policy vs. mechanism) and are deliberately kept in separate phases.
- **80 bundles robustness + dedup because they share code:** Both touch the same Sonarr cycle loop (malformed-record guards and season-claim bookkeeping sit in the same call sites), and 80's malformed-record counts feed into 78's grading model — splitting them would fracture one code path across two phases.
- **81 is last and fully independent:** Per spec §5, it carries the only DB migration (ownership table + cutover marker) and the only config-schema addition (stable per-instance ID), and doesn't depend on 79 or 80's behavior.
- **Backlog promotions:** 999.3 (reset-token log-viewer exposure) and 999.6 (secret-redaction gaps across log paths) promoted into Phase 77; 999.5 (cycle-wedge robustness) promoted into Phase 80. The 2026-10-18 future milestones below organize retained fixes; maintenance rules and closed decisions live in .planning/backlog/ (spec §2).

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

- Total plans completed: 183 across 15 shipped milestones (through v2.9)
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
| Phase 79 P02 | 5min | 3 tasks | 6 files |
| Phase 79 P03 | 26min | 3 tasks | 3 files |
| Phase 79 P04 | 13min | 2 tasks | 2 files |

## Accumulated Context

### Decisions

- 2026-10-21 (v2.13 roadmap amendment, owner-authorized for planning only): added the docs/planning review-classification policy. REVIEW-07/08 (Phase 83) define content-based classification (ordinary docs/planning gets a focused consistency review; agent instructions, workflows, hooks, permissions, acceptance/release policy and operational procedures need a risk assessment and technical review; mixed PRs follow their consequential changes; classification recorded against the exact head) and replace blanket "every PR" wording, keeping Codex paired with every BM code-review run. ACCEPT-03 (Phase 85) designs and verifies GitHub-check handling across ordinary-docs, sensitive-docs, mixed and misclassification cases without ad hoc check disabling. Existing protections stay until then; exact-commit owner acceptance stays for every PR. No live settings changed. Now 31 requirements.
- 2026-10-21 (v2.13 roadmap): 28 requirements mapped to 5 phases (82-86) with 100% coverage, no orphans. REVIEW-01 (BM update) folded into the start of Phase 83 rather than a standalone phase, per the granularity rule against single-requirement phases, while keeping its owner-approval gate as that phase's first explicit success criterion. PLANCHK (84) kept fully independent per owner instruction. CIMAINT + ACCEPT grouped into Phase 85 since both extend the Phase 82 CI baseline and CIMAINT-06 feeds Phase 83's risk-based review.
- 2026-10-21 (v2.12 closeout): the owner confirmed the review blueprint and the CI reference-baseline plan as written; they form the CI & Review Workflow milestone. No BM settings, CLAUDE.md, CI or acceptance changes until that milestone implements them.

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
- [Phase 79]: 79-02: a tag_warnings entry with no reason key (pre-upgrade state.json) renders the 'not found' wording via an explicit {% else %} branch, never Jinja's implicit Undefined
- [Phase 79]: 79-02: a legacy scoped count with no scoped_count_tags provenance stamp is never trusted even if a current unresolved_tag_scopes marker exists -- only a count stamped with the exact tag name that is now unresolved is kept, everything else shows the em dash
- [Phase 79]: 79-02: the unresolved-tag skip gate for progress denominators applies regardless of whether the queue is currently flagged in tag_warnings (badge/grading stay gated on active per D-04), so an inactive unresolved queue's count also shows unknown (OQ1)
- [Phase 79]: 79-03: _clear_faulted_scoped_counts is a pure per-queue gate, never reading or writing ist['scoped_count_tags']/ist['unresolved_tag_scopes'] -- the card already treats a None count as unknown regardless of the stamp — Keeps the fault-clearing logic simple and additive to Plan 02's card-side trust decision rather than a parallel reimplementation
- [Phase 79]: 79-03: all six engine entry points (3 cycles + 3 refreshes) now share one tag-resolution path via _resolve_tag_scope and one provenance-stamping path via _stamp_scoped_counts — No inline tag-resolution code remains anywhere in engine.py; refresh functions pass tally=None so refresh never touches the grade
- [Phase 79]: 79-04: _finish_both_inactive_unreachable and _cap_and_log fold the R-07 both-inactive early return and the hard-max cap-and-log block (each previously copied three times across run_radarr_cycle/run_sonarr_cycle/run_lidarr_cycle) into shared helpers mirroring _rebalance_and_log's style -- behavior-preserving, full suite green at 1369 tests

### Pending Todos

- Resolved (D-14): not needed -- SONARRV5-02 closed before release, so v2.12.0 shipped with no scope exception.
- Deferred follow-up: bound/prune timestamped pre-migration DB backups (Plan 81-03 keeps the first backup and timestamps later ones with no cleanup, so a startup crash-loop on a failing upgrade accumulates copies). Not Phase 81 scope.

### Roadmap Evolution

v2.8 roadmap created 2026-05-25 from codebase audit (CONCERNS.md). 16 v1 requirements across 4 phases (64-67). No deferred requirements.

v2.9 roadmap created 2026-06-02 from the launch-hardening design spec. 19 v1 requirements across 4 phases (68-71). Two disjoint tracks, each gated by a discovery phase. Shipped 2026-06-03 as v2.9.0.

v2.10 roadmap created 2026-06-03 from the recovery/counts/config design spec. 14 v1 requirements across 4 phases (72-75, continuing from v2.9's Phase 71 — not reset to 1). Three disjoint tracks: Track A (RCOV-01..06, Phases 72-73), Track B (CNT-01..05, Phase 74), Track C (CFG-03/CFG-04/DOCS-01, Phase 75). 100% coverage, no orphans. Track A split backend/UI given its auth-surface risk and adversarial test weight; Tracks B and C each a single phase; DOCS-01 deferred-record correction folded into Phase 75 (no standalone docs phase). Backlog phases 999.1 (password recovery) and 999.2 (count-only refresh) promoted into this milestone. Flat phase layout (`.planning/phases/<N>-<slug>/`) per the v2.7/v2.8/v2.9 convention.

v2.11 roadmap created 2026-06-04 from the search-queue-priority design spec. 11 v1 requirements (QUEUE-01..11) mapped to a single phase (76, continuing from v2.10's Phase 75 — not reset to 1). 100% coverage, no orphans, no double-mapping. One coherent phase because the requirements are not independent tracks: a single pure `prioritize_batch()` + the same 6 cycle call sites realize the state model, the dispatch, and the lifecycle together. Flat phase layout (`.planning/phases/76-<slug>/`).

v2.12 roadmap created 2026-10-08 from the approved search-correctness design spec. 25 v1 requirements across 5 phases (77-81, continuing from v2.11's Phase 76 — not reset to 1). 100% coverage, no orphans, no double-mapping. Phases derived 1:1 from spec §4's five numbered subsections; 79 and 80 depend on 78 (grading model); 77 and 81 are independent of each other and of 79/80. Backlog phases 999.3 and 999.6 (log-hygiene findings) promoted into Phase 77; 999.5 (cycle-wedge robustness) promoted into Phase 80. Flat phase layout (`.planning/phases/<N>-<slug>/`) per the v2.7+ convention.

2026-10-12 plan amendment: added SONARRV5-01..03 as one bounded Phase 81 compatibility task; v2.12 now has 28 requirements across the same five phases. Correct v5 version reporting, verify existing v3/API-key flows against isolated v4/v5 instances, and extend attribution fixtures for alternate orders and packs. Final compatibility verification follows Phase 80; no live v5 support claim until tested. Current execution position and completed-phase status are unchanged.

v2.13 roadmap created 2026-10-21 from the owner-confirmed review blueprint (`docs/bm-greptile-codex-blueprint.md`) and CI reference-baseline plan (`docs/ci-reference-baseline-plan.md`). 28 requirements across 5 phases (82-86, continuing from v2.12's Phase 81 — not reset to 1). 100% coverage, no orphans, no double-mapping. Phase order follows binding owner sequencing constraints (recorded in REQUIREMENTS.md and above): CISHIP first; REVIEW-01's BM-update gate folded into the start of the review-pairing phase; PLANCHK kept fully separate so it cannot block or bundle into review-pairing or CI phases; CIMAINT+ACCEPT grouped as baseline-extension work; PILOT last. Phase 81's `.planning/phases/` directory is explicitly preserved (not cleared) because PLANCHK-03's blind comparison needs the original plan inputs. Flat phase layout (`.planning/phases/<N>-<slug>/`) per the v2.7+ convention.

### Cross-cutting thread

77 and 81 are isolated fixes; 78 is the shared substrate for 79 and 80 (the grading model both consume). Every phase carries the same constraints from the project (spec §7): SecretStr discipline (`.get_secret_value()` only at HTTP client init), loguru-only logging through the redacting sink, atomic write-then-rename for config/state, and the established `httpx.HTTPError` + `pydantic.ValidationError` error-handling pattern, widened only where the spec says so (Phase 80's malformed-record guards). Phase 81's stable per-instance ID (backfilled via the atomic config write) is the only new config-schema addition this milestone, and its ownership-table migration is the only new DB migration.

For v2.13: Phase 83 is the shared substrate for Phase 86 (the paired review workflow Pilot exercises); Phase 82 is the shared substrate Phase 85 extends (CI baseline → follow-on CI improvements). Phase 84 (PLANCHK) is deliberately cross-cutting to nothing — it is isolated by owner instruction and touches no other v2.13 phase's deliverables.

### Blockers/Concerns

- _[Security-sensitive detail removed before publication; the full record is kept privately.]_

### Future Milestones

Organized 2026-10-18 following SeedSyncarr's structure; CI & Review Workflow became the active milestone (v2.13) on 2026-10-21. ROADMAP.md defines two further future milestones below; release versions and phase numbers will be assigned during their planning.

1. **Reliability:** state/config recovery (999.9), narrowed startup/shutdown cleanup (999.13), and ambiguous POST delivery/retry semantics.
2. **Authentication Safety & Responsiveness:** bcrypt offloading (999.4), evidence-backed auth-boundary review (999.10), and compatibility checks for changed paths.

Routine maintenance and the after-v2.12 owner-confirmed review-workflow proposal are in [maintenance](backlog/MAINTENANCE.md). [Earlier backlog and closed decisions](backlog/archive/2026-10-18/README.md) are archived rather than carried forward as pending tasks.

### Quick Tasks Completed

| Date | Task | Outcome |
|------|------|---------|
| 2026-05-19 | Address Dependabot alerts and PR | Merged PR #19 (idna 3.11→3.15, squash cc61133). Closes alert #12 (CVE-2026-45409, IDNA encoding bypass, medium). |
| 2026-10-22 | 261022-l7h: Fix card reasons label for skip-only rows (Phase 83 quick-task review demo, `--full`) | Verified. Test `7da265f`, fix `e0e72ba`; skip-only → "Show N skipped record(s)", 0-failure with unevaluated queue → "Show N detail(s)", real failures unchanged. BM quick review: 0 blockers, 2 warnings. Paired Codex pass recorded in 83-REVIEW-EVIDENCE.md. [261022-l7h](./quick/261022-l7h-fix-card-reasons-label-for-skip-only-row/) |
| 2026-10-26 | 261026-s2v: Activate the Codex-routed plan checker for Triggarr only (`--full`) | Needs Review (verifier human_needed item since fixed: README disable semantics). Plugin under `.claude/plugins/planchk-router` (router `agent.spawn` hook + fail-closed PreToolUse guard), switched on only in gitignored `settings.local.json`. Live smoke: checker → codex `gpt-6-astra`, orchestrator → anthropic; guard refusal proven from real registration. Final head `4d7e677`: BM quick 0 blockers, Codex complete 0 findings; records in 84-REVIEW-EVIDENCE.md. [261026-s2v](./quick/261026-s2v-activate-the-codex-routed-plan-checker-f/) |

### Reference Artifacts

- `docs/bm-greptile-codex-blueprint.md` -- v2.13 review-pairing source of truth (owner-confirmed 2026-10-21, as written)
- `docs/ci-reference-baseline-plan.md` -- v2.13 CI-baseline source of truth (owner-confirmed 2026-10-21, as written)
- `docs/superpowers/specs/2026-10-08-search-correctness-design.md` -- v2.12 design spec
- `docs/superpowers/specs/2026-06-02-recovery-counts-config-design.md` -- v2.10 design spec
- `docs/superpowers/specs/2026-06-02-launch-hardening-design.md` -- v2.9 design spec
- `.planning/milestones/v2.9-ROADMAP.md` -- archived v2.9 roadmap
- `.planning/milestones/v2.8-ROADMAP.md` -- archived v2.8 roadmap
- `.planning/codebase/CONCERNS.md` -- v2.8 source audit (2026-05-25); file:line pointers
- **Note:** `.planning/research/SUMMARY.md` is STALE (prior milestone) — v2.12 skipped research because the approved design spec resolved all technical decisions against the live codebase. Do NOT treat that SUMMARY.md as current research for v2.12 or v2.13.

## Session Continuity

Last session: 2026-10-27T12:37:41.000Z
Stopped at: Phase 85 planned; next: /bm:execute-phase 85
Resume file: .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-CONTEXT.md

## Operator Next Steps

- `/bm:plan-phase 82` -- plan Phase 82 (CI Tests What We Ship) from 82-CONTEXT.md
- Phase 83 begins with REVIEW-01's gate: record the BM baseline, assess the target version's native review/fixer behavior, and get explicit owner approval of the exact version + bounded settings list before any BM update runs
- Phase 84 (PLANCHK) is separately gated: nothing from it is activated in the repo without owner approval, and it blocks no other phase. Routine vibe-check stays on code and control changes until the owner explicitly retires it (PILOT-03); ordinary docs/planning-only changes follow the classification policy once Phase 83 defines it
- Follow-up kept out of PR #28 (carried from v2.12, still open): "Refresh counts" still marks an instance disconnected on one malformed record while scheduled cycles skip the record per item (per-item screening remains deferred; the shared release-date fix also benefits refresh). Decide whether to align it.
- Phase 81 checkout handoff (carried from v2.12): `.planning/` is excluded locally (`.git/info/exclude`). Already-tracked planning files (STATE.md, ROADMAP.md and others) are carried by Git; new or untracked ones are not. The Phase 81 phase directory (`.planning/phases/81-correct-sonarr-grab-attribution/`) is explicitly kept, not cleared, because Phase 84 (PLANCHK-03) needs its original plan inputs for the blind comparison.
