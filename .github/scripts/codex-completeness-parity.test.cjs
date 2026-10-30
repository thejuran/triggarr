// T-85.1-07: acceptance-readiness.cjs's codexStatusFor() and codex-fallback.cjs's
// codexStatusFromOutput() must agree on completeness and on fallback eligibility
// for an untrusted (inspection-only) or trusted head. This file drives the same
// fixture table through both entry points so the two scripts cannot drift.

const {test} = require('node:test');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {readiness, codexStatusFor, ciIndependenceRuleApplies} = require('./acceptance-readiness.cjs');
const {INSPECTION_REVIEW_MODE, codexStatusFromOutput, validateFallback} = require('./codex-fallback.cjs');

const HEAD = 'a'.repeat(40);
const BASE = 'b'.repeat(40);
const HEAD12 = HEAD.slice(0, 12);
// The origin/main SHA the trusted grader came from: provenance main_sha,
// harness_head and grader_ref, and the meta's harness_head (Codex 2aa2cc8 F001).
const MAIN = 'd'.repeat(40);
const PHASE_DIR = '85.1-isolated-codex-review-for-untrusted-prs';
const PR = 90;
const REGISTER_KEY = `${PR}:${HEAD}`;
const DECIDED_AT = '2026-10-28T12:00:00.000Z';

function outPrefix(label, attempt) {
  return `.planning/phases/${PHASE_DIR}/codex/${HEAD12}-${label}-a${attempt}`;
}

function verifiedBoundary(overrides = {}) {
  return {
    boundary_version: 1, verdict: 'verified', reasons: [], head: HEAD, attempt: 1,
    checked_at: DECIDED_AT, image_ref: 'codex-review:local', image_id: `sha256:${'a'.repeat(64)}`,
    codex_version: '0.153.4', credential_mode: 'copied-login', network: 'default', mounts: [],
    env_names: [], canary: 'ok', schema_sha256: 'b'.repeat(64), ...overrides,
  };
}

function validProvenance(overrides = {}) {
  return {
    established: true, main_ref: 'refs/remotes/origin/main', main_sha: MAIN, harness_head: MAIN, base: BASE,
    base_on_main: true, grader_ref: MAIN, grader_source: 'trusted-origin-main', ...overrides,
  };
}

function validCiEvidence(overrides = {}) {
  const ciReady = {
    id: 1, name: 'CI ready', head_sha: HEAD, status: 'completed', conclusion: 'success', html_url: 'https://x/1',
    ...overrides,
  };
  return {check_runs: [ciReady], ci_ready: ciReady};
}

// Author shapes for rows that exercise the CI-independence rule (ciRule).
const COVERED_FORK = Object.freeze({prAuthor: 'outsider', prAuthorIsBot: false, isCrossRepository: true});
const COVERED_COLLABORATOR = Object.freeze({prAuthor: 'collaborator', prAuthorIsBot: false, isCrossRepository: false});
const DEPENDABOT = Object.freeze({prAuthor: 'dependabot[bot]', prAuthorIsBot: true, isCrossRepository: false});

