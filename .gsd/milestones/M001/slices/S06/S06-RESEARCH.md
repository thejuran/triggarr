# M001/S06 — Research

**Date:** 2026-05-05

## Summary

S06 is a validation-remediation slice, not a runtime feature slice. The formal `.gsd/REQUIREMENTS.md` has no Active requirements, so S06 should not reopen or revalidate the full historical requirements table. The blocker is that `M001-VALIDATION.md` treated project-wide validated requirements as if M001 had to prove all of them again; S06 needs a milestone-scope requirement artifact that distinguishes M001-touched acceptance criteria from already-validated/deferred/out-of-scope project requirements. If INST-04 remains mentioned as M001-related continuity evidence, the artifact should cite direct config migration proof: `tests/test_config.py` contains `detect_and_migrate_v22(...)` backup, valid migrated settings, return value, `.migrated` marker, disabled-instance preservation, plaintext-key preservation, `ensure_config(...)` migration, and round-trip tests. Scout verification ran `uv run pytest tests/test_config.py -q -k 'v22 or migrate_v22 or ensure_config_calls_migration or toml_round_trip'` and it passed with `21 passed, 33 deselected` (`.gsd/exec/141ba5bf-0aed-4457-a83d-673467be575a.stdout`).

The second blocker is S02 artifact/state inconsistency. `S02-SUMMARY.md` is a mechanical blocker placeholder, and DB status shows S02 is complete while one task remains pending (`T04`). S04 already supplies the correct canonical evidence trail in `S04/tasks/T03-ASSESSMENT.md`, and prior memory explicitly says not to rely on the S02 placeholder. Important surprise: the old `S02/tasks/T04-PLAN.md` contains pre-S04 wording that says cookies are secure when the request "carries X-Forwarded-Proto: https"; that is now wrong after D001/D002 and S04. Do **not** implement that old wording. Treat T04 as superseded by S04's ASGI/Uvicorn trust-boundary remediation, then either mark T04 complete with a supersession narrative if GSD tooling accepts it, or write a S06 canonical supersession artifact that validation can cite.

The third blocker is still human-gate honesty. S05 produced a strong review packet and release-gate evidence index, but `S05-UAT-GATE.md` intentionally records `Gate status: unresolved` because no human approval, change request, or explicit deferral existed in auto-mode. S06 cannot legitimately turn that into approval from agent scans. It must collect a real human decision if interactive prompting is available, or record an explicit unresolved/escalated state and keep validation from claiming pass. If the human says no push/tag/release is happening, an explicit human deferral of `/deep-review` is acceptable as a release caveat; it must be recorded with source, timestamp, scope, and caveats.

## Recommendation

Plan S06 as four thin remediation tasks:

1. **Requirement-scope coverage artifact.** Create `.gsd/milestones/M001/slices/S06/S06-REQUIREMENT-SCOPE.md` that says there are no Active requirements owned by S06, lists M001-touched acceptance themes (portable config directory, documentation parity, backlog hygiene, auth/proxy doc accuracy, validation evidence), and explicitly classifies project-wide validated requirements as historical/prior coverage rather than M001 revalidation scope. Include direct proof for INST-04 if it remains referenced: `triggarr/config.py:detect_and_migrate_v22`, `tests/test_config.py` v2.2 migration tests, and the scout/fresh command output.
2. **S02 supersession/state repair.** Preferred path: complete `M001/S02/T04` with `gsd_task_complete` using a narrative that S04 superseded T04, no additional source edits are required, and old T04 forwarded-proto wording must not be applied. Key evidence should cite `S04/tasks/T03-ASSESSMENT.md`, D001/D002, `tests/test_docs_accuracy.py`, and fresh S06 guardrail output. If `gsd_task_complete` rejects completing a task under a closed slice, fallback to `.gsd/milestones/M001/slices/S06/S06-S02-SUPERSESSION.md` that explicitly accepts the residual DB inconsistency as canonical supersession and tells validation to use S02 task summaries + S04 T03 assessment, not `S02-SUMMARY.md`.
3. **Human documentation UAT/deep-review decision.** Use `ask_user_questions` before claiming gate resolution. Reuse the S05 review packet scope: README/SECURITY/TODO over `a3f09ad^..HEAD`. A good single question is: approve docs for milestone and defer `/deep-review` until push/tag/release; request documentation changes; or explicitly defer docs UAT and `/deep-review` as release caveats. If changes are requested, patch docs and rerun docs guardrails before continuing. If the user defers, validation can record a caveat, not approval.
4. **Fresh evidence index and validation rerun readiness.** Create `.gsd/milestones/M001/slices/S06/S06-VALIDATION-EVIDENCE.md` after rerunning focused docs/config/migration checks, full pytest, and ruff. It should state whether human UAT is approved/deferred/unresolved and whether `/deep-review` is completed/deferred/unresolved; do not let passing mechanical checks override human-gate state.

