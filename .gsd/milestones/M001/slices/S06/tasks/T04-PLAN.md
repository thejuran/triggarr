---
estimated_steps: 5
estimated_files: 10
skills_used:
  - test
  - verify-before-complete
  - write-docs
---

# T04: Refresh validation evidence index and rerun readiness checks

Rerun the focused/full mechanical verification suite after S06 artifacts exist and write a single evidence index that validation can consume without rediscovering the S02/S05 history.

Expected executor skills/frontmatter: `test`, `verify-before-complete`, `write-docs`.

Steps:
1. Use `gsd_exec` for each noisy verification command and capture command, exit code, verdict, duration if available, stdout path, and stderr path.
2. Run docs accuracy, focused v2.2 migration/config round-trip tests, config-dir/state/startup/docs integration tests, full pytest, ruff, stale-claim scan, and an S06 artifact self-check.
3. Write `.gsd/milestones/M001/slices/S06/S06-VALIDATION-EVIDENCE.md` for a cold-reader milestone validator/release verifier; reference the S06 requirement-scope, S02 supersession/repair, human gate, and command evidence artifacts.
4. Tie validation posture to the human-gate state: if T03 is unresolved/escalated, recommend `needs-attention` even when all mechanical commands pass.
5. Do not modify runtime code or user docs in this task unless T03 recorded requested documentation changes; if docs changed, rerun docs guardrails before writing final evidence.

Must-haves:
- Evidence includes fresh S06 runs of all minimum commands, not only S05 or research outputs.
- The stale-claim scan treats no matches as pass and scans README/SECURITY/TODO/CONTRIBUTING/docs with `rg`.
- The artifact self-check confirms the S06 scope, S02 supersession/repair, human gate, and evidence files exist and contain expected statuses.

Failure Modes (Q5):
- Dependency: test/lint command failure. Record failing exit code and stderr path, stop claiming readiness, and set validation posture to needs-remediation.
- Dependency: human gate unresolved. Do not let passing tests override unresolved UAT/deep-review status.
- Dependency: command output volume. Use `gsd_exec` so full transcripts stay in `.gsd/exec/*` and the evidence index only references paths and concise verdicts.

Load Profile (Q6):
- Shared resources: local test runner, filesystem, `.gsd/exec` artifact directory.
- Per-operation cost: one docs guardrail run, one focused config migration run, one focused integration run, one full pytest run, one ruff run, one stale scan, and one small artifact self-check.
- 10x breakpoint: repeated full pytest runs cost wall-clock time and context if raw output is pasted; mitigate by using `gsd_exec` and referencing artifacts.

Negative Tests (Q7):
- Stale-claim scan must fail on stale auth/config/proxy phrases including direct raw `X-Forwarded-Proto` trust claims and flat `[radarr]` examples.
- Artifact self-check must fail if any required S06 artifact is missing or if human-gate status is absent.

Verification:
- `uv run pytest tests/test_docs_accuracy.py -q`
- `uv run pytest tests/test_config.py -q -k 'v22 or migrate_v22 or ensure_config_calls_migration or toml_round_trip'`
- `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py tests/test_docs_accuracy.py -q`
- `uv run pytest tests/ -x -q`
- `uv run ruff check triggarr/ tests/`
- wrapper scan: `rg -n -i -e 'no authentication|authentication is not implemented|config directory is not configurable|make config directory configurable|flat \[radarr\]|\[radarr\][[:space:]]*$|TRIGGARR_GENERAL__|directly trusts.*x-forwarded-proto|routes trust.*x-forwarded-proto|carries `x-forwarded-proto: https`' -- README.md SECURITY.md TODO.md CONTRIBUTING.md docs` must produce no matches.
- `test -s .gsd/milestones/M001/slices/S06/S06-VALIDATION-EVIDENCE.md` and artifact self-check pass.

## Inputs

- `.gsd/milestones/M001/slices/S06/S06-REQUIREMENT-SCOPE.md`
- `.gsd/milestones/M001/slices/S06/S06-S02-SUPERSESSION.md`
- `.gsd/milestones/M001/slices/S02/tasks/T04-SUMMARY.md`
- `.gsd/milestones/M001/slices/S06/S06-HUMAN-UAT-GATE.md`
- `tests/test_docs_accuracy.py`
- `tests/test_config.py`
- `tests/test_config_dir.py`
- `tests/test_state.py`
- `tests/test_startup.py`
- `README.md`
- `SECURITY.md`
- `TODO.md`

## Expected Output

- `.gsd/milestones/M001/slices/S06/S06-VALIDATION-EVIDENCE.md`

## Verification

Run the listed pytest, ruff, stale-claim scan, and S06 artifact self-check through gsd_exec; then require `test -s .gsd/milestones/M001/slices/S06/S06-VALIDATION-EVIDENCE.md` and evidence index entries for each command.

## Observability Impact

Creates the final S06 diagnostics index linking pass/fail status, command evidence artifacts, human-gate state, and validation recommendation for future milestone validation.
