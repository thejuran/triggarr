// Classifies one full, unfiltered Trivy JSON report (--pkg-types os, with no
// result-filtering flags at all) into blocking vs. reporting buckets under
// the OS-scan policy (docs/os-scan-policy.md, D-08..D-12). Node stdlib only:
// fs is required lazily inside the CLI's default IO so the pure
// classification functions stay dependency-free, in the same style as
// ci-job-consistency.cjs.

const REQUIRED_EXCEPTION_FIELDS = ['id', 'package', 'reason', 'approved_by', 'approved_on'];
const STRICT_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const MS_PER_DAY = 24 * 60 * 60 * 1000;

// Parses a strict YYYY-MM-DD string to a UTC millisecond timestamp, rejecting
// any string that doesn't round-trip exactly (catches e.g. "2026-13-40",
// which Date.UTC would otherwise silently roll over into a different date).
function parseStrictDateUTC(value) {
  if (typeof value !== 'string' || !STRICT_DATE_RE.test(value)) return null;
  const [year, month, day] = value.split('-').map(Number);
  const ms = Date.UTC(year, month - 1, day);
  const roundTrip = new Date(ms);
  if (roundTrip.getUTCFullYear() !== year || roundTrip.getUTCMonth() !== month - 1 || roundTrip.getUTCDate() !== day) {
    return null;
  }
  return ms;
}

// Parses + structurally validates a Trivy JSON report, throwing a
// "scanner error: ..." message for every failure mode so the caller can
// fail the job closed rather than silently treating a hollow scan as clean
// (D-12, T-85-20).
function parseReport(text) {
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error('scanner error: report is not valid JSON');
  }
  if (!parsed || parsed.SchemaVersion !== 2) {
    throw new Error('scanner error: unsupported SchemaVersion');
  }
  if (!Array.isArray(parsed.Results)) {
    throw new Error('scanner error: report has no Results');
  }
  const hasOsPkgs = parsed.Results.some(result => result && result.Class === 'os-pkgs');
  if (!hasOsPkgs) {
    throw new Error('scanner error: no OS-package result');
  }
  const family = parsed.Metadata && parsed.Metadata.OS && parsed.Metadata.OS.Family;
  if (typeof family !== 'string' || family.trim() === '') {
    throw new Error('scanner error: image OS was not detected');
  }
  return parsed;
}

// Validates the custom exceptions register (schema 1) against D-10: every
// entry needs id/package/reason/approved_by/approved_on/expires, approved_on
// can't be in the future, and expires must be within 30 days of both
// approved_on and today. A well-formed but now-past-expiry entry is not an
// error -- it moves to the `expired` bucket so classifyFindings re-blocks its
// finding instead of the whole file failing closed.
function validateExceptions(parsed, today) {
  if (!parsed || parsed.schema !== 1 || !Array.isArray(parsed.exceptions)) {
    throw new Error('exceptions file: schema must be 1 with an "exceptions" array');
  }
  const todayMs = parseStrictDateUTC(today);
  if (todayMs === null) {
    throw new Error(`exceptions file: invalid date for "today": ${JSON.stringify(today)}`);
  }

  const valid = [];
  const expired = [];
  for (const entry of parsed.exceptions) {
    const id = (entry && entry.id) || '?';
    for (const field of REQUIRED_EXCEPTION_FIELDS) {
      if (!entry || !entry[field]) {
        throw new Error(`exceptions file: ${id}: missing required field "${field}"`);
      }
    }
    if (!entry.expires) {
      throw new Error(`exceptions file: ${id}: no expiry`);
    }

    const approvedMs = parseStrictDateUTC(entry.approved_on);
    if (approvedMs === null) {
      throw new Error(`exceptions file: ${id}: invalid date in "approved_on"`);
    }
    const expiresMs = parseStrictDateUTC(entry.expires);
    if (expiresMs === null) {
      throw new Error(`exceptions file: ${id}: invalid date in "expires"`);
    }

    if (approvedMs > todayMs) {
      throw new Error(`exceptions file: ${id}: approved_on is in the future`);
    }

    const daysFromApproval = (expiresMs - approvedMs) / MS_PER_DAY;
    if (daysFromApproval > 30) {
      throw new Error(`exceptions file: ${id}: expires more than 30 days after approved_on`);
    }
    const daysFromToday = (expiresMs - todayMs) / MS_PER_DAY;
    if (daysFromToday > 30) {
      throw new Error(`exceptions file: ${id}: expires more than 30 days after today`);
    }

    if (expiresMs < todayMs) {
      expired.push(entry);
    } else {
      valid.push(entry);
    }
  }
  return {valid, expired};
}

