const {test, describe} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {REQUIRED_JOBS} = require('./release-policy.cjs');
const {
  parseJobs,
  extractCiReady,
  checkJobListConsistency,
  extractJobIf,
  findSkipConditions,
  requiredJobsFor,
  aggregateCanPassWith,
  STEP_IF_ALLOWLIST,
  TRIGGER_CONTRACTS,
} = require('./ci-job-consistency.cjs');

const ciPath = path.join(__dirname, '../workflows/ci.yml');
const releasePath = path.join(__dirname, '../workflows/release.yml');
const acceptancePath = path.join(__dirname, '../workflows/review-acceptance.yml');
const ciText = fs.readFileSync(ciPath, 'utf8');
const releaseText = fs.readFileSync(releasePath, 'utf8');
const acceptanceText = fs.readFileSync(acceptancePath, 'utf8');

const NEEDS_LINE =
  '    needs: [test, lint, docker, secrets, dependencies, image-smoke, browser-e2e, os-scan, actionlint]';
const PYTHON_REQUIRED_LINE =
  '          required = {"test", "lint", "docker", "secrets", "dependencies", "image-smoke", "browser-e2e", ' +
  '"os-scan", "actionlint"}\n';

// Asserts the replacement actually changed the text so a negative test
// cannot pass vacuously if ci.yml/release.yml formatting changes underneath it.
function mutate(text, from, to) {
  assert.ok(text.includes(from), `expected to find ${JSON.stringify(from)} in text`);
  const result = text.replace(from, to);
  assert.notEqual(result, text, 'mutation did not change text');
  return result;
}

test('real ci.yml and real REQUIRED_JOBS are consistent', () => {
  assert.deepEqual(checkJobListConsistency({workflowText: ciText, requiredJobs: REQUIRED_JOBS}), []);
});

test('renamed job id breaks consistency', () => {
  let mutated = mutate(ciText, '  lint:\n', '  ruff:\n');
  mutated = mutate(mutated, '    needs: [test, lint]', '    needs: [test, ruff]');
  const problems = checkJobListConsistency({workflowText: mutated, requiredJobs: REQUIRED_JOBS});
  assert.ok(problems.length > 0);
});

test('extra job only in ci-ready needs breaks consistency', () => {
  let mutated = mutate(ciText, NEEDS_LINE,
    '    needs: [test, lint, docker, secrets, dependencies, image-smoke, browser-e2e, os-scan, actionlint, extra]');
  mutated = mutate(mutated, '  ci-ready:\n', '  extra:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo noop\n  ci-ready:\n');
  const problems = checkJobListConsistency({workflowText: mutated, requiredJobs: REQUIRED_JOBS});
  assert.ok(problems.length > 0);
});

test('extra job only in REQUIRED_JOBS breaks consistency', () => {
  const problems = checkJobListConsistency({workflowText: ciText, requiredJobs: [...REQUIRED_JOBS, 'extra']});
  assert.ok(problems.length > 0);
});

test('extra job only in the Python required set breaks consistency', () => {
  const mutated = mutate(ciText, PYTHON_REQUIRED_LINE,
    '          required = {"test", "lint", "docker", "secrets", "dependencies", "image-smoke", "browser-e2e", ' +
    '"os-scan", "actionlint", "extra"}\n');
  const problems = checkJobListConsistency({workflowText: mutated, requiredJobs: REQUIRED_JOBS});
  assert.ok(problems.length > 0);
});

test('job removed from needs and Python set (REQUIRED_JOBS unchanged) breaks consistency', () => {
  let mutated = mutate(ciText, NEEDS_LINE,
    '    needs: [test, lint, docker, secrets, image-smoke, browser-e2e, os-scan, actionlint]');
  mutated = mutate(mutated, PYTHON_REQUIRED_LINE,
    '          required = {"test", "lint", "docker", "secrets", "image-smoke", "browser-e2e", "os-scan", "actionlint"}\n');
  const problems = checkJobListConsistency({workflowText: mutated, requiredJobs: REQUIRED_JOBS});
  assert.ok(problems.length > 0);
});

