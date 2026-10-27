---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "01"
subsystem: ci
tags: [ci, docker, release, trivy, security-policy, documentation, acceptance]

# Dependency graph
requires:
  - phase: 83-paired-bm-codex-review-risk-based-depth
    provides: content-based review classification policy (REVIEW-07/08) that D-01/ACCEPT-03 implements at the GitHub-check level
provides:
  - Dated, named owner decisions D-01 (ACCEPT-03: no docs fast path, every required check runs on every PR) and D-14 (CIMAINT-05: Python distributions dropped, Docker image only) recorded in REQUIREMENTS.md and ROADMAP.md, following the Phase 83 D-14 amendment pattern
  - Written OS-package scan policy (docs/os-scan-policy.md) covering scope, blocking/reporting rules (D-08/D-09), fail-closed scanner errors (D-12), the owner-approved time-limited exceptions file (D-10), gate placement (D-11), and database/pinning rules — committed before any os-scan job exists in ci.yml
  - SECURITY.md cross-link to the new OS-scan policy
  - README's "Standalone (pip)" section rewritten to install from a tagged source checkout instead of a release `.whl`, per the owner's live decision (option-source)
affects: [85-07 (OS-scan gate implementation reads this policy), 85-10 (drops wheel/sdist release assets per D-14), 85-15 (enforces the os-scan job required by this policy), 85-16 (review-machinery drift guard references the D-01 policy status line)]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Phase 83 D-14 amendment pattern: append a dated, named owner-decision sentence to the original requirement/criterion text rather than rewriting or deleting it, and never tick a box the decision doesn't fully satisfy"]

key-files:
  created: [docs/os-scan-policy.md]
  modified: [.planning/REQUIREMENTS.md, .planning/ROADMAP.md, SECURITY.md, README.md]

key-decisions:
  - "Owner decision 2026-10-26 (Phase 85 D-01, ACCEPT-03): no docs fast path — every PR runs every required check whatever its classification; verified by a permanent no-skip test over four fixture cases plus Phase 85's own mixed PR as the real GitHub run."
  - "Owner decision 2026-10-26 (Phase 85 D-14, CIMAINT-05): Python distributions are dropped; releases ship the Docker image only; no clean-install wheel smoke test is built; existing releases' assets stay untouched."
  - "Owner decision recorded 2026-10-27 (answered live via AskUserQuestion) for Task 3: \"Install from source tag (Recommended)\" = option-source. README's standalone-install path becomes `pip install \"git+https://github.com/thejuran/triggarr@vX.Y.Z\"` with no Tailwind-build caveat needed, because `triggarr/static/css/output.css` is already a tracked file."

patterns-established:
  - "D-01/D-14 amendment pattern: append the owner's dated decision sentence to the existing requirement/criterion text; never tick the box or change traceability status until the decision is actually implemented and verified."

requirements-completed: []

# Metrics
duration: ~5min active execution, split across a checkpoint pause awaiting the owner's Task 3 decision
completed: 2026-10-27
---

# Phase 85 Plan 01: Owner Decisions, OS-Scan Policy, and README Install Path Summary

**Records D-01/D-14 as dated owner decisions in REQUIREMENTS/ROADMAP, commits the written OS-package scan policy before any gate enforces it, and switches README's standalone install from a soon-to-be-removed release wheel to a source-tag `pip install`.**

## Performance

- **Duration:** ~5 min of active execution (3 task commits, ~4 minutes apart), with a checkpoint pause between Task 2 and Task 3 while the owner's README-install decision was pending
- **Started:** 2026-10-27T12:39:00Z (approx., per worktree base commit `57e7e34`)
- **Completed:** 2026-10-27T12:46:43Z
- **Tasks:** 3 (all complete)
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments

- `.planning/REQUIREMENTS.md` and `.planning/ROADMAP.md` now carry the owner's D-01 (ACCEPT-03) and D-14 (CIMAINT-05) decisions, dated and ID'd, with no boxes ticked and no traceability status changed
- `docs/os-scan-policy.md` is written and committed, covering the full D-08..D-12 rule set, before any `os-scan` job exists in `.github/workflows/ci.yml`
- `SECURITY.md` cross-links the new policy from a short "Build Pipeline" section
- README's "Standalone (pip)" section no longer tells users to download a `.whl` that will stop existing after the next release; it now documents a tagged source-checkout install

## Task Commits

Each task was committed atomically:

