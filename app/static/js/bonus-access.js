/* Teacher: unlock / lock Bonus Courses (HSK 1-3) per student. Saves on every change. */
(function () {
  'use strict';
  const table = document.getElementById('bonusTable');
  if (!table) return;
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const toast = (m, t) => (window.showToast ? window.showToast(m, t) : null);

  async function save(studentId, level, on) {
    const r = await fetch('/teacher/bonus_access', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify({ student_id: studentId, level: Number(level), on }),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok || !j.ok) throw new Error(j.msg || 'Could not save');
    return j;
  }

  table.addEventListener('change', async (e) => {
    const box = e.target.closest('.bonus-chk');
    if (!box) return;
    const want = box.checked;
    box.disabled = true;
    try {
      await save(box.dataset.sid, box.dataset.level, want);
      toast(want ? '🔓 HSK ' + box.dataset.level + ' unlocked' : '🔒 HSK ' + box.dataset.level + ' locked');
    } catch (err) {
      box.checked = !want;                       // put it back: the server did not save it
      toast(err.message || 'Network error. Please try again.', 'err');
    } finally { box.disabled = false; }
  });

  table.addEventListener('click', async (e) => {
    const b = e.target.closest('.bonus-all');
    if (!b) return;
    const on = b.dataset.on === '1', level = b.dataset.level;
    if (!on && !(await UI.confirm('Lock HSK ' + level + ' for ALL students?', { ok: 'Lock', danger: true }))) return;
    try {
      await save('all', level, on);
      table.querySelectorAll('.bonus-chk[data-level="' + level + '"]').forEach((x) => { x.checked = on; });
      toast(on ? '🔓 HSK ' + level + ' unlocked for everyone' : '🔒 HSK ' + level + ' locked for everyone');
    } catch (err) { toast(err.message || 'Network error. Please try again.', 'err'); }
  });
})();
