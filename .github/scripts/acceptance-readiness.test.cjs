const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {
  readiness, renderChecklist, codexStatusFor, headTrustFor, runCli, AUDITED_INPUTS,
} = require('./acceptance-readiness.cjs');

const HEAD = 'a'.repeat(40);
const BASE = 'b'.repeat(40);
const HEAD12 = HEAD.slice(0, 12);
const OTHER_HEAD = 'c'.repeat(40);
const PHASE_DIR = '85-follow-on-ci-improvements-acceptance-usability';
const CODEX_OUT = `.planning/phases/${PHASE_DIR}/codex/${HEAD12}-task3-a2`;
const DECIDED_AT = '2026-10-27T12:00:00.000Z';
const PR = 90;
const REGISTER_KEY = `${PR}:${HEAD}`;

function baseline() {
  return {
    pr: PR,
    prAuthor: 'thejuran',
    prAuthorIsBot: false,
    isCrossRepository: false,
    draft: false,
    open: true,
    head: HEAD,
    baseSha: BASE,
    checks: [
      {id: 1, name: 'CI ready', head_sha: HEAD, status: 'completed', conclusion: 'success'},
      {id: 2, name: 'CodeQL', head_sha: HEAD, status: 'completed', conclusion: 'success'},
    ],
    comments: [],
    dispositions: {schema: 2, by_pr_head: {[REGISTER_KEY]: {items: {}}}},
    blockers: {schema: 2, global_open: [], by_pr_head: {[REGISTER_KEY]: {open: []}}},
    codex: {
      status: {status: 'complete'},
      baseStatus: null,
      meta: {
        meta_version: 2,
        head: HEAD,
        base: BASE,
        attempt: 1,
        review_mode: 'trusted-local-tests',
        audited_inputs_changed_in_diff: [],
      },
      out: `.planning/phases/${PHASE_DIR}/codex/${HEAD12}-task3-a1`,
    },
    fallback: null,
  };
}

function item(result, name) {
  const found = result.items.find(i => i.name === name);
  assert.ok(found, `expected an item named "${name}"`);
  return found;
}

function validFallback(overrides = {}) {
  return {
    schema: 1,
    pr: PR,
    head: HEAD,
    base: BASE,
    codex_out: CODEX_OUT,
    reviewer: {name: 'vibe-check deep review (owner-run)', kind: 'vibe-check-deep-review'},
    scope: {base: BASE, head: HEAD, diff: 'full'},
    result: {status: 'complete', summary: 'reviewed the full diff', findings: []},
    owner_decision: {decision: 'approve-fallback', verbatim: `approved for ${HEAD12}`, decided_at: DECIDED_AT},
    ...overrides,
  };
}

function codexIncompleteNoFallback() {
  const input = baseline();
  input.codex = {
    status: {status: 'incomplete', reasons: ['codex attempt 2 failed']},
    baseStatus: null,
    meta: {
      meta_version: 2,
      head: HEAD,
      base: BASE,
      attempt: 2,
      review_mode: 'trusted-local-tests',
      audited_inputs_changed_in_diff: [],
    },
    out: CODEX_OUT,
  };
  input.fallback = null;
  return input;
}

function untrustedRefusalOut() {
  return `.planning/phases/${PHASE_DIR}/codex/${HEAD12}-task3-a1`;
}

function untrustedBaseline({prAuthor, prAuthorIsBot, isCrossRepository}) {
  const input = baseline();
  input.prAuthor = prAuthor;
  input.prAuthorIsBot = Boolean(prAuthorIsBot);
  input.isCrossRepository = Boolean(isCrossRepository);
  const out = untrustedRefusalOut();
  input.codex = {
    status: {status: 'incomplete', reasons: ['untrusted head: refused until Phase 85.1']},
    baseStatus: null,
    meta: {
      meta_version: 2,
      head: HEAD,
      base: BASE,
      attempt: 1,
      review_mode: 'untrusted-refused',
      audited_inputs_changed_in_diff: [],
    },
    out,
  };
  input.fallback = null;
  return input;
}

