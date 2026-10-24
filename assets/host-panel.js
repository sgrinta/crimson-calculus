/* Modeless local shell: it never remounts a game or writes to session stores. */
(function () {
  'use strict';
  let returnFocus = null;
  function setOpen(open, trigger) {
    const panel = document.getElementById('host-panel');
    const launcher = document.getElementById('host-launcher');
    if (!panel || !launcher) return;
    if (open && panel.hidden) returnFocus = trigger || document.activeElement;
    panel.hidden = !open;
    document.querySelectorAll('[data-host-toggle],[data-host-open]').forEach(el => el.setAttribute('aria-expanded', String(open)));
    launcher.classList.toggle('is-open', open);
    launcher.setAttribute('aria-label', (open ? 'Minimize' : 'Open') + ' Vivienne, AI host and analyst');
    if (open) {
      requestAnimationFrame(() => {
        const prompt = document.getElementById('prompt');
        (prompt && !prompt.disabled ? prompt : document.getElementById('host-close'))?.focus({preventScroll:true});
        const thread = document.getElementById('thread');
        if (thread) thread.scrollTop = thread.scrollHeight;
      });
    } else if (returnFocus?.isConnected) returnFocus.focus({preventScroll:true});
  }
  document.addEventListener('click', event => {
    const trigger = event.target.closest?.('[data-host-toggle],[data-host-open],[data-host-close]');
    if (!trigger) return;
    event.preventDefault();
    const panel = document.getElementById('host-panel');
    if (!panel) return;
    setOpen(trigger.hasAttribute('data-host-close') ? false : trigger.hasAttribute('data-host-open') ? true : panel.hidden, trigger);
  });
  // A review link also reveals the form when Step 1 is already selected.
  let reviewPending = false;
  function revealSettings() {
    const panel = document.getElementById('workflow-tabs-panel-settings');
    if (!reviewPending || !panel || !panel.getClientRects().length) return;
    reviewPending = false;
    requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(() => {
      const form = panel.querySelector('.scenario-panel');
      form?.scrollIntoView({block:'start', behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
    })));
  }
  document.addEventListener('click', event => {
    if (!event.target.closest?.('.host-settings-update button')) return;
    reviewPending = true;
    requestAnimationFrame(revealSettings);
  });
  new MutationObserver(revealSettings).observe(document.documentElement,{subtree:true,attributes:true,attributeFilter:['style']});
  document.addEventListener('keydown', event => {
    if (document.getElementById('tutorial-dialog')?.open) return;
    const panel = document.getElementById('host-panel');
    if (event.key !== 'Escape' || !panel || panel.hidden) return;
    if (document.querySelector('#roulette-definition:not([hidden]),#system-preview-overlay:not([hidden])')) return;
    event.preventDefault(); setOpen(false);
  });
})();
