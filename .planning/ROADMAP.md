# Roadmap: Triggarr

## Overview

Triggarr is a single-process automation daemon that cycles through Radarr, Sonarr, and Lidarr's wanted/cutoff-unmet lists on a configurable schedule, with closed-loop download tracking. Security invariants (no API key in any HTTP response) are established from day one and never relaxed.

## Milestones

- ✅ v1.0 MVP -- Phases 1-8 (shipped 2026-02-24) -- [archive](milestones/v1.0-ROADMAP.md)
- ✅ v1.1 Ship & Document -- Phases 9-12 (shipped 2026-02-24) -- [archive](milestones/v1.1-ROADMAP.md)
- ✅ v1.2 Polish & Harden -- Phases 13-16 (shipped 2026-02-24) -- [archive](milestones/v1.2-ROADMAP.md)
- ✅ v2.0 Closed-Loop Tracking -- Phases 17-22 (shipped 2026-03-09) -- [archive](milestones/v2.0-ROADMAP.md)
- ✅ v2.1 Harden & Fix -- Phases 23-24 (shipped 2026-03-09) -- [archive](milestones/v2.1-ROADMAP.md)
- ✅ v2.2 Skip Unreleased Media -- Phases 25-28 (shipped 2026-03-09) -- [archive](milestones/v2.2-ROADMAP.md)
- ✅ v2.3 Multi-Instance & Tag Filtering -- Phases 33-44 (shipped 2026-03-14) -- [archive](milestones/v2.3-ROADMAP.md)
- ✅ v2.4 Community Polish & Test Hardening -- Phases 45-47 (shipped 2026-04-09) -- [archive](milestones/v2.4-ROADMAP.md)
- ✅ v2.5 Dashboard UI Refresh -- Phases 48-53 (shipped 2026-04-13) -- [archive](milestones/v2.5-ROADMAP.md)
- ✅ v2.6 Built-In Authentication -- Phases 54-59 (shipped 2026-04-15) -- [archive](milestones/v2.6-ROADMAP.md)
- ✅ v2.7 Dashboard Scale Refresh -- Phases 60-63 (shipped 2026-04-18) -- [archive](milestones/v2.7-ROADMAP.md)
- ✅ v2.8 Hardening & Observability -- Phases 64-67 (shipped 2026-06-01) -- [archive](milestones/v2.8-ROADMAP.md)
- ✅ v2.9 Launch-Hardening / Sibling Consistency -- Phases 68-71 (shipped 2026-06-03) -- [archive](milestones/v2.9-ROADMAP.md)
- ✅ v2.10 Recovery, Counts & Config Parity -- Phases 72-75 (shipped 2026-06-04) -- [archive](milestones/v2.10-ROADMAP.md)
- ✅ v2.11 Never-Searched-First Search Queue Priority -- Phase 76 (shipped 2026-06-04) -- [archive](milestones/v2.11-ROADMAP.md)
- ✅ v2.12 Search Correctness & Trustworthy Feedback -- Phases 77-81 (shipped 2026-10-21) -- [archive](milestones/v2.12-ROADMAP.md)
- 🔨 v2.13 CI & Review Workflow -- Phases 82-86 (in progress)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-8) -- SHIPPED 2026-02-24</summary>

- [x] Phase 1: Foundation (3/3 plans) -- completed 2026-02-23
- [x] Phase 2: Search Engine (3/3 plans) -- completed 2026-02-24
- [x] Phase 3: Web UI (3/3 plans) -- completed 2026-02-24
- [x] Phase 4: Docker (1/1 plan) -- completed 2026-02-24
- [x] Phase 5: Security Hardening (2/2 plans) -- completed 2026-02-24
- [x] Phase 6: Bug Fixes & Resilience (3/3 plans) -- completed 2026-02-24
- [x] Phase 7: Test Coverage (2/2 plans) -- completed 2026-02-24
- [x] Phase 8: Tech Debt Cleanup (1/1 plan) -- completed 2026-02-24

</details>

<details>
<summary>v1.1 Ship & Document (Phases 9-12) -- SHIPPED 2026-02-24</summary>

- [x] Phase 9: CI/CD Pipeline (1/1 plan) -- completed 2026-02-24
- [x] Phase 10: Release Pipeline (1/1 plan) -- completed 2026-02-24
- [x] Phase 11: Search Enhancements (2/2 plans) -- completed 2026-02-24
- [x] Phase 12: Documentation (1/1 plan) -- completed 2026-02-24

</details>

<details>
<summary>v1.2 Polish & Harden (Phases 13-16) -- SHIPPED 2026-02-24</summary>

- [x] Phase 13: CI & Search Diagnostics (2/2 plans) -- completed 2026-02-24
- [x] Phase 14: Dashboard Observability (2/2 plans) -- completed 2026-02-24
- [x] Phase 15: Search History UI (2/2 plans) -- completed 2026-02-24
- [x] Phase 16: Deep Code Review (2/2 plans) -- completed 2026-02-24

</details>

<details>
<summary>v2.0 Closed-Loop Tracking (Phases 17-22) -- SHIPPED 2026-03-09</summary>

- [x] Phase 17: Foundation & DB Preparation (3/3 plans) -- completed 2026-02-25
- [x] Phase 18: Security & Operations (2/2 plans) -- completed 2026-02-25
- [x] Phase 19: Tracking Infrastructure (2/2 plans) -- completed 2026-02-25
- [x] Phase 20: Tracking Integration (3/3 plans) -- completed 2026-02-25
- [x] Phase 20.1: Deep Review — Security & Safety (2/2 plans) -- completed 2026-02-26
- [x] Phase 20.2: Deep Review — Code Quality (2/2 plans) -- completed 2026-02-26
- [x] Phase 21: Dashboard & Stats (2/2 plans) -- completed 2026-03-07
- [x] Phase 22: Rename to Triggarr (2/2 plans) -- completed 2026-03-07

</details>

<details>
<summary>v2.1 Harden & Fix (Phases 23-24) -- SHIPPED 2026-03-09</summary>

- [x] Phase 23: Deploy Fixes (1/1 plan) -- completed 2026-03-09
- [x] Phase 24: Hardening (1/1 plan) -- completed 2026-03-09

