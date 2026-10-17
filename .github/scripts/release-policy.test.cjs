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
