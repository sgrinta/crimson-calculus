/* Override the installed number stepper's unbounded-max bug and add modifier clicks. */
(function () {
  'use strict';
  const hint='Click ±1 · Ctrl/⌘ click ±10 · Shift click ±100 · Ctrl/⌘ + Shift click ±1,000';
  function increment(event) {
    return event.shiftKey ? ((event.ctrlKey || event.metaKey) ? 1000 : 100) : ((event.ctrlKey || event.metaKey) ? 10 : 1);
  }
  function bound(input,name) {
    const raw=input.getAttribute(name);
    return raw===null || raw.trim()==='' ? NaN : Number(raw);
  }
  function adjusted(current,direction,amount,min,max) {
    let value=(Number.isFinite(current) ? current : 0)+direction*amount;
    if(Number.isFinite(min))value=Math.max(value,min);
    if(Number.isFinite(max))value=Math.min(value,max);
    return Number(value.toFixed(10));
  }
  function control(button) {
    return button.closest('.dash-input-container')?.querySelector('input[type="number"]');
  }
  function annotate() {
    document.querySelectorAll('.dash-input-stepper').forEach(button=>{
      if(!control(button))return;
      if(button.title!==hint)button.title=hint;
      if(!button.hasAttribute('aria-describedby'))button.setAttribute('aria-describedby','numeric-click-help');
    });
  }
  function buttonFor(event) {return event.target.closest?.('.dash-input-stepper');}
  function stop(event) {event.preventDefault();event.stopImmediatePropagation();}
  function apply(event,button) {
    const input=control(button);
    if(!input || !input.id || input.disabled || input.readOnly || button.disabled)return;
    // Stop the built-in React stepper from running a second time or producing NaN.
    stop(event);
    const direction=button.classList.contains('dash-stepper-decrement') ? -1 : 1;
    const value=adjusted(input.value.trim()==='' ? NaN : Number(input.value),direction,increment(event),bound(input,'min'),bound(input,'max'));
    if(!Number.isFinite(value))return;
    // Use the native setter so React observes the input event and refreshes its local state.
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,String(value));
    input.dispatchEvent(new Event('input',{bubbles:true}));
    input.dispatchEvent(new Event('change',{bubbles:true}));
    // Public Dash API also commits debounced fields immediately for the next action.
    let id=input.id;
    if(id.startsWith('{')){try{id=JSON.parse(id);}catch(_){return;}}
    window.dash_clientside.set_props(id,{value:value});
  }
  // macOS turns Control-click into a context-menu gesture instead of a click.
  // Commit on pointer-down in that case, then consume any subsequent click once.
  let controlPress=null;
  document.addEventListener('pointerdown',event=>{
    const button=buttonFor(event);
    if(!button || !event.ctrlKey || event.button!==0)return;
    controlPress={button:button,pointerId:event.pointerId};
    apply(event,button);
  },true);
  function release(event) {
    const press=controlPress;
    if(press && press.pointerId===event.pointerId)setTimeout(()=>{if(controlPress===press)controlPress=null;},0);
  }
  document.addEventListener('pointerup',release,true);
  document.addEventListener('pointercancel',release,true);
  document.addEventListener('contextmenu',event=>{
    if(event.ctrlKey && buttonFor(event))stop(event);
  },true);
  document.addEventListener('click',event=>{
    const button=buttonFor(event);
    if(!button)return;
    if(controlPress?.button===button){controlPress=null;stop(event);return;}
    apply(event,button);
  },true);
  let scheduled=false;
  function schedule() {
    if(scheduled)return;
    scheduled=true;
    requestAnimationFrame(()=>{scheduled=false;annotate();});
  }
  new MutationObserver(schedule).observe(document.documentElement,{subtree:true,childList:true});
  schedule();
  // Small pure surface used by local regression tests; no app/session state is exposed.
  if(typeof module!=='undefined' && module.exports)module.exports={increment:increment,adjusted:adjusted};
})();
