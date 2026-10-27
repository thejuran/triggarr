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

// Returns a job's 4-space `if:` condition, whitespace-normalized to single
// spaces, supporting both a single-line value and a folded `>-`/`|` block.
// Returns null if the job has no `if:`.
function extractJobIf(text, jobId) {
  const jobs = parseJobs(text);
  const job = jobs.find(j => j.id === jobId);
  if (!job) {
    throw new Error(`Job "${jobId}" not found`);
  }

  for (let i = 0; i < job.lines.length; i++) {
    const line = job.lines[i];
    const singleMatch = line.match(/^    if:\s*(.+?)\s*$/);
    if (!singleMatch) continue;

    const value = singleMatch[1];
    if (/^[>|][-+]?$/.test(value)) {
      const collected = [];
      for (let j = i + 1; j < job.lines.length; j++) {
        const continuation = job.lines[j];
        if (/^\s*$/.test(continuation)) continue;
        if (!/^      /.test(continuation)) break; // dedent back to job-key level ends the block
        collected.push(continuation.trim());
      }
      return collected.join(' ').replace(/\s+/g, ' ').trim();
    }

    return value.replace(/\s+/g, ' ').trim();
  }

  return null;
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
      const keyMatch = line.match(/^    ([A-Za-z0-9_-]+):\s*(.*)$/);
      if (keyMatch) {
        triggers[currentTrigger][keyMatch[1]] = keyMatch[2];
      }
    }
  }

  return {triggers};
}

// Collects every step-level `if:` inside a job's raw lines, paired with
// that step's `name:` (single-line or folded `>-`/`|` block, normalized
// like extractJobIf). Steps with no `if:` are omitted.
function extractStepIfs(jobLines) {
  const steps = [];
  let current = null;
  for (let i = 0; i < jobLines.length; i++) {
    const line = jobLines[i];
    if (/^      - /.test(line)) {
      current = {name: null, condition: null};
      steps.push(current);
    }
    if (!current) continue;

    const nameMatch = line.match(/^      - name:\s*(.+?)\s*$/) || line.match(/^        name:\s*(.+?)\s*$/);
    if (nameMatch) {
      current.name = stripQuotes(nameMatch[1]);
      continue;
    }

    // `if:` is a step key either on its own 8-space line or as the first key
    // on the step-start line (`      - if: false`); a quoted key is the same
    // key to YAML. An empty value (scalar on the following lines) is read
    // like a block so it can never slip past as "no condition".
    const ifMatch = line.match(/^(?:      - |        )(?:if|"if"|'if'):(?:\s+(.*?))?\s*$/);
    if (ifMatch && current.condition === null) {
      const value = ifMatch[1] || '';
      if (value === '' || /^[>|][-+]?$/.test(value)) {
        const collected = [];
        for (let j = i + 1; j < jobLines.length; j++) {
          const continuation = jobLines[j];
          if (/^\s*$/.test(continuation)) continue;
          if (!/^          /.test(continuation)) break; // dedent ends the folded block
          collected.push(continuation.trim());
        }
        current.condition = collected.join(' ').replace(/\s+/g, ' ').trim();
      } else {
        current.condition = value.replace(/\s+/g, ' ').trim();
      }
    }
  }

  return steps.filter(step => step.condition !== null);
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

    for (const step of extractStepIfs(job.lines)) {
      const allowlistKey = `${id}::${step.name}`;
      if (STEP_IF_ALLOWLIST[allowlistKey] !== step.condition) {
        problems.push(
          `required job "${id}" step if: not on the reviewed allowlist: "${step.name}": ${step.condition}`
        );
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
