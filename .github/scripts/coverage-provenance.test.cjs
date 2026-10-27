const {test} = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const {
  buildProvenance,
  buildLocalProvenance,
  checkEvidence,
  MEASURED_PATHS,
  runCli,
} = require('./coverage-provenance.cjs');

function sha256(text) {
  return crypto.createHash('sha256').update(text, 'utf8').digest('hex');
}

const HEAD_SHA = '1'.repeat(40);
const BASE_SHA = '2'.repeat(40);
const MERGE_SHA = '3'.repeat(40);
const PUSH_SHA = '4'.repeat(40);
const LOCAL_SHA = '5'.repeat(40);
const OTHER_SHA = '6'.repeat(40);
const RUN_ID = '987654321';

const WITH_BRANCHES =
  '<?xml version="1.0"?>\n<coverage line-rate="0.5" branch-rate="0.1" branches-valid="10" branches-covered="2"></coverage>\n';
const NO_BRANCHES =
  '<?xml version="1.0"?>\n<coverage line-rate="0.5" branch-rate="0" branches-valid="0" branches-covered="0"></coverage>\n';
const NO_BRANCH_ATTR = '<?xml version="1.0"?>\n<coverage line-rate="0.5"></coverage>\n';

const MEASURED_TREES = {
  triggarr: 'a'.repeat(40),
  tests: 'b'.repeat(40),
  'pyproject.toml': 'c'.repeat(40),
  'uv.lock': 'd'.repeat(40),
};

const PR_ENV = {
  GITHUB_EVENT_NAME: 'pull_request',
  GITHUB_SHA: MERGE_SHA,
  GITHUB_RUN_ID: RUN_ID,
  GITHUB_RUN_ATTEMPT: '1',
  GITHUB_WORKFLOW: 'CI',
  GITHUB_REPOSITORY: 'thejuran/triggarr',
  PR_HEAD_SHA: HEAD_SHA,
  PR_BASE_SHA: BASE_SHA,
};

const PUSH_ENV = {
  GITHUB_EVENT_NAME: 'push',
  GITHUB_SHA: PUSH_SHA,
  GITHUB_RUN_ID: RUN_ID,
  GITHUB_RUN_ATTEMPT: '1',
  GITHUB_WORKFLOW: 'CI',
  GITHUB_REPOSITORY: 'thejuran/triggarr',
};

function prProvenance({testExit = 0, coverageText = WITH_BRANCHES} = {}) {
  return buildProvenance(PR_ENV, {coverageText, testExit, testSeconds: 90, measuredTrees: MEASURED_TREES});
}

function pushProvenance({testExit = 0, coverageText = WITH_BRANCHES} = {}) {
  return buildProvenance(PUSH_ENV, {coverageText, testExit, testSeconds: 10, measuredTrees: MEASURED_TREES});
}

function localProvenanceFixture({testExit = 0} = {}) {
  return buildLocalProvenance({head: LOCAL_SHA, coverageText: WITH_BRANCHES, testExit, testSeconds: 5, measuredTrees: MEASURED_TREES});
}

// ---- buildProvenance ----

test('buildProvenance for pull_request event returns pull-request-synthetic-merge kind bound to the PR head', () => {
  const provenance = buildProvenance(PR_ENV, {
    coverageText: WITH_BRANCHES,
    testExit: 0,
    testSeconds: 90,
    measuredTrees: MEASURED_TREES,
    now: () => new Date('2026-10-27T00:00:00Z'),
  });
  assert.equal(provenance.schema, 1);
  assert.equal(provenance.event_name, 'pull_request');
  assert.equal(provenance.tested_sha_kind, 'pull-request-synthetic-merge');
  assert.equal(provenance.pr_head_sha, HEAD_SHA);
  assert.equal(provenance.pr_base_sha, BASE_SHA);
  assert.equal(provenance.tested_sha, MERGE_SHA);
  assert.equal(provenance.coverage_sha256, sha256(WITH_BRANCHES));
  assert.equal(provenance.branch_coverage, true);
  assert.deepEqual(provenance.measured_trees, MEASURED_TREES);
});

