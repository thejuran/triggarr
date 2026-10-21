const {test} = require('node:test');
const assert = require('node:assert/strict');
const {rehearseReleaseIdentity} = require('./release-identity-rehearsal.cjs');
const {releaseIdentityGate, parseReleaseTag} = require('./release-policy.cjs');

const SHA = 'a'.repeat(40);
const IMAGE_ID = `sha256:${'0'.repeat(64)}`;
const PYPROJECT_212 = '[project]\nname = "demo"\nversion = "2.12.0"\n';

test('rehearseReleaseIdentity resolves the image/sha header plus matching, mismatched, malformed and missing case lines', async () => {
  const lines = await rehearseReleaseIdentity({
    pyprojectText: PYPROJECT_212,
    sha: SHA,
    imageVersion: '2.12.0',
    imageId: IMAGE_ID,
  });
  assert.equal(lines.length, 5);
  assert.match(lines[0], new RegExp(IMAGE_ID.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  assert.match(lines[0], new RegExp(SHA));
  assert.equal(lines[1], 'matching: accepted 2.12.0');
  assert.equal(lines[2], 'mismatched: rejected as expected (disagree)');
  assert.equal(lines[3], 'malformed: rejected as expected (malformed)');
  assert.equal(lines[4], 'missing: rejected as expected (missing)');
});

test('every case invokes releaseIdentityGate, and the malformed case also invokes parseReleaseTag, both rejecting with /malformed/', async () => {
  const gateCalls = [];
  const spyGate = async args => {
    try {
      const result = await releaseIdentityGate(args);
      gateCalls.push({ref: args.context.ref, result});
      return result;
    } catch (err) {
      gateCalls.push({ref: args.context.ref, error: err.message});
      throw err;
    }
  };
  const parseTagCalls = [];
  const spyParseTag = ref => {
    parseTagCalls.push(ref);
    return parseReleaseTag(ref);
  };

  const lines = await rehearseReleaseIdentity({
    pyprojectText: PYPROJECT_212,
    sha: SHA,
    imageVersion: '2.12.0',
    imageId: IMAGE_ID,
    gate: spyGate,
    parseTag: spyParseTag,
  });

  assert.equal(gateCalls.length, 4, 'releaseIdentityGate must be invoked for matching, mismatched, malformed and missing');
  assert.equal(parseTagCalls.length, 1, 'parseReleaseTag must be invoked for the malformed case');
  assert.match(parseTagCalls[0], /-rc1$/);

  assert.equal(gateCalls[0].result, '2.12.0');
  assert.match(gateCalls[1].error, /disagree/);
  assert.match(gateCalls[2].error, /malformed/);
  assert.match(gateCalls[3].error, /missing/);
  assert.match(gateCalls[3].error, /image: missing/);

  assert.equal(lines[1], 'matching: accepted 2.12.0');
});

test('gate exercises its own pyproject.toml parsing via the contents API, not a hardcoded value', async () => {
  const pyprojectText = '[project]\nname = "demo"\nversion = "9.9.9"\n';
  const lines = await rehearseReleaseIdentity({
    pyprojectText,
    sha: SHA,
    imageVersion: '9.9.9',
    imageId: IMAGE_ID,
  });
  assert.equal(lines[1], 'matching: accepted 9.9.9');
});

test('a dev/pre-release package version skips the matching, mismatched and missing cases instead of failing', async () => {
  for (const devVersion of ['2.13.0.dev0', '2.6.1-dev']) {
    const pyprojectText = `[project]\nname = "demo"\nversion = "${devVersion}"\n`;
    const lines = await rehearseReleaseIdentity({pyprojectText, sha: SHA, imageVersion: devVersion, imageId: IMAGE_ID});
    assert.equal(lines.length, 5);
    assert.match(lines[1], /^matching: skipped \(package version .* is not a releasable X\.Y\.Z version\)$/);
    assert.match(lines[2], /^mismatched: skipped /);
    assert.equal(lines[3], 'malformed: rejected as expected (malformed)');
    assert.match(lines[4], /^missing: skipped /);
  }
});

test('a dev/pre-release package version still rejects a missing or mismatched image version label', async () => {
  for (const devVersion of ['2.13.0.dev0', '2.6.1-dev']) {
    const pyprojectText = `[project]\nname = "demo"\nversion = "${devVersion}"\n`;
    for (const badImageVersion of [undefined, '']) {
      await assert.rejects(
        rehearseReleaseIdentity({pyprojectText, sha: SHA, imageVersion: badImageVersion, imageId: IMAGE_ID}),
        /image version label is missing/
      );
    }
    for (const badImageVersion of ['9.9.9', '2.13.0', `${devVersion}x`]) {
      await assert.rejects(
        rehearseReleaseIdentity({pyprojectText, sha: SHA, imageVersion: badImageVersion, imageId: IMAGE_ID}),
        /disagrees with package version/
      );
    }
  }
});

test('an image label drifted from the package version rejects matching as "matching tag was not accepted"', async () => {
  await assert.rejects(
    rehearseReleaseIdentity({pyprojectText: PYPROJECT_212, sha: SHA, imageVersion: '2.12.1', imageId: IMAGE_ID}),
    /matching tag was not accepted/
  );
});

test('rehearseReleaseIdentity refuses to run without a valid audited image identity, before any case runs', async () => {
  for (const badImageId of [undefined, '', 'sha256:abc', 'not-an-id', `sha256:${'0'.repeat(63)}`]) {
    await assert.rejects(
      rehearseReleaseIdentity({pyprojectText: PYPROJECT_212, sha: SHA, imageVersion: '2.12.0', imageId: badImageId}),
      /image identity/
    );
  }
});

test('a stubbed gate that accepts everything causes rehearseReleaseIdentity to reject with "expected rejection did not occur"', async () => {
  const packageVersion = '2.12.0';
  const acceptAllGate = async () => packageVersion;
  await assert.rejects(
    rehearseReleaseIdentity({pyprojectText: PYPROJECT_212, sha: SHA, imageVersion: '2.12.0', imageId: IMAGE_ID, gate: acceptAllGate}),
    /expected rejection did not occur/
  );
});

test('a stubbed gate that rejects the mismatch with an unrelated message causes rehearseReleaseIdentity to reject with "unexpected rejection reason"', async () => {
  const packageVersion = '2.12.0';
  const weirdGate = async ({context}) => {
    const match = /^refs\/tags\/v(.+)$/.exec(context.ref);
    const version = match ? match[1] : undefined;
    if (version === packageVersion) return packageVersion;
    throw new Error('nope');
  };
  await assert.rejects(
    rehearseReleaseIdentity({pyprojectText: PYPROJECT_212, sha: SHA, imageVersion: '2.12.0', imageId: IMAGE_ID, gate: weirdGate}),
    /unexpected rejection reason/
  );
});
