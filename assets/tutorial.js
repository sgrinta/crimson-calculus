/* Prepared screenshot walkthrough. No session stores or AI calls are touched. */
(function () {
  'use strict';
  let chapter = 0;
  let control = 0;
  let returnFocus = null;
  let observer = null;
  function dialog() { return document.getElementById('tutorial-dialog'); }
  function pages() { return Array.from(dialog().querySelectorAll('.tutorial-page')); }
  function items(page) { return Array.from(page.querySelectorAll('[data-control-box]')); }
  function highlight() {
    const root = dialog();
    if (!root?.open) return;
    const page = pages()[chapter];
    const img = page.querySelector('.tutorial-screenshot-stage img');
    if (!img.complete || !img.naturalWidth) return;
    const stage = page.querySelector('.tutorial-screenshot-stage');
    const bounds = stage.getBoundingClientRect();
    // The image uses object-fit:contain; map percentages to its actual painted pixels.
    const scale = Math.min(stage.clientWidth / img.naturalWidth, stage.clientHeight / img.naturalHeight);
    const width = img.naturalWidth * scale;
    const height = img.naturalHeight * scale;
    const [x,y,w,h] = JSON.parse(items(page)[control].dataset.controlBox);
    const spot = page.querySelector('.tutorial-spotlight');
    Object.assign(spot.style, {
      left: ((stage.clientWidth-width)/2+x*width/100)+'px',
      top: ((stage.clientHeight-height)/2+y*height/100)+'px',
      width: (w*width/100)+'px', height: (h*height/100)+'px',
      visibility: bounds.width ? 'visible' : 'hidden'
    });
    spot.querySelector('.tutorial-spotlight-number').style.top = parseFloat(spot.style.top) < 22 ? '2px' : '-21px';
  }
  function show(chapterIndex, controlIndex, focus) {
    const root = dialog();
    if (!root) return;
    const allPages = pages();
    chapter = Math.max(0,Math.min(chapterIndex,allPages.length-1));
    control = Math.max(0,Math.min(controlIndex,items(allPages[chapter]).length-1));
    const page = allPages[chapter];
    const entry = items(page)[control];
    allPages.forEach((p,i) => { p.hidden = i !== chapter; });
    const chapters = Array.from(root.querySelectorAll('[data-tutorial-step]'));
    chapters.forEach((button,i) => {
      if (i === chapter) button.setAttribute('aria-current','step');
      else button.removeAttribute('aria-current');
    });
    chapters[chapter].scrollIntoView({block:'nearest',inline:'nearest',behavior:'instant'});
    page.querySelector('.tutorial-control-title').textContent = entry.dataset.controlTitle;
    page.querySelector('.tutorial-control-explanation').textContent = entry.dataset.controlExplanation;
    page.querySelector('.tutorial-speaker').textContent = `VIVIENNE EXPLAINS · ${control+1} OF ${items(page).length}`;
    page.querySelector('.tutorial-spotlight-number').textContent = String(control+1);
    const previous = allPages.slice(0,chapter).reduce((n,p)=>n+items(p).length,0);
    const total = allPages.reduce((n,p)=>n+items(p).length,0);
    document.getElementById('tutorial-progress').textContent = `Control ${previous+control+1} of ${total} · ${chapters[chapter].textContent.slice(2)}`;
    document.getElementById('tutorial-back').disabled = chapter === 0 && control === 0;
    document.getElementById('tutorial-next').textContent = chapter === allPages.length-1 && control === items(page).length-1 ? 'Finish tour ✓' : 'Next →';
    root.querySelector('.tutorial-content').scrollTop = 0;
    highlight();
    requestAnimationFrame(highlight);
    if (focus) page.querySelector('h3').focus({preventScroll:true});
  }
  function move(direction) {
    const allPages = pages();
    const next = control+direction;
    if (next >= 0 && next < items(allPages[chapter]).length) show(chapter,next,true);
    else if (direction > 0 && chapter < allPages.length-1) show(chapter+1,0,true);
    else if (direction < 0 && chapter > 0) show(chapter-1,items(allPages[chapter-1]).length-1,true);
  }
  document.addEventListener('click', function(event) {
    const root = dialog();
    if (!root) return;
    const trigger = event.target.closest('[data-tutorial-open],[data-tutorial-close],[data-tutorial-step],#tutorial-back,#tutorial-next');
    if (!trigger) return;
    if (trigger.hasAttribute('data-tutorial-open')) {
      returnFocus = trigger;
      if (!root.open) root.showModal();
      if (!observer) {
        observer = new ResizeObserver(highlight);
        root.querySelectorAll('.tutorial-screenshot-stage').forEach(stage=>observer.observe(stage));
        root.querySelectorAll('.tutorial-screenshot-stage img').forEach(img=>img.addEventListener('load',highlight));
      }
      show(0,0,true);
    } else if (trigger.hasAttribute('data-tutorial-close')) root.close();
    else if (trigger.hasAttribute('data-tutorial-step')) show(Number(trigger.dataset.tutorialStep),0,true);
    else if (trigger.id === 'tutorial-back') move(-1);
    else if (trigger.id === 'tutorial-next') {
      if (chapter === pages().length-1 && control === items(pages()[chapter]).length-1) root.close();
      else move(1);
    }
  });
  document.addEventListener('keydown', function(event) {
    if (!dialog()?.open || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault(); move(event.key === 'ArrowRight' ? 1 : -1);
    }
  });
  document.addEventListener('close', function(event) {
    if (event.target.id === 'tutorial-dialog' && returnFocus?.isConnected) returnFocus.focus({preventScroll:true});
  },true);
})();