test('buildProvenance for push event has a null pr_head_sha and push-head kind', () => {
  const provenance = buildProvenance(PUSH_ENV, {
    coverageText: WITH_BRANCHES,
    testExit: 0,
    testSeconds: 42,
    measuredTrees: MEASURED_TREES,
  });
  assert.equal(provenance.pr_head_sha, null);
  assert.equal(provenance.pr_base_sha, null);
  assert.equal(provenance.tested_sha_kind, 'push-head');
  assert.equal(provenance.tested_sha, PUSH_SHA);
});

test('buildProvenance throws when GITHUB_SHA is missing', () => {
  assert.throws(
    () =>
      buildProvenance(
        {GITHUB_EVENT_NAME: 'push', GITHUB_RUN_ID: RUN_ID},
        {coverageText: WITH_BRANCHES, testExit: 0, testSeconds: 1, measuredTrees: MEASURED_TREES}
      ),
    /GITHUB_SHA/
  );
});

test('buildProvenance throws when GITHUB_RUN_ID is missing', () => {
  assert.throws(
    () =>
      buildProvenance(
        {GITHUB_EVENT_NAME: 'push', GITHUB_SHA: PUSH_SHA},
        {coverageText: WITH_BRANCHES, testExit: 0, testSeconds: 1, measuredTrees: MEASURED_TREES}
      ),
    /GITHUB_RUN_ID/
  );
});

test('buildProvenance throws when GITHUB_SHA is not 40 hex', () => {
  assert.throws(
    () =>
      buildProvenance(
        {GITHUB_EVENT_NAME: 'push', GITHUB_SHA: 'not-a-sha', GITHUB_RUN_ID: RUN_ID},
        {coverageText: WITH_BRANCHES, testExit: 0, testSeconds: 1, measuredTrees: MEASURED_TREES}
      ),
    /40-hex/
  );
});

test('buildProvenance throws when measuredTrees is missing a MEASURED_PATHS entry', () => {
  const incomplete = {...MEASURED_TREES};
  delete incomplete['uv.lock'];
  assert.throws(
    () => buildProvenance(PUSH_ENV, {coverageText: WITH_BRANCHES, testExit: 0, testSeconds: 1, measuredTrees: incomplete}),
    /uv\.lock/
  );
});

// ---- buildLocalProvenance ----

test('buildLocalProvenance returns local-exact-head kind bound to the given head', () => {
  const provenance = buildLocalProvenance({
    head: LOCAL_SHA,
    coverageText: WITH_BRANCHES,
    testExit: 0,
    testSeconds: 12,
    measuredTrees: MEASURED_TREES,
  });
  assert.equal(provenance.event_name, 'local');
  assert.equal(provenance.tested_sha_kind, 'local-exact-head');
  assert.equal(provenance.tested_sha, LOCAL_SHA);
  assert.equal(provenance.pr_head_sha, null);
  assert.equal(provenance.pr_base_sha, null);
  assert.equal(provenance.run_id, null);
  assert.equal(provenance.run_attempt, null);
  assert.equal(provenance.workflow, 'local');
});

// ---- MEASURED_PATHS ----

test('MEASURED_PATHS is frozen to the four files that determine what coverage measures', () => {
  assert.deepEqual(MEASURED_PATHS, ['triggarr', 'tests', 'pyproject.toml', 'uv.lock']);
});

// ---- checkEvidence ----

test('checkEvidence valid PR case returns no problems', () => {
  const problems = checkEvidence({
    provenance: prProvenance(),
    coverageText: WITH_BRANCHES,
    expectedHead: HEAD_SHA,
    headTrees: MEASURED_TREES,
  });
  assert.deepEqual(problems, []);
});

test('checkEvidence rejects a wrong-commit PR association', () => {
  const problems = checkEvidence({
    provenance: prProvenance(),
    coverageText: WITH_BRANCHES,
    expectedHead: OTHER_SHA,
    headTrees: MEASURED_TREES,
  });
  assert.ok(problems.some(p => p.includes('wrong commit')), JSON.stringify(problems));
});

test('checkEvidence flags using the synthetic merge commit as if it were the PR head', () => {
  const problems = checkEvidence({
    provenance: prProvenance(),
    coverageText: WITH_BRANCHES,
    expectedHead: MERGE_SHA,
    headTrees: MEASURED_TREES,
  });
  assert.ok(problems.some(p => p.includes('synthetic merge commit')), JSON.stringify(problems));
});

