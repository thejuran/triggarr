const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {upsertSlice, verifyWrite, migrateSchema1, runCli} = require('./review-register.cjs');
const {assess, registerKey} = require('./review-acceptance.cjs');

const HEAD_A = 'a'.repeat(40);
const HEAD_B = 'b'.repeat(40);

test('upsertSlice keys multiple PRs without mutating inputs', () => {
  const base = {schema: 2, by_pr_head: {}};
  const baseSnapshot = JSON.stringify(base);
  const sliceA = {items: {1: {head: HEAD_A, decision: 'fixed', evidence: 'x'.repeat(20)}}};
  const result1 = upsertSlice(base, {kind: 'dispositions', prNumber: 1, head: HEAD_A, slice: sliceA});
  assert.equal(JSON.stringify(base), baseSnapshot);

  const result1Snapshot = JSON.stringify(result1);
  const sliceB = {items: {}};
  const result2 = upsertSlice(result1, {kind: 'dispositions', prNumber: 2, head: HEAD_B, slice: sliceB});
  assert.equal(JSON.stringify(result1), result1Snapshot);

  assert.ok(Object.hasOwn(result2.by_pr_head, registerKey(1, HEAD_A)));
  assert.ok(Object.hasOwn(result2.by_pr_head, registerKey(2, HEAD_B)));
});

test('verifyWrite flags a lost update from a stale base ("lost update")', () => {
  const base = {schema: 2, by_pr_head: {}};
  const writerA = upsertSlice(base, {kind: 'dispositions', prNumber: 1, head: HEAD_A, slice: {items: {}}});
  const writerB = upsertSlice(base, {kind: 'dispositions', prNumber: 2, head: HEAD_B, slice: {items: {}}}); // stale base
  const final = writerB;

  const problems = verifyWrite({before: base, written: writerA, readBack: final, key: registerKey(1, HEAD_A)});
  assert.ok(problems.some(p => p.includes('own slice missing after write')));

  assert.throws(() => assess({
    prNumber: 1, head: HEAD_A, currentHead: HEAD_A, draft: false,
    checks: [], comments: [],
    dispositions: final,
    blockers: {schema: 2, global_open: [], by_pr_head: {[registerKey(1, HEAD_A)]: {open: []}}},
  }), /No disposition register entry for PR 1/);
});

test('verifyWrite reports another slice changed', () => {
  const key1 = registerKey(1, HEAD_A);
  const key2 = registerKey(2, HEAD_B);
  const before = {schema: 2, by_pr_head: {[key2]: {open: []}}};
  const written = upsertSlice(before, {kind: 'blockers', prNumber: 1, head: HEAD_A, slice: {open: []}});
  const readBack = structuredClone(written);
  readBack.by_pr_head[key2] = {open: ['tampered']};

  const problems = verifyWrite({before, written, readBack, key: key1});
  assert.ok(problems.some(p => p.includes(`another slice changed: ${key2}`)));
});

test('verifyWrite reports another slice disappeared', () => {
  const key1 = registerKey(1, HEAD_A);
  const key2 = registerKey(2, HEAD_B);
  const before = {schema: 2, by_pr_head: {[key2]: {open: []}}};
  const written = upsertSlice(before, {kind: 'blockers', prNumber: 1, head: HEAD_A, slice: {open: []}});
  const readBack = structuredClone(written);
  delete readBack.by_pr_head[key2];

  const problems = verifyWrite({before, written, readBack, key: key1});
  assert.ok(problems.some(p => p.includes(`another slice disappeared: ${key2}`)));
});

test('verifyWrite returns no problems for a clean sequential write', () => {
  const key1 = registerKey(1, HEAD_A);
  const before = {schema: 2, by_pr_head: {}};
  const written = upsertSlice(before, {kind: 'blockers', prNumber: 1, head: HEAD_A, slice: {open: []}});
  const readBack = structuredClone(written);

  const problems = verifyWrite({before, written, readBack, key: key1});
  assert.deepEqual(problems, []);
});

test('upsertSlice rejects a non-40-hex head', () => {
  const base = {schema: 2, by_pr_head: {}};
  assert.throws(() => upsertSlice(base, {kind: 'blockers', prNumber: 1, head: 'not-a-sha', slice: {open: []}}));
});

test('upsertSlice rejects a non-integer PR number', () => {
  const base = {schema: 2, by_pr_head: {}};
  assert.throws(() => upsertSlice(base, {kind: 'blockers', prNumber: 1.5, head: HEAD_A, slice: {open: []}}));
});

