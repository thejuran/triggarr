---
phase: 82-ci-tests-what-we-ship
plan: "01"
subsystem: ci-release-safety
tags: [release-policy, node-test, github-actions, release-identity, cjs]

# Dependency graph
requires: []
provides:
  - "parseReleaseTag(ref) -> X.Y.Z, fail-closed on any non-stable D-21 tag grammar"
  - "parseProjectVersion(pyprojectText) -> the [project] table's version, fail-closed on 0 or 2+ matches"
  - "validateReleaseIdentity({ref, packageVersion, imageVersion}) -> X.Y.Z when tag/package/image agree, fail-closed otherwise with all three values named"
  - "releaseIdentityGate({github, context, core, sha, imageVersion}) -> reads pyproject.toml at sha via the GitHub contents API and validates identity"
affects: ["82-03 (wires releaseIdentityGate into release.yml preflight)", "82-07 (CI rehearsal of the same entry points)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fail-closed pure functions: destructured single-object args, guard clauses throwing new Error('Release rejected: <reason> (tag: .., package: .., image: ..)'), plain return value on success — mirrors the existing validateEvidence style in the same file"
    - "describeVersions() helper renders undefined as 'not inspected' and '' as 'missing' in every rejection message (D-23)"

key-files:
  created: []
  modified:
    - ".github/scripts/release-policy.cjs"
    - ".github/scripts/release-policy.test.cjs"

key-decisions:
  - "Kept REQUIRED_JOBS, validateEvidence and preflight byte-identical; this plan only adds four new exports (Plan 07 owns REQUIRED_JOBS)"
  - "releaseIdentityGate reads pyproject.toml via github.rest.repos.getContent at the exact release sha (GitHub contents API), never via a filesystem read or a widened sparse-checkout — keeps release.yml's existing tag-tampering boundary intact"
  - "module.exports kept as a single-line statement (matching the file's existing convention) so the full export list stays grep-visible on one line"

requirements-completed: [CISHIP-03]

# Metrics
duration: ~15min
completed: 2026-10-21
---

# Phase 82 Plan 01: Release Identity Rules Summary

**Four fail-closed exports in `release-policy.cjs` (parseReleaseTag, parseProjectVersion, validateReleaseIdentity, releaseIdentityGate) enforcing CISHIP-03's tag/package/image version agreement, written test-first against the real functions.**

> **Release-safeguard change:** This plan extends `.github/scripts/release-policy.cjs`, the file `release.yml`'s preflight job loads from `main` (never from a tag) to authorize every publication. Per `CLAUDE.md`'s Deep Code Review Convention, this change should be included in the `/deep-review` scope before this phase's PR is pushed.

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-10-21
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `parseReleaseTag` implements the D-21 stable `vX.Y.Z` grammar as a single anchored regex (no semver library), rejecting malformed, pre-release, build-metadata, leading-zero and case-variant tags with a message naming the raw ref and reporting package/image as "not inspected"
- `parseProjectVersion` scans only the `[project]` table of a `pyproject.toml` text for exactly one double-quoted `version = "..."` line, correctly ignoring version-looking lines in later tables (e.g. `[project.optional-dependencies]`)
- `validateReleaseIdentity` is the single point that compares tag, package and image versions, failing closed on any missing/empty value or disagreement and always naming all three values in the rejection (D-17, D-23)
- `releaseIdentityGate` reads `pyproject.toml` at the release commit through `github.rest.repos.getContent` (not the filesystem, not a widened sparse-checkout), decodes it, and runs the identity check, calling `core.info` only on success
- 39 new `node:test` cases added, covering every positive/negative case in the plan's behavior block; all 28 pre-existing `release-policy.test.cjs` tests remain untouched and passing
- Full `.github/scripts/*.test.cjs` suite: 102/102 passing after the GREEN commit

## Task Commits

1. **Task 1 (RED): Write failing positive/negative tests for the identity functions** - `b1785df` (test)
2. **Task 2 (GREEN): Implement the four exports in release-policy.cjs** - `559291b` (feat)

**Plan metadata:** (this commit, pending) - `docs(82-01): complete release identity plan`

## Files Created/Modified
- `.github/scripts/release-policy.cjs` - Adds `RELEASE_TAG_RE`, `describeVersions`, `parseReleaseTag`, `parseProjectVersion`, `validateReleaseIdentity`, `releaseIdentityGate`; extends `module.exports`. `REQUIRED_JOBS`, `validateEvidence` and `preflight` are byte-identical to before.
- `.github/scripts/release-policy.test.cjs` - Adds 39 `node:test` cases for the four new exports (positive tag/version tables, malformed-tag table, `parseProjectVersion` table including a real-file read against an independently-derived expected value, `validateReleaseIdentity` mismatch/missing cases, and a `releaseIdentityGate` fixture covering success, invalid sha, API failure, bad content shape and image mismatch).

## Decisions Made
- Followed the plan's exact interface names (`parseReleaseTag`, `parseProjectVersion`, `validateReleaseIdentity`, `releaseIdentityGate`) rather than the earlier `validateTagFormat`/`validateVersionIdentity` names sketched in `82-PATTERNS.md`, since `82-01-PLAN.md`'s `<interfaces>` block is the authoritative, more recent contract consumed by Plans 03/07.
- Left `module.exports` as a single-line statement (not reformatted to one-name-per-line) specifically so the plan's acceptance-criteria grep (`grep -n "module.exports" ...` showing all seven names) stays satisfied; this also matches the file's pre-existing style.
- For the real-`pyproject.toml` test case, derived the expected version independently via a small standalone regex scoped to the `[project]` table (`^\[project\][\s\S]*?^version = "([^"]+)"`, multiline) rather than re-deriving the implementation's line-scanning state machine, satisfying D-04's "independent of the implementation" requirement while still only reading the `[project]` table.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `module.exports` reformatted back to single-line to satisfy the acceptance-criteria grep**
- **Found during:** Task 2
- **Issue:** Initially wrote `module.exports` as a multi-line object literal (one name per line) for readability. The plan's acceptance criteria run `grep -n "module.exports" .github/scripts/release-policy.cjs` and expect that single grep hit to show all seven exported names, which only holds if the statement is on one line.
- **Fix:** Reverted to a single-line `module.exports = {REQUIRED_JOBS, validateEvidence, preflight, parseReleaseTag, parseProjectVersion, validateReleaseIdentity, releaseIdentityGate};`, matching the original file's convention.
- **Files modified:** `.github/scripts/release-policy.cjs`
- **Verification:** `grep -n "module.exports" .github/scripts/release-policy.cjs` now shows the full list on line 110; full test suite still green (102/102).
- **Committed in:** `559291b` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking/acceptance-criteria)
**Impact on plan:** Cosmetic only — no behavior change. No scope creep.