const UNTRUSTED_VARIANTS = [
  {label: 'dependabot[bot] author', prAuthor: 'dependabot[bot]', prAuthorIsBot: true, isCrossRepository: false},
  {label: 'cross-repository PR', prAuthor: 'thejuran', prAuthorIsBot: false, isCrossRepository: true},
  {label: 'author outside TRUSTED_AUTHORS', prAuthor: 'someone-else', prAuthorIsBot: false, isCrossRepository: false},
];

// --- readiness(): all prerequisites present ---

test('all prerequisites present: ready, every item ok', () => {
  const result = readiness(baseline());
  assert.equal(result.ready, true);
  for (const i of result.items) assert.equal(i.status, 'ok', `${i.name} should be ok: ${i.detail}`);
  const checklist = renderChecklist(result);
  assert.ok(checklist.includes(HEAD));
  assert.ok(checklist.includes(BASE));
  assert.ok(checklist.includes('Ready to request approval'));
});

// --- PR ready for review (draft) ---

test('draft true blocks "PR ready for review"', () => {
  const input = baseline();
  input.draft = true;
  const result = readiness(input);
  assert.equal(result.ready, false);
  const i = item(result, 'PR ready for review');
  assert.equal(i.status, 'blocked');
  assert.ok(i.detail.includes('mark the PR ready'));
});

// --- CI ready ---

test('no "CI ready" check for this head blocks CI ready', () => {
  const input = baseline();
  input.checks = input.checks.filter(c => c.name !== 'CI ready');
  const result = readiness(input);
  assert.equal(item(result, 'CI ready').status, 'blocked');
});

test('a "CI ready" conclusion failure blocks CI ready', () => {
  const input = baseline();
  input.checks = input.checks.map(c => (c.name === 'CI ready' ? {...c, conclusion: 'failure'} : c));
  const result = readiness(input);
  assert.equal(item(result, 'CI ready').status, 'blocked');
});

test('a successful "CI ready" on a different head does not count', () => {
  const input = baseline();
  input.checks = input.checks.map(c => (c.name === 'CI ready' ? {...c, head_sha: OTHER_HEAD} : c));
  const result = readiness(input);
  assert.equal(item(result, 'CI ready').status, 'blocked');
});

// --- CodeQL ---

test('CodeQL missing on head blocks CodeQL', () => {
  const input = baseline();
  input.checks = input.checks.filter(c => c.name !== 'CodeQL');
  const result = readiness(input);
  assert.equal(item(result, 'CodeQL').status, 'blocked');
});

test('CodeQL failure on head blocks CodeQL', () => {
  const input = baseline();
  input.checks = input.checks.map(c => (c.name === 'CodeQL' ? {...c, conclusion: 'failure'} : c));
  const result = readiness(input);
  assert.equal(item(result, 'CodeQL').status, 'blocked');
});

test('CodeQL reported as "Analyze (...)" via github-advanced-security is accepted', () => {
  const input = baseline();
  input.checks = input.checks.filter(c => c.name !== 'CodeQL');
  input.checks.push({
    id: 9, name: 'Analyze (javascript)', head_sha: HEAD, status: 'completed', conclusion: 'success',
    app: {slug: 'github-advanced-security'},
  });
  const result = readiness(input);
  assert.equal(item(result, 'CodeQL').status, 'ok');
});

// --- Review acceptance gate (dry run) ---

test('a missing register slice blocks the gate item with assess\'s own message', () => {
  const input = baseline();
  input.dispositions = {schema: 2, by_pr_head: {}};
  const result = readiness(input);
  const i = item(result, 'Review acceptance gate (dry run)');
  assert.equal(i.status, 'blocked');
  assert.ok(i.detail.includes(`No disposition register entry for PR ${PR}`));
});

test('a Greptile finding without disposition blocks the gate item, naming the finding', () => {
  const input = baseline();
  input.checks.push({id: 3, name: 'Greptile Review', head_sha: HEAD, app: {id: 867647}, status: 'completed', conclusion: 'success'});
  input.comments = [{id: 501, user: {login: 'greptile-apps[bot]'}}];
  const result = readiness(input);
  const i = item(result, 'Review acceptance gate (dry run)');
  assert.equal(i.status, 'blocked');
  assert.ok(i.detail.includes('501'));
});

// --- Codex: basic incomplete/complete contract ---

