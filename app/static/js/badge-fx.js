/* Badge effects on the student Profile page.
   Tap the big badge and it plays an effect that belongs to its tier:
     bronze  stamp    - presses down with a thud, dust and a copper ring
     silver  gleam    - a light sweeps across it and stars twinkle
     gold    coin     - spins like a coin and gold confetti bursts and falls
     jade    bloom    - glows and floats while green rings and orbs drift up
     diamond facet    - flips like a cut stone, white flashes and crystal glints
     ruby    slam     - drops in hard, red shock rings and ruby glints
     dragon  ascend   - floats up while the colours of the rainbow flow through it
   The seal does the motion (CSS class fx-<tier>); this file adds the particles around it.
   With "reduce motion" on, only a quiet pulse is played. */
(function () {
  'use strict';

  const rand = (a, b) => a + Math.random() * (b - a);
  const reduce = () => window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  function particle(layer, cls, vars, text) {
    const el = document.createElement('i');
    el.className = 'bfx ' + cls;
    if (text) el.textContent = text;
    Object.keys(vars).forEach((k) => el.style.setProperty(k, vars[k]));
    layer.appendChild(el);
    el.addEventListener('animationend', () => el.remove());
    return el;
  }
  const ring = (layer, color, delay, size) =>
    particle(layer, 'bfx-ring', { '--c': color, '--delay': (delay || 0) + 's', '--s': (size || 1) });

  // each tier: how long it plays, and what it throws around the seal
  const EFFECTS = {
    bronze(layer) {
      ring(layer, '#c9854a', 0.08);
      ring(layer, '#a8642a', 0.22, 1.25);
      for (let i = 0; i < 14; i++) {
        const side = i % 2 ? 1 : -1;
        particle(layer, 'bfx-dust', {
          '--dx': side * rand(40, 120) + 'px', '--dy': rand(30, 70) + 'px',
          '--size': rand(5, 11) + 'px', '--delay': rand(0.1, 0.25) + 's', '--c': i % 3 ? '#b47a4a' : '#e0a470',
        });
      }
      return 1100;
    },
    silver(layer) {
      for (let i = 0; i < 10; i++) {
        const a = rand(0, Math.PI * 2), r = rand(80, 130);
        particle(layer, 'bfx-star', {
          '--x': Math.cos(a) * r + 'px', '--y': Math.sin(a) * r + 'px',
          '--size': rand(14, 26) + 'px', '--delay': rand(0.1, 0.8) + 's', '--c': i % 2 ? '#ffffff' : '#cfd6e2',
        }, '✦');
      }
      return 1500;
    },
    gold(layer) {
      ring(layer, '#e0a915', 0.25);
      for (let i = 0; i < 26; i++) {
        particle(layer, 'bfx-coin', {
          '--dx': rand(-150, 150) + 'px', '--up': -rand(90, 190) + 'px', '--fall': rand(90, 190) + 'px',
          '--rot': rand(-540, 540) + 'deg', '--size': rand(7, 14) + 'px', '--delay': rand(0.2, 0.45) + 's',
          '--c': ['#ffd54a', '#e0a915', '#fff2a8', '#b57d06'][i % 4], '--r': i % 3 ? '50%' : '2px',
        });
      }
      return 1900;
    },
    jade(layer) {
      ring(layer, '#43c98f', 0.0);
      ring(layer, '#43c98f', 0.35, 1.2);
      ring(layer, '#9af0c6', 0.7, 1.4);
      for (let i = 0; i < 16; i++) {
        particle(layer, 'bfx-orb', {
          '--x': rand(-120, 120) + 'px', '--rise': -rand(140, 230) + 'px', '--sway': rand(-30, 30) + 'px',
          '--size': rand(8, 18) + 'px', '--delay': rand(0, 0.9) + 's', '--c': i % 2 ? '#7bf0b8' : '#2fb67f',
        });
      }
      return 2400;
    },
    diamond(layer) {
      ring(layer, '#ffffff', 0.15); ring(layer, '#78d6ff', 0.4, 1.3);
      for (let i = 0; i < 16; i++) {
        const a = rand(0, Math.PI * 2), r = rand(70, 150);
        particle(layer, 'bfx-star', {
          '--x': Math.cos(a) * r + 'px', '--y': Math.sin(a) * r + 'px',
          '--size': rand(14, 30) + 'px', '--delay': rand(0.1, 1.0) + 's', '--c': ['#ffffff', '#bff0ff', '#78d6ff'][i % 3],
        }, i % 2 ? '◆' : '✦');
      }
      return 1900;
    },
    ruby(layer) {
      ring(layer, '#ff3b6b', 0.05); ring(layer, '#ffffff', 0.25, 1.3);
      for (let i = 0; i < 12; i++) {
        const a = rand(0, Math.PI * 2), r = rand(80, 150);
        particle(layer, 'bfx-star', { '--x': Math.cos(a) * r + 'px', '--y': Math.sin(a) * r + 'px', '--size': rand(12, 24) + 'px', '--delay': rand(0.1, 0.9) + 's', '--c': ['#ff3b6b', '#ff8fa8', '#ffffff'][i % 3] }, i % 2 ? '◆' : '✦');
      }
      return 1700;
    },
    dragon(layer) {
      const hues = ['#ff9db8', '#ffcf8a', '#f6f08a', '#9df0b8', '#8ad8f5', '#b9a8ff', '#f0a8f8'];
      [0, 2, 4, 6].forEach((i, k) => ring(layer, hues[i], 0.1 + k * 0.25, 1 + k * 0.2));
      for (let i = 0; i < 12; i++) {
        particle(layer, 'bfx-orb', {
          '--x': rand(-130, 130) + 'px', '--rise': -rand(120, 230) + 'px', '--sway': rand(-40, 40) + 'px',
          '--size': rand(8, 14) + 'px', '--delay': rand(0.2, 1.6) + 's', '--c': hues[i % 7],
        });
      }
      for (let i = 0; i < 6; i++) {
        const a = rand(0, Math.PI * 2), r = rand(80, 150);
        particle(layer, 'bfx-star', { '--x': Math.cos(a) * r + 'px', '--y': Math.sin(a) * r + 'px', '--size': rand(14, 24) + 'px', '--delay': rand(0.3, 1.8) + 's', '--c': hues[(i + 3) % 7] }, '✦');
      }
      return 2800;
    },
  };

  function play(seal, celebrate) {
    if (!seal || seal.classList.contains('fx-on')) return;
    const tier = seal.dataset.tier || 'bronze';
    const stage = seal.closest('.badge-stage');
    const layer = stage && stage.querySelector('.badge-fx');
    if (!stage || !layer) return;

    stage.classList.add('fx-on', 'fx-' + tier);
    seal.classList.add('fx-on', 'fx-' + tier);
    if (celebrate) stage.classList.add('fx-celebrate');

    let ms = 700;
    if (reduce()) {
      seal.classList.add('fx-reduced');
    } else if (EFFECTS[tier]) {
      ms = EFFECTS[tier](layer);
      if (celebrate) ms += 600;
    }
    setTimeout(() => {
      seal.classList.remove('fx-on', 'fx-' + tier, 'fx-reduced');
      stage.classList.remove('fx-on', 'fx-' + tier, 'fx-celebrate');
    }, ms);
  }

  document.addEventListener('click', (e) => {
    const seal = e.target.closest('.badge-seal');
    if (seal) play(seal, false);
  });

  window.BadgeFX = { play };
})();
