---
phase: quick-261026-s2v
reviewed: 2026-10-27T01:11:01Z
depth: quick
files_reviewed: 7
files_reviewed_list:
  - .claude/plugins/.claude-plugin/marketplace.json
  - .claude/plugins/planchk-router/.claude-plugin/plugin.json
  - .claude/plugins/planchk-router/README.md
  - .claude/plugins/planchk-router/hooks/guard.mjs
  - .claude/plugins/planchk-router/hooks/hooks.json
  - .claude/plugins/planchk-router/hooks/register.js
  - .claude/plugins/planchk-router/test/planchk-router.test.mjs
findings:
  critical: 0
  warning: 4
  info: 1
  total: 5
status: issues_found
---

# Phase quick-261026-s2v: Code Review Report

**Reviewed:** 2026-10-27T01:11:01Z
**Depth:** quick (with targeted standard-depth reading of `guard.mjs`, `register.js`, `hooks.json` and the test file per reviewer instructions)
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the new `planchk-router` Claude Code plugin (diff base `cbec881..e261c58`, all 7 files new). The plugin's core contract — `register.js` rewrites only `bm:bm-plan-checker`'s model with no `try`/`catch`, and `guard.mjs` fail-closes the `Agent`/`Task` spawn when the function-hooks module gate is off — is implemented correctly and matches the committed test suite (9/9 pass) and the project's own `RESEARCH.md`/`SUMMARY.md` live-smoke evidence. No hardcoded secrets, `eval`, `innerHTML`, or empty catch blocks were found by pattern scan.

The findings below are about the guard's robustness under conditions the current test suite and live smoke run never exercised (stream-level I/O errors, `process.exit()`-after-write ordering), and about verification/documentation gaps that would let a regression in the guard's wiring (not its internal logic) ship silently. No finding here contradicts that the plugin works as designed today; all are about what isn't proven yet.

## Warnings

### WR-01: `process.exit()` immediately after `process.stderr.write()` risks truncating the one piece of output the guard exists to make visible

**File:** `.claude/plugins/planchk-router/hooks/guard.mjs:16-19` and `:34-37`
**Issue:** Both refusal paths do `process.stderr.write(msg); process.exit(code);` back to back. Node's own documentation warns against this pattern: `process.exit()` terminates the process immediately and can truncate data still buffered for stdout/stderr, particularly when the stream is a pipe (exactly how a hook's stderr is captured by the parent CLI) rather than a TTY. If the write is truncated, the blocking exit code (2) still fires — but the owner's locked requirement is specifically that "failures must be visible," and a truncated/missing reason string undermines that even though the block itself still happens.
**Fix:**
```js
// Instead of writing then forcing exit:
process.stderr.write(msg);
process.exit(2);

// Set exitCode and let the process exit naturally once the event loop drains
// (nothing else is pending after this callback), which lets the write flush:
process.stderr.write(msg);
process.exitCode = 2;
// no process.exit() call here
```

### WR-02: No `error` handler on `process.stdin` — a stream-level error crashes the process outside the intended exit-code contract

**File:** `.claude/plugins/planchk-router/hooks/guard.mjs:7-10`
**Issue:** Only `data` and `end` listeners are registered on `process.stdin`. If the stream emits an `error` event (broken pipe, ECONNRESET, etc.) there is no listener, so Node throws an uncaught exception and the process exits via its own uncaught-exception path (historically exit code 1), not the script's explicit `exit(2)`. This guard's entire job is to fail closed for exactly one case (`bm:bm-plan-checker`, module gate off); a crash that produces an exit code other than the two codes the script otherwise uses deliberately (0 or 2) is untested territory for how the host hook runner treats it. Given the stated purpose — never allow a silent pass — this code path should be made to resolve to the blocking exit code explicitly rather than falling through to Node's default crash behavior.
**Fix:**
```js
let raw = '';
process.stdin.on('data', (chunk) => { raw += chunk; });
process.stdin.on('error', () => {
  process.stderr.write('planchk-router: stdin error; refusing Agent spawn. Stop and report.\n');
  process.exitCode = 2;
});
process.stdin.on('end', () => { /* ... */ });
```

### WR-03: `hooks.json` (and the plugin/marketplace manifests) are completely untested — the dispatch wiring that makes the guard reachable has zero coverage

