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
  assert.deepEqual(f.output,[['sha',sha]]);
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
