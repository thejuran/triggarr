const {test} = require('node:test');
const assert = require('node:assert/strict');
const {
  FALLBACK_SCHEMA_VERSION,
  FALLBACK_FIELDS,
  REVIEWER_KINDS,
  DISALLOWED_REVIEWERS,
  OWNER_DECISIONS,
  validateFallback,
  runCli,
} = require('./codex-fallback.cjs');

const HEAD = 'a'.repeat(40);
const BASE = 'b'.repeat(40);
const HEAD12 = HEAD.slice(0, 12);
const PHASE_DIR = '85-follow-on-ci-improvements-acceptance-usability';
const CODEX_OUT = `.planning/phases/${PHASE_DIR}/codex/${HEAD12}-task1-a2`;
const DECIDED_AT = '2026-10-27T12:00:00.000Z';

function validRecord(overrides = {}) {
  return {
    schema: 1,
    pr: 90,
    head: HEAD,
    base: BASE,
    codex_out: CODEX_OUT,
    reviewer: {name: 'vibe-check deep review (owner-run)', kind: 'vibe-check-deep-review'},
    scope: {base: BASE, head: HEAD, diff: 'full'},
    result: {
      status: 'complete',
      summary: 'reviewed the full diff',
      findings: [{id: 'F001', severity: 'low', disposition: 'fixed', note: 'addressed'}],
    },
    owner_decision: {
      decision: 'approve-fallback',
      verbatim: `I approve the fallback for head ${HEAD12}`,
      decided_at: DECIDED_AT,
    },
    ...overrides,
  };
}

function validContext(overrides = {}) {
  return {
    pr: 90,
    head: HEAD,
    base: BASE,
    prAuthor: 'thejuran',
    headTrust: 'trusted',
    codexStatus: {complete: false, attempt: 2, out: CODEX_OUT, reviewMode: 'trusted-local-tests'},
    ...overrides,
  };
}

test('exports the frozen fallback schema constants', () => {
  assert.equal(FALLBACK_SCHEMA_VERSION, 1);
  assert.deepEqual(
    [...FALLBACK_FIELDS].sort(),
    ['base', 'codex_out', 'head', 'owner_decision', 'pr', 'reviewer', 'result', 'schema', 'scope'].sort()
  );
  assert.ok(REVIEWER_KINDS.includes('vibe-check-deep-review'));
  assert.ok(DISALLOWED_REVIEWERS.includes('bm'));
  assert.deepEqual(OWNER_DECISIONS, ['approve-fallback', 'wait', 'retry-later']);
});

test('valid trusted-head record is ok with no reasons', () => {
  const result = validateFallback(validRecord(), validContext());
  assert.deepEqual(result, {ok: true, reasons: []});
});

test('each missing required top-level field is reported', () => {
  for (const name of FALLBACK_FIELDS) {
    const record = validRecord();
    delete record[name];
    const {ok, reasons} = validateFallback(record, validContext());
    assert.equal(ok, false);
    assert.ok(
      reasons.some(r => r === `missing required field ${name}`),
      `expected missing-field reason for ${name}, got ${JSON.stringify(reasons)}`
    );
  }
});

test('an unknown top-level key is reported', () => {
  const record = validRecord({extra: 'surprise'});
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes('unknown field extra'));
});

test('an unknown nested key is reported for reviewer, scope, result, owner_decision and findings', () => {
  const reviewerRecord = validRecord();
  reviewerRecord.reviewer = {...reviewerRecord.reviewer, extra: 'x'};
  assert.ok(validateFallback(reviewerRecord, validContext()).reasons.includes('unknown field reviewer.extra'));

  const scopeRecord = validRecord();
  scopeRecord.scope = {...scopeRecord.scope, extra: 'x'};
  assert.ok(validateFallback(scopeRecord, validContext()).reasons.includes('unknown field scope.extra'));

  const resultRecord = validRecord();
  resultRecord.result = {...resultRecord.result, extra: 'x'};
  assert.ok(validateFallback(resultRecord, validContext()).reasons.includes('unknown field result.extra'));

  const ownerRecord = validRecord();
  ownerRecord.owner_decision = {...ownerRecord.owner_decision, extra: 'x'};
  assert.ok(validateFallback(ownerRecord, validContext()).reasons.includes('unknown field owner_decision.extra'));

  const findingRecord = validRecord();
  findingRecord.result = {
    ...findingRecord.result,
    findings: [{...findingRecord.result.findings[0], extra: 'x'}],
  };
  assert.ok(validateFallback(findingRecord, validContext()).reasons.includes('unknown field result.findings[].extra'));
});

