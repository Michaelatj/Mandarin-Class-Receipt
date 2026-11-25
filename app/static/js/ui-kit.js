/* UI kit: our own dialogs (instead of the browser's alert / confirm / prompt), our own date and time
   picker (instead of the browser's), and the notification bell. Plain JS, no libraries, loaded on every page.
     UI.alert(msg)  UI.confirm(msg, {ok, cancel, danger})  UI.prompt(msg, {placeholder, ok})  -> Promise
   Native date fields (date / time / datetime-local) are upgraded automatically, also ones added later. */
(function () {
  'use strict';
  const $ = (s, r) => (r || document).querySelector(s);
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const t = (s) => { try { return window.I18N && I18N.t ? I18N.t(s) : s; } catch (e) { return s; } };
  const pad = (n) => String(n).padStart(2, '0');

  /* ---------------- dialogs ---------------- */
  let dlgOpen = 0;
  function dialog(kind, msg, o) {
    o = o || {};
    return new Promise((resolve) => {
      const back = el('div', 'ui-dlg'); back.setAttribute('role', 'dialog'); back.setAttribute('aria-modal', 'true');
      const card = el('div', 'ui-dlg-card');
      const icon = el('div', 'ui-dlg-ico ' + (o.danger ? 'danger' : kind === 'alert' ? 'info' : 'ask'), o.danger ? '!' : kind === 'alert' ? 'i' : '?');
      const body = el('div', 'ui-dlg-msg'); String(msg).split('\n\n').forEach((p) => { const d = el('p'); d.textContent = t(p); body.appendChild(d); });
      card.append(icon, body);
      let input = null;
      if (kind === 'prompt') { input = el('input', 'ui-dlg-input'); input.type = 'text'; input.placeholder = o.placeholder || ''; input.autocomplete = 'off'; card.appendChild(input); }
      const row = el('div', 'ui-dlg-row');
      const ok = el('button', 'ui-btn ' + (o.danger ? 'danger' : 'primary'), esc(t(o.ok || (kind === 'confirm' && o.danger ? 'Delete' : 'OK')))); ok.type = 'button';
      let cancel = null;
      if (kind !== 'alert') { cancel = el('button', 'ui-btn ghost', esc(t(o.cancel || 'Cancel'))); cancel.type = 'button'; row.appendChild(cancel); }
      row.appendChild(ok); card.appendChild(row); back.appendChild(card); document.body.appendChild(back);
      dlgOpen++; document.body.classList.add('ui-lock');
      const prevFocus = document.activeElement;
      function done(v) {
        document.removeEventListener('keydown', key, true);
        back.classList.add('out'); setTimeout(() => back.remove(), 160);
        if (--dlgOpen <= 0) document.body.classList.remove('ui-lock');
        if (prevFocus && prevFocus.focus) try { prevFocus.focus({ preventScroll: true }); } catch (e) { /* gone */ }
        resolve(v);
      }
      const accept = () => done(kind === 'prompt' ? input.value : true);
      const dismiss = () => done(kind === 'prompt' ? null : kind === 'alert' ? true : false);
      function key(e) {
        if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); dismiss(); }
        else if (e.key === 'Enter' && document.activeElement !== cancel) { e.preventDefault(); accept(); }
        else if (e.key === 'Tab') {                      // keep the focus inside the dialog
          const f = [...card.querySelectorAll('button,input')]; if (!f.length) return;
          const i = f.indexOf(document.activeElement);
          if (e.shiftKey && i <= 0) { e.preventDefault(); f[f.length - 1].focus(); } else if (!e.shiftKey && i === f.length - 1) { e.preventDefault(); f[0].focus(); }
        }
      }
      document.addEventListener('keydown', key, true);
      ok.addEventListener('click', accept); if (cancel) cancel.addEventListener('click', dismiss);
      back.addEventListener('mousedown', (e) => { if (e.target === back) dismiss(); });
      (input || (o.danger && cancel ? cancel : ok)).focus();
    });
  }
  window.UI = window.UI || {};
  UI.alert = (m, o) => dialog('alert', m, o);
  UI.confirm = (m, o) => dialog('confirm', m, o);
  UI.prompt = (m, o) => dialog('prompt', m, o);
  /* a form with a confirmation: <form onsubmit="return UI.confirmForm(event, 'Sure?')"> */
  UI.confirmForm = function (ev, msg, o) {
    const f = ev.target; if (f._uiOk) return true;
    ev.preventDefault(); ev.stopPropagation();
    UI.confirm(msg, Object.assign({ danger: true }, o)).then((yes) => { if (yes) { f._uiOk = true; if (f.requestSubmit) f.requestSubmit(ev.submitter || undefined); else f.submit(); } });
    return false;
  };
  window.alert = (m) => { UI.alert(String(m)); };       // anything old that still calls alert() gets the nice one

  /* ---------------- date / time picker ---------------- */
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], DAYS_L = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const valDesc = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
  const ICON_CAL = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15.5" rx="3"/><path d="M8 3v4M16 3v4M3.5 10h17"/></svg>';
  const ICON_CLOCK = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>';
  let pop = null;

  function parse(type, v) {
    let m;
    if (type === 'time') { m = /^(\d{2}):(\d{2})/.exec(v || ''); return m ? { h: +m[1], mi: +m[2] } : null; }
    m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(v || '');
    return m ? { y: +m[1], m: +m[2] - 1, d: +m[3], h: m[4] ? +m[4] : 0, mi: m[5] ? +m[5] : 0 } : null;
  }
  function fmtOut(type, o) {
    const dpart = `${o.y}-${pad(o.m + 1)}-${pad(o.d)}`, tpart = `${pad(o.h)}:${pad(o.mi)}`;
    return type === 'time' ? tpart : type === 'date' ? dpart : dpart + 'T' + tpart;
  }
  function fmtShow(type, v) {
    const o = parse(type, v); if (!o) return '';
    if (type === 'time') return `${pad(o.h)}:${pad(o.mi)}`;
    const dow = DAYS_L[new Date(o.y, o.m, o.d).getDay()], day = `${dow}, ${o.d} ${MONTHS[o.m].slice(0, 3)} ${o.y}`;
    return type === 'date' ? day : `${day} · ${pad(o.h)}:${pad(o.mi)}`;
  }

  function upgrade(inp) {
    if (inp._ui || !/^(date|time|datetime-local)$/.test(inp.type)) return;
    const type = inp.type, required = inp.required, btn = el('button', 'ui-dt');
    btn.type = 'button'; btn.className = 'ui-dt ' + (inp.className || ''); if (inp.getAttribute('style')) btn.setAttribute('style', inp.getAttribute('style'));
    btn.innerHTML = (type === 'time' ? ICON_CLOCK : ICON_CAL) + '<span class="ui-dt-t"></span>';
    const label = btn.querySelector('.ui-dt-t');
    const ph = type === 'time' ? 'Choose time' : type === 'date' ? 'Choose date' : 'Choose date and time';
    const sync = () => { const s = fmtShow(type, valDesc.get.call(inp)); label.textContent = s || ph; btn.classList.toggle('empty', !s); };
    inp._ui = btn; inp.required = false;
    inp.before(btn);
    const val = valDesc.get.call(inp); inp.type = 'hidden'; valDesc.set.call(inp, val);   // hidden: keeps its name, id and value for the form and for old scripts
    Object.defineProperty(inp, 'value', { configurable: true, get() { return valDesc.get.call(this); }, set(v) { valDesc.set.call(this, v); sync(); } });
    sync();
    btn.addEventListener('click', () => open(inp, btn, type, sync));
    const form = inp.form;
    if (form && required && !form._uiReq) {
      form._uiReq = true;
      form.addEventListener('submit', (e) => {
        const bad = [...form.querySelectorAll('input[type=hidden]')].find((i) => i._ui && i._req && !i.value);
        if (bad) { e.preventDefault(); e.stopImmediatePropagation(); UI.alert('Please choose a date and time first.'); bad._ui.focus(); }
      }, true);
    }
    inp._req = required;
  }

  function close() { if (!pop) return; const p = pop; pop = null; document.removeEventListener('mousedown', outside, true); document.removeEventListener('keydown', escKey, true); window.removeEventListener('resize', close); p.back.classList.add('out'); setTimeout(() => p.back.remove(), 140); }
  function outside(e) { if (pop && !pop.card.contains(e.target) && !(pop.btn.contains(e.target))) close(); }
  function escKey(e) { if (e.key === 'Escape') { e.stopPropagation(); close(); } }

  function open(inp, btn, type, sync) {
    if (pop) { const same = pop.btn === btn; close(); if (same) return; }
    const cur = parse(type, inp.value), now = new Date();
    let st;
    if (cur) st = Object.assign({}, cur);
    else { const r = Math.ceil(now.getMinutes() / 5) * 5; st = { y: now.getFullYear(), m: now.getMonth(), d: now.getDate(), h: now.getHours() + (r === 60 ? 1 : 0), mi: r % 60 }; if (st.h > 23) st.h = 23; }
    let vy = st.y, vm = st.m, chosen = !!cur;
    const back = el('div', 'ui-pick-back'), card = el('div', 'ui-pick');
    back.appendChild(card); document.body.appendChild(back);
    pop = { back, card, btn };
    const commit = () => { if (!chosen) return; valDesc.set.call(inp, fmtOut(type, st)); sync(); inp.dispatchEvent(new Event('input', { bubbles: true })); inp.dispatchEvent(new Event('change', { bubbles: true })); };

    function render() {
      let h = '';
      if (type !== 'time') {
        h += `<div class="ui-pick-head"><button type="button" class="ui-pk-nav" data-nav="-1" aria-label="Previous month">‹</button><b>${MONTHS[vm]} ${vy}</b><button type="button" class="ui-pk-nav" data-nav="1" aria-label="Next month">›</button></div>`;
        h += '<div class="ui-pk-week">' + DAYS.map((d) => `<span>${d}</span>`).join('') + '</div><div class="ui-pk-grid">';
        const first = (new Date(vy, vm, 1).getDay() + 6) % 7, start = new Date(vy, vm, 1 - first);
        for (let i = 0; i < 42; i++) {
          const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
          const sel = chosen && d.getFullYear() === st.y && d.getMonth() === st.m && d.getDate() === st.d;
          const today = d.toDateString() === now.toDateString();
          h += `<button type="button" class="ui-pk-d${d.getMonth() !== vm ? ' off' : ''}${today ? ' today' : ''}${sel ? ' sel' : ''}" data-d="${d.getFullYear()}-${d.getMonth()}-${d.getDate()}">${d.getDate()}</button>`;
        }
        h += '</div>';
      }
      if (type !== 'date') {
        h += '<div class="ui-pk-time"><div class="ui-pk-tl">Time</div><div class="ui-pk-cols"><div class="ui-pk-col" data-col="h">';
        for (let i = 0; i < 24; i++) h += `<button type="button" class="ui-pk-t${chosen && st.h === i ? ' sel' : ''}" data-h="${i}">${pad(i)}</button>`;
        h += '</div><span class="ui-pk-colon">:</span><div class="ui-pk-col" data-col="m">';
        const mins = []; for (let i = 0; i < 60; i += 5) mins.push(i); if (chosen && mins.indexOf(st.mi) < 0) { mins.push(st.mi); mins.sort((a, b) => a - b); }
        mins.forEach((i) => { h += `<button type="button" class="ui-pk-t${chosen && st.mi === i ? ' sel' : ''}" data-mi="${i}">${pad(i)}</button>`; });
        h += '</div></div></div>';
      }
      h += `<div class="ui-pk-foot"><button type="button" class="ui-btn ghost sm" data-act="now">${type === 'time' ? 'Now' : 'Today'}</button><span class="ui-pk-sum">${chosen ? esc(fmtShow(type, fmtOut(type, st))) : ''}</span><button type="button" class="ui-btn primary sm" data-act="done">Done</button></div>`;
      card.innerHTML = h;
      card.querySelectorAll('.ui-pk-col').forEach((c) => { const s = c.querySelector('.sel'); if (s) c.scrollTop = s.offsetTop - c.clientHeight / 2 + s.offsetHeight / 2; });
    }
    render();
    function place() {
      if (window.innerWidth < 640) { back.classList.add('sheet'); card.style.cssText = ''; return; }
      const r = btn.getBoundingClientRect(), w = card.offsetWidth, hgt = card.offsetHeight;
      let left = Math.min(Math.max(8, r.left), window.innerWidth - w - 8), top = r.bottom + 6;
      if (top + hgt > window.innerHeight - 8) top = Math.max(8, r.top - hgt - 6);
      card.style.left = left + 'px'; card.style.top = top + 'px';
    }
    place();
    card.addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return;
      if (b.dataset.nav) { vm += +b.dataset.nav; if (vm < 0) { vm = 11; vy--; } else if (vm > 11) { vm = 0; vy++; } render(); return; }
      if (b.dataset.d) { const [y, m, d] = b.dataset.d.split('-').map(Number); st.y = y; st.m = m; st.d = d; vy = y; vm = m; chosen = true; commit(); render(); return; }
      if (b.dataset.h != null && b.dataset.h !== '') { st.h = +b.dataset.h; if (!cur && type === 'datetime-local' && !chosen) { st.y = now.getFullYear(); st.m = now.getMonth(); st.d = now.getDate(); } chosen = true; commit(); render(); return; }
      if (b.dataset.mi != null && b.dataset.mi !== '') { st.mi = +b.dataset.mi; chosen = true; commit(); render(); return; }
      if (b.dataset.act === 'now') {
        const n = new Date(); if (type !== 'time') { st.y = n.getFullYear(); st.m = n.getMonth(); st.d = n.getDate(); vy = st.y; vm = st.m; }
        if (type !== 'date') { st.h = n.getHours(); st.mi = n.getMinutes(); }
        chosen = true; commit(); render(); return;
      }
      if (b.dataset.act === 'done') { chosen = true; commit(); close(); btn.focus({ preventScroll: true }); }
    });
    document.addEventListener('mousedown', outside, true); document.addEventListener('keydown', escKey, true); window.addEventListener('resize', close);
    back.addEventListener('mousedown', (e) => { if (e.target === back) close(); });
  }

  const scan = (root) => (root.querySelectorAll ? root.querySelectorAll('input[type=date],input[type=time],input[type=datetime-local]') : []).forEach(upgrade);
  scan(document);
  new MutationObserver((muts) => muts.forEach((m) => m.addedNodes.forEach((n) => { if (n.nodeType === 1) { if (n.matches && n.matches('input[type=date],input[type=time],input[type=datetime-local]')) upgrade(n); scan(n); } }))).observe(document.body, { childList: true, subtree: true });

  /* ---------------- notification bell ---------------- */
  const loggedIn = document.body.dataset.notif != null;
  if (loggedIn) {
    const KIND = { class: '📆', quiz: '📝', receipt: '🧾', hsk: '🎁', student: '👤', info: '🔔' };
    let unread = parseInt(document.body.dataset.notif, 10) || 0, panel = null, bell = null, badge = null;
    const ago = (iso) => {
      const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
      if (s < 60) return 'just now'; if (s < 3600) return Math.floor(s / 60) + ' min ago';
      if (s < 86400) return Math.floor(s / 3600) + ' h ago'; return Math.floor(s / 86400) + ' d ago';
    };
    const csrf = () => { const m = $('meta[name="csrf-token"]'); return m ? m.content : ''; };
    const post = (url, body) => fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() }, body: JSON.stringify(body || {}), credentials: 'same-origin' });
    function paint() { if (!badge) return; badge.textContent = unread > 9 ? '9+' : unread; badge.hidden = unread <= 0; bell.classList.toggle('has', unread > 0); bell.setAttribute('aria-label', unread ? `Notifications, ${unread} new` : 'Notifications'); }
    function build() {
      const bar = $('.app-topbar'); if (!bar || bell) return;
      bell = el('button', 'ui-bell', '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9a6 6 0 1 1 12 0c0 6 2.5 7.5 2.5 7.5h-17S6 15 6 9z"/><path d="M10 20a2 2 0 0 0 4 0"/></svg><i class="ui-bell-n" hidden></i>');
      bell.type = 'button'; badge = $('.ui-bell-n', bell); bar.appendChild(bell); paint();
      bell.addEventListener('click', toggle);
    }
    function closePanel() { if (!panel) return; panel.remove(); panel = null; document.removeEventListener('mousedown', away, true); document.removeEventListener('keydown', esc2, true); bell.setAttribute('aria-expanded', 'false'); }
    const away = (e) => { if (panel && !panel.contains(e.target) && !bell.contains(e.target)) closePanel(); };
    const esc2 = (e) => { if (e.key === 'Escape') closePanel(); };
    async function toggle() {
      if (panel) { closePanel(); return; }
      panel = el('div', 'ui-np'); panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', 'Notifications');
      panel.innerHTML = '<div class="ui-np-head"><b>Notifications</b><span><button type="button" class="ui-np-link" data-a="read">Mark all read</button><button type="button" class="ui-np-link" data-a="clear">Clear</button></span></div><div class="ui-np-list"><p class="ui-np-empty">Loading…</p></div>';
      document.body.appendChild(panel); bell.setAttribute('aria-expanded', 'true');
      document.addEventListener('mousedown', away, true); document.addEventListener('keydown', esc2, true);
      const list = $('.ui-np-list', panel);
      panel.addEventListener('click', async (e) => {
        const a = e.target.closest('[data-a]');
        if (a && a.dataset.a === 'read') { await post('/notifications/read'); unread = 0; paint(); list.querySelectorAll('.unread').forEach((x) => x.classList.remove('unread')); }
        if (a && a.dataset.a === 'clear') { if (!(await UI.confirm('Remove all notifications?', { ok: 'Remove', danger: true }))) return; await post('/notifications/clear'); unread = 0; paint(); list.innerHTML = '<p class="ui-np-empty">Nothing yet. New classes, quizzes and receipts will show up here.</p>'; }
        const it = e.target.closest('.ui-np-item'); if (it && it.dataset.url) { post('/notifications/read', { id: +it.dataset.id }); location.href = it.dataset.url; }
      });
      try {
        const r = await fetch('/notifications', { credentials: 'same-origin' }), j = await r.json();
        if (!panel) return;
        list.innerHTML = j.items.length ? j.items.map((n) => `<button type="button" class="ui-np-item${n.unread ? ' unread' : ''}" data-id="${n.id}" data-url="${esc(n.url)}"><span class="ui-np-ico">${KIND[n.kind] || KIND.info}</span><span class="ui-np-tx"><b>${esc(n.title)}</b>${n.body ? `<small>${esc(n.body)}</small>` : ''}<em>${ago(n.at)}</em></span></button>`).join('')
          : '<p class="ui-np-empty">Nothing yet. New classes, quizzes and receipts will show up here.</p>';
        if (unread) { await post('/notifications/read'); unread = 0; paint(); }       // opening the bell counts as seeing them (the blue dots stay for this visit)
      } catch (err) { if (panel) list.innerHTML = '<p class="ui-np-empty">Could not load. Check your connection.</p>'; }
    }
    build(); if (!bell) window.addEventListener('load', build);
  }
})();
