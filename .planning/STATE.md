---
gsd_state_version: 1.0
milestone: v2.13
milestone_name: CI & Review Workflow
status: "Phase 86 complete -- PR #59 merged as e5e1584 (main CI passing); PILOT-01..04 recorded; all v2.13 phases executed; milestone audit next"
stopped_at: "Phase 86 PR #59 accepted (review acceptance run 43620557671) and merged on the owner's instruction as e5e1584 (2026-11-14T20:11:46Z); main CI run 43636188254 and the post-merge Release run 43636707792 both passing. Next: milestone audit (/bm:audit-milestone), then milestone closeout"
last_updated: "2026-11-14T20:27:01Z"
last_activity: "2026-11-14 -- Phase 86 PR #59 pushed (head 6ca643d), per-head checkpoint comment, owner settled codex:6ca643dcf210:a1:F001 as non-blocking debt; later-found-misses update and checkpoint record added at head 92b9dac; owner approved review acceptance (run 43620557671) and merged as e5e1584; main CI and the post-merge Release workflow both passing"
progress:
  total_phases: 7
  completed_phases: 6
  total_plans: 65
  completed_plans: 65
  percent: 86
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-21)

**Core value:** Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.
**Current focus:** Phase 86 complete (PR #59 merged as `e5e1584`); v2.13 milestone audit and closeout next

> **Releases:** latest release v2.12.0 (2026-10-21, tag on `dbb38fa`); production runs v2.12.0. v2.13 is unreleased. Earlier release notes are archived in [STATE history](milestones/STATE-history-through-v2.12.md).

**Published-history note (2026-10-21):** before the first push, this unpushed branch's history was rewritten to remove private infrastructure and credential details from planning text and commit messages. Code, tests and config are byte-identical in every commit (checked commit by commit). Planning docs still cite pre-rewrite hashes; map them as follows: `b35470b` (sandbox build, revision label on `triggarr:phase81-b35470b66f`) → `69f5733`; `a2b8c1c` (full deep review) → `1915a7d`; `d14b71e` → `06519aa`; `9a1d423` (frozen deep-review commit) → `3e19e48`; `363060e` → `c2fb07a`; `b498475` → `91b7992`. The review and live evidence apply unchanged, because the code trees are identical.

## Current Position

Phase: 86 (Pilot & Reference Record) — COMPLETE (merged, PR #59 as `e5e1584`)
Plan: 10 of 10 finished (Phase 86 has ten plans, 86-01..86-10)
Status: Phase 86 complete. PR #59 (phase PR: pilot & reference record, PILOT-03 decisions, adoption guide) accepted at head `92b9daca2775` (review acceptance run 43620557671) and merged by the owner as `e5e1584` (2026-11-14T20:11:46Z); main CI (run 43636188254) and the post-merge Release workflow (run 43636707792) both passing. All v2.13 phases (82, 83, 84, 85, 85.1, 86) are now executed. Next: the milestone audit (`/bm:audit-milestone`), then milestone closeout.
Last activity: 2026-11-14 -- Phase 86 PR #59 pushed and accepted; owner merged as `e5e1584`; main CI and the post-merge Release workflow both green; milestone audit next.

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

## Performance Metrics

Per-plan metrics through v2.12 are archived in [STATE history](milestones/STATE-history-through-v2.12.md). v2.13 plan durations are recorded in each phase SUMMARY.md.

## Accumulated Context

### Decisions

- 2026-10-21 (v2.13 roadmap amendment, owner-authorized for planning only): added the docs/planning review-classification policy. REVIEW-07/08 (Phase 83) define content-based classification (ordinary docs/planning gets a focused consistency review; agent instructions, workflows, hooks, permissions, acceptance/release policy and operational procedures need a risk assessment and technical review; mixed PRs follow their consequential changes; classification recorded against the exact head) and replace blanket "every PR" wording, keeping Codex paired with every BM code-review run. ACCEPT-03 (Phase 85) designs and verifies GitHub-check handling across ordinary-docs, sensitive-docs, mixed and misclassification cases without ad hoc check disabling. Existing protections stay until then; exact-commit owner acceptance stays for every PR. No live settings changed. Now 31 requirements.
- 2026-10-21 (v2.13 roadmap): 28 requirements mapped to 5 phases (82-86) with 100% coverage, no orphans. REVIEW-01 (BM update) folded into the start of Phase 83 rather than a standalone phase, per the granularity rule against single-requirement phases, while keeping its owner-approval gate as that phase's first explicit success criterion. PLANCHK (84) kept fully independent per owner instruction. CIMAINT + ACCEPT grouped into Phase 85 since both extend the Phase 82 CI baseline and CIMAINT-06 feeds Phase 83's risk-based review.
- 2026-10-21 (v2.12 closeout): the owner confirmed the review blueprint and the CI reference-baseline plan as written; they form the CI & Review Workflow milestone. No BM settings, CLAUDE.md, CI or acceptance changes until that milestone implements them.

- 2026-10-30 (Phase 86 discuss, owner): pilot = #48, #36, #44 + two new separate PRs (Refresh-counts skips a malformed record per item; card-template structured reason kind); PILOT-02 comparison is fresh on the Refresh-counts PR's first head; proof-based judging; retire routine vibe-check only if it made no proven unique catch (bar fixed before results). See 86-CONTEXT.md.
- 2026-10-30 (Phase 85.1 closeout, owner): kept the D-16 vibe-check fallback for bot/fork PRs rather than pinning `gpt-5.5` or allowlisting the code-mode notice; closed Phase 85.1 as an exception with live criterion 3 unmet (85.1-REVIEW-EVIDENCE.md).

Full decision log in PROJECT.md Key Decisions table. v2.12 phasing decisions are recorded above in "v2.12 milestone shape" / "Key v2.12 Phasing Rationale", derived from the approved design spec `docs/superpowers/specs/2026-10-08-search-correctness-design.md` (locked grading definitions §3, per-phase behavior + acceptance §4, ordering rationale §5).

### Pending Todos

- Deferred follow-up: bound/prune timestamped pre-migration DB backups (Plan 81-03 keeps the first backup and timestamps later ones with no cleanup, so a startup crash-loop on a failing upgrade accumulates copies). Not Phase 81 scope.

### Roadmap Evolution

Earlier entries (v2.8-v2.12) are archived in [STATE history](milestones/STATE-history-through-v2.12.md).

v2.13 roadmap created 2026-10-21 from the owner-confirmed review blueprint (`docs/bm-greptile-codex-blueprint.md`) and CI reference-baseline plan (`docs/ci-reference-baseline-plan.md`). 28 requirements across 5 phases (82-86, continuing from v2.12's Phase 81 — not reset to 1). 100% coverage, no orphans, no double-mapping. Phase order follows binding owner sequencing constraints (recorded in REQUIREMENTS.md and above): CISHIP first; REVIEW-01's BM-update gate folded into the start of the review-pairing phase; PLANCHK kept fully separate so it cannot block or bundle into review-pairing or CI phases; CIMAINT+ACCEPT grouped as baseline-extension work; PILOT last. Phase 81's `.planning/phases/` directory is explicitly preserved (not cleared) because PLANCHK-03's blind comparison needs the original plan inputs. Flat phase layout (`.planning/phases/<N>-<slug>/`) per the v2.7+ convention.

### Cross-cutting thread

For v2.13: Phase 83 is the shared substrate for Phase 86 (the paired review workflow Pilot exercises); Phase 82 is the shared substrate Phase 85 extends (CI baseline → follow-on CI improvements). Phase 84 (PLANCHK) is deliberately cross-cutting to nothing — it is isolated by owner instruction and touches no other v2.13 phase's deliverables.

### Blockers/Concerns

- 2026-11-13 (resolved the same day): CI on main failed after the PR #54 merge for three date-driven reasons (a new `opentelemetry-api` advisory, review-tooling tests that read the real clock, and two HIGH `zlib1g` findings in the base image). PR #57 fixed all three; main CI passes at `aeead4b`. The temporary Dockerfile step it added is tracked for removal in backlog/MAINTENANCE.md.
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
| 2026-10-30 | 261030-oaf: Stop Codex startup code-mode notice from failing the untrusted-path event audit (`--full`) | Not executed (owner decision). Research: disabling `code_mode` does not suppress the notice (default model is code-mode-only; `-m gpt-5.5` does). Owner kept the vibe-check fallback; no code change, no review. [261030-oaf](./quick/261030-oaf-stop-codex-startup-code-mode-notice-from/) |
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

Last session: 2026-11-14T20:27:01Z
Stopped at: Phase 86 PR #59 accepted (run 43620557671) and merged as e5e1584; main CI and the post-merge Release workflow both passing. Next: the v2.13 milestone audit (/bm:audit-milestone), then milestone closeout
Resume file: none (Phase 86 is merged; the next step is the milestone audit, not a plan file)

## Operator Next Steps

- Phase 86 is complete: PR #59 (push, checkpoint comments, exact-commit owner acceptance at `92b9daca2775`, run 43620557671) merged by the owner as `e5e1584`; main CI and the post-merge Release workflow both pass. Next: the v2.13 milestone audit and closeout (`/bm:audit-milestone`). This held planning branch (`planning/post-phase-86`) is pushed with the next substantive push, not on its own (no docs-only PRs). The Roadmaps page still needs the owner's own check for a "Planning files disagree" warning now that Phase 86 is ticked complete — no tool access to the rendered page from this session. The review-loop backlog named under "Stopping rule" in 86-REVIEW-EVIDENCE.md is now filed in `backlog/MAINTENANCE.md` ("Phase 86 review-loop follow-ups")
- Decide BM SA-01 (pin the uv version CI installs) and SA-12 (FastAPI opt-in OpenTelemetry auto-configure can fail startup if a user sets it) -- see backlog/MAINTENANCE.md
- Next release (v2.13.x): CHANGELOG states wheels/sdists are no longer attached (Phase 85 UAT P5); roll in open Dependabot alerts/PRs per the release rule; add an unreleased CHANGELOG section covering the two security fixes from PR #57 (`opentelemetry-api` 1.45.2, `zlib1g` upgrade in the image)
- Follow-up carried from v2.12: "Refresh counts" vs scheduled cycles on a malformed record -- owner decided 2026-10-30 to align (skip per record); delivered as a Phase 86 pilot PR (86-CONTEXT D-02)
- `.planning/` is excluded locally (`.git/info/exclude`): tracked planning files are carried by Git, new ones need `git add -f`
