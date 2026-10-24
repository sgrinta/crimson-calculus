/* Header shortcuts must reveal mounted tabs without writing to game stores. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const handlers={};
const updates=[];
let observed;
let visible=false;
let scrolled=[];
const nodes={};
for(const id of ['lab','portfolio']){
  nodes[id]={isConnected:true,getClientRects:()=>visible ? [{}] : [],scrollIntoView:()=>scrolled.push(id)};
}
const context={
  document:{addEventListener:(name,fn)=>handlers[name]=fn,querySelectorAll:()=>[],getElementById:id=>nodes[id],documentElement:{}},
  MutationObserver:class{constructor(fn){observed=fn;}observe(){}},
  requestAnimationFrame:fn=>fn(),
  window:{dash_clientside:{set_props:(id,props)=>updates.push({id,props})}}
};
vm.runInNewContext(fs.readFileSync('assets/workflow-tabs.js','utf8'),context);
function click(href,modifiers={}){
  let prevented=false;
  handlers.click({button:0,target:{closest:()=>({getAttribute:()=>href})},preventDefault:()=>prevented=true,...modifiers});
  return prevented;
}
assert.ok(click('#portfolio'));
assert.equal(JSON.stringify(updates),JSON.stringify([{id:'workflow-tabs',props:{value:'tools'}},{id:'tools-view',props:{value:'builder'}}]));
assert.deepEqual(scrolled,[],'Do not scroll to an invisible destination');
visible=true;observed();
assert.deepEqual(scrolled,['portfolio']);
updates.length=0;scrolled=[];
assert.ok(click('#lab'));
assert.equal(JSON.stringify(updates),JSON.stringify([{id:'workflow-tabs',props:{value:'systems'}}]));
assert.deepEqual(scrolled,['lab']);
for(const modifiers of [{ctrlKey:true},{metaKey:true},{shiftKey:true},{altKey:true},{button:1}]){
  updates.length=0;assert.equal(click('#portfolio',modifiers),false);assert.equal(updates.length,0);
}
assert.ok(updates.every(x=>!['session-data','practice-data','free-data'].includes(x.id)));
console.log('Workflow navigation: both header shortcuts reveal the correct tabs; hidden destinations wait; modified clicks and game stores are preserved.');
