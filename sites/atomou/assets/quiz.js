/* 案4 「今日の1問」: one small question a day, made from the date alone (no server, no AI, nothing sent).  The same date gives the same question and the same order of choices.
   The answer is always shown with its reason; one of the questions is about an official day of the catalogue and links to its page.  A quiet day is never asked about.
   What was answered is kept on this device only (localStorage "atomou.q.v1"), as 1 or 0 for each date, for the last 100 days. */
(function (root) {
  'use strict';
  var C = root.AtomouCore;
  var WD = ['月', '火', '水', '木', '金', '土', '日'];

  function md(a) { return a[1] + '月' + a[2] + '日'; }
  function mdw(a) { return md(a) + '(' + WD[C.weekday(a)] + ')'; }
  function uniq(list, not) { var out = []; list.forEach(function (x) { if (x !== not && out.indexOf(x) < 0) out.push(x); }); return out; }
  function nums(n, deltas, min) {   // wrong answers near a number: n + each delta, at least min, not n itself
    return uniq(deltas.map(function (d) { return n + d; }).filter(function (x) { return x >= min; }), n);
  }

  function firstAfter(list, t) {   // the earliest [name, iso] after today, whatever order the list came in
    var best = null;
    (list || []).forEach(function (x) { var d = C.parse(x[1]); if (d && C.cmp(d, t) > 0 && (!best || x[1] < best[1])) best = x; });
    return best;
  }

  // each maker returns {q, ans, wrong:[...], why, link} or null when the data for it is missing; the strings are shown as they are
  var MAKERS = {
    holiday: function (t, D) {
      var h = firstAfter(D.hol, t);
      if (!h) return null;
      var d = C.parse(h[1]), n = C.totalDays(t, d);
      return { q: '今日から数えて、次の祝日まであと何日?', ans: n + '日', wrong: nums(n, [1, -1, 2, -2, 7, 3, -3], 1).map(function (x) { return x + '日'; }),
        why: '次の祝日は「' + h[0] + '」(' + mdw(d) + ')です。今日から' + n + '日後です。' };
    },
    sat: function (t) {
      var n = C.weekdaysLeft(t, 5);
      return { q: t[0] + '年の残りで、今日より後の土曜日は、あと何回?', ans: n + '回', wrong: nums(n, [1, 2, -1, 3, -2], 0).map(function (x) { return x + '回'; }),
        why: '今日(' + mdw(t) + ')より後、12月31日までに、土曜日は' + n + '回あります。' };
    },
    doy: function (t) {
      var n = C.dayOfYear(t)[0];
      return { q: '今日(' + md(t) + ')は、今年の何日目?', ans: n + '日目', wrong: nums(n, [1, -1, 7, -7, 10, 30], 1).map(function (x) { return x + '日目'; }),
        why: t[0] + '年1月1日を1日目と数えると、' + md(t) + 'は' + n + '日目です。' };
    },
    xmas: function (t) {
      var y = t[1] === 12 && t[2] > 25 ? t[0] + 1 : t[0], w = C.weekday([y, 12, 25]);
      return { q: y + '年のクリスマス(12月25日)は、何曜日?', ans: WD[w] + '曜日', wrong: WD.filter(function (x, i) { return i !== w; }).map(function (x) { return x + '曜日'; }),
        why: y + '年12月25日は' + WD[w] + '曜日です。' };
    },
    plus100: function (t) {
      var d = C.addDays(t, 100);
      return { q: '今日(' + md(t) + ')から100日後は、何月何日?', ans: md(d), wrong: uniq([-1, 1, -7, 10, 7].map(function (k) { return md(C.addDays(d, k)); }), md(d)),
        why: '今日(' + mdw(t) + ')に100日を足すと、' + mdw(d) + 'です。' };
    },
    nextmonth: function (t) {
      var m = t[1] % 12 + 1, y = t[1] === 12 ? t[0] + 1 : t[0], n = C.dim(y, m);
      return { q: m + '月は、何日まである?', ans: n + '日', wrong: [28, 29, 30, 31].filter(function (x) { return x !== n; }).map(function (x) { return x + '日'; }),
        why: y + '年' + m + '月は' + n + '日までです。' };
    },
    term: function (t, D) {
      var s = firstAfter(D.terms, t);
      if (!s) return null;
      var d = C.parse(s[1]), n = C.totalDays(t, d);
      return { q: '次の二十四節気「' + s[0] + '」まで、あと何日?', ans: n + '日', wrong: nums(n, [1, -1, 2, -2, 5, 3], 1).map(function (x) { return x + '日'; }),
        why: '「' + s[0] + '」は' + mdw(d) + 'です(国立天文台の暦要項)。今日から' + n + '日後です。' };
    },
    card: function (t, D) {   // an official day of the catalogue in the next 120 days: a full date, not an estimate, not a quiet day
      var list = (D.cards || []).filter(function (c) {
        var d = C.parse(c.date), n = d ? C.totalDays(t, d) : -1;
        return d && (c.precision || 'day') === 'day' && !c.quiet && !c.estimated && n > 0 && n <= 120;
      }).sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : a.id < b.id ? -1 : 1; });
      if (!list.length) return null;
      var c = list[C.toDays(t[0], t[1], t[2]) % list.length], d = C.parse(c.date), w = C.weekday(d);
      return { q: '「' + c.title + '」の日(' + md(d) + ')は、何曜日?', ans: WD[w] + '曜日', wrong: WD.filter(function (x, i) { return i !== w; }).map(function (x) { return x + '曜日'; }),
        why: md(d) + 'は' + WD[w] + '曜日です。出典と確認した日は、日付のページにあります。', link: '/e/' + c.id + '/' };
    }
  };
  var ORDER = ['holiday', 'sat', 'doy', 'xmas', 'plus100', 'nextmonth', 'term', 'card'];

  // today: [y, m, d]; data: {hol:[[name, iso]], terms:[[name, iso]], cards:[{id, title, date, precision, quiet, estimated}]}
  function make(today, data) {
    data = data || {};
    var seed = C.toDays(today[0], today[1], today[2]), start = seed % ORDER.length, made = null, type = '';
    for (var k = 0; k < ORDER.length && !made; k++) { type = ORDER[(start + k) % ORDER.length]; made = MAKERS[type](today, data); }
    if (!made) return null;
    var wrong = made.wrong.slice(), pick = [];
    var off = seed % wrong.length;
    for (var i = 0; i < 3 && wrong.length; i++) pick.push(wrong[(off + i) % wrong.length]);
    pick = uniq(pick, made.ans);
    while (pick.length < 3 && wrong.length > pick.length) { var extra = wrong.filter(function (x) { return pick.indexOf(x) < 0; })[0]; if (!extra) break; pick.push(extra); }
    var pos = seed % (pick.length + 1), choices = pick.slice();
    choices.splice(pos, 0, made.ans);
    return { type: type, date: C.iso(today), q: made.q, choices: choices, ans: pos, why: made.why, link: made.link || '' };
  }

  var KEY = 'atomou.q.v1';
  function load() {
    try {
      var o = JSON.parse(localStorage.getItem(KEY) || '{}'), d = {};
      Object.keys((o && o.d) || {}).forEach(function (k) { if (/^\d{4}-\d{2}-\d{2}$/.test(k) && (o.d[k] === 0 || o.d[k] === 1)) d[k] = o.d[k]; });
      return { d: d };
    } catch (e) { return { d: {} }; }
  }
  function save(st) {
    var keys = Object.keys(st.d).sort().slice(-100), d = {};
    keys.forEach(function (k) { d[k] = st.d[k]; });
    try { localStorage.setItem(KEY, JSON.stringify({ d: d })); } catch (e) { /* the page works without it */ }
  }
  function weekCount(st, today) {   // how many of the days from this week's Monday to today were answered
    var n = 0, back = C.weekday(today);
    for (var i = 0; i <= back; i++) if (st.d[C.iso(C.addDays(today, -i))] !== undefined) n++;
    return n;
  }

  function init() {
    var A = root.AtomouApp, box = A && A.page === 'quiz' ? A.$('#quiz') : null;
    if (!box) return;
    var H = A.H, today = A.TODAY, hol = [], terms = [];
    try { hol = JSON.parse(box.getAttribute('data-hol') || '[]'); terms = JSON.parse(box.getAttribute('data-terms') || '[]'); } catch (e) { /* the questions that need no data remain */ }
    A.loadCatalog().then(function (cat) {
      var Q = make(today, { hol: hol, terms: terms, cards: cat || [] });
      if (!Q) { box.innerHTML = '<p>今日の問題を用意できませんでした。</p>'; return; }
      var st = load(), done = st.d[Q.date];
      function draw(chosen) {
        var answered = chosen !== null && chosen !== undefined, ok = answered && chosen === Q.ans;
        var h = '<p class="quiz-q" id="quiz-q">' + H(Q.q) + '</p><div class="quiz-choices" role="group" aria-labelledby="quiz-q">' + Q.choices.map(function (c, i) {
          var cls = 'btn ghost' + (answered && i === Q.ans ? ' quiz-right' : '') + (answered && i === chosen && !ok ? ' quiz-wrong' : '');
          return '<button type="button" class="' + cls + '" data-i="' + i + '"' + (answered ? ' disabled' : '') + '>' + H(c) + '</button>';
        }).join('') + '</div>';
        if (answered) {
          h += '<div class="quiz-result" aria-live="polite"><p><b>' + (ok ? '正解です。' : 'ざんねん。答えは「' + H(Q.choices[Q.ans]) + '」です。') + '</b></p><p>' + H(Q.why) + '</p>' +
            (Q.link ? '<p><a class="btn small ghost" href="' + H(Q.link) + '">この日のページを見る</a></p>' : '') +
            '<p class="muted">今週は ' + weekCount(st, today) + '回 答えました。お休みしても、何も失いません。</p>' +
            '<p><button type="button" class="btn small" id="quiz-share">結果を送る(○×だけ)</button></p></div>';
        }
        box.innerHTML = h;
      }
      draw(done === undefined ? null : (done === 1 ? Q.ans : -1));
      box.addEventListener('click', function (ev) {
        var b = ev.target.closest ? ev.target.closest('button') : null;
        if (!b) return;
        if (b.hasAttribute('data-i') && st.d[Q.date] === undefined) {
          var i = +b.getAttribute('data-i');
          st.d[Q.date] = i === Q.ans ? 1 : 0; save(st); draw(i);
        } else if (b.id === 'quiz-share') {
          var text = '「あと何日、もう何日」今日の1問 ' + (st.d[Q.date] === 1 ? '○' : '×') + ' ' + location.origin + '/quiz/';
          if (navigator.share) navigator.share({ text: text }).catch(function () { /* cancelled */ });
          else if (navigator.clipboard) navigator.clipboard.writeText(text).then(function () { A.toast('コピーしました。'); }, function () { A.toast('コピーできませんでした。'); });
        }
      });
    });
  }

  root.AtomouQuiz = { make: make, ORDER: ORDER, init: init, weekCount: weekCount };
  if (root.document) {
    if (root.AtomouApp) init(); else root.addEventListener('load', init);
  }
})(typeof window !== 'undefined' ? window : this);
