# S06 Requirement Scope Coverage

## Reader and Post-Read Action

Reader: a milestone validator or release verifier reviewing M001 after S06 remediation.

Post-read action: decide whether M001 requirement validation can pass, needs attention, or needs remediation without reopening unrelated historical project requirements.

## Scope Decision

`.gsd/REQUIREMENTS.md` currently has no Active requirements. Its coverage summary records:

- Active requirements: 0
- Validated: 18
- Deferred: 2
- Out of scope: 3

S06 does not mutate requirement records, add requirement IDs, or reopen historically validated/deferred/out-of-scope work. The validation question for M001 is narrower: did this milestone prove its own acceptance themes and preserve the evidence chain for any project-wide requirements it touched?

The task input names `.gsd/milestones/M001/M001-VALIDATION.md`, but that file is not present in the tracked milestone directory. Treat that as a source-artifact gap, not as proof that all historical requirements must be re-opened. This artifact therefore prefers the current tracked requirement register, M001 context/roadmap, S06 plan, and current source/tests over absent or stale validation summaries.

## M001 Acceptance Themes

| Requirement/capability | M001 relationship | Evidence | Validation treatment |
|---|---|---|---|
| Portable config directory behavior | Direct M001 acceptance theme. The milestone exists to verify `TRIGGARR_CONFIG_DIR` and preserve Docker `/config` defaults. | M001 context and roadmap define the acceptance contract; slice-level verification is scheduled in S06/T04 for config-dir/state/startup/docs tests. | In scope for M001 validation. Require fresh S06/T04 command evidence before final milestone pass. |
| Documentation accuracy for config, auth/security, Docker, and standalone install | Direct M001 acceptance theme. README/SECURITY/TODO must match current behavior and avoid stale missing-config-dir claims. | M001 context, S05 gate artifacts, and S06 plan identify docs accuracy as a release gate; S05 mechanical docs checks passed but human UAT remains unresolved. | In scope for M001 validation. Mechanical evidence may support the claim; unresolved human UAT keeps the gate at needs-attention until a human decision exists. |
| Stale TODO/backlog hygiene | Direct M001 acceptance theme. The stale configurable-config-directory TODO must not misdirect future work. | M001 context names the stale TODO risk; S05 evidence records a no-match stale-claim scan over README/SECURITY/TODO/CONTRIBUTING/docs. | In scope for M001 validation. S06/T04 should refresh stale-claim evidence after all S06 artifacts exist. |
| S02 documentation/evidence chain | M001 validation remediation concern, not a new product capability. S06 must resolve or canonically supersede the S02 placeholder/task-state inconsistency. | S06 plan requires either S02/T04 completion as superseded-by-S04 or an S06 supersession artifact that points validation to S02 task summaries plus `S04/tasks/T03-ASSESSMENT.md`. | In scope for S06 remediation. Validation should not rely on a placeholder `S02-SUMMARY.md` when a canonical supersession record exists or is required. |
| Human documentation UAT and `/deep-review` gate | Direct M001 release-readiness gate. Auto-mode cannot convert agent scans into human approval. | S05 `S05-UAT-GATE.md` and `S05-RELEASE-GATE-EVIDENCE.md` record the gate as unresolved and release readiness as blocked. | In scope for final validation posture. If still unresolved after S06, validation should be needs-attention rather than pass. |
| INST-04 auto-migration from v2.2 | Historical validated requirement with direct source/test proof relevant when migration compatibility is mentioned by M001 docs. | `triggarr/config.py` defines `detect_and_migrate_v22(...)`, which detects flat v2.2 sections, backs up the original TOML, writes the nested multi-instance structure atomically, creates a `.migrated` marker, and returns whether migration ran. `tests/test_config.py` includes migration tests for v2.2 detection, wrapping Radarr/Sonarr under `Default`, backup creation, marker creation, preserving disabled apps, preserving plaintext API key values in the written TOML instead of SecretStr masking, `ensure_config(...)` invoking migration, and TOML round-trip behavior. Focused command pending S06/T04: `uv run pytest tests/test_config.py -q -k 'v22 or migrate_v22 or ensure_config_calls_migration or toml_round_trip'`. | Preserve prior validated coverage and refresh focused command evidence in T04. Do not fabricate a fresh pass in this artifact before T04 reruns the command. |

