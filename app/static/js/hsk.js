/* HSK study pages. UI text is English; the lesson content itself (meanings, tricks, notes)
   stays Indonesian. Everything runs in the browser; "mastered" marks live in localStorage
   per account and level on this device. All text goes in with textContent. */
(function () {
  const root = document.getElementById('hsk-app');
  if (!root) return;
  const $ = (id) => document.getElementById(id);
  const LEVEL = root.dataset.level || '1';
  const KEY = 'hsk' + LEVEL + '_known_v1_' + (root.dataset.uid || '0');
  const SVGNS = 'http://www.w3.org/2000/svg';

  let known = new Set();
  try { known = new Set(JSON.parse(localStorage.getItem(KEY) || '[]')); } catch (e) {}
  function save() { try { localStorage.setItem(KEY, JSON.stringify([...known])); } catch (e) {} }

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }
  function icon(name) {                       // <svg><use href="#i-name"/></svg> from the page sprite
    const s = document.createElementNS(SVGNS, 'svg');
    s.setAttribute('class', 'hk-i');
    const u = document.createElementNS(SVGNS, 'use');
    u.setAttribute('href', '#i-' + name);
    s.appendChild(u);
    return s;
  }
  const norm = (s) => String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  const canSpeak = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
  /* Phones are the tricky part: the voice list loads late, Android only speaks Chinese when a Chinese
     voice is installed (Settings > Text-to-speech), and iPhones stay silent in silent mode. So we wait
     for the voices, pick a Chinese one, and tell the student what is wrong when nothing plays. */
  let voices = [];
  function loadVoices() { try { voices = speechSynthesis.getVoices() || []; } catch (e) { voices = []; } }
  if (canSpeak) { loadVoices(); speechSynthesis.addEventListener && speechSynthesis.addEventListener('voiceschanged', loadVoices); }
  const say = (m) => { if (typeof showToast === 'function') showToast(m, 'err'); };
  function speak(t) {
    if (!canSpeak) { say('This browser cannot read aloud. Try Chrome or Safari.'); return; }
    loadVoices();
    const zh = voices.filter((v) => /^zh[-_]?(cn|hans)?/i.test(v.lang) || /chinese|mandarin|中文|普通话/i.test(v.name));
    if (voices.length && !zh.length) { say('No Chinese voice on this device. Install one: Settings > Text-to-speech (Android) or Spoken Content (iPhone).'); return; }
    const u = new SpeechSynthesisUtterance(t);
    u.lang = 'zh-CN'; u.rate = 0.85; u.volume = 1;
    if (zh.length) u.voice = zh.find((v) => /zh[-_]cn/i.test(v.lang)) || zh[0];
    let started = false;
    u.onstart = () => { started = true; };
    u.onerror = () => say('Could not play the sound. Check the volume, and that the phone is not on silent.');
    try { speechSynthesis.cancel(); if (speechSynthesis.paused) speechSynthesis.resume(); } catch (e) {}
    setTimeout(() => {                                 // Chrome on Android drops a speak() sent right after cancel()
      try { speechSynthesis.speak(u); } catch (e) { say('Could not play the sound.'); }
      setTimeout(() => { if (!started && !speechSynthesis.speaking) say('No sound started. Turn the volume up and switch silent mode off.'); }, 2500);
    }, 60);
  }

  /* ───────────── index page ───────────── */
  if (root.dataset.page === 'index') {
    const countKnown = (ns) => ns.filter((n) => known.has(n)).length;
    function paint() {
      document.querySelectorAll('.hk-theme[data-ns]').forEach((a) => {
        const ns = a.dataset.ns.split(',').map(Number);
        const k = countKnown(ns);
        a.querySelector('.hk-theme-done').textContent = k;
        a.querySelector('.hk-theme-bar i').style.width = (ns.length ? k / ns.length * 100 : 0) + '%';
      });
      const all = $('hk-overall').dataset.all.split(',').map(Number);
      const k = countKnown(all);
      $('hk-overall-text').textContent = 'Mastered ' + k + ' of ' + all.length + ' words';
      $('hk-overall-bar').style.width = (k / all.length * 100) + '%';
    }
    paint();

    let all = null, loading = false;
    const input = $('hk-search'), box = $('hk-results');
    function render(q) {
      box.replaceChildren();
      const nq = norm(q.trim());
      if (!nq) { box.hidden = true; return; }
      const hits = all.filter((e) => e.hanzi.includes(q.trim()) || norm(e.pinyin).replace(/\s/g, '').includes(nq.replace(/\s/g, '')) || norm(e.arti).includes(nq)).slice(0, 12);
      box.hidden = false;
      if (!hits.length) { box.appendChild(el('div', 'hk-nohit', 'No words found')); return; }
      hits.forEach((e) => {
        const a = el('a', 'hk-hit');
        a.href = '/hsk' + LEVEL + '/' + e.theme + '#w' + e.n;
        const zh = el('span', 'hk-hit-zh', e.hanzi); zh.lang = 'zh';
        a.append(zh, el('span', 'hk-hit-py', e.pinyin), el('span', 'hk-hit-id', e.arti));
        box.appendChild(a);
      });
    }
    input.addEventListener('input', async () => {
      if (!all && !loading) {
        loading = true;
        try {
          const r = await fetch('/hsk' + LEVEL + '/data.json', { credentials: 'same-origin' });
          all = r.ok ? await r.json() : [];
        } catch (e) { all = []; }
        loading = false;
      }
      if (all) render(input.value);
    });
    return;
  }

  /* ───────────── theme page ───────────── */
  const entries = JSON.parse($('hsk-data').textContent);
  const updateKnownCount = () => { $('hk-known-count').textContent = entries.filter((e) => known.has(e.n)).length; };

  /* tabs */
  const tabList = $('tab-list'), tabPrac = $('tab-practice');
  function showTab(which) {
    const list = which === 'list';
    $('view-list').hidden = !list; $('view-practice').hidden = list;
    tabList.classList.toggle('on', list); tabPrac.classList.toggle('on', !list);
    tabList.setAttribute('aria-selected', list); tabPrac.setAttribute('aria-selected', !list);
    if (!list) startPractice();
  }
  tabList.addEventListener('click', () => showTab('list'));
  tabPrac.addEventListener('click', () => showTab('practice'));

  /* word list */
  const listEl = $('hk-list');
  function section(ic, label, content, cls) {
    const s = el('div', 'hk-sec' + (cls ? ' ' + cls : ''));
    const h = el('div', 'hk-sec-label'); h.append(icon(ic), document.createTextNode(label));
    s.appendChild(h);
    if (typeof content === 'string') s.appendChild(el('div', 'hk-sec-text', content));
    else s.appendChild(content);
    return s;
  }
  function buildItem(e) {
    const item = el('div', 'hk-item'); item.id = 'w' + e.n;
    const row = el('button', 'hk-row'); row.type = 'button'; row.setAttribute('aria-expanded', 'false');
    const zh = el('span', 'hk-zh', e.hanzi); zh.lang = 'zh';
    const mid = el('span', 'hk-mid');
    mid.append(el('span', 'hk-py', e.pinyin), el('span', 'hk-id', e.arti));
    const flag = el('span', 'hk-flag'); flag.appendChild(icon('check'));
    const chev = el('span', 'hk-chev'); chev.appendChild(icon('down'));
    row.append(zh, mid, flag, chev);

    const det = el('div', 'hk-detail'); det.hidden = true;
    det.appendChild(section('parts', 'Components', e.parts));
    det.appendChild(section('bulb', 'Memory trick', e.trick));
    if (e.history) det.appendChild(section('history', 'Origin', e.history));
    if (e.words && e.words.length) {
      const ul = el('div', 'hk-words');
      e.words.forEach((w) => {
        const li = el('div', 'hk-word');
        const wz = el('span', 'hk-word-zh', w[0]); wz.lang = 'zh';
        li.append(wz, el('span', 'hk-word-py', w[1]), el('span', 'hk-word-id', w[2]));
        ul.appendChild(li);
      });
      det.appendChild(section('words', 'Example words', ul));
    }
    const sen = el('div', 'hk-sen');
    const s0 = el('div', 'hk-sen-zh', e.sentence[0]); s0.lang = 'zh';
    sen.append(s0, el('div', 'hk-sen-py', e.sentence[1]), el('div', 'hk-sen-id', e.sentence[2]));
    det.appendChild(section('quote', 'Example sentence', sen));
    if (e.note) det.appendChild(section('info', 'Note', e.note, 'hk-note'));

    const act = el('div', 'hk-act');
    function pill(ic, text, fn, cls) {
      const b = el('button', 'hk-pill' + (cls ? ' ' + cls : '')); b.type = 'button';
      b.append(icon(ic), document.createTextNode(text)); b.addEventListener('click', fn); return b;
    }
    if (canSpeak) {
      act.appendChild(pill('volume', 'Word', () => speak(e.hanzi)));
      act.appendChild(pill('volume', 'Sentence', () => speak(e.sentence[0])));
    }
    const kb = el('button', 'hk-pill hk-pill-main'); kb.type = 'button';
    function paintKb() {
      const k = known.has(e.n);
      kb.replaceChildren(icon(k ? 'x' : 'check'), document.createTextNode(k ? 'Mark as not mastered' : 'Mark as mastered'));
      item.classList.toggle('known', k);
    }
    kb.addEventListener('click', () => {
      if (known.has(e.n)) known.delete(e.n); else known.add(e.n);
      save(); paintKb(); updateKnownCount();
    });
    paintKb();
    act.appendChild(kb);
    det.appendChild(act);

    row.addEventListener('click', () => {
      const open = det.hidden;
      det.hidden = !open; row.setAttribute('aria-expanded', open); item.classList.toggle('open', open);
    });
    item._paint = paintKb;
    item.append(row, det);
    return item;
  }
  const items = entries.map(buildItem);
  items.forEach((i) => listEl.appendChild(i));

  const filterEl = $('hk-filter'), onlyUnknown = $('hk-only-unknown');
  function applyFilter() {
    const q = filterEl.value.trim(), nq = norm(q).replace(/\s/g, '');
    let shown = 0;
    entries.forEach((e, idx) => {
      let ok = true;
      if (q) ok = e.hanzi.includes(q) || norm(e.pinyin).replace(/\s/g, '').includes(nq) || norm(e.arti).includes(norm(q));
      if (ok && onlyUnknown.checked && known.has(e.n)) ok = false;
      items[idx].hidden = !ok; if (ok) shown++;
    });
    $('hk-empty').hidden = shown > 0;
  }
  filterEl.addEventListener('input', applyFilter);
  onlyUnknown.addEventListener('change', applyFilter);
  updateKnownCount();

  if (location.hash && /^#w\d+$/.test(location.hash)) {      // open the word a search result pointed at
    const t = document.querySelector(location.hash + ' .hk-row');
    if (t) { t.click(); t.scrollIntoView({ block: 'center' }); }
  }

  /* flashcards */
  const card = $('fc-card');
  let deck = [], pos = 0, gotIt = 0, mode = 'zh', onlyNew = true;

  function buildDeck() { return onlyNew ? entries.filter((e) => !known.has(e.n)) : entries.slice(); }
  function showDeck(on) { $('fc').hidden = !on; }
  function startPractice(shuffle) {
    deck = buildDeck();
    if (shuffle) for (let i = deck.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [deck[i], deck[j]] = [deck[j], deck[i]]; }
    pos = 0; gotIt = 0;
    $('fc-done').hidden = true;
    const none = deck.length === 0;
    $('fc-none').hidden = !none; showDeck(!none);
    if (!none) render();
  }
  function render() {
    const e = deck[pos], zhMode = mode === 'zh';
    card.classList.remove('flipped');
    const f = $('fc-front'), b = $('fc-back');
    f.textContent = zhMode ? e.hanzi : e.arti;
    f.classList.toggle('is-zh', zhMode); if (zhMode) f.lang = 'zh'; else f.removeAttribute('lang');
    b.textContent = zhMode ? e.arti : e.hanzi;
    b.classList.toggle('is-zh', !zhMode); if (!zhMode) b.lang = 'zh'; else b.removeAttribute('lang');
    $('fc-back-sub').textContent = e.pinyin;
    $('fc-sen-zh').textContent = e.sentence[0];
    $('fc-sen-py').textContent = e.sentence[1];
    $('fc-sen-id').textContent = e.sentence[2];
    $('fc-count').textContent = 'Card ' + (pos + 1) + ' of ' + deck.length;
    $('fc-known').textContent = known.size ? entries.filter((x) => known.has(x.n)).length + ' mastered' : '';
    $('fc-prog').style.width = ((pos + 1) / deck.length * 100) + '%';
    $('fc-prev').disabled = pos === 0;
    $('fc-speak').hidden = !canSpeak;
  }
  function advance() { if (pos + 1 >= deck.length) finish(); else { pos++; render(); } }
  function finish() {
    showDeck(false); $('fc-done').hidden = false;
    $('fc-done-title').textContent = 'Nice work!';
    $('fc-done-sub').textContent = 'You marked ' + gotIt + ' of ' + deck.length + ' cards as mastered.';
  }
  function setKnown(n, on) {
    if (on) known.add(n); else known.delete(n);
    save(); updateKnownCount();
    const it = document.getElementById('w' + n); if (it && it._paint) it._paint();
  }
  const flip = () => card.classList.toggle('flipped');
  card.addEventListener('click', flip);
  card.addEventListener('keydown', (ev) => {
    if (ev.key === ' ' || ev.key === 'Enter') { ev.preventDefault(); flip(); }
    else if (ev.key === 'ArrowRight') advance();
    else if (ev.key === 'ArrowLeft' && pos > 0) { pos--; render(); }
  });
  $('fc-next').addEventListener('click', advance);
  $('fc-prev').addEventListener('click', () => { if (pos > 0) { pos--; render(); } });
  $('fc-know').addEventListener('click', () => { setKnown(deck[pos].n, true); gotIt++; advance(); });
  $('fc-again').addEventListener('click', () => { setKnown(deck[pos].n, false); advance(); });
  $('fc-speak').addEventListener('click', (ev) => { ev.stopPropagation(); speak(deck[pos].hanzi); });
  $('fc-redo').addEventListener('click', () => startPractice());
  $('hk-shuffle').addEventListener('click', () => startPractice(true));
  document.querySelectorAll('.hk-seg-btn').forEach((b) => b.addEventListener('click', () => {
    mode = b.dataset.mode;
    document.querySelectorAll('.hk-seg-btn').forEach((x) => { const on = x === b; x.classList.toggle('on', on); x.setAttribute('aria-pressed', on); });
    if (deck.length && !$('fc').hidden) render();
  }));
  const chip = $('hk-practice-unknown');
  chip.addEventListener('click', () => {
    onlyNew = !onlyNew; chip.classList.toggle('on', onlyNew); chip.setAttribute('aria-pressed', onlyNew);
    startPractice();
  });
})();
