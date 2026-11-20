/* Streak pop-up + level-up celebration (student side).
   StreakOverlay.show({ mode: 'join' | 'levelup', streak, link })
   - join    : shown right after "Join Class" and before Meet opens. Shows the streak and the badge.
   - levelup : shown when the student reached a new badge. Bigger, with a "NEW BADGE" banner.
   Every tier has its own show, and the higher the tier the bigger it gets:
     bronze  stamp + copper dust          silver  gleam + twinkling stars
     gold    coin spin + confetti storm   jade    bloom + rising orbs + shock rings
     dragon  screen shake + fire + dragon + lightning flashes
   Needs badge-fx.js (the seal's own motion) and the .badge-* styles from main.css. */
(function () {
  'use strict';
  const T = (s) => (window.I18N ? window.I18N.t(s) : s);
  const rand = (a, b) => a + Math.random() * (b - a);
  const reduce = () => window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const TIERS = ['bronze', 'silver', 'gold', 'jade', 'dragon'];

  /* ---------- tiny sound kit (WebAudio, no files) ---------- */
  let ac = null;
  function tone(f, d, type, at, vol) {
    try {
      ac = ac || new (window.AudioContext || window.webkitAudioContext)();
      const t0 = ac.currentTime + (at || 0), o = ac.createOscillator(), g = ac.createGain();
      o.type = type || 'sine'; o.frequency.setValueAtTime(f, t0);
      g.gain.setValueAtTime(0.0001, t0); g.gain.exponentialRampToValueAtTime(vol || 0.15, t0 + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t0 + d);
      o.connect(g).connect(ac.destination); o.start(t0); o.stop(t0 + d + 0.05);
    } catch (e) { /* sound is optional */ }
  }
  function roar() {
    try {
      ac = ac || new (window.AudioContext || window.webkitAudioContext)();
      const t0 = ac.currentTime, len = ac.sampleRate * 1.2, buf = ac.createBuffer(1, len, ac.sampleRate), d = buf.getChannelData(0);
      for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 1.5);
      const s = ac.createBufferSource(), f = ac.createBiquadFilter(), g = ac.createGain();
      s.buffer = buf; f.type = 'lowpass'; f.frequency.setValueAtTime(900, t0); f.frequency.exponentialRampToValueAtTime(120, t0 + 1.1);
      g.gain.value = 0.5; s.connect(f).connect(g).connect(ac.destination); s.start(t0);
    } catch (e) { /* optional */ }
  }
  const SOUND = {
    bronze() { tone(110, 0.25, 'triangle', 0, 0.25); tone(165, 0.2, 'triangle', 0.05, 0.15); },
    silver() { [880, 1175, 1480].forEach((f, i) => tone(f, 0.5, 'sine', i * 0.12, 0.12)); },
    gold() { [523, 659, 784, 1047, 1319].forEach((f, i) => tone(f, 0.35, 'triangle', i * 0.09, 0.15)); },
    jade() { [392, 494, 587, 784, 988, 1175].forEach((f, i) => tone(f, 0.9, 'sine', i * 0.16, 0.11)); },
    dragon() { roar(); tone(65, 1.4, 'sawtooth', 0, 0.22); [262, 330, 392, 523, 659, 784].forEach((f, i) => tone(f, 0.5, 'square', 0.5 + i * 0.08, 0.08)); },
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
    dragon(L, big) {
      L.parentNode.classList.add('so-shake', 'so-glow-dragon');
      flash(L, 'rgba(255,60,30,.65)', 900);
      setTimeout(() => flash(L, 'rgba(255,255,255,.85)', 220), 260);          // lightning
      setTimeout(() => flash(L, 'rgba(255,200,90,.6)', 500), 900);
      bit(L, 'sof-dragon', { '--delay': '0.1s' }, '龙');
      for (let i = 0; i < 5; i++) wave(L, ['#ff5a36', '#ffb347', '#d61f26'][i % 3], i * 0.28, 1 + i * 0.5);
      for (let i = 0; i < (big ? 150 : 110); i++) bit(L, 'sof-rise sof-ember', { '--x': rand(0, W()) + 'px', '--size': rand(6, 16) + 'px', '--delay': rand(0, 2.2) + 's', '--dur': rand(1.6, 3.4) + 's', '--sway': rand(-60, 60) + 'px', '--c': ['#ff5a36', '#ffb347', '#ffe08a', '#d61f26'][i % 4] });
      for (let i = 0; i < 40; i++) { const a = rand(0, Math.PI * 2), r = rand(120, Math.max(W(), H()) * 0.6); bit(L, 'sof-burst', { '--dx': Math.cos(a) * r + 'px', '--dy': Math.sin(a) * r + 'px', '--size': rand(6, 15) + 'px', '--delay': rand(0.15, 0.6) + 's', '--c': ['#ff5a36', '#ffb347', '#ffe08a'][i % 3] }); }
      bit(L, 'sof-fire', {});
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
    setTimeout(() => solo.remove(), 5200);
  }

  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && current && !current.querySelector('[data-act="go"]')) close(); });
  window.StreakOverlay = { show, close, burst };
})();
