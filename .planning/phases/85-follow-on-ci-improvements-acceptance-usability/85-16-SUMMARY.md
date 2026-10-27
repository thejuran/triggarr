---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "16"
subsystem: testing
tags: [codex-review, drift-guard, review-machinery, D-17, classification-policy]

# Dependency graph
requires:
  - phase: 85-follow-on-ci-improvements-acceptance-usability (85-13)
    provides: audited_inputs_changed_in_diff + base-commit cross-grading, which this plan's AUDITED_INPUTS changes will exercise on the phase's own Codex pass
provides:
  - "tests/test_review_machinery_lists.py: a dependency-free drift guard (extract_policy_machinery, extract_checklist_machinery, in_effective_codex_scope, machinery_list_problems) that pins exact agreement between the classification policy's sensitive row, the acceptance checklist's Codex line, AUDITED_INPUTS and EXCLUDE_PATHSPECS, with two documented role exceptions"
  - "*-PLAN.md phase plan files classified sensitive (not ordinary-docs) in docs/review-classification-policy.md, with the D-01 no-fast-path resolution recorded in the status line and D-14 ground rule"
  - "Fixed prompt version 6: a second, positive :(glob).planning/**/*-PLAN.md diff brings PLAN files back into Codex review scope despite the blanket .planning/**/*.md exclusion"
affects: ["85-17 (contract/record docs may reference the v6 prompt and the drift guard)", "this phase's own final Codex pass, which will see 2 AUDITED_INPUTS files changed in this diff"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A dependency-free glob matcher (segment-aware ** / * translation to regex) for git :(exclude,glob)/:(glob) pathspecs, used to prove scope coverage without shelling out to git"
    - "Majority-vote attribution across three independently-sourced sets (policy-extracted, checklist-extracted, and the passed-in AUDITED_INPUTS) to name which specific hand-kept list drifted, rather than reporting a generic mismatch"

key-files:
  created:
    - tests/test_review_machinery_lists.py
  modified:
    - docs/review-classification-policy.md
    - docs/codex-adversarial-review-contract.md
    - tests/codex_review_run.py
    - tests/test_codex_review_run.py
    - tests/test_codex_review_contract.py

key-decisions:
  - "machinery_list_problems() uses majority-vote attribution (comparing audited_inputs, policy-reconciled-machinery and checklist-reconciled-machinery pairwise) to blame the specific drifted list by name, since AUDITED_INPUTS, the policy row and the checklist line are three independent sources describing the same underlying set"
  - "EXCLUDE_PATHSPECS gets two separate checks: exact-membership against a literal EXPECTED_EXCLUDES tuple (catches add/remove), and a no-match-against-machinery scan (catches an exclusion that would silently hide a review-machinery file)"

requirements-completed: [ACCEPT-03]

# Metrics
duration: ~25min
completed: 2026-10-27
---

# Phase 85 Plan 16: Review-List Drift Guard and PLAN-File Codex Scope Summary

**A three-list drift guard (policy sensitive row, Codex AUDITED_INPUTS/EXCLUDE_PATHSPECS, acceptance checklist) with majority-vote problem attribution; `*-PLAN.md` phase plan files classified sensitive and brought into Codex review scope via a second, positive diff in fixed prompt version 6.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2
- **Files modified:** 6 (1 created, 5 modified)

## Accomplishments

- `tests/test_review_machinery_lists.py` extracts the review-machinery file set from two independently hand-maintained prose sources (the classification policy's sensitive row, the acceptance checklist's "- Codex:" line) and compares them against `AUDITED_INPUTS`/`EXCLUDE_PATHSPECS` with two documented, named exceptions (`POLICY_ONLY`, `CHECKLIST_OMITS`). Ten mutation tests each prove `machinery_list_problems()` names the specific list and path that drifted — removing or adding an entry anywhere, or emptying either prose region, is caught, never a vacuous pass.
- `in_effective_codex_scope()` computes the real, net Codex scope as the union of the full diff (minus `EXCLUDE_PATHSPECS`) and the positive PLAN diff (`PLAN_PATHSPECS`), via a dependency-free glob matcher that correctly handles `**` matching zero or more path segments. The drift guard proves every `*-PLAN.md` sample is in that union, no `EXCLUDE_PATHSPECS` entry ever matches a review-machinery file, and an emptied `PLAN_PATHSPECS` is caught rather than silently losing PLAN coverage (checker W04).
- `docs/review-classification-policy.md`: the sensitive row now names `*-PLAN.md` phase plan files under `.planning/phases/` as agent instructions (not ordinary-docs); the status line and the D-14 ground rule record the D-01 owner decision (no docs fast path — every PR runs every required check, enforced by the permanent no-skip test).
- `docs/codex-adversarial-review-contract.md` fixed prompt version 6 adds a second, positive `git diff {{BASE_SHA}}..{{HEAD_SHA}} -- ':(glob).planning/**/*-PLAN.md'` command (a pathspec exclude cannot be re-included, so the blanket `.planning/**/*.md` exclusion needed a second diff rather than a narrower one). `tests/codex_review_run.py` adds matching `PLAN_PATHSPECS`/`plan_diff_argv()`, bumps `TEMPLATE_HEADING` to version 6, and previews both diff commands in `dry_run()`.

## Task Commits

1. **Task 1: Three-list drift guard (RED, then align the lists)**
   - `d0b2b75` test(85-16): add failing review-machinery drift guard (D-17)
   - `695e7de` docs(85-16): classify plan files as sensitive and record the D-01 resolution
2. **Task 2: Bring PLAN files into Codex scope — fixed prompt version 6 and runner pathspecs**
   - `19f4f6d` test(85-16): add failing prompt v6 PLAN-scope tests
   - `7cdb651` feat(85-16): put phase plan files in Codex review scope (prompt v6, D-17)

Both tasks followed RED -> GREEN per the plan's `tdd="true"` requirement. Worktree base (before this plan's commits): `1fbfc3960cc28256202ca94e8375e40c61340fbe`.