// --- Fixture table: rows covering completeness and fallback-eligibility -----
//
// provenance defaults to a valid trusted-main record when a row omits it;
// null means no .grader-provenance.json at all. ciEvidence likewise defaults
// to valid CI evidence for HEAD (null: no .ci-evidence.json). The meta and a
// non-null boundary carry the row's label unless metaOverrides or the
// boundary itself set one (Codex 2aa2cc8 F001). metaAttempt (default:
// attempt) lets a row record a meta attempt that differs from the -aN suffix
// of its output prefix (WR-05).
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
    label: 'missing-provenance-complete-claim',
    headTrust: 'untrusted',
    attempt: 2,
    meta: {audited_inputs_changed_in_diff: []},
    status: {status: 'complete', inspected_head: HEAD, inspected_base: BASE},
    baseStatus: null,
    boundary: verifiedBoundary({attempt: 2}),
    provenance: null,
    expectComplete: false,
    fallbackEligible: false,
  },
  {
    label: 'provenance-not-established-complete-claim',
    headTrust: 'untrusted',
    attempt: 2,
    meta: {audited_inputs_changed_in_diff: []},
    status: {status: 'complete', inspected_head: HEAD, inspected_base: BASE},
    baseStatus: null,
    boundary: verifiedBoundary({attempt: 2}),
    provenance: {established: false, reasons: ['trusted grader could not be re-verified after the run']},
    expectComplete: false,
    fallbackEligible: false,
  },
  {
    label: 'provenance-base-not-on-main-complete-claim',
    headTrust: 'untrusted',
    attempt: 2,
    meta: {audited_inputs_changed_in_diff: []},
    status: {status: 'complete', inspected_head: HEAD, inspected_base: BASE},
    baseStatus: null,
    boundary: verifiedBoundary({attempt: 2}),
    provenance: validProvenance({base_on_main: false}),
    expectComplete: false,
    fallbackEligible: false,
  },
  {
    label: 'provenance-wrong-grader-source-complete-claim',
    headTrust: 'untrusted',
    attempt: 2,
    meta: {audited_inputs_changed_in_diff: []},
    status: {status: 'complete', inspected_head: HEAD, inspected_base: BASE},
    baseStatus: null,
    boundary: verifiedBoundary({attempt: 2}),
    provenance: validProvenance({grader_source: 'base'}),
    expectComplete: false,
    fallbackEligible: false,
  },
  {
    label: 'provenance-not-an-object-complete-claim',
    headTrust: 'untrusted',
    attempt: 2,
    meta: {audited_inputs_changed_in_diff: []},
    status: {status: 'complete', inspected_head: HEAD, inspected_base: BASE},
    baseStatus: null,
    boundary: verifiedBoundary({attempt: 2}),
    provenance: [],
    expectComplete: false,
    fallbackEligible: false,
  },
  {
    label: 'meta-attempt-differs-from-prefix-complete-claim',
    headTrust: 'untrusted',
    attempt: 2,
    metaAttempt: 3,
    meta: {audited_inputs_changed_in_diff: []},
    status: {status: 'complete', inspected_head: HEAD, inspected_base: BASE},
    baseStatus: null,
    boundary: verifiedBoundary({attempt: 3}), // bound to the meta's attempt, not the prefix's
    expectComplete: false,
    fallbackEligible: false,
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
  // --- BM iter-3 IN-05: the CI-independence stop is fallback-eligible at attempt 1 ---
  // BM iter-4 IN-02: only for a head the rule covers whose .github/ changed or
  // is unknown (ciRule); the status file alone never opens the exception.
  ...[
    ['ci-not-independent-stop-attempt-1', COVERED_FORK, true, true],
    ['ci-not-independent-stop-attempt-1-github-unknown', COVERED_COLLABORATOR, null, true],
    ['ci-not-independent-stop-attempt-1-github-unchanged', COVERED_FORK, false, false],
    ['ci-not-independent-stop-attempt-1-bot-head', DEPENDABOT, true, false],
  ].map(([label, author, ciDefinitionsChanged, fallbackEligible]) => ({
    label,
    headTrust: 'untrusted',
    attempt: 1,
    ciRule: {...author, ciDefinitionsChanged},
    meta: {audited_inputs_changed_in_diff: []},
    status: {
      status: 'incomplete',
      reasons: ['fork or non-bot untrusted PR changes files under .github/; CI evidence is not independent; owner fallback required'],
    },
    baseStatus: null,
    boundary: null,
    provenance: null,
    expectComplete: false,
    fallbackEligible,
  })),
  {
    label: 'ci-not-independent-plus-another-reason-attempt-1',
    headTrust: 'untrusted',
    attempt: 1,
    meta: {audited_inputs_changed_in_diff: []},
    status: {
      status: 'incomplete',
      reasons: [
        'fork or non-bot untrusted PR changes files under .github/; CI evidence is not independent; owner fallback required',
        'interrupted by SIGINT',
      ],
    },
    baseStatus: null,
    boundary: null,
    provenance: null,
    expectComplete: false,
    fallbackEligible: false,
  },
  {
    label: 'other-incomplete-reason-attempt-1',
    headTrust: 'untrusted',
    attempt: 1,
    meta: {audited_inputs_changed_in_diff: []},
    status: {status: 'incomplete', reasons: ['boundary unverified']},
    baseStatus: null,
    boundary: null,
    expectComplete: false,
    fallbackEligible: false,
  },
  // --- Codex 2aa2cc8 F001: records of one attempt must be bound together ---
  ...[
    ['meta-and-boundary-from-another-label', {metaOverrides: {label: 'old-review'}, boundary: verifiedBoundary({label: 'old-review'})}],
    ['boundary-from-another-label', {boundary: verifiedBoundary({label: 'old-review'})}],
    ['provenance-base-differs-from-meta', {provenance: validProvenance({base: 'c'.repeat(40)})}],
    ['provenance-grader-ref-differs-from-main', {provenance: validProvenance({grader_ref: 'e'.repeat(40)})}],
    ['provenance-harness-not-on-main', {provenance: validProvenance({harness_head: 'e'.repeat(40)})}],
    ['provenance-grader-differs-from-meta-harness', {metaOverrides: {harness_head: 'e'.repeat(40)}}],
    ['provenance-established-truthy-not-true', {provenance: validProvenance({established: 1})}],
    ['ci-evidence-missing', {ciEvidence: null}],
    ['ci-evidence-for-another-head', {ciEvidence: validCiEvidence({head_sha: 'c'.repeat(40)})}],
    ['codex-f001-reproduction', {
      metaOverrides: {label: 'old-review'}, boundary: verifiedBoundary({label: 'old-review'}),
      provenance: validProvenance({base: 'c'.repeat(40), main_sha: MAIN, harness_head: 'e'.repeat(40), grader_ref: 'f'.repeat(40)}),
    }],
  ].map(([label, overrides]) => ({
    label: `${label}-complete-claim`,
    headTrust: 'untrusted',
    attempt: 1,
    meta: {audited_inputs_changed_in_diff: []},
    status: {status: 'complete', inspected_head: HEAD, inspected_base: BASE},
    baseStatus: null,
    boundary: verifiedBoundary({attempt: 1}),
    expectComplete: false,
    fallbackEligible: null,
    ...overrides,
  })),
];

