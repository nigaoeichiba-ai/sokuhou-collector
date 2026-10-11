/* 案7 "毎月の日付を、休みを避けて数える": a day of every month that moves off the closed days (the same count as sites/atomou/bizday.py; both are checked on the same hand-verified cases).
   A bank is closed on Saturdays, Sundays, the national holidays and 12/31-1/3 (銀行法第15条・同施行令第5条); an office, a company or a city hall usually only on Saturdays, Sundays and the holidays.
   The holidays come with the page (data-hol, the build's own count).  Everything stays on this device: the rules in localStorage "atomou.rules.v1", a day put into the planner in "atomou.v1". */
(function (root) {
  'use strict';
  var C = root.AtomouCore;

  function isClosed(d, hol, bank) {   // d: [y, m, d]; hol: an object whose keys are 'YYYY-MM-DD'
    if (C.weekday(d) >= 5 || hol[C.iso(d)]) return true;
    return !!bank && ((d[1] === 12 && d[2] === 31) || (d[1] === 1 && d[2] <= 3));
  }
  function adjust(d, how, hol, bank) {
    if (how === 'none') return d;
    var step = how === 'prev' ? -1 : 1, n = 0;
    while (isClosed(d, hol, bank)) { d = C.addDays(d, step); if (++n > 20) return null; }
    return d;
  }
  function nominal(y, m, day) { var last = C.dim(y, m); return [y, m, day === 0 || day > last ? last : day]; }
  // the next n dates of a rule {day, how, bank, months} on or after start; months: 'all' | 'even' | 'odd'
  function occurrences(rule, start, n, hol) {
    var out = [], y = start[0], m = start[1] - 1;
    if (m < 1) { y -= 1; m = 12; }
    for (var i = 0; i < n * 3 + 30 && out.length < n; i++) {
      if (!rule.months || rule.months === 'all' || ((m % 2 === 0) === (rule.months === 'even'))) {
        var d = adjust(nominal(y, m, rule.day), rule.how || 'prev', hol, rule.bank !== false);
        if (d && C.cmp(d, start) >= 0 && !out.some(function (x) { return C.cmp(x, d) === 0; })) out.push(d);
      }
      m += 1; if (m > 12) { y += 1; m = 1; }
    }
    return out.sort(C.cmp).slice(0, n);
  }

  var KEY = 'atomou.rules.v1', PRESETS = { pension: { title: '年金の支払日', day: 15, months: 'even', how: 'prev', bank: true } };
  function clean(r) {
    if (!r || typeof r !== 'object') return null;
    var day = Math.floor(+r.day);
    if (!(day >= 0 && day <= 31) || ['all', 'even', 'odd'].indexOf(r.months) < 0 || ['prev', 'next', 'none'].indexOf(r.how) < 0 || !/^[A-Za-z0-9_-]{1,20}$/.test(String(r.id || ''))) return null;
    return { id: String(r.id), title: String(r.title || '').slice(0, 30), day: day, months: r.months, how: r.how, bank: r.bank !== false };
  }
  function load() { try { return (JSON.parse(localStorage.getItem(KEY) || '[]') || []).map(clean).filter(Boolean).slice(0, 20); } catch (e) { return []; } }
  function save(list) { try { localStorage.setItem(KEY, JSON.stringify(list.slice(0, 20))); } catch (e) { /* the page works without it */ } }

  function describe(r) {
    return (r.months === 'even' ? '偶数月の' : r.months === 'odd' ? '奇数月の' : '毎月') + (r.day === 0 ? '月末' : r.day + '日') +
      (r.how === 'none' ? '(そのまま)' : '(休みなら' + (r.how === 'prev' ? '前' : '次') + 'の' + (r.bank ? '銀行の営業日' : '平日') + ')');
  }

  function init() {
    var A = root.AtomouApp, box = A && A.page === 'rule' ? A.$('#rule') : null;
    if (!box) return;
    var H = A.H, today = A.TODAY, hol = {}, last = '';
    try { JSON.parse(box.getAttribute('data-hol') || '[]').forEach(function (x) { hol[x] = 1; }); } catch (e) { /* no holidays: only the weekends are counted */ }
    last = box.getAttribute('data-last') || '';
    var rules = load(), WDN = ['月', '火', '水', '木', '金', '土', '日'];
    function f(id) { return A.$('#' + id); }
    function dayText(d) { return d[1] + '月' + d[2] + '日(' + WDN[C.weekday(d)] + ')'; }
    function lines(r) {
      var list = occurrences(r, today, 4, hol).filter(function (d) { return !last || C.iso(d) <= last; });
      if (!list.length) return '<p class="muted">この先の日は、数えられる範囲(' + H(last.slice(0, 4)) + '年末まで)にありません。</p>';
      return '<ul class="rule-dates">' + list.map(function (d, i) {
        var n = C.totalDays(today, d);
        return '<li><b>' + dayText(d) + '</b> ' + (n === 0 ? '今日です' : 'あと' + n + '日') + (i === 0 ? ' <button type="button" class="btn small ghost" data-add="' + C.iso(d) + '">この日を予定に入れる</button>' : '') + '</li>';
      }).join('') + '</ul>';
    }
    function draw() {
      var out = f('rule-list');
      out.innerHTML = rules.length ? rules.map(function (r) {
        return '<article class="panel rule-item" data-id="' + H(r.id) + '"><h3>' + H(r.title || '(名前なし)') + '</h3><p class="muted">' + H(describe(r)) + '</p>' + lines(r) +
          '<p><button type="button" class="btn small ghost" data-del="' + H(r.id) + '">このルールを消す</button></p></article>';
      }).join('') : '<p class="muted">保存したルールは、まだありません。</p>';
    }
    function read() {
      var t = f('r-title').value.trim().slice(0, 30), r = { id: 'r' + Math.random().toString(36).slice(2, 9), title: t, day: +f('r-day').value, months: f('r-months').value, how: f('r-how').value, bank: f('r-bank').value === 'bank' };
      return clean(r);
    }
    function preview() {
      var r = read(), p = f('rule-preview');
      p.innerHTML = r ? '<p class="muted">' + H(describe(r)) + '</p>' + lines(r) : '';
    }
    function apply(p) { f('r-title').value = p.title; f('r-day').value = p.day; f('r-months').value = p.months; f('r-how').value = p.how; f('r-bank').value = p.bank ? 'bank' : 'office'; preview(); }
    ['r-day', 'r-months', 'r-how', 'r-bank'].forEach(function (id) { f(id).addEventListener('change', preview); });
    f('r-title').addEventListener('input', preview);
    if (PRESETS[A.P.preset]) apply(PRESETS[A.P.preset]); else preview();
    f('r-presets').addEventListener('click', function (ev) { var b = ev.target.closest ? ev.target.closest('[data-preset]') : null; if (b) apply(PRESETS[b.getAttribute('data-preset')]); });
    f('r-save').addEventListener('click', function () {
      var r = read(); if (!r) return;
      if (!r.title) { A.toast('名前を入れてください。'); f('r-title').focus(); return; }
      if (rules.length >= 20) { A.toast('保存できるのは20件までです。'); return; }
      rules.unshift(r); save(rules); draw(); A.toast('保存しました。');
    });
    box.addEventListener('click', function (ev) {
      var b = ev.target.closest ? ev.target.closest('button') : null;
      if (!b) return;
      if (b.hasAttribute('data-del')) { rules = rules.filter(function (r) { return r.id !== b.getAttribute('data-del'); }); save(rules); draw(); }
      else if (b.hasAttribute('data-add')) {
        var host = b.closest('.rule-item'), r = host ? rules.filter(function (x) { return x.id === host.getAttribute('data-id'); })[0] : read(), d = C.parse(b.getAttribute('data-add'));
        if (!r || !d) return;
        var st = A.state();
        st.entries.push({ id: A.uid(), title: (r.title || '支払日').slice(0, 40), date: C.iso(d), precision: 'day', kind: 'event', quiet: false, yearly: false, every100: false, alarm: '', time: '', created: C.iso(today) });
        A.persist(); A.toast(dayText(d) + 'を、予定に入れました。');
      }
    });
    draw();
  }

  root.AtomouBiz = { isClosed: isClosed, adjust: adjust, nominal: nominal, occurrences: occurrences, describe: describe, clean: clean, init: init };
  if (root.document) { if (root.AtomouApp) init(); else root.addEventListener('load', init); }
})(typeof window !== 'undefined' ? window : this);
