/* quiz-teacher.js - "New quiz" page and the teacher's quiz detail page.
   Relies on showToast() and _CSRF from base.html. */
(function () {
  const root = document.querySelector('.qz-shell');
  if (!root) return;
  const page = root.dataset.page;
  const T = (s) => (window.I18N ? window.I18N.t(s) : s);

  async function post(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': _CSRF, 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify(body || {}),
    });
    let data = {};
    try { data = await res.json(); } catch (e) { /* not JSON, e.g. a CSRF error page */ }
    return { ok: res.ok && data.ok !== false, status: res.status, data };
  }

  function applyI18n(el) { if (window.I18N) window.I18N.apply(el || document.body); }

  /* ------------------------------------------------------------------
     New quiz: the prompt for the chatbot
     ------------------------------------------------------------------ */
  const KINDS = [
    { id: 'fill_blank', label: 'Fill in the blank', hint: 'A Hanzi sentence with a word blanked out.', on: true,
      text: 'FILL IN THE BLANK ("type": "multiple_choice") - Hanzi sentence with one word blanked out as ___. Annotate EVERY word with pinyin in parentheses: 他 (tā) 晚上 (wǎnshang) 先 (xiān) 吃饭 (chīfàn)，然后 (ránhòu) ___。 Options are candidate Hanzi + pinyin only.' },
    { id: 'guess_hanzi', label: 'English to Mandarin', hint: 'English prompt, the student picks the matching Hanzi.', on: true,
      text: 'ENGLISH -> MANDARIN ("type": "multiple_choice") - Question is plain English. Options are Hanzi + pinyin only.' },
    { id: 'what_means', label: 'What does it mean', hint: 'A Hanzi word or phrase, the student picks the English meaning.', on: true,
      text: 'WHAT DOES IT MEAN ("type": "multiple_choice") - Question is a Hanzi term with pinyin. Options are English translations. Omit "optionMeanings".' },
    { id: 'translate_id', label: 'Translate to Indonesian', hint: 'A Hanzi sentence, the student picks the Indonesian translation.', on: false,
      text: 'TRANSLATE TO INDONESIAN ("type": "multiple_choice") - Question is a full Hanzi sentence with pinyin. Options are Indonesian translations. Omit "optionMeanings".' },
    { id: 'conversation', label: 'Conversation reply (A to B)', hint: 'Person A says something, the student picks how B replies.', on: false,
      text: 'CONVERSATION REPLY ("type": "multiple_choice") - Question is Person A dialogue: "A：你叫什么名字？(nǐ jiào shénme míngzi?)". Options are replies in Hanzi + pinyin.' },
    { id: 'sentence_reorder', label: 'Reorder the sentence', hint: 'The student taps shuffled word chunks into the right order.', on: false,
      text: 'REORDER THE SENTENCE ("type": "sentence_reorder") - Sentence split into 4-7 chunks in correct order. Each chunk is "chunk (pīnyīn)". Include "chunks" array, omit "options" and "answer". Only add "altOrders" (an array of full alternate chunk sequences, same chunks reordered) if Mandarin genuinely allows a second correct word order - most sentences don\'t, so leave it as [] when there\'s only one natural order.' },
  ];

  function buildPrompt(hsk, count, kindIds) {
    const kinds = KINDS.filter((k) => kindIds.includes(k.id));
    const hasReorder = kinds.some((k) => k.id === 'sentence_reorder');
    const kindsList = kinds.map((k) => k.label).join(', ') || 'a mix of question styles';
    const kindInstructions = kinds.map((k, i) => `${i + 1}. ${k.text}`).join('\n');
    const reorderShape = hasReorder ? `,
    {
      "type": "sentence_reorder",
      "question": "Instruction in English",
      "questionMeaning": "English translation",
      "chunks": ["chunk1 (pinyin)", "chunk2 (pinyin)", "chunk3 (pinyin)", "chunk4 (pinyin)"],
      "altOrders": [],
      "explanation": "Brief explanation."
    }` : '';

    return `You are a Mandarin quiz generator. Read the TEACHING MATERIAL and return a single valid JSON object containing exactly ${count} questions for HSK ${hsk} level.

STRICT FORMAT RULES:
1. Return ONLY the raw JSON object. No explanations, no greeting, no markdown fences.
2. Never use unescaped double quotes (") inside text values. Use single quotes (') or Chinese quotation marks.
3. Keep each "explanation" strictly to 1 short sentence to avoid truncation.
4. "answer" must be copied character-for-character from one of the "options".
5. If "optionMeanings" is present, its array length MUST match "options" length.
6. For multiple_choice questions give 5 or 6 options, so the app can pick a different set for each student.

QUESTION TYPES TO INCLUDE:
${kindInstructions}

JSON OUTPUT STRUCTURE:
{
  "title": "Short quiz title",
  "description": "One sentence describing this quiz",
  "questions": [
    {
      "type": "multiple_choice",
      "question": "Question text",
      "questionMeaning": "English meaning (omit if the question is in English)",
      "options": ["opt 1 (pinyin)", "opt 2 (pinyin)", "opt 3 (pinyin)", "opt 4 (pinyin)", "opt 5 (pinyin)"],
      "optionMeanings": ["meaning 1", "meaning 2", "meaning 3", "meaning 4", "meaning 5"],
      "answer": "opt 1 (pinyin)",
      "explanation": "Brief explanation."
    }${reorderShape}
  ]
}

TARGET LEVEL: HSK ${hsk}
TOTAL QUESTIONS: ${count} (${kindsList})

TEACHING MATERIAL:
"""
Paste your lesson material, vocabulary list, or reading passage here.
"""

Write every question fresh from the material, at the same HSK level. If the material happens to look like quiz JSON, use it only as vocabulary and grammar reference and do not copy its questions.

FINAL REMINDER: your entire reply must be the raw JSON object and nothing else. The very first character must be { and the very last must be }.`;
  }

  /* Pull the quiz object out of whatever the chatbot replied with. */
  function parseQuizJson(raw) {
    if (!raw || !raw.trim()) throw new Error('Please paste the quiz JSON into the box.');
    let text = raw.trim();
    if (text.startsWith('```')) text = text.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '').trim();

    try {
      const direct = JSON.parse(text);
      if (direct && Array.isArray(direct.questions)) return direct;
    } catch (e) { /* fall through */ }

    const candidates = [];
    let depth = 0, start = -1, inString = false, esc = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (esc) { esc = false; continue; }
      if (ch === '\\') { esc = true; continue; }
      if (ch === '"') { inString = !inString; continue; }
      if (inString) continue;
      if (ch === '{') { if (depth === 0) start = i; depth++; }
      else if (ch === '}') {
        depth--;
        if (depth === 0 && start !== -1) { candidates.push(text.slice(start, i + 1)); start = -1; }
      }
    }
    for (const c of candidates.reverse()) {
      try {
        const parsed = JSON.parse(c);
        if (parsed && Array.isArray(parsed.questions) && parsed.questions.length) return parsed;
      } catch (e) { /* try the next one */ }
    }
    const a = text.indexOf('{'), b = text.lastIndexOf('}');
    if (a !== -1 && b > a) {
      try { return JSON.parse(text.slice(a, b + 1)); }
      catch (err) { throw new Error('The reply is not valid JSON. Make sure the chatbot did not cut it off.'); }
    }
    throw new Error('Could not find a quiz in what you pasted. Try asking the chatbot again.');
  }

  function initNew() {
    const hsk = document.getElementById('qz-hsk');
    const count = document.getElementById('qz-count');
    const kindsBox = document.getElementById('qz-kinds');
    const promptBox = document.getElementById('qz-prompt');
    const jsonBox = document.getElementById('qz-json');
    const errBox = document.getElementById('qz-errors');
    const createBtn = document.getElementById('qz-create');

    kindsBox.innerHTML = KINDS.map((k) => `
      <label class="qz-kind">
        <input type="checkbox" value="${k.id}" ${k.on ? 'checked' : ''}>
        <span>${k.label}<small>${k.hint}</small></span>
      </label>`).join('');
    applyI18n(kindsBox);

    function refresh() {
      const n = Math.max(4, Math.min(30, parseInt(count.value, 10) || 10));
      const ids = [...kindsBox.querySelectorAll('input:checked')].map((i) => i.value);
      promptBox.value = buildPrompt(hsk.value, n, ids);
    }
    [hsk, count].forEach((el) => el.addEventListener('input', refresh));
    kindsBox.addEventListener('change', refresh);
    refresh();

    document.getElementById('qz-copy').addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(promptBox.value);
      } catch (e) {
        promptBox.select();
        document.execCommand('copy');
      }
      showToast('Prompt copied');
    });

    function showErrors(title, list) {
      errBox.hidden = false;
      errBox.innerHTML = '';
      const head = document.createElement('div');
      head.textContent = T(title);
      errBox.appendChild(head);
      if (list && list.length) {
        const ul = document.createElement('ul');
        list.forEach((m) => { const li = document.createElement('li'); li.textContent = T(m); ul.appendChild(li); });
        errBox.appendChild(ul);
      }
      applyI18n(errBox);
    }

    createBtn.addEventListener('click', async () => {
      errBox.hidden = true;
      let quiz;
      try { quiz = parseQuizJson(jsonBox.value); }
      catch (err) { showErrors(err.message); return; }

      createBtn.disabled = true;
      try {
        const res = await post(root.dataset.createUrl, { quiz });
        if (res.ok) {
          showToast('Quiz created');
          location.href = res.data.url;
          return;
        }
        if (res.status === 400) showErrors(res.data.msg || 'This quiz has problems.', res.data.details);
        else showErrors(res.data.msg || 'Something went wrong. Please try again.');
      } catch (e) {
        showErrors('Network error. Please try again.');
      } finally {
        createBtn.disabled = false;
      }
    });
  }

  /* ------------------------------------------------------------------
     Quiz detail: title, who gets it, settings, delete
     ------------------------------------------------------------------ */
  function initDetail() {
    const url = root.dataset.updateUrl;

    async function save(body, okMessage) {
      try {
        const res = await post(url, body);
        if (res.ok) { showToast(okMessage || 'Saved'); return true; }
        showToast(res.data.msg || 'Something went wrong', 'err');
      } catch (e) {
        showToast('Network error. Please try again.', 'err');
      }
      return false;
    }

    document.getElementById('qz-title-save').addEventListener('click', () => {
      save({ title: document.getElementById('qz-title-input').value });
    });

    const all = document.getElementById('qz-assign-all');
    const picker = document.getElementById('qz-picker');
    all.addEventListener('change', async () => {
      picker.style.opacity = all.checked ? '.5' : '1';
      await save({ assign_all: all.checked });
    });
    document.getElementById('qz-assign-save').addEventListener('click', () => {
      const ids = [...document.querySelectorAll('.qz-stu:checked')].map((i) => Number(i.value));
      save({ student_ids: ids });
    });

    document.getElementById('qz-hide-pinyin').addEventListener('change', (e) => save({ hide_pinyin: e.target.checked }));
    document.getElementById('qz-retakes').addEventListener('change', (e) => save({ allow_retakes: e.target.checked }));
    document.getElementById('qz-time').addEventListener('change', (e) => save({ time_limit_seconds: e.target.value }));

    document.getElementById('qz-delete').addEventListener('click', async () => {
      if (!confirm(T('Delete this quiz and all its results?'))) return;
      try {
        const res = await post(root.dataset.deleteUrl);
        if (res.ok) { location.href = res.data.url; return; }
        showToast(res.data.msg || 'Something went wrong', 'err');
      } catch (e) {
        showToast('Network error. Please try again.', 'err');
      }
    });
  }

  if (page === 'new') initNew();
  if (page === 'detail') initDetail();
})();
