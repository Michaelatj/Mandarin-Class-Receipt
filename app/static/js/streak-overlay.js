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
  const TIERS = ['bronze', 'silver', 'gold', 'jade', 'diamond', 'dragon'];

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
    // gold: a short fanfare and a coin "ching"
    gold() { [[523, 0], [523, 0.13], [523, 0.26], [659, 0.4]].forEach(([f, t]) => { note(f, 0.28, { type: 'sawtooth', at: t, vol: 0.07, lp: 1800 }); note(f / 2, 0.28, { type: 'triangle', at: t, vol: 0.08 }); });
      [523, 659, 784, 1047].forEach((f) => note(f, 1.1, { type: 'sawtooth', at: 0.55, vol: 0.05, lp: 2200, att: 0.03 })); bell(2093, 0.75, 1.2, 0.09); bell(2637, 0.85, 1.2, 0.07); },
    // jade: a plucked zither running up and down the pentatonic scale over a soft pad
    jade() { const sc = [293.7, 329.6, 370, 440, 493.9, 587.3, 659.3, 740, 880]; sc.forEach((f, i) => pluck(f, i * 0.11, 0.13)); sc.slice(0, 8).reverse().forEach((f, i) => pluck(f, 1.1 + i * 0.13, 0.09)); pad([293.7, 440, 587.3], 0, 3.2, 0.045); },
    // diamond: a cascade of crystal bells and a rising sparkle sweep
    diamond() { [1568, 1976, 2349, 2637, 3136, 3951].forEach((f, i) => bell(f, i * 0.075, 1.5, 0.075)); note(1200, 0.7, { at: 0.1, type: 'sine', vol: 0.05, to: 7000 });
      for (let i = 0; i < 9; i++) note(rand(3500, 6500), 0.18, { at: 0.5 + i * 0.09, vol: 0.03, att: 0.004 }); pad([1047, 1319, 1568], 0.4, 2.2, 0.03); },
    // dragon: a deep gong, a harp running over two octaves and a warm choir-like chord. Grand, never harsh
    dragon() { bell(98, 0, 4.2, 0.2); note(49, 3.2, { type: 'sine', vol: 0.18, att: 0.05 });
      const sc = [261.6, 293.7, 329.6, 392, 440, 523.3, 587.3, 659.3, 784, 880, 1047, 1175, 1318.5]; sc.forEach((f, i) => pluck(f, 0.5 + i * 0.075, 0.1));
      pad([261.6, 329.6, 392, 523.3], 1.4, 3.6, 0.06); pad([130.8, 196], 1.4, 3.6, 0.05); bell(2093, 1.6, 2.4, 0.06); bell(1568, 1.9, 2.4, 0.05); },
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

  const SHOW = {
    bronze(L, big) {
      wave(L, '#c9854a', 0.1); if (big) wave(L, '#a8642a', 0.3, 1.4);
      for (let i = 0; i < (big ? 26 : 14); i++) bit(L, 'sof-burst', { '--dx': rand(-170, 170) + 'px', '--dy': rand(-130, 90) + 'px', '--size': rand(5, 11) + 'px', '--delay': rand(0.12, 0.3) + 's', '--c': i % 2 ? '#b47a4a' : '#e0a470' });
    },
    silver(L, big) {
      flash(L, 'rgba(220,230,255,.45)', 600);
      for (let i = 0; i < (big ? 46 : 26); i++) bit(L, 'sof-twinkle', { '--x': rand(0, W()) + 'px', '--y': rand(0, H()) + 'px', '--size': rand(14, 32) + 'px', '--delay': rand(0, 1.6) + 's', '--c': i % 3 ? '#ffffff' : '#bcd0ff' }, '✦');
      wave(L, '#cfd6e2', 0.2);
    },
    gold(L, big) {
      flash(L, 'rgba(255,214,90,.5)', 800);
      for (let i = 0; i < (big ? 120 : 80); i++) bit(L, 'sof-confetti', { '--x': rand(0, W()) + 'px', '--drift': rand(-120, 120) + 'px', '--size': rand(7, 14) + 'px', '--delay': rand(0, 1.3) + 's', '--dur': rand(1.8, 3.2) + 's', '--rot': rand(-900, 900) + 'deg', '--c': ['#ffd54a', '#e0a915', '#fff2a8', '#d4380d', '#ffffff'][i % 5] });
      for (let i = 0; i < 18; i++) bit(L, 'sof-burst', { '--dx': rand(-220, 220) + 'px', '--dy': rand(-260, 40) + 'px', '--size': rand(10, 18) + 'px', '--delay': rand(0.1, 0.4) + 's', '--c': '#ffd54a', '--r': '50%' }, '');
      wave(L, '#e0a915', 0.15); wave(L, '#fff2a8', 0.4, 1.5);
    },
    jade(L, big) {
      L.parentNode.classList.add('so-glow-jade');
      for (let i = 0; i < 4; i++) wave(L, i % 2 ? '#9af0c6' : '#43c98f', i * 0.35, 1 + i * 0.35);
      for (let i = 0; i < (big ? 70 : 46); i++) bit(L, 'sof-rise', { '--x': rand(0, W()) + 'px', '--size': rand(8, 22) + 'px', '--delay': rand(0, 2) + 's', '--dur': rand(2.4, 4.2) + 's', '--sway': rand(-50, 50) + 'px', '--c': i % 2 ? '#7bf0b8' : '#2fb67f' });
      for (let i = 0; i < 12; i++) bit(L, 'sof-twinkle', { '--x': rand(0, W()) + 'px', '--y': rand(0, H()) + 'px', '--size': rand(18, 34) + 'px', '--delay': rand(0, 2) + 's', '--c': '#c9ffe5' }, '翠');
    },
    diamond(L, big) {
      L.parentNode.classList.add('so-glow-diamond');
      flash(L, 'rgba(255,255,255,.85)', 420);
      for (let i = 0; i < (big ? 7 : 5); i++) bit(L, 'sof-beam', { '--x': rand(0, W()) + 'px', '--w': rand(50, 130) + 'px', '--delay': (0.15 + i * 0.18) + 's' });
      for (let i = 0; i < (big ? 46 : 30); i++) bit(L, 'sof-shard', { '--x': rand(0, W()) + 'px', '--drift': rand(-90, 90) + 'px', '--size': rand(12, 30) + 'px', '--delay': rand(0, 1.6) + 's', '--dur': rand(1.8, 3) + 's', '--rot': rand(-360, 360) + 'deg', '--c': ['#bff0ff', '#78d6ff', '#ffffff', '#9ab8ff'][i % 4] }, i % 3 ? '◆' : '✧');
      for (let i = 0; i < 26; i++) bit(L, 'sof-twinkle', { '--x': rand(0, W()) + 'px', '--y': rand(0, H()) + 'px', '--size': rand(16, 36) + 'px', '--delay': rand(0.2, 2.2) + 's', '--c': '#e8fbff' }, '✦');
      wave(L, '#78d6ff', 0.2, 1.1); wave(L, '#ffffff', 0.45, 1.5);
    },
    dragon(L, big) {
      L.parentNode.classList.add('so-glow-dragon');
      bit(L, 'sof-aurora', {});
      bit(L, 'sof-dragon', { '--delay': '0.15s' }, '龙');
      const hues = ['#ff6b8b', '#ffb15c', '#f6e65a', '#6fe39a', '#4cc9f0', '#8a7dff', '#e879f9'];
      for (let i = 0; i < 7; i++) wave(L, hues[i], 0.1 + i * 0.22, 1 + i * 0.22);
      for (let i = 0; i < (big ? 46 : 34); i++) bit(L, 'sof-petal', { '--x': rand(0, W()) + 'px', '--size': rand(9, 18) + 'px', '--delay': rand(0.3, 2.6) + 's', '--dur': rand(3.2, 5) + 's', '--sway': rand(30, 90) + 'px', '--c': hues[i % 7] });
      for (let i = 0; i < 24; i++) bit(L, 'sof-twinkle', { '--x': rand(0, W()) + 'px', '--y': rand(0, H()) + 'px', '--size': rand(16, 34) + 'px', '--delay': rand(0.4, 3) + 's', '--c': hues[(i + 2) % 7] }, '✦');
      setTimeout(() => flash(L, 'rgba(255,255,255,.22)', 700), 650);
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
    setTimeout(() => solo.remove(), key === 'dragon' ? 7000 : 5200);
  }

  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && current && !current.querySelector('[data-act="go"]')) close(); });
  window.StreakOverlay = { show, close, burst };
})();
