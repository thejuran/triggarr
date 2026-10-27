// Binds a coverage.xml report to the exact commit and CI run it was measured on, so a
// downloaded report can never be mistaken for another commit's evidence.
//
// On a `pull_request` trigger, GITHUB_SHA is GitHub's synthetic merge commit, not the
// PR head (research Pitfall 4) -- this script records both explicitly, and review
// evidence is always bound to the PR head, never the merge commit. A synthetic-merge
// report is accepted as evidence for the head only when the measured source
// (MEASURED_PATHS) is identical between the tested commit and the reviewed head -- a
// base-only change that altered measured files makes the merge report unusable for the
// head (B08).
//
// Coverage is evidence only: this script never compares anything against a percentage
// threshold or gate. vibe-check's test-sufficiency lane discovers coverage by the fixed
// filename `coverage.xml` in the worktree under review, so the reviewer must run `check`
// against the head before placing the file in the review worktree -- evidence is never
// added to a review that has already run.

const crypto = require('node:crypto');
const fs = require('node:fs');
const {execFileSync} = require('node:child_process');

const SHA_RE = /^[a-f0-9]{40}$/;

// The files whose content determines what coverage measures. Changing this list is a
// sensitive change: it redefines what "the reviewed head's measured source" means for
// every provenance record this script accepts.
const MEASURED_PATHS = ['triggarr', 'tests', 'pyproject.toml', 'uv.lock'];

function sha256(text) {
  return crypto.createHash('sha256').update(text, 'utf8').digest('hex');
}

function defaultGit(args) {
  return execFileSync('git', args, {encoding: 'utf8'}).trim();
}

// Returns {path: <tree-or-blob-sha>} for every MEASURED_PATHS entry at `sha`. Throws if
// any lookup fails -- an unreadable path is a hard failure, not a tolerated gap.
function measuredTreesAt(sha, git = defaultGit) {
  const trees = {};
  for (const p of MEASURED_PATHS) {
    let id;
    try {
      id = git(['rev-parse', `${sha}:${p}`]);
    } catch (err) {
      throw new Error(`Cannot read measured source "${p}" at ${sha}: ${err.message}`);
    }
    if (!id) {
      throw new Error(`Cannot read measured source "${p}" at ${sha}`);
    }
    trees[p] = id;
  }
  return trees;
}

function assertMeasuredTrees(measuredTrees) {
  if (!measuredTrees || typeof measuredTrees !== 'object') {
    throw new Error('measuredTrees is required');
  }
  for (const p of MEASURED_PATHS) {
    if (!measuredTrees[p]) {
      throw new Error(`measuredTrees is missing entry for "${p}"`);
    }
  }
}

function branchCoverageFrom(coverageText) {
  const match = /<coverage\b[^>]*\bbranches-valid="(\d+)"/.exec(coverageText || '');
  return Boolean(match && Number(match[1]) > 0);
}

function buildProvenance(env, {coverageText, testExit, testSeconds, measuredTrees, now = () => new Date()}) {
  const eventName = env.GITHUB_EVENT_NAME;
  const sha = env.GITHUB_SHA;
  const runId = env.GITHUB_RUN_ID;
  const runAttempt = env.GITHUB_RUN_ATTEMPT;
  const workflow = env.GITHUB_WORKFLOW;
  const repository = env.GITHUB_REPOSITORY;

  if (!sha) throw new Error('GITHUB_SHA is required');
  if (!runId) throw new Error('GITHUB_RUN_ID is required');
  if (!SHA_RE.test(sha)) throw new Error(`GITHUB_SHA is not a 40-hex commit sha: ${JSON.stringify(sha)}`);
  assertMeasuredTrees(measuredTrees);

  const isPullRequest = eventName === 'pull_request';
  let prHeadSha = null;
  let prBaseSha = null;
  let reconciliation;

  if (isPullRequest) {
    prHeadSha = env.PR_HEAD_SHA || null;
    prBaseSha = env.PR_BASE_SHA || null;
    if (!prHeadSha || !SHA_RE.test(prHeadSha)) {
      throw new Error(
        `PR_HEAD_SHA is required and must be a 40-hex commit sha on a pull_request event: ${JSON.stringify(prHeadSha)}`
      );
    }
    if (prBaseSha && !SHA_RE.test(prBaseSha)) {
      throw new Error(`PR_BASE_SHA is not a 40-hex commit sha: ${JSON.stringify(prBaseSha)}`);
    }
    reconciliation = "tested_sha is GitHub's synthetic merge of pr_head_sha into pr_base_sha; review evidence binds to pr_head_sha";
  } else {
    reconciliation = 'tested_sha is the pushed commit';
  }

  return {
    schema: 1,
    event_name: eventName,
    pr_head_sha: prHeadSha,
    pr_base_sha: prBaseSha,
    tested_sha: sha,
    tested_sha_kind: isPullRequest ? 'pull-request-synthetic-merge' : 'push-head',
    run_id: runId,
    run_attempt: runAttempt,
    workflow,
    repository,
    test_exit_code: testExit,
    test_seconds: testSeconds,
    coverage_file: 'coverage.xml',
    coverage_sha256: sha256(coverageText),
    branch_coverage: branchCoverageFrom(coverageText),
    generated_at: now().toISOString(),
    measured_trees: {...measuredTrees},
    reconciliation,
  };
}

