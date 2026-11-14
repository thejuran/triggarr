---
phase: 86-pilot-reference-record
fixed_at: 2026-11-14T16:15:57Z
review_path: .planning/phases/86-pilot-reference-record/86-REVIEW-phase-4066d538e12d.md
codex_report_path: .planning/phases/86-pilot-reference-record/codex/4066d538e12d-phase-a1.last.json
iteration: 3
findings_in_scope: 5
fixed: 5
skipped: 0
rejected: 0
status: all_fixed
---

# Phase 86: Code Review Fix Report (iteration 3)

**Fixed at:** 2026-11-14T16:15:57Z
**Source review:** `.planning/phases/86-pilot-reference-record/86-REVIEW-phase-4066d538e12d.md` (BM iteration 3, head `4066d538e12d`)
**Codex report:** `.planning/phases/86-pilot-reference-record/codex/4066d538e12d-phase-a1.last.json` (read only; nothing under `codex/` was edited, staged or committed)
**Iteration:** 3
**Base:** `4066d53` on `phase-86-pilot-reference-record`; commits made directly on that branch (no worktree, no temp branch).

**Summary:**
- Findings in scope: 5 (BM WR-01 to WR-05; Codex F001 medium is the same defect as WR-05)
- Fixed: 5
- Skipped: 0
- Rejected: 0

Scope rule applied (owner stopping rule): after iteration 3 only critical and warning findings are fixed. The six info findings (IN-01 to IN-06) and the two set-aside items (SA-01, SA-02) were not changed and go to the backlog.

No application code, test or `.github/` file was changed. `docs/codex-adversarial-review-contract.md`, `STATE.md` and `ROADMAP.md` were not changed.

## Fixed Issues

### WR-01: The automatic high-risk vibe-check has no exception for untrusted heads

