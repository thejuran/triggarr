---
phase: 85-follow-on-ci-improvements-acceptance-usability
reviewed: 2026-10-28T18:48:54Z
reviewed_head: 684ae13c8e5ac4e913a9a1d57866925083af0e97
diff_base: d7889b8fca4f46e70dd8eb65eb92199cd2236cf1
iteration: 7
depth: standard
files_reviewed: 4
files_reviewed_list:
  - .github/scripts/codex-fallback.cjs
  - .github/scripts/codex-fallback.test.cjs
  - tests/codex_review_run.py
  - tests/test_codex_review_run.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 85: Code Review Report (iteration 7, confirming the iteration-6 fixes)

**Reviewed:** 2026-10-28T18:48:54Z (head `684ae13c8e5ac4e913a9a1d57866925083af0e97`, diff base `d7889b8fca4f46e70dd8eb65eb92199cd2236cf1`)
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Scope: `git diff d7889b8..684ae13` for the four listed files, covering 06ac793 (WR-01) and 684ae13 (WR-02). I read the full files for context. The only later commit, e9f55f8, is docs-only and does not touch these files.

Verification run on this tree:
- `uv run pytest tests/test_codex_review_run.py tests/test_required_jobs_no_skip.py -q`: 261 passed
- `node --test .github/scripts/codex-fallback.test.cjs .github/scripts/ci-job-consistency.test.cjs`: 173 passed, 0 failed
- `uv run ruff check tests/`: clean
- `gsd-tools verify conventions --check` on the four files: no findings

**Iteration-6 WR-01 is resolved.** I ran a real `--dry-run` with a PR URL. It now prints `gh pr view ...`, then `git merge-base <baseRefOid-from-gh> <head>  # must equal --base <base>`, then `git merge-base --is-ancestor <base> refs/remotes/origin/main`. That is the same order `_verify_trust_pr` uses. The new parity test checks this properly. Main has moved on in the test, so the gh base and `--base` differ, and mapping only the gh base to the placeholder cannot hide a wrong argument in either merge-base call. It also uses exact list equality, so a missing, extra or reordered command fails it.

**Iteration-6 WR-02 is resolved as specified.** `BM2`, `B.M2`, `GSD2 agent`, `claude2`, `ClaudeCode`, `GSDReviewer`, `2BM` and `CodexReviewRun` are all rejected now. `submarine review` and the other accepted names still pass.

Regression checks:
- The exact-name comparison still lowercases first (`DISALLOWED_REVIEWERS.includes(lowered)`), so it is still case-insensitive.
- The PR-author comparison still compares the two lowercased, trimmed strings (`nameNorm === authorNorm`), so it is also still case-insensitive.
- The raw name reaches `reviewerNameIsDisallowed` only when `nameNorm` is non-empty, which means it is always a string there. A non-string name cannot crash the check.
- I probed 40 names. These legitimate ones stay accepted: `McAllister`, `JBMorgan reviewer`, `MacBMiller`, `J.BMartinez`, `OBrien BMcKay`, `iOSDev Team`, `eBMS reviewer`, `R2D2`, `QA2 team`, `Claudette Dupont`, `Anne-Marie O'Neil`.
- One new kind of false positive appeared. The digit split can now produce a single-letter token next to an initial. For example, `Room 2B, M. Ortiz` gives the tokens `2`,`b`,`m`, which join to `2bm`. The same goes for `Team 4B M`. At d7889b8 both were accepted. Both cases come down to letters that read as human initials, which falls inside the owner-accepted residual ("B. M. Smith"). The check fails closed, so I am not filing it.

There is one new warning. The case split makes the check depend on how a name is capitalised: `ClaudeCode` is rejected, but `claudecode` and `CLAUDECODE` are accepted. The same holds for `bmreviewer`, `gsdagent` and `codexreviewrun`.

## Structural Findings (fallow)

No structural findings were provided for this run.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: All-lowercase and all-caps run-together spellings still pass (`claudecode`, `CLAUDECODE`, `bmreviewer`, `gsdagent`, `codexreviewrun`)

**File:** `.github/scripts/codex-fallback.cjs:113-137` (`reviewerTokens` / `reviewerNameIsDisallowed`)
**Issue:** 684ae13 only splits at a change of case or at a letter/digit boundary. A run-together name typed in a single case has no such boundary, so it stays one token, and the token check needs an exact match. I probed this head and `reviewerNameIsDisallowed` returned:
- `ClaudeCode`: true (rejected), but `claudecode` and `CLAUDECODE`: false (accepted)
- `BMReviewer`: true, but `bmreviewer`: false
- `GSD-agent`: true, but `gsdagent`: false
- `CodexReviewRun`: true, but `codexreviewrun`: false. The runner's own name, `codex_review_run`, is on the exact-name list.