test('upsertSlice rejects a kind outside the allowlist', () => {
  const base = {schema: 2, by_pr_head: {}};
  assert.throws(() => upsertSlice(base, {kind: 'something-else', prNumber: 1, head: HEAD_A, slice: {}}));
});

test('upsertSlice rejects a register whose schema is not 2', () => {
  assert.throws(() => upsertSlice({schema: 1, open: []}, {kind: 'blockers', prNumber: 1, head: HEAD_A, slice: {open: []}}));
});

test('migrateSchema1 migrates a schema-1 dispositions register', () => {
  const old = {schema: 1, items: {42: {head: HEAD_A, decision: 'fixed', evidence: 'x'.repeat(20)}}};
  const migrated = migrateSchema1('dispositions', old);
  assert.deepEqual(migrated, {schema: 2, by_pr_head: {}, archived_schema1: old});
});

test('migrateSchema1 migrates a schema-1 blockers register', () => {
  const old = {schema: 1, open: ['legacy-blocker']};
  const migrated = migrateSchema1('blockers', old);
  assert.deepEqual(migrated, {schema: 2, global_open: ['legacy-blocker'], by_pr_head: {}, archived_schema1: old});
});

test('migrateSchema1 rejects a non-schema-1 input', () => {
  assert.throws(() => migrateSchema1('blockers', {schema: 2, global_open: [], by_pr_head: {}}));
});

test('CLI rejects a shell-injection PR value before any subprocess call', () => {
  let called = false;
  const fakeExec = () => { called = true; return ''; };
  const exitCode = runCli(
    ['upsert', '--kind', 'dispositions', '--pr', '5; rm -rf /', '--head', HEAD_A, '--slice-file', '/tmp/does-not-matter.json'],
    {exec: fakeExec}
  );
  assert.notEqual(exitCode, 0);
  assert.equal(called, false);
});

test('CLI rejects a --kind outside the allowlist before any subprocess call', () => {
  let called = false;
  const fakeExec = () => { called = true; return ''; };
  const exitCode = runCli(
    ['upsert', '--kind', 'bogus', '--pr', '5', '--head', HEAD_A, '--slice-file', '/tmp/does-not-matter.json'],
    {exec: fakeExec}
  );
  assert.notEqual(exitCode, 0);
  assert.equal(called, false);
});

test('CLI rejects an unknown subcommand before any subprocess call', () => {
  let called = false;
  const fakeExec = () => { called = true; return ''; };
  const exitCode = runCli(['delete', '--kind', 'blockers'], {exec: fakeExec});
  assert.notEqual(exitCode, 0);
  assert.equal(called, false);
});

test('CLI migrate dry run never calls exec for writing and reports schema 2', () => {
  const calls = [];
  const fakeExec = (cmd, args) => {
    calls.push([cmd, ...args]);
    return JSON.stringify({schema: 1, open: ['legacy']});
  };
  const exitCode = runCli(['migrate', '--kind', 'blockers'], {exec: fakeExec});
  assert.equal(exitCode, 0);
  assert.ok(calls.every(c => !(c[1] === 'variable' && c[2] === 'set')));
});

test('CLI upsert --apply reads, writes, and verifies via injected exec', () => {
  const sliceFile = path.join(os.tmpdir(), `review-register-test-slice-${Date.now()}.json`);
  fs.writeFileSync(sliceFile, JSON.stringify({open: []}));
  try {
    let currentValue = JSON.stringify({schema: 2, by_pr_head: {}});
    const calls = [];
    const fakeExec = (cmd, args) => {
      calls.push([cmd, ...args]);
      if (cmd !== 'gh') throw new Error('unexpected command');
      if (args[0] === 'variable' && args[1] === 'get') return currentValue;
      if (args[0] === 'variable' && args[1] === 'set') { currentValue = args[3]; return ''; }
      throw new Error(`unexpected gh invocation: ${args.join(' ')}`);
    };
    const exitCode = runCli(
      ['upsert', '--kind', 'blockers', '--pr', '9', '--head', HEAD_A, '--slice-file', sliceFile, '--apply'],
      {exec: fakeExec}
    );
    assert.equal(exitCode, 0);
    assert.ok(calls.every(c => c[0] === 'gh'));
    assert.ok(Object.hasOwn(JSON.parse(currentValue).by_pr_head, registerKey(9, HEAD_A)));
  } finally {
    fs.unlinkSync(sliceFile);
  }
});
