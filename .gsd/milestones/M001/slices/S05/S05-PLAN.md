# S05: S05

**Goal:** Produce an honest human-documentation UAT and release-gate record for the completed README/SECURITY/TODO documentation changes, without confusing agent-side checks for human approval. The slice should leave future milestone validation with a concise review packet, a recorded human approval/defer/change decision or an explicit blocker if no human decision is available, and fresh mechanical verification evidence.
**Demo:** After this: a human has reviewed the README/SECURITY/TODO documentation diff, release/deep-review caveats are resolved or explicitly deferred by the user, and validation can rerun with UAT evidence.

## Must-Haves

- ## Must-Haves
- A durable review packet exists for `README.md`, `SECURITY.md`, and `TODO.md` using the broad milestone docs diff range `a3f09ad^..HEAD` and the cold-reader/operator checklist.
- The review packet names the reader as an operator installing or upgrading Triggarr, and the post-read action as configuring Docker or standalone runtime paths plus choosing a safe auth/proxy mode.
- A gate artifact records the human documentation decision and the `/deep-review`/release decision. If no human decision is available, the artifact must say the gate is unresolved and execution must not claim human UAT passed.
- Any requested documentation changes are handled by replanning or patching before final verification; docs are not mutated after approval without rerunning the docs guardrail and refreshing the gate note.
- Fresh mechanical verification evidence is captured for docs accuracy, config/state/startup regressions, full pytest, ruff, and a stale-claim scan.
- ## Threat Surface
- **Abuse**: Misleading External-auth or proxy documentation could cause operators to expose Triggarr without upstream authentication/authorization or to trust spoofed forwarded headers.
- **Data exposure**: Review artifacts must use documentation placeholders only and must not include real API keys, generated auth secrets, cookies, or environment secret values.
- **Input trust**: Human review feedback is untrusted prose that may request scope changes; executors must treat requested changes as documentation/code work requiring guardrail reruns rather than silently accepting unsafe wording.
- ## Requirement Impact
- **Requirements touched**: No Active requirements. This slice preserves validated documentation/evidence coverage for `INST-01`, `INST-02`, `OBS-02`, `OBS-03`, and milestone-level portable-config/auth documentation acceptance.
- **Re-verify**: `tests/test_docs_accuracy.py`, config-dir/state/startup regressions, full test suite, ruff lint, and stale documentation claim scan.
- **Decisions revisited**: `D001` and `D002` must remain honored; docs and review artifacts must keep forwarded-proto trust at the Uvicorn/ASGI scheme boundary.
- ## Verification
- `uv run pytest tests/test_docs_accuracy.py -q`
- `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py tests/test_docs_accuracy.py -q`
- `uv run pytest tests/ -x -q`
- `uv run ruff check triggarr/ tests/`
- `git grep -n -i -E 'no authentication|authentication is not implemented|config directory is not configurable|make config directory configurable|flat \[radarr\]|\[radarr\][[:space:]]*$|TRIGGARR_GENERAL__|directly trusts.*x-forwarded-proto|routes trust.*x-forwarded-proto' -- README.md SECURITY.md TODO.md CONTRIBUTING.md docs 2>/dev/null || true`
- `test -s .gsd/milestones/M001/slices/S05/S05-DOCS-REVIEW-PACKET.md && test -s .gsd/milestones/M001/slices/S05/S05-UAT-GATE.md && test -s .gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md`
- ## Proof Level
- This slice proves: final release-gate/documentation-UAT readiness, but only when `S05-UAT-GATE.md` records an actual human approval or explicit user deferral. If the artifact says unresolved because auto-mode could not reach a human, the proof level is needs-attention rather than passed UAT.
- Real runtime required: no live deployment or reverse proxy; proof is documentation review artifacts plus test/lint commands against tracked code and docs.
- Human/UAT required: yes. Agent-side scans and cold-reader checks are only preparation and evidence, not a substitute for human UAT.
- ## Observability / Diagnostics
- Runtime signals: none added; this slice does not change production runtime behavior.
- Inspection surfaces: `.gsd/milestones/M001/slices/S05/S05-DOCS-REVIEW-PACKET.md`, `.gsd/milestones/M001/slices/S05/S05-UAT-GATE.md`, `.gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md`, and referenced `.gsd/exec/*.stdout` command artifacts.
- Failure visibility: gate status, human decision source, requested changes, verification command, exit code, and stale-claim scan result are captured in durable files.
- Redaction constraints: never include real API keys, generated auth secrets, cookies, or secret environment values; use existing placeholders only.
- ## Integration Closure
- Upstream surfaces consumed: S04 documentation remediation in `README.md`, `SECURITY.md`, `TODO.md`, guardrails in `tests/test_docs_accuracy.py`, and S04 evidence assessment in `.gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md`.
- New wiring introduced in this slice: no runtime wiring; this slice wires the release evidence trail by connecting the docs diff packet, gate decision, and fresh verification output.
- What remains before the milestone is truly usable end-to-end: nothing if the human gate is approved or explicitly deferred and mechanical verification passes; otherwise milestone validation must remain needs-attention until a human resolves the gate.

## Proof Level

