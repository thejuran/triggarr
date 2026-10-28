const {test}=require('node:test');
const assert=require('node:assert/strict');
const {assess,registerKey}=require('./review-acceptance.cjs');
const HEAD='a'.repeat(40);
const KEY=registerKey(85,HEAD);
function fixture(){return {prNumber:85,head:HEAD,currentHead:HEAD,draft:false,
 checks:[{id:1,name:'Greptile Review',head_sha:HEAD,app:{id:867647},status:'completed',conclusion:'success'}],
 comments:[{id:42,user:{login:'greptile-apps[bot]'},resolved:true}],
 dispositions:{schema:2,by_pr_head:{[KEY]:{items:{42:{head:HEAD,decision:'fixed',evidence:'Regression test demonstrates the defect is fixed.'}}}}},
 blockers:{schema:2,global_open:[],by_pr_head:{[KEY]:{open:[]}}}};}

test('current review and independently recorded evidence pass',()=>assert.deepEqual(assess(fixture()),{findings:1,greptile:'success'}));
test('registerKey formats as "pr:head"',()=>assert.equal(registerKey(85,HEAD),`85:${HEAD}`));

// Greptile is optional (owner decision 2026-10-22): no Greptile review for this head does not block acceptance.
for(const [name,change] of [
 ['no Greptile review for this head',f=>f.checks=[]],
 ['only a review of an older head',f=>f.checks[0].head_sha='b'.repeat(40)],
 ['a non-Greptile app posting a Greptile-named check',f=>f.checks[0].app.id=15368]
])test(`allows ${name}`,()=>{const f=fixture();change(f);assert.deepEqual(assess(f),{findings:1,greptile:'none'});});

test("allows another PR's open blockers when this PR's slice is clear",()=>{
 const f=fixture();
 f.blockers.by_pr_head['7:'+HEAD]={open:['x']};
 assert.deepEqual(assess(f),{findings:1,greptile:'success'});
});

for(const [name,change] of [
 ['bot resolution without evidence',f=>f.dispositions.by_pr_head[KEY].items={}],
 ['stale approval',f=>f.currentHead='b'.repeat(40)],
 ['stale disposition',f=>f.dispositions.by_pr_head[KEY].items[42].head='b'.repeat(40)],
 ['failed review',f=>f.checks[0].conclusion='failure'],
 ['new review still running',f=>f.checks.push({...f.checks[0],id:2,status:'in_progress',conclusion:null})],
 ['failed review even with no findings',f=>{f.checks[0].conclusion='failure';f.comments=[];f.dispositions.by_pr_head[KEY].items={};}],
 ['open accepted blocker on this PR slice',f=>f.blockers.by_pr_head[KEY].open=['old-tag-bypass']],
 ['missing register',f=>f.blockers=null],
 ['unsupported waiver',f=>f.dispositions.by_pr_head[KEY].items[42].decision='accepted_risk'],
 ['empty evidence',f=>f.dispositions.by_pr_head[KEY].items[42].evidence=''],
 ['additional finding',f=>f.comments.push({id:43,user:{login:'greptile-apps[bot]'}})],
 ['undisposed finding even without a current review',f=>{f.checks=[];f.comments.push({id:43,user:{login:'greptile-apps[bot]'}});}]
])test(`blocks ${name}`,()=>{const f=fixture();change(f);assert.throws(()=>assess(f));});

test('blocks a draft PR',()=>{const f=fixture();f.draft=true;assert.throws(()=>assess(f),/PR is still a draft/);});
test('blocks an undefined draft flag (fail closed)',()=>{const f=fixture();delete f.draft;assert.throws(()=>assess(f));});

for(const bad of [0,-1,1.5,'85',null,undefined])
 test(`blocks invalid PR number ${JSON.stringify(bad)}`,()=>{const f=fixture();f.prNumber=bad;assert.throws(()=>assess(f),/Invalid PR number/);});

test("blocks a disposition stored only under another PR's key",()=>{
 const f=fixture();
 f.dispositions.by_pr_head={['7:'+HEAD]:f.dispositions.by_pr_head[KEY]};
 assert.throws(()=>assess(f),/No disposition register entry for PR 85/);
});

test('blocks a missing blocker slice for this PR+head',()=>{
 const f=fixture();
 delete f.blockers.by_pr_head[KEY];
 assert.throws(()=>assess(f),/No blocker register entry for PR 85/);
});

test('blocks a nonempty global_open list',()=>{
 const f=fixture();
 f.blockers.global_open=['global-incident'];
 assert.throws(()=>assess(f),/Open accepted blockers/);
});

test('blocks a schema-1 blockers register as retired',()=>{
 const f=fixture();
 f.blockers={schema:1,open:[]};
 assert.throws(()=>assess(f),/schema 1 is retired/);
});

test('blocks a schema-1 dispositions register as retired',()=>{
 const f=fixture();
 f.dispositions={schema:1,items:{}};
 assert.throws(()=>assess(f),/schema 1 is retired/);
});
