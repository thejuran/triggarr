---
phase: 86-pilot-reference-record
reviewed: 2026-11-14T16:12:00Z
head: 4066d538e12d38ab8612dc651965fbfb38dca2f5
diff_base: origin/main
depth: standard
iteration: 3
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
  warning: 5
  info: 6
  total: 11
status: issues_found
---

# Phase 86: Code Review Report (iteration 3)

**Reviewed:** 2026-11-14T16:12:00Z
**Head:** `4066d538e12d38ab8612dc651965fbfb38dca2f5` (branch `phase-86-pilot-reference-record`, diff base `origin/main`)
**Depth:** standard (requested standard, ran standard)
**Iteration:** 3 (fresh full review after fix round 2)
**Files Reviewed:** 9
**Status:** issues_found

## Summary

No application code changed. The seven instruction and policy files now state the owner's five-point rule consistently, and every iteration-2 finding is resolved. No blocker was found.

Five warnings remain. One is in the instruction text and four are in the publication check script:

- The new "Claude starts it automatically, without asking" rule has no exception for untrusted heads (bot, fork, non-owner), where another rule forbids a tool-enabled review inside a checkout of that head (WR-01).
- The publication check passes without scanning a covered file that is not yet staged, which is the order the phase plans describe (WR-02).
- The publication check does not cover `86-REVIEW.md`, BM's default report name (WR-03).
- The user-name, host-name and public-infrastructure checks are case-sensitive, so a differently cased spelling passes (WR-04).
- The credential-shape hand-review entry is bound to the path only, so a file that changes after review still passes (WR-05).

Each of WR-02 to WR-05 was reproduced in a throwaway repository; the results are quoted in the finding. None of them is a leak at this head: the covered files, the seven docs and the scrubbed UAT file contain no private infrastructure details (see "Checks that came back clean").

Self-test, run as asked: last line `selftest: 38 passed, 0 failed`. The check itself, run on this repository at this head: `publication gate: PASS (68 tracked artifacts)`, after listing the two files that have hand-review entries.

### Iteration-2 findings: all resolved at this head

| ID | Result | Where checked |
|---|---|---|
| WR-01 | Resolved. The pilot record's Corrections section has entries 3 to 6 and the decisions log has the "who starts" row; the three pointers name the decision lines plus the Corrections section. | `86-PILOT-RECORD.md:472,664-708`; guide `:109`; blueprint `:47`; pilot doc `:36` |
| WR-02 | Resolved. Four status values, the "one run serves both" sentence, and "blocks acceptance" for a pending required run. | record `:64,66,128,181` |
| WR-03 | Resolved. Actor, timing and authorization are stated. New gap: WR-01 below. | `CLAUDE.md:71-72,98-101`; record `:128`; pilot doc `:56,83`; guide `:87`; blueprint `:47`; CI plan `:5` |
| IN-01 | Resolved. | blueprint `:47` |
| IN-02 | Resolved. | policy `:21` |
| IN-03 | Resolved. | guide `:20-21,27` |
| IN-04 | Resolved. | guide `:103` |
| IN-05 | Resolved. | guide `:59,61,136` |
| IN-06 | Resolved. | `CLAUDE.md:96-98`; record `:128` |
| IN-07 | Resolved. | record `:128` |
| IN-08 | Resolved. | guide `:85` |
| SA-01 | Resolved by a dated note; body unchanged. | CI plan `:5` |
| SA-02 | Ruled "no change". The Deep Code Review Convention section is not in the diff against `origin/main`. | `CLAUDE.md:24-39` |

The paired Codex findings of iteration 2 are also resolved: the staged-content check exists and is self-tested (gate `:77-82`, self-test `:78-80`).

### Checks that came back clean

