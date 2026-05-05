# S03: Integrated verification and docs UAT

**Goal:** Close the milestone by verifying the assembled runtime/docs state rather than relying on individual slice claims.
**Demo:** After this: focused tests, full tests, lint, operational config-dir check, and user documentation review have all passed, so the milestone can be completed with evidence.

## Must-Haves

- Focused config-dir tests pass.
- Full test suite passes.
- Ruff passes.
- A fresh custom config-dir operational check is recorded.
- User reviews documentation changes before UAT completion.

## Proof Level

- This slice proves: Final assembly proof with command evidence and human docs-review gate.

## Integration Closure

Nothing remains before the milestone is usable end-to-end once this slice passes and user review feedback is incorporated.

## Verification

- Records final verification evidence, docs-review feedback, and any remaining caveats for future agents.

## Tasks

- [x] **T01: Run focused runtime and docs verification** `est:30m`
  Why: docs and runtime behavior are now coupled; focused verification should rerun after all code/docs edits to catch regressions before expensive full-suite checks.
  - Files: `tests/test_config_dir.py`, `tests/test_state.py`, `tests/test_startup.py`, `README.md`, `TODO.md`, `.gsd/DEFERRED-BACKLOG.md`
  - Verify: `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py -q` and stale-content `rg` checks from S02.

- [x] **T02: Run full tests and lint** `est:1h`
  Why: milestone completion requires project-level confidence, not only focused checks.
  - Files: `triggarr`, `tests`, `README.md`, `TODO.md`
  - Verify: `uv run pytest tests/ -x -q` and `uv run ruff check triggarr/ tests/`

- [ ] **T03: Run user docs review gate before UAT** `est:45m + review wait`
  Why: documentation changes need human judgment, and project preference requires prompting the user to run deep review before UAT when completing a slice.
  - Files: `README.md`, `TODO.md`, `.gsd/DEFERRED-BACKLOG.md`
  - Verify: Manual review gate — user confirms README/docs changes are acceptable and any requested deep-review findings are resolved before slice completion.

## Files Likely Touched

- tests/test_config_dir.py
- tests/test_state.py
- tests/test_startup.py
- README.md
- TODO.md
- .gsd/DEFERRED-BACKLOG.md
- triggarr
- tests
