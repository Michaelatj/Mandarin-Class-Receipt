/* audio-kit.js - one place for every sound on the site, made to work on phones.
   Why phones stayed silent before:
   - iPhone and Android only let a page make sound after a tap. An AudioContext created later (for example after a
     server answer) stays "suspended" for ever, so the right/wrong tones and the streak music never played.
   - Read-aloud (speechSynthesis) was started after a timer, which iPhone no longer counts as the tap, and the
     code refused to speak when the Chinese voice was not named "zh" (Android names it "cmn-CN" or "Mandarin").
   This file unlocks sound on the first tap, and gives window.AudioKit.ctx() and window.AudioKit.speak(). */
(function () {
  'use strict';
  const AC = window.AudioContext || window.webkitAudioContext;
  let ac = null, unlocked = false;

  /* mute switch: saved on this device, one switch for every game, quiz and celebration */
  let off = false;
  try { off = localStorage.getItem('soundOff') === '1'; } catch (e) { /* private mode */ }
  const muted = () => off;
  function setMuted(v) {
    off = !!v;
    try { localStorage.setItem('soundOff', off ? '1' : '0'); } catch (e) { /* optional */ }
    if (off && 'speechSynthesis' in window) { try { speechSynthesis.cancel(); } catch (e) { /* optional */ } }
    document.querySelectorAll('[data-sound-toggle]').forEach(paintToggle);
    const box = document.getElementById('gm-sound'); if (box) box.checked = !off;
  }
  function paintToggle(b) {
    b.textContent = off ? '🔇' : '🔊';
    b.setAttribute('aria-pressed', off ? 'true' : 'false');
    b.setAttribute('aria-label', off ? 'Sound is off. Tap to turn it on.' : 'Sound is on. Tap to turn it off.');
    b.title = off ? 'Sound off' : 'Sound on';
  }
  // a small button in the menu, next to "Log out", on every page that has the menu
  function addToggle() {
    const out = document.querySelector('.app-sidebar .sidebar-logout');
    if (!out || document.querySelector('.app-sidebar [data-sound-toggle]')) return;
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'sound-toggle'; b.setAttribute('data-sound-toggle', '');
    b.onclick = () => setMuted(!off);
    paintToggle(b);
    out.parentNode.insertBefore(b, out);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', addToggle); else addToggle();

  function ctx() {
    if (!AC || off) return null;
    try {
      ac = ac || new AC();
      if (ac.state !== 'running' && ac.resume) ac.resume();
    } catch (e) { return null; }
    return ac;
  }

  const ss = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window ? window.speechSynthesis : null;
  let voices = [];
  function loadVoices() { try { voices = ss ? (ss.getVoices() || []) : []; } catch (e) { voices = []; } }
  if (ss) { loadVoices(); if (ss.addEventListener) ss.addEventListener('voiceschanged', loadVoices); }

  /* the first tap anywhere: wake the audio engine with one silent sample */
  function unlock() {
    if (unlocked) return;
    const c = ctx();
    if (c) {
      try {
        const b = c.createBuffer(1, 1, 22050), s = c.createBufferSource();
        s.buffer = b; s.connect(c.destination); s.start(0);
      } catch (e) { /* optional */ }
    }
    unlocked = !c || c.state === 'running' || c.state === undefined;
    if (unlocked) ['pointerdown', 'touchend', 'click', 'keydown'].forEach((t) => document.removeEventListener(t, unlock, true));
  }
  ['pointerdown', 'touchend', 'click', 'keydown'].forEach((t) => document.addEventListener(t, unlock, true));
  // coming back to the tab (or unlocking the phone) suspends the engine again
  document.addEventListener('visibilitychange', () => { if (!document.hidden && ac && ac.state !== 'running') ctx(); });

  /* ---- read aloud ---- */
  const isZh = (v) => /^(zh|cmn)/i.test(v.lang) || /chinese|mandarin|中文|普通话|國語|国语/i.test(v.name);
  function pickVoice() {
    const zh = voices.filter((v) => isZh(v) && !/yue|zh[-_]hk|cantonese|粤|廣東/i.test(v.lang + ' ' + v.name));
    return zh.find((v) => /zh[-_]cn|cmn[-_](hans[-_])?cn|hans/i.test(v.lang)) || zh[0] || null;
  }
  // short pieces: Android Chrome cuts off a long utterance after about 15 seconds
  const pieces = (t) => (String(t).match(/[^，,。！？!?；;\n]+[，,。！？!?；;]?/g) || [String(t)]).map((s) => s.trim()).filter(Boolean);

  function speak(text, fail) {
    const bad = (m) => { if (typeof fail === 'function') fail(m); else if (typeof showToast === 'function') showToast(m, 'err'); };
    if (off) { bad('Sound is off. Turn it on with the 🔇 button in the menu.'); return; }
    if (!ss) { bad('This browser cannot read aloud. Try Chrome or Safari.'); return; }
    unlock();
    loadVoices();
    const voice = pickVoice();
    let started = false, failed = false;
    const list = pieces(text).map((p) => {
      const u = new SpeechSynthesisUtterance(p);
      u.lang = voice ? voice.lang : 'zh-CN'; u.rate = 0.85; u.volume = 1;
      if (voice) u.voice = voice;
      u.onstart = () => { started = true; };
      u.onerror = (e) => {
        if (failed || (e && (e.error === 'canceled' || e.error === 'interrupted'))) return;
        failed = true;
        bad(e && /language|voice|unavailable/i.test(e.error || '')
          ? 'No Chinese voice on this device. Install one: Settings > Text-to-speech (Android) or Spoken Content (iPhone).'
          : 'Could not play the sound. Check the volume, and that the phone is not on silent.');
      };
      return u;
    });
    const run = () => {
      try { if (ss.paused) ss.resume(); list.forEach((u) => ss.speak(u)); } catch (e) { bad('Could not play the sound.'); return; }
      setTimeout(() => { if (!started && !failed && !ss.speaking) bad('No sound started. Turn the volume up and switch silent mode off.'); }, 3000);
    };
    // speak straight away inside the tap; only wait when something is playing (Android drops a speak() sent right after cancel())
    if (ss.speaking || ss.pending) { try { ss.cancel(); } catch (e) { /* optional */ } setTimeout(run, 150); } else run();
  }

  window.AudioKit = { ctx, speak, unlock, muted, setMuted };
})();
