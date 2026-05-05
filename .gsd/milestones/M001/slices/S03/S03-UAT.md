# S03: Integrated verification and docs UAT — UAT

**Milestone:** M001
**Written:** 2026-05-05T22:21:33.824Z

# UAT: S03 Integrated verification and docs UAT

## UAT Type

Agent-executed release verification gate for runtime config-dir behavior, documentation consistency, full tests, lint, and operational smoke evidence. This is not a human copy review and not a live Docker/reverse-proxy deployment test.

## Preconditions

- Repository is checked out at the current S03 closure tree.
- `uv` dependencies are installed or available to resolve.
- Commands are run from `/Users/julianamacbook/triggarr`.
- No real Radarr/Sonarr/Lidarr credentials are required.

## Test Case 1 — Focused portable config-dir runtime tests

1. Run `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py -q`.
2. Expected: all focused tests pass, including absolute `TRIGGARR_CONFIG_DIR`, `/config` default behavior, state path derivation, and startup validation coverage.
3. Observed in closure: 52 passed in 0.13s.

## Test Case 2 — README/TODO/SECURITY stale-doc scan

1. Scan README.md, SECURITY.md, TODO.md, and `.gsd/DEFERRED-BACKLOG.md` for retired config-dir TODO language, stale URL-validation phrasing, stale TOML-env wording, and obsolete documentation markers.
2. Expected: no stale markers remain; TODO.md does not present configurable config directory as pending work.
3. Observed in closure: corrected stale-doc marker check passed.

## Test Case 3 — README nested TOML example remains executable documentation

1. Extract TOML code blocks from README.md.
2. Parse the nested Radarr/Sonarr/Lidarr instance example with `tomllib.loads(...)`.
3. Validate the parsed object through `triggarr.models.config.Settings.model_validate(...)`.
4. Expected: at least one nested multi-instance example parses and validates with the real Settings model.
5. Observed in closure: one README Settings TOML block parsed and validated.

## Test Case 4 — Operational custom config-dir smoke check

1. Create a temporary directory.
2. Start a fresh Python process with `TRIGGARR_CONFIG_DIR` set to a custom absolute subdirectory before importing Triggarr modules.
3. Verify `CONFIG_DIR` and `get_config_dir()` equal that directory.
4. Verify `CONFIG_PATH`, `get_config_path()`, `STATE_PATH`, `get_state_path()`, and the scheduler-derived `triggarr.db` path all live under that directory.
5. Expected: all derived paths stay under the custom config directory.
6. Observed in closure: operational check passed.

## Test Case 5 — Project-level regression and lint gate

1. Run `uv run pytest tests/ -x -q`.
2. Expected: full suite passes without stopping on a failure.
3. Run `uv run ruff check triggarr/ tests/`.
4. Expected: ruff reports all checks passed.
5. Observed in closure: 861 tests passed with 25 warnings; ruff all checks passed.

## Test Case 6 — Documentation review gate surrogate

1. Review README.md, TODO.md, and SECURITY.md for current config-dir, nested multi-instance config, Lidarr scope, auth/security posture, and Docker/standalone behavior.
2. Expected for an agent-side gate: docs contain the current claims and no stale blockers from S02/T01-T04.
3. Observed in closure: agent-side review passed mechanically.
4. Caveat: no human documentation review or `/deep-review` was actually performed because auto-mode cannot prompt or wait for external feedback.

## Edge Cases Covered

- Relative `TRIGGARR_CONFIG_DIR` rejection and Docker `/config` fallback are covered by focused tests.
- README config examples are checked against the real Pydantic Settings model, not just prose.
- State and scheduler database path derivation are checked in a fresh process so import-time constants see the custom environment.

## Not Proven By This UAT

- Human judgment on README/SECURITY wording, because auto-mode could not ask the user.
- `/deep-review on the current branch against main`, because no human review loop was available.
- Live Docker container startup with mounted volumes.
- Live reverse-proxy behavior, especially secure-cookie handling and External-auth deployment safety.
- Resolution of the security-review follow-ups around External auth wording and `X-Forwarded-Proto`/`TRUSTED_PROXY_IPS` secure-cookie accuracy.