assert.ok(ROWS.length >= 24, 'the parity fixture table must have at least 24 rows');

function provenanceFor(row) {
  return row.provenance === undefined ? validProvenance() : row.provenance;
}

function ciEvidenceFor(row) {
  return row.ciEvidence === undefined ? validCiEvidence() : row.ciEvidence;
}

function boundaryFor(row) {
  return row.boundary === null ? null : {label: row.label, ...row.boundary};
}

function filesFor(row, prefix) {
  const reviewMode = row.reviewMode || INSPECTION_REVIEW_MODE;
  const meta = {
    meta_version: 2, head: HEAD, base: BASE, label: row.label, attempt: row.metaAttempt ?? row.attempt,
    review_mode: reviewMode, harness_head: MAIN, trusted: row.headTrust === 'trusted', ...row.meta,
    ...row.metaOverrides,
  };
  const files = {
    [`${prefix}.status.json`]: JSON.stringify(row.status),
    [`${prefix}.meta.json`]: JSON.stringify(meta),
  };
  if (row.baseStatus !== null) files[`${prefix}.base-status.json`] = JSON.stringify(row.baseStatus);
  if (row.boundary !== null) files[`${prefix}.boundary.json`] = JSON.stringify(boundaryFor(row));
  const provenance = provenanceFor(row);
  if (provenance !== null) files[`${prefix}.grader-provenance.json`] = JSON.stringify(provenance);
  const ciEvidence = ciEvidenceFor(row);
  if (ciEvidence !== null) files[`${prefix}.ci-evidence.json`] = JSON.stringify(ciEvidence);
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

function authorFor(row) {
  if (row.ciRule) return row.ciRule;
  return row.headTrust === 'untrusted' ? DEPENDABOT : {prAuthor: 'thejuran', prAuthorIsBot: false, isCrossRepository: false};
}

// The same rule readiness() applies: covered head, and .github/ changed or unknown.
function ciIndependenceRequiredFor(row) {
  const {prAuthor, prAuthorIsBot, isCrossRepository, ciDefinitionsChanged} = {ciDefinitionsChanged: false, ...authorFor(row)};
  return ciIndependenceRuleApplies({isCrossRepository, author: {login: prAuthor, is_bot: prAuthorIsBot}})
    && ciDefinitionsChanged !== false;
}

function readinessInputFor(row, prefix, meta, fallback) {
  const author = authorFor(row);
  return {
    pr: PR,
    prAuthor: author.prAuthor,
    prAuthorIsBot: author.prAuthorIsBot,
    isCrossRepository: author.isCrossRepository,
    ciDefinitionsChanged: row.ciRule ? row.ciRule.ciDefinitionsChanged : false,
    draft: false,
    open: true,
    head: HEAD,
    baseSha: BASE,
    mergeBase: BASE,
    checks: [
      {
        id: 1, name: 'CI ready', head_sha: HEAD, status: 'completed', conclusion: 'success',
        app: {slug: 'github-actions'}, check_suite: {id: 100},
      },
      {id: 2, name: 'CodeQL', head_sha: HEAD, status: 'completed', conclusion: 'success'},
    ],
    workflowRuns: [{id: 7100, check_suite_id: 100, path: '.github/workflows/ci.yml', head_sha: HEAD}],
    comments: [],
    dispositions: {schema: 2, by_pr_head: {[REGISTER_KEY]: {items: {}}}},
    blockers: {schema: 2, global_open: [], by_pr_head: {[REGISTER_KEY]: {open: []}}},
    codex: {
      status: row.status, baseStatus: row.baseStatus, meta, boundary: boundaryFor(row), provenance: provenanceFor(row),
      ciEvidence: ciEvidenceFor(row), out: prefix,
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
      status: row.status, baseStatus: row.baseStatus, meta, boundary: boundaryFor(row), provenance: provenanceFor(row),
      ciEvidence: ciEvidenceFor(row), auditedChanged: [],
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
      prAuthor: authorFor(row).prAuthor,
      headTrust: row.headTrust, codexStatus: fromOutput, ciIndependenceRequired: ciIndependenceRequiredFor(row),
    });

    const result = readiness(readinessInputFor(row, prefix, meta, fallback));
    const codexItem = result.items.find(i => i.name === 'Codex');
    const okViaFallback = codexItem.status === 'ok';

    assert.equal(direct.ok, okViaFallback, `${row.label}: validateFallback.ok=${direct.ok} vs readiness ok=${okViaFallback}`);
    assert.equal(okViaFallback, row.fallbackEligible, `${row.label}: expected fallbackEligible=${row.fallbackEligible}`);
    assert.equal(direct.ok, row.fallbackEligible, `${row.label}: expected fallbackEligible=${row.fallbackEligible}`);
  });
}

