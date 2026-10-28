---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "06"
subsystem: infra
tags: [dependabot, ci, dependency-updates, github-actions, docker, uv]

# Dependency graph
requires:
  - phase: 82-ci-tests-what-we-ship
    provides: the SHA-pinned Actions convention and existing CI baseline this plan's repo-wide SHA-pin test checks against
provides:
  - ".github/dependabot.yml with three grouped, bounded, monthly ecosystem blocks (uv, github-actions, docker)"
  - "tests/test_dependabot_config.py permanent contract test (8 tests) pinning CIMAINT-02's config shape"
  - "Live-doc recheck evidence for D-07 (uv ecosystem support, groups/cooldown semantics, cooldown restriction) recorded below"
affects: [85-13, 85-14, 85-17, 85-19]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Dependabot groups.applies-to: version-updates + update-types: [minor, patch] to split majors into their own PR with zero extra config"]

key-files:
  created:
    - .github/dependabot.yml
    - tests/test_dependabot_config.py
  modified: []

key-decisions:
  - "uv ecosystem block carries no cooldown key -- this repo has no exclude-newer in pyproject.toml, so uv's own guide's cooldown-matches-exclude-newer recommendation doesn't apply; GitHub's repo-wide 3-day default cooldown (2026-07-14) still applies to it"
  - "docker/github-actions cooldown blocks use only default-days: 5, confirmed live against GitHub's own support table (docker/github-actions: default-days supported, semver-*-days NOT supported) -- matches Pitfall 5/D-05"

patterns-established:
  - "Dependabot config contract test (tests/test_dependabot_config.py) mirrors tests/test_github_workflows.py's yaml.safe_load/REPO_ROOT convention and keeps its own copy of USES_SHA_RE rather than importing across test modules"

requirements-completed: [CIMAINT-02]

# Metrics
duration: 11min
completed: 2026-10-27
---

# Phase 85 Plan 06: Grouped Monthly Dependabot Updates Summary

**Three grouped, bounded, monthly Dependabot ecosystems (uv/github-actions/docker) with an 8-test permanent config contract and no auto-merge path.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-10-27T12:39:00Z
- **Completed:** 2026-10-27T12:49:48Z
- **Tasks:** 2
- **Files modified:** 2 (both created)

## Accomplishments
- `.github/dependabot.yml` added: `uv`, `github-actions` and `docker` ecosystems, each monthly, each with exactly one `minor`+`patch` group (so a major bump opens its own, ungrouped PR) and a bounded `open-pull-requests-limit` (5/5/2)
- `tests/test_dependabot_config.py` added as a permanent contract test: version, ecosystem set, schedule, PR limits, grouping shape, cooldown-key restriction, no-auto-merge, and repo-wide SHA-pin invariants (8 tests)
- Live Dependabot documentation rechecked against the actual GitHub/uv docs (not just RESEARCH.md) and two read-only `gh api` checks confirmed the repo's current security-update and auto-merge settings, per D-07's instruction to recheck before choosing keys

## Task Commits

Each task was committed atomically:

1. **Task 1: Recheck current Dependabot behavior, then write the config contract test (RED)** - `7fea735` (test)
2. **Task 2: Write .github/dependabot.yml (GREEN)** - `71a7bb7` (ci)

**Plan metadata:** this commit (docs: complete plan)

## Files Created/Modified
- `tests/test_dependabot_config.py` - 8 pytest tests pinning the Dependabot config contract (version=2, three ecosystems at `/`, monthly schedule, bounded `open-pull-requests-limit`, one minor+patch group per ecosystem, cooldown-key restriction for docker/github-actions, no auto-merge anywhere in `.github/workflows`, repo-wide 40-hex SHA pinning on every `uses:`)
- `.github/dependabot.yml` - version 2 config with three `updates` entries (uv, github-actions, docker), each `directory: "/"`, `schedule.interval: monthly`, a `groups.<name>-minor-patch` block (`applies-to: version-updates`, `update-types: [minor, patch]`), and a header comment recording the D-04..D-07 rationale

## Live-doc recheck (Task 1, per D-07)

Checked 2026-10-27 against the live pages (not just RESEARCH.md citations), by fetching each URL and inspecting the rendered content directly:

