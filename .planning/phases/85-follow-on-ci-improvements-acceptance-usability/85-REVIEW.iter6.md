---
phase: 85-follow-on-ci-improvements-acceptance-usability
reviewed: 2026-10-28T18:40:38Z
reviewed_head: d7889b8fca4f46e70dd8eb65eb92199cd2236cf1
diff_base: 1f8e3391f02f7637bdf29d6e68038563fadc2258
iteration: 6
depth: standard
files_reviewed: 8
files_reviewed_list:
  - .github/scripts/ci-job-consistency.cjs
  - .github/scripts/ci-job-consistency.test.cjs
  - .github/scripts/codex-fallback.cjs
  - .github/scripts/codex-fallback.test.cjs
  - docs/codex-adversarial-review-contract.md
  - tests/codex_review_run.py
  - tests/test_codex_review_run.py
  - tests/test_required_jobs_no_skip.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 85: Code Review Report (iteration 6, post vibe-check fixes)

**Reviewed:** 2026-10-28T18:40:38Z (head `d7889b8fca4f46e70dd8eb65eb92199cd2236cf1`, diff base `1f8e3391f02f7637bdf29d6e68038563fadc2258`)
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Scope: `git diff 1f8e339..HEAD` for the eight listed files, which covers the six vibe-check fix commits (bfe1e38, 0bd95dd, 66b5581, 0e5a08d, ca87b0e, d7889b8). I read the full files for context.

Verification run on this head:
- `uv run pytest tests/test_required_jobs_no_skip.py tests/test_codex_review_run.py -q`: 260 passed
- `node --test .github/scripts/ci-job-consistency.test.cjs .github/scripts/codex-fallback.test.cjs`: 162 passed
- `uv run ruff check tests/`: clean

Probes I ran beyond the tests:
- The PyYAML trigger guard rejects an escape-spelled filter key (`"paths":`) and accepts a quoted trigger name (`"pull_request":`). Both are correct.
- The Node detector fails closed on a quoted trigger name (`on.pull_request is required`).
- The runner's merge-base rule matches `acceptance-readiness.cjs:417`, which also uses `git merge-base <base> <head>`.

The fixes do what they claim. I found no blockers. There are two warnings. First, the runner's `--dry-run` no longer previews every command that trust verification runs, even though the contract doc promises it does. Second, after the new split-letter checks, the reviewer-name check rejects `B M 2` but accepts `BM2`, `B.M2` and `ClaudeCode`.

## Structural Findings (fallow)

No structural findings were provided for this run.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: `--dry-run` no longer lists every command PR-form trust verification runs

**File:** `tests/codex_review_run.py:1233-1250` (the preview), compared with `tests/codex_review_run.py:470-488, 525-538` (what actually runs)
**Issue:** bfe1e38 added a third command to `_verify_trust_pr`: `git merge-base <PR baseRefOid> <head>`, run through `_pr_merge_base`. `_trust_preview_commands` is documented as "Commands verify_trust() would run for *run*", but for the PR form it still returns only `gh pr view ...` and `git merge-base --is-ancestor <base> refs/remotes/origin/main`. The contract (`docs/codex-adversarial-review-contract.md`, Invocation step 3) says the dry run "prints every command without running any of them". An operator who checks a run with `--dry-run` now sees an incomplete command list, and it leaves out the exact command that decides whether `--base` is accepted. No test compares the preview with the trust runner's calls, which is why this slipped through.
**Fix:** Add the merge-base command to the PR preview, using a placeholder for the base, which is unknown until `gh` answers. Then add a parity test.
```python
    return [
        shlex.join(["gh", "pr", "view", number, "--repo", REPO_SLUG, "--json", _GH_PR_VIEW_FIELDS]),
        f"git merge-base <baseRefOid from gh> {run.head}  # must equal --base {run.base}",
        base_on_main,
    ]
```
The test should use `_TrustRunner` to run `verify_trust(_pr_run(), fake)` and assert that every argv prefix in `fake.calls` appears in `_trust_preview_commands(run)`. This catches the next drift as well.

### WR-02: The split-letter check makes `B M 2` stricter than `BM2`, and leaves `ClaudeCode` accepted

**File:** `.github/scripts/codex-fallback.cjs:59-122`
**Issue:** 66b5581 substring-checks runs of single-character tokens, so `B M 2` (tokens `b`,`m`,`2` joined as `bm2`) is rejected, and the new test at `codex-fallback.test.cjs:542` pins that. Multi-character tokens still need an exact match, though, so the plainer spellings get through. I probed this head and `reviewerNameIsDisallowed` returned:
- `BM2`: false (accepted)
- `B.M2`: false (accepted)
- `GSD2 agent`: false (accepted)
- `claude2`: false (accepted)
- `ClaudeCode`: false (accepted)
- `B M 2`: true (rejected)

