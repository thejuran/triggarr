# Triggarr CI reference baseline — post-v2.12 proposal

Recorded: 2026-10-18. Status: deferred proposal, not an active workflow change.

## Intent and timing

Make Triggarr the reference for other repositories: meaningful tests, enforceable acceptance, and publication of the artifact that actually passed checks. Finish v2.12 under the existing workflow first. At closeout, read this plan alongside [the review blueprint](bm-greptile-codex-blueprint.md), refresh the evidence, and present implementation scope for owner confirmation. This is not a v2.12 blocker or a new product milestone.

No changes to Actions, settings, reviewers, approvals, or deployment are activated by this document.

## Comparison recorded on October 18

Live main-branch workflows and repository rules were inspected, rather than inferred from the Actions sidebar.

| Capability | Triggarr | Seedsyncarr |
|---|---|---|
| Merge enforcement | PRs, required CI/CodeQL/Greptile/acceptance, protected owner environment | Rules prevent deletion and force-push, but do not require PRs or successful CI |
| Application image tests | Builds, Python-package audit, saved artifact round trip | Container E2E; AMD64 on PRs and AMD64/ARM64 on main/tag runs |
| Python distributions | Builds wheel/sdist | Metadata/archive checks, clean install, CLI startup |
| Publication | Promotes exact audited CI image | Makefile rebuilds image after testing; PyPI job also builds separately |
| Explicit security jobs | Gitleaks and Python dependency audits | No equivalent explicit jobs in inspected CI workflow |
| Action pinning | Full SHA pins plus repository enforcement | Full SHA pins; repository enforcement disabled |
| Update configuration | No Dependabot configuration found on main | Weekly Python/npm updates; no Actions/Docker update entries |

Sources: [Triggarr CI](https://github.com/thejuran/triggarr/blob/main/.github/workflows/ci.yml), [release](https://github.com/thejuran/triggarr/blob/main/.github/workflows/release.yml), [Seedsyncarr CI](https://github.com/thejuran/seedsyncarr/blob/main/.github/workflows/ci.yml), [Makefile](https://github.com/thejuran/seedsyncarr/blob/main/Makefile). These URLs move; recheck before implementing.

## First bounded implementation: test what we ship

1. **Actual container startup smoke test.** Start the same image CI will publish through its normal entrypoint. Verify health, setup/login behavior, static assets, writable isolated configuration, and persistence after restart. Use mocks/test services, never production credentials or data. Existing pip inspection overrides the entrypoint and cannot prove startup works.
2. **Small browser regression suite.** Cover the connection-pill request-loop regression and critical setup/login behavior. Assert observable behavior, not screenshots or implementation details. Capture failure logs/screenshots as artifacts without secrets.
3. **Release-version consistency.** Before any version-tag publication, verify the tag agrees with package metadata and image version. Include positive and mismatch tests. Preserve exact-commit CI and artifact identity checks. Validate the trusted release policy against deliberate mismatches without publishing production tags.

Acceptance: demonstrate a broken entrypoint or missing asset fails the smoke test; the polling regression fails with the buggy behavior; a mismatched version is rejected before publication; all tests pass on the corrected implementation; published image identity remains tied to the tested artifact. Add mandatory jobs to the existing consistency checks and required gate together.

## Next bounded improvements

- **Dependency consistency:** align the Docker runtime dependency set with the tested locked dependencies. Currently CI uses uv.lock, while Docker installs with pip install .; preserve compiled frontend assets and runtime behavior while closing that mismatch.
- **Automated maintenance PRs:** configure bounded/grouped updates for uv dependencies, SHA-pinned Actions, and Docker base images. Keep manual acceptance; no blanket auto-merge. Recheck current ecosystem support and update behavior before choosing exact configuration.
- **OS image audit:** scan system packages as well as Python packages. Define severity, fix availability, scanner-error handling, and time-limited documented exceptions before enforcing the gate. Avoid silently waiving failures or duplicating equivalent scanners.
- **Workflow lint:** run actionlint when workflows change. Keep required-job consistency and release-policy tests. Define skip behavior so a required aggregate gate cannot pass when mandatory validation was omitted.
- **Package smoke checks:** if Python distributions remain release deliverables, validate metadata and install the built wheel in a clean environment; verify required packaged templates/assets and the supported startup interface. Borrow the principle, not Seedsyncarr-specific commands.

## Acceptance usability and permissions

Preserve protected owner acceptance. Improve when it is requested: mark PRs ready before final approval, and make machine-checkable prerequisites visible before asking. Address stale evidence/register snapshots without removing SHA binding. Confirm repository-wide registers handle concurrent PRs safely; until proven, serialize final acceptance updates.

Narrow publication permissions: main/dev image publishing should not need repository contents write solely because the same job also creates tagged GitHub releases. Separate only the duties needed for least privilege; do not build an orchestration framework.

### Owner acceptance from Claude CLI — separately activated

On 2026-10-18 the owner authorized this approval transport now, independently of
the deferred CI plan. Follow [the active owner CLI acceptance procedure](owner-cli-acceptance.md).
Claude may transmit only explicit owner approval for the exact commit and pending
run; autonomous approval and bypass remain prohibited. All other changes in this
plan remain deferred. No pending PR is approved by this standing permission.

## Retain / do not copy blindly

Retain exact-artifact promotion, checks tied to the intended commit, expected-app required statuses, finding dispositions independent of thread resolution, owner acceptance, full-SHA action enforcement, read-default credentials, timeouts, and sensible cancellation/serialization.

Do not copy rebuild-after-test publication or registry-write requirements into PR tests. Do not add Angular/PyPI/docs-publishing jobs to repositories that do not ship those products. Add ARM64 only if it is supported or intentionally becomes supported; then test the shipped architecture rather than assuming portability. Avoid arbitrary coverage percentages, large screenshot suites, redundant AI reviewers, and custom orchestrators.

## Adoption by other repositories

Standardize the acceptance contract, evidence, job naming, and least-privilege principles; adapt implementation to each stack. A reusable workflow is optional after the pattern is proven in two repositories, not a prerequisite. Do not copy Triggarr's IDs, trusted policy commit, artifact names, or app-specific tests blindly.

Seedsyncarr's first portability priorities are enforceable PR/check requirements, exact tested-artifact publication, and security/update coverage; retain its useful container E2E and package validation. Recheck fork PR behavior before imposing registry-dependent tests.

Keep publication and deployment evidence separate. Registry tags prove availability; verifying the running container's digest/revision proves deployment.

## Definition of ready to serve as the reference

- CI starts and exercises the actual release image with isolated test data.
- Focused browser regressions and package checks cover shipped user behavior.
- Version mismatches and missing/failed mandatory checks fail before publication.
- The published image is the tested/audited artifact.
- Review and owner-acceptance evidence is current, understandable, and does not require repeated avoidable approvals.
- Update PRs and scans have clear ownership and manageable noise.
- Negative tests demonstrate claimed enforcement; final release/publication verification is recorded.
- No custom orchestrator or unnecessary repository-wide workflow migration is introduced.
