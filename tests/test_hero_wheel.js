/* Display wheel completion/reset geometry. No browser dependencies. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
async function check(wheel,count,reduced=false){
 const handlers={},observers=[],frames=[],finished=[];let winked=0,rested=0;
 const orders={[wheel]:Array.from({length:count},(_,i)=>String(i))};
 const status={textContent:''};
 function node(angle){
  return {style:{},dataset:{angle:String(angle)},animate(keyframes,timing){
   frames.push({keyframes,timing});
   return {finished:new Promise(resolve=>finished.push(resolve)),cancel(){}};
  }};
 }
 const disc=node(47),orbit=node(21),ball=node(0);disc.getAttribute=()=>'/assets/practice-wheel-'+wheel+'.svg';
 const button={dataset:{wheelOrders:JSON.stringify(orders),redNumbers:'[1,3,5]'},disabled:false,
  querySelector:s=>({'.hero-wheel-disc':disc,'.hero-ball-orbit':orbit,'.hero-ball':ball})[s],setAttribute(){},removeAttribute(){}};
 const document={documentElement:{},addEventListener:(n,fn)=>handlers[n]=fn,getElementById:id=>({'hero-wheel-spin':button,'hero-wheel-status':status})[id]};
 const window={crypto:{getRandomValues:a=>{a[0]=5;}},matchMedia:()=>({matches:reduced}),CrimsonDealerWink:{rest:()=>rested++,play:()=>winked++}};
 vm.runInNewContext(fs.readFileSync('assets/hero-wheel.js','utf8'),{document,window,Uint32Array,WeakMap,Promise,MutationObserver:class{constructor(fn){observers.push(fn);}observe(){}}});
 handlers.click({target:{closest:()=>button}});
 if(!reduced){
  assert.equal(button.disabled,true);
  assert.equal(frames.length,3);
  const angle=text=>Number(text.match(/rotate\(([^d]+)deg\)/)[1]);
  assert.ok(angle(frames[0].keyframes[1].transform)-47>=1080,'At least three full rotations');
  for(const f of frames.slice(0,2))assert.equal(f.keyframes[1].transform,f.keyframes[2].transform,'Rotation stops at ball contact');
  finished.forEach(resolve=>resolve());await Promise.resolve();await Promise.resolve();
 }
 assert.equal(button.disabled,false);assert.equal(winked,1);
 assert.ok(status.textContent.includes('Display result: 5'));
 assert.ok(status.textContent.includes('No session result was recorded'));
 const normalize=n=>(n%360+360)%360;
 assert.ok(Math.abs(normalize(Number(orbit.dataset.angle)-Number(disc.dataset.angle))-5*360/count)<1e-8,'Ball aligns with sampled pocket');
 observers[1]();assert.equal(disc.dataset.angle,'0');assert.equal(orbit.dataset.angle,'0');
 assert.equal(button.disabled,false);assert.ok(rested>=2);
}
(async()=>{for(const [w,n] of [['single',37],['french',37],['double',38],['triple',39]])await check(w,n);await check('single',37,true);console.log('Display wheel: four pocket counts, minimum rotations, stationary landing, exact pocket alignment, reset, reduced-motion completion passed.');})().catch(e=>{console.error(e);process.exitCode=1;});
