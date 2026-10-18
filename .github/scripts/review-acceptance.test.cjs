const {test}=require('node:test');
const assert=require('node:assert/strict');
const {assess}=require('./review-acceptance.cjs');
function fixture(){return {head:'a'.repeat(40),currentHead:'a'.repeat(40),
 checks:[{id:1,name:'Greptile Review',head_sha:'a'.repeat(40),app:{id:867647},status:'completed',conclusion:'success'}],
 comments:[{id:42,user:{login:'greptile-apps[bot]'},resolved:true}],
 dispositions:{schema:1,items:{42:{head:'a'.repeat(40),decision:'fixed',evidence:'Regression test demonstrates the defect is fixed.'}}},
 blockers:{schema:1,open:[]}};}
test('current review and independently recorded evidence pass',()=>assert.equal(assess(fixture()),1));
for(const [name,change] of [
 ['bot resolution without evidence',f=>f.dispositions.items={}],
 ['stale approval',f=>f.currentHead='b'.repeat(40)],
 ['stale disposition',f=>f.dispositions.items[42].head='b'.repeat(40)],
 ['missing review',f=>f.checks=[]],
 ['stale review',f=>f.checks[0].head_sha='b'.repeat(40)],
 ['spoofed review source',f=>f.checks[0].app.id=15368],
 ['failed review',f=>f.checks[0].conclusion='failure'],
 ['new review still running',f=>f.checks.push({...f.checks[0],id:2,status:'in_progress',conclusion:null})],
 ['open accepted blocker',f=>f.blockers.open=['old-tag-bypass']],
 ['missing register',f=>f.blockers=null],
 ['unsupported waiver',f=>f.dispositions.items[42].decision='accepted_risk'],
 ['empty evidence',f=>f.dispositions.items[42].evidence=''],
 ['additional finding',f=>f.comments.push({id:43,user:{login:'greptile-apps[bot]'}})]
])test(`blocks ${name}`,()=>{const f=fixture();change(f);assert.throws(()=>assess(f));});
