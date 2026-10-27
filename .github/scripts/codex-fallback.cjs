// This file is the single definition of an owner-approved fallback (D-16).
// docs/codex-adversarial-review-contract.md and docs/review-checkpoint-record.md
// describe it and must name these fields; changing it is a sensitive change.
//
// Node stdlib only -- no YAML library, no new dependency. Fail-closed throughout:
// a record that is structurally wrong, scoped to the wrong head/base, incomplete,
// reviewed by a non-independent reviewer, or missing an explicit approve-fallback
// decision naming the head is never ok.

const fs = require('node:fs');

const FALLBACK_SCHEMA_VERSION = 1;
const FALLBACK_FIELDS = Object.freeze([
  'schema', 'pr', 'head', 'base', 'codex_out', 'reviewer', 'scope', 'result', 'owner_decision',
]);
const REVIEWER_KINDS = Object.freeze(['vibe-check-deep-review', 'manual-codex-inspection-session', 'other-independent']);
const DISALLOWED_REVIEWERS = Object.freeze(['bm', 'bm code review', 'buildomator', 'claude', 'gsd-code-reviewer', 'codex_review_run']);
// WR-03 (iteration 2): BM, its agents (bm-code-reviewer, gsd-*), Claude and the
// Codex runner are never independent, however the name is spelled. The name is
// lowercased and split on every non-alphanumeric run; a name is rejected when
// any of these tokens appears, or the runner's token sequence appears.
const DISALLOWED_REVIEWER_TOKENS = Object.freeze(['bm', 'buildomator', 'gsd', 'claude']);
const DISALLOWED_REVIEWER_TOKEN_SEQUENCES = Object.freeze([Object.freeze(['codex', 'review', 'run'])]);
const OWNER_DECISIONS = Object.freeze(['approve-fallback', 'wait', 'retry-later']);

const REVIEWER_FIELDS = ['name', 'kind'];
const SCOPE_FIELDS = ['base', 'head', 'diff'];
const RESULT_FIELDS = ['status', 'summary', 'findings'];
const FINDING_FIELDS = ['id', 'severity', 'disposition', 'note'];
const OWNER_DECISION_FIELDS = ['decision', 'verbatim', 'decided_at'];
const FINDING_DISPOSITIONS = ['fixed', 'accepted', 'rejected', 'deferred'];

const ISO_8601_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;
const HEAD_RE = /^[0-9a-f]{40}$/;
const PR_ARG_RE = /^[1-9][0-9]*$/;
// Same OUT path shape used by the acceptance-readiness CLI's --codex-out.
const OUT_PATH_RE = /^\.planning\/phases\/[A-Za-z0-9._-]+\/codex\/[0-9a-f]{12}-[a-z0-9-]+-a[0-9]+$/;

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function unknownFieldProblems(obj, allowed, pathPrefix) {
  if (!isPlainObject(obj)) return [];
  return Object.keys(obj)
    .filter(key => !allowed.includes(key))
    .map(key => `unknown field ${pathPrefix ? `${pathPrefix}.${key}` : key}`);
}

// Reports each required nested field that is absent. A non-object parent is
// reported separately ("<x> must be an object"), so it is skipped here.
function missingNestedFields(obj, fields, pathPrefix) {
  if (!isPlainObject(obj)) return [];
  return fields
    .filter(field => !Object.hasOwn(obj, field))
    .map(field => `missing required field ${pathPrefix}.${field}`);
}

function reviewerNameIsDisallowed(name) {
  const lowered = name.trim().toLowerCase();
  if (DISALLOWED_REVIEWERS.includes(lowered)) return true;
  const tokens = lowered.split(/[^a-z0-9]+/).filter(Boolean);
  if (tokens.some(token => DISALLOWED_REVIEWER_TOKENS.includes(token))) return true;
  return DISALLOWED_REVIEWER_TOKEN_SEQUENCES.some(sequence =>
    tokens.some((_, start) => sequence.every((token, offset) => tokens[start + offset] === token))
  );
}

function basename(path) {
  const str = typeof path === 'string' ? path : '';
  const idx = str.lastIndexOf('/');
  return idx === -1 ? str : str.slice(idx + 1);
}

