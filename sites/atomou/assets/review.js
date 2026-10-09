/* The review build of the site (see sites/atomou/review.py) has no application: this only recounts the days on the cards for the visitor's own date
   (the build wrote them for the build date).  It needs core.js before it. */
(function () {
  'use strict';
  var C = window.AtomouCore;
  if (!C) return;
  var n = new Date(), TODAY = [n.getFullYear(), n.getMonth() + 1, n.getDate()];
  function split(r) {
    var w = r.big.slice(0, 2);
    return (w === 'あと' || w === 'もう') ? [w, r.big.slice(2)] : ['', r.big];
  }
  document.querySelectorAll('.card[data-date]').forEach(function (card) {
    var d = C.parse(card.getAttribute('data-date')), p = card.getAttribute('data-p') || 'day';
    if (!d) return;
    var r = C.countdown(d, TODAY, p), w = split(r), word = card.querySelector('.word'), num = card.querySelector('.num'), sub = card.querySelector('.c-sub'), rl = card.querySelector('.rel'), t = r.total;
    card.setAttribute('data-dir', r.dir);
    card.setAttribute('data-long', w[1].length > 5 ? '1' : '0');
    if (word) word.textContent = w[0];
    if (num) num.textContent = w[1];
    if (sub) sub.textContent = r.sub ? '合計 ' + r.sub : '';
    if (rl) rl.textContent = (p === 'day' && t != null) ? (t === 1 ? '(明日)' : t === 2 ? '(明後日)' : t === -1 ? '(昨日)' : t === -2 ? '(おととい)' : '') : '';
  });
})();
