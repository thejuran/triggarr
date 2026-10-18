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

module.exports = {parseJobs, extractCiReady, checkJobListConsistency, extractJobIf};
