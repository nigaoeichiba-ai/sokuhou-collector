/* Taking days in from another calendar (the .ics file Google Calendar, Apple Calendar, Outlook and Yahoo!カレンダー can export).
   The file is read on this device and turned into days of the planner; nothing is sent anywhere.  Days that were taken in before are not added twice (the file's own UID makes the id).
   A repeating day is taken in once (a yearly one stays yearly); weekly and monthly repeats become the first day only, and the page says so. */
(function () {
  'use strict';
  var A = window.AtomouApp;
  if (!A) return;
  var C = A.C, $ = A.$, TODAY = A.TODAY;

  function unfold(t) { return t.replace(/\r?\n[ \t]/g, ''); }
  function unesc(s) { return String(s || '').replace(/\\n/gi, '\n').replace(/\\([,;\\])/g, '$1'); }
  function fnv(s) {   // a short stable id from the UID (not a secret, only a name)
    var h = 0x811c9dc5, i;
    for (i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = (h * 0x01000193) >>> 0; }
    return h.toString(36);
  }
  function parseDate(v, params) {   // "20261201" / "20261201T190000" / "20261201T100000Z" -> {d:[y,m,d], time:'HH:MM'|''}
    var m = /^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2})?(Z?))?$/.exec(String(v || '').trim());
    if (!m) return null;
    var d = [+m[1], +m[2], +m[3]], hh = m[4] != null ? +m[4] : null, mm = m[5] != null ? +m[5] : 0;
    if (hh == null || /VALUE=DATE(?!-)/.test(params || '')) return { d: d, time: '' };
    if (m[7] === 'Z') {   // UTC -> Japan time (+9)
      var mins = hh * 60 + mm + 540;
      if (mins >= 1440) { d = C.addDays(d, 1); mins -= 1440; }
      hh = Math.floor(mins / 60); mm = mins % 60;
    }
    return { d: d, time: (hh < 10 ? '0' : '') + hh + ':' + (mm < 10 ? '0' : '') + mm };
  }

  /* parse(text) -> {events: [{id, title, date, time, yearly, memo, repeat}], skipped: n} */
  function parse(text) {
    var blocks = unfold(String(text || '')).split(/BEGIN:VEVENT\r?\n/i).slice(1), events = [], skipped = 0;
    blocks.forEach(function (b) {
      b = b.split(/END:VEVENT/i)[0];
      var props = {};
      b.split(/\r?\n/).forEach(function (line) {
        var i = line.indexOf(':');
        if (i < 1) return;
        var left = line.slice(0, i), name = left.split(';')[0].toUpperCase();
        if (!(name in props)) props[name] = { v: line.slice(i + 1), p: left.slice(name.length) };
      });
      if (!props.DTSTART || /CANCELLED/i.test((props.STATUS || {}).v || '')) { skipped++; return; }
      var s = parseDate(props.DTSTART.v, props.DTSTART.p);
      if (!s || !C.parse(C.iso(s.d))) { skipped++; return; }
      var rule = (props.RRULE || {}).v || '', yearly = /FREQ=YEARLY/i.test(rule), repeat = rule && !yearly ? true : false;
      if (!yearly && C.totalDays(TODAY, s.d) < -7 && !rule) { skipped++; return; }   // a day well in the past is not brought along
      var title = unesc((props.SUMMARY || {}).v).replace(/[\u0000-\u001f<>]/g, ' ').trim().slice(0, 80) || '(題名なし)';
      events.push({ id: 'i' + fnv(((props.UID || {}).v || title + C.iso(s.d)) + (props['RECURRENCE-ID'] ? props['RECURRENCE-ID'].v : '')), title: title, date: C.iso(s.d), time: s.time, yearly: yearly,
        memo: unesc((props.DESCRIPTION || {}).v).replace(/[\u0000-\u0008<>]/g, '').slice(0, 300), repeat: repeat });
    });
    return { events: events.slice(0, 300), skipped: skipped + Math.max(0, events.length - 300) };
  }

  function addAll(events) {
    var S = A.state(), have = {};
    S.entries.forEach(function (e) { have[e.id] = 1; });
    var n = 0;
    events.forEach(function (e) {
      if (have[e.id] || S.entries.length >= 500) return;
      S.entries.push({ id: e.id, title: e.title, date: e.date, precision: 'day', kind: 'event', quiet: false, yearly: e.yearly, every100: false, alarm: '', time: e.time, created: C.iso(TODAY) });
      if (e.memo) S.notes['m:' + e.id] = { memo: e.memo, tasks: [], remind: [] };
      n++;
    });
    if (n) A.persist();
    return n;
  }

  function wire() {
    var input = $('#ical-file'), out = $('#ical-out');
    if (!input || !out) return;
    input.addEventListener('change', function () {
      var f = input.files && input.files[0];
      if (!f) return;
      var rd = new FileReader();
      rd.onload = function () {
        var r = parse(String(rd.result || '')), have = {}, fresh;
        A.state().entries.forEach(function (e) { have[e.id] = 1; });
        fresh = r.events.filter(function (e) { return !have[e.id]; });
        if (!r.events.length) { out.textContent = '取り込める予定が見つかりませんでした。カレンダーから書き出した .ics のファイルを選んでください。'; return; }
        out.innerHTML = '<p>' + r.events.length + '件の予定が見つかりました。新しく入れるのは' + fresh.length + '件です。' + (r.skipped ? '(過ぎた予定などで' + r.skipped + '件は入れません。)' : '') +
          (r.events.some(function (e) { return e.repeat; }) ? '毎週・毎月のくり返しは、最初の1回だけ入ります。' : '') + '</p>' +
          (fresh.length ? '<p><button type="button" class="btn small" id="ical-go">' + fresh.length + '件を入れる</button></p>' : '');
        var go = $('#ical-go');
        if (go) go.addEventListener('click', function () {
          var n = addAll(fresh);
          A.stat('act:ical_import');
          out.innerHTML = '<p>' + n + '件を、予定帳に入れました。<a href="/calendar/">カレンダーを見る</a></p>';
          document.dispatchEvent(new CustomEvent('atomou:changed'));
        });
      };
      rd.readAsText(f);
    });
  }
  if (A.page === 'my') wire();
  window.AtomouIcal = { parse: parse };
})();