**Files modified:** `CLAUDE.md`, `docs/review-checkpoint-record.md`, `docs/buildomator-greptile-pilot.md`, `docs/bm-greptile-codex-blueprint.md`, `docs/review-workflow-adoption.md`
**Commit:** c136483
**Status:** fixed: requires human verification (instruction text; the conservative reading was applied by ruling, and the owner is to be told)
**Applied fix:** One sentence was added in each place that states the automatic start (six places: the pilot document states it twice). The sentence says the automatic start applies only to trusted heads (the owner's own branches of this repository, by the same trust test the Codex contract uses). For a bot, fork or other untrusted head Claude does not start vibe-check automatically and never checks out or executes that head; it records the vibe-check as required and pending for that head and asks the owner how to proceed. The existing rules for untrusted heads are unchanged. `CLAUDE.md` and the checkpoint record use the record's own status value, REQUIRED, NOT YET RUN (PENDING). The adoption guide uses its own plain wording (commit, pull request, the agent). Nothing else in those files was changed.
**Check:** the four doc-guard test files that read these documents pass (53 passed).

### WR-02: The publication check passes without scanning a covered file that is not staged yet

**Files modified:** `86-publication-gate.sh`, `86-publication-gate-selftest.sh`
**Commit:** 3ea2a67
**Status:** fixed: requires human verification (logic change)
**Applied fix:** The covered locations are now one list used by two listings. After the tracked files are listed, the gate lists working-tree files under the same locations that are not in the index, without any exclude option, so locally ignored files are seen too. Each such file is named with "covered file is not staged; stage it with git add -f, then re-run", and the gate blocks. An error from that listing blocks. The existing "tracked file missing from worktree blocks" behaviour is unchanged and still tested. The threat-model note was added to the gate's header in this commit.
**Failing first:** against the unchanged gate the two new blocking cases failed (the gate exited 0): "untracked covered file blocks and is named" and "locally ignored covered file blocks and is named"; `selftest: 41 passed, 2 failed`. After the fix: `selftest: 43 passed, 0 failed`.
**Self-test cases added (5):** untracked covered file blocks and is named; the same file is scanned once staged; locally ignored covered file blocks and is named; passes once the ignored file is force-added; untracked file outside the covered locations does not block.

### WR-03: BM's default report file is not covered by the check

**Files modified:** `86-publication-gate.sh`, `86-publication-gate-selftest.sh`, `86-REVIEW-EVIDENCE.md`
**Commit:** e888ff7
**Status:** fixed
**Applied fix:** `86-REVIEW.md` was added to the covered locations beside `86-REVIEW-*.md`. The real `86-REVIEW.md` then had one public-infrastructure hit, at line 42. That line was read: it is the reviewer's sentence reporting that no private infrastructure was found, followed by the list of categories that were searched for; it names a category of private network name, not an actual one. It is exactly the kind of line the ruling described, so one hash-bound entry was added to the `## Public-infrastructure hand review` section with a reason saying so. The section's intro now says "in each review file" instead of "in the review file".
**Failing first:** against the gate before this change both new cases failed (the gate exited 0): "match in the default-named review report blocks" and "untracked default-named review report blocks"; `selftest: 43 passed, 2 failed`. After the fix: `selftest: 45 passed, 0 failed`.

### WR-04: The user-name, host-name and public-infrastructure checks are case-sensitive

**Files modified:** `86-publication-gate.sh`, `86-publication-gate-selftest.sh`
**Commit:** 2622aeb
**Status:** fixed
**Applied fix:** The three checks now ignore letter case (`-i`).
**Failing first:** against the gate before this change all five new cases failed (none of the name checks fired): the user name in the other letter case, the host name in the other letter case, an upper-case local path, an upper-case host suffix, and a capitalised network word; `selftest: 45 passed, 5 failed`. After the fix: `selftest: 50 passed, 0 failed`.
**New hits in the real covered set:** none. The 69 tracked covered files were checked with the case-insensitive gate; the only public-infrastructure hits are the three files that have hand-review entries, and the user-name and host-name checks found nothing.

### WR-05 / Codex F001: A credential-shape hand-review entry still passes after the file changes

**Files modified:** `86-publication-gate.sh`, `86-publication-gate-selftest.sh`, `86-REVIEW-EVIDENCE.md`
**Commit:** 2489859
**Status:** fixed: requires human verification (logic change)
**Applied fix:** A credential-shape entry is now bound to the file's current SHA-256, with the same helper and the same form as the public-infrastructure entries: the path in backticks, `sha256`, the 64-character hash in backticks, then `: not a credential -- <reason>`. A path-only entry no longer passes. The gate's header and format comment describe the new form. The `## Credential-shape hand review` section of the evidence file got an intro stating the form; it still has no entries ("none"), so nothing needed migrating.
**Failing first:** the defect was reproduced on the unchanged gate in a throwaway repository: a file with one approved value passed, a second value was added at the same path and staged, and the gate still passed (exit 0 both times). With the self-test's entries rewritten to the new form, the unchanged gate failed two cases: "accepted entry for the exact path with the current hash passes" and "credential entry without a hash blocks"; `selftest: 50 passed, 2 failed`. After the fix: `selftest: 52 passed, 0 failed`.
**Self-test changes:** every existing credential-shape case now uses the hash-bound form. Added: the regression Codex asked for ("second 32-hex value added and staged after review blocks (stale hash)") and "credential entry without a hash blocks".

## Threat model (stated in the gate header)

The gate is a backstop against accidental publication of private details by a cooperative author. It is not designed to resist deliberate evasion (for example git flags that hide changes, or obfuscated values). No defence beyond the four gate fixes above was added.

## Verification

- **Self-test** after all fixes: `selftest: 52 passed, 0 failed` (38 at the reviewed head; 14 cases added, none removed).
- **Real gate, run from the repository root:** BLOCKED, exit 1, as expected with WR-02 fixed. It named seven covered files that are in the working tree but not staged: the iteration-3 review report and the six Codex files of the `4066d538e12d` attempt. This round did not stage or commit them and added no hand-review entry for them.
- **Tracked covered set alone:** a copy of the 69 staged covered files in a throwaway repository gave `publication gate: PASS (69 tracked artifacts)`, after listing the three files that have hand-review entries.
- `bash -n` is clean on both scripts.

## Left for a ruling

1. **The Codex transcript of the `4066d538e12d` attempt will not pass the gate once staged.** Counts only: the transcript file (`.jsonl`) has 2 lines matching the local user name check, which has no exception, and 11 lines matching the public-infrastructure check. The other five Codex files of that attempt and the iteration-3 review report have no match in any of the four pattern checks. The same situation occurred for the previous attempt, whose transcript was withheld. Needs: withhold this transcript the same way, or another disposition.
2. **WR-01 wording is the conservative reading.** The owner has not yet seen it. If the owner wants the automatic run on untrusted heads within the untrusted-head limits instead, the six sentences change.
3. **Backlog, not fixed by the stopping rule:** IN-01 to IN-06, SA-01 and SA-02 of the iteration-3 review.

---

_Fixed: 2026-11-14T16:15:57Z_
_Fixer: Claude (bm-code-fixer)_
_Iteration: 3_
