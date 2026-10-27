const {test} = require('node:test');
const assert = require('node:assert/strict');
const {parseReport, validateExceptions, classifyFindings, renderSummary, runCli} = require('./os-scan-gate.cjs');

// Fixed "today" for every call -- never Date.now() in these tests (D-10 math must be deterministic).
const TODAY = '2026-10-26';

// Small inline report builders (per plan action: report({vulns, os, extraResults})).
function vuln(overrides = {}) {
  return {
    VulnerabilityID: 'CVE-2026-0001',
    PkgName: 'openssl',
    InstalledVersion: '3.0.1',
    FixedVersion: '3.0.2',
    Severity: 'HIGH',
    Status: 'fixed',
    Title: 'Example vulnerability',
    ...overrides,
  };
}

function report({vulns = [], os = 'debian', extraResults = []} = {}) {
  return {
    SchemaVersion: 2,
    Metadata: {OS: {Family: os, Name: '13.1'}},
    Results: [
      {Target: 'rootfs', Class: 'os-pkgs', Type: os, Vulnerabilities: vulns},
      ...extraResults,
    ],
  };
}

function exceptionEntry(overrides = {}) {
  return {
    id: 'CVE-2026-0001',
    package: 'openssl',
    reason: 'Base image rebuild scheduled next monthly cycle.',
    approved_by: 'thejuran',
    approved_on: '2026-10-20',
    expires: '2026-11-15',
    ...overrides,
  };
}

function exceptionsFile(entries = []) {
  return {schema: 1, exceptions: entries};
}

const NO_EXCEPTIONS = {valid: [], expired: []};

// --- classifyFindings: severity/fix classification ---------------------------------------

test('HIGH with a fix blocks, naming the CVE, package, installed and fixed versions', () => {
  const r = report({vulns: [vuln({Severity: 'HIGH', FixedVersion: '3.0.2'})]});
  const result = classifyFindings({report: r, exceptions: NO_EXCEPTIONS, today: TODAY});
  assert.equal(result.blocking.length, 1);
  const entry = result.blocking[0];
  assert.equal(entry.id, 'CVE-2026-0001');
  assert.equal(entry.package, 'openssl');
  assert.equal(entry.installed, '3.0.1');
  assert.equal(entry.fixed, '3.0.2');
});

test('CRITICAL with no fix available is not blocking; it is reportedUnfixed', () => {
  const r = report({vulns: [vuln({Severity: 'CRITICAL', FixedVersion: ''})]});
  const result = classifyFindings({report: r, exceptions: NO_EXCEPTIONS, today: TODAY});
  assert.equal(result.blocking.length, 0);
  assert.equal(result.reportedUnfixed.length, 1);
  assert.equal(result.reportedUnfixed[0].id, 'CVE-2026-0001');
});

test('MEDIUM with a fix is not blocking; it is reportedOther', () => {
  const r = report({vulns: [vuln({Severity: 'MEDIUM', FixedVersion: '1.2.3'})]});
  const result = classifyFindings({report: r, exceptions: NO_EXCEPTIONS, today: TODAY});
  assert.equal(result.blocking.length, 0);
  assert.equal(result.reportedOther.length, 1);
});

test('a lang-pkgs result with a CRITICAL fixable finding is ignored, never blocking', () => {
  const r = report({
    vulns: [],
    extraResults: [
      {
        Target: 'app/requirements.txt',
        Class: 'lang-pkgs',
        Type: 'python-pkg',
        Vulnerabilities: [vuln({VulnerabilityID: 'CVE-2026-LANG', Severity: 'CRITICAL', FixedVersion: '9.9.9'})],
      },
    ],
  });
  const result = classifyFindings({report: r, exceptions: NO_EXCEPTIONS, today: TODAY});
  assert.equal(result.blocking.length, 0);
  assert.equal(result.ignoredNonOs.length, 1);
  assert.equal(result.ignoredNonOs[0].id, 'CVE-2026-LANG');
});

test('unknown severity strings are never dropped; they land in reportedOther', () => {
  const r = report({vulns: [vuln({Severity: 'weird-value', FixedVersion: '1.0.0'})]});
  const result = classifyFindings({report: r, exceptions: NO_EXCEPTIONS, today: TODAY});
  assert.equal(result.blocking.length, 0);
  assert.equal(result.reportedOther.length, 1);
});

test('severity comparison is case-insensitive', () => {
  const r = report({vulns: [vuln({Severity: 'high', FixedVersion: '3.0.2'})]});
  const result = classifyFindings({report: r, exceptions: NO_EXCEPTIONS, today: TODAY});
  assert.equal(result.blocking.length, 1);
});

// --- classifyFindings: exception matching -------------------------------------------------

