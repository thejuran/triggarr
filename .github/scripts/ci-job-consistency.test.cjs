const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {REQUIRED_JOBS} = require('./release-policy.cjs');
const {parseJobs, extractCiReady, checkJobListConsistency, extractJobIf} = require('./ci-job-consistency.cjs');

const ciPath = path.join(__dirname, '../workflows/ci.yml');
const releasePath = path.join(__dirname, '../workflows/release.yml');
const ciText = fs.readFileSync(ciPath, 'utf8');
const releaseText = fs.readFileSync(releasePath, 'utf8');

const NEEDS_LINE = '    needs: [test, lint, docker, secrets, dependencies, image-smoke, browser-e2e]';
const PYTHON_REQUIRED_LINE =
  '          required = {"test", "lint", "docker", "secrets", "dependencies", "image-smoke", "browser-e2e"}\n';

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
    '    needs: [test, lint, docker, secrets, dependencies, image-smoke, browser-e2e, extra]');
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
    '          required = {"test", "lint", "docker", "secrets", "dependencies", "image-smoke", "browser-e2e", "extra"}\n');
  const problems = checkJobListConsistency({workflowText: mutated, requiredJobs: REQUIRED_JOBS});
  assert.ok(problems.length > 0);
});

test('job removed from needs and Python set (REQUIRED_JOBS unchanged) breaks consistency', () => {
  let mutated = mutate(ciText, NEEDS_LINE, '    needs: [test, lint, docker, secrets, image-smoke, browser-e2e]');
  mutated = mutate(mutated, PYTHON_REQUIRED_LINE,
    '          required = {"test", "lint", "docker", "secrets", "image-smoke", "browser-e2e"}\n');
  const problems = checkJobListConsistency({workflowText: mutated, requiredJobs: REQUIRED_JOBS});
  assert.ok(problems.length > 0);
});

test('removing image-smoke from needs and the Python set (REQUIRED_JOBS unchanged) breaks consistency', () => {
  let mutated = mutate(ciText, NEEDS_LINE, '    needs: [test, lint, docker, secrets, dependencies, browser-e2e]');
  mutated = mutate(mutated, PYTHON_REQUIRED_LINE,
    '          required = {"test", "lint", "docker", "secrets", "dependencies", "browser-e2e"}\n');
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
    '    needs: [test, lint, docker, secrets, dependencies, image-smoke, browser-e2e, test]');
  const problems = checkJobListConsistency({workflowText: mutated, requiredJobs: REQUIRED_JOBS});
  assert.ok(problems.length > 0);
});

test('duplicate entry in the Python required set breaks consistency', () => {
  const mutated = mutate(ciText, PYTHON_REQUIRED_LINE,
    '          required = {"test", "lint", "docker", "secrets", "dependencies", "image-smoke", "browser-e2e", "test"}\n');
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
    '    needs:\n      - test\n      - lint\n      - docker\n      - secrets\n      - dependencies\n      - image-smoke\n      - browser-e2e');
  assert.throws(() => parseJobs(mutated));
});

test('parseJobs returns the real ci.yml job graph', () => {
  const jobs = parseJobs(ciText);
  const ids = jobs.map(j => j.id);
  assert.deepEqual(new Set(ids),
    new Set(['test', 'lint', 'docker', 'secrets', 'dependencies', 'image-smoke', 'browser-e2e', 'ci-ready']));
  assert.equal(jobs.find(j => j.id === 'ci-ready').name, 'CI ready');
  assert.deepEqual(jobs.find(j => j.id === 'docker').needs, ['test', 'lint']);
  assert.deepEqual(jobs.find(j => j.id === 'image-smoke').needs, ['docker']);
  assert.deepEqual(jobs.find(j => j.id === 'browser-e2e').needs, ['docker']);
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
