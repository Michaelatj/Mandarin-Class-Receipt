/* Teacher: preview every badge and its animations (the streak pop-up and the level-up show). */
(function () {
  'use strict';
  const btn = document.getElementById('badgeGalleryBtn');
  const dataEl = document.getElementById('stuTierData');
  if (!btn || !dataEl || !window.StreakOverlay) return;
  let tiers = [];
  try { tiers = JSON.parse(dataEl.textContent || '[]'); } catch (e) { return; }

  const el = document.createElement('div');
  el.className = 'modal-overlay hidden';
  el.id = 'badgeGallery';
  el.setAttribute('role', 'dialog'); el.setAttribute('aria-modal', 'true');
  el.innerHTML = `
    <div class="modal-box bg-box">
      <div class="bg-head"><h3>Badges &amp; animations</h3><button type="button" class="bg-x" aria-label="Close">✕</button></div>
      <p class="bg-sub">This is what your students see. The higher the badge, the bigger the show. Tap a button to play it (turn the sound on for the full effect).</p>
      <div class="bg-grid"></div>
    </div>`;
  document.body.appendChild(el);
  const grid = el.querySelector('.bg-grid');

  tiers.forEach((t, i) => {
    const nxt = tiers[i + 1];
    const cur = t.min || 1;
    const sample = { cur, best: cur, tier: i, key: t.key, char: t.char, name: t.name, zh: t.zh,
                     next_at: nxt ? nxt.min : null, next_name: nxt ? nxt.name : null,
                     progress: nxt ? Math.round((cur - t.min) / (nxt.min - t.min) * 100) : 100 };
    const card = document.createElement('div');
    card.className = 'bg-card tier-' + t.key;
    card.innerHTML = `
      <span class="streak-chip tier-${t.key} bg-chip">${t.char}</span>
      <div class="bg-info"><b>${t.name} · ${t.zh}</b><small>${t.min ? t.min + '+ classes in a row' : 'First badge, from the start'}</small></div>
      <div class="bg-acts">
        <button type="button" class="btn bgh bsm" data-mode="join">▶ Streak pop-up</button>
        <button type="button" class="btn bgh bsm" data-mode="levelup">▶ New badge</button>
      </div>`;
    card.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => {
      window.StreakOverlay.show({ mode: b.dataset.mode, streak: sample, link: '' });
    }));
    grid.appendChild(card);
  });

  const close = () => el.classList.add('hidden');
  btn.addEventListener('click', () => el.classList.remove('hidden'));
  el.querySelector('.bg-x').addEventListener('click', close);
  el.addEventListener('click', (e) => { if (e.target === el) close(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !el.classList.contains('hidden') && !document.querySelector('.so')) close(); });
})();
