/* Streak pop-up + level-up celebration (student side).
   StreakOverlay.show({ mode: 'join' | 'levelup', streak, link })
   - join    : shown right after "Join Class" and before Meet opens. Shows the streak and the badge.
   - levelup : shown when the student reached a new badge. Bigger, with a "NEW BADGE" banner.
   Every tier has its own show, and the higher the tier the bigger it gets:
     bronze  stamp + copper dust          silver  gleam + twinkling stars
     gold    coin spin + confetti storm   jade    bloom + rising orbs + shock rings
     diamond light beams + falling crystals + white flash
     dragon  rainbow aurora + glowing dragon glyph + drifting rainbow petals (elegant, slow)
   Needs badge-fx.js (the seal's own motion) and the .badge-* styles from main.css. */
(function () {
  'use strict';
  const T = (s) => (window.I18N ? window.I18N.t(s) : s);
  const rand = (a, b) => a + Math.random() * (b - a);
  const reduce = () => window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const TIERS = ['bronze', 'silver', 'gold', 'jade', 'diamond', 'ruby', 'dragon'];
  // weaker phones get fewer particles, so the show stays smooth
  const LOW = (navigator.hardwareConcurrency || 4) <= 4 || (navigator.deviceMemory || 4) <= 2 || Math.min(window.innerWidth, window.innerHeight) < 480;
  const N = (n) => Math.max(3, Math.round(n * (LOW ? 0.5 : 1)));

  /* ---------- sound kit (WebAudio, no files). Every tier has its own little piece of music ---------- */
  let ac = null;
  function ctx() {
    ac = ac || new (window.AudioContext || window.webkitAudioContext)();
    if (ac.state === 'suspended' && ac.resume) ac.resume();
    return ac;
  }
  // one note: type, start offset, length, volume, attack, optional low-pass
  function note(f, dur, o) {
    try {
      o = o || {};
      const c = ctx(), t0 = c.currentTime + (o.at || 0), osc = c.createOscillator(), g = c.createGain();
      osc.type = o.type || 'sine'; osc.frequency.setValueAtTime(f, t0);
      if (o.to) osc.frequency.exponentialRampToValueAtTime(o.to, t0 + dur);
      const att = o.att || 0.012, v = o.vol || 0.12;
      g.gain.setValueAtTime(0.0001, t0); g.gain.exponentialRampToValueAtTime(v, t0 + att); g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
      let out = osc;
      if (o.lp) { const lp = c.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = o.lp; osc.connect(lp); out = lp; }
      out.connect(g).connect(c.destination); osc.start(t0); osc.stop(t0 + dur + 0.05);
    } catch (e) { /* sound is optional */ }
  }
  const pluck = (f, at, vol) => { note(f, 1.3, { type: 'triangle', at, vol: vol || 0.14, att: 0.004, lp: 3200 }); note(f * 2, 0.5, { type: 'sine', at, vol: (vol || 0.14) * 0.35, att: 0.004 }); };
  const bell = (f, at, dur, vol) => { [[1, 1], [2.76, 0.45], [5.4, 0.2]].forEach(([m, k]) => note(f * m, dur || 1.6, { at, vol: (vol || 0.1) * k, att: 0.003 })); };
  const pad = (freqs, at, dur, vol) => freqs.forEach((f) => note(f, dur, { type: 'sine', at, vol: vol || 0.05, att: dur * 0.35 }));
  function noise(at, dur, lpFrom, lpTo, vol) {
    try {
      const c = ctx(), t0 = c.currentTime + (at || 0), len = Math.floor(c.sampleRate * dur), buf = c.createBuffer(1, len, c.sampleRate), d = buf.getChannelData(0);
      for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2);
      const src = c.createBufferSource(), f = c.createBiquadFilter(), g = c.createGain();
      src.buffer = buf; f.type = 'lowpass'; f.frequency.setValueAtTime(lpFrom, t0); f.frequency.exponentialRampToValueAtTime(lpTo, t0 + dur);
      g.gain.value = vol || 0.3; src.connect(f).connect(g).connect(c.destination); src.start(t0);
    } catch (e) { /* optional */ }
  }
  const SOUND = {
    // bronze: a short wooden drum thud, like a stamp on paper
    bronze() { noise(0, 0.18, 900, 150, 0.35); note(90, 0.35, { type: 'sine', vol: 0.3, to: 55 }); note(196, 0.18, { type: 'triangle', at: 0.06, vol: 0.1 }); note(262, 0.25, { type: 'triangle', at: 0.16, vol: 0.09 }); },
    // silver: glass chimes, light and airy
    silver() { [1319, 1760, 2093, 2637].forEach((f, i) => bell(f, i * 0.14, 1.8, 0.075)); note(5200, 0.9, { at: 0.5, vol: 0.02, att: 0.4 }); },
    // gold: a fanfare, then a shower of coins
    gold() { [[523, 0], [523, 0.13], [523, 0.26], [659, 0.4]].forEach(([f, t]) => { note(f, 0.28, { type: 'sawtooth', at: t, vol: 0.07, lp: 1800 }); note(f / 2, 0.28, { type: 'triangle', at: t, vol: 0.08 }); });
      [523, 659, 784, 1047].forEach((f) => note(f, 1.0, { type: 'sawtooth', at: 0.55, vol: 0.05, lp: 2200, att: 0.03 }));
      for (let i = 0; i < 16; i++) bell([2093, 2349, 2637, 3136][i % 4], 0.7 + i * 0.09 + Math.random() * 0.04, 0.5, 0.05); },
    // jade: a plucked zither running up and down the pentatonic scale over a soft pad
    jade() { const sc = [293.7, 329.6, 370, 440, 493.9, 587.3, 659.3, 740, 880]; sc.forEach((f, i) => pluck(f, i * 0.11, 0.13)); sc.slice(0, 8).reverse().forEach((f, i) => pluck(f, 1.1 + i * 0.13, 0.09)); pad([293.7, 440, 587.3], 0, 3.2, 0.045); },
    // diamond: a cascade of crystal bells and a rising sparkle sweep
    diamond() { [1568, 1976, 2349, 2637, 3136, 3951].forEach((f, i) => bell(f, i * 0.075, 1.5, 0.075)); note(1200, 0.7, { at: 0.1, type: 'sine', vol: 0.05, to: 7000 });
      for (let i = 0; i < 9; i++) note(rand(3500, 6500), 0.18, { at: 0.5 + i * 0.09, vol: 0.03, att: 0.004 }); pad([1047, 1319, 1568], 0.4, 2.2, 0.03); },
    // ruby: glass cracks and falls, a deep boom, then rich strings in a minor key
    ruby() { noise(0, 0.5, 9000, 2500, 0.32); noise(0.05, 0.35, 5000, 800, 0.25); note(62, 1.3, { type: 'sine', vol: 0.34, to: 38 }); bell(1568, 0.1, 1.2, 0.06);
      for (let i = 0; i < 7; i++) note(rand(2500, 6000), 0.12, { at: 0.35 + i * 0.07, vol: 0.04, att: 0.003 });
      [[220, 0.5], [261.6, 0.5], [329.6, 0.5], [440, 0.5]].forEach(([f, t]) => note(f, 2.6, { type: 'sawtooth', at: t, vol: 0.045, lp: 1400, att: 0.5 }));
      [659, 784, 988].forEach((f, i) => pluck(f, 1.2 + i * 0.15, 0.1)); },
    // dragon: bright and hopeful. A rising harp, a warm choir chord and a shower of tiny bells, like a sunrise
    dragon() { const sc = [261.6, 329.6, 392, 523.3, 659.3, 784, 1047, 1319, 1568]; sc.forEach((f, i) => pluck(f, i * 0.09, 0.11));
      pad([261.6, 329.6, 392, 523.3], 0.3, 3.8, 0.06); pad([392, 493.9, 587.3, 784], 1.5, 3.2, 0.05); pad([130.8, 196], 0.3, 3.8, 0.05);
      for (let i = 0; i < 10; i++) bell(rand(1800, 3600), 1.1 + i * 0.16, 1.2, 0.04); note(1047, 3, { type: 'sine', at: 1.6, vol: 0.05, att: 0.8 }); },
  };

  /* ---------- particles (full screen layer) ---------- */
  function bit(layer, cls, vars, text) {
    const el = document.createElement('i');
    el.className = 'sof ' + cls;
    if (text) el.textContent = text;
    Object.keys(vars).forEach((k) => el.style.setProperty(k, vars[k]));
    layer.appendChild(el);
    el.addEventListener('animationend', () => el.remove());
  }
  const W = () => window.innerWidth, H = () => window.innerHeight;
  const flash = (layer, c, ms) => bit(layer, 'sof-flash', { '--c': c, '--ms': (ms || 700) + 'ms' });
  const wave = (layer, c, delay, size) => bit(layer, 'sof-wave', { '--c': c, '--delay': (delay || 0) + 's', '--s': size || 1 });

  const solid = (L, cls, vars, text) => bit(L, cls, vars, text);
  const SHOW = {
    // bronze: a plain, small stamp of copper dust
    bronze(L, big) {
      wave(L, '#c9854a', 0.1);
      for (let i = 0; i < N(big ? 20 : 12); i++) bit(L, 'sof-burst', { '--dx': rand(-170, 170) + 'px', '--dy': rand(-130, 130) + 'px', '--size': rand(5, 10) + 'px', '--delay': rand(0, 0.25) + 's', '--c': ['#c9854a', '#a8642a', '#e3a76b'][i % 3] });
    },
    // silver: one clean sweep of light and a few quiet glints
    silver(L, big) {
      flash(L, 'rgba(225,232,255,.35)', 500);
      bit(L, 'sof-beam', { '--x': '50%', '--w': '140px', '--delay': '0.1s' });
      for (let i = 0; i < N(big ? 26 : 16); i++) bit(L, 'sof-twinkle', { '--x': rand(0, W()) + 'px', '--y': rand(0, H()) + 'px', '--size': rand(14, 30) + 'px', '--delay': rand(0, 1.4) + 's', '--c': '#eef2ff' }, '✦');
      wave(L, '#cfd6e2', 0.2);
    },
    // gold: money everywhere
    gold(L, big) {
      flash(L, 'rgba(255,214,90,.35)', 700);
      const money = ['🪙', '🪙', '💰', '🪙', '💵'];
      for (let i = 0; i < N(big ? 56 : 38); i++) bit(L, 'sof-coin', { '--x': rand(0, W()) + 'px', '--drift': rand(-70, 70) + 'px', '--size': rand(20, 38) + 'px', '--delay': rand(0, 1.6) + 's', '--dur': rand(1.7, 2.8) + 's' }, money[i % money.length]);
      for (let i = 0; i < N(14); i++) bit(L, 'sof-burst', { '--dx': rand(-220, 220) + 'px', '--dy': rand(-240, 40) + 'px', '--size': rand(6, 12) + 'px', '--delay': rand(0, 0.3) + 's', '--c': '#ffd34d' });
      wave(L, '#e0a915', 0.15);
    },
    // jade: calm and elegant. Slow green light rising, soft rings
    jade(L, big) {
      L.parentNode.classList.add('so-glow-jade');
      for (let i = 0; i < 3; i++) wave(L, i % 2 ? '#9af0c6' : '#43c98f', i * 0.5, 1 + i * 0.4);
      for (let i = 0; i < N(big ? 30 : 22); i++) bit(L, 'sof-orb', { '--x': rand(0, W()) + 'px', '--size': rand(8, 18) + 'px', '--delay': rand(0, 2.2) + 's', '--dur': rand(3.2, 5) + 's', '--sway': rand(-50, 50) + 'px', '--c': ['#7ee8b4', '#43c98f', '#d4ffe9'][i % 3] });
      for (let i = 0; i < N(8); i++) bit(L, 'sof-twinkle', { '--x': rand(0, W()) + 'px', '--y': rand(0, H()) + 'px', '--size': rand(14, 26) + 'px', '--delay': rand(0.4, 2.4) + 's', '--c': '#d4ffe9' }, '✦');
    },
    // diamond: luxury. Beams of white light, falling crystals, a white flash
    diamond(L, big) {
      flash(L, 'rgba(255,255,255,.75)', 420);
      for (let i = 0; i < N(big ? 5 : 4); i++) bit(L, 'sof-beam', { '--x': rand(0, W()) + 'px', '--w': rand(50, 120) + 'px', '--delay': (0.15 + i * 0.2) + 's' });
      for (let i = 0; i < N(big ? 30 : 22); i++) bit(L, 'sof-shard', { '--x': rand(0, W()) + 'px', '--drift': rand(-90, 90) + 'px', '--size': rand(12, 28) + 'px', '--delay': rand(0, 1.6) + 's', '--dur': rand(1.8, 3) + 's', '--rot': rand(-360, 360) + 'deg', '--c': ['#bff0ff', '#78d6ff', '#ffffff', '#9ab8ff'][i % 4] }, i % 3 ? '◆' : '✧');
      for (let i = 0; i < N(14); i++) bit(L, 'sof-twinkle', { '--x': rand(0, W()) + 'px', '--y': rand(0, H()) + 'px', '--size': rand(16, 34) + 'px', '--delay': rand(0.2, 2.2) + 's', '--c': '#e8fbff' }, '✦');
      wave(L, '#78d6ff', 0.2, 1.1); wave(L, '#ffffff', 0.45, 1.5);
    },
    // ruby: expensive and dramatic. Red flash, the screen cracks and shakes, glass falls
    ruby(L, big) {
      L.parentNode.classList.add('so-glow-ruby');
      flash(L, 'rgba(255,40,80,.5)', 600);
      const cx = W() / 2, cy = H() * 0.45, ns = 'http://www.w3.org/2000/svg';
      const svg = document.createElementNS(ns, 'svg'); svg.setAttribute('class', 'sof sof-crack'); svg.setAttribute('viewBox', '0 0 ' + W() + ' ' + H()); svg.setAttribute('preserveAspectRatio', 'none');
      const rays = LOW ? 9 : 14;
      for (let i = 0; i < rays; i++) {
        const a = (i / rays) * Math.PI * 2 + rand(-0.12, 0.12); let x = cx, y = cy, d = 'M' + x + ' ' + y;
        const segs = Math.floor(rand(4, 7)); let len = rand(60, 120);
        for (let k = 0; k < segs; k++) { const aa = a + rand(-0.25, 0.25); x += Math.cos(aa) * len; y += Math.sin(aa) * len; d += 'L' + x.toFixed(0) + ' ' + y.toFixed(0); len *= rand(1, 1.5); }
        const p = document.createElementNS(ns, 'path'); p.setAttribute('d', d); p.style.animationDelay = (0.05 + i * 0.012) + 's'; svg.appendChild(p);
        if (i % 2) { const f = document.createElementNS(ns, 'path'); f.setAttribute('d', d); f.setAttribute('class', 'f'); f.style.animationDelay = (0.1 + i * 0.012) + 's'; svg.appendChild(f); }
      }
      L.appendChild(svg); svg.addEventListener('animationend', (e) => { if (e.target === svg) svg.remove(); });
      L.parentNode.classList.add('so-shake'); setTimeout(() => L.parentNode.classList.remove('so-shake'), 650);
      for (let i = 0; i < N(big ? 22 : 16); i++) {
        const x = rand(0, W()), y = rand(0, H() * 0.7), sz = rand(26, 70);
        bit(L, 'sof-glass', { '--x': x + 'px', '--y': y + 'px', '--size': sz + 'px', '--p1': rand(0, 40) + '% ' + rand(0, 40) + '%', '--p2': rand(60, 100) + '% ' + rand(0, 50) + '%', '--p3': rand(20, 80) + '% ' + rand(60, 100) + '%', '--dx': rand(-80, 80) + 'px', '--rot': rand(-200, 200) + 'deg', '--delay': (0.45 + rand(0, 0.5)) + 's', '--dur': rand(1.2, 2) + 's' });
      }
      for (let i = 0; i < N(14); i++) bit(L, 'sof-twinkle', { '--x': rand(0, W()) + 'px', '--y': rand(0, H()) + 'px', '--size': rand(16, 30) + 'px', '--delay': rand(0.8, 2.4) + 's', '--c': ['#ff8fa8', '#ffffff', '#ff3b6b'][i % 3] }, '✦');
      wave(L, '#ff3b6b', 0.5, 1.4);
    },
    // dragon: the godly one. Bright, colourful and hopeful, like a sunrise with a rainbow
    dragon(L, big) {
      flash(L, 'rgba(255,255,255,.6)', 900);
      bit(L, 'sof-ray', {}); bit(L, 'sof-arch', { '--delay': '0.3s' });
      const hues = ['#ff9db8', '#ffcf8a', '#f6f08a', '#9df0b8', '#8ad8f5', '#b9a8ff', '#f0a8f8'];
      for (let i = 0; i < 4; i++) wave(L, hues[i * 2 % 7], 0.15 + i * 0.3, 1 + i * 0.4);
      for (let i = 0; i < N(big ? 34 : 26); i++) bit(L, 'sof-orb', { '--x': rand(0, W()) + 'px', '--size': rand(7, 15) + 'px', '--delay': rand(0.2, 3) + 's', '--dur': rand(3.4, 5.4) + 's', '--sway': rand(-60, 60) + 'px', '--c': hues[i % 7] });
      for (let i = 0; i < N(16); i++) bit(L, 'sof-twinkle', { '--x': rand(0, W()) + 'px', '--y': rand(0, H()) + 'px', '--size': rand(16, 34) + 'px', '--delay': rand(0.4, 3) + 's', '--c': hues[(i + 2) % 7] }, '✦');
    },
  };

  let current = null;
  function close() {
    if (!current) return;
    const el = current; current = null;
    el.classList.add('out'); setTimeout(() => el.remove(), 260);
    document.body.classList.remove('so-open');
  }

  function countUp(node, from, to) {
    if (reduce() || from === to) { node.textContent = to; return; }
    const t0 = performance.now(), dur = 800;
    (function step(now) {
      const k = Math.min(1, (now - t0) / dur);
      node.textContent = Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3)));
      if (k < 1) requestAnimationFrame(step);
    })(t0);
  }

  function show(opts) {
    close();
    const s = opts.streak;
    if (!s) return false;
    const key = TIERS.includes(s.key) ? s.key : 'bronze';
    const level = opts.mode === 'levelup';
    const link = opts.link || '';
    const nextTxt = s.next_at
      ? (s.next_at - s.cur) + ' ' + T('more classes in a row to reach') + ' ' + esc(s.next_name)
      : '🏆 ' + T('Highest badge reached');
    const el = document.createElement('div');
    el.className = 'so tier-' + key + ' so-' + key + (level ? ' so-level' : '');
    el.setAttribute('role', 'dialog'); el.setAttribute('aria-modal', 'true');
    el.innerHTML = `
      <div class="so-fx" aria-hidden="true"></div>
      <div class="so-card">
        <div class="so-kicker">${level ? T('NEW BADGE!') : T('Your streak')}</div>
        <div class="badge-stage so-stage"><span class="badge-aura" aria-hidden="true"></span>
          <button type="button" class="badge-seal tier-${key}" data-tier="${key}" tabindex="-1" aria-hidden="true"><span class="badge-char">${esc(s.char)}</span><i class="badge-shine" aria-hidden="true"></i></button>
          <div class="badge-fx" aria-hidden="true"></div></div>
        <div class="so-tier">${esc(s.name)} · ${esc(s.zh)}</div>
        <div class="so-streak"><b class="so-num">0</b><span>${T('classes in a row')}</span></div>
        <div class="so-bar tier-${key}"><i style="width:${s.next_at ? s.progress : 100}%"></i></div>
        <div class="so-next">${nextTxt}</div>
        <div class="so-actions">
          ${link ? `<button type="button" class="btn bg so-go" data-act="go">🎥 ${T('Open Meet')}</button>` : `<button type="button" class="btn bg so-go" data-act="close">${T('Continue')}</button>`}
        </div>
      </div>`;
    document.body.appendChild(el);
    document.body.classList.add('so-open');
    current = el;

    const fx = el.querySelector('.so-fx'), seal = el.querySelector('.badge-seal');
    countUp(el.querySelector('.so-num'), level ? Math.max(0, s.cur - 1) : Math.max(0, s.cur - 1), s.cur);
    requestAnimationFrame(() => el.classList.add('in'));
    setTimeout(() => {
      if (window.BadgeFX) window.BadgeFX.play(seal, level);
      if (!reduce()) { SHOW[key](fx, level); (SOUND[key] || SOUND.bronze)(); }
    }, 250);

    el.addEventListener('click', (e) => {
      const b = e.target.closest('[data-act]');
      if (!b) return;
      if (b.dataset.act === 'go' && link) window.open(link, '_blank', 'noopener');
      close();
      if (opts.onDone) opts.onDone();
    });
    return true;
  }

  /* Just the celebration, no card: for the end of a quiz or a game. big = a great result. */
  function burst(key, big) {
    if (reduce()) return;
    key = TIERS.includes(key) ? key : 'bronze';
    const solo = document.createElement('div');
    solo.className = 'so-solo tier-' + key;
    solo.innerHTML = '<div class="so-fx" aria-hidden="true"></div>';
    document.body.appendChild(solo);
    SHOW[key](solo.firstChild, !!big);
    (SOUND[key] || SOUND.bronze)();
    setTimeout(() => solo.remove(), key === 'dragon' ? 7000 : key === 'ruby' ? 5200 : 5200);
  }

  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && current && !current.querySelector('[data-act="go"]')) close(); });
  window.StreakOverlay = { show, close, burst };
})();
