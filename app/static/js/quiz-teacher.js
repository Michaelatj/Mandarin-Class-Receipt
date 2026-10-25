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
      text: 'FILL IN THE BLANK ("type": "multiple_choice") - A Hanzi sentence with one word blanked out as ___. Annotate EVERY word with pinyin in parentheses: 他 (tā) 晚上 (wǎnshang) 先 (xiān) 吃饭 (chīfàn)，然后 (ránhòu) ___。 Test one specific word or grammar point (measure word, particle, conjunction, adverb, preposition, or a vocabulary word with a clear context). The sentence must carry a clue so that exactly ONE option fits. Options are candidate Hanzi + pinyin only.' },
    { id: 'guess_hanzi', label: 'English to Mandarin', hint: 'English prompt, the student picks the matching Hanzi.', on: true,
      text: 'ENGLISH -> MANDARIN ("type": "multiple_choice") - The question is a specific plain English sentence or phrase, so only one option can match it. Options are Hanzi + pinyin only. Wrong options must differ in meaning or be clearly ungrammatical, never a near-synonym of the answer.' },
    { id: 'what_means', label: 'What does it mean', hint: 'A Hanzi word or phrase, the student picks the English meaning.', on: true,
      text: 'WHAT DOES IT MEAN ("type": "multiple_choice") - The question is a Hanzi term with pinyin. Options are English translations with clearly different meanings (no synonyms). Omit "optionMeanings".' },
    { id: 'translate_id', label: 'Translate to Indonesian', hint: 'A Hanzi sentence, the student picks the Indonesian translation.', on: false,
      text: 'TRANSLATE TO INDONESIAN ("type": "multiple_choice") - The question is a full Hanzi sentence with pinyin. Options are Indonesian translations; each wrong option must change the meaning (who, what, when, negation), not just the style. Omit "optionMeanings".' },
    { id: 'conversation', label: 'Conversation reply (A to B)', hint: 'Person A says something, the student picks how B replies.', on: false,
      text: 'CONVERSATION REPLY ("type": "multiple_choice") - The question is Person A dialogue: "A：你叫什么名字？(nǐ jiào shénme míngzi?)". Exactly one reply logically answers it; the other options clearly do not fit. Options are replies in Hanzi + pinyin.' },
    { id: 'multi_select', label: 'Select all that apply', hint: 'Several options are correct and the student ticks all of them.', on: false,
      text: 'SELECT ALL THAT APPLY ("type": "multiple_select") - Give 5 or 6 options of which 2 or 3 are correct, and put every correct option in "answers". Use it for "which sentences are correct" or "which words can complete this sentence", where each correct option is clearly right and each wrong option is clearly wrong. The question text must say "Choose all correct answers (选出所有正确的答案)".' },
    { id: 'sentence_reorder', label: 'Reorder the sentence', hint: 'The student taps shuffled word chunks into the right order.', on: false,
      text: 'REORDER THE SENTENCE ("type": "sentence_reorder") - A sentence split into 4-7 chunks, listed in the correct order. Each chunk is "chunk (pinyin)". Include the "chunks" array and omit "options" and "answer". Put EVERY other natural word order with the same meaning in "altOrders" (see the rules below).' },
  ];

  function buildPrompt(hsk, count, kindIds) {
    const kinds = KINDS.filter((k) => kindIds.includes(k.id));
    const hasReorder = kinds.some((k) => k.id === 'sentence_reorder');
    const hasMulti = kinds.some((k) => k.id === 'multi_select');
    const hasChoice = kinds.some((k) => !['sentence_reorder', 'multi_select'].includes(k.id)) || (!hasReorder && !hasMulti);
    const kindsList = kinds.map((k) => k.label).join(', ') || 'a mix of question styles';
    const kindInstructions = kinds.map((k, i) => `${i + 1}. ${k.text}`).join('\n');

    const choiceShape = `    {
      "type": "multiple_choice",
      "question": "Question text",
      "questionMeaning": "English meaning (omit if the question is in English)",
      "options": ["opt 1 (pinyin)", "opt 2 (pinyin)", "opt 3 (pinyin)", "opt 4 (pinyin)", "opt 5 (pinyin)"],
      "optionMeanings": ["meaning 1", "meaning 2", "meaning 3", "meaning 4", "meaning 5"],
      "answer": "opt 1 (pinyin)",
      "explanation": "Why this option is right and why the closest wrong option is wrong."
    }`;
    const multiShape = `    {
      "type": "multiple_select",
      "question": "Choose all correct answers (选出所有正确的答案): ...",
      "questionMeaning": "English meaning",
      "options": ["opt 1 (pinyin)", "opt 2 (pinyin)", "opt 3 (pinyin)", "opt 4 (pinyin)", "opt 5 (pinyin)"],
      "optionMeanings": ["meaning 1", "meaning 2", "meaning 3", "meaning 4", "meaning 5"],
      "answers": ["opt 1 (pinyin)", "opt 3 (pinyin)"],
      "explanation": "Why each correct option is right."
    }`;
    const reorderShape = `    {
      "type": "sentence_reorder",
      "question": "Put the words in the correct order",
      "questionMeaning": "English translation of the sentence",
      "chunks": ["我 (wǒ)", "昨天 (zuótiān)", "去了 (qù le)", "商店 (shāngdiàn)"],
      "altOrders": [["昨天 (zuótiān)", "我 (wǒ)", "去了 (qù le)", "商店 (shāngdiàn)"]],
      "explanation": "Brief explanation."
    }`;
    const shapes = [hasChoice ? choiceShape : '', hasMulti ? multiShape : '', hasReorder ? reorderShape : ''].filter(Boolean).join(',\n');

    const multiRules = hasMulti ? `
WHEN SEVERAL ANSWERS ARE CORRECT
- Use "type": "multiple_select" with an "answers" array that lists EVERY correct option, copied exactly from "options". Give 2 or 3 correct options out of 5 or 6, and make sure at least one option is wrong.
- A student only gets the question right if they tick exactly the correct set, so every wrong option must be clearly wrong and every correct option clearly right.
` : `
WHEN SEVERAL ANSWERS ARE CORRECT
- If a question naturally has more than one correct answer, do not write it as multiple_choice. Rewrite it so only one option fits.
`;
    const reorderRules = hasReorder ? `
SENTENCE ORDER QUESTIONS
- Chinese word order is often flexible. List EVERY other natural word order that keeps the same meaning in "altOrders". Each alternative is a full list of the same chunks in a different order. For example the time word can come before or after the subject: 我昨天去了商店 / 昨天我去了商店.
- Only add an order that a native speaker would accept as normal and that means exactly the same thing. Do not add orders that sound odd or change the meaning. If the sentence really has only one natural order, use [].
- Write each alternative with the chunk text copied exactly from "chunks".
` : '';

    return `You are a Mandarin quiz writer for a teacher. Read the TEACHING MATERIAL and return ONE valid JSON object with exactly ${count} questions at HSK ${hsk} level.

WRITE NEW QUESTIONS, DO NOT COPY THE MATERIAL
- Test the same vocabulary, grammar points and sentence patterns as the material, but write fresh sentences and situations. Change the people, places, objects, numbers and context.
- Never reuse a sentence from the material word for word. A student who only memorised the material's sentences must still need to understand the words and grammar to answer.
- Stay at HSK ${hsk} level: use the material's words plus other common words of the same level or easier. Do not introduce harder grammar.

EVERY QUESTION MUST HAVE ONE CLEAR ANSWER (the most important rule)
- A "multiple_choice" question has exactly ONE correct option. Every other option must be clearly wrong for a reason you could state (wrong grammar, wrong meaning in this sentence, wrong measure word, wrong word order, and so on).
- The app shows each student a random set of the wrong options, so EVERY wrong option must be wrong on its own. No wrong option may be an acceptable answer.
- Give the sentence enough context that only one option fits. Avoid blanks that several words of the same kind can fill (sports, places, foods, activities, and so on).
    BAD:  今天下雨，我没去___。  a. 游泳  b. 旅游  c. 跳舞  d. 打篮球   (all four make sense)
    GOOD: 我家有一___小猫。  a. 只  b. 本  c. 杯  d. 张   (only 只 fits)
- Before you write the final JSON, check every question again. If any wrong option could be defended as correct, change the option or the sentence. If a question can only be fixed by accepting several answers, make it a select-all question instead of leaving it ambiguous.
${multiRules}${reorderRules}
STRICT FORMAT RULES
1. Return ONLY the raw JSON object. No explanations, no greeting, no markdown fences.
2. Never use unescaped double quotes (") inside text values. Use single quotes (') or Chinese quotation marks.
3. Keep each "explanation" to 1 short sentence to avoid truncation.
4. "answer" and every item in "answers" must be copied character-for-character from "options". Options must all be different.
5. If "optionMeanings" is present, its length MUST match "options".
6. For multiple_choice give 5 or 6 options, so the app can pick a different set for each student.

QUESTION TYPES TO INCLUDE
${kindInstructions}

JSON OUTPUT STRUCTURE
{
  "title": "Short quiz title",
  "description": "One sentence describing this quiz",
  "questions": [
${shapes}
  ]
}

TARGET LEVEL: HSK ${hsk}
TOTAL QUESTIONS: ${count} (${kindsList})

TEACHING MATERIAL:
"""
Paste your lesson material, vocabulary list, or reading passage here.
"""

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
