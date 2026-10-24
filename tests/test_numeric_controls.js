/* Run with node tests/test_numeric_controls.js; no browser/package dependencies. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const handlers={};const updates=[];const timers=[];
class FakeInput {
  constructor(value,min,max){this._value=String(value);this.min=min;this.max=max;this.id='free-amount';this.events=[];}
  get value(){return this._value;}
  set value(value){this._value=value;}
  getAttribute(name){return this[name]===undefined ? null : String(this[name]);}
  dispatchEvent(event){this.events.push(event.type);}
}
const context={module:{exports:{}},document:{addEventListener:(name,fn)=>handlers[name]=fn,querySelectorAll:()=>[],documentElement:{}},
  MutationObserver:class{observe(){}},requestAnimationFrame:fn=>fn(),setTimeout:fn=>timers.push(fn),HTMLInputElement:FakeInput,Event:class{constructor(type){this.type=type;}},
  window:{dash_clientside:{set_props:(id,props)=>updates.push({id,props})}}};
vm.runInNewContext(fs.readFileSync('assets/numeric-controls.js','utf8'),context);
const {increment,adjusted}=context.module.exports;
for(const [event,amount] of [[{},1],[{ctrlKey:true},10],[{metaKey:true},10],[{shiftKey:true},100],[{ctrlKey:true,shiftKey:true},1000],[{metaKey:true,shiftKey:true},1000]]){
  assert.equal(increment(event),amount);
  for(const direction of [-1,1]){
    const input=new FakeInput(2000,5);
    const button={closest:()=>({querySelector:()=>input}),classList:{contains:()=>direction===-1}};
    let prevented=false,stopped=false;
    handlers.click({...event,target:{closest:()=>button},preventDefault:()=>prevented=true,stopImmediatePropagation:()=>stopped=true});
    assert.equal(input.value,String(2000+direction*amount));
    assert.equal(updates.at(-1).props.value,2000+direction*amount);
    assert.deepEqual(input.events,['input','change']);
    assert.ok(prevented && stopped);
  }
}
assert.equal(adjusted(5,1,1,5,NaN),6); // Missing maximum must not produce NaN/blank.
assert.equal(adjusted(6,-1,1,5,NaN),5);
assert.equal(adjusted(5,-1,1000,5,NaN),5);
assert.equal(adjusted(280,1,1000,1,500),500);
assert.equal(adjusted(NaN,1,1,5,NaN),5);
assert.equal(adjusted(12.5,1,1,0,NaN),13.5);
for(const property of ['disabled','readOnly']){
  const input=new FakeInput(10,5);input[property]=true;
  const button={closest:()=>({querySelector:()=>input})};
  handlers.click({target:{closest:()=>button}});
  assert.equal(input.value,'10');
}
console.log('Numeric controls: 6 modifier combinations × 2 directions, public Dash updates, missing max, bounds, empty/fractional inputs and locked fields passed.');

// Control-click: macOS context-menu path and platforms which also emit click.
for(const sendsClick of [false,true]){
  const input=new FakeInput(20,5);const button={closest:()=>({querySelector:()=>input}),classList:{contains:()=>false}};
  const event={ctrlKey:true,button:0,pointerId:7,target:{closest:()=>button},preventDefault(){},stopImmediatePropagation(){}};
  handlers.pointerdown(event);handlers.pointerup(event);
  if(sendsClick)handlers.click(event);
  while(timers.length)timers.shift()();
  assert.equal(input.value,'30');
  handlers.click({...event,ctrlKey:false});
  assert.equal(input.value,'31');
}
console.log('macOS Control-click and duplicate-click suppression passed.');
