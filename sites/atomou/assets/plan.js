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
  function rel(d) { var n = C.totalDays(TODAY, d); return n === 0 ? '今日' : n === 1 ? '明日' : n > 1 ? 'あと' + n + '日' : 'もう' + (-n) + '日'; }

  /* ---------- what is in the book ---------- */
  function planItems(cat) {  // the visitor's own days and the official dates they put in the calendar
    var st = S(), items = st.entries.map(A.ownItem), by = {};
    (cat || []).forEach(function (c) { by[c.id] = c; });
    st.saved.forEach(function (id) { if (by[id]) items.push(A.catItem(by[id])); });
    return items;
  }
  function notesOf(key) { return S().notes[key] || { memo: '', tasks: [] }; }
  function setNotes(key, n) {
    var st = S();
    if (!n.memo && !n.tasks.length) delete st.notes[key]; else st.notes[key] = n;
    A.persist();
  }
  function baseOf(it) {  // the date the tasks count back from (a yearly day: its next turn)
    var d = C.parse(it.date);
    if (!d || it.p !== 'day') return null;
    return it.yearly ? A.nextYearly(d, TODAY) : d;
  }
  function eventsOn(items, d) {
    var out = [];
    items.forEach(function (it) {
      var dd = C.parse(it.date);
      if (!dd || it.p !== 'day') return;
      if (C.cmp(dd, d) === 0 || (it.yearly && d[0] > dd[0] && C.cmp(A.occ(dd, d[0]), d) === 0)) out.push(it);
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
  function whenWord(n) { return n < 0 ? '期限をすぎています' : n === 0 ? '今日' : n === 1 ? '明日' : 'あと' + n + '日'; }
  function renderTodo(cat) {
    var box = $('#todo');
    if (!box) return;
    var items = planItems(cat);
    box.hidden = !items.length;
    if (!items.length) return;
    var rows = todoRows(items), list = $('#todo-list');
    list.innerHTML = rows.length ? rows.slice(0, 8).map(function (r) {
      if (r.k === 'event') return '<li><span class="when">' + whenWord(r.n) + '</span> <a href="/plan/?key=' + H(r.it.key) + '">' + H(r.it.title) + '</a>' + (r.it.time ? ' <span class="muted">' + H(r.it.time) + '</span>' : '') + '</li>';
      return '<li class="task' + (r.n < 0 ? ' over' : '') + '"><span class="when">' + whenWord(r.n) + '</span> ' + taskCheckbox(r.it, r.t) + ' <span class="muted">(' + H(r.it.title) + ')</span></li>';
    }).join('') : '<li class="muted">今日の予定・やることは、ありません。</li>';
  }

  /* ---------- the calendar page ---------- */
  function pageCalendar() {
    var host = $('#cal'), items = [];
    var view = P.v === 'list' ? 'list' : 'month';
    var ym = /^\d{4}-\d{2}$/.test(P.m || '') && +P.m.slice(5) >= 1 && +P.m.slice(5) <= 12 ? [+P.m.slice(0, 4), +P.m.slice(5)] : [TODAY[0], TODAY[1]];
    var sel = (P.d && C.parse(P.d)) || TODAY;
    function chip(it) { return '<span class="cal-chip g' + (it.g || 1) + (it.quiet ? ' quiet' : '') + '"><span class="t">' + H(it.title) + '</span></span>'; }
    function cell(d, evs, tks) {
      var marks = evs.slice(0, 3).map(chip).join('') + (tks.length && evs.length < 3 ? '<span class="cal-chip task"><span class="t">やること' + tks.length + '</span></span>' : '');
      var more = evs.length + (tks.length ? 1 : 0) - 3;
      var cls = 'cal-cell' + (C.cmp(d, TODAY) === 0 ? ' today' : '') + (C.cmp(d, sel) === 0 ? ' sel' : '') + (wdIdx(d) === 0 ? ' sun' : wdIdx(d) === 6 ? ' sat' : '');
      return '<button type="button" class="' + cls + '" data-d="' + C.iso(d) + '" aria-pressed="' + (C.cmp(d, sel) === 0) + '" aria-label="' + md(d) + ' 予定' + evs.length + '件 やること' + tks.length + '件">' +
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
        (lines ? '<ul class="plist">' + lines + '</ul>' : '<p class="muted">この日の予定は、ありません。</p>') +
        '<p><a class="btn small" href="/add/?kind=event&amp;date=' + C.iso(sel) + '">この日に予定を追加</a></p></section>';
      return h;
    }
    function list() {
      var h = '', any = false;
      for (var i = 0; i < 60; i++) {
        var d = C.addDays(TODAY, i), lines = dayLines(d);
        if (lines) { any = true; h += '<section class="plist-day"><h3>' + md(d) + ' <small class="muted">' + rel(d) + '</small></h3><ul class="plist">' + lines + '</ul></section>'; }
      }
      return any ? '<p class="hint">これから60日の予定とやることです。</p>' + h : '<p class="empty">これから60日の予定は、ありません。<br><a class="btn small" href="/add/?kind=event">予定を追加する</a></p>';
    }
    function render() {
      host.innerHTML = '<div class="chips cal-tools" role="group" aria-label="表示の切りかえ"><button type="button" class="chip" data-v="month" aria-pressed="' + (view === 'month') + '">月</button>' +
        '<button type="button" class="chip" data-v="list" aria-pressed="' + (view === 'list') + '">一覧</button><a class="btn small" href="/add/?kind=event">＋ 予定を追加</a></div>' + (view === 'month' ? month() : list());
    }
    redo = render;
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
    A.loadCatalog().then(function (cat) { items = planItems(cat); render(); });
  }

  /* ---------- one plan: its card, memo, "do this N days before", and the optional file for other calendar apps ---------- */
  function pagePlan() {
    var key = P.key || '', box = $('#plan'), item = null;
    function missing() { box.innerHTML = '<p class="empty">この予定は、見つかりませんでした。<br><a class="btn small" href="/calendar/">カレンダーへ</a></p>'; }
    if (!/^[cm]:[A-Za-z0-9_-]{1,40}$/.test(key)) return missing();
    function taskList() {
      var b = baseOf(item), n = notesOf(key);
      if (!n.tasks.length) return '<li class="muted">まだ、ありません。</li>';
      return n.tasks.slice().sort(function (x, y) { return y.before - x.before; }).map(function (t) {
        var due = b ? C.addDays(b, -t.before) : null;
        return '<li class="task">' + taskCheckbox(item, t) + ' <span class="muted">(' + beforeLabel(t.before) + (due ? ' ' + md(due) : '') + ')</span> <button type="button" class="mini" data-del-task="' + H(t.id) + '" aria-label="このやることを消す">×</button></li>';
      }).join('');
    }
    function render() {
      var own = item.own, e = own ? A.findEntry(item.id) : null, n = notesOf(key), h = '';
      h += '<div class="cards plan-card">' + A.cardHtml(item).replace('class="card', 'class="card big') + '</div>';
      h += '<section class="plan-sec" id="tasks"><h2>やること(何日前までに何をするか)</h2><ul class="plist" id="task-list">' + taskList() + '</ul>' +
        '<form class="task-add" id="task-add"><label class="vh" for="t-before">いつまでに</label><select id="t-before">' + BEFORE.map(function (b) { return '<option value="' + b[0] + '"' + (b[0] === 7 ? ' selected' : '') + '>' + b[1] + '</option>'; }).join('') + '</select>' +
        '<label class="vh" for="t-text">やること</label><input type="text" id="t-text" maxlength="80" placeholder="例: 書類をそろえる" autocomplete="off"><button type="submit" class="btn small">追加</button></form>' +
        '<p class="hint">期限の日は、カレンダーと、ホームの「今日の予定・やること」に出ます。</p></section>';
      h += '<section class="plan-sec"><h2>メモ</h2><div class="field"><label class="vh" for="p-memo">メモ</label><textarea id="p-memo" rows="4" maxlength="600" placeholder="持ち物、場所、連絡先など">' + H(n.memo) + '</textarea></div>' +
        '<p class="hint">メモは、この端末の中だけに保存します。</p></section>';
      if (e) {
        h += '<section class="plan-sec"><h2>内容を直す</h2><div class="field"><label for="e-title">名前</label><input type="text" id="e-title" maxlength="40" value="' + H(e.title) + '"></div>';
        if (e.precision === 'day') h += '<div class="field"><label for="e-date">日付</label><input type="date" id="e-date" value="' + H(e.date) + '"></div>';
        if (e.kind === 'event' && e.precision === 'day') h += '<div class="field"><label for="e-time">時刻</label><input type="time" id="e-time" value="' + H(e.time || '') + '"></div>';
        h += '<p><button type="button" class="btn small" id="e-save">変更を保存</button></p></section>';
      }
      if (item.p === 'day') h += '<details class="plan-sec more"><summary>他のカレンダーアプリも使うとき</summary><p class="hint">この予定を、iPhone の「カレンダー」や Google カレンダーなどに取り込める、ファイルをつくります。</p>' +
        '<p><button type="button" class="btn small ghost" data-ics-for="' + H(key) + '">ファイルをつくる</button></p></details>';
      box.innerHTML = h;
      A.hydrate(box);
      if (own) $$('.c-act a', box).forEach(function (a) { a.remove(); });
    }
    redo = function () { var m = $('#p-memo'); if (m) notesOf(key).memo = m.value; render(); };
    box.addEventListener('input', function (ev) {
      if (ev.target.id !== 'p-memo') return;
      clearTimeout(box._t);
      box._t = setTimeout(function () { var n = notesOf(key); n.memo = ev.target.value; setNotes(key, n); }, 350);
    });
    box.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var text = $('#t-text').value.trim();
      if (!text) { $('#t-text').focus(); return; }
      var n = notesOf(key);
      if (n.tasks.length >= 30) { A.toast('やることは、30件までです。'); return; }
      n.tasks.push({ id: Math.random().toString(36).slice(2, 8), before: +$('#t-before').value, text: text.slice(0, 80), done: false });
      setNotes(key, n); A.stat('act:task_add');
      var memo = $('#p-memo').value; if (memo !== n.memo) { n.memo = memo; setNotes(key, n); }
      render(); var t = $('#t-text'); if (t) t.focus();
    });
    box.addEventListener('click', function (ev) {
      var d = ev.target.closest ? ev.target.closest('[data-del-task]') : null;
      if (d) { var n = notesOf(key); n.tasks = n.tasks.filter(function (t) { return t.id !== d.getAttribute('data-del-task'); }); setNotes(key, n); render(); return; }
      if (ev.target.id === 'e-save') {
        var e = A.findEntry(item.id), title = $('#e-title').value.trim(), dt = $('#e-date'), tm = $('#e-time');
        if (!e) return;
        if (title) e.title = title.slice(0, 80);
        if (dt && C.parse(dt.value)) e.date = C.iso(C.parse(dt.value));
        if (tm) e.time = /^([01]\d|2[0-3]):[0-5]\d$/.test(tm.value) ? tm.value : '';
        A.persist(); A.stat('act:plan_edit'); item = A.ownItem(e); render(); A.toast('直しました。');
      }
    });
    A.loadCatalog().then(function (cat) {
      if (key.charAt(0) === 'm') { var e = A.findEntry(key.slice(2)); item = e ? A.ownItem(e) : null; }
      else { var c = (cat || []).filter(function (x) { return x.id === key.slice(2); })[0]; item = c ? A.catItem(c) : null; }
      if (!item) return missing();
      render();
      if (P.new) { A.toast('残しました。メモと、何日前までにやることを、続けて書けます。'); try { history.replaceState(null, '', '/plan/?key=' + key); } catch (x) { /* ignore */ } }
    });
  }

  if (page === 'calendar') pageCalendar();
  else if (page === 'plan') pagePlan();
  else if (page === 'home') {
    redo = function () { A.loadCatalog().then(renderTodo); };
    A.loadCatalog().then(renderTodo);
  }
  A.plan = { planItems: planItems, eventsOn: eventsOn, tasksOn: tasksOn, todoRows: todoRows, baseOf: baseOf, notesOf: notesOf };
  window.AtomouPlan = A.plan;
})();
