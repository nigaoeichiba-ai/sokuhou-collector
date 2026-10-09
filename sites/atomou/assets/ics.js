/* ICS (calendar file) writer.  Wording on the site: "カレンダーに入れる" -- an alarm is requested but never promised (calendars treat VALARM differently).
   Events are all-day (DTSTART;VALUE=DATE), except a day with a time of day, which is a one-hour event in Japan time.  UIDs are stable, so importing a file twice updates instead of duplicating. */
(function (root) {
  'use strict';
  var C = root.AtomouCore;

  function esc(s) { return String(s).replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\r?\n/g, '\\n'); }
  function fold(line) {  // 75 octets per line, never inside a multi-byte character
    var out = [], cur = '', bytes = 0, enc = new TextEncoder();
    for (var ch of line) {
      var b = enc.encode(ch).length;
      if (bytes + b > (out.length ? 74 : 75)) { out.push(cur); cur = ' ' + ch; bytes = 1 + b; } else { cur += ch; bytes += b; }
    }
    out.push(cur);
    return out.join('\r\n');
  }
  function stamp(now) {
    var p = function (n) { return (n < 10 ? '0' : '') + n; };
    return now.getUTCFullYear() + p(now.getUTCMonth() + 1) + p(now.getUTCDate()) + 'T' + p(now.getUTCHours()) + p(now.getUTCMinutes()) + p(now.getUTCSeconds()) + 'Z';
  }
  function dateStr(a) { return C.iso(a).replace(/-/g, ''); }

  function hm(t) { var m = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(t || ''); return m ? [+m[1], +m[2]] : null; }
  function wall(d, h, m) { var p = function (n) { return (n < 10 ? '0' : '') + n; }; return dateStr(d) + 'T' + p(h) + p(m) + '00'; }
  function dur(min) { var d = Math.floor(min / 1440), h = Math.floor(min % 1440 / 60), m = min % 60; return '-P' + (d ? d + 'D' : '') + (h || m ? 'T' + (h ? h + 'H' : '') + (m ? m + 'M' : '') : 'T0M'); }
  // when the alert should come before an event that starts at minute t of its day: morning = 9:00 that day, eve = 21:00 the day before, week = 9:00 seven days before
  function alertBefore(alarm, t) {
    if (alarm === 'eve') return t + 180;
    if (alarm === 'week') return 7 * 1440 - 540 + t;
    return t > 540 ? t - 540 : 30;   // morning; an event earlier than that is announced 30 minutes before
  }

  // ev: {uid, title, date:[y,m,d], time:'HH:MM' (optional: then it is a one-hour event in Japan time, not an all-day one), yearly:bool, every100:bool, alarm:'morning'|'eve'|'week'|'none', note}
  function vevent(ev, now) {
    var d = ev.date, end = C.addDays(d, 1), t = hm(ev.time), L = ['BEGIN:VEVENT', 'UID:' + ev.uid + '@atomou.com', 'DTSTAMP:' + stamp(now), 'SUMMARY:' + esc(ev.title)];
    if (t) {
      var endMin = t[0] * 60 + t[1] + 60, endDay = endMin >= 1440 ? end : d;
      L.push('DTSTART;TZID=Asia/Tokyo:' + wall(d, t[0], t[1]), 'DTEND;TZID=Asia/Tokyo:' + wall(endDay, Math.floor(endMin % 1440 / 60), endMin % 60), 'TRANSP:OPAQUE');
    } else L.push('DTSTART;VALUE=DATE:' + dateStr(d), 'DTEND;VALUE=DATE:' + dateStr(end), 'TRANSP:TRANSPARENT');
    if (ev.rrule) L.push('RRULE:' + ev.rrule);
    else if (ev.yearly) L.push('RRULE:FREQ=YEARLY' + (d[1] === 2 && d[2] === 29 ? ';BYMONTH=2;BYMONTHDAY=-1' : ''));
    if (ev.note) L.push('DESCRIPTION:' + esc(ev.note));
    if (ev.alarm && ev.alarm !== 'none') {
      L.push('BEGIN:VALARM', 'ACTION:DISPLAY', 'DESCRIPTION:' + esc(ev.title),
        'TRIGGER:' + (t ? dur(alertBefore(ev.alarm, t[0] * 60 + t[1])) : (ev.alarm === 'eve' ? '-PT3H' : ev.alarm === 'week' ? '-P6DT15H' : 'PT9H')), 'END:VALARM');
    }
    (ev.reminds || []).forEach(function (r) {   // "the days before" notices: 9:00 that many days earlier (an all-day event starts at 0:00)
      if (!(r >= 1)) return;
      L.push('BEGIN:VALARM', 'ACTION:DISPLAY', 'DESCRIPTION:' + esc('あと' + r + '日: ' + ev.title), 'TRIGGER:-P' + (r - 1) + 'DT15H', 'END:VALARM');
    });
    L.push('END:VEVENT');
    return L;
  }
  function build(events, name, now) {
    now = now || new Date();
    var L = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//atomou.com//あと何日、もう何日//JA', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', 'X-WR-CALNAME:' + esc(name || 'あと何日、もう何日'),
      'X-WR-TIMEZONE:Asia/Tokyo'];
    if (events.some(function (ev) { return hm(ev.time); })) {   // a fixed +09:00 zone, no summer time: every calendar app reads it
      L.push('BEGIN:VTIMEZONE', 'TZID:Asia/Tokyo', 'BEGIN:STANDARD', 'DTSTART:19700101T000000', 'TZOFFSETFROM:+0900', 'TZOFFSETTO:+0900', 'TZNAME:JST', 'END:STANDARD', 'END:VTIMEZONE');
    }
    events.forEach(function (ev) {
      vevent(ev, now).forEach(function (l) { L.push(l); });
      if (ev.every100) {  // the 100-day marks of a date (100, 200, ...): one repeating event, the first one 100 days after the date
        vevent({ uid: ev.uid + '-100', title: ev.title + '(100日ごとの節目)', date: C.addDays(ev.date, 100), rrule: 'FREQ=DAILY;INTERVAL=100;COUNT=60', alarm: ev.alarm }, now)
          .forEach(function (l) { L.push(l); });
      }
    });
    L.push('END:VCALENDAR');
    return L.map(fold).join('\r\n') + '\r\n';
  }
  function download(filename, text) {
    var blob = new Blob([text], { type: 'text/calendar;charset=utf-8' }), url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = filename; document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(url); a.remove(); }, 1000);
  }
  root.AtomouICS = { build: build, download: download, fold: fold, esc: esc };
})(typeof window !== 'undefined' ? window : this);
