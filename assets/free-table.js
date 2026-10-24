/* Preview exact coverage for native clickable roulette-table positions. */
(function () {
  'use strict';
  function preview(event) {
    const button=event.target.closest('[data-free-bet]');
    if(!button || button.disabled)return;
    const board=button.closest('.free-table-wrap');
    if(!board)return;
    const numbers=new Set((button.dataset.betNumbers || '').split(','));
    board.querySelectorAll('[data-pocket]').forEach(cell => cell.classList.toggle('is-preview',numbers.has(cell.dataset.pocket)));
    const text=board.querySelector('.free-table-preview');
    if(text)text.textContent=button.dataset.betLabel+' · covers '+Array.from(numbers).join(', ')+' · pays '+button.dataset.betPayout+':1 net profit.';
  }
  function clear(event) {
    const board=event.target.closest('.free-table-wrap');
    if(!board || (event.relatedTarget && board.contains(event.relatedTarget)))return;
    board.querySelectorAll('.is-preview').forEach(cell=>cell.classList.remove('is-preview'));
    const text=board.querySelector('.free-table-preview');
    if(text)text.textContent='Hover over a number, dividing line, intersection or street edge to preview the bet.';
  }
  document.addEventListener('mouseover',preview);
  document.addEventListener('focusin',preview);
  document.addEventListener('mouseout',clear);
  document.addEventListener('focusout',clear);
})();
