/* Monthly recap: pick a month, download the PDF, or send it through WhatsApp.
   WhatsApp has no free way to push a file by itself, so on a phone this opens the share
   sheet with the PDF already attached (pick WhatsApp and the chat). Where file sharing is
   not available it downloads the PDF and opens the chat with the message filled in. */
(function () {
  const modal = document.getElementById('recapModal');
  if (!modal) return;

  const $ = (id) => document.getElementById(id);
  const monthSel = $('recapMonth'), phoneIn = $('recapPhone'), who = $('recapWho');
  const dlBtn = $('recapDownload'), shareBtn = $('recapShare'), hint = $('recapHint');
  let studentId = null, studentName = '', ready = null, token = 0;

  function fillMonths() {
    monthSel.innerHTML = '';
    const now = new Date();
    for (let i = 0; i < 6; i++) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const value = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
      const opt = document.createElement('option');
      opt.value = value;
      opt.textContent = d.toLocaleDateString('id-ID', { month: 'long', year: 'numeric' });
      monthSel.appendChild(opt);
    }
  }

  const pdfUrl = (extra) => '/teacher/recap/' + studentId + '.pdf?month=' + monthSel.value + (extra || '');

  // fetch the PDF and the message ahead of time, so the share call can run right inside the tap
  async function prepare() {
    const mine = ++token;
    ready = null;
    shareBtn.disabled = true;
    hint.textContent = 'Preparing the recap...';
    try {
      const [infoRes, pdfRes] = await Promise.all([
        fetch('/teacher/recap/' + studentId + '/info?month=' + monthSel.value, { credentials: 'same-origin' }),
        fetch(pdfUrl(), { credentials: 'same-origin' }),
      ]);
      if (!infoRes.ok || !pdfRes.ok) throw new Error('request failed');
      const info = await infoRes.json();
      const blob = await pdfRes.blob();
      if (mine !== token) return;
      ready = { info, blob, file: new File([blob], info.filename, { type: 'application/pdf' }) };
      if (!phoneIn.value && info.phone) phoneIn.value = info.phone;
      shareBtn.disabled = false;
      hint.textContent = info.sessions + ' session' + (info.sessions === 1 ? '' : 's') + ' this month.'
        + (info.outstanding ? ' Unpaid total is included in the message.' : '');
    } catch (e) {
      if (mine === token) hint.textContent = 'Could not prepare the recap. Check your connection and try again.';
    }
  }

  function waNumber(raw) {
    let d = (raw || '').replace(/\D/g, '');
    if (d.startsWith('0')) d = '62' + d.slice(1);
    else if (d.startsWith('8')) d = '62' + d;
    return d.length >= 9 ? d : '';
  }

  function openChat(text) {
    const num = waNumber(phoneIn.value);
    window.open('https://wa.me/' + num + '?text=' + encodeURIComponent(text), '_blank', 'noopener');
  }

  function save(blob, name) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
  }

  function open(btn) {
    studentId = btn.dataset.id;
    studentName = btn.dataset.name;
    who.textContent = studentName;
    phoneIn.value = btn.dataset.phone || '';
    fillMonths();
    modal.classList.remove('hidden');
    prepare();
  }
  function close() { modal.classList.add('hidden'); token++; }

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.recap-btn');
    if (btn) open(btn);
  });
  $('recapClose').addEventListener('click', close);
  modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.classList.contains('hidden')) close(); });
  monthSel.addEventListener('change', prepare);

  dlBtn.addEventListener('click', () => { window.location.href = pdfUrl('&download=1'); });

  shareBtn.addEventListener('click', async () => {
    if (!ready) return;
    const { info, blob, file } = ready;
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      try {
        await navigator.share({ files: [file], text: info.text });
        return;
      } catch (err) {
        if (err && err.name === 'AbortError') return;   // the teacher closed the share sheet
      }
    }
    save(blob, info.filename);
    openChat(info.text);
    hint.textContent = 'The PDF was downloaded. Attach it in the WhatsApp chat that just opened.';
  });
})();