test('removing image-smoke from needs and the Python set (REQUIRED_JOBS unchanged) breaks consistency', () => {
  let mutated = mutate(ciText, NEEDS_LINE,
    '    needs: [test, lint, docker, secrets, dependencies, browser-e2e, os-scan, actionlint]');
  mutated = mutate(mutated, PYTHON_REQUIRED_LINE,
    '          required = {"test", "lint", "docker", "secrets", "dependencies", "browser-e2e", "os-scan", "actionlint"}\n');
  const problems = checkJobListConsistency({workflowText: mutated, requiredJobs: REQUIRED_JOBS});
  assert.ok(problems.length > 0);
});

test('removing browser-e2e from REQUIRED_JOBS only breaks consistency', () => {
  const requiredJobs = REQUIRED_JOBS.filter(name => name !== 'browser-e2e');
  const problems = checkJobListConsistency({workflowText: ciText, requiredJobs});
  assert.ok(problems.length > 0);
});

test('display-name override on a needed job breaks consistency', () => {
  const mutated = mutate(ciText, '  test:\n    timeout-minutes: 20', '  test:\n    name: Unit tests\n    timeout-minutes: 20');
  const problems = checkJobListConsistency({workflowText: mutated, requiredJobs: REQUIRED_JOBS});
  assert.ok(problems.length > 0);
});

test('aggregate display name change breaks consistency', () => {
  const mutated = mutate(ciText, '    name: CI ready', '    name: CI gate');
  const problems = checkJobListConsistency({workflowText: mutated, requiredJobs: REQUIRED_JOBS});
  assert.ok(problems.length > 0);
});

test('duplicate entry in REQUIRED_JOBS breaks consistency', () => {
  const problems = checkJobListConsistency({workflowText: ciText, requiredJobs: [...REQUIRED_JOBS, 'test']});
  assert.ok(problems.length > 0);
});

test('duplicate entry in ci-ready needs breaks consistency', () => {
  const mutated = mutate(ciText, NEEDS_LINE,
    '    needs: [test, lint, docker, secrets, dependencies, image-smoke, browser-e2e, os-scan, actionlint, test]');
  const problems = checkJobListConsistency({workflowText: mutated, requiredJobs: REQUIRED_JOBS});
  assert.ok(problems.length > 0);
});

test('duplicate entry in the Python required set breaks consistency', () => {
  const mutated = mutate(ciText, PYTHON_REQUIRED_LINE,
    '          required = {"test", "lint", "docker", "secrets", "dependencies", "image-smoke", "browser-e2e", ' +
    '"os-scan", "actionlint", "test"}\n');
  const problems = checkJobListConsistency({workflowText: mutated, requiredJobs: REQUIRED_JOBS});
  assert.ok(problems.length > 0);
});

test('missing ci-ready job throws (fail closed)', () => {
  const idx = ciText.indexOf('\n  ci-ready:');
  assert.ok(idx > -1);
  const mutated = ciText.slice(0, idx) + '\n';
  assert.throws(() => extractCiReady(mutated));
  assert.throws(() => checkJobListConsistency({workflowText: mutated, requiredJobs: REQUIRED_JOBS}));
});

test('missing needs line on ci-ready throws (fail closed)', () => {
  const mutated = mutate(ciText, NEEDS_LINE + '\n', '');
  assert.throws(() => extractCiReady(mutated));
});

test('missing Python required line throws (fail closed)', () => {
  const mutated = mutate(ciText, PYTHON_REQUIRED_LINE, '');
  assert.throws(() => extractCiReady(mutated));
});

test('duplicated Python required line throws (fail closed)', () => {
  const mutated = mutate(ciText, PYTHON_REQUIRED_LINE, PYTHON_REQUIRED_LINE + PYTHON_REQUIRED_LINE);
  assert.throws(() => extractCiReady(mutated));
});

