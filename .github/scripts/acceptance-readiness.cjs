// Read-only: this file never writes a repository variable, never approves a
// deployment, and never marks a PR ready. It gathers an exact head's
// machine-checkable prerequisites, runs the real acceptance gate (assess())
// as a dry run, and prints a single ready/not-ready checklist (ACCEPT-01,
// D-20). Run it immediately before presenting a pending run to the owner and
// again right before submission (docs/owner-cli-acceptance.md steps 1 and 5).

const fs = require('node:fs');
const {execFileSync} = require('node:child_process');

const {assess} = require('./review-acceptance.cjs');
const {validateFallback} = require('./codex-fallback.cjs');

const REPO = 'thejuran/triggarr';
// Mirrors tests/codex_review_run.py TRUSTED_AUTHORS (owner decision 2026-10-22).
// Widening this set is a sensitive review-machinery change.
const TRUSTED_AUTHORS = Object.freeze(['thejuran']);

// Mirrors tests/codex_review_run.py AUDITED_INPUTS (a drift test pins the two).
// Readiness recomputes which of these changed in base..head itself rather than
// trusting the reviewed head's own runner to report it (D-18, WR-01).
const AUDITED_INPUTS = Object.freeze([
  'docs/codex-adversarial-review-contract.md',
  '.claude/schemas/codex-review-findings.schema.json',
  'tests/codex_report_status.py',
  'tests/codex_review_run.py',
]);

const PR_ARG_RE = /^[1-9][0-9]*$/;
const HEAD_RE = /^[0-9a-f]{40}$/;
const OUT_PATH_RE = /^\.planning\/phases\/[A-Za-z0-9._-]+\/codex\/[0-9a-f]{12}-[a-z0-9-]+-a[0-9]+$/;

function headTrustFor({isCrossRepository, author}) {
  const login = author?.login;
  const isBot = Boolean(author?.is_bot) || (typeof login === 'string' && login.endsWith('[bot]'));
  if (isCrossRepository || isBot || !TRUSTED_AUTHORS.includes(login)) return 'untrusted';
  return 'trusted';
}

