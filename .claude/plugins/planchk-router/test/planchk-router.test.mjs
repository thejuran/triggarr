// node:test coverage for the planchk-router plugin: the classic PreToolUse
// guard (guard.mjs) and the agent.spawn module hook (register.js).
//
// Only node:test, node:assert/strict, node:child_process, node:fs and
// node:url are used -- no packages installed, nothing to audit.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const GUARD_PATH = path.join(__dirname, '..', 'hooks', 'guard.mjs');
const REGISTER_PATH = path.join(__dirname, '..', 'hooks', 'register.js');
const HOOKS_JSON_PATH = path.join(__dirname, '..', 'hooks', 'hooks.json');

function runGuard(stdinPayload, flagValue) {
  const env = { ...process.env };
  delete env.CLAUDE_CODE_ENABLE_FUNCTION_HOOKS;
  if (flagValue !== undefined) {
    env.CLAUDE_CODE_ENABLE_FUNCTION_HOOKS = flagValue;
  }
  const input = typeof stdinPayload === 'string' ? stdinPayload : JSON.stringify(stdinPayload);
  return spawnSync(process.execPath, [GUARD_PATH], { input, env, encoding: 'utf8' });
}

test('guard: flag unset, bm:bm-plan-checker -> exit 2, refusal message on stderr', () => {
  const r = runGuard({ tool_input: { subagent_type: 'bm:bm-plan-checker' } }, undefined);
  assert.equal(r.status, 2);
  assert.match(r.stderr, /planchk-router: refusing bm:bm-plan-checker spawn/);
  assert.match(r.stderr, /Stop and report/);
});

test('guard: flag="0", bm:bm-plan-checker -> exit 2', () => {
  const r = runGuard({ tool_input: { subagent_type: 'bm:bm-plan-checker' } }, '0');
  assert.equal(r.status, 2);
  assert.match(r.stderr, /planchk-router: refusing bm:bm-plan-checker spawn/);
});

test('guard: flag="1", bm:bm-plan-checker -> exit 0, empty stderr', () => {
  const r = runGuard({ tool_input: { subagent_type: 'bm:bm-plan-checker' } }, '1');
  assert.equal(r.status, 0);
  assert.equal(r.stderr, '');
});

test('guard: other subagent type, flag unset -> exit 0 (untouched)', () => {
  const r = runGuard({ tool_input: { subagent_type: 'bm:bm-executor' } }, undefined);
  assert.equal(r.status, 0);
  assert.equal(r.stderr, '');
});

test('guard: unparseable stdin, flag unset -> exit 2 (fail closed)', () => {
  const r = runGuard('not json', undefined);
  assert.equal(r.status, 2);
  assert.match(r.stderr, /could not parse PreToolUse input/);
});

test('guard: valid JSON, no tool_input/subagent_type -> exit 0', () => {
  const r = runGuard({}, undefined);
  assert.equal(r.status, 0);
  assert.equal(r.stderr, '');
});

test('register: registers exactly one agent.spawn/bm:bm-plan-checker handler; rewrites only model', async () => {
  const handlers = [];
  function fakeOn(event, filter, handler) {
    handlers.push({ event, filter, handler });
  }
  const mod = await import(pathToFileURL(REGISTER_PATH).href);
  mod.register(fakeOn);

  assert.equal(handlers.length, 1);
  assert.equal(handlers[0].event, 'agent.spawn');
  assert.deepEqual(handlers[0].filter, { subagentType: 'bm:bm-plan-checker' });

  const e = { subagentType: 'bm:bm-plan-checker', model: 'sonnet', prompt: 'x', permissionMode: 'default' };
  let passedToNext;
  async function next(arg) {
    passedToNext = arg;
    return 'NEXT_RESULT';
  }
  const result = await handlers[0].handler('$', e, next);

  assert.equal(result, 'NEXT_RESULT');
  assert.ok(passedToNext);
  assert.equal(passedToNext.model, 'claude-gpt-6-astra[1m]');
  const { model: _rewrittenModel, ...restOfPassed } = passedToNext;
  const { model: _originalModel, ...restOfOriginal } = e;
  assert.deepEqual(restOfPassed, restOfOriginal);
});

