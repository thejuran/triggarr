---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "09"
subsystem: testing
tags: [pytest-cov, coverage, provenance, ci, node-test, cjs]

# Dependency graph
requires:
  - phase: 82-ci-tests-what-we-ship
    provides: commit-identity fields (PR head/base/tested SHA, D-34) and the evidence-record pattern this plan's provenance object follows
provides:
  - pytest-cov dev dependency (runtime export unchanged) with branch coverage verified >0
  - .gitignore entries for coverage.xml, .coverage, .coverage.*, coverage-provenance.json
  - .github/scripts/coverage-provenance.cjs: buildProvenance, buildLocalProvenance, checkEvidence, MEASURED_PATHS, runCli (write/write-local/check)
  - Local test-runtime overhead measurement (no coverage vs branch coverage, full suite)
affects: [85-11 (CI wiring of `write`), 85-17 (reviewer procedure using `check`)]

# Tech tracking
tech-stack:
  added: [pytest-cov>=7.1.0]
  patterns: ["node:crypto/fs/child_process-only CLI scripts with execFileSync argument arrays (no shell), injected io/git for unit tests", "schema-1 provenance JSON binding evidence to PR-head vs synthetic-merge commit with measured-source tree equivalence"]

key-files:
  created:
    - .github/scripts/coverage-provenance.cjs
    - .github/scripts/coverage-provenance.test.cjs
  modified:
    - pyproject.toml
    - uv.lock
    - .gitignore

key-decisions:
  - "checkEvidence's `provenance` parameter accepts either a parsed object or raw JSON text, so write/buildProvenance callers can pass objects directly while the `check` CLI path parses disk-read text through the same function -- this is what lets 'unparseable provenance' and 'schema !== 1' share one code path and one error message prefix."
  - "The measured-source tree comparison in checkEvidence runs unconditionally whenever headTrees is available, independent of which commit-association branch fired -- matches the plan's 'for every kind it compares headTrees with provenance.measured_trees path by path' instruction and keeps B08 detection orthogonal to wrong-commit detection."

patterns-established:
  - "Coverage provenance pattern: a CI/local writer records tested_sha + tested_sha_kind + measured_trees; a separate checker re-derives the reviewed head's measured_trees from the live repository and rejects any report whose measured source differs, rather than trusting the writer's self-report."

requirements-completed: [CIMAINT-06]

# Metrics
duration: 25min
completed: 2026-10-27
---

# Phase 85 Plan 09: Coverage Provenance Writer & Evidence Check Summary

**pytest-cov dev dependency plus a `coverage-provenance.cjs` writer/checker that binds `coverage.xml` to the exact tested commit, run, and measured source, rejecting synthetic-merge-as-head confusion and base-only drift (CIMAINT-06).**

## Performance

- **Duration:** ~25 min (git worktree reset + reading start to final commit)
- **Started:** 2026-10-27T08:30:00-04:00 (approx, worktree base correction)
- **Completed:** 2026-10-27T08:56:42-04:00
- **Tasks:** 2 completed (Task 2 ran RED then GREEN)
- **Files modified:** 5 (pyproject.toml, uv.lock, .gitignore, coverage-provenance.cjs, coverage-provenance.test.cjs)

## Accomplishments

