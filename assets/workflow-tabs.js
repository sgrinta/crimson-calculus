/* Add standard keyboard/ARIA behavior to Dash's persistent navigation tabs. */
(function () {
  'use strict';
  let scheduled = false;
  let pendingDestination = null;
  function revealDestination() {
    const destination = pendingDestination && document.getElementById(pendingDestination);
    if (!destination?.getClientRects().length) return;
    pendingDestination = null;
    // Let the primary-tab resize/scroll callback finish before revealing the tool.
    requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(() => {
      if (destination.isConnected && destination.getClientRects().length) {
        destination.scrollIntoView({block:'start', behavior:'instant'});
      }
    })));
  }
  function syncTabs() {
    scheduled = false;
    document.querySelectorAll('.workflow-tab-list').forEach(list => {
      list.setAttribute('role', 'tablist');
      list.setAttribute('aria-label', ({'workflow-tabs':'Session steps','systems-view':'System views','session-view':'Session views','tools-view':'Tools and learning','practice-view':'Practice views','practice-mode':'Practice modes','free-view':'Free-play views'})[list.id] || 'Views');
      list.querySelectorAll('.workflow-tab').forEach(tab => {
        const selected = tab.classList.contains('workflow-tab-selected');
        tab.setAttribute('role', 'tab');
        tab.setAttribute('aria-selected', String(selected));
        tab.tabIndex = selected ? 0 : -1;
        const panelId = tab.id.replace('-tab-', '-panel-');
        const panel = document.getElementById(panelId);
        if (panel) tab.setAttribute('aria-controls', panelId);
        if (list.id === 'session-view') {
          tab.setAttribute('aria-controls', 'session-result');
          if (selected) document.getElementById('session-result')?.setAttribute('aria-labelledby', tab.id);
        }
      });
    });
    revealDestination();
  }
  function schedule() {
    if (!scheduled) { scheduled = true; requestAnimationFrame(syncTabs); }
  }
  document.addEventListener('click', event => {
    const link = event.target.closest?.('.topbar a[href="#lab"],.topbar a[href="#portfolio"]');
    if (!link || event.button > 0 || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const setProps = window.dash_clientside?.set_props;
    if (!setProps) return;
    event.preventDefault();
    const builder = link.getAttribute('href') === '#portfolio';
    pendingDestination = builder ? 'portfolio' : 'lab';
    setProps('workflow-tabs', {value:builder ? 'tools' : 'systems'});
    if (builder) setProps('tools-view', {value:'builder'});
    schedule();
  });
  document.addEventListener('keydown', event => {
    const tab = event.target.closest('.workflow-tab');
    if (!tab) return;
    const tabs = Array.from(tab.closest('.workflow-tab-list').querySelectorAll('.workflow-tab'));
    const index = tabs.indexOf(tab);
    let next;
    if (event.key === 'ArrowRight') next = tabs[(index + 1) % tabs.length];
    else if (event.key === 'ArrowLeft') next = tabs[(index + tabs.length - 1) % tabs.length];
    else if (event.key === 'Home') next = tabs[0];
    else if (event.key === 'End') next = tabs[tabs.length - 1];
    else if (event.key === 'Enter' || event.key === ' ') next = tab;
    if (next) { event.preventDefault(); next.click(); next.focus(); }
  });
  new MutationObserver(schedule).observe(document.documentElement, {subtree:true, childList:true, attributes:true, attributeFilter:['class','style']});
  schedule();
})();