Use the installed `write-docs` skill's cold-reader rule for S06 artifacts: name the reader and post-read action in each free-form artifact. For these artifacts, the reader is a milestone validator/release verifier; the post-read action is to decide whether M001 validation can pass, needs attention, or needs remediation without rediscovering the S02/S05 history.

## Implementation Landscape

### Key Files

- `.gsd/milestones/M001/M001-VALIDATION.md` — The authoritative remediation source for S06. It names the blockers: requirement-scope ambiguity, S02 placeholder/pending-task inconsistency, unresolved human UAT/deep-review, and fresh verification before rerun validation.
- `.gsd/milestones/M001/slices/S06/` — Currently empty. New S06 artifacts should live here: recommended names are `S06-REQUIREMENT-SCOPE.md`, `S06-S02-SUPERSESSION.md`, `S06-HUMAN-UAT-GATE.md`, and `S06-VALIDATION-EVIDENCE.md`.
- `.gsd/REQUIREMENTS.md` — Contains zero Active requirements and many already validated/deferred/out-of-scope project requirements. S06 should reference this as the project coverage contract but avoid changing statuses unless the user explicitly decides to rescope requirements.
- `.gsd/milestones/M001/slices/S02/S02-SUMMARY.md` — Non-authoritative blocker placeholder. It should not be cited as delivery proof except to explain the historical failure.
- `.gsd/milestones/M001/slices/S02/S02-PLAN.md` and `S02/tasks/T04-PLAN.md` — Show S02's residual pending task. T04's original secure-cookie wording is superseded and must not be implemented literally.
- `.gsd/milestones/M001/slices/S02/tasks/T01-SUMMARY.md` — Authoritative S02 audit evidence: stale README/SECURITY/TODO/config-dir/auth/multi-instance findings and focused source/test checks.
- `.gsd/milestones/M001/slices/S02/tasks/T02-SUMMARY.md` — Authoritative README edit evidence: Docker/standalone path docs, nested multi-instance TOML, and auth/security guidance.
- `.gsd/milestones/M001/slices/S02/tasks/T03-SUMMARY.md` — Authoritative TODO/SECURITY/backlog evidence: configurable config-dir TODO retired and SECURITY reconciled.
- `.gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md` — The strongest existing canonical supersession artifact. It explicitly says S04 supersedes the S02 placeholder for downstream validation and lists the verification matrix.
- `.gsd/milestones/M001/slices/S05/S05-DOCS-REVIEW-PACKET.md` — Human review checklist for README/SECURITY/TODO over `a3f09ad^..HEAD`. Reuse this packet instead of inventing a new review scope.
- `.gsd/milestones/M001/slices/S05/S05-UAT-GATE.md` — Current human gate state: unresolved, not approval/change request/deferral.
- `.gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md` — Passing mechanical evidence with release readiness blocked and milestone validation recommendation `needs-attention`.
- `tests/test_docs_accuracy.py` — Tracked docs guardrails for External auth upstream auth/authz/direct-access wording, ASGI/Uvicorn secure-cookie wording, stale auth/config-dir claims, and README TOML examples via `Settings.model_validate(...)`.
- `triggarr/config.py` — Config generation/loading and `detect_and_migrate_v22(...)`; direct source for INST-04 continuity proof if needed.
- `tests/test_config.py` — Contains direct v2.2 migration proof: wrapping flat Radarr/Sonarr into `Default`, backup creation, valid migrated settings, `.migrated` marker, disabled app preservation, plaintext key preservation, `ensure_config` migration call, round-trip, and edge cases.
- `README.md`, `SECURITY.md`, `TODO.md` — User-facing docs under human review. Current anchors show portable config-dir guidance, nested TOML, auth modes, External direct-access warnings, ASGI/Uvicorn secure-cookie language, and retired TODO text.

### Build Order

1. **Scope artifact first** — This retires Reviewer A's false premise before other work. Include a table with columns: requirement/capability, M001 relationship, evidence, validation treatment. Classify project-wide requirements as preserved historical coverage unless M001 actually changed them. Include direct INST-04 migration proof or explain why INST-04 is prior coverage only.
2. **S02 supersession/state second** — This removes or canonically accepts the DB/artifact inconsistency. First try to close `S02/T04` as superseded-by-S04 with `gsd_task_complete`; if that fails, write a S06 supersession artifact and leave a clear validation instruction. Do not reopen S02 because `gsd_slice_reopen` resets all tasks and would create needless rework.
3. **Human gate third** — Ask the user for the documentation/deep-review decision after the evidence scope is clear. If the user requests changes, execute those docs changes before final verification. If no human response exists, S06 must remain unresolved/escalated; do not fabricate deferral.
4. **Fresh verification last** — Rerun commands after any docs changes and after recording the human decision. Then write a S06 evidence index and rerun milestone validation.

### Verification Approach