## Files Created/Modified

- `tests/test_review_machinery_lists.py` (created) — extractors, glob matcher, `in_effective_codex_scope()`, `machinery_list_problems()`, real-document tests, and 10 mutation tests, each asserting its specific problem substring.
- `docs/review-classification-policy.md` — ordinary-docs row excludes `*-PLAN.md`; sensitive row adds it; status line and D-14 bullet record D-01.
- `docs/codex-adversarial-review-contract.md` — version-history line, "## Review scope" explanation, heading rename, prompt's second diff command, "Template version: 6."
- `tests/codex_review_run.py` — `PLAN_PATHSPECS`, `plan_diff_argv()`, `TEMPLATE_HEADING` -> version 6, `dry_run()` previews both diff commands.
- `tests/test_codex_review_run.py` — imports/tests for `PLAN_PATHSPECS`/`plan_diff_argv`, dry-run assertions for both diff commands, version-6 rename, and the two deviation fixes below.
- `tests/test_codex_review_contract.py` — `_extract_fixed_prompt` heading, `test_contract_template_version_six`, `test_prompt_includes_plan_file_diff`.

## Decisions Made

- `machinery_list_problems()` attributes a drifted path to whichever of the three sources (AUDITED_INPUTS, policy-reconciled machinery, checklist-reconciled machinery) is the minority view when the other two agree — this lets a single helper blame the correct list by name instead of only reporting "something disagrees."
- `EXCLUDE_PATHSPECS` gets two independent checks (exact-membership vs. a literal `EXPECTED_EXCLUDES`, and a no-match-against-machinery scan) because the two mutation shapes (remove an entry vs. add one that collides with machinery) need different detection logic.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_policy_sensitive_planning_paths()` crashed on the new `.planning/phases/` mention**
- **Found during:** Task 2's full verify run (`tests/test_codex_review_run.py::test_pathspecs_keep_planning_config_and_drop_planning_docs`)
- **Issue:** Task 1's policy edit added `` `.planning/phases/` `` (a bare, backtick-wrapped directory reference) to the sensitive row, right next to the unrelated `` `*-PLAN.md` `` glob mention. The existing helper `_policy_sensitive_planning_paths()` in `tests/test_codex_review_run.py` matches any backtick-wrapped `.planning/...` substring in that row and feeds every result into a fixture that creates a *file* at each returned path. A directory-shaped entry with a trailing slash collided with a sibling fixture file's parent directory, crashing with `IsADirectoryError` instead of the fixture's intended fixed set.
- **Fix:** Narrowed the helper to exclude any match ending in `/`, so it only returns concrete file paths (e.g. `.planning/config.json`) the fixture can actually create — matching the helper's actual purpose (naming sensitive *files*, not directories).
- **Cost if wrong:** Left unfixed, this existing fixture test fails outright on this phase's own PR (not a silent gap — a hard crash), blocking CI on an unrelated-looking file-creation error that obscures the real cause.
- **Files modified:** tests/test_codex_review_run.py
- **Commit:** `7cdb651`

**2. [Rule 1 - Bug] `test_execute_records_provenance` hardcoded `template_version == "5"`**
- **Found during:** Task 2's full verify run, after fixing deviation #1
- **Issue:** An existing provenance test asserted the recorded `meta["template_version"]` equals the string `"5"`, which the version-6 bump in `tests/codex_review_run.py`'s `TEMPLATE_HEADING`/contract doc correctly changed to `"6"`, failing the hardcoded assertion.
- **Fix:** Updated the assertion to `"6"`.
- **Cost if wrong:** A real template-version regression (e.g. the contract and runner silently drifting apart) would go undetected if this assertion were left pinned to the old value instead of tracking the current version.
- **Files modified:** tests/test_codex_review_run.py
- **Commit:** `7cdb651`

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs, both discovered by running the plan's own verify command against pre-existing tests in files already in this plan's scope)
**Impact on plan:** Both fixes necessary for the plan's own verify command to pass cleanly; no scope creep — both touched files (`tests/test_codex_review_run.py`) were already in Task 2's `<files>` list.

## Issues Encountered

None beyond the two deviations above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- The drift guard, PLAN-file classification and prompt v6 are complete, committed, and independently verified: `uv run pytest tests/test_codex_review_contract.py tests/test_codex_review_run.py tests/test_review_machinery_lists.py tests/test_review_checkpoint_record.py tests/test_review_instructions.py -x -q` passes (191 passed); `uv run ruff check tests/` is clean.
- Full repository suite verified: `uv run pytest tests/ -q` — **2536 passed**, 38 pre-existing warnings (starlette/httpx deprecation, unrelated to this plan). `uv run ruff check triggarr/ tests/` — clean.
- This plan changed 2 `AUDITED_INPUTS` files (`docs/codex-adversarial-review-contract.md`, `tests/codex_review_run.py`). Per the plan's note, this phase's own final Codex pass will record them in `audited_inputs_changed_in_diff` and cross-grade with the base commit's checker (Plan 85-13's mechanism) — no action needed from this plan, but downstream reviewers should expect that cross-grade to appear in the evidence.
- Plan 85-17 (contract/record docs, not yet executed as of this summary) should be aware the contract is now at "Template version: 6" with an added "## Review scope" paragraph on PLAN-file handling.

## Self-Check: PASSED

- FOUND: tests/test_review_machinery_lists.py
- FOUND: docs/review-classification-policy.md
- FOUND: docs/codex-adversarial-review-contract.md
- FOUND: tests/codex_review_run.py
- FOUND: tests/test_codex_review_run.py
- FOUND: tests/test_codex_review_contract.py
- FOUND: .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-16-SUMMARY.md
- FOUND commit: d0b2b75 (test(85-16): add failing review-machinery drift guard (D-17))
- FOUND commit: 695e7de (docs(85-16): classify plan files as sensitive and record the D-01 resolution)
- FOUND commit: 19f4f6d (test(85-16): add failing prompt v6 PLAN-scope tests)
- FOUND commit: 7cdb651 (feat(85-16): put phase plan files in Codex review scope (prompt v6, D-17))

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Completed: 2026-10-27*