test('reviewer name matching a disallowed reviewer is not independent', () => {
  const record = validRecord();
  record.reviewer = {name: 'BM', kind: 'other-independent'};
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.some(r => r === 'reviewer is not independent: BM'));
});

test('reviewer name matching the PR author is not independent', () => {
  const record = validRecord();
  record.reviewer = {name: 'thejuran', kind: 'other-independent'};
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.some(r => r === 'reviewer is not independent: thejuran'));
});

test('reviewer kind outside REVIEWER_KINDS is unknown', () => {
  const record = validRecord();
  record.reviewer = {name: 'someone independent', kind: 'friend-of-owner'};
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes('unknown reviewer kind'));
});

test('a record head mismatch is a different head', () => {
  const record = validRecord({head: 'c'.repeat(40)});
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes('fallback is for a different head'));
});

test('a scope head mismatch is a different head', () => {
  const record = validRecord();
  record.scope = {...record.scope, head: 'c'.repeat(40)};
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes('fallback is for a different head'));
});

test('a base mismatch does not match the PR base', () => {
  const record = validRecord({base: 'd'.repeat(40)});
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes('fallback scope base does not match the PR base'));
});

test('a scope base mismatch does not match the PR base', () => {
  const record = validRecord();
  record.scope = {...record.scope, base: 'd'.repeat(40)};
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes('fallback scope base does not match the PR base'));
});

test('a partial scope diff must review the full diff', () => {
  const record = validRecord();
  record.scope = {...record.scope, diff: 'partial'};
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes('fallback must review the full base..head diff'));
});

test('a non-complete result status is not complete', () => {
  const record = validRecord();
  record.result = {...record.result, status: 'in progress'};
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes('fallback review is not complete'));
});

test('an undisposed finding has no disposition', () => {
  const record = validRecord();
  record.result = {
    ...record.result,
    findings: [{id: 'F001', severity: 'low', disposition: 'unsure', note: 'x'}],
  };
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes('finding F001 has no disposition'));
});

test('owner_decision wait blocks acceptance', () => {
  const record = validRecord();
  record.owner_decision = {...record.owner_decision, decision: 'wait'};
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes('owner chose wait: wait blocks acceptance'));
});

test('owner_decision retry-later blocks acceptance', () => {
  const record = validRecord();
  record.owner_decision = {...record.owner_decision, decision: 'retry-later'};
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes('owner chose retry later: retry later blocks acceptance'));
});

test('an empty owner verbatim does not name the head', () => {
  const record = validRecord();
  record.owner_decision = {...record.owner_decision, verbatim: ''};
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes('owner approval does not name this head'));
});

test('a verbatim that never names the head is rejected', () => {
  const record = validRecord();
  record.owner_decision = {...record.owner_decision, verbatim: 'approved, looks fine'};
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes('owner approval does not name this head'));
});

test('an invalid decided_at is rejected', () => {
  const record = validRecord();
  record.owner_decision = {...record.owner_decision, decided_at: 'not-a-date'};
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes('invalid decided_at'));
});

test('Codex actually complete means the fallback is not used (trusted head)', () => {
  const record = validRecord();
  const context = validContext({codexStatus: {complete: true, attempt: 2, out: CODEX_OUT, reviewMode: 'trusted-local-tests'}});
  const {ok, reasons} = validateFallback(record, context);
  assert.equal(ok, false);
  assert.ok(reasons.includes('Codex is complete for this head; a fallback is not used'));
});

test('trusted head: attempt 1 only is not enough', () => {
  const record = validRecord();
  const context = validContext({codexStatus: {complete: false, attempt: 1, out: CODEX_OUT, reviewMode: 'trusted-local-tests'}});
  const {reasons} = validateFallback(record, context);
  assert.ok(reasons.includes(
    'fallback needs the retried Codex attempt for this head (attempt 2 or later) to have stayed INCOMPLETE/PENDING'
  ));
});

