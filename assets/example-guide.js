/* Focus, Escape and backdrop support for the calculator-only example. */
(function(){
  'use strict';let opener=null,wasOpen=false;
  function open(){const modal=document.getElementById('example-modal');return modal && getComputedStyle(modal).display!=='none';}
  function sync(){const now=open();if(now&&!wasOpen){opener=document.activeElement;document.getElementById('example-close')?.focus();}if(!now&&wasOpen&&opener?.isConnected)opener.focus();wasOpen=now;}
  new MutationObserver(sync).observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:['style']});
  document.addEventListener('click',event=>{if(event.target.id==='example-modal')document.getElementById('example-close')?.click();});
  document.addEventListener('keydown',event=>{
    if(!open())return;
    if(event.key==='Escape'){event.preventDefault();document.getElementById('example-close')?.click();}
    if(event.key==='Tab'){
      const items=[...document.querySelectorAll('#example-modal button:not([disabled]),#example-modal a[href]')].filter(e=>e.getClientRects().length);
      const first=items[0],last=items[items.length-1];
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
    }
  });
})();