- **Points 1 to 5, statement by statement.** Every statement in `CLAUDE.md` (`:53-55,71-72,93-106`), the checkpoint record (`:3,56-68,127-128,181`), the classification policy (`:14,15,21`), the pilot doc (`:36,56,83,85`), the guide (`:20,87,111-112,140`), the blueprint note (`:47`) and the CI plan note (`:5`) agrees with the owner's rule and with the pilot record's decision lines and Corrections entries 3 and 4 (`86-PILOT-RECORD.md:631-635,675-697`). No two statements contradict each other.
- **Against the two read-only documents.** `docs/codex-adversarial-review-contract.md:147-165` (fallback only after the retry, explicit `approve-fallback` naming the head, Codex stays INCOMPLETE) and `docs/owner-cli-acceptance.md:15` ("applicable vibe-check/UAT") are consistent with points 2 and 3, apart from WR-01.
- **Point 4.** Stated correctly in record `:3,195`, blueprint `:47`, guide `:112`.
- **Point 5.** `CLAUDE.md:24-39` is unchanged against `origin/main`, and no edited sentence speaks about the release-time offer.
- **No other protection weakened**, apart from WR-01: Codex pairing, classification, one record per head, frozen head, exact-commit acceptance and Greptile's optional status are unchanged in meaning in the diff.
- **Quoted phrases in the dated notes** exist in the text they supersede (blueprint `:103`; CI plan `:57,59,61`).
- **References.** Every relative link and named path in the seven files resolves to a tracked file; the guide's internal cross-references (`:20,55,91,111`) point at real items; step numbers in the guide agree (`:20-21,27`).
- **Private infrastructure details.** A case-insensitive search of the seven docs, the UAT file and the whole phase folder for home-directory paths, private-network names, private address ranges, storage-volume paths, the local user name and the local host name found only the check's own patterns and placeholders, prose that names the categories, and one version number. No real value.
- **Doc-guard tests.** The six doc-guard test files pass at this head (61 passed). The full suite was not run by this review.
- **Scripts.** `bash -n` is clean on both; both ran under bash 3.2 on macOS. Fail-closed behaviour was confirmed for: grep errors, missing or unreadable files, an empty list, a missing hashing tool, a missing or duplicated hand-review section, a stale entry next to a current one, a hit in the evidence file itself, file names with spaces or glob characters, and a staged file that differs from its working copy. Quoting is correct throughout the gate; `awk` compares with `substr`, not a pattern, and reads values from `ENVIRON`, so paths with special characters are safe. The hash binding of the public-infrastructure entry works as described: a changed file needs a new entry.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: The automatic high-risk vibe-check has no exception for untrusted heads

**File:** `CLAUDE.md:98-101`; `docs/review-checkpoint-record.md:128`; `docs/buildomator-greptile-pilot.md:83`; `docs/review-workflow-adoption.md:87`
**Issue:** The new rule is unconditional: at a high-risk checkpoint "Claude starts it automatically, right after the BM review and the paired Codex pass, on the same exact commit, without asking first". Three existing statements cover the same head when it comes from a bot, a fork or a non-owner author:

- record `:131`: for untrusted heads "the head is never checked out or executed".
- contract `:160`: the fallback reviewer is "Never a session opened inside a checkout of an untrusted head, and never run on the operator's machine with the untrusted head's code."
- record `:164`: vibe-check works in a review worktree ("copied to the vibe-check review worktree root").

High risk on such a head is realistic: the blueprint's guide rates "changes to safeguards/publication" high (`docs/bm-greptile-codex-blueprint.md:101`), and automated dependency updates change pinned workflow actions. `CLAUDE.md:105-106` also names bot/fork PRs as the standing case where Codex stays incomplete, and record `:66` then says the one automatic run "serves both purposes", which makes it the fallback review that contract `:160` restricts.

An agent can follow this two ways. It can start a multi-agent, tool-enabled review in a worktree of the untrusted head without asking, which is what the untrusted-head rules exist to prevent. Or it can hold back, leaving a required review unrun with no instruction telling it to. Before this PR the owner decided whether and how vibe-check ran on every such head; that decision point is now gone for high-risk ones.

**Fix:** State one behaviour. The conservative choice, in `CLAUDE.md` after "...where its report is;" and mirrored in record `:128`:

```markdown
On an untrusted head (bot, fork or non-owner author) Claude does not start it
automatically: it records REQUIRED, NOT YET RUN (PENDING) and asks the owner, and any
run stays within the untrusted-head limits of docs/codex-adversarial-review-contract.md
(no session inside a checkout of that head).
```

Which behaviour applies is the owner's decision; the text needs to say one.

### WR-02: The publication check passes without scanning a covered file that is not staged yet

**File:** `.planning/phases/86-pilot-reference-record/86-publication-gate.sh:15-19`
**Issue:** The file list comes from `git ls-files`, which lists the index only. `.planning/` is ignored in this checkout, so every new review artifact is untracked until it is added with `git add -f`. The phase plans say to run the check "immediately before every `git add -f`" (`86-03-PLAN.md:71`, `86-10-PLAN.md:67`). In that order the script scans the already-tracked files, prints PASS, and never reads the new file. Nothing in its output says a covered file was skipped.

Reproduced: with the evidence file present but untracked, the script reported `PASS (3 tracked artifacts)` instead of 4, and it still accepted a hand-review entry read from that untracked file. The staged-content check at `:80` cannot catch this, because the file is not in the list it compares.

**Fix:** Block when an untracked file exists under the covered paths (`--others` without `--exclude-standard` includes ignored files):

