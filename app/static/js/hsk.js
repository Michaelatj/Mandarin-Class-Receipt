/* HSK 1 study pages. Everything runs in the browser; "hafal" marks live in
   localStorage per account on this device. All text goes in with textContent. */
(function () {
  const root = document.getElementById('hsk-app');
  if (!root) return;
  const $ = (id) => document.getElementById(id);
  const KEY = 'hsk1_known_v1_' + (root.dataset.uid || '0');

  let known = new Set();
  try { known = new Set(JSON.parse(localStorage.getItem(KEY) || '[]')); } catch (e) {}
  function save() { try { localStorage.setItem(KEY, JSON.stringify([...known])); } catch (e) {} }

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }
  const norm = (s) => String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  const canSpeak = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
  function speak(t) {
    if (!canSpeak) return;
    const u = new SpeechSynthesisUtterance(t);
    u.lang = 'zh-CN'; u.rate = 0.85;
    speechSynthesis.cancel(); speechSynthesis.speak(u);
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
      $('hk-overall-text').textContent = 'Hafal ' + k + ' dari ' + all.length + ' kata';
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
      if (!hits.length) { box.appendChild(el('div', 'hk-nohit', 'Tidak ditemukan')); return; }
      hits.forEach((e) => {
        const a = el('a', 'hk-hit');
        a.href = '/hsk1/' + e.theme + '#w' + e.n;
        a.appendChild(el('span', 'hk-hit-zh', e.hanzi));
        a.appendChild(el('span', 'hk-hit-py', e.pinyin));
        a.appendChild(el('span', 'hk-hit-id', e.arti));
        box.appendChild(a);
      });
    }
    input.addEventListener('input', async () => {
      if (!all && !loading) {
        loading = true;
        try {
          const r = await fetch('/hsk1/data.json', { credentials: 'same-origin' });
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

  function updateKnownCount() {
    $('hk-known-count').textContent = entries.filter((e) => known.has(e.n)).length;
  }

  /* tabs */
  const tabList = $('tab-list'), tabPrac = $('tab-practice');
  function showTab(which) {
    const list = which === 'list';
    $('view-list').hidden = !list; $('view-practice').hidden = list;
    tabList.classList.toggle('on', list); tabPrac.classList.toggle('on', !list);
    tabList.setAttribute('aria-selected', list); tabPrac.setAttribute('aria-selected', !list);
    if (!list) startPractice(true);
  }
  tabList.addEventListener('click', () => showTab('list'));
  tabPrac.addEventListener('click', () => showTab('practice'));

  /* word list */
  const listEl = $('hk-list');
  function section(label, content, cls) {
    const s = el('div', 'hk-sec' + (cls ? ' ' + cls : ''));
    s.appendChild(el('div', 'hk-sec-label', label));
    if (typeof content === 'string') s.appendChild(el('div', 'hk-sec-text', content));
    else s.appendChild(content);
    return s;
  }
  function buildItem(e) {
    const item = el('div', 'hk-item'); item.id = 'w' + e.n; item.dataset.n = e.n;
    const row = el('button', 'hk-row'); row.type = 'button'; row.setAttribute('aria-expanded', 'false');
    const zh = el('span', 'hk-zh', e.hanzi); zh.lang = 'zh';
    const mid = el('span', 'hk-mid');
    mid.appendChild(el('span', 'hk-py', e.pinyin));
    mid.appendChild(el('span', 'hk-id', e.arti));
    const flag = el('span', 'hk-flag', '✓');
    row.append(zh, mid, flag);

    const det = el('div', 'hk-detail'); det.hidden = true;
    det.appendChild(section('Komponen', e.parts));
    det.appendChild(section('Trik mengingat', e.trick));
    if (e.history) det.appendChild(section('Asal-usul', e.history));
    if (e.words && e.words.length) {
      const ul = el('div', 'hk-words');
      e.words.forEach((w) => {
        const li = el('div', 'hk-word');
        const wz = el('span', 'hk-word-zh', w[0]); wz.lang = 'zh';
        li.append(wz, el('span', 'hk-word-py', w[1]), el('span', 'hk-word-id', w[2]));
        ul.appendChild(li);
      });
      det.appendChild(section('Kata contoh', ul));
    }
    const sen = el('div', 'hk-sen');
    const s0 = el('div', 'hk-sen-zh', e.sentence[0]); s0.lang = 'zh';
    sen.append(s0, el('div', 'hk-sen-py', e.sentence[1]), el('div', 'hk-sen-id', e.sentence[2]));
    det.appendChild(section('Contoh kalimat', sen));
    if (e.note) det.appendChild(section('Catatan', e.note, 'hk-note'));

    const act = el('div', 'hk-act');
    if (canSpeak) {
      const sp = el('button', 'btn bgh qz-btn-sm', '🔊 Dengarkan'); sp.type = 'button';
      sp.addEventListener('click', () => speak(e.hanzi));
      const sp2 = el('button', 'btn bgh qz-btn-sm', '🔊 Kalimat'); sp2.type = 'button';
      sp2.addEventListener('click', () => speak(e.sentence[0]));
      act.append(sp, sp2);
    }
    const kb = el('button', 'btn qz-btn-gold qz-btn-sm'); kb.type = 'button';
    function paintKb() { kb.textContent = known.has(e.n) ? 'Tandai belum hafal' : 'Tandai hafal'; item.classList.toggle('known', known.has(e.n)); }
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

  /* open the word a search result pointed at (#w123) */
  if (location.hash && /^#w\d+$/.test(location.hash)) {
    const t = document.querySelector(location.hash + ' .hk-row');
    if (t) { t.click(); t.scrollIntoView({ block: 'center' }); }
  }

  /* flashcards */
  const card = $('fc-card');
  let deck = [], pos = 0, seen = 0, gotIt = 0;
  function buildDeck() {
    let d = entries.slice();
    if ($('hk-practice-unknown').checked) d = d.filter((e) => !known.has(e.n));
    return d;
  }
  function startPractice(keepOrder) {
    deck = buildDeck(); pos = 0; seen = 0; gotIt = 0;
    $('fc-done').hidden = true;
    const none = deck.length === 0;
    $('fc-none').hidden = !none; $('fc').hidden = none;
    if (!none) render();
  }
  function render() {
    const e = deck[pos], zhMode = $('hk-mode').value === 'zh';
    card.classList.remove('flipped');
    const f = $('fc-front'), b = $('fc-back'), bs = $('fc-back-sub'), bw = $('fc-back-why');
    if (zhMode) {
      f.textContent = e.hanzi; f.lang = 'zh'; f.classList.remove('hk-small');
      b.textContent = e.arti; b.removeAttribute('lang');
      bs.textContent = e.pinyin;
      bw.textContent = e.sentence[0] + '\n' + e.sentence[1] + '\n' + e.sentence[2];
    } else {
      f.textContent = e.arti; f.removeAttribute('lang'); f.classList.add('hk-small');
      b.textContent = e.hanzi; b.lang = 'zh';
      bs.textContent = e.pinyin;
      bw.textContent = e.sentence[0] + '\n' + e.sentence[1] + '\n' + e.sentence[2];
    }
    $('fc-count').textContent = 'Kartu ' + (pos + 1) + ' dari ' + deck.length;
    $('fc-prog').style.width = ((pos + 1) / deck.length * 100) + '%';
    $('fc-prev').disabled = pos === 0;
    $('fc-speak').hidden = !canSpeak;
  }
  function advance() {
    if (pos + 1 >= deck.length) { finish(); return; }
    pos++; render();
  }
  function finish() {
    $('fc').querySelector('.fc-stage').hidden = true;
    $('fc-done').hidden = false;
    $('fc-done-title').textContent = 'Selesai!';
    $('fc-done-sub').textContent = 'Kamu menandai ' + gotIt + ' dari ' + deck.length + ' kartu sebagai hafal.';
  }
  function flip() { card.classList.toggle('flipped'); }
  card.addEventListener('click', flip);
  card.addEventListener('keydown', (ev) => {
    if (ev.key === ' ' || ev.key === 'Enter') { ev.preventDefault(); flip(); }
    else if (ev.key === 'ArrowRight') advance();
    else if (ev.key === 'ArrowLeft' && pos > 0) { pos--; render(); }
  });
  $('fc-next').addEventListener('click', advance);
  $('fc-prev').addEventListener('click', () => { if (pos > 0) { pos--; render(); } });
  $('fc-know').addEventListener('click', () => { known.add(deck[pos].n); gotIt++; save(); updateKnownCount(); refreshItem(deck[pos].n); advance(); });
  $('fc-again').addEventListener('click', () => { known.delete(deck[pos].n); save(); updateKnownCount(); refreshItem(deck[pos].n); advance(); });
  $('fc-speak').addEventListener('click', () => speak(deck[pos].hanzi));
  $('fc-redo').addEventListener('click', () => { $('fc').querySelector('.fc-stage').hidden = false; startPractice(); });
  $('hk-mode').addEventListener('change', () => { if (deck.length) render(); });
  $('hk-practice-unknown').addEventListener('change', () => { $('fc').querySelector('.fc-stage').hidden = false; startPractice(); });
  $('hk-shuffle').addEventListener('click', () => {
    $('fc').querySelector('.fc-stage').hidden = false;
    deck = buildDeck();
    for (let i = deck.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [deck[i], deck[j]] = [deck[j], deck[i]]; }
    pos = 0; seen = 0; gotIt = 0;
    $('fc-done').hidden = true;
    const none = deck.length === 0; $('fc-none').hidden = !none; $('fc').hidden = none;
    if (!none) render();
  });
  /* keep the list's "known" styling in sync when marking from the cards */
  function refreshItem(n) {
    const it = document.getElementById('w' + n);
    if (!it) return;
    it.classList.toggle('known', known.has(n));
    const btn = it.querySelector('.hk-act .qz-btn-gold');
    if (btn) btn.textContent = known.has(n) ? 'Tandai belum hafal' : 'Tandai hafal';
  }
})();
