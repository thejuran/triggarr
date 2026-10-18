const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const release=fs.readFileSync(path.join(__dirname,'../workflows/release.yml'),'utf8');
const ci=fs.readFileSync(path.join(__dirname,'../workflows/ci.yml'),'utf8');
test('both exact-run artifacts are downloaded and checked before publication',()=>{
 const publish=release.indexOf('      - name: Publish audited image');
 assert.ok(publish>0);
 for(const name of ['Download exact successful CI image','Verify and load audited image',
 'Download exact successful CI Python distributions','Verify distribution artifacts before any publication']) {
   const pos=release.indexOf(`      - name: ${name}`);
   assert.ok(pos>=0 && pos<publish,`${name} must precede publishing`);
 }
 assert.equal((release.match(/run-id: \$\{\{ steps.recheck.outputs.run_id \}\}/g)||[]).length,2);
 assert.doesNotMatch(release,/docker\/build-push-action|python -m build|docker build/);
});
test('CI sets immutable provenance labels before auditing and saving the image',()=>{
 const labels=ci.indexOf('          labels: |');
 assert.ok(labels>0 && labels<ci.indexOf('      - name: Audit actual image dependencies'));
 for(const key of ['source','revision','version']) assert.ok(ci.includes(`org.opencontainers.image.${key}=`));
 assert.ok(ci.includes('org.opencontainers.image.revision=${{ github.sha }}'));
});
