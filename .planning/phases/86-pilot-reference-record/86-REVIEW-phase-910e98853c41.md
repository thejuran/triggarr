---
phase: 86-pilot-reference-record
reviewed: 2026-11-14T16:31:37Z
head: 910e98853c41a8ac0086d110f4bc1fb26b816b4b
diff_base: origin/main
depth: standard
iteration: 5
files_reviewed: 9
files_reviewed_list:
  - CLAUDE.md
  - docs/review-checkpoint-record.md
  - docs/review-classification-policy.md
  - docs/bm-greptile-codex-blueprint.md
  - docs/buildomator-greptile-pilot.md
  - docs/ci-reference-baseline-plan.md
  - docs/review-workflow-adoption.md
  - .planning/phases/86-pilot-reference-record/86-publication-gate.sh
  - .planning/phases/86-pilot-reference-record/86-publication-gate-selftest.sh
findings:
  critical: 0
  warning: 0
  info: 2
  total: 2
status: issues_found
---

# Phase 86: Code Review Report (iteration 5)

**Reviewed:** 2026-11-14T16:31:37Z
**Head:** `910e98853c41a8ac0086d110f4bc1fb26b816b4b` (branch `phase-86-pilot-reference-record`, diff base `origin/main`)
**Depth:** standard (requested standard, ran standard)
**Iteration:** 5 (fresh review after fix round 4)
**Files Reviewed:** 9
**Status:** issues_found (info only; no critical and no warning finding)

## Summary

No critical finding and no warning. Nothing needs fixing under the stopping rule.

Both round-4 fixes work as claimed and fail closed. Iteration 4's WR-01 is resolved. No check that passed or blocked correctly at the iteration-4 head does the opposite at this head, in any case this review ran.

Two info items are recorded for the backlog. Both are limits of the byte-wise search that do not apply to this machine or to the files this phase publishes.

Scope confirmed from the diff between the two heads (Codex output folder excluded): the only files changed since iteration 4 are the two scripts, the evidence file (one added hand-review line), the iteration-4 report and the round-4 fix report. None of the seven instruction documents changed, so iteration 4's clean result for them stands and they were read again only for context.

Self-test, run as asked with the system bash (version 3.2): last line `selftest: 57 passed, 0 failed`.

### Iteration-4 warning: resolved

| ID | Result | How checked |
|---|---|---|
| WR-01 | Resolved. The script sets the C locale at `:16`, before any search, so a byte that is not valid UTF-8 no longer hides the rest of its line. | Gate `:16`; self-test `:85-90`. All four iteration-4 reproductions now block with the correct message. Further cases run by this review are listed below. |

### Round-4 fixes: both work as claimed

**Byte-wise search (gate `:16`).** Run in throwaway repositories under a temp directory, every fixture staged, system bash 3.2:

| Case | Result |
|---|---|
| Local user name in the other letter case, after two invalid bytes on the same line | blocks (user name check) |
| Local host name in the other letter case, after two invalid bytes | blocks (host name check) |
| Mixed-case private-network host suffix after an invalid byte | blocks (public-infrastructure check) |
| User name between valid accented letters | blocks |
| User name directly after a single legacy-encoded byte | blocks |
| 32-character hex value directly after a cut-off three-byte character | blocks |
| 32-character hex value directly before an invalid byte | blocks |
| User name after a byte-order mark | blocks |
| User name after a NUL byte; local path after a NUL byte and an invalid byte | both block |
| 32-character hex value before a Windows line ending | blocks |
| User name on a last line with no newline | blocks |
| User name at the end of a 300 KB single line, after an invalid byte | blocks |
| Clean text with valid accented letters and a dash character | passes |
| Clean line holding only invalid bytes | passes |

**Symbolic links (gate `:36-44`).**

| Case | Result |
|---|---|
| Staged link to a clean file | blocks, link named |
| Staged dangling link whose link text looks like a local path | blocks, link named |
| Staged link with a space in its name | blocks, full name printed correctly |
| Index holds a regular file, working tree holds a link (not staged) | blocks |
| Index holds a link, working tree holds a regular file (not staged) | blocks |
| Index-only link (mode 120000 written directly, working copy a regular file) | blocks |
| Staged link to a directory | blocks |
| Staged link matching the review-report name pattern | blocks |
| A covered directory that is itself a staged link | blocks |
| Two staged links | both named |
| Link that is not staged | blocks earlier, as "not staged" |
| Staged link outside the covered locations | passes (correct: not covered) |
| Hard link (a regular file to git) | passes (correct) |

The fifth and sixth rows exercise the index-mode half of the check, which has no self-test case of its own (already known and accepted); it works.

Fail-closed reading of the new block: a failure of the mode listing blocks (`:38`); the list is NUL-separated, so no file name can split or merge entries; the mode is taken before the first space and the path after the first tab, which is correct for names containing spaces or tabs; the check runs before any content scan, so nothing is read through a link first.

### Checks that came back clean