test('checkEvidence (B08) rejects a synthetic-merge report when measured source differs for triggarr', () => {
  const headTrees = {...MEASURED_TREES, triggarr: 'f'.repeat(40)};
  const problems = checkEvidence({
    provenance: prProvenance(),
    coverageText: WITH_BRANCHES,
    expectedHead: HEAD_SHA,
    headTrees,
  });
  assert.ok(
    problems.some(p => p.includes('measured source differs between the tested commit and the reviewed head: triggarr')),
    JSON.stringify(problems)
  );
});

test('checkEvidence (B08) rejects a synthetic-merge report when measured source differs for uv.lock', () => {
  const headTrees = {...MEASURED_TREES, 'uv.lock': 'f'.repeat(40)};
  const problems = checkEvidence({
    provenance: prProvenance(),
    coverageText: WITH_BRANCHES,
    expectedHead: HEAD_SHA,
    headTrees,
  });
  assert.ok(
    problems.some(p => p.includes('measured source differs between the tested commit and the reviewed head: uv.lock')),
    JSON.stringify(problems)
  );
});

test('checkEvidence rejects evidence when the reviewed head measured source cannot be read', () => {
  const problems = checkEvidence({
    provenance: prProvenance(),
    coverageText: WITH_BRANCHES,
    expectedHead: HEAD_SHA,
    headTrees: null,
  });
  assert.ok(
    problems.some(p => p.includes("cannot read the reviewed head's measured source")),
    JSON.stringify(problems)
  );
});

test('checkEvidence accepts a push-head report bound to the pushed commit', () => {
  const problems = checkEvidence({
    provenance: pushProvenance(),
    coverageText: WITH_BRANCHES,
    expectedHead: PUSH_SHA,
    headTrees: MEASURED_TREES,
  });
  assert.deepEqual(problems, []);
});

test('checkEvidence accepts a local-exact-head report bound to the reviewed head', () => {
  const problems = checkEvidence({
    provenance: localProvenanceFixture(),
    coverageText: WITH_BRANCHES,
    expectedHead: LOCAL_SHA,
    headTrees: MEASURED_TREES,
  });
  assert.deepEqual(problems, []);
});

test('checkEvidence rejects a local-exact-head report for the wrong head', () => {
  const problems = checkEvidence({
    provenance: localProvenanceFixture(),
    coverageText: WITH_BRANCHES,
    expectedHead: OTHER_SHA,
    headTrees: MEASURED_TREES,
  });
  assert.ok(problems.some(p => p.includes('wrong commit')), JSON.stringify(problems));
});

test('checkEvidence rejects a missing coverage.xml', () => {
  const problems = checkEvidence({
    provenance: pushProvenance(),
    coverageText: null,
    expectedHead: PUSH_SHA,
    headTrees: MEASURED_TREES,
  });
  assert.ok(problems.some(p => p.includes('coverage.xml is missing')), JSON.stringify(problems));
});

test('checkEvidence rejects a coverage.xml that does not match the provenance checksum', () => {
  const problems = checkEvidence({
    provenance: pushProvenance(),
    coverageText: NO_BRANCHES,
    expectedHead: PUSH_SHA,
    headTrees: MEASURED_TREES,
  });
  assert.ok(
    problems.some(p => p.includes('coverage.xml does not match the provenance checksum')),
    JSON.stringify(problems)
  );
});

test('checkEvidence rejects coverage with no branch data', () => {
  const provenance = buildProvenance(PUSH_ENV, {
    coverageText: NO_BRANCH_ATTR,
    testExit: 0,
    testSeconds: 10,
    measuredTrees: MEASURED_TREES,
  });
  const problems = checkEvidence({
    provenance,
    coverageText: NO_BRANCH_ATTR,
    expectedHead: PUSH_SHA,
    headTrees: MEASURED_TREES,
  });
  assert.ok(problems.some(p => p.includes('no branch coverage data')), JSON.stringify(problems));
});

test('checkEvidence rejects coverage with branches-valid="0"', () => {
  const provenance = buildProvenance(PUSH_ENV, {
    coverageText: NO_BRANCHES,
    testExit: 0,
    testSeconds: 10,
    measuredTrees: MEASURED_TREES,
  });
  const problems = checkEvidence({
    provenance,
    coverageText: NO_BRANCHES,
    expectedHead: PUSH_SHA,
    headTrees: MEASURED_TREES,
  });
  assert.ok(problems.some(p => p.includes('no branch coverage data')), JSON.stringify(problems));
});