**File:** `.claude/plugins/planchk-router/test/planchk-router.test.mjs` (whole file); related: `.claude/plugins/planchk-router/hooks/hooks.json`
**Issue:** All 9 tests exercise `guard.mjs` and `register.js` directly (via `spawnSync`/dynamic `import()`), bypassing `hooks.json` entirely. Nothing in this test suite reads or asserts on `hooks.json`'s `modules` array or its `PreToolUse` `matcher` string. That means the actual thing a future edit is most likely to silently break — e.g. dropping `"./register.js"` from `modules`, or narrowing the matcher from `"Agent|Task"` to just `"Task"` — would pass all 9 tests unchanged while weakening or removing the real protection this plugin exists to provide. This is precisely the "tests pass but the behavior being tested isn't the behavior that matters" trap: the unit tests prove `guard.mjs`'s internal branching is correct in isolation, never that it is actually wired to fire.
**Fix:** add a static test that loads `hooks.json` and asserts the invariants directly, e.g.:
```js
test('hooks.json: wires register.js as a module and guards Agent|Task via PreToolUse', () => {
  const hooksConfig = JSON.parse(readFileSync(path.join(__dirname, '..', 'hooks', 'hooks.json'), 'utf8'));
  assert.ok(hooksConfig.modules.includes('./register.js'));
  const preToolUse = hooksConfig.hooks.PreToolUse[0];
  assert.equal(preToolUse.matcher, 'Agent|Task');
  assert.match(preToolUse.hooks[0].command, /guard\.mjs/);
});
```

### WR-04: README's post-update recheck and "Known limitations" never re-verify the guard's negative (fail-closed) path, only the module's happy path

**File:** `.claude/plugins/planchk-router/README.md:48-57`, `:77-88`
**Issue:** The documented procedure for re-checking after a Claude Code update is `claude --debug hooks -p "Reply OK"` plus grepping for `hooks module planchk-router@triggarr-local loaded`. That only proves the **module** still loads when the flag is set — it says nothing about whether the guard still fires when the module does **not** load. The plugin's own `RESEARCH.md` (Assumptions Log, item A2, not carried into this README) records the residual risk explicitly: the guard's match depends on the live runtime still naming the spawn tool `Agent`/`Task` and still carrying `tool_input.subagent_type`; if a future update changes either of those at the same time it changes the module gate, the guard would silently `exit(0)` on every spawn and `bm:bm-plan-checker` would run unrouted on a Claude model with no visible error — the exact outcome the owner locked against. None of the four bullets under "Known limitations" name this risk, and the recheck procedure the README tells the owner to run after every update would not catch it.
**Fix:** add a one-line negative recheck next to the existing load-check instructions (e.g., "also confirm the guard still refuses: run a throwaway `bm:bm-plan-checker` spawn with the flag unset and confirm it is blocked with the refusal message"), and add the field-name/tool-name assumption to "Known limitations" so a future reader of just this README (not the quick-task planning docs) knows the guard's coverage is contingent on it.

## Info

### IN-01: Asymmetric assertion depth between sibling refusal tests

**File:** `.claude/plugins/planchk-router/test/planchk-router.test.mjs:52-55`
**Issue:** The "unparseable stdin" test only asserts `r.status === 2`; it does not assert on `r.stderr` content, unlike the structurally identical "flag unset" test a few lines above it (lines 27-32), which checks both the exit code and two regex matches against the stderr message. A future change that reaches `exit(2)` for the wrong reason (e.g., an accidental fallthrough from a different branch) would not be caught here.
**Fix:**
```js
test('guard: unparseable stdin, flag unset -> exit 2 (fail closed)', () => {
  const r = runGuard('not json', undefined);
  assert.equal(r.status, 2);
  assert.match(r.stderr, /could not parse PreToolUse input/);
});
```

## Set aside (needs ruling)

### SA-01: The negative (guard-blocks) check never exercised the actual production failure mode — `PRECEDENCE: UNKNOWN`

**Where:** Outside the reviewed file set — `.planning/quick/261026-s2v-activate-the-codex-routed-plan-checker-f/261026-s2v-RESEARCH.md` Finding 4/5 and `261026-s2v-SUMMARY.md` "Decisions Made" / "Live Evidence" sections (scratch evidence, not committed source).
**Why excluded:** This concerns ephemeral planning/scratch artifacts and test methodology, not the 7 committed plugin files under review; there is no production source line to cite it against.
**Effect if left as is:** The most realistic real-world failure this plugin guards against is "plugin registered at local scope the normal way, but the `env.CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` key is missing or reverted" (new machine, lost settings file, etc.). The precedence probe that was supposed to pick the right way to simulate this came back `PRECEDENCE: UNKNOWN` (the isolated scratch config dir had no auth), so Task 3's negative check instead used the documented fallback: a session-sideload via `--plugin-dir` with no `.claude/` directory at all. That proves the guard's own logic blocks correctly in isolation, but it is a different activation code path (CLI sideload vs. persistent local-scope registration) than the one actually running in production. If CLI precedence or directory-based registration ever behaves differently for the guard specifically, that gap would surface first in production, not in this evidence.
**Needs:** Owner ruling — accept the sideload-based negative check as sufficient residual proof for this activation, or schedule a follow-up to re-run the precedence probe with an authenticated scratch config dir and redo the negative check against the real local-scope registration path once `PRECEDENCE` resolves to a known value.

## Convention checks

Ran the shared conventions module (`verify conventions --check`) against the changed `.js`/`.mjs` files (`guard.mjs`, `register.js`, `planchk-router.test.mjs`). Result: `{"mode":"check","findings":[],"skipped":false}` — no CONVENTION-tier deviations detected.

---

_Reviewed: 2026-10-27T01:11:01Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: quick_