test('Codex status incomplete with no fallback blocks with the standard message', () => {
  const result = readiness(codexIncompleteNoFallback());
  const i = item(result, 'Codex');
  assert.equal(i.status, 'blocked');
  assert.ok(i.detail.includes('INCOMPLETE/PENDING: no recorded fallback; wait or retry later blocks acceptance'));
});

test('Codex complete but a changed grader with an incomplete base-status blocks with the grader-changed detail', () => {
  const input = baseline();
  input.codex = {
    status: {status: 'complete'},
    baseStatus: {status: 'incomplete'},
    meta: {
      meta_version: 2,
      head: HEAD,
      base: BASE,
      attempt: 1,
      review_mode: 'trusted-local-tests',
      audited_inputs_changed_in_diff: ['tests/codex_report_status.py'],
    },
    out: CODEX_OUT,
  };
  const result = readiness(input);
  const i = item(result, 'Codex');
  assert.equal(i.status, 'blocked');
  assert.ok(i.detail.includes('grader changed in this diff'));
});

test('Codex meta head differing from the PR head blocks with a different-head detail', () => {
  const input = baseline();
  input.codex.meta = {...input.codex.meta, head: OTHER_HEAD};
  const result = readiness(input);
  const i = item(result, 'Codex');
  assert.equal(i.status, 'blocked');
  assert.ok(i.detail.includes('Codex evidence is for a different head'));
});

// --- Codex: untrusted head (interim rule until Phase 85.1) ---

for (const variant of UNTRUSTED_VARIANTS) {
  test(`untrusted head (${variant.label}) with its recorded refusal and a valid fallback is ok`, () => {
    const input = untrustedBaseline(variant);
    input.fallback = validFallback({codex_out: untrustedRefusalOut()});
    const result = readiness(input);
    const i = item(result, 'Codex');
    assert.equal(i.status, 'ok');
    assert.ok(i.detail.includes('owner-approved fallback for untrusted head: vibe-check deep review (owner-run)'));
    assert.ok(i.detail.includes('isolated review is Phase 85.1'));
  });

  test(`untrusted head (${variant.label}) with no fallback is blocked`, () => {
    const input = untrustedBaseline(variant);
    const result = readiness(input);
    const i = item(result, 'Codex');
    assert.equal(i.status, 'blocked');
    assert.ok(i.detail.includes(
      'untrusted head (bot/fork): Codex review is refused until Phase 85.1; an owner-approved fallback (D-16) is required'
    ));
  });
}

test('an untrusted head whose Codex files claim complete is blocked even with a fallback present', () => {
  const input = untrustedBaseline(UNTRUSTED_VARIANTS[0]);
  input.codex.meta = {...input.codex.meta, review_mode: 'trusted-local-tests'};
  input.codex.status = {status: 'complete'};
  input.fallback = validFallback({codex_out: untrustedRefusalOut()});
  const result = readiness(input);
  const i = item(result, 'Codex');
  assert.equal(i.status, 'blocked');
  assert.ok(i.detail.includes('Codex evidence claims complete for an untrusted head'));
});

test('a trusted head with only an untrusted-refused record and a fallback is blocked by the validator\'s reason', () => {
  const input = baseline();
  const out = untrustedRefusalOut();
  input.codex = {
    status: {status: 'incomplete', reasons: ['refused']},
    baseStatus: null,
    meta: {
      meta_version: 2,
      head: HEAD,
      base: BASE,
      attempt: 1,
      review_mode: 'untrusted-refused',
      audited_inputs_changed_in_diff: [],
    },
    out,
  };
  input.fallback = validFallback({codex_out: out});
  const result = readiness(input);
  const i = item(result, 'Codex');
  assert.equal(i.status, 'blocked');
  assert.ok(i.detail.includes('does not open the fallback for a trusted head'));
});

// --- Codex: fallback for a trusted head's genuinely-incomplete, retried run ---

test('Codex incomplete with a valid fallback is ok (trusted head)', () => {
  const input = codexIncompleteNoFallback();
  input.fallback = validFallback();
  const result = readiness(input);
  const i = item(result, 'Codex');
  assert.equal(i.status, 'ok');
  assert.ok(i.detail.includes('owner-approved fallback: vibe-check deep review (owner-run)'));
});

