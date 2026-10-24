/* The server chooses and settles the pocket; this animation only presents it. */
window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.practice = {
  animate: function (command) {
    const prefix = command?.prefix || 'practice';
    const frame = document.getElementById(prefix + '-wheel');
    const rotor = document.getElementById(prefix + '-disc');
    const ball = document.getElementById(prefix + '-ball-track');
    if (!frame || !rotor || !ball || !command) return window.dash_clientside.no_update;
    const order = command.order;
    const index = order.indexOf(String(command.number));
    if (index < 0) return window.dash_clientside.no_update;
    const mod = value => ((value % 360) + 360) % 360;
    const finalAngle = mod(-index * 360 / order.length);
    const image = '/assets/practice-wheel-' + command.wheel + '.svg';
    if (rotor.getAttribute('src') !== image) rotor.setAttribute('src', image);
    const key = command.active ? command.id : 'rest-' + command.wheel + '-' + command.number;
    if (frame.dataset.animationKey === key) return {id:command.id, active:command.active};
    frame.dataset.animationKey = key;
    for (const element of [rotor, ball]) element.getAnimations().forEach(animation => animation.cancel());
    frame.classList.toggle('is-spinning', Boolean(command.active));
    if (!command.active) {
      rotor.style.transform = 'rotate(' + finalAngle + 'deg)';
      rotor.dataset.angle = String(finalAngle);
      ball.style.transform = 'rotate(0deg)';
      return {id:command.id, active:false};
    }
    const from = Number(rotor.dataset.angle || 0);
    const end = from + 5 * 360 + mod(finalAngle - from);
    const duration = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 2800;
    const timing = {duration:duration, easing:'cubic-bezier(.12,.65,.18,1)', fill:'forwards'};
    const settle = () => {
      if (frame.dataset.animationKey !== key) return;
      rotor.style.transform = 'rotate(' + end + 'deg)';
      rotor.dataset.angle = String(mod(end));
      ball.style.transform = 'rotate(0deg)';
      frame.classList.remove('is-spinning');
      window.dash_clientside.set_props(prefix + '-animation-done', {data:{id:command.id}});
    };
    if (!rotor.animate || duration === 0) {
      settle();
    } else {
      const wheelAnimation = rotor.animate([{transform:'rotate(' + from + 'deg)'},{transform:'rotate(' + end + 'deg)'}],timing);
      const ballAnimation = ball.animate([{transform:'rotate(0deg)'},{transform:'rotate(-2160deg)'}],timing);
      Promise.all([wheelAnimation.finished,ballAnimation.finished]).then(settle).catch(() => {});
    }
    return {id:command.id, active:true};
  }
};
