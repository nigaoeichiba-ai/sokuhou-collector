/* 案3 "桜と紅葉の、例年の日" (/kyou/sakura/): the visitor chooses a station of the Japan Meteorological Agency (the one of their prefecture when they chose one on the setup); for each of the four series
   the page shows the Agency's normal day, the mean of the last ten years, the earliest and the latest day, the days still to go to the normal day, and the last ten years as small dots.
   The numbers are in the page (id "ph-data", made at build time by sites/atomou/phenology.py).  Only the past is shown: nothing here forecasts a bloom or a colour. */
(function (root) {
  'use strict';
  var C = root.AtomouCore;

  function md(n) { return Math.floor(n / 100) + '月' + (n % 100) + '日'; }
  function dayOf(mmdd, y) { return [y, Math.floor(mmdd / 100), mmdd % 100]; }

  // the dots of the last ten years on one line of the season (the places "ro" were counted by the build, see phenology.ordinal): later days are lower
  function dots(row, last) {
    var pts = [], lo = 1e9, hi = -1e9;
    row.ro.forEach(function (v) { if (v) { lo = Math.min(lo, v); hi = Math.max(hi, v); } });
    if (!isFinite(lo) || row.ro.filter(Boolean).length < 3) return '';
    var span = Math.max(1, hi - lo), label = [];
    row.ro.forEach(function (v, i) {
      if (!v) return;
      var y = last - 9 + i;
      pts.push('<circle cx="' + (12 + i * 22) + '" cy="' + (8 + (v - lo) / span * 36).toFixed(1) + '" r="4"></circle>');
      label.push(y + '年 ' + md(row.recent[i]));
    });
    return '<svg class="ph-dots" viewBox="0 0 232 52" role="img" aria-label="直近10年: ' + label.join('、') + '。下ほど遅い日です。" focusable="false">' + pts.join('') + '</svg>';
  }

  function init() {
    var A = root.AtomouApp, box = A && A.page === 'special' ? A.$('#pheno') : null, blob = box ? A.$('#ph-data') : null;
    if (!box || !blob) return;
    var data, H = A.H, today = A.TODAY, sel = A.$('#ph-st'), out = A.$('#ph-out');
    try { data = JSON.parse(blob.textContent); } catch (e) { return; }
    var names = [];
    data.items.forEach(function (it) { it.stations.forEach(function (s) { if (names.indexOf(s.n) < 0) names.push(s.n); }); });
    var region = (A.state().prefs || {}).region, mine = data.map && data.map[region], start = names.indexOf(mine) >= 0 ? mine : '東京';
    sel.innerHTML = names.map(function (n) { return '<option value="' + H(n) + '"' + (n === start ? ' selected' : '') + '>' + H(n) + '</option>'; }).join('');

    function next(mmdd) {   // the next time that day of the year comes (this year, or next year when it has passed)
      var t = dayOf(mmdd, today[0]);
      if (C.cmp(t, today) < 0) t = dayOf(mmdd, today[0] + 1);
      return { n: C.totalDays(today, t), nextYear: t[0] !== today[0] };
    }
    function render() {
      var name = sel.value, h = '<h2>' + H(name) + '</h2>';
      data.items.forEach(function (it) {
        var row = it.stations.filter(function (s) { return s.n === name; })[0];
        if (!row) { h += '<section class="ph-item"><h3>' + H(it.name) + '</h3><p class="muted">この地点では、いま観測していません。</p></section>'; return; }
        var base = row.normal || row.usual, c = base ? next(base) : null;
        h += '<section class="ph-item"><h3>' + H(it.name) + '</h3><ul>' +
          (row.normal ? '<li>平年(気象庁、1991〜2020年): <b>' + md(row.normal) + '</b>ごろ</li>' : '') +
          (row.usual ? '<li>直近10年の平均: <b>' + md(row.usual) + '</b>ごろ</li>' : '') +
          '<li>いちばん早い日: ' + md(row.early[0]) + '(' + row.early[1] + '年) / いちばん遅い日: ' + md(row.late[0]) + '(' + row.late[1] + '年)</li></ul>' +
          (c ? '<p>' + (row.normal ? '平年' : '例年') + 'の日(' + md(base) + ')まで、' + (c.n === 0 ? '<b>今日</b>です。' : (c.nextYear ? '来年の同じ日まで、' : '') + 'あと<b>' + c.n + '日</b>です。') + '</p>' : '') +
          dots(row, data.last) + '</section>';
      });
      out.innerHTML = h + '<p class="hint">これは過去の記録です。今年の時期の予想ではありません。</p>';
    }
    sel.addEventListener('change', render);
    render();
  }

  root.AtomouPheno = { init: init, md: md };
  if (root.document) { if (root.AtomouApp) init(); else root.addEventListener('load', init); }
})(typeof window !== 'undefined' ? window : this);