const REJECTION_CASES = [
  {label: 'owner_decision wait', mutate: f => { f.owner_decision = {...f.owner_decision, decision: 'wait'}; }, expect: 'owner chose wait'},
  {label: 'owner_decision retry-later', mutate: f => { f.owner_decision = {...f.owner_decision, decision: 'retry-later'}; }, expect: 'owner chose retry later'},
  {label: 'reviewer BM', mutate: f => { f.reviewer = {name: 'BM', kind: 'other-independent'}; }, expect: 'reviewer is not independent'},
  {label: 'missing reviewer', mutate: f => { delete f.reviewer; }, expect: 'missing required field reviewer'},
  {label: 'missing scope', mutate: f => { delete f.scope; }, expect: 'missing required field scope'},
  {label: 'result status "in progress"', mutate: f => { f.result = {...f.result, status: 'in progress'}; }, expect: 'fallback review is not complete'},
  {
    label: 'fallback for another head',
    mutate: f => { f.head = OTHER_HEAD; f.scope = {...f.scope, head: OTHER_HEAD}; },
    expect: 'fallback is for a different head',
  },
];

for (const rc of REJECTION_CASES) {
  test(`Codex incomplete with a fallback rejected by the validator (${rc.label})`, () => {
    const input = codexIncompleteNoFallback();
    const fallback = validFallback();
    rc.mutate(fallback);
    input.fallback = fallback;
    const result = readiness(input);
    const i = item(result, 'Codex');
    assert.equal(i.status, 'blocked');
    assert.ok(i.detail.includes(rc.expect), `expected "${rc.expect}" in ${JSON.stringify(i.detail)}`);
  });
}

// --- headTrustFor / codexStatusFor direct checks ---

test('headTrustFor: a fork PR is untrusted', () => {
  assert.equal(headTrustFor({isCrossRepository: true, author: {login: 'thejuran', is_bot: false}}), 'untrusted');
});

test('headTrustFor: a bot author is untrusted', () => {
  assert.equal(headTrustFor({isCrossRepository: false, author: {login: 'dependabot[bot]', is_bot: true}}), 'untrusted');
});

test('headTrustFor: an author outside TRUSTED_AUTHORS is untrusted', () => {
  assert.equal(headTrustFor({isCrossRepository: false, author: {login: 'someone-else', is_bot: false}}), 'untrusted');
});

test('headTrustFor: the repository owner on the home repo is trusted', () => {
  assert.equal(headTrustFor({isCrossRepository: false, author: {login: 'thejuran', is_bot: false}}), 'trusted');
});

test('codexStatusFor: trusted + complete + no audited changes is ok', () => {
  const result = codexStatusFor({
    status: {status: 'complete'},
    baseStatus: null,
    meta: {head: HEAD, base: BASE, attempt: 1, review_mode: 'trusted-local-tests', audited_inputs_changed_in_diff: []},
    out: CODEX_OUT,
    head: HEAD,
    base: BASE,
    pr: PR,
    prAuthor: 'thejuran',
    headTrust: 'trusted',
    fallback: null,
  });
  assert.equal(result.ok, true);
});

// --- runCli: read-only CLI, multi-page GitHub responses (checker W03) ---

function execTable(table) {
  return (cmd, args) => {
    const key = JSON.stringify([cmd, ...args]);
    if (!Object.hasOwn(table, key)) throw new Error(`unexpected exec call: ${JSON.stringify([cmd, ...args])}`);
    return table[key];
  };
}

function fileTable(table) {
  return path => {
    if (!Object.hasOwn(table, path)) throw new Error(`ENOENT: no such file: ${path}`);
    return table[path];
  };
}

function prViewKey() {
  return JSON.stringify([
    'gh', 'pr', 'view', String(PR), '--repo', 'thejuran/triggarr', '--json',
    'number,state,isDraft,headRefOid,baseRefOid,author,isCrossRepository',
  ]);
}

function checkRunsKey(head = HEAD) {
  return JSON.stringify(['gh', 'api', `repos/thejuran/triggarr/commits/${head}/check-runs`, '--paginate', '--slurp']);
}

function commentsKey() {
  return JSON.stringify(['gh', 'api', `repos/thejuran/triggarr/pulls/${PR}/comments`, '--paginate', '--slurp']);
}

function variableKey(name) {
  return JSON.stringify(['gh', 'variable', 'get', name]);
}

