/* Render system help outside the cards so their text cannot paint over it. */
(function () {
  'use strict';
  const pop = document.createElement('aside');
  pop.id = 'system-preview-overlay';
  pop.className = 'system-preview system-preview-overlay';
  pop.setAttribute('role', 'tooltip');
  pop.hidden = true;
  const topLayer = typeof pop.showPopover === 'function';
  if (topLayer) pop.setAttribute('popover', 'manual');
  document.body.append(pop);
  let anchor = null, timer = null;

  function position() {
    if (!anchor) return;
    const r = anchor.querySelector('strong').getBoundingClientRect();
    const width = pop.offsetWidth, height = pop.offsetHeight;
    const left = r.right + width + 12 < innerWidth ? r.right + 12 :
      r.left - width - 12 >= 12 ? r.left - width - 12 :
      Math.max(12, Math.min(r.left, innerWidth - width - 12));
    pop.style.left = left + 'px';
    pop.style.top = Math.max(12, Math.min(r.top, innerHeight - height - 12)) + 'px';
  }
  function hide() {
    clearTimeout(timer);
    if (topLayer && pop.matches(':popover-open')) pop.hidePopover();
    pop.hidden = true;
    anchor = null;
  }
  function show(name) {
    const source = name.querySelector('.system-preview');
    if (!source) return;
    clearTimeout(timer);
    if (anchor !== name) {
      pop.replaceChildren(...Array.from(source.childNodes, node => node.cloneNode(true)));
      pop.setAttribute('aria-label', name.querySelector('strong').textContent + ' — system description');
    }
    anchor = name;
    pop.hidden = false;
    if (topLayer && !pop.matches(':popover-open')) pop.showPopover();
    position();
  }
  document.addEventListener('mouseover', event => {
    if (pop.contains(event.target)) { clearTimeout(timer); return; }
    const name = event.target.closest?.('.system-name');
    if (name) show(name);
  });
  document.addEventListener('mouseout', event => {
    if (!anchor) return;
    const next = event.relatedTarget;
    if (next && (anchor.contains(next) || pop.contains(next))) return;
    if (anchor.contains(event.target) || pop.contains(event.target)) {
      clearTimeout(timer); timer = setTimeout(hide, 150);
    }
  });
  document.addEventListener('click', event => {
    if (!pop.contains(event.target) && !anchor?.matches(':hover')) hide();
  });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') hide(); });
  document.addEventListener('scroll', event => { if (!pop.contains(event.target)) hide(); }, true);
  window.addEventListener('resize', position);
  new MutationObserver(() => {
    if (anchor && (!anchor.isConnected || !anchor.getClientRects().length)) hide();
  }).observe(document.documentElement, {subtree: true, childList: true, attributes: true, attributeFilter: ['style']});
})();