function hasFixAvailable(vuln) {
  return typeof vuln.FixedVersion === 'string' && vuln.FixedVersion.trim() !== '';
}

function isBlockingSeverity(severity) {
  const upper = (severity || '').toUpperCase();
  return upper === 'CRITICAL' || upper === 'HIGH';
}

function findMatchingException(entries, id, pkg) {
  return entries.find(entry => entry.id === id && entry.package === pkg);
}

// Classifies every finding in the report into exactly one bucket. Never
// filters a result before classifying it (a status-filtering Trivy flag
// would silently drop unfixed Critical/High findings, violating D-09) --
// every finding from every Results entry lands somewhere.
function classifyFindings({report, exceptions, today}) {
  const blocking = [];
  const excepted = [];
  const expiredExceptions = [];
  const reportedUnfixed = [];
  const reportedOther = [];
  const ignoredNonOs = [];

  const validExceptions = (exceptions && exceptions.valid) || [];
  const expiredEntries = (exceptions && exceptions.expired) || [];

  for (const result of report.Results || []) {
    const vulnerabilities = result.Vulnerabilities || [];
    for (const vuln of vulnerabilities) {
      const entry = {
        id: vuln.VulnerabilityID,
        package: vuln.PkgName,
        installed: vuln.InstalledVersion,
        fixed: typeof vuln.FixedVersion === 'string' ? vuln.FixedVersion : '',
        severity: (vuln.Severity || 'UNKNOWN').toUpperCase(),
      };

      if (result.Class !== 'os-pkgs') {
        ignoredNonOs.push(entry);
        continue;
      }

      const blockingSeverity = isBlockingSeverity(entry.severity);
      const fixed = hasFixAvailable(vuln);

      if (!blockingSeverity) {
        reportedOther.push(entry);
        continue;
      }
      if (!fixed) {
        reportedUnfixed.push(entry);
        continue;
      }

      const validMatch = findMatchingException(validExceptions, entry.id, entry.package);
      if (validMatch) {
        excepted.push({...entry, expires: validMatch.expires});
        continue;
      }

      const expiredMatch = findMatchingException(expiredEntries, entry.id, entry.package);
      if (expiredMatch) {
        expiredExceptions.push(entry.id);
      }
      blocking.push(entry);
    }
  }

  return {blocking, excepted, expiredExceptions, reportedUnfixed, reportedOther, ignoredNonOs};
}

function renderTable(lines, label, entries, withExpiry) {
  if (!entries.length) return;
  lines.push(`### ${label}`);
  lines.push('');
  lines.push(
    withExpiry
      ? '| ID | Package | Installed | Fixed | Severity | Exception expiry |'
      : '| ID | Package | Installed | Fixed | Severity |'
  );
  lines.push(withExpiry ? '|----|---------|-----------|-------|----------|-------------------|' : '|----|---------|-----------|-------|----------|');
  for (const entry of entries) {
    const row = [entry.id, entry.package, entry.installed, entry.fixed || '(none)', entry.severity];
    if (withExpiry) row.push(entry.expires || '');
    lines.push(`| ${row.join(' | ')} |`);
  }
  lines.push('');
}