- **https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference**
  - (a) `package-ecosystem: "uv"` is a currently supported value (listed in the ecosystem table, YAML value `uv`, supported Dependabot version `v0.11`) for both version and security updates.
  - (b) `groups.<name>.applies-to` accepts `version-updates` or `security-updates`; `groups.<name>.update-types` accepts `minor`, `patch`, `major` (default includes all three when omitted) -- confirms that a group scoped to `["minor", "patch"]` leaves majors ungrouped, satisfying D-05 with no extra config.
  - (c) The cooldown support table (parsed from the page's own check/x-mark icons) confirms: `docker` and `github-actions` support `default-days` but **not** per-bump `semver-*-days`; `uv` supports both. This directly confirms Pitfall 5 and D-05's restriction.
  - (e) `open-pull-requests-limit` defaults to 5 and is freely configurable per ecosystem; security-update PRs have a separate fixed limit of 10, not configurable by this key.
- **https://docs.astral.sh/uv/guides/integration/dependabot/**
  - Confirms `package-ecosystem: "uv"` is the documented way to enable uv.lock updates, and that uv's own guidance is to set `cooldown.default-days` to match any `exclude-newer` value in `pyproject.toml`. This repo's `pyproject.toml`/`uv.lock` have no `exclude-newer` configured (checked directly), so no cooldown block was added for `uv` -- GitHub's repo-wide 3-day default cooldown (made default 2026-07-14, per RESEARCH.md's State-of-the-Art row) still applies.
  - (d) Dependabot's github-actions SHA-pin-plus-version-comment update behavior (rewriting a pinned SHA while keeping its trailing version comment current) was not independently re-confirmed against a single live doc page in this recheck -- the GitHub "About Dependabot version updates" and "Keeping your actions up to date with Dependabot" pages describe the update mechanism in general terms but don't spell out the comment-preservation detail. This repo's own SHA-pin-with-comment convention (enforced by `test_actions_remain_sha_pinned_repo_wide` here and `test_every_uses_in_ci_workflow_is_sha_pinned` in `tests/test_github_workflows.py`) is unaffected either way: Dependabot updating the SHA and comment, or only the SHA, both still produce a 40-hex-pinned `uses:` line that these tests require.
- **`gh api repos/thejuran/triggarr/automated-security-fixes`** (read-only): `{"enabled":true,"paused":false}` -- repository-level Dependabot security updates are confirmed enabled, satisfying D-06's "security updates open right away" premise.
- **`gh api repos/thejuran/triggarr --jq .allow_auto_merge`** (read-only): `false` -- confirms no repository-level auto-merge is enabled, consistent with D-05's "no auto-merge, ever."

## Decisions Made
- uv's block carries no `cooldown` key (see key-decisions above): matches uv's own documented guidance that `cooldown` should mirror `exclude-newer`, which this repo doesn't set.
- docker/github-actions blocks use `cooldown.default-days: 5` only, confirmed against the live per-ecosystem cooldown support table rather than trusting schema validation alone (schema validation accepts `semver-*-days` for every ecosystem even where GitHub silently ignores/breaks on it).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Acceptance-criterion violation] Header comment contained the literal substring "semver-", failing the plan's `grep -c "semver-"` acceptance check**
- **Found during:** Task 2, acceptance-criteria verification
- **Issue:** The first draft of `.github/dependabot.yml`'s header comment explained the forbidden `semver-*-days` cooldown keys by name, which made `grep -c "semver-" .github/dependabot.yml` return 1 instead of the required 0.
- **Fix:** Reworded the comment to describe the restriction ("any other, per-bump-type cooldown key") without using the literal substring "semver-". Behavior and documentation intent are unchanged; only the comment wording differs.
- **Cost if wrong:** None functionally -- this was a comment-text-only fix verified by rerunning the exact `grep -c` command from the plan's acceptance criteria (now returns 0) and rerunning all 8 contract tests (still pass).
- **Files modified:** `.github/dependabot.yml`
- **Verification:** `grep -c "semver-" .github/dependabot.yml` returns 0; `uv run pytest tests/test_dependabot_config.py -x -q` still 8 passed.
- **Committed in:** `71a7bb7` (Task 2 commit -- fixed before commit, not a separate commit)

---

**Total deviations:** 1 auto-fixed (1 acceptance-criterion wording fix)
**Impact on plan:** Cosmetic only (comment wording); no behavioral or test change. No scope creep.

## Issues Encountered
- `tests/conftest.py` failed to import (`ModuleNotFoundError: No module named 'loguru'`) on the first test run because the worktree's `.venv` hadn't been synced yet. Resolved by running `uv sync --extra dev` per this repo's documented Development Commands, before any test run. Not a plan deviation -- standard environment setup.

## User Setup Required

None - no external service configuration required. The first real Dependabot run happens only after this plan's commits merge to `main` (post-merge verification item, tracked in Plan 85-19).

## Next Phase Readiness
- `.github/dependabot.yml` is in place and test-pinned; no further Plan 85-06 work remains.
- Post-merge: confirm via the repo's Dependabot "Insights"/logs that the three ecosystems actually run on schedule and that no silently-rejected key disabled updates (Pitfall 5's warning sign) -- this is explicitly out of this plan's scope and deferred to Plan 85-19.
- Bot PRs from this config will be classified and reviewed like any PR (D-07); until Phase 85.1 ships the isolated Codex review for untrusted heads, each bot PR's Codex pass is recorded INCOMPLETE with an owner-approved fallback review, per the existing interim rule.

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Completed: 2026-10-27*

## Self-Check: PASSED

- FOUND: `.github/dependabot.yml`
- FOUND: `tests/test_dependabot_config.py`
- FOUND: `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-06-SUMMARY.md`
- FOUND commit `7fea735` (Task 1: test(85-06))
- FOUND commit `71a7bb7` (Task 2: ci(85-06))
