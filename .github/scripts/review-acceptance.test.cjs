const {test}=require('node:test');
const assert=require('node:assert/strict');
const {assess}=require('./review-acceptance.cjs');
function fixture(){return {head:'a'.repeat(40),currentHead:'a'.repeat(40),
 checks:[{id:1,name:'Greptile Review',head_sha:'a'.repeat(40),app:{id:867647},status:'completed',conclusion:'success'}],
 comments:[{id:42,user:{login:'greptile-apps[bot]'},resolved:true}],
 dispositions:{schema:1,items:{42:{head:'a'.repeat(40),decision:'fixed',evidence:'Regression test demonstrates the defect is fixed.'}}},
 blockers:{schema:1,open:[]}};}
test('current review and independently recorded evidence pass',()=>assert.deepEqual(assess(fixture()),{findings:1,greptile:'success'}));
// Greptile is optional (owner decision 2026-10-22): no Greptile review for this head does not block acceptance.
for(const [name,change] of [
 ['no Greptile review for this head',f=>f.checks=[]],
 ['only a review of an older head',f=>f.checks[0].head_sha='b'.repeat(40)],
 ['a non-Greptile app posting a Greptile-named check',f=>f.checks[0].app.id=15368]
])test(`allows ${name}`,()=>{const f=fixture();change(f);assert.deepEqual(assess(f),{findings:1,greptile:'none'});});
for(const [name,change] of [
 ['bot resolution without evidence',f=>f.dispositions.items={}],
 ['stale approval',f=>f.currentHead='b'.repeat(40)],
 ['stale disposition',f=>f.dispositions.items[42].head='b'.repeat(40)],
 ['failed review',f=>f.checks[0].conclusion='failure'],
 ['new review still running',f=>f.checks.push({...f.checks[0],id:2,status:'in_progress',conclusion:null})],
 ['failed review even with no findings',f=>{f.checks[0].conclusion='failure';f.comments=[];f.dispositions.items={};}],
 ['open accepted blocker',f=>f.blockers.open=['old-tag-bypass']],
 ['missing register',f=>f.blockers=null],
 ['unsupported waiver',f=>f.dispositions.items[42].decision='accepted_risk'],
 ['empty evidence',f=>f.dispositions.items[42].evidence=''],
 ['additional finding',f=>f.comments.push({id:43,user:{login:'greptile-apps[bot]'}})],
 ['undisposed finding even without a current review',f=>{f.checks=[];f.comments.push({id:43,user:{login:'greptile-apps[bot]'}});}]
])test(`blocks ${name}`,()=>{const f=fixture();change(f);assert.throws(()=>assess(f));});
