---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "10"
subsystem: infra
tags: [github-actions, release, least-privilege, ci]

# Dependency graph
requires:
  - phase: 82-ci-tests-what-we-ship
    provides: the audited-image artifact and release-identity gate (preflight -> release) this plan builds the job split on top of
provides:
  - release.yml release job narrowed to packages:write/contents:read/actions:read
  - new tag-only github-release job holding the repo's only remaining contents:write, gated by needs:[preflight, release] and the tag-only if
  - release.yml no longer downloads, verifies, or attaches Python distribution assets (D-14)
  - extended publication_bypass_violations() covering contents:write leakage, github-release misconfiguration, and re-attached dist assets
affects: [86-pilot-reference-record]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Job-level permissions split: a second job with needs:[preflight, release] holds the only contents:write, mirroring the existing preflight -> release two-job needs/outputs shape one level up"

key-files:
  created: []
  modified:
    - .github/workflows/release.yml
    - .github/scripts/artifact-promotion.test.cjs
    - tests/test_github_workflows.py

key-decisions:
  - "Followed PLAN.md's exact job id 'github-release' (not 85-RESEARCH.md's illustrative 'create-github-release'/'publish-images' names), since the plan is the authoritative executable spec and the research doc predates that naming decision"

patterns-established:
  - "publication_bypass_violations() now asserts, by structure not just by name: no job other than github-release holds contents:write; github-release's own if/needs/step are validated independently of the release job's checks; any run text containing dist/ or .whl anywhere in the workflow is itself a violation"

requirements-completed: [CIMAINT-05, CIMAINT-07]

# Metrics
duration: ~15min
completed: 2026-10-27
---

# Phase 85 Plan 10: Split Release Permissions & Drop Python Distributions Summary