</details>

<details>
<summary>v2.2 Skip Unreleased Media (Phases 25-28) -- SHIPPED 2026-03-09</summary>

- [x] Phase 25: Filter Foundation (1/1 plan) -- completed 2026-03-09
- [x] Phase 26: Settings UI & Engine Integration (1/1 plan) -- completed 2026-03-09
- [x] Phase 27: Dashboard Display (1/1 plan) -- completed 2026-03-09
- [x] Phase 28: Fix Code Review Findings (2/2 plans) -- completed 2026-03-09

</details>

<details>
<summary>v2.3 Multi-Instance & Tag Filtering (Phases 33-44) -- SHIPPED 2026-03-14</summary>

- [x] Phase 33: Config Model & Migration (2/2 plans) -- completed 2026-03-11
- [x] Phase 34: State Model & Cursor Isolation (2/2 plans) -- completed 2026-03-11
- [x] Phase 35: Client Registry & Tag Resolution (1/1 plan) -- completed 2026-03-11
- [x] Phase 36: Search Engine & Tag Filtering (2/2 plans) -- completed 2026-03-11
- [x] Phase 37: Database Schema & Instance Scoping (1/1 plan) -- completed 2026-03-11
- [x] Phase 38: Scheduler & Tracking Wiring (1/1 plan) -- completed 2026-03-11
- [x] Phase 39: Web UI Integration (1/1 plan) -- completed 2026-03-11
- [x] Phase 40: Fix Multi-Instance Bugs (3/3 plans) -- completed 2026-03-12
- [x] Phase 41: Multi-Instance Settings UI (1/1 plan) -- completed 2026-03-12
- [x] Phase 42: Dashboard Enhancements (2/2 plans) -- completed 2026-03-13
- [x] Phase 43: Update Notification & Cleanup (1/1 plan) -- completed 2026-03-13
- [x] Phase 44: Deep Review Fixes (1/1 plan) -- completed 2026-03-14

</details>

<details>
<summary>v2.4 Community Polish & Test Hardening (Phases 45-47) -- SHIPPED 2026-04-09</summary>

- [x] Phase 45: Community Health & Repo Metadata (2/2 plans) -- completed 2026-04-09
- [x] Phase 46: Test Hardening -- Infrastructure Failures (2/2 plans) -- completed 2026-04-09
- [x] Phase 47: Test Hardening -- State & Search Edge Cases (2/2 plans) -- completed 2026-04-09

</details>

<details>
<summary>v2.5 Dashboard UI Refresh (Phases 48-53) -- SHIPPED 2026-04-13</summary>

- [x] Phase 48: Foundations & Navigation Chrome (3/3 plans) -- completed 2026-04-13
- [x] Phase 49: Stats & Health Strip (3/3 plans) -- completed 2026-04-13
- [x] Phase 50: App Cards & Services Grid (2/2 plans) -- completed 2026-04-13
- [x] Phase 51: Application Log Redesign (3/3 plans) -- completed 2026-04-13
- [x] Phase 52: Recent Activity Rail (2/2 plans) -- completed 2026-04-13
- [x] Phase 53: Docs & Metadata (2/2 plans) -- completed 2026-04-13

</details>

<details>
<summary>v2.6 Built-In Authentication (Phases 54-59) -- SHIPPED 2026-04-15</summary>

- [x] Phase 54: Auth Config & Helpers (2/2 plans) -- completed 2026-04-14
- [x] Phase 55: Auth Middleware & Health Endpoint (2/2 plans) -- completed 2026-04-15
- [x] Phase 56: First-Run Setup & Login (4/4 plans) -- completed 2026-04-15
- [x] Phase 57: Settings Security & Nav Logout (2/2 plans) -- completed 2026-04-15
- [x] Phase 58: Auth Test Suite (2/2 plans) -- completed 2026-04-15
- [x] Phase 59: Security Hardening (4/4 plans) -- completed 2026-04-15

</details>

<details>
<summary>v2.7 Dashboard Scale Refresh (Phases 60-63) -- SHIPPED 2026-04-18</summary>

- [x] Phase 60: Foundation & Header (3/3 plans) -- completed 2026-04-16
- [x] Phase 61: Stat Cards & App Cards (2/2 plans) -- completed 2026-04-16
- [x] Phase 62: Activity Rail & Log Viewer (2/2 plans) -- completed 2026-04-17
- [x] Phase 63: Header Favicon Icon (1/1 plan) -- completed 2026-04-17

</details>

<details>
<summary>v2.8 Hardening & Observability (Phases 64-67) -- SHIPPED 2026-06-01</summary>

- [x] Phase 64: Data Safety & Config Integrity (4/4 plans) -- completed 2026-05-26
- [x] Phase 65: Scheduler Hardening & Resilience (4/4 plans) -- completed 2026-05-26
- [x] Phase 66: Security Hardening (5/5 plans) -- completed 2026-05-26
- [x] Phase 67: Observability & CSRF Test Coverage (3/3 plans) -- completed 2026-05-31

Full phase details: [milestones/v2.8-ROADMAP.md](milestones/v2.8-ROADMAP.md)

</details>

<details>
<summary>✅ v2.9 Launch-Hardening / Sibling Consistency (Phases 68-71) -- SHIPPED 2026-06-03</summary>

- [x] Phase 68: Code-track hostile-reader discovery (1/1 plan) -- completed 2026-06-02
- [x] Phase 69: Code-track hardening (3/3 plans) -- completed 2026-06-02
- [x] Phase 70: Presentation discovery (1/1 plan) -- completed 2026-06-02
- [x] Phase 71: Presentation rewrite (6/6 plans) -- completed 2026-06-02

Full phase details: [milestones/v2.9-ROADMAP.md](milestones/v2.9-ROADMAP.md)

</details>

<details>
<summary>✅ v2.10 Recovery, Counts & Config Parity (Phases 72-75) -- SHIPPED 2026-06-04</summary>

