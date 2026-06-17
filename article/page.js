(() => {
  const lines = [...document.querySelectorAll('[data-wave]')].map((el) => {
    const seg = +el.dataset.seg;
    const rand = [];
    for (let i = 0; i <= seg; i++) rand.push(0.35 + Math.random() * 0.65);
    return { el, seg, mid: +el.dataset.mid, amp: +el.dataset.amp, speed: +el.dataset.speed, phase: +el.dataset.phase, rand };
  });
  const t0 = performance.now();
  function tick(now) {
    const t = (now - t0) / 1000;
    lines.forEach((line) => {
      const env = 0.42 + 0.58 * Math.abs(Math.sin(t * line.speed + line.phase));
      let points = '';
      for (let i = 0; i <= line.seg; i++) {
        const x = Math.round((i * 1440) / line.seg);
        const dir = i % 2 ? 1 : -1;
        const flutter = Math.sin(t * 6.5 + i * 1.9 + line.phase) * 0.16;
        const a = line.amp * line.rand[i] * Math.max(0.08, env + flutter);
        points += x + ',' + Math.round(line.mid - dir * a) + ' ';
      }
      line.el.setAttribute('points', points.trim());
    });
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);

  const reveal = [...document.querySelectorAll('[data-reveal]')];
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });
  reveal.forEach((el) => io.observe(el));

  const counters = [...document.querySelectorAll('[data-count]')];
  counters.forEach((el) => {
    const target = +el.dataset.count;
    const start = performance.now();
    function step(now) {
      const p = Math.min(1, (now - start) / 1500);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(target * eased).toLocaleString();
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });
})();