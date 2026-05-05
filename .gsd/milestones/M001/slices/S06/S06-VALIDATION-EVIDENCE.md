# S06 Validation Evidence Index

## Reader and Post-Read Action

Reader: a milestone validator or release verifier rerunning M001 validation after S06 remediation.

Post-read action: decide whether M001 is mechanically ready for validation rerun, whether any remediation remains, and what validation posture to assign without rediscovering the S02/S05 evidence history.

## Scope and Source Artifacts

This evidence index is scoped to S06 remediation for M001. It does not modify runtime code, user documentation, or requirement records.

Required S06 artifacts:

| Artifact | Status | Validation use |
|---|---:|---|
| `.gsd/milestones/M001/slices/S06/S06-REQUIREMENT-SCOPE.md` | Present | Defines the M001 requirement-scope boundary and separates direct M001 acceptance themes from historical project-wide requirements. |
| `.gsd/milestones/M001/slices/S06/S06-S02-SUPERSESSION.md` | Present | Canonically supersedes the residual S02/T04 evidence inconsistency and directs validators to the S02 task summaries plus S04 assessment/D001/D002/docs tests. |
| `.gsd/milestones/M001/slices/S06/S06-HUMAN-UAT-GATE.md` | Present | Records human documentation UAT and `/deep-review` as unresolved/escalated and sets validation posture to needs-attention. |
| `.gsd/milestones/M001/slices/S06/S06-VALIDATION-EVIDENCE.md` | Present | This index: fresh S06 command evidence and final validation recommendation. |

## Fresh S06 Verification Commands

All command evidence below was generated during S06/T04 with `gsd_exec`; full stdout/stderr transcripts are stored in `.gsd/exec`.

| Check | Command | Exit code | Verdict | Duration | stdout | stderr |
|---|---|---:|---|---:|---|---|
| Docs accuracy guardrail | `uv run pytest tests/test_docs_accuracy.py -q` | 0 | ✅ pass — 4 passed | 599 ms | `.gsd/exec/d5607921-12e8-4f5b-8882-9b5b464c2c2f.stdout` | `.gsd/exec/d5607921-12e8-4f5b-8882-9b5b464c2c2f.stderr` |
| Focused v2.2 migration/config round-trip | `uv run pytest tests/test_config.py -q -k 'v22 or migrate_v22 or ensure_config_calls_migration or toml_round_trip'` | 0 | ✅ pass — 21 passed, 33 deselected | 361 ms | `.gsd/exec/51713fb7-a84e-4329-9262-83626c954ccb.stdout` | `.gsd/exec/51713fb7-a84e-4329-9262-83626c954ccb.stderr` |
| Config-dir/state/startup/docs integration | `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py tests/test_docs_accuracy.py -q` | 0 | ✅ pass — 56 passed | 538 ms | `.gsd/exec/53b1cafc-394f-42fa-90e4-3a6e293e9663.stdout` | `.gsd/exec/53b1cafc-394f-42fa-90e4-3a6e293e9663.stderr` |
| Full test suite | `uv run pytest tests/ -x -q` | 0 | ✅ pass — 873 passed, 27 warnings | 18,264 ms | `.gsd/exec/be7f20b3-48a9-4829-9d71-4ec833305db6.stdout` | `.gsd/exec/be7f20b3-48a9-4829-9d71-4ec833305db6.stderr` |
| Ruff lint | `uv run ruff check triggarr/ tests/` | 0 | ✅ pass — all checks passed | 68 ms | `.gsd/exec/cefa3725-3f88-499a-a88e-5f81441017a5.stdout` | `.gsd/exec/cefa3725-3f88-499a-a88e-5f81441017a5.stderr` |
| Stale-claim scan | ``rg -n -i -e 'no authentication|authentication is not implemented|config directory is not configurable|make config directory configurable|flat \[radarr\]|\[radarr\][[:space:]]*$|TRIGGARR_GENERAL__|directly trusts.*x-forwarded-proto|routes trust.*x-forwarded-proto|carries `x-forwarded-proto: https`' -- README.md SECURITY.md TODO.md CONTRIBUTING.md docs`` | 0 | ✅ pass — `rg` produced no matches; raw `rg` exit 1 was normalized to pass | 65 ms | `.gsd/exec/f16acee3-9d97-4391-b945-99c349690de0.stdout` | `.gsd/exec/f16acee3-9d97-4391-b945-99c349690de0.stderr` |

## Stale-Claim Scan Semantics

The stale-claim scan is intentionally a no-match check over `README.md`, `SECURITY.md`, `TODO.md`, `CONTRIBUTING.md`, and `docs`. It fails if any stale auth/config/proxy phrase appears, including direct raw `X-Forwarded-Proto` trust claims, legacy flat `[radarr]` examples, stale `TRIGGARR_GENERAL__` examples, or claims that authentication/config-directory support is missing.

The clean S06/T04 rerun produced no matches, so the no-match condition is satisfied.

## Artifact Self-Check Status

Artifact self-check status: pass.

| Check | Command | Exit code | Verdict | Duration | stdout | stderr |
|---|---|---:|---|---:|---|---|
| S06 artifact self-check | `test -s .gsd/milestones/M001/slices/S06/S06-VALIDATION-EVIDENCE.md && uv run python <artifact self-check>` | 0 | ✅ pass — required S06 scope, S02 supersession, human-gate, and evidence-index artifacts exist with expected statuses | 168 ms | `.gsd/exec/637588eb-3468-4748-854e-8ee90f98d5c3.stdout` | `.gsd/exec/637588eb-3468-4748-854e-8ee90f98d5c3.stderr` |

The self-check confirmed:

1. `S06-REQUIREMENT-SCOPE.md` exists and contains the M001 acceptance scope and validation posture guidance.
2. `S06-S02-SUPERSESSION.md` exists and contains canonical supersession instructions for S02/T04.
3. `S06-HUMAN-UAT-GATE.md` exists and contains `Gate status: unresolved/escalated`, `Human UAT: not approved`, and `Validation posture: needs-attention`.
4. `S06-VALIDATION-EVIDENCE.md` exists, is non-empty, and contains entries for docs accuracy, focused migration/config tests, integration tests, full pytest, ruff, stale-claim scan, and artifact self-check.

## Validation Recommendation

Mechanical readiness: pass.

Validation posture recommendation: needs-attention.

Rationale: all fresh S06 mechanical checks above passed, and no test/lint/stale-claim failure requires needs-remediation. However, `S06-HUMAN-UAT-GATE.md` records the human documentation UAT and `/deep-review` gate as unresolved/escalated. Passing mechanical checks do not convert that missing human decision into approval. A milestone validator should therefore rerun M001 validation with a needs-attention posture until a human approval, change request, completed `/deep-review`, or explicit human deferral is recorded.

## Redaction and Artifact Hygiene

This index references only command names, exit codes, durations, verdicts, and local transcript paths. It does not store API keys, cookies, generated auth/session values, password hashes, bearer tokens, or secret environment values.

## Reader-Test Result

Cold-reader result: a validator can identify the S06 scope artifact, the S02 supersession record, the unresolved human gate, the fresh command transcripts, and the correct validation posture without reopening S02 history or interpreting passing tests as human approval.