test('a job with a block-form needs: throws rather than mis-parsing', () => {
  const mutated = mutate(ciText, NEEDS_LINE,
    '    needs:\n      - test\n      - lint\n      - docker\n      - secrets\n      - dependencies\n      ' +
    '- image-smoke\n      - browser-e2e\n      - os-scan\n      - actionlint');
  assert.throws(() => parseJobs(mutated));
});

test('parseJobs returns the real ci.yml job graph', () => {
  const jobs = parseJobs(ciText);
  const ids = jobs.map(j => j.id);
  assert.deepEqual(new Set(ids),
    new Set(['test', 'lint', 'docker', 'secrets', 'dependencies', 'image-smoke', 'browser-e2e', 'os-scan', 'actionlint', 'ci-ready']));
  assert.equal(jobs.find(j => j.id === 'ci-ready').name, 'CI ready');
  assert.deepEqual(jobs.find(j => j.id === 'docker').needs, ['test', 'lint']);
  assert.deepEqual(jobs.find(j => j.id === 'image-smoke').needs, ['docker']);
  assert.deepEqual(jobs.find(j => j.id === 'browser-e2e').needs, ['docker']);
  assert.deepEqual(jobs.find(j => j.id === 'os-scan').needs, ['docker']);
  assert.equal(jobs.find(j => j.id === 'actionlint').needs, null);
});

// preflight must filter triggers exactly like release, so a failed or
// cancelled CI run skips both jobs instead of failing preflight.
test('release.yml preflight and release if: are equal and non-null', () => {
  const preflightIf = extractJobIf(releaseText, 'preflight');
  const releaseIf = extractJobIf(releaseText, 'release');
  assert.ok(releaseIf, 'release job must have an if:');
  assert.ok(preflightIf, 'preflight job must have an if: matching release');
  assert.equal(preflightIf, releaseIf);
});

test('removing the conclusion check from preflight only breaks the if: equality', () => {
  const target = "       github.event.workflow_run.conclusion == 'success' &&\n";
  const mutated = mutate(releaseText, target, '');
  const preflightIf = extractJobIf(mutated, 'preflight');
  const releaseIf = extractJobIf(mutated, 'release');
  assert.notEqual(preflightIf, releaseIf);
});