// codexStatusFor implements the completeness contract shared with codex-fallback.cjs
// and Plan 85-13's runner: complete iff review_mode is "trusted-local-tests" AND
// the head-side checker says "complete" AND (no audited input changed in the diff,
// or the base checker also says "complete"). For an untrusted head this never
// reports complete; a record claiming complete is blocked outright. When
// incomplete, the single owner-approved-fallback validator decides whether the
// fallback satisfies the item -- never a local re-implementation of that rule.
// auditedChanged is readiness's own recomputation of the audited inputs changed
// in reviewedBase..head; it is unioned with the meta's claim so the head's runner
// can never talk the base cross-grade away. The meta must name this head and the
// reviewed base: the merge-base of the PR base and head (WR-01, iteration 2).
// That single rule covers both contract forms: a PR checkpoint's base must be an
// ancestor of the head, so it IS the merge-base, and a local phase checkpoint
// uses `git merge-base origin/main HEAD`, which stays the merge-base after main
// moves on. A PR base that is not an ancestor of the head is never accepted,
// since no runner reviews that range. Without a reviewedBase (direct callers)
// the PR base itself is required, which is the stricter pre-existing rule.
// `base` stays the PR base for the fallback validator.
function codexStatusFor({
  status, baseStatus, meta, auditedChanged: recomputed, out, head, base, reviewedBase, pr, prAuthor, headTrust, fallback,
}) {
  if (!meta || meta.head !== head) {
    return {ok: false, detail: 'Codex evidence is for a different head'};
  }
  const expectedBase = reviewedBase === undefined ? base : reviewedBase;
  if (!HEAD_RE.test(expectedBase || '') || meta.base !== expectedBase) {
    return {ok: false, detail: 'Codex evidence is for a different base'};
  }

  const claimed = Array.isArray(meta.audited_inputs_changed_in_diff) ? meta.audited_inputs_changed_in_diff : [];
  const auditedChanged = [...new Set([...claimed, ...(Array.isArray(recomputed) ? recomputed : [])])];
  const baseRequired = auditedChanged.length > 0;
  const claimsComplete = meta?.review_mode === 'trusted-local-tests' && status?.status === 'complete';

  if (headTrust === 'untrusted' && claimsComplete) {
    return {ok: false, detail: 'Codex evidence claims complete for an untrusted head; untrusted runs are refused until Phase 85.1'};
  }

  // A checker verdict counts only for the commits it graded (WR-02, iteration
  // 2): the inspected head and base it reports must be this head and the
  // reviewed base, for the head-side status and for any required base grade.
  const boundHere = graded => graded?.inspected_head === head && graded?.inspected_base === meta.base;
  if (status?.status === 'complete' && !boundHere(status)) {
    return {ok: false, detail: 'Codex status file is not bound to this head and base (inspected_head/inspected_base differ)'};
  }
  if (claimsComplete && baseRequired && baseStatus?.status === 'complete' && !boundHere(baseStatus)) {
    return {
      ok: false,
      detail: 'grader changed in this diff: the base checker status is not bound to this head and base (inspected_head/inspected_base differ)',
    };
  }
  const baseOk = !baseRequired || baseStatus?.status === 'complete';
  const headSideComplete = claimsComplete;

  if (headTrust === 'trusted' && headSideComplete && !baseOk) {
    return {ok: false, detail: "grader changed in this diff: the base commit's checker did not confirm completeness"};
  }

  const complete = headTrust === 'trusted' && headSideComplete && baseOk;
  if (complete) {
    return {ok: true, detail: 'complete'};
  }

  const codexStatus = {complete: false, attempt: meta?.attempt, out, reviewMode: meta?.review_mode};

  if (!fallback) {
    if (headTrust === 'untrusted') {
      return {ok: false, detail: 'untrusted head (bot/fork): Codex review is refused until Phase 85.1; an owner-approved fallback (D-16) is required'};
    }
    return {ok: false, detail: 'INCOMPLETE/PENDING: no recorded fallback; wait or retry later blocks acceptance'};
  }

  const {ok, reasons} = validateFallback(fallback, {pr, head, base, prAuthor, headTrust, codexStatus});
  if (!ok) {
    return {ok: false, detail: reasons.join('; ')};
  }
  if (headTrust === 'untrusted') {
    return {ok: true, detail: `ok (owner-approved fallback for untrusted head: ${fallback.reviewer?.name}; isolated review is Phase 85.1)`};
  }
  return {ok: true, detail: `ok (owner-approved fallback: ${fallback.reviewer?.name})`};
}

function latestCheck(checks, head, name) {
  return (checks || [])
    .filter(c => c.head_sha === head && c.name === name)
    .sort((a, b) => (b.id || 0) - (a.id || 0))[0];
}

function isSuccessful(check) {
  return Boolean(check) && check.status === 'completed' && check.conclusion === 'success';
}

function ciReadyItem(checks, head) {
  const latest = latestCheck(checks, head, 'CI ready');
  if (!isSuccessful(latest)) {
    return {name: 'CI ready', status: 'blocked', detail: 'no successful "CI ready" check run for this head'};
  }
  return {name: 'CI ready', status: 'ok', detail: 'success'};
}

function codeQlItem(checks, head) {
  let latest = latestCheck(checks, head, 'CodeQL');
  if (!latest) {
    latest = (checks || [])
      .filter(c => c.head_sha === head && c.app?.slug === 'github-advanced-security' && /^(Analyze|CodeQL)/.test(c.name || ''))
      .sort((a, b) => (b.id || 0) - (a.id || 0))[0];
  }
  if (!isSuccessful(latest)) {
    return {name: 'CodeQL', status: 'blocked', detail: 'no successful CodeQL check run for this head'};
  }
  return {name: 'CodeQL', status: 'ok', detail: `success (${latest.name})`};
}

