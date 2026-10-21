// Rehearses release.yml's own release-identity entry points (releaseIdentityGate,
// parseReleaseTag) against the exact audited publish-candidate image, without
// pushing a tag. See release-policy.cjs for the rules this rehearsal exercises
// but never reimplements.
const {releaseIdentityGate, parseReleaseTag, parseProjectVersion} = require('./release-policy.cjs');

const IMAGE_ID_RE = /^sha256:[a-f0-9]{64}$/;
const COMMIT_SHA_RE = /^[a-f0-9]{40}$/;
const REHEARSAL_REPO = {owner: 'rehearsal', repo: 'triggarr'};

// Asks release-policy.cjs's own tag rule (parseReleaseTag) whether a tag for this package version could
// ever be accepted, rather than keeping a copy of that rule here. A package version it refuses
// (e.g. "2.13.0.dev0", "2.6.1-dev") can never be released, so no tag can match it.
function isReleasableVersion(version) {
  try {
    return parseReleaseTag(`refs/tags/v${version}`) === version;
  } catch {
    return false;
  }
}

function buildContentsStandIn(pyprojectText, sha) {
  return {
    rest: {
      repos: {
        getContent: async ({owner, repo, path, ref}) => {
          if (owner !== REHEARSAL_REPO.owner || repo !== REHEARSAL_REPO.repo || path !== 'pyproject.toml' || ref !== sha) {
            throw new Error(`Rehearsal contents stand-in received an unexpected getContent call: ${JSON.stringify({owner, repo, path, ref})}`);
          }
          return {data: {content: Buffer.from(pyprojectText, 'utf8').toString('base64'), encoding: 'base64'}};
        },
      },
    },
  };
}

function incrementPatch(version) {
  const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(version);
  if (!match) {
    throw new Error(`Release identity rehearsal refused: package version is not a plain X.Y.Z string (${JSON.stringify(version)})`);
  }
  const [, major, minor, patch] = match;
  return `${major}.${minor}.${Number(patch) + 1}`;
}

async function matchingCase({packageVersion, imageVersion, sha, github, core, gate}) {
  const label = 'matching';
  const context = {ref: `refs/tags/v${packageVersion}`, repo: REHEARSAL_REPO};
  let result;
  try {
    result = await gate({github, context, core, sha, imageVersion});
  } catch (err) {
    throw new Error(`${label}: matching tag was not accepted (${err.message})`);
  }
  if (result !== packageVersion) {
    throw new Error(`${label}: matching tag was not accepted (got ${JSON.stringify(result)}, expected ${JSON.stringify(packageVersion)})`);
  }
  return `${label}: accepted ${result}`;
}

async function mismatchedCase({packageVersion, imageVersion, sha, github, core, gate}) {
  const label = 'mismatched';
  const context = {ref: `refs/tags/v${incrementPatch(packageVersion)}`, repo: REHEARSAL_REPO};
  try {
    await gate({github, context, core, sha, imageVersion});
  } catch (err) {
    if (!/disagree/.test(err.message)) {
      throw new Error(`${label}: unexpected rejection reason: ${err.message}`);
    }
    return `${label}: rejected as expected (disagree)`;
  }
  throw new Error(`${label}: expected rejection did not occur`);
}

async function malformedCase({packageVersion, imageVersion, sha, github, core, gate, parseTag}) {
  const label = 'malformed';
  const ref = `refs/tags/v${packageVersion}-rc1`;

  let tagError;
  try {
    parseTag(ref);
  } catch (err) {
    tagError = err;
  }
  if (!tagError) {
    throw new Error(`${label}: expected rejection did not occur`);
  }
  if (!/malformed/.test(tagError.message)) {
    throw new Error(`${label}: unexpected rejection reason: ${tagError.message}`);
  }

  const context = {ref, repo: REHEARSAL_REPO};
  let gateError;
  try {
    await gate({github, context, core, sha, imageVersion});
  } catch (err) {
    gateError = err;
  }
  if (!gateError) {
    throw new Error(`${label}: expected rejection did not occur`);
  }
  if (!/malformed/.test(gateError.message)) {
    throw new Error(`${label}: unexpected rejection reason: ${gateError.message}`);
  }
  return `${label}: rejected as expected (malformed)`;
}

async function missingCase({packageVersion, sha, github, core, gate}) {
  const label = 'missing';
  const context = {ref: `refs/tags/v${packageVersion}`, repo: REHEARSAL_REPO};
  try {
    await gate({github, context, core, sha, imageVersion: ''});
  } catch (err) {
    if (!/missing/.test(err.message) || !err.message.includes('image: missing')) {
      throw new Error(`${label}: unexpected rejection reason: ${err.message}`);
    }
    return `${label}: rejected as expected (missing)`;
  }
  throw new Error(`${label}: expected rejection did not occur`);
}

async function rehearseReleaseIdentity({pyprojectText, sha, imageVersion, imageId, gate = releaseIdentityGate, parseTag = parseReleaseTag}) {
  if (!IMAGE_ID_RE.test(imageId || '')) {
    throw new Error(`Release identity rehearsal refused: invalid audited image identity ${JSON.stringify(imageId)} -- refusing to run without the exact image under test`);
  }
  if (!COMMIT_SHA_RE.test(sha || '')) {
    throw new Error(`Release identity rehearsal refused: invalid commit sha ${JSON.stringify(sha)}`);
  }

  const packageVersion = parseProjectVersion(pyprojectText);
  const github = buildContentsStandIn(pyprojectText, sha);
  const core = {info: () => {}};

  const lines = [`Rehearsing release identity for image ${imageId} at commit ${sha}`];
  if (!isReleasableVersion(packageVersion)) {
    // A dev/pre-release package version is not releasable: no tag can ever match it, so the
    // matching, mismatched and missing cases have nothing to rehearse. Skip them (visibly) rather
    // than failing CI for a commit that is not a release candidate; the malformed case still runs.
    // The image still gets published for main/dev builds, so its version label must still be present
    // and agree with the package version -- skipping the tag cases never skips the image identity.
    if (typeof imageVersion !== 'string' || imageVersion === '') {
      throw new Error(`Release identity rehearsal refused: image version label is missing for development package version ${JSON.stringify(packageVersion)}`);
    }
    if (imageVersion !== packageVersion) {
      throw new Error(`Release identity rehearsal refused: image version ${JSON.stringify(imageVersion)} disagrees with package version ${JSON.stringify(packageVersion)}`);
    }
    const reason = `skipped (package version ${JSON.stringify(packageVersion)} is not a releasable X.Y.Z version)`;
    lines.push(`matching: ${reason}`);
    lines.push(`mismatched: ${reason}`);
    lines.push(await malformedCase({packageVersion, imageVersion, sha, github, core, gate, parseTag}));
    lines.push(`missing: ${reason}`);
    return lines;
  }
  lines.push(await matchingCase({packageVersion, imageVersion, sha, github, core, gate}));
  lines.push(await mismatchedCase({packageVersion, imageVersion, sha, github, core, gate}));
  lines.push(await malformedCase({packageVersion, imageVersion, sha, github, core, gate, parseTag}));
  lines.push(await missingCase({packageVersion, sha, github, core, gate}));
  return lines;
}

if (require.main === module) {
  const fs = require('node:fs');
  const path = require('node:path');
  const pyprojectText = fs.readFileSync(path.join(__dirname, '../../pyproject.toml'), 'utf8');
  rehearseReleaseIdentity({
    pyprojectText,
    sha: process.env.REHEARSAL_SHA,
    imageVersion: process.env.IMAGE_VERSION,
    imageId: process.env.IMAGE_ID,
  }).then(lines => {
    for (const line of lines) console.log(line);
  }).catch(err => {
    console.error(err.message);
    process.exitCode = 1;
  });
}

module.exports = {rehearseReleaseIdentity};
