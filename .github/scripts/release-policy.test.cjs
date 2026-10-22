const {test} = require('node:test');
const assert = require('node:assert/strict');
const {REQUIRED_JOBS, validateEvidence} = require('./release-policy.cjs');
const sha = 'a'.repeat(40);
function evidence() {
  return {sha, mainSha:sha, ancestry:'identical', tag:false,
    runs:[{id:12,head_sha:sha,event:'push',head_branch:'main',status:'completed',conclusion:'success'}],
    jobs:REQUIRED_JOBS.map(name => ({name,run_id:12,status:'completed',conclusion:'success'}))};
}
test('exact current commit with all successful mandatory jobs passes', () => assert.equal(validateEvidence(evidence()),sha));
for (const conclusion of ['skipped','neutral','failure','cancelled','timed_out',null]) {
 test(`rejects ${conclusion} job even if run says success`, () => {
   const e=evidence(); e.jobs[0].conclusion=conclusion;
   assert.throws(()=>validateEvidence(e));
 });
}
test('missing aggregate blocks',()=>{const e=evidence();e.jobs.pop();assert.throws(()=>validateEvidence(e));});
test('different commit cannot authorize release',()=>{const e=evidence();e.runs[0].head_sha='b'.repeat(40);assert.throws(()=>validateEvidence(e));});
test('newer failed run supersedes old successful run',()=>{const e=evidence();e.runs.push({...e.runs[0],id:13,conclusion:'failure'});assert.throws(()=>validateEvidence(e));});
test('PR CI does not authorize a release',()=>{const e=evidence();e.runs[0].event='pull_request';assert.throws(()=>validateEvidence(e));});
test('tag must belong to main',()=>{const e=evidence();e.tag=true;e.ancestry='diverged';assert.throws(()=>validateEvidence(e));});
test('old main run cannot overwrite current main image',()=>{const e=evidence();e.mainSha='b'.repeat(40);assert.throws(()=>validateEvidence(e));});
test('tag on an older verified main commit is valid',()=>{const e=evidence();e.tag=true;e.mainSha='b'.repeat(40);e.ancestry='behind';assert.equal(validateEvidence(e),sha);});

const {preflight} = require('./release-policy.cjs');
function fixture({tag=false}={}) {
  const e=evidence();
  const calls=[];
  const context={repo:{owner:'owner',repo:'repo'},eventName:tag?'push':'workflow_run',
    ref:tag?'refs/tags/v1.0.0':'refs/heads/main',sha:tag?sha:'b'.repeat(40),
    payload:{workflow_run:{event:'push',head_branch:'main',conclusion:'success',
      head_sha:sha,head_repository:{full_name:'owner/repo'}}}};
  const output=[];
  const github={rest:{repos:{
    getBranch:async args=>{calls.push(['branch',args]);return {data:{commit:{sha:e.mainSha}}};},
    compareCommitsWithBasehead:async args=>{calls.push(['compare',args]);return {data:{status:e.ancestry}};}
  },actions:{listWorkflowRuns:Symbol('runs'),listJobsForWorkflowRun:Symbol('jobs')}},
  paginate:async (method,args)=>{
    if(method===github.rest.actions.listWorkflowRuns){calls.push(['runs',args]);return e.runs;}
    if(method===github.rest.actions.listJobsForWorkflowRun){calls.push(['jobs',args]);return e.jobs;}
    throw Error('Unexpected API method');
  }};
  const core={setOutput:(...args)=>output.push(args),info:()=>{}};
  return {github,context,core,e,calls,output};
}
for(const tag of [false,true])test(`preflight authorizes ${tag?'tag':'main CI'} trigger using exact commit evidence`,async()=>{
  const f=fixture({tag});await preflight(f);
  assert.deepEqual(f.output,[['sha',sha],['run_id','12']]);
  assert.deepEqual(f.calls,[
    ['branch',{owner:'owner',repo:'repo',branch:'main'}],
    ['compare',{owner:'owner',repo:'repo',basehead:`main...${sha}`}],
    ['runs',{owner:'owner',repo:'repo',workflow_id:'ci.yml',event:'push',branch:'main',head_sha:sha,per_page:100}],
    ['jobs',{owner:'owner',repo:'repo',run_id:12,filter:'latest',per_page:100}]
  ]);
});
for(const [label,mutate] of [
  ['fork',f=>f.context.payload.workflow_run.head_repository.full_name='other/repo'],
  ['PR workflow',f=>f.context.payload.workflow_run.event='pull_request'],
  ['failed source',f=>f.context.payload.workflow_run.conclusion='failure'],
  ['non-main branch',f=>f.context.payload.workflow_run.head_branch='feature'],
  ['missing source',f=>delete f.context.payload.workflow_run],
  ['untrusted event',f=>f.context.eventName='issue_comment'],
  ['non-release tag',f=>{f.context.eventName='push';f.context.ref='refs/tags/test';}]
])test(`preflight rejects ${label} before querying APIs`,async()=>{
  const f=fixture();mutate(f);await assert.rejects(preflight(f),/Untrusted/);
  assert.deepEqual(f.calls,[]);assert.deepEqual(f.output,[]);
});
for(const api of ['getBranch','compareCommitsWithBasehead','paginate'])test(`preflight fails closed on ${api} API failure`,async()=>{
  const f=fixture();const fail=async()=>{throw Error('API unavailable');};
  if(api==='paginate')f.github.paginate=fail;else f.github.rest.repos[api]=fail;
  await assert.rejects(preflight(f),/API unavailable/);assert.deepEqual(f.output,[]);
});
test('preflight refuses a release without a matching CI run',async()=>{
  const f=fixture();f.e.runs=[];await assert.rejects(preflight(f),/has not succeeded/);
  assert.equal(f.calls.some(([name])=>name==='jobs'),false);assert.deepEqual(f.output,[]);
});
test('preflight recheck rejects main that advanced while queued',async()=>{
  const f=fixture();await preflight(f);f.output.length=0;f.e.mainSha='c'.repeat(40);
  await assert.rejects(preflight(f),/Superseded/);assert.deepEqual(f.output,[]);
});