test('trusted head: codex_out for a different head is not enough', () => {
  const otherHead12 = 'f'.repeat(12);
  const record = validRecord({codex_out: `.planning/phases/${PHASE_DIR}/codex/${otherHead12}-task1-a2`});
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes(
    'fallback needs the retried Codex attempt for this head (attempt 2 or later) to have stayed INCOMPLETE/PENDING'
  ));
});

test('trusted head: an untrusted-mode refusal record never opens the fallback', () => {
  const record = validRecord();
  const context = validContext({codexStatus: {complete: false, attempt: 2, out: CODEX_OUT, reviewMode: 'untrusted-refused'}});
  const {reasons} = validateFallback(record, context);
  assert.ok(reasons.includes(
    'an untrusted-mode refusal does not open the fallback for a trusted head; run the trusted Codex pass'
  ));
});

test('valid untrusted-head record with its recorded refusal is ok', () => {
  const refusalOut = `.planning/phases/${PHASE_DIR}/codex/${HEAD12}-task1-a1`;
  const record = validRecord({codex_out: refusalOut});
  const context = validContext({
    headTrust: 'untrusted',
    codexStatus: {complete: false, attempt: 1, out: refusalOut, reviewMode: 'untrusted-refused'},
  });
  const result = validateFallback(record, context);
  assert.deepEqual(result, {ok: true, reasons: []});
});

test('untrusted head without its recorded refusal needs one', () => {
  const record = validRecord();
  const context = validContext({
    headTrust: 'untrusted',
    codexStatus: {complete: false, attempt: 1, out: CODEX_OUT, reviewMode: undefined},
  });
  const {reasons} = validateFallback(record, context);
  assert.ok(reasons.includes('untrusted head needs its recorded INCOMPLETE Codex refusal for this head'));
});

test('untrusted head whose Codex record claims complete is never ok', () => {
  const record = validRecord();
  const context = validContext({
    headTrust: 'untrusted',
    codexStatus: {complete: true, attempt: 1, out: CODEX_OUT, reviewMode: 'trusted-local-tests'},
  });
  const {ok, reasons} = validateFallback(record, context);
  assert.equal(ok, false);
  assert.ok(reasons.includes(
    'Codex evidence claims complete for an untrusted head; untrusted runs are refused until Phase 85.1'
  ));
});

test('missing head trust fails closed', () => {
  const record = validRecord();
  const context = validContext({headTrust: undefined});
  const {reasons} = validateFallback(record, context);
  assert.ok(reasons.includes('head trust not established'));
});

test('an unrecognized head trust value fails closed', () => {
  const record = validRecord();
  const context = validContext({headTrust: 'maybe'});
  const {reasons} = validateFallback(record, context);
  assert.ok(reasons.includes('head trust not established'));
});

test('an unsupported fallback schema is rejected', () => {
  const record = validRecord({schema: 2});
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes('unsupported fallback schema'));
});

// --- CR-01 regressions: records built from empty sub-objects, not mutations of the valid fixture ---

test('a record with empty reviewer/scope/result/owner_decision and the wrong PR is never ok', () => {
  const record = {
    schema: 1, pr: 999, head: HEAD, base: BASE, codex_out: CODEX_OUT,
    reviewer: {}, scope: {}, result: {}, owner_decision: {},
  };
  const {ok, reasons} = validateFallback(record, validContext({pr: 5}));
  assert.equal(ok, false);
  assert.ok(reasons.includes('fallback is for a different PR'), JSON.stringify(reasons));
  assert.ok(reasons.includes('owner_decision.decision must be approve-fallback'), JSON.stringify(reasons));
  for (const field of ['reviewer.name', 'reviewer.kind', 'scope.base', 'scope.head', 'scope.diff',
    'result.status', 'result.summary', 'result.findings',
    'owner_decision.decision', 'owner_decision.verbatim', 'owner_decision.decided_at']) {
    assert.ok(reasons.includes(`missing required field ${field}`), `expected missing ${field}, got ${JSON.stringify(reasons)}`);
  }
});

test('an owner decision outside approve-fallback is rejected', () => {
  for (const decision of ['nope', '', 'APPROVE-FALLBACK', 42]) {
    const record = validRecord();
    record.owner_decision = {...record.owner_decision, decision};
    const {ok, reasons} = validateFallback(record, validContext());
    assert.equal(ok, false, `decision ${JSON.stringify(decision)} must not pass`);
    assert.ok(reasons.includes('owner_decision.decision must be approve-fallback'), JSON.stringify(reasons));
  }
});