// validateFallback(record, context) -> {ok, reasons}
// context: {pr, head, base, prAuthor, headTrust: 'trusted'|'untrusted',
//           codexStatus: {complete, attempt, out, reviewMode}}
// `base` is the reviewed base: the base the Codex evidence records (the
// merge-base of the PR base and head), never a newer PR base (WR-02, iteration 3).
function validateFallback(record, context = {}) {
  const {pr, head, base, prAuthor, headTrust, codexStatus} = context;
  const reasons = [];

  if (!isPlainObject(record)) {
    return {ok: false, reasons: ['fallback record must be an object']};
  }

  for (const name of FALLBACK_FIELDS) {
    if (!Object.hasOwn(record, name)) reasons.push(`missing required field ${name}`);
  }
  reasons.push(...unknownFieldProblems(record, FALLBACK_FIELDS, ''));

  if (Object.hasOwn(record, 'schema') && record.schema !== FALLBACK_SCHEMA_VERSION) {
    reasons.push('unsupported fallback schema');
  }

  if (Object.hasOwn(record, 'pr') && record.pr !== pr) {
    reasons.push('fallback is for a different PR');
  }

  // reviewer
  if (Object.hasOwn(record, 'reviewer')) {
    const reviewer = record.reviewer;
    if (isPlainObject(reviewer)) {
      reasons.push(...unknownFieldProblems(reviewer, REVIEWER_FIELDS, 'reviewer'));
      reasons.push(...missingNestedFields(reviewer, REVIEWER_FIELDS, 'reviewer'));
      if (Object.hasOwn(reviewer, 'name') && (typeof reviewer.name !== 'string' || !reviewer.name.trim())) {
        reasons.push('reviewer.name is required');
      }
      const nameRaw = reviewer.name;
      const nameNorm = typeof nameRaw === 'string' ? nameRaw.trim().toLowerCase() : '';
      const authorNorm = typeof prAuthor === 'string' ? prAuthor.trim().toLowerCase() : '';
      if (nameNorm && (reviewerNameIsDisallowed(nameNorm) || (authorNorm && nameNorm === authorNorm))) {
        reasons.push(`reviewer is not independent: ${nameRaw}`);
      }
      if (Object.hasOwn(reviewer, 'kind') && !REVIEWER_KINDS.includes(reviewer.kind)) {
        reasons.push('unknown reviewer kind');
      }
    } else {
      reasons.push('reviewer must be an object');
    }
  }

  // scope
  if (Object.hasOwn(record, 'scope')) {
    if (isPlainObject(record.scope)) {
      reasons.push(...unknownFieldProblems(record.scope, SCOPE_FIELDS, 'scope'));
      reasons.push(...missingNestedFields(record.scope, SCOPE_FIELDS, 'scope'));
    } else {
      reasons.push('scope must be an object');
    }
  }

  const scope = isPlainObject(record.scope) ? record.scope : {};
  const headMismatch =
    (Object.hasOwn(record, 'head') && record.head !== head) ||
    (Object.hasOwn(scope, 'head') && scope.head !== head);
  if (headMismatch) reasons.push('fallback is for a different head');

  const baseMismatch =
    (Object.hasOwn(record, 'base') && record.base !== base) ||
    (Object.hasOwn(scope, 'base') && scope.base !== base);
  if (baseMismatch) reasons.push('fallback scope base does not match the reviewed base (merge-base)');

  if (Object.hasOwn(scope, 'diff') && scope.diff !== 'full') {
    reasons.push('fallback must review the full base..head diff');
  }

  // result
  if (Object.hasOwn(record, 'result')) {
    const result = record.result;
    if (isPlainObject(result)) {
      reasons.push(...unknownFieldProblems(result, RESULT_FIELDS, 'result'));
      reasons.push(...missingNestedFields(result, RESULT_FIELDS, 'result'));
      if (Object.hasOwn(result, 'status') && result.status !== 'complete') {
        reasons.push('fallback review is not complete');
      }
      if (Object.hasOwn(result, 'findings') && !Array.isArray(result.findings)) {
        reasons.push('result.findings must be an array');
      }
      if (Array.isArray(result.findings)) {
        for (const finding of result.findings) {
          if (!isPlainObject(finding)) {
            if (!reasons.includes('result.findings entries must be objects')) {
              reasons.push('result.findings entries must be objects');
            }
            continue;
          }
          reasons.push(...unknownFieldProblems(finding, FINDING_FIELDS, 'result.findings[]'));
          if (!FINDING_DISPOSITIONS.includes(finding.disposition)) {
            reasons.push(`finding ${finding.id} has no disposition`);
          }
        }
      }
    } else {
      reasons.push('result must be an object');
    }
  }

  // owner_decision
  if (Object.hasOwn(record, 'owner_decision')) {
    const ownerDecision = record.owner_decision;
    if (isPlainObject(ownerDecision)) {
      reasons.push(...unknownFieldProblems(ownerDecision, OWNER_DECISION_FIELDS, 'owner_decision'));
      reasons.push(...missingNestedFields(ownerDecision, OWNER_DECISION_FIELDS, 'owner_decision'));
      if (Object.hasOwn(ownerDecision, 'verbatim')) {
        const verbatim = typeof ownerDecision.verbatim === 'string' ? ownerDecision.verbatim : '';
        const headPrefix = typeof head === 'string' ? head.slice(0, 12) : '';
        const namesHead = verbatim.trim().length > 0 &&
          ((typeof head === 'string' && verbatim.includes(head)) || (headPrefix && verbatim.includes(headPrefix)));
        if (!namesHead) reasons.push('owner approval does not name this head');
      }
      if (Object.hasOwn(ownerDecision, 'decided_at') && !ISO_8601_RE.test(ownerDecision.decided_at || '')) {
        reasons.push('invalid decided_at');
      }
    } else {
      reasons.push('owner_decision must be an object');
    }
  }

  // Only an explicit approve-fallback satisfies the prerequisite; anything else
  // (absent, blank, misspelled, or another type) blocks.
  const decision = isPlainObject(record.owner_decision) ? record.owner_decision.decision : undefined;
  if (decision === 'wait') {
    reasons.push('owner chose wait: wait blocks acceptance');
  } else if (decision === 'retry-later') {
    reasons.push('owner chose retry later: retry later blocks acceptance');
  } else if (decision !== 'approve-fallback') {
    reasons.push('owner_decision.decision must be approve-fallback');
  }

  // Head trust and Codex status -- fail closed when trust is not established.
  const trustEstablished = headTrust === 'trusted' || headTrust === 'untrusted';
  if (!trustEstablished) reasons.push('head trust not established');

  const headPrefix = typeof head === 'string' ? head.slice(0, 12) : '';
  const codexOutBasename = basename(record.codex_out);
  const codexOutMatchesHead = Boolean(headPrefix) && codexOutBasename.startsWith(headPrefix);

  // The record must name the exact Codex output whose status/meta supplied
  // codexStatus, so another attempt's evidence cannot stand in for it.
  if (Object.hasOwn(record, 'codex_out') && record.codex_out !== codexStatus?.out) {
    reasons.push('fallback codex_out does not match the Codex output checked');
  }

  if (codexStatus && codexStatus.complete === true) {
    // Fallback is reserved for runs that actually stayed incomplete.
    if (headTrust === 'untrusted') {
      reasons.push('Codex evidence claims complete for an untrusted head; untrusted runs are refused until Phase 85.1');
    } else {
      reasons.push('Codex is complete for this head; a fallback is not used');
    }
  } else if (headTrust === 'trusted') {
    const attempt = codexStatus?.attempt;
    if (!codexOutMatchesHead || !(typeof attempt === 'number' && attempt >= 2)) {
      reasons.push(
        'fallback needs the retried Codex attempt for this head (attempt 2 or later) to have stayed INCOMPLETE/PENDING'
      );
    }
    if (codexStatus?.reviewMode === 'untrusted-refused') {
      reasons.push('an untrusted-mode refusal does not open the fallback for a trusted head; run the trusted Codex pass');
    }
  } else if (headTrust === 'untrusted') {
    if (!(codexStatus?.reviewMode === 'untrusted-refused' && codexOutMatchesHead)) {
      reasons.push('untrusted head needs its recorded INCOMPLETE Codex refusal for this head');
    }
  }

  return {ok: reasons.length === 0, reasons};
}