function buildLocalProvenance({head, coverageText, testExit, testSeconds, measuredTrees, now = () => new Date()}) {
  if (!head || !SHA_RE.test(head)) {
    throw new Error(`head is required and must be a 40-hex commit sha: ${JSON.stringify(head)}`);
  }
  assertMeasuredTrees(measuredTrees);
  return {
    schema: 1,
    event_name: 'local',
    pr_head_sha: null,
    pr_base_sha: null,
    tested_sha: head,
    tested_sha_kind: 'local-exact-head',
    run_id: null,
    run_attempt: null,
    workflow: 'local',
    repository: null,
    test_exit_code: testExit,
    test_seconds: testSeconds,
    coverage_file: 'coverage.xml',
    coverage_sha256: sha256(coverageText),
    branch_coverage: branchCoverageFrom(coverageText),
    generated_at: now().toISOString(),
    measured_trees: {...measuredTrees},
    reconciliation: 'tested_sha is the reviewed head itself, measured on a clean local checkout',
  };
}

// Accepts either a parsed provenance object or the raw JSON text read from disk.
// Unparseable text and a schema other than 1 are both treated as a malformed
// provenance record: this script refuses to interpret it rather than guess.
function parseProvenance(input) {
  let obj = input;
  if (typeof input === 'string') {
    try {
      obj = JSON.parse(input);
    } catch (err) {
      throw new Error(`Coverage evidence rejected: provenance is not valid JSON (${err.message})`);
    }
  }
  if (!obj || typeof obj !== 'object' || obj.schema !== 1) {
    throw new Error(`Coverage evidence rejected: provenance schema is not 1 (got ${JSON.stringify(obj && obj.schema)})`);
  }
  return obj;
}

// Returns an array of human-readable problem strings (empty = evidence accepted).
// For every tested_sha_kind this compares headTrees against provenance.measured_trees
// path by path -- this is what makes a synthetic-merge report usable for the reviewed
// head only when the measured source is identical (B08).
function checkEvidence({provenance, coverageText, expectedHead, expectedRunId, headTrees}) {
  const parsed = parseProvenance(provenance);
  const problems = [];

  if (coverageText == null) {
    problems.push('coverage.xml is missing');
  } else {
    if (sha256(coverageText) !== parsed.coverage_sha256) {
      problems.push('coverage.xml does not match the provenance checksum');
    }
    if (!branchCoverageFrom(coverageText)) {
      problems.push('no branch coverage data');
    }
  }

  if (parsed.test_exit_code !== 0) {
    problems.push('tests failed in this run');
  }

  if (expectedRunId !== undefined && expectedRunId !== null && String(parsed.run_id) !== String(expectedRunId)) {
    problems.push('different CI run');
  }

  if (parsed.tested_sha_kind === 'pull-request-synthetic-merge') {
    if (expectedHead === parsed.tested_sha && expectedHead !== parsed.pr_head_sha) {
      problems.push(
        `wrong commit: expected head equals the PR's synthetic merge commit (${parsed.tested_sha}), not the PR head -- using the synthetic merge commit as PR head evidence is rejected`
      );
    } else if (expectedHead !== parsed.pr_head_sha) {
      problems.push(`wrong commit: provenance is for PR head ${parsed.pr_head_sha}, expected ${expectedHead}`);
    }
  } else if (expectedHead !== parsed.tested_sha) {
    problems.push(`wrong commit: provenance is for ${parsed.tested_sha}, expected ${expectedHead}`);
  }

  if (!headTrees) {
    problems.push("cannot read the reviewed head's measured source");
  } else {
    for (const p of MEASURED_PATHS) {
      if (headTrees[p] !== parsed.measured_trees[p]) {
        problems.push(`measured source differs between the tested commit and the reviewed head: ${p}`);
      }
    }
  }

  return problems;
}

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    if (token.startsWith('--')) {
      const key = token.slice(2);
      const next = argv[i + 1];
      if (next !== undefined && !next.startsWith('--')) {
        args[key] = next;
        i++;
      } else {
        args[key] = true;
      }
    }
  }
  return args;
}