```bash
git ls-files -z --others -- "$d/codex" "$d/vibe-check" "$d/86-REVIEW*.md" "$d/86-PILOT-RECORD.md" > "$t/others" \
  || fail "git ls-files --others failed"
[ ! -s "$t/others" ] || { tr '\0' '\n' < "$t/others" >&2
  fail "untracked review artifacts listed above were not scanned: stage them with git add -f or move them out, then re-run"; }
```

Add a self-test case: an untracked file with a match under `codex/` blocks.

### WR-03: BM's default report file, `86-REVIEW.md`, is not covered by the check

**File:** `.planning/phases/86-pilot-reference-record/86-publication-gate.sh:15`
**Issue:** The pathspec is `86-REVIEW-*.md`. It needs a hyphen after `REVIEW`, so it does not match `86-REVIEW.md`, which is tracked (the iteration-1 report) and is the name BM writes by default (`docs/review-checkpoint-record.md:140`). That file is published and never scanned by any of the five checks.

Reproduced: a fixture `86-REVIEW.md` containing a home-directory path and the local user name gave `PASS (4 tracked artifacts)`.

At this head the real `86-REVIEW.md` holds one line (`:42`) that names a category with a word the public-infrastructure pattern matches; it is prose, not a real value.

**Fix:** Add `"$d/86-REVIEW.md"` to the pathspec list at `:15` (or change the glob to `86-REVIEW*.md`). The real file will then need one public-infrastructure hand-review entry for line 42. Add a self-test case with a match in `86-REVIEW.md`.

### WR-04: The user-name, host-name and public-infrastructure checks are case-sensitive

**File:** `.planning/phases/86-pilot-reference-record/86-publication-gate.sh:44,59,60`
**Issue:** All three use case-sensitive matching (`grep -lE`, `grep -l -F`). Reproduced, each giving `PASS (4 tracked artifacts)`:

- the local user name in upper case;
- the local host name in lower case, and in upper case. This machine's short host name contains upper-case letters, and the lower-case form is how a host name normally appears in DNS-style and private-network machine names;
- the capitalised spelling of the private-network product name the pattern lists in lower case, the capitalised spelling of the network word, and an upper-case host suffix.

The header (`:9`) says the user-name and host-name checks "have no exception". A differently cased spelling is an unintended one.

**Fix:**

```bash
px=$(grep -liE '<same pattern>' -- "${F[@]}"); r=$?      # line 44
nohit "local user name check" -i -F -e "$u"              # line 59
nohit "local host name check" -i -F -e "$h"              # line 60
```

A case-insensitive search of the covered files at this head finds no file beyond the two that already have entries, so this adds no new hand-review work now. Add self-test cases for an upper-case user name and a lower-case host name.

### WR-05: A credential-shape hand-review entry still passes after the file changes

**File:** `.planning/phases/86-pilot-reference-record/86-publication-gate.sh:65` (format at `:32-33`)
**Issue:** The public-infrastructure entry is bound to the file's SHA-256, so a changed file needs a fresh review. The credential-shape entry is bound to the path only. Once a file has an accepted entry, any 32-character hex value added to it later passes that check. This is the check for unprefixed API keys, which the contract says pattern scanners easily miss (`docs/codex-adversarial-review-contract.md:137`), so gitleaks is not a reliable second line. The covered set includes files that are edited repeatedly (`86-PILOT-RECORD.md`, `86-REVIEW-EVIDENCE.md`, the fix reports).

Reproduced: a file with an accepted entry passed; a second, different 32-character hex value was appended and staged; the result was still `PASS (4 tracked artifacts)`.

Latent at this head: the real section reads "none", so no file is currently excused.

**Fix:** Bind the entry to the hash the same way, reusing `sha`:

```bash
s=$(sha "$x"); [[ "$s" =~ ^[0-9a-f]{64}$ ]] || fail "32-hex hit: cannot hash: $x"
reviewed "$x" "Credential-shape hand review" " sha256 \`$s\`: not a credential -- "; r=$?
```

Update the format comment (`:32-33`), the header (`:6-8`) and the self-test's credential entries, and add a case "entry for a file changed since review blocks". No existing entry needs migrating.

## Info

### IN-01: Git's per-file "assume unchanged" flag hides a staged difference from the last check

**File:** `.planning/phases/86-pilot-reference-record/86-publication-gate.sh:80`
**Issue:** `git diff` skips files flagged with `git update-index --assume-unchanged` (and skip-worktree). Reproduced: a staged match, the flag set, the working copy redacted, result PASS. This needs a deliberate, unusual command, so it is not a routine path.
**Fix:** Compare content directly, for example `git ls-files -s` blob ids against `git hash-object` of each working file, or block when `git ls-files -v` shows a lower-case or `S` tag for a covered file.