test('a valid exception matching id+package excepts the finding and records its expiry', () => {
  const r = report({vulns: [vuln({Severity: 'HIGH', FixedVersion: '3.0.2'})]});
  const exception = exceptionEntry({approved_on: '2026-10-20', expires: '2026-11-15'});
  const result = classifyFindings({report: r, exceptions: {valid: [exception], expired: []}, today: TODAY});
  assert.equal(result.blocking.length, 0);
  assert.equal(result.excepted.length, 1);
  assert.equal(result.excepted[0].id, 'CVE-2026-0001');
  assert.equal(result.excepted[0].expires, '2026-11-15');
});

test('an exception for the same id but a different package does not except the finding', () => {
  const r = report({vulns: [vuln({Severity: 'HIGH', FixedVersion: '3.0.2'})]});
  const exception = exceptionEntry({package: 'curl'});
  const result = classifyFindings({report: r, exceptions: {valid: [exception], expired: []}, today: TODAY});
  assert.equal(result.blocking.length, 1);
  assert.equal(result.excepted.length, 0);
});

test('an expired exception stops suppressing: the finding blocks again and the id is listed as expired', () => {
  const r = report({vulns: [vuln({Severity: 'HIGH', FixedVersion: '3.0.2'})]});
  const exceptionsParsed = exceptionsFile([exceptionEntry({approved_on: '2026-09-26', expires: '2026-10-25'})]);
  const {valid, expired} = validateExceptions(exceptionsParsed, TODAY);
  assert.equal(valid.length, 0);
  assert.equal(expired.length, 1);
  const result = classifyFindings({report: r, exceptions: {valid, expired}, today: TODAY});
  assert.equal(result.blocking.length, 1);
  assert.deepEqual(result.expiredExceptions, ['CVE-2026-0001']);
});

// --- validateExceptions: structural and date validation (fails closed) --------------------

test('expires missing throws "no expiry"', () => {
  const exceptionsParsed = exceptionsFile([exceptionEntry({expires: undefined})]);
  assert.throws(() => validateExceptions(exceptionsParsed, TODAY), /no expiry/);
});

test('expires more than 30 days after approved_on throws "more than 30 days"', () => {
  const exceptionsParsed = exceptionsFile([exceptionEntry({approved_on: '2026-09-25', expires: '2026-10-26'})]);
  assert.throws(() => validateExceptions(exceptionsParsed, TODAY), /more than 30 days/);
});

test('expires more than 30 days after today throws "more than 30 days" even though approved_on is recent', () => {
  const exceptionsParsed = exceptionsFile([exceptionEntry({approved_on: '2026-10-26', expires: '2026-12-10'})]);
  assert.throws(() => validateExceptions(exceptionsParsed, TODAY), /more than 30 days/);
});

test('approved_on after today throws "approved_on is in the future"', () => {
  const exceptionsParsed = exceptionsFile([exceptionEntry({approved_on: '2026-10-27', expires: '2026-11-10'})]);
  assert.throws(() => validateExceptions(exceptionsParsed, TODAY), /approved_on is in the future/);
});

test('missing reason throws "missing required field"', () => {
  const exceptionsParsed = exceptionsFile([exceptionEntry({reason: undefined})]);
  assert.throws(() => validateExceptions(exceptionsParsed, TODAY), /missing required field/);
});

test('missing approved_by throws "missing required field"', () => {
  const exceptionsParsed = exceptionsFile([exceptionEntry({approved_by: undefined})]);
  assert.throws(() => validateExceptions(exceptionsParsed, TODAY), /missing required field/);
});

test('schema other than 1 throws "exceptions file"', () => {
  assert.throws(() => validateExceptions({schema: 2, exceptions: []}, TODAY), /exceptions file/);
});

test('exceptions not an array throws "exceptions file"', () => {
  assert.throws(() => validateExceptions({schema: 1, exceptions: {}}, TODAY), /exceptions file/);
});

test('an invalid date string throws "invalid date"', () => {
  const exceptionsParsed = exceptionsFile([exceptionEntry({expires: '2026-13-40'})]);
  assert.throws(() => validateExceptions(exceptionsParsed, TODAY), /invalid date/);
});

// --- parseReport: scanner errors fail closed (D-12) ----------------------------------------

test('non-JSON report text fails closed with "report is not valid JSON"', () => {
  assert.throws(() => parseReport('this is not json'), /scanner error: report is not valid JSON/);
});

test('SchemaVersion other than 2 fails closed with "unsupported SchemaVersion"', () => {
  const bad = JSON.stringify({
    SchemaVersion: 1,
    Metadata: {OS: {Family: 'debian'}},
    Results: [{Class: 'os-pkgs', Vulnerabilities: []}],
  });
  assert.throws(() => parseReport(bad), /scanner error: unsupported SchemaVersion/);
});

test('a missing Results array fails closed with "report has no Results"', () => {
  const bad = JSON.stringify({SchemaVersion: 2, Metadata: {OS: {Family: 'debian'}}});
  assert.throws(() => parseReport(bad), /scanner error: report has no Results/);
});

test('Results with no os-pkgs entry fails closed with "no OS-package result"', () => {
  const bad = JSON.stringify({
    SchemaVersion: 2,
    Metadata: {OS: {Family: 'debian'}},
    Results: [{Class: 'lang-pkgs', Vulnerabilities: []}],
  });
  assert.throws(() => parseReport(bad), /scanner error: no OS-package result/);
});

