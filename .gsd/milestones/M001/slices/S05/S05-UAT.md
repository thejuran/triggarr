# S05: S05 — UAT

**Milestone:** M001
**Written:** 2026-05-05T23:05:14.708Z

## UAT Type

Artifact-based release/documentation gate UAT preparation with a negative human-gate result. This UAT verifies that the review packet, gate note, and evidence index give a future human/release verifier enough information to approve, request changes, or defer README/SECURITY/TODO documentation review. It does **not** prove human approval.

## Preconditions

- Worktree contains the completed S04 documentation remediation for `README.md`, `SECURITY.md`, and `TODO.md`.
- S05 artifacts exist:
  - `.gsd/milestones/M001/slices/S05/S05-DOCS-REVIEW-PACKET.md`
  - `.gsd/milestones/M001/slices/S05/S05-UAT-GATE.md`
  - `.gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md`
- No real API keys, generated auth secrets, password hashes, cookies, bearer tokens, or secret environment values are used in review notes.

## Test Case 1 — Cold-reader packet is actionable for the intended operator

1. Open `S05-DOCS-REVIEW-PACKET.md`.
2. Confirm the reader is named as `an operator installing or upgrading Triggarr`.
3. Confirm the post-read action is to configure Docker or standalone runtime paths and choose a safe authentication/proxy mode.
4. Confirm the packet names the diff range `a3f09ad^..HEAD` and scopes review to `README.md`, `SECURITY.md`, and `TODO.md`.
5. Confirm the checklist covers portable `TRIGGARR_CONFIG_DIR`, `/config` Docker default, standalone first-run behavior, nested multi-instance TOML, auth modes, External-auth proxy/direct-access boundary, ASGI/Uvicorn secure-cookie behavior, TODO retirement, and secret redaction.

Expected outcome: a human reviewer can perform the documentation review without relying on prior agent context.

## Test Case 2 — Agent-side review is not confused with human approval

1. Open `S05-UAT-GATE.md`.
2. Confirm `Gate status: unresolved`.
3. Confirm the decision source says no human documentation UAT decision was available in auto-mode.
4. Confirm the artifact rejects surrogate decisions such as agent packet creation, mechanical checks, or absence of objections.

Expected outcome: the artifact does not claim human UAT passed.

## Test Case 3 — `/deep-review` release caveat is explicit

1. In `S05-UAT-GATE.md`, find `Deep-review decision:`.
2. Confirm it is recorded as blocked/unavailable in auto-mode, not completed and not human-deferred.
3. Confirm the caveat says a human must run `/deep-review`, explicitly defer it, or request changes before push/tag/release.

Expected outcome: release managers are not misled into treating S05 as release approval.

## Test Case 4 — Release evidence recommends the correct milestone posture

1. Open `S05-RELEASE-GATE-EVIDENCE.md`.
2. Confirm `Gate status: unresolved`.
3. Confirm `Release readiness: blocked`.
4. Confirm `Milestone validation recommendation: needs-attention`.
5. Confirm the rationale says mechanical diagnostics are supporting evidence only and do not replace human UAT.

Expected outcome: downstream milestone validation should not mark the milestone passed solely from agent checks.

## Test Case 5 — Mechanical diagnostics are traceable

1. In `S05-RELEASE-GATE-EVIDENCE.md`, inspect the command evidence table.
2. Confirm each command includes command text, exit code, verdict, stdout artifact path, stderr artifact path, and notes.
3. Confirm the table includes docs accuracy, focused config/state/startup/docs tests, full pytest, ruff, stale-claim scan, and artifact self-check.
4. Confirm the latest closer evidence points to `.gsd/exec/b73f0f50-3261-495f-ac82-e7e04795c090.stdout`, `.gsd/exec/aace1c32-569f-4364-9064-4a6e4e09308b.stdout`, `.gsd/exec/ba75ab1c-ea35-4123-b684-24749706842e.stdout`, `.gsd/exec/c976accb-49b1-40e8-9404-d0e204c70154.stdout`, `.gsd/exec/f3093198-96a8-4f97-8494-7135faa1f83e.stdout`, and `.gsd/exec/b7d028f6-66a2-4733-ac3b-ac514eb86b81.stdout`.

Expected outcome: a future verifier can audit exactly what was run and where full output lives.

## Test Case 6 — Stale-claim guardrail remains clean

1. Review the stale-claim command in the evidence index.
2. Confirm it scans README/SECURITY/TODO/CONTRIBUTING/docs for stale claims including `no authentication`, `config directory is not configurable`, flat `[radarr]`, `TRIGGARR_GENERAL__`, and direct `x-forwarded-proto` trust wording.
3. Confirm the recorded result is no matches.

Expected outcome: known stale or unsafe documentation claims did not reappear in the scanned user-facing docs.

## Edge Cases / Negative Paths

- If a human later requests documentation changes, README/SECURITY/TODO changes must be applied or replanned, `uv run pytest tests/test_docs_accuracy.py -q` must be rerun, and the gate note/evidence index must be refreshed before claiming readiness.
- If a human explicitly defers documentation UAT or `/deep-review`, the artifact should say deferred with source, timestamp, scope, and caveats; this is a release caveat, not approval.
- If docs are mutated after a future approval or deferral, the previous gate decision must not be carried forward without rerunning guardrails and refreshing review notes.
- If any real secret appears in review artifacts, the artifact is invalid and must be remediated before release validation.

## Not Proven By This UAT

- Actual human documentation approval, explicit deferral, or change request.
- A completed `/deep-review` run or human decision to defer it.
- Live Docker/standalone installation by a human operator.
- Live reverse-proxy behavior, HTTPS deployment behavior, or production cookie behavior beyond the existing automated tests and documentation guardrails.
- Release/tag/push readiness while the human gate remains unresolved.
