const {test} = require('node:test');
const assert = require('node:assert/strict');
const {
  FALLBACK_SCHEMA_VERSION,
  FALLBACK_FIELDS,
  REVIEWER_KINDS,
  DISALLOWED_REVIEWERS,
  OWNER_DECISIONS,
  INSPECTION_REVIEW_MODE,
  inspectionOnlyCompleteness,
  codexStatusFromOutput,
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

test('a base mismatch does not match the reviewed base', () => {
  const record = validRecord({base: 'd'.repeat(40)});
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes('fallback scope base does not match the reviewed base (merge-base)'));
});

test('a scope base mismatch does not match the reviewed base', () => {
  const record = validRecord();
  record.scope = {...record.scope, base: 'd'.repeat(40)};
  const {reasons} = validateFallback(record, validContext());
  assert.ok(reasons.includes('fallback scope base does not match the reviewed base (merge-base)'));
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

test('trusted head: an inspection-only result never opens the fallback', () => {
  const record = validRecord();
  const context = validContext({
    codexStatus: {complete: false, attempt: 2, out: CODEX_OUT, reviewMode: INSPECTION_REVIEW_MODE},
  });
  const {reasons} = validateFallback(record, context);
  assert.ok(reasons.includes(
    'an inspection-only result does not open the fallback for a trusted head; run the trusted Codex pass'
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

test('untrusted head with a legitimate INCOMPLETE inspection-only result at attempt 2 is ok', () => {
  const record = validRecord();
  const context = validContext({
    headTrust: 'untrusted',
    codexStatus: {
      complete: false, invalidEvidence: false, attempt: 2, out: CODEX_OUT, reviewMode: INSPECTION_REVIEW_MODE,
    },
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
  assert.ok(reasons.includes(
    'untrusted head needs its INCOMPLETE inspection-only Codex result for this head (attempt 2 or later) or its recorded untrusted-refused result'
  ));
});

test('untrusted head whose only record is a trusted-mode incomplete still needs the inspection-only result', () => {
  const record = validRecord();
  const context = validContext({
    headTrust: 'untrusted',
    codexStatus: {complete: false, attempt: 2, out: CODEX_OUT, reviewMode: 'trusted-local-tests'},
  });
  const {reasons} = validateFallback(record, context);
  assert.ok(reasons.includes(
    'untrusted head needs its INCOMPLETE inspection-only Codex result for this head (attempt 2 or later) or its recorded untrusted-refused result'
  ));
});

test('untrusted head whose Codex record claims complete is never ok', () => {
  const record = validRecord();
  const context = validContext({
    headTrust: 'untrusted',
    codexStatus: {complete: true, attempt: 1, out: CODEX_OUT, reviewMode: INSPECTION_REVIEW_MODE},
  });
  const {ok, reasons} = validateFallback(record, context);
  assert.equal(ok, false);
  assert.ok(reasons.includes('Codex is complete for this head; a fallback is not used'));
});

test('test_invalid_evidence_never_opens_fallback: invalid evidence is never rescued, at attempt 2 or attempt 3', () => {
  for (const attempt of [2, 3]) {
    const record = validRecord();
    const context = validContext({
      headTrust: 'untrusted',
      codexStatus: {
        complete: false, invalidEvidence: true, attempt, out: CODEX_OUT, reviewMode: INSPECTION_REVIEW_MODE,
      },
    });
    const {ok, reasons} = validateFallback(record, context);
    assert.equal(ok, false, `attempt ${attempt} must not pass`);
    assert.ok(reasons.includes(
      'Codex evidence claims completion but is not valid for this head and attempt; a fallback cannot rescue invalid evidence — rerun the inspection-only review'
    ), JSON.stringify(reasons));
  }
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

// --- D-07/D-12: inspectionOnlyCompleteness, the shared completeness predicate ---

function inspectionStatus(overrides = {}) {
  return {status: 'complete', inspected_head: HEAD, inspected_base: BASE, ...overrides};
}

function inspectionMeta(overrides = {}) {
  return {
    meta_version: 2, head: HEAD, base: BASE, label: 'task1', attempt: 2, review_mode: INSPECTION_REVIEW_MODE,
    harness_head: BASE, audited_inputs_changed_in_diff: [], ...overrides,
  };
}

function validCiEvidence(overrides = {}) {
  const ciReady = {
    id: 1, name: 'CI ready', head_sha: HEAD, status: 'completed', conclusion: 'success', html_url: 'https://x/1',
    ...overrides,
  };
  return {check_runs: [ciReady], ci_ready: ciReady};
}

function verifiedBoundary(overrides = {}) {
  return {
    boundary_version: 1, verdict: 'verified', reasons: [], head: HEAD, label: 'task1', attempt: 2,
    checked_at: DECIDED_AT, image_ref: 'codex-review:local', image_id: `sha256:${'a'.repeat(64)}`,
    codex_version: '0.153.4', credential_mode: 'copied-login', network: 'default', mounts: [],
    env_names: [], canary: 'ok', schema_sha256: 'b'.repeat(64), ...overrides,
  };
}

function validProvenance(overrides = {}) {
  return {
    established: true, main_ref: 'refs/remotes/origin/main', main_sha: BASE, harness_head: BASE, base: BASE,
    base_on_main: true, grader_ref: BASE, grader_source: 'trusted-origin-main', ...overrides,
  };
}

// The predicate with this file's CODEX_OUT (-a2, matching inspectionMeta's
// attempt), a valid trusted-main provenance and valid CI evidence unless a
// test overrides them.
function predicate(args) {
  return inspectionOnlyCompleteness({
    provenance: validProvenance(), ciEvidence: validCiEvidence(), out: CODEX_OUT, ...args,
  });
}

test('inspectionOnlyCompleteness: complete status, bound, verified boundary, no base required is complete', () => {
  const result = predicate({
    meta: inspectionMeta(), status: inspectionStatus(), baseStatus: null, boundary: verifiedBoundary(),
    head: HEAD, baseRequired: false,
  });
  assert.deepEqual(result, {complete: true, invalidEvidence: false, reasons: []});
});

test('inspectionOnlyCompleteness: an incomplete status is a legitimate incomplete, never invalid evidence', () => {
  const result = predicate({
    meta: inspectionMeta(), status: {status: 'incomplete', reasons: ['boundary unverified']}, baseStatus: null,
    boundary: null, head: HEAD, baseRequired: false,
  });
  assert.equal(result.complete, false);
  assert.equal(result.invalidEvidence, false);
  assert.ok(result.reasons.includes('Codex status is incomplete'));
});

test('inspectionOnlyCompleteness: a missing boundary makes a complete claim invalid evidence', () => {
  const result = predicate({
    meta: inspectionMeta(), status: inspectionStatus(), baseStatus: null, boundary: null,
    head: HEAD, baseRequired: false,
  });
  assert.equal(result.complete, false);
  assert.equal(result.invalidEvidence, true);
  assert.ok(result.reasons.includes('inspection-only result has no verified isolation boundary for this head, label and attempt'));
});

test('inspectionOnlyCompleteness: an unverified, wrong-head, or wrong-attempt boundary is invalid evidence', () => {
  for (const boundary of [
    verifiedBoundary({verdict: 'unverified'}),
    verifiedBoundary({head: 'f'.repeat(40)}),
    verifiedBoundary({attempt: 1}),
  ]) {
    const result = predicate({
      meta: inspectionMeta(), status: inspectionStatus(), baseStatus: null, boundary, head: HEAD, baseRequired: false,
    });
    assert.equal(result.complete, false, JSON.stringify(boundary));
    assert.equal(result.invalidEvidence, true, JSON.stringify(boundary));
    assert.ok(result.reasons.includes('inspection-only result has no verified isolation boundary for this head, label and attempt'));
  }
});

test('inspectionOnlyCompleteness: a missing required base-status blocks with the grader-changed reason', () => {
  const result = predicate({
    meta: inspectionMeta(), status: inspectionStatus(), baseStatus: null, boundary: verifiedBoundary(),
    head: HEAD, baseRequired: true,
  });
  assert.equal(result.complete, false);
  assert.ok(result.reasons.includes("grader changed in this diff: the trusted-main checker's base-status is missing"));
});

test('inspectionOnlyCompleteness: an incomplete required base-status blocks with the grader-changed reason', () => {
  const result = predicate({
    meta: inspectionMeta(), status: inspectionStatus(), baseStatus: {status: 'incomplete'}, boundary: verifiedBoundary(),
    head: HEAD, baseRequired: true,
  });
  assert.equal(result.complete, false);
  assert.ok(result.reasons.includes('grader changed in this diff: the trusted-main checker did not confirm completeness'));
});

test('inspectionOnlyCompleteness: a complete but unbound required base-status blocks with the grader-changed reason', () => {
  const result = predicate({
    meta: inspectionMeta(), status: inspectionStatus(),
    baseStatus: {status: 'complete', inspected_head: 'f'.repeat(40), inspected_base: BASE},
    boundary: verifiedBoundary(), head: HEAD, baseRequired: true,
  });
  assert.equal(result.complete, false);
  assert.ok(result.reasons.includes(
    'grader changed in this diff: the base checker status is not bound to this head and base (inspected_head/inspected_base differ)'
  ));
});

test('inspectionOnlyCompleteness: a complete and bound required base-status is complete', () => {
  const result = predicate({
    meta: inspectionMeta(), status: inspectionStatus(), baseStatus: inspectionStatus(), boundary: verifiedBoundary(),
    head: HEAD, baseRequired: true,
  });
  assert.deepEqual(result, {complete: true, invalidEvidence: false, reasons: []});
});

// --- D-07/D-12: codexStatusFromOutput end-to-end over inspection-only output files ---

function inspectionOutputFiles(overrides = {}) {
  const out = overrides.out || CODEX_OUT;
  const files = {
    [`${out}.status.json`]: JSON.stringify(overrides.status || inspectionStatus()),
    [`${out}.meta.json`]: JSON.stringify(overrides.meta || inspectionMeta()),
  };
  if (overrides.boundary !== undefined) {
    if (overrides.boundary !== null) files[`${out}.boundary.json`] = JSON.stringify(overrides.boundary);
  } else {
    files[`${out}.boundary.json`] = JSON.stringify(verifiedBoundary());
  }
  if (overrides.provenance !== undefined) {
    if (overrides.provenance !== null) files[`${out}.grader-provenance.json`] = JSON.stringify(overrides.provenance);
  } else {
    files[`${out}.grader-provenance.json`] = JSON.stringify(validProvenance());
  }
  if (overrides.ciEvidence !== undefined) {
    if (overrides.ciEvidence !== null) files[`${out}.ci-evidence.json`] = JSON.stringify(overrides.ciEvidence);
  } else {
    files[`${out}.ci-evidence.json`] = JSON.stringify(validCiEvidence());
  }
  return files;
}

function stubReadFile(files) {
  return path => {
    if (!Object.hasOwn(files, path)) throw new Error(`ENOENT: no such file: ${path}`);
    return files[path];
  };
}

test('codexStatusFromOutput: a complete claim with a missing boundary.json is invalid evidence, at attempt 2', () => {
  const files = inspectionOutputFiles({boundary: null});
  const result = codexStatusFromOutput(CODEX_OUT, stubReadFile(files));
  assert.equal(result.complete, false);
  assert.equal(result.invalidEvidence, true);

  const {ok, reasons} = validateFallback(validRecord({codex_out: CODEX_OUT}), validContext({
    headTrust: 'untrusted', codexStatus: result,
  }));
  assert.equal(ok, false);
  assert.ok(reasons.includes(
    'Codex evidence claims completion but is not valid for this head and attempt; a fallback cannot rescue invalid evidence — rerun the inspection-only review'
  ), JSON.stringify(reasons));
});

test('codexStatusFromOutput: a genuinely incomplete inspection-only result at attempt 1 still needs attempt 2 or a historical refusal', () => {
  const files = inspectionOutputFiles({
    status: {status: 'incomplete', reasons: ['boundary unverified']},
    meta: inspectionMeta({attempt: 1}),
    boundary: null,
  });
  const result = codexStatusFromOutput(CODEX_OUT, stubReadFile(files));
  assert.equal(result.complete, false);
  assert.equal(result.invalidEvidence, false);

  const {ok, reasons} = validateFallback(validRecord({codex_out: CODEX_OUT}), validContext({
    headTrust: 'untrusted', codexStatus: result,
  }));
  assert.equal(ok, false);
  assert.ok(reasons.includes(
    'untrusted head needs its INCOMPLETE inspection-only Codex result for this head (attempt 2 or later) or its recorded untrusted-refused result'
  ), JSON.stringify(reasons));
});

test('codexStatusFromOutput: a complete, bound, verified-boundary inspection-only result is complete', () => {
  const files = inspectionOutputFiles();
  const result = codexStatusFromOutput(CODEX_OUT, stubReadFile(files));
  assert.equal(result.complete, true);
  assert.equal(result.invalidEvidence, false);
  assert.equal(result.boundaryVerdict, 'verified');
});

// --- WR-05: grader provenance and output-prefix attempt, as the Python gate ---

test('inspectionOnlyCompleteness: missing or unestablished grader provenance makes a complete claim invalid evidence', () => {
  for (const provenance of [
    null, [], {established: false, reasons: ['x']}, validProvenance({base_on_main: false}),
    validProvenance({grader_source: 'base'}),
  ]) {
    const result = predicate({
      meta: inspectionMeta(), status: inspectionStatus(), baseStatus: null, boundary: verifiedBoundary(),
      provenance, head: HEAD, baseRequired: false,
    });
    assert.equal(result.complete, false, JSON.stringify(provenance));
    assert.equal(result.invalidEvidence, true, JSON.stringify(provenance));
    assert.ok(result.reasons.includes('grader provenance not established from origin/main'), JSON.stringify(result));
  }
});

test('inspectionOnlyCompleteness: a meta head or attempt that differs from the output prefix is invalid evidence', () => {
  for (const [meta, boundary, out] of [
    [inspectionMeta({attempt: 3}), verifiedBoundary({attempt: 3}), CODEX_OUT],
    [inspectionMeta(), verifiedBoundary(), CODEX_OUT.replace(/-a2$/, '-a1')],
    [inspectionMeta(), verifiedBoundary(), undefined],
  ]) {
    const result = predicate({
      meta, status: inspectionStatus(), baseStatus: null, boundary, out, head: HEAD, baseRequired: false,
    });
    assert.equal(result.complete, false, String(out));
    assert.ok(result.reasons.includes('inspection-only meta does not match the output prefix (head, label or attempt)'));
  }
});

test('codexStatusFromOutput: a complete claim with no .grader-provenance.json is invalid evidence', () => {
  const files = inspectionOutputFiles({provenance: null});
  const result = codexStatusFromOutput(CODEX_OUT, stubReadFile(files));
  assert.equal(result.complete, false);
  assert.equal(result.invalidEvidence, true);
});

test('codexStatusFromOutput: trusted-local-tests records never carry invalidEvidence', () => {
  const files = {
    [`${CODEX_OUT}.status.json`]: JSON.stringify({status: 'complete', inspected_head: HEAD, inspected_base: BASE}),
    [`${CODEX_OUT}.meta.json`]: JSON.stringify({
      meta_version: 2, head: HEAD, base: BASE, attempt: 1, review_mode: 'trusted-local-tests',
      audited_inputs_changed_in_diff: [],
    }),
  };
  const result = codexStatusFromOutput(CODEX_OUT, stubReadFile(files));
  assert.equal(result.complete, true);
  assert.equal(result.invalidEvidence, false);
});

test('codexStatusFromOutput: untrusted-refused records never carry invalidEvidence', () => {
  const files = {
    [`${CODEX_OUT}.status.json`]: JSON.stringify({status: 'incomplete', reasons: ['refused']}),
    [`${CODEX_OUT}.meta.json`]: JSON.stringify({
      meta_version: 2, head: HEAD, base: BASE, attempt: 1, review_mode: 'untrusted-refused',
      audited_inputs_changed_in_diff: [],
    }),
  };
  const result = codexStatusFromOutput(CODEX_OUT, stubReadFile(files));
  assert.equal(result.complete, false);
  assert.equal(result.invalidEvidence, false);
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
      base: BASE,
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
      base: BASE,
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
  // A separator inside the short token itself must not split it away.
  'B.M. Code Review',
  'B M',
  'b/m',
  'G.S.D. reviewer',
  'C l a u d e',
  'c.o.d.e.x review run',
  // Review pass 2: an adjacent letter must not absorb the split name.
  'X B.M.',
  'B.M.X review',
  'A G.S.D.',
  'C.l.a.u.d.e.X',
  'B.M. / G.S.D. reviewer',
  'B M 2',
  'c o d e x r e v i e w r u n',
  // Review pass 4 (WR-02): case and letter/digit boundaries split tokens, so
  // the unsplit spelling is rejected exactly as the split one is.
  'BM2',
  'B.M2',
  'GSD2 agent',
  'claude2',
  'ClaudeCode',
  'GSDReviewer',
  '2BM',
  'CodexReviewRun',
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
  'J. R. independent reviewer', // initials that do not spell a disallowed token
  // Review pass 4 (WR-02): the case and digit splits leave ordinary names alone.
  'Submarine Review', // a capitalised word is not split inside itself
  'McAllister independent review', // a case split that spells no disallowed token
  'reviewer 2', // a digit beside an ordinary word
]) {
  test(`reviewer name ${JSON.stringify(name)} stays acceptable`, () => {
    const record = validRecord();
    record.reviewer = {name, kind: 'other-independent'};
    const {ok, reasons} = validateFallback(record, validContext());
    assert.equal(ok, true, JSON.stringify(reasons));
  });
}

// --- Iteration-3 WR-02 regressions: the CLI binds --base to the Codex evidence's base ---

test('runCli validate rejects Codex output whose meta base differs from --base', () => {
  const {exitCode, errors} = runValidate(cliFiles({base: 'd'.repeat(40)}));
  assert.equal(exitCode, 1);
  assert.ok(errors.some(e => e.includes('Codex output is for a different base')), errors.join('\n'));
});

test('runCli validate rejects Codex output whose meta names no base', () => {
  const files = cliFiles();
  const meta = JSON.parse(files[`${CODEX_OUT}.meta.json`]);
  delete meta.base;
  files[`${CODEX_OUT}.meta.json`] = JSON.stringify(meta);
  const {exitCode, errors} = runValidate(files);
  assert.equal(exitCode, 1);
  assert.ok(errors.some(e => e.includes('Codex output is for a different base')), errors.join('\n'));
});

test('runCli validate accepts a fallback whose base matches the Codex evidence base', () => {
  const {exitCode, errors} = runValidate(cliFiles());
  assert.equal(exitCode, 0, errors.join('\n'));
});

// --- Codex 2aa2cc8 F001: every record of the selected attempt is bound together ---

const PROVENANCE_BINDING_REASON = "grader provenance does not name this review's grader and reviewed base";

test('inspectionOnlyCompleteness: Codex 2aa2cc8 F001 reproduction is not complete', () => {
  const head = HEAD;
  const base = BASE;
  const result = inspectionOnlyCompleteness({
    meta: {head, base, label: 'old-review', attempt: 1},
    status: {status: 'complete', inspected_head: head, inspected_base: base},
    boundary: {verdict: 'verified', head, label: 'old-review', attempt: 1},
    provenance: {
      established: true, base_on_main: true, grader_source: 'trusted-origin-main', base: 'c'.repeat(40),
      main_sha: 'd'.repeat(40), harness_head: 'e'.repeat(40), grader_ref: 'f'.repeat(40),
    },
    ciEvidence: validCiEvidence(),
    out: `.planning/phases/x/codex/${head.slice(0, 12)}-new-review-a1`, head, baseRequired: false,
  });
  assert.equal(result.complete, false);
  assert.equal(result.invalidEvidence, true);
  assert.ok(result.reasons.includes('inspection-only meta does not match the output prefix (head, label or attempt)'));
  assert.ok(result.reasons.includes(PROVENANCE_BINDING_REASON), JSON.stringify(result.reasons));
});

test('inspectionOnlyCompleteness: a meta label that differs from the output prefix is invalid evidence', () => {
  const result = predicate({
    meta: inspectionMeta({label: 'old-review'}), status: inspectionStatus(), baseStatus: null,
    boundary: verifiedBoundary({label: 'old-review'}), head: HEAD, baseRequired: false,
  });
  assert.equal(result.complete, false);
  assert.deepEqual(result.reasons, ['inspection-only meta does not match the output prefix (head, label or attempt)']);
});

test('inspectionOnlyCompleteness: a boundary for another label is invalid evidence', () => {
  const result = predicate({
    meta: inspectionMeta(), status: inspectionStatus(), baseStatus: null,
    boundary: verifiedBoundary({label: 'old-review'}), head: HEAD, baseRequired: false,
  });
  assert.equal(result.complete, false);
  assert.deepEqual(result.reasons, ['inspection-only result has no verified isolation boundary for this head, label and attempt']);
});

test('inspectionOnlyCompleteness: provenance must name the grader and reviewed base the meta records', () => {
  const D = 'd'.repeat(40);
  for (const [overrides, metaOverrides] of [
    [{base: 'c'.repeat(40)}, {}],
    [{main_sha: D}, {}],
    [{grader_ref: D}, {}],
    [{harness_head: D}, {}],
    [{main_sha: D, harness_head: D, grader_ref: D}, {}],
    [{base: null}, {}],
    [{main_sha: 'not-a-sha', harness_head: 'not-a-sha', grader_ref: 'not-a-sha'}, {harness_head: 'not-a-sha'}],
  ]) {
    const result = predicate({
      meta: inspectionMeta(metaOverrides), status: inspectionStatus(), baseStatus: null, boundary: verifiedBoundary(),
      provenance: validProvenance(overrides), head: HEAD, baseRequired: false,
    });
    assert.equal(result.complete, false, JSON.stringify(overrides));
    assert.deepEqual(result.reasons, [PROVENANCE_BINDING_REASON], JSON.stringify(overrides));
  }
});

test('inspectionOnlyCompleteness: provenance.established must be exactly true', () => {
  for (const established of [1, 'yes', [1]]) {
    const result = predicate({
      meta: inspectionMeta(), status: inspectionStatus(), baseStatus: null, boundary: verifiedBoundary(),
      provenance: validProvenance({established}), head: HEAD, baseRequired: false,
    });
    assert.equal(result.complete, false, JSON.stringify(established));
    assert.deepEqual(result.reasons, ['grader provenance not established from origin/main']);
  }
});

test('inspectionOnlyCompleteness: CI evidence must exist and be for this head', () => {
  for (const ciEvidence of [
    null, [], {check_runs: []}, {check_runs: [], ci_ready: null}, validCiEvidence({head_sha: 'c'.repeat(40)}),
  ]) {
    const result = predicate({
      meta: inspectionMeta(), status: inspectionStatus(), baseStatus: null, boundary: verifiedBoundary(),
      ciEvidence, head: HEAD, baseRequired: false,
    });
    assert.equal(result.complete, false, JSON.stringify(ciEvidence));
    assert.deepEqual(result.reasons, ['CI evidence is not bound to this head'], JSON.stringify(ciEvidence));
  }
});

test('codexStatusFromOutput: reads <out>.ci-evidence.json; without it a complete claim is invalid evidence', () => {
  const result = codexStatusFromOutput(CODEX_OUT, stubReadFile(inspectionOutputFiles({ciEvidence: null})));
  assert.equal(result.complete, false);
  assert.equal(result.invalidEvidence, true);
});
