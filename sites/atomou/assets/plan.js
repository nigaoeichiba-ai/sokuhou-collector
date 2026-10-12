/* The schedule book: a month calendar and a list, one page per plan (memo and "do this N days before"), and today's list on the home page.
   Everything stays in this browser (the state of app.js, localStorage "atomou.v1"); nothing here is sent anywhere. */
(function () {
  'use strict';
  var A = window.AtomouApp;
  if (!A) return;
  var C = A.C, H = A.H, $ = A.$, $$ = A.$$, P = A.P, TODAY = A.TODAY, page = A.page;
  var BEFORE = [[0, '当日'], [1, '1日前'], [2, '2日前'], [3, '3日前'], [7, '1週間前'], [14, '2週間前'], [30, '1か月前']];
  function S() { return A.state(); }
  function beforeLabel(n) { for (var i = 0; i < BEFORE.length; i++) if (BEFORE[i][0] === n) return BEFORE[i][1]; return n + '日前'; }
  function wdIdx(a) { return ((C.toDays(a[0], a[1], a[2]) % 7) + 11) % 7; }  // 0 = Sunday
  function md(a) { return a[1] + '月' + a[2] + '日(' + A.wd(a) + ')'; }
  function mic() { return window.AtomouMicHint ? window.AtomouMicHint('') : ''; }   // the small microphone hint under a free-text field
  function rel(d) { var n = C.totalDays(TODAY, d); return n === 0 ? '今日' : n === 1 ? '明日' : n > 1 ? 'あと' + n + '日' : 'もう' + (-n) + '日'; }

  /* ---------- what is in the book ---------- */
  function planItems(cat) {  // the visitor's own days and the official dates they put in the calendar
    var st = S(), items = st.entries.map(A.ownItem), by = {};
    (cat || []).forEach(function (c) { by[c.id] = c; });
    st.saved.forEach(function (id) { if (by[id]) items.push(A.catItem(by[id])); });
    return items;
  }
  function remindPreset(item) {   // the notices that suit the kind of day (a test, a trip and a birthday are not prepared for alike)
    var g = item.g ? (A.CONF.groups || [])[item.g - 1] : '', k = item.own ? ((A.findEntry(item.id) || {}).kind || '') : '';
    if (item.own) return k === 'until' ? [30, 7, 1] : k === 'anniversary' || k === 'birthday' ? [7, 1] : k === 'event' ? [1] : k === 'since' ? [] : [7, 1];
    return g === '学校・資格' ? [30, 14, 7, 1] : g === 'お金・税金・制度' ? [14, 7, 3, 1] : g === '買い物・料金・セール' ? [7, 1] : [7, 1];
  }
  function notesOf(key) { var n = S().notes[key] || { memo: '', tasks: [] }; if (!n.remind) n.remind = []; return n; }
  function setNotes(key, n) {
    var st = S();
    if (!n.memo && !n.tasks.length && !(n.remind && n.remind.length) && !n.mute) delete st.notes[key]; else st.notes[key] = n;
    A.persist();
  }
  function baseOf(it) {  // the date the tasks count back from (a yearly day: its next turn)
    var d = C.parse(it.date);
    if (!d || it.p !== 'day') return null;
    if (it.rep) return C.repNext(d, it.rep, TODAY);   // a weekly or monthly day: its next turn
    return it.yearly ? A.nextYearly(d, TODAY) : d;
  }
  function eventsOn(items, d) {
    var out = [];
    items.forEach(function (it) {
      var dd = C.parse(it.date);
      if (!dd || it.p !== 'day') return;
      if (C.cmp(dd, d) === 0 || (it.yearly && d[0] > dd[0] && C.cmp(A.occ(dd, d[0]), d) === 0) || (it.rep && C.repOn(dd, it.rep, d))) out.push(it);
      else if (it.every100 && !it.quiet) {   // the 100-day marks (100, 200, ...) of a day
        var n = C.totalDays(dd, d);
        if (n >= 100 && n % 100 === 0) out.push(Object.assign({}, it, { title: it.title + ' から' + n + '日', mark: n }));
      }
    });
    return out.sort(function (a, b) { return (a.time || '99') < (b.time || '99') ? -1 : 1; });
  }
  function tasksOn(items, d) {
    var out = [];
    items.forEach(function (it) {
      var b = baseOf(it);
      if (!b) return;
      notesOf(it.key).tasks.forEach(function (t) { if (C.cmp(C.addDays(b, -t.before), d) === 0) out.push({ it: it, t: t }); });
    });
    return out;
  }
  function taskCheckbox(it, t) {
    return '<label><input type="checkbox" data-task="' + H(it.key) + '|' + H(t.id) + '"' + (t.done ? ' checked' : '') + '> ' + H(t.text) + '</label>';
  }
  function toggleTask(key, id, done) {
    var n = notesOf(key);
    n.tasks.forEach(function (t) { if (t.id === id) t.done = done; });
    setNotes(key, n);
    again();
  }
  document.addEventListener('change', function (ev) {
    var c = ev.target;
    if (!c.getAttribute || !c.hasAttribute('data-task')) return;
    var kv = c.getAttribute('data-task').split('|');
    toggleTask(kv[0], kv[1], c.checked);
  });
  var redo = null;
  function again() { if (redo) redo(); }

  /* ---------- today's list on the home page ---------- */
  function todoRows(items) {
    var rows = [];
    items.forEach(function (it) {
      var b = baseOf(it);
      if (!b) return;
      var left = C.totalDays(TODAY, b);
      if (left >= 0 && left <= 3) rows.push({ k: 'event', it: it, n: left });
      if (left < 0) return;
      notesOf(it.key).tasks.forEach(function (t) {
        if (t.done) return;
        var n = C.totalDays(TODAY, C.addDays(b, -t.before));
        if (n <= 3) rows.push({ k: 'task', it: it, t: t, n: n });
      });
    });
    return rows.sort(function (a, b) { return a.n - b.n || (a.k < b.k ? -1 : 1); });
  }
  function whenWord(n) { return n < 0 ? '期限切れ' : n === 0 ? '今日' : n === 1 ? '明日' : 'あと' + n + '日'; }
  function renderTodo(cat) {
    var box = $('#todo');
    if (!box) return;
    var items = planItems(cat);
    var rows = items.length ? todoRows(items) : [], list = $('#todo-list');
    box.hidden = !rows.length;   // nothing today: the part is left out (it only said so); the calendar is in the tab bar
    if (!rows.length) return;
    list.innerHTML = rows.length ? rows.slice(0, 8).map(function (r) {
      if (r.k === 'event') return '<li><span class="when">' + whenWord(r.n) + '</span> <a href="/plan/?key=' + H(r.it.key) + '">' + H(r.it.title) + '</a>' + (r.it.time ? ' <span class="muted">' + H(r.it.time) + '</span>' : '') + '</li>';
      return '<li class="task' + (r.n < 0 ? ' over' : '') + '"><span class="when">' + whenWord(r.n) + '</span> ' + taskCheckbox(r.it, r.t) + ' <span class="muted">(' + H(r.it.title) + ')</span></li>';
    }).join('') : '<li class="muted">今日の予定とやることはありません。</li>';
  }

  /* ---------- the calendar page ---------- */
  function pageCalendar() {
    var host = $('#cal'), items = [], catCache = [];
    var view = P.v === 'list' ? 'list' : 'month';
    var ym = /^\d{4}-\d{2}$/.test(P.m || '') && +P.m.slice(5) >= 1 && +P.m.slice(5) <= 12 ? [+P.m.slice(0, 4), +P.m.slice(5)] : [TODAY[0], TODAY[1]];
    var sel = (P.d && C.parse(P.d)) || TODAY;
    function chip(it) { return '<span class="cal-chip g' + (it.g || 1) + (it.quiet ? ' quiet' : '') + '"><span class="t">' + H(it.title) + '</span></span>'; }
    function cell(d, evs, tks) {
      var marks = evs.slice(0, 3).map(chip).join('') + (tks.length && evs.length < 3 ? '<span class="cal-chip task"><span class="t">やること' + tks.length + '</span></span>' : '');
      var more = evs.length + (tks.length ? 1 : 0) - 3;
      var cls = 'cal-cell' + (C.cmp(d, TODAY) === 0 ? ' today' : '') + (C.cmp(d, sel) === 0 ? ' sel' : '') + (wdIdx(d) === 0 ? ' sun' : wdIdx(d) === 6 ? ' sat' : '');
      return '<button type="button" class="' + cls + '" data-d="' + C.iso(d) + '" aria-pressed="' + (C.cmp(d, sel) === 0) + '" aria-label="' + md(d) + ' 予定' + evs.length + '件のやること' + tks.length + '件">' +
        '<span class="cal-n">' + d[2] + '</span><span class="cal-marks">' + marks + (more > 0 ? '<span class="cal-more">+' + more + '</span>' : '') + '</span></button>';
    }
    function dayLines(d) {
      var evs = eventsOn(items, d), tks = tasksOn(items, d), h = '';
      evs.forEach(function (it) {
        h += '<li><span class="badge">' + H(it.kind) + '</span> <a href="/plan/?key=' + H(it.key) + '">' + H(it.title) + '</a>' + (it.time ? ' <span class="muted">' + H(it.time) + '</span>' : '') + '</li>';
      });
      tks.forEach(function (o) { h += '<li class="task">' + taskCheckbox(o.it, o.t) + ' <span class="muted">(' + H(o.it.title) + 'の' + beforeLabel(o.t.before) + ')</span></li>'; });
      return h;
    }
    function month() {
      var y = ym[0], m = ym[1], lead = wdIdx([y, m, 1]), n = C.dim(y, m);
      var h = '<div class="cal-head"><button type="button" class="mini" data-cal="prev" aria-label="前の月">‹</button><h2 class="cal-title">' + y + '年' + m + '月</h2>' +
        '<button type="button" class="mini" data-cal="next" aria-label="次の月">›</button><button type="button" class="chip" data-cal="today">今日</button></div>';
      h += '<div class="cal-grid" role="grid" aria-label="' + y + '年' + m + '月のカレンダー">' + '日月火水木金土'.split('').map(function (c, i) {
        return '<div class="cal-dow' + (i === 0 ? ' sun' : i === 6 ? ' sat' : '') + '" role="columnheader">' + c + '</div>';
      }).join('');
      for (var i = 0; i < lead; i++) h += '<span class="cal-blank"></span>';
      for (var day = 1; day <= n; day++) { var d = [y, m, day]; h += cell(d, eventsOn(items, d), tasksOn(items, d)); }
      h += '</div>';
      var lines = dayLines(sel);
      h += '<section class="day-panel" id="day-panel" aria-live="polite"><h3>' + md(sel) + ' <small class="muted">' + rel(sel) + '</small></h3>' +
        (lines ? '<ul class="plist">' + lines + '</ul>' : '<p class="muted">この日の予定はありません。</p>') +
        '<p><a class="btn small" href="/add/?kind=event&amp;date=' + C.iso(sel) + '">この日に予定を追加</a></p></section>';
      return h;
    }
    function list() {
      var h = '', any = false;
      for (var i = 0; i < 60; i++) {
        var d = C.addDays(TODAY, i), lines = dayLines(d);
        if (lines) { any = true; h += '<section class="plist-day"><h3>' + md(d) + ' <small class="muted">' + rel(d) + '</small></h3><ul class="plist">' + lines + '</ul></section>'; }
      }
      return any ? '<p class="hint">今日から60日後まで表示しています。</p>' + h : '<p class="empty">60日後までの予定はありません。<br><a class="btn small" href="/add/?kind=event">予定を追加</a></p>';
    }
    function render() {
      host.innerHTML = '<div class="chips cal-tools" role="group" aria-label="表示の切り替え"><button type="button" class="chip" data-v="month" aria-pressed="' + (view === 'month') + '">月</button>' +
        '<button type="button" class="chip" data-v="list" aria-pressed="' + (view === 'list') + '">一覧</button><a class="btn small" href="/add/?kind=event">＋ 予定を追加</a></div>' + (view === 'month' ? month() : list());
    }
    redo = function () { items = planItems(catCache); render(); };
    host.addEventListener('click', function (ev) {
      var t = ev.target.closest ? ev.target.closest('button') : null;
      if (!t) return;
      if (t.hasAttribute('data-v')) { view = t.getAttribute('data-v'); A.stat('act:cal_' + view); render(); }
      else if (t.hasAttribute('data-cal')) {
        var a = t.getAttribute('data-cal');
        if (a === 'today') { ym = [TODAY[0], TODAY[1]]; sel = TODAY; }
        else { var k = ym[0] * 12 + ym[1] - 1 + (a === 'next' ? 1 : -1); ym = [Math.floor(k / 12), k % 12 + 1]; }
        render();
      } else if (t.hasAttribute('data-d')) { sel = C.parse(t.getAttribute('data-d')); render(); var p = $('#day-panel'); if (p && p.scrollIntoView) p.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
    });
    A.loadCatalog().then(function (cat) { catCache = cat || []; items = planItems(catCache); render(); });
  }

  function nextMilestone(e) {   // right after saving: when the day comes round next, so there is a reason to open the page again
    var d = e && e.precision === 'day' ? C.parse(e.date) : null;
    if (!d) return '';
    if (A.repOf(e)) return '次は、' + A.fmtDate(C.iso(C.repNext(d, A.repOf(e), TODAY)), 'day') + 'です。';
    var gone = C.toDays(TODAY[0], TODAY[1], TODAY[2]) - C.toDays(d[0], d[1], d[2]), next;
    if (e.every100 && gone >= 0) { var n = (Math.floor(gone / 100) + 1) * 100; return '次の100日ごとの節目は、' + n + '日目の' + A.fmtDate(C.iso(C.addDays(d, n)), 'day') + 'です。'; }
    if (e.yearly) {
      var dd = d[1] === 2 && d[2] > 28 ? 28 : d[2];
      next = [TODAY[0], d[1], dd];
      if (C.cmp(next, TODAY) < 0) next = [TODAY[0] + 1, d[1], dd];
      return '次の同じ日は、' + A.fmtDate(C.iso(next), 'day') + 'です。';
    }
    return '';
  }

  // "週で見る": how many weeks and days there are to a day (or since it), and one cell for each week.  Not for a quiet day.  A day with more than 26 years behind it or 2 years ahead gets the words only.
  function weeksSection(item) {
    var d = item.p === 'day' && !item.quiet ? C.parse(item.rep ? item.next : item.date) : null;
    if (!d) return '';
    var n = C.totalDays(TODAY, d), m = Math.abs(n);
    if (!m) return '';
    var past = n < 0, whole = Math.floor(m / 7), part = m % 7 ? 1 : 0, cells = whole + part, cap = past ? 1352 : 104, words = C.weeksText(m);
    var h = '<section class="plan-sec" id="weeks"><h2>週で見る</h2><p class="weeks-line">' + (past ? 'もう' : 'あと') + '<b>' + words + '</b>' + (m >= 7 ? '(' + C.group(m) + '日)' : '') + 'です。</p>';
    if (cells <= cap) {
      var out = '';
      for (var i = 0; i < cells; i++) out += '<i class="' + (past ? 'on' : 'fut') + (i >= whole ? ' part' : '') + '"></i>';
      h += '<div class="wgrid" role="img" aria-label="1マスが1週です。' + (past ? 'この日から' : 'この日まで') + words + '分を並べています。">' + out + '</div>' +
        '<p class="hint">1マスが1週です。1段が約1年(52週)で、' + (past ? 'この日の週から今日の週まで' : '今日の週からこの日の週まで') + 'を数えています。' + (part ? '最後の薄いマスは、7日に満たない分です。' : '') + '</p>';
    } else h += '<p class="hint">' + (past ? '26年' : '2年') + 'をこえるため、マスは並べません。</p>';
    return h + '</section>';
  }

  /* ---------- one plan: its card, memo, "do this N days before", and the optional file for other calendar apps ---------- */
  function pagePlan() {
    var key = P.key || '', box = $('#plan'), item = null;
    function missing() { box.innerHTML = '<p class="empty">この予定は見つかりません。カレンダーから選び直してください。<br><a class="btn small" href="/calendar/">カレンダーへ</a></p>'; }
    if (!/^[cm]:[A-Za-z0-9_-]{1,40}$/.test(key)) return missing();
    function taskList() {
      var b = baseOf(item), n = notesOf(key);
      if (!n.tasks.length) return '<li class="muted">やることはまだありません。</li>';
      return n.tasks.slice().sort(function (x, y) { return y.before - x.before; }).map(function (t) {
        var due = b ? C.addDays(b, -t.before) : null;
        return '<li class="task">' + taskCheckbox(item, t) + ' <span class="muted">(' + beforeLabel(t.before) + (due ? ' ' + md(due) : '') + ')</span> <button type="button" class="mini" data-del-task="' + H(t.id) + '" aria-label="このやることを消す">×</button></li>';
      }).join('');
    }
    function planBar(e) {   // the actions on a card of one's own, right under the card (they used to be two or three screens down)
      if (!e) return '';
      return '<div class="plan-bar" id="plan-bar" role="group" aria-label="このカードの操作"><button type="button" class="btn small" data-plan-act="edit">修正</button>' +
        '<button type="button" class="btn small ghost" data-plan-act="copy">コピー</button>' +
        '<button type="button" class="btn small ghost" data-plan-act="pin" aria-pressed="' + (e.pin ? 'true' : 'false') + '">' + (e.pin ? '★ ピン留め中' : '☆ ピン留め') + '</button>' +
        '<button type="button" class="btn small ghost" data-plan-act="del">消す</button></div>';
    }
    function shiftRow(e) {   // a plan that moved: one tap puts it a day, a week or a month later
      if (!e || e.precision !== 'day' || e.yearly || A.repOf(e) || ['event', 'until', 'memo'].indexOf(e.kind) < 0) return '';
      return '<p class="shift" id="shift-row"><span class="lab">日付をずらす</span> <button type="button" class="chip" data-shift="d1">+1日</button><button type="button" class="chip" data-shift="w1">+1週間</button><button type="button" class="chip" data-shift="m1">+1か月</button></p>';
    }
    function arrange() {   // the order on the page: the card, its actions, sending it, correcting it, then the notices, tasks and memo, the weeks, the files for other calendars
      var anchor = $('.plan-card', box);
      if (!anchor) return;
      ['#plan-bar', '#shift-row', '.share-row', '#edit-sec', '#remind', '#tasks', '#memo-sec', '#weeks', '.more'].forEach(function (sel) {
        var el = $(sel, box);
        if (!el) return;
        if (anchor.nextElementSibling !== el) anchor.parentNode.insertBefore(el, anchor.nextSibling);
        anchor = el;
      });
    }
    function render() {
      var own = item.own, e = own ? A.findEntry(item.id) : null, n = notesOf(key), h = '';
      h += '<div class="cards plan-card' + (own ? ' own' : '') + '">' + A.cardHtml(item).replace('class="card', 'class="card big') + '</div>';
      h += planBar(e) + shiftRow(e) + weeksSection(item);
      if (item.p === 'day') {   // the notices of this day: one switch for all of them, the days before, and (plus plan) any number of days and the time of day
        var nn = notesOf(key), rem = nn.remind, sug = remindPreset(item), T = A.tier, free = T && T.on && !T.plus();
        var allowed = function (r) { return !T || T.remindAllowed(r); };
        h += '<section class="plan-sec" id="remind"><h2>知らせ</h2>' +
          '<p><label class="lab" for="r-on"><input type="checkbox" id="r-on"' + (nn.mute ? '' : ' checked') + '> この日の知らせを出す(オフにすると、この日の知らせはすべて止まります)</label></p>' +
          (item.quiet ? '<p class="hint">大切な日です。知らせは、ふだんは出しません。必要なときだけ、ご自分で選んでオンにしてください。</p>' : '') +
          '<h3 class="x-h3">あと何日の知らせ</h3><p class="hint">日にちが近づくたびに、知らせます。通知をオンにしているときに届きます。カレンダーのファイルにも入ります。</p><div class="chiprow">' +
          [100, 60, 30, 14, 7, 3, 1].map(function (r) {
            var ok = allowed(r);
            if (!ok && !(T && T.plusOpen)) return '';   // a day only the plus plan has is not offered until that plan exists
            return '<button type="button" class="chip" data-remind="' + r + '" aria-pressed="' + (rem.indexOf(r) >= 0) + '"' + (ok ? '' : ' disabled') + '>' + (r === 1 ? '前日' : r + '日前') + (ok ? '' : '(プラス)') + '</button>';
          }).join('') + '</div>' +
          '<p class="share-btns"><button type="button" class="btn small ghost" data-remind-preset="' + sug.filter(allowed).join(',') + '">おすすめにする(' + sug.filter(allowed).map(function (r) { return r === 1 ? '前日' : r + '日前'; }).join('・') + ')</button> <button type="button" class="btn small ghost" data-remind-preset="">あと何日の知らせをなしにする</button></p>' +
          (T && T.plus() ? '<div class="field"><label for="r-custom">日数を自分で決める(1〜365)</label><div class="x-task"><input type="number" id="r-custom" min="1" max="365" inputmode="numeric" placeholder="例: 45"><button type="button" class="btn small" id="r-custom-add">足す</button></div></div>' +
            '<div class="field"><label for="r-slot">知らせる時間帯</label><select id="r-slot"><option value="m"' + (nn.remindSlot === 'e' ? '' : ' selected') + '>朝</option><option value="e"' + (nn.remindSlot === 'e' ? ' selected' : '') + '>前の日の夜</option></select></div>' :
            (free && T && T.plusOpen ? '<p class="hint">プラスプランでは、日数を自由に決めたり、朝か夜かを選んだりできます。</p>' : '')) +
          (rem.some(function (r) { return [100, 60, 30, 14, 7, 3, 1].indexOf(r) < 0; }) ? '<p class="hint">自分で決めた日数: ' + rem.filter(function (r) { return [100, 60, 30, 14, 7, 3, 1].indexOf(r) < 0; }).map(function (r) { return '<button type="button" class="chip" data-remind="' + r + '" aria-pressed="true">' + r + '日前 ×</button>'; }).join(' ') + '</p>' : '') +
          '</section>';
      }
      h += '<section class="plan-sec" id="tasks"><h2>やること(期限)</h2><ul class="plist" id="task-list">' + taskList() + '</ul>' +
        '<form class="task-add" id="task-add"><label class="vh" for="t-before">いつまでに</label><select id="t-before">' + BEFORE.map(function (b) { return '<option value="' + b[0] + '"' + (b[0] === 7 ? ' selected' : '') + '>' + b[1] + '</option>'; }).join('') + '</select>' +
        '<label class="vh" for="t-text">やること</label><input type="text" id="t-text" maxlength="80" placeholder="例: 書類をそろえる" autocomplete="off"><button type="submit" class="btn small">追加</button></form>' +
        '<p class="hint">期限の日は、カレンダーとホームに表示されます。</p>' + mic() + '</section>';
      h += '<section class="plan-sec" id="memo-sec"><h2>メモ</h2><div class="field"><label class="vh" for="p-memo">メモ</label><textarea id="p-memo" rows="4" maxlength="600" placeholder="持ち物、場所、連絡先など">' + H(n.memo) + '</textarea></div>' +
        mic() + '</section>';
      if (e) {
        h += '<section class="plan-sec" id="edit-sec"><h2>修正</h2><div class="field"><label for="e-title">名前</label><input type="text" id="e-title" maxlength="40" value="' + H(e.title) + '">' + mic() + '</div>';
        if (e.precision === 'day') h += '<div class="field"><label for="e-date">日付</label><input type="date" id="e-date" value="' + H(e.date) + '"></div>';
        else if (e.precision === 'month') h += '<div class="field"><label for="e-date">年と月(例 2026-10)</label><input type="month" id="e-date" value="' + H(String(e.date).slice(0, 7)) + '" placeholder="2026-10"></div>';
        else h += '<div class="field"><label for="e-date">年(例 1990)</label><input type="number" id="e-date" inputmode="numeric" min="1" max="2200" value="' + H(String(e.date).slice(0, 4)) + '"></div>';
        h += '<div class="field"><label for="e-say">文字で日付を入力する</label><input type="text" id="e-say" autocomplete="off" maxlength="30" placeholder="' + (e.precision === 'day' ? '12月25日 / 2027年3月3日' : e.precision === 'month' ? '2026年10月' : '1990年') + '"><p class="hint" id="e-say-note" aria-live="polite"></p>' + mic() + '</div>';
        if (e.kind === 'event' && e.precision === 'day') h += '<div class="field"><label for="e-time">時刻</label><input type="time" id="e-time" value="' + H(e.time || '') + '"></div>';
        if (e.precision === 'day') {
          var curRep = A.repOf(e) || (e.yearly ? 'year' : '');
          h += '<div class="field"><label for="e-rep">くり返し</label><select id="e-rep">' + [['', 'しない'], ['week', '毎週(同じ曜日)'], ['month', '毎月(同じ日付)'], ['year', '毎年(同じ月日)']].map(function (o) {
            return '<option value="' + o[0] + '"' + (curRep === o[0] ? ' selected' : '') + '>' + o[1] + '</option>';
          }).join('') + '</select><p class="hint">毎週・毎月は、カードに次の日までの日数が出ます。毎月は、その日がない月は月の最後の日です。</p></div>';
        }
        if (e.precision === 'day' && !e.quiet && e.kind !== 'event') h += '<div class="field"><label class="lab" for="e-100"><input type="checkbox" id="e-100"' + (e.every100 ? ' checked' : '') + '> 100日ごとの節目も入れる</label></div>';
        h += '<div class="field"><label for="e-alarm">お知らせ</label><select id="e-alarm">' + [['', '設定に合わせる(マイページ)'], ['morning', '当日の朝'], ['eve', '前日の夜'], ['week', '1週間前の朝'], ['none', 'しない']].map(function (o) {
          return '<option value="' + o[0] + '"' + ((e.alarm || '') === o[0] ? ' selected' : '') + '>' + o[1] + '</option>';
        }).join('') + '</select></div>';
        h += '<p><button type="button" class="btn small" id="e-save">保存</button></p></section>';
      }
      if (item.p === 'day') {
        var gurl = window.AtomouShare ? AtomouShare.googleUrl(item.title, item.date, own ? '' : '詳しい日付: ' + location.origin + '/e/' + item.id + '/') : '';
        h += '<details class="plan-sec more"><summary>他のカレンダーアプリに入れる</summary><p class="hint">Google カレンダーと Outlook には、下のボタンから入れられます。iPhone の「カレンダー」、Yahoo!カレンダー、TimeTree などには、ファイルを作って取り込みます。</p>' +
          '<p>' + (gurl ? '<a class="btn small ghost" href="' + H(gurl) + '" target="_blank" rel="noopener">Googleカレンダーに追加</a> <a class="btn small ghost" href="' + H(AtomouShare.outlookUrl(item.title, item.date, own ? '' : '詳しい日付: ' + location.origin + '/e/' + item.id + '/')) + '" target="_blank" rel="noopener">Outlookに追加</a> ' : '') +
          '<button type="button" class="btn small ghost" data-ics-for="' + H(key) + '">ファイルを作る</button></p></details>';
      }
      if (!(own && (!e || e.quiet))) {   // a day of one's own is sent as words and a picture only (no page to link to), without its title unless the box is ticked
        h += '<div class="plan-sec share share-row" aria-label="人に送る" data-title="' + H(item.title) + '" data-date="' + H(item.date) + '" data-p="' + H(item.p) + '"' +
          (own ? ' data-private="1"' : ' data-url="' + H(location.origin + '/e/' + item.id + '/') + '"') + '><span class="share-lead">送る</span>' + AtomouShare.icons(['line', 'x', 'copy', 'image', 'native']) +
          '<a class="share-more" href="/card/#from=' + H(key) + '" title="ひとこと・やることを入れたカードにして送ります">カードにして送る</a>' +
          (own ? '<label class="lab share-title" for="sh-title"><input type="checkbox" id="sh-title" data-share-title> 題名も入れる</label>' : '') + '</div>';
      }
      box.innerHTML = h;
      if (window.AtomouShare) AtomouShare.init(box);
      A.hydrate(box);
      if (own) $$('.c-act a', box).forEach(function (a) { a.remove(); });
      arrange();
    }
    function saySpoken(input) {   // the words in "文字で日付を入力する" fill the date field above it; "保存" writes it
      var dt = $('#e-date'), note = $('#e-say-note'), e = A.findEntry(item.id), p = e ? e.precision : 'day', d;
      if (!dt || !note) return;
      if (!input.value.trim()) { note.textContent = ''; return; }
      d = C.parseSpoken(input.value, p, TODAY);
      if (!d) { note.textContent = '読み取れませんでした。' + (p === 'day' ? '年月日の形で入れてください(例: 12月25日)。' : p === 'month' ? '(例: 2026年10月)' : '(例: 1990年)'); return; }
      dt.value = p === 'day' ? C.iso(d) : p === 'month' ? String(d[0]).padStart(4, '0') + '-' + String(d[1]).padStart(2, '0') : String(d[0]);
      note.textContent = '→ ' + A.fmtDate(C.iso(d), p) + '(保存すると反映されます)';
    }
    redo = function () { var m = $('#p-memo'); if (m) notesOf(key).memo = m.value; render(); };
    box.addEventListener('input', function (ev) {
      if (ev.target.id === 'e-say') { saySpoken(ev.target); return; }
      if (ev.target.id !== 'p-memo') return;
      clearTimeout(box._t);
      box._t = setTimeout(function () { var n = notesOf(key); n.memo = ev.target.value; setNotes(key, n); }, 350);
    });
    box.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var text = $('#t-text').value.trim();
      if (!text) { $('#t-text').focus(); return; }
      var n = notesOf(key);
      if (n.tasks.length >= 30) { A.toast('やることは30件までです。'); return; }
      n.tasks.push({ id: Math.random().toString(36).slice(2, 8), before: +$('#t-before').value, text: text.slice(0, 80), done: false });
      setNotes(key, n); A.stat('act:task_add');
      var memo = $('#p-memo').value; if (memo !== n.memo) { n.memo = memo; setNotes(key, n); }
      render(); var t = $('#t-text'); if (t) t.focus();
    });
    box.addEventListener('change', function (ev) {
      var id = ev.target.id;
      if (id === 'r-on') { var m1 = notesOf(key); m1.mute = !ev.target.checked; setNotes(key, m1); A.stat('act:notice_' + (m1.mute ? 'off' : 'on')); }
      else if (id === 'r-slot') { var m2 = notesOf(key); m2.remindSlot = ev.target.value === 'e' ? 'e' : 'm'; setNotes(key, m2); }
    });
    box.addEventListener('click', function (ev) {
      var pb = ev.target.closest ? ev.target.closest('[data-plan-act]') : null;
      if (pb) {
        var pact = pb.getAttribute('data-plan-act'), pe = A.findEntry(item.id);
        if (!pe) return;
        if (pact === 'edit') { var ed = $('#edit-sec'); if (ed) { ed.scrollIntoView({ block: 'start' }); var et = $('#e-title'); if (et) et.focus({ preventScroll: true }); } }
        else if (pact === 'copy') { if (!pe.quiet && A.tier && A.tier.blocked(1)) return; if (window.AtomouQuick) window.AtomouQuick.open({ copy: pe.id }); }
        else if (pact === 'pin') { if (A.setPin(pe.id) !== null) { item = A.ownItem(pe); render(); } }
        else if (pact === 'del') { var pc = $('.plan-card .card', box); if (pc) A.removeEntry(pc); }
        return;
      }
      var sb = ev.target.closest ? ev.target.closest('[data-shift]') : null;
      if (sb) {
        var se = A.findEntry(item.id), sd = se && C.parse(se.date);
        if (!se || !sd) return;
        var sk = sb.getAttribute('data-shift'), nd2 = sk === 'd1' ? C.addDays(sd, 1) : sk === 'w1' ? C.addDays(sd, 7) : C.addMonths(sd, 1), was = se.date;
        se.date = C.iso(nd2); A.persist(); A.stat('act:shift_' + sk); item = A.ownItem(se); render();
        A.toastAct(A.fmtDate(se.date, 'day') + ' にずらしました。', '元に戻す', function () { se.date = was; A.persist(); item = A.ownItem(se); render(); });
        return;
      }
      if (ev.target.id === 'r-custom-add') {
        var cv = Math.floor(+($('#r-custom') || {}).value), cn = notesOf(key);
        if (!(cv >= 1 && cv <= 365)) { A.toast('日数は、1から365までで入れてください。'); return; }
        if (cn.remind.length >= 12) { A.toast('あと何日の知らせは、12個までです。'); return; }
        if (cn.remind.indexOf(cv) < 0) cn.remind.push(cv);
        cn.remind.sort(function (x, y) { return y - x; }); setNotes(key, cn); render(); return;
      }
      var rb = ev.target.closest ? ev.target.closest('[data-remind],[data-remind-preset]') : null;
      if (rb) {
        var rn = notesOf(key), r = rb.getAttribute('data-remind');
        if (r !== null) { r = +r; var at = rn.remind.indexOf(r); if (at >= 0) rn.remind.splice(at, 1); else rn.remind.push(r); }
        else rn.remind = rb.getAttribute('data-remind-preset') ? rb.getAttribute('data-remind-preset').split(',').map(Number) : [];
        rn.remind.sort(function (a, b) { return b - a; });
        setNotes(key, rn); A.stat('act:remind_set'); render(); return;
      }
      var d = ev.target.closest ? ev.target.closest('[data-del-task]') : null;
      if (d) { var n = notesOf(key); n.tasks = n.tasks.filter(function (t) { return t.id !== d.getAttribute('data-del-task'); }); setNotes(key, n); render(); return; }
      if (ev.target.id === 'e-save') {
        var e = A.findEntry(item.id), title = $('#e-title').value.trim(), dt = $('#e-date'), tm = $('#e-time');
        if (!e) return;
        if (title) e.title = title.slice(0, 80);
        if (dt) {
          var v = dt.value.trim(), nd = null, mm;
          if (e.precision === 'day') nd = C.parse(v);
          else if (e.precision === 'month') { mm = /^(\d{4})-(\d{2})$/.exec(v); nd = mm && +mm[2] >= 1 && +mm[2] <= 12 ? [+mm[1], +mm[2], 1] : null; }
          else { var yy = parseInt(v, 10); nd = yy >= 1 && yy <= 2200 ? [yy, 1, 1] : null; }
          if (!nd) { A.toast('日付を確かめてください。'); return; }
          e.date = C.iso(nd);
        }
        var rp = $('#e-rep'); if (rp) { e.yearly = rp.value === 'year'; e.repeat = rp.value === 'week' || rp.value === 'month' ? rp.value : ''; if (e.repeat) e.every100 = false; }
        var h100 = $('#e-100'); if (h100 && !e.repeat) e.every100 = h100.checked;
        var al = $('#e-alarm'); if (al) e.alarm = al.value;
        if (tm) e.time = /^([01]\d|2[0-3]):[0-5]\d$/.test(tm.value) ? tm.value : '';
        A.persist(); A.stat('act:plan_edit'); item = A.ownItem(e); render(); A.toast('保存しました。');
      }
    });
    A.loadCatalog().then(function (cat) {
      if (key.charAt(0) === 'm') { var e = A.findEntry(key.slice(2)); item = e ? A.ownItem(e) : null; }
      else { var c = (cat || []).filter(function (x) { return x.id === key.slice(2); })[0]; item = c ? A.catItem(c) : null; }
      if (!item) return missing();
      render();
      if (P.new) { A.toast('記録しました。' + (nextMilestone(item.own && A.findEntry(item.id)) || '続けてメモとやることを書けます。')); if (window.AtomouPush && item.own) window.AtomouPush.afterSave(box, !!item.quiet); try { history.replaceState(null, '', '/plan/?key=' + key); } catch (x) { /* ignore */ } }
    });
  }

  if (page === 'calendar') pageCalendar();
  else if (page === 'plan') pagePlan();
  else if (page === 'home') {
    var need = function () { return A.state().saved.length ? A.loadCatalog() : Promise.resolve([]); };
    redo = function () { need().then(renderTodo); };
    need().then(renderTodo);
  }
  document.addEventListener('atomou:changed', function () { again(); });
  A.plan = { planItems: planItems, eventsOn: eventsOn, tasksOn: tasksOn, todoRows: todoRows, baseOf: baseOf, notesOf: notesOf };
  window.AtomouPlan = A.plan;
})();