test('checkEvidence rejects evidence from a failed test run', () => {
  const problems = checkEvidence({
    provenance: pushProvenance({testExit: 1}),
    coverageText: WITH_BRANCHES,
    expectedHead: PUSH_SHA,
    headTrees: MEASURED_TREES,
  });
  assert.ok(problems.some(p => p.includes('tests failed in this run')), JSON.stringify(problems));
});

test('checkEvidence rejects evidence from a different CI run when a run id is expected', () => {
  const problems = checkEvidence({
    provenance: pushProvenance(),
    coverageText: WITH_BRANCHES,
    expectedHead: PUSH_SHA,
    expectedRunId: 'some-other-run-id',
    headTrees: MEASURED_TREES,
  });
  assert.ok(problems.some(p => p.includes('different CI run')), JSON.stringify(problems));
});

test('checkEvidence accepts evidence when the expected run id matches', () => {
  const problems = checkEvidence({
    provenance: pushProvenance(),
    coverageText: WITH_BRANCHES,
    expectedHead: PUSH_SHA,
    expectedRunId: RUN_ID,
    headTrees: MEASURED_TREES,
  });
  assert.deepEqual(problems, []);
});

test('checkEvidence throws on a schema mismatch', () => {
  const provenance = {...pushProvenance(), schema: 2};
  assert.throws(
    () =>
      checkEvidence({provenance, coverageText: WITH_BRANCHES, expectedHead: PUSH_SHA, headTrees: MEASURED_TREES}),
    /provenance/
  );
});

test('checkEvidence throws on unparseable provenance', () => {
  assert.throws(
    () =>
      checkEvidence({
        provenance: '{not json',
        coverageText: WITH_BRANCHES,
        expectedHead: PUSH_SHA,
        headTrees: MEASURED_TREES,
      }),
    /provenance/
  );
});

// ---- runCli ----

function fakeIo(overrides = {}) {
  return {
    env: {},
    git: () => {
      throw new Error('git should not be called in this test');
    },
    readFile: () => {
      throw new Error('readFile should not be called in this test');
    },
    writeFile: () => {
      throw new Error('writeFile should not be called in this test');
    },
    log: () => {},
    error: () => {},
    now: () => new Date('2026-10-27T00:00:00Z'),
    ...overrides,
  };
}

test('runCli write-local refuses when the worktree is not clean', () => {
  const errors = [];
  const io = fakeIo({
    git: argsArr => {
      if (argsArr.join(' ') === 'status --porcelain') return ' M some-file.txt';
      throw new Error(`unexpected git call: ${argsArr.join(' ')}`);
    },
    error: msg => errors.push(msg),
  });
  const exitCode = runCli(
    ['write-local', '--head', LOCAL_SHA, '--coverage', 'coverage.xml', '--test-exit', '0', '--test-seconds', '1', '--out', 'out.json'],
    io
  );
  assert.equal(exitCode, 1);
  assert.ok(errors.some(m => m.includes('worktree is not clean')), JSON.stringify(errors));
});

test('runCli write-local refuses when HEAD does not match --head', () => {
  const errors = [];
  const io = fakeIo({
    git: argsArr => {
      const joined = argsArr.join(' ');
      if (joined === 'status --porcelain') return '';
      if (joined === 'rev-parse HEAD') return OTHER_SHA;
      throw new Error(`unexpected git call: ${joined}`);
    },
    error: msg => errors.push(msg),
  });
  const exitCode = runCli(
    ['write-local', '--head', LOCAL_SHA, '--coverage', 'coverage.xml', '--test-exit', '0', '--test-seconds', '1', '--out', 'out.json'],
    io
  );
  assert.equal(exitCode, 1);
  assert.ok(errors.some(m => m.includes('HEAD is not --head')), JSON.stringify(errors));
});