// Mirrors tests/codex_review_run.py AUDITED_INPUTS (checked by a drift test below).
const EXPECTED_AUDITED_INPUTS = [
  'docs/codex-adversarial-review-contract.md',
  '.claude/schemas/codex-review-findings.schema.json',
  'tests/codex_report_status.py',
  'tests/codex_review_run.py',
];

function gitDiffKey(base = BASE, head = HEAD) {
  return JSON.stringify(['git', 'diff', '--name-only', `${base}..${head}`, '--', ...EXPECTED_AUDITED_INPUTS]);
}

function withCapturedConsole(fn) {
  const logs = [];
  const errors = [];
  const originalLog = console.log;
  const originalError = console.error;
  console.log = (...args) => logs.push(args.join(' '));
  console.error = (...args) => errors.push(args.join(' '));
  try {
    const exitCode = fn();
    return {exitCode, logs, errors};
  } finally {
    console.log = originalLog;
    console.error = originalError;
  }
}

test('runCli finds a relevant check run on page 2 and blocks on a page-2 undisposed finding', () => {
  const prInfo = JSON.stringify({
    number: PR, state: 'OPEN', isDraft: false, headRefOid: HEAD, baseRefOid: BASE,
    author: {login: 'thejuran', is_bot: false}, isCrossRepository: false,
  });
  const checksPages = JSON.stringify([
    {total_count: 1, check_runs: [{id: 1, name: 'CodeQL', head_sha: HEAD, status: 'completed', conclusion: 'success'}]},
    {total_count: 1, check_runs: [{id: 2, name: 'CI ready', head_sha: HEAD, status: 'completed', conclusion: 'success'}]},
  ]);
  const commentsPages = JSON.stringify([
    [{id: 1, user: {login: 'greptile-apps[bot]'}}],
    [{id: 2, user: {login: 'greptile-apps[bot]'}}],
  ]);
  const dispositions = {schema: 2, by_pr_head: {[REGISTER_KEY]: {items: {1: {head: HEAD, decision: 'fixed', evidence: 'x'.repeat(20)}}}}};
  const blockers = {schema: 2, global_open: [], by_pr_head: {[REGISTER_KEY]: {open: []}}};

  const exec = execTable({
    [prViewKey()]: prInfo,
    [checkRunsKey()]: checksPages,
    [commentsKey()]: commentsPages,
    [variableKey('REVIEW_DISPOSITIONS')]: JSON.stringify(dispositions),
    [variableKey('REVIEW_BLOCKERS')]: JSON.stringify(blockers),
    [gitDiffKey()]: '',
  });
  const readFile = fileTable({
    [`${CODEX_OUT}.status.json`]: JSON.stringify({status: 'complete'}),
    [`${CODEX_OUT}.meta.json`]: JSON.stringify({
      meta_version: 2, head: HEAD, base: BASE, attempt: 1, review_mode: 'trusted-local-tests', audited_inputs_changed_in_diff: [],
    }),
  });

  const {exitCode, logs} = withCapturedConsole(() => runCli(['--pr', String(PR), '--codex-out', CODEX_OUT], {exec, readFile}));
  assert.equal(exitCode, 1);
  const output = logs.join('\n');
  assert.ok(output.includes('CI ready: ok'));
  assert.ok(output.includes('2'));
});

