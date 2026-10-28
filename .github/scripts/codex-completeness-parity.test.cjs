// T-85.1-07: acceptance-readiness.cjs's codexStatusFor() and codex-fallback.cjs's
// codexStatusFromOutput() must agree on completeness and on fallback eligibility
// for an untrusted (inspection-only) or trusted head. This file drives the same
// fixture table through both entry points so the two scripts cannot drift.

const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readiness, codexStatusFor} = require('./acceptance-readiness.cjs');
const {INSPECTION_REVIEW_MODE, codexStatusFromOutput, validateFallback} = require('./codex-fallback.cjs');

const HEAD = 'a'.repeat(40);
const BASE = 'b'.repeat(40);
const HEAD12 = HEAD.slice(0, 12);
const PHASE_DIR = '85.1-isolated-codex-review-for-untrusted-prs';
const PR = 90;
const REGISTER_KEY = `${PR}:${HEAD}`;
const DECIDED_AT = '2026-10-28T12:00:00.000Z';

function outPrefix(label, attempt) {
  return `.planning/phases/${PHASE_DIR}/codex/${HEAD12}-${label}-a${attempt}`;
}

function verifiedBoundary(overrides = {}) {
  return {
    boundary_version: 1, verdict: 'verified', reasons: [], head: HEAD, label: 'parity', attempt: 1,
    checked_at: DECIDED_AT, image_ref: 'codex-review:local', image_id: `sha256:${'a'.repeat(64)}`,
    codex_version: '0.153.4', credential_mode: 'copied-login', network: 'default', mounts: [],
    env_names: [], canary: 'ok', schema_sha256: 'b'.repeat(64), ...overrides,
  };
}

// --- Fixture table: 8 rows covering completeness and fallback-eligibility ---
//
// fallbackEligible is null for rows where the item is already complete
// through the direct path (readiness never consults the fallback in that
// case, so there is nothing to compare); it is true/false for the rows where
// completeness is false and the fallback decision is the thing under test.
const ROWS = [
  {
    label: 'complete-inspection-only',
    headTrust: 'untrusted',
    attempt: 1,
    meta: {audited_inputs_changed_in_diff: []},
    status: {status: 'complete', inspected_head: HEAD, inspected_base: BASE},
    baseStatus: null,
    boundary: verifiedBoundary({attempt: 1}),
    expectComplete: true,
    fallbackEligible: null,
  },
  {
    label: 'missing-boundary-complete-claim',
    headTrust: 'untrusted',
    attempt: 2,
    meta: {audited_inputs_changed_in_diff: []},
    status: {status: 'complete', inspected_head: HEAD, inspected_base: BASE},
    baseStatus: null,
    boundary: null,
    expectComplete: false,
    fallbackEligible: false,
  },
  {
    label: 'wrong-attempt-boundary-complete-claim',
    headTrust: 'untrusted',
    attempt: 2,
    meta: {audited_inputs_changed_in_diff: []},
    status: {status: 'complete', inspected_head: HEAD, inspected_base: BASE},
    baseStatus: null,
    boundary: verifiedBoundary({attempt: 1}), // mismatched: meta.attempt is 2
    expectComplete: false,
    fallbackEligible: false,
  },
  {
    label: 'audited-change-missing-base-status',
    headTrust: 'untrusted',
    attempt: 1,
    meta: {audited_inputs_changed_in_diff: ['tests/codex_report_status.py']},
    status: {status: 'complete', inspected_head: HEAD, inspected_base: BASE},
    baseStatus: null,
    boundary: verifiedBoundary({attempt: 1}),
    expectComplete: false,
    fallbackEligible: false,
  },
  {
    label: 'audited-change-complete-bound-base-status',
    headTrust: 'untrusted',
    attempt: 1,
    meta: {audited_inputs_changed_in_diff: ['tests/codex_report_status.py']},
    status: {status: 'complete', inspected_head: HEAD, inspected_base: BASE},
    baseStatus: {status: 'complete', inspected_head: HEAD, inspected_base: BASE},
    boundary: verifiedBoundary({attempt: 1}),
    expectComplete: true,
    fallbackEligible: null,
  },
  {
    label: 'trusted-complete',
    headTrust: 'trusted',
    attempt: 1,
    reviewMode: 'trusted-local-tests',
    meta: {audited_inputs_changed_in_diff: []},
    status: {status: 'complete', inspected_head: HEAD, inspected_base: BASE},
    baseStatus: null,
    boundary: null,
    expectComplete: true,
    fallbackEligible: null,
  },
  {
    label: 'legitimate-incomplete-attempt-2',
    headTrust: 'untrusted',
    attempt: 2,
    meta: {audited_inputs_changed_in_diff: []},
    status: {status: 'incomplete', reasons: ['boundary unverified']},
    baseStatus: null,
    boundary: null,
    expectComplete: false,
    fallbackEligible: true,
  },
  {
    label: 'unverified-boundary-complete-claim-attempt-2',
    headTrust: 'untrusted',
    attempt: 2,
    meta: {audited_inputs_changed_in_diff: []},
    status: {status: 'complete', inspected_head: HEAD, inspected_base: BASE},
    baseStatus: null,
    boundary: verifiedBoundary({verdict: 'unverified', attempt: 2}),
    expectComplete: false,
    fallbackEligible: false,
  },
];

