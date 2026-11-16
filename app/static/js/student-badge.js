/* Teacher view: a student's badge and streak in a big card.
   Opened from the Students list (name or "Badge & streak"). Data is already on the page. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const modal = $('stuBadgeModal');
  if (!modal) return;
  let data = {}, tiers = [];
  try { data = JSON.parse($('stuBadgeData').textContent || '{}'); tiers = JSON.parse($('stuTierData').textContent || '[]'); } catch (e) {}

  const close = () => modal.classList.add('hidden');
  function open(id) {
    const d = data[id];
    if (!d) return;
    const t = tiers[d.tier] || tiers[0] || { key: 'bronze', char: '铜', name: 'Bronze', zh: '青铜' };
    $('sbmHero').className = 'badge-hero tier-' + t.key;
    $('sbmSeal').className = 'badge-seal tier-' + t.key;
    $('sbmSeal').dataset.tier = t.key;
    $('sbmChar').textContent = t.char;
    $('sbmAvatar').textContent = (d.name || '?').charAt(0);
    $('sbmName').textContent = d.name + (d.user ? '  @' + d.user : '');
    $('sbmTier').textContent = t.name + ' · ' + t.zh;
    $('sbmCur').textContent = d.cur;
    $('sbmBest').textContent = d.best;
    $('sbmAtt').textContent = d.att + '/' + d.tot;
    $('sbmRate').textContent = d.tot ? Math.round(d.att / d.tot * 100) + '% of scheduled classes attended' : 'No scheduled class yet, so no streak yet';
    const bar = $('sbmNextBar');
    bar.className = 'badge-next-bar tier-' + t.key;
    if (d.tot === 0) {
      $('sbmNext').hidden = true;
    } else {
      $('sbmNext').hidden = false;
      if (d.next_at) {
        bar.firstElementChild.style.width = d.progress + '%';
        $('sbmNextTxt').textContent = (d.next_at - d.cur) + ' more classes in a row to reach ' + d.next_name;
      } else {
        bar.firstElementChild.style.width = '100%';
        $('sbmNextTxt').textContent = '🏆 Highest badge reached';
      }
    }
    const ladder = $('sbmLadder');
    ladder.replaceChildren();
    tiers.forEach((x, i) => {
      const cell = document.createElement('div');
      cell.className = 'sbm-step' + (i < d.tier ? ' done' : i === d.tier ? ' now' : ' ahead');
      const seal = document.createElement('span');
      seal.className = 'streak-chip tier-' + x.key + ' sbm-mini';
      seal.textContent = x.char;
      const nm = document.createElement('b'); nm.textContent = x.name;
      const need = document.createElement('small'); need.textContent = x.min ? x.min + '+ in a row' : 'start';
      cell.append(seal, nm, need);
      ladder.appendChild(cell);
    });
    modal.classList.remove('hidden');
  }

  document.addEventListener('click', (e) => {
    const b = e.target.closest('.stu-info-btn');
    if (b) { open(b.dataset.id); return; }
    if (e.target === modal) close();
  });
  $('sbmClose').addEventListener('click', close);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.classList.contains('hidden')) close(); });
})();
