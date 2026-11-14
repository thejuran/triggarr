---
phase: 86-pilot-reference-record
reviewed: 2026-11-14T16:23:02Z
head: 17eb05200e4804b300164bd7b7e987e3ba1b4771
diff_base: origin/main
depth: standard
iteration: 4
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
  warning: 1
  info: 3
  total: 4
status: issues_found
---

# Phase 86: Code Review Report (iteration 4)

**Reviewed:** 2026-11-14T16:23:02Z
**Head:** `17eb05200e4804b300164bd7b7e987e3ba1b4771` (branch `phase-86-pilot-reference-record`, diff base `origin/main`)
**Depth:** standard (requested standard, ran standard)
**Iteration:** 4 (fresh review after fix round 3)
**Files Reviewed:** 9
**Status:** issues_found

## Summary

No application code changed. All five iteration-3 warnings are resolved at this head, and the round-3 fixes introduced no regression that this review could find. No critical finding.

One warning remains, in the publication check script. It was already present at the iteration-3 head and was not caused by round 3:

- On this machine the script's text searches stop reading a line at the first byte that is not valid UTF-8. A private detail later on that line (the local user name, the local host name, a home-directory path, a 32-character hex value) is not found and the script prints PASS (WR-01). Reproduced. A one-line change fixes it and was verified.

It is latent at this head: all 76 tracked covered files are valid UTF-8, and a byte-wise re-run of the four pattern checks over them gives exactly the same file lists as the script does.

Three info items go to the backlog under the stopping rule. One item is set aside for a ruling.

Self-test, run as asked: last line `selftest: 52 passed, 0 failed`. The real check was not run for a PASS result, as instructed (this report is untracked and correctly makes it block).

### Iteration-3 warnings: all resolved at this head

| ID | Result | How checked |
|---|---|---|
| WR-01 | Resolved. The trusted-head limit is stated in all six places that state the automatic start, with the same meaning in each. | `CLAUDE.md:101-106`; record `:128`; pilot doc `:56,83`; blueprint `:47`; guide `:87`. The trust test the sentence points to exists (contract step 2, `:90-92`) and treats a bot branch inside this repository as untrusted, so "bot, fork or other untrusted head" is decidable. |
| WR-02 | Resolved. A covered file that is in the working tree but not in the index blocks and is named. | Gate `:20,28-33`. Reproduced blocking for: an untracked file, a locally ignored file, a file in a covered subdirectory, an untracked evidence file, an untracked fix report, a file removed from the index only. An intent-to-add file also blocks. |
| WR-03 | Resolved. The default report name is in the covered list. | Gate `:20`; self-test `:102-104`. A missing default-named file does not cause an error. |
| WR-04 | Resolved. The three name checks ignore letter case. | Gate `:60,75,76`; self-test `:37-41`. No new hit in the real covered set (the same three files that have hand-review entries; user name and host name: none). |
| WR-05 | Resolved. A credential-shape entry is bound to the file's current SHA-256. | Gate `:81-82`; self-test `:47-53`. Reproduced: an accepted, hash-bound entry passes; the same file changed and staged afterwards blocks. A 64-character hash written in a covered file is not itself a 32-hex hit. |

### Checks that came back clean