function greptileItem(checks, head) {
  const latest = (checks || [])
    .filter(c => c.head_sha === head && c.name === 'Greptile Review' && c.app?.id === 867647)
    .sort((a, b) => (b.id || 0) - (a.id || 0))[0];
  if (!latest) {
    return {name: 'Greptile (optional)', status: 'ok', detail: 'did not run on this head (optional)'};
  }
  const resolved = latest.status === 'completed' ? latest.conclusion : latest.status;
  return {name: 'Greptile (optional)', status: 'ok', detail: `${resolved} (optional; the acceptance gate still requires success if present)`};
}

function gateItem({pr, draft, head, checks, comments, dispositions, blockers}) {
  try {
    const {findings} = assess({
      prNumber: pr, head, currentHead: head, draft,
      checks: checks || [], comments: comments || [], dispositions, blockers,
    });
    return {name: 'Review acceptance gate (dry run)', status: 'ok', detail: `${findings} Greptile findings disposed`};
  } catch (err) {
    return {name: 'Review acceptance gate (dry run)', status: 'blocked', detail: err.message};
  }
}

// readiness(input) -> {ready, pr, head, base, items}
function readiness(input) {
  const {
    pr, prAuthor, prAuthorIsBot, isCrossRepository, draft, open,
    head, baseSha, mergeBase, checks, comments, checksError, commentsError,
    dispositions, blockers, codex = {}, fallback,
  } = input;

  const items = [];

  items.push(open === false
    ? {name: 'PR open', status: 'blocked', detail: 'PR is not open'}
    : {name: 'PR open', status: 'ok', detail: 'open'});

  items.push(draft === true
    ? {name: 'PR ready for review', status: 'blocked', detail: 'mark the PR ready for review before requesting approval'}
    : {name: 'PR ready for review', status: 'ok', detail: 'not a draft'});

  items.push(HEAD_RE.test(head || '')
    ? {name: 'Head SHA', status: 'ok', detail: head}
    : {name: 'Head SHA', status: 'blocked', detail: 'invalid head SHA (expected 40 hex characters)'});

  if (checksError) {
    items.push({name: 'CI ready', status: 'blocked', detail: checksError});
    items.push({name: 'CodeQL', status: 'blocked', detail: checksError});
  } else {
    items.push(ciReadyItem(checks, head));
    items.push(codeQlItem(checks, head));
  }

  items.push(greptileItem(checksError ? [] : checks, head));

  if (commentsError) {
    items.push({name: 'Review acceptance gate (dry run)', status: 'blocked', detail: commentsError});
  } else {
    items.push(gateItem({pr, draft, head, checks, comments, dispositions, blockers}));
  }

  const headTrust = headTrustFor({isCrossRepository, author: {login: prAuthor, is_bot: prAuthorIsBot}});
  const codexResult = codexStatusFor({...codex, head, base: baseSha, reviewedBase: mergeBase, pr, prAuthor, headTrust, fallback});
  items.push({name: 'Codex', status: codexResult.ok ? 'ok' : 'blocked', detail: codexResult.detail});

  const ready = items.every(i => i.status === 'ok');
  return {ready, pr, head, base: baseSha, reviewedBase: mergeBase, items};
}

// renderChecklist(result) -> the D-12 owner-acceptance checklist text, extended
// with this plan's machine-checkable items. BM's own result is not
// machine-readable, so that line stays a fill-in.
function renderChecklist(result) {
  const lines = [];
  lines.push(`Repository: ${REPO}`);
  lines.push(`PR: #${result.pr}`);
  lines.push(`Full head SHA: ${result.head}`);
  lines.push(`Full base SHA: ${result.base}`);
  if (result.reviewedBase !== undefined) {
    lines.push(`Reviewed base SHA (merge-base): ${result.reviewedBase}`);
  }
  lines.push('');
  lines.push('Review status on this head:');
  lines.push('- BM: <fill from the checkpoint record>');
  for (const item of result.items) {
    lines.push(`- ${item.name}: ${item.status === 'ok' ? 'ok' : 'BLOCKED'} — ${item.detail}`);
  }
  lines.push('');
  lines.push(result.ready ? 'Ready to request approval' : 'NOT ready: fix the blocked items before presenting the pending run');
  return lines.join('\n');
}

