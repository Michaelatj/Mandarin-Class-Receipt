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
    return a && a.value != null ? 'pending' : '';
  }

  function ready(q) {
    if (q.type === 'sentence_reorder') return (S.reorder[q.id] || []).length === q.chunks.length;
    const a = S.answers[q.id];
    return !!(a && a.value != null);
  }

  function render() {
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

    let body = '';
    if (q.type === 'sentence_reorder') {
      const placed = S.reorder[q.id] || [];
      const chunkById = {};
      q.chunks.forEach((c) => { chunkById[c.id] = c; });
      const verdict = a.checked ? (a.correct === true ? 'right' : a.correct === false ? 'wrong' : '') : '';
      const assembled = placed.length
        ? placed.map((id) => `<button type="button" class="qz-chip ${locked ? 'locked' : ''}" data-a="unplace" data-id="${id}">${esc(chunkById[id].text)}</button>`).join('')
        : `<span class="qz-placeholder">${T('Tap the pieces below to build the sentence.')}</span>`;
      const pool = q.chunks.filter((c) => !placed.includes(c.id))
        .map((c) => `<button type="button" class="qz-chip ${locked ? 'locked' : ''}" data-a="place" data-id="${c.id}">${esc(c.text)}</button>`).join('');
      body = `
        <div class="qz-assembled ${verdict} ${a.checking ? 'checking' : ''}" id="qz-target">${assembled}</div>
        <div class="qz-pool">${pool}</div>
        ${locked || !placed.length ? '' : `<button type="button" class="qz-link" data-a="reset">${T('Start over')}</button>`}`;
    } else {
      body = '<div class="qz-options">' + q.options.map((text, idx) => {
        const value = q.optionValues[idx];
        const chosen = a.value === value;
        let cls = 'qz-option';
        if (chosen && a.checked) cls += a.correct === true ? ' right' : a.correct === false ? ' wrong' : ' selected';
        else if (chosen) cls += a.checking ? ' selected checking' : ' selected';
        if (locked) cls += ' locked';
        const mark = chosen && a.checked ? (a.correct === true ? '<span class="qz-mark" style="color:var(--green)">✓</span>' : a.correct === false ? '<span class="qz-mark" style="color:var(--red)">✕</span>' : '') : '';
        const meaning = showHint && q.optionMeanings && q.optionMeanings[idx]
          ? `<span class="qz-option-meaning">${esc(q.optionMeanings[idx])}</span>` : '';
        return `<div class="${cls}" data-a="opt" data-i="${idx}" role="button" tabindex="0"><span class="qz-dot"></span><span>${esc(text)}${meaning}</span>${mark}</div>`;
      }).join('') + '</div>';
    }

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
        <div class="qz-qtext">${esc(q.question)}</div>
        ${showHint && q.questionMeaning ? `<div class="qz-meaning">${esc(q.questionMeaning)}</div>` : ''}
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

  /* ---------------- actions ---------------- */
  async function check() {
    const q = cur();
    if (!ready(q)) return;
    const prev = S.answers[q.id] || {};
    if (prev.checked || prev.checking) return;
    const value = q.type === 'sentence_reorder' ? (S.reorder[q.id] || []).slice() : prev.value;
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
      if (S.streak >= 3) { soundStreak(); showToast(S.streak + ' in a row!'); } else { soundRight(); }
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
    return S.quiz.questions.filter((q) => !(S.answers[q.id] && S.answers[q.id].checked)).length;
  }

  async function submit(auto) {
    if (S.finished) return;
    if (!auto) {
      const left = unanswered();
      if (left > 0 && !confirm(T('You still have unanswered questions. Submit anyway?'))) return;
    }
    S.finished = true;
    clearInterval(S.timerId);
    paint(`<div class="qz-start"><p>${T('Submitting your answers...')}</p></div>`);

    const answers = {};
    S.quiz.questions.forEach((q) => {
      const a = S.answers[q.id];
      if (!a || a.value == null) return;
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
        <div class="q">${idx + 1}. ${esc(item.question)}</div>
        <div class="a"><b>${T('Your answer')}:</b> ${esc(item.given || '-')}</div>
        ${item.correct ? '' : `<div class="a"><b>${T('Correct answer')}:</b> ${esc(item.correctAnswer)}</div>`}
        ${item.explanation ? `<div class="why">${esc(item.explanation)}</div>` : ''}
      </div>`).join('');

    paint(`
      <div class="qz-done">
        <div class="qz-title-reveal ${top ? 'top' : ''}">
          <div class="qz-title-label">${T('Your title for this quiz')}</div>
          <div class="qz-title-icon">${esc(t.icon)}</div>
          <div class="qz-title-name">${esc(t.name)}</div>
          <div class="qz-title-sub">${esc(t.pinyin)} · ${esc(t.meaning)}</div>
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
      if (seal) { burst(seal, top); soundStreak(); }
    }
  }

  /* ---------------- events ---------------- */
  box.addEventListener('click', (e) => {
    if (e.target.closest('#qz-begin')) { begin(); return; }
    const el = e.target.closest('[data-a]');
    if (!el || !S.quiz) {
      return;
    }
    const q = S.quiz.questions[S.i];
    const a = S.answers[q.id] || {};
    const locked = !!(a.checked || a.checking);
    const act = el.dataset.a;

    if (act === 'opt') {
      if (locked) return;
      S.answers[q.id] = { value: q.optionValues[Number(el.dataset.i)], usedMeaning: !!S.usedHint[q.id] };
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
        if (!confirm(T('Showing the meaning halves the points for this question. Show it anyway?'))) return;
        S.usedHint[q.id] = true;
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
      if (confirm(T('Leave this quiz? Your answers will not be saved.'))) {
        clearInterval(S.timerId);
        location.href = root.dataset.home;
      }
    }
  });
  box.addEventListener('keydown', (e) => {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('[data-a="opt"]')) {
      e.preventDefault();
      e.target.click();
    }
  });
})();