This is the same defect iteration-6 WR-02 described: the plain, likely-by-accident spelling gets through while a more elaborate one is caught. Now the deciding factor is capitalisation. All-lowercase run-together handles like `claudecode` are an ordinary way to write a tool's name, so they are not the deliberate fragment spoofs (`Cla Ude`) or mixed spellings the owner accepted. With this check as the gate, a fallback "reviewed" by `claudecode` is treated as independent. The owner's verbatim approval is still a second line of defense.
**Fix:** Split a single all-letter token when it can be broken entirely into known words, at least one of which is disallowed. Use a small vocabulary so ordinary words such as `submarine` are never split.
```js
const TOOL_WORDS = ['code', 'review', 'reviewer', 'agent', 'run', 'codex', 'bot', 'ai', 'cli'];
const SEGMENT_WORDS = [...DISALLOWED_REVIEWER_TOKENS, ...TOOL_WORDS];
// True when `token` is entirely SEGMENT_WORDS and its split is itself disallowed.
function segmentsToDisallowed(token) {
  const parts = [];
  const walk = rest => {
    if (!rest) return parts.length > 1 && tokensAreDisallowed(parts);
    return SEGMENT_WORDS.some(word => {
      if (!rest.startsWith(word)) return false;
      parts.push(word);
      const hit = walk(rest.slice(word.length));
      parts.pop();
      return hit;
    });
  };
  return walk(token);
}
// in reviewerNameIsDisallowed:
//   || tokens.some(segmentsToDisallowed)
```
Add `claudecode`, `CLAUDECODE`, `bmreviewer`, `gsdagent` and `codexreviewrun` to the rejected list, and keep `submarine review` and `Claudette Dupont` in the accepted list. The recursion requires a disallowed token or the full runner sequence, so `codereview` alone stays accepted. If the owner rules that run-together lowercase spellings belong to the accepted "mixed spellings" residual, record that ruling and drop this finding.

## Info

### IN-01 (carried from iteration 6 IN-01, owner left out of scope): The Node detector's quoted-key support misses YAML escape spellings

**File:** `.github/scripts/ci-job-consistency.cjs:589-596` (not changed in this round)
**Issue:** The key regex accepts `"paths"` and `'paths'` but silently drops escape spellings such as `"pa\x74hs"`. The PyYAML guard in `tests/test_required_jobs_no_skip.py` still catches them, so the gate is not weakened. The comment claims more than the regex delivers.
**Fix:** Inside `on:`, treat a quoted key line that does not match the strict regex as unsupported trigger syntax and fail closed, or narrow the comment.

### IN-02 (carried from iteration 6 IN-02, owner left out of scope): Run-splitting logic is duplicated

**File:** `.github/scripts/codex-fallback.cjs:63-79, 99-111, 133-137`
**Issue:** `collapseSingleCharRuns` and `singleCharRunsAreDisallowed` still contain the same run-accumulation loop. `tokensAreDisallowed(collapseSingleCharRuns(tokens))` is partly redundant with the substring check. This round makes the duplication matter more, because the digit and case splits now produce more single-character tokens that feed both loops.
**Fix:** Get the runs from one shared helper, or return both the collapsed list and the runs from a single pass.

## Set aside (needs ruling)

### SA-06: Digit splitting creates new initial-like false positives

**Where:** `.github/scripts/codex-fallback.cjs:119-120`
**Why excluded:** These are the owner-accepted "false positives on human initials" in a new form. Examples are `Room 2B, M. Ortiz` and `Team 4B M`, which were accepted at d7889b8 and are rejected now.
**Effect if left as is:** A reviewer whose name has a letter after a digit next to an initial `M` (or `SD`) is refused. The owner would need to write the name differently. Nothing unsafe is let through.
**Needs:** None, unless the owner wants this case treated differently from the accepted initials residual.

### SA-04 (carried, owner-recorded follow-up): A PR that changes `tests/codex_review_run.py` can certify its own base cross-grade
**Where:** `tests/codex_review_run.py` (`_run_base_grader`); `.github/scripts/acceptance-readiness.cjs:80-98`
**Why excluded:** The owner recorded this on 2026-10-27. This round does not change it.
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

_Reviewed: 2026-10-28T18:48:54Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