## Project-Wide Historical Requirements

| Requirement/capability | M001 relationship | Evidence | Validation treatment |
|---|---|---|---|
| INST-01 and INST-02 multiple named Radarr/Sonarr instances | Historical validated multi-instance capability. M001 documentation may describe this format, but S06 is not rebuilding the runtime feature. | `.gsd/REQUIREMENTS.md` marks both validated with M001/S05 ownership and support from earlier slices. Current config model and docs tests are the relevant preservation checks if documentation claims mention them. | Historical/prior coverage unless M001 documentation contradicts current behavior. Validate M001 docs accuracy, not the full runtime feature from scratch. |
| INST-03 independent round-robin cursors | Historical validated capability owned by M001/S02. S06 only cares about evidence-chain consistency if S02 artifacts conflict. | `.gsd/REQUIREMENTS.md` marks it validated and notes per-instance state model with v2.2 migration. S06/T02 handles S02 supersession if needed. | Historical/prior coverage. Do not reopen except to resolve the S02 evidence inconsistency for validator navigation. |
| INST-04 auto-migration from v2.2 | Historical validated continuity requirement with direct M001 relevance because docs/config compatibility can mention migration. | See the M001 acceptance table above for direct source/test proof and the pending S06/T04 focused migration command. | Historical/prior coverage with fresh focused command evidence pending T04. |
| INST-05 through INST-07 instance UI, enable/disable, and health summary | Historical validated UI/operability capabilities. M001 may mention them only as current product context. | `.gsd/REQUIREMENTS.md` marks these validated with UI and health-summary test notes. | Historical/prior coverage unless M001 changed related docs. Validation should check docs for accuracy, not re-prove the UI feature set. |
| TAG-01 through TAG-06 tag filtering and tag visibility | Historical validated tag capabilities outside the portable-config/docs-remediation milestone. | `.gsd/REQUIREMENTS.md` marks these validated and notes filtering, tag resolution, dashboard warning, and autocomplete evidence. | Historical/prior coverage. Not part of M001 pass/fail unless M001 docs introduce inaccurate tag claims. |
| OBS-01 through OBS-03 per-instance observability/history/stats | Historical validated observability capabilities. M001/S06 requirement impact explicitly preserves OBS-02 and OBS-03 coverage without changing runtime behavior. | `.gsd/REQUIREMENTS.md` marks these validated with dashboard/history/stats test notes. | Historical/prior coverage. S06 should preserve coverage and avoid stale documentation, not re-run every historical observability proof. |
| VER-01 and VER-02 version display/update notification | Historical validated operability capabilities unrelated to M001 acceptance themes. | `.gsd/REQUIREMENTS.md` marks both validated with version/update test notes. | Historical/prior coverage. Out of M001 validation scope unless altered by docs. |
| DEFER-01 and DEFER-02 deferred cross-instance dedupe and dynamic hot-add | Explicitly deferred project work, not M001 acceptance. | `.gsd/REQUIREMENTS.md` marks both deferred with no primary owner. | Preserve deferral. M001 should not be penalized for not delivering deferred capabilities. |
| OOS-01 through OOS-03 auto-discovery, tag management, and tag exclusion | Explicitly out-of-scope anti-features. | `.gsd/REQUIREMENTS.md` marks these out of scope with safety/product rationale. | Preserve out-of-scope treatment. M001 should not introduce or validate these anti-features. |

## Validation Posture Guidance

A milestone validator should use this treatment:

1. For M001 acceptance themes, require fresh S06 evidence: task artifacts, docs/config/full/lint/stale-claim commands, and the human-gate record.
2. For historically validated requirements, preserve prior coverage unless current M001 files changed or contradicted the requirement.
3. For deferred and out-of-scope entries, confirm M001 did not accidentally pull them into scope.
4. For INST-04, use the current migration implementation and `tests/test_config.py` migration tests as the direct proof surface, with fresh focused command output pending T04.
5. If command evidence is not yet refreshed, mark the specific check pending T04 rather than treating it as passed.

## Reader-Test Result

A cold-reader milestone validator can now distinguish direct M001 acceptance themes from historical project-wide requirements, see that Active requirements are zero, identify the absent validation source artifact, and know which evidence should be refreshed before deciding pass, needs-attention, or remediation.