test('register: next rejection propagates (no swallowing)', async () => {
  const handlers = [];
  function fakeOn(event, filter, handler) {
    handlers.push({ event, filter, handler });
  }
  const mod = await import(pathToFileURL(REGISTER_PATH).href);
  mod.register(fakeOn);

  const e = { subagentType: 'bm:bm-plan-checker', model: 'sonnet', prompt: 'x', permissionMode: 'default' };
  async function rejectingNext() {
    throw new Error('boom');
  }
  await assert.rejects(handlers[0].handler('$', e, rejectingNext), /boom/);
});

test('static: register.js has no try/catch/console (comments stripped) and only one claude- model id', () => {
  const raw = readFileSync(REGISTER_PATH, 'utf8');
  const stripped = raw
    .split('\n')
    .filter((line) => !line.trim().startsWith('//'))
    .join('\n');

  assert.doesNotMatch(stripped, /\btry\b/);
  assert.doesNotMatch(stripped, /\bcatch\b/);
  assert.doesNotMatch(stripped, /console\./);

  const ids = [...raw.matchAll(/claude-[A-Za-z0-9.\-[\]]+/g)].map((m) => m[0]);
  const uniqueIds = [...new Set(ids)];
  assert.deepEqual(uniqueIds, ['claude-gpt-6-astra[1m]']);
});

// All tests above exercise guard.mjs/register.js directly, bypassing hooks.json
// entirely -- nothing asserted that the real dispatch wiring (the module list and
// the PreToolUse matcher that actually makes guard.mjs reachable) is intact. This
// test closes that gap: dropping "./register.js" from `modules`, narrowing the
// matcher, or pointing the command at a different file would fail this test even
// though it would leave all 9 behavior tests above untouched.
function loadHooksConfig(hooksJsonPath) {
  return JSON.parse(readFileSync(hooksJsonPath, 'utf8'));
}

test('hooks.json: wires register.js as a module and guards Agent|Task via PreToolUse', () => {
  const hooksConfig = loadHooksConfig(HOOKS_JSON_PATH);

  assert.ok(Array.isArray(hooksConfig.modules));
  assert.ok(hooksConfig.modules.includes('./register.js'));

  const preToolUse = hooksConfig.hooks.PreToolUse[0];
  assert.equal(preToolUse.matcher, 'Agent|Task');
  assert.match(preToolUse.hooks[0].command, /guard\.mjs/);
});

// Preload that drives the guard's own process.stdin deterministically: once
// guard.mjs has registered its listeners, deliver a non-checker payload (which
// alone would exit 0), then a stream error, then 'end'. The parent never closes
// the real stdin, so the guard must exit on its own (no hang after an error).
const STDIN_ERROR_PRELOAD =
  'data:text/javascript,' +
  encodeURIComponent(`
const t = setInterval(() => {
  if (process.stdin.listenerCount('end') === 0) return;
  clearInterval(t);
  process.stdin.emit('data', JSON.stringify({ tool_input: { subagent_type: 'other' } }));
  process.stdin.emit('error', new Error('synthetic stdin error'));
  process.stdin.emit('end');
}, 5);
`);

test('guard: stdin error then end -> exits 2 on its own, refusal on stderr', { timeout: 5000 }, async () => {
  const env = { ...process.env };
  delete env.CLAUDE_CODE_ENABLE_FUNCTION_HOOKS;
  const child = spawn(process.execPath, ['--import', STDIN_ERROR_PRELOAD, GUARD_PATH], { env });
  let stderr = '';
  child.stderr.setEncoding('utf8');
  child.stdin.on('error', () => {});
  child.stderr.on('data', (chunk) => {
    stderr += chunk;
  });
  // A hung guard is killed so the test fails cleanly instead of hanging the runner.
  const killer = setTimeout(() => child.kill('SIGKILL'), 3000);
  const code = await new Promise((resolve) => child.on('close', resolve));
  clearTimeout(killer);
  child.stdin.destroy();
  assert.equal(code, 2);
  assert.match(stderr, /planchk-router: stdin error while reading PreToolUse input/);
});
