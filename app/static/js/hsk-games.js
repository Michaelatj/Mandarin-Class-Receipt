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

  // the two display switches (saved on this device)
  const SET = (() => { try { return JSON.parse(localStorage.getItem('hskGameSet') || '{}'); } catch (e) { return {}; } })();
  function applySet() {
    app.classList.toggle('gm-nopy', SET.py === false);
    app.classList.toggle('gm-nomean', SET.mean === false);
    const a = document.getElementById('gm-showpy'), b = document.getElementById('gm-showmean');
    if (a) a.checked = SET.py !== false; if (b) b.checked = SET.mean !== false;
    try { localStorage.setItem('hskGameSet', JSON.stringify(SET)); } catch (e) { /* optional */ }
  }
  document.addEventListener('change', (e) => {
    if (e.target.id === 'gm-showpy') { SET.py = e.target.checked; applySet(); }
    if (e.target.id === 'gm-showmean') { SET.mean = e.target.checked; applySet(); }
  });

  function paintBest() {
    document.querySelectorAll('em[data-best]').forEach((el) => {
      const b = best[el.dataset.best];
      el.textContent = b && b.plays ? 'Best ' + b.best + ' · played ' + b.plays + '×' : 'Not played yet';
    });
  }
  paintBest();
  applySet();

  async function load() {
    const [d, p] = await Promise.all([
      fetch(DATA_URL, { credentials: 'same-origin' }).then((r) => r.json()),
      fetch('/hsk' + LEVEL + '/progress', { credentials: 'same-origin' }).then((r) => r.json()).catch(() => ({ known: [] })),
    ]);
    words = d; knownSet = new Set((p && p.known) || []);
  }
  const ready = load().then(() => {
    if (!words.some((w) => w.riddle)) { const t = document.querySelector('.gm-tile[data-game="riddle"]'); if (t) t.hidden = true; }   // riddles exist only for some levels
  }).catch(() => { words = []; });

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
      ? `<div class="gm-review"><b style="font-size:.8rem;font-family:inherit">Words to review</b>${wrong.map((w) => `<div><b>${esc(w.hanzi)}</b><span class="py">${esc(w.pinyin)} · </span>${esc(w.arti)}</div>`).join('')}</div>` : '';
    stage.innerHTML = `<div class="card gm-end">
      <h2>${great ? 'Excellent! 太棒了!' : 'Finished! 加油!'}</h2>
      <div class="gm-big">${score}</div>
      ${res && res.record ? '<span class="gm-record">New best score!</span>' : (res && res.ok ? `<p>Best: ${res.best}</p>` : '')}
      ${lines.map((l) => `<p>${l}</p>`).join('')}
      <div class="gm-acts"><button type="button" class="btn bg" id="gm-again">Play again</button><button type="button" class="btn bgh" id="gm-back">All games</button></div>
      ${review}</div>`;
    $('gm-again').onclick = () => start(game, true);
    $('gm-back').onclick = backToMenu;
    if (window.StreakOverlay && (great || score > 0)) {
      later(() => window.StreakOverlay.burst(BADGE, great), 250);
    }
  }
  /* ---------- leaderboard (top 10 of one game; one tiny request when the menu opens or the game is changed) ---------- */
  const boardSel = $('gm-board-game'), boardList = $('gm-board-list');
  async function loadBoard() {
    if (!boardSel || !boardList) return;
    boardList.innerHTML = '<li class="gm-board-empty">Loading…</li>';
    try {
      const r = await fetch(app.dataset.boardUrl.replace('GAME', boardSel.value), { credentials: 'same-origin' }), j = await r.json();
      boardList.innerHTML = j.ok && j.rows.length
        ? j.rows.map((x, i) => `<li class="${x.me ? 'me' : ''}"><span class="gm-board-rank">${['🥇', '🥈', '🥉'][i] || i + 1}</span><span class="gm-board-name">${esc(x.name)}</span><b>${x.best}</b></li>`).join('')
        : '<li class="gm-board-empty">Nobody has played this one yet. Be the first!</li>';
    } catch (e) { boardList.innerHTML = '<li class="gm-board-empty">Could not load the leaderboard.</li>'; }
  }
  if (boardSel) { boardSel.addEventListener('change', loadBoard); loadBoard(); }

  /* the browser's back button and the page's "back" link return to the games menu while a game is open */
  const backLabel = document.getElementById('gm-backlabel'), backText = backLabel ? backLabel.textContent : '';
  function showMenu() { stopTimers(); stage.hidden = true; stage.innerHTML = ''; menu.hidden = false; if (backLabel) backLabel.textContent = backText; if (boardSel) loadBoard(); window.scrollTo({ top: 0 }); }
  function backToMenu() { if (history.state && history.state.gm) history.back(); else showMenu(); }
  window.addEventListener('popstate', () => { if (!stage.hidden) showMenu(); });
  document.addEventListener('click', (e) => {
    const a = e.target.closest('a.qz-back');
    if (a && !stage.hidden) { e.preventDefault(); backToMenu(); }
  });



  /* ---------- memory match ---------- */
  function memory(list) {
    const pairs = Math.min(8, list.length);
    const picked = shuffle(list).slice(0, pairs);
    const cards = shuffle(picked.flatMap((w) => [{ id: w.n, kind: 'zh', w }, { id: w.n, kind: 'id', w }]));
    const PEEK = Math.max(4, Math.round(pairs * 0.9) + 2);      // seconds to memorise
    let matched = 0, moves = 0, misses = 0, secs = 0, started = false;
    stage.innerHTML = `<div class="gm-bar"><span class="gm-stat">Pairs <b id="m-p">0</b>/${pairs}</span><span class="gm-stat">Moves <b id="m-m">0</b></span><span class="gm-stat">Time <b id="m-t">0</b>s</span><span class="gm-spacer"></span><button type="button" class="btn bgh bsm" id="gm-quit">Quit</button></div>
      <p class="gm-tip" id="m-tip"></p>
      <div class="gm-board">${cards.map((c, i) => `<button type="button" class="gm-mcard open" data-i="${i}" aria-label="Card ${i + 1}"><span class="gm-mback">文</span><span class="gm-mfront ${c.kind === 'zh' ? 'zh' : ''}">${c.kind === 'zh' ? `${esc(c.w.hanzi)}<small>${esc(c.w.pinyin)}</small>` : esc(short(c.w))}</span></button>`).join('')}</div>`;
    $('gm-quit').onclick = backToMenu;
    const cardEls = [...stage.querySelectorAll('.gm-mcard')];
    const tip = $('m-tip');
    // 1) show every card first, then turn them all face down
    let left = PEEK;
    tip.textContent = `Memorise the cards! They close in ${left}s…`;
    every(() => {
      if (started) return;
      left--;
      if (left > 0) { tip.textContent = `Memorise the cards! They close in ${left}s…`; return; }
      started = true;
      cardEls.forEach((x) => x.classList.remove('open'));
      tip.textContent = 'Tap a card to open it, tap it again to close it. Open two cards that go together to score a pair.';
    }, 1000);
    every(() => { if (started) { secs++; $('m-t').textContent = secs; } }, 1000);

    // 2) tap = open, tap again = close. Two open cards are checked; a wrong pair stays open until you close one
    stage.querySelector('.gm-board').addEventListener('click', (e) => {
      const el = e.target.closest('.gm-mcard');
      if (!el || !started || el.classList.contains('done')) return;
      const opened = () => cardEls.filter((x) => x.classList.contains('open') && !x.classList.contains('done'));
      if (el.classList.contains('open')) {                       // close it
        el.classList.remove('open', 'bad');
        opened().forEach((x) => x.classList.remove('bad'));
        return;
      }
      if (opened().length >= 2) {                                // already two open: close one first
        opened().forEach((x) => { x.classList.remove('bad'); void x.offsetWidth; x.classList.add('bad'); });
        return;
      }
      el.classList.add('open');
      const now = opened();
      if (now.length < 2) return;
      moves++; $('m-m').textContent = moves;
      const [a, b] = now.map((x) => cards[+x.dataset.i]);
      if (a.id === b.id && a.kind !== b.kind) {
        now.forEach((x) => x.classList.add('done')); matched++; $('m-p').textContent = matched;
        if (matched === pairs) later(() => {
          const score = Math.max(50, pairs * 120 - misses * 15 - secs * 2);
          finish('memory', score, [`${pairs} pairs in ${moves} moves · ${secs}s`, `${misses} wrong ${misses === 1 ? 'try' : 'tries'}`], score >= pairs * 80);
        }, 500);
      } else {
        misses++; now.forEach((x) => x.classList.add('bad'));
        tip.textContent = 'Not a pair. Tap one of the open cards to close it.';
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
        reveal: `<b lang="zh">${esc(zh)}</b><br><span class="py">${esc(py || '')}</span>` };
    });
  }

  /* ---------- riddle: a real Indonesian riddle, the answer is one of the 4 words ---------- */
  function riddle(list) {
    const pool = list.filter((w) => w.riddle);
    if (pool.length < 4) { alert('This selection has fewer than 4 riddles. Try "All words".'); return; }
    quiz10('riddle', pool, (w) => ({ word: w,
      options: choices(w, 'hanzi'),
      prompt: `<div class="gm-meaning" style="font-size:.9rem">Teka-teki: siapa / apa aku?</div><div class="gm-riddle">${esc(w.riddle)}</div>`,
      reveal: `<b lang="zh">${esc(w.hanzi)}</b> <span class="py">${esc(w.pinyin)} · </span>${esc(w.arti)}` }));
  }

  /* ---------- racing: 60 seconds, first to the finish line. Right answer = faster, wrong answer = breakdown, and three bots keep driving ---------- */
  function race(list) {
    const LV = { easy: { name: 'Easy', icon: '🐢', note: 'Slow bots. Relax and learn.', bots: [58, 68, 78], mult: 0.7 },
      normal: { name: 'Normal', icon: '🚗', note: 'Bots drive at a steady pace.', bots: [74, 86, 98], mult: 1 },
      hard: { name: 'Hard', icon: '🚀', note: 'Fast bots. No room for mistakes.', bots: [88, 102, 116], mult: 1.3 } };
    stage.innerHTML = `<div class="gm-bar"><b>🏎️ Racing</b><span class="gm-spacer"></span><button type="button" class="btn bgh bsm" id="gm-quit">Back</button></div>
      <div class="gm-pick"><h2>Choose your difficulty</h2><p>Race three bots over 1,200 m. Harder levels give a higher score.</p></div>
      <div class="gm-levels">${Object.keys(LV).map((k) => `<button type="button" class="gm-lvl" data-lv="${k}"><span>${LV[k].icon}</span><b>${LV[k].name}</b><small>${LV[k].note}</small></button>`).join('')}</div>`;
    $('gm-quit').onclick = backToMenu;
    stage.querySelector('.gm-levels').onclick = (e) => { const b = e.target.closest('.gm-lvl'); if (b) raceRun(list, LV[b.dataset.lv], b.dataset.lv); };
  }
  function raceRun(list, lv, lvKey) {
    const next = deckOf(list), TIME = 60, MAXV = 200, TARGET = 1200;
    const FAULTS = ['💥 Flat tire!', '🔥 Engine overheating!', '⛽ Fuel leak!', '🔧 Gearbox stuck!'];
    const cars = [
      { name: 'You', me: true, icon: '🏎️', d: 0, v: 50 },
      { name: 'Bot Ming', icon: '🚙', d: 0, v: lv.bots[0] * .8, base: lv.bots[0] },
      { name: 'Bot Lan', icon: '🚕', d: 0, v: lv.bots[1] * .8, base: lv.bots[1] },
      { name: 'Bot Hu', icon: '🚓', d: 0, v: lv.bots[2] * .8, base: lv.bots[2] },
    ];
    const me = cars[0];
    let left = TIME, right = 0, total = 0, combo = 0, bestCombo = 0, trouble = 0, over = false, cur = null, locked = false, clock = 0;
    const wrong = [];
    stage.innerHTML = `<div class="gm-bar"><span class="gm-stat">⏱ <b id="r-t">${TIME}</b>s</span><span class="gm-stat">Speed <b id="r-v">50</b> km/h</span><span class="gm-stat">Place <b id="r-p">1</b>/4</span><span class="gm-spacer"></span><button type="button" class="btn bgh bsm" id="gm-quit">Quit</button></div>
      <div class="gm-time" id="r-bar"><i style="width:100%"></i></div>
      <div class="rc-track">${cars.map((c, i) => `<div class="rc-lane${c.me ? ' me' : ''}"><span class="rc-name">${esc(c.name)}</span><div class="rc-run"><div class="rc-car" id="r-c${i}"><span class="rc-body">${c.icon}</span>${c.me ? '<span class="rc-smoke">💨</span>' : ''}</div></div><span class="rc-finish">🏁</span></div>`).join('')}</div>
      <div class="rc-flag" id="r-flag"></div>
      <div id="r-q"></div>`;
    $('gm-quit').onclick = backToMenu;
    const flag = $('r-flag'), meEl = $('r-c0');
    function ask() {
      if (over) return;
      cur = { w: next(), mode: Math.random() < 0.6 ? 'zh' : 'id' }; locked = false;
      $('r-q').innerHTML = question(cur.w, cur.mode).html;
    }
    $('r-q').addEventListener('click', (e) => {
      const b = e.target.closest('.gm-opt'); if (!b || b.disabled || over || locked) return;
      locked = true; total++;
      document.querySelectorAll('#r-q .gm-opt').forEach((x) => { x.disabled = true; if (x.dataset.n === String(cur.w.n)) x.classList.add('right'); });
      if (b.dataset.n === String(cur.w.n)) {
        right++; combo++; bestCombo = Math.max(bestCombo, combo);
        me.v = Math.min(MAXV, me.v + (trouble > 0 ? 16 : 30) + Math.min(combo, 5) * 3);
      } else {
        b.classList.add('wrong'); combo = 0;
        trouble = 2.5; me.v = Math.max(30, me.v * 0.55);
        flag.textContent = FAULTS[Math.floor(Math.random() * FAULTS.length)];
        meEl.classList.add('hurt');
        if (!wrong.find((x) => x.n === cur.w.n) && wrong.length < 8) wrong.push(cur.w);
      }
      later(ask, 400);
    });
    const place = () => 1 + cars.filter((c) => c !== me && ((c.at != null && (me.at == null || c.at < me.at)) || (c.at == null && me.at == null && c.d > me.d))).length;
    const DT = 0.05;
    every(() => {
      if (over) return;
      left -= DT; clock += DT;
      if (trouble > 0) { trouble -= DT; if (trouble <= 0) { meEl.classList.remove('hurt'); flag.textContent = ''; } }
      me.v = Math.max(trouble > 0 ? 20 : 35, me.v - (trouble > 0 ? 6 : 3) * DT);   // the car slowly loses speed if you stop answering
      cars.forEach((c, i) => {
        if (!c.me && c.at == null) {                      // bots: a steady pace with a little random wobble
          c.v += (c.base - c.v) * 0.04 + (Math.random() - 0.5) * 7;
          c.v = Math.max(lv.bots[0] * .7, Math.min(c.base + 14, c.v));
        }
        if (c.at == null) { c.d += c.v / 3.6 * DT; if (c.d >= TARGET) { c.d = TARGET; c.at = clock; } }
        $('r-c' + i).style.left = Math.min(100, c.d / TARGET * 100) + '%';
      });
      const sec = Math.ceil(Math.max(0, left));
      if (sec !== +$('r-t').textContent) { $('r-t').textContent = sec; $('r-bar').classList.toggle('low', sec <= 10); }
      $('r-v').textContent = Math.round(me.v); $('r-p').textContent = place();
      $('r-bar').firstChild.style.width = Math.max(0, left) / TIME * 100 + '%';
      if (left <= 0 || me.at != null) {
        over = true;
        const pos = place(), won = pos === 1 && me.at != null;
        const bonus = me.at != null ? [800, 400, 150, 0][pos - 1] : 0;
        const score = Math.min(5000, Math.round((Math.round(me.d) + bonus) * lv.mult)), acc = total ? Math.round(right / total * 100) : 0;
        const lines = [won ? '🏆 You crossed the finish line first!' : me.at != null ? `🏁 You finished in place ${pos} of 4` : `⏱ Time is up. You were in place ${pos} of 4 (${Math.round(me.d)} of ${TARGET} m)`,
          `${lv.icon} ${lv.name} level · ${right} of ${total} correct (${acc}%) · best combo ${bestCombo}`];
        finish('race', score, lines, won || (acc >= 80 && right >= 12), wrong);
      }
    }, DT * 1000);
    ask();
  }


  /* ---------- story time (HSK 1-3): branching stories, several endings each, one message to take home ----------
     The stories live in hsk-stories<level>.js (window.HSK_STORIES[level]). A scene is {narr?, say, opts:[{zh,py,id,to}]};
     an ending is {end:'good'|'ok'|'bad', title, msg}. Paths can merge, so a story can be long without a huge tree. */
  const PTS = { good: 100, ok: 60, bad: 20 };
  function story() {
    const STORIES = (window.HSK_STORIES || {})[LEVEL] || [], KEY = 'hskStory' + LEVEL;
    let seen = {}; try { seen = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { seen = {}; }
    const total = (S) => Object.values(S.nodes).filter((n) => n.end).length;
    const found = (i) => (seen[i] || []).filter((id) => STORIES[i].nodes[id]).length;
    stage.innerHTML = `<div class="gm-bar"><b>📖 Story time</b><span class="gm-spacer"></span><button type="button" class="btn bgh bsm" id="gm-quit">Back</button></div>
      <div class="gm-pick"><h2>Choose a story</h2><p>Every choice changes what happens. Find all the endings.</p></div>
      <div class="st-list">${STORIES.map((s, i) => `<button type="button" class="st-book" data-i="${i}"><span>${s.icon}</span><div><b>${esc(s.title)}</b><small>${esc(s.sub)}</small></div><em>${found(i)}/${total(s)} endings</em></button>`).join('')}</div>`;
    $('gm-quit').onclick = backToMenu;
    stage.querySelector('.st-list').onclick = (e) => { const b = e.target.closest('.st-book'); if (b) play(+b.dataset.i); };
    function play(i) {
      const S = STORIES[i], N = total(S), trail = [];   // trail = the scenes visited, so "Previous" can step back
      function show(id) {
        const n = S.nodes[id];
        if (!n) return story();
        if (n.end) return ending(id, n);
        if (trail[trail.length - 1] !== id) trail.push(id);
        const step = trail.length;
        stage.innerHTML = `<div class="gm-bar"><b>${S.icon} ${esc(S.title)}</b><span class="gm-spacer"></span>${step > 1 ? '<button type="button" class="btn bgh bsm" id="st-prev">↩ Previous</button>' : ''}<button type="button" class="btn bgh bsm" id="gm-quit">Back</button></div>
          <div class="st-dots" aria-label="Scene ${step}"><span class="st-step">Scene ${step}</span><i class="on"></i>${'<i class="on"></i>'.repeat(Math.min(step - 1, 7))}${'<i></i>'.repeat(Math.max(0, 5 - step))}</div>
          <div class="st-card">${step === 1 ? `<p class="st-narr">${esc(S.intro)}</p>` : ''}${n.narr ? `<p class="st-narr">${esc(n.narr)}</p>` : ''}
            <div class="st-say"><span class="st-who">💬 ${esc(n.say.who)}</span><span class="zh" lang="zh">${esc(n.say.zh)}</span><span class="py">${esc(n.say.py)}</span><span class="id">${esc(n.say.id)}</span></div>
            <div class="st-ask">👇 What do you do?</div><div class="st-pick">${n.opts.map((o) => `<button type="button" class="st-opt" data-to="${esc(o.to)}"><span class="zh" lang="zh">${esc(o.zh)}</span><span class="py">${esc(o.py)}</span><span class="id">${esc(o.id)}</span></button>`).join('')}</div></div>`;
        $('gm-quit').onclick = story;
        const prev = $('st-prev'); if (prev) prev.onclick = () => { trail.pop(); show(trail.pop()); };
        stage.querySelector('.st-pick').onclick = (e) => { const b = e.target.closest('.st-opt'); if (b) show(b.dataset.to); };
        window.scrollTo({ top: 0 });
      }
      function ending(id, n) {
        (seen[i] = seen[i] || []); if (!seen[i].includes(id)) seen[i].push(id);
        try { localStorage.setItem(KEY, JSON.stringify(seen)); } catch (e) { /* optional */ }
        const icon = { good: '🌟', ok: '🙂', bad: '🌧️' }[n.end], f = found(i);
        const all = f >= N ? `<span class="st-msg" style="display:block"><b>🏅 All ${N} endings found!</b>You have seen every way this story can end.</span>` : '';
        finish('story', PTS[n.end], [`${icon} <b>${esc(n.title)}</b> (ending ${f} of ${N} found · ${trail.length} scenes)`, `<span class="st-msg" style="display:block"><b>💡 Message to take home</b>${esc(n.msg)}</span>`, all], n.end === 'good', []);
      }
      show(S.start);
    }
  }

  async function start(game, skipIntro) {
    await ready;
    const list = pool();
    if (list.length < 4) { alert('Choose more words: this selection has fewer than 4 words. Try "All words".'); return; }
    stopTimers(); menu.hidden = true; stage.hidden = false;
    if (!(history.state && history.state.gm)) { try { history.pushState({ gm: 1 }, ''); } catch (err) { /* optional */ } }
    if (backLabel) backLabel.textContent = 'All games';
    const run = () => ({ memory, speed, ladder, match, fill, riddle, race, story })[game](list);
    const tile = menu.querySelector(`[data-game="${game}"]`);
    if (game === 'race' || game === 'story' || !tile || skipIntro) run();
    else {                                   // a small "how it works" screen inside the frame
      stage.innerHTML = `<div class="gm-bar"><b>${esc(tile.querySelector('b').textContent)}</b><span class="gm-spacer"></span><button type="button" class="btn bgh bsm" id="gm-quit">Back</button></div>
        <div class="gm-intro"><span class="gm-ico">${tile.querySelector('.gm-ico').textContent}</span><h2>${esc(tile.querySelector('b').textContent)}</h2><p>${esc(tile.querySelector('small').textContent)}</p><button type="button" class="btn bg" id="gm-go">▶ Start</button></div>`;
      $('gm-quit').onclick = backToMenu; $('gm-go').onclick = run;
    }
    window.scrollTo({ top: 0 });
  }
  menu.addEventListener('click', (e) => { const t = e.target.closest('[data-game]'); if (t) start(t.dataset.game); });
})();
