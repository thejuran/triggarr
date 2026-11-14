---
phase: 86-pilot-reference-record
plan: 10
subsystem: review-workflow
tags: [pilot, integration, merge-main, owner-acceptance, merge, ci-fix]

requires:
  - phase: 86-pilot-reference-record
    provides: "86-07: PR #54 accepted and merged (b80c3e26cf9456dde7245350d7033f6feb94db0f); PR #55 open at 46c39194249d1e7bcd2362a91d238d0997539f3f"
provides:
  - "PR #55 (card-template) accepted by the owner on its integration head and merged: merge commit 7f6b5d4b567c06ce9a4764b94352366ef008c22b"
  - "PR #57 (maintenance, not a pilot PR): CI on main restored, merged as aeead4b601d7a26b927656bf1a07ab8c66fde58f"
affects: [86-08, 86-09]

key-files:
  modified:
    - .planning/phases/86-pilot-reference-record/86-REVIEW-EVIDENCE.md
    - .planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md
    - .planning/backlog/MAINTENANCE.md
  created:
    - .planning/phases/86-pilot-reference-record/86-REVIEW-card-5d58264e93a2.md
    - .planning/phases/86-pilot-reference-record/vibe-check/5d58264e93a2-card-routine.{md,json}
    - .planning/phases/86-pilot-reference-record/codex/5d58264e93a2-pilot-card-merge-a1.{prompt.txt,meta.json,jsonl,last.json,status.json,pytest.txt}
    - .planning/phases/86-pilot-reference-record/86-REVIEW-mainfix-{49403734406a,e18d1ed8bbb4,8e3d6b49f6b5}.md
    - .planning/phases/86-pilot-reference-record/vibe-check/{49403734406a,8e3d6b49f6b5}-mainfix-routine.{md,json}
    - .planning/phases/86-pilot-reference-record/codex/{49403734406a-main-ci-fix-a1,e18d1ed8bbb4-main-ci-fix-r2-a1,8e3d6b49f6b5-main-ci-fix-r3-a1}.*

key-decisions:
  - "CI on main failed after PR #54 merged, for date-driven reasons unrelated to it. The owner chose a separate fix PR from main (PR #57) over folding the fix into PR #55."
  - "PR #57's image scan then failed on two HIGH zlib1g findings in the base image. The owner chose to upgrade the package in the Dockerfile over a time-limited exception or waiting for upstream."
  - "Review of that Dockerfile step found it never checked the installed version (vibe-check Warning, BM info). Treated as a confirmed defect and fixed in one batched revision with a build-time version check, then re-reviewed."
  - "PR #55: main was merged in once with a plain merge commit. No confirmed defect at the integration head, so H_final = H_merge and there was no fix round."
  - "The owner instructed all three merges (#54, #57, #55) in the session; Claude ran them under the owner's account, each pinned to the accepted head."

requirements-completed: []

completed: 2026-11-14
---

# Phase 86 Plan 10: Integrate and accept the second pilot PR

