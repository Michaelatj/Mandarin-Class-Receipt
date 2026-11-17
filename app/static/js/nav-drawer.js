/* Menu drawer. On every page that has the app shell (student + teacher dashboard, Quiz, Bonus Courses)
   a top bar with a burger button is added. The burger opens the menu (the old sidebar) as a drawer
   from the left, on phones and on computers. The bottom tab bar is no longer shown. */
(function () {
  'use strict';
  const shell = document.querySelector('.app-shell');
  const side = document.getElementById('appSidebar') || document.querySelector('.app-sidebar');
  const main = shell && shell.querySelector('.app-main');
  if (!shell || !side || !main) return;

  const brandZh = side.querySelector('.sidebar-brand-zh');
  const brandTag = side.querySelector('.sidebar-brand-tag');

  const bar = document.createElement('header');
  bar.className = 'app-topbar';
  const burger = document.createElement('button');
  burger.type = 'button';
  burger.className = 'burger-btn';
  burger.setAttribute('aria-label', 'Open menu');
  burger.setAttribute('aria-controls', side.id || 'appSidebar');
  burger.setAttribute('aria-expanded', 'false');
  burger.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path class="b1" d="M4 7h16"/><path class="b2" d="M4 12h16"/><path class="b3" d="M4 17h16"/></svg><i class="burger-dot" hidden></i>';
  const brand = document.createElement('div');
  brand.className = 'topbar-brand';
  const zh = document.createElement('span'); zh.className = 'topbar-zh'; zh.textContent = brandZh ? brandZh.textContent : '中文课堂';
  const tag = document.createElement('span'); tag.className = 'topbar-tag'; tag.textContent = brandTag ? brandTag.textContent : '';
  brand.append(zh, tag);
  bar.append(burger, brand);
  main.insertBefore(bar, main.firstChild);

  const scrim = document.createElement('div');
  scrim.className = 'nav-scrim';
  shell.appendChild(scrim);

  if (!side.id) side.id = 'appSidebar';
  // the drawer's own close button (for screen readers and for the thumb)
  const closeBtn = document.createElement('button');
  closeBtn.type = 'button'; closeBtn.className = 'drawer-close'; closeBtn.setAttribute('aria-label', 'Close menu');
  closeBtn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
  side.insertBefore(closeBtn, side.firstChild);

  const isOpen = () => document.body.classList.contains('nav-open');
  function set(open) {
    document.body.classList.toggle('nav-open', open);
    burger.setAttribute('aria-expanded', String(open));
    burger.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    if ('inert' in side) side.inert = !open;           // closed drawer: keep it out of the tab order
    if (open) { const a = side.querySelector('.snav-btn.active, .snav-link.active') || side.querySelector('.snav-btn, .snav-link'); if (a) a.focus({ preventScroll: true }); }
    else if (document.activeElement && side.contains(document.activeElement)) burger.focus({ preventScroll: true });
  }
  set(false);

  burger.addEventListener('click', () => set(!isOpen()));
  closeBtn.addEventListener('click', () => set(false));
  scrim.addEventListener('click', () => set(false));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && isOpen()) set(false); });
  side.addEventListener('click', (e) => { if (e.target.closest('.snav-btn')) set(false); });   // picking a tab closes it

  // a dot on the burger while a menu item carries a badge (new classes, unpaid receipts, ...)
  const pips = () => [...side.querySelectorAll('.snav-pip')].some((p) => p.offsetParent !== null || getComputedStyle(p).display !== 'none');
  const dot = burger.querySelector('.burger-dot');
  const refreshDot = () => { dot.hidden = !pips(); };
  refreshDot();
  new MutationObserver(refreshDot).observe(side, { subtree: true, childList: true, attributes: true, attributeFilter: ['class', 'style', 'hidden'] });
})();