- [x] Phase 72: Password Reset Backend & Token Lifecycle (3/3 plans) -- completed 2026-06-03
- [x] Phase 73: Password Reset UI (1/1 plan) -- completed 2026-06-03
- [x] Phase 74: Count-Only Refresh (3/3 plans) -- completed 2026-06-04
- [x] Phase 75: Drain-Timeout Config Parity & Deferred-Record Correction (4/4 plans) -- completed 2026-06-04

Full phase details: [milestones/v2.10-ROADMAP.md](milestones/v2.10-ROADMAP.md)

</details>

<details>
<summary>✅ v2.11 Never-Searched-First Search Queue Priority (Phase 76) -- SHIPPED 2026-06-04</summary>

- [x] Phase 76: Never-Searched-First Search Queue (3/3 plans) -- completed 2026-06-04

Replaced the integer-cursor walk with an ordered per-instance searched-log on `AppState` + a pure `prioritize_batch()` dispatcher (never-searched-first, top-up oldest-searched-first, mark-on-attempt, reset-per-pass, prune-to-eligible, commit-at-cycle-end); `_merge_defaults` strips legacy cursor keys on load; `slice_batch` removed. QUEUE-01..11.

Full phase details: [milestones/v2.11-ROADMAP.md](milestones/v2.11-ROADMAP.md)

</details>

<details>
<summary>✅ v2.12 Search Correctness & Trustworthy Feedback (Phases 77-81) -- SHIPPED 2026-10-21</summary>

- [x] Phase 77: Secret & Reset-Token Log Hygiene (5/5 plans) -- completed 2026-10-08
- [x] Phase 78: Honest Cycle Outcomes (5/5 plans) -- completed 2026-10-09
- [x] Phase 79: Tag-Scoped Searches Stay in Scope (4/4 plans) -- completed 2026-10-18
- [x] Phase 80: Cycle Robustness & Sonarr Season Dedup (5/5 plans) -- completed 2026-10-18
- [x] Phase 81: Correct Sonarr Grab Attribution + v5 Compatibility (14/14 plans) -- completed 2026-10-21

