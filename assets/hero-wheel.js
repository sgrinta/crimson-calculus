/* An independent display spin. Never records a game result or calls Dash/AI. */
(function () {
  'use strict';
  const mod = value => ((value % 360) + 360) % 360;
  const active = new WeakMap();
  function dealerRest() {
    window.CrimsonDealerWink?.rest();
  }
  function dealerWink() {
    window.CrimsonDealerWink?.play();
  }
  function randomUnit() {
    const sample = new Uint32Array(1);
    window.crypto.getRandomValues(sample);
    return sample[0] / 4294967296;
  }
  function randomIndex(count) {
    const sample = new Uint32Array(1);
    const limit = Math.floor(4294967296 / count) * count;
    do { window.crypto.getRandomValues(sample); } while (sample[0] >= limit);
    return sample[0] % count;
  }
  function reset(button) {
    dealerRest();
    const spin = active.get(button);
    active.delete(button); // Invalidate completion handlers before cancelling.
    spin?.animations.forEach(animation => animation.cancel());
    button.querySelector('.hero-wheel-disc').style.transform = '';
    button.querySelector('.hero-wheel-disc').dataset.angle = '0';
    button.querySelector('.hero-ball-orbit').style.transform = '';
    button.querySelector('.hero-ball-orbit').dataset.angle = '0';
    button.querySelector('.hero-ball').style.top = '14.2%';
    button.disabled = false;
    button.removeAttribute('aria-busy');
    document.getElementById('hero-wheel-status').textContent = 'Click the wheel to spin it. Display only; no session result is recorded.';
  }
  function watchWheel() {
    const button = document.getElementById('hero-wheel-spin');
    if (!button || button.dataset.ballReady) return;
    button.dataset.ballReady = 'true';
    new MutationObserver(() => reset(button)).observe(button.querySelector('.hero-wheel-disc'), {attributes:true,attributeFilter:['src']});
  }
  new MutationObserver(watchWheel).observe(document.documentElement, {childList:true,subtree:true});
  watchWheel();
  document.addEventListener('click', event => {
    const button = event.target.closest?.('#hero-wheel-spin');
    if (!button || button.disabled) return;
    const disc = button.querySelector('.hero-wheel-disc');
    const orbit = button.querySelector('.hero-ball-orbit');
    const ball = button.querySelector('.hero-ball');
    const status = document.getElementById('hero-wheel-status');
    const wheel = disc.getAttribute('src').match(/practice-wheel-(single|french|double|triple)\.svg/)?.[1];
    const order = JSON.parse(button.dataset.wheelOrders)[wheel];
    if (!order) return;
    const index = randomIndex(order.length);
    const number = order[index];
    const color = /^0+$/.test(number) ? 'zero' : JSON.parse(button.dataset.redNumbers).includes(Number(number)) ? 'red' : 'black';
    const from = Number(disc.dataset.angle || 0);
    const ballFrom = Number(orbit.dataset.angle || 0);
    const travel = 1080 + randomUnit() * 1080; // At least three full wheel turns.
    const end = from + travel;
    const dropWheel = end;
    const pocketAngle = index * 360 / order.length;
    // Both rotations stop at first pocket contact; only the radial settling bounce continues.
    const ballDrop = ballFrom - (4 + Math.floor(randomUnit() * 3)) * 360 - mod(ballFrom - dropWheel - pocketAngle);
    const ballEnd = ballDrop;
    const duration = 4600 + randomUnit() * 1000;
    const spin = {animations:[]};
    dealerRest();
    active.set(button, spin);
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    status.textContent = 'Display wheel and ball spinning. No session result is recorded.';
    const finish = () => {
      if (active.get(button) !== spin) return;
      active.delete(button);
      disc.style.transform = 'rotate(' + mod(end) + 'deg)';
      disc.dataset.angle = String(mod(end));
      orbit.style.transform = 'rotate(' + mod(ballEnd) + 'deg)';
      orbit.dataset.angle = String(mod(ballEnd));
      ball.style.top = '14.2%';
      dealerWink();
      button.disabled = false;
      button.removeAttribute('aria-busy');
      status.textContent = 'Display result: ' + number + ', ' + color + '. Click or press Enter to spin again. No session result was recorded.';
    };
    if (!disc.animate || window.matchMedia('(prefers-reduced-motion: reduce)').matches) { finish(); return; }
    const easing = 'cubic-bezier(.12,.65,.18,1)';
    const timing = {duration:duration};
    spin.animations = [
      disc.animate([
        {transform:'rotate(' + from + 'deg)',offset:0,easing:easing},
        {transform:'rotate(' + dropWheel + 'deg)',offset:.82,easing:easing},
        {transform:'rotate(' + end + 'deg)',offset:1}
      ], timing),
      orbit.animate([
        {transform:'rotate(' + ballFrom + 'deg)',offset:0,easing:'cubic-bezier(.25,.45,.5,1)'},
        {transform:'rotate(' + ballDrop + 'deg)',offset:.82,easing:easing},
        {transform:'rotate(' + ballEnd + 'deg)',offset:1}
      ], timing),
      ball.animate([
        {top:'14.2%',offset:0}, {top:'3.1%',offset:.04},
        {top:'3.1%',offset:.64}, {top:'5.5%',offset:.72},
        {top:'11%',offset:.78}, {top:'14.2%',offset:.82},
        {top:'13.5%',offset:.89}, {top:'14.5%',offset:.94},
        {top:'14.2%',offset:1}
      ], timing)
    ];
    Promise.all(spin.animations.map(animation => animation.finished)).then(finish, () => {
      if (active.get(button) === spin) reset(button);
    });
  });
})();