// --- Cross-language parity (WR-05): the Python completion gate agrees ------
//
// tests/codex_review_run.py's completion_gate() is the other acceptor named
// in docs/review-checkpoint-record.md. Every inspection-only row is written
// to a temporary REPO_ROOT and graded by the real Python gate; its pass/fail
// must equal the JS completeness above.
const REPO_ROOT = path.resolve(__dirname, '..', '..');
const PY_GATE = `
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from tests import codex_review_run as runner
runner.REPO_ROOT = Path(sys.argv[2])
print(json.dumps({p: runner.completion_gate(Path(p)) for p in json.loads(sys.argv[3])}))
`;

test('cross-language parity: Python completion_gate agrees with JS completeness on every inspection-only row', () => {
  const inspectionRows = ROWS.filter(row => (row.reviewMode || INSPECTION_REVIEW_MODE) === INSPECTION_REVIEW_MODE);
  assert.ok(inspectionRows.length >= 12);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'codex-parity-'));
  try {
    const prefixes = [];
    for (const row of inspectionRows) {
      const prefix = outPrefix(row.label, row.attempt);
      prefixes.push(prefix);
      const {files} = filesFor(row, prefix);
      for (const [relPath, text] of Object.entries(files)) {
        fs.mkdirSync(path.join(tmp, path.dirname(relPath)), {recursive: true});
        fs.writeFileSync(path.join(tmp, relPath), text);
      }
    }
    const proc = spawnSync(
      'uv', ['run', '--frozen', '--quiet', 'python', '-c', PY_GATE, REPO_ROOT, tmp, JSON.stringify(prefixes)],
      {cwd: REPO_ROOT, encoding: 'utf8'},
    );
    assert.equal(proc.status, 0, `python completion gate failed to run: ${proc.stderr || proc.error}`);
    const gate = JSON.parse(proc.stdout);
    for (const row of inspectionRows) {
      const prefix = outPrefix(row.label, row.attempt);
      const fromOutput = codexStatusFromOutput(prefix, filePath => fs.readFileSync(path.join(tmp, filePath), 'utf8'));
      const pythonPass = gate[prefix].length === 0;
      assert.equal(pythonPass, row.expectComplete, `${row.label}: python gate reasons ${JSON.stringify(gate[prefix])}`);
      assert.equal(fromOutput.complete, pythonPass, `${row.label}: JS complete=${fromOutput.complete} vs python pass=${pythonPass}`);
    }
  } finally {
    fs.rmSync(tmp, {recursive: true, force: true});
  }
});

