/* Teacher: delete a student account (the trash button in the Students list). */
(function () {
  'use strict';
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.del-student-btn');
    if (!btn) return;
    const name = btn.dataset.name || 'this student';
    const typed = await UI.prompt(
      'Delete "' + name + '"?\n\nThis permanently erases the account with all attendance, receipts, streak history and quiz results. It cannot be undone.\n\nType the student\'s name to confirm:',
      { ok: 'Delete', placeholder: name, danger: true }
    );
    if (typed === null) return;
    if (typed.trim().toLowerCase() !== name.trim().toLowerCase()) { UI.alert('The name did not match, so nothing was deleted.'); return; }
    btn.disabled = true;
    try {
      const r = await fetch('/teacher/delete_student/' + encodeURIComponent(btn.dataset.id), {
        method: 'POST', credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.ok) throw new Error(j.msg || 'Could not delete.');
      const row = btn.closest('.dt-row') || btn.closest('[class*="stu-"]');
      if (row) row.remove();
      location.reload();                         // refresh counts, the access matrix and the badge data
    } catch (err) {
      btn.disabled = false;
      alert(err.message || 'Network error. Please try again.');
    }
  });
})();