test('runCli blocks "CI ready" when a page-2 match has a different head_sha', () => {
  const prInfo = JSON.stringify({
    number: PR, state: 'OPEN', isDraft: false, headRefOid: HEAD, baseRefOid: BASE,
    author: {login: 'thejuran', is_bot: false}, isCrossRepository: false,
  });
  const checksPages = JSON.stringify([
    {total_count: 1, check_runs: [{id: 1, name: 'CodeQL', head_sha: HEAD, status: 'completed', conclusion: 'success'}]},
    {total_count: 1, check_runs: [{id: 2, name: 'CI ready', head_sha: OTHER_HEAD, status: 'completed', conclusion: 'success'}]},
  ]);
  const commentsPages = JSON.stringify([[]]);
  const dispositions = {schema: 2, by_pr_head: {[REGISTER_KEY]: {items: {}}}};
  const blockers = {schema: 2, global_open: [], by_pr_head: {[REGISTER_KEY]: {open: []}}};

  const exec = execTable({
    [prViewKey()]: prInfo,
    [checkRunsKey()]: checksPages,
    [commentsKey()]: commentsPages,
    [variableKey('REVIEW_DISPOSITIONS')]: JSON.stringify(dispositions),
    [variableKey('REVIEW_BLOCKERS')]: JSON.stringify(blockers),
    [gitDiffKey()]: '',
  });
  const readFile = fileTable({
    [`${CODEX_OUT}.status.json`]: JSON.stringify({status: 'complete'}),
    [`${CODEX_OUT}.meta.json`]: JSON.stringify({
      meta_version: 2, head: HEAD, base: BASE, attempt: 1, review_mode: 'trusted-local-tests', audited_inputs_changed_in_diff: [],
    }),
  });

  const {exitCode, logs} = withCapturedConsole(() => runCli(['--pr', String(PR), '--codex-out', CODEX_OUT], {exec, readFile}));
  assert.equal(exitCode, 1);
  assert.ok(logs.join('\n').includes('CI ready: BLOCKED'));
});

test('runCli fails closed on unparseable check-runs slurp output', () => {
  const prInfo = JSON.stringify({
    number: PR, state: 'OPEN', isDraft: false, headRefOid: HEAD, baseRefOid: BASE,
    author: {login: 'thejuran', is_bot: false}, isCrossRepository: false,
  });
  const dispositions = {schema: 2, by_pr_head: {[REGISTER_KEY]: {items: {}}}};
  const blockers = {schema: 2, global_open: [], by_pr_head: {[REGISTER_KEY]: {open: []}}};

  const exec = execTable({
    [prViewKey()]: prInfo,
    [checkRunsKey()]: 'not json',
    [commentsKey()]: JSON.stringify([[]]),
    [variableKey('REVIEW_DISPOSITIONS')]: JSON.stringify(dispositions),
    [variableKey('REVIEW_BLOCKERS')]: JSON.stringify(blockers),
    [gitDiffKey()]: '',
  });
  const readFile = fileTable({
    [`${CODEX_OUT}.status.json`]: JSON.stringify({status: 'complete'}),
    [`${CODEX_OUT}.meta.json`]: JSON.stringify({
      meta_version: 2, head: HEAD, base: BASE, attempt: 1, review_mode: 'trusted-local-tests', audited_inputs_changed_in_diff: [],
    }),
  });

  const {exitCode, logs} = withCapturedConsole(() => runCli(['--pr', String(PR), '--codex-out', CODEX_OUT], {exec, readFile}));
  assert.equal(exitCode, 1);
  assert.ok(logs.join('\n').includes('could not read GitHub check runs'));
});

test('runCli fails closed on a non-array comments slurp output', () => {
  const prInfo = JSON.stringify({
    number: PR, state: 'OPEN', isDraft: false, headRefOid: HEAD, baseRefOid: BASE,
    author: {login: 'thejuran', is_bot: false}, isCrossRepository: false,
  });
  const checksPages = JSON.stringify([
    {total_count: 1, check_runs: [{id: 1, name: 'CodeQL', head_sha: HEAD, status: 'completed', conclusion: 'success'}]},
    {total_count: 1, check_runs: [{id: 2, name: 'CI ready', head_sha: HEAD, status: 'completed', conclusion: 'success'}]},
  ]);
  const dispositions = {schema: 2, by_pr_head: {[REGISTER_KEY]: {items: {}}}};
  const blockers = {schema: 2, global_open: [], by_pr_head: {[REGISTER_KEY]: {open: []}}};

  const exec = execTable({
    [prViewKey()]: prInfo,
    [checkRunsKey()]: checksPages,
    [commentsKey()]: JSON.stringify({not: 'an array'}),
    [variableKey('REVIEW_DISPOSITIONS')]: JSON.stringify(dispositions),
    [variableKey('REVIEW_BLOCKERS')]: JSON.stringify(blockers),
    [gitDiffKey()]: '',
  });
  const readFile = fileTable({
    [`${CODEX_OUT}.status.json`]: JSON.stringify({status: 'complete'}),
    [`${CODEX_OUT}.meta.json`]: JSON.stringify({
      meta_version: 2, head: HEAD, base: BASE, attempt: 1, review_mode: 'trusted-local-tests', audited_inputs_changed_in_diff: [],
    }),
  });

  const {exitCode, logs} = withCapturedConsole(() => runCli(['--pr', String(PR), '--codex-out', CODEX_OUT], {exec, readFile}));
  assert.equal(exitCode, 1);
  assert.ok(logs.join('\n').includes('could not read PR comments'));
});