test('missing Metadata.OS.Family fails closed with "image OS was not detected"', () => {
  const bad = JSON.stringify({
    SchemaVersion: 2,
    Metadata: {OS: {}},
    Results: [{Class: 'os-pkgs', Vulnerabilities: []}],
  });
  assert.throws(() => parseReport(bad), /scanner error: image OS was not detected/);
});

test('a clean os-pkgs result parses even when it omits Vulnerabilities entirely', () => {
  const clean = JSON.stringify({
    SchemaVersion: 2,
    Metadata: {OS: {Family: 'debian', Name: '13.1'}},
    Results: [{Target: 'rootfs', Class: 'os-pkgs', Type: 'debian'}],
  });
  const parsed = parseReport(clean);
  assert.equal(parsed.Metadata.OS.Family, 'debian');
});

// --- renderSummary: nothing dropped ---------------------------------------------------------

test('renderSummary includes every finding id across all buckets, and the counts', () => {
  const result = {
    blocking: [{id: 'CVE-BLOCK', package: 'openssl', installed: '1.0.0', fixed: '1.0.1', severity: 'HIGH'}],
    excepted: [
      {id: 'CVE-EXCEPT', package: 'curl', installed: '7.0', fixed: '7.1', severity: 'CRITICAL', expires: '2026-11-01'},
    ],
    expiredExceptions: ['CVE-EXPIRED'],
    reportedUnfixed: [{id: 'CVE-UNFIXED', package: 'zlib', installed: '1.2', fixed: '', severity: 'CRITICAL'}],
    reportedOther: [{id: 'CVE-OTHER', package: 'bash', installed: '5.0', fixed: '5.1', severity: 'MEDIUM'}],
    ignoredNonOs: [{id: 'CVE-LANG', package: 'requests', installed: '2.0', fixed: '2.1', severity: 'CRITICAL'}],
  };
  const summary = renderSummary(result, {today: TODAY, trivyVersion: '0.69.0'});
  for (const id of ['CVE-BLOCK', 'CVE-EXCEPT', 'CVE-EXPIRED', 'CVE-UNFIXED', 'CVE-OTHER', 'CVE-LANG']) {
    assert.ok(summary.includes(id), `summary is missing finding id ${id}`);
  }
  assert.match(summary, /OS-package scan/);
  assert.match(summary, /blocking.*1/i);
  assert.match(summary, /Policy: docs\/os-scan-policy\.md/);
});

// --- runCli: exit codes and injectable IO ---------------------------------------------------

function fakeIo({reportText, exceptionsText}) {
  const summaries = [];
  const stderrLines = [];
  return {
    io: {
      readFile: p => (p === 'report.json' ? reportText : exceptionsText),
      writeSummary: (p, content) => summaries.push({path: p, content}),
      stderr: msg => stderrLines.push(msg),
    },
    summaries,
    stderrLines,
  };
}

test('runCli exits 1 with "blocking" in stderr when blocking is non-empty', () => {
  const reportText = JSON.stringify(report({vulns: [vuln({Severity: 'HIGH', FixedVersion: '1.0.1'})]}));
  const exceptionsText = JSON.stringify(exceptionsFile([]));
  const {io, stderrLines, summaries} = fakeIo({reportText, exceptionsText});
  const code = runCli(['--report', 'report.json', '--exceptions', 'exceptions.json', '--today', TODAY], io);
  assert.equal(code, 1);
  assert.ok(stderrLines.some(l => l.includes('blocking')));
  assert.equal(summaries.length, 1, 'summary must still be written on a blocked run');
});

test('runCli exits 0 when only reported (non-blocking) findings exist', () => {
  const reportText = JSON.stringify(report({vulns: [vuln({Severity: 'MEDIUM', FixedVersion: '1.0.1'})]}));
  const exceptionsText = JSON.stringify(exceptionsFile([]));
  const {io} = fakeIo({reportText, exceptionsText});
  const code = runCli(['--report', 'report.json', '--exceptions', 'exceptions.json', '--today', TODAY], io);
  assert.equal(code, 0);
});

test('runCli exits 1 for a scanner error (fails closed)', () => {
  const {io} = fakeIo({reportText: 'not json at all', exceptionsText: JSON.stringify(exceptionsFile([]))});
  const code = runCli(['--report', 'report.json', '--exceptions', 'exceptions.json', '--today', TODAY], io);
  assert.equal(code, 1);
});

test('runCli exits 1 for an invalid exceptions file (fails closed)', () => {
  const reportText = JSON.stringify(report({vulns: [vuln({Severity: 'MEDIUM'})]}));
  const {io} = fakeIo({reportText, exceptionsText: JSON.stringify({schema: 2, exceptions: []})});
  const code = runCli(['--report', 'report.json', '--exceptions', 'exceptions.json', '--today', TODAY], io);
  assert.equal(code, 1);
});
