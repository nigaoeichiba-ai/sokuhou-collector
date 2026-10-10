/* あと何日、もう何日: date arithmetic.  The same rules as sites/atomou/datecore.py (checked against tests/fixtures/atomou/date_vectors.json in a real Chrome).
   Calendar dates only: [year, month, day]; no Date object, no time zone, so a visitor's clock can never move a date by a day.
   "Today" is passed in by the caller. */
// an uncaught error anywhere in the bundle is written on <html data-jserr>, so a headless test (and a person with the inspector) can see it
if (typeof window !== 'undefined' && window.addEventListener) {
  window.addEventListener('error', function (e) { try { document.documentElement.setAttribute('data-jserr', String(e && e.message || e).slice(0, 200)); } catch (x) {} });
  window.addEventListener('unhandledrejection', function (e) { try { document.documentElement.setAttribute('data-jserr', 'promise: ' + String(e && e.reason || e).slice(0, 200)); } catch (x) {} });
}
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

  // a date typed or dictated as words: "12月25日", "2027年3月3日", "令和8年4月1日", "二〇二七年三月三日", "2027/3/3", "明日" -> [y, m, d] ([y, m, 1] / [y, 1, 1] for the coarser
  // precisions), or null.  Without a year it is the next time that day comes (today counts).
  var KDIG = { '〇': 0, '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9 };
  var ERA_WORDS = { '令和': 'reiwa', '平成': 'heisei', '昭和': 'showa', '大正': 'taisho', '明治': 'meiji' };
  var REL_DAYS = { '今日': 0, '明日': 1, '明後日': 2, '昨日': -1, 'きょう': 0, 'あした': 1, 'あさって': 2, 'きのう': -1 };
  function kanjiNumbers(s) {   // 十二 -> 12, 二〇二七 -> 2027
    return s.replace(/[〇零一二三四五六七八九十百]+/g, function (k) {
      if (!/[十百]/.test(k)) return k.split('').map(function (c) { return KDIG[c]; }).join('');
      var n = 0, cur = 0, i, c;
      for (i = 0; i < k.length; i++) {
        c = k.charAt(i);
        if (c === '百') { n += (cur || 1) * 100; cur = 0; } else if (c === '十') { n += (cur || 1) * 10; cur = 0; } else cur = KDIG[c];
      }
      return String(n + cur);
    });
  }
  function parseSpoken(text, p, today) {
    var s = kanjiNumbers(String(text || '').normalize('NFKC').replace(/\s+/g, '')).replace(/[。.,、]+$/, '').replace(/元年/, '1年'), r, y, m, d;
    r = /^(令和|平成|昭和|大正|明治)(\d{1,2})年/.exec(s);
    if (r) s = (ERAS[ERA_WORDS[r[1]]] + +r[2]) + '年' + s.slice(r[0].length);
    if (p === 'day') {
      if (REL_DAYS.hasOwnProperty(s)) return addDays(today, REL_DAYS[s]);
      r = /^(\d{1,4})[年\/.\-](\d{1,2})[月\/.\-](\d{1,2})日?$/.exec(s);
      if (r) return +r[1] <= 2200 && valid(+r[1], +r[2], +r[3]) ? [+r[1], +r[2], +r[3]] : null;
      r = /^(\d{1,2})[月\/.](\d{1,2})日?$/.exec(s);
      if (!r) return null;
      for (y = today[0]; y <= today[0] + 8; y++) if (valid(y, +r[1], +r[2]) && cmp([y, +r[1], +r[2]], today) >= 0) return [y, +r[1], +r[2]];
      return null;
    }
    if (p === 'month') {
      r = /^(\d{1,4})[年\/.\-](\d{1,2})月?$/.exec(s);
      if (r) return +r[1] >= 1 && +r[1] <= 2200 && +r[2] >= 1 && +r[2] <= 12 ? [+r[1], +r[2], 1] : null;
      r = /^(\d{1,2})月$/.exec(s);
      if (!r || +r[1] < 1 || +r[1] > 12) return null;
      m = +r[1]; return [m < today[1] ? today[0] + 1 : today[0], m, 1];
    }
    r = /^(\d{1,4})年?$/.exec(s);
    return r && +r[1] >= 1 && +r[1] <= 2200 ? [+r[1], 1, 1] : null;
  }

  /* extractDays(text, today): the days written in a pasted text (a search result, an answer of an AI, a flyer's words) -> [{date:[y,m,d], iso, time, title, context}], nearest first,
     at most 8.  "2026年12月1日", "12月1日(火)", "12/1(火)", "令和8年12月1日" and a time near it ("19:00", "19時30分"; "開演" wins over "開場").  A day written without a year is the
     next such day from today.  The title is the sentence the day stands in (the day and the time cut out).  Nothing is guessed beyond the words: no LLM, no network. */
  var WD_CH = '月火水木金土日';
  function extractDays(text, today) {
    var src = String(text || '').normalize('NFKC').replace(/[\r\n]+/g, '\n'), found = [], seen = {}, re, m;
    function push(y, mo, d, at, len) {
      if (!valid(y, mo, d)) return;
      var key = y + '-' + mo + '-' + d;
      if (seen[key]) return;
      seen[key] = 1;
      var a = Math.max(src.lastIndexOf('\n', at), src.lastIndexOf('。', at), src.lastIndexOf('!', at), src.lastIndexOf('?', at)) + 1;
      var bn = src.indexOf('\n', at + len), bk = src.indexOf('。', at + len), b = Math.min(bn < 0 ? 1e9 : bn, bk < 0 ? 1e9 : bk, src.length);
      var sentence = src.slice(a, b).trim(), around = src.slice(at, Math.min(src.length, at + len + 60));
      var time = '', tm = /(開演|開始|スタート|START)[^0-9]{0,6}(\d{1,2})[:時](\d{2})?/.exec(around) || /(\d{1,2}):(\d{2})/.exec(around) || /(\d{1,2})時(?:(\d{1,2})分)?/.exec(around);
      if (tm) {
        var hh = +(tm[1] && /^\d/.test(tm[1]) ? tm[1] : tm[2]), mm = tm[1] && /^\d/.test(tm[1]) ? +(tm[2] || 0) : +(tm[3] || 0);
        if (hh >= 0 && hh <= 23 && mm >= 0 && mm <= 59) time = (hh < 10 ? '0' : '') + hh + ':' + (mm < 10 ? '0' : '') + mm;
      }
      var title = sentence.replace(/(令和|平成|昭和)?\d{1,4}年\s*\d{1,2}月\s*\d{1,2}日|\d{1,2}月\s*\d{1,2}日|\d{1,2}\/\d{1,2}/g, ' ').replace(/[\(（][月火水木金土日](?:曜日?)?[\)）]|[月火水木金土日]曜日/g, ' ').replace(/\d{1,2}[:時]\d{0,2}分?/g, ' ').replace(/[\s　、,:：\-~〜～]+/g, ' ').replace(/^[\s・●○■□▼▲]+|[\s　]+$/g, '').trim().slice(0, 40);
      found.push({ date: [y, mo, d], iso: iso([y, mo, d]), time: time, title: title, context: src.slice(Math.max(0, at - 20), Math.min(src.length, at + len + 40)).replace(/\n/g, ' ').trim() });
    }
    function nextYear(mo, d) {
      var y = today[0];
      if (!valid(y, mo, d)) { if (valid(y + 1, mo, d)) return y + 1; return 0; }
      return cmp([y, mo, d], today) >= -30 ? y : y + 1;   // a day up to a month past is still this year's
    }
    re = /(令和|平成|昭和)\s*(\d{1,2}|元)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日/g;
    while ((m = re.exec(src))) push(({ '令和': 2018, '平成': 1988, '昭和': 1925 })[m[1]] + (m[2] === '元' ? 1 : +m[2]), +m[3], +m[4], m.index, m[0].length);
    re = /(\d{4})\s*[年\/.\-]\s*(\d{1,2})\s*[月\/.\-]\s*(\d{1,2})\s*日?/g;
    while ((m = re.exec(src))) push(+m[1], +m[2], +m[3], m.index, m[0].length);
    re = /(^|[^\d\/])(\d{1,2})\s*月\s*(\d{1,2})\s*日/g;
    while ((m = re.exec(src))) { var y1 = nextYear(+m[2], +m[3]); if (y1) push(y1, +m[2], +m[3], m.index + m[1].length, m[0].length - m[1].length); }
    re = /(^|[^\d\/.])(\d{1,2})\/(\d{1,2})(?=[\(（日]|[月火水木金土](?!\d)|\s|$|[。、])(?:[\(（][月火水木金土日][\)）])?/g;
    while ((m = re.exec(src))) { var y2 = nextYear(+m[2], +m[3]); if (y2 && +m[2] <= 12) push(y2, +m[2], +m[3], m.index + m[1].length, m[0].length - m[1].length); }
    found.sort(function (a, b) { return a.iso < b.iso ? -1 : a.iso > b.iso ? 1 : 0; });
    var future = found.filter(function (x) { return cmp(x.date, today) >= -30; });
    return (future.length ? future : found).slice(0, 8);
  }

  var api = { extractDays: extractDays, parseSpoken: parseSpoken, isLeap: isLeap, dim: dim, valid: valid, toDays: toDays, fromDays: fromDays, parse: parse, iso: iso, cmp: cmp, addDays: addDays, addMonths: addMonths,
    totalDays: totalDays, ymd: ymd, nextThousand: nextThousand, dayOfYear: dayOfYear, fiscalYear: fiscalYear, warekiToYear: warekiToYear, countdown: countdown, group: group };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.AtomouCore = api;
})(typeof window !== 'undefined' ? window : this);
