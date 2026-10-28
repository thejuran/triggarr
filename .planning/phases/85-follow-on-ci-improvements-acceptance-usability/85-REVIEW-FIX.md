---
phase: 85-follow-on-ci-improvements-acceptance-usability
fixed_at: 2026-10-28T18:46:16Z
review_path: .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
rejected: 0
status: all_fixed
---

# Phase 85: Code Review Fix Report

**Fixed at:** 2026-10-28T18:46:16Z
**Source review:** .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-REVIEW.md (review iteration 6, head d7889b8)
**Iteration:** 1 (fix run against review iteration 6; the round-4 fix report is preserved as 85-REVIEW-FIX.iter4.md)

**Summary:**
- Findings in scope: 2 (WR-01, WR-02; owner direction: IN-01/IN-02 out of scope)
- Fixed: 2
- Skipped: 0
- Rejected: 0

**Verification (on 684ae13):**
- `.venv/bin/python -m pytest tests/test_codex_review_run.py -x -q`: 151 passed
- `node --test .github/scripts/codex-fallback.test.cjs`: 86 passed
- `.venv/bin/ruff check tests/`: clean
- Extra: `node --test .github/scripts/*.test.cjs`: 433 passed

## Fixed Issues

### WR-01: `--dry-run` no longer lists every command PR-form trust verification runs

**Files modified:** `tests/codex_review_run.py`, `tests/test_codex_review_run.py`
**Commit:** 06ac793
**Applied fix:** `_trust_preview_commands` now lists the PR-form commands in the order `_verify_trust_pr` runs them: `gh pr view ...`, then `git merge-base <baseRefOid-from-gh> <head>  # must equal --base <base>`, then the base-on-origin/main check. The placeholder is a module constant, `_PR_BASE_PLACEHOLDER`. New parity test: `test_pr_trust_preview_lists_exactly_the_commands_verify_trust_runs`. It runs `verify_trust` against `_TrustRunner` in the main-moved-on case, where the gh base differs from `--base`, so swapping the placeholder in cannot hide a wrong argument. It maps the gh-reported base to the placeholder and asserts that the preview's argv lists equal `fake.calls`, in order and with nothing extra. The old preview fails this test because it lists 2 commands and 3 run. The contract doc already promises "every command", so it needed no change.

### WR-02: The split-letter check makes `B M 2` stricter than `BM2`, and leaves `ClaudeCode` accepted

**Files modified:** `.github/scripts/codex-fallback.cjs`, `.github/scripts/codex-fallback.test.cjs`
**Commit:** 684ae13
**Status:** fixed: requires human verification (this is a logic change to the independence rule)
**Applied fix:** Added `reviewerTokens(name)`. Before lowercasing, it splits camelCase (`ClaudeCode`), acronym-then-word (`GSDReviewer`) and letter/digit boundaries in both directions (`BM2`, `2BM`). It then tokenizes as before, and every existing token, collapsed-run and substring check now runs on those tokens. Making this work needed one more change the review did not mention. `validateFallback` lowercased the name before calling `reviewerNameIsDisallowed`, which erased the case boundaries, so the call now passes the raw name. The function lowercases internally, and the exact-match and PR-author checks still use the lowercased name. The acronym split goes slightly past the review's snippet. It fits the owner-approved camelCase scope and catches `GSDReviewer`, which the plain camelCase rule misses.
**Regression tests:**
- Now rejected: `BM2`, `B.M2`, `GSD2 agent`, `claude2`, `ClaudeCode`, `GSDReviewer`, `2BM`, `CodexReviewRun`.
- Still accepted: every previously allowed name ('vibe-check deep review (owner-run)', 'manual Codex inspection session', 'independent human reviewer', 'submarine review', 'J. R. independent reviewer'), plus the new cases `Submarine Review`, `McAllister independent review` and `reviewer 2`.

---

_Fixed: 2026-10-28T18:46:16Z_
_Fixer: Claude (bm-code-fixer)_
_Iteration: 1_
