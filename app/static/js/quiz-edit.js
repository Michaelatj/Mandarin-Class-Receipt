/* quiz-edit.js - the teacher's question editor.
   Every question can be changed: its text, the options and which ones are correct,
   the order of sentence chunks and any other word orders that are also correct.
   Saving sends the whole list; the server checks it again and re-grades finished results. */
(function () {
  const root = document.querySelector('.qz-shell');
  if (!root || root.dataset.page !== 'edit') return;

  const T = (s) => (window.I18N ? window.I18N.t(s) : s);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const list = document.getElementById('qe-list');
  const errBox = document.getElementById('qe-errors');
  const stats = JSON.parse(document.getElementById('qe-stats').textContent || '{}');
  const MAX_CHUNKS = 12;

  let seq = 0;
  const nid = () => 'n' + (++seq);
  let dirty = false;
  let builder = null;            // { cid, picked: [chunk keys] } while adding another correct order

  /* ---------------- model <-> server shape ---------------- */
  function blankOptions(n) { return Array.from({ length: n }, () => ({ k: nid(), text: '', meaning: '', correct: false })); }
  function blankChunks(n) { return Array.from({ length: n }, () => ({ k: nid(), text: '' })); }

  function fromServer(q) {
    const m = { cid: nid(), id: q.id, type: q.type, question: q.question || '', meaning: q.questionMeaning || '',
                explanation: q.explanation || '', points: q.points || 1, errors: [] };
    if (q.type === 'sentence_reorder') {
      m.chunks = q.chunks.map((t, i) => ({ k: 'c' + i, text: t }));
      m.alts = (q.altOrders || []).map((order) => order.map((i) => 'c' + i));
    } else {
      const right = new Set(q.type === 'multiple_select' ? q.answers : [q.answer]);
      m.options = q.options.map((t, i) => ({ k: nid(), text: t, meaning: q.optionMeanings ? (q.optionMeanings[i] || '') : '', correct: right.has(t) }));
    }
    return m;
  }
  function blankQuestion(type) {
    const m = { cid: nid(), id: null, type, question: '', meaning: '', explanation: '', points: 1, errors: [] };
    if (type === 'sentence_reorder') { m.chunks = blankChunks(4); m.alts = []; }
    else m.options = blankOptions(type === 'multiple_select' ? 5 : 4);
    return m;
  }
  function toServer(m) {
    const out = { type: m.type, question: m.question.trim(), points: Number(m.points) || 1 };
    if (m.id) out.id = m.id;
    if (m.meaning.trim()) out.questionMeaning = m.meaning.trim();
    if (m.explanation.trim()) out.explanation = m.explanation.trim();
    if (m.type === 'sentence_reorder') {
      out.chunks = m.chunks.map((c) => c.text.trim());
      const at = new Map(m.chunks.map((c, i) => [c.k, i]));
      out.altOrders = m.alts.filter((a) => a.length === m.chunks.length && a.every((k) => at.has(k))).map((a) => a.map((k) => at.get(k)));
    } else {
      out.options = m.options.map((o) => o.text.trim());
      if (m.options.some((o) => o.meaning.trim())) out.optionMeanings = m.options.map((o) => o.meaning.trim());
      if (m.type === 'multiple_select') out.answers = m.options.filter((o) => o.correct).map((o) => o.text.trim());
      else out.answer = (m.options.find((o) => o.correct) || { text: '' }).text.trim();
    }
    return out;
  }

  const Q = JSON.parse(document.getElementById('qe-data').textContent).map(fromServer);

  /* ---------------- checks before saving ---------------- */
  function problems(m) {
    const p = [];
    if (!m.question.trim()) p.push('Write the question text.');
    if (m.type === 'sentence_reorder') {
      if (m.chunks.length < 2 || m.chunks.length > MAX_CHUNKS) p.push('Use between 2 and 12 chunks.');
      if (m.chunks.some((c) => !c.text.trim())) p.push('Every chunk needs text.');
    } else {
      const texts = m.options.map((o) => o.text.trim());
      if (m.options.length < 2) p.push('Add at least 2 options.');
      if (texts.some((t) => !t)) p.push('Every option needs text.');
      if (new Set(texts).size !== texts.length) p.push('The options must all be different.');
      const right = m.options.filter((o) => o.correct).length;
      if (m.type === 'multiple_choice' && right !== 1) p.push('Mark exactly one correct option.');
      if (m.type === 'multiple_select') {
        if (right < 1) p.push('Mark at least one correct option.');
        if (right >= m.options.length) p.push('At least one option must be wrong.');
      }
    }
    return p;
  }

  /* ---------------- drawing ---------------- */
  const TYPES = [['multiple_choice', 'One correct answer'], ['multiple_select', 'Several correct answers'], ['sentence_reorder', 'Reorder the sentence']];
  const chunkText = (m, k) => (m.chunks.find((c) => c.k === k) || { text: '' }).text;

  function bodyHtml(m) {
    if (m.type === 'sentence_reorder') {
      const rows = m.chunks.map((c, i) => `
        <div class="qe-chunk" data-k="${c.k}">
          <span class="qe-idx">${i + 1}</span>
          <input type="text" data-f="ctext" value="${esc(c.text)}" placeholder="Chunk">
          <button type="button" class="qe-btn" data-a="chunk-up" title="Move up">↑</button>
          <button type="button" class="qe-btn" data-a="chunk-down" title="Move down">↓</button>
          <button type="button" class="qe-btn danger" data-a="rm-chunk" title="Remove">✕</button>
        </div>`).join('');
      const alts = m.alts.map((a, n) => `
        <div class="qe-alt"><span data-no-i18n>${esc(a.map((k) => chunkText(m, k)).join(' '))}</span>
          <button type="button" class="qe-btn danger" data-a="rm-alt" data-n="${n}" title="Remove">✕</button></div>`).join('');
      let build = `<button type="button" class="qe-link" data-a="add-alt">Add another correct order</button>`;
      if (builder && builder.cid === m.cid) {
        const pool = m.chunks.filter((c) => !builder.picked.includes(c.k))
          .map((c) => `<button type="button" class="qz-chip" data-no-i18n data-a="pick" data-k="${c.k}">${esc(c.text) || '…'}</button>`).join('');
        const done = builder.picked.map((k) => `<button type="button" class="qz-chip" data-no-i18n data-a="unpick" data-k="${k}">${esc(chunkText(m, k)) || '…'}</button>`).join('');
        build = `<div class="qe-builder">
          <div class="qe-sub">Tap the chunks in this other correct order</div>
          <div class="qz-assembled" style="margin-top:0">${done || '<span class="qz-placeholder">Tap the pieces below.</span>'}</div>
          <div class="qz-pool">${pool}</div>
          <div class="qz-actions-row" style="margin-top:10px">
            <button type="button" class="btn qz-btn-gold qz-btn-sm" data-a="save-alt">Add this order</button>
            <button type="button" class="btn bgh qz-btn-sm" data-a="cancel-alt">Cancel</button>
          </div></div>`;
      }
      return `<div class="qe-sub">Chunks in the correct order</div>${rows}
        <button type="button" class="qe-link" data-a="add-chunk">Add a chunk</button>
        <div class="qe-alts"><div class="qe-sub">Other correct orders (same meaning)</div>
          ${alts || '<div class="qz-hint-text">None yet. Add one if a different word order is also correct.</div>'}${build}</div>`;
    }
    const multi = m.type === 'multiple_select';
    const rows = m.options.map((o) => `
      <div class="qe-opt" data-k="${o.k}">
        <input type="${multi ? 'checkbox' : 'radio'}" name="ok-${m.cid}" data-f="correct" ${o.correct ? 'checked' : ''} aria-label="Correct answer">
        <input type="text" class="qe-opt-text" data-f="otext" value="${esc(o.text)}" placeholder="Option text">
        <input type="text" class="qe-opt-meaning" data-f="omeaning" value="${esc(o.meaning)}" placeholder="Meaning (optional)">
        <button type="button" class="qe-btn danger" data-a="rm-opt" title="Remove">✕</button>
      </div>`).join('');
    return `<div class="qe-sub">${multi ? 'Tick every correct option' : 'Mark the one correct option'}</div>${rows}
      <button type="button" class="qe-link" data-a="add-opt">Add an option</button>`;
  }

  function cardHtml(m, i) {
    const st = m.id ? stats[m.id] : null;
    const statLine = !m.id ? '' : (st && st.answered
      ? `Answered by ${st.answered}, ${Math.round(st.correct / st.answered * 100)}% correct` : 'Nobody has answered yet');
    return `
      <div class="qe-card ${m.errors.length ? 'invalid' : ''}" data-cid="${m.cid}">
        <div class="qe-head">
          <div class="qe-num">Question ${i + 1}</div>
          <select class="qe-type" data-f="type">${TYPES.map(([v, label]) => `<option value="${v}" ${m.type === v ? 'selected' : ''}>${label}</option>`).join('')}</select>
          <div class="qe-tools">
            <button type="button" class="qe-btn" data-a="q-up" title="Move up" ${i === 0 ? 'disabled' : ''}>↑</button>
            <button type="button" class="qe-btn" data-a="q-down" title="Move down" ${i === Q.length - 1 ? 'disabled' : ''}>↓</button>
            <button type="button" class="qe-btn danger" data-a="q-del" title="Delete question">✕</button>
          </div>
        </div>
        ${statLine ? `<div class="qe-stat">${statLine}</div>` : ''}
        <label>Question</label>
        <textarea data-f="question" rows="2">${esc(m.question)}</textarea>
        <div class="qz-row" style="margin-bottom:0">
          <div class="qz-field"><label>Meaning in English (optional)</label><input type="text" data-f="meaning" value="${esc(m.meaning)}"></div>
          <div class="qz-field" style="max-width:110px"><label>Points</label><input type="number" data-f="points" min="0.5" max="10" step="0.5" value="${esc(m.points)}"></div>
        </div>
        ${bodyHtml(m)}
        <label style="display:block;margin-top:10px">Explanation shown after the quiz (optional)</label>
        <input type="text" data-f="explanation" value="${esc(m.explanation)}">
        <div class="qe-error" ${m.errors.length ? '' : 'hidden'}>${m.errors.map((e) => `<div>${esc(e)}</div>`).join('')}</div>
      </div>`;
  }

  function render() {
    list.innerHTML = Q.map(cardHtml).join('') || '<div class="qz-hint-text">No questions yet. Add one below.</div>';
    if (window.I18N) window.I18N.apply(list);
  }
  const find = (el) => Q.find((m) => m.cid === (el.closest('.qe-card') || {}).dataset.cid);
  const touch = () => { dirty = true; };

  /* ---------------- typing and ticking (no redraw, so the cursor stays put) ---------------- */
  list.addEventListener('input', (e) => {
    const f = e.target.dataset.f; if (!f) return;
    const m = find(e.target); if (!m) return;
    touch();
    if (f === 'question') m.question = e.target.value;
    else if (f === 'meaning') m.meaning = e.target.value;
    else if (f === 'explanation') m.explanation = e.target.value;
    else if (f === 'points') m.points = e.target.value;
    else if (f === 'otext') m.options.find((o) => o.k === e.target.closest('.qe-opt').dataset.k).text = e.target.value;
    else if (f === 'omeaning') m.options.find((o) => o.k === e.target.closest('.qe-opt').dataset.k).meaning = e.target.value;
    else if (f === 'ctext') m.chunks.find((c) => c.k === e.target.closest('.qe-chunk').dataset.k).text = e.target.value;
  });
  list.addEventListener('change', (e) => {
    const f = e.target.dataset.f; if (!f) return;
    const m = find(e.target); if (!m) return;
    touch();
    if (f === 'correct') {
      const k = e.target.closest('.qe-opt').dataset.k;
      if (m.type === 'multiple_select') m.options.find((o) => o.k === k).correct = e.target.checked;
      else m.options.forEach((o) => { o.correct = o.k === k; });
    } else if (f === 'type') {
      if (!convert(m, e.target.value)) { render(); return; }
      render();
    }
  });

  function convert(m, to) {
    const optionBased = (t) => t !== 'sentence_reorder';
    if (optionBased(m.type) && optionBased(to)) {
      if (to === 'multiple_choice') {
        let seen = false;
        m.options.forEach((o) => { if (o.correct && !seen) seen = true; else o.correct = false; });
      }
      m.type = to;
      return true;
    }
    if (!confirm(T('Changing to this type clears the answer options. Continue?'))) return false;
    if (to === 'sentence_reorder') { delete m.options; m.chunks = blankChunks(4); m.alts = []; }
    else { delete m.chunks; delete m.alts; m.options = blankOptions(to === 'multiple_select' ? 5 : 4); }
    m.type = to;
    return true;
  }

  /* ---------------- buttons ---------------- */
  list.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-a]'); if (!btn) return;
    const m = find(btn); if (!m) return;
    const a = btn.dataset.a;
    const i = Q.indexOf(m);
    touch();

    if (a === 'q-up' && i > 0) { Q.splice(i - 1, 0, Q.splice(i, 1)[0]); }
    else if (a === 'q-down' && i < Q.length - 1) { Q.splice(i + 1, 0, Q.splice(i, 1)[0]); }
    else if (a === 'q-del') {
      if (!confirm(T('Delete this question?'))) return;
      Q.splice(i, 1);
    }
    else if (a === 'add-opt') { m.options.push({ k: nid(), text: '', meaning: '', correct: false }); }
    else if (a === 'rm-opt') { m.options = m.options.filter((o) => o.k !== btn.closest('.qe-opt').dataset.k); }
    else if (a === 'add-chunk') { if (m.chunks.length < MAX_CHUNKS) m.chunks.push({ k: nid(), text: '' }); }
    else if (a === 'rm-chunk') {
      const k = btn.closest('.qe-chunk').dataset.k;
      m.chunks = m.chunks.filter((c) => c.k !== k);
      m.alts = m.alts.filter((alt) => !alt.includes(k));       // an alternative that used this chunk no longer fits
      if (builder) builder = null;
    }
    else if (a === 'chunk-up' || a === 'chunk-down') {
      const at = m.chunks.findIndex((c) => c.k === btn.closest('.qe-chunk').dataset.k);
      const to = a === 'chunk-up' ? at - 1 : at + 1;
      if (to >= 0 && to < m.chunks.length) m.chunks.splice(to, 0, m.chunks.splice(at, 1)[0]);
    }
    else if (a === 'add-alt') { builder = { cid: m.cid, picked: [] }; }
    else if (a === 'pick') { builder.picked.push(btn.dataset.k); }
    else if (a === 'unpick') { builder.picked = builder.picked.filter((k) => k !== btn.dataset.k); }
    else if (a === 'cancel-alt') { builder = null; }
    else if (a === 'save-alt') {
      const same = (x, y) => x.length === y.length && x.every((v, n) => v === y[n]);
      const main = m.chunks.map((c) => c.k);
      if (builder.picked.length !== m.chunks.length) { showToast('Use every chunk once.', 'err'); return; }
      if (same(builder.picked, main) || m.alts.some((alt) => same(alt, builder.picked))) { showToast('That order is already there.', 'err'); return; }
      m.alts.push(builder.picked.slice());
      builder = null;
    }
    else if (a === 'rm-alt') { m.alts.splice(Number(btn.dataset.n), 1); }
    render();
  });

  document.getElementById('qe-add').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-add]'); if (!btn) return;
    Q.push(blankQuestion(btn.dataset.add));
    touch();
    render();
    const last = list.lastElementChild;
    if (last && last.scrollIntoView) last.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });

  /* ---------------- save ---------------- */
  let saving = false;
  async function save() {
    if (saving) return;
    errBox.hidden = true;
    let bad = null;
    Q.forEach((m) => { m.errors = problems(m); if (m.errors.length && !bad) bad = m; });
    if (!Q.length) {
      errBox.hidden = false; errBox.textContent = 'A quiz needs at least one question.';
      if (window.I18N) window.I18N.apply(errBox);
      return;
    }
    if (bad) {
      render();
      const el = list.querySelector(`[data-cid="${bad.cid}"]`);
      if (el && el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      showToast('Fix the questions marked in red first.', 'err');
      return;
    }
    saving = true;
    document.querySelectorAll('#qe-save, #qe-save2').forEach((b) => { b.disabled = true; });
    try {
      const res = await fetch(root.dataset.saveUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': _CSRF, 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ questions: Q.map(toServer) }),
      });
      let data = {};
      try { data = await res.json(); } catch (err) { /* not JSON */ }
      if (res.ok && data.ok) {
        dirty = false;
        showToast(data.regraded ? 'Saved. Finished results were graded again.' : 'Saved');
        setTimeout(() => location.replace(location.pathname), 700);
        return;
      }
      errBox.hidden = false;
      errBox.innerHTML = '';
      const head = document.createElement('div');
      head.textContent = data.msg || 'Something went wrong. Please try again.';
      errBox.appendChild(head);
      if (data.details && data.details.length) {
        const ul = document.createElement('ul');
        data.details.forEach((d) => { const li = document.createElement('li'); li.textContent = d; ul.appendChild(li); });
        errBox.appendChild(ul);
      }
      if (window.I18N) window.I18N.apply(errBox);
      errBox.scrollIntoView && errBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch (err) {
      showToast('Network error. Please try again.', 'err');
    } finally {
      saving = false;
      document.querySelectorAll('#qe-save, #qe-save2').forEach((b) => { b.disabled = false; });
    }
  }
  document.getElementById('qe-save').addEventListener('click', save);
  document.getElementById('qe-save2').addEventListener('click', save);
  window.addEventListener('beforeunload', (e) => { if (dirty) { e.preventDefault(); e.returnValue = ''; } });

  render();
})();
