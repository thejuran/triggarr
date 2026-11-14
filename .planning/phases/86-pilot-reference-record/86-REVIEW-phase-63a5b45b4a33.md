---
phase: 86-pilot-reference-record
reviewed: 2026-11-14T00:00:00Z
iteration: 6
head: 63a5b45b4a33ae84e7a34313d05275812d4d4650
previous_head: 910e98853c41
diff_base: origin/main
depth: standard
files_reviewed: 2
files_reviewed_list:
  - .planning/phases/86-pilot-reference-record/86-publication-gate.sh
  - .planning/phases/86-pilot-reference-record/86-publication-gate-selftest.sh
findings:
  critical: 0
  warning: 0
  info: 2
  total: 2
status: issues_found
---

# Phase 86: Code Review Report (iteration 6)

**Reviewed:** 2026-11-14
**Head:** 63a5b45b4a33ae84e7a34313d05275812d4d4650
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found (info only; 0 critical, 0 warning)

## Summary

Scope confirmed. Between the iteration 5 head (910e988) and this head, excluding the
Codex evidence directory and the review reports, exactly two files changed: the
publication gate (16 lines) and its self-test (2 lines). No instruction document under
`docs/` and no `CLAUDE.md` changed.

The change under review is the superseded-entry rule in `reviewed()`: an older accepted
hand-review line for the same path (same form, a well-formed 64-hex sha256, the
section's accepted disposition) is now skipped instead of blocking, and the function
takes the hash and the disposition as separate arguments.

No defect was found by which an accidental private detail in a covered, staged, regular
file gets a PASS. The fix works as claimed, there is no regression, and no error path
fails open. Two info items follow; one behavior is set aside for an owner ruling.

## Narrative Findings (AI reviewer)

### What was verified, and how

**Self-test.** Run against the gate at this head. Last line:
`selftest: 58 passed, 0 failed`.

**Reproduction.** 44 additional cases were run through the real gate in throwaway
repositories under a temporary directory (22 per section, for both the
Public-infrastructure and the Credential-shape section, plus two cross-section cases).
Every case produced the expected result.

Cases that must pass, and did:

- fresh accepted entry with the current hash only
- older accepted entry followed by a fresh accepted entry
- fresh accepted entry followed by an older accepted entry (order does not matter)

Cases that must block, and did (each in both sections):

- no entry at all for the path
- only an older accepted entry, file changed since (the older entry does not excuse it)
- older accepted entry plus a rejected line carrying the current hash
- fresh accepted entry plus a rejected line with no hash
- fresh accepted entry plus a pending line
- fresh accepted entry plus a rejected line carrying an older hash
- fresh accepted entry plus an accepted-wording line with no hash
- older accepted entry plus a current-hash line with no reason
- current-hash line with no reason, alone, with and without trailing blanks
- fresh accepted entry plus an older line whose hash is upper-case, 63 characters,
  65 characters, contains a non-hex character, lacks the closing backtick, carries a
  different hash label, or has a truncated disposition
- a line whose hash field is the current hash with one extra leading character
- cross-section: the other section's accepted wording is not accepted, neither as the
  fresh entry nor as a superseded one

### Checks that came back clean

- **A file with no entry matching its current hash still blocks.** `ok` is set only by
  the full-prefix comparison, which includes the current hash. The superseded branch
  only skips a line; it never sets `ok`.
- **Rejected, pending, hash-less and reason-less lines still block.** Rejected, pending
  and hash-less lines fail the superseded shape test and set `bad`. A reason-less line
  with the current hash is skipped rather than marked bad, but it cannot set `ok`, so
  on its own it still blocks (see IN-02 for the one observable difference).
- **An older accepted entry does not excuse a changed file by itself.** Confirmed in
  both sections.
- **The Credential-shape section behaves the same as the Public-infrastructure one.**
  Both call the same function; the only difference is the disposition argument, and
  all 22 per-section cases agree.
- **Substring arithmetic.** The label is 9 bytes, so the hash occupies bytes 10 to 73 of
  the remainder and the disposition starts at byte 74, which is what
  `length(h) + 1` and `length(h) + 65` compute. The explicit `length(o) == 64` test
  rejects a short line, and a 65-character hash fails because byte 74 is then not the
  closing backtick. Comparisons are plain string comparisons, so characters in a path
  that are special in a regular expression have no effect. Values arrive through
  `ENVIRON`, which is not escape-processed, so a backslash in a path is taken
  literally. The bracket range in the hex test is unambiguous under the C locale.
- **Variable names.** The new `H` and `D` are set only in the environment of the awk
  process. The awk variables `h`, `d` and `r` are separate from the shell variables of
  the same names (host name, phase directory, exit status), which are unchanged after
  the call.
- **Call sites.** Both pass the validated 64-hex hash and the disposition with its
  trailing blank; the exit-status handling after each call is unchanged.
- **Existing self-test cases remain meaningful.** The stale-hash cases still fail for
  the asserted reason; they now exercise the superseded branch with `ok` unset rather
  than `bad`, and the asserted message is the same. No case passes vacuously because of
  the change.
- **The new case tests what it claims.** It records an entry, changes the file, records
  a second entry with the new hash, stages everything and expects a pass. Against the
  iteration 5 gate the first entry sets `bad`, so the case would have failed there.
  Its blocking counterpart (same setup without the second entry) is the case directly
  above it.

**Limit of verification:** the reproduction ran on the BSD awk shipped with the review
machine only. No GNU awk was installed, so GNU behavior was checked by reading: the
function uses only `substr`, `length`, `ENVIRON`, string equality and one bracket
expression, all specified by POSIX and byte-oriented under the C locale the script
exports.

## Info

### IN-01: The superseded rule is pinned by one passing case in one section only

**File:** `.planning/phases/86-pilot-reference-record/86-publication-gate-selftest.sh:72-73`
**Issue:** The self-test covers the rule once, in the Public-infrastructure section,
for the passing direction. Nothing pins (a) the same rule in the Credential-shape
section, (b) that an older accepted entry beside a current-hash line with no reason
still blocks, or (c) that an older line with a malformed hash (wrong length or
upper-case) beside a fresh entry still blocks. All three behave correctly today (see
the reproduction list), but a later edit to the shape test could loosen them without
any self-test case failing.
**Fix:** Add three cases, for example after line 53 for the credential section
(`cacc` again after the file change, stage, expect pass), and in the public section an
older entry plus `acc ""` expecting a block, and a fresh entry plus an older line with a
63-character hash expecting a block.

### IN-02: "A different sha256" is documented but not checked

**File:** `.planning/phases/86-pilot-reference-record/86-publication-gate.sh:60-61,68-69`
**Issue:** The header comment says a superseded entry has "a different well-formed
sha256". The code does not compare the older hash with the current one. The only line
this affects is an accepted-wording line carrying the current hash with an empty
reason: it used to set `bad` and now is skipped. On its own it still blocks. Beside a
complete accepted entry for the same hash it now passes where iteration 5 blocked.
No private detail can pass this way, because a complete, reasoned entry for the exact
current content is still required.
**Fix:** Either reword the comment to "any well-formed sha256", or add
`&& o != ENVIRON["H"]` to the condition on line 69 so a reason-less current-hash line
keeps blocking as before.

## Set aside (needs ruling)

### SA-01: An older rejected line keeps blocking after a later accepted re-review

**Where:** `.planning/phases/86-pilot-reference-record/86-publication-gate.sh:68-70`
**Why excluded:** This is the documented behavior ("any other line ... blocks") and it
fails closed, so it is not a defect under the gate's threat model. It is raised because
the change under review made the accepted-then-re-reviewed flow work without editing
old lines, and the rejected-then-fixed flow does not get the same treatment.
**Effect if left as is:** If a file is first recorded as rejected or withheld, then
redacted and re-reviewed as accepted, the gate keeps blocking until the author deletes
or rewrites the old rejected line. The message shown is "no accepted entry", which does
not point at the old line as the cause.
**Needs:** Owner ruling: accept as is (the safest reading), or allow a rejected line
bound to an older hash to be superseded the same way, or keep the block and name the
conflicting line in the message.

---

_Reviewed: 2026-11-14_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
_Iteration: 6, head 63a5b45b4a33ae84e7a34313d05275812d4d4650_
