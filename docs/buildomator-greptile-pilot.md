# Buildomator + Greptile pilot

Status: hosted protections are active; the implementation PR still awaits final review, owner acceptance, and merge. Do not claim the migration complete until the remaining activation items below pass.

## Connect Greptile

1. Sign in at https://app.greptile.com using the GitHub account that owns `thejuran/triggarr`.
2. Install/authorize the Greptile GitHub app. Select **only Triggarr** when GitHub offers repository selection. Review the permissions shown by GitHub before authorizing.
3. Add/select Triggarr in Greptile and wait for indexing to complete. Enable automatic PR reviews and status checks. The repository's `greptile.json` requests reviews on draft PRs and every new push.
4. Request a review of the pilot PR. Record the actual check name, GitHub app identity, reviewed commit SHA, conclusion, and unresolved findings. Do not guess a check name when configuring GitHub.
5. Optional Claude integration: follow https://www.greptile.com/docs/integrations/claude-code to install the Greptile plugin, authenticate via `/mcp` and `/greptile:login`, and read/fix review findings from Claude. This is convenience access; GitHub remains the merge enforcement point. No Greptile API key belongs in this repository.

TREX is optional and must be separately confirmed available for this account. It is not a dependency of this pilot and is not represented as an active runtime test gate.

## What the checks cover

- Locked Python dependencies, compilation, package build, the complete pytest suite, and Ruff.
- Docker build plus audit of Python packages actually installed in that image.
- Gitleaks secret scanning and pip-audit of locked production dependencies. Scanner failures block; any reported dependency vulnerability blocks, not only high/critical findings. Investigate findings rather than adding blanket ignores.
- `CI ready` requires every mandatory job to return success. Missing, failed, cancelled, or skipped jobs cannot pass it.
- Release preflight requires successful push CI on the exact release commit, including every mandatory job. PR CI alone cannot authorize publication. For commits containing this workflow, tags must point to main history and version-tag releases do not update the main image tag. Rejected triggers cannot enter the publishing queue; queued releases recheck eligibility before publication. This does not prevent main advancing during a running publication.

Releases promote the image archive uploaded by the exact successful CI run, without rebuilding; Python distributions are no longer published (Phase 85 D-14). Image checksums and image IDs are checked before publication. The image's OS packages are scanned under [the OS-package scan policy](os-scan-policy.md); Python packages are audited by pip-audit.

## Activation checklist — before retiring the orchestrator

