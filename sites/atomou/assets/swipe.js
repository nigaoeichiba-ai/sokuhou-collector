/* Moving the cards with a finger or a mouse, lightly (no libraries, no effects that run all the time):
   1. "めくって見る": the home page's lists become pages that snap sideways, one card to a page (the browser's own scroll snapping: a swipe turns the page, like a book).
      The choice is kept in the visitor's settings (prefs.pager).  The arrows and "2 / 6" are there for a mouse and for the keyboard.
   2. Swipe a card to the right (touch): it follows the finger; past a short distance it goes into the planner (or out of it again), and the card springs back.
      The buttons stay: the swipe is a shortcut and never the only way.  A vertical move is a scroll, a press-and-hold is the reorder (app.js), a tap is a tap.
   Nothing is sent anywhere. */
(function () {
  'use strict';
  var A = window.AtomouApp;
  if (!A) return;
  var $ = A.$, $$ = A.$$, H = A.H;

  /* ---------- 1. page-turn view of the home page's lists ---------- */
  var GRIDS = ['#grid', '#int-grid', '#reg-grid', '#mine-grid'];
  function pagerOn() { return !!(A.state().prefs.pager); }
  function apply() {
    var on = pagerOn();
    GRIDS.forEach(function (sel) {
      var g = $(sel);
      if (!g) return;
      g.classList.toggle('pager', on);
      var bar = g.nextElementSibling && g.nextElementSibling.classList && g.nextElementSibling.classList.contains('pager-bar') ? g.nextElementSibling : null;
      if (on && !bar) { bar = document.createElement('p'); bar.className = 'pager-bar'; bar.innerHTML = '<button type="button" class="mini" data-pg="-1" aria-label="前のカード">‹</button><span class="pg-n" aria-live="polite"></span><button type="button" class="mini" data-pg="1" aria-label="次のカード">›</button>'; g.parentNode.insertBefore(bar, g.nextSibling); }
      if (!on && bar) bar.parentNode.removeChild(bar);
      if (on) update(g);
    });
    var t = $('#pager-toggle');
    if (t) { t.setAttribute('aria-pressed', on ? 'true' : 'false'); t.textContent = on ? '並べて見る' : 'めくって見る'; }
  }
  function pageOf(g) { var cards = $$('.card', g), w = g.clientWidth || 1, i = Math.round(g.scrollLeft / (cards[0] ? cards[0].getBoundingClientRect().width + 10 : w)); return { i: Math.max(0, Math.min(cards.length - 1, i)), n: cards.length }; }
  function update(g) {
    var bar = g.nextElementSibling, p = pageOf(g);
    if (!bar || !bar.classList || !bar.classList.contains('pager-bar')) return;
    var n = bar.querySelector('.pg-n'), txt = p.n ? (p.i + 1) + ' / ' + p.n : '';
    if (n && n.textContent !== txt) n.textContent = txt;
  }
  function turn(g, d) {
    var cards = $$('.card', g), p = pageOf(g), to = cards[Math.max(0, Math.min(cards.length - 1, p.i + d))];
    if (to) g.scrollTo({ left: to.offsetLeft - g.offsetLeft, behavior: 'smooth' });
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest ? ev.target.closest('[data-pg]') : null;
    if (b) { var g = b.parentNode.previousElementSibling; if (g) turn(g, +b.getAttribute('data-pg')); return; }
    var t = ev.target.closest ? ev.target.closest('#pager-toggle') : null;
    if (t) { var S = A.state(); S.prefs.pager = !S.prefs.pager; A.persist(); A.stat('act:pager_' + (S.prefs.pager ? 'on' : 'off')); apply(); }
  });
  document.addEventListener('scroll', function (ev) { var g = ev.target; if (g && g.classList && g.classList.contains('pager')) update(g); }, true);
  document.addEventListener('keydown', function (ev) {
    var g = ev.target.closest ? ev.target.closest('.cards.pager') : null;
    if (g && (ev.key === 'ArrowRight' || ev.key === 'ArrowLeft') && !ev.target.matches('input,select,textarea')) { turn(g, ev.key === 'ArrowRight' ? 1 : -1); ev.preventDefault(); }
  });
  if (A.page === 'home') {
    if (A.P.today && A.P.pager) A.state().prefs.pager = A.P.pager === '1';   // tests: ?today=...&pager=1 (not saved)
    apply();
    GRIDS.forEach(function (sel) {   // the lists are drawn again after the catalogue arrives: the arrows and the counter follow (only the cards of a list are watched, not the bar beside it)
      var g = $(sel);
      if (g) new MutationObserver(function () { clearTimeout(apply.t); apply.t = setTimeout(apply, 60); }).observe(g, { childList: true });
    });
  }

  /* ---------- 2. swipe a card to the right: into the planner (or out of it) ---------- */
  var sw = null, THRESH = 84;
  function official(card) { return card && /^c:/.test(card.getAttribute('data-key') || '') && !card.classList.contains('quiet') && !card.classList.contains('ghost'); }
  function interactive(t) { return t.closest && t.closest('a,button,input,select,textarea,label,summary'); }
  document.addEventListener('touchstart', function (ev) {
    sw = null;
    if (ev.touches.length !== 1 || !ev.target.closest) return;
    var card = ev.target.closest('.card');
    if (!official(card) || interactive(ev.target) || card.closest('.cards.pager') || document.body.classList.contains('drag-on')) return;
    var t = ev.touches[0];
    sw = { card: card, x: t.clientX, y: t.clientY, dx: 0, dir: null, hint: null };
  }, { passive: true });
  document.addEventListener('touchmove', function (ev) {
    if (!sw || document.body.classList.contains('drag-on')) return;
    var t = ev.touches[0], dx = t.clientX - sw.x, dy = t.clientY - sw.y;
    if (sw.dir === null) {
      if (Math.abs(dx) + Math.abs(dy) < 12) return;
      sw.dir = (dx > 0 && Math.abs(dx) > Math.abs(dy) * 1.5) ? 'h' : 'v';   // a clearly sideways move to the right is a swipe; anything else is the page's own scroll
      if (sw.dir === 'h') {
        sw.hint = document.createElement('span'); sw.hint.className = 'swipe-hint'; sw.hint.setAttribute('aria-hidden', 'true');
        var saved = A.state().saved.indexOf((sw.card.getAttribute('data-key') || '').slice(2)) >= 0;
        sw.hint.textContent = saved ? '予定から外す' : '予定に入れる';
        sw.card.appendChild(sw.hint); sw.card.classList.add('swiping'); document.body.classList.add('sw-on');
      }
    }
    if (sw.dir !== 'h') return;
    if (ev.cancelable) ev.preventDefault();
    sw.dx = Math.max(0, Math.min(dx, 150));
    sw.card.style.transform = 'translateX(' + sw.dx + 'px)';
    sw.hint.classList.toggle('go', sw.dx >= THRESH);
  }, { passive: false });
  function end() {
    if (!sw) return;
    var s = sw; sw = null;
    if (s.dir !== 'h') return;
    var go = s.dx >= THRESH;
    s.card.classList.remove('swiping'); document.body.classList.remove('sw-on'); s.card.style.transition = 'transform .18s ease'; s.card.style.transform = '';
    setTimeout(function () { s.card.style.transition = ''; if (s.hint && s.hint.parentNode) s.hint.parentNode.removeChild(s.hint); }, 200);
    if (go) { A.stat('act:swipe_save'); A.toggleSave(s.card); }
    swallow = true; setTimeout(function () { swallow = false; }, 350);   // the tap that ends a swipe is not a tap
  }
  var swallow = false;
  document.addEventListener('touchend', end);
  document.addEventListener('touchcancel', end);
  document.addEventListener('click', function (ev) { if (swallow) { ev.stopPropagation(); ev.preventDefault(); } }, true);
})();
