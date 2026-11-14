---
phase: 86-pilot-reference-record
fixed_at: 2026-11-14
review_path: 86-REVIEW-phase-17eb05200e48.md (BM iteration 4) and codex/17eb05200e48-phase-a1.last.json (paired Codex pass)
iteration: 4
findings_in_scope: 2
fixed: 2
skipped: 0
rejected: 0
status: all_fixed
---

# Phase 86: Code Review Fix Report (iteration 4)

**Source reviews:** BM iteration 4 report and the paired Codex report, both on head `17eb052`
**Iteration:** 4
**Scope given for this round:** BM WR-01 and Codex F001 only. Files changed: the publication gate script and its self-test, nothing else.

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0
- Rejected: 0

## Fixed Issues

### WR-01 (BM): A byte that is not valid UTF-8 hides the rest of its line from the pattern checks

**Files modified:** `86-publication-gate.sh`, `86-publication-gate-selftest.sh`
**Commit:** 37143ab
**Applied fix:** The gate now sets `LC_ALL=C` near the top, so every search and text comparison works on bytes. Four self-test cases were added first: invalid bytes followed on the same line by a local path, by a 32-character hex value, by the local user name, and by the local host name.
**Test-first evidence:** Against the unchanged gate the four new cases failed because the gate exited 0 (`selftest: 52 passed, 4 failed`). After the fix: `selftest: 56 passed, 0 failed`. The five existing letter-case cases still pass under the C locale.

### F001 (Codex): A covered symbolic link is scanned through its target, but git publishes the link text

**Files modified:** `86-publication-gate.sh`, `86-publication-gate-selftest.sh`
**Commit:** 7183a50
**Applied fix:** The gate lists the index modes of the covered paths and blocks any path that is a symbolic link in the working tree or has symlink mode (120000) in the index. Each one is named with the message "covered file is a symbolic link; publish a regular file". A failure of the listing command blocks too. One self-test case was added first: a staged symbolic link in a covered location pointing at a clean file.
**Test-first evidence:** Against the gate before this fix the new case failed because the gate exited 0 (`selftest: 56 passed, 1 failed`). After the fix: `selftest: 57 passed, 0 failed`.

## Checks after both fixes

- Self-test: `selftest: 57 passed, 0 failed`, exit 0.
- Real gate from the repository root, before this report was added: `publication gate: PASS (82 tracked artifacts)`, exit 0. It printed the four files with public-infrastructure hits; each has an accepted, hash-matching hand-review entry.
- Test suite: `3282 passed, 1 skipped, 38 warnings`.

## Not in scope this round

- Codex F002 (plan files still show the older hand-review entry format) was not part of this round's instructions and is untouched.
- BM info items IN-01 to IN-03 and the set-aside item SA-01 (32-hex check is lowercase only, needs the owner's ruling) are untouched.

## Notes

- Both fixes are of the logic class that syntax checks cannot prove. They are covered by the new self-test cases, each shown failing before its fix and passing after.
- Limit of the symbolic-link check: it covers the paths git lists under the covered locations. It follows the script's stated threat model (accidental publication, not deliberate evasion).

---

_Fixer: Claude (bm-code-fixer)_
_Iteration: 4_
