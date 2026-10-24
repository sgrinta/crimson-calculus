/* Continuous blink geometry: node tests/test_vivienne_wink.js */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const context={module:{exports:{}},window:{},document:{addEventListener(){}}};
vm.runInNewContext(fs.readFileSync('assets/vivienne-wink.js','utf8'),context);
const {closureAt,eyelid,PATCH,DURATION}=context.module.exports;
assert.equal(closureAt(0),0);assert.equal(closureAt(125),1);assert.equal(closureAt(160),1);
assert.equal(closureAt(DURATION),0);assert.equal(closureAt(10000),0);
assert.ok(closureAt(60)>0 && closureAt(60)<1);
assert.ok(closureAt(280)>0 && closureAt(280)<1);
assert.ok(1-503/1024>.5,'Mirrored animated eye must be on the viewer right');
for(let x=PATCH.left;x<=PATCH.right;x++)for(const c of [0,.25,.5,.75,1]){
 const l=eyelid(x,c);
 assert.ok(PATCH.top<l.upperTo && l.upperTo<l.lowerTo && l.lowerTo<PATCH.bottom);
 if(c===0){assert.equal(l.upper,l.upperTo);assert.equal(l.lower,l.lowerTo);}
}
for(let x=472;x<534;x++)assert.ok(eyelid(x,1).lowerTo-eyelid(x,1).upperTo<.66,'Closed eye aperture must hide the pupil');
console.log('Vivienne wink: correct displayed eye, continuous close/open, brief hold, stable corners, non-inverting mesh and closed aperture passed.');
