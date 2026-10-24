(function(){
'use strict';
const terms=[
['outside','Outside bets','Bets in boxes outside the numbered grid: red/black, odd/even, low/high, dozens, and columns. Coverage and payouts vary by box. Zero pockets are excluded. The outlined areas show where outside bets are placed.','outside',['outside bets','outside bet','outside box','outside positions']],
['inside','Inside bets','Bets on individual numbers or small neighboring groups within the numbered grid. Examples include straight-up, split, street, corner, and six-line.','inside',['inside bets','inside bet','inside positions']],
['straight','Straight-up','One chip position covering one number. Pays 35:1 net profit: a $5 win earns $175 plus your $5 stake back.','straight',['straight-up','straight']],
['split','Split','One wager on the line between two adjacent numbers. Covers both and pays 17:1 net profit.','split',['split']],
['street','Street','One wager covering a row of three numbers, such as 1–2–3. Place the chip at the outside end of that row. Pays 11:1 net profit.','street',['street']],
['corner','Corner','One wager at the intersection of four number squares, such as 1–2–4–5. Covers all four and pays 8:1 net profit.','corner',['corner']],
['sixline','Six-line','One wager covering two adjacent rows: six numbers, such as 1–6. Place the chip on their shared outside junction. Pays 5:1 net profit.','sixline',['six-line','six line']],
['dozen','Dozen','One wager on 1st 12 (1–12), 2nd 12 (13–24), or 3rd 12 (25–36). Covers 12 numbers and pays 2:1 net profit.','dozen',['dozen','dozens']],
['column','Column','One wager on a vertical column of 12 numbers, such as 1, 4, 7, …, 34. Use its 2 TO 1 box. Pays 2:1 net profit.','column',['column','columns']],
['even','Even-money','A winning bet earns net profit equal to the stake (1:1). Red/black, odd/even, and 1–18/19–36 each cover 18 numbers. Zero pockets are not wins.','even',['even-money']],
['partage','La Partage','At tables offering La Partage, any permitted bet amount on red/black, odd/even, or low (1–18)/high (19–36) qualifies. If zero lands, half your stake is returned and half is lost. The $10 bet on red below is just an example. Inside, dozen, and column bets do not qualify.','partage',['la partage']],
['bankroll','Bankroll','The cash available for the session. Net profit is the current bankroll minus the starting bankroll.',null,['bankroll']],
['base','Base bet','The starting wager, or one unit, used by a progression. A $5 base makes a 1–2–4 Martingale sequence $5, $10, $20.',null,['base bet']],
['recovery','Recovery cycle','A sequence of wagers that attempts to recover earlier losses. It can take several spins and can end when the next required wager exceeds a limit.',null,['recovery cycle','recovery cycles']],
['portfolio','Portfolio','All wagers placed on the same spin. A number may win several overlapping positions; add their returns and subtract every stake to find net profit.',null,['portfolio','portfolios']],
['adaptive','Adaptive','A plan that chooses the next stake, and sometimes the bet type, using your remaining bankroll and spins. Recheck the policy after every result.',null,['adaptive']],
['policy','Policy','The calculator’s plan for which wager or combination to use in each bankroll-and-spins situation. It does not predict the next number.',null,['policy']],
['edge','House edge','The long-run average loss per dollar wagered under the chosen rules. It is not the probability of losing the session. More total wagering usually means more expected loss.',null,['house edge']],
['net','Net profit','Winnings after subtracting stakes and earlier losses. A 5:1 payout on a $10 six-line bet earns $50 net and returns $60 including the stake.',null,['net profit']],
['worst','Worst 5%','The average net result among the worst five percent of modeled sessions. This describes severe downside, rather than the most likely result.',null,['worst 5%','worst 5% average']],
['chip','Chip size','The increment used for legal wagers. With $5 chips, stakes must be multiples of $5. French half-refunds may leave smaller cash amounts.',null,['chip size']]
];
terms.push(...(window.CrimsonCalculusExtraDefinitions||[]));
const byId=new Map(terms.map(x=>[x[0],x]));
const aliases=new Map();terms.forEach(t=>t[4].forEach(a=>aliases.set(a,t[0])));
const escape=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
const pattern=new RegExp('\\b('+Array.from(aliases.keys()).sort((a,b)=>b.length-a.length).map(escape).join('|')+')(?![\\w-])','gi');
let anchor=null,timer=null,scheduled=false,pinned=false;
const pop=document.createElement('aside');pop.id='roulette-definition';pop.className='roulette-definition';pop.hidden=true;pop.setAttribute('role','dialog');pop.setAttribute('aria-label','Roulette term definition');
const close=document.createElement('button');close.type='button';close.className='definition-close';close.textContent='×';close.setAttribute('aria-label','Close definition');
const title=document.createElement('h3'),desc=document.createElement('div'),img=document.createElement('img'),caption=document.createElement('small');
caption.textContent='Illustrative single-zero layout. Ivory outlines show covered numbers; the striped chip marks where to place the bet.';
pop.append(close,title,desc,img,caption);
function hide(){pinned=false;clearTimeout(timer);if(anchor)anchor.setAttribute('aria-expanded','false');anchor=null;pop.hidden=true;}
function position(){
 if(!anchor)return;const r=anchor.getBoundingClientRect(),w=pop.offsetWidth,h=pop.offsetHeight;
 const side=r.right+w+12<innerWidth?r.right+12:r.left-w-12>=10?r.left-w-12:Math.max(10,Math.min(r.left,innerWidth-w-10));
 pop.style.left=side+'px';
 const below=r.bottom+8;pop.style.top=Math.max(10,below+h<innerHeight-10?below:r.top-h-8)+'px';
}
function show(el){
 clearTimeout(timer);if(anchor&&anchor!==el)anchor.setAttribute('aria-expanded','false');
 anchor=el;const t=byId.get(el.dataset.rouletteTerm);title.textContent=t[1];desc.replaceChildren();
 if(t[5]){
  const info=t[5];
  for(const [label,value] of [['How it works',info.how],['Example',info.example],['Pros',info.pros],['Cons / risks',info.cons],['What losses can look like',info.pattern],['Why it may stop with cash left',info.stop]]){
   const heading=document.createElement('strong');heading.className='definition-label';heading.textContent=label;desc.append(heading);
   if(Array.isArray(value)){const list=document.createElement('ul');for(const text of value){const li=document.createElement('li');li.textContent=text;list.append(li);}desc.append(list);}
   else{const paragraph=document.createElement('p');paragraph.textContent=value;desc.append(paragraph);}
  }
  const note=document.createElement('small');note.textContent=info.note;desc.append(note);
 }else{const paragraph=document.createElement('p');paragraph.textContent=t[2];desc.append(paragraph);}

 caption.textContent=({partage:'Only a zero triggers the half-refund. In this app, that half-loss advances a named progression as a loss. En Prison is a different rule and is not modeled.',inside:'The ivory frame outlines the inside betting area, including zero. Bets cover individual numbers or neighboring groups.',outside:'The ivory frames outline the outside betting areas: dozens on the left, columns below, and the six even-money boxes on the right.',even:'The ivory frame outlines the six even-money betting boxes. Each box is a separate choice, not one combined bet.'})[t[0]]||'Illustrative single-zero layout. Ivory outlines show covered numbers; the striped chip marks where to place the bet.';
 img.hidden=!t[3];caption.hidden=!t[3];if(t[3]){img.src='/assets/definitions/'+t[3]+'.svg';img.alt=t[0]==='partage'?'A $10 red bet splits into $5 returned and $5 lost when zero lands':['inside','outside','even'].includes(t[0])?t[1]+': betting areas outlined with ivory frames':t[1]+': highlighted covered numbers and chip placement';}
 pop.hidden=false;el.setAttribute('aria-expanded','true');position();
}
img.addEventListener('load',position);
close.addEventListener('click',()=>{const old=anchor;old?.focus();hide();});
function trigger(text,id){
 const el=document.createElement('span');el.className='roulette-term';el.dataset.rouletteTerm=id;el.textContent=text;el.tabIndex=0;
 el.setAttribute('role','button');el.setAttribute('aria-haspopup','dialog');el.setAttribute('aria-expanded','false');el.setAttribute('aria-controls',pop.id);el.setAttribute('aria-label',text+' — definition');return el;
}
function scan(){
 scheduled=false;
 if(!document.body)return;
 if(!pop.isConnected)document.body.append(pop);
 const root=document.getElementById('roulette-glossary');
 if(root&&!root.children.length){
 const note=document.createElement('p');note.textContent='All terms, betting systems, and roulette types, in alphabetical order. Hover, focus, or tap a dotted term for its definition. Bet definitions include diagrams.';root.append(note);
 const row=document.createElement('div');row.className='glossary-terms';[...terms].sort((a,b)=>a[1].localeCompare(b[1])).forEach(t=>row.append(trigger(t[1],t[0])));root.append(row);
 }
 const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
 const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
 for(const node of nodes){
  if(!node.parentElement||node.parentElement.closest('.roulette-term,.system-preview,#tutorial-dialog,#roulette-glossary,#roulette-definition,script,style,textarea,input,button,a,svg,canvas,[role="option"],[role="listbox"],[role="combobox"],.js-plotly-plot,[contenteditable]'))continue;
  pattern.lastIndex=0;const text=node.nodeValue;if(!pattern.test(text))continue;pattern.lastIndex=0;
  const fragment=document.createDocumentFragment();let end=0;
  for(const match of text.matchAll(pattern)){
   fragment.append(document.createTextNode(text.slice(end,match.index)),trigger(match[0],aliases.get(match[0].toLowerCase())));end=match.index+match[0].length;
  }
  fragment.append(document.createTextNode(text.slice(end)));node.replaceWith(fragment);
 }
 if(anchor&&!anchor.isConnected)hide();
}
function schedule(){if(!scheduled){scheduled=true;requestAnimationFrame(scan);}}
document.addEventListener('mouseover',e=>{const el=e.target.closest?.('.roulette-term');if(el&&!pinned)show(el);if(pop.contains(e.target))clearTimeout(timer);});
document.addEventListener('mouseout',e=>{if(e.target.closest?.('.roulette-term')||pop.contains(e.target)){clearTimeout(timer);if(!pinned)timer=setTimeout(hide,250);}});
document.addEventListener('focusin',e=>{const el=e.target.closest?.('.roulette-term');if(el)show(el);else if(!pop.contains(e.target))hide();});
document.addEventListener('click',e=>{const el=e.target.closest?.('.roulette-term');if(el){e.preventDefault();show(el);pinned=true;}else if(!pop.contains(e.target))hide();});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!pop.hidden){e.preventDefault();e.stopImmediatePropagation();hide();}if((e.key==='Enter'||e.key===' ')&&e.target.matches?.('.roulette-term')){e.preventDefault();show(e.target);}});
window.addEventListener('resize',position);document.addEventListener('scroll',hide,true);
new MutationObserver(schedule).observe(document.documentElement,{childList:true,subtree:true});schedule();
})();