The rule's stated intent (lines 59-62) is that "B.M." is checked "exactly as 'BM' is". The check is now stricter for the split spelling than for the unsplit one. That is backwards, because the unsplit spelling is the one a person is likely to type by accident. `ClaudeCode` and `BM2` are not the deliberate fragment spoofs the owner accepted (`Cla Ude`, mixed spellings); they are ordinary ways to write the tool's name. The owner's verbatim approval is a second line of defense. Still, with this check as the gate, a fallback "reviewed" by `ClaudeCode` passes as independent.
**Fix:** Before the token checks, split letter/digit boundaries and camelCase boundaries. Do it on the original string, before lowercasing, so case boundaries survive.
```js
function reviewerTokens(name) {
  return name.trim()
    .replace(/([a-z])([A-Z])/g, '$1 $2')        // ClaudeCode -> Claude Code
    .replace(/([A-Za-z])([0-9])/g, '$1 $2')     // BM2 -> BM 2
    .replace(/([0-9])([A-Za-z])/g, '$1 $2')
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(Boolean);
}
```
Then add `BM2`, `B.M2`, `GSD2 agent` and `ClaudeCode` to the rejected list, and keep `submarine review` in the accepted list. The camelCase split does not touch an all-lowercase word, so that name stays accepted. If the owner decides `ClaudeCode` counts as a deliberate spoof, drop that part, but keep the digit split so `BM2` and `B M 2` agree.

## Info

### IN-01: The Node detector's quoted-key support misses YAML escape spellings (the PyYAML guard catches them)

**File:** `.github/scripts/ci-job-consistency.cjs:589-596`
**Issue:** The new key regex accepts `"paths"` and `'paths'`. YAML also reads `"paths"` and `"pa\x74hs"` as the key `paths`, and the regex silently drops those lines. I confirmed that `findSkipConditions` returns `[]` for both. `acceptance_problems` in `tests/test_required_jobs_no_skip.py` does catch them, since it works on the parsed mapping, and the docstrings say the Python guard wins where the two disagree. The gate itself is not weakened. The issue is that the comment ("a quoted `"paths":` must not slip past") claims more than the regex delivers.
**Fix:** Inside the `on:` block, treat any 4-space-indented line that starts with a quote but does not match the strict key regex as `unsupported trigger syntax`, so the detector fails closed. Alternatively, narrow the comment to "plain quoted keys; escape sequences are left to the PyYAML guard".

### IN-02: Run-splitting logic is duplicated, and one check is partly redundant

**File:** `.github/scripts/codex-fallback.cjs:63-79, 99-111, 117-121`
**Issue:** `collapseSingleCharRuns` and `singleCharRunsAreDisallowed` contain the same run-accumulation loop. `tokensAreDisallowed(collapseSingleCharRuns(tokens))` is only needed for the token sequence (`codex review run` with some words letter-split). Its single-token check is a strict subset of the substring check in `singleCharRunsAreDisallowed`. If the two copies of the loop drift apart, the checks go out of step without any test failing.
**Fix:** Have `singleCharRunsAreDisallowed` take its runs from one shared helper, for example by filtering `collapseSingleCharRuns(tokens)` to the entries built from single characters. Or return both the collapsed list and the runs from a single pass.

## Set aside (needs ruling)

### SA-04 (carried, owner-recorded follow-up): A PR that changes `tests/codex_review_run.py` can certify its own base cross-grade
**Where:** `tests/codex_review_run.py` (`_run_base_grader`); `.github/scripts/acceptance-readiness.cjs:80-98`
**Why excluded:** The owner recorded this on 2026-10-27. This round's diff does not change it.
**Effect if left as is:** For a PR that changes the runner, a "complete" Codex item rests on the changed runner's honesty.
**Needs:** None this round.

### SA-05 (carried, owner-recorded follow-up): The checks do not look inside reusable workflows or local actions
**Where:** `tests/test_required_jobs_no_skip.py`
**Why excluded:** The owner recorded this. The guard forbids both in required jobs.
**Effect if left as is:** None today.
**Needs:** None this round.

### SA-01 (carried): This PR's acceptance runs on the gate it introduces
**Where:** `.github/workflows/review-acceptance.yml`
**Why excluded:** The workflow discloses it, and it is a governance choice.
**Effect if left as is:** A defect in the schema-2 gate would also admit this PR.
**Needs:** An owner ruling.

### SA-02 (carried): The register schema cutover strands other open PRs
**Where:** `.github/scripts/review-acceptance.cjs:10-12`; `.github/scripts/review-register.cjs:95-112`
**Why excluded:** It is a question of operational ordering.
**Effect if left as is:** In-flight PRs need their dispositions re-entered after migration.
**Needs:** An owner ruling on migration timing.

### SA-03 (carried): The Dependabot `uv` ecosystem has no cooldown
**Where:** `.github/dependabot.yml:23-31`
**Why excluded:** It is a policy choice.
**Effect if left as is:** There is less buffer against a malicious or yanked PyPI release.
**Needs:** An owner ruling.

---

_Reviewed: 2026-10-28T18:40:38Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