// --- Cross-language parity (BM iter-2 WR-02/WR-03): "CI ready" -------------
//
// acceptance-readiness.cjs's CI ready item and tests/codex_review_run.py's
// ci_evidence() are the two acceptors of CI evidence for an untrusted head.
// Both must count only a github-actions "CI ready" whose check suite belongs
// to a .github/workflows/ci.yml workflow run for this head, refuse one from
// any other (or an unidentifiable) workflow, and take the latest result.
const CI_YML = '.github/workflows/ci.yml';
const OTHER = 'c'.repeat(40);

function ciRun(id, {conclusion = 'success', status = 'completed', slug = 'github-actions', suite = 100, head = HEAD} = {}) {
  const run = {id, name: 'CI ready', head_sha: head, status, conclusion, html_url: `https://x/${id}`};
  if (slug !== null) run.app = {slug};
  if (suite !== null) run.check_suite = {id: suite};
  return run;
}

function wfRun(suite, path = CI_YML, head = HEAD) {
  return {id: 7000 + suite, check_suite_id: suite, path, head_sha: head};
}

const CI_READY_ROWS = [
  {label: 'single-ci-yml-success', checks: [ciRun(1)], workflowRuns: [wfRun(100)], ok: true},
  {label: 'reopen-latest-success', checks: [ciRun(2, {conclusion: 'failure'}), ciRun(5, {suite: 200})], workflowRuns: [wfRun(100), wfRun(200)], ok: true},
  {label: 'reopen-latest-failure', checks: [ciRun(2), ciRun(5, {conclusion: 'failure', suite: 200})], workflowRuns: [wfRun(100), wfRun(200)], ok: false},
  {label: 'foreign-workflow-later-success', checks: [ciRun(2, {conclusion: 'failure'}), ciRun(5, {suite: 200})], workflowRuns: [wfRun(100), wfRun(200, '.github/workflows/evil.yml')], ok: false},
  {label: 'foreign-workflow-only', checks: [ciRun(5, {suite: 200})], workflowRuns: [wfRun(200, '.github/workflows/evil.yml')], ok: false},
  {label: 'other-app-only', checks: [ciRun(9, {slug: 'some-other-app', suite: 900})], workflowRuns: [], ok: false},
  {label: 'other-app-later-success-ci-failed', checks: [ciRun(2, {conclusion: 'failure'}), ciRun(9, {slug: 'some-other-app', suite: 900})], workflowRuns: [wfRun(100)], ok: false},
  {label: 'other-app-ignored-ci-succeeded', checks: [ciRun(2), ciRun(9, {slug: 'some-other-app', suite: 900, conclusion: 'failure'})], workflowRuns: [wfRun(100)], ok: true},
  {label: 'no-app', checks: [ciRun(1, {slug: null})], workflowRuns: [wfRun(100)], ok: false},
  {label: 'no-check-suite', checks: [ciRun(1, {suite: null})], workflowRuns: [wfRun(100)], ok: false},
  {label: 'workflow-unidentified', checks: [ciRun(1)], workflowRuns: [], ok: false},
  {label: 'workflow-run-for-other-head', checks: [ciRun(1)], workflowRuns: [wfRun(100, CI_YML, OTHER)], ok: false},
  {label: 'workflow-run-without-path', checks: [ciRun(1)], workflowRuns: [{check_suite_id: 100, head_sha: HEAD}], ok: false},
  {label: 'workflow-runs-unreadable', checks: [ciRun(1)], workflowRuns: [], workflowRunsError: true, ok: false},
  {label: 'ci-ready-for-other-head', checks: [ciRun(1, {head: OTHER})], workflowRuns: [wfRun(100)], ok: false},
  {label: 'latest-still-running', checks: [ciRun(1), ciRun(3, {status: 'in_progress', conclusion: null})], workflowRuns: [wfRun(100)], ok: false},
  {label: 'no-ci-ready-at-all', checks: [], workflowRuns: [], workflowRunsError: true, ok: false},
];

function jsCiReadyOk(row) {
  const input = readinessInputFor(ROWS[0], outPrefix(ROWS[0].label, ROWS[0].attempt), {}, null);
  input.checks = [...row.checks, {id: 99, name: 'CodeQL', head_sha: HEAD, status: 'completed', conclusion: 'success'}];
  input.workflowRuns = row.workflowRuns;
  if (row.workflowRunsError) input.workflowRunsError = 'could not read GitHub workflow runs';
  return readiness(input).items.find(i => i.name === 'CI ready').status === 'ok';
}

