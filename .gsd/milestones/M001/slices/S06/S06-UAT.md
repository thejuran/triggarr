# S06: S06 — UAT

**Milestone:** M001
**Written:** 2026-05-05T23:52:45.787Z

# S06 UAT: Validation Remediation Evidence Review

## UAT Type

Document and validation-artifact UAT for M001 release validation readiness. This UAT is designed for a human milestone validator or release reviewer reading the repository artifacts, not for live app runtime interaction.

## Preconditions

- Worktree contains completed S06 artifacts under `.gsd/milestones/M001/slices/S06/`.
- No real API keys, session secrets, cookies, password hashes, or generated auth/session values are required or available.
- The reviewer understands that mechanical checks can pass while the human documentation UAT and `/deep-review` gate remain unresolved.

## Test Case 1 — Requirement scope is bounded for a cold reader

1. Open `.gsd/milestones/M001/slices/S06/S06-REQUIREMENT-SCOPE.md`.
2. Confirm it states there are zero Active requirements in `.gsd/REQUIREMENTS.md`.
3. Confirm it distinguishes M001 acceptance themes from historical validated/deferred/out-of-scope requirements.
4. Confirm it includes INST-04 proof by naming `detect_and_migrate_v22` and the focused migration/config tests.

Expected outcome: the reviewer can validate M001 scope without assuming S06 must re-prove every historical project requirement.

## Test Case 2 — S02 evidence inconsistency has a canonical validator path

1. Open `.gsd/milestones/M001/slices/S06/S06-S02-SUPERSESSION.md`.
2. Confirm it names the S02 placeholder/pending-task inconsistency.
3. Confirm it instructs validators to use S02 task summaries plus `S04/tasks/T03-ASSESSMENT.md`, D001, D002, and docs-accuracy tests instead of relying on `S02-SUMMARY.md`.
4. Confirm it does not reintroduce stale direct app-layer `X-Forwarded-Proto` trust wording.

Expected outcome: downstream validation has an explicit, safe evidence chain for S02/S04 documentation claims.

## Test Case 3 — Human gate is not fabricated by auto-mode

1. Open `.gsd/milestones/M001/slices/S06/S06-HUMAN-UAT-GATE.md`.
2. Confirm `Gate status`, `Human UAT`, `/deep-review`, `needs-attention`, `unresolved`, and `human source` are present.
3. Confirm the artifact does not convert agent scans, tests, or subagent reviews into human approval.
4. Confirm the next acceptable human actions are clear: approve, request changes, complete `/deep-review`, or explicitly defer with caveats.

Expected outcome: a validator cannot truthfully mark the milestone pass solely from agent-side verification.

## Test Case 4 — Mechanical evidence is indexed and reproducible

1. Open `.gsd/milestones/M001/slices/S06/S06-VALIDATION-EVIDENCE.md`.
2. Confirm it lists docs accuracy, focused v2.2 migration/config, config-dir/state/startup/docs integration, full pytest, ruff, stale-claim scan, and artifact self-check evidence.
3. Confirm it recommends `needs-attention`, not pass, because human UAT/deep-review is unresolved.
4. Confirm `.gsd/milestones/M001/slices/S06/tasks/T04-VERIFY.json` encodes the unresolved human gate as machine-readable needs-attention rather than release approval.

Expected outcome: mechanical verification can be rerun, but automated readers are not falsely green-lit for release.

## Test Case 5 — Secret hygiene and trust-boundary claims remain safe

1. Review the S06 artifacts and the referenced README/SECURITY/TODO diff.
2. Confirm no real API keys, cookies, generated auth/session secrets, password hashes, bearer headers, or secret environment values are stored.
3. Confirm External-auth and secure-cookie guidance remains aligned with D001/D002: ASGI scheme controls secure-cookie behavior, and trusted proxy forwarding is constrained to Uvicorn via `TRUSTED_PROXY_IPS`.

Expected outcome: the validation/release artifacts do not leak secrets or encourage unsafe proxy/auth deployment.

## Not Proven By This UAT

- Live Radarr/Sonarr/Lidarr integration behavior or performance under load.
- A real human documentation approval/change request/deep-review completion; S06 records that this remains unresolved.
- New runtime behavior; S06 is documentation/evidence remediation only.
- Final milestone pass posture; milestone validation should remain needs-attention until the human gate is resolved.
