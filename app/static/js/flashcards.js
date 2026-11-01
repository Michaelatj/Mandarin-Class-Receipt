/* Flashcards for a finished quiz. Everything runs in the browser, nothing is saved. */
(function () {
  const dataEl = document.getElementById('fc-data');
  if (!dataEl) return;
  const deck = JSON.parse(dataEl.textContent);
  const $ = (id) => document.getElementById(id);

  const card = $('fc-card');
  let order = deck.map((_, i) => i);
  let pos = 0;
  const learned = new Set();     // got it
  const missed = new Set();      // still learning

  function render() {
    const c = deck[order[pos]];
    card.classList.remove('flipped');
    $('fc-front').textContent = c.front;
    $('fc-front-sub').textContent = c.frontSub;
    $('fc-back').textContent = c.back;
    $('fc-why').textContent = c.why;
    $('fc-count').textContent = 'Card ' + (pos + 1) + ' of ' + order.length;
    $('fc-prog').style.width = ((pos + 1) / order.length * 100) + '%';
    $('fc-prev').disabled = pos === 0;
  }

  function flip() { card.classList.toggle('flipped'); }

  function go(step) {
    const next = pos + step;
    if (next < 0) return;
    if (next >= order.length) { finish(); return; }
    pos = next;
    render();
  }

  function mark(set) {
    const id = order[pos];
    learned.delete(id); missed.delete(id);
    set.add(id);
    go(1);
  }

  function finish() {
    $('fc-done').hidden = false;
    $('fc-done-title').textContent = learned.size + ' of ' + deck.length + ' cards learned';
    $('fc-done-sub').textContent = missed.size
      ? missed.size + ' card' + (missed.size === 1 ? '' : 's') + ' marked as still learning.'
      : 'Nothing left to review.';
    $('fc-redo-learning').style.display = missed.size ? '' : 'none';
    $('fc-done').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function restart(ids) {
    order = ids;
    pos = 0;
    $('fc-done').hidden = true;
    render();
  }

  function shuffle(list) {
    const a = list.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  card.addEventListener('click', flip);
  card.addEventListener('keydown', (e) => {
    if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); flip(); }
  });
  document.addEventListener('keydown', (e) => {
    if (e.target.closest('input, textarea, select')) return;
    if (e.key === 'ArrowRight') go(1);
    else if (e.key === 'ArrowLeft') go(-1);
  });
  $('fc-prev').addEventListener('click', () => go(-1));
  $('fc-next').addEventListener('click', () => go(1));
  $('fc-know').addEventListener('click', () => mark(learned));
  $('fc-again').addEventListener('click', () => mark(missed));
  $('fc-shuffle').addEventListener('click', () => { learned.clear(); missed.clear(); restart(shuffle(deck.map((_, i) => i))); });
  $('fc-redo-all').addEventListener('click', () => { learned.clear(); missed.clear(); restart(deck.map((_, i) => i)); });
  $('fc-redo-learning').addEventListener('click', () => {
    const ids = Array.from(missed);
    learned.clear(); missed.clear();
    restart(shuffle(ids));
  });

  render();
})();
