---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "14"
subsystem: ci
tags: [github-actions, acceptance, codex-fallback, review-acceptance, node-test]

requires:
  - phase: 85-follow-on-ci-improvements-acceptance-usability (plan 05)
    provides: "assess({prNumber, head, currentHead, draft, checks, comments, dispositions, blockers}) keyed by registerKey(prNumber, head), and the schema-2 register shape readiness's gate dry run reuses"
provides:
  - "codex-fallback.cjs: the single owner-approved-fallback schema (schema 1) and validateFallback(), used by both the readiness check and (per the plan's objective) the docs updated in Plan 85-17"
  - "acceptance-readiness.cjs: readiness() pure function assembling PR open/ready/Head SHA/CI ready/CodeQL/Greptile/gate-dry-run/Codex into one ready/not-ready checklist, renderChecklist(), codexStatusFor()/headTrustFor() implementing the Codex completeness and head-trust contracts, and a read-only runCli"
affects: [85-17, 85-19]

tech-stack:
  added: []
  patterns:
    - "Stdlib-only Node CJS gate/validator scripts (no YAML, no new dependency), matching ci-job-consistency.cjs's existing style"
    - "A single owner-approved-fallback schema and validator, called (never re-implemented) by every consumer that needs to know whether a fallback satisfies an incomplete Codex result"
    - "A pure readiness() function fed already-gathered data, with a thin runCli() doing all gh/fs I/O via argument-array exec and an injectable readFile, so every behavior is unit-testable without a network call"

key-files:
  created:
    - .github/scripts/codex-fallback.cjs
    - .github/scripts/codex-fallback.test.cjs
    - .github/scripts/acceptance-readiness.cjs
    - .github/scripts/acceptance-readiness.test.cjs

key-decisions:
  - "validateFallback() accumulates every applicable problem into reasons[] rather than short-circuiting on the first one, except for the codexStatus.complete===true case (and its untrusted-head variant), which returns its own single reason immediately since a fallback is categorically not needed when Codex actually completed"
  - "codex_out's head-prefix match checks the path's final segment (its basename), not the full OUT path, since the full path starts with '.planning/phases/<dir>/codex/' before the head12 prefix appears"
  - "codexStatusFor()'s 'grader changed in this diff' case (status complete, audited inputs changed, base-status incomplete) returns directly, bypassing the fallback path entirely -- a self-grading defense signal is never satisfied by an ordinary owner-approved fallback"
  - "headTrustFor({isCrossRepository, author}) is the exported contract (matching Task 3's interface text); readiness() adapts its own flatter {prAuthor, prAuthorIsBot} input into that shape internally, resolving a wording mismatch between Task 2's destructure and Task 3's function signature in the plan text"
  - "The 'Greptile (optional)' checklist item never blocks readiness on its own -- it only reports what it finds; the actual Greptile-success-if-present rule lives in assess() via the 'Review acceptance gate (dry run)' item, so there is exactly one place that rule is enforced"

patterns-established:
  - "Owner-approved fallback schema and validator (D-16): any future consumer of 'did the owner approve a fallback for this head' calls validateFallback() with the same codexStatus shape, never reimplementing the rule"

requirements-completed: [ACCEPT-01]

duration: 9min
completed: 2026-10-27
---

# Phase 85 Plan 14: Acceptance Readiness Check and Codex Fallback Validator Summary

**A read-only `acceptance-readiness.cjs` checklist (PR state, CI ready, CodeQL, Greptile, the acceptance gate as a dry run, and Codex) built on the gate's own `assess()`, plus `codex-fallback.cjs`'s single owner-approved-fallback schema and validator that both the readiness check and the untrusted-head interim rule (D-07 amendment) depend on.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-10-27T09:19:31-04:00 (first commit)
- **Completed:** 2026-10-27T09:28:10-04:00 (last commit)
- **Tasks:** 3
- **Files modified:** 4 (all new files)

## Accomplishments

- `codex-fallback.cjs` defines the one owner-approved fallback record shape (schema 1) and `validateFallback(record, context)`, covering every rejection case the plan specifies: missing/unknown fields at every level, a non-independent reviewer (BM/Claude/the PR author/etc.), a head or base mismatch, a partial diff scope, an undisposed finding, `wait`/`retry-later`, a verbatim that doesn't name the head, an invalid `decided_at`, Codex actually being complete, a trusted head's attempt-1-only or untrusted-mode-refusal case, and an untrusted head's missing or claimed-complete record. `runCli` reads the Codex status/meta files for a given `--codex-out` prefix and validates a `--file` fallback record against them, rejecting a malformed `--pr` before any file read.
- `acceptance-readiness.cjs` assembles `readiness()`'s eight checklist items (`PR open`, `PR ready for review`, `Head SHA`, `CI ready`, `CodeQL`, `Greptile (optional)`, `Review acceptance gate (dry run)`, `Codex`) into one `{ready, items}` result, with `renderChecklist()` printing the D-12-style checklist (repository, PR, full head/base SHAs, a `BM: <fill from the checkpoint record>` line, each item's ok/BLOCKED status and detail, and a final `Ready to request approval` / `NOT ready: ...` line).
- `codexStatusFor()` implements the shared Codex completeness contract (review_mode `trusted-local-tests` + head-side `complete` + base-grader-ok-if-a-grader-input-changed) for a trusted head, never reports complete for an untrusted head, and for any incomplete case calls `validateFallback()` (never re-implementing the rule) to decide whether a given fallback satisfies the item.
- `headTrustFor()` derives trust solely from GitHub-reported facts (`isCrossRepository`, bot author, `TRUSTED_AUTHORS = ['thejuran']`), matching the interim rule (D-07 amendment) that a bot or fork head is never trusted regardless of what any Codex record claims.
- `runCli` gathers PR state, check runs, and PR comments via argument-array `gh` calls only (`gh pr view`, `gh api .../check-runs --paginate --slurp`, `gh api .../comments --paginate --slurp`, two `gh variable get` reads), flattens multi-page `--paginate --slurp` output with `flattenPages()` (fail-closed on a non-array page or a page missing its expected shape), and is strictly read-only — no `variable set`, no `pending_deployments`, no `--method POST` anywhere in the file (grep-verified, 0 matches).

