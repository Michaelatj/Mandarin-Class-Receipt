/* Theme choice for the whole app: Light, Dark, Night, Chinese, Chinese (dark).
   Saved on this device. The same dropdown is used on the login page and in Settings. */
(function () {
  'use strict';
  const root = document.documentElement;

  const THEMES = [
    { id: 'light',      label: 'Light',            note: 'Clean and bright',                    theme: 'light', skin: '' },
    { id: 'dark',       label: 'Dark',             note: 'Easy on the eyes',                    theme: 'dark',  skin: '' },
    { id: 'night',      label: 'Night',            note: 'Blue dusk with mountains and a moon', theme: 'dark',  skin: 'night' },
    { id: 'china',      label: 'Chinese',          note: 'Red and cream with lanterns',         theme: 'light', skin: 'china' },
    { id: 'china-dark', label: 'Chinese (dark)',   note: 'Red accents on warm charcoal',        theme: 'dark',  skin: 'china' },
  ];

  // first visit without a saved choice: follow the device setting
  if (!root.getAttribute('data-theme')) {
    root.setAttribute('data-theme', window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }

  function current() {
    const th = root.getAttribute('data-theme') || 'light';
    const sk = root.getAttribute('data-skin') || '';
    return THEMES.find((t) => t.theme === th && t.skin === sk) || THEMES.find((t) => t.skin === sk && sk) || THEMES.find((t) => t.theme === th) || THEMES[0];
  }

  const pickers = [];

  function sync() {
    const cur = current();
    pickers.forEach((p) => p.sync(cur));
  }

  function apply(id) {
    const t = THEMES.find((x) => x.id === id);
    if (!t) return;
    root.classList.add('theme-anim');                       // short colour fade
    root.setAttribute('data-theme', t.theme);
    if (t.skin) root.setAttribute('data-skin', t.skin); else root.removeAttribute('data-skin');
    try {
      localStorage.setItem('theme', t.theme);
      if (t.skin) localStorage.setItem('skin', t.skin); else localStorage.removeItem('skin');
    } catch (e) { /* private mode */ }
    clearTimeout(window._fadeT);
    window._fadeT = setTimeout(() => root.classList.remove('theme-anim'), 450);
    sync();
  }

  function build(el, index) {
    const btn = el.querySelector('.tp-btn');
    const label = el.querySelector('.tp-current');
    const list = el.querySelector('.tp-list');
    let activeIndex = 0;

    THEMES.forEach((t, i) => {
      const li = document.createElement('li');
      li.className = 'tp-opt';
      li.id = 'tp' + index + '-' + t.id;
      li.setAttribute('role', 'option');
      li.dataset.id = t.id;
      const b = document.createElement('b'); b.textContent = t.label;
      const s = document.createElement('span'); s.textContent = t.note;
      li.append(b, s);
      li.addEventListener('mousemove', () => setActive(i));
      li.addEventListener('click', () => { choose(t.id); });
      list.appendChild(li);
    });
    const opts = Array.from(list.children);

    function setActive(i) {
      activeIndex = (i + opts.length) % opts.length;
      opts.forEach((o, n) => o.classList.toggle('active', n === activeIndex));
      list.setAttribute('aria-activedescendant', opts[activeIndex].id);
      opts[activeIndex].scrollIntoView({ block: 'nearest' });
    }
    function isOpen() { return !list.hidden; }
    const host = el.closest('.card');         // the settings card that holds this dropdown
    function open() {
      list.classList.remove('up');
      list.hidden = false;
      if (host) host.classList.add('tp-host-open');
      btn.setAttribute('aria-expanded', 'true');
      const r = list.getBoundingClientRect();
      if (r.bottom > window.innerHeight - 8 && btn.getBoundingClientRect().top > r.height + 16) list.classList.add('up');
      const cur = current();
      setActive(Math.max(0, THEMES.findIndex((t) => t.id === cur.id)));
      list.focus({ preventScroll: true });
    }
    function close(focusBtn) {
      list.hidden = true;
      if (host) host.classList.remove('tp-host-open');
      btn.setAttribute('aria-expanded', 'false');
      if (focusBtn) btn.focus();
    }
    function choose(id) { apply(id); close(true); }

    btn.addEventListener('click', () => (isOpen() ? close(false) : open()));
    btn.addEventListener('keydown', (e) => {
      if (['ArrowDown', 'ArrowUp'].includes(e.key)) { e.preventDefault(); open(); }
    });
    list.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') { e.preventDefault(); setActive(activeIndex + 1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(activeIndex - 1); }
      else if (e.key === 'Home') { e.preventDefault(); setActive(0); }
      else if (e.key === 'End') { e.preventDefault(); setActive(opts.length - 1); }
      else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(opts[activeIndex].dataset.id); }
      else if (e.key === 'Escape') { e.preventDefault(); close(true); }
      else if (e.key === 'Tab') { close(false); }
    });
    document.addEventListener('click', (e) => { if (isOpen() && !el.contains(e.target)) close(false); });

    return {
      sync(cur) {
        label.textContent = cur.label;
        opts.forEach((o) => o.setAttribute('aria-selected', o.dataset.id === cur.id ? 'true' : 'false'));
      },
    };
  }

  document.querySelectorAll('[data-theme-picker]').forEach((el, i) => pickers.push(build(el, i)));
  window.setThemeChoice = apply;
  window.currentThemeChoice = () => current().id;
  sync();
})();