- This slice proves: Final release-gate/documentation-UAT proof. This is passed only if the gate artifact records an actual human approval or explicit user deferral plus fresh mechanical verification. In auto-mode with no human response, the proof remains needs-attention/unresolved and must not be described as human UAT passed.

## Integration Closure

Consumes S04's README/SECURITY/TODO remediation, docs-accuracy tests, and evidence assessment; adds review/gate/evidence artifacts only. No production code or runtime wiring is introduced. Milestone completion can proceed only after the gate artifact is not unresolved and verification evidence passes.

## Verification

- Diagnostics are artifact-based: the review packet, gate note, release evidence index, and gsd_exec stdout paths make it clear what was reviewed, who/what approved or deferred it, which commands ran, and what remains unresolved. No production logs or metrics are changed.

## Tasks

- [x] **T01: Created the S05 cold-reader documentation review packet for human README/SECURITY/TODO UAT.** `est:45m`
  Create the durable packet a human reviewer will use to review the README/SECURITY/TODO documentation changes. It must be concise enough for a real operator to read, but specific enough to cover portable config directory behavior, nested multi-instance TOML, auth/security modes, External-auth trust boundaries, secure-cookie ASGI/Uvicorn behavior, and TODO retirement.
  - Files: `.gsd/milestones/M001/slices/S05/S05-DOCS-REVIEW-PACKET.md`, `README.md`, `SECURITY.md`, `TODO.md`, `tests/test_docs_accuracy.py`, `.gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md`
  - Verify: test -s .gsd/milestones/M001/slices/S05/S05-DOCS-REVIEW-PACKET.md && grep -q 'a3f09ad\^..HEAD' .gsd/milestones/M001/slices/S05/S05-DOCS-REVIEW-PACKET.md && grep -q 'operator installing or upgrading Triggarr' .gsd/milestones/M001/slices/S05/S05-DOCS-REVIEW-PACKET.md

- [x] **T02: Recorded the docs UAT gate as unresolved because auto-mode had no human decision.** `est:30m`
  Create the gate artifact that records the documentation UAT outcome and the `/deep-review` release decision. This task is the human-required gate: if an actual human approval, change request, or explicit deferral is available in the execution context, record it with source, timestamp, scope, and any caveats. If no human decision is available because execution is in auto-mode, record the gate as unresolved and do not mark human UAT as passed.
  - Files: `.gsd/milestones/M001/slices/S05/S05-UAT-GATE.md`, `.gsd/milestones/M001/slices/S05/S05-DOCS-REVIEW-PACKET.md`, `README.md`, `SECURITY.md`, `TODO.md`
  - Verify: test -s .gsd/milestones/M001/slices/S05/S05-UAT-GATE.md && grep -E 'Gate status: (approved|changes-requested|deferred|unresolved)' .gsd/milestones/M001/slices/S05/S05-UAT-GATE.md && grep -q 'Deep-review decision:' .gsd/milestones/M001/slices/S05/S05-UAT-GATE.md

- [x] **T03: Capture blocked-gate verification evidence without claiming release readiness** `est:1h`
  Read the current `S05-UAT-GATE.md` status. If the gate is `approved` or `deferred`, run the fresh release-gate verification suite and write `S05-RELEASE-GATE-EVIDENCE.md` as passing/ready only if all commands pass. If the gate is `unresolved` or `changes-requested`, do not treat this as release approval: write `S05-RELEASE-GATE-EVIDENCE.md` as a blocked-gate evidence index that records the gate status, explains that human UAT and `/deep-review` remain unresolved or require changes, and optionally includes fresh mechanical regression evidence as supporting diagnostics only. In all cases, the evidence index must include command, exit code, verdict, and `.gsd/exec` stdout/stderr artifact path for each command that is run, and must state whether milestone validation should be `pass`, `needs-attention`, or `needs-remediation` based on both the human gate and mechanical results. Do not mutate README/SECURITY/TODO after an approval or deferral without rerunning docs guardrails and refreshing the gate note.
  - Files: `.gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md`, `.gsd/milestones/M001/slices/S05/S05-UAT-GATE.md`, `.gsd/milestones/M001/slices/S05/S05-DOCS-REVIEW-PACKET.md`, `tests/test_docs_accuracy.py`, `tests/test_config_dir.py`, `tests/test_state.py`, `tests/test_startup.py`, `README.md`, `SECURITY.md`, `TODO.md`
  - Verify: test -s .gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md && grep -q 'Gate status:' .gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md && grep -q 'uv run pytest tests/test_docs_accuracy.py -q' .gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md && grep -q 'uv run pytest tests/ -x -q' .gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md && grep -q 'uv run ruff check triggarr/ tests/' .gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md && grep -E 'Release readiness: (ready|blocked|needs-remediation)' .gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md

## Files Likely Touched

- .gsd/milestones/M001/slices/S05/S05-DOCS-REVIEW-PACKET.md
- README.md
- SECURITY.md
- TODO.md
- tests/test_docs_accuracy.py
- .gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md
- .gsd/milestones/M001/slices/S05/S05-UAT-GATE.md
- .gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md
- tests/test_config_dir.py
- tests/test_state.py
- tests/test_startup.py