function readJson(readFileSync, path) {
  const text = readFileSync(path, 'utf8');
  return JSON.parse(text);
}

// Reads the Codex status/meta files under the OUT prefix to build the
// codexStatus object validateFallback expects, implementing the same
// completeness contract as acceptance-readiness.cjs's codexStatusFor().
function codexStatusFromOutput(codexOutPrefix, readFileSync) {
  let status;
  let meta;
  try {
    status = readJson(readFileSync, `${codexOutPrefix}.status.json`);
  } catch (err) {
    throw new Error(`could not read Codex status file for ${codexOutPrefix}: ${err.message}`);
  }
  try {
    meta = readJson(readFileSync, `${codexOutPrefix}.meta.json`);
  } catch (err) {
    throw new Error(`could not read Codex meta file for ${codexOutPrefix}: ${err.message}`);
  }
  const auditedChanged = Array.isArray(meta.audited_inputs_changed_in_diff) ? meta.audited_inputs_changed_in_diff : [];
  let baseStatus = null;
  if (auditedChanged.length > 0) {
    try {
      baseStatus = readJson(readFileSync, `${codexOutPrefix}.base-status.json`);
    } catch {
      baseStatus = null;
    }
  }
  const complete =
    meta.review_mode === 'trusted-local-tests' &&
    status?.status === 'complete' &&
    (auditedChanged.length === 0 || baseStatus?.status === 'complete');
  return {
    complete,
    attempt: meta.attempt,
    out: codexOutPrefix,
    reviewMode: meta.review_mode,
    head: meta.head,
    base: meta.base,
  };
}

