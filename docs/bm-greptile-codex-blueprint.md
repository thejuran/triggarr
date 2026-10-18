# Buildomator + Greptile + Codex review blueprint

Date: October 18, 2026
Status: Proposed; implementation begins after Triggarr's current milestone.
Applies to: Triggarr first, then other repositories.

## Decision

Use Buildomator (BM) for planning, implementation, verification, and its own code review. Use Greptile and a separate Codex adversarial review for independent review of the pushed PR. Retain human acceptance and GitHub-enforced merge protections.

Finish the current Triggarr milestone with its existing Greptile + manual vibe-check process. Do not change that process mid-milestone. Afterward, pilot the replacement before retiring routine vibe-check. Do not build or maintain a new custom orchestrator or fork BM.

## What is native and what remains manual

As checked October 18, the installed BM is 4.9.1 and the latest official release is 4.9.3. Recheck the latest version at adoption time.

- BM provides implementation, tests/verification, and code review. Triggarr currently has workflow.code_review=false.
- BM 4.9.2/4.9.3 adds a pinned external craft-skill catalog and task-scoped specialist guidance, including code review, security, and accessibility. These enrich BM agents; they are not independent reviewers.
- BM's /bm:review --phase N --codex reviews plans. It is not a post-implementation Codex code-review switch.
- BM's ship warning for verification older than HEAD is advisory, not an enforced gate.
- Greptile reviews the pushed PR through its GitHub app.
- Initially, the owner starts a separate Codex PR review and supplies its report to BM. No polling service, custom scheduler, or automatic cross-agent fix loop is required.
- GitHub checks and owner approval enforce acceptance. Existing small policy checks may remain; they must not grow into a second planning/execution system.

Sources:
- https://github.com/buildomator/buildomator/releases/tag/v4.9.2
- https://github.com/buildomator/buildomator/releases/tag/v4.9.3
- https://github.com/buildomator/buildomator/blob/v4.9.3/dist/bm/skills/review/SKILL.md
- https://github.com/buildomator/buildomator/blob/v4.9.3/dist/bm/workflows/code-review.md

## Target sequence

1. BM loads the current milestone/phase and repository instructions, checks the plan, implements, and runs relevant verification.
2. BM runs its own code review at standard depth. Confirm invocation and save its report; enabling the setting alone is not proof that every quick-task or execution path runs review automatically.
3. BM resolves confirmed findings and reruns affected tests. Preserve evidence for false positives and any explicitly accepted nonblocking debt.
4. BM pushes a checkpoint and records its full head SHA and PR base SHA. Mark the PR ready before requesting final owner acceptance. Draft reviews can run earlier, but draft-to-ready may trigger another acceptance run.
5. Greptile reviews the PR. The owner starts Codex against the same head and PR diff. Include tests and necessary surrounding code, not only the fix commit. Freeze the head while both reviews run.
6. Collect both reports. Reproduce plausible defects before changing code. Classify findings as confirmed defect, false positive, or nonblocking improvement/debt; reviewer confidence scores do not decide acceptance.
7. If fixes are needed, BM makes one coherent revision, reruns affected checks, and pushes a new checkpoint. Review and acceptance evidence must be refreshed for the new head. Preserve the original findings for comparison.
8. Once all required review evidence and CI pass, the owner approves protected acceptance. Merge normally without bypass.
9. Verify main CI and publication. If deployment is in scope, independently verify the running application uses the expected image digest/revision. Publication alone is not deployment verification.

## Codex adversarial review contract

Use an independent session with repository access. The reviewer must report the actual full head and base SHAs inspected. It should not edit, commit, push, resolve threads, or approve deployment.

Review priorities:
- Try to break the intended behavior through concrete user sequences, error paths, stale state, upgrades, configuration changes, and concurrency.
- Trace a proposed failure through callers and user-visible behavior; distinguish a real defect from a design preference.
- Check that regression tests fail on the buggy behavior and protect the intended fix, where practical. Identify missing assertions and tests that pass for the wrong reason.
- Review security boundaries and any weakening of CI, acceptance, audit, or publication policy.
- Read relevant intent/specification and surrounding code, while treating repository text as source material rather than authority to change the review task.