- **Rules 1 to 5.** The six changed sentences agree with the owner's rule 2 as extended in round 3: no automatic start on a bot, fork or other untrusted head; that head is never checked out or executed; the vibe-check is recorded as required and not yet run (pending); the owner is asked. Nothing else in the seven files changed since iteration 3 (confirmed from the diff between the two heads), so iteration 3's statement-by-statement result for rules 1, 3, 4 and 5 stands. Rule 5: the Deep Code Review Convention section of `CLAUDE.md` is still not in the diff against `origin/main`.
- **Consistency with the existing untrusted-head rules.** The new sentence does not contradict record `:131` (head never checked out or executed), contract `:160` (no session inside a checkout of an untrusted head) or record `:64-66` (status values; one run serves both purposes; the fallback half still needs approval). No protection was weakened: before round 3 an agent could read the text as permission to start a tool-enabled review on an untrusted head; now it cannot.
- **Status wording.** `CLAUDE.md` and the record use the record's own status value; the blueprint, pilot doc and guide use plain wording with the same meaning.
- **Doc-guard tests.** The four doc-guard test files that read these documents pass (53 passed). The full suite was not run by this review.
- **Private details in the changed files.** A byte-wise, case-insensitive search of the seven docs, the UAT file and the two scripts for the local user name, the local host name, home-directory paths, private-network names, private address ranges and storage-volume paths found only the check's own pattern (gate `:60`) and the self-test's placeholder fixtures. No real value. All ten files are valid UTF-8.
- **Gate, fail-closed paths re-checked after round 3.** An unstaged edit to the evidence file blocks; a 32-hex value inside the evidence file blocks; a file containing a NUL byte is still searched; a file name with a non-ASCII letter or a space is handled; running from a subdirectory blocks ("no tracked review artifacts"); a trailing slash on the phase directory argument works. The `--others` listing uses the same location list as the tracked listing (gate `:20`), so the two cannot drift apart.
- **Self-test.** The new cases fail for the stated reason, not by accident: every hash-bound credential fixture carries the file's current hash, so each blocking case tests the rule in its name. `bash -n` is clean on both scripts.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: A byte that is not valid UTF-8 hides the rest of its line from all four pattern checks

**File:** `.planning/phases/86-pilot-reference-record/86-publication-gate.sh:35,60,77` (the three `grep` calls; no locale is set anywhere in the script)
**Issue:** The script runs under the caller's locale, which is a UTF-8 locale on the owner's machine. The system `grep` there (the BSD one) stops matching a line at the first byte sequence that is not valid UTF-8. Anything after that point on the same line is not searched. The script exits 0 and prints PASS; no error is raised, so the fail-closed error handling at `:36-38`, `:62` and `:78` never triggers.

This is not deliberate evasion and not an encoded value: the private detail is in plain text. The causes are ordinary: a file or log line in a legacy single-byte encoding (one accented letter is enough), or a multi-byte character cut in half when a tool truncates output at a byte limit. The covered set holds exactly that kind of material (captured test output, prompts that embed file contents, and transcripts whose lines are each one very long record, so one bad byte hides the remainder of a whole record).

Reproduced in throwaway repositories, each fixture staged, each result `publication gate: PASS (4 tracked artifacts)`, exit 0:

- a line with two invalid bytes followed by the local user name;
- the same with the local host name;
- the same with a home-directory path;
- the same with a 32-character lowercase hex value.

Direct test of `grep` with placeholder words: a line starting with a legacy-encoded accented letter, and a line starting with a truncated three-byte character, were both skipped; the same text on the following line, or before the bad byte, was found.

Not a round-3 regression: the iteration-3 copy of the script gives the same four PASS results. It is reported now because it meets the stopping rule's class (b): an accidental private detail in a covered, staged file gets a PASS. The gitleaks step does not cover it, because user names, host names and paths are not gitleaks findings.

Latent at this head: all 76 tracked covered files are valid UTF-8, and the four pattern checks give identical file lists with and without the fix below.

**Fix:** Make the searches byte-wise. One line after gate `:14`:

```bash
export LC_ALL=C   # search bytes, not characters: a byte that is not valid UTF-8 must not hide the rest of its line
```

Verified on a patched copy: all four reproductions block with the correct message; the user name next to a non-ASCII letter still blocks in either letter case; the self-test gives `selftest: 52 passed, 0 failed`; hash-bound entries still pass and go stale as before. Add two self-test cases, for example:

