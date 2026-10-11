/* Send the visitor's days to a calendar of their own in Google Calendar, straight from the browser (no server of ours is involved, nothing is stored by us).
   The only permission asked is calendar.app.created: it can make a calendar of its own and manage the events on that calendar, and nothing else (it cannot read or change the
   visitor's other calendars).  One way only: what is in this app goes to Google when the visitor presses the button; a change made later in Google is not read back.
   Event ids are made from our own ids (base32hex, as the API wants), so sending twice updates instead of duplicating.  Wording on the site: "Google カレンダーに送る". */
(function (root) {
  'use strict';
  var C = root.AtomouCore, ICS = root.AtomouICS;
  var SCOPE = 'https://www.googleapis.com/auth/calendar.app.created';
  var API = 'https://www.googleapis.com/calendar/v3';
  var NAME = 'あと何日、もう何日';
  var ALPHA = '0123456789abcdefghijklmnopqrstuv';

  function idOf(uid) {   // base32hex of the UTF-8 bytes: only 0-9 and a-v, 5 to 1024 characters
    var bytes = new TextEncoder().encode(String(uid)), out = '', bits = 0, acc = 0;
    for (var i = 0; i < bytes.length; i++) {
      acc = (acc << 8) | bytes[i]; bits += 8;
      while (bits >= 5) { out += ALPHA[(acc >> (bits - 5)) & 31]; bits -= 5; }
      acc &= (1 << bits) - 1;
    }
    if (bits) out += ALPHA[(acc << (5 - bits)) & 31];
    while (out.length < 5) out += '0';
    return out;
  }
  function hm(t) { var m = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(t || ''); return m ? [+m[1], +m[2]] : null; }
  function p2(n) { return (n < 10 ? '0' : '') + n; }

  // the alerts, in minutes before the start (the API takes 0 to 40320).  A day without a time starts at 0:00, so "the morning of the day" (9:00 after the start) cannot be said: it is
  // the start of the day instead; the evening before (21:00) and the week before (9:00, 7 days earlier) are exact.
  function overrides(ev, t) {
    var out = [], tm = t ? t[0] * 60 + t[1] : 0;
    if (ev.alarm && ev.alarm !== 'none') {
      var m = t ? ICS.alertBefore(ev.alarm, tm) : (ev.alarm === 'eve' ? 180 : ev.alarm === 'week' ? 6 * 1440 + 900 : 0);
      out.push(m);
    }
    (ev.reminds || []).forEach(function (r) { if (r >= 1) out.push(r * 1440 + tm - 540); });   // 9:00, r days before
    return out.filter(function (m, i, a) { return m >= 0 && m <= 40320 && a.indexOf(m) === i; }).slice(0, 5).map(function (m) { return { method: 'popup', minutes: m }; });
  }

  // ev: the same shape the calendar file takes: {uid, title, date:[y,m,d], time, yearly, rrule, alarm, reminds, note}
  function body(ev) {
    var d = ev.date, t = hm(ev.time), b = { id: idOf(ev.uid), summary: ev.title, reminders: { useDefault: false, overrides: overrides(ev, t) } };
    if (t) {
      var endMin = t[0] * 60 + t[1] + 60, endDay = endMin >= 1440 ? C.addDays(d, 1) : d;
      b.start = { dateTime: C.iso(d) + 'T' + p2(t[0]) + ':' + p2(t[1]) + ':00', timeZone: 'Asia/Tokyo' };
      b.end = { dateTime: C.iso(endDay) + 'T' + p2(Math.floor(endMin % 1440 / 60)) + ':' + p2(endMin % 60) + ':00', timeZone: 'Asia/Tokyo' };
      b.transparency = 'opaque';
    } else {
      b.start = { date: C.iso(d) };
      b.end = { date: C.iso(C.addDays(d, 1)) };
      b.transparency = 'transparent';
    }
    if (ev.rrule) b.recurrence = ['RRULE:' + ev.rrule];
    else if (ev.yearly) b.recurrence = ['RRULE:FREQ=YEARLY' + (d[1] === 2 && d[2] === 29 ? ';BYMONTH=2;BYMONTHDAY=-1' : '')];
    if (ev.note) b.description = ev.note;
    return b;
  }

  // the events to send: each of ours, and for a day with the 100-day marks the second, repeating one (as in the calendar file)
  function expand(events) {
    var out = [];
    events.forEach(function (ev) {
      out.push(ev);
      if (ev.every100) out.push({ uid: ev.uid + '-100', title: ev.title + '(100日ごとの節目)', date: C.addDays(ev.date, 100), rrule: 'FREQ=DAILY;INTERVAL=100;COUNT=60', alarm: ev.alarm });
    });
    return out;
  }

  // call(method, path, bodyObject) -> Promise of {status, json}; it never rejects for an HTTP status, only for a network failure
  function makeCall(tok, fetchImpl) {
    fetchImpl = fetchImpl || root.fetch.bind(root);
    return function (method, path, obj) {
      var opt = { method: method, headers: { Authorization: 'Bearer ' + tok } };
      if (obj !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(obj); }
      return fetchImpl(API + path, opt).then(function (r) {
        return (r.status === 204 ? Promise.resolve({}) : r.json().catch(function () { return {}; })).then(function (j) { return { status: r.status, json: j }; });
      });
    };
  }
  function eachLimited(list, n, fn) {   // n at a time, in order of arrival; the first failure stops what has not started
    var i = 0, failed = null;
    function next() {
      if (failed || i >= list.length) return Promise.resolve();
      var item = list[i++];
      return fn(item).then(next, function (e) { failed = failed || e; });
    }
    var runners = [];
    for (var k = 0; k < Math.min(n, list.length); k++) runners.push(next());
    return Promise.all(runners).then(function () { if (failed) throw failed; });
  }
  function fail(r, what) { var e = new Error(what + ' ' + r.status); e.status = r.status; return e; }

  function ensureCalendar(call, state) {
    if (state.cal) return Promise.resolve(state);
    return call('POST', '/calendars', { summary: NAME, timeZone: 'Asia/Tokyo' }).then(function (r) {
      if (r.status !== 200 || !r.json.id) throw fail(r, 'calendar');
      state.cal = r.json.id; state.sent = [];
      return state;
    });
  }
  // one event.  One we sent before is updated first (a deleted one answers 404 and is made again); a new one is inserted, and when that id is taken (409) it is updated.
  function upsert(call, cal, ev, known) {
    var b = body(ev), base = '/calendars/' + encodeURIComponent(cal) + '/events';
    function put() { return call('PUT', base + '/' + b.id, b); }
    function insert() {
      return call('POST', base, b).then(function (r) {
        if (r.status === 200) return 'added';
        if (r.status === 409) return put().then(function (u) { if (u.status !== 200) throw fail(u, 'update'); return 'updated'; });
        throw fail(r, 'insert');
      });
    }
    if (!known) return insert();
    return put().then(function (u) { if (u.status === 200) return 'updated'; if (u.status === 404 || u.status === 410) return insert(); throw fail(u, 'update'); });
  }
  function remove(call, cal, uid) {
    return call('DELETE', '/calendars/' + encodeURIComponent(cal) + '/events/' + idOf(uid)).then(function (r) {
      if (r.status !== 204 && r.status !== 200 && r.status !== 404 && r.status !== 410) throw fail(r, 'delete');
    });
  }

  // state: {cal, sent:[uids]} (kept with the visitor's settings).  Returns a Promise of {state, added, updated, removed}.  A calendar that was deleted in Google is made again once.
  function send(tok, events, state, fetchImpl) {
    var call = makeCall(tok, fetchImpl), list = expand(events), want = {}, st = { cal: (state && state.cal) || '', sent: ((state && state.sent) || []).slice() }, res = { added: 0, updated: 0, removed: 0 };
    list.forEach(function (e) { want[e.uid] = 1; });
    function run(again) {
      return ensureCalendar(call, st).then(function () {
        var had = {}; st.sent.forEach(function (u) { had[u] = 1; });
        return eachLimited(list, 4, function (ev) { return upsert(call, st.cal, ev, !!had[ev.uid]).then(function (k) { res[k]++; }); });
      }).then(function () {
        var stale = st.sent.filter(function (u) { return !want[u]; });
        return eachLimited(stale, 4, function (u) { return remove(call, st.cal, u).then(function () { res.removed++; }); });
      }).then(function () {
        st.sent = list.map(function (e) { return e.uid; });
        return { state: st, added: res.added, updated: res.updated, removed: res.removed };
      }, function (e) {
        if (again && e && e.status === 404 && st.cal) { st.cal = ''; st.sent = []; res.added = res.updated = res.removed = 0; return run(false); }   // the calendar is gone from Google
        throw e;
      });
    }
    return run(true);
  }
  // take the calendar away from Google (our own calendar only: that is all the permission reaches)
  function unlink(tok, state, fetchImpl) {
    var call = makeCall(tok, fetchImpl);
    if (!state || !state.cal) return Promise.resolve({ cal: '', sent: [] });
    return call('DELETE', '/calendars/' + encodeURIComponent(state.cal)).then(function (r) {
      if (r.status !== 204 && r.status !== 200 && r.status !== 404 && r.status !== 410) throw fail(r, 'calendar delete');
      return { cal: '', sent: [] };
    });
  }

  root.AtomouGcal = { SCOPE: SCOPE, NAME: NAME, idOf: idOf, body: body, expand: expand, overrides: overrides, send: send, unlink: unlink };
})(typeof window !== 'undefined' ? window : this);