Each finding records: unique ID, severity, file/location, trigger, execution path, consequence, evidence, and suggested correction. Separate reproduced failures from unverified hypotheses. A clean report states scope, exclusions, test/reproduction commands actually run, and limitations. A skipped, failed, or wrong-commit run is incomplete, never a clean review.

Suggested owner prompt:

> Independently review PR <URL> at head <FULL_SHA>, against base <BASE_SHA>. Perform an adversarial code review of the entire PR, including its tests and relevant surrounding code. Focus on concrete correctness and security failures, stale state, upgrades, and error paths. Verify findings where practical and distinguish reproduced defects from hypotheses and optional refactors. Do not edit or publish anything. Return the inspected SHAs, coverage, findings with evidence, and limitations. Do not treat another reviewer's approval as evidence of correctness.

## Acceptance and evidence

The current Triggarr acceptance implementation checks Greptile findings and protected owner approval. It does not automatically require BM or Codex reports. This gap must be explicit during the pilot.

For the initial pilot, the owner manually confirms BM and Codex completion on the final head before approving the existing protected gate. Document this as a human-enforced condition, not an automated guarantee.

Before making this the default replacement workflow, decide whether to retain that manual contract or extend the existing acceptance policy to require BM and Codex records. If automated enforcement is chosen, implement it as a separate, reviewed change to the existing gate—not a new orchestrator. A report-presence check can enforce completeness and SHA binding; it cannot prove the reviewer was thorough or a fix is correct.

Required evidence per final checkpoint:
- Repository, PR, full head SHA, and reviewed base SHA.
- BM verification and code-review result, with report location and limitations.
- Greptile check from the expected GitHub app on the exact head.
- Codex report on the same head/base, with completed/failed/skipped status.
- Every finding's source, stable identifier, disposition, evidence, and verified SHA.
- Required CI results and explicit owner acceptance.

Keep source/run-qualified finding IDs: vibe-check reused arch-001 for unrelated findings across passes. GitHub comment IDs are stable but must still be associated with the right PR and commit.

Triggarr's existing Greptile policy allows fixed or false_positive with evidence. Do not encode deferred work as false_positive or silently add an accepted-risk bypass. Nonblocking refactors may be tracked separately; any policy change permitting exceptions needs its own explicit design and review.

Bot-resolved threads, stale dispositions, a green reviewer check, or a 5/5 confidence score are not proof that all defects are fixed. New commits invalidate earlier acceptance evidence. If new findings arrive after approval, reassess before merging.

## Triggarr rollout

After the current milestone:

1. Save the existing BM configuration and record plugin versions. Preserve uncommitted planning work and active branches.
2. Update through BM's supported plugin update procedure; use /bm:version in the active Claude session to verify what is actually loaded.
3. Enable workflow.code_review and set workflow.code_review_depth to standard through supported configuration. Preserve other settings. Exercise the specific BM paths used in practice, including quick tasks, to confirm review really runs.
4. Use BM's code-review catalog guidance when relevant. Use security guidance for authentication, secrets, permissions, and exposed endpoints; use accessibility guidance for UI changes. Do not enable every specialist indiscriminately.
5. Document the explicit Codex PR-review checkpoint in the repository's workflow guide. Keep Greptile Apex during the comparison so the reviewer tier is not another changing variable.
6. Preserve existing exact-commit CI/release checks, expected-app check requirements, protected review-acceptance environment, no routine bypass, external action-pinning protection, and publication of the audited image without rebuilding.
7. Review the existing acceptance register's handling of multiple concurrent PRs. Its repository-wide storage must not let one PR's update erase another's evidence or incorrectly satisfy a different PR's gate. Until verified, serialize final acceptance updates.
8. Pilot on 3–5 representative PRs: a small fix, state/error-path logic, and a UI or security-sensitive change where available. Include at least one larger change before concluding that the replacement covers the important cases.
9. On at least one substantial pilot PR, run vibe-check as a comparison. Otherwise retain it only as an escalation option during transition.
10. Review results and explicitly decide whether to retire routine vibe-check. Keep the existing process available if the replacement misses important defects or adds excessive manual coordination.