Search exactly what the user configured and report honestly what happened. Reset tokens and *arr secrets stay out of the in-app logs; each cycle is graded Success/Partial/Failed/Nothing needed; an unresolved tag skips its queue; one malformed record no longer wedges a cycle and a Sonarr season gets at most one dispatch per cycle; Sonarr grabs credit only the matching series+season, once, counting distinct episodes, with stable instance IDs and an honest stats cutover note; Sonarr v5 compatibility verified live on isolated v5/v4 sandboxes. Released as v2.12.0 (PRs #26-#30; tag on dbb38fa).

Full phase details: [milestones/v2.12-ROADMAP.md](milestones/v2.12-ROADMAP.md)

</details>

### 🔨 v2.13 CI & Review Workflow (Phases 82-86, in progress)

- [x] **Phase 82: CI Tests What We Ship** - Shipped-image startup, browser regression, and release-version checks join the required gate
- [x] **Phase 83: Paired BM + Codex Review & Risk-Based Depth** - A gated BM update, then every BM review gets an independent Codex pass plus a high-risk vibe-check recommendation (merged 2026-10-23, PR #35)
- [x] **Phase 84: Codex Plan-Checker Investigation** - Record whether a narrowly scoped hook can route only the plan checker, and how it compares on the original Phase 81 plans — separately gated, nothing activated without approval (verified 2026-10-26: hook routing proven; blind comparison invalid — input was post-review, not original; owner chose to adopt anyway, activation is a separate quick task)
- [ ] **Phase 85: Follow-on CI Improvements & Acceptance Usability** - Dependency/image/lint/coverage/permissions hardening plus an acceptance register usable under real PR traffic
- [ ] **Phase 85.1: Isolated Codex Review for Untrusted PRs** (INSERTED) - Bot/fork PRs get the paired Codex review through an enforced isolation boundary instead of the interim per-PR fallback
- [ ] **Phase 86: Pilot & Reference Record** - 3-5 real PRs run the paired workflow; the owner records a retirement decision and reusable guidance is written

### Phase 82: CI Tests What We Ship

**Goal**: CI proves the exact artifact it will publish actually works — image startup, critical browser flows, and release-version identity are all tested before publication, and a broken instance of each check fails.
**Depends on**: Nothing (first phase)
**Requirements**: CISHIP-01, CISHIP-02, CISHIP-03, CISHIP-04
**Success Criteria** (what must be TRUE):
  1. CI starts the exact publish-candidate image through its normal entrypoint with isolated test config and mocked/test services, and verifies health, setup/login, static assets, writable config, and persistence across a restart; a deliberately broken entrypoint and a deliberately missing static asset each make the check fail. (GitHub-enforced: required status check)
  2. A small browser regression suite asserts the connection-pill request-loop behavior and critical setup/login behavior as observable behavior, not screenshots; reintroducing the polling bug makes the suite fail, and failure logs/screenshots are uploaded as artifacts with no secrets present. (GitHub-enforced)
  3. Before any version-tag publication, CI rejects a tag that disagrees with package metadata or image version, and accepts one that matches — both proven without publishing a production tag, with exact-commit CI and artifact-identity checks preserved. (GitHub-enforced)
  4. The CISHIP jobs join the existing required aggregate gate and consistency checks together; a missing or skipped mandatory job cannot let the gate pass, and the artifact published afterward is the same tested/audited image, never rebuilt. (GitHub-enforced)
**Plans**: 9 plans

- [x] 82-01-PLAN.md — release tag/package/image identity rules in release-policy.cjs (TDD)
- [x] 82-02-PLAN.md — CI harness: stub *arr service and reason-coded HTTP checks (TDD)
- [x] 82-03-PLAN.md — release.yml identity gate before publication, CI rehearsal script, wiring tests
- [x] 82-04-PLAN.md — shipped-image startup smoke driver with isolated config and missing-asset negative
- [x] 82-05-PLAN.md — Playwright dev deps, browser setup/login/logout flows, artifact secret scan
- [x] 82-06-PLAN.md — connection-pill polling regression test and local sensitivity check
- [x] 82-07-PLAN.md — image-smoke and browser-e2e CI jobs joined to CI ready and REQUIRED_JOBS
- [x] 82-08-PLAN.md — reproduction recipes, pre-push deep-review decision, first real PR run with reconciled commit identities, time-budget measurement
- [x] 82-09-PLAN.md — browser sensitivity on the audited image (local) and gate-enforcement demonstrations on draft PRs after owner go-ahead

### Phase 83: Paired BM + Codex Review & Risk-Based Depth

**Goal**: Every BM code review is paired with an independent, exact-commit Codex pass, preceded by a recorded, owner-approved BM baseline and update, with BM explicitly recommending review depth and vibe-check at high-risk checkpoints.
**Depends on**: Phase 82 (sequenced immediately after per owner instruction; no technical coupling)
**Requirements**: REVIEW-01, REVIEW-02, REVIEW-03, REVIEW-04, REVIEW-05, REVIEW-06, REVIEW-07, REVIEW-08, RISK-01, RISK-02
**Success Criteria** (what must be TRUE):
  1. (Gate) Before any BM update, a baseline is recorded (current configuration, plugin and runtime versions) and the proposed target version's native review/fixer behavior is assessed and documented; the owner explicitly approves an exact target version and a bounded settings list (expected: `workflow.code_review` on at `standard` depth) — passing case: the update proceeds only after that recorded approval, `/bm:version` confirms the loaded version, and only the approved settings changed; broken case: an attempted update or settings change without a recorded owner approval does not happen. (Instruction-enforced)
  2. Every BM code review path used in practice — phase execution, quick task, explicit review command, and review after fixes — is followed by an independent Codex adversarial pass on the same checkpoint commit, demonstrated once per path; if BM cannot invoke Codex directly it explicitly requests the exact-SHA review and tracks it pending, demonstrated with a deliberate case where the report is missing, stale, or on the wrong commit and is reported as incomplete rather than clean. (Instruction-enforced)
  3. Each Codex report records the inspected full head and base SHAs, coverage, exclusions, commands actually run, and findings with source/run-qualified IDs, severity, location, trigger, path, consequence, evidence, and suggested fix, distinguishing reproduced defects from hypotheses; finding dispositions survive bot thread resolution. (Instruction-enforced)
  4. Each review records requested versus actual depth and the instruction/configuration file responsible; a BM effective-depth reduction (e.g. deep → standard above 50 files) is reported rather than silently labelled deep. (Instruction-enforced)
  5. Checkpoint evidence is bound to one pushed, frozen head: Greptile reviews the same head as Codex, and after any fix the affected tests, finding dispositions, and every applicable review are refreshed for the new head with the original findings preserved for comparison — evidence from an earlier head never counts for a later one. (Instruction-enforced)
  6. At a high-risk checkpoint, BM's report records scope (full head/base SHAs, affected behavior, full-PR vs. follow-up), concrete risk rationale, recommended depth and specialist focus, required evidence, and an explicit vibe-check recommendation with the owner's recorded decision — demonstrated on a real high-risk checkpoint, without ever substituting vibe-check for Codex or Greptile, waiving findings, or reducing mandatory coverage. (Instruction-enforced)
  7. A written review-classification policy replaces blanket "every PR" wording in `CLAUDE.md` and the BM/repository instructions. Ordinary docs/planning-only changes get a focused consistency review, without routine Greptile, Codex code review or vibe-check. Classification is by content, not file extension: agent instructions, executable workflows, hooks, permissions, acceptance/release policy and operational procedures need a risk assessment and the applicable technical review, and a mixed PR follows its most consequential change. Each PR records its classification and rationale against the exact head. Codex stays paired with every BM code-review run, but ordinary planning edits don't force a code-review run. Demonstrated on Phase 83's own sensitive-docs/mixed PR (owner decision 2026-10-22, D-14: no docs-only PRs are opened); exact-commit owner acceptance is unchanged. (Instruction-enforced; GitHub-side handling is Phase 85's ACCEPT-03)
**Plans**: 10 plans

- [x] 83-01-PLAN.md — REVIEW-01 baseline, BM v5.0.3 assessment from the tag's own files, owner gate on exact version and settings
- [x] 83-02-PLAN.md — Fixed Codex adversarial review contract (read-only, exact-commit) and strict output schema
- [x] 83-03-PLAN.md — TDD: Codex report checker (complete only on the expected, current head; every failure incomplete)
- [x] 83-04-PLAN.md — Content-based review classification policy; D-14 amendment of REVIEW-08 and criterion 7
- [x] 83-05-PLAN.md — Apply the owner-approved BM update and settings; confirm with /bm:version; re-verify installed behavior
- [x] 83-06-PLAN.md — Checkpoint-record procedure; CLAUDE.md and pilot-doc review instructions; guard test
- [x] 83-07-PLAN.md — Quick-task path on an owner-approved maintenance item, with paired Codex
- [x] 83-08-PLAN.md — Explicit /bm:code-review path with paired Codex; local negative demonstrations
- [x] 83-09-PLAN.md — Review after fixes: one batched revision, snapshot, fresh BM and Codex on the new head
- [x] 83-10-PLAN.md — Classify the phase PR, RISK-01/RISK-02 decision, single push, draft PR, per-head checkpoint comment

### Phase 84: Codex Plan-Checker Investigation

**Goal**: Record whether a narrowly scoped `agent.spawn` hook can route only `bm:bm-plan-checker` through model-gateway, and how a Codex-backed checker compares against manual Codex review on the original Phase 81 plans — an investigation only, with nothing activated in the repo without separate owner approval.
**Depends on**: Nothing (independent investigation, separately gated so it cannot block or bundle into the review-pairing or CI phases; requires the preserved Phase 81 phase directories)
**Requirements**: PLANCHK-01, PLANCHK-02, PLANCHK-03
**Success Criteria** (what must be TRUE):
  1. Whether the installed Claude Code runtime supports an `agent.spawn` hook that changes only `bm:bm-plan-checker`'s model through model-gateway is verified and recorded (fields, model selection, permissions, resume); a passing case records clear support, a negative case records it as unsupported/unavailable rather than assumed, and any needed runtime update is proposed separately, never applied silently. (Instruction-enforced)
  2. If supported, a scratch-project pilot routes only the plan checker — proven from gateway metadata, with every other agent staying on its own model — and exercises initial check, a known-defective plan, revision/recheck, and post-bounce checks; an unavailable gateway/model or incomplete output leaves the check explicitly incomplete with an error rather than silently passing, and nothing from this pilot is activated in the Triggarr repo without separate owner approval. (Instruction-enforced)
  3. The blind comparison on the original Phase 81 plans runs per the blueprint — recovered and hashed inputs, matched sessions, a withheld answer key, a separate revision round, adoption criteria set before the runs — or is explicitly recorded as unavailable if the exact originals cannot be recovered. (Instruction-enforced)
  4. At closeout, the phase record separates what was actually investigated (with its evidence and result) from work that was deferred or not run (with the reason), so a deferred or unavailable item is never reported as an investigated outcome. (Instruction-enforced)
**Plans**: 7 plans

- [x] 84-01-PLAN.md — isolation baseline, installed-runtime agent.spawn verification, scratch opt-in hook with live gateway routing proof, conditional D-02 update gate
- [x] 84-02-PLAN.md — matched-run harness, pilot exercises through BM's checker loop, fail-closed negatives and disable test
- [x] 84-03-PLAN.md — evidence-based cutoff, Phase 81 input recovery and freeze, Time Machine owner gate, ORIGINAL/PARTIAL/RECONSTRUCTED label
- [x] 84-04-PLAN.md — evaluator-only answer key, locked adoption criteria with owner acknowledgment, blind packet with contamination check
- [x] 84-05-PLAN.md — 2+2 matched blind runs, arm-blind fresh-session adjudication, locked-rule scoring, owner spot-check
- [ ] 84-06-PLAN.md — revised snapshot freeze, shared feedback, 1+1 revision runs and blind adjudication — NOT PERFORMED (comparison input invalid; owner ruling 2026-10-26)
- [x] 84-07-PLAN.md — adoption evaluation, Triggarr isolation proof, investigated-vs-deferred closeout, owner decision

### Phase 85: Follow-on CI Improvements & Acceptance Usability

**Goal**: Close the remaining CI gaps (locked dependencies, grouped updates, OS-package audit, workflow lint, coverage evidence, least-privilege publish permissions) and make acceptance usable under real PR traffic (ready-state visibility, concurrent-PR safety).
**Depends on**: Phase 82 (extends the CI baseline) and, for ACCEPT-03, Phase 83 (the review-classification policy that the GitHub checks implement); also relates to Phase 83 through CIMAINT-06 (the coverage artifact feeds the vibe-check test-sufficiency lane)
**Requirements**: CIMAINT-01, CIMAINT-02, CIMAINT-03, CIMAINT-04, CIMAINT-05, CIMAINT-06, CIMAINT-07, ACCEPT-01, ACCEPT-02, ACCEPT-03
**Success Criteria** (what must be TRUE):
  1. The Docker image installs runtime dependencies from the same locked set CI tests (`uv.lock`), with compiled frontend assets and runtime behavior unchanged; a passing build matches the lockfile and a deliberately mismatched lockfile/image fails the consistency check. (GitHub-enforced)
  2. Grouped, bounded automated update PRs exist for uv dependencies, SHA-pinned Actions, and the Docker base image with no auto-merge (manual acceptance stays), and publishing `:main`/`:dev` images no longer requires repository contents-write permission — only tagged GitHub release creation holds it — demonstrated by a successful publish under the narrower permission. (GitHub-enforced)
  3. The shipped image's OS packages are scanned under a written policy for severity, fix availability, scanner errors, and time-limited documented exceptions defined before the gate is enforced with no duplicate equivalent scanner, and workflow changes are linted with actionlint such that skipping the lint when workflows are unchanged cannot let the required gate pass when mandatory validation was omitted — a passing lint and a deliberately bad workflow failing it both demonstrated. (GitHub-enforced)
  4. The built wheel's metadata validates and it installs in a clean environment and starts via the supported interface with packaged templates/assets present (or the owner's explicit decision to drop Python distributions is recorded instead), demonstrated with a passing clean-install smoke test and a deliberately broken package failing it. (GitHub-enforced) Outcome (owner decision 2026-10-26, D-14): Python distributions dropped; releases ship the Docker image only, so the wheel smoke test is not built.
  5. The CI pytest run produces a branch-coverage `coverage.xml` bound to the exact tested full commit SHA and run (PR head distinguished from the synthetic merge commit) without a percentage gate or masked test failures, discoverable by vibe-check's test-sufficiency lane; a wrong-commit or missing report is rejected as evidence, and test-runtime overhead is recorded. (Instruction-enforced discovery; GitHub-enforced artifact generation)
  6. Before final owner approval is requested, the PR is marked ready with visible machine-checkable prerequisites (SHA binding unchanged) so avoidable repeat approvals aren't needed; and the acceptance register is shown to handle concurrent PRs without one PR's update erasing another's evidence or satisfying another PR's gate, or — until that is shown — final acceptance updates are serialized with the rule documented. (Instruction-enforced)
  7. GitHub's required checks honor Phase 83's review classification without weakening protection for code or control changes. The mechanism is designed and verified with an ordinary-docs PR, a sensitive-docs PR, a mixed docs-and-code PR, and a misclassified PR (claims ordinary docs but contains a consequential change) that still gets the full checks. Required checks are never disabled ad hoc, and exact-commit owner acceptance stays required for every PR. Until this is verified, existing protections are preserved and any review still running automatically on docs-only PRs is disclosed. (GitHub-enforced) Owner decision 2026-10-26 (D-01): no docs fast path — every PR runs every required check; verified by a permanent no-skip test over ordinary-docs, sensitive-docs, mixed and misclassified fixture diffs plus Phase 85's own mixed PR as the real GitHub run (D-02).
**Plans**: 19 plans

- [x] 85-01-PLAN.md — Record owner decisions D-01/D-14 in requirements/roadmap; written OS-scan policy before enforcement; README standalone install (owner choice)
- [x] 85-02-PLAN.md — TDD: ACCEPT-03 no-skip detector over required workflows with four classification fixtures
- [x] 85-03-PLAN.md — Codex runner: SIGTERM/SIGHUP cleanup, bounded drain, evidence-dir cleanup, getpass warning, raw-output redaction
- [x] 85-04-PLAN.md — TDD: hollow-report guard rejects null exit codes and trivial-only commands
- [x] 85-05-PLAN.md — Acceptance register keyed by PR + head, draft rejection, read-back writer, gate pin bootstrap
- [x] 85-06-PLAN.md — Grouped, bounded monthly Dependabot updates with a config contract test
- [x] 85-07-PLAN.md — TDD: OS-package scan gate with expiring owner-approved exceptions, fail-closed scanner errors
- [x] 85-08-PLAN.md — Dockerfile installs runtime deps from uv.lock (hash-checked); image/lockfile consistency checker
- [x] 85-09-PLAN.md — TDD: pytest-cov and coverage provenance writer/checker (PR head vs synthetic merge)
- [x] 85-10-PLAN.md — Release: drop Python distributions; only tag-only github-release job holds contents: write
- [x] 85-11-PLAN.md — CI wiring: branch coverage with provenance, planchk-router tests, lock consistency, no dist build
- [x] 85-12-PLAN.md — Verify Trivy/actionlint pins with checksums; local OS-scan baseline; owner decision on blocking findings
- [x] 85-13-PLAN.md — Codex runner: verified-origin --trusted, base-checker cross-grade from main; --untrusted runs nothing and records INCOMPLETE (interim until 85.1)
- [x] 85-14-PLAN.md — TDD: owner-approved fallback validator and read-only acceptance readiness check (D-12 checklist, gate's own logic; bot/fork heads need the fallback until 85.1)
- [x] 85-15-PLAN.md — Required os-scan and actionlint jobs in CI ready and REQUIRED_JOBS; all workflows lint clean
- [x] 85-16-PLAN.md — Review-machinery drift guard; PLAN files sensitive and in Codex scope (prompt v6); D-01 policy status
- [ ] 85-17-PLAN.md — Docs: owner-approved Codex fallback, keyed register and serialized updates, readiness and coverage procedures
- [ ] 85-18-PLAN.md — Prepare the on-PR negative demonstration (mismatched image, bad workflow): recipes, patch, evidence skeleton; push is a hand-off step
- [ ] 85-19-PLAN.md — Phase verification, pending GitHub evidence, backlog resolution, classification, RISK-01 and hand-off

### Phase 85.1: Isolated Codex Review for Untrusted PRs (INSERTED)

**Goal**: Deliver Phase 85 D-07's normal paired review for bot (Dependabot) and fork PRs. Codex reviews the untrusted head through an enforced isolation boundary: inert input, a grader from trusted main, and a deterministically checked disposable container. The head's code never runs with access to host secrets.
**Depends on**: Phase 85 (main's checker must know the inspection-only mode; the D-16 fallback definition covers the interim)
**Requirements**: none new; completes Phase 85 D-07 for untrusted heads (owner split decision 2026-10-27)
**Interim**: until this phase ships, bot and fork PRs get CI plus a per-PR owner-approved fallback review (D-16). Untrusted Codex runs are recorded INCOMPLETE, never clean.
**Success Criteria** (what must be TRUE):
  1. An untrusted head is reviewed by Codex without being checked out or executed. The grader comes only from fresh `origin/main`, and a fork-controlled base is rejected before any of its code runs.
  2. The isolation boundary is verified deterministically on every run (container configuration, mounts, environment, and output ingestion that can't follow a symlink or FIFO). Behavioral probes are only supplementary.
  3. A live end-to-end review of a real PR completes. Any incomplete outcome blocks and is escalated, never reported clean.
**Plans**: TBD (carry-in: `.planning/phases/85.1-isolated-codex-review-for-untrusted-prs/85.1-CARRY-IN.md`)

### Phase 86: Pilot & Reference Record

**Goal**: Prove the paired workflow on real PRs, record the owner's retirement/extension decisions, and leave reusable guidance for other repositories.
**Depends on**: Phases 82, 83 and 85 (needs the paired review workflow in place; draws pilot PRs from this milestone's own authorized work). Pilot evidence is collected from PRs after Phase 83 while later authorized work proceeds. Not Phase 84: the plan-checker investigation is separately gated and does not block the pilot.
**Requirements**: PILOT-01, PILOT-02, PILOT-03, PILOT-04
**Success Criteria** (what must be TRUE):
  1. 3-5 representative PRs run under the paired workflow, drawn from this milestone's own PRs and owner-authorized maintenance/backlog work (no invented product changes), aiming to cover a small fix, state/error-path logic, a UI or security-sensitive change, and at least one larger change; any category without suitable work is recorded as a gap, and each PR records per reviewer: confirmed consequential defects, false positives, later-found misses, revision rounds, review time, observable usage/cost, and owner effort.
  2. At least one substantial pilot PR gets a recorded side-by-side comparison of vibe-check against the paired workflow, in addition to routine vibe-check, which continues on every pilot PR until the owner retires it.
  3. The owner's decisions are recorded: whether to retire routine vibe-check, and whether BM/Codex completion stays a manual owner check or the existing acceptance gate is extended to require those reports — recording the decisions completes this, and if extension is chosen it is scheduled as its own later reviewed change (FUT-03), not required before this milestone closes.
  4. Reusable adoption guidance for other repositories is written, distinguishing instruction-enforced from GitHub-enforced requirements and listing what not to copy blindly.
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 72. Password Reset Backend & Token Lifecycle | 3/3 | Complete   | 2026-06-03 |
| 73. Password Reset UI | 1/1 | Complete   | 2026-06-03 |
| 74. Count-Only Refresh | 3/3 | Complete   | 2026-06-04 |
| 75. Drain-Timeout Config Parity & Deferred-Record Correction | 4/4 | Complete   | 2026-06-04 |
| 76. Never-Searched-First Search Queue | 3/3 | Complete    | 2026-06-04 |
| 77. Secret & Reset-Token Log Hygiene | 5/5 | Complete | 2026-10-08 (merged/deployed 2026-10-18) |
| 78. Honest Cycle Outcomes | 5/5 | Complete (UAT partial: fixture for amber/legacy) | 2026-10-09 (merged/deployed 2026-10-18) |
| 79. Tag-Scoped Searches Stay in Scope | 4/4 | Complete (79-3 automated only) | 2026-10-18 |
| 80. Cycle Robustness & Sonarr Season Dedup | 5/5 | Complete (scheduled-cycle check passed 2026-10-21: 24 consecutive 180-min cycles, 0 failed, no duplicate season dispatch) | 2026-10-18 |
| 81. Correct Sonarr Grab Attribution + v5 Compatibility | 14/14 | Complete (multi-season pack and alternate series order unverified-live under D-12) | 2026-10-21 |
| 82. CI Tests What We Ship | 9/9 | Complete | 2026-10-22 |
| 83. Paired BM + Codex Review & Risk-Based Depth | 10/10 | Complete | 2026-10-23 |
| 84. Codex Plan-Checker Investigation | 6/7 (84-06 not performed) | Complete (comparison invalid: post-review input; adoption not recommended, owner override to adopt; activation pending as quick task) | 2026-10-26 |
| 85. Follow-on CI Improvements & Acceptance Usability | 16/19 | In Progress|  |
| 85.1. Isolated Codex Review for Untrusted PRs (INSERTED) | 0/TBD | Not started | - |
| 86. Pilot & Reference Record | 0/TBD | Not started | - |

## Following milestone: Reliability

**Goal:** Keep scheduled searching and saved state correct through failed writes, ambiguous network responses, partial startup and shutdown.

- [ ] **State/config consistency (999.9):** write validated replacement settings before removing an instance from live state. Failed writes must preserve settings, jobs and clients. Recover safely from non-object state JSON (`[]`, `42`, `null`).
- [ ] **Resource lifecycle (999.13, narrowed):** close resources opened during failed startup; a client-close failure must not prevent other clients or the database from closing. Correct cursor lifetime issues locally if confirmed. No blanket I/O/offloading rewrite.
- [ ] **Search-command delivery (POST-retry semantics):** prevent blind retries from duplicating an already-accepted search after a response timeout. Distinguish confirmed acceptance from unknown delivery and retain safe read retries; no generic retry framework.

**Done when:** targeted write-failure, malformed-state, partial-startup, shutdown and response-loss regressions pass with the existing suite; an isolated built-image smoke test demonstrates restart/recovery behavior. Record residual delivery limitations explicitly rather than claiming exactly-once behavior without evidence.

**Sequence:** follows CI & Review Workflow. Check current implementation before planning each carried-forward fix. Release version and phase numbers are assigned during milestone planning; no implementation is started by this organization.

## Later milestone: Authentication Safety & Responsiveness

**Goal:** Keep authentication responsive and close demonstrated boundary defects without redesigning the authentication system.

- [ ] **Password hashing (999.4):** move synchronous bcrypt work off the shared event loop across async login/setup/password/reset and Basic-auth paths, preserving authentication and rate limiting. Verify other requests and scheduled work can progress during hashing.
- [ ] **Auth-boundary review (999.10, narrowed):** validate missing-Origin/Referer mutation handling, auth-exempt path matching, trusted-proxy/rate-limit behavior, and cookie/CSP behavior in supported deployments. Reproduce issues and establish prerequisites before choosing fixes; older proposals are not requirements.
- [ ] **Compatibility verification:** verify browser login/setup/reset/logout and existing API-key/Basic clients, plus supported reverse-proxy deployments, for the boundaries changed. No new auth modes or speculative security settings; HX-Request alone is not proof of CSRF protection.

**Done when:** demonstrated defects have focused regression tests, authentication remains compatible, bcrypt work no longer stalls unrelated async work, and relevant deployed browser checks pass. If review finds an active credential exposure or exploitable bypass, fix it promptly rather than waiting for this milestone.

**Sequence:** follows Reliability; release version and phase numbers assigned during planning.

## Later milestone: UI Redesign

**Goal:** Make every screen answer "is it working, and what's next?" at a glance. Do this by removing repeated and unexplained labels, making status and actions clearer, and making the app usable at phone width. Keep the current dark look, the htmx + Tailwind v4 stack and all existing behavior.

**Design reference:** [mockups in docs/design/ui-redesign](../docs/design/ui-redesign/README.md): a PNG and static HTML for each screen, listed by artboard name below. Editable source: the [Triggarr Redesign canvas](https://claude.ai/artifact/RWWVHSdV2TL51oU1EpwL8C) (claude.ai, private to the owner). Numbers are live values from 2026-10-21. `[N]` and `[YOUR VALUE]` mark values that weren't captured, and the "[Example title]" rows only show what the outcome tags look like.

- [ ] **Header and navigation:** Show the wordmark in full, with no version badge on top of it. Merge "v2.11.0" and "v2.11.1 available" into one update pill. Replace "Connection Stable" with "2 of 2 apps connected" and remove the duplicate connected/disconnected/pending row. Move Logout out of the page nav into a labelled icon button. Files: [base.html](../triggarr/templates/base.html), [connection_pill.html](../triggarr/templates/partials/connection_pill.html), [health_summary.html](../triggarr/templates/partials/health_summary.html). Artboard: [Dashboard](../docs/design/ui-redesign/desktop-dashboard.png). Done when: the header fits at 390 px and 1280 px with nothing overlapping, and connection status appears only once.
- [ ] **Dashboard stats and notices:** Replace the four "includes historical estimates" captions with one asterisk and one footnote. Hide Lidarr in the grab-rate breakdown when no Lidarr instance is configured. Remove the empty "Last sync" label, or give it a value. Show the attribution-correction text as a dismissible notice. Keep the Phase 81 disclosure meaning intact. Files: [stats_row.html](../triggarr/templates/partials/stats_row.html), [migration_banner.html](../triggarr/templates/partials/migration_banner.html), [dashboard.html](../triggarr/templates/dashboard.html). Done when: no label renders without a value, the disclosure is still visible until dismissed, and the existing stats tests pass.
- [ ] **Instance cards:** Show the last-run time once, in one line with the result and the next run. Show each queue as a progress bar with a plain label such as "Pass 19 · 68 of 112 eligible searched". Make "Search now" the primary button and "Refresh counts" secondary. Before relabelling, confirm in code what the second number means ("112" against a total of 729) and word the label to match. Files: [app_card.html](../triggarr/templates/partials/app_card.html), [cycle_grade.html](../triggarr/templates/partials/cycle_grade.html). Done when: the labels are confirmed against the code, and cycle grades and failure-reason expanders behave as before (see the "Card reasons label" item in [maintenance](backlog/MAINTENANCE.md)).
- [ ] **History list:** Add outcome tiles with counts that also work as filters. Give filter chips a visible selected state, add "Clear all", group rows by day, and add a date filter. Shorten "Legacy — tracking discontinued" to "Legacy" with a tooltip, and show Grabbed in green as the success tag. Files: [history.html](../triggarr/templates/history.html), [history_results.html](../triggarr/templates/partials/history_results.html), [routes.py `history_page` / `partial_history_results`](../triggarr/web/routes.py). Artboards: [History](../docs/design/ui-redesign/desktop-history.png), [History, phone](../docs/design/ui-redesign/phone-history.png). Done when: existing filter URLs and query parameters keep working, and the counts match the filtered results.
- [ ] **Consistent timestamps:** History showed 17:52 for a cycle that the log viewer showed at 13:52 (2026-10-21). That suggests History displays UTC and the log viewer local time. Confirm in [routes.py](../triggarr/web/routes.py) (timestamp formatting around lines 126 and 163), then pick one timezone for display and label it. If confirmed, this is a user-facing bug: consider moving it into [maintenance](backlog/MAINTENANCE.md) rather than waiting for this milestone. Done when: a regression test pins the display timezone, and the dashboard, History and logs agree.
- [ ] **Settings sections and one save:** Give Settings a section sidebar: General, Security, then Radarr, Sonarr and Lidarr under "Apps". Lidarr shows "Set up" when it has no instance. Show help text beside each field, and fold rarely used settings (request timeout, page size, max consecutive failures, shutdown drain timeout) under "Advanced". Replace the separate Save and "Save Settings" buttons with one save bar that appears on change (unsaved count, Discard, Save). Password change keeps its own action. Instance pages get instance tabs, a "Test connection" button that doesn't save, and Remove moved into a separate red-outlined box with a confirmation step. Files: [settings.html](../triggarr/templates/settings.html), [security_password.html](../triggarr/templates/partials/security_password.html), [security_apikey.html](../triggarr/templates/partials/security_apikey.html). Artboards: [Settings › General](../docs/design/ui-redesign/desktop-settings-general.png), [Settings › Security](../docs/design/ui-redesign/desktop-settings-security.png), [Settings › Radarr instance](../docs/design/ui-redesign/desktop-settings-radarr-instance.png). Done when: config is still validated before every write (atomic writes, TOML comments preserved), no API key appears in HTML, and an existing endpoint backs "Test connection" (or one is added under the SecretStr rules in CLAUDE.md).
- [ ] **Phone layout:** Add a slim top bar and a Dashboard / History / Settings bar at the bottom. Stats go into a 2×2 grid, instance cards stack with full-width action buttons, History rows become two-line cards with sideways-scrolling filters and "Load 50 more", and Settings shows grouped fields with the save bar fixed to the bottom. Artboards: [Dashboard, phone](../docs/design/ui-redesign/phone-dashboard.png), [History, phone](../docs/design/ui-redesign/phone-history.png), [Settings, phone](../docs/design/ui-redesign/phone-settings-general.png). Done when: no screen scrolls sideways at 390 px, and every touch target is at least 44 px.
- [ ] **Login page polish:** Use a darker green for the button and focus ring so the white text reads more easily. Use a real wordmark instead of small green text. Raise the contrast of "Forgot password?". File: [login.html](../triggarr/templates/login.html) (plus [setup.html](../triggarr/templates/setup.html) and [reset.html](../triggarr/templates/reset.html) for consistency). Done when: login, setup and reset still pass their existing tests and browser checks.
- [ ] **Accessibility and screenshots:** Body text and the small grey labels reach a 4.5:1 contrast ratio. Controls are real buttons and links with visible focus, and icon-only buttons have labels. Update [docs/screenshots](../docs/screenshots/) and the README images, and close the README-screenshot task in [TODO.md](../TODO.md). Done when: a contrast check of the new palette is recorded and the screenshots match the shipped UI.

**Done when:** every item above is complete with its own check. The full suite and ruff pass. A browser walkthrough at 1280 px and 390 px is recorded against the design canvas, and any intentional differences from the mockups are written down. Behavior, config format and API responses are unchanged, except for the timestamp fix if item 5 confirms it.

**Sequence:** follows Authentication Safety & Responsiveness unless the owner reorders it. Release version and phase numbers are assigned during milestone planning. This entry starts no implementation and doesn't change v2.12 scope.

## Backlog

### Phase 999.14: Deferred: Migrate the Sonarr client to the v5 API before v3 is retired (BACKLOG)

**Goal:** Keep Sonarr support working when Sonarr removes its `/api/v3` routes. Triggarr calls `/api/v3` with API-key auth today; Sonarr v5 still serves v3, and Phase 81 deliberately kept those routes (no blanket v5 migration in v2.12).
**Scope when promoted:** track Sonarr's v3 deprecation/removal timeline; migrate the existing flows (system status, tags, missing/cutoff pagination, series counts, SeasonSearch, grab-history tracking with episode identity — v5 uses `includeSubresources` instead of `includeSeries`/`includeEpisode`), select routes from the detected version, keep v4 support while needed, and re-run the live v4/v5 matrix. Background: Phase 81 research (v5 OpenAPI differences).
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /bm:review-backlog when ready)

## Planning boundaries and maintenance

Keep the existing single-process architecture, SQLite and the current product scope. Finish v2.12 and its outstanding verification before starting these milestones. Routine maintenance and change-time safeguards live in [maintenance](backlog/MAINTENANCE.md), including the separately approved-after-v2.12 workflow discussion.

[Earlier backlog and closed decisions](backlog/archive/2026-10-18/README.md) are preserved outside this active work list.
