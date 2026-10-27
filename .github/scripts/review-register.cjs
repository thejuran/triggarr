// Writes REVIEW_DISPOSITIONS/REVIEW_BLOCKERS (see review-acceptance.cjs's schema-2
// shape) with a read-back check after every write.
//
// GitHub repository variables have no compare-and-swap: `gh variable set` always
// overwrites the whole value. The read-back check in this file detects some lost
// updates (a stale-base writer whose own slice never lands, or another slice that
// changed or disappeared underneath it) but not all of them -- two writers racing
// between this script's own read and write can still both report success while one
// overwrites the other. Final acceptance updates therefore stay serialized
// (docs/owner-cli-acceptance.md), and the readiness check re-reads the register
// immediately before approval is requested.
//
// Register content (dispositions, blocker ids) is evidence text, not a secret, but
// this script never prints `gh`'s own auth output -- only the JSON it reads/writes.

const {execFileSync: defaultExecFileSync} = require('node:child_process');
const fs = require('node:fs');

const {registerKey} = require('./review-acceptance.cjs');

const KIND_VARIABLES = {dispositions: 'REVIEW_DISPOSITIONS', blockers: 'REVIEW_BLOCKERS'};
const HEAD_RE = /^[0-9a-f]{40}$/;
const PR_ARG_RE = /^[1-9][0-9]*$/;

function isPositiveInteger(value) {
  return Number.isSafeInteger(value) && value > 0;
}

function validateSlice(kind, slice) {
  if (kind === 'dispositions') {
    if (!slice || typeof slice.items !== 'object' || slice.items === null || Array.isArray(slice.items)) {
      throw new Error('Invalid dispositions slice: expected {items: object}');
    }
    return;
  }
  if (kind === 'blockers') {
    if (!slice || !Array.isArray(slice.open) || !slice.open.every(entry => typeof entry === 'string')) {
      throw new Error('Invalid blockers slice: expected {open: string[]}');
    }
    return;
  }
  throw new Error(`Invalid register kind: ${JSON.stringify(kind)} (expected "dispositions" or "blockers")`);
}

// Pure: returns a cloned register with by_pr_head[registerKey(prNumber, head)] set to
// slice. Never mutates register or slice.
function upsertSlice(register, {kind, prNumber, head, slice}) {
  if (!Object.hasOwn(KIND_VARIABLES, kind)) {
    throw new Error(`Invalid register kind: ${JSON.stringify(kind)} (expected "dispositions" or "blockers")`);
  }
  if (!isPositiveInteger(prNumber)) throw new Error('Invalid PR number');
  if (!HEAD_RE.test(head || '')) throw new Error('Invalid head SHA (expected 40 hex characters)');
  validateSlice(kind, slice);
  if (!register || register.schema !== 2) {
    throw new Error('Register schema must be 2 (migrate schema 1 with migrateSchema1 first)');
  }

  const next = structuredClone(register);
  if (typeof next.by_pr_head !== 'object' || next.by_pr_head === null) next.by_pr_head = {};
  next.by_pr_head[registerKey(prNumber, head)] = structuredClone(slice);
  return next;
}

// Pure: compares before (the register this writer read), written (what this writer
// computed), and readBack (the register actually read back after the write) and
// returns a problems array (empty = clean). Detects, but cannot always detect, a
// lost update -- see the header comment.
function verifyWrite({before, written, readBack, key}) {
  const problems = [];
  const beforeMap = before?.by_pr_head ?? {};
  const writtenMap = written?.by_pr_head ?? {};
  const readBackMap = readBack?.by_pr_head ?? {};

  if (!Object.hasOwn(readBackMap, key)) {
    problems.push(`own slice missing after write: ${key}`);
  } else if (JSON.stringify(readBackMap[key]) !== JSON.stringify(writtenMap[key])) {
    problems.push(`own slice differs from what was written: ${key}`);
  }

  for (const otherKey of Object.keys(beforeMap)) {
    if (otherKey === key) continue;
    if (!Object.hasOwn(readBackMap, otherKey)) {
      problems.push(`another slice disappeared: ${otherKey}`);
    } else if (JSON.stringify(readBackMap[otherKey]) !== JSON.stringify(beforeMap[otherKey])) {
      problems.push(`another slice changed: ${otherKey}`);
    }
  }

  return problems;
}

// Pure: migrates a schema-1 register to schema 2 with its original content
// preserved verbatim under archived_schema1. Throws on anything that is not a
// schema-1 register for the given kind.
function migrateSchema1(kind, old) {
  if (!Object.hasOwn(KIND_VARIABLES, kind)) {
    throw new Error(`Invalid register kind: ${JSON.stringify(kind)} (expected "dispositions" or "blockers")`);
  }
  if (!old || old.schema !== 1) {
    throw new Error(`migrateSchema1 refused: input is not a schema-1 register (schema=${JSON.stringify(old?.schema)})`);
  }
  if (kind === 'dispositions') {
    if (typeof old.items !== 'object' || old.items === null) {
      throw new Error('migrateSchema1 refused: schema-1 dispositions register is missing an items object');
    }
    return {schema: 2, by_pr_head: {}, archived_schema1: structuredClone(old)};
  }
  if (!Array.isArray(old.open)) {
    throw new Error('migrateSchema1 refused: schema-1 blockers register is missing an open array');
  }
  return {schema: 2, global_open: structuredClone(old.open), by_pr_head: {}, archived_schema1: structuredClone(old)};
}