test('a fallback for a different PR is rejected', () => {
  const {ok, reasons} = validateFallback(validRecord({pr: 91}), validContext());
  assert.equal(ok, false);
  assert.ok(reasons.includes('fallback is for a different PR'));
});

test('a blank reviewer name is rejected', () => {
  const record = validRecord();
  record.reviewer = {...record.reviewer, name: '   '};
  const {ok, reasons} = validateFallback(record, validContext());
  assert.equal(ok, false);
  assert.ok(reasons.includes('reviewer.name is required'));
});

test('result.findings that is not an array is rejected', () => {
  const record = validRecord();
  record.result = {...record.result, findings: 'none'};
  const {ok, reasons} = validateFallback(record, validContext());
  assert.equal(ok, false);
  assert.ok(reasons.includes('result.findings must be an array'));
});

test('a non-object finding entry is rejected, not skipped', () => {
  const record = validRecord();
  record.result = {...record.result, findings: ['F001 fixed', null]};
  const {ok, reasons} = validateFallback(record, validContext());
  assert.equal(ok, false);
  assert.ok(reasons.includes('result.findings entries must be objects'));
});

test('runCli validates a valid fallback file and exits 0', () => {
  const logs = [];
  const errors = [];
  const files = {
    '/tmp/fallback.json': JSON.stringify(validRecord()),
    [`${CODEX_OUT}.status.json`]: JSON.stringify({status: 'incomplete', reasons: ['x']}),
    [`${CODEX_OUT}.meta.json`]: JSON.stringify({
      meta_version: 2,
      head: HEAD,
      attempt: 2,
      review_mode: 'trusted-local-tests',
      audited_inputs_changed_in_diff: [],
    }),
  };
  const io = {
    readFileSync: path => {
      if (!Object.hasOwn(files, path)) throw new Error(`ENOENT: no such file: ${path}`);
      return files[path];
    },
    log: (...args) => logs.push(args.join(' ')),
    error: (...args) => errors.push(args.join(' ')),
  };
  const exitCode = runCli(
    ['validate', '--file', '/tmp/fallback.json', '--pr', '90', '--head', HEAD, '--base', BASE,
      '--pr-author', 'thejuran', '--head-trust', 'trusted', '--codex-out', CODEX_OUT],
    io
  );
  assert.equal(exitCode, 0);
  assert.ok(logs.some(l => l === `fallback valid for ${HEAD}`));
  assert.deepEqual(errors, []);
});

test('runCli prints each reason and exits 1 for an invalid fallback file', () => {
  const errors = [];
  const files = {
    '/tmp/fallback.json': JSON.stringify(validRecord({}, )),
    [`${CODEX_OUT}.status.json`]: JSON.stringify({status: 'incomplete', reasons: ['x']}),
    [`${CODEX_OUT}.meta.json`]: JSON.stringify({
      meta_version: 2,
      head: HEAD,
      attempt: 2,
      review_mode: 'trusted-local-tests',
      audited_inputs_changed_in_diff: [],
    }),
  };
  const badRecord = validRecord();
  badRecord.owner_decision = {...badRecord.owner_decision, decision: 'wait'};
  files['/tmp/fallback.json'] = JSON.stringify(badRecord);
  const io = {
    readFileSync: path => {
      if (!Object.hasOwn(files, path)) throw new Error(`ENOENT: no such file: ${path}`);
      return files[path];
    },
    log: () => {},
    error: (...args) => errors.push(args.join(' ')),
  };
  const exitCode = runCli(
    ['validate', '--file', '/tmp/fallback.json', '--pr', '90', '--head', HEAD, '--base', BASE,
      '--pr-author', 'thejuran', '--head-trust', 'trusted', '--codex-out', CODEX_OUT],
    io
  );
  assert.equal(exitCode, 1);
  assert.ok(errors.includes('owner chose wait: wait blocks acceptance'));
});

test('runCli rejects an invalid --pr before any file read', () => {
  let readCalled = false;
  const io = {
    readFileSync: () => {
      readCalled = true;
      throw new Error('should not be called');
    },
    log: () => {},
    error: () => {},
  };
  const exitCode = runCli(
    ['validate', '--file', '/tmp/fallback.json', '--pr', '12abc', '--head', HEAD, '--base', BASE,
      '--pr-author', 'thejuran', '--head-trust', 'trusted', '--codex-out', CODEX_OUT],
    io
  );
  assert.equal(exitCode, 2);
  assert.equal(readCalled, false);
});

