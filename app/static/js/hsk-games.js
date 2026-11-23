/* Bonus Courses games: Memory match, Speed round, Level ladder.
   The questions are made from the level's own word list (data.json): nothing to write by hand.
   A good result plays the celebration of the student's badge (StreakOverlay.burst). */
(function () {
  'use strict';
  const app = document.getElementById('gm-app');
  if (!app) return;
  const LEVEL = app.dataset.level, BADGE = app.dataset.badge || 'gold';
  const SCORE_URL = app.dataset.scoreUrl, DATA_URL = app.dataset.dataUrl;
  const csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
  let best = {};
  try { best = JSON.parse(app.dataset.best || '{}'); } catch (e) {}

  const $ = (id) => document.getElementById(id);
  const stage = $('gm-stage'), menu = $('gm-menu');
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const shuffle = (a) => { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
  const short = (w) => String(w.arti).split(/[;；]/)[0].trim();

  let words = [], knownSet = new Set(), timers = [];
  const later = (fn, ms) => { const t = setTimeout(fn, ms); timers.push(t); return t; };
  const every = (fn, ms) => { const t = setInterval(fn, ms); timers.push(t); return t; };
  const stopTimers = () => { timers.forEach((t) => { clearTimeout(t); clearInterval(t); }); timers = []; };

  function paintBest() {
    document.querySelectorAll('em[data-best]').forEach((el) => {
      const b = best[el.dataset.best];
      el.textContent = b && b.plays ? 'Best ' + b.best + ' · played ' + b.plays + '×' : 'Not played yet';
    });
  }
  paintBest();

  async function load() {
    const [d, p] = await Promise.all([
      fetch(DATA_URL, { credentials: 'same-origin' }).then((r) => r.json()),
      fetch('/hsk' + LEVEL + '/progress', { credentials: 'same-origin' }).then((r) => r.json()).catch(() => ({ known: [] })),
    ]);
    words = d; knownSet = new Set((p && p.known) || []);
  }
  const ready = load().catch(() => { words = []; });

  function pool() {
    const theme = $('gm-theme').value, onlyNew = $('gm-unknown').checked;
    let list = words.filter((w) => theme === 'all' || w.theme === theme);
    if (onlyNew) list = list.filter((w) => !knownSet.has(Number(w.n)));
    return list;
  }

  /* 4 answers: the right one and 3 other words, preferably from the same theme, all different */
  function choices(w, field) {
    const key = (x) => field === 'arti' ? short(x).toLowerCase() : x.hanzi;
    const used = new Set([key(w)]);
    const others = shuffle(words.filter((x) => x.n !== w.n));
    const same = others.filter((x) => x.theme === w.theme), rest = others.filter((x) => x.theme !== w.theme);
    const out = [w];
    for (const x of same.concat(rest)) { if (out.length >= 4) break; if (!used.has(key(x))) { used.add(key(x)); out.push(x); } }
    return shuffle(out);
  }

  function deckOf(list) {                       // endless supply of words, no repeat until all were used
    let q = [];
    return () => { if (!q.length) q = shuffle(list); return q.pop(); };
  }

  function question(w, mode) {                  // mode 'zh' = show Hanzi, answer meaning; 'id' = show meaning, answer Hanzi
    const field = mode === 'zh' ? 'arti' : 'hanzi';
    const prompt = mode === 'zh'
      ? `<div class="gm-hanzi">${esc(w.hanzi)}</div><div class="gm-pinyin">${esc(w.pinyin)}</div>`
      : `<div class="gm-meaning">${esc(short(w))}</div>`;
    const opts = choices(w, field).map((o) =>
      `<button type="button" class="gm-opt ${mode === 'id' ? 'zh' : ''}" data-n="${esc(o.n)}">${esc(mode === 'zh' ? short(o) : o.hanzi)}${mode === 'id' ? `<div class="gm-pinyin">${esc(o.pinyin)}</div>` : ''}</button>`).join('');
    return { html: `<div class="card gm-q">${prompt}</div><div class="gm-opts">${opts}</div>` };
  }

  /* ---------- finish ---------- */
  async function finish(game, score, lines, great, wrong) {
    stopTimers();
    let res = null;
    try {
      const r = await fetch(SCORE_URL, { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf }, body: JSON.stringify({ game, score }) });
      res = await r.json();
      if (res && res.ok) { best[game] = { best: res.best, plays: res.plays }; paintBest(); }
    } catch (e) {}
    const review = (wrong || []).length
      ? `<div class="gm-review"><b style="font-size:.8rem;font-family:inherit">Words to review</b>${wrong.map((w) => `<div><b>${esc(w.hanzi)}</b>${esc(w.pinyin)} · ${esc(w.arti)}</div>`).join('')}</div>` : '';
    stage.innerHTML = `<div class="card gm-end">
      <h2>${great ? 'Excellent! 太棒了!' : 'Finished! 加油!'}</h2>
      <div class="gm-big">${score}</div>
      ${res && res.record ? '<span class="gm-record">New best score!</span>' : (res && res.ok ? `<p>Best: ${res.best}</p>` : '')}
      ${lines.map((l) => `<p>${l}</p>`).join('')}
      <div class="gm-acts"><button type="button" class="btn bg" id="gm-again">Play again</button><button type="button" class="btn bgh" id="gm-back">All games</button></div>
      ${review}</div>`;
    $('gm-again').onclick = () => start(game);
    $('gm-back').onclick = backToMenu;
    if (window.StreakOverlay && (great || score > 0)) {
      later(() => window.StreakOverlay.burst(BADGE, great), 250);
    }
  }
  function backToMenu() { stopTimers(); stage.hidden = true; stage.innerHTML = ''; menu.hidden = false; window.scrollTo({ top: 0 }); }

  /* ---------- memory match ---------- */
  function memory(list) {
    const pairs = Math.min(8, list.length);
    const picked = shuffle(list).slice(0, pairs);
    const cards = shuffle(picked.flatMap((w) => [{ id: w.n, kind: 'zh', w }, { id: w.n, kind: 'id', w }]));
    let open = [], matched = 0, moves = 0, misses = 0, secs = 0, lock = false;
    stage.innerHTML = `<div class="gm-bar"><span class="gm-stat">Pairs <b id="m-p">0</b>/${pairs}</span><span class="gm-stat">Moves <b id="m-m">0</b></span><span class="gm-stat">Time <b id="m-t">0</b>s</span><span class="gm-spacer"></span><button type="button" class="btn bgh bsm" id="gm-quit">Quit</button></div>
      <div class="gm-board">${cards.map((c, i) => `<button type="button" class="gm-mcard" data-i="${i}" aria-label="Card ${i + 1}"><span class="gm-mback">文</span><span class="gm-mfront ${c.kind === 'zh' ? 'zh' : ''}">${c.kind === 'zh' ? `${esc(c.w.hanzi)}<small>${esc(c.w.pinyin)}</small>` : esc(short(c.w))}</span></button>`).join('')}</div>`;
    $('gm-quit').onclick = backToMenu;
    every(() => { secs++; $('m-t').textContent = secs; }, 1000);
    stage.querySelector('.gm-board').addEventListener('click', (e) => {
      const el = e.target.closest('.gm-mcard');
      if (!el || lock || el.classList.contains('open') || el.classList.contains('done')) return;
      el.classList.add('open'); open.push(el);
      if (open.length < 2) return;
      moves++; $('m-m').textContent = moves;
      const [a, b] = open.map((x) => cards[+x.dataset.i]);
      if (a.id === b.id && a.kind !== b.kind) {
        open.forEach((x) => x.classList.add('done')); open = []; matched++; $('m-p').textContent = matched;
        if (matched === pairs) later(() => {
          const score = Math.max(50, pairs * 120 - misses * 15 - secs * 2);
          finish('memory', score, [`${pairs} pairs in ${moves} moves · ${secs}s`, `${misses} wrong ${misses === 1 ? 'try' : 'tries'}`], score >= pairs * 80);
        }, 500);
      } else {
        misses++; lock = true; open.forEach((x) => x.classList.add('bad'));
        later(() => { open.forEach((x) => x.classList.remove('open', 'bad')); open = []; lock = false; }, 800);
      }
    });
  }

  /* ---------- speed round ---------- */
  function speed(list) {
    const next = deckOf(list);
    let left = 60, score = 0, combo = 0, bestCombo = 0, right = 0, total = 0, over = false, cur = null;
    const wrong = [];
    stage.innerHTML = `<div class="gm-bar"><span class="gm-stat">Score <b id="s-s">0</b></span><span class="gm-stat">Combo <b id="s-c" class="gm-combo">0</b></span><span class="gm-stat">⏱ <b id="s-t">60</b>s</span><span class="gm-spacer"></span><button type="button" class="btn bgh bsm" id="gm-quit">Quit</button></div>
      <div class="gm-time" id="s-bar"><i style="width:100%"></i></div><div id="s-q"></div>`;
    $('gm-quit').onclick = backToMenu;
    const paintStats = () => { $('s-s').textContent = score; $('s-c').textContent = combo; $('s-t').textContent = Math.max(0, left); const b = $('s-bar'); b.firstChild.style.width = Math.max(0, left) / 60 * 100 + '%'; b.classList.toggle('low', left <= 10); };
    function ask() {
      if (over) return;
      cur = { w: next(), mode: Math.random() < 0.6 ? 'zh' : 'id' };
      $('s-q').innerHTML = question(cur.w, cur.mode).html;
    }
    $('s-q').addEventListener('click', (e) => {
      const b = e.target.closest('.gm-opt'); if (!b || b.disabled || over) return;
      document.querySelectorAll('#s-q .gm-opt').forEach((x) => { x.disabled = true; if (x.dataset.n === String(cur.w.n)) x.classList.add('right'); });
      total++;
      if (b.dataset.n === String(cur.w.n)) { right++; combo++; bestCombo = Math.max(bestCombo, combo); score += 10 + Math.min(combo, 10) * 2; }
      else { b.classList.add('wrong'); combo = 0; left -= 3; if (!wrong.find((x) => x.n === cur.w.n) && wrong.length < 8) wrong.push(cur.w); }
      paintStats(); later(ask, 450);
    });
    every(() => {
      left--; paintStats();
      if (left <= 0 && !over) {
        over = true;
        const acc = total ? Math.round(right / total * 100) : 0;
        finish('speed', score, [`${right} of ${total} correct (${acc}%)`, `Best combo: ${bestCombo}`], acc >= 80 && right >= 15, wrong);
      }
    }, 1000);
    paintStats(); ask();
  }

  /* ---------- level ladder ---------- */
  function ladder(list) {
    const TOP = 10, MAX_Q = 30;
    const next = deckOf(list);
    let floor = 0, asked = 0, right = 0, cur = null, over = false;
    const wrong = [];
    const floors = Array.from({ length: TOP + 1 }, (_, i) => i);
    stage.innerHTML = `<div class="gm-bar"><span class="gm-stat">Floor <b id="l-f">0</b>/${TOP}</span><span class="gm-stat">Question <b id="l-q">0</b>/${MAX_Q}</span><span class="gm-spacer"></span><button type="button" class="btn bgh bsm" id="gm-quit">Quit</button></div>
      <div class="gm-ladder" id="l-lad">${floors.map((i) => `<div class="gm-floor" data-f="${i}">${i === TOP ? '🏆 Top' : i === 0 ? 'Ground' : 'Floor ' + i}<span class="gm-me"></span></div>`).join('')}</div><div id="l-q-box"></div>`;
    $('gm-quit').onclick = backToMenu;
    const paint = () => {
      $('l-f').textContent = floor; $('l-q').textContent = asked;
      document.querySelectorAll('#l-lad .gm-floor').forEach((el) => {
        const f = +el.dataset.f; el.classList.toggle('reached', f < floor); el.classList.toggle('here', f === floor);
        el.querySelector('.gm-me').textContent = f === floor ? '🧗' : '';
      });
    };
    function ask() {
      if (over) return;
      cur = { w: next(), mode: Math.random() < 0.7 ? 'zh' : 'id' };
      $('l-q-box').innerHTML = question(cur.w, cur.mode).html;
    }
    $('l-q-box').addEventListener('click', (e) => {
      const b = e.target.closest('.gm-opt'); if (!b || b.disabled || over) return;
      document.querySelectorAll('#l-q-box .gm-opt').forEach((x) => { x.disabled = true; if (x.dataset.n === String(cur.w.n)) x.classList.add('right'); });
      asked++;
      if (b.dataset.n === String(cur.w.n)) { right++; floor = Math.min(TOP, floor + 1); }
      else { b.classList.add('wrong'); floor = Math.max(0, floor - 1); if (!wrong.find((x) => x.n === cur.w.n) && wrong.length < 8) wrong.push(cur.w); }
      paint();
      if (floor >= TOP || asked >= MAX_Q) {
        over = true;
        const win = floor >= TOP;
        const score = win ? Math.max(400, 1000 - (asked - TOP) * 20) : floor * 40;
        later(() => finish('ladder', score, [win ? `You reached the top in ${asked} questions!` : `You reached floor ${floor} of ${TOP}.`, `${right} of ${asked} correct`], win, wrong), 600);
      } else later(ask, 450);
    });
    paint(); ask();
  }

  /* ---------- draw the lines ---------- */
  function match(list) {
    const ROUNDS = 3, PER = 5;
    if (list.length < PER) { alert('Choose at least 5 words for this game.'); backToMenu(); return; }
    const next = deckOf(list);
    let round = 0, misses = 0, pairs = 0, t0 = Date.now();
    const wrongWords = [];
    stage.innerHTML = `<div class="gm-bar"><span class="gm-stat">Round <b id="m-r">1</b>/${ROUNDS}</span><span class="gm-stat">Mistakes <b id="m-x">0</b></span><span class="gm-spacer"></span><button type="button" class="btn bgh bsm" id="gm-quit">Quit</button></div>
      <p class="gm-tip">Drag from a word to its meaning. On a phone you can also tap the word, then the meaning.</p>
      <div class="gm-lines" id="m-board"></div>`;
    $('gm-quit').onclick = backToMenu;
    const board = $('m-board');

    function newRound() {
      const ws = []; const seen = new Set();
      while (ws.length < PER) { const w = next(); if (!seen.has(w.n) && !seen.has('m' + short(w))) { seen.add(w.n); seen.add('m' + short(w)); ws.push(w); } }
      const rights = shuffle(ws);
      board.innerHTML = `<svg class="gm-svg" id="m-svg"></svg>
        <div class="gm-col">${ws.map((w) => `<div class="gm-node left" data-n="${w.n}"><b lang="zh">${esc(w.hanzi)}</b><small>${esc(w.pinyin)}</small><i class="gm-dot"></i></div>`).join('')}</div>
        <div class="gm-col">${rights.map((w) => `<div class="gm-node right" data-n="${w.n}"><i class="gm-dot"></i><span>${esc(short(w))}</span></div>`).join('')}</div>`;
      let left = 0, from = null, drag = null, solved = 0;
      const svg = $('m-svg');
      const dot = (node) => { const r = node.querySelector('.gm-dot').getBoundingClientRect(), b = board.getBoundingClientRect(); return [r.left + r.width / 2 - b.left, r.top + r.height / 2 - b.top]; };
      const line = (a, b, cls) => { const l = document.createElementNS('http://www.w3.org/2000/svg', 'line'); l.setAttribute('x1', a[0]); l.setAttribute('y1', a[1]); l.setAttribute('x2', b[0]); l.setAttribute('y2', b[1]); l.setAttribute('class', 'gm-line ' + cls); svg.appendChild(l); return l; };
      const clearSel = () => { board.querySelectorAll('.gm-node.sel').forEach((x) => x.classList.remove('sel')); from = null; };
      function connect(l, r) {
        if (l.dataset.n === r.dataset.n) {
          const ln = line(dot(l), dot(r), 'ok'); l.classList.add('done'); r.classList.add('done'); solved++;
          if (solved === PER) later(() => { pairs += PER; round++; if (round >= ROUNDS) end(); else { $('m-r').textContent = round + 1; newRound(); } }, 700);
        } else {
          misses++; $('m-x').textContent = misses;
          const w = words.find((x) => String(x.n) === l.dataset.n); if (w && !wrongWords.find((x) => x.n === w.n) && wrongWords.length < 8) wrongWords.push(w);
          const ln = line(dot(l), dot(r), 'bad'); l.classList.add('shake'); r.classList.add('shake');
          later(() => { ln.remove(); l.classList.remove('shake'); r.classList.remove('shake'); }, 600);
        }
        clearSel();
      }
      const nodeAt = (x, y) => { const e = document.elementFromPoint(x, y); return e && e.closest('.gm-node'); };
      board.onpointerdown = (e) => {
        const n = e.target.closest('.gm-node'); if (!n) return;
        if (n.classList.contains('done')) return;
        if (n.classList.contains('left')) { clearSel(); from = n; n.classList.add('sel'); drag = line(dot(n), dot(n), 'drag'); try { board.setPointerCapture(e.pointerId); } catch (x) {} }
        else if (from) { connect(from, n); }
      };
      board.onpointermove = (e) => {
        if (!drag || !from) return; const b = board.getBoundingClientRect();
        drag.setAttribute('x2', e.clientX - b.left); drag.setAttribute('y2', e.clientY - b.top);
      };
      board.onpointerup = (e) => {
        if (!drag) return;
        const startedAt = drag; drag = null; startedAt.remove();
        const n = nodeAt(e.clientX, e.clientY);
        if (n && n.classList.contains('right') && !n.classList.contains('done') && from) connect(from, n);   // dragged onto a meaning
        // otherwise it was a tap: the word stays selected, the next tap on a meaning connects
      };
    }
    function end() {
      const secs = Math.round((Date.now() - t0) / 1000);
      const score = Math.max(50, pairs * 70 - misses * 25 - secs);
      finish('match', score, [`${pairs} pairs connected, ${misses} mistake${misses === 1 ? '' : 's'}`, `Time: ${secs}s`], misses <= 3, wrongWords);
    }
    newRound();
  }

  /* ---------- a generic 10-question round used by Fill the blank and Character riddle ---------- */
  function quiz10(game, list, build, introHtml) {
    const TOTAL = 10, next = deckOf(list);
    let n = 0, right = 0, streak = 0, bonus = 0, cur = null, locked = false;
    const wrong = [];
    stage.innerHTML = `<div class="gm-bar"><span class="gm-stat">Question <b id="q-n">0</b>/${TOTAL}</span><span class="gm-stat">Correct <b id="q-r">0</b></span><span class="gm-stat">Combo <b id="q-c">0</b></span><span class="gm-spacer"></span><button type="button" class="btn bgh bsm" id="gm-quit">Quit</button></div><div id="q-box"></div>`;
    $('gm-quit').onclick = backToMenu;
    function ask() {
      let q = null;
      for (let i = 0; i < 60 && !q; i++) q = build(next());
      if (!q) { alert('Not enough suitable words in this selection. Try "All words".'); backToMenu(); return; }
      cur = q; locked = false; n++; $('q-n').textContent = n;
      $('q-box').innerHTML = `<div class="card gm-q">${q.prompt}</div><div class="gm-opts">${q.options.map((o) => `<button type="button" class="gm-opt zh" data-n="${esc(o.n)}">${esc(o.hanzi)}<div class="gm-pinyin">${esc(o.pinyin)}</div></button>`).join('')}</div><div class="gm-reveal" id="q-rev"></div>`;
    }
    $('q-box').addEventListener('click', (e) => {
      const b = e.target.closest('.gm-opt'); if (!b || locked) return; locked = true;
      document.querySelectorAll('#q-box .gm-opt').forEach((x) => { x.disabled = true; if (x.dataset.n === String(cur.word.n)) x.classList.add('right'); });
      if (b.dataset.n === String(cur.word.n)) { right++; streak++; bonus += Math.min(streak, 5) * 10; }
      else { b.classList.add('wrong'); streak = 0; if (wrong.length < 8 && !wrong.find((x) => x.n === cur.word.n)) wrong.push(cur.word); }
      $('q-r').textContent = right; $('q-c').textContent = streak;
      $('q-rev').innerHTML = cur.reveal;
      if (n >= TOTAL) later(() => finish(game, right * 100 + bonus, [`${right} of ${TOTAL} correct`], right >= 8, wrong), 1500);
      else later(ask, 1500);
    });
    ask();
  }

  /* ---------- fill the blank ---------- */
  function fill(list) {
    const pool = list.filter((w) => w.sentence && w.sentence[0] && w.sentence[0].includes(w.hanzi));
    if (pool.length < 4) { alert('Not enough example sentences in this selection. Try "All words".'); return; }
    quiz10('fill', pool, (w) => {
      const [zh, py, id] = w.sentence;
      return { word: w,
        options: choices(w, 'hanzi'),
        prompt: `<div class="gm-sent" lang="zh">${esc(zh.replace(w.hanzi, '＿＿'))}</div><div class="gm-meaning" style="font-size:1rem">${esc(id || '')}</div>`,
        reveal: `<b lang="zh">${esc(zh)}</b><br>${esc(py || '')}` };
    });
  }

  /* ---------- character riddle ---------- */
  function riddle(list) {
    const pool = list.filter((w) => w.parts && !w.parts.includes(w.hanzi));
    if (pool.length < 4) { alert('Not enough words with parts in this selection. Try "All words".'); return; }
    quiz10('riddle', pool, (w) => {
      const clue = (w.trick || '').split(w.hanzi).join('＿');
      return { word: w,
        options: choices(w, 'hanzi'),
        prompt: `<div class="gm-meaning" style="font-size:.95rem">Which character is built from these parts?</div><div class="gm-parts" lang="zh">${esc(w.parts)}</div>${clue ? `<div class="gm-clue">💡 ${esc(clue)}</div>` : ''}<div class="gm-meaning" style="font-size:.9rem">Meaning: ${esc(short(w))}</div>`,
        reveal: `<b lang="zh">${esc(w.hanzi)}</b> ${esc(w.pinyin)} · ${esc(w.arti)}` };
    });
  }

  async function start(game) {
    await ready;
    const list = pool();
    if (list.length < 4) { alert('Choose more words: this selection has fewer than 4 words. Try "All words".'); return; }
    stopTimers(); menu.hidden = true; stage.hidden = false;
    ({ memory, speed, ladder, match, fill, riddle })[game](list);
    window.scrollTo({ top: 0 });
  }
  menu.addEventListener('click', (e) => { const t = e.target.closest('[data-game]'); if (t) start(t.dataset.game); });
})();
