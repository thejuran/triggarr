// Guards the three copies of the mandatory CI job list from drifting apart:
// release-policy.cjs's REQUIRED_JOBS, ci.yml's `ci-ready` needs/display names,
// and the Python `required` set inside ci-ready's step. Node stdlib only — no
// YAML library, no new dependency — so this stays installable with zero installs.

function stripQuotes(value) {
  if (value.length >= 2) {
    const first = value[0];
    const last = value[value.length - 1];
    if ((first === '"' && last === '"') || (first === "'" && last === "'")) {
      return value.slice(1, -1);
    }
  }
  return value;
}

function findDuplicates(list, label) {
  const seen = new Set();
  const duplicates = new Set();
  for (const item of list) {
    if (seen.has(item)) duplicates.add(item);
    seen.add(item);
  }
  return [...duplicates].map(item => `${label} contains duplicate entry "${item}"`);
}

// Splits the text under the top-level `jobs:` key into per-job blocks.
// Each job is returned as {id, name, needs, lines}: `name` is the 4-space
// `name:` override (or null), `needs` is the parsed list of needed job ids
// (or null if absent), and `lines` holds the job's raw body lines so other
// extractors (ci-ready's Python set, job `if:` conditions) can scan them.
function parseJobs(text) {
  const lines = text.split('\n');
  const jobsLineIdx = lines.findIndex(line => /^jobs:\s*$/.test(line));
  if (jobsLineIdx === -1) {
    throw new Error('No top-level "jobs:" key found in workflow text');
  }

  const jobs = [];
  let current = null;
  for (let i = jobsLineIdx + 1; i < lines.length; i++) {
    const line = lines[i];
    if (/^\S/.test(line)) break; // next top-level key ends the jobs section

    const jobStart = line.match(/^  ([A-Za-z0-9_.-]+):\s*$/);
    if (jobStart) {
      current = {id: jobStart[1], name: null, needs: null, lines: []};
      jobs.push(current);
      continue;
    }
    if (current) current.lines.push(line);
  }

  for (const job of jobs) {
    for (const line of job.lines) {
      const nameMatch = line.match(/^    name:\s*(.+?)\s*$/);
      if (nameMatch) {
        job.name = stripQuotes(nameMatch[1]);
      }

      const needsMatch = line.match(/^    needs:(.*)$/);
      if (needsMatch) {
        const raw = needsMatch[1].trim();
        const flowMatch = raw.match(/^\[(.*)\]$/);
        if (flowMatch) {
          job.needs = flowMatch[1].split(',').map(s => s.trim()).filter(Boolean);
        } else if (/^[A-Za-z0-9_.-]+$/.test(raw)) {
          job.needs = [raw];
        } else {
          // Empty (block-list form on following lines) or any other shape
          // we don't recognize — fail closed rather than mis-parse.
          throw new Error(`Job "${job.id}" has an unsupported needs form: ${JSON.stringify(raw)}`);
        }
      }
    }
  }

  return jobs;
}