// --- WR-02 regressions: the fallback is bound to the Codex output it was checked against ---

test('a fallback whose codex_out names the head but is not the Codex output checked is rejected', () => {
  const record = validRecord({codex_out: `.planning/phases/${PHASE_DIR}/codex/${HEAD12}-task1-a3`});
  const {ok, reasons} = validateFallback(record, validContext());
  assert.equal(ok, false);
  assert.ok(reasons.includes('fallback codex_out does not match the Codex output checked'), JSON.stringify(reasons));
});

test('a missing codexStatus.out never matches a fallback codex_out', () => {
  const context = validContext({codexStatus: {complete: false, attempt: 2, reviewMode: 'trusted-local-tests'}});
  const {ok, reasons} = validateFallback(validRecord(), context);
  assert.equal(ok, false);
  assert.ok(reasons.includes('fallback codex_out does not match the Codex output checked'));
});

function cliFiles(metaOverrides = {}) {
  return {
    '/tmp/fallback.json': JSON.stringify(validRecord()),
    [`${CODEX_OUT}.status.json`]: JSON.stringify({status: 'incomplete', reasons: ['x']}),
    [`${CODEX_OUT}.meta.json`]: JSON.stringify({
      meta_version: 2, head: HEAD, base: BASE, attempt: 2, review_mode: 'trusted-local-tests',
      audited_inputs_changed_in_diff: [], ...metaOverrides,
    }),
  };
}

function runValidate(files) {
  const errors = [];
  const io = {
    readFileSync: p => {
      if (!Object.hasOwn(files, p)) throw new Error(`ENOENT: no such file: ${p}`);
      return files[p];
    },
    log: () => {},
    error: (...args) => errors.push(args.join(' ')),
  };
  const exitCode = runCli(
    ['validate', '--file', '/tmp/fallback.json', '--pr', '90', '--head', HEAD, '--base', BASE,
      '--pr-author', 'thejuran', '--head-trust', 'trusted', '--codex-out', CODEX_OUT],
    io
  );
  return {exitCode, errors};
}

test('runCli validate rejects Codex output whose meta is for a different head', () => {
  const {exitCode, errors} = runValidate(cliFiles({head: 'c'.repeat(40)}));
  assert.equal(exitCode, 1);
  assert.ok(errors.some(e => e.includes('Codex output is for a different head')), errors.join('\n'));
});

test('runCli validate rejects Codex output whose meta names no head', () => {
  const files = cliFiles();
  const meta = JSON.parse(files[`${CODEX_OUT}.meta.json`]);
  delete meta.head;
  files[`${CODEX_OUT}.meta.json`] = JSON.stringify(meta);
  const {exitCode, errors} = runValidate(files);
  assert.equal(exitCode, 1);
  assert.ok(errors.some(e => e.includes('Codex output is for a different head')), errors.join('\n'));
});

// --- Iteration-2 WR-03 regressions: BM/Claude names in any spelling are not independent ---

for (const name of [
  'bm-code-reviewer',
  'Claude Code',
  'Claude (bm-code-reviewer)',
  'claude-opus',
  'BM_code_review',
  'GSD code reviewer',
  'gsd-code-fixer',
  'Buildomator review agent',
  'codex_review_run.py',
  'Codex Review Run',
  '  BM  ',
]) {
  test(`reviewer name ${JSON.stringify(name)} is not independent`, () => {
    const record = validRecord();
    record.reviewer = {name, kind: 'other-independent'};
    const {ok, reasons} = validateFallback(record, validContext());
    assert.equal(ok, false);
    assert.ok(reasons.includes(`reviewer is not independent: ${name}`), JSON.stringify(reasons));
  });
}

for (const name of [
  'vibe-check deep review (owner-run)',
  'manual Codex inspection session',
  'independent human reviewer',
  'submarine review', // contains "bm" only inside a word, not as a token
]) {
  test(`reviewer name ${JSON.stringify(name)} stays acceptable`, () => {
    const record = validRecord();
    record.reviewer = {name, kind: 'other-independent'};
    const {ok, reasons} = validateFallback(record, validContext());
    assert.equal(ok, true, JSON.stringify(reasons));
  });
}
