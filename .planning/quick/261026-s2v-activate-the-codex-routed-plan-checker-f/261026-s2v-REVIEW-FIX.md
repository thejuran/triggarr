---
phase: quick-261026-s2v
fixed_at: 2026-10-27T01:28:24Z
review_path: .planning/quick/261026-s2v-activate-the-codex-routed-plan-checker-f/261026-s2v-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
rejected: 0
status: all_fixed
---

# Quick Task 261026-s2v: Code Review Fix Report

**Fixed at:** 2026-10-27T01:28:24Z
**Source review:** `.planning/quick/261026-s2v-activate-the-codex-routed-plan-checker-f/261026-s2v-REVIEW.md` (plus one Codex finding folded into WR-04 per task instructions: `codex:e261c58f8464:a1:F001`)
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (WR-01, WR-02, WR-03, WR-04+Codex, IN-01)
- Fixed: 5
- Skipped: 0
- Rejected: 0

Work was done directly on `codex-plan-checker` (no worktree spun up, per explicit
task instruction), touching only `guard.mjs`, `planchk-router.test.mjs`, and
`README.md`. `register.js`, `hooks.json`, manifests, and both `.claude/settings*`
files were never touched. `SA-01` (set aside, needs owner ruling) was out of scope
for this fix pass and is untouched.

## Fixed Issues

### WR-01: `process.exit()` immediately after `process.stderr.write()` risks truncating the refusal message

**Files modified:** `.claude/plugins/planchk-router/hooks/guard.mjs`
**Commit:** `d8d6d84`
**Applied fix:** Both refusal paths (unparseable-stdin, flag-not-enabled) now set
`process.exitCode = 2` instead of calling `process.exit(2)` right after the
`stderr.write()`. The process ends naturally once the `end` handler returns (nothing
else is pending), guaranteeing the write flushes before exit. The two "nothing to
say" paths (`exit(0)` on non-matching subagent, `exit(0)` on flag already `"1"`)
were left as `process.exit(0)` since there is no pending write to flush there and
changing them would be scope creep beyond the finding.

### WR-02: No `error` handler on `process.stdin`

**Files modified:** `.claude/plugins/planchk-router/hooks/guard.mjs`
**Commit:** `341db6f`
**Applied fix:** Added `process.stdin.on('error', ...)` that writes a refusal
message to stderr and sets `process.exitCode = 2`, so a stream-level error (broken
pipe, ECONNRESET) routes through the same deliberate fail-closed contract instead of
Node's uncaught-exception path.

**Stdin-error test — attempted, not added (documented per task instruction "if
practical; otherwise note why not"):** Tried to synthesize a genuine stream-level
`error` event on the child's `process.stdin` from the test harness two ways:
(1) `spawnSync` with a string `input` — no stream object exists to attack, no path
to an error event at all; (2) `spawn` + `child.stdin.destroy(new Error('synthetic'))`
from the parent — this throws an **unhandled 'error' event on the parent's own
socket** (confirmed empirically: `Error: synthetic` with
`Emitted 'error' event on Socket instance`), it does not deliver an `'error'` event
to the child's read-side `process.stdin` at all. Producing a genuine OS-level
broken-pipe/ECONNRESET on the *child's* read fd from a `node:test` harness would
require relying on non-deterministic, platform-dependent kernel/timing behavior
rather than exercising our own code's logic — that's a flaky test, not a reliable
regression guard, so it was left out. The handler's correctness (right message,
right exit code) is covered by code review of the one-line change; no unit test
asserts it fires. This is the same judgment call the finding's own "if practical"
qualifier anticipated.

### WR-03: `hooks.json` dispatch wiring has zero test coverage

**Files modified:** `.claude/plugins/planchk-router/test/planchk-router.test.mjs`
**Commit:** `3ee5120`
**Applied fix:** Added `test('hooks.json: wires register.js as a module and guards
Agent|Task via PreToolUse', ...)`, which loads the real `hooks.json` and asserts
`modules` includes `./register.js`, the `PreToolUse` matcher is exactly `Agent|Task`,
and the hook command references `guard.mjs`.

