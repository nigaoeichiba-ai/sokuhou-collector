'use strict';
/* The monthly calendars (see redesign/schedule.py).  The page is complete without this script: the grid of the first month and the list of every month are written into the HTML.
   Here: month to month, filters, the day's detail, and "開催中 / あとN日", all from the visitor's own clock (Japan time), never from the build. */
(function () {
  var WD = '月火水木金土日', KIND = { confirmed: ['確定', '●'], expected: ['例年の予想', '◇'], regular: ['毎月の定例', '↻'], notice: ['発表予定日', '▲'] };
  var MALL = {};
  function jstNow() { return new Date(Date.now() + 9 * 3600 * 1000); }
  function todayIso() { return jstNow().toISOString().slice(0, 10); }
  function pad(n) { return n < 10 ? '0' + n : '' + n; }
  function iso(y, m, d) { return y + '-' + pad(m) + '-' + pad(d); }
  function dayNo(s) { var p = s.split('-'); return Date.UTC(+p[0], +p[1] - 1, +p[2]) / 86400000; }
  function wd(s) { var p = s.split('-'); return WD[(new Date(Date.UTC(+p[0], +p[1] - 1, +p[2])).getUTCDay() + 6) % 7]; }
  function jp(s) { var p = s.split('-'); return +p[1] + '月' + +p[2] + '日(' + wd(s) + ')'; }
  function esc(t) { return String(t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  document.querySelectorAll('[data-cal]').forEach(function (root) {
    var data = JSON.parse(root.querySelector('.cal-data').textContent), items = data.items;
    var ym = root.dataset.ym, minYm = data.min, maxYm = data.max;
    var tbody = function () { return root.querySelector('.cal-grid tbody'); };
    var kinds = {}, malls = {}, segs = {};
    MALL = data.ent;
    Object.keys(KIND).forEach(function (k) { kinds[k] = true; });
    Object.keys(MALL).forEach(function (k) { malls[k] = true; });
    Object.keys(data.seg).forEach(function (k) { segs[k] = true; });
    root.querySelector('.cal-controls').hidden = false;
    root.querySelector('.cal-all').hidden = false;
    var showAll = false;

    function covers(it, day) { if (it.d) return it.d.indexOf(day) >= 0; return !!it.s && it.s <= day && day <= it.e; }
    function visible(it) { return kinds[it.k] && malls[it.m] && segs[it.g]; }
    function mk(it) {
      var t = MALL[it.m][0] + ' ' + KIND[it.k][0] + ' ' + it.t;
      return '<li class="cal-mk k-' + it.k + '" title="' + esc(t) + '"><span aria-hidden="true">' + MALL[it.m][1] + KIND[it.k][1] + '</span><span class="sr">' + esc(t) + '</span></li>';
    }
    function drawGrid() {
      var p = ym.split('-'), y = +p[0], m = +p[1], first = new Date(Date.UTC(y, m - 1, 1)), lead = (first.getUTCDay() + 6) % 7, last = new Date(Date.UTC(y, m, 0)).getUTCDate();
      var today = todayIso(), rows = '', n = 0, cells = Math.ceil((lead + last) / 7) * 7;
      for (var i = 0; i < cells; i++) {
        var day = i - lead + 1, inm = day >= 1 && day <= last;
        if (i % 7 === 0) rows += '<tr>';
        if (!inm) { rows += '<td class="cal-day is-out" aria-hidden="true"><span class="cal-num"></span></td>'; }
        else {
          var s = iso(y, m, day), list = items.filter(function (it) { return visible(it) && covers(it, s); });
          list.sort(function (a, b) { return ((a.d || a.s === s) ? 0 : 1) - ((b.d || b.s === s) ? 0 : 1); });
          var marks = list.slice(0, 3).map(mk).join('') + (list.length > 3 ? '<li class="cal-more">+' + (list.length - 3) + '</li>' : '');
          rows += '<td class="cal-day' + (s === today ? ' is-today' : '') + (list.length ? ' has-ev' : '') + '" data-date="' + s + '" tabindex="0" aria-label="' + m + '月' + day + '日' + (list.length ? '、' + list.length + '件' : '') + '"><span class="cal-num">' + day + '</span>' + (marks ? '<ul class="cal-mks">' + marks + '</ul>' : '') + '</td>';
        }
        if (i % 7 === 6) rows += '</tr>';
      }
      tbody().innerHTML = rows;
      root.querySelector('.cal-title').textContent = y + '年' + m + '月';
      root.querySelector('.cal-prev').disabled = ym <= minYm;
      root.querySelector('.cal-next').disabled = ym >= maxYm;
      var det = root.querySelector('.cal-detail'); det.hidden = true; det.innerHTML = '';
    }
    function drawLists() {
      root.querySelectorAll('.cal-month').forEach(function (sec) { sec.hidden = !showAll && sec.dataset.month !== ym; });
      root.querySelectorAll('.cal-item').forEach(function (li) { li.hidden = !(kinds[li.dataset.kind] && malls[li.dataset.mall] && segs[li.dataset.seg]); });
      root.querySelector('.cal-showall').textContent = showAll ? '表示中の月だけにする' : 'すべての月を表示する';
    }
    function draw() { drawGrid(); drawLists(); }
    function go(delta) {
      var p = ym.split('-'), y = +p[0], m = +p[1] + delta;
      if (m < 1) { m = 12; y--; } else if (m > 12) { m = 1; y++; }
      var n = y + '-' + pad(m);
      if (n < minYm || n > maxYm) return;
      ym = n; draw();
    }
    function detail(day) {
      var list = items.filter(function (it) { return visible(it) && covers(it, day); }), det = root.querySelector('.cal-detail');
      var html = '<h4>' + jp(day) + 'の予定</h4>';
      html += list.length ? '<ul>' + list.map(function (it) {
        return '<li><span class="cal-badge k-' + it.k + '">' + KIND[it.k][1] + ' ' + KIND[it.k][0] + '</span> <span class="cal-mall">' + MALL[it.m][0] + '</span> ' + (it.h ? '<a href="' + esc(it.h) + '">' + esc(it.t) + '</a>' : esc(it.t)) + '<br><span class="cal-when">' + esc(it.w) + '</span></li>';
      }).join('') + '</ul>' : '<p>この日に載せられる予定は、いまのところありません。</p>';
      det.innerHTML = html; det.hidden = false;
    }
    root.querySelector('.cal-prev').addEventListener('click', function () { go(-1); });
    root.querySelector('.cal-next').addEventListener('click', function () { go(1); });
    root.querySelector('.cal-today').addEventListener('click', function () { var t = todayIso().slice(0, 7); ym = t < minYm ? minYm : t > maxYm ? maxYm : t; draw(); });
    root.querySelector('.cal-showall').addEventListener('click', function () { showAll = !showAll; drawLists(); });
    root.querySelectorAll('.cal-controls input').forEach(function (inp) {
      inp.addEventListener('change', function () { (inp.dataset.kind ? kinds : inp.dataset.seg ? segs : malls)[inp.dataset.kind || inp.dataset.seg || inp.dataset.mall] = inp.checked; draw(); });
    });
    root.addEventListener('click', function (ev) { var td = ev.target.closest && ev.target.closest('td.cal-day[data-date]'); if (td && !ev.target.closest('a')) detail(td.dataset.date); });
    root.addEventListener('keydown', function (ev) { if ((ev.key === 'Enter' || ev.key === ' ') && ev.target.matches && ev.target.matches('td.cal-day[data-date]')) { ev.preventDefault(); detail(ev.target.dataset.date); } });
    var t0 = todayIso().slice(0, 7); if (t0 >= minYm && t0 <= maxYm) ym = t0;
    draw();
  });

  /* "開催中 / あとN日": the sales and notices of the lists, from the visitor's clock */
  function live() {
    var today = todayIso(), n = dayNo(today);
    document.querySelectorAll('.cal-item[data-s]').forEach(function (li) {
      var el = li.querySelector('[data-live]'); if (!el) return;
      var s = li.dataset.s, e = li.dataset.e, k = li.dataset.kind, txt = '';
      if (k === 'notice') txt = s < today ? '発表の予定日は過ぎました' : s === today ? '本日' : 'あと' + (dayNo(s) - n) + '日';
      else if (k === 'confirmed') txt = e < today ? '終了' : s <= today ? (e === today ? '本日が最終日' : '開催中') : '開始まであと' + (dayNo(s) - n) + '日';
      else if (k === 'expected') txt = s < today ? '' : s === today ? '予想の日は本日' : '予想の日まであと' + (dayNo(s) - n) + '日';
      el.textContent = txt;
    });
    document.querySelectorAll('tr[data-next]').forEach(function (tr) {
      var out = tr.querySelector('[data-next-day]'); if (!out) return;
      var next = (tr.dataset.next || '').split(' ').filter(function (x) { return x >= today; })[0];
      out.textContent = next ? jp(next) + (next === today ? '(本日)' : '(あと' + (dayNo(next) - n) + '日)') : '載せている期間では、これ以降の日はありません';
    });
  }
  live();
})();