test('runCli: a fully ready PR exits 0 and the output never contains the string "token"', () => {
  const prInfo = JSON.stringify({
    number: PR, state: 'OPEN', isDraft: false, headRefOid: HEAD, baseRefOid: BASE,
    author: {login: 'thejuran', is_bot: false}, isCrossRepository: false,
  });
  const checksPages = JSON.stringify([
    {total_count: 2, check_runs: [
      {id: 1, name: 'CodeQL', head_sha: HEAD, status: 'completed', conclusion: 'success'},
      {id: 2, name: 'CI ready', head_sha: HEAD, status: 'completed', conclusion: 'success'},
    ]},
  ]);
  const dispositions = {schema: 2, by_pr_head: {[REGISTER_KEY]: {items: {}}}};
  const blockers = {schema: 2, global_open: [], by_pr_head: {[REGISTER_KEY]: {open: []}}};

  const exec = execTable({
    [prViewKey()]: prInfo,
    [checkRunsKey()]: checksPages,
    [commentsKey()]: JSON.stringify([[]]),
    [variableKey('REVIEW_DISPOSITIONS')]: JSON.stringify(dispositions),
    [variableKey('REVIEW_BLOCKERS')]: JSON.stringify(blockers),
    [gitDiffKey()]: '',
  });
  const readFile = fileTable({
    [`${CODEX_OUT}.status.json`]: JSON.stringify({status: 'complete'}),
    [`${CODEX_OUT}.meta.json`]: JSON.stringify({
      meta_version: 2, head: HEAD, base: BASE, attempt: 1, review_mode: 'trusted-local-tests', audited_inputs_changed_in_diff: [],
    }),
  });

  const {exitCode, logs, errors} = withCapturedConsole(
    () => runCli(['--pr', String(PR), '--codex-out', CODEX_OUT], {exec, readFile})
  );
  assert.equal(exitCode, 0);
  const output = [...logs, ...errors].join('\n');
  assert.ok(!output.toLowerCase().includes('token'));
  assert.ok(output.includes('Ready to request approval'));
});

test('runCli rejects an invalid --pr before calling the injected exec', () => {
  let execCalled = false;
  let readCalled = false;
  const exec = () => { execCalled = true; throw new Error('exec should not be called'); };
  const readFile = () => { readCalled = true; throw new Error('readFile should not be called'); };
  const {exitCode} = withCapturedConsole(() => runCli(['--pr', '12abc', '--codex-out', CODEX_OUT], {exec, readFile}));
  assert.equal(exitCode, 2);
  assert.equal(execCalled, false);
  assert.equal(readCalled, false);
});

// --- WR-01 regressions: readiness must not trust the head runner's own meta ---

test('AUDITED_INPUTS mirrors tests/codex_review_run.py AUDITED_INPUTS', () => {
  const runner = fs.readFileSync(path.join(__dirname, '../../tests/codex_review_run.py'), 'utf8');
  const block = runner.match(/^AUDITED_INPUTS = \(\n([\s\S]*?)^\)/m);
  assert.ok(block, 'AUDITED_INPUTS tuple not found in tests/codex_review_run.py');
  const pyList = [...block[1].matchAll(/"([^"]+)"/g)].map(m => m[1]);
  assert.deepEqual([...AUDITED_INPUTS], pyList);
  assert.deepEqual([...AUDITED_INPUTS], EXPECTED_AUDITED_INPUTS);
});

test('codexStatusFor: a recomputed audited change overrides a meta that claims none', () => {
  const result = codexStatusFor({
    status: {status: 'complete'},
    baseStatus: null,
    meta: {head: HEAD, base: BASE, attempt: 1, review_mode: 'trusted-local-tests', audited_inputs_changed_in_diff: []},
    auditedChanged: ['tests/codex_report_status.py'],
    out: CODEX_OUT, head: HEAD, base: BASE, pr: PR, prAuthor: 'thejuran', headTrust: 'trusted', fallback: null,
  });
  assert.equal(result.ok, false);
  assert.ok(result.detail.includes('grader changed in this diff'), result.detail);
});