### IN-02: Two operating rules of the hand-review section are enforced but not written down

**File:** `.planning/phases/86-pilot-reference-record/86-publication-gate.sh:27-34`
**Issue:** Both fail closed, so neither can leak, but each will stop someone who does not know it:

1. A match inside `86-REVIEW-EVIDENCE.md` itself can never be excused, because an entry would have to contain the hash of the file it is written in. Reasons in that file must avoid the pattern's words.
2. When a reviewed file changes, the old entry must be replaced. An old entry left beside the new one blocks ("any other line starting with the same path").

**Fix:** Add both sentences to the comment block at `:27-34`.

### IN-03: Self-test gaps

**File:** `.planning/phases/86-pilot-reference-record/86-publication-gate-selftest.sh:50-80`
**Issue:** The header says the public-infrastructure entries follow "the same rules", but three of those rules are tested for the credential section only: an accepted entry under another heading, a basename-only path, and a same-basename different file. The code is shared, so the risk is low. Also untested: a stale entry beside a current one, an unstaged edit to the evidence file, the `git diff` error path (`:82` of the gate), the "cannot hash" path, and the "gitleaks not installed" path. None of WR-02 to WR-05 has a case.
**Fix:** Add the three public-infrastructure cases and one case per warning fixed.

### IN-04: Portability notes for Linux and CI

**File:** `.planning/phases/86-pilot-reference-record/86-publication-gate.sh:25,59`; self-test `:28,73`
**Issue:** The user-name check is a substring match on `whoami`. Under an account with a common word as its name (for example the administrator account, or a CI runner account) it blocks on ordinary prose. The self-test's unreadable-file case fails when run as the administrator account, and two cases need `zsh`. All of these fail closed or fail loudly.
**Fix:** Note in the gate header that it is meant to run on the owner's machine under the owner's account.

### IN-05: "Right after the paired Codex pass" does not say what happens while Codex is still pending

**File:** `CLAUDE.md:98-99`; `docs/review-checkpoint-record.md:128`
**Issue:** When Codex ends INCOMPLETE after its retry, record `:66` implies the high-risk run still happens. When Codex could not be invoked at all and is recorded as "PENDING, requested" (record `:130`), the text does not say whether the vibe-check starts or waits.
**Fix:** One clause: "...and the paired Codex pass (whether that pass completed or stayed INCOMPLETE/PENDING)".

### IN-06: "Running vibe-check automatically" describes the retired rule with the new rule's word

**File:** `docs/review-workflow-adoption.md:111`
**Issue:** The retired practice was the owner running vibe-check on every "code"-class change. The guide calls it "Running vibe-check automatically on every 'code'-class change", while item 6 (`:87`) uses "automatically" for the new high-risk start by the agent.
**Fix:** "Running vibe-check routinely on every 'code'-class change is retired."

## Convention (advisory, non-blocking)

The convention checker ran and returned the same file-name-casing items as in iteration 2 ("should be camel") for the Markdown files. The rule packs apply to JS/TS sources; `CLAUDE.md` is a fixed name and every file in `docs/` is kebab-case. They are recorded as tool output only, are not counted in the totals, and no change is recommended.

## Set aside (needs ruling)

### SA-01: The public-infrastructure pattern covers home-directory paths and one private-network product only

**Where:** `.planning/phases/86-pilot-reference-record/86-publication-gate.sh:44`
**Why excluded:** The pattern list is the owner's definition of this check (`86-03-PLAN.md`, interfaces block); widening it is a scope decision, not a defect in the script.
**Effect if left as is:** Reproduced: a line with two private address ranges and a storage-volume path gave PASS. Other forms of the machine's name (the full host name, the sharing name) are also not checked; only the short host name is.
**Needs:** Ruling from the owner: add private address ranges, storage-volume paths and the other name forms / defer / accept.

### SA-02: Other tracked phase files are outside the check

**Where:** `.planning/phases/86-pilot-reference-record/86-publication-gate.sh:15`
**Why excluded:** The check is scoped to review evidence by design. Plans, summaries, context, research, validation and the two scripts are not review evidence.
**Effect if left as is:** 28 tracked files in the phase folder are published without this check. Reproduced: a summary file containing a home-directory path and the local user name gave PASS. A manual search at this head found nothing real in them.
**Needs:** Ruling from the owner: extend the check to the whole phase folder (the scripts and the plan that embeds the gate would need hand-review entries) / defer / accept.

---

_Reviewed: 2026-11-14T16:12:00Z_
_Head: 4066d538e12d38ab8612dc651965fbfb38dca2f5_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
_Iteration: 3_
