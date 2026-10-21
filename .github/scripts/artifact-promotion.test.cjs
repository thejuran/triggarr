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

// --- Release-identity wiring: supplementary ordering checks (D-31b's blocking
// proof is the Python structural test in tests/test_github_workflows.py; these
// are the ordering-only checks this file's existing pattern already covers). ---
// orderingViolations(text) is implemented in the following commit (TDD RED).

test('release.yml release-identity steps are correctly ordered relative to publication (supplementary; D-31b)',()=>{
 assert.deepEqual(orderingViolations(release), []);
 assert.doesNotMatch(release,/docker\/build-push-action|python -m build|docker build/);
});

test('orderingViolations flags the identity step reordered after the first docker/login-action',()=>{
 const badText=[
   '      - name: Validate release tag format',
   '      - name: Download exact successful CI image',
   '      - name: Verify and load audited image',
   '      - name: Read audited image version label',
   '      - uses: docker/login-action@pinned',
   '      - name: Verify release version identity',
   '      - name: Publish audited image',
   '      - name: Create GitHub Release',
 ].join('\n');
 const violations=orderingViolations(badText);
 assert.ok(violations.length>0);
 assert.ok(violations.some(v=>v.includes('docker/login-action')));
});

test('orderingViolations flags a tag-deletion pattern',()=>{
 const violations=orderingViolations(`${release}\n# git push --delete origin refs/tags/v1.0.0\n`);
 assert.ok(violations.some(v=>v.includes('tag-deletion')));
});

test('orderingViolations flags a sparse-checkout count drift',()=>{
 const violations=orderingViolations('          sparse-checkout: .github/scripts\n');
 assert.ok(violations.some(v=>v.includes('sparse-checkout')));
});