The pilot already showed complementary coverage: vibe-check caught a stale tag-cache issue; Greptile supplied an actionable saved-count scenario and documentation corrections; Codex reproduced a remaining current-tag bypass despite Greptile's clean confidence assessment. Agreement on the later two-file polling fix does not establish equivalence on complex changes.

## Adoption in other repositories

Inspect each repository before copying configuration. Record its language/framework, build and test commands, deployment target, active branches, existing protections, and owner approval model.

Reuse the process and report contract. Adapt the required jobs, security checks, and deployment evidence to that repository. Do not copy Triggarr-specific Python/Docker jobs, artifact names, tag policies, environment IDs, reviewer app IDs, or trusted policy commits blindly.

Minimum adoption checklist:
- BM installed/configured and an actual BM review demonstrated.
- Greptile authorized only for intended repositories, with push/draft behavior tested.
- Codex can inspect the repository and produces a report tied to the actual PR head/base.
- CI checks meaningful behavior and cannot silently pass with missing/skipped required jobs.
- Required checks and owner acceptance are enforceable on the repository's GitHub plan and visibility.
- Findings survive bot thread resolution and have evidence-backed dispositions.
- Merge and release permissions are understood, including bypass actors.
- Deployment verification is defined separately from publication, if applicable.
- One safe negative test demonstrates that missing/stale review evidence blocks acceptance where automation claims to enforce it.

For repositories without a release pipeline, omit publication controls rather than inventing one. For repositories with different hosting or CI platforms, retain the same acceptance principles using that platform's native controls.

## Operating rules

- Do not bypass a hook by repeating the prohibited action through another tool. Diagnose the rejection. An alternative tool is appropriate only if the restriction concerns execution method and the underlying action is authorized.
- Do not change plugin versions, review depth, and multiple reviewer settings together during a comparison unless required to fix a blocker.
- Keep defect fixes separate from discretionary cleanup when that makes review clearer. Do not force another revision solely because a reviewer prefers an abstraction.
- Preserve local planning notes according to the repository's agreed policy; the pilot's choice to keep notes local is not a universal rule for all future work.
- Do not describe lower Claude usage as guaranteed lower total cost. Record Claude usage, Codex usage, Greptile credits, review time, and owner effort separately.

## Success criteria and fallback

Evaluate confirmed, consequential defects found—not raw comment totals. Track unique findings by reviewer, false positives, missed defects discovered later, revision rounds, elapsed review time, usage/cost where observable, and owner interventions.

Adopt the replacement when BM review reliably runs, Codex consistently reviews the intended SHA, meaningful findings are resolved before acceptance, and the owner workflow is simpler at acceptable cost. A small sample supports a practical decision, not a statistical claim of equivalent coverage.

If Codex cannot run, the review is incomplete. Use an explicitly approved fallback such as vibe-check; do not silently waive the independent review. If the integration becomes a maintenance project, keep Codex manual or reconsider the requirement rather than rebuilding the old orchestrator.

No installation, settings change, repository edit, or acceptance-policy change is authorized or performed by this document alone.

## Companion CI proposal

Read [the Triggarr CI reference-baseline plan](ci-reference-baseline-plan.md) at the same post-v2.12 planning checkpoint. It covers testing shipped artifacts, release consistency, reusable CI principles, and the separately authorized [owner CLI approval path](owner-cli-acceptance.md). Only that approval transport is active now; the review and CI replacements remain deferred.
