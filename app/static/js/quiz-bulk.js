/* Teacher quiz list: select several quizzes (or all) and delete them in one go. */
(function () {
  'use strict';
  const bar = document.getElementById('qz-bulkbar');
  if (!bar) return;
  const all = document.getElementById('qz-selall');
  const count = document.getElementById('qz-bulkcount');
  const del = document.getElementById('qz-bulkdel');
  const picks = () => [...document.querySelectorAll('.qz-pick')];
  const csrf = (typeof _CSRF !== 'undefined' && _CSRF) || document.querySelector('meta[name="csrf-token"]')?.content || '';

  function sync() {
    const p = picks(), on = p.filter((c) => c.checked);
    p.forEach((c) => c.closest('.qz-item').classList.toggle('picked', c.checked));
    count.textContent = on.length + ' selected';
    del.disabled = on.length === 0;
    all.checked = p.length > 0 && on.length === p.length;
    all.indeterminate = on.length > 0 && on.length < p.length;
  }
  all.addEventListener('change', () => { picks().forEach((c) => { c.checked = all.checked; }); sync(); });
  document.addEventListener('change', (e) => { if (e.target.classList.contains('qz-pick')) sync(); });

  del.addEventListener('click', async () => {
    const ids = picks().filter((c) => c.checked).map((c) => parseInt(c.value, 10));
    if (!ids.length) return;
    if (!(await UI.confirm('Delete ' + ids.length + ' quiz' + (ids.length === 1 ? '' : 'zes') + '?\n\nAll student results for them are erased too. This cannot be undone.', { danger: true }))) return;
    del.disabled = true;
    try {
      const r = await fetch(bar.dataset.url, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ ids }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.ok) throw new Error(j.msg || 'Could not delete.');
      location.reload();
    } catch (err) { alert(err.message || 'Network error.'); sync(); }
  });
  sync();
})();
