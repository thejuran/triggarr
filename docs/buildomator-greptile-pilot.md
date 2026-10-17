# Buildomator + Greptile pilot

Status: prepared, not activated. Keep the existing orchestrator review process until the activation checklist is complete. Repository configuration alone does not install Greptile or enforce merging rules.

## Connect Greptile

1. Sign in at https://app.greptile.com using the GitHub account that owns `thejuran/triggarr`.
2. Install/authorize the Greptile GitHub app. Select **only Triggarr** when GitHub offers repository selection. Review the permissions shown by GitHub before authorizing.
3. Add/select Triggarr in Greptile and wait for indexing to complete. Enable automatic PR reviews and status checks. The repository's `greptile.json` requests reviews on draft PRs and every new push.
4. Request a review of the pilot PR. Record the actual check name, GitHub app identity, reviewed commit SHA, conclusion, and unresolved findings. Do not guess a check name when configuring GitHub.
5. Optional Claude integration: follow https://www.greptile.com/docs/integrations/claude-code to install the Greptile plugin, authenticate via `/mcp` and `/greptile:login`, and read/fix review findings from Claude. This is convenience access; GitHub remains the merge enforcement point. No Greptile API key belongs in this repository.

TREX is optional and must be separately confirmed available for this account. It is not a dependency of this pilot and is not represented as an active runtime test gate.

## What the proposed checks cover

- Locked Python dependencies, compilation, package build, the complete pytest suite, and Ruff.
- Docker build plus audit of Python packages actually installed in that image.
- Gitleaks secret scanning and pip-audit of locked production dependencies. Scanner failures block; any reported dependency vulnerability blocks, not only high/critical findings. Investigate findings rather than adding blanket ignores.
- `CI ready` requires every mandatory job to return success. Missing, failed, cancelled, or skipped jobs cannot pass it.
- Release preflight requires successful push CI on the exact release commit, including every mandatory job. PR CI alone cannot authorize publication. For commits containing this workflow, tags must point to main history and version-tag releases do not update the main image tag. Rejected triggers cannot enter the publishing queue; queued releases recheck eligibility before building. This does not prevent main advancing during a running build.

The release rebuild is not an attestation of byte-for-byte image identity: dependencies in the existing Dockerfile are not locked. Promoting the tested image digest, or making release builds reproducible, remains a follow-up before claiming release artifact parity. Python package auditing is not an OS image vulnerability scan.

## Activation checklist — before retiring the orchestrator

- [ ] Pilot PR CI succeeds on GitHub, including Docker and both vulnerability audits.
- [ ] Greptile is connected, indexed, and reviews the current PR commit.
- [ ] On a disposable PR, demonstrate that a known unresolved defect blocks the Greptile check, fixing it passes, and pushing another commit requires a new review. Also verify unavailable/failed reviews block. If its native check only signals completion, it cannot be the finding-resolution gate: add and test a separate fail-closed gate using the supported API before cutover.
- [ ] Update the existing default-branch ruleset: require PRs, strict/up-to-date `CI ready` from GitHub Actions, and the verified Greptile check from its actual app. Preserve deletion/force-push protections and no bypass actors. Require conversation resolution. Do not require a second human approval for a solo developer who cannot approve their own PR.
- [ ] Prove enforcement with negative cases: failed tests, skipped mandatory job, missing/stale Greptile review, unresolved findings, direct push, and unverified release tag. A green badge alone is insufficient.
- [ ] Define and test protection for changes to workflows, policy scripts, Greptile configuration, and tests themselves. Rules naming a check do not stop a PR from rewriting that check to always succeed. Independent review of safeguard changes is still necessary.
- [ ] Preserve the existing plan review, static security analysis, post-fix verification, and product/UAT acceptance steps. Greptile is not a substitute for executing these. Establish their equivalent evidence before cutover; they are not fully implemented by this pilot.
- [ ] Merge the pilot only after review. Main merges retain the existing automatic image publication behavior. Verify a main CI run and release preflight, then a version-tag release when a release is actually intended.
- [ ] Only after all of the above: stop using the orchestrator for ordinary changes and document the final active check names and ruleset configuration here.

## Routine workflow after activation

Ask Buildomator to plan, implement, and verify on a feature branch, then open a PR. Let CI and Greptile run. Have Claude investigate and fix each finding; rerun the full relevant tests after the final fix and wait for review of that new commit. Keep product acceptance explicit, especially for authentication, search correctness, persistence, scheduler behavior, and UI changes. Merge only when the enforced checks and acceptance evidence are complete.

Buildomator's ship-time review hook is advisory. Do not use its completion message as merge authorization. Do not auto-dismiss findings, bypass checks, or directly push to main to finish a task. Nontechnical product acceptance can be done by the owner; uncertain security or policy changes require competent independent review.

## Rollback

This pilot does not change hosted rules or remove the orchestrator. Before activating rules, export the current ruleset JSON and record its ID. If a new check malfunctions, repair the integration or return to the prior review process; do not silently bypass it. Revert the pilot through a reviewed PR if needed. A tag pointing to a pre-pilot commit still executes the old workflow, which contains no preflight. It can publish unchecked and overwrite image tags. External tag/publication protection must be established and tested before cutover; editing this workflow or this guide does not close that bypass.

References: https://www.greptile.com/docs/code-review/greptile-json-reference and https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets

## Release sequencing during the pilot

Wait for successful push CI on the exact main commit before creating its version tag. Pushing a tag together with main can fail preflight while CI is still running; retry that release workflow only after CI succeeds. A cancelled main CI run must first be rerun successfully. This is deliberate fail-closed behavior, not automatic waiting. Do not test old-tag publication against production: use an isolated repository/registry to validate the external protection.

## Review checkpoints

Review both tools against the same immutable commit. Preserve their original outputs before fixes; compare the results after the pilot. Vibe-check is run by the owner.

| Round | Commit | Greptile | Vibe-check |
| --- | --- | --- | --- |
| 1 | `dd8f4b53f59baa3183fbcfcc4aef1b02991b3439` | Apex completed, three findings; native check succeeded despite unresolved P1s | Owner supplied report; scored zero findings, supervising assistant raised release concerns |

The native `Greptile Review` success status is review-completion evidence only. It is not a finding-resolution gate. Keep the pilot draft until a separate tested gate and the remaining cutover protections are in place.