test('codexStatusFor: a meta without head is never complete', () => {
  const meta = {base: BASE, attempt: 1, review_mode: 'trusted-local-tests', audited_inputs_changed_in_diff: []};
  const result = codexStatusFor({
    status: {status: 'complete'}, baseStatus: null, meta, auditedChanged: [],
    out: CODEX_OUT, head: HEAD, base: BASE, pr: PR, prAuthor: 'thejuran', headTrust: 'trusted', fallback: null,
  });
  assert.equal(result.ok, false);
  assert.ok(result.detail.includes('Codex evidence is for a different head'), result.detail);
});

test('codexStatusFor: a meta for a different base (or none) is never complete', () => {
  for (const meta of [
    {head: HEAD, base: 'd'.repeat(40), attempt: 1, review_mode: 'trusted-local-tests', audited_inputs_changed_in_diff: []},
    {head: HEAD, attempt: 1, review_mode: 'trusted-local-tests', audited_inputs_changed_in_diff: []},
  ]) {
    const result = codexStatusFor({
      status: {status: 'complete'}, baseStatus: null, meta, auditedChanged: [],
      out: CODEX_OUT, head: HEAD, base: BASE, pr: PR, prAuthor: 'thejuran', headTrust: 'trusted', fallback: null,
    });
    assert.equal(result.ok, false);
    assert.ok(result.detail.includes('Codex evidence is for a different base'), result.detail);
  }
});

function readyCliFixture(gitDiffOutput) {
  const prInfo = JSON.stringify({
    number: PR, state: 'OPEN', isDraft: false, headRefOid: HEAD, baseRefOid: BASE,
    author: {login: 'thejuran', is_bot: false}, isCrossRepository: false,
  });
  const checksPages = JSON.stringify([
    {total_count: 2, check_runs: [
      {id: 1, name: 'CodeQL', head_sha: HEAD, status: 'completed', conclusion: 'success'},
      {id: 2, name: 'CI ready', head_sha: HEAD, status: 'completed', conclusion: 'success'},
    ]},
  ]);
  const table = {
    [prViewKey()]: prInfo,
    [checkRunsKey()]: checksPages,
    [commentsKey()]: JSON.stringify([[]]),
    [variableKey('REVIEW_DISPOSITIONS')]: JSON.stringify({schema: 2, by_pr_head: {[REGISTER_KEY]: {items: {}}}}),
    [variableKey('REVIEW_BLOCKERS')]: JSON.stringify({schema: 2, global_open: [], by_pr_head: {[REGISTER_KEY]: {open: []}}}),
  };
  if (gitDiffOutput !== undefined) table[gitDiffKey()] = gitDiffOutput;
  const readFile = fileTable({
    [`${CODEX_OUT}.status.json`]: JSON.stringify({status: 'complete'}),
    [`${CODEX_OUT}.meta.json`]: JSON.stringify({
      meta_version: 2, head: HEAD, base: BASE, attempt: 1, review_mode: 'trusted-local-tests',
      audited_inputs_changed_in_diff: [],
    }),
  });
  return {exec: execTable(table), readFile};
}

test('runCli recomputes audited-input changes and blocks when meta hid a changed grader', () => {
  const {exec, readFile} = readyCliFixture('tests/codex_review_run.py\n');
  const {exitCode, logs} = withCapturedConsole(() => runCli(['--pr', String(PR), '--codex-out', CODEX_OUT], {exec, readFile}));
  assert.equal(exitCode, 1);
  const output = logs.join('\n');
  assert.ok(output.includes('Codex: BLOCKED'), output);
  assert.ok(output.includes('grader changed in this diff'), output);
});

test('runCli fails closed when the audited-input diff cannot be computed', () => {
  const {exec, readFile} = readyCliFixture(undefined);
  const {exitCode, errors} = withCapturedConsole(() => runCli(['--pr', String(PR), '--codex-out', CODEX_OUT], {exec, readFile}));
  assert.equal(exitCode, 1);
  assert.ok(errors.some(e => e.includes('could not compute audited-input changes')), errors.join('\n'));
});
