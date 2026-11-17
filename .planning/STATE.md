---
gsd_state_version: 1.0
milestone: v2.14
milestone_name: Reliability
status: executing
stopped_at: Phase 88 plan 01 (bounded upgrade backups) executed, BKUP-01/02 complete; plan 02 (telemetry regression) next
last_updated: "2026-11-17T02:52:15.912Z"
last_activity: 2026-11-17 -- Phase 88 plan 01 executed (bounded upgrade backups, BKUP-01/02 complete)
progress:
  total_phases: 7
  completed_phases: 1
  total_plans: 5
  completed_plans: 4
  percent: 14
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-15)

**Core value:** Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.
**Current focus:** Phase 88: bounded-upgrade-backups-telemetry-regression

> **Releases:** latest release v2.12.1 (2026-11-15, tag on `3cede40`, PR #60): security updates, the Refresh-counts and card-label fixes, lockfile-installed image dependencies. Production runs v2.12.1 since 2026-11-15 (deployed and walked through the same day; the compose service tracks the `:main` tag). v2.13 closed as a milestone on 2026-11-14; its work shipped to users in v2.12.1, there is no v2.13.0 release. Earlier release notes are archived in [STATE history](milestones/STATE-history-through-v2.12.md).

**Published-history note (2026-10-21):** before the first push, this unpushed branch's history was rewritten to remove private infrastructure and credential details from planning text and commit messages. Code, tests and config are byte-identical in every commit (checked commit by commit). Planning docs still cite pre-rewrite hashes; map them as follows: `b35470b` (sandbox build, revision label on `triggarr:phase81-b35470b66f`) → `69f5733`; `a2b8c1c` (full deep review) → `1915a7d`; `d14b71e` → `06519aa`; `9a1d423` (frozen deep-review commit) → `3e19e48`; `363060e` → `c2fb07a`; `b498475` → `91b7992`. The review and live evidence apply unchanged, because the code trees are identical.

## Current Position

Phase: 88 (bounded-upgrade-backups-telemetry-regression) — EXECUTING
Plan: 1 of 2 executed (88-01 bounded backups, BKUP-01/02 complete; 88-02 telemetry regression, Wave 2, next)
Status: Executing Phase 88
Last activity: 2026-11-17 -- Phase 88 plan 01 executed (bounded upgrade backups, BKUP-01/02 complete)

Previous milestone: v2.13 CI & Review Workflow closed 2026-11-14: 6 phases (82, 83, 84, 85, 85.1, 86; last phase 86 merged as PR #59, `e5e1584`), 65 plans, 31/31 requirements. Milestone audit result `tech_debt` with no blockers; the owner accepted the debt ([audit](milestones/v2.13-MILESTONE-AUDIT.md)). Archives: [roadmap](milestones/v2.13-ROADMAP.md), [requirements](milestones/v2.13-REQUIREMENTS.md). No git tag: v2.13 was not cut as a release; its results shipped in v2.12.1, which was deployed to production and walked through with no defects on 2026-11-15.

### v2.14 milestone shape (Phases 87-92; roadmap written 2026-11-15)

Six phases derived from this milestone's 24 requirements (CONSIST, LIFE, DELIV, BKUP, RMINST, TELEM, SMOKE), continuing phase numbering from v2.13's Phase 86 (starts at 87, not reset to 1). Phase order follows the build order recommended in `.planning/research/SUMMARY.md` (2026-11-15): smallest/most-isolated fixes first, then the two higher-blast-radius items, then the cross-cutting smoke-test extension last. LIFE stays in one phase per the roadmapping instruction (startup and shutdown are two sides of one function); DELIV stays in one phase per the roadmapping instruction (the retry-safety fix and the new "unconfirmed" bucket are one change); RMINST is sequenced after CONSIST because both touch the same instance-removal route. Flat phase layout (`.planning/phases/<N>-<slug>/`) per the v2.7+ convention; no phase directories created at roadmap time.

| Phase | Goal | Requirements | Depends on |
|-------|------|--------------|------------|
| 87 — Settings & State-File Safety | A failed settings write during instance removal never corrupts live state; a non-object state file recovers instead of crashing | CONSIST-01..03 | — (first phase) |
| 88 — Bounded Upgrade Backups & Telemetry Regression | Pre-upgrade backups stay capped through a crash loop; a permanent test pins the already-fixed telemetry variable | BKUP-01..02, TELEM-01..02 | — (independent; batched with 87 as equally small, isolated work) |
| 89 — Startup & Shutdown Resource Cleanup | A partial startup closes what it opened; one failed client close never blocks the rest from closing | LIFE-01..03 | — (self-contained; sequenced after 87-88 so the reorder pattern is proven first) |
| 90 — Removed-Instance Pending-Search Lifecycle | A removed Sonarr instance's leftover pending searches get a defined "Instance removed" outcome, never credited to a reused name | RMINST-01..04 | Phase 87 (same instance-removal route) |
| 91 — Search-Command Delivery Confidence | A timed-out search command is never blindly resent; an unconfirmed outcome is tracked honestly | DELIV-01..07 | — (self-contained; sequenced last as the largest blast radius) |
| 92 — Built-Image Recovery Demonstration | CI proves on the real built image that state-file corruption and repeated failed upgrades both recover correctly | SMOKE-01..03 | Phases 87-91 (validates the real fixes, written last) |

**Key v2.14 Phasing Rationale**

- Phases 87-88 go first because both are small, fully independent, reorder-not-rebuild fixes already proven correct elsewhere in the same files — establishing the pattern before it's applied to busier code.
- Phase 90 is sequenced after Phase 87 because it's a genuine dependency: both touch the same `remove_instance` route.
- Phases 89 and 91 are each self-contained but carry the most risk (shared code, more existing tests to keep passing), so they land later — not because they're bigger, but because nothing forces them earlier.
- Phase 92 is last by design: it should validate real fixes, not anticipate them.
- The aiosqlite cursor-lifetime concern named in the earlier roadmap wording was not found by research; SUMMARY.md treats it as closed/not-applicable, and it is not carried into any v2.14 phase unless something surfaces during execution.

### v2.13 milestone shape (closed 2026-11-14; kept as the record)

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

## Performance Metrics

Per-plan metrics through v2.12 are archived in [STATE history](milestones/STATE-history-through-v2.12.md). v2.13 plan durations are recorded in each phase SUMMARY.md.

## Accumulated Context

### Decisions

- 2026-11-15 (Phase 87 deep review close-out, owner): dismissed the record-keeping Warning (planning record corrected in `9648de06`); deferred the cancelled-removal Needs-verification item and the missing bad-instance-URL Save test to the maintenance backlog.
- 2026-11-15 (Phase 87 deep review, owner): the general-only Save Settings case is fixed in Phase 87 after all (`7a92e735`), superseding "Save Settings stays in the backlog" for that case only. Reason: the deep review showed this phase introduced it (a general-only Save overlapping a removal kept the instance removed at `3cede400` and brought it back at `821c8922`); the earlier statement that the phase did not create or widen the Save Settings problem was true only for a Save carrying instance fields, the one case tested at the time. The full-form stale-page case stays in the maintenance backlog.
- 2026-11-15 (Phase 87 review, owner): fix round 1 for the first review's warnings; Codex F001 at `f099c6a8` (Add Instance during a removal save) fixed in Phase 87; Save Settings' stale-snapshot behavior stays in the maintenance backlog (it predates the phase; proposed design recorded there); stopping rule after fix round 2: only critical or warning findings are fixed, minor items go to the backlog; Codex F001 at `0cb0f12e` (removal cancelled mid-save) goes to the backlog, to be fixed once for all settings routes. See 87-REVIEW.md, 87-REVIEW-FIX.md and `.planning/backlog/MAINTENANCE.md`.
- 2026-11-15 (Phase 87 discuss, owner): a failed removal shows its error on the instance row without a page reload, with fixed plain wording; a reset state file is set aside as one copy (both wrong-shape and truncated cases); other settings routes found unsafe and the Save/Add failure messages are recorded in the maintenance backlog, not fixed here; post-save cleanup failures are logged and the user sees a normal removal. See 87-CONTEXT.md.
- 2026-11-15 (v2.14 roadmap): 24 requirements mapped to 6 phases (87-92) with 100% coverage, no orphans, no double-mapping. Phase order follows the build order recommended in `.planning/research/SUMMARY.md`; LIFE and DELIV each kept in one phase per the roadmapping instruction; RMINST sequenced after CONSIST for the shared instance-removal route; Phase 92 depends on all five fix phases since it validates them rather than anticipating them.
- 2026-11-15 (v2.14 start, owner): Reliability scope confirmed as agreed in ROADMAP.md (state/config consistency 999.9, narrowed resource lifecycle 999.13, search-command delivery). Folded in from the backlog: bounding pre-upgrade database backups, a lifecycle for pending searches of a removed Sonarr instance (bugs-005), and SA-12 in reduced form (regression check plus an "unsupported" note; the 2026-11-14 correction showed startup is not affected). The dashboard card re-render/click item was not folded in. Milestone label v2.14, planned release v2.14.0; no v2.13.0 release will exist.
- 2026-10-21 (v2.13 roadmap amendment, owner-authorized for planning only): added the docs/planning review-classification policy. REVIEW-07/08 (Phase 83) define content-based classification (ordinary docs/planning gets a focused consistency review; agent instructions, workflows, hooks, permissions, acceptance/release policy and operational procedures need a risk assessment and technical review; mixed PRs follow their consequential changes; classification recorded against the exact head) and replace blanket "every PR" wording, keeping Codex paired with every BM code-review run. ACCEPT-03 (Phase 85) designs and verifies GitHub-check handling across ordinary-docs, sensitive-docs, mixed and misclassification cases without ad hoc check disabling. Existing protections stay until then; exact-commit owner acceptance stays for every PR. No live settings changed. Now 31 requirements.
- 2026-10-21 (v2.13 roadmap): 28 requirements mapped to 5 phases (82-86) with 100% coverage, no orphans. REVIEW-01 (BM update) folded into the start of Phase 83 rather than a standalone phase, per the granularity rule against single-requirement phases, while keeping its owner-approval gate as that phase's first explicit success criterion. PLANCHK (84) kept fully independent per owner instruction. CIMAINT + ACCEPT grouped into Phase 85 since both extend the Phase 82 CI baseline and CIMAINT-06 feeds Phase 83's risk-based review.
- 2026-10-21 (v2.12 closeout): the owner confirmed the review blueprint and the CI reference-baseline plan as written; they form the CI & Review Workflow milestone. No BM settings, CLAUDE.md, CI or acceptance changes until that milestone implements them.

- 2026-10-30 (Phase 86 discuss, owner): pilot = #48, #36, #44 + two new separate PRs (Refresh-counts skips a malformed record per item; card-template structured reason kind); PILOT-02 comparison is fresh on the Refresh-counts PR's first head; proof-based judging; retire routine vibe-check only if it made no proven unique catch (bar fixed before results). See 86-CONTEXT.md.
- 2026-10-30 (Phase 85.1 closeout, owner): kept the D-16 vibe-check fallback for bot/fork PRs rather than pinning `gpt-5.5` or allowlisting the code-mode notice; closed Phase 85.1 as an exception with live criterion 3 unmet (85.1-REVIEW-EVIDENCE.md).

Full decision log in PROJECT.md Key Decisions table. v2.12 phasing decisions are recorded above in "v2.12 milestone shape" / "Key v2.12 Phasing Rationale", derived from the approved design spec `docs/superpowers/specs/2026-10-08-search-correctness-design.md` (locked grading definitions §3, per-phase behavior + acceptance §4, ordering rationale §5).

- [Phase 88-01]: Followed CONTEXT.md D-01..D-09 exactly: no new dependency; canonical and just-written backups are structurally excluded from the prune candidate set, not merely filtered by a rule that could be bypassed.

### Pending Todos

None currently pending. (Bound/prune timestamped pre-migration DB backups, previously tracked here, closed 2026-11-17 by Phase 88 plan 01 -- BKUP-01/02.)

### Roadmap Evolution

Earlier entries (v2.8-v2.12) are archived in [STATE history](milestones/STATE-history-through-v2.12.md).

v2.13 roadmap created 2026-10-21 from the owner-confirmed review blueprint (`docs/bm-greptile-codex-blueprint.md`) and CI reference-baseline plan (`docs/ci-reference-baseline-plan.md`). 28 requirements across 5 phases (82-86, continuing from v2.12's Phase 81 — not reset to 1). 100% coverage, no orphans, no double-mapping. Phase order follows binding owner sequencing constraints (recorded in REQUIREMENTS.md and above): CISHIP first; REVIEW-01's BM-update gate folded into the start of the review-pairing phase; PLANCHK kept fully separate so it cannot block or bundle into review-pairing or CI phases; CIMAINT+ACCEPT grouped as baseline-extension work; PILOT last. Phase 81's `.planning/phases/` directory is explicitly preserved (not cleared) because PLANCHK-03's blind comparison needs the original plan inputs. Flat phase layout (`.planning/phases/<N>-<slug>/`) per the v2.7+ convention.

v2.14 roadmap created 2026-11-15 from the owner-confirmed scope in PROJECT.md and the build order recommended in `.planning/research/SUMMARY.md` (2026-11-15). 24 requirements across 6 phases (87-92, continuing from v2.13's Phase 86 — not reset to 1). 100% coverage, no orphans, no double-mapping. LIFE and DELIV each kept in one phase per the roadmapping instruction; RMINST sequenced after CONSIST for the shared instance-removal route; the built-image smoke-test phase (92) depends on all five fix phases. Flat phase layout (`.planning/phases/<N>-<slug>/`) per the v2.7+ convention; no phase directories created yet.

### Cross-cutting thread

For v2.13: Phase 83 is the shared substrate for Phase 86 (the paired review workflow Pilot exercises); Phase 82 is the shared substrate Phase 85 extends (CI baseline → follow-on CI improvements). Phase 84 (PLANCHK) is deliberately cross-cutting to nothing — it is isolated by owner instruction and touches no other v2.13 phase's deliverables.

For v2.14: Phase 87 is the shared substrate for Phase 90 (both touch the instance-removal route); Phases 87-91 together are the shared substrate for Phase 92 (the built-image smoke test demonstrates their fixes, not its own new behavior).

### Blockers/Concerns

- 2026-11-13 (resolved the same day): CI on main failed after the PR #54 merge for three date-driven reasons (a new `opentelemetry-api` advisory, review-tooling tests that read the real clock, and two HIGH `zlib1g` findings in the base image). PR #57 fixed all three; main CI passes at `aeead4b`. The temporary Dockerfile step it added is tracked for removal in backlog/MAINTENANCE.md.
- _[Security-sensitive detail removed before publication; the full record is kept privately.]_

### Future Milestones

Organized 2026-10-18 following SeedSyncarr's structure; CI & Review Workflow became the active milestone (v2.13) on 2026-10-21. Reliability became the active milestone (v2.14) on 2026-11-15. ROADMAP.md defines the further future milestones; release versions and phase numbers will be assigned during their planning.

1. **Authentication Safety & Responsiveness:** bcrypt offloading (999.4), evidence-backed auth-boundary review (999.10), and compatibility checks for changed paths.

Routine maintenance and the after-v2.12 owner-confirmed review-workflow proposal are in [maintenance](backlog/MAINTENANCE.md). [Earlier backlog and closed decisions](backlog/archive/2026-10-18/README.md) are archived rather than carried forward as pending tasks.

### Quick Tasks Completed

| Date | Task | Outcome |
|------|------|---------|
| 2026-05-19 | Address Dependabot alerts and PR | Merged PR #19 (idna 3.11→3.15, squash cc61133). Closes alert #12 (CVE-2026-45409, IDNA encoding bypass, medium). |
| 2026-10-22 | 261022-l7h: Fix card reasons label for skip-only rows (Phase 83 quick-task review demo, `--full`) | Verified. Test `7da265f`, fix `e0e72ba`; skip-only → "Show N skipped record(s)", 0-failure with unevaluated queue → "Show N detail(s)", real failures unchanged. BM quick review: 0 blockers, 2 warnings. Paired Codex pass recorded in 83-REVIEW-EVIDENCE.md. [261022-l7h](./quick/261022-l7h-fix-card-reasons-label-for-skip-only-row/) |
| 2026-10-30 | 261030-oaf: Stop Codex startup code-mode notice from failing the untrusted-path event audit (`--full`) | Not executed (owner decision). Research: disabling `code_mode` does not suppress the notice (default model is code-mode-only; `-m gpt-5.5` does). Owner kept the vibe-check fallback; no code change, no review. [261030-oaf](./quick/261030-oaf-stop-codex-startup-code-mode-notice-from/) |
| 2026-10-26 | 261026-s2v: Activate the Codex-routed plan checker for Triggarr only (`--full`) | Needs Review (verifier human_needed item since fixed: README disable semantics). Plugin under `.claude/plugins/planchk-router` (router `agent.spawn` hook + fail-closed PreToolUse guard), switched on only in gitignored `settings.local.json`. Live smoke: checker → codex `gpt-6-astra`, orchestrator → anthropic; guard refusal proven from real registration. Final head `4d7e677`: BM quick 0 blockers, Codex complete 0 findings; records in 84-REVIEW-EVIDENCE.md. [261026-s2v](./quick/261026-s2v-activate-the-codex-routed-plan-checker-f/) |

### Reference Artifacts

- `docs/bm-greptile-codex-blueprint.md` -- v2.13 review-pairing source of truth (owner-confirmed 2026-10-21, as written)
- `docs/ci-reference-baseline-plan.md` -- v2.13 CI-baseline source of truth (owner-confirmed 2026-10-21, as written)
- `.planning/research/SUMMARY.md` -- v2.14 Reliability research (completed 2026-11-15); current for v2.14, defect confirmations and build-order rationale
- `docs/superpowers/specs/2026-10-08-search-correctness-design.md` -- v2.12 design spec
- `docs/superpowers/specs/2026-06-02-recovery-counts-config-design.md` -- v2.10 design spec
- `docs/superpowers/specs/2026-06-02-launch-hardening-design.md` -- v2.9 design spec
- `.planning/milestones/v2.9-ROADMAP.md` -- archived v2.9 roadmap
- `.planning/milestones/v2.8-ROADMAP.md` -- archived v2.8 roadmap
- `.planning/codebase/CONCERNS.md` -- v2.8 source audit (2026-05-25); file:line pointers

## Deferred Items

Items acknowledged and deferred at milestone close on 2026-11-14:

| Kind | Item | Status |
|------|------|--------|
| uat | Phase 85 UAT item 5: the next release's CHANGELOG states that Python wheel/sdist are no longer attached as release assets (D-14) | Closed 2026-11-15 by v2.12.1 |
| follow-up | Add a "superseded by PILOT-03" note to docs/bm-greptile-codex-blueprint.md | Deferred (rides with the next substantive PR) |
| follow-up | Draft VALIDATION.md files for Phases 83, 85 and 86 (nyquist_compliant false) | Deferred (owner has not asked for them) |
| follow-up | Tag-triggered publication is unverified until the next authorized release (Phase 82 waiver) | Closed 2026-11-15: tag-triggered Release run 43758123019 succeeded for v2.12.1 |
| follow-up | Phase 87 deep-review deferrals: `save_settings` close loop not cancellation-safe, self-cancelled close aborts a committed removal's response, startup set-aside copy blocks the loop, BM iteration 6 IN-01..03 | Deferred 2026-11-16 (backlog/MAINTENANCE.md) |
| follow-up | Isolated Codex review for bot/fork PRs is incomplete on current Codex models (Phase 85.1 exception); vibe-check fallback stays | Deferred (reopening tracked in backlog/MAINTENANCE.md) |

## Session Continuity

Last session: 2026-11-17T02:52:15.908Z
Stopped at: Phase 88 plan 01 (bounded upgrade backups) executed, BKUP-01/02 complete; plan 02 (telemetry regression) next
Resume file: .planning/phases/88-bounded-upgrade-backups-telemetry-regression/88-02-PLAN.md

## Operator Next Steps

- Discuss Phase 88 next (`/bm:discuss-phase 88`), on branch `phase-88-bounded-upgrade-backups-telemetry-regression` (cut from main at `d7704342`; carries Phase 87's closeout records: this update, the PR #62 checkpoint copy and the PR-head Codex evidence)
- Production compose tracks `:main`, so a pull and recreate now runs Phase 87; not done yet
- Production runs v2.12.1 (deployed and walked through 2026-11-15). The production compose service tracks the `:main` tag on purpose (owner, 2026-11-15: "main is fine"), so a later recreate after a merge to main runs main, not the last release. The held branch `planning/post-v2.12.1` is pushed with the next substantive push, not on its own (no docs-only PRs)
- Decide BM SA-01 (pin the uv version CI installs) -- see backlog/MAINTENANCE.md. SA-12 is in v2.14 scope in reduced form (startup is not affected; regression check plus an "unsupported" note)
- Release follow-ups from v2.12.1: remove the temporary `zlib1g` Dockerfile step once the base image carries the fix; update the `idna` text in docs/ci-negative-demonstrations.md; add the "superseded by PILOT-03" note to the blueprint -- see backlog/MAINTENANCE.md and Deferred Items
- Follow-up carried from v2.12: "Refresh counts" vs scheduled cycles on a malformed record -- owner decided 2026-10-30 to align (skip per record); delivered as a Phase 86 pilot PR (86-CONTEXT D-02)
- `.planning/` is excluded locally (`.git/info/exclude`): tracked planning files are carried by Git, new ones need `git add -f`
