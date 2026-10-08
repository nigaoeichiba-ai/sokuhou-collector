/* あと何日、もう何日: date arithmetic.  The same rules as sites/atomou/datecore.py (checked against tests/fixtures/atomou/date_vectors.json in a real Chrome).
   Calendar dates only: [year, month, day]; no Date object, no time zone, so a visitor's clock can never move a date by a day.
   "Today" is passed in by the caller. */
(function (root) {
  'use strict';
  var ERAS = { reiwa: 2018, heisei: 1988, showa: 1925, taisho: 1911, meiji: 1867 };
  var SHORT_DAYS = 100;

  function isLeap(y) { return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0; }
  function dim(y, m) { return [31, isLeap(y) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]; }
  function valid(y, m, d) { return y >= 1 && m >= 1 && m <= 12 && d >= 1 && d <= dim(y, m); }

  // days since 1970-01-01 (proleptic Gregorian), Howard Hinnant's algorithm
  function toDays(y, m, d) {
    y -= m <= 2 ? 1 : 0;
    var era = Math.floor(y / 400), yoe = y - era * 400;
    var doy = Math.floor((153 * (m + (m > 2 ? -3 : 9)) + 2) / 5) + d - 1;
    var doe = yoe * 365 + Math.floor(yoe / 4) - Math.floor(yoe / 100) + doy;
    return era * 146097 + doe - 719468;
  }
  function fromDays(z) {
    z += 719468;
    var era = Math.floor(z / 146097), doe = z - era * 146097;
    var yoe = Math.floor((doe - Math.floor(doe / 1460) + Math.floor(doe / 36524) - Math.floor(doe / 146096)) / 365);
    var y = yoe + era * 400, doy = doe - (365 * yoe + Math.floor(yoe / 4) - Math.floor(yoe / 100));
    var mp = Math.floor((5 * doy + 2) / 153), d = doy - Math.floor((153 * mp + 2) / 5) + 1, m = mp + (mp < 10 ? 3 : -9);
    return [y + (m <= 2 ? 1 : 0), m, d];
  }
  function parse(s) {  // 'YYYY-MM-DD' -> [y, m, d] or null
    var r = /^(\d{1,4})-(\d{2})-(\d{2})$/.exec(String(s));
    if (!r) return null;
    var y = +r[1], m = +r[2], d = +r[3];
    return valid(y, m, d) ? [y, m, d] : null;
  }
  function pad(n, w) { n = String(n); while (n.length < w) n = '0' + n; return n; }
  function iso(a) { return pad(a[0], 4) + '-' + pad(a[1], 2) + '-' + pad(a[2], 2); }
  function cmp(a, b) { return toDays(a[0], a[1], a[2]) - toDays(b[0], b[1], b[2]); }
  function addDays(a, n) { return fromDays(toDays(a[0], a[1], a[2]) + n); }
  function addMonths(a, n) {
    var total = a[0] * 12 + (a[1] - 1) + n, y = Math.floor(total / 12), m = total - y * 12 + 1;
    return [y, m, Math.min(a[2], dim(y, m))];
  }
  function totalDays(a, b) { return toDays(b[0], b[1], b[2]) - toDays(a[0], a[1], a[2]); }
  function ymd(a, b) {
    var s = cmp(a, b) <= 0 ? a : b, e = cmp(a, b) <= 0 ? b : a;
    var n = (e[0] - s[0]) * 12 + (e[1] - s[1]);
    if (cmp(addMonths(s, n), e) > 0) n -= 1;
    var base = addMonths(s, n);
    return [Math.floor(n / 12), n % 12, totalDays(base, e)];
  }
  function nextThousand(start, today) {
    var since = totalDays(start, today);
    var k = since > 0 ? Math.max(1, Math.ceil(since / 1000)) : 1;
    return { days: k * 1000, date: addDays(start, k * 1000) };
  }
  function dayOfYear(d) {
    var n = totalDays([d[0], 1, 1], d) + 1, total = isLeap(d[0]) ? 366 : 365;
    return [n, total - n];
  }
  function fiscalYear(d) {
    var y = d[1] >= 4 ? d[0] : d[0] - 1;
    return [y, totalDays([y, 4, 1], d) + 1, totalDays(d, [y + 1, 3, 31])];
  }
  function warekiToYear(era, n) { return ERAS[era] + n; }
  function unitText(y, m, d) {
    var p = '';
    if (y) p += y + '年';
    if (m) p += m + 'か月';
    if (d || !p) p += d + '日';
    return p;
  }
  function group(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }

  function countdown(target, today, precision) {
    precision = precision || 'day';
    var n;
    if (precision === 'year') {
      n = today[0] - target[0];
      return { dir: n > 0 ? 'mou' : n < 0 ? 'ato' : 'today', big: n === 0 ? '今年' : (n > 0 ? 'もう' : 'あと') + '約' + group(Math.abs(n)) + '年', sub: '', total: null, approx: true };
    }
    if (precision === 'month') {
      n = (today[0] - target[0]) * 12 + (today[1] - target[1]);
      var a = Math.abs(n), txt = a ? unitText(Math.floor(a / 12), a % 12, 0) : '今月';
      return { dir: n > 0 ? 'mou' : n < 0 ? 'ato' : 'today', big: a === 0 ? txt : (n > 0 ? 'もう約' : 'あと約') + txt, sub: '', total: null, approx: true };
    }
    var t = totalDays(today, target);
    if (t === 0) return { dir: 'today', big: '今日', sub: '', total: 0, approx: false };
    var word = t > 0 ? 'あと' : 'もう', dir = t > 0 ? 'ato' : 'mou', b = ymd(today, target);
    if (Math.abs(t) <= SHORT_DAYS) return { dir: dir, big: word + Math.abs(t) + '日', sub: '', total: t, approx: false };
    return { dir: dir, big: word + unitText(b[0], b[1], b[2]), sub: group(Math.abs(t)) + '日', total: t, approx: false };
  }

  var api = { isLeap: isLeap, dim: dim, valid: valid, toDays: toDays, fromDays: fromDays, parse: parse, iso: iso, cmp: cmp, addDays: addDays, addMonths: addMonths,
    totalDays: totalDays, ymd: ymd, nextThousand: nextThousand, dayOfYear: dayOfYear, fiscalYear: fiscalYear, warekiToYear: warekiToYear, countdown: countdown, group: group };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.AtomouCore = api;
})(typeof window !== 'undefined' ? window : this);
