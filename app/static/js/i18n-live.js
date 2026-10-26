/* i18n-live.js - switch the whole page between English and Mandarin with no reload.

   The server renders each page in the language saved in the session. This script
   then (1) converts anything that is still in the other language, using the
   dictionary from /i18n-data.js, and (2) when the person clicks EN or 中文,
   converts the whole page on the spot and tells the server to remember the choice.

   Public API: window.I18N.t(text), .apply(element), .set(lang), .lang */
(function () {
  const D = window.I18N_DATA;
  if (!D) return;

  const html = document.documentElement;
  let lang = /^zh/i.test(html.lang) ? 'zh' : 'en';

  const SKIP = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'CODE', 'PRE', 'NOSCRIPT']);
  const ATTRS = ['placeholder', 'title', 'aria-label', 'alt', 'data-show', 'data-hide'];
  const hasOwn = Object.prototype.hasOwnProperty;
  const escRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  /* ---------- patterns: "{n} students registered" <-> "已注册 {n} 位学生" ---------- */
  function compile(from, to) {
    return D.patterns.map((pair) => {
      const names = [];
      const src = escRe(pair[from]).replace(/\\\{(\w+)\\\}/g, (_, n) => { names.push(n); return /^num/.test(n) ? '(\\d+)' : '([\\s\\S]+?)'; });
      return { re: new RegExp('^' + src + '$'), dst: pair[to], names };
    });
  }
  const PATTERNS = { zh: compile(0, 1), en: compile(1, 0) };
  function fill(p, m) {
    return p.dst.replace(/\{(\w+)\}/g, (_, n) => {
      const i = p.names.indexOf(n);
      return i >= 0 ? m[i + 1] : '';
    });
  }

  /* ---------- dates produced by fmt_date() ---------- */
  const dd = D.dates;
  const DATES = {
    zh: {
      re: new RegExp('(' + dd.en.days.join('|') + '), (\\d{2}) (' + dd.en.months.join('|') + ') (\\d{4})\\s+(\\d{2}):(\\d{2})', 'g'),
      fn: (m, day, d, mon, y, hh, mm) => y + '年' + dd.zh.months[dd.en.months.indexOf(mon)] + parseInt(d, 10) +
        '日（' + dd.zh.days[dd.en.days.indexOf(day)] + '）' + hh + ':' + mm,
    },
    en: {
      re: new RegExp('(\\d{4})年(' + dd.zh.months.join('|') + ')(\\d{1,2})日（(' + dd.zh.days.join('|') + ')）(\\d{2}):(\\d{2})', 'g'),
      fn: (m, y, mon, d, day, hh, mm) => dd.en.days[dd.zh.days.indexOf(day)] + ', ' + String(d).padStart(2, '0') + ' ' +
        dd.en.months[dd.zh.months.indexOf(mon)] + ' ' + y + '  ' + hh + ':' + mm,
    },
  };

  /* ---------- string lookup ---------- */
  function lookup(s, target) {
    const map = target === 'zh' ? D.en2zh : D.zh2en;
    if (hasOwn.call(map, s)) return map[s];
    for (const p of PATTERNS[target]) {
      const m = p.re.exec(s);
      if (m) return fill(p, m);
    }
    return null;
  }

  const TO_ZH = { ':': '：', '?': '？', '!': '！', ',': '，', '.': '。' };
  const TO_EN = { '：': ':', '？': '?', '！': '!', '，': ',', '。': '.' };
  const punct = (s, target) => s.replace(target === 'zh' ? /[:?!,.]/g : /[：？！，。]/g, (c) => (target === 'zh' ? TO_ZH : TO_EN)[c]);
  const EDGE = /^([^\p{L}\p{N}]*)([\s\S]*?)([^\p{L}\p{N}]*)$/u;

  /* strftime-style dates written by the schedule code: "Mon, 19 Oct 2026 · 05:15", "21 Oct", "23 Oct 2026" */
  const sh = dd.short;
  const alt = (a) => a.join('|');
  const SHORT = {
    zh: {
      embedded: [{
        re: new RegExp('(' + alt(sh.en_days) + '), (\\d{2}) (' + alt(sh.en_months) + ') (\\d{4}) · (\\d{2}):(\\d{2})', 'g'),
        fn: (m, day, d, mon, y, hh, mm) => y + '年' + (sh.en_months.indexOf(mon) + 1) + '月' + parseInt(d, 10) + '日（' +
          sh.zh_days[sh.en_days.indexOf(day)] + '）' + hh + ':' + mm,
      }],
      whole: [
        { re: new RegExp('^(\\d{1,2}) (' + alt(sh.en_months) + ') (\\d{4})$'), fn: (m, d, mon, y) => y + '年' + (sh.en_months.indexOf(mon) + 1) + '月' + parseInt(d, 10) + '日' },
        { re: new RegExp('^(\\d{1,2}) (' + alt(sh.en_months) + ')$'), fn: (m, d, mon) => (sh.en_months.indexOf(mon) + 1) + '月' + parseInt(d, 10) + '日' },
      ],
    },
    en: {
      embedded: [{
        re: new RegExp('(\\d{4})年(\\d{1,2})月(\\d{1,2})日（(' + alt(sh.zh_days) + ')）(\\d{2}):(\\d{2})', 'g'),
        fn: (m, y, mon, d, day, hh, mm) => sh.en_days[sh.zh_days.indexOf(day)] + ', ' + String(d).padStart(2, '0') + ' ' +
          sh.en_months[parseInt(mon, 10) - 1] + ' ' + y + ' · ' + hh + ':' + mm,
      }],
      whole: [
        { re: /^(\d{4})年(\d{1,2})月(\d{1,2})日$/, fn: (m, y, mon, d) => String(d).padStart(2, '0') + ' ' + sh.en_months[parseInt(mon, 10) - 1] + ' ' + y },
        { re: /^(\d{1,2})月(\d{1,2})日$/, fn: (m, mon, d) => String(d).padStart(2, '0') + ' ' + sh.en_months[parseInt(mon, 10) - 1] },
      ],
    },
  };

  function convert(s, target) {
    s = s.replace(DATES[target].re, DATES[target].fn);
    for (const r of SHORT[target].embedded) s = s.replace(r.re, r.fn);
    const whole = s.trim();
    for (const r of SHORT[target].whole) {
      if (r.re.test(whole)) return s.replace(whole, whole.replace(r.re, r.fn));
    }
    const trimmed = s.trim();
    if (!trimmed) return s;
    const start = s.indexOf(trimmed);
    const lead = s.slice(0, start);
    const tail = s.slice(start + trimmed.length);

    let out = lookup(trimmed, target);
    if (out === null) {
      const m = EDGE.exec(trimmed);
      if (m && (m[1] || m[3]) && m[2]) {
        const pre = m[1], core = m[2], post = m[3];
        let r = lookup(core + post, target);          // trailing punctuation may be part of the entry
        if (r !== null) out = pre + r;
        else {
          r = lookup(core, target);
          if (r !== null) out = pre + r + punct(post, target);
        }
      }
    }
    return out === null ? s : lead + out + tail;
  }

  /* ---------- walking the page ---------- */
  function skipped(el) {
    return !el || SKIP.has(el.nodeName.toUpperCase()) || !!(el.closest && el.closest('[data-no-i18n]'));
  }
  function doText(node, target) {
    if (skipped(node.parentElement)) return;
    const v = node.nodeValue;
    if (!v || !v.trim()) return;
    const out = convert(v, target);
    if (out !== v) node.nodeValue = out;
  }
  function doAttrs(el, target) {
    if (skipped(el)) return;
    for (const a of ATTRS) {
      if (!el.hasAttribute(a)) continue;
      const v = el.getAttribute(a);
      const out = convert(v, target);
      if (out !== v) el.setAttribute(a, out);
    }
    if (el.nodeName === 'INPUT' && (el.type === 'submit' || el.type === 'button') && el.value) {
      const out = convert(el.value, target);
      if (out !== el.value) el.value = out;
    }
  }
  function walk(root, target) {
    if (!root) return;
    if (root.nodeType === 3) { doText(root, target); return; }
    if (root.nodeType !== 1 || skipped(root)) return;
    doAttrs(root, target);
    const tw = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    let n;
    while ((n = tw.nextNode())) {
      if (n.nodeType === 3) doText(n, target);
      else doAttrs(n, target);
    }
  }
  function doTitle(target) {
    const parts = document.title.split(' · ');
    const out = parts.map((p) => convert(p, target)).join(' · ');
    if (out !== document.title) document.title = out;
  }

  /* ---------- keep up with content added later (toasts, modals, fetched cards) ---------- */
  let observer = null;
  function watch() {
    if (observer) return;
    observer = new MutationObserver((mutations) => {
      if (lang !== 'zh') return;     // English text needs no conversion
      for (const m of mutations) {
        if (m.type === 'childList') m.addedNodes.forEach((n) => walk(n, 'zh'));
        else if (m.type === 'characterData') doText(m.target, 'zh');
        else if (m.type === 'attributes') doAttrs(m.target, 'zh');
      }
    });
    observer.observe(html, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  }

  /* ---------- public API ---------- */
  function markButtons() {
    document.querySelectorAll('a[href*="/lang/"]').forEach((a) => {
      const m = /\/lang\/(en|zh)$/.exec(a.getAttribute('href') || '');
      if (m) a.classList.toggle('on', m[1] === lang);
    });
  }

  function set(next, persist) {
    if (next !== 'zh' && next !== 'en') return;
    lang = next;
    html.lang = next;
    walk(document.body, next);
    doTitle(next);
    markButtons();
    if (persist !== false) {
      fetch('/lang/' + next, { headers: { 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' })
        .catch(() => { /* the page is already switched; the next load falls back to the saved choice */ });
    }
    window.dispatchEvent(new CustomEvent('i18n:change', { detail: { lang: next } }));
  }

  window.I18N = {
    get lang() { return lang; },
    t: (s) => (lang === 'zh' ? convert(String(s), 'zh') : String(s)),
    apply: (el) => { if (lang === 'zh') walk(el || document.body, 'zh'); },
    set,
  };

  document.addEventListener('click', (e) => {
    const a = e.target.closest && e.target.closest('a[href*="/lang/"]');
    if (!a) return;
    const m = /\/lang\/(en|zh)$/.exec(a.getAttribute('href') || '');
    if (!m) return;
    e.preventDefault();
    set(m[1]);
  });

  /* first pass for the language this page was rendered in */
  if (lang === 'zh') { walk(document.body, 'zh'); doTitle('zh'); }
  watch();
})();