// Parses CLI arguments without ever invoking a subprocess. Throws (rejects) before
// any exec call for every invalid argument, including injection attempts.
function parseArgs(argv) {
  const [subcommand, ...rest] = argv;
  if (subcommand !== 'upsert' && subcommand !== 'migrate') {
    throw new Error(`Unknown subcommand: ${JSON.stringify(subcommand)} (expected "upsert" or "migrate")`);
  }

  const opts = {subcommand, apply: false};
  for (let i = 0; i < rest.length; i++) {
    const arg = rest[i];
    switch (arg) {
      case '--kind':
        opts.kind = rest[++i];
        break;
      case '--pr':
        opts.prRaw = rest[++i];
        break;
      case '--head':
        opts.head = rest[++i];
        break;
      case '--slice-file':
        opts.sliceFile = rest[++i];
        break;
      case '--apply':
        opts.apply = true;
        break;
      default:
        throw new Error(`Unknown argument: ${JSON.stringify(arg)}`);
    }
  }

  if (!Object.hasOwn(KIND_VARIABLES, opts.kind)) {
    throw new Error(`Invalid --kind: ${JSON.stringify(opts.kind)} (expected "dispositions" or "blockers")`);
  }

  if (subcommand === 'upsert') {
    if (!PR_ARG_RE.test(opts.prRaw || '')) {
      throw new Error(`Invalid --pr: ${JSON.stringify(opts.prRaw)} (expected a positive integer)`);
    }
    opts.prNumber = Number(opts.prRaw);
    if (!HEAD_RE.test(opts.head || '')) {
      throw new Error(`Invalid --head: ${JSON.stringify(opts.head)} (expected 40 hex characters)`);
    }
    if (!opts.sliceFile) {
      throw new Error('upsert requires --slice-file <path>');
    }
  }

  return opts;
}

function readRegister(execFileSync, name) {
  const text = execFileSync('gh', ['variable', 'get', name], {encoding: 'utf8'});
  try {
    return JSON.parse(text);
  } catch (err) {
    throw new Error(`Could not parse ${name} as JSON: ${err.message}`);
  }
}

function writeRegister(execFileSync, name, register) {
  execFileSync('gh', ['variable', 'set', name, '--body', JSON.stringify(register)], {encoding: 'utf8'});
}

function runUpsert(opts, execFileSync) {
  const name = KIND_VARIABLES[opts.kind];
  let slice;
  try {
    slice = JSON.parse(fs.readFileSync(opts.sliceFile, 'utf8'));
  } catch (err) {
    console.error(`Could not read --slice-file ${opts.sliceFile}: ${err.message}`);
    return 1;
  }

  let before;
  try {
    before = readRegister(execFileSync, name);
  } catch (err) {
    console.error(err.message);
    return 1;
  }

  let written;
  try {
    written = upsertSlice(before, {kind: opts.kind, prNumber: opts.prNumber, head: opts.head, slice});
  } catch (err) {
    console.error(err.message);
    return 1;
  }

  const key = registerKey(opts.prNumber, opts.head);
  if (!opts.apply) {
    console.log(`Dry run -- would write ${name} slice ${key}:`);
    console.log(JSON.stringify(written));
    return 0;
  }

  writeRegister(execFileSync, name, written);

  let readBack;
  try {
    readBack = readRegister(execFileSync, name);
  } catch (err) {
    console.error(err.message);
    return 1;
  }

  const problems = verifyWrite({before, written, readBack, key});
  if (problems.length) {
    for (const problem of problems) console.error(`Write verification problem: ${problem}`);
    return 1;
  }
  console.log(`Wrote and verified ${name} slice ${key}.`);
  return 0;
}

function runMigrate(opts, execFileSync) {
  const name = KIND_VARIABLES[opts.kind];

  let before;
  try {
    before = readRegister(execFileSync, name);
  } catch (err) {
    console.error(err.message);
    return 1;
  }

  let migrated;
  try {
    migrated = migrateSchema1(opts.kind, before);
  } catch (err) {
    console.error(err.message);
    return 1;
  }

  if (!opts.apply) {
    console.log(`Dry run -- would migrate ${name} to schema 2:`);
    console.log(JSON.stringify(migrated));
    return 0;
  }

  writeRegister(execFileSync, name, migrated);

  let readBack;
  try {
    readBack = readRegister(execFileSync, name);
  } catch (err) {
    console.error(err.message);
    return 1;
  }

  if (JSON.stringify(readBack) !== JSON.stringify(migrated)) {
    console.error(`Write verification problem: migrated register differs from read-back for ${name}`);
    return 1;
  }
  console.log(`Migrated and verified ${name} to schema 2.`);
  return 0;
}

// CLI entry point. argv is the subcommand + flag list (no node/script path).
// The exec option defaults to node:child_process's execFileSync and is injectable
// for tests; every gh invocation passes an argument array, never a shell string.
function runCli(argv, {exec: execFileSync = defaultExecFileSync} = {}) {
  let opts;
  try {
    opts = parseArgs(argv);
  } catch (err) {
    console.error(err.message);
    return 1;
  }

  if (opts.subcommand === 'migrate') return runMigrate(opts, execFileSync);
  return runUpsert(opts, execFileSync);
}

if (require.main === module) {
  process.exitCode = runCli(process.argv.slice(2));
}

module.exports = {upsertSlice, verifyWrite, migrateSchema1, runCli};
