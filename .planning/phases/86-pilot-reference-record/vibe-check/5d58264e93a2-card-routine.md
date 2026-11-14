# Vibe-check deep review (routine): card-template PR, integration head 5d58264e93a2 (pass 2)

Continues `46c39194249d-card-routine.md` (pass 1 at the pre-integration head) on the same state file. Run 2026-11-13 (2026-11-14T04:50:37Z to 04:56:01Z; exact-head coverage prepared 04:47Z to 04:50Z).

- **Tool:** vibe-check deep-review 2.14.1, stock invocation, range mode `aeead4b601d7..5d58264e93a2`, pass 2.
- **What was reviewed:** the PR's own net change against current main (`tests/test_outcome.py`, `triggarr/search/outcome.py`, `triggarr/templates/partials/cycle_grade.html`; 126 changed lines). The tool's instructions are ambiguous about whether a second pass in range mode reviews the named range or only the changes since the last pass; the named range was used, because plan 86-10 asks for evidence on the PR's net change at the new head. The content the merge brought in from main (PR #54 and PR #57) was reviewed under those PRs and was not re-reviewed here.
- **Coverage evidence:** exact-head local coverage for `5d58264e93a2` (3282 passed, 1 skipped) on a clean tree; the provenance `check` passed. Rows for `triggarr/search/outcome.py` were given to the test-sufficiency lane; the template has no coverage rows.
- **Agents (7):** bugs (opus), security, architecture (opus), impact, test-sufficiency, compliance, language-python. Vibe-check's own Codex lane was skipped (`unauthenticated`); the paired Codex review is separate and complete.
- **Git-safety gate:** rc 0. The guard refused six agent commands (a `git diff` with a shell variable, a `uv run`, a file redirect, a `ruff` run and two `awk` calls); the repository was untouched.

| Found | Reported | Filtered |
|---|---|---|
| 3 | 0 | 3 sub-threshold |

## Resolved on recheck

- Pass 1's Medium, `cycle_grade.html:24`, "Card template's switch to structured reason kinds has no measured or diff-visible rendering test": the test-sufficiency lane answered "resolved". Its reason: the existing tests in `tests/test_app_cards.py` render the real card partial and exercise the template's unevaluated, malformed and other branches and the `skip_count` sum. It re-filed the remaining gap as the low-severity item below.

## Filtered (sub-threshold)

- test-sufficiency cov-001, `cycle_grade.html:20`: no test uses a failure reason whose wording looks like a skip or a not-evaluated message, which is the case the old wording check got wrong. A later return to wording-based matching would not be caught.
- architecture arch-001, `outcome.py:267`: the reason-kind names are plain string literals where the module's grades use named constants.
- test-sufficiency cov-002, `outcome.py:273`: the tampered-entry guards in two loops never run in tests. Not changed by this PR.

## Bottom line

No product defect. Bugs and impact each confirm the card groups rows as before for every input the application produces. Bugs, impact and BM also describe one difference as a correction: under the old wording check, a failure reason whose truncated text ended in "skipped" would have been counted as a skipped record.