function parseValidateArgs(rest) {
  const opts = {};
  for (let i = 0; i < rest.length; i++) {
    const arg = rest[i];
    switch (arg) {
      case '--file':
        opts.file = rest[++i];
        break;
      case '--pr':
        opts.prRaw = rest[++i];
        break;
      case '--head':
        opts.head = rest[++i];
        break;
      case '--base':
        opts.base = rest[++i];
        break;
      case '--pr-author':
        opts.prAuthor = rest[++i];
        break;
      case '--head-trust':
        opts.headTrust = rest[++i];
        break;
      case '--codex-out':
        opts.codexOut = rest[++i];
        break;
      default:
        throw new Error(`unknown argument: ${arg}`);
    }
  }
  if (!PR_ARG_RE.test(opts.prRaw || '')) {
    throw new Error(`invalid --pr: ${JSON.stringify(opts.prRaw)} (expected a positive integer)`);
  }
  opts.pr = Number(opts.prRaw);
  if (!HEAD_RE.test(opts.head || '')) {
    throw new Error(`invalid --head: ${JSON.stringify(opts.head)} (expected 40 hex characters)`);
  }
  if (!HEAD_RE.test(opts.base || '')) {
    throw new Error(`invalid --base: ${JSON.stringify(opts.base)} (expected 40 hex characters)`);
  }
  if (!opts.prAuthor) {
    throw new Error('--pr-author is required');
  }
  if (opts.headTrust !== 'trusted' && opts.headTrust !== 'untrusted') {
    throw new Error(`invalid --head-trust: ${JSON.stringify(opts.headTrust)} (expected "trusted" or "untrusted")`);
  }
  if (!OUT_PATH_RE.test(opts.codexOut || '')) {
    throw new Error(`invalid --codex-out: ${JSON.stringify(opts.codexOut)}`);
  }
  if (!opts.file) {
    throw new Error('--file is required');
  }
  return opts;
}

// runCli(argv, io): argv is ['validate', ...flags]. io.readFileSync/log/error are
// injectable for tests; io.readFileSync defaults to node:fs's readFileSync. Every
// argument is validated before any file is read. Exits 0 when the fallback is
// valid, 1 when it is invalid (reasons printed via io.error), 2 on a usage error.
function runCli(argv, io = {}) {
  const readFileSync = io.readFileSync || fs.readFileSync;
  const log = io.log || ((...args) => console.log(...args));
  const error = io.error || ((...args) => console.error(...args));

  const [subcommand, ...rest] = argv;
  if (subcommand !== 'validate') {
    error(`unknown subcommand: ${JSON.stringify(subcommand)} (expected "validate")`);
    return 2;
  }

  let opts;
  try {
    opts = parseValidateArgs(rest);
  } catch (err) {
    error(err.message);
    return 2;
  }

  let record;
  try {
    record = JSON.parse(readFileSync(opts.file, 'utf8'));
  } catch (err) {
    error(`could not read --file ${opts.file}: ${err.message}`);
    return 1;
  }

  let codexStatus;
  try {
    codexStatus = codexStatusFromOutput(opts.codexOut, readFileSync);
  } catch (err) {
    error(err.message);
    return 1;
  }
  if (codexStatus.head !== opts.head) {
    error(`Codex output is for a different head: ${opts.codexOut} records ${JSON.stringify(codexStatus.head)}`);
    return 1;
  }
  // --base is the reviewed base: the BASE_SHA the Codex run recorded, which
  // readiness requires to be the merge-base of the PR base and head. Binding it
  // to the meta keeps the fallback and its Codex evidence on one base (WR-02).
  if (codexStatus.base !== opts.base) {
    error(`Codex output is for a different base: ${opts.codexOut} records ${JSON.stringify(codexStatus.base)}`);
    return 1;
  }

  const {ok, reasons} = validateFallback(record, {
    pr: opts.pr,
    head: opts.head,
    base: opts.base,
    prAuthor: opts.prAuthor,
    headTrust: opts.headTrust,
    codexStatus,
  });

  if (ok) {
    log(`fallback valid for ${opts.head}`);
    return 0;
  }
  for (const reason of reasons) error(reason);
  return 1;
}

if (require.main === module) {
  process.exitCode = runCli(process.argv.slice(2));
}

module.exports = {
  FALLBACK_SCHEMA_VERSION,
  FALLBACK_FIELDS,
  REVIEWER_KINDS,
  DISALLOWED_REVIEWERS,
  OWNER_DECISIONS,
  validateFallback,
  runCli,
};