// ACCEPT-03 (D-02): the no-skip detector proves no skip path exists for the
// jobs that back GitHub's required checks (CI ready via ci.yml, Review
// acceptance via review-acceptance.yml). Of the four classification
// fixtures below, three (ordinary-docs, sensitive-docs, misclassified) are
// proven here by test against the real workflow files, not by separate
// GitHub runs; the fourth real case is this phase's own PR (mixed docs +
// code + sensitive workflow changes).
describe('ACCEPT-03 no-skip detector', () => {
  const FIXTURES = Object.freeze([
    Object.freeze({
      name: 'ordinary-docs',
      claimedClass: 'ordinary-docs',
      files: ['docs/os-scan-policy.md', '.planning/STATE.md'],
      labels: [],
      title: 'docs: update roadmap',
    }),
    Object.freeze({
      name: 'sensitive-docs',
      claimedClass: 'sensitive',
      files: ['CLAUDE.md', '.github/workflows/ci.yml', '.planning/phases/85-x/85-01-PLAN.md'],
      labels: [],
      title: 'docs: workflow and agent-instruction changes',
    }),
    Object.freeze({
      name: 'mixed',
      claimedClass: 'code',
      files: ['docs/x.md', 'triggarr/config.py'],
      labels: [],
      title: 'feat: mixed docs and code change',
    }),
    Object.freeze({
      name: 'misclassified',
      claimedClass: 'ordinary-docs',
      files: ['docs/x.md', 'triggarr/engine.py'],
      labels: ['docs-only'],
      title: 'docs: typo',
    }),
  ]);

  test('findSkipConditions on real ci.yml returns no problems', () => {
    assert.deepEqual(
      findSkipConditions({workflowText: ciText, aggregateJobId: 'ci-ready', triggerContract: TRIGGER_CONTRACTS['ci.yml']}),
      []
    );
  });

  test('findSkipConditions on real review-acceptance.yml returns no problems', () => {
    assert.deepEqual(
      findSkipConditions({
        workflowText: acceptanceText,
        aggregateJobId: null,
        triggerContract: TRIGGER_CONTRACTS['review-acceptance.yml'],
      }),
      []
    );
  });

  test('findSkipConditions without a trigger contract throws (fail closed)', () => {
    assert.throws(
      () => findSkipConditions({workflowText: ciText, aggregateJobId: 'ci-ready'}),
      /trigger contract is required/
    );
  });

  test('removing the pull_request trigger from ci.yml fails on the specific reason', () => {
    const mutated = mutate(ciText, '  pull_request:\n    branches: [main]\n', '');
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('on.pull_request is required')));
  });

  test('removing the push trigger from ci.yml fails on the specific reason', () => {
    const mutated = mutate(ciText, '  push:\n    branches: [main]\n', '');
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('on.push is required')));
  });

  test('narrowing ci.yml pull_request branches fails on the specific reason', () => {
    const mutated = mutate(ciText, '  pull_request:\n    branches: [main]', '  pull_request:\n    branches: [release]');
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('on.pull_request.branches must be exactly [main]')));
  });

  test('widening ci.yml push branches fails on the specific reason', () => {
    const mutated = mutate(ciText, '  push:\n    branches: [main]', "  push:\n    branches: [main, 'feature/**']");
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('on.push.branches must be exactly [main]')));
  });

  test('removing ready_for_review from review-acceptance.yml types fails on the specific reason', () => {
    const mutated = mutate(acceptanceText, ', ready_for_review]', ']');
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: null,
      triggerContract: TRIGGER_CONTRACTS['review-acceptance.yml'],
    });
    assert.ok(problems.some(p => p.includes('on.pull_request.types omits ready_for_review')));
  });

  test('renaming review-acceptance.yml pull_request to pull_request_target fails on both specific reasons', () => {
    const mutated = mutate(acceptanceText, '  pull_request:', '  pull_request_target:');
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: null,
      triggerContract: TRIGGER_CONTRACTS['review-acceptance.yml'],
    });
    assert.ok(problems.some(p => p.includes('on.pull_request is required')));
    assert.ok(problems.some(p => p.includes('unsupported trigger "pull_request_target"')));
  });

  test('a sequence-form on: fails on unsupported trigger syntax', () => {
    const mutated = mutate(
      ciText,
      'on:\n  push:\n    branches: [main]\n  pull_request:\n    branches: [main]\n',
      'on: [push, pull_request]\n'
    );
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('unsupported trigger syntax')));
  });

  test('a flow-mapping trigger value fails on unsupported trigger syntax', () => {
    const mutated = mutate(ciText, '  pull_request:\n    branches: [main]', '  pull_request: {branches: [main]}');
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('unsupported trigger syntax')));
  });

  test('an unknown key under on.pull_request fails on the specific reason', () => {
    const mutated = mutate(
      ciText,
      '  pull_request:\n    branches: [main]\n',
      '  pull_request:\n    branches: [main]\n    branch: [main]\n'
    );
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('unsupported key "branch" under on.pull_request')));
  });

  test("requiredJobsFor derives ci-ready's run set from the file for every fixture", () => {
    const aggregate = extractCiReady(ciText);
    const expectedRuns = new Set([...aggregate.needs, 'ci-ready']);
    for (const fixture of FIXTURES) {
      const result = requiredJobsFor({workflowText: ciText, change: fixture});
      assert.deepEqual(new Set(result.runs), expectedRuns, `fixture ${fixture.name}`);
      assert.deepEqual(result.skippable, [], `fixture ${fixture.name}`);
    }
  });

  test('a pull_request paths-ignore filter fails and makes every job skippable for ordinary-docs', () => {
    const mutated = mutate(
      ciText,
      '  pull_request:\n    branches: [main]\n',
      "  pull_request:\n    branches: [main]\n    paths-ignore: ['**/*.md', 'docs/**']\n"
    );
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('on.pull_request.paths-ignore')));

    const ordinaryDocs = FIXTURES.find(f => f.name === 'ordinary-docs');
    const result = requiredJobsFor({workflowText: mutated, change: ordinaryDocs});
    const aggregate = extractCiReady(ciText);
    for (const id of [...aggregate.needs, 'ci-ready']) {
      assert.ok(result.skippable.includes(id), `expected "${id}" to be skippable`);
    }
  });

  test('a push paths filter fails on the specific reason', () => {
    const mutated = mutate(
      ciText,
      '  push:\n    branches: [main]\n',
      "  push:\n    branches: [main]\n    paths: ['triggarr/**']\n"
    );
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('on.push.paths')));
  });

  test('a pull_request branches-ignore filter fails on the specific reason', () => {
    const mutated = mutate(
      ciText,
      '  pull_request:\n    branches: [main]\n',
      '  pull_request:\n    branches: [main]\n    branches-ignore: [release]\n'
    );
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('on.pull_request.branches-ignore')));
  });

  test('a narrowed pull_request types list fails on the specific missing type', () => {
    const mutated = mutate(
      ciText,
      '  pull_request:\n    branches: [main]\n',
      '  pull_request:\n    branches: [main]\n    types: [opened]\n'
    );
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('on.pull_request.types omits synchronize')));
  });

  test('a job-level if: on the test job fails and marks it skippable', () => {
    const mutated = mutate(
      ciText,
      '  test:\n    timeout-minutes: 20\n    runs-on: ubuntu-latest\n',
      "  test:\n    timeout-minutes: 20\n    if: ${{ !contains(github.event.pull_request.labels.*.name, 'docs-only') }}\n    runs-on: ubuntu-latest\n"
    );
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('required job "test" has a job-level if:')));

    const misclassified = FIXTURES.find(f => f.name === 'misclassified');
    const result = requiredJobsFor({workflowText: mutated, change: misclassified});
    assert.ok(result.skippable.includes('test'));
  });

  test('job-level continue-on-error on the lint job fails on the specific reason', () => {
    const mutated = mutate(
      ciText,
      '  lint:\n    timeout-minutes: 20\n    runs-on: ubuntu-latest\n',
      '  lint:\n    timeout-minutes: 20\n    runs-on: ubuntu-latest\n    continue-on-error: true\n'
    );
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('required job "lint" sets continue-on-error')));
  });

  test('step-level continue-on-error on a lint job step fails on the specific reason', () => {
    const mutated = mutate(
      ciText,
      '      - name: Run ruff\n        run: uv run --no-sync ruff check triggarr/ tests/\n',
      '      - name: Run ruff\n        run: uv run --no-sync ruff check triggarr/ tests/\n        continue-on-error: true\n'
    );
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('required job "lint" sets continue-on-error')));
  });

  test('(checker B11) job-level continue-on-error on ci-ready fails as an aggregate problem', () => {
    const mutated = mutate(
      ciText,
      '  ci-ready:\n    name: CI ready\n    if: always()\n',
      '  ci-ready:\n    name: CI ready\n    if: always()\n    continue-on-error: true\n'
    );
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('aggregate job "ci-ready" sets continue-on-error')));
  });

  test("(checker B11) step-level continue-on-error on ci-ready's validation step fails as an aggregate problem", () => {
    const mutated = mutate(
      ciText,
      '      - name: Require every mandatory job to succeed\n        env:\n',
      '      - name: Require every mandatory job to succeed\n        continue-on-error: true\n        env:\n'
    );
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('aggregate job "ci-ready" sets continue-on-error')));
  });

  test("expression-form continue-on-error on ci-ready's validation step fails the same way", () => {
    const mutated = mutate(
      ciText,
      '      - name: Require every mandatory job to succeed\n        env:\n',
      '      - name: Require every mandatory job to succeed\n        continue-on-error: ${{ true }}\n        env:\n'
    );
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('aggregate job "ci-ready" sets continue-on-error')));
  });

  test('(checker B11) aggregateCanPassWith is false for the real ci-ready and true once a continue-on-error escape exists', () => {
    assert.equal(aggregateCanPassWith({workflowText: ciText, aggregateJobId: 'ci-ready', failedNeeds: ['test']}), false);

    const stepMutated = mutate(
      ciText,
      '      - name: Require every mandatory job to succeed\n        env:\n',
      '      - name: Require every mandatory job to succeed\n        continue-on-error: true\n        env:\n'
    );
    assert.equal(
      aggregateCanPassWith({workflowText: stepMutated, aggregateJobId: 'ci-ready', failedNeeds: ['test']}),
      true
    );
    assert.ok(
      findSkipConditions({
        workflowText: stepMutated,
        aggregateJobId: 'ci-ready',
        triggerContract: TRIGGER_CONTRACTS['ci.yml'],
      }).some(p => p.includes('aggregate job "ci-ready" sets continue-on-error'))
    );

    const jobMutated = mutate(
      ciText,
      '  ci-ready:\n    name: CI ready\n    if: always()\n',
      '  ci-ready:\n    name: CI ready\n    if: always()\n    continue-on-error: true\n'
    );
    assert.equal(
      aggregateCanPassWith({workflowText: jobMutated, aggregateJobId: 'ci-ready', failedNeeds: ['test']}),
      true
    );
  });

  test('a step-level continue-on-error in any review-acceptance.yml job fails on the specific reason', () => {
    const mutated = mutate(
      acceptanceText,
      '      - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6\n        with:\n',
      '      - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6\n        continue-on-error: true\n        with:\n'
    );
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: null,
      triggerContract: TRIGGER_CONTRACTS['review-acceptance.yml'],
    });
    assert.ok(problems.some(p => p.includes('required job "acceptance" sets continue-on-error')));
  });

  test('a non-always() aggregate if: fails on the specific reason', () => {
    const mutated = mutate(
      ciText,
      '    name: CI ready\n    if: always()\n',
      '    name: CI ready\n    if: success()\n'
    );
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('aggregate job "ci-ready" if: must be exactly always()')));
  });

  test('a new unallowlisted step if: inside the docker job fails on the specific reason', () => {
    const mutated = mutate(
      ciText,
      '      - name: Set up Docker Buildx\n        uses: docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069 # v4\n',
      "      - name: Set up Docker Buildx\n        uses: docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069 # v4\n      - name: Check PR title\n        if: github.event.pull_request.title != 'docs'\n        run: echo noop\n"
    );
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('required job "docker" step if: not on the reviewed allowlist')));
  });

  test('changing the allowlisted always() condition text fails and names the step', () => {
    const mutated = mutate(
      ciText,
      '      - name: Upload test evidence\n        if: always()\n',
      '      - name: Upload test evidence\n        if: success()\n'
    );
    const problems = findSkipConditions({
      workflowText: mutated,
      aggregateJobId: 'ci-ready',
      triggerContract: TRIGGER_CONTRACTS['ci.yml'],
    });
    assert.ok(problems.some(p => p.includes('Upload test evidence')));
  });

  test('STEP_IF_ALLOWLIST pins exactly the two currently reviewed entries', () => {
    assert.deepEqual(new Set(Object.keys(STEP_IF_ALLOWLIST)), new Set([
      'test::Upload test evidence',
      'browser-e2e::Upload browser failure evidence',
    ]));
  });
});
