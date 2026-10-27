---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "07"
subsystem: infra
tags: [ci, trivy, security-scan, node, stdlib-only, tdd]

# Dependency graph
requires:
  - phase: 82-ci-tests-what-we-ship
    provides: audited-image artifact convention, pinned-binary-tool pattern, fail-closed job style (pip-audit --strict)
provides:
  - "os-scan-gate.cjs: parseReport/validateExceptions/classifyFindings/renderSummary/runCli classifier enforcing D-08..D-12"
  - "os-scan-gate.test.cjs: 29 passing tests covering severity/fix classification, exception matching+expiry math, scanner fail-closed errors, renderSummary completeness, runCli exit codes"
  - "os-scan-exceptions.json: empty schema-1 exception register, ready for owner-approved entries"
affects: ["Plan 85-15 (ci.yml os-scan job wiring)", "Plan 85-12 (Trivy binary pin + local baseline)", "docs/os-scan-policy.md"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fail-closed classifier (parse -> throw on structural surprise) mirroring ci-job-consistency.cjs"
    - "Schema-versioned register with per-entry fail-closed validation (schema 1, required fields), mirroring review-acceptance.cjs's dispositions/blockers shape"
    - "Injectable IO (readFile/writeSummary/stderr) for runCli, same test-without-filesystem style as other repo CLI scripts"

key-files:
  created:
    - .github/scripts/os-scan-gate.cjs
    - .github/scripts/os-scan-gate.test.cjs
    - .github/os-scan-exceptions.json
  modified: []

key-decisions:
  - "classifyFindings takes already-validated exceptions ({valid, expired} from validateExceptions), not the raw exceptions file -- keeps the two concerns (structural/date validation vs. severity/fix classification) cleanly separated and matches the plan's described data flow through runCli"
  - "Exception-match keys on VulnerabilityID + PkgName only (not installed/fixed version), per the plan's explicit requirement; a same-id-different-package exception never excepts the finding"
  - "renderSummary always shows a dedicated 'Expired exceptions' list (plain id list, not a table) in addition to the finding reappearing in the Blocking table, so the expired-exception id itself is never dependent on table formatting to be found"

requirements-completed: [CIMAINT-03]

# Metrics
duration: ~12min
completed: 2026-10-27
---

# Phase 85 Plan 07: OS-Package Scan Gate Summary

**Stdlib-only Node classifier (os-scan-gate.cjs) that reads a full, unfiltered Trivy JSON report and enforces the written OS-scan policy: blocks only CRITICAL/HIGH findings with a fix and no valid exception, reports everything else, and fails closed on any scanner or exceptions-file error.**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-10-27T12:49:27Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 3 (all new)

## Accomplishments
- A single tested classifier (`os-scan-gate.cjs`) implements D-08 (block Critical/High with a fix), D-09 (report, never drop, unfixed/other findings), D-10 (owner-approved exceptions with ≤30-day expiry from both approval date and scan date, expired exceptions re-block), and D-12 (fail closed on unparseable JSON, wrong SchemaVersion, missing Results, no os-pkgs result, or undetected OS)
- `renderSummary` renders every bucket (blocking, excepted, expired, reported-unfixed, reported-other, ignored-non-OS) so a blocked run still shows everything found (T-85-22)
- `runCli` writes the summary before returning, so a blocked CI run still produces full evidence, then exits 1 for blocking/scanner-error/invalid-exceptions and 0 otherwise
- Empty `.github/os-scan-exceptions.json` (schema 1) committed, ready for the first owner-approved exception entry

## Task Commits

Each task was committed atomically (TDD RED -> GREEN):

1. **Task 1: RED — classification, exception and fail-closed tests** - `f5fd8b8` (test)
2. **Task 2: GREEN — implement os-scan-gate.cjs and the empty exceptions file** - `fff523f` (feat)

**Plan metadata:** (this commit, created after this summary)

## Files Created/Modified
- `.github/scripts/os-scan-gate.cjs` - parseReport/validateExceptions/classifyFindings/renderSummary/runCli; Node stdlib only (fs required lazily inside the CLI's default IO)
- `.github/scripts/os-scan-gate.test.cjs` - 29 tests: severity/fix classification, lang-pkgs exclusion, case-insensitive/unknown severity, exception id+package matching, exception expiry math (missing/too-far/future/malformed), parseReport's 5 scanner-error messages, renderSummary completeness, runCli exit codes with injectable IO
- `.github/os-scan-exceptions.json` - empty exception register, `{"schema": 1, "exceptions": []}`

## Decisions Made
- `classifyFindings` consumes `validateExceptions`'s already-split `{valid, expired}` result rather than the raw exceptions file, keeping structural/date validation (fail-closed, throws) separate from per-finding classification (never throws, always buckets)
- Comment text in `os-scan-gate.cjs` deliberately avoids the literal substring `ignore-unfixed` (even when explaining why that Trivy flag is wrong to use) because the plan's acceptance criterion greps the file for that exact string and expects a zero count

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed the literal string "ignore-unfixed" from two explanatory comments**
- **Found during:** Task 2 acceptance-criteria check (`grep -c "ignore-unfixed" .github/scripts/os-scan-gate.cjs` must return 0)
- **Issue:** My first draft of `os-scan-gate.cjs` included two header/inline comments naming the Trivy flag `--ignore-unfixed` as the thing being deliberately avoided (matching Pitfall 2 from 85-RESEARCH.md). The grep-based acceptance check doesn't distinguish code from comments, so these comments failed the check even though no code used the flag.
- **Fix:** Reworded both comments to describe the behavior ("no result-filtering flags at all", "a status-filtering Trivy flag") without using the literal substring.
- **Cost if wrong:** None functionally — this was a pure wording fix with no behavior change; re-adding the phrase would only fail the same acceptance grep again.
- **Files modified:** `.github/scripts/os-scan-gate.cjs`
- **Commit:** `fff523f` (part of Task 2 commit — found and fixed before committing)

---

**Total deviations:** 1 auto-fixed (1 bug/acceptance-criteria wording)
**Impact on plan:** Comment-only change; no behavior or test was affected. No scope creep.

## Issues Encountered

**Worktree branch setup:** At agent startup, the worktree's HEAD (`decd5f1`, a merge of PR #35 "paired-review") was not an ancestor of the expected phase base commit `57e7e34` (`ci-followon`'s current tip), and vice versa — the two branches had diverged. Per the mandatory `<worktree_branch_check>` step, `git reset --hard 57e7e34ddcde5045994ce05565b96a44a846a479` was run to correct the worktree's base before any plan work began. This is the explicitly authorized exception to the destructive-git-operations prohibition and was verified to bring HEAD to the exact expected commit before any file was touched.

## User Setup Required

None - no external service configuration required. This plan does not wire the gate into CI; that is Plan 85-15's scope (invoking `node .github/scripts/os-scan-gate.cjs --report trivy-results.json --exceptions .github/os-scan-exceptions.json` from the `os-scan` job).

## Next Phase Readiness

- `os-scan-gate.cjs`'s exported `runCli` signature (`--report <path> --exceptions <path> [--today YYYY-MM-DD] [--summary <path>] [--trivy-version <v>]`) matches the invocation documented in this plan's `key_links` and in 85-RESEARCH.md Pattern 4 — Plan 85-15 can wire it directly into `ci.yml`'s new `os-scan` job without further script changes.
- `docs/os-scan-policy.md` (Plan 85-01, if not yet committed) should use message wording consistent with what this gate actually emits (`scanner error: ...`, `exceptions file: ... missing required field`, `... no expiry`, `... more than 30 days ...`, `... approved_on is in the future`, `... invalid date ...`) — Task 2's `<read_first>` flagged this but 85-01's doc was not present in this worktree at execution time, so no cross-check against it was possible from this plan.
- No blockers for Plan 85-15 or 85-12.

## Self-Check: PASSED

- FOUND: `.github/scripts/os-scan-gate.cjs`
- FOUND: `.github/scripts/os-scan-gate.test.cjs`
- FOUND: `.github/os-scan-exceptions.json`
- FOUND: commit `f5fd8b8` (test(85-07))
- FOUND: commit `fff523f` (feat(85-07))

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Completed: 2026-10-27*
