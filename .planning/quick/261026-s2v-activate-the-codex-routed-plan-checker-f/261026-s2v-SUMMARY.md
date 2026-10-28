---
phase: quick-261026-s2v
plan: 01
subsystem: tooling
tags: [claude-code-plugin, model-gateway, hooks, codex, plan-checker]

requires:
  - phase: 84-codex-plan-checker-investigation
    provides: proven hook shape, model id, fail-closed behavior (N1-N4), activation boundary decision
provides:
  - Triggarr-only agent.spawn router for bm:bm-plan-checker to the model-gateway Codex model
  - Classic PreToolUse guard that fail-closes when the hooks-module gate is off
  - Local-only activation (committed plugin source + owner's gitignored settings.local.json switch)
  - Live routing evidence (positive smoke + negative guard check) in scratch
affects: [phase-85-planning, future-plan-checker-runs]

tech-stack:
  added: []
  patterns: ["agent.spawn module hook rewriting only `model`, no try/catch (errors must surface)", "classic PreToolUse guard as fail-closed backstop for a module-hook gate"]

key-files:
  created:
    - .claude/plugins/.claude-plugin/marketplace.json
    - .claude/plugins/planchk-router/.claude-plugin/plugin.json
    - .claude/plugins/planchk-router/hooks/hooks.json
    - .claude/plugins/planchk-router/hooks/register.js
    - .claude/plugins/planchk-router/hooks/guard.mjs
    - .claude/plugins/planchk-router/test/planchk-router.test.mjs
    - .claude/plugins/planchk-router/README.md
  modified:
    - .claude/settings.local.json (local only, gitignored, never committed)

key-decisions:
  - "PRECEDENCE: UNKNOWN recorded (scratch config dir had no auth, matching the plan's own documented fallback), so Task 3's negative check used method scratch-plugin-dir-fallback instead of cli-settings-override"
  - "Node v25.9.0's `node --test <dir>/` CLI form does not recurse into a bare directory argument (reproduced independently outside the project); used the equivalent glob form `node --test '<dir>/*.test.mjs'` to actually run and observe the suite"

requirements-completed: [PLANCHK-ACTIVATE]

duration: ~20min
completed: 2026-10-27
---

# Quick Task 261026-s2v: Activate the Codex-routed plan checker (Triggarr only) Summary

**Committed a Triggarr-only `planchk-router` plugin (agent.spawn model rewrite + fail-closed PreToolUse guard), registered it at local scope with the early-access hooks flag in the owner's gitignored settings.local.json, and proved live routing with one smoke run plus a negative guard check — all with the owner's pre-existing local settings keys verified byte/deep-equal before and after.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-10-27
- **Tasks:** 3/3 complete
- **Files modified:** 7 committed (plugin) + 1 local-only (`.claude/settings.local.json`, never committed)

## Accomplishments

- A `bm:bm-plan-checker` subagent spawn from the Triggarr root now routes to the model-gateway Codex model (`claude-gpt-6-astra[1m]` / backend `gpt-6-astra`) while the orchestrating session stays on Anthropic (`claude-opus-5-5[1m]`) — proven live via one real checker run against a throwaway toy plan.
- A classic PreToolUse guard closes the gap Phase 84's research identified: if the module hook ever fails to load (lost settings file, new machine, a Claude Code update that changes the gate), the checker spawn is now refused visibly instead of silently running on a Claude model — proven live via a session-sideload run with no flag anywhere.
- Activation lives entirely in the owner's gitignored `.claude/settings.local.json`; every pre-existing key in that file (`permissions`, `enabledMcpjsonServers`) was proven byte/deep-equal to a pre-activation backup, first on an isolated byte-copy, then on the live file after every write, with no restore ever triggered.

## Task Commits

1. **Task 1: Commit the planchk-router plugin, guard, tests and re-enable note**
   - `8424611` (test) — add failing planchk-router tests (RED: confirmed failing before guard.mjs/register.js existed)
   - `e261c58` (feat) — add Triggarr-only Codex plan-checker router plugin (GREEN: 9/9 node:test pass, both `claude plugin validate` pass)
2. **Task 2: Dry-run on a byte-copy, register at local scope with restore-on-failure, prove the load, write the gate** — no repo commits (writes only `.claude/settings.local.json`, local-only and never committed, plus scratch evidence under `~/scratch/planchk-activation/activate/`)
3. **Task 3: Live smoke run (positive) and guard negative check** — no repo commits (scratch only, under `~/scratch/planchk-activation/smoke-toy/`, `smoke-driver.txt`, `run_smoke.py`, `smoke/`, `negproj/`)

No plan-metadata commit from this executor — per this task's constraints, the docs commit (SUMMARY.md, STATE.md) is the orchestrator's responsibility, not this executor's.

## Files Created/Modified

- `.claude/plugins/.claude-plugin/marketplace.json` — local directory marketplace `triggarr-local`, lists only `planchk-router`
- `.claude/plugins/planchk-router/.claude-plugin/plugin.json` — plugin manifest
- `.claude/plugins/planchk-router/hooks/hooks.json` — registers the `register.js` module plus a `PreToolUse` guard on matcher `Agent|Task`
- `.claude/plugins/planchk-router/hooks/register.js` — `agent.spawn` hook rewriting only `bm:bm-plan-checker`'s `model`; no try/catch (errors surface, never a silent Claude fallback)
- `.claude/plugins/planchk-router/hooks/guard.mjs` — classic PreToolUse guard; exits 2 for a `bm:bm-plan-checker` spawn when `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` is not `"1"`, or when stdin is unparseable
- `.claude/plugins/planchk-router/test/planchk-router.test.mjs` — 9 `node:test` cases covering every behavior bullet
- `.claude/plugins/planchk-router/README.md` — re-enable/disable steps, Accept/Retry/Stop caution, carried-forward limitations
- `.claude/settings.local.json` (local only, not committed) — gained `extraKnownMarketplaces`, `enabledPlugins`, `env.CLAUDE_CODE_ENABLE_FUNCTION_HOOKS`; `permissions` and `enabledMcpjsonServers` proven deep-equal to the pre-activation backup

## Decisions Made

- **Unparseable guard stdin fails closed (exit 2):** chosen per the plan's own discretion note — a payload-format change after a Claude Code update shows up loudly (every Agent/Task spawn refused) instead of passing every spawn silently.
- **Negative-check method = scratch-plugin-dir-fallback:** `precedence.txt` records `PRECEDENCE: UNKNOWN` because both precedence-probe runs in the isolated scratch config dir hit "Not logged in" before reaching any hook-loading step (that config dir was never authenticated — CLAUDE_CONFIG_DIR scopes OAuth state separately from the default `~/.claude`). This is the plan's own documented fallback case ("UNKNOWN if ... either run errors, for example no auth in the scratch config dir") and is explicitly not a stop condition; it only selects which Task 3 method to use.
- **Model id re-check:** `model-gateway.js doctor` confirmed `gpt-6-astra | claude-gpt-6-astra[1m]` is still present and still the newest-named Codex row (evidence date 2026-09-05, same as Phase 84) — no stop condition triggered.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking tooling issue] `node --test <dir>/` does not recurse into a bare directory argument on the installed Node v25.9.0**
- **Found during:** Task 1, running the task's literal automated verify command.
- **Issue:** `node --test .claude/plugins/planchk-router/test/` fails with `Error: Cannot find module '.../test'` (a CJS-loader resolution error), even once the test file and all implementation files exist. Reproduced independently in an unrelated `/tmp` scratch directory with a trivial passing test, confirming this is a Node CLI/environment behavior on this machine's Node build, not a defect in the plugin or its tests. `node --test '<dir>/*.test.mjs'` (explicit glob, quoted so Node does its own expansion) and bare `node --test` with no args (auto-discovery) both work correctly on the same files.
- **Fix:** Used the equivalent glob-form invocation (`node --test '.claude/plugins/planchk-router/test/*.test.mjs'`) to actually run the suite and observe real pass/fail output, per this task's own `type="auto"` requirement to run verification and observe real results rather than assume. All 9 tests passed. The remaining chained checks in Task 1's verify string (both `claude plugin validate` calls, the register.js grep checks, the README grep checks, the untracked-file check) were each run and passed exactly as written.
- **Cost if wrong:** None — this is a reporting/tooling-invocation substitution, not a code change. The literal plan command, as written, would report a false failure on this Node build regardless of code correctness; a future reader following this task's verify line verbatim should expect the same dir-argument quirk and use the glob form instead.
- **Files modified:** None (test/implementation files unaffected).
- **Commit:** N/A (verification-invocation choice, not a code change).

## Incident: permission values momentarily printed to tool output

**What happened:** During Task 2's dry-run verification (before the live write), one command (`cat .claude/settings.local.json | python3 -m json.tool`) dumped the full parsed contents of the dry-run copy of the owner's `settings.local.json` — including the full `permissions.allow` list (~130 entries) and `enabledMcpjsonServers` — to tool output in this transcript. This is the owner's own pre-existing permission list (copied byte-for-byte from the live backup into the isolated dry-run project), not a secret or credential, but it directly violates this task's explicit constraint: "Never print permission values from settings.local.json to output or evidence files."

**Why it happened:** I ran a human-readable pretty-print of the whole file to sanity-check the registration result, instead of checking only keys/counts as the rest of the task consistently did.

**Corrective action:** Flagged immediately in the transcript when it happened. Every subsequent check in Tasks 2 and 3 (dry-run integrity, live integrity, re-hash comparisons, assertions) printed only key names, booleans, counts, or PASS/FAIL — never values — and no evidence file written to scratch or committed to the repo contains any permission value. No evidence file is affected; this was a live tool-output-only incident, not a file-persistence one.

**Cost if wrong (i.e., if this is treated as acceptable rather than flagged):** If unflagged, a reviewer could reasonably conclude the "never print values" constraint held throughout, when it did not for one command. Flagging it here ensures the owner has an accurate record and can decide whether any remediation (e.g., scrubbing this transcript) is warranted.

## Live Evidence (scratch, not committed)

All under `~/scratch/planchk-activation/`:
- `activate/before.txt`, `activate/dryrun.txt` (PASS), `activate/precedence.txt` (`PRECEDENCE: UNKNOWN`), `activate/live-integrity.txt` (PASS), `activate/load-check.txt`, `activate/other-dir.txt`, `activate/gate.txt` (`GATE: PASS`), `activate/integrity.py`, `activate/merge_env.py`
- `smoke-toy/` (throwaway fixture, copied from the Phase 84 pilot toy project, never modified)
- `smoke-driver.txt`, `run_smoke.py`, `smoke/verdict.txt` (PASS), `smoke/negative.txt` (PASS, `METHOD: scratch-plugin-dir-fallback`)
- `negative-driver.txt`, `negative_run.py`, `negproj/` (`git init` only, no `.claude/`)
- No `RESTORED.txt` was ever created (no restore was needed at any step).

## Final Verification

- `node --test '.claude/plugins/planchk-router/test/*.test.mjs'`: **9/9 passed**, 0 failed.
- `claude plugin validate .claude/plugins` and `claude plugin validate .claude/plugins/planchk-router`: both **Validation passed**.
- Live smoke run (session `df8296a0-4227-4cb3-9c76-057040babd4e`): completed in 167.9s (bound 900s); result contains `## ISSUES FOUND`; `modelUsage` keys exactly `["claude-opus-5-5[1m]", "claude-gpt-6-astra[1m]"]`; gateway route log for that session shows only `anthropic claude-opus-5-5` (3) and `codex gpt-6-astra` (17); debug log shows the module `loaded` line; `git status --porcelain` unchanged before/after.
- Negative check (session `b27e9bb9-4178-4c7a-b820-1e0966f7144f`, method scratch-plugin-dir-fallback): completed in 12.2s (bound 300s); result contains `planchk-router: refusing bm:bm-plan-checker spawn`; `modelUsage` keys exactly `["claude-opus-5-5[1m]"]`; gateway route log for that session shows only `anthropic claude-opus-5-5` (2), no codex lines; debug log confirms the PreToolUse guard registered and fired, and the module hook was correctly not loaded.
- `uv run pytest tests/ -x -q`: **2432 passed**, 0 failed (38 pre-existing deprecation warnings, unrelated to this change).
- `uv run ruff check triggarr/ tests/`: **All checks passed!**
- `git status --porcelain` in `/Users/julianamacbook/triggarr`: empty after every step; `.claude/settings.local.json` confirmed untracked (`git ls-files --error-unmatch` fails as expected) and ignored (`git check-ignore -q` succeeds).

## Known Stubs

None. No hardcoded empty values, placeholder text, or unwired data sources were introduced.

## Threat Flags

None beyond what the plan's own threat model already covers (T-s2v-01 through T-s2v-08, T-s2v-SC) — no new network endpoints, auth paths, file-access patterns, or schema changes outside that register were introduced.

## Self-Check: PASSED

All 7 committed plugin files found on disk at their claimed paths. Both commit hashes (`8424611`, `e261c58`) found in `git log --oneline --all`. All 6 spot-checked scratch evidence files (`activate/gate.txt`, `activate/dryrun.txt`, `activate/precedence.txt`, `activate/live-integrity.txt`, `smoke/verdict.txt`, `smoke/negative.txt`) found on disk. No missing items.
