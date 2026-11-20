/* Teacher: reset a student's password (the key button in the Students list). */
(function () {
  'use strict';
  const modal = document.getElementById('resetPwModal');
  if (!modal) return;
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const form = document.getElementById('resetPwForm');
  const input = document.getElementById('resetPwInput');
  const sub = document.getElementById('resetPwSubtitle');
  const submit = document.getElementById('resetPwSubmit');
  let studentId = null;

  const open = (id, name) => {
    studentId = id; input.value = ''; submit.disabled = false; submit.textContent = 'Set New Password';
    sub.textContent = 'Student: ' + name;
    modal.classList.remove('hidden'); setTimeout(() => input.focus(), 30);
  };
  const close = () => modal.classList.add('hidden');

  document.addEventListener('click', (e) => {
    const b = e.target.closest('.reset-pw-btn');
    if (b) { open(b.dataset.id, b.dataset.name || ''); return; }
    if (e.target.closest('#resetPwClose') || e.target === modal) close();
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.classList.contains('hidden')) close(); });

  document.getElementById('resetPwGenerate')?.addEventListener('click', () => {
    const chars = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    const buf = new Uint32Array(10); crypto.getRandomValues(buf);
    input.value = Array.from(buf, n => chars[n % chars.length]).join('');
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const pw = input.value.trim();
    if (pw.length < 6) { alert('Password must be at least 6 characters.'); return; }
    submit.disabled = true; submit.textContent = 'Saving…';
    try {
      const body = new URLSearchParams({ new_password: pw });
      const r = await fetch('/teacher/reset_student_password/' + encodeURIComponent(studentId), {
        method: 'POST', credentials: 'same-origin', body,
        headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.ok) throw new Error(j.msg || 'Could not reset the password.');
      submit.textContent = 'Saved ✓';
      alert('Password updated. Give the student this new password:\n\n' + pw);
      close();
    } catch (err) {
      submit.disabled = false; submit.textContent = 'Set New Password';
      alert(err.message || 'Network error. Please try again.');
    }
  });
})();