// flattenPages(text, kind): parses one --paginate --slurp JSON document (an
// array of pages) and concatenates it into a flat array. Throws (fail closed)
// on anything that is not the expected shape -- a non-array top level, or,
// for 'check-runs', a page without its own check_runs array.
function flattenPages(text, kind) {
  const errorMessage = kind === 'check-runs' ? 'could not read GitHub check runs' : 'could not read PR comments';
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error(errorMessage);
  }
  if (!Array.isArray(parsed)) throw new Error(errorMessage);

  const flat = [];
  if (kind === 'check-runs') {
    for (const page of parsed) {
      if (!page || !Array.isArray(page.check_runs)) throw new Error(errorMessage);
      flat.push(...page.check_runs);
    }
    return flat;
  }
  if (kind === 'comments') {
    for (const page of parsed) {
      if (!Array.isArray(page)) throw new Error(errorMessage);
      flat.push(...page);
    }
    return flat;
  }
  throw new Error(`unknown flattenPages kind: ${kind}`);
}

function parseCliArgs(argv) {
  const opts = {};
  for (let i = 0; i < argv.length; i++) {
    switch (argv[i]) {
      case '--pr':
        opts.prRaw = argv[++i];
        break;
      case '--codex-out':
        opts.codexOut = argv[++i];
        break;
      case '--fallback':
        opts.fallback = argv[++i];
        break;
      default:
        throw new Error(`unknown argument: ${argv[i]}`);
    }
  }
  if (!PR_ARG_RE.test(opts.prRaw || '')) {
    throw new Error(`invalid --pr: ${JSON.stringify(opts.prRaw)} (expected a positive integer)`);
  }
  opts.pr = Number(opts.prRaw);
  if (!OUT_PATH_RE.test(opts.codexOut || '')) {
    throw new Error(`invalid --codex-out: ${JSON.stringify(opts.codexOut)}`);
  }
  return opts;
}

function readJsonOrThrow(readFile, path, label) {
  let text;
  try {
    text = readFile(path);
  } catch (err) {
    throw new Error(`could not read ${label} (${path}): ${err.message}`);
  }
  try {
    return JSON.parse(text);
  } catch (err) {
    throw new Error(`could not parse ${label} as JSON (${path}): ${err.message}`);
  }
}