test('runCli write-local succeeds on a clean worktree at the exact head', () => {
  const written = {};
  const io = fakeIo({
    git: argsArr => {
      const joined = argsArr.join(' ');
      if (joined === 'status --porcelain') return '';
      if (joined === 'rev-parse HEAD') return LOCAL_SHA;
      if (argsArr[0] === 'rev-parse') {
        const [sha, pathPart] = argsArr[1].split(':');
        assert.equal(sha, LOCAL_SHA);
        return MEASURED_TREES[pathPart];
      }
      throw new Error(`unexpected git call: ${joined}`);
    },
    readFile: () => WITH_BRANCHES,
    writeFile: (p, data) => {
      written.path = p;
      written.data = data;
    },
  });

  const exitCode = runCli(
    ['write-local', '--head', LOCAL_SHA, '--coverage', 'coverage.xml', '--test-exit', '0', '--test-seconds', '3', '--out', 'coverage-provenance.json'],
    io
  );
  assert.equal(exitCode, 0);
  const provenance = JSON.parse(written.data);
  assert.equal(provenance.tested_sha_kind, 'local-exact-head');
  assert.equal(provenance.tested_sha, LOCAL_SHA);
  assert.equal(written.path, 'coverage-provenance.json');
});

test('runCli write computes measured trees at HEAD and writes provenance even when tests failed', () => {
  const written = {};
  const io = fakeIo({
    env: PUSH_ENV,
    git: argsArr => {
      const joined = argsArr.join(' ');
      if (joined === 'rev-parse HEAD') return PUSH_SHA;
      if (argsArr[0] === 'rev-parse') {
        const [sha, pathPart] = argsArr[1].split(':');
        assert.equal(sha, 'HEAD');
        return MEASURED_TREES[pathPart];
      }
      throw new Error(`unexpected git call: ${joined}`);
    },
    readFile: () => WITH_BRANCHES,
    writeFile: (p, data) => {
      written.path = p;
      written.data = data;
    },
  });

  const exitCode = runCli(
    ['write', '--coverage', 'coverage.xml', '--test-exit', '1', '--test-seconds', '77', '--out', 'coverage-provenance.json'],
    io
  );
  assert.equal(exitCode, 0);
  const provenance = JSON.parse(written.data);
  assert.equal(provenance.test_exit_code, 1);
  assert.equal(provenance.tested_sha, PUSH_SHA);
});

test('runCli write refuses when HEAD does not match GITHUB_SHA', () => {
  const errors = [];
  const io = fakeIo({
    env: PUSH_ENV,
    git: argsArr => {
      const joined = argsArr.join(' ');
      if (joined === 'rev-parse HEAD') return OTHER_SHA;
      throw new Error(`unexpected git call: ${joined}`);
    },
    error: msg => errors.push(msg),
  });

  const exitCode = runCli(
    ['write', '--coverage', 'coverage.xml', '--test-exit', '0', '--test-seconds', '1', '--out', 'coverage-provenance.json'],
    io
  );
  assert.equal(exitCode, 1);
  assert.ok(errors.length > 0);
});

test('runCli check exits 0 and logs the match when evidence is valid', () => {
  const provenance = pushProvenance();
  const logs = [];
  const io = fakeIo({
    readFile: p => (p === 'coverage-provenance.json' ? JSON.stringify(provenance) : WITH_BRANCHES),
    git: argsArr => {
      if (argsArr[0] === 'rev-parse') {
        const [sha, pathPart] = argsArr[1].split(':');
        assert.equal(sha, PUSH_SHA);
        return MEASURED_TREES[pathPart];
      }
      throw new Error(`unexpected git call: ${argsArr.join(' ')}`);
    },
    log: msg => logs.push(msg),
  });

  const exitCode = runCli(
    ['check', '--provenance', 'coverage-provenance.json', '--coverage', 'coverage.xml', '--expected-head', PUSH_SHA],
    io
  );
  assert.equal(exitCode, 0);
  assert.ok(logs.some(m => m.includes(`Coverage evidence matches head ${PUSH_SHA}`)), JSON.stringify(logs));
});

test('runCli check exits 1 and prints each problem when evidence is invalid', () => {
  const provenance = pushProvenance({testExit: 1});
  const errors = [];
  const io = fakeIo({
    readFile: p => (p === 'coverage-provenance.json' ? JSON.stringify(provenance) : WITH_BRANCHES),
    git: () => {
      throw new Error('head unreadable');
    },
    error: msg => errors.push(msg),
  });

  const exitCode = runCli(
    ['check', '--provenance', 'coverage-provenance.json', '--coverage', 'coverage.xml', '--expected-head', PUSH_SHA],
    io
  );
  assert.equal(exitCode, 1);
  assert.ok(errors.some(m => m.includes('tests failed in this run')), JSON.stringify(errors));
  assert.ok(errors.some(m => m.includes("cannot read the reviewed head's measured source")), JSON.stringify(errors));
});