assert.ok(ROWS.length >= 8, 'the parity fixture table must have at least 8 rows');

function filesFor(row, prefix) {
  const reviewMode = row.reviewMode || INSPECTION_REVIEW_MODE;
  const meta = {
    meta_version: 2, head: HEAD, base: BASE, attempt: row.attempt, review_mode: reviewMode,
    ...row.meta,
  };
  const files = {
    [`${prefix}.status.json`]: JSON.stringify(row.status),
    [`${prefix}.meta.json`]: JSON.stringify(meta),
  };
  if (row.baseStatus !== null) files[`${prefix}.base-status.json`] = JSON.stringify(row.baseStatus);
  if (row.boundary !== null) files[`${prefix}.boundary.json`] = JSON.stringify(row.boundary);
  return {files, meta};
}

function stubReadFile(files) {
  return path => {
    if (!Object.hasOwn(files, path)) throw new Error(`ENOENT: no such file: ${path}`);
    return files[path];
  };
}

function validFallbackFor(prefix) {
  return {
    schema: 1,
    pr: PR,
    head: HEAD,
    base: BASE,
    codex_out: prefix,
    reviewer: {name: 'vibe-check deep review (owner-run)', kind: 'vibe-check-deep-review'},
    scope: {base: BASE, head: HEAD, diff: 'full'},
    result: {status: 'complete', summary: 'reviewed the full diff', findings: []},
    owner_decision: {decision: 'approve-fallback', verbatim: `approved for ${HEAD12}`, decided_at: DECIDED_AT},
  };
}

function readinessInputFor(row, prefix, meta, fallback) {
  return {
    pr: PR,
    prAuthor: row.headTrust === 'untrusted' ? 'dependabot[bot]' : 'thejuran',
    prAuthorIsBot: row.headTrust === 'untrusted',
    isCrossRepository: false,
    draft: false,
    open: true,
    head: HEAD,
    baseSha: BASE,
    mergeBase: BASE,
    checks: [
      {id: 1, name: 'CI ready', head_sha: HEAD, status: 'completed', conclusion: 'success'},
      {id: 2, name: 'CodeQL', head_sha: HEAD, status: 'completed', conclusion: 'success'},
    ],
    comments: [],
    dispositions: {schema: 2, by_pr_head: {[REGISTER_KEY]: {items: {}}}},
    blockers: {schema: 2, global_open: [], by_pr_head: {[REGISTER_KEY]: {open: []}}},
    codex: {
      status: row.status, baseStatus: row.baseStatus, meta, boundary: row.boundary, out: prefix,
    },
    fallback,
  };
}

for (const row of ROWS) {
  test(`completeness parity: codexStatusFor and codexStatusFromOutput agree (${row.label})`, () => {
    const prefix = outPrefix(row.label, row.attempt);
    const {files, meta} = filesFor(row, prefix);
    const readFile = stubReadFile(files);

    const fromOutput = codexStatusFromOutput(prefix, readFile);
    assert.equal(fromOutput.complete, row.expectComplete, `codexStatusFromOutput.complete for ${row.label}`);

    const fromGate = codexStatusFor({
      status: row.status, baseStatus: row.baseStatus, meta, boundary: row.boundary, auditedChanged: [],
      out: prefix, head: HEAD, base: BASE, reviewedBase: BASE, pr: PR,
      prAuthor: row.headTrust === 'untrusted' ? 'dependabot[bot]' : 'thejuran',
      headTrust: row.headTrust, fallback: null,
    });

    assert.equal(fromGate.ok, fromOutput.complete, `codexStatusFor.ok (no fallback) for ${row.label}: ${fromGate.detail}`);
  });
}

for (const row of ROWS.filter(r => r.fallbackEligible !== null)) {
  test(`fallback-eligibility parity: readiness(+fallback) and validateFallback agree (${row.label})`, () => {
    const prefix = outPrefix(row.label, row.attempt);
    const {files, meta} = filesFor(row, prefix);
    const readFile = stubReadFile(files);
    const fallback = validFallbackFor(prefix);

    const fromOutput = codexStatusFromOutput(prefix, readFile);
    const direct = validateFallback(fallback, {
      pr: PR, head: HEAD, base: BASE,
      prAuthor: row.headTrust === 'untrusted' ? 'dependabot[bot]' : 'thejuran',
      headTrust: row.headTrust, codexStatus: fromOutput,
    });

    const result = readiness(readinessInputFor(row, prefix, meta, fallback));
    const codexItem = result.items.find(i => i.name === 'Codex');
    const okViaFallback = codexItem.status === 'ok';

    assert.equal(direct.ok, okViaFallback, `${row.label}: validateFallback.ok=${direct.ok} vs readiness ok=${okViaFallback}`);
    assert.equal(okViaFallback, row.fallbackEligible, `${row.label}: expected fallbackEligible=${row.fallbackEligible}`);
    assert.equal(direct.ok, row.fallbackEligible, `${row.label}: expected fallbackEligible=${row.fallbackEligible}`);
  });
}