// Renders the full classification result as markdown. Every bucket gets its
// own section (when non-empty) so nothing found by the scan is ever hidden
// from reviewers, even a blocked run's unfixed/other/ignored findings
// (T-85-22).
function renderSummary(result, {today, trivyVersion} = {}) {
  const lines = [];
  lines.push('## OS-package scan');
  lines.push('');
  if (today || trivyVersion) {
    lines.push(`Scanned: ${today || 'unknown date'}${trivyVersion ? ` (Trivy ${trivyVersion})` : ''}`);
    lines.push('');
  }
  lines.push(
    [
      `blocking: ${result.blocking.length}`,
      `excepted: ${result.excepted.length}`,
      `expired exceptions: ${result.expiredExceptions.length}`,
      `reported unfixed: ${result.reportedUnfixed.length}`,
      `reported other: ${result.reportedOther.length}`,
      `ignored non-OS: ${result.ignoredNonOs.length}`,
    ].join(', ')
  );
  lines.push('');

  renderTable(lines, 'Blocking', result.blocking, false);
  renderTable(lines, 'Excepted', result.excepted, true);
  if (result.expiredExceptions.length) {
    lines.push('### Expired exceptions (no longer suppressing; finding now blocks)');
    lines.push('');
    lines.push(result.expiredExceptions.join(', '));
    lines.push('');
  }
  renderTable(lines, 'Reported (unfixed)', result.reportedUnfixed, false);
  renderTable(lines, 'Reported (other)', result.reportedOther, false);
  renderTable(lines, 'Ignored (non-OS)', result.ignoredNonOs, false);

  lines.push('Policy: docs/os-scan-policy.md');
  return lines.join('\n');
}

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    if (token.startsWith('--')) {
      args[token.slice(2)] = argv[i + 1];
      i++;
    }
  }
  return args;
}

function defaultIo() {
  const fs = require('node:fs');
  return {
    readFile: path => fs.readFileSync(path, 'utf8'),
    writeSummary: (path, content) => {
      if (path) fs.writeFileSync(path, content);
    },
    stderr: message => {
      process.stderr.write(`${message}\n`);
    },
  };
}

// CLI entry point: --report <path> --exceptions <path> [--today YYYY-MM-DD]
// [--summary <path>] [--trivy-version <v>]. Writes the summary before
// returning so a blocked run still shows everything it found, then exits 1
// for a non-empty blocking bucket, a scanner error, or an invalid exceptions
// file -- 0 otherwise.
function runCli(argv, io = defaultIo()) {
  const args = parseArgs(argv);
  const today = args.today || new Date().toISOString().slice(0, 10);

  let reportText;
  let exceptionsText;
  try {
    reportText = io.readFile(args.report);
  } catch (err) {
    io.stderr(`OS-package scan: failed to read report file: ${err.message}`);
    return 1;
  }
  try {
    exceptionsText = io.readFile(args.exceptions);
  } catch (err) {
    io.stderr(`OS-package scan: failed to read exceptions file: ${err.message}`);
    return 1;
  }

  let report;
  try {
    report = parseReport(reportText);
  } catch (err) {
    io.stderr(`OS-package scan: ${err.message}`);
    return 1;
  }

  let exceptionsParsed;
  try {
    exceptionsParsed = JSON.parse(exceptionsText);
  } catch {
    io.stderr('OS-package scan: exceptions file: report is not valid JSON');
    return 1;
  }

  let validated;
  try {
    validated = validateExceptions(exceptionsParsed, today);
  } catch (err) {
    io.stderr(`OS-package scan: ${err.message}`);
    return 1;
  }

  const result = classifyFindings({report, exceptions: validated, today});
  const summary = renderSummary(result, {today, trivyVersion: args['trivy-version']});
  io.writeSummary(args.summary, summary);

  if (result.blocking.length > 0) {
    io.stderr(`OS-package scan: ${result.blocking.length} blocking finding(s)`);
    return 1;
  }
  return 0;
}

if (require.main === module) {
  process.exitCode = runCli(process.argv.slice(2));
}

module.exports = {parseReport, validateExceptions, classifyFindings, renderSummary, runCli};