Fresh S06 verification should use `gsd_exec` for noisy commands and save stdout/stderr artifact paths in `S06-VALIDATION-EVIDENCE.md`.

Minimum commands:

```bash
uv run pytest tests/test_docs_accuracy.py -q
uv run pytest tests/test_config.py -q -k 'v22 or migrate_v22 or ensure_config_calls_migration or toml_round_trip'
uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py tests/test_docs_accuracy.py -q
uv run pytest tests/ -x -q
uv run ruff check triggarr/ tests/
```

Recommended stale-claim scan, using `rg` rather than `git grep` to avoid relying on git commands in auto-mode:

```bash
rg -n -i -e 'no authentication|authentication is not implemented|config directory is not configurable|make config directory configurable|flat \[radarr\]|\[radarr\][[:space:]]*$|TRIGGARR_GENERAL__|directly trusts.*x-forwarded-proto|routes trust.*x-forwarded-proto|carries `x-forwarded-proto: https`' -- README.md SECURITY.md TODO.md CONTRIBUTING.md docs
```

For this `rg` scan, no matches is the pass condition, so run it in a wrapper that exits 0 only when no matches are found. Also add an artifact self-check that confirms the S06 scope, supersession, human gate, and evidence files exist and contain their expected statuses.

Scout checks already run:

- `uv run pytest tests/test_docs_accuracy.py -q` → exit 0, `4 passed` (`.gsd/exec/141ba5bf-0aed-4457-a83d-673467be575a.stdout`).
- `uv run pytest tests/test_config.py -q -k 'v22 or migrate_v22 or ensure_config_calls_migration or toml_round_trip'` → exit 0, `21 passed, 33 deselected` (same stdout artifact).

These are research evidence only; executor closure still needs fresh outputs.

## Constraints

- There are no Active requirements for S06. Do not invent new requirement IDs or change requirement statuses just to satisfy validation. Prefer a S06 requirement-scope artifact over DB requirement mutation.
- S02/T04's old direct-forwarded-proto wording is superseded by D001/D002 and S04. Any S06 artifact should say secure-cookie decisions use the ASGI request scheme; `X-Forwarded-Proto` only matters after Uvicorn accepts forwarded headers from `TRUSTED_PROXY_IPS` peers.
- Human UAT cannot be inferred from agent scans, passing tests, review packet creation, or absence of objections. It must come from a human approval/change request/explicit deferral record.
- Project convention requires offering `/deep-review` before pushing to main or creating a release tag. M001 scope excludes publishing/tagging/pushing, so a human can defer `/deep-review` until release, but the deferral must be explicit.
- Do not include real API keys, password hashes, generated auth/session secrets, cookies, or secret environment values in review/gate artifacts.
- Avoid reopening S02 unless absolutely necessary; reopening a completed slice resets all its tasks and summaries.

## Common Pitfalls

- **Trying to prove every validated requirement again** — M001 is about portable config/docs/backlog hygiene. The requirement-scope artifact should separate milestone acceptance from historical product requirements such as tag autocomplete, version display, and per-instance dashboard features.
- **Treating `S02-SUMMARY.md` as authoritative** — It is explicitly a recovery placeholder. Use S02 task summaries plus S04 T03 assessment.
- **Applying stale S02/T04 wording** — The pending T04 plan predates S04's security decision and contains unsafe wording now guarded against by `tests/test_docs_accuracy.py`.
- **Marking human UAT passed from S05 evidence** — S05 deliberately says unresolved. S06 must obtain a human decision or preserve that unresolved state.
- **Mutating docs after approval without refreshing evidence** — Any README/SECURITY/TODO change after approval/deferral requires `tests/test_docs_accuracy.py` and the human gate/evidence index to be refreshed.

## Open Risks

- `gsd_task_complete` may reject completing `S02/T04` because S02 is already marked complete. If so, fallback to S06 canonical supersession, but validation may still need to accept the residual task-count mismatch explicitly.
- A human may request documentation changes, which will turn S06 from artifact-only remediation into a docs-editing slice. Keep docs corrections isolated to README/SECURITY/TODO and rerun docs guardrails immediately.
- If no human response is available in auto-mode, S06 cannot honestly satisfy the human UAT/deep-review remediation item. The correct behavior is to escalate/block validation rather than silently proceed.

## Skills Discovered

| Technology / Work Type | Skill | Status |
|---|---|---|
| Documentation artifacts / cold-reader checks | `write-docs` | Installed and used for research guidance |
| Release/code review fallback if `/deep-review` is unavailable | `turingmind-code-review`, `review`, `security-review`, `test` | Installed; only use if the user asks to run a review or if the actual `/deep-review` command is unavailable |

No external technology-specific skill search was needed. S06 is GSD artifact remediation, documentation gating, pytest/ruff verification, and existing Triggarr config migration proof; it does not introduce a third-party API or unfamiliar framework.