## Assumption Drift (advisory)

None material. `82-RESEARCH.md`'s "Don't Hand-Roll" guidance (reuse `test_version.py`, don't re-derive the package version inside `release.yml`) initially read as if `releaseIdentityGate` reading `pyproject.toml` at all might be an anti-pattern, but `82-01-PLAN.md`'s `<interfaces>` and D-31(a) in `82-CONTEXT.md` explicitly name `releaseIdentityGate` as one of the two exact entry points the CI rehearsal and `release.yml` must call, reading `pyproject.toml` via the GitHub contents API (not a filesystem read, not a widened `sparse-checkout`). The two documents describe the same constraint from different angles (don't re-derive via file I/O in the workflow's checkout) rather than conflicting; no behavior changed as a result, so this is recorded as advisory only.

## Issues Encountered
- `node --test` on this environment's Node (v25.9.0) defaults to a "spec"-style reporter that prints `ℹ fail N` rather than the `# fail N` TAP line the plan's `<verify>` command greps for. Confirmed the RED/GREEN state by also running `node --test --test-reporter=tap` (which does emit `# fail 39` then `# fail 0`) and by checking the plain exit code (`1` then `0`), so the intended check passed under both reporters — this is a Node-version/default-reporter difference, not a test failure.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - both new functions and their tests are fully wired; no placeholder data or empty stubs introduced.

## Threat Flags

None beyond what the plan's own `<threat_model>` already registers (T-82-01 through T-82-06). This plan adds no new network endpoints, auth paths or schema changes — `releaseIdentityGate`'s one new GitHub API call (`repos.getContent` against `pyproject.toml` at a specific commit SHA) is explicitly covered by the plan's trust-boundary table ("GitHub contents API -> release policy").

## Next Phase Readiness
- `parseReleaseTag`, `parseProjectVersion`, `validateReleaseIdentity` and `releaseIdentityGate` are ready for Plan 03 to wire into `release.yml`'s preflight path (before `docker/login-action`) and for Plan 07's CI rehearsal to call directly.
- No blockers. `REQUIRED_JOBS` is untouched, leaving Plan 07 free to extend it with `image-smoke`/`browser-e2e` without conflict.

---
*Phase: 82-ci-tests-what-we-ship*
*Completed: 2026-10-21*

## Self-Check: PASSED

- FOUND: `.github/scripts/release-policy.cjs`
- FOUND: `.github/scripts/release-policy.test.cjs`
- FOUND: `.planning/phases/82-ci-tests-what-we-ship/82-01-SUMMARY.md`
- FOUND: commit `b1785df` (test(82-01): add failing tests for release identity rules)
- FOUND: commit `559291b` (feat(82-01): add release tag/package/image identity rules)
