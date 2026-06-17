(() => {
  const wavePatterns = {
    broadcast: [
      { amp: 222, seg: 9, speed: 1.3 },
      { amp: 232, seg: 11, speed: 1.7 },
      { amp: 210, seg: 8, speed: 2.1 },
    ],
    pulse: [
      { amp: 260, seg: 6, speed: 1.05 },
      { amp: 170, seg: 14, speed: 2.45 },
      { amp: 245, seg: 10, speed: 1.8 },
    ],
    static: [
      { amp: 125, seg: 22, speed: 3.35 },
      { amp: 265, seg: 17, speed: 2.9 },
      { amp: 95, seg: 26, speed: 4.1 },
    ],
  };

  function randomEnvelope(seg) {
    const rand = [];
    for (let i = 0; i <= seg; i++) rand.push(0.35 + Math.random() * 0.65);
    return rand;
  }

  const lines = [...document.querySelectorAll('[data-wave]')].map((el) => {
    const seg = +el.dataset.seg;
    return { el, seg, mid: +el.dataset.mid, amp: +el.dataset.amp, speed: +el.dataset.speed, phase: +el.dataset.phase, rand: randomEnvelope(seg) };
  });

  function setWavePattern(name) {
    const pattern = wavePatterns[name] || wavePatterns.broadcast;
    lines.forEach((line, index) => {
      const next = pattern[index % pattern.length];
      line.amp = next.amp;
      line.seg = next.seg;
      line.speed = next.speed;
      line.rand = randomEnvelope(next.seg);
    });
  }

  function wireRadioControls(scope = document) {
    const buttons = [...scope.querySelectorAll('[data-pattern-button]')];
    const knobs = [...scope.querySelectorAll('.rotary-knob')];
    const sliders = [...scope.querySelectorAll('.small-slider-control')];
    knobs.forEach((knob) => {
      knob.addEventListener('mouseenter', () => knob.classList.add('is-rotating'));
      knob.addEventListener('mouseleave', () => knob.classList.remove('is-rotating'));
      knob.addEventListener('focus', () => knob.classList.add('is-rotating'));
      knob.addEventListener('blur', () => knob.classList.remove('is-rotating'));
    });
    sliders.forEach((slider) => {
      slider.addEventListener('pointerover', () => slider.classList.add('is-sliding'));
      slider.addEventListener('pointerout', (event) => {
        if (!event.relatedTarget || !slider.contains(event.relatedTarget)) slider.classList.remove('is-sliding');
      });
      slider.addEventListener('mouseenter', () => slider.classList.add('is-sliding'));
      slider.addEventListener('mouseleave', () => slider.classList.remove('is-sliding'));
      slider.addEventListener('focus', () => slider.classList.add('is-sliding'));
      slider.addEventListener('blur', () => slider.classList.remove('is-sliding'));
    });
    buttons.forEach((button) => {
      const press = () => {
        setWavePattern(button.dataset.patternButton);
        buttons.forEach((item) => {
          const active = item === button;
          item.classList.toggle('is-active', active);
          item.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
      };
      button.addEventListener('click', press);
      button.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          press();
        }
      });
    });
  }

  const radioMount = document.querySelector('[data-radio-inline]');
  if (radioMount) {
    fetch('radio.svg?v=20260617-small-knob-rotate')
      .then((response) => response.text())
      .then((svgText) => {
        const svg = new DOMParser().parseFromString(svgText, 'image/svg+xml').documentElement;
        svg.removeAttribute('width');
        svg.removeAttribute('height');
        radioMount.replaceChildren(svg);
        wireRadioControls(radioMount);
      })
      .catch(() => wireRadioControls());
  }

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