// --- Release tag / package / image identity rules (CISHIP-03) ---
const {parseReleaseTag, parseProjectVersion, validateReleaseIdentity, releaseIdentityGate} = require('./release-policy.cjs');

for (const [ref, version] of [
  ['refs/tags/v2.13.0', '2.13.0'],
  ['refs/tags/v0.0.0', '0.0.0'],
  ['refs/tags/v10.20.30', '10.20.30'],
]) {
  test(`parseReleaseTag accepts ${ref}`, () => assert.equal(parseReleaseTag(ref), version));
}

for (const ref of [
  'refs/tags/v2.13',
  'refs/tags/v2.13.0.1',
  'refs/tags/2.13.0',
  'refs/tags/v2.13.0-rc1',
  'refs/tags/v2.13.0+build5',
  'refs/tags/v02.13.0',
  'refs/tags/v2.013.0',
  'refs/tags/v2.13.00',
  'refs/heads/main',
  '',
  undefined,
  'refs/tags/v2.13.0\n',
  'refs/tags/V2.13.0',
  'refs/tags/v-1.0.0',
]) {
  test(`parseReleaseTag rejects malformed ref ${JSON.stringify(ref)}`, () => {
    assert.throws(() => parseReleaseTag(ref), /malformed/);
  });
}

test('parseReleaseTag rejection names the raw ref and reports package/image as not inspected', () => {
  assert.throws(() => parseReleaseTag('refs/tags/v2.13'), err => {
    assert.match(err.message, /malformed/);
    assert.match(err.message, /refs\/tags\/v2\.13/);
    assert.match(err.message, /package: not inspected/);
    assert.match(err.message, /image: not inspected/);
    return true;
  });
});

test('parseProjectVersion reads the version from the [project] table only', () => {
  const text = [
    '[project]',
    'name = "demo"',
    'version = "1.2.3"',
    '[project.optional-dependencies]',
    'version = "9.9.9"',
  ].join('\n');
  assert.equal(parseProjectVersion(text), '1.2.3');
});

test('parseProjectVersion matches the real pyproject.toml version', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const text = fs.readFileSync(path.join(__dirname, '../../pyproject.toml'), 'utf8');
  const expected = /^\[project\][\s\S]*?^version = "([^"]+)"/m.exec(text);
  assert.ok(expected, 'expected a version line under [project] in the real pyproject.toml');
  assert.equal(parseProjectVersion(text), expected[1]);
});

for (const [label, text] of [
  ['no [project] table', 'name = "demo"\nversion = "1.2.3"\n'],
  ['[project] without version', '[project]\nname = "demo"\n'],
  ['two version lines in [project]', '[project]\nversion = "1.2.3"\nversion = "1.2.4"\n'],
  ['version = ""', '[project]\nversion = ""\n'],
  ['version not a double-quoted string', '[project]\nversion = 1.2.3\n'],
]) {
  test(`parseProjectVersion rejects ${label}`, () => {
    assert.throws(() => parseProjectVersion(text), /package version/);
  });
}

test('validateReleaseIdentity accepts a tag, package and image that all agree', () => {
  assert.equal(validateReleaseIdentity({ref: 'refs/tags/v1.2.3', packageVersion: '1.2.3', imageVersion: '1.2.3'}), '1.2.3');
});

test('validateReleaseIdentity rejects a package version mismatch', () => {
  assert.throws(() => validateReleaseIdentity({ref: 'refs/tags/v1.2.3', packageVersion: '1.2.4', imageVersion: '1.2.3'}), err => {
    assert.match(err.message, /disagree/);
    assert.match(err.message, /tag: 1\.2\.3/);
    assert.match(err.message, /package: 1\.2\.4/);
    assert.match(err.message, /image: 1\.2\.3/);
    return true;
  });
});