**Regression-catch verification (per task instruction, temp copies only, real file
never touched):** Copied `hooks.json` to a scratch temp path, (a) dropped
`./register.js` from `modules` — replayed the test's assertions against that copy
and confirmed `assert.ok(hooksConfig.modules.includes('./register.js'))` throws; (b)
narrowed the matcher from `Agent|Task` to `Task` — confirmed
`assert.equal(preToolUse.matcher, 'Agent|Task')` throws with
`+ 'Task' - 'Agent|Task'`. Both regressions are caught. `git status --short` on the
real `hooks.json` was empty before and after — only the temp copies were edited, and
they were deleted afterward.

### IN-01: Asymmetric assertion depth between sibling refusal tests

**Files modified:** `.claude/plugins/planchk-router/test/planchk-router.test.mjs`
**Commit:** `e884e32`
**Applied fix:** The "unparseable stdin" test now also asserts
`assert.match(r.stderr, /could not parse PreToolUse input/)`, matching the assertion
depth of the sibling "flag unset" test just above it.

### WR-04 + Codex `codex:e261c58f8464:a1:F001`: README disable semantics, recheck gap, missing A2 limitation

**Files modified:** `.claude/plugins/planchk-router/README.md`
**Commit:** `3c52116`
**Applied fix (three parts, as specified):**
1. Corrected the "Disable / remove" section. The old text claimed disabling the
   plugin keeps the guard blocking spawns — that's backwards: `claude plugin
   disable` turns off the *entire* plugin, including `guard.mjs` itself, so a
   disabled plugin leaves `bm:bm-plan-checker` running unrouted on the ordinary
   Claude model with nothing blocking it. That's the intended opt-out switch, not a
   fail-closed state. Rewrote the section to state plainly: disabling the plugin →
   ordinary Claude checker (deliberate opt-out); removing/reverting *only* the
   `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` env key while the plugin stays enabled →
   `register.js` stops loading but `guard.mjs` (classic hook) still loads and blocks
   every spawn (the actual fail-closed path).
2. Added a negative (fail-closed) recheck step next to the existing module-loaded
   check, using a `--plugin-dir` sideload from a throwaway directory with no
   `.claude/` of its own and the env flag left unset — matching the method the
   project's own activation evidence used (`SUMMARY.md`'s
   "scratch-plugin-dir-fallback" negative check), explicitly without editing
   `settings.local.json`.
3. Added a "Known limitations" bullet naming the RESEARCH.md Assumptions Log A2
   item: the guard depends on the PreToolUse tool names `Agent`/`Task` and the
   `tool_input.subagent_type` field staying stable; a future Claude Code rename of
   either (concurrent with a hooks-gate change) would let the guard silently
   `exit(0)` on every spawn — which is exactly why the new negative recheck step
   has to be re-run after every update, not just the module-loaded line.

## Verification performed (all fixes)

- `node --check` on every modified `.mjs`/`.js` file: all pass.
- `node --test '.claude/plugins/planchk-router/test/*.test.mjs'`: **10/10 passed**
  (9 original + 1 new wiring test), 0 failed, after every commit.
- `claude plugin validate .claude/plugins` and `claude plugin validate
  .claude/plugins/planchk-router`: both **Validation passed**, final state.
- `git status --short`: clean after every commit; no uncommitted changes remain.
- New wiring test confirmed to fail against two synthetically broken temp copies of
  `hooks.json` (register.js dropped from `modules`; matcher narrowed to `Task`) —
  the real file was never modified.

## Skipped Issues

None.

## Rejected Issues

None.

---

_Fixed: 2026-10-27T01:28:24Z_
_Fixer: Claude (bm-code-fixer)_
_Iteration: 1_