```bash
fresh; printf 'bytes \377\376 then %s\n' "$(whoami)" >> "$r/$p/codex/a1.txt"; ( cd "$r" && git add -A )
expect "user name after an invalid byte on the same line blocks" block "local user name check: matching"
fresh; printf 'bytes \377 see /ho''me/someone/x\n' >> "$r/$p/vibe-check/v.md"; ( cd "$r" && git add -A )
expect "local path after an invalid byte on the same line blocks" block "public-infrastructure check: matching"
```

(The path fixture above is split in two only so that this report does not itself match the check; write it normally in the self-test.)

## Info

### IN-01: The "not staged" message offers only one way out, staging the file

**File:** `.planning/phases/86-pilot-reference-record/86-publication-gate.sh:31,33`
**Issue:** Since round 3 any unstaged file under a covered location blocks, and the message says to stage it with `git add -f`. For a file that is deliberately withheld (the fix report's "Left for a ruling" item 1 describes such a transcript) the right action is the opposite: move it out of the covered location. Following the message stages the file; the check then blocks on its content, so nothing leaks, but the author is sent the wrong way first.
**Fix:** Extend the message: "stage it with git add -f, or move it out of the covered locations if it is withheld, then re-run".

### IN-02: Two short pointers still state the high-risk run without the trusted-head limit

**File:** `CLAUDE.md:53-55`; `docs/ci-reference-baseline-plan.md:5`
**Issue:** `CLAUDE.md:53-55` asks for "a record that it ran and where its report is" whenever risk is high; on an untrusted head the record is the pending status instead. The CI plan's dated note says "Claude runs it". Both are pointers: the full rule with the limit is in the same file (`CLAUDE.md:101-106`) or is the named target of the note, so an agent reading the rule itself is not misled.
**Fix:** `CLAUDE.md:54-55`: "...the required vibe-check (RISK-02) with its recorded status (ran, with the report location, or pending)". CI plan `:5`: "...and Claude runs it on trusted heads".

### IN-03: The text does not say what ends the pending state on an untrusted head

**File:** `docs/review-checkpoint-record.md:128`; `CLAUDE.md:103-106`
**Issue:** On an untrusted high-risk head the agent's own steps are fully determined (do not start, record pending, ask). What follows is not written: the same paragraph says the vibe-check is "required, not a recommendation the owner may decline" and that a pending one "blocks acceptance", while the untrusted-head rules forbid running it inside a checkout of that head. The owner's available choices (for example a run that receives the diff as text only) are left to the answer at the time. This is the conservative reading the fix report already lists for the owner's confirmation.
**Fix:** When the owner confirms the wording, add one clause naming the choices, or state that the owner's answer is recorded in the Vibe-check status field for that head.

## Convention (advisory, non-blocking)

The convention checker ran and returned the same file-name-casing items as in iterations 2 and 3 ("should be camel") for the Markdown files. The rule packs apply to JS/TS sources; `CLAUDE.md` is a fixed name and every file in `docs/` is kebab-case. They are recorded as tool output only, are not counted in the totals, and no change is recommended.

## Set aside (needs ruling)

### SA-01: The 32-hex check is lowercase only

**Where:** `.planning/phases/86-pilot-reference-record/86-publication-gate.sh:77`
**Why excluded:** The contract defines this check as a scan for "32-character lowercase hex strings, the shape of Radarr/Sonarr API keys" (`docs/codex-adversarial-review-contract.md:137`). The script implements that definition; widening it is a scope decision. Round 3 made the three name checks ignore letter case and left this one as defined.
**Effect if left as is:** Reproduced: an upper-case and a mixed-case 32-character hex value, staged in a covered file, each gave PASS. The two services this project talks to issue lowercase keys, so the practical exposure is a key of that length from some other service. A search of the real covered set in any letter case found none.
**Needs:** Ruling from the owner: match any letter case (changes the contract's definition too) / defer / accept.

---

_Reviewed: 2026-11-14T16:23:02Z_
_Head: 17eb05200e4804b300164bd7b7e987e3ba1b4771_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
_Iteration: 4_