- **No regression on the real published set.** On a clean copy of this exact head (a local clone, so the working tree was clean), the gate at this head and the gate from the iteration-4 head gave identical output: the same four files listed by the public-infrastructure check, each with an accepted hash-matching entry, then `publication gate: PASS (83 tracked artifacts)`, exit 0. Every tracked file in the phase folder has a regular-file mode; none is a link.
- **Case-insensitive matching under the C locale.** The five existing letter-case self-test cases pass, and the swapped-case cases above pass with invalid bytes on the same line. All patterns and both local names are plain ASCII, so byte-wise case folding covers them fully.
- **Hand-review section parser (awk) under the C locale.** An accepted entry for a file whose name has accented letters passes, and blocks once that file changes; an accepted entry with accented letters in its reason passes; a rejected entry on a line next to invalid bytes still blocks. Prefix and length comparisons are byte-wise on both sides, so they stay consistent.
- **Hashing.** Hash-bound entries pass with the current hash and go stale after a change, as before. The hash tool reads bytes and is not affected by the locale.
- **Messages and exit codes.** Unchanged for every pre-existing case run: clean set, upper-case network word, unreviewed 32-character hex value, unreadable file (search error, exit 2 path), run from a subdirectory (no tracked artifacts).
- **bash 3.2.** `bash -n` is clean on both scripts. The constructs added in round 4 (`$'\t'` inside a parameter expansion, `"${@:2}"` with no extra arguments, NUL-delimited `read`) behave correctly on the system bash 3.2; the self-test and every case above ran under it.
- **Linux, by reading.** The added lines use only POSIX test operators, bash parameter expansion and `git ls-files -s -z`, whose output format is the same on every platform. Under the C locale GNU grep treats every byte as a character, so it neither skips invalid bytes nor reports an encoding error. Not executed on Linux by this review.
- **Self-test additions.** Each of the five new cases blocks for the reason in its name (the expected message is checked, not only the exit code). The fix report's before/after counts (52+4 failing, then 56; 56+1 failing, then 57) are consistent with the diff.
- **Private details in the changed files.** A byte-wise, case-insensitive search of both scripts for the local user name, the local host name, home-directory paths, private-network names, private address ranges and storage-volume paths found only the gate's own search pattern (`:71`) and the self-test's placeholder fixtures. No real value. The round-4 fix report and the iteration-4 report are inside the covered set and passed the gate run described above.
- **Instruction documents.** Unchanged since iteration 4 (confirmed from the diff), which found them clean.

## Narrative Findings (AI reviewer)

## Info

### IN-01: Byte-wise matching ignores letter case for unaccented letters only

**File:** `.planning/phases/86-pilot-reference-record/86-publication-gate.sh:16,86,87`
**Issue:** Under the C locale the case-insensitive option folds only the letters a to z. A local user name or host name that contains an accented letter, appearing in a covered file in the other letter case, is no longer matched; before round 4 it was (checked with a placeholder word: found under a UTF-8 locale, not found under the C locale). The same name in its own letter case still matches. This is a narrow trade made by the round-4 fix, not a defect in this phase: both local names on this machine are plain ASCII (checked), and all fixed patterns are ASCII. It matters only if the script is reused on a machine whose user or host name has an accented letter. Classified info as a portability note; no accidental path to it exists in this phase's workflow.
**Fix:** None needed here. If the script is reused elsewhere, add a note to the header, or run the two name checks a second time under the caller's locale and block on a hit from either run.

### IN-02: Text stored two bytes per character is not searched

**File:** `.planning/phases/86-pilot-reference-record/86-publication-gate.sh:71,86,87,88`
**Issue:** A file saved in a two-byte encoding (as some Windows tools write) has a NUL byte between letters, so none of the four pattern checks match it. This is unchanged by round 4: the result is the same under a UTF-8 locale and under the C locale (checked with a placeholder path). The tools that write this phase's covered files (the review agents and the Codex runner on this machine) write UTF-8, so there is no plausible accidental path in this workflow. Classified info as coverage expansion.
**Fix:** Optional: block any covered file that contains a NUL byte unless it has a hand-review entry.

## Convention (advisory, non-blocking)

The convention checker ran and returned the same file-name-casing items as in iterations 2 to 4 ("should be camel") for the Markdown files. The rule packs apply to JS/TS sources; `CLAUDE.md` is a fixed name and every file in `docs/` is kebab-case. They are recorded as tool output only, are not counted in the totals, and no change is recommended.

## Set aside (needs ruling)

None new. Iteration 4's SA-01 (the 32-character hex check is lowercase only, as the Codex contract defines it) is already known and accepted and is not re-reported.

## Limits of this review

- The gate at this head was run against the committed content of this head in a clean copy, not in the working repository: while this review ran, untracked Codex output files for this head were present under a covered location, and the gate correctly blocked there as "not staged". Those files, and this report, have not been scanned by this review.
- Linux behaviour was assessed by reading, not by running.
- The full test suite was not run by this review; the fix report records it passing.

---

_Reviewed: 2026-11-14T16:31:37Z_
_Head: 910e98853c41a8ac0086d110f4bc1fb26b816b4b_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
_Iteration: 5_
