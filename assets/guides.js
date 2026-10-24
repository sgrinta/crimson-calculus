(function(){
  let wasOpen=false,previousFocus=null;
  function sync(){
    const modal=document.getElementById('strategy-guide-modal');
    const open=modal && modal.style.display!=='none';
    if(open && !wasOpen){previousFocus=document.activeElement;document.body.style.overflow='hidden';document.getElementById('close-strategy-guide')?.focus();}
    if(!open && wasOpen){document.body.style.overflow='';if(previousFocus?.isConnected)previousFocus.focus();}
    wasOpen=!!open;
  }
  document.addEventListener('keydown',function(e){
    const modal=document.getElementById('strategy-guide-modal');
    if(!modal || modal.style.display==='none')return;
    if(e.key==='Escape'){e.preventDefault();document.getElementById('close-strategy-guide')?.click();}
    if(e.key==='Tab'){
      const items=Array.from(modal.querySelectorAll('button,a[href],input,select,textarea,[tabindex="0"]')).filter(el=>!el.disabled && el.getClientRects().length);
      if(!items.length)return;
      if(e.shiftKey && document.activeElement===items[0]){e.preventDefault();items[items.length-1].focus();}
      if(!e.shiftKey && document.activeElement===items[items.length-1]){e.preventDefault();items[0].focus();}
    }
  });
  document.addEventListener('click',e=>{if(e.target.id==='strategy-guide-modal')document.getElementById('close-strategy-guide')?.click();});
  new MutationObserver(sync).observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:['style']});
})();