function readJsonIfPresent(readFile, path) {
  let text;
  try {
    text = readFile(path);
  } catch {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

// runCli(argv, {exec, readFile}): read-only. --pr and --codex-out are
// validated before any exec/readFile call. exec defaults to
// node:child_process's execFileSync (argument arrays only, never a shell
// string); readFile defaults to node:fs's readFileSync. Exits 0 when ready,
// 1 when not ready (or when GitHub/Codex evidence cannot be read), 2 on a
// usage error.
function runCli(argv, {exec, readFile} = {}) {
  const execFn = exec || ((cmd, args) => execFileSync(cmd, args, {encoding: 'utf8'}));
  const readFileFn = readFile || (path => fs.readFileSync(path, 'utf8'));

  let opts;
  try {
    opts = parseCliArgs(argv);
  } catch (err) {
    console.error(err.message);
    return 2;
  }

  let prInfo;
  try {
    const prText = execFn('gh', [
      'pr', 'view', String(opts.pr), '--repo', REPO, '--json',
      'number,state,isDraft,headRefOid,baseRefOid,author,isCrossRepository',
    ]);
    prInfo = JSON.parse(prText);
  } catch (err) {
    console.error(`could not read PR state: ${err.message}`);
    return 1;
  }

  const head = prInfo.headRefOid;
  const base = prInfo.baseRefOid;

  let checks = [];
  let checksError = null;
  try {
    const checksText = execFn('gh', ['api', `repos/${REPO}/commits/${head}/check-runs`, '--paginate', '--slurp']);
    checks = flattenPages(checksText, 'check-runs');
  } catch (err) {
    checksError = err.message;
  }

  let comments = [];
  let commentsError = null;
  try {
    const commentsText = execFn('gh', ['api', `repos/${REPO}/pulls/${opts.pr}/comments`, '--paginate', '--slurp']);
    comments = flattenPages(commentsText, 'comments');
  } catch (err) {
    commentsError = err.message;
  }

  let dispositions;
  let blockers;
  try {
    dispositions = JSON.parse(execFn('gh', ['variable', 'get', 'REVIEW_DISPOSITIONS']));
    blockers = JSON.parse(execFn('gh', ['variable', 'get', 'REVIEW_BLOCKERS']));
  } catch (err) {
    console.error(`could not read the acceptance register: ${err.message}`);
    return 1;
  }

  let status;
  let meta;
  try {
    status = readJsonOrThrow(readFileFn, `${opts.codexOut}.status.json`, 'Codex status file');
    meta = readJsonOrThrow(readFileFn, `${opts.codexOut}.meta.json`, 'Codex meta file');
  } catch (err) {
    console.error(err.message);
    return 1;
  }
  const baseStatus = readJsonIfPresent(readFileFn, `${opts.codexOut}.base-status.json`);

  // Recompute the reviewed base and the audited-input change set from git
  // itself (argument arrays, no shell); fail closed when either cannot be
  // computed (e.g. commits not fetched). The reviewed range is
  // merge-base..head, the PR's own changes, so audited inputs changed only on
  // the base branch after the fork point are not counted (WR-01, iteration 2).
  if (!HEAD_RE.test(head || '') || !HEAD_RE.test(base || '')) {
    console.error('could not compute audited-input changes: PR head/base is not a 40-hex commit SHA');
    return 1;
  }
  let mergeBase;
  try {
    mergeBase = String(execFn('git', ['merge-base', base, head])).trim();
  } catch (err) {
    console.error(`could not compute the merge-base (git merge-base ${base} ${head}): ${err.message}`);
    return 1;
  }
  if (!HEAD_RE.test(mergeBase)) {
    console.error(`could not compute the merge-base (git merge-base ${base} ${head}): not a 40-hex commit SHA`);
    return 1;
  }
  let auditedChanged;
  try {
    const diffText = execFn('git', ['diff', '--name-only', `${mergeBase}..${head}`, '--', ...AUDITED_INPUTS]);
    auditedChanged = String(diffText).split('\n').map(line => line.trim()).filter(Boolean);
  } catch (err) {
    console.error(`could not compute audited-input changes (git diff ${mergeBase}..${head}): ${err.message}`);
    return 1;
  }

  let fallback = null;
  if (opts.fallback) {
    try {
      fallback = readJsonOrThrow(readFileFn, opts.fallback, 'fallback record');
    } catch (err) {
      console.error(err.message);
      return 1;
    }
  }

  const result = readiness({
    pr: opts.pr,
    prAuthor: prInfo.author?.login,
    prAuthorIsBot: Boolean(prInfo.author?.is_bot),
    isCrossRepository: Boolean(prInfo.isCrossRepository),
    draft: Boolean(prInfo.isDraft),
    open: prInfo.state === 'OPEN',
    head,
    baseSha: base,
    mergeBase,
    checks,
    comments,
    checksError,
    commentsError,
    dispositions,
    blockers,
    codex: {status, baseStatus, meta, auditedChanged, out: opts.codexOut},
    fallback,
  });

  console.log(renderChecklist(result));
  return result.ready ? 0 : 1;
}

if (require.main === module) {
  process.exitCode = runCli(process.argv.slice(2));
}

module.exports = {readiness, renderChecklist, codexStatusFor, headTrustFor, runCli, AUDITED_INPUTS};