test('validateReleaseIdentity rejects an image version mismatch', () => {
  assert.throws(() => validateReleaseIdentity({ref: 'refs/tags/v1.2.3', packageVersion: '1.2.3', imageVersion: '1.2.2'}), err => {
    assert.match(err.message, /disagree/);
    assert.match(err.message, /tag: 1\.2\.3/);
    assert.match(err.message, /package: 1\.2\.3/);
    assert.match(err.message, /image: 1\.2\.2/);
    return true;
  });
});

test('validateReleaseIdentity reports an unread image as not inspected', () => {
  assert.throws(() => validateReleaseIdentity({ref: 'refs/tags/v1.2.3', packageVersion: '1.2.3', imageVersion: undefined}), err => {
    assert.match(err.message, /image: not inspected/);
    return true;
  });
});

test('validateReleaseIdentity rejects an inspected but missing image label', () => {
  assert.throws(() => validateReleaseIdentity({ref: 'refs/tags/v1.2.3', packageVersion: '1.2.3', imageVersion: ''}), err => {
    assert.match(err.message, /missing/);
    assert.match(err.message, /image: missing/);
    return true;
  });
});

test('validateReleaseIdentity reports an unread package version as not inspected', () => {
  assert.throws(() => validateReleaseIdentity({ref: 'refs/tags/v1.2.3', packageVersion: undefined, imageVersion: '1.2.3'}), err => {
    assert.match(err.message, /package: not inspected/);
    return true;
  });
});

test('validateReleaseIdentity rejects an inspected but missing package version', () => {
  assert.throws(() => validateReleaseIdentity({ref: 'refs/tags/v1.2.3', packageVersion: '', imageVersion: '1.2.3'}), err => {
    assert.match(err.message, /missing/);
    assert.match(err.message, /package: missing/);
    return true;
  });
});

test('validateReleaseIdentity rejects a malformed tag before comparing versions', () => {
  assert.throws(() => validateReleaseIdentity({ref: 'refs/tags/v1.2', packageVersion: '1.2.0', imageVersion: '1.2.0'}), /malformed/);
});

function gateFixture({ref = 'refs/tags/v1.2.3', pyprojectText = '[project]\nversion = "1.2.3"\n', sha = 'f'.repeat(40), getContentImpl} = {}) {
  const calls = [];
  const info = [];
  const context = {repo: {owner: 'owner', repo: 'repo'}, ref};
  const github = {rest: {repos: {getContent: getContentImpl || (async args => {
    calls.push(['getContent', args]);
    return {data: {content: Buffer.from(pyprojectText, 'utf8').toString('base64'), encoding: 'base64'}};
  })}}};
  const core = {info: (...args) => info.push(args), setOutput: () => {}};
  return {github, context, core, calls, info, sha};
}

test('releaseIdentityGate resolves the version from a matching tag, package and image', async () => {
  const f = gateFixture();
  const result = await releaseIdentityGate({github: f.github, context: f.context, core: f.core, sha: f.sha, imageVersion: '1.2.3'});
  assert.equal(result, '1.2.3');
  assert.deepEqual(f.calls, [['getContent', {owner: 'owner', repo: 'repo', path: 'pyproject.toml', ref: f.sha}]]);
  assert.equal(f.info.length, 1);
});

test('releaseIdentityGate rejects an invalid sha before any API call', async () => {
  const f = gateFixture();
  await assert.rejects(releaseIdentityGate({github: f.github, context: f.context, core: f.core, sha: 'not-a-sha', imageVersion: '1.2.3'}), /Invalid release commit/);
  assert.deepEqual(f.calls, []);
  assert.equal(f.info.length, 0);
});

test('releaseIdentityGate fails closed when getContent throws', async () => {
  const f = gateFixture({getContentImpl: async () => { throw new Error('API unavailable'); }});
  await assert.rejects(releaseIdentityGate({github: f.github, context: f.context, core: f.core, sha: f.sha, imageVersion: '1.2.3'}), /API unavailable/);
  assert.equal(f.info.length, 0);
});

test('releaseIdentityGate rejects non-base64 content', async () => {
  const f = gateFixture({getContentImpl: async () => ({data: {content: 'plain text', encoding: 'utf-8'}})});
  await assert.rejects(releaseIdentityGate({github: f.github, context: f.context, core: f.core, sha: f.sha, imageVersion: '1.2.3'}), /package version/);
  assert.equal(f.info.length, 0);
});

test('releaseIdentityGate rejects a directory listing instead of file content', async () => {
  const f = gateFixture({getContentImpl: async () => ({data: [{name: 'pyproject.toml'}]})});
  await assert.rejects(releaseIdentityGate({github: f.github, context: f.context, core: f.core, sha: f.sha, imageVersion: '1.2.3'}), /package version/);
  assert.equal(f.info.length, 0);
});

test('releaseIdentityGate rejects an image label mismatch', async () => {
  const f = gateFixture();
  await assert.rejects(releaseIdentityGate({github: f.github, context: f.context, core: f.core, sha: f.sha, imageVersion: '9.9.9'}), /disagree/);
  assert.equal(f.info.length, 0);
});
