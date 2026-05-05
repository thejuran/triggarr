---
estimated_steps: 4
estimated_files: 6
skills_used:
  - verify-before-complete
  - write-docs
  - test
---

# T03: Supersede S02 evidence gap and rerun final verification

Expected task-plan frontmatter skills_used: `verify-before-complete`, `write-docs`, `test`.

After the runtime and documentation fixes land, create the durable evidence trail for this remediation slice and rerun the complete verification matrix. Do not mutate closed S02 history unless GSD tooling explicitly supports it; the planned default is to supersede the placeholder S02 summary with a clear S04 assessment.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|------------|------------------------|
| Prior S02 GSD artifacts | Treat `S02-SUMMARY.md` as non-authoritative if it is the known placeholder; cite task summaries instead | N/A | If a cited artifact is missing, record that as a known limitation and do not claim clean S02 evidence |
| Verification commands | Stop and fix failures before writing pass evidence | Use normal pytest/ruff timeouts and rerun after fixing | N/A |

## Load Profile

- **Shared resources**: local test suite and GSD artifact store.
- **Per-operation cost**: one focused auth/proxy run, one config/docs regression run, one full test suite, one ruff lint run, and one GSD assessment write.
- **10x breakpoint**: full pytest runtime; use focused commands first to localize failures before running the full suite.

## Negative Tests

- **Malformed inputs**: docs-accuracy tests should fail stale or invalid docs content from T02.
- **Error paths**: final verification must fail if direct app-layer `x-forwarded-proto` trust remains in route/middleware cookie logic.
- **Boundary conditions**: evidence assessment must explicitly distinguish agent-side S04 evidence from S05 human documentation UAT, which is not available in auto-mode.

## Steps

1. Verify the S02 evidence state by reading `.gsd/milestones/M001/slices/S02/S02-SUMMARY.md` and the real S02 task summaries; do not rely on the placeholder summary as authoritative evidence.
2. Run a direct source scan proving `triggarr/web/routes.py` and `triggarr/web/middleware.py` no longer contain runtime cookie logic that directly reads `x-forwarded-proto`.
3. Run the final S04 verification matrix: focused auth/proxy tests, config-dir/state/startup regressions plus docs-accuracy tests, full pytest, and ruff lint.
4. Use `gsd_summary_save` to write `.gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md` documenting the S02 placeholder gap, the S04 supersession path, all verification commands/artifacts, and the explicit deferral of human docs UAT to S05.

## Must-Haves

- [ ] S04 evidence assessment cites S02 task summaries as the historical evidence trail and states that S04 supersedes the placeholder `S02-SUMMARY.md` for this remediation.
- [ ] Final evidence includes focused auth/proxy tests, config-dir/state/startup tests, docs-accuracy tests, full pytest, and ruff lint.
- [ ] Evidence does not claim human docs UAT or `/deep-review`; those remain assigned to S05.
- [ ] No secrets or generated credentials appear in verification output or evidence text.

## Inputs

- `triggarr/web/routes.py`
- `triggarr/web/middleware.py`
- `tests/test_auth_routes.py`
- `tests/test_auth_middleware.py`
- `tests/test_root_path.py`
- `tests/test_config_dir.py`
- `tests/test_state.py`
- `tests/test_startup.py`
- `tests/test_docs_accuracy.py`
- `.gsd/milestones/M001/slices/S02/S02-SUMMARY.md`
- `.gsd/milestones/M001/slices/S02/tasks/T01-SUMMARY.md`
- `.gsd/milestones/M001/slices/S02/tasks/T02-SUMMARY.md`
- `.gsd/milestones/M001/slices/S02/tasks/T03-SUMMARY.md`

## Expected Output

- `.gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md`

## Verification

uv run pytest tests/test_auth_routes.py tests/test_auth_middleware.py tests/test_root_path.py -q && uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py tests/test_docs_accuracy.py -q && uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/

## Observability Impact

- Signals added/changed: S04 assessment records verification commands, GSD evidence paths, and the known S02 supersession decision.
- How a future agent inspects this: read `.gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md` plus the referenced `gsd_exec` artifacts.
- Failure state exposed: whether the blocker is runtime auth/proxy behavior, documentation accuracy, config-dir regression, full-suite regression, lint, or evidence incompleteness.