1. **Task 1: Amend ACCEPT-03 / CIMAINT-05 and ROADMAP criteria 4 and 7 (D-01, D-14)** - `4b8643a` (docs)
2. **Task 2: Write docs/os-scan-policy.md and link it from SECURITY.md (D-08..D-12, before enforcement)** - `a55f690` (docs)
3. **Task 3: Owner decision — README standalone install (D-14)** - `4e2a96a` (docs)

**Plan metadata:** this SUMMARY's own commit (recorded separately, see below)

## Files Created/Modified

- `docs/os-scan-policy.md` - new written OS-package scan policy (scope, blocking rules, exceptions, fail-closed errors, gate placement, database/pinning)
- `.planning/REQUIREMENTS.md` - ACCEPT-03, CIMAINT-05, and the standing docs-fast-path rule each carry the dated D-01/D-14 owner decision; footer updated; nothing ticked
- `.planning/ROADMAP.md` - Phase 85 success criteria 4 and 7 each carry the same dated decisions; Phase 85 stays unticked
- `SECURITY.md` - new "Build Pipeline" section linking to `docs/os-scan-policy.md`
- `README.md` - "### Standalone (pip)" section rewritten to a tagged source-checkout `pip install` command, with a sentence noting the Docker-only release change

## Decisions Made

- **D-01 (ACCEPT-03):** no docs fast path — every PR runs every required check regardless of classification. Recorded verbatim with the 2026-10-26 date and decision ID in both REQUIREMENTS.md and ROADMAP.md.
- **D-14 (CIMAINT-05):** Python distributions dropped; Docker image is the only release deliverable going forward. Recorded verbatim with the 2026-10-26 date and decision ID.
- **Task 3 README decision (owner, 2026-10-27, answered live via AskUserQuestion):** "Install from source tag (Recommended)" = **option-source**. Applied to README.md's "### Standalone (pip)" section: `pip install "git+https://github.com/thejuran/triggarr@vX.Y.Z"`. Checked `git ls-files triggarr/static/css/output.css` before writing the section — the file is already tracked, so the section does not need a Tailwind-build caveat; a source install from a tag already includes the compiled CSS.

## Deviations from Plan

None - plan executed exactly as written. The owner's Task 3 decision (option-source) matched the plan's own recommendation, and the `output.css`-tracked check came back positive, so no Tailwind-build-step caveat was needed in the README text.

## Issues Encountered

None. All automated verification commands specified in the plan passed on first run:
- Task 1: `grep -c "Phase 85 D-01"` (3), `grep -c "Phase 85 D-14"` (1), `grep -c "owner decision 2026-10-26, D-14"` in ROADMAP.md (1), both `- [ ] **ACCEPT-03**`/`- [ ] **CIMAINT-05**` lines still present (1 each)
- Task 2: `docs/os-scan-policy.md` exists; `"30 days"` (2), `"os-scan-exceptions.json"` (2), `"fail closed"` (2), `SECURITY.md` link (1), `"ignore-unfixed"` (1); all required strings (CRITICAL, HIGH, FixedVersion, approved_by, expires, fail, pip-audit, CVE-2026-33634, `--pkg-types os`, `.github/os-scan-exceptions.json`, CI ready, REQUIRED_JOBS) confirmed present; `aquasecurity/trivy-action`/`setup-trivy` appear only in the "never" sentence; no `os-scan` job exists yet in `ci.yml` (`grep -c "^  os-scan:"` returns 0)
- Task 3: `grep -c "Docker image only"` README.md (1); `grep -c 'endswith(".whl")'` (0) and `grep -c "py3-none-any.whl"` (0)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The OS-scan policy is in place for Plan 85-07 (TDD gate implementation) and Plan 85-15 (CI wiring/enforcement) to build against.
- The D-14 decision is recorded for Plan 85-10 (drop Python distributions, split release permissions) to implement.
- The D-01 decision is recorded for Plan 85-02 (ACCEPT-03 no-skip detector TDD) to verify against.
- No blockers. `.planning/REQUIREMENTS.md` and `.planning/ROADMAP.md` traceability/ticks remain exactly as before except for the appended decision text — plan-progress tracking (STATE.md, phase/plan tick counts) was deliberately left untouched for the orchestrator to update after the wave completes.

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Completed: 2026-10-27*

## Self-Check: PASSED

- FOUND: docs/os-scan-policy.md
- FOUND: .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-01-SUMMARY.md
- FOUND: commit 4b8643a
- FOUND: commit a55f690
- FOUND: commit 4e2a96a