## Task Commits

1. **Task 1: Shared fallback record schema and validator (RED then GREEN)**
   - `2b8f7c7` test(85-14): add failing fallback record validator tests
   - `282ada4` feat(85-14): define the owner-approved Codex fallback record and validator (D-16)
2. **Task 2: RED — readiness cases**
   - `a739d81` test(85-14): add failing acceptance readiness tests
3. **Task 3: GREEN — implement readiness, checklist rendering and the read-only CLI**
   - `171913d` feat(85-14): add read-only acceptance readiness check (ACCEPT-01, D-20)

_Note: both TDD tasks (Task 1, and the Task 2/Task 3 pair) ran RED (`test(...)`) then GREEN (`feat(...)`); no REFACTOR commit was needed for either — all tests passed on the first implementation run._

## Files Created/Modified

- `.github/scripts/codex-fallback.cjs` - `FALLBACK_SCHEMA_VERSION`, `FALLBACK_FIELDS`, `REVIEWER_KINDS`, `DISALLOWED_REVIEWERS`, `OWNER_DECISIONS`, `validateFallback()`, `runCli()` (`validate` subcommand)
- `.github/scripts/codex-fallback.test.cjs` - 33 tests covering every behavior bullet from the plan, including both the trusted- and untrusted-head fallback paths and `runCli`'s pre-file-read `--pr` rejection
- `.github/scripts/acceptance-readiness.cjs` - `readiness()`, `renderChecklist()`, `codexStatusFor()`, `headTrustFor()`, `runCli()`, plus the internal `flattenPages()`/item helpers
- `.github/scripts/acceptance-readiness.test.cjs` - 40 tests covering every checklist item, the Codex completeness/fallback/untrusted-head matrix, direct `headTrustFor`/`codexStatusFor` checks, and `runCli`'s multi-page GitHub response handling, fail-closed parsing, and output content

## Decisions Made

See `key-decisions` in the frontmatter above. In summary: `validateFallback()` accumulates problems rather than stopping at the first one (except the two `codexStatus.complete === true` short-circuits, which are categorically exclusive outcomes); the codex_out head-prefix check operates on the path's basename, not the full `.planning/phases/.../codex/` prefix; the "grader changed in this diff" case bypasses the fallback path entirely rather than letting an ordinary fallback paper over a self-grading risk; and `headTrustFor`'s exported `{isCrossRepository, author}` signature is adapted internally from `readiness()`'s flatter `{prAuthor, prAuthorIsBot}` input to resolve a minor wording difference between the plan's Task 2 and Task 3 text.

## Deviations from Plan

None - plan executed exactly as written. All 104 tests (33 + 40 + 31 from the unchanged `review-acceptance.test.cjs`) passed on the first implementation run with no fix cycles needed.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. This plan adds local, read-only tooling; it introduces no new CI job and does not touch the acceptance workflow's permissions or environment.

## Next Phase Readiness

- `.github/scripts/codex-fallback.cjs`'s `validateFallback()` and `.github/scripts/acceptance-readiness.cjs`'s `readiness()`/`renderChecklist()`/`codexStatusFor()`/`headTrustFor()`/`runCli()` are complete, tested, and committed — all five named exports from the plan's `key_links`/`artifacts` are present and the two `require('./review-acceptance.cjs')` / `require('./codex-fallback.cjs')` lines each appear exactly once (grep-verified).
- Plan 85-17 (docs: contract/record wording for the fallback and readiness check) can now cite this plan's concrete field names, messages, and CLI flags directly.
- Plan 85-19's final-wave hard gates (`uv run pytest tests/ -x -q`, the full `node --test .github/scripts/*.test.cjs ...` glob) were deliberately **not** run here — they are W06/W07 post-wave integration gates, not a per-plan gate, since other wave-2 plans may hold intentionally failing RED tests. The existing `ci.yml` Node step's `.github/scripts/*.test.cjs` glob already picks up both new test files with no workflow change needed.
- This plan does not itself run `tests/codex_review_run.py`'s trust/base-grader machinery (Plan 85-13, same wave); `codexStatusFor()`'s contract (`review_mode`, `attempt`, `audited_inputs_changed_in_diff`, `.base-status.json`) was implemented directly from the plan's documented interface text, not from reading 85-13's own commits, since 85-13 may not have landed its GREEN commits yet when this plan runs.

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Completed: 2026-10-27*

## Self-Check: PASSED

- All 5 key files confirmed present on disk (`.github/scripts/codex-fallback.cjs`, `.github/scripts/codex-fallback.test.cjs`, `.github/scripts/acceptance-readiness.cjs`, `.github/scripts/acceptance-readiness.test.cjs`, this SUMMARY.md).
- All 4 task commit hashes (`2b8f7c7`, `282ada4`, `a739d81`, `171913d`) confirmed present in `git log --oneline --all`.