**release.yml's only `contents: write` now lives in a new tag-only `github-release` job; Python distribution download/verify/upload steps are removed from the release pipeline entirely (D-14)**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-10-27T12:52:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `release` job permissions narrowed from `{packages: write, contents: write, actions: read}` to `{packages: write, contents: read, actions: read}`
- New `github-release` job (`needs: [preflight, release]`, tag-only `if`, 5-minute timeout, own concurrency group) holds `{contents: write}` as the only job in the file with that permission, and does no checkout
- `Create GitHub Release` moved into `github-release`, stripped of all dist-asset handling (`gh release create ... --generate-notes --latest`, no asset arguments)
- `publication_bypass_violations()` extended with three new structural checks (contents:write leakage outside github-release; github-release's own if/needs/step integrity; any re-introduced `dist/`/`.whl` text anywhere in the workflow), each proven by a dedicated mutation test
- Confirmed via `git grep` that no other workflow, test, or doc file references the two removed dist steps before deleting them

## Task Commits

Each task was committed atomically:

1. **Task 1: Tests first — no-dist and permission-split contract (RED)** - `90705a7` (test)
2. **Task 2: Remove dist handling and split release.yml permissions (GREEN)** - `30cc961` (ci)

_TDD plan: RED commit (`90705a7`) precedes GREEN commit (`30cc961`); no refactor commit was needed._

## Files Created/Modified
- `.github/workflows/release.yml` - `release` job permissions narrowed; dist download/verify steps and the `Create GitHub Release` step removed; new tag-only `github-release` job added holding the sole `contents: write`
- `.github/scripts/artifact-promotion.test.cjs` - first test renamed and narrowed to the image-only exact-run artifact with exactly 1 `run-id:` line (was 2, included the dist download)
- `tests/test_github_workflows.py` - `test_release_job_permissions_unchanged` replaced by `test_only_github_release_job_holds_contents_write`; added `test_github_release_job_is_tag_only_and_needs_release` and `test_release_workflow_has_no_python_distributions`; `publication_bypass_violations()` extended; 4 new `BYPASS_MUTATIONS` entries added (all 11 original names preserved, 15 total); `create-release-not-cancelled` retargeted at the `github-release` job's step

## Decisions Made
- Used the PLAN.md-specified job id `github-release` rather than 85-RESEARCH.md's illustrative `create-github-release`/`publish-images` naming — the plan's `must_haves.key_links` and task actions pin the exact id, and the research doc's names were only ever illustrative pattern sketches written before that naming was finalized.
- Dropped the "Phase 85" phase-framing from the in-file comment the plan's action text specified ("Only this tag-only job holds contents: write (Phase 85 CIMAINT-07)...") and kept only the bare requirement/decision IDs (`CIMAINT-07`, `D-14`), matching this repository's established convention of requirement-ID comments (e.g. `SAFETY-03`, `ROBUST-01`, `D-08` appear throughout `triggarr/`) with no GSD phase numbers in product code or comments.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Unused loop variable from the new D-14 dist-asset scan**
- **Found during:** Task 1 (writing the extended `publication_bypass_violations()`)
- **Issue:** The new "any run text containing dist/ or .whl" scan originally iterated `for job_name, job in jobs.items()` without using `job_name`, tripping ruff's B007 (unused loop control variable).
- **Fix:** Changed to `for job in jobs.values()`.
- **Cost if wrong:** Purely cosmetic (lint-only); no behavior change either way.
- **Files modified:** `tests/test_github_workflows.py`
- **Commit:** `90705a7`

**2. [Rule 1 - Bug] Environment's forced ANSI color broke the RED self-test's text matching**
- **Found during:** Task 1 verification (running the plan's RED check script)
- **Issue:** This sandbox has `FORCE_COLOR=3` set, which made `pytest`'s short summary lines start with ANSI escape codes (e.g. `\x1b[31mFAILED\x1b[0m ...`) instead of plain `FAILED `, so the verify script's `grep -qE "^FAILED ..."` anchors never matched even though the correct tests were failing for the correct reasons.
- **Fix:** Ran the pytest portion of the RED/GREEN verification with `FORCE_COLOR=0 NO_COLOR=1 ... --color=no`. This only affects how I verified the result in this session; the plan's committed test files and verify commands are unchanged.
- **Cost if wrong:** None to the shipped artifact — this only affected my own terminal verification step, not any committed file or CI command.
- **Files modified:** none (verification-only; no file changes)
- **Commit:** n/a (not a code change)

**3. [Rule 1/compliance] Translated the plan's "Phase 85" comment framing into bare requirement IDs**
- **Found during:** Task 2 (writing the `github-release` job's explanatory comment)
- **Issue:** The plan's `<action>` text specifies the comment verbatim as `"Only this tag-only job holds contents: write (Phase 85 CIMAINT-07). Python distributions are no longer attached (Phase 85 D-14); earlier releases keep theirs."` — but GSD phase/plan numbers must never be written into product code or comments (that's GSD-internal bookkeeping, not product documentation), per this executor's standing constraint.
- **Fix:** Kept the behavioral content and the requirement/decision IDs (`CIMAINT-07`, `D-14`) — consistent with this repo's existing convention of bare requirement-ID comments throughout `triggarr/` — but dropped the "Phase 85" prefix from both.
- **Cost if wrong:** None to CI behavior; purely a comment-wording question. If this reading is wrong, the fix is a one-line comment edit.
- **Files modified:** `.github/workflows/release.yml`
- **Commit:** `30cc961`

---

**Total deviations:** 3 (2 Rule 1 auto-fixes, 1 compliance translation per standing constraint)
**Impact on plan:** None of these change the shipped behavior from what the plan specified; all are lint/verification/comment-wording adjustments. No scope creep.

## Issues Encountered
None beyond the deviations above.

## Post-Merge Verification (PENDING — CIMAINT-07, T-85-31)

**This item cannot be verified locally and must be recorded after this plan's changes reach `main` and a real push-triggered Release run executes.**

The first `main`-push Release run after merge must be checked and the following recorded here or in the phase's review evidence:
- Run ID / URL of that Release workflow run
- The `release` job's actual permissions as shown in that run's "Set up job" log (expect `packages: write`, `contents: read`, `actions: read` — no `contents: write`)
- Confirmation that `:main` and `:dev` tags were pushed successfully to `ghcr.io/thejuran/triggarr` (and Docker Hub mirror, if configured) under the narrowed permission
- The pushed image digests

Until that run is observed and recorded, CIMAINT-07's "demonstrate a successful `:main`/`:dev` publish under the narrower permission" acceptance criterion and threat T-85-31 (repudiation: claiming the narrowed publish works without a real run) stay **PENDING**. This plan proves the structure (permissions split, job gating, bypass-mutation coverage) by test; it does not and cannot prove the live publish by test.

Separately, a real `v*` tag push is needed to observe `github-release` actually creating a GitHub Release with no distribution assets attached — also not exercised in this plan (per Phase 82's standing rule, a deliberately broken push and any production tag push each need the owner's separate go-ahead at execution time).

## Known Stubs
None.

## Threat Flags
None — the new `github-release` job and its sole `contents: write` are exactly the surface this plan's own `<threat_model>` (T-85-29, T-85-30, T-85-31) already covers; no additional undocumented surface was introduced.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Structural tests (`uv run pytest tests/test_github_workflows.py -x -q`, `node --test .github/scripts/artifact-promotion.test.cjs`, `actionlint .github/workflows/release.yml`) all pass against the real `release.yml`.
- `ci.yml`'s `python-dist` upload step is intentionally untouched — this plan's objective explicitly defers that removal to Plan 85-11; until then the extra CI-side artifact is harmless (nothing in `release.yml` downloads it anymore).
- The CIMAINT-07 live-publish verification above is the one open item before this requirement can be called fully closed; it is a post-merge, real-GitHub-run check, not a blocker to merging this plan's own changes.
- Post-wave integration run (`uv run pytest tests/ -x -q` plus the full `node --test` glob) is deliberately NOT run as part of this plan, per the plan's own `<verification>` note that it is a wave-level gate run once after every plan in wave 1 has finished (same-wave plans may hold intentionally failing RED tests mid-wave).

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Completed: 2026-10-27*