const PY_CI = `
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from tests import codex_review_run as runner
head = sys.argv[2]
result = {}
for row in json.loads(sys.argv[3]):
    def fake(argv, row=row, **kwargs):
        if argv[2].endswith("/check-runs"):
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps([{"check_runs": row["checks"]}]))
        if "/actions/runs?" in argv[2]:
            if row.get("workflowRunsError"):
                return subprocess.CompletedProcess(argv, 1, stdout="")
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps([{"workflow_runs": row["workflowRuns"]}]))
        raise AssertionError(argv)
    run = runner.ReviewRun(head=head, base="b" * 40, label="parity", attempt=1,
                           pr_url="https://github.com/thejuran/triggarr/pull/90", scope="parity",
                           phase_dir=Path(".planning/phases/parity"), trusted=False)
    try:
        runner.ci_evidence(run, fake)
        result[row["label"]] = True
    except runner.RunnerError:
        result[row["label"]] = False
print(json.dumps(result))
`;

for (const row of CI_READY_ROWS) {
  test(`CI ready rule (JS): ${row.label}`, () => {
    assert.equal(jsCiReadyOk(row), row.ok);
  });
}

test('cross-language parity: Python ci_evidence agrees with the JS "CI ready" item on every row', () => {
  const proc = spawnSync(
    'uv', ['run', '--frozen', '--quiet', 'python', '-c', PY_CI, REPO_ROOT, HEAD, JSON.stringify(CI_READY_ROWS)],
    {cwd: REPO_ROOT, encoding: 'utf8'},
  );
  assert.equal(proc.status, 0, `python ci_evidence failed to run: ${proc.stderr || proc.error}`);
  const python = JSON.parse(proc.stdout);
  for (const row of CI_READY_ROWS) {
    assert.equal(python[row.label], row.ok, `${row.label}: python ci_evidence accepted=${python[row.label]}`);
    assert.equal(jsCiReadyOk(row), python[row.label], `${row.label}: JS and Python disagree`);
  }
});

// --- Cross-language parity (SA-03/SA-04, IN-07): who the CI-independence rule covers ---
//
// The runner's ci_independence_rule_applies() decides which heads are stopped;
// acceptance-readiness.cjs's ciIndependenceRuleApplies() decides which heads'
// "CI ready" is shown as not independent. They must agree on every author shape.
const CI_RULE_ROWS = [
  {isCrossRepository: true, login: 'outsider', isBot: false},
  {isCrossRepository: true, login: 'thejuran', isBot: false},
  {isCrossRepository: true, login: 'dependabot[bot]', isBot: true},
  {isCrossRepository: false, login: 'collaborator', isBot: false},
  {isCrossRepository: false, login: 'dependabot[bot]', isBot: false},
  {isCrossRepository: false, login: 'app/dependabot', isBot: true},
  {isCrossRepository: false, login: 'thejuran', isBot: false},
  {isCrossRepository: false, login: '', isBot: false},
  {isCrossRepository: false, login: null, isBot: false},
];

const PY_CI_RULE = `
import json, sys
sys.path.insert(0, sys.argv[1])
from tests import codex_review_run as runner
rows = json.loads(sys.argv[2])
print(json.dumps([runner.ci_independence_rule_applies({
    "is_cross_repository": r["isCrossRepository"], "author_login": r["login"], "author_is_bot": r["isBot"],
}) for r in rows]))
`;

test('cross-language parity: Python ci_independence_rule_applies agrees with JS ciIndependenceRuleApplies', () => {
  const proc = spawnSync(
    'uv', ['run', '--frozen', '--quiet', 'python', '-c', PY_CI_RULE, REPO_ROOT, JSON.stringify(CI_RULE_ROWS)],
    {cwd: REPO_ROOT, encoding: 'utf8'},
  );
  assert.equal(proc.status, 0, `python ci_independence_rule_applies failed to run: ${proc.stderr || proc.error}`);
  const python = JSON.parse(proc.stdout);
  CI_RULE_ROWS.forEach((row, index) => {
    const js = ciIndependenceRuleApplies({isCrossRepository: row.isCrossRepository, author: {login: row.login, is_bot: row.isBot}});
    assert.equal(js, python[index], `${JSON.stringify(row)}: JS ${js} vs python ${python[index]}`);
  });
});