// Extracts the aggregate job's display name, needed job ids, and the Python
// `required = {...}` set from its heredoc step. Throws (fails closed) on any
// structurally missing or duplicated piece rather than silently reporting
// "consistent" because nothing was found.
function extractCiReady(text, jobId = 'ci-ready') {
  const jobs = parseJobs(text);
  const job = jobs.find(j => j.id === jobId);
  if (!job) {
    throw new Error(`Aggregate job "${jobId}" not found`);
  }
  if (!job.name) {
    throw new Error(`Aggregate job "${jobId}" has no "name:" display override`);
  }
  if (!job.needs || job.needs.length === 0) {
    throw new Error(`Aggregate job "${jobId}" has no "needs:"`);
  }

  const requiredLines = job.lines.filter(line => /required\s*=\s*\{/.test(line));
  if (requiredLines.length !== 1) {
    throw new Error(
      `Aggregate job "${jobId}" must contain exactly one "required = {...}" line, found ${requiredLines.length}`
    );
  }

  const braceMatch = requiredLines[0].match(/required\s*=\s*\{([^}]*)\}/);
  if (!braceMatch) {
    throw new Error(`Aggregate job "${jobId}" required set is not well-formed`);
  }

  const pythonRequired = [];
  const stringLiteral = /(['"])((?:(?!\1).)*)\1/g;
  let match;
  while ((match = stringLiteral.exec(braceMatch[1])) !== null) {
    pythonRequired.push(match[2]);
  }

  return {displayName: job.name, needs: job.needs, pythonRequired};
}

// Returns an array of human-readable problem strings (empty = consistent).
// Each problem names which copy disagrees and the offending job so a CI
// failure explains itself without needing this file open.
function checkJobListConsistency({workflowText, requiredJobs}) {
  const problems = [];
  const jobs = parseJobs(workflowText);
  const ciReady = extractCiReady(workflowText);

  problems.push(...findDuplicates(requiredJobs, 'REQUIRED_JOBS'));
  problems.push(...findDuplicates(ciReady.needs, 'ci-ready needs'));
  problems.push(...findDuplicates(ciReady.pythonRequired, 'ci-ready Python required set'));

  for (const id of ciReady.needs) {
    if (!jobs.some(j => j.id === id)) {
      problems.push(`ci-ready needs references unknown job "${id}"`);
    }
  }

  const effectiveNames = ciReady.needs.map(id => {
    const job = jobs.find(j => j.id === id);
    return job ? (job.name ?? job.id) : id;
  });
  const computedSet = new Set([...effectiveNames, ciReady.displayName]);
  const requiredSet = new Set(requiredJobs);
  const aggregate = requiredJobs[requiredJobs.length - 1];
  if (aggregate !== ciReady.displayName) {
    problems.push(
      `REQUIRED_JOBS aggregate entry "${aggregate}" does not match ci-ready display name "${ciReady.displayName}"`
    );
  }
  for (const name of computedSet) {
    if (!requiredSet.has(name)) {
      problems.push(`ci-ready needs/display names produce "${name}" which is not present in REQUIRED_JOBS`);
    }
  }
  for (const name of requiredSet) {
    if (!computedSet.has(name)) {
      problems.push(`REQUIRED_JOBS entry "${name}" has no matching needed job or aggregate display name`);
    }
  }

  const pythonSet = new Set(ciReady.pythonRequired);
  const needsSet = new Set(ciReady.needs);
  for (const id of pythonSet) {
    if (!needsSet.has(id)) {
      problems.push(`ci-ready Python required set has "${id}" which is not in needs`);
    }
  }
  for (const id of needsSet) {
    if (!pythonSet.has(id)) {
      problems.push(`ci-ready needs has "${id}" which is not in the Python required set`);
    }
  }

  return problems;
}

// ---- Minimal YAML block-mapping reader (stdlib only) ----------------------
// The skip detector must find a mapping key however YAML lets it be spelled
// (`if:`, `if :`, `"if":`, `'if' :`, a key on the dash line with any number
// of spaces after the dash, a flow-mapping step), and must REPORT any shape
// it cannot read rather than treat it as "no condition". These helpers read
// only the structure the detector needs: keys at a known column, and the
// scalar value of a key. Anything else (explicit `?` keys, merge `<<` keys,
// aliases/anchors/tags in key position, undecodable quoted keys) is returned
// as unparseable so the caller can fail closed.

const JOB_KEY_INDENT = 4;

function indentOf(line) {
  return line.match(/^ */)[0].length;
}

function isBlankOrComment(line) {
  return /^\s*(#.*)?$/.test(line);
}

// Parses `key: rest` at the start of `text` (text begins at the key column).
// Returns {key, rest} or null when the text is not a plain or quoted
// mapping key. In flow context a quoted key may be followed directly by `:`.
function parseMappingKey(text, {flow = false} = {}) {
  const afterColon = flow ? '' : '(?=\\s|$)';
  let match = text.match(new RegExp(`^("(?:[^"\\\\]|\\\\.)*")\\s*:${afterColon}([\\s\\S]*)$`));
  if (match) {
    try {
      return {key: JSON.parse(match[1]), rest: match[2]};
    } catch {
      return null; // a YAML escape JSON cannot decode (e.g. "i\x66"): fail closed
    }
  }
  match = text.match(new RegExp(`^'((?:[^']|'')*)'\\s*:${afterColon}([\\s\\S]*)$`));
  if (match) {
    return {key: match[1].replace(/''/g, "'"), rest: match[2]};
  }
  // A plain key may not start with a YAML indicator (quote, flow bracket,
  // anchor/alias/tag, block scalar, explicit key, directive, comment, merge
  // `<<`, sequence dash) or whitespace.
  match = text.match(/^([^\s"'{}[\],&*!|>?%@`#<-][^#\n]*?)\s*:(?=\s|$)([\s\S]*)$/);
  if (match) {
    return {key: match[1], rest: match[2]};
  }
  return null;
}

// Reads the scalar value of the key on lines[index] (whose inline remainder
// is `inlineRaw` and whose key sits at `keyCol`): the inline text plus every
// following line indented deeper than the key (block scalar or multi-line
// plain scalar), whitespace-normalized to single spaces.
function readKeyValue(lines, index, inlineRaw, keyCol) {
  const inline = inlineRaw.trim();
  const collected = /^[>|][-+0-9]*$/.test(inline) ? [] : [inline];
  for (let j = index + 1; j < lines.length; j++) {
    const continuation = lines[j];
    if (/^\s*$/.test(continuation)) continue;
    if (indentOf(continuation) <= keyCol) break;
    collected.push(continuation.trim());
  }
  return collected.join(' ').replace(/\s+/g, ' ').trim();
}

// Reads the block mapping whose keys sit at `keyCol` in `lines`. Returns
// {entries: [{key, value}], problems: [string]}. Lines deeper than keyCol
// belong to the previous key's value; a non-comment line shallower than
// keyCol, or a key line that does not parse, is a problem.
function readBlockMapping(lines, keyCol) {
  const entries = [];
  const problems = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (isBlankOrComment(line)) continue;
    const indent = indentOf(line);
    if (indent > keyCol) continue;
    if (indent < keyCol) {
      problems.push(`unexpected indentation at ${JSON.stringify(line.trim())}`);
      continue;
    }
    const parsed = parseMappingKey(line.slice(keyCol));
    if (!parsed) {
      problems.push(`unreadable key at ${JSON.stringify(line.trim())}`);
      continue;
    }
    entries.push({key: parsed.key, value: readKeyValue(lines, i, parsed.rest, keyCol)});
  }
  return {entries, problems};
}

// Reads a flow mapping `{k: v, ...}` from `text` (starting at `{`, possibly
// spanning lines). Returns {entries, problems}; an unbalanced mapping, text
// after the closing brace, or an entry without a readable key is a problem.
function readFlowMapping(text) {
  const parts = [];
  let current = '';
  let depth = 0;
  let quote = null;
  let lastSignificant = '';
  let end = -1;
  for (let i = 0; i < text.length && end === -1; i++) {
    const ch = text[i];
    if (quote) {
      current += ch;
      if (quote === '"' && ch === '\\') {
        current += text[i + 1] ?? '';
        i++;
      } else if (ch === quote) {
        if (quote === "'" && text[i + 1] === "'") {
          current += "'";
          i++;
        } else {
          quote = null;
          lastSignificant = ch;
        }
      }
      continue;
    }
    if ((ch === '"' || ch === "'") && ['', ':', '{', '[', ','].includes(lastSignificant)) {
      quote = ch;
      current += ch;
      continue;
    }
    if (ch === '#' && (i === 0 || /\s/.test(text[i - 1]))) {
      while (i + 1 < text.length && text[i + 1] !== '\n') i++;
      continue;
    }
    if (!/\s/.test(ch)) lastSignificant = ch;
    if (ch === '{' || ch === '[') {
      depth++;
      if (depth === 1) {
        lastSignificant = '{';
        continue;
      }
    } else if (ch === '}' || ch === ']') {
      depth--;
      if (depth === 0) {
        parts.push(current);
        end = i;
        continue;
      }
    } else if (ch === ',' && depth === 1) {
      parts.push(current);
      current = '';
      continue;
    }
    current += ch;
  }

  if (end === -1) {
    return {entries: [], problems: ['unterminated flow mapping']};
  }
  const problems = [];
  if (!isBlankOrComment(text.slice(end + 1).replace(/\n/g, ' '))) {
    problems.push('text after a flow mapping');
  }
  const entries = [];
  for (const part of parts) {
    const trimmed = part.trim();
    if (trimmed === '') continue;
    const parsed = parseMappingKey(trimmed, {flow: true});
    if (!parsed) {
      problems.push(`unreadable flow-mapping entry ${JSON.stringify(trimmed)}`);
      continue;
    }
    entries.push({key: parsed.key, value: parsed.rest.replace(/\s+/g, ' ').trim()});
  }
  return {entries, problems};
}

// Reads one `steps:` item (its lines, the first starting with the dash at
// seqCol) into {entries, problems}.
function readStepItem(lines, seqCol) {
  const afterDash = lines[0].slice(seqCol + 1);
  const gap = indentOf(afterDash);
  const content = afterDash.slice(gap);

  if (content.startsWith('{')) {
    return readFlowMapping([content, ...lines.slice(1)].join('\n'));
  }
  if (isBlankOrComment(content)) {
    // `-` alone: the mapping starts on the next content line.
    const body = lines.slice(1);
    const firstIdx = body.findIndex(line => !isBlankOrComment(line));
    if (firstIdx === -1 || indentOf(body[firstIdx]) <= seqCol) {
      return {entries: [], problems: ['empty step']};
    }
    return readBlockMapping(body, indentOf(body[firstIdx]));
  }
  // The first key sits on the dash line, after any number of spaces.
  const keyCol = seqCol + 1 + gap;
  return readBlockMapping([' '.repeat(keyCol) + content, ...lines.slice(1)], keyCol);
}

// Reads a job's body (parseJobs' raw `lines`) into its job-level keys and
// its steps. Returns {jobKeys: [{key, value}], steps: [{name, conditions, uses, hasRun}],
// problems: [string]}. Every shape it cannot read is a problem, so callers
// fail closed instead of treating an unread step as having no condition.
function readJobBody(jobLines) {
  const problems = [];
  const steps = [];
  const firstIdx = jobLines.findIndex(line => !isBlankOrComment(line));
  if (firstIdx === -1) {
    return {jobKeys: [], steps, problems};
  }
  if (indentOf(jobLines[firstIdx]) !== JOB_KEY_INDENT) {
    problems.push(`job keys are not indented by ${JOB_KEY_INDENT} spaces`);
    return {jobKeys: [], steps, problems};
  }

  // Job-level keys: every non-comment line at the job-key column, except
  // the dash lines of a sequence written at that same column.
  const jobKeyLines = jobLines.map(line =>
    !isBlankOrComment(line) && indentOf(line) === JOB_KEY_INDENT && /^ *-(\s|$)/.test(line) ? '' : line
  );
  const jobMapping = readBlockMapping(jobKeyLines, JOB_KEY_INDENT);
  problems.push(...jobMapping.problems);
  const jobKeys = jobMapping.entries;

  const stepsKeyIdxs = [];
  jobLines.forEach((line, idx) => {
    if (isBlankOrComment(line) || indentOf(line) !== JOB_KEY_INDENT) return;
    const parsed = parseMappingKey(line.slice(JOB_KEY_INDENT));
    if (parsed && parsed.key === 'steps') stepsKeyIdxs.push({idx, rest: parsed.rest});
  });
  if (stepsKeyIdxs.length > 1) {
    problems.push('more than one steps: key');
  }
  if (stepsKeyIdxs.length === 0) {
    return {jobKeys, steps, problems};
  }
  const {idx: stepsIdx, rest: stepsRest} = stepsKeyIdxs[0];
  if (!isBlankOrComment(stepsRest)) {
    problems.push(`steps: is not a block sequence (${JSON.stringify(stepsRest.trim())})`);
    return {jobKeys, steps, problems};
  }

  // Split the steps region into items by the dash column of the first item.
  const items = [];
  let seqCol = null;
  for (let i = stepsIdx + 1; i < jobLines.length; i++) {
    const line = jobLines[i];
    if (isBlankOrComment(line)) {
      if (items.length) items[items.length - 1].push(line);
      continue;
    }
    const indent = indentOf(line);
    const isItem = /^-(\s|$)/.test(line.slice(indent));
    if (seqCol === null) {
      if (!isItem || indent < JOB_KEY_INDENT) {
        if (indent > JOB_KEY_INDENT) problems.push(`steps: is not a block sequence (${JSON.stringify(line.trim())})`);
        break;
      }
      seqCol = indent;
    }
    if (indent <= JOB_KEY_INDENT && !(indent === seqCol && isItem)) break; // back at a job-level key
    if (indent === seqCol && isItem) {
      items.push([line]);
    } else if (indent > seqCol) {
      items[items.length - 1].push(line);
    } else {
      problems.push(`unexpected line in steps: ${JSON.stringify(line.trim())}`);
    }
  }

  for (const itemLines of items) {
    const item = readStepItem(itemLines, seqCol);
    problems.push(...item.problems);
    const names = item.entries.filter(entry => entry.key === 'name').map(entry => stripQuotes(entry.value));
    const conditions = item.entries.filter(entry => entry.key === 'if').map(entry => entry.value);
    const uses = item.entries.filter(entry => entry.key === 'uses').map(entry => stripQuotes(entry.value));
    const hasRun = item.entries.some(entry => entry.key === 'run');
    steps.push({name: names.length ? names[0] : null, conditions, uses: uses.length ? uses[0] : null, hasRun});
  }

  return {jobKeys, steps, problems};
}

// Returns a job's job-level `if` condition, whitespace-normalized to single
// spaces, supporting a single-line value, a folded `>-`/`|` block, and a
// value on the following lines, in any key spelling YAML allows. Returns
// null if the job has no `if`.
function extractJobIf(text, jobId) {
  const jobs = parseJobs(text);
  const job = jobs.find(j => j.id === jobId);
  if (!job) {
    throw new Error(`Job "${jobId}" not found`);
  }
  const ifEntry = readJobBody(job.lines).jobKeys.find(entry => entry.key === 'if');
  return ifEntry ? ifEntry.value : null;
}

// ACCEPT-03 (D-01/D-02): no skip condition may let a required check pass
// without a required job running. The functions below extend the same
// text-scanning approach as extractJobIf/checkJobListConsistency above:
// parse once, then push a descriptive problem string per offending line.
// Still Node stdlib only -- no YAML library, no new dependency.

// Each workflow's `on:` trigger contract is reviewed and locked here.
// Changing a contract (adding a trigger, widening branches, dropping a
// required activity type) is a sensitive change reviewed under
// docs/review-classification-policy.md, same as the workflow files
// themselves.
const TRIGGER_CONTRACTS = Object.freeze({
  'ci.yml': Object.freeze({
    push: Object.freeze({branches: ['main']}),
    pull_request: Object.freeze({branches: ['main'], requiredTypes: ['opened', 'synchronize', 'reopened']}),
  }),
  'review-acceptance.yml': Object.freeze({
    pull_request: Object.freeze({
      branches: ['main'],
      requiredTypes: ['opened', 'synchronize', 'reopened', 'ready_for_review'],
    }),
  }),
});

// GitHub applies these activity types to `pull_request` by default when a
// workflow's trigger omits `types:` entirely.
const GITHUB_DEFAULT_PULL_REQUEST_TYPES = ['opened', 'synchronize', 'reopened'];

// These keys let a trigger narrow which pushes/PRs run required jobs at
// all, which is exactly the skip path ACCEPT-03 closes. Recognized (so they
// don't also trip "unsupported key"), but always reported.
const TRIGGER_FILTER_KEYS = ['paths', 'paths-ignore', 'branches-ignore', 'tags-ignore'];

// These are the current reviewed step-level `if:` conditions on required
// jobs. Both are evidence-upload steps that never gate required work.
// Adding an entry here is a sensitive change reviewed under
// docs/review-classification-policy.md -- it is the one place a required
// job may skip a step without failing the no-skip detector.
const STEP_IF_ALLOWLIST = Object.freeze({
  'test::Upload test evidence': 'always()',
  'browser-e2e::Upload browser failure evidence':
    "failure() && hashFiles('e2e-artifacts/credential/scan-complete.json') != '' && " +
    "hashFiles('e2e-artifacts/pages/scan-complete.json') != ''",
});
// Every allowlisted entry is an evidence upload, so the step carrying it must
// be the only step of that name in its job, use this action and have no run:
// (review iteration 3 WR-01). The authoritative check is the PyYAML guard in
// tests/test_required_jobs_no_skip.py; this detector is a secondary line.
const ALLOWLISTED_STEP_USES = 'actions/upload-artifact@';

function parseFlowList(raw) {
  const trimmed = raw.trim();
  const bracketed = trimmed.match(/^\[(.*)\]$/);
  if (!bracketed) {
    return trimmed === '' ? [] : [stripQuotes(trimmed)];
  }
  if (bracketed[1].trim() === '') return [];
  return bracketed[1].split(',').map(item => stripQuotes(item.trim()));
}

function arraysEqual(a, b) {
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

// Minimal glob support for requiredJobsFor's path-filter simulation: `**`
// matches any number of path segments, `*` matches within one segment,
// everything else is literal. No dependency added for this.
function globToRegExp(pattern) {
  let out = '';
  for (let i = 0; i < pattern.length; i++) {
    if (pattern[i] === '*' && pattern[i + 1] === '*') {
      out += '.*';
      i++;
    } else if (pattern[i] === '*') {
      out += '[^/]*';
    } else {
      out += pattern[i].replace(/[.+^${}()|[\]\\]/g, '\\$&');
    }
  }
  return new RegExp(`^${out}$`);
}

function globMatch(pattern, filePath) {
  return globToRegExp(pattern).test(filePath);
}

// Reads the top-level `on:` block. Returns {triggers: {name: {key: raw}}}
// on a recognized block-mapping form, or {syntaxError: 'unsupported trigger
// syntax'} for a scalar/sequence `on:` (e.g. `on: [push, pull_request]` or
// `on: push`) or a trigger expressed as a flow mapping (e.g.
// `pull_request: {branches: [main]}`). Throws (fail closed) when no `on:`
// key exists at all.
function parseOnBlock(text) {
  const lines = text.split('\n');
  const onIdx = lines.findIndex(line => /^on:\s*$/.test(line));
  if (onIdx === -1) {
    const hasScalarOn = lines.some(line => /^on:\s*\S.*$/.test(line));
    if (!hasScalarOn) {
      throw new Error('No top-level "on:" key found in workflow text');
    }
    return {syntaxError: 'unsupported trigger syntax'};
  }

  const triggers = {};
  let currentTrigger = null;
  for (let i = onIdx + 1; i < lines.length; i++) {
    const line = lines[i];
    if (/^\S/.test(line)) break; // next top-level key ends the "on:" block

    const triggerStart = line.match(/^  ([A-Za-z0-9_-]+):\s*(.*)$/);
    if (triggerStart) {
      const [, name, rest] = triggerStart;
      if (rest !== '') {
        return {syntaxError: 'unsupported trigger syntax'};
      }
      currentTrigger = name;
      triggers[name] = {};
      continue;
    }

    if (currentTrigger) {
      // A key may be bare, 'single-quoted' or "double-quoted": YAML reads all
      // three as the same key, so a quoted `"paths":` must not slip past the
      // filter-key check (review pass 2).
      const keyMatch = line.match(/^    (?:"([A-Za-z0-9_-]+)"|'([A-Za-z0-9_-]+)'|([A-Za-z0-9_-]+))\s*:\s*(.*)$/);
      if (keyMatch) {
        const key = keyMatch[1] ?? keyMatch[2] ?? keyMatch[3];
        triggers[currentTrigger][key] = keyMatch[4];
      }
    }
  }

  return {triggers};
}

// Resolves which job ids are "required" for a given aggregate: every job
// when aggregateJobId is null (every job in the workflow is required, as in
// review-acceptance.yml), otherwise the aggregate's own needs plus the
// aggregate itself (as in ci.yml's ci-ready).
function resolveRequiredJobIds(jobs, aggregateJobId) {
  if (aggregateJobId === null) {
    return jobs.map(job => job.id);
  }
  const aggregateJob = jobs.find(job => job.id === aggregateJobId);
  if (!aggregateJob) {
    throw new Error(`Aggregate job "${aggregateJobId}" not found`);
  }
  return [...(aggregateJob.needs || []), aggregateJobId];
}

// Proves no skip condition exists anywhere in the trigger contract or the
// required jobs that back a GitHub required check. Returns an array of
// human-readable, specific-reason problem strings (empty = no skip path
// found). Throws (fail closed) when no triggerContract is supplied, so no
// caller can accidentally skip trigger validation.
function findSkipConditions({workflowText, aggregateJobId, triggerContract}) {
  if (!triggerContract) {
    throw new Error('trigger contract is required');
  }

  const problems = [];

  const onBlock = parseOnBlock(workflowText);
  if (onBlock.syntaxError) {
    problems.push(onBlock.syntaxError);
    return problems;
  }

  const contractTriggerNames = Object.keys(triggerContract);
  const foundTriggerNames = Object.keys(onBlock.triggers);

  for (const name of contractTriggerNames) {
    if (!foundTriggerNames.includes(name)) {
      problems.push(`on.${name} is required`);
    }
  }
  for (const name of foundTriggerNames) {
    if (!contractTriggerNames.includes(name)) {
      problems.push(`unsupported trigger "${name}"`);
    }
  }

  for (const name of foundTriggerNames) {
    if (!contractTriggerNames.includes(name)) continue;
    const spec = triggerContract[name];
    const data = onBlock.triggers[name];

    for (const [key, rawValue] of Object.entries(data)) {
      if (TRIGGER_FILTER_KEYS.includes(key)) {
        problems.push(`on.${name}.${key} lets a PR or push skip required jobs`);
        continue;
      }
      if (key === 'branches') {
        const branches = parseFlowList(rawValue);
        const expected = spec.branches || [];
        if (!arraysEqual(branches, expected)) {
          problems.push(`on.${name}.branches must be exactly [${expected.join(', ')}]`);
        }
        continue;
      }
      if (key === 'types') {
        continue; // validated below against requiredTypes
      }
      problems.push(`unsupported key "${key}" under on.${name}`);
    }

    if (spec.requiredTypes) {
      const typesRaw = data.types;
      if (typesRaw === undefined) {
        for (const type of spec.requiredTypes) {
          if (!GITHUB_DEFAULT_PULL_REQUEST_TYPES.includes(type)) {
            problems.push(`on.${name}.types omits ${type}`);
          }
        }
      } else {
        const types = parseFlowList(typesRaw);
        for (const type of spec.requiredTypes) {
          if (!types.includes(type)) {
            problems.push(`on.${name}.types omits ${type}`);
          }
        }
      }
    }
  }

  const jobs = parseJobs(workflowText);
  const requiredJobIds = resolveRequiredJobIds(jobs, aggregateJobId);

  for (const id of requiredJobIds) {
    const job = jobs.find(j => j.id === id);
    if (!job) {
      throw new Error(`Required job "${id}" not found`);
    }
    const isAggregate = aggregateJobId !== null && id === aggregateJobId;

    if (!isAggregate) {
      const jobIf = extractJobIf(workflowText, id);
      if (jobIf !== null) {
        problems.push(`required job "${id}" has a job-level if:`);
      }
    }

    // continue-on-error is checked for EVERY required job including the
    // aggregate (checker B11): job-level or any step-level occurrence,
    // whatever its value, lets a rejected prerequisite still report success.
    const hasContinueOnError = job.lines.some(line => /\bcontinue-on-error\s*:/.test(line));
    if (hasContinueOnError) {
      problems.push(
        isAggregate ? `aggregate job "${id}" sets continue-on-error` : `required job "${id}" sets continue-on-error`
      );
    }

    if (isAggregate) {
      const aggregateIf = extractJobIf(workflowText, id);
      if (aggregateIf !== 'always()') {
        problems.push(`aggregate job "${id}" if: must be exactly always()`);
      }
    }

    // Any job or step shape the reader cannot parse is reported (fail
    // closed): an unread step could carry a condition nobody reviewed.
    const body = readJobBody(job.lines);
    for (const problem of body.problems) {
      problems.push(`required job "${id}" cannot be parsed for skip conditions: ${problem}`);
    }
    if (body.jobKeys.filter(entry => entry.key === 'if').length > 1) {
      problems.push(`required job "${id}" cannot be parsed for skip conditions: more than one job-level if`);
    }

    for (const step of body.steps) {
      for (const condition of step.conditions) {
        const allowlistKey = `${id}::${step.name}`;
        if (STEP_IF_ALLOWLIST[allowlistKey] !== condition) {
          problems.push(`required job "${id}" step if: not on the reviewed allowlist: "${step.name}": ${condition}`);
          continue;
        }
        const sameName = body.steps.filter(other => other.name === step.name).length;
        if (sameName !== 1) {
          problems.push(`required job "${id}" step "${step.name}": allowlisted step name appears ${sameName} times`);
        }
        if (!step.uses || !step.uses.startsWith(ALLOWLISTED_STEP_USES)) {
          problems.push(`required job "${id}" step "${step.name}": allowlisted step must use ${ALLOWLISTED_STEP_USES}`);
        }
        if (step.hasRun) {
          problems.push(`required job "${id}" step "${step.name}": allowlisted step must not have run:`);
        }
      }
    }
  }

  return problems;
}

// Simulates which required jobs would run for a given change
// {files, labels, title}. Path filters make a required job skippable when
// the change's files don't trigger it (paths: no match / paths-ignore: all
// match); any job-level if: other than none (and the aggregate's always())
// conservatively marks the job skippable for every change, since a
// condition the simulator cannot evaluate is treated as a possible skip.
function requiredJobsFor({workflowText, aggregateJobId = 'ci-ready', change}) {
  const jobs = parseJobs(workflowText);
  const requiredJobIds = resolveRequiredJobIds(jobs, aggregateJobId);
  const files = (change && change.files) || [];
  const skippable = new Set();

  const onBlock = parseOnBlock(workflowText);
  if (!onBlock.syntaxError) {
    for (const data of Object.values(onBlock.triggers)) {
      if (data.paths !== undefined) {
        const patterns = parseFlowList(data.paths);
        const anyMatch = files.some(file => patterns.some(pattern => globMatch(pattern, file)));
        if (!anyMatch) {
          requiredJobIds.forEach(id => skippable.add(id));
        }
      }
      if (data['paths-ignore'] !== undefined) {
        const patterns = parseFlowList(data['paths-ignore']);
        const allIgnored = files.length > 0 && files.every(file => patterns.some(pattern => globMatch(pattern, file)));
        if (allIgnored) {
          requiredJobIds.forEach(id => skippable.add(id));
        }
      }
    }
  }

  for (const id of requiredJobIds) {
    if (aggregateJobId !== null && id === aggregateJobId) continue;
    const jobIf = extractJobIf(workflowText, id);
    if (jobIf !== null) {
      skippable.add(id);
    }
  }

  return {runs: requiredJobIds, skippable: [...skippable]};
}

// A conservative simulator (used only to demonstrate the escape in tests):
// could the aggregate job conclude success although every job in
// failedNeeds actually failed? True when the aggregate (or any of its
// steps) sets continue-on-error, or when its needs don't even cover every
// failedNeeds job. False for the real ci-ready, whose validation step fails
// closed on any non-success result.
function aggregateCanPassWith({workflowText, aggregateJobId, failedNeeds}) {
  const jobs = parseJobs(workflowText);
  const aggregateJob = jobs.find(job => job.id === aggregateJobId);
  if (!aggregateJob) {
    throw new Error(`Aggregate job "${aggregateJobId}" not found`);
  }

  const needs = aggregateJob.needs || [];
  if (failedNeeds.some(id => !needs.includes(id))) {
    return true;
  }

  return aggregateJob.lines.some(line => /\bcontinue-on-error\s*:/.test(line));
}

module.exports = {
  parseJobs,
  extractCiReady,
  checkJobListConsistency,
  extractJobIf,
  findSkipConditions,
  requiredJobsFor,
  aggregateCanPassWith,
  STEP_IF_ALLOWLIST,
  TRIGGER_CONTRACTS,
};
