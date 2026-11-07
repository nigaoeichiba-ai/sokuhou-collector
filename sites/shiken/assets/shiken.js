/* shiken-nittei.com: search, the three views, the saved exams (this browser only), the counters, the cost and the study-plan tools.
   Nothing is sent to a server.  Dates are read from the page's JSON (#shiken-data) and counted from today in Japan (Asia/Tokyo). */
(function () {
  'use strict';
  var WD = ['日', '月', '火', '水', '木', '金', '土'];
  var TYPE = { application_start: '申込開始', application_deadline: '申込締切', exam: '試験日', announcement: '合格発表' };
  var KEY = 'shiken_my_exams_v1';
  var MAX = 20;
  var override = null;
  var DATA = { events: [], cards: [] };

  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function iso(y, m, d) { return y + '-' + pad(m) + '-' + pad(d); }
  function parse(s) { var p = s.split('-'); return Date.UTC(+p[0], +p[1] - 1, +p[2]); }
  function today() {
    if (override) return override;
    var t = new Date(Date.now() + 9 * 3600 * 1000);
    return iso(t.getUTCFullYear(), t.getUTCMonth() + 1, t.getUTCDate());
  }
  function diff(a, b) { return Math.round((parse(a) - parse(b)) / 86400000); }
  function left(s) { return diff(s, today()); }
  function wd(s) { return WD[new Date(parse(s)).getUTCDay()]; }
  function md(s) { var p = s.split('-'); return (+p[1]) + '月' + (+p[2]) + '日(' + wd(s) + ')'; }
  function state(n, kind) {
    if (n < 0) return { cls: 'past', label: '' };
    if (n === 0) return { cls: kind === 'deadline' ? 'today' : 'examday', label: '' };
    if (kind === 'deadline') return { cls: n <= 7 ? 'red' : n <= 30 ? 'yellow' : 'blue', label: n <= 7 ? 'まもなく締切' : '' };
    return { cls: 'blue', label: '' };
  }
  function norm(s) { return (s || '').normalize('NFKC').toLowerCase().replace(/\s+/g, ''); }

  /* ---------- counters ("あと3日") */
  function counters() {
    $$('[data-countdown]').forEach(function (el) {
      var day = el.getAttribute('data-countdown'), kind = el.getAttribute('data-kind');
      var n = left(day);
      if (kind === 'band') { el.hidden = n < 0 || n > 7; var b = $('b', el); if (b) b.textContent = 'あと' + n + '日'; return; }
      var st = state(n, kind), html;
      if (n > 0) html = 'あと<b class="num">' + n + '</b>日';
      else if (n === 0) html = '<b class="num">本日</b>';
      else html = '<span class="past-text">' + (-n) + '日前に終了</span>';
      if (st.label && n >= 0) html += '<span class="urgent-label">' + st.label + '</span>';
      el.innerHTML = html;
      el.className = 'days ' + st.cls + (el.getAttribute('data-big') !== null || el.classList.contains('big') ? ' big' : '');
      var card = el.closest('.dcard');
      if (card) card.className = 'dcard ' + st.cls;
    });
  }

  /* ---------- search */
  function search() {
    var q = $('#q'); if (!q) return;
    var box = $('#noresult');
    function run() {
      var key = norm(q.value), shown = 0;
      $$('#view-cards .dcard').forEach(function (c) {
        var hit = !key || norm(c.getAttribute('data-name')).indexOf(key) >= 0;
        c.hidden = !hit; if (hit) shown++;
      });
      if (box) box.hidden = !(key && shown === 0);
    }
    q.addEventListener('input', run);
    var f = q.form; if (f) f.addEventListener('submit', function (e) { e.preventDefault(); run(); });
    run();
  }

  /* ---------- the three views */
  var view = 'cards';
  function setView(v) {
    view = v;
    $$('[data-view]').forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-view') === v ? 'true' : 'false'); });
    $$('[data-panel]').forEach(function (p) { p.hidden = p.getAttribute('data-panel') !== v; });
    if (v === 'cal') drawCal();
  }
  function views() {
    $$('[data-view]').forEach(function (b) { b.addEventListener('click', function () { setView(b.getAttribute('data-view')); }); });
    if ($('[data-view]')) setView('cards');
  }

  /* ---------- month calendar: the deadline cards, and the exams and results of the month */
  var cal = null;
  function calEvents() {
    var ids = {}; DATA.cards.forEach(function (i) { ids[i] = 1; });
    return DATA.events.filter(function (e) { return ids[e.id] || e.type === 'exam' || e.type === 'announcement'; });
  }
  function drawCal() {
    var root = $('#cal'); if (!root) return;
    if (!cal) { var t = today().split('-'); cal = { y: +t[0], m: +t[1] }; }
    var first = new Date(Date.UTC(cal.y, cal.m - 1, 1)), start = first.getUTCDay();
    var days = new Date(Date.UTC(cal.y, cal.m, 0)).getUTCDate();
    var evs = calEvents().filter(function (e) { return e.iso.indexOf(cal.y + '-' + pad(cal.m)) === 0; });
    var by = {}; evs.forEach(function (e) { (by[e.iso] = by[e.iso] || []).push(e); });
    var td = today(), h = '<div class="cal-head"><button type="button" class="btn" data-cal="-1" aria-label="前の月">前の月</button><b>' + cal.y + '年' + cal.m + '月</b><button type="button" class="btn" data-cal="1" aria-label="次の月">次の月</button></div>';
    h += '<table class="cal-grid"><thead><tr>' + WD.map(function (w) { return '<th>' + w + '</th>'; }).join('') + '</tr></thead><tbody><tr>';
    for (var i = 0; i < start; i++) h += '<td class="blank"></td>';
    for (var d = 1; d <= days; d++) {
      var key = iso(cal.y, cal.m, d), list = by[key] || [];
      if ((start + d - 1) % 7 === 0 && d > 1) h += '</tr><tr>';
      h += '<td' + (key === td ? ' class="today"' : '') + '><span class="dn">' + d + (key === td ? '<small>今日</small>' : '') + '</span>';
      list.slice(0, 2).forEach(function (e) { h += '<span class="ev ' + (e.type === 'application_deadline' ? 'dl' : 'ex') + '">' + short(e) + '</span>'; });
      if (list.length > 2) h += '<button type="button" class="more" data-day="' + key + '">＋' + (list.length - 2) + '件</button>';
      if (list.length) h += '<span class="dots" aria-hidden="true">' + list.map(function (e) { return '<i class="' + (e.type === 'application_deadline' ? 'dl' : 'ex') + '"></i>'; }).join('') + '</span>';
      h += '</td>';
    }
    for (var k = (7 - (start + days) % 7) % 7; k > 0; k--) h += '<td class="blank"></td>';
    h += '</tr></tbody></table>';
    var rows = Object.keys(by).sort();
    h += '<ul class="cal-list" aria-label="' + cal.m + '月の日程">' + (rows.length ? rows.map(function (k) {
      return by[k].map(function (e, n) {
        return '<li id="' + (n ? '' : 'cal-day-' + k) + '"><b>' + md(k) + (e.time ? ' ' + e.time : '') + '</b> <a href="' + e.url + '">' + esc(e.name) + ' ' + TYPE[e.type] + '</a> <span class="when-left">' + leftText(k, e.type) + '</span></li>';
      }).join('');
    }).join('') : '<li>この月の日程は載っていません。前の月・次の月を見てください。</li>') + '</ul>';
    root.innerHTML = h;
    $$('[data-cal]', root).forEach(function (b) { b.addEventListener('click', function () {
      cal.m += +b.getAttribute('data-cal'); if (cal.m < 1) { cal.m = 12; cal.y--; } if (cal.m > 12) { cal.m = 1; cal.y++; } drawCal(); }); });
    $$('[data-day]', root).forEach(function (b) { b.addEventListener('click', function () {
      var li = document.getElementById('cal-day-' + b.getAttribute('data-day')); if (li) { li.scrollIntoView({ block: 'center' }); li.classList.add('flash'); } }); });
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function short(e) { return esc(e.name.replace(/国家試験|\(第\d+回\)|（第\d+回）/g, '').replace(/\s+/g, ' ').trim()) + ' ' + TYPE[e.type]; }
  function leftText(day, type) {
    var n = left(day);
    return n > 0 ? 'あと' + n + '日' : n === 0 ? '本日' : (-n) + '日前に終了';
  }

  /* ---------- saved exams (this browser only) */
  function load() {
    try { var o = JSON.parse(localStorage.getItem(KEY) || 'null'); if (o && o.version === 1 && Array.isArray(o.items)) return o.items; } catch (e) { /* private mode */ }
    return [];
  }
  function save(items) { try { localStorage.setItem(KEY, JSON.stringify({ version: 1, items: items })); return true; } catch (e) { return false; } }
  function has(items, id) { return items.some(function (i) { return i.examId === id; }); }
  function nextEvent(examId) {
    var td = today(), best = null;
    DATA.events.forEach(function (e) {
      if (e.exam !== examId || e.iso < td || e.type === 'application_start') return;
      var rank = e.type === 'application_deadline' ? 0 : 1;
      if (!best || rank < best.rank || (rank === best.rank && e.iso < best.e.iso)) best = { rank: rank, e: e };
    });
    return best && best.e;
  }
  function nameOf(examId) {
    var f = DATA.events.filter(function (e) { return e.exam === examId; })[0];
    return f ? f.name : examId;
  }
  function renderMy(msg) {
    var items = load();
    $$('.js-my').forEach(function (b) {
      var on = has(items, b.getAttribute('data-exam'));
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.classList.toggle('added', on);
      b.textContent = on ? 'マイ試験から外す' : 'マイ試験に追加';
    });
    var list = $('#mylist'); if (!list) return;
    var note = $('#my-msg'); if (note) note.textContent = msg || '';
    if (!items.length) { list.innerHTML = '<li class="myempty">気になる試験を保存すると、ここに残り日数が並びます。</li>'; var c0 = $('#my-clear'); if (c0) c0.hidden = true; return; }
    var rows = items.map(function (it) { return { it: it, e: nextEvent(it.examId) }; }).sort(function (a, b) { return (a.e ? a.e.iso : '9999') < (b.e ? b.e.iso : '9999') ? -1 : 1; });
    list.innerHTML = rows.map(function (r) {
      var url = r.e ? r.e.url : (DATA.events.filter(function (e) { return e.exam === r.it.examId; })[0] || { url: '/schedule/' }).url;
      var when = r.e ? '<span class="my-when">' + TYPE[r.e.type] + ' ' + md(r.e.iso) + (r.e.time ? ' ' + r.e.time : '') + '</span><b class="my-left">' + leftText(r.e.iso) + '</b>'
        : '<span class="my-when">載っている日程はすべて終わりました</span>';
      return '<li class="myitem"><a href="' + url + '">' + esc(nameOf(r.it.examId)) + '</a>' + when + '<button type="button" class="btn" data-remove="' + esc(r.it.examId) + '">解除</button></li>';
    }).join('');
    $$('[data-remove]', list).forEach(function (b) { b.addEventListener('click', function () { toggle(b.getAttribute('data-remove')); }); });
    var c = $('#my-clear'); if (c) c.hidden = false;
  }
  function toggle(examId) {
    var items = load();
    if (has(items, examId)) { items = items.filter(function (i) { return i.examId !== examId; }); save(items); renderMy(); return; }
    if (items.length >= MAX) { renderMy('上限の' + MAX + '件に達しています。不要な試験を外してください'); return; }
    items.push({ examId: examId, addedAt: new Date().toISOString() });
    if (!save(items)) { renderMy('このブラウザでは保存できませんでした。プライベートモードでは保存されません。'); return; }
    renderMy();
  }
  function mine() {
    $$('.js-my').forEach(function (b) { b.addEventListener('click', function () { toggle(b.getAttribute('data-exam')); }); });
    var c = $('#my-clear');
    if (c) c.addEventListener('click', function () { if (window.confirm('保存した試験をすべて削除します。よろしいですか。')) { save([]); renderMy(); } });
    renderMy();
  }

  /* ---------- cost */
  function cost() {
    var root = $('#cost'); if (!root) return;
    var fee = +root.getAttribute('data-fee'), warn = $('[data-cost-warn]', root);
    function run() {
      var sum = fee, bad = false;
      $$('[data-cost]', root).forEach(function (i) {
        var v = parseFloat(i.value);
        if (i.value !== '' && (isNaN(v) || v < 0)) bad = true;
        sum += (isNaN(v) || v < 0) ? 0 : Math.round(v);
      });
      $('[data-total]', root).textContent = sum.toLocaleString('ja-JP');
      if (warn) warn.hidden = !bad;
    }
    $$('[data-cost]', root).forEach(function (i) { i.addEventListener('input', run); });
    run();
  }

  /* ---------- study plan: days needed = ceil(H / ((a*5 + b*2) / 7)); start = target - days */
  function plan() {
    var root = $('#planner'); if (!root) return;
    var out = $('[data-plan-out]', root);
    function run() {
      var dv = $('[data-plan-date]', root).value, H = parseFloat($('[data-plan-total]', root).value);
      var a = parseFloat($('[data-plan-weekday]', root).value), b = parseFloat($('[data-plan-weekend]', root).value);
      if (isNaN(b)) b = 0;
      if (!dv || !(H > 0) || !(a >= 0) || isNaN(a)) { out.innerHTML = '<p>目標日、総学習時間、平日の学習時間を入れると、勉強を始める日の目安が出ます。</p>'; return; }
      var week = a * 5 + b * 2;
      if (!(week > 0)) { out.innerHTML = '<p>学習時間が0のままでは計算できません。</p>'; return; }
      var td = today(), D = diff(dv, td), need = Math.ceil(H / (week / 7));
      if (D < 0) { out.innerHTML = '<p class="bad">目標日が今日より前です。日付を確かめてください。</p>'; return; }
      var startMs = parse(dv) - need * 86400000, s = new Date(startMs), sIso = iso(s.getUTCFullYear(), s.getUTCMonth() + 1, s.getUTCDate());
      var fin = new Date(parse(td) + need * 86400000), fIso = iso(fin.getUTCFullYear(), fin.getUTCMonth() + 1, fin.getUTCDate());
      var h = '<p><b>今日から目標日まで：</b>' + (D >= 0 ? D + '日' : '目標日が過ぎています') + '</p>' +
        '<p><b>週のペース：</b>週' + (Math.round(week * 10) / 10) + '時間</p>' +
        '<p><b>必要な日数：</b>' + need + '日（総' + H + '時間 ÷ 1日平均' + (Math.round(week / 7 * 100) / 100) + '時間）</p>' +
        '<p><b>勉強を始める日：</b>' + md(sIso).replace(/^/, s.getUTCFullYear() + '年') + 'までに始めると、目標日に間に合います。</p>' +
        '<p><b>今日から始めた場合の完了の見込み：</b>' + fin.getUTCFullYear() + '年' + md(fIso) + '</p>';
      if (D < 0) h += '<p class="bad">目標日が今日より前です。日付を確かめてください。</p>';
      else if (need > D) {
        var short = H - D * week / 7, extra = short / Math.max(D, 1);
        h += '<p class="bad">このペースでは、あと' + (Math.round(short * 10) / 10) + '時間不足しています。1日あたり' + (Math.round(extra * 10) / 10) + '時間の上乗せが必要です。</p>';
      } else h += '<p class="ok">このペースで、目標日に間に合います。</p>';
      out.innerHTML = h;
    }
    $$('input', root).forEach(function (i) { i.addEventListener('input', run); });
  }

  /* ---------- a field filter on the lists */
  function chips() {
    $$('[data-chip]').forEach(function (b) { b.addEventListener('click', function () {
      var v = b.getAttribute('data-chip');
      $$('[data-chip]').forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
      $$('[data-cat]').forEach(function (c) { c.hidden = !(v === 'all' || c.getAttribute('data-cat') === v); });
    }); });
  }

  function init() {
    var el = document.getElementById('shiken-data');
    if (el) { try { DATA = JSON.parse(el.textContent); } catch (e) { /* the page still reads without it */ } }
    counters(); search(); views(); mine(); cost(); plan(); chips();
  }
  window.Shiken = { setToday: function (s) { override = s; counters(); if (cal) { cal = null; } if (view === 'cal') drawCal(); renderMy(); }, today: today, left: left, state: state };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
}());
