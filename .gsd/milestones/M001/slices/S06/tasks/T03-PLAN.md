---
estimated_steps: 5
estimated_files: 7
skills_used:
  - write-docs
  - verify-before-complete
---

# T03: Record human UAT and deep-review gate truthfully

Create the S06 human-gate artifact that records the real state of documentation UAT and `/deep-review` without fabricating approval in auto-mode.

Expected executor skills/frontmatter: `write-docs`, `verify-before-complete`.

Steps:
1. Reuse the S05 review packet scope: README/SECURITY/TODO over `a3f09ad^..HEAD`, portable config directory behavior, nested multi-instance TOML, auth modes, External-auth direct-access warnings, ASGI/Uvicorn secure-cookie trust boundary, and TODO retirement.
2. If a real human approval, change request, or explicit deferral is already available in the current execution context, record it with source, timestamp, scope, caveats, and whether `/deep-review` is approved, completed, or deferred.
3. In autonomous/no-human mode, do not call `ask_user_questions`; write `.gsd/milestones/M001/slices/S06/S06-HUMAN-UAT-GATE.md` with gate status `unresolved/escalated`, human UAT `not approved`, `/deep-review` `not completed and not human-deferred`, and validation posture `needs-attention`.
4. If the human requests documentation changes in a future interactive run, keep changes isolated to `README.md`, `SECURITY.md`, or `TODO.md`, then rerun docs guardrails before T04.
5. Do not include secrets, cookies, hashes, generated auth/session values, or environment secret values in the gate record.

Must-haves:
- The artifact distinguishes review preparation and mechanical checks from actual human approval.
- It records a clear validation posture: pass only with real human approval/deferral; otherwise needs-attention.
- It states whether `/deep-review` is completed, explicitly human-deferred until push/tag/release, or unresolved.

Failure Modes (Q5):
- Dependency: human decision availability. If unavailable, preserve unresolved/escalated state; do not infer consent from silence or passing tests.
- Dependency: docs change request. If changes are requested, route them through tracked docs and guardrails rather than modifying gate prose only.

Negative Tests (Q7):
- Confirm the artifact does not contain `approved` unless it also cites a concrete human source/timestamp.
- Confirm unresolved auto-mode artifacts recommend `needs-attention`, not `pass` or `release ready`.

Verification:
- `test -s .gsd/milestones/M001/slices/S06/S06-HUMAN-UAT-GATE.md`
- `rg -n "Gate status|Human UAT|/deep-review|needs-attention|unresolved|human source" .gsd/milestones/M001/slices/S06/S06-HUMAN-UAT-GATE.md`

## Inputs

- `.gsd/milestones/M001/slices/S05/S05-DOCS-REVIEW-PACKET.md`
- `.gsd/milestones/M001/slices/S05/S05-UAT-GATE.md`
- `.gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md`
- `README.md`
- `SECURITY.md`
- `TODO.md`

## Expected Output

- `.gsd/milestones/M001/slices/S06/S06-HUMAN-UAT-GATE.md`

## Verification

test -s .gsd/milestones/M001/slices/S06/S06-HUMAN-UAT-GATE.md && rg -n "Gate status|Human UAT|/deep-review|needs-attention|unresolved|human source" .gsd/milestones/M001/slices/S06/S06-HUMAN-UAT-GATE.md

## Observability Impact

Makes the human release/UAT gate inspectable through an explicit status artifact so future validation can distinguish unresolved human approval from passing mechanical diagnostics.
