/* Upfront payments, students without an account, and receipt sharing (teacher dashboard). */
(function () {
  'use strict';
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  function init() {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const $ = (id) => document.getElementById(id);
    const toast = (msg, type) => { if (typeof showToast === 'function') showToast(msg, type); };

    async function post(url, body) {
      const res = await fetch(url, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify(body || {}),
      });
      let data = {};
      try { data = await res.json(); } catch (e) { /* not json */ }
      return data;
    }

    const open = (el) => el.classList.remove('hidden');
    const close = (el) => el.classList.add('hidden');
    document.querySelectorAll('[data-close-modal]').forEach((b) => b.addEventListener('click', () => close(b.closest('.modal-overlay'))));
    ['addStudentModal', 'prepayModal', 'linkModal'].forEach((id) => {
      const m = $(id);
      if (!m) return;
      m.addEventListener('click', (e) => { if (e.target === m) close(m); });
    });
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      ['addStudentModal', 'prepayModal', 'linkModal'].forEach((id) => { const m = $(id); if (m && !m.classList.contains('hidden')) close(m); });
    });

    function say(el, text, kind) { el.textContent = text || ''; el.className = 'rc-msg' + (kind ? ' ' + kind : ''); }
    function stayOn(tab) { try { sessionStorage.setItem('teacher_page', tab); } catch (e) { /* private mode */ } }

    /* ───── student without an account ───── */
    const asModal = $('addStudentModal');
    if ($('addStudentBtn') && asModal) {
      $('addStudentBtn').addEventListener('click', () => {
        $('asName').value = ''; $('asPhone').value = ''; say($('asMsg'), '');
        open(asModal); setTimeout(() => $('asName').focus(), 60);
      });
      async function saveStudent() {
        const name = $('asName').value.trim();
        if (name.length < 2) { say($('asMsg'), 'Enter the student name.', 'err'); return; }
        $('asSave').disabled = true;
        const data = await post('/teacher/student/add', { name, phone: $('asPhone').value });
        $('asSave').disabled = false;
        if (data.ok) { stayOn('students'); toast(data.name + ' added'); setTimeout(() => location.reload(), 500); }
        else say($('asMsg'), data.msg || 'Could not add the student.', 'err');
      }
      $('asSave').addEventListener('click', saveStudent);
      $('asName').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); saveStudent(); } });
    }

    /* ───── upfront payment ───── */
    const pp = $('prepayModal');
    if (pp) {
      let mode = 'monthly', fee = 0, packet = 'session', receiptId = null;
      const monthSel = $('ppMonth');

      function fillMonths() {
        monthSel.innerHTML = '';
        const now = new Date(Date.now() + 7 * 3600 * 1000);          // WIB
        for (let i = -1; i <= 4; i++) {
          const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + i, 1));
          const o = document.createElement('option');
          o.value = d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0');
          o.textContent = d.toLocaleDateString('id-ID', { month: 'long', year: 'numeric', timeZone: 'UTC' });
          if (i === 0) o.selected = true;
          monthSel.appendChild(o);
        }
      }
      function today() {
        const d = new Date(Date.now() + 7 * 3600 * 1000);
        return d.toISOString().slice(0, 10);
      }
      function setMode(m) {
        mode = m;
        $('ppMode').querySelectorAll('.seg-btn').forEach((b) => b.classList.toggle('on', b.dataset.mode === m));
        $('ppMonthly').hidden = m !== 'monthly';
        $('ppSessions').hidden = m !== 'sessions';
        suggest();
      }
      function suggest() {
        if (!fee) return;
        const qty = mode === 'monthly' ? parseInt($('ppMonths').value, 10) : parseInt($('ppCount').value, 10) || 0;
        // a monthly packet fee is per month; a per-session fee is per class
        if (mode === 'monthly' && packet === 'monthly') $('ppAmount').value = fee * qty;
        else if (mode === 'sessions' && packet !== 'monthly') $('ppAmount').value = fee * qty;
        else $('ppAmount').value = '';
      }
      async function loadDefaults() {
        fee = 0; packet = 'session';
        try {
          const res = await fetch('/teacher/prepay/defaults?student_id=' + $('ppStudent').value, { credentials: 'same-origin' });
          const d = await res.json();
          if (d.ok) { fee = d.fee || 0; packet = d.packet || 'session'; }
        } catch (e) { /* keep manual entry */ }
        setMode(packet === 'monthly' ? 'monthly' : 'sessions');
      }
      function openPrepay() {
        if (!$('ppStudent').options.length) { toast('Add a student first', 'err'); return; }
        fillMonths(); $('ppDate').value = today(); $('ppMethod').value = ''; $('ppAmount').value = '';
        $('ppCount').value = 8; $('ppMonths').value = '1';
        say($('ppMsg'), ''); $('ppForm').hidden = false; $('ppDone').hidden = true;
        open(pp); loadDefaults();
      }
      document.addEventListener('click', (e) => { if (e.target.closest('.open-prepay')) openPrepay(); });
      $('ppStudent').addEventListener('change', loadDefaults);
      $('ppMode').addEventListener('click', (e) => { const b = e.target.closest('.seg-btn'); if (b) setMode(b.dataset.mode); });
      $('ppMonths').addEventListener('change', suggest);
      $('ppCount').addEventListener('input', suggest);

      $('ppSave').addEventListener('click', async () => {
        const amount = parseInt($('ppAmount').value, 10);
        if (!amount || amount <= 0) { say($('ppMsg'), 'Enter the amount you received.', 'err'); return; }
        const body = { student_id: $('ppStudent').value, mode, amount, paid_on: $('ppDate').value, method: $('ppMethod').value };
        if (mode === 'monthly') {
          const [y, m] = monthSel.value.split('-');
          Object.assign(body, { year: y, month: m, months: $('ppMonths').value });
        } else {
          body.sessions = $('ppCount').value;
        }
        $('ppSave').disabled = true;
        const data = await post('/teacher/prepay', body);
        $('ppSave').disabled = false;
        if (!data.ok) { say($('ppMsg'), data.msg || 'Could not record the payment.', 'err'); return; }
        receiptId = data.receipt_id;
        $('ppDoneText').textContent = data.student + ': ' + data.covers + '. The receipt is marked paid.';
        $('ppOpenPdf').href = data.pdf;
        $('ppShare').dataset.shareReceipt = data.receipt_id;
        $('ppForm').hidden = true; $('ppDone').hidden = false;
      });
      $('ppFinish').addEventListener('click', () => { stayOn('receipts'); location.reload(); });
    }

    /* ───── link to a registered account ───── */
    const lk = $('linkModal');
    if (lk) {
      let managedId = null;
      document.addEventListener('click', (e) => {
        const b = e.target.closest('.link-student-btn');
        if (!b) return;
        managedId = b.dataset.id;
        $('lkWho').textContent = b.dataset.name + ' has no account yet. Pick the account she registered.';
        say($('lkMsg'), '');
        if (!$('lkAccount').options.length) say($('lkMsg'), 'No registered student accounts yet. Ask her to register first.', 'err');
        open(lk);
      });
      $('lkSave').addEventListener('click', async () => {
        if (!managedId || !$('lkAccount').value) return;
        $('lkSave').disabled = true;
        const data = await post('/teacher/student/' + managedId + '/link', { account_id: $('lkAccount').value });
        $('lkSave').disabled = false;
        if (data.ok) { stayOn('students'); toast(data.msg); setTimeout(() => location.reload(), 600); }
        else say($('lkMsg'), data.msg || 'Could not link the account.', 'err');
      });
    }

    /* ───── share a receipt PDF (WhatsApp share sheet on phones) ───── */
    document.addEventListener('click', async (e) => {
      const b = e.target.closest('[data-share-receipt]');
      if (!b) return;
      const id = b.dataset.shareReceipt;
      b.disabled = true;
      try {
        const res = await fetch('/teacher/receipt/' + id + '.pdf', { credentials: 'same-origin' });
        if (!res.ok) throw new Error('failed');
        const blob = await res.blob();
        const file = new File([blob], 'Kwitansi_' + id + '.pdf', { type: 'application/pdf' });
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
          await navigator.share({ files: [file], text: 'Kwitansi pembayaran kursus Mandarin' });
        } else {
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob); a.download = file.name;
          document.body.appendChild(a); a.click();
          setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
          toast('PDF downloaded. Send it from your files or WhatsApp Web.');
        }
      } catch (err) {
        if (!err || err.name !== 'AbortError') toast('Could not prepare the receipt', 'err');
      } finally { b.disabled = false; }
    });
  }
})();
