/* Offline (in-person) classes.
   - Teacher: class type switch in the schedule forms, and the roll call (点名) panel.
   - Student: the check-in box where the roll call code is typed.
   Loaded on both dashboards; each part only runs if its elements are on the page. */
(function () {
  'use strict';

  // the script tag sits in the middle of the page, so wait until every modal below it exists
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  function init() {

  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const $ = (id) => document.getElementById(id);
  const toast = (msg, type) => { if (typeof showToast === 'function') showToast(msg, type); };

  async function post(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify(body || {}),
    });
    let data = {};
    try { data = await res.json(); } catch (e) { /* not json */ }
    return data;
  }

  /* ───────── class type switch (teacher forms) ───────── */
  function makeSwitch(segId, hiddenId, onlineId, offlineId) {
    const seg = $(segId), hidden = $(hiddenId), online = $(onlineId), offline = $(offlineId);
    if (!seg || !hidden) return null;

    function apply(mode) {
      const off = mode === 'offline';
      hidden.value = off ? 'offline' : 'online';
      seg.querySelectorAll('.seg-btn').forEach((b) => b.classList.toggle('on', b.dataset.mode === hidden.value));
      if (online) online.hidden = off;
      if (offline) offline.hidden = !off;
    }
    seg.addEventListener('click', (e) => {
      const b = e.target.closest('.seg-btn');
      if (b) apply(b.dataset.mode);
    });
    return apply;
  }

  const applyCreate = makeSwitch('modeSeg', 'schedMode', 'onlineFields', 'offlineFields');
  const applyEdit = makeSwitch('editModeSeg', 'editMode', 'editOnlineFields', 'editOfflineFields');

  // a form reset (after a class is created) should put the switch back to Online
  const createForm = $('scheduleForm');
  if (createForm && applyCreate) createForm.addEventListener('reset', () => setTimeout(() => applyCreate('online'), 0));

  function cardMode(card, data) {
    // keep the card in step with what the server saved after an edit
    const offline = data.mode === 'offline';
    const time = card.querySelector('.sc-time');
    if (time) {
      time.querySelector('.sc-mode')?.remove();
      if (offline) {
        const pill = document.createElement('span');
        pill.className = 'sc-mode offline';
        pill.textContent = 'Offline';
        time.append(' ', pill);
      }
    }
    card.querySelectorAll('.sc-link').forEach((el) => el.remove());
    const anchor = card.querySelector('.sc-desc') || card.querySelector('.sc-head');
    const row = document.createElement('div');
    if (offline) {
      row.className = 'sc-link sc-loc';
      row.append('📍 ');
      const span = document.createElement('span');
      span.className = 'sc-loc-text';
      span.textContent = data.location || 'Offline class';
      row.append(span);
    } else if (data.meet_link) {
      row.className = 'sc-link';
      row.append('🔗 ');
      const a = document.createElement('a');
      a.href = data.meet_link; a.target = '_blank'; a.rel = 'noopener'; a.textContent = data.meet_link;
      row.append(a);
    }
    if (row.className) anchor.after(row);
    const joined = card.querySelector('.sc-joined');
    if (joined) joined.textContent = joined.textContent.replace(/(joined|present)\s*$/, offline ? 'present' : 'joined');
    card.querySelectorAll('.edit-sc-btn, .dup-sc-btn').forEach((b) => {
      b.dataset.mode = data.mode || 'online';
      b.dataset.location = data.location || '';
    });
  }

  window.OffClass = {
    setCreate(mode, location) {
      if (applyCreate) applyCreate(mode || 'online');
      const loc = $('schedLocation');
      if (loc) loc.value = location || '';
    },
    setEdit(mode, location) {
      if (applyEdit) applyEdit(mode || 'online');
      const loc = $('editLocation');
      if (loc) loc.value = location || '';
    },
    afterEdit: cardMode,
  };

  /* ───────── teacher: roll call panel ───────── */
  const rc = $('rcModal');
  if (rc) {
    let sid = null, timer = null, poll = null, secondsLeft = 0;

    const els = {
      title: $('rcTitle'), closedBox: $('rcClosedBox'), openBox: $('rcOpenBox'), code: $('rcCode'),
      timer: $('rcTimer'), list: $('rcList'), count: $('rcCount'),
    };

    function fmt(sec) {
      const m = Math.floor(sec / 60), s = sec % 60;
      return m + ':' + String(s).padStart(2, '0');
    }

    function tick() {
      if (secondsLeft <= 0) { els.timer.textContent = 'Closed'; return; }
      secondsLeft -= 1;
      els.timer.textContent = 'Open for ' + fmt(secondsLeft);
      if (secondsLeft <= 0) refresh();
    }

    function render(state) {
      if (!state || !state.ok) return;
      els.title.textContent = state.title + (state.location ? ' · ' + state.location : '');
      els.closedBox.hidden = state.open;
      els.openBox.hidden = !state.open;
      if (state.open) {
        els.code.textContent = state.code;
        secondsLeft = state.seconds_left;
        els.timer.textContent = 'Open for ' + fmt(secondsLeft);
      }
      els.count.textContent = state.present_count + ' of ' + state.students.length + ' present';
      els.list.textContent = '';
      state.students.forEach((s) => {
        const row = document.createElement('button');
        row.type = 'button';
        row.className = 'rc-row' + (s.present ? ' on' : '');
        row.dataset.id = s.id;
        row.setAttribute('aria-pressed', s.present ? 'true' : 'false');
        const name = document.createElement('span');
        name.className = 'rc-name';
        name.textContent = s.name;
        const mark = document.createElement('span');
        mark.className = 'rc-mark';
        mark.textContent = s.present ? 'Present' : 'Not yet';
        row.append(name, mark);
        els.list.append(row);
      });
      if (!state.students.length) {
        const empty = document.createElement('div');
        empty.className = 'rc-empty';
        empty.textContent = 'No students are invited to this class.';
        els.list.append(empty);
      }
    }

    async function refresh() {
      if (!sid) return;
      try {
        const res = await fetch('/teacher/schedule/' + sid + '/rollcall', { credentials: 'same-origin' });
        render(await res.json());
      } catch (e) { /* offline for a moment, the next poll will retry */ }
    }

    function openModal(btn) {
      sid = btn.dataset.id;
      els.title.textContent = btn.dataset.title || '';
      els.list.textContent = '';
      els.closedBox.hidden = false; els.openBox.hidden = true;
      rc.classList.remove('hidden');
      refresh();
      timer = setInterval(tick, 1000);
      poll = setInterval(refresh, 4000);
    }

    function closeModal() {
      rc.classList.add('hidden');
      clearInterval(timer); clearInterval(poll);
      sid = null;
    }

    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.rollcall-btn');
      if (btn) openModal(btn);
    });
    $('rcClose').addEventListener('click', closeModal);
    rc.addEventListener('click', (e) => { if (e.target === rc) closeModal(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !rc.classList.contains('hidden')) closeModal(); });

    $('rcOpen').addEventListener('click', async () => {
      render(await post('/teacher/schedule/' + sid + '/rollcall/open', { minutes: parseInt($('rcMinutes').value, 10) }));
    });
    $('rcStop').addEventListener('click', async () => {
      render(await post('/teacher/schedule/' + sid + '/rollcall/close'));
    });
    els.list.addEventListener('click', async (e) => {
      const row = e.target.closest('.rc-row');
      if (!row) return;
      const present = !row.classList.contains('on');
      const state = await post('/teacher/schedule/' + sid + '/rollcall/mark', { student_id: parseInt(row.dataset.id, 10), present });
      if (state && state.ok) render(state); else toast((state && state.msg) || 'Could not update', 'err');
    });
  }

  /* ───────── student: check-in box ───────── */
  const cs = $('rcsModal');
  if (cs) {
    const input = $('rcsCode'), msg = $('rcsMsg'), submit = $('rcsSubmit');
    let sid = null;

    function open(btn) {
      sid = btn.dataset.id;
      $('rcsTitle').textContent = btn.dataset.title || '';
      input.value = ''; msg.textContent = ''; msg.className = 'rc-msg';
      submit.disabled = false;
      cs.classList.remove('hidden');
      setTimeout(() => input.focus(), 60);
    }
    function close() { cs.classList.add('hidden'); sid = null; }

    async function send() {
      const code = input.value.trim();
      if (code.length !== 4) { msg.textContent = 'Enter the 4-digit code.'; msg.className = 'rc-msg err'; return; }
      submit.disabled = true;
      const data = await post('/schedule/' + sid + '/rollcall', { code });
      if (data.ok) {
        msg.textContent = data.msg; msg.className = 'rc-msg ok';
        toast(data.msg);
        setTimeout(() => window.location.reload(), 900);
      } else {
        msg.textContent = data.msg || 'Could not check in. Try again.'; msg.className = 'rc-msg err';
        submit.disabled = false;
        input.select();
      }
    }

    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.rollcall-checkin-btn');
      if (btn) open(btn);
    });
    $('rcsClose').addEventListener('click', close);
    cs.addEventListener('click', (e) => { if (e.target === cs) close(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !cs.classList.contains('hidden')) close(); });
    input.addEventListener('input', () => { input.value = input.value.replace(/\D/g, '').slice(0, 4); });
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); send(); } });
    submit.addEventListener('click', send);
  }
  }
})();