**Both new pilot PRs are merged, each accepted on the exact head that merged. Along the way CI on main broke for date-driven reasons and was restored by a separate maintenance PR (#57), which went through the same review and acceptance process.**

## Second pilot PR (#55, card template)

| Item | Value |
|---|---|
| Pre-integration head | `46c39194249d1e7bcd2362a91d238d0997539f3f` |
| Main merged in | `aeead4b601d7a26b927656bf1a07ab8c66fde58f` (contains PR #54 and PR #57) |
| H_merge (integration head) | `5d58264e93a21b100d01e80503b9a7d064253d36` |
| Fix rounds after integration | none |
| H_final | `5d58264e93a21b100d01e80503b9a7d064253d36` |
| CI run on H_final | 43559074846 (all jobs passing) |
| Review acceptance run | 43559074842, attempt 2: success |
| Checkpoint comment | issuecomment-6872112603 |
| Merge commit | `7f6b5d4b567c06ce9a4764b94352366ef008c22b` (2026-11-14T05:05:32Z) |

Review at the integration head:

- **BM (standard/standard):** 0 critical, 1 warning, 3 info. The warning is the test gap already known: no test fails if the template returns to wording-based matching.
- **Codex `pilot-card-merge` a1:** complete, no findings.
- **Routine vibe-check (pass 2):** 0 reported, 3 below threshold; pass 1's Medium was rechecked as resolved by the lane that raised it.
- **D-09:** 0 confirmed defects. Every finding is nonblocking debt.

## Maintenance PR that restored CI on main (#57; not a pilot PR)

After PR #54 merged, CI on main (run 43551352373) failed. None of the causes came from PR #54:

1. A new advisory (CVE-2026-126360) against `opentelemetry-api` 1.45.1, a runtime dependency.
2. Eleven review-tooling tests whose fixture sign-in date had aged past the runner's 7-day limit, because the runner's entry points read the real clock.
3. Two HIGH findings (CVE-2026-76844, CVE-2026-85091) in `zlib1g` in the `python:3.13-slim` base image. This only became visible once 1 and 2 were fixed, because the scan job had been skipped.

| Head | What it added | Review outcome |
|---|---|---|
| `49403734406a7c0073def56b5fc5740b81fcf30e` (pushed) | dependency bump; frozen test clock | BM 0 critical/0 warning; Codex no findings; vibe-check 0 reported. CI failed on the image scan (cause 3). |
| `e18d1ed8bbb492c15b2d1b5a34384e697b7659ff` (local only) | Dockerfile step upgrading `zlib1g` | vibe-check Warning and BM info: the step never checked the installed version. Confirmed defect. |
| `8e3d6b49f6b5a923d7ee7202c3d5e56f7ec233dc` (pushed, accepted) | build-time version check; naive `now()` in the test clock | BM 0 critical/0 warning; Codex no findings; vibe-check 0 reported, Warning rechecked as resolved. CI passing (run 43556379938). |

Accepted on `8e3d6b4` (Review acceptance run 43556379926, attempt 2) and merged as `aeead4b601d7a26b927656bf1a07ab8c66fde58f`. CI on main passed afterwards (run 43557418199).

## Deviations

- **A maintenance PR was added inside this plan's window.** Plan 86-10 assumed main would contain only PR #54. Main had to be repaired first, so PR #55 was integrated with a main that also contains PR #57.
- **Merges were executed by Claude on the owner's instruction**, not by the owner personally as the plans describe (T-86-22, T-86-32). Each was pinned to the accepted head with `--match-head-commit`.
- **Acceptance runs were re-run once each** (#57 and #55), because attempt 1 was created before the register entries were written. The owner approved attempt 2 in both cases.
- **Vibe-check scope on PR #55's integration head:** the named range (the PR's net change against main) was reviewed. The tool's instructions can also be read as reviewing only the changes since the previous pass. The reading used is recorded in the vibe-check report.
- **Vibe-check's own Codex lane was skipped on every pass in this plan** (`unauthenticated`). The paired Codex review, run through the project's runner, completed on every reviewed head.
- **Two Codex transcripts for PR #57 were withheld** under the publication gate (a made-up home path quoted from a test file). Graded reports are published.
- **A local pre-run hook refused two combined shell commands** (one of mine, one of a BM reviewer's). Nothing ran; the merge was reissued as a single command, and the BM convention check for PR #55 is recorded as not run.

## Open items for the owner (none blocking)

- Whether `docs/os-scan-policy.md` should list a targeted in-image package upgrade as an allowed response to a red scan.
- Whether the Codex review runner's entry points should accept an injected clock.
- Removal of the temporary `zlib1g` step once the base image is rebuilt (tracked in `backlog/MAINTENANCE.md`).
- Next release notes: `CHANGELOG.md` has no unreleased section for the two security fixes.
- The card rendering test BM drafted for PR #55's test gap.

## Commits (phase branch)

- `0f03140` docs(86-07): record acceptance and merge of the first pilot PR
- `1485b3c`, `d5b1f5b`, `eced2b9`, `7c5deaa`, `7b4752c`: PR #57 review records, acceptance and merge
- `8371a2d` docs(86-10): integration-head review record for the second pilot PR
- `c1f47f0` docs(86-10): record owner acceptance of PR #55
- docs(86-10): record acceptance and merge of the second pilot PR (this commit)