function requireArg(args, name) {
  const value = args[name];
  if (value === undefined || value === true) {
    throw new Error(`--${name} is required`);
  }
  return value;
}

function defaultIo() {
  return {
    env: process.env,
    git: defaultGit,
    readFile: p => fs.readFileSync(p, 'utf8'),
    writeFile: (p, data) => fs.writeFileSync(p, data),
    log: (...args) => console.log(...args),
    error: (...args) => console.error(...args),
    now: () => new Date(),
  };
}

// `write` computes measured trees at HEAD after asserting HEAD equals GITHUB_SHA, and
// writes the provenance file even when tests failed so the failure is recorded as
// evidence -- the CI step invoking this itself re-asserts the test exit code, so this
// command always exits 0 on a successful write.
function cliWrite(args, io) {
  const coveragePath = requireArg(args, 'coverage');
  const testExit = Number(requireArg(args, 'test-exit'));
  const testSeconds = Number(requireArg(args, 'test-seconds'));
  const outPath = requireArg(args, 'out');

  const env = io.env;
  const head = io.git(['rev-parse', 'HEAD']);
  if (head !== env.GITHUB_SHA) {
    throw new Error(`HEAD (${head}) does not match GITHUB_SHA (${env.GITHUB_SHA}) -- refusing to measure trees for the wrong commit`);
  }
  const measuredTrees = measuredTreesAt('HEAD', io.git);
  const coverageText = io.readFile(coveragePath);
  const provenance = buildProvenance(env, {coverageText, testExit, testSeconds, measuredTrees, now: io.now});
  io.writeFile(outPath, JSON.stringify(provenance, null, 2));
  io.log(`Coverage provenance written to ${outPath} for ${provenance.tested_sha}`);
  return 0;
}

// `write-local` refuses unless the worktree is clean and HEAD is exactly --head, so a
// pre-push review can trust the measured trees came from the exact reviewed head (B09).
function cliWriteLocal(args, io) {
  const head = requireArg(args, 'head');
  const coveragePath = requireArg(args, 'coverage');
  const testExit = Number(requireArg(args, 'test-exit'));
  const testSeconds = Number(requireArg(args, 'test-seconds'));
  const outPath = requireArg(args, 'out');

  const status = io.git(['status', '--porcelain']);
  if (status) {
    throw new Error('worktree is not clean -- commit or discard changes before writing local coverage provenance');
  }
  const actualHead = io.git(['rev-parse', 'HEAD']);
  if (actualHead !== head) {
    throw new Error(`HEAD is not --head (HEAD is ${actualHead}, --head was ${head})`);
  }
  const measuredTrees = measuredTreesAt(head, io.git);
  const coverageText = io.readFile(coveragePath);
  const provenance = buildLocalProvenance({head, coverageText, testExit, testSeconds, measuredTrees, now: io.now});
  io.writeFile(outPath, JSON.stringify(provenance, null, 2));
  io.log(`Local coverage provenance written to ${outPath} for ${provenance.tested_sha}`);
  return 0;
}

// `check` computes headTrees at --expected-head through the injected git; an unreadable
// head is a problem reported by checkEvidence, never a silent pass.
function cliCheck(args, io) {
  const provenancePath = requireArg(args, 'provenance');
  const coveragePath = requireArg(args, 'coverage');
  const expectedHead = requireArg(args, 'expected-head');
  const expectedRunId = args['expected-run-id'];

  const provenanceText = io.readFile(provenancePath);

  let coverageText = null;
  try {
    coverageText = io.readFile(coveragePath);
  } catch {
    coverageText = null;
  }

  let headTrees = null;
  try {
    headTrees = measuredTreesAt(expectedHead, io.git);
  } catch {
    headTrees = null;
  }

  const problems = checkEvidence({provenance: provenanceText, coverageText, expectedHead, expectedRunId, headTrees});
  if (problems.length > 0) {
    for (const problem of problems) io.error(problem);
    return 1;
  }
  io.log(`Coverage evidence matches head ${expectedHead}`);
  return 0;
}

function runCli(argv, io = defaultIo()) {
  const [command, ...rest] = argv;
  const args = parseArgs(rest);

  try {
    if (command === 'write') return cliWrite(args, io);
    if (command === 'write-local') return cliWriteLocal(args, io);
    if (command === 'check') return cliCheck(args, io);
    io.error(`Unknown command "${command}". Expected one of: write, write-local, check.`);
    return 1;
  } catch (err) {
    io.error(err.message);
    return 1;
  }
}

if (require.main === module) {
  process.exitCode = runCli(process.argv.slice(2));
}

module.exports = {buildProvenance, buildLocalProvenance, checkEvidence, MEASURED_PATHS, runCli};