- `pytest-cov>=7.1.0` added as a dev-only dependency; the `--no-dev` runtime export is byte-identical before and after (diff empty after stripping uv's progress-line noise).
- Behavior check: `uv run pytest tests/test_version.py -q --cov=triggarr --cov-branch --cov-report=xml` exits 0 and writes a Cobertura file with `branches-valid="1364"` (>0).
- `.github/scripts/coverage-provenance.cjs` built with only `node:crypto`/`node:fs`/`node:child_process` (no shell, `execFileSync` with argument arrays only): `buildProvenance` (PR vs push), `buildLocalProvenance` (exact local head), `checkEvidence` (rejects wrong-commit, synthetic-merge-as-PR-head confusion, B08 measured-source drift, unreadable head trees, missing/mismatched/branchless coverage, failed test runs, wrong CI run id), and `runCli` (`write`, `write-local`, `check`).
- 33/33 tests pass in `node --test .github/scripts/coverage-provenance.test.cjs`, run directly (not piped), including a real-git smoke test (not just injected fixtures) proving `check` accepts evidence at its own tested commit and rejects it at a different real commit.
- No percentage gate anywhere: `grep -cE "cov-fail-under|fail_under" pyproject.toml` → 0; `grep -vE '^\s*(//|\*)' coverage-provenance.cjs | grep -ciE "fail_under|threshold|line-rate *[<>]"` → 0 (comment-line exclusion only, so the header comment is free to say there is no gate).

## Task Commits

Each task was committed atomically:

1. **Task 1: Add pytest-cov and ignore generated coverage files** - `d58f3a4` (build)
2. **Task 2a: Provenance writer and evidence checker (RED)** - `e08d11e` (test)
3. **Task 2b: Provenance writer and evidence checker (GREEN)** - `babf3f5` (feat)

_TDD task: RED (`e08d11e`) then GREEN (`babf3f5`); no REFACTOR commit was needed (implementation went in clean on the first GREEN pass)._

## Files Created/Modified

- `pyproject.toml` - added `pytest-cov>=7.1.0` to the dev extras
- `uv.lock` - regenerated; pulls `coverage==7.17.0` transitively, runtime (`--no-dev`) export unchanged
- `.gitignore` - added `coverage.xml`, `.coverage`, `.coverage.*`, `coverage-provenance.json`
- `.github/scripts/coverage-provenance.cjs` - provenance writer/checker (schema 1, `MEASURED_PATHS`, `runCli` with `write`/`write-local`/`check`)
- `.github/scripts/coverage-provenance.test.cjs` - 33 tests covering every behavior bullet in the plan, including the B08 negative fixtures

## Decisions Made

- `checkEvidence`'s `provenance` argument accepts either an object or raw JSON text (parsed internally) so the same function serves in-process callers and the `check` CLI's disk-read path, and so "unparseable JSON" and "schema !== 1" can share one validation function and one error-message prefix (`Coverage evidence rejected: provenance ...`).
- The measured-source tree comparison in `checkEvidence` always runs (when `headTrees` is available) regardless of which commit-association branch fired, per the plan's instruction that it applies "for every kind" — keeps B08 detection independent of wrong-commit/merge-confusion detection rather than nesting it inside one branch.
- `cliWrite` writes the provenance file unconditionally, even when `--test-exit` is non-zero, because the CI step invoking it re-asserts the real test exit code separately (Pattern 7's "fail the job if tests failed" step, delivered in Plan 85-11) — the provenance writer's job is to record evidence, not to gate on it.

## Deviations from Plan

None - plan executed exactly as written. The only interpretive decisions were the two implementation-detail calls above (both within the plan's explicit `<action>` and `<behavior>` text), documented as Decisions Made rather than deviations since no plan requirement was added, changed, or skipped.

## Issues Encountered

- `uv export`'s progress/status lines (`Using CPython ...`, `Resolved N packages ...`) are written with ANSI color codes and mixed into the captured output when stderr is redirected into the same file as stdout, which made the first before/after diff look non-empty. Resolved by re-running the export with stdout and stderr captured separately and stripping ANSI escape codes before diffing — the actual requirements content (107 lines) is byte-identical before and after adding `pytest-cov`.
- A Bash sandbox guard inside this worktree refused several compound commands (variable assignments combined with `git`, or `grep`/`echo` combinations it couldn't statically verify as worktree-scoped) with a "too complex to verify" refusal. Each was split into separate plain commands, which the guard then allowed; no command needed `dangerouslySetInnerHTML`-style bypassing or sandbox override.

## User Setup Required

None - no external service configuration required. `pytest-cov` is a dev-only dependency; CI wiring (invoking `coverage-provenance.cjs write` from `ci.yml`) is Plan 85-11, and the reviewer procedure for running `check` before placing `coverage.xml` in a vibe-check worktree is Plan 85-17 — neither is in this plan's scope.

## Next Phase Readiness

- Plan 85-11 can now add the `test` job's `--cov=triggarr --cov-branch --cov-report=xml:coverage.xml` step and call `node .github/scripts/coverage-provenance.cjs write --coverage coverage.xml --test-exit <exit> --test-seconds <seconds> --out coverage-provenance.json`, uploading both files as a `coverage-${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}` artifact per Pattern 7.
- Plan 85-17 can document the reviewer step: download the CI artifact for the head under review, run `node .github/scripts/coverage-provenance.cjs check --provenance coverage-provenance.json --coverage coverage.xml --expected-head <PR head sha>` against the local repository, and only place `coverage.xml` in the vibe-check worktree if it exits 0.
- Local test-runtime overhead (measured in an isolated detached worktree at `main`, per W06 isolation from this wave's shared tree): full suite without coverage `2164 passed in 90.80s` (real 90.80s); with `--cov=triggarr --cov-branch` `2164 passed in 102.40s` (real 103.35s) — roughly +12.5s / +14% wall-clock overhead for branch coverage on the full suite. Both runs exited 0.
- No blockers for downstream plans.

## Self-Check: PASSED

- FOUND: `.github/scripts/coverage-provenance.cjs`
- FOUND: `.github/scripts/coverage-provenance.test.cjs`
- FOUND: `pytest-cov>=7.1.0` in `pyproject.toml` (grep -c = 1)
- FOUND commit `d58f3a4` (build: pytest-cov dev dependency)
- FOUND commit `e08d11e` (test: RED)
- FOUND commit `babf3f5` (feat: GREEN)

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Completed: 2026-10-27*
