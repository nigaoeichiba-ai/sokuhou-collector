/* Screen guide: a short step-by-step tour that points at the real buttons of the page.  It starts by itself the first time a page is opened
   (not when ?today= is used, which the tests and screenshots use), and the "ガイド" button starts it again at any time.
   Which pages were seen is kept in the visitor's own settings (prefs.tour); nothing is sent anywhere. */
(function () {
  'use strict';
  var A = window.AtomouApp;
  if (!A) return;
  var $ = A.$, H = A.H, P = A.P, page = A.page;
  var TOURS = {
    home: [
      ['[data-block="search"] input[type="search"]', 'ここで、日付や行事をさがせます。たとえば「年賀状」と入れてみてください。'],
      ['[data-block="cats"] .cats a', 'ジャンルから、さがすこともできます。'],
      ['#grid .card [data-act="save"]', '「予定に入れる」を押すと、その日がカレンダーに入ります。'],
      ['#grid .card', 'カードは、ドラッグで動かせます。スマホは、長く押してから動かします。'],
      ['header.site nav a[href="/calendar/"]', '入れた予定は、ここのカレンダーで見られます。'],
      ['header.site nav a[href="/add/"]', '自分の予定や記念日は、ここから入れます。']
    ],
    calendar: [
      ['.cal-tools', '「月」と「一覧」を切りかえられます。'],
      ['.cal-grid', '日を押すと、下に、その日の予定とやることが出ます。'],
      ['#day-panel .btn', 'この日に予定を追加できます。入れた予定を押すと、メモや「何日前までにやること」を書けます。']
    ],
    plan: [
      ['#p-memo', '持ち物や場所など、メモを書けます。自動で保存されます。'],
      ['#t-text', '「何日前までに何をするか」を書き込めます。期限の日が、カレンダーとホームに出ます。'],
      ['.plan-card .c-act', '予定を消すときは、ここです。']
    ],
    add: [
      ['#s1 .tile', 'まず、どんな日かを選びます。デートや会議なら「予定」です。']
    ],
    search: [
      ['#q', '言葉を入れると、日付が出ます。ジャンルでしぼることもできます。'],
      ['[data-g-chip]', 'ジャンルをえらぶと、そのジャンルだけが出ます。']
    ]
  };
  var steps = TOURS[page];
  if (!steps) return;
  var idx = 0, live = [], shade, hole, tip, btn;

  function seen() { var t = A.state().prefs.tour || {}; return !!t[page]; }
  function markSeen() { var st = A.state(); st.prefs.tour = st.prefs.tour || {}; st.prefs.tour[page] = true; A.persist(); }
  function visible(el) { var r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'; }
  function usable() {
    return steps.map(function (s) { var el = document.querySelector(s[0]); return el && visible(el) ? { el: el, text: s[1] } : null; }).filter(Boolean);
  }
  function place() {
    if (!live[idx]) return;
    var el = live[idx].el, r = el.getBoundingClientRect(), pad = 6;
    hole.style.left = Math.max(0, r.left - pad) + 'px'; hole.style.top = Math.max(0, r.top - pad) + 'px';
    hole.style.width = (r.width + pad * 2) + 'px'; hole.style.height = (r.height + pad * 2) + 'px';
    var below = (r.top + r.height / 2) < window.innerHeight * 0.5;
    tip.className = 'guide-tip ' + (below ? 'at-bottom' : 'at-top');
  }
  function show() {
    var step = live[idx], last = idx === live.length - 1;
    step.el.scrollIntoView({ block: 'center', behavior: 'instant' });  // not smooth: the spotlight must not lag behind the page
    tip.innerHTML = '<p class="g-n">' + (idx + 1) + ' / ' + live.length + '</p><p class="g-t">' + H(step.text) + '</p>' +
      '<div class="g-b"><button type="button" class="btn small ghost" data-g="close">とじる</button>' +
      (idx > 0 ? '<button type="button" class="btn small ghost" data-g="prev">戻る</button>' : '') +
      '<button type="button" class="btn small" data-g="next">' + (last ? 'おわり' : '次へ') + '</button></div>';
    place();
    var nb = tip.querySelector('[data-g="next"]');
    if (nb) nb.focus({ preventScroll: true });
  }
  function stop(done) {
    [shade, hole, tip].forEach(function (e) { if (e && e.parentNode) e.parentNode.removeChild(e); });
    shade = hole = tip = null;
    window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true); document.removeEventListener('keydown', onKey);
    markSeen();
    if (done) A.stat('act:guide_done');
  }
  function onKey(ev) { if (ev.key === 'Escape') stop(false); else if (ev.key === 'ArrowRight') go(1); else if (ev.key === 'ArrowLeft') go(-1); }
  function go(d) {
    if (!tip) return;
    var n = idx + d;
    if (n >= live.length) { stop(true); return; }
    if (n < 0) return;
    idx = n; show();
  }
  function start() {
    if (tip) return;
    live = usable();
    if (!live.length) return;
    idx = 0;
    shade = document.createElement('div'); shade.className = 'guide-shade';
    hole = document.createElement('div'); hole.className = 'guide-hole';
    tip = document.createElement('div'); tip.className = 'guide-tip'; tip.setAttribute('role', 'dialog'); tip.setAttribute('aria-label', 'この画面の使い方ガイド'); tip.tabIndex = -1;
    document.body.appendChild(shade); document.body.appendChild(hole); document.body.appendChild(tip);
    shade.addEventListener('click', function () { stop(false); });
    tip.addEventListener('click', function (ev) {
      var b = ev.target.closest ? ev.target.closest('[data-g]') : null;
      if (!b) return;
      var a = b.getAttribute('data-g');
      if (a === 'close') stop(false); else go(a === 'next' ? 1 : -1);
    });
    window.addEventListener('resize', place); window.addEventListener('scroll', place, true); document.addEventListener('keydown', onKey);
    A.stat('act:guide_start');
    show();
  }
  btn = document.createElement('button');
  btn.type = 'button'; btn.className = 'guide-btn'; btn.setAttribute('aria-label', 'この画面の使い方ガイドを見る'); btn.innerHTML = '<span aria-hidden="true">?</span> ガイド';
  btn.addEventListener('click', start);
  document.body.appendChild(btn);
  document.addEventListener('click', function (ev) { var b = ev.target.closest ? ev.target.closest('[data-guide]') : null; if (b) start(); });
  window.AtomouGuide = { start: start, steps: steps };
  // by itself, once per page, after the page has drawn its cards (and never in the tests, which pass ?today=)
  if (!P.today && !seen() && P.guide !== '0') setTimeout(start, 1200);
  else if (P.guide === '1') setTimeout(start, 600);
})();
