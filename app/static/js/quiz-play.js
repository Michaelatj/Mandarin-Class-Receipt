/* quiz-play.js - the student side of a quiz.
   One question at a time. Each answer is checked on the server the moment the
   student presses "Check answer", and the whole attempt is graded again on the
   server when it is submitted. Relies on showToast() and _CSRF from base.html. */
(function () {
  const root = document.querySelector('.qz-shell');
  if (!root || root.dataset.page !== 'play') return;
  const box = document.getElementById('qz-play');
  const T = (s) => (window.I18N ? window.I18N.t(s) : s);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const S = {
    attemptId: null, quiz: null, i: 0,
    answers: {},      // qid -> { value, usedMeaning, answeredAtMs, checking, checked, correct }
    reorder: {},      // qid -> chunk ids in the order the student placed them
    hint: {},         // qid -> meaning currently visible
    usedHint: {},     // qid -> meaning was shown before the answer was checked
    order: [],        // qids in the order they were checked
    streak: 0, best: 0, startedAt: 0, timerId: null, finished: false,
  };

  /* ---------------- helpers ---------------- */
  async function api(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': _CSRF, 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify(body || {}),
    });
    let data = {};
    try { data = await res.json(); } catch (e) { /* not JSON */ }
    return { ok: res.ok && data.ok !== false, status: res.status, data };
  }
  function paint(html) {
    box.innerHTML = html;
    if (window.I18N) window.I18N.apply(box);
  }
  const cur = () => S.quiz.questions[S.i];
  const attemptUrl = (tail) => root.dataset.attemptBase + S.attemptId + '/' + tail;

  /* ---------------- small sound + particle effects ---------------- */
  let audio = null;
  function tone(freq, dur, type, delay) {
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      const t0 = audio.currentTime + (delay || 0);
      const osc = audio.createOscillator();
      const gain = audio.createGain();
      osc.type = type || 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, t0);
      gain.gain.exponentialRampToValueAtTime(0.18, t0 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
      osc.connect(gain).connect(audio.destination);
      osc.start(t0);
      osc.stop(t0 + dur + 0.05);
    } catch (e) { /* sound is optional */ }
  }
  const soundRight = () => { tone(660, 0.12, 'triangle'); tone(880, 0.18, 'triangle', 0.1); };
  const soundWrong = () => { tone(180, 0.28, 'sawtooth'); };
  const soundStreak = () => { [660, 784, 988, 1175].forEach((f, k) => tone(f, 0.14, 'triangle', k * 0.07)); };

  function burst(el, big) {
    const r = el.getBoundingClientRect();
    const wrap = document.createElement('div');
    wrap.className = 'qz-burst';
    wrap.style.left = (r.left + r.width / 2) + 'px';
    wrap.style.top = (r.top + r.height / 2) + 'px';
    const glyphs = ['✦', '★', '✧'];
    const n = big ? 22 : 12;
    for (let k = 0; k < n; k++) {
      const p = document.createElement('span');
      p.className = 'qz-particle';
      p.textContent = glyphs[k % glyphs.length];
      const angle = (Math.PI * 2 * k) / n;
      const dist = (big ? 110 : 70) * (0.6 + Math.random() * 0.6);
      p.style.setProperty('--dx', Math.cos(angle) * dist + 'px');
      p.style.setProperty('--dy', Math.sin(angle) * dist + 'px');
      p.style.setProperty('--rot', (Math.random() * 360 - 180) + 'deg');
      p.style.color = k % 2 ? 'var(--gold)' : 'var(--green)';
      wrap.appendChild(p);
    }
    document.body.appendChild(wrap);
    setTimeout(() => wrap.remove(), 1000);
  }
  function sadFx(el) {
    const r = el.getBoundingClientRect();
    const s = document.createElement('div');
    s.className = 'qz-sad';
    s.textContent = '✕';
    s.style.left = (r.left + r.width / 2) + 'px';
    s.style.top = (r.top + r.height / 2) + 'px';
    s.style.color = 'var(--red)';
    document.body.appendChild(s);
    setTimeout(() => s.remove(), 900);
  }

  /* ---------------- start ---------------- */
  async function begin() {
    const btn = document.getElementById('qz-begin');
    if (btn) btn.disabled = true;
    try {
      const res = await api(root.dataset.startUrl, {});
      if (!res.ok) {
        showToast(res.data.msg || 'Could not start the quiz', 'err');
        if (btn) btn.disabled = false;
        return;
      }
      S.attemptId = res.data.attemptId;
      S.quiz = res.data.quiz;
      S.startedAt = Date.now();
      if (S.quiz.timeLimitSeconds > 0) startTimer();
      render();
    } catch (e) {
      showToast('Network error. Please try again.', 'err');
      if (btn) btn.disabled = false;
    }
  }

  /* ---------------- timer (one budget for the whole quiz) ---------------- */
  function startTimer() {
    const total = S.quiz.timeLimitSeconds * 1000;
    S.timerId = setInterval(() => {
      const left = Math.max(0, total - (Date.now() - S.startedAt));
      const fill = document.getElementById('qz-timer-fill');
      const label = document.getElementById('qz-timer-text');
      if (fill) {
        fill.style.width = (left / total * 100) + '%';
        fill.classList.toggle('low', left / total < 0.2);
      }
      if (label) {
        const sec = Math.ceil(left / 1000);
        label.textContent = Math.floor(sec / 60) + ':' + String(sec % 60).padStart(2, '0');
      }
      if (left <= 0) {
        clearInterval(S.timerId);
        showToast("Time is up. Submitting your answers.");
        submit(true);
      }
    }, 250);
  }

  /* ---------------- rendering ---------------- */
  function hasHint(q) { return !!(q.questionMeaning || (q.optionMeanings && q.optionMeanings.length)); }

  function stateOf(q) {
    const a = S.answers[q.id];
    if (a && a.checked) return a.correct === true ? 'right' : a.correct === false ? 'wrong' : 'done';
    if (q.type === 'sentence_reorder') return (S.reorder[q.id] || []).length ? 'pending' : '';
    return a && (Array.isArray(a.value) ? a.value.length > 0 : a.value != null) ? 'pending' : '';
  }

  function ready(q) {
    if (q.type === 'sentence_reorder') return (S.reorder[q.id] || []).length === q.chunks.length;
    const a = S.answers[q.id];
    return !!(a && (Array.isArray(a.value) ? a.value.length > 0 : a.value != null));
  }

  function bodyHtml(q, a, locked, showHint) {
    let body = '';
    if (q.type === 'type_answer') {
      const verdict = a.checked ? (a.correct === true ? 'right' : a.correct === false ? 'wrong' : '') : '';
      body = `<input type="text" class="qz-typed ${verdict}" data-a="typed" data-q="${q.id}" value="${esc(typeof a.value === 'string' ? a.value : '')}" placeholder="${T('Type your answer')}" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" ${locked ? 'disabled' : ''} data-no-i18n>`;
    } else if (q.type === 'sentence_reorder') {
      const placed = S.reorder[q.id] || [];
      const chunkById = {};
      q.chunks.forEach((c) => { chunkById[c.id] = c; });
      const verdict = a.checked ? (a.correct === true ? 'right' : a.correct === false ? 'wrong' : '') : '';
      const assembled = placed.length
        ? placed.map((id) => `<button type="button" class="qz-chip ${locked ? 'locked' : ''}" data-no-i18n data-a="unplace" data-q="${q.id}" data-id="${id}">${esc(chunkById[id].text)}</button>`).join('')
        : `<span class="qz-placeholder">${T('Tap the pieces below to build the sentence.')}</span>`;
      const pool = q.chunks.filter((c) => !placed.includes(c.id))
        .map((c) => `<button type="button" class="qz-chip ${locked ? 'locked' : ''}" data-no-i18n data-a="place" data-q="${q.id}" data-id="${c.id}">${esc(c.text)}</button>`).join('');
      body = `
        <div class="qz-assembled ${verdict} ${a.checking ? 'checking' : ''}" id="qz-target">${assembled}</div>
        <div class="qz-pool">${pool}</div>
        ${locked || !placed.length ? '' : `<button type="button" class="qz-link" data-a="reset" data-q="${q.id}">${T('Start over')}</button>`}`;
    } else {
      const multi = q.type === 'multiple_select';
      body = (multi ? `<div class="qz-multi-hint">${T('Select all that apply')}</div>` : '') + '<div class="qz-options">' + q.options.map((text, idx) => {
        const value = q.optionValues[idx];
        const chosen = multi ? (Array.isArray(a.value) && a.value.includes(value)) : a.value === value;
        let cls = 'qz-option';
        if (chosen && a.checked) cls += a.correct === true ? ' right' : a.correct === false ? ' wrong' : ' selected';
        else if (chosen) cls += a.checking ? ' selected checking' : ' selected';
        if (locked) cls += ' locked';
        const mark = chosen && a.checked ? (a.correct === true ? '<span class="qz-mark" style="color:var(--green)">✓</span>' : a.correct === false ? '<span class="qz-mark" style="color:var(--red)">✕</span>' : '') : '';
        const meaning = showHint && q.optionMeanings && q.optionMeanings[idx]
          ? `<span class="qz-option-meaning">${esc(q.optionMeanings[idx])}</span>` : '';
        return `<div class="${cls}" data-a="opt" data-q="${q.id}" data-i="${idx}" role="button" tabindex="0"><span class="${multi ? 'qz-box' : 'qz-dot'}"></span><span data-no-i18n>${esc(text)}${meaning}</span>${mark}</div>`;
      }).join('') + '</div>';
    }

    return (q.audio ? `<button type="button" class="btn bgh qz-btn-sm qz-audio" data-a="qaudio" data-q="${q.id}">🔊 ${T('Listen')}</button>` : '') + body;
  }

  function render() {
    if (S.quiz.story) { renderStory(); return; }
    const quiz = S.quiz, n = quiz.questions.length, q = cur();
    const a = S.answers[q.id] || {};
    const locked = !!(a.checked || a.checking);
    const showHint = !!S.hint[q.id];

    const nav = quiz.questions.map((x, idx) => {
      const st = stateOf(x);
      const cls = [idx === S.i ? 'current' : '', st === 'right' ? 'right' : st === 'wrong' ? 'wrong' : st === 'pending' ? 'pending' : ''].join(' ').trim();
      return `<button type="button" class="${cls}" data-a="jump" data-i="${idx}" aria-label="${T('Question')} ${idx + 1}">${idx + 1}</button>`;
    }).join('');

    const checkedCount = quiz.questions.filter((x) => (S.answers[x.id] || {}).checked).length;

    const body = bodyHtml(q, a, locked, showHint);

    let verdictLine = '';
    if (a.checked) {
      verdictLine = a.correct === true
        ? `<p style="color:var(--green);font-weight:600;margin:12px 0 0">${T('Correct!')}</p>`
        : a.correct === false
          ? `<p style="color:var(--red);font-weight:600;margin:12px 0 0">${T('Not quite.')}</p>`
          : `<p style="color:var(--text3);margin:12px 0 0">${T('Answer saved. The score appears at the end.')}</p>`;
    }

    const isLast = S.i === n - 1;
    let primary;
    if (!a.checked) {
      primary = `<button type="button" class="btn qz-btn-gold" data-a="check" ${ready(q) && !a.checking ? '' : 'disabled'}>${T('Check answer')}</button>`;
    } else if (!isLast) {
      primary = `<button type="button" class="btn qz-btn-gold" data-a="next">${T('Next')}</button>`;
    } else {
      primary = `<button type="button" class="btn qz-btn-gold" data-a="finish">${T('Finish quiz')}</button>`;
    }

    const timer = quiz.timeLimitSeconds > 0
      ? `<div class="qz-timer-row"><span>${T('Time left')}</span><span id="qz-timer-text"></span></div>
         <div class="qz-timer-track"><div class="qz-timer-fill" id="qz-timer-fill"></div></div>` : '';

    paint(`
      <div class="qz-progress"><div style="width:${Math.round(checkedCount / n * 100)}%"></div></div>
      ${timer}
      <div class="qz-qnav">${nav}</div>
      ${S.streak >= 2 ? `<div class="qz-streak">${S.streak} ${T('in a row')}</div>` : ''}
      <div class="qz-qblock">
        <div class="qz-qhead">
          <span class="qz-qindex">${T('Question')} ${S.i + 1} / ${n}</span>
          ${hasHint(q) ? `<button type="button" class="qz-lamp ${showHint ? 'lit' : ''}" data-a="lamp" title="${T('Show the meaning (halves the points for this question)')}" aria-label="${T('Show the meaning (halves the points for this question)')}">💡</button>` : ''}
        </div>
        <div class="qz-qtext" data-no-i18n>${esc(q.question)}</div>
        ${showHint && q.questionMeaning ? `<div class="qz-meaning" data-no-i18n>${esc(q.questionMeaning)}</div>` : ''}
        ${body}
        ${verdictLine}
      </div>
      <div class="qz-nav">
        <button type="button" class="btn bgh" data-a="back" ${S.i === 0 ? 'disabled' : ''}>${T('Back')}</button>
        <div class="qz-nav-right">${primary}</div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:12px">
        <button type="button" class="qz-quit" data-a="quit">${T('Quit quiz')}</button>
        <button type="button" class="qz-link" data-a="submit-now">${T('Submit now')}</button>
      </div>`);
  }

  /* ---------------- story mode: one page, story on top, every question below ---------------- */
  function speak(text) {
    if (!('speechSynthesis' in window)) { showToast('This browser cannot read aloud. Try Chrome or Safari.', 'err'); return; }
    const voices = window.speechSynthesis.getVoices() || [];
    const zh = voices.filter((x) => /^zh/i.test(x.lang) || /chinese|mandarin|中文|普通话/i.test(x.name));
    if (voices.length && !zh.length) { showToast('No Chinese voice on this device. Install one in Settings > Text-to-speech.', 'err'); return; }
    const u = new SpeechSynthesisUtterance(text);
    u.lang = 'zh-CN'; u.rate = 0.85;
    if (zh.length) u.voice = zh.find((x) => /zh[-_]cn/i.test(x.lang)) || zh[0];
    u.onerror = () => showToast('Could not play the sound. Check the volume and silent mode.', 'err');
    try { window.speechSynthesis.cancel(); } catch (e) {}
    setTimeout(() => { try { window.speechSynthesis.speak(u); } catch (e) { showToast('Could not play the sound.', 'err'); } }, 60);
  }

  function renderStory() {
    const quiz = S.quiz, st = quiz.story, n = quiz.questions.length;
    const answered = quiz.questions.filter(ready).length;
    const timer = quiz.timeLimitSeconds > 0
      ? `<div class="qz-timer-row"><span>${T('Time left')}</span><span id="qz-timer-text"></span></div>
         <div class="qz-timer-track"><div class="qz-timer-fill" id="qz-timer-fill"></div></div>` : '';
    const paras = String(st.text).split(/\n+/).map((p) => `<p>${esc(p)}</p>`).join('');
    const pinyin = st.pinyin ? String(st.pinyin).split(/\n+/).map((p) => `<p>${esc(p)}</p>`).join('') : '';
    const meaning = st.meaning ? String(st.meaning).split(/\n+/).map((p) => `<p>${esc(p)}</p>`).join('') : '';
    const block = (q, idx) => {
      const a = S.answers[q.id] || {};
      return `<div class="qz-qblock qz-story-q ${ready(q) ? 'filled' : ''}" id="sq-${idx}">
        <div class="qz-qhead"><span class="qz-qindex">${T('Question')} ${idx + 1} / ${n}</span></div>
        <div class="qz-qtext" data-no-i18n>${esc(q.question)}</div>
        ${bodyHtml(q, a, false, false)}
      </div>`;
    };
    // questions about the story come first; the others (if the teacher made any) sit under their own heading
    const flagged = quiz.questions.some((q) => q.aboutStory);
    const about = (q) => !flagged || q.aboutStory;
    const aboutHtml = quiz.questions.map((q, i) => (about(q) ? block(q, i) : '')).join('');
    const otherHtml = quiz.questions.map((q, i) => (about(q) ? '' : block(q, i))).join('');
    const qs = aboutHtml + (otherHtml ? `<h3 class="qz-other-title">${T('Other questions')}<small>${T('These are not about the story')}</small></h3>` + otherHtml : '');
    paint(`
      ${timer}
      <div class="qz-story-card">
        ${st.title ? `<h2 class="qz-story-title" data-no-i18n>${esc(st.title)}</h2>` : ''}
        <div class="qz-story-text" data-no-i18n>${paras}</div>
        <div class="qz-story-tools">
          <button type="button" class="btn bgh qz-btn-sm" data-a="speak">🔊 ${T('Listen')}</button>
          ${pinyin ? `<button type="button" class="btn bgh qz-btn-sm ${S.showPinyin ? 'on' : ''}" data-a="toggle-pinyin">拼 ${T('Pinyin')}</button>` : ''}
          ${meaning ? `<button type="button" class="btn bgh qz-btn-sm ${S.showMeaning ? 'on' : ''}" data-a="toggle-meaning">🇮🇩 ${T('Meaning')}</button>` : ''}
        </div>
        ${S.showPinyin && pinyin ? `<div class="qz-story-sub" data-no-i18n>${pinyin}</div>` : ''}
        ${S.showMeaning && meaning ? `<div class="qz-story-sub qz-story-mean" data-no-i18n>${meaning}</div>` : ''}
      </div>
      <div class="qz-story-bar"><span>${answered} / ${n} ${T('answered')}</span><div class="qz-progress"><div style="width:${Math.round(answered / n * 100)}%"></div></div></div>
      ${qs}
      <div class="qz-story-submit">
        <button type="button" class="btn qz-btn-gold" data-a="story-submit">${T('Submit answers')}</button>
        <button type="button" class="qz-quit" data-a="quit">${T('Quit quiz')}</button>
      </div>`);
  }

  /* ---------------- actions ---------------- */
  async function check() {
    const q = cur();
    if (!ready(q)) return;
    const prev = S.answers[q.id] || {};
    if (prev.checked || prev.checking) return;
    const value = q.type === 'sentence_reorder' ? (S.reorder[q.id] || []).slice()
      : (Array.isArray(prev.value) ? prev.value.slice() : prev.value);
    const a = S.answers[q.id] = {
      value, usedMeaning: !!S.usedHint[q.id], answeredAtMs: Date.now() - S.startedAt,
      checking: true, checked: false, correct: null,
    };
    render();
    try {
      const res = await api(attemptUrl('answer'), { questionId: q.id, value });
      a.correct = res.ok ? res.data.correct : null;
      if (!res.ok) showToast('Could not check this answer', 'err');
    } catch (e) {
      a.correct = null;
      showToast('Could not check this answer', 'err');
    }
    a.checking = false;
    a.checked = true;
    if (!S.order.includes(q.id)) S.order.push(q.id);

    if (a.correct === true) {
      S.streak += 1;
      S.best = Math.max(S.best, S.streak);
    } else if (a.correct === false) {
      S.streak = 0;
    }
    render();

    const target = box.querySelector('.qz-option.right, .qz-option.wrong, #qz-target') || box;
    if (a.correct === true) {
      burst(target, S.streak >= 3);
      // a run of right answers plays the show of the student's own badge (bronze is small, dragon is rainbow)
      const milestone = S.streak === 3 || S.streak === 5 || (S.streak >= 8 && S.streak % 5 === 0);
      if (S.streak >= 3) { showToast(S.streak + ' in a row!'); }
      if (milestone && window.StreakOverlay && root.dataset.badge) window.StreakOverlay.burst(root.dataset.badge, S.streak >= 8);
      else if (S.streak >= 3) soundStreak(); else soundRight();
    } else if (a.correct === false) {
      sadFx(target);
      soundWrong();
    }
  }

  function go(idx) {
    if (idx < 0 || idx >= S.quiz.questions.length) return;
    S.i = idx;
    render();
  }

  function unanswered() {
    if (S.quiz.story) return S.quiz.questions.filter((q) => !ready(q)).length;
    return S.quiz.questions.filter((q) => !(S.answers[q.id] && S.answers[q.id].checked)).length;
  }

  async function submit(auto) {
    if (S.finished) return;
    if (!auto) {
      const left = unanswered();
      if (left > 0 && !(await UI.confirm(T('You still have unanswered questions. Submit anyway?'), { ok: 'Submit' }))) return;
    }
    S.finished = true;
    clearInterval(S.timerId);
    paint(`<div class="qz-start"><p>${T('Submitting your answers...')}</p></div>`);

    const answers = {};
    if (S.quiz.story) {                // story mode: nothing was checked one by one, so build the answers now
      S.order = [];
      S.quiz.questions.forEach((q) => {
        if (q.type === 'sentence_reorder' && ready(q)) S.answers[q.id] = { value: (S.reorder[q.id] || []).slice(), usedMeaning: false, answeredAtMs: Date.now() - S.startedAt };
        if (ready(q)) S.order.push(q.id);
      });
    }
    S.quiz.questions.forEach((q) => {
      const a = S.answers[q.id];
      if (!a || a.value == null) return;
      if (Array.isArray(a.value) && !a.value.length) return;
      if (q.type === 'sentence_reorder' && a.value.length !== q.chunks.length) return;
      answers[q.id] = { value: a.value, usedMeaning: !!a.usedMeaning, answeredAtMs: a.answeredAtMs };
    });
    try {
      const res = await api(attemptUrl('submit'), { answers, answerOrder: S.order });
      if (!res.ok) throw new Error(res.data.msg || 'submit failed');
      done(res.data);
    } catch (e) {
      S.finished = false;
      paint(`<div class="qz-start"><p>${T('Could not submit your answers.')}</p>
        <button type="button" class="btn qz-btn-gold" data-a="retry-submit">${T('Try again')}</button></div>`);
    }
  }

  function done(r) {
    const t = r.title;
    const top = t.name === '状元';
    const review = r.review.map((item, idx) => `
      <div class="qz-review-q ${item.correct ? 'ok' : 'bad'}">
        <div class="q" data-no-i18n>${idx + 1}. ${esc(item.question)}</div>
        <div class="a"><b>${T('Your answer')}:</b> <span data-no-i18n>${esc(item.given || '-')}</span></div>
        ${item.correct ? '' : `<div class="a"><b>${T('Correct answer')}:</b> <span data-no-i18n>${esc(item.correctAnswer)}</span></div>`}
        ${!item.correct && item.otherOrders && item.otherOrders.length ? `<div class="a"><b>${T('Also accepted')}:</b> <span data-no-i18n>${esc(item.otherOrders.join('  |  '))}</span></div>` : ''}
        ${item.explanation ? `<div class="why" data-no-i18n>${esc(item.explanation)}</div>` : ''}
      </div>`).join('');

    paint(`
      <div class="qz-done">
        <div class="qz-title-reveal ${top ? 'top' : ''}">
          <div class="qz-title-label">${T('Your title for this quiz')}</div>
          <div class="qz-title-icon">${esc(t.icon)}</div>
          <div class="qz-title-name">${esc(t.name)}</div>
          <div class="qz-title-sub"><span data-no-i18n>${esc(t.pinyin)}</span> · <span>${esc(t.meaning)}</span></div>
        </div>
        <div class="qz-scores">
          <div class="qz-score">
            <div class="qz-seal ${r.accuracyScore >= 60 ? 'good' : ''}"><b>${Math.round(r.accuracyScore)}</b><span>/ 100</span></div>
            <div class="qz-score-label">${T('Accuracy')}</div>
          </div>
          <div class="qz-score">
            <div class="qz-xp">${esc(r.xpScore)} XP</div>
            <div class="qz-score-label" style="margin-top:6px">${T('Game score')}</div>
          </div>
          <div class="qz-score">
            <div class="qz-seal"><b>${r.longestStreak}</b><span>${T('in a row')}</span></div>
            <div class="qz-score-label">${T('Best streak')}</div>
          </div>
        </div>
        <div class="qz-done-actions">
          <a class="btn bgh" href="${esc(root.dataset.home)}">${T('Back to quizzes')}</a>
          <a class="btn qz-btn-gold" href="">${T('Try again')}</a>
        </div>
        <div class="qz-review-wrap">
          <div class="qz-section-title">${T('Review')}</div>
          <div class="qz-review-list">${review}</div>
        </div>
      </div>`);
    if (r.accuracyScore >= 75) {
      const seal = box.querySelector('.qz-title-reveal');
      if (seal) { burst(seal, top); if (!r.badge || !window.StreakOverlay) soundStreak(); }
    }
    // the finish celebration belongs to the student's badge: bronze is small, dragon is wild
    if (r.badge && window.StreakOverlay && r.accuracyScore >= 60) {
      setTimeout(() => window.StreakOverlay.burst(r.badge.key, r.accuracyScore >= 90), 350);
    }
  }

  /* ---------------- events ---------------- */
  box.addEventListener('click', (e) => {
    if (e.target.closest('#qz-begin')) { begin(); return; }
    const el = e.target.closest('[data-a]');
    if (!el || !S.quiz) {
      return;
    }
    const act = el.dataset.a;
    if (act === 'qaudio') {
      const qa = S.quiz.questions.find((x) => x.id === el.dataset.q);
      if (qa && qa.audio) speak(qa.audio);
      return;
    }
    if (S.quiz.story) {
      if (act === 'speak') { speak(S.quiz.story.text); return; }
      if (act === 'toggle-pinyin') { S.showPinyin = !S.showPinyin; renderStory(); return; }
      if (act === 'toggle-meaning') { S.showMeaning = !S.showMeaning; renderStory(); return; }
      if (act === 'story-submit') { submit(false); return; }
    }
    const q = el.dataset.q ? S.quiz.questions.find((x) => x.id === el.dataset.q) : S.quiz.questions[S.i];
    if (!q) return;
    const a = S.answers[q.id] || {};
    const locked = !!(a.checked || a.checking);

    if (act === 'opt') {
      if (locked) return;
      const picked = q.optionValues[Number(el.dataset.i)];
      if (q.type === 'multiple_select') {
        const now = Array.isArray(a.value) ? a.value.slice() : [];
        const at = now.indexOf(picked);
        if (at >= 0) now.splice(at, 1); else now.push(picked);
        S.answers[q.id] = { value: now, usedMeaning: !!S.usedHint[q.id], answeredAtMs: Date.now() - S.startedAt };
      } else {
        S.answers[q.id] = { value: picked, usedMeaning: !!S.usedHint[q.id], answeredAtMs: Date.now() - S.startedAt };
      }
      render();
    } else if (act === 'place') {
      if (locked) return;
      S.reorder[q.id] = (S.reorder[q.id] || []).concat(Number(el.dataset.id));
      render();
    } else if (act === 'unplace') {
      if (locked) return;
      S.reorder[q.id] = (S.reorder[q.id] || []).filter((id) => id !== Number(el.dataset.id));
      render();
    } else if (act === 'reset') {
      if (locked) return;
      S.reorder[q.id] = [];
      render();
    } else if (act === 'lamp') {
      if (!S.hint[q.id] && !a.checked) {
        UI.confirm(T('Showing the meaning halves the points for this question. Show it anyway?'), { ok: 'Show it' }).then((y) => { if (y) { S.usedHint[q.id] = true; S.hint[q.id] = true; render(); } });
        return;
      }
      S.hint[q.id] = !S.hint[q.id];
      render();
    } else if (act === 'check') check();
    else if (act === 'next') go(S.i + 1);
    else if (act === 'back') go(S.i - 1);
    else if (act === 'jump') go(Number(el.dataset.i));
    else if (act === 'finish') submit(false);
    else if (act === 'submit-now') submit(false);
    else if (act === 'retry-submit') submit(true);
    else if (act === 'quit') {
      UI.confirm(T('Leave this quiz? Your answers will not be saved.'), { ok: 'Leave', danger: true }).then((y) => { if (y) { clearInterval(S.timerId); location.href = root.dataset.home; } });
    }
  });
  box.addEventListener('input', (e) => {
    const el = e.target.closest('[data-a="typed"]'); if (!el) return;
    const q = S.quiz.questions.find((x) => x.id === el.dataset.q); if (!q) return;
    const val = el.value;
    S.answers[q.id] = { value: val.trim() ? val : null, usedMeaning: !!S.usedHint[q.id], answeredAtMs: Date.now() - S.startedAt };
    const b = box.querySelector('[data-a="check"]'); if (b) b.disabled = !val.trim();
  });
  box.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.matches('[data-a="typed"]')) {
      e.preventDefault(); const b = box.querySelector('[data-a="check"]'); if (b && !b.disabled) b.click(); return;
    }
    if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('[data-a="opt"]')) {
      e.preventDefault();
      e.target.click();
    }
  });
})();
