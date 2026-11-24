/* Hover, focus or tap a title or a badge name to see its hanzi, pinyin and meaning.
   Works on [data-tt-zh][data-tt-py][data-tt-en] and automatically on the badge chips/seals. */
(function () {
  'use strict';
  const TIER = {
    bronze: ['青铜', 'qīngtóng', 'Bronze · where everyone starts'],
    silver: ['白银', 'báiyín', 'Silver · 5 classes in a row'],
    gold: ['黄金', 'huángjīn', 'Gold · 10 classes in a row'],
    jade: ['翡翠', 'fěicuì', 'Jade · 15 classes in a row'],
    diamond: ['钻石', 'zuànshí', 'Diamond · 20 classes in a row'],
    ruby: ['红宝石', 'hóngbǎoshí', 'Ruby · 25 classes in a row'],
    dragon: ['神龙', 'shénlóng', 'Divine Dragon · 30 classes in a row'],
  };
  let tip = null, owner = null, shownAt = 0;
  function info(el) {
    if (el.dataset.ttZh) return [el.dataset.ttZh, el.dataset.ttPy || '', el.dataset.ttEn || ''];
    const m = (el.className || '').toString().match(/tier-(bronze|silver|gold|jade|diamond|ruby|dragon)/);
    return m ? TIER[m[1]] : null;
  }
  const SEL = '[data-tt-zh], .streak-chip[class*="tier-"], .badge-seal[class*="tier-"], .so-tier';
  function hide() { if (tip) { tip.remove(); tip = null; owner = null; } }
  function show(el) {
    let d = info(el);
    if (!d && el.classList.contains('so-tier')) { const m = el.closest('.so').className.match(/tier-(\w+)/); d = m && TIER[m[1]]; }
    if (!d) return;
    hide(); owner = el; shownAt = Date.now();
    tip = document.createElement('div'); tip.className = 'tt-pop'; tip.setAttribute('role', 'tooltip');
    tip.innerHTML = '<b class="tt-zh"></b><span class="tt-py"></span><span class="tt-en"></span>';
    tip.querySelector('.tt-zh').textContent = d[0]; tip.querySelector('.tt-py').textContent = d[1]; tip.querySelector('.tt-en').textContent = d[2];
    document.body.appendChild(tip);
    const r = el.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
    let x = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), window.innerWidth - w - 8);
    let y = r.top - h - 8; if (y < 8) y = r.bottom + 8;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }
  document.addEventListener('mouseover', (e) => { const el = e.target.closest && e.target.closest(SEL); if (el && el !== owner) show(el); });
  document.addEventListener('mouseout', (e) => { const el = e.target.closest && e.target.closest(SEL); if (el && el === owner && !el.contains(e.relatedTarget)) hide(); });
  document.addEventListener('click', (e) => {
    const el = e.target.closest && e.target.closest(SEL);
    if (el) { if (el === owner) hide(); else show(el); } else hide();
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(); });
  window.addEventListener('scroll', () => { if (Date.now() - shownAt > 400) hide(); }, { passive: true });
})();