- [x] Greptile is connected and indexed. Its native `Greptile Review` check (app ID 867647) signals completion, not remediation. Automatic review started on push 7fb8fca after dashboard settings were corrected.
- [x] Default-branch ruleset 14805779 requires PRs, strict/current `CI ready`, `CodeQL`, and `Review acceptance` from their expected apps. `Greptile Review` was removed from the required checks on 2026-10-22 (owner decision: Greptile is optional; the free tier's 300 reviews per period are not topped up with paid credits). Conversation resolution and the protected `review-acceptance` environment are required; deletion/force-push protections and no bypass actors are retained.
- [x] Repository-wide full-SHA action enforcement rejects the unpinned action used by historical release workflows. Read-only negative probe 39081443569 failed at job setup as expected. No production tag or image was published for this test.
- [x] Acceptance policy negative tests reject missing/stale/failed/spoofed reviews, auto-resolved findings without evidence, stale approvals/dispositions, unsupported waivers, and accepted open blockers. Release-policy tests reject failed/skipped/neutral/cancelled or missing mandatory CI jobs.
- [x] GitHub reports this PR BLOCKED with the owner-acceptance job waiting. Owner approval is a required deployment, so removing or faking the job's check does not remove the deployment requirement.
- [ ] Latest implementation CI (including artifact round trip) and Greptile review pass; findings have verified dispositions.
- [ ] Owner approves the concrete final result in the protected environment; acceptance job passes on the current checkpoint.
- [ ] Merge the pilot after acceptance, then verify main CI and release promotion. Test a version-tag release only when a release is actually intended.

BM plan checking, post-fix verification, and explicit product/UAT acceptance remain required workflow steps. CodeQL is required static analysis. For application-code pilot checkpoints, the owner runs vibe-check in parallel on the same SHA. Any safeguard or test weakening requires independent inspection before owner acceptance. GitHub enforces approval and evidence presence; it cannot establish technical correctness or user acceptance on its own.

## Routine workflow after activation

Ask Buildomator to plan, implement, and verify on a feature branch, then open a PR. Let CI and Greptile run. Have Claude investigate and fix each finding; rerun the full relevant tests after the final fix and wait for review of that new commit. Keep product acceptance explicit, especially for authentication, search correctness, persistence, scheduler behavior, and UI changes. Merge only when the enforced checks and acceptance evidence are complete.

Buildomator's ship-time review hook is advisory. Do not use its completion message as merge authorization. Do not auto-dismiss findings, bypass checks, or directly push to main to finish a task. Nontechnical product acceptance can be done by the owner; uncertain security or policy changes require competent independent review.

## Rollback

Hosted rules are now changed. The original ruleset and action-policy settings are saved outside the branch in the pilot evidence folder. Revert code through a reviewed PR if needed. Do not disable SHA pinning as a casual rollback: it would re-enable the unsafe historical release workflows. Missing/expired release artifacts fail closed; regenerate them by rerunning CI for the exact main commit. The custom orchestrator has not been deleted or modified.

References: https://www.greptile.com/docs/code-review/greptile-json-reference and https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets

## Release sequencing during the pilot

Wait for successful push CI on the exact main commit before creating its version tag. Pushing a tag together with main can fail preflight while CI is still running; retry that release workflow only after CI succeeds. A cancelled main CI run must first be rerun successfully. This is deliberate fail-closed behavior, not automatic waiting. Do not test old-tag publication against production: use an isolated repository/registry to validate the external protection.

## Review checkpoints

Review both tools against the same immutable commit. Preserve their original outputs before fixes; compare the results after the pilot. Vibe-check is run by the owner.

| Round | Commit | Greptile | Vibe-check |
| --- | --- | --- | --- |
| 1 | `dd8f4b53f59baa3183fbcfcc4aef1b02991b3439` | Apex completed, three findings; native check succeeded despite unresolved P1s | Owner supplied report; scored zero findings, supervising assistant raised release concerns |
| 2 | `5a3cb44f93e14641ec967a2079418c8855bb30a4` | Apex completed, zero new comments; all original threads resolved by greptile-apps[bot], including the unfixed old-tag bypass | One Medium finding (required-job list consistency across release policy, ci-ready needs, and aggregate set); a sparse-checkout concern it raised was subsequently disproved |

Bot-resolved threads are not evidence a finding was fixed — the old-tag bypass (round 1) remains open despite its thread being marked resolved.

The native `Greptile Review` success status is review-completion evidence only. The separate protected acceptance step and repository-variable evidence registers are the additional merge gate. Keep the pilot draft until final validation and owner acceptance.

## Safeguard rollout (checkpoint after 4f9d9da)

- GitHub now requires full-SHA action pins at repository level. The read-only negative probe run 39081443569 was rejected during job setup because `actions/checkout@v6` was unpinned. All 11 historical release-workflow versions on main reference unpinned actions. This external policy blocks those known historical publishing paths even when an old tag supplies the workflow. Keep this policy enabled. It is not a general defense against an administrator deliberately replacing workflows or disabling policies.
- CI uploads the audited Docker image. Releases download artifacts from the exact successful CI run selected by preflight, verify the image archive checksum and image ID, and publish without rebuilding. CI downloads its own image artifact, removes the local image, reloads it, and verifies image ID and installed requirements. Expired/missing artifacts block publication; rerun CI for the exact commit to regenerate them. Artifacts are retained for 30 days.
- `review-acceptance` is a protected GitHub environment, not a production deployment. The owner must approve it; administrator bypass is disabled. Self-approval is permitted because this is a solo-maintainer project. An agent must not decide approval autonomously. By owner authorization dated 2026-10-18, Claude may transmit the owner's explicit approval of the exact commit through the existing GitHub API, following [the owner CLI acceptance procedure](owner-cli-acceptance.md).
- The acceptance workflow executes a pinned policy commit, never code from the PR checkout. It verifies the event's head still matches the PR, requires the latest Greptile check for that head from app ID 867647, and requires disposition evidence for every Greptile inline finding, including resolved/outdated findings. Since 2026-10-22 a Greptile review is optional: a head with no Greptile check may be accepted, but a Greptile check that exists for the head must have completed successfully (a running or failed review blocks).
- `REVIEW_BLOCKERS` and `REVIEW_DISPOSITIONS` are repository variables, outside the PR. Missing/malformed registers fail closed. A nonempty blocker list blocks acceptance. Each finding disposition needs the current full head SHA, a decision of `fixed` or `false_positive`, and verification evidence; there is no automatic accepted-risk disposition. Resolved threads do not update these records.
- GitHub cannot determine whether prose evidence is truthful or a fix is correct. A competent reviewer/agent must investigate and demonstrate the fix, then the owner approves the prepared result. Any safeguard/test weakening needs independent inspection before this approval. An administrator with settings credentials remains capable of disabling controls; these controls protect the routine workflow, not against a hostile repository owner.

### Routine BM workflow

See [the review-classification policy](review-classification-policy.md) for which reviews a checkpoint needs, and [the review checkpoint record](review-checkpoint-record.md) for the paired Codex pass and the per-head evidence record.

Every push to a PR uses one of Greptile's limited free reviews (paid credits are not bought), so push only when the head needs a new review. When Greptile is unavailable, its review is skipped; safeguard changes still get independent inspection from another reviewer. Batch fixes into one checkpoint push. Hold docs-only, evidence and tracking commits locally until the next substantive push. Keep deliberately broken demonstration pushes to the minimum the plan requires.

1. BM plans and verifies on a feature branch, pushes a checkpoint, and records its full SHA. Keep internal quick-task notes local unless separately requested.
2. Confirm CI and Greptile run on that checkpoint. For application-code pilot work, the owner runs vibe-check independently on the same SHA, in parallel with Greptile. No vibe-check is required for the remaining infrastructure setup.
3. Investigate findings, add regression evidence, and batch fixes into a new checkpoint. Never use bot thread resolution as proof of remediation. After the final tests and reviews, a reviewer prepares the repository-variable dispositions with concrete evidence for the current SHA. Plan and product/UAT acceptance remain explicit tasks; check passes cannot establish them.
4. Present the exact SHA, evidence, and any remaining blockers to the owner. The owner either uses GitHub Actions → Review acceptance → Review deployments, or explicitly approves the exact commit in Claude CLI and has Claude transmit that decision under [the owner CLI acceptance procedure](owner-cli-acceptance.md). This is an explicit approval, not a coding task. Approve only after CI, the current Greptile review when one ran, the paired Codex review for this exact head (complete, or INCOMPLETE/PENDING with an owner-approved fallback accepted by `.github/scripts/codex-fallback.cjs`), and any applicable vibe-check/UAT are complete. The job independently checks the records and fails if incomplete. Rerun this workflow after repairing records if necessary.
5. Merge only once GitHub's required checks and required environment are satisfied. A new push requires new checks, dispositions, and environment approval. If another review adds findings after approval, rerun acceptance before merging.

### Register shape

`REVIEW_BLOCKERS`: `{"schema":2,"global_open":["descriptive-blocker-id"],"by_pr_head":{"<PR>:<FULL_SHA>":{"open":[]}}}`. Every PR head needs its own `by_pr_head` entry (even an empty `open` array) before acceptance for that head; `global_open` stays for blockers that are not scoped to one PR. Use an empty `open` array only after verification; keep the evidence in pilot-notes.md or a durable linked report.

`REVIEW_DISPOSITIONS`: `{"schema":2,"by_pr_head":{"<PR>:<FULL_SHA>":{"items":{"COMMENT_ID":{"head":"FULL_SHA","decision":"fixed","evidence":"Specific regression test/result or external-control evidence"}}}}}`. Every PR head needs its own `by_pr_head` entry before acceptance for that head. Keep previous entries when adding new ones. PR authors cannot amend these variables through a code diff. The approval step exists because an evidence string alone is not proof.

Write entries with `node .github/scripts/review-register.cjs upsert --kind dispositions|blockers --pr <N> --head <sha> --slice-file <path> --apply`, which reads the value back and verifies the write landed. The live repository variables migrate from schema 1 to schema 2 once, with an owner go-ahead, via `node .github/scripts/review-register.cjs migrate --kind dispositions|blockers --apply` (keeps the old value under `archived_schema1`). Because repository variables have no compare-and-swap, final acceptance updates are serialized: finish writing and approving one PR's register entries before starting another's.

The deployment approval and required-check rules must be read back and tested before calling rollout complete. A successful artifact round trip does not claim that a production release has been executed.
