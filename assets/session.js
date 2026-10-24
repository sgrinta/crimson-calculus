(function(){
 let pending=null;
 function reveal(){
  const heading=document.querySelector('#session-result h2');
  if(pending&&heading?.textContent===pending){
   pending=null;
   requestAnimationFrame(()=>requestAnimationFrame(()=>document.getElementById('next-step')?.scrollIntoView({behavior:'instant',block:'start'})));
  }
 }
 document.addEventListener('click',e=>{
  const button=e.target.closest?.('.system-option');
  if(button){pending=button.querySelector('strong')?.textContent;requestAnimationFrame(reveal);}
 });
 new MutationObserver(reveal).observe(document.documentElement,{subtree:true,childList:true});
})();
