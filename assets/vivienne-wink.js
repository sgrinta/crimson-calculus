/* A continuous local eyelid deformation of Vivienne's original portrait.
   The portrait is mirrored in CSS: source-left is the viewer's RIGHT eye.
   No alternate face, raster asset edit, provider call, or session update. */
(function () {
  'use strict';
  const DURATION = 440;
  const PATCH = {left:452, right:552, top:224, bottom:326};
  const clamp = n => Math.min(1, Math.max(0, n));
  const ease = t => t*t*(3-2*t);
  function closureAt(ms) {
    if (ms < 0 || ms >= DURATION) return 0;
    if (ms < 125) return ease(ms/125);
    if (ms < 160) return 1;
    return 1-ease((ms-160)/(DURATION-160));
  }
  function eyelid(x, closure) {
    const q = (x-503)/36;
    const envelope = Math.pow(Math.max(0, 1-q*q), .65);
    const line = 272 + .30*(x-503);
    const upper = line-.35-10*envelope;
    const lower = line+.35+8*envelope;
    const closed = line+3*envelope;
    return {upper, lower,
      upperTo:upper+(closed-upper)*clamp(closure),
      lowerTo:lower+(closed+.65-lower)*clamp(closure)};
  }
  function draw(canvas, source, closure) {
    if (!canvas || !source?.complete || !source.naturalWidth) return false;
    // Match the original 1024×1536 coordinate space at any source resolution.
    if (canvas.width !== 1024 || canvas.height !== 1536) {
      canvas.width=1024; canvas.height=1536;
    }
    const context=canvas.getContext('2d');
    if (!context) return false;
    context.clearRect(0,0,1024,1536);
    if (closure <= 0) return true;
    const sx=source.naturalWidth/1024, sy=source.naturalHeight/1536;
    // Warp the eyelid and adjacent skin continuously, retaining the original
    // eye corners, face, lighting and dress. The pupil collapses beneath the lid.
    for(let x=PATCH.left;x<PATCH.right;x++) {
      const lid=eyelid(x+.5,closure);
      const src=[PATCH.top,lid.upper,lid.lower,PATCH.bottom];
      const dst=[PATCH.top,lid.upperTo,lid.lowerTo,PATCH.bottom];
      for(let j=0;j<3;j++) {
        context.drawImage(source,x*sx,src[j]*sy,sx,(src[j+1]-src[j])*sy,
          x,dst[j],1,dst[j+1]-dst[j]);
      }
    }
    canvas.dataset.closure=clamp(closure).toFixed(3);
    return true;
  }
  let request=null;
  let generation=0;
  function rest() {
    generation++;
    if(request !== null) window.cancelAnimationFrame(request);
    request=null;
    const canvas=document.querySelector('#hero-dealer .hero-dealer-eyelid');
    if(canvas) {
      canvas.getContext('2d')?.clearRect(0,0,canvas.width,canvas.height);
      canvas.dataset.closure='0';
    }
    document.getElementById('hero-dealer')?.classList.remove('is-winking');
  }
  function play() {
    rest();
    if(window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const dealer=document.getElementById('hero-dealer');
    const source=dealer?.querySelector('.hero-dealer-rest');
    const canvas=dealer?.querySelector('.hero-dealer-eyelid');
    if(!canvas || !source?.complete || !source.naturalWidth) return;
    const token=generation;
    let start;
    dealer.classList.add('is-winking');
    function frame(now) {
      if(token!==generation || !dealer.isConnected) return;
      if(start===undefined) start=now;
      const elapsed=now-start;
      if(elapsed>=DURATION) {rest();return;}
      draw(canvas,source,closureAt(elapsed));
      request=window.requestAnimationFrame(frame);
    }
    request=window.requestAnimationFrame(frame);
  }
  window.CrimsonDealerWink={play,rest,draw,closureAt,duration:DURATION};
  document.addEventListener('visibilitychange',()=>{if(document.hidden) rest();});
  if(typeof module!=='undefined' && module.exports) module.exports={closureAt,eyelid,PATCH,DURATION};
})();
