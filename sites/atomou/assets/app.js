/* あと何日、もう何日 -- the browser side.
   Everything a visitor enters stays in this browser (localStorage "atomou.v1"); nothing is sent anywhere.  The server only ships the pages and
   assets/catalog.json (the verified public dates).  "Today" is the device's calendar date (or ?today=YYYY-MM-DD, used by the tests). */
(function () {
  'use strict';
  var C = window.AtomouCore, ICS = window.AtomouICS, CONF = window.ATOMOU || { groups: [], slugs: [], skins: {}, v: '' };
  var KEY = 'atomou.v1', WD = '日月火水木金土';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var H = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var page = document.body.getAttribute('data-page') || '';

  /* ---------- today ---------- */
  function params() {
    var o = {}, q = location.search.replace(/^\?/, '');
    q.split('&').forEach(function (kv) {
      if (!kv) return;
      var i = kv.indexOf('=');
      try { o[decodeURIComponent((i < 0 ? kv : kv.slice(0, i)).replace(/\+/g, ' '))] = i < 0 ? '' : decodeURIComponent(kv.slice(i + 1).replace(/\+/g, ' ')); } catch (e) { /* ignore a broken pair */ }
    });
    return o;
  }
  var P = params();
  var SUBCAP = P.today && +P.cap >= 3 ? +P.cap : 24;   // how many small chips before the rest become one "その他" (the tests lower it)
  var TODAY = (function () {
    var p = P.today && /^\d{4}-\d{2}-\d{2}$/.test(P.today) ? C.parse(P.today) : null;
    if (p) return p;
    var n = new Date();
    return [n.getFullYear(), n.getMonth() + 1, n.getDate()];
  })();

  /* ---------- state ---------- */
  var S = blank(), brokenSaved = false;
  var BLOCK_IDS = ['todo', 'live', 'search', 'cats', 'daily', 'mine', 'interests', 'region', 'soon', 'record', 'usecases'], KIND_IDS = ['event', 'anniversary', 'birthday', 'memorial', 'since', 'until', 'memo'];
  function statsDefault() {  // statistics are on unless the browser says "do not track" (DNT / Global Privacy Control)
    try { return !(navigator.doNotTrack === '1' || window.doNotTrack === '1' || navigator.globalPrivacyControl === true); } catch (e) { return true; }
  }
  function blank() { return { v: 1, updated: '', entries: [], deleted: [], saved: [], order: [], genre: {}, interests: [], notes: {}, prefs: { skin: 'basic', big: false, skinAuto: false, skinNight: 'dark', nightAsked: false, alarm: 'morning', stats: statsDefault(), push: false, pushHash: '', blocks: { order: [], hidden: [] }, tour: {}, intro: false } }; }
  function oneOf(v, list, dflt) { return list.indexOf(v) >= 0 ? v : dflt; }
  function cleanEntry(e) {  // whatever is in storage (or in a restored backup, or in a synced file) is reduced to known shapes before it can reach the page
    if (!e || typeof e !== 'object') return null;
    var id = String(e.id || ''), d = C.parse(String(e.date));
    if (!/^[A-Za-z0-9_-]{1,40}$/.test(id) || !d) return null;
    var kind = oneOf(e.kind, KIND_IDS, 'memo');
    return { id: id, title: String(e.title == null ? '' : e.title).slice(0, 80), date: C.iso(d), precision: oneOf(e.precision, ['day', 'month', 'year'], 'day'), kind: kind,
      quiet: !!e.quiet || kind === 'memorial', yearly: !!e.yearly, every100: !!e.every100, alarm: oneOf(e.alarm, ['', 'morning', 'eve', 'week', 'none'], ''),   // '' = follow the setting on the my page
      time: /^([01]\d|2[0-3]):[0-5]\d$/.test(String(e.time)) ? e.time : '', created: /^\d{4}-\d{2}-\d{2}$/.test(String(e.created)) ? e.created : '' };
  }
  function cleanNotes(n) {  // memo and "do this N days before" tasks, per day (key c:<catalogue id> or m:<own id>)
    var out = {}, keys = n && typeof n === 'object' ? Object.keys(n).slice(0, 300) : [];
    keys.forEach(function (k) {
      var v = n[k];
      if (!/^[cm]:[A-Za-z0-9_-]{1,40}$/.test(k) || !v || typeof v !== 'object') return;
      var tasks = (Array.isArray(v.tasks) ? v.tasks : []).slice(0, 30).map(function (t) {
        if (!t || typeof t !== 'object') return null;
        var b = Math.floor(+t.before), text = String(t.text == null ? '' : t.text).slice(0, 80);
        return (b >= 0 && b <= 365 && text) ? { id: /^[a-z0-9]{1,12}$/.test(String(t.id)) ? t.id : Math.random().toString(36).slice(2, 8), before: b, text: text, done: !!t.done } : null;
      }).filter(Boolean), memo = String(v.memo == null ? '' : v.memo).slice(0, 600);
      var remind = (Array.isArray(v.remind) ? v.remind : []).map(function (r) { return Math.floor(+r); }).filter(function (r, i, l) { return r >= 1 && r <= 365 && l.indexOf(r) === i; }).sort(function (a, b) { return b - a; }).slice(0, 12);   // days before: a notice for each
      var slot = v.remindSlot === 'e' ? 'e' : 'm', mute = v.mute === true;   // morning (default) or the evening before the day's count; mute = no notice at all for this day
      if (memo || tasks.length || remind.length || mute) out[k] = { memo: memo, tasks: tasks, remind: remind, remindSlot: slot, mute: mute };
    });
    return out;
  }
  function cleanInterests(list) {   // the fields (subjects) and words the visitor likes: short plain text, at most 30
    var out = [];
    (Array.isArray(list) ? list : []).forEach(function (w) {
      w = String(w == null ? '' : w).replace(/[\u0000-\u001f<>"'&\\]/g, '').trim().slice(0, 24);
      if (w && out.indexOf(w) < 0 && out.length < 30) out.push(w);
    });
    return out;
  }
  function normalize(o) {
    var s = blank(), p = (o && o.prefs) || {};
    o = o || {};
    s.updated = /^\d{4}-\d{2}-\d{2}T[\d:.]+Z$/.test(String(o.updated)) ? o.updated : '';
    s.entries = (Array.isArray(o.entries) ? o.entries : []).map(cleanEntry).filter(Boolean);
    s.deleted = (Array.isArray(o.deleted) ? o.deleted : []).filter(function (x) { return /^[A-Za-z0-9_-]{1,40}$/.test(String(x)); }).slice(-300);
    s.saved = (Array.isArray(o.saved) ? o.saved : []).filter(function (x) { return /^[0-9a-f]{10}$/.test(String(x)); });
    s.notes = cleanNotes(o.notes);
    s.interests = cleanInterests(o.interests);
    s.order = (Array.isArray(o.order) ? o.order : []).filter(function (x) { return /^[cm]:[A-Za-z0-9_-]{1,40}$/.test(String(x)); });
    (CONF.groups || []).forEach(function (g) { var n = o.genre && +o.genre[g]; if (n > 0) s.genre[g] = Math.min(20, Math.floor(n)); });
    s.prefs.skin = CONF.skins[p.skin] ? p.skin : 'basic';
    s.prefs.big = !!p.big;
    s.prefs.skinAuto = !!p.skinAuto;   // follow the device: the night skin when the device is set dark
    s.prefs.skinNight = CONF.skins[p.skinNight] && CONF.skins[p.skinNight].dark ? p.skinNight : 'dark';
    s.prefs.nightAsked = !!p.nightAsked;
    s.prefs.alarm = oneOf(p.alarm, ['morning', 'eve', 'week', 'none'], 'morning');
    s.prefs.stats = p.stats === undefined ? statsDefault() : !!p.stats;
    s.prefs.push = !!p.push;
    s.prefs.pushHash = /^[0-9me,-]{0,4000}$/.test(String(p.pushHash || '')) ? String(p.pushHash || '') : '';
    s.prefs.tour = {};
    s.prefs.intro = p.intro === true;
    s.prefs.setup = p.setup === true;
    s.prefs.pager = p.pager === true;
    s.prefs.liveAlert = p.liveAlert === true;   // announce a new official headline that matches the visitor's words (assets/live.js)   // the home lists as pages to turn (assets/swipe.js)   // the first-visit setup was done (or put off)
    s.prefs.genres = Array.isArray(p.genres) ? p.genres.filter(function (g, i, a) { return CONF.groups.indexOf(g) >= 0 && a.indexOf(g) === i; }) : [];   // the genres the visitor chose: the home page leans to them
    s.prefs.region = CONF.regions && CONF.regions.indexOf(p.region) >= 0 ? p.region : '';   // the prefecture the visitor lives in (this device only): days near it come first
    s.prefs.shares = Math.max(0, Math.min(9999, Math.floor(+p.shares) || 0));   // how many times a day was sent (the plan: sending earns room for more cards)
    ['home', 'calendar', 'plan', 'add', 'search'].forEach(function (k) { if (p.tour && p.tour[k] === true) s.prefs.tour[k] = true; });
    s.prefs.seasonOff = /^[a-z0-9-]{1,30}$/.test(String(p.seasonOff)) && CONF.skins[p.seasonOff] ? p.seasonOff : '';
    var b = p.blocks || {};
    s.prefs.blocks = { order: (Array.isArray(b.order) ? b.order : []).filter(function (k) { return BLOCK_IDS.indexOf(k) >= 0; }),
      hidden: (Array.isArray(b.hidden) ? b.hidden : []).filter(function (k) { return BLOCK_IDS.indexOf(k) >= 0; }) };
    return s;
  }
  function load() {
    var raw = null;
    try {
      raw = localStorage.getItem(KEY);
      if (raw) return normalize(JSON.parse(raw));
    } catch (e) {
      if (raw) {  // unreadable data: keep a copy before anything is written over it, and say so
        brokenSaved = true;
        try { localStorage.setItem(KEY + '.broken', raw); } catch (e2) { /* nothing more can be done */ }
      }
    }
    return blank();
  }
  function mergeStates(a, b) {  // a = this device, b = the synced file (both normalised): entries are united, the newer side wins on settings
    var newer = a.updated >= b.updated ? a : b, older = newer === a ? b : a, del = {}, byId = {}, out = blank();
    a.deleted.concat(b.deleted).forEach(function (id) { del[id] = 1; });
    older.entries.concat(newer.entries).forEach(function (e) { byId[e.id] = e; });
    out.entries = Object.keys(byId).filter(function (id) { return !del[id]; }).map(function (id) { return byId[id]; });
    out.deleted = Object.keys(del).slice(-300);
    out.saved = older.saved.concat(newer.saved).filter(function (x, i, l) { return l.indexOf(x) === i; });
    out.order = newer.order.slice();
    out.interests = cleanInterests(older.interests.concat(newer.interests));
    out.notes = Object.assign({}, older.notes, newer.notes);
    Object.keys(out.notes).forEach(function (k) { if (k.charAt(0) === 'm' && del[k.slice(2)]) delete out.notes[k]; });
    Object.keys(older.genre).concat(Object.keys(newer.genre)).forEach(function (g) { out.genre[g] = Math.max(older.genre[g] || 0, newer.genre[g] || 0); });
    out.prefs = JSON.parse(JSON.stringify(newer.prefs));
    out.updated = newer.updated;
    return out;
  }
  var warned = false;
  var savedT = null;
  function persist() {
    S.updated = new Date().toISOString();
    clearTimeout(savedT);
    savedT = setTimeout(function () { document.dispatchEvent(new CustomEvent('atomou:saved')); }, 600);   // the notice lists (push, mail) follow every change, not only the next page load
    try { localStorage.setItem(KEY, JSON.stringify(S)); return true; } catch (e) {
      if (!warned) { warned = true; toast('この端末に保存できません。プライベートモードなどでは、ページを閉じると消えます。'); }
      return false;
    }
  }
  S = load();
  if (brokenSaved) setTimeout(function () { toast('保存したデータを読み込めませんでした。元のデータはそのまま残っています。'); }, 300);

  /* ---------- usage statistics: counts of fixed items only (no text, no dates, no ids); see /privacy/#stats ---------- */
  var STAT_RE = /^(view|skin|big|home_order|home_hidden|act)(:[a-z0-9_,-]{1,60}){1,2}$/, statQ = {}, statN = 0;
  function stat(name) {
    if (!S.prefs.stats || !STAT_RE.test(name) || name.length > 80 || statN >= 40) return;
    if (!statQ[name]) statN++;
    statQ[name] = Math.min(50, (statQ[name] || 0) + 1);
  }
  function flushStats() {
    if (!statN) return;
    var body = JSON.stringify({ v: 1, c: statQ });
    statQ = {}; statN = 0;
    try { if (navigator.sendBeacon) navigator.sendBeacon('/api/e.php', new Blob([body], { type: 'text/plain' })); } catch (e) { /* statistics are never worth an error */ }
  }
  document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'hidden') flushStats(); });
  window.addEventListener('pagehide', flushStats);

  /* ---------- small helpers ---------- */
  var toastTimer;
  function toast(msg) {
    var t = $('#toast');
    if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    t.className = 'toast'; t.textContent = msg; t.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.hidden = true; }, 4200);
  }
  function toastAct(msg, label, fn) {   // a message with one button (undo)
    var t = $('#toast');
    if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    t.className = 'toast act'; t.innerHTML = '<span></span><button type="button" class="btn small ghost"></button>';
    t.firstChild.textContent = msg; t.lastChild.textContent = label; t.hidden = false;
    t.lastChild.addEventListener('click', function () { t.hidden = true; clearTimeout(toastTimer); fn(); });
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.hidden = true; }, 7000);
  }
  function wd(a) { return WD.charAt(((C.toDays(a[0], a[1], a[2]) % 7) + 11) % 7); }
  function fmtDate(iso, p) {
    var a = C.parse(iso);
    if (!a) return '';
    if (p === 'year') return a[0] + '年ごろ';
    if (p === 'month') return a[0] + '年' + a[1] + '月ごろ';
    return a[0] + '年' + a[1] + '月' + a[2] + '日(' + wd(a) + ')';
  }
  function host(u) { try { return new URL(u).hostname.replace(/^www\./, ''); } catch (e) { return ''; } }
  function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
  function download(name, text, type) {
    var blob = new Blob([text], { type: type || 'application/json' }), url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = name; document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(url); a.remove(); }, 1000);
  }

  /* ---------- kinds of personal days ---------- */
  var KINDS = {
    event: { t: '予定', d: 'デート、会議、用事', g: 1, yearly: false, r100: false, time: true, words: ['デート', '会議', '打ち合わせ', '病院', '旅行の予定'] },
    anniversary: { t: '記念日', d: '結婚、付き合った日、開店', g: 3, yearly: true, r100: true, words: ['結婚記念日', '付き合った日', '出会った日', '開店した日'] },
    birthday: { t: '誕生日', d: '家族・友だち・推し', g: 2, yearly: true, r100: false, words: ['の誕生日', '家族の誕生日', '推しの誕生日'] },
    memorial: { t: '大切な人を思う日', d: '命日・ペット・あの日', g: 0, yearly: true, r100: false, quiet: true, words: ['命日', 'ペットの命日', 'あの日'] },
    since: { t: 'はじめた日', d: '禁煙、転職、引っ越し', g: 4, yearly: false, r100: true, words: ['禁煙をはじめた日', '引っ越した日', '転職した日', 'ダイエットをはじめた日'] },
    until: { t: '楽しみな日・期限', d: '旅行・試験・提出・ライブ', g: 1, yearly: false, r100: false, words: ['旅行', '試験', 'ライブ', '提出の期限'] },
    memo: { t: 'そのほか', d: 'どんな日でも', g: 6, yearly: false, r100: false, words: [] }
  };

  /* ---------- counting (the card's big number) ---------- */
  function split(r) {
    var w = r.big.slice(0, 2);
    return (w === 'あと' || w === 'もう') ? [w, r.big.slice(2)] : ['', r.big];
  }
  function occ(d, y) { return (d[1] === 2 && d[2] === 29 && !C.isLeap(y)) ? [y, 2, 28] : [y, d[1], d[2]]; }
  function nextYearly(d, today) {
    var c = occ(d, today[0]);
    return C.cmp(c, today) < 0 ? occ(d, today[0] + 1) : c;
  }
  function nextRound(d, today, step) {
    var n = C.totalDays(d, today), k = Math.max(1, Math.ceil(n / step));
    return { n: k * step, date: C.addDays(d, k * step) };
  }
  function nextLines(e, today) {  // the milestones under a personal day
    var out = [], d = C.parse(e.date);
    if (!d || e.precision !== 'day' || C.totalDays(d, today) <= 0) return out;
    function when(a, label) {
      var r = C.countdown(a, today, 'day');
      return label + ' ' + a[1] + '月' + a[2] + '日・' + (r.dir === 'today' ? '今日' : r.big);
    }
    if (e.yearly) {
      var y = nextYearly(d, today), n = y[0] - d[0];
      out.push(when(y, e.kind === 'birthday' ? '次の誕生日(' + n + '歳)' : e.kind === 'memorial' ? '次の同じ日(' + n + '年目)' : '次の記念日(' + n + '年目)'));
    }
    if (!e.quiet && e.kind !== 'birthday') {
      var s = nextRound(d, today, e.every100 ? 100 : 1000);
      out.push(when(s.date, '次の節目(' + C.group(s.n) + '日目)'));
    }
    return out;
  }

  /* gentle, plain suggestions under a personal day (written by hand; no AI, no sales talk; a memorial day never gets congratulations or products) */
  var NENKI = { 1: '一周忌', 2: '三回忌', 6: '七回忌', 12: '十三回忌', 16: '十七回忌', 22: '二十三回忌', 26: '二十七回忌', 32: '三十三回忌' };
  function lastYearly(d, today) { var c = occ(d, today[0]); return C.cmp(c, today) > 0 ? occ(d, today[0] - 1) : c; }
  function tipFor(e, today) {
    var d = C.parse(e.date);
    if (!d || e.precision !== 'day' || C.totalDays(d, today) <= 0) return '';
    var next, left, passed;
    if (e.kind === 'memorial') {
      next = nextYearly(d, today); left = C.totalDays(today, next);
      var n = next[0] - d[0];
      if (NENKI[n] && !/あの日|震災|災害|事故|事件/.test(e.title)) {
        if (left === 0) return '今日は' + NENKI[n] + 'にあたります。';
        if (left <= 150) return 'もうすぐ' + NENKI[n] + 'にあたります。法要の日取りは、早めに家族と相談しておくと安心です。';
      }
      if (left > 0 && left <= 30) return 'まもなく同じ日です。花やお供えは、早めに用意できます。';
      return '';
    }
    if (e.yearly) {
      next = nextYearly(d, today); left = C.totalDays(today, next); passed = C.totalDays(lastYearly(d, today), today);
      var bd = e.kind === 'birthday';
      if (left === 0) return bd ? '今日は誕生日です。メッセージを送りませんか。' : '今日は記念日です。';
      if (left <= 14) return left + '日後です。プレゼントやお店の予約は、もう決まりましたか？';
      if (passed >= 1 && passed <= 30) return bd ? '誕生日を少し過ぎました。メッセージは、いまからでも間に合います。' : '記念日を少し過ぎました。まだなら、食事やプレゼントを考えてもよさそうです。';
      return '';
    }
    if (!e.quiet && e.kind === 'since') {
      var r = nextRound(d, today, e.every100 ? 100 : 1000);
      var gap = C.totalDays(today, r.date);
      if (gap >= 0 && gap <= 7) return 'もうすぐ' + C.group(r.n) + '日目です。ここまでの日々を、少し振り返ってみませんか。';
    }
    return '';
  }

  /* ---------- cards (the same markup as build.py card_html) ---------- */
  function catItem(c) {
    return { key: 'c:' + c.id, id: c.id, title: c.title, date: c.date, p: c.precision || 'day', g: CONF.groups.indexOf(c.group) + 1, kind: c.subject || c.category || c.kind, what: c.what || c.kind, kword: c.kind, place: c.place != null ? c.place : (c.region || ''), quiet: !!c.quiet,
      cat: c.mid, sub: c.subject, own: false, href: '/e/' + c.id + '/', est: !!c.estimated, typical: c.typical || '' };
  }
  function ownItem(e) {
    var k = KINDS[e.kind] || KINDS.memo;
    return { key: 'm:' + e.id, id: e.id, title: e.title, date: e.date, p: e.precision || 'day', g: k.g, kind: k.t, quiet: !!e.quiet, own: true, time: e.time || '', yearly: !!e.yearly, every100: !!e.every100 };
  }
  function cardHtml(it) {
    var h = '<article class="card' + (it.quiet ? ' quiet' : '') + '" data-key="' + H(it.key) + '" data-title="' + H(it.title) + '" data-date="' + H(it.date) + '" data-p="' + H(it.p) + '"' + (it.est ? ' data-est="1"' : '') +
      (it.g ? ' data-g="' + it.g + '"' : '') + (it.cat ? ' data-cat="' + H(it.cat) + '"' : '') + (it.cat && it.sub ? ' data-sub="' + H(it.sub) + '"' : '') + '>';
    h += '<div class="c-top">' + (it.g ? '<span class="mark m' + it.g + '" data-g="' + it.g + '" aria-hidden="true"></span>' : '') + '<span class="badge">' + H(it.kind) + '</span>' +
      (it.what ? '<span class="what">' + H(it.what) + '</span>' : '') + '</div>';
    h += '<p class="c-count"><span class="word"></span><span class="num"></span><span class="rel"></span></p><p class="c-sub"></p>';
    h += '<h3 class="c-title">' + (it.href ? '<a href="' + H(it.href) + '">' + H(it.title) + '</a>' : H(it.title)) + '</h3>';
    h += '<p class="c-date">' + H(it.est && it.typical ? it.typical : fmtDate(it.date, it.p)) + (it.time ? ' ' + H(it.time) : '') + (it.kword ? ' ' + H(it.kword) : '') +
      (it.place && it.place !== '全国' ? '<span class="pl"><b>' + (['改定', '終了', '施行', '改正', '締切'].indexOf(it.kind) >= 0 ? '対象地域' : '場所') + '</b>' + H(it.place) + '</span>' : '') + '</p>';
    if (it.own) h += '<div class="c-next"></div>';
    h += '<div class="c-act">';
    if (!it.own) h += '<button type="button" class="btn small" data-act="save" aria-pressed="false">☆ 予定に入れる</button><a class="btn small ghost" href="' + H(it.href) + '">詳細</a>';
    if (it.own) h += '<a class="btn small" href="/plan/?key=' + H(it.key) + '">開く</a><button type="button" class="btn small ghost" data-act="del">消す</button>';
    h += '</div>';
    h += '<div class="c-move"><button type="button" class="mini grip" data-act="grip" aria-label="つかんで動かす">⠿</button><button type="button" class="mini" data-act="up" aria-label="ひとつ前へ">↑</button>' +
      '<button type="button" class="mini" data-act="down" aria-label="ひとつ後ろへ">↓</button></div>';
    return h + '</article>';
  }
  function findEntry(id) { for (var i = 0; i < S.entries.length; i++) if (S.entries[i].id === id) return S.entries[i]; return null; }
  function fillCard(card) {
    var d = C.parse(card.getAttribute('data-date')), p = card.getAttribute('data-p') || 'day';
    if (!d) return;
    var r = C.countdown(d, TODAY, p), w = split(r), key = card.getAttribute('data-key') || '';
    card.setAttribute('data-dir', r.dir);
    card.setAttribute('data-long', w[1].length > 5 ? '1' : '0');
    var word = $('.word', card), num = $('.num', card), sub = $('.c-sub', card);
    if (word) word.textContent = w[0];
    if (num) num.textContent = w[1];
    if (sub) sub.textContent = r.sub ? '合計 ' + r.sub : '';
    var rl = $('.rel', card), t = r.total;
    if (rl) rl.textContent = card.getAttribute('data-est') === '1' ? '(予想)' : (p === 'day' && t != null) ? (t === 1 ? '(明日)' : t === 2 ? '(明後日)' : t === -1 ? '(昨日)' : t === -2 ? '(おととい)' : '') : '';
    var cnt = $('.c-count', card);
    if (cnt) cnt.setAttribute('aria-label', r.big + (r.sub ? '(合計 ' + r.sub + ')' : ''));
    var nx = $('.c-next', card);
    if (nx && key.indexOf('m:') === 0) {
      var e = findEntry(key.slice(2));
      var tip = e ? tipFor(e, TODAY) : '';
      nx.innerHTML = e ? nextLines(e, TODAY).map(function (l) { return '<p>' + H(l) + '</p>'; }).join('') + (tip ? '<p class="c-tip">' + H(tip) + '</p>' : '') : '';
    }
    var sv = $('[data-act="save"]', card);
    if (sv && key.indexOf('c:') === 0) {
      var on = S.saved.indexOf(key.slice(2)) >= 0;
      sv.setAttribute('aria-pressed', on ? 'true' : 'false');
      sv.textContent = on ? '★ 予定に入っています' : '☆ 予定に入れる';
    }
  }
  function hydrate(root) { $$('.card[data-date]', root || document).forEach(fillCard); }
  function render(el, items) {
    el.innerHTML = items.length ? items.map(cardHtml).join('') : '';
    hydrate(el);
  }

  /* ---------- catalogue ---------- */
  var catPromise;
  function loadCatalog() {
    if (!catPromise) {
      catPromise = fetch('/assets/catalog.json?v=' + encodeURIComponent(CONF.v)).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).catch(function () { return null; });
    }
    return catPromise;
  }
  function liveFrom(cat) {  // what the home page may show: not finished, as seen from today
    return cat.filter(function (c) {
      if (c.status === 'ended') return false;
      var last = C.parse(c.date_end || c.date);
      return last && C.cmp(last, TODAY) >= 0;
    }).sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : a.title < b.title ? -1 : 1; });
  }
  function diverse(pool, n) {  // the soonest ones of each genre, so the first screen is not one kind of date
    var kinds = {}; pool.forEach(function (c) { kinds[c.group] = 1; });
    var per = Math.ceil(n / Math.max(1, Object.keys(kinds).length)), pick = [], seen = {};
    pool.forEach(function (c) { seen[c.group] = seen[c.group] || 0; if (seen[c.group] < per && pick.length < n) { seen[c.group]++; pick.push(c); } });
    pool.forEach(function (c) { if (pick.length < n && pick.indexOf(c) < 0) pick.push(c); });
    return pick.sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; });
  }
  function weighted(pool, n) {  // shuffle: random, leaning to genres the visitor saved from and to dates that are near
    var ws = pool.map(function (c) {
      var away = Math.max(0, C.totalDays(TODAY, C.parse(c.date)));
      return { c: c, w: (1 + 2 * (S.genre[c.group] || 0)) / (1 + away / 120) };
    }), out = [];
    while (out.length < n && ws.length) {
      var sum = ws.reduce(function (a, x) { return a + x.w; }, 0), r = Math.random() * sum, i = 0;
      while (i < ws.length - 1 && r >= ws[i].w) { r -= ws[i].w; i++; }
      out.push(ws.splice(i, 1)[0].c);
    }
    return out;
  }
  function bump(group) { S.genre[group] = Math.min(20, (S.genre[group] || 0) + 1); }

  /* ---------- order / drag ---------- */
  function rank(it) {   // without a hand-made order: the day that comes next first (a yearly day by its next turn), then past days, the most recent first
    var a = C.parse(it.date);
    if (!a) return 5e5;
    var d = C.totalDays(TODAY, a);
    if (it.yearly) return C.totalDays(TODAY, nextYearly(a, TODAY));
    return d >= 0 ? d : 1e5 - d;
  }
  function ordered(items) {
    var idx = {};
    S.order.forEach(function (k, i) { idx[k] = i; });
    return items.map(function (it, i) { return { it: it, i: i }; }).sort(function (a, b) {
      var x = idx[a.it.key] == null ? 1e6 + rank(a.it) + a.i / 1000 : idx[a.it.key], y = idx[b.it.key] == null ? 1e6 + rank(b.it) + b.i / 1000 : idx[b.it.key];
      return x - y;
    }).map(function (o) { return o.it; });
  }
  var slidAt = 0, calm = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  function slide(grid, change, held) {   // the cards that change places glide there (a short ease), the one in the hand stays where the finger is
    if (calm) { change(); return; }
    var cards = $$('.card', grid), before = cards.map(function (c) { return c.getBoundingClientRect(); });
    slidAt = Date.now();
    change();
    cards.forEach(function (c, i) {
      if (c === held) return;
      var a = c.getBoundingClientRect(), dx = before[i].left - a.left, dy = before[i].top - a.top;
      if (!dx && !dy) return;
      c.style.transition = 'none'; c.style.transform = 'translate(' + dx + 'px,' + dy + 'px)';
      requestAnimationFrame(function () { requestAnimationFrame(function () { c.style.transition = 'transform .16s ease-out'; c.style.transform = ''; setTimeout(function () { c.style.transition = ''; }, 200); }); });
    });
  }
  function moveCard(card, dir) {
    var sib = dir < 0 ? card.previousElementSibling : card.nextElementSibling;
    if (!sib) return;
    slide(card.parentNode, function () { if (dir < 0) card.parentNode.insertBefore(card, sib); else card.parentNode.insertBefore(sib, card); }, null);
    card.focus && card.scrollIntoView({ block: 'nearest' });
    changed(card.parentNode);
  }
  function changed(grid) {
    if (grid.getAttribute('data-save-order') === '1') {
      S.order = $$('.card', grid).map(function (c) { return c.getAttribute('data-key'); });
      persist();
    }
  }
  /* A card can be grabbed anywhere (mouse: drag 6px; finger: press and hold), by its grip, or moved with the arrows (see "カードを動かす").
     A floating copy follows the pointer; the real card is dimmed and takes the place it is dropped on. */
  var drag = null, ghost = null, suppressClick = false, press = null, tPress = null;
  function interactive(t) { return t.closest && t.closest('a,button,input,select,textarea,label,summary'); }
  function dragGrid(card) { var g = card.parentNode; return g && g.getAttribute && g.getAttribute('data-save-order') === '1' && !g.classList.contains('pager') && !card.classList.contains('big') && !card.classList.contains('ghost') ? g : null; }
  function beginDrag(card, x, y) {
    var r = card.getBoundingClientRect();
    drag = { card: card, grid: card.parentNode, dx: x - r.left, dy: y - r.top };
    ghost = card.cloneNode(true);
    ghost.classList.add('ghost'); ghost.removeAttribute('data-key');
    ghost.style.width = r.width + 'px'; ghost.style.left = r.left + 'px'; ghost.style.top = r.top + 'px';
    document.body.appendChild(ghost);
    card.classList.add('dragging'); document.body.classList.add('drag-on');
    try { var sel = window.getSelection && window.getSelection(); if (sel) sel.removeAllRanges(); if (navigator.vibrate) navigator.vibrate(12); } catch (e) { /* only a nicety */ }
  }
  function dragMove(x, y) {
    if (!drag) return;
    ghost.style.left = (x - drag.dx) + 'px'; ghost.style.top = (y - drag.dy) + 'px';
    if (y < 80) window.scrollBy(0, -16); else if (y > window.innerHeight - 80) window.scrollBy(0, 16);
    var el = document.elementFromPoint(x, y), over = el && el.closest && el.closest('.card');
    if (!over || over === drag.card || over.parentNode !== drag.grid) return;
    if (Date.now() - slidAt < 130) return;   // the cards are still gliding: where they are drawn is not where they will be
    var r = over.getBoundingClientRect(), after = (x - r.left) / r.width + (y - r.top) / r.height > 1;
    slide(drag.grid, function () { drag.grid.insertBefore(drag.card, after ? over.nextSibling : over); }, drag.card);
  }
  function endDrag() {
    if (!drag) return;
    drag.card.classList.remove('dragging'); document.body.classList.remove('drag-on');
    if (ghost) { ghost.remove(); ghost = null; }
    var g = drag.grid;
    drag = null; changed(g); stat('act:drag');
  }
  function quietClick() { suppressClick = true; setTimeout(function () { suppressClick = false; }, 0); }
  document.addEventListener('pointerdown', function (ev) {
    if (ev.pointerType === 'touch' || ev.button !== 0 || !ev.target.closest) return;
    var card = ev.target.closest('.card'), grip = ev.target.closest('[data-act="grip"]');
    if (!card || !dragGrid(card) || (!grip && interactive(ev.target))) return;
    press = { card: card, x: ev.clientX, y: ev.clientY, id: ev.pointerId, started: false };
    if (grip) { ev.preventDefault(); press.started = true; beginDrag(card, ev.clientX, ev.clientY); }
  });
  document.addEventListener('pointermove', function (ev) {
    if (!press || ev.pointerId !== press.id) return;
    if (!press.started) {
      if (Math.abs(ev.clientX - press.x) + Math.abs(ev.clientY - press.y) < 6) return;
      press.started = true; beginDrag(press.card, press.x, press.y);
    }
    dragMove(ev.clientX, ev.clientY);
  });
  function pressEnd(ev) {
    if (!press || ev.pointerId !== press.id) return;
    if (press.started) { quietClick(); endDrag(); }
    press = null;
  }
  document.addEventListener('pointerup', pressEnd);
  document.addEventListener('pointercancel', pressEnd);
  document.addEventListener('click', function (ev) { if (suppressClick) { ev.stopPropagation(); ev.preventDefault(); } }, true);
  document.addEventListener('dragstart', function (ev) { if (ev.target.closest && ev.target.closest('.cards .card')) ev.preventDefault(); });
  document.addEventListener('contextmenu', function (ev) { if (drag || tPress) ev.preventDefault(); });
  function cancelTouch() { if (tPress) { clearTimeout(tPress.timer); tPress = null; } }
  document.addEventListener('touchstart', function (ev) {
    cancelTouch();
    if (ev.touches.length !== 1 || !ev.target.closest) return;
    var card = ev.target.closest('.card'), grip = ev.target.closest('[data-act="grip"]');
    if (!card || !dragGrid(card) || (!grip && interactive(ev.target))) return;
    var tc = ev.touches[0];
    tPress = { card: card, x: tc.clientX, y: tc.clientY, on: false };
    tPress.timer = setTimeout(function () { if (tPress) { tPress.on = true; beginDrag(card, tPress.x, tPress.y); } }, grip ? 0 : 380);
  }, { passive: true });
  document.addEventListener('touchmove', function (ev) {
    if (!tPress) return;
    var tc = ev.touches[0];
    if (!tPress.on) { if (Math.abs(tc.clientX - tPress.x) + Math.abs(tc.clientY - tPress.y) > 10) cancelTouch(); return; }
    ev.preventDefault();
    dragMove(tc.clientX, tc.clientY);
  }, { passive: false });
  function touchEnd() { if (tPress && tPress.on) { quietClick(); endDrag(); } cancelTouch(); }
  document.addEventListener('touchend', touchEnd);
  document.addEventListener('touchcancel', touchEnd);
  function wireReorderToggle(btn, grid) {
    if (!btn) return;
    btn.addEventListener('click', function () {
      var on = !grid.classList.contains('reorder');
      grid.classList.toggle('reorder', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      btn.textContent = on ? '並べ替えを終える' : '並べ替え';
      if (on) { toast('↑↓で並べ替えできます。ドラッグ(スマホは長押し)でも動かせます。'); stat('act:reorder'); }
    });
  }

  /* ---------- actions on cards ---------- */
  function icsFor(card) {
    var key = card.getAttribute('data-key') || '', d = C.parse(card.getAttribute('data-date')), title = card.getAttribute('data-title');
    if (!d || card.getAttribute('data-p') !== 'day') { toast('年や月までの日付は、ファイルにできません。'); return; }
    var ev;
    if (key.indexOf('m:') === 0) {
      var e = findEntry(key.slice(2));
      if (!e) return;
      ev = { uid: 'm-' + e.id, title: e.title, date: d, time: e.time || '', yearly: !!e.yearly, every100: !!e.every100, alarm: e.alarm || S.prefs.alarm, reminds: (S.notes[key] && S.notes[key].remind) || [] };
    } else {
      ev = { uid: 'e-' + key.slice(2), title: title, date: d, alarm: S.prefs.alarm, reminds: (S.notes[key] && S.notes[key].remind) || [], note: '詳しい日付と出典: ' + location.origin + '/e/' + key.slice(2) + '/' };
      if (S.saved.indexOf(key.slice(2)) < 0) { S.saved.push(key.slice(2)); persist(); fillCard(card); }
      var g = card.getAttribute('data-g');
      if (g && CONF.groups[g - 1]) { bump(CONF.groups[g - 1]); persist(); }
    }
    stat('act:ics');
    ICS.download('atomou-' + key.slice(2) + '.ics', ICS.build([ev], title));
    toast('作成したファイルを開くと、カレンダーに追加できます。');
  }
  function toggleSave(card) {
    var id = (card.getAttribute('data-key') || '').slice(2), i = S.saved.indexOf(id), g = card.getAttribute('data-g');
    if (i >= 0) { S.saved.splice(i, 1); toast('予定から外しました。'); }
    else { S.saved.push(id); stat('act:save'); if (/^[0-9a-f]{10}$/.test(id)) stat('act:pop:' + id); if (g && CONF.groups[g - 1]) bump(CONF.groups[g - 1]); toast('予定に入れました。カレンダーに表示されます。'); }
    persist();
    $$('.card[data-key="c:' + id + '"]').forEach(fillCard);
    if (page === 'my') renderMy();
  }
  function saveAll(btn) {   // "この日を含むN件を、まとめて予定に入れる": every day of the same kind (the exam's entry, test day, results...) in one tap
    var ids = (btn.getAttribute('data-saveall') || '').split(',').filter(function (x) { return /^[0-9a-f]{10}$/.test(x); }), added = 0;
    ids.forEach(function (id) { if (S.saved.indexOf(id) < 0) { S.saved.push(id); added++; stat('act:pop:' + id); } });
    if (!added) { toast('すべて予定に入っています。'); return; }
    stat('act:save');
    persist();
    ids.forEach(function (id) { $$('.card[data-key="c:' + id + '"]').forEach(fillCard); });
    toast(added + '件を予定に入れました。カレンダーに表示されます。');
  }
  function removeEntry(card) {
    var id = (card.getAttribute('data-key') || '').slice(2), e = findEntry(id);
    if (!e) return;
    if (page === 'plan' && !window.confirm('「' + e.title + '」を消しますか。')) return;   // the plan page leaves for the calendar, so there is no room for "undo": ask first
    var at = S.entries.indexOf(e), notes = S.notes['m:' + id], ord = S.order.indexOf('m:' + id);
    S.entries = S.entries.filter(function (x) { return x.id !== id; });
    S.deleted.push(id); S.deleted = S.deleted.slice(-300);
    S.order = S.order.filter(function (k) { return k !== 'm:' + id; });
    delete S.notes['m:' + id];
    persist();
    if (page === 'my') renderMy(); else if (page === 'home') renderMine(); else if (page === 'plan') { toast('消しました。'); location.href = '/calendar/'; return; }
    toastAct('「' + e.title + '」を消しました。', '元に戻す', function () {
      S.entries.splice(Math.min(at, S.entries.length), 0, e);
      S.deleted = S.deleted.filter(function (x) { return x !== id; });
      if (notes) S.notes['m:' + id] = notes;
      if (ord >= 0) S.order.splice(Math.min(ord, S.order.length), 0, 'm:' + id);
      persist(); stat('act:undo_delete');
      if (page === 'my') renderMy(); else if (page === 'home') renderMine();
    });
  }
  document.addEventListener('click', function (ev) {
    var ib = ev.target.closest ? ev.target.closest('[data-ics-for]') : null;
    if (ib) {  // "make a file for another calendar app": a small secondary button on the plan and event pages
      var target = document.querySelector('.card[data-key="' + String(ib.getAttribute('data-ics-for')).replace(/[^cm:A-Za-z0-9_-]/g, '') + '"]');
      if (target) icsFor(target);
      return;
    }
    var all = ev.target.closest ? ev.target.closest('[data-saveall]') : null;
    if (all) { saveAll(all); return; }
    var b = ev.target.closest ? ev.target.closest('[data-act]') : null;
    if (!b) return;
    var card = b.closest('.card'), act = b.getAttribute('data-act');
    if (!card) return;
    if (act === 'save') toggleSave(card);
    else if (act === 'ics') icsFor(card);
    else if (act === 'del') removeEntry(card);
    else if (act === 'up') moveCard(card, -1);
    else if (act === 'down') moveCard(card, 1);
  });

  /* ---------- skins ---------- */
  var SKIN_ATTRS = ['head', 'btn', 'density', 'num', 'deco', 'nav', 'cat', 'list'];
  function ensureSkinCss() {
    (CONF.css || []).forEach(function (u) {
      var name = u.split('?')[0];
      if (!document.querySelector('link[href^="' + name + '"]')) { var l = document.createElement('link'); l.rel = 'stylesheet'; l.href = u; document.head.appendChild(l); }
    });
  }
  function deviceIsDark() { try { return !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches); } catch (e) { return false; } }
  try { var mq = window.matchMedia('(prefers-color-scheme: dark)'); if (mq.addEventListener) mq.addEventListener('change', function () { if (S.prefs.skinAuto) applyPrefs(); }); } catch (e) { /* ignore */ }
  function applyPrefs() {
    var r = document.documentElement, id = (P.skin && CONF.skins[P.skin]) ? P.skin : (S.prefs.skinAuto && deviceIsDark() && CONF.skins[S.prefs.skinNight]) ? S.prefs.skinNight : S.prefs.skin, sk = CONF.skins[id];  // ?skin= is for screenshots and tests
    if (!sk || id === 'basic') { r.removeAttribute('data-skin'); r.setAttribute('data-card', 'plain'); SKIN_ATTRS.forEach(function (k) { r.removeAttribute('data-' + k); }); }
    else {
      ensureSkinCss();
      r.setAttribute('data-skin', id); r.setAttribute('data-card', sk.card);
      SKIN_ATTRS.forEach(function (k) { var v = sk.attrs && sk.attrs[k]; if (v) r.setAttribute('data-' + k, v); else r.removeAttribute('data-' + k); });
    }
    if (S.prefs.big) r.setAttribute('data-big', '1'); else r.removeAttribute('data-big');
  }
  function seasonSkin() {  // the seasonal skin whose dates include today ("MM-DD" windows; a window may cross the new year)
    var md = ('0' + TODAY[1]).slice(-2) + '-' + ('0' + TODAY[2]).slice(-2), found = null;
    Object.keys(CONF.skins).forEach(function (id) {
      var se = CONF.skins[id].season;
      if (!se || found) return;
      if (se.from <= se.to ? (md >= se.from && md <= se.to) : (md >= se.from || md <= se.to)) found = id;
    });
    return found;
  }
  function renderSeason() {
    var box = $('#season'), id = seasonSkin();
    if (box && !P.today && deviceIsDark() && !S.prefs.skinAuto && !S.prefs.nightAsked && !CONF.skins[S.prefs.skin].dark) {   // the first time on a device set to dark: offer, never switch by itself
      box.hidden = false;
      box.innerHTML = '<span>端末が暗い配色に設定されています。サイトも暗い配色にしますか。</span><button type="button" class="btn small" data-night="1">暗い配色にする</button><button type="button" class="btn small ghost" data-night="0">このまま</button>';
      return;
    }
    if (!box || !id || S.prefs.skin === id || (S.prefs.seasonOff === id)) return;
    var sk = CONF.skins[id];
    box.hidden = false;
    box.innerHTML = '<span>季節のきせかえ「<b>' + H(sk.season.label || sk.name) + '</b>」</span><button type="button" class="btn small" data-season="' + H(id) + '">使う</button>' +
      '<button type="button" class="mini" data-season-off="' + H(id) + '" aria-label="閉じる">×</button>';
  }
  document.addEventListener('click', function (ev) {
    var nt = ev.target.closest ? ev.target.closest('[data-night]') : null;
    if (nt) {
      S.prefs.nightAsked = true; S.prefs.skinAuto = nt.getAttribute('data-night') === '1'; persist(); applyPrefs();
      var nb = $('#season'); if (nb) nb.hidden = true;
      stat('act:night_' + (S.prefs.skinAuto ? 'on' : 'off'));
      toast(S.prefs.skinAuto ? '端末が暗い配色のときは、サイトも暗い配色にします。きせかえで変更できます。' : '今のままにします。きせかえでいつでも変更できます。');
      return;
    }
    var on = ev.target.closest ? ev.target.closest('[data-season]') : null, off = ev.target.closest ? ev.target.closest('[data-season-off]') : null;
    if (on) { S.prefs.skin = on.getAttribute('data-season'); persist(); applyPrefs(); stat('act:skin:' + S.prefs.skin); var bx = $('#season'); if (bx) bx.hidden = true; toast('きせかえを変更しました。いつでも元に戻せます。'); }
    else if (off) { S.prefs.seasonOff = off.getAttribute('data-season-off'); persist(); var b2 = $('#season'); if (b2) b2.hidden = true; }
  });
  function pageSkins() {
    var box = $('#skin-list');
    function shown() { return S.prefs.skinAuto && deviceIsDark() ? S.prefs.skinNight : S.prefs.skin; }
    function mark() { $$('.skin', box).forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-skin') === shown() ? 'true' : 'false'); }); }
    box.addEventListener('click', function (ev) {
      var b = ev.target.closest('.skin');
      if (!b) return;
      var picked = b.getAttribute('data-skin');
      if (S.prefs.skinAuto && CONF.skins[picked] && CONF.skins[picked].dark) S.prefs.skinNight = picked;   // with "follow the device" on, a dark pick is the night skin
      else S.prefs.skin = picked;
      persist(); applyPrefs(); mark(); stat('act:skin:' + picked);
      toast(S.prefs.skinAuto && deviceIsDark() && !(CONF.skins[picked] && CONF.skins[picked].dark) ? '昼の配色を「' + b.getAttribute('data-name') + '」にしました。暗い設定の間は、暗い配色のままです。' : '「' + b.getAttribute('data-name') + '」にしました。');
    });
    var auto = $('#skin-auto');
    if (auto) { auto.checked = !!S.prefs.skinAuto; auto.addEventListener('change', function () { S.prefs.skinAuto = auto.checked; S.prefs.nightAsked = true; persist(); applyPrefs(); stat('act:night_' + (auto.checked ? 'on' : 'off')); toast(auto.checked ? '端末が暗い配色のときは、サイトも暗い配色にします。' : '端末の配色には合わせません。'); }); }
    mark();
  }

  /* ---------- home ---------- */
  function renderDaily() {
    var el = $('#daily');
    if (!el) return;
    var n = C.dayOfYear(TODAY), fy = C.fiscalYear(TODAY);
    el.innerHTML = '<span class="d-today">' + fmtDate(C.iso(TODAY), 'day') + '</span><a href="/today/#year">年末まであと' + n[1] + '日</a>' +
      '<a href="/today/#newyear">' + (TODAY[0] + 1) + '年まであと' + (n[1] + 1) + '日</a><a href="/today/#fy">年度末まであと' + fy[2] + '日</a>';
  }
  function myItems(cat) {
    var items = S.entries.map(ownItem);
    if (cat) {
      var by = {};
      cat.forEach(function (c) { by[c.id] = c; });
      S.saved.forEach(function (id) { if (by[id]) items.push(catItem(by[id])); });
    }
    return ordered(items);
  }
  function needCatalog() { return S.saved.length > 0 ? loadCatalog() : Promise.resolve([]); }
  function renderMine() {
    var box = $('#mine'), grid = $('#mine-grid');
    if (!box) return;
    needCatalog().then(function (cat) {
      var items = myItems(cat).slice(0, 3);
      box.hidden = !items.length;
      if (items.length) render(grid, items);
    });
  }

  /* ---------- the fields the visitor likes: chosen on /interests/, listed on the home page ---------- */
  function interestHits(cat, w) {   // the upcoming days that belong to a field or a word ("将棋", "剣道"); a quiet day is never put on such a list
    var nw = norm(w), out = [];
    cat.forEach(function (c) {
      if (c.status === 'ended' || c.quiet) return;
      var last = C.parse(c.date_end || c.date);
      if (!last || C.cmp(last, TODAY) < 0) return;
      if (c.subject === w || (c.tags || []).indexOf(w) >= 0 || hayOf(c).indexOf(nw) >= 0) out.push(c);
    });
    return out.sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : a.title < b.title ? -1 : 1; });
  }
  function regionHits(cat, pref) {   // upcoming days whose place or region is in the prefecture ("東京都(東京ビッグサイト)" or region "東京都")
    var out = [];
    cat.forEach(function (c) {
      if (c.status === 'ended' || c.quiet) return;
      var last = C.parse(c.date_end || c.date);
      if (!last || C.cmp(last, TODAY) < 0) return;
      if (String(c.place || '').indexOf(pref) === 0 || c.region === pref || String(c.place || '').indexOf(pref) >= 0) out.push(c);
    });
    return out.sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : a.title < b.title ? -1 : 1; });
  }
  function renderRegion() {
    var box = $('#region');
    if (!box) return;
    var pref = S.prefs.region, none = $('#reg-none'), wrap = $('#reg-wrap'), grid = $('#reg-grid'), more = $('#reg-more');
    box.hidden = false;
    none.hidden = !!pref; wrap.hidden = !pref;
    if (!pref) return;
    $('#reg-title').textContent = pref + 'の日';
    loadCatalog().then(function (cat) {
      var hits = regionHits(cat || [], pref);
      render(grid, hits.slice(0, 6).map(catItem));
      more.innerHTML = hits.length ? (hits.length > 6 ? 'ほかに' + (hits.length - 6) + '件あります。<a href="/search/?q=' + encodeURIComponent(pref) + '">' + H(pref) + 'の日をすべて見る</a>' : '') : pref + 'の日は、まだありません。全国の日は、下に並んでいます。';
    });
  }
  function hasInterest(w) { return S.interests.indexOf(w) >= 0; }
  function setInterest(w, on) {
    var i = S.interests.indexOf(w);
    if (on && i < 0 && S.interests.length < 30) { S.interests.push(w); stat('act:interest_add'); }
    else if (!on && i >= 0) S.interests.splice(i, 1);
    persist();
  }
  function requestLink(w) { return '/contact/?kind=request&q=' + encodeURIComponent(w); }
  function renderInterests() {
    var box = $('#interests');
    if (!box) return;
    var prompt = $('#int-prompt'), wrap = $('#int-wrap'), grid = $('#int-grid'), miss = $('#int-miss'), list = S.interests;
    box.hidden = false;
    prompt.hidden = !!list.length; wrap.hidden = !list.length;
    if (!list.length) return;
    loadCatalog().then(function (cat) {
      var seen = {}, items = [], missing = [];
      list.forEach(function (w) {
        var hits = interestHits(cat || [], w);
        if (!hits.length) missing.push(w);
        hits.forEach(function (c) { if (!seen[c.id]) { seen[c.id] = 1; items.push(c); } });
      });
      items.sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; });
      render(grid, items.slice(0, 6).map(catItem));
      miss.innerHTML = (items.length > 6 ? '選んだ分野の日は、ほかに' + (items.length - 6) + '件あります。<a href="/search/?q=' + encodeURIComponent(list[0]) + '">探す</a> ' : '') +
        missing.map(function (w) { return '「' + H(w) + '」は、まだ日付がありません。<a href="' + requestLink(w) + '">載せてほしい分野として送る</a>'; }).join('<br>');
    });
  }
  function pageInterests() {
    var regSel = $('#reg-select');
    if (regSel) {
      regSel.value = S.prefs.region || '';
      regSel.addEventListener('change', function () { S.prefs.region = CONF.regions && CONF.regions.indexOf(regSel.value) >= 0 ? regSel.value : ''; persist(); stat('act:region_set'); $('#reg-note').textContent = S.prefs.region ? S.prefs.region + 'を選びました。ホームに、' + S.prefs.region + 'の日が並びます。' : '地域の選択を外しました。'; });
    }
    var chips = $$('[data-int]'), chosen = $('#int-chosen'), note = $('#int-note'), q = $('#int-q'), form = $('#int-form'), go = $('#int-go'), cat = [];
    function sync() {
      chips.forEach(function (b) { b.setAttribute('aria-pressed', hasInterest(b.getAttribute('data-int')) ? 'true' : 'false'); });
      chosen.innerHTML = S.interests.length ? '<p class="hint">選んだ分野(押すと外せます)</p><div class="chiprow">' + S.interests.map(function (w) { return '<button type="button" class="chip" aria-pressed="true" data-int-drop="' + H(w) + '">' + H(w) + ' ×</button>'; }).join('') + '</div>'
        : '<p class="hint">まだ選んでいません。下の分野を押すか、言葉を入れて追加します。</p>';
      go.hidden = !S.interests.length;
    }
    function say(w) {
      var n = interestHits(cat, w).length;
      note.innerHTML = n ? '「' + H(w) + '」を追加しました。今は' + n + '件の日があります。' : '「' + H(w) + '」を追加しました。まだ日付がありません。<a href="' + requestLink(w) + '">載せてほしい分野として送る</a>';
    }
    loadCatalog().then(function (c) { cat = c || []; });
    document.addEventListener('click', function (ev) {
      var b = ev.target.closest ? ev.target.closest('[data-int],[data-int-drop]') : null;
      if (!b) return;
      if (b.hasAttribute('data-int')) { var w = b.getAttribute('data-int'); setInterest(w, !hasInterest(w)); if (hasInterest(w)) { say(w); if (/^[0-9]{1,4}$/.test(b.getAttribute('data-id') || '')) stat('act:int_' + b.getAttribute('data-id')); } else note.textContent = ''; }
      else setInterest(b.getAttribute('data-int-drop'), false);
      sync();
    });
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var w = q.value.replace(/[\u0000-\u001f<>"'&\\]/g, '').trim().slice(0, 24);
      if (!w) return;
      var hit = chips.filter(function (b) { return norm(b.getAttribute('data-int')) === norm(w); })[0];
      if (hit) w = hit.getAttribute('data-int');
      if (!hasInterest(w) && S.interests.length >= 30) { note.textContent = '選べるのは30個までです。'; return; }
      setInterest(w, true); say(w); q.value = ''; filter(); sync();
    });
    function filter() {   // typing narrows the fields shown
      var t = norm(q.value);
      chips.forEach(function (b) { b.hidden = !!t && norm(b.getAttribute('data-hay') || b.getAttribute('data-int')).indexOf(t) < 0; });
      $$('[data-int-sec]').forEach(function (s) { s.hidden = !!t && !$$('[data-int]', s).some(function (b) { return !b.hidden; }); });
    }
    q.addEventListener('input', filter);
    sync();
  }
  function toggleLabel(b) {
    var w = b.getAttribute('data-int-toggle');
    b.textContent = hasInterest(w) ? '好きな分野から外す' : '「' + w + '」を好きな分野に入れる';
    b.setAttribute('aria-pressed', hasInterest(w) ? 'true' : 'false');
  }
  $$('[data-int-toggle]').forEach(toggleLabel);
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest ? ev.target.closest('[data-int-toggle]') : null;
    if (!b) return;
    var w = b.getAttribute('data-int-toggle');
    setInterest(w, !hasInterest(w));
    toggleLabel(b);
    toast(hasInterest(w) ? 'ホームに、この分野の日が並びます。' : '外しました。');
  });

  /* ---------- home blocks: reorder / show / hide (this device only) ---------- */
  var BLOCKS = BLOCK_IDS;
  function blockPrefs() {
    var b = S.prefs.blocks || {};
    return { order: Array.isArray(b.order) ? b.order : [], hidden: Array.isArray(b.hidden) ? b.hidden : [] };
  }
  function applyBlocks(editing) {
    var host = $('#blocks');
    if (!host) return;
    var bp = blockPrefs(), els = {};
    $$('[data-block]', host).forEach(function (el) { els[el.getAttribute('data-block')] = el; });
    var order = bp.order.filter(function (k) { return els[k]; });
    BLOCKS.forEach(function (k) { if (els[k] && order.indexOf(k) < 0) order.push(k); });
    order.forEach(function (k) { host.appendChild(els[k]); });
    order.forEach(function (k) { els[k].classList.toggle('block-off', bp.hidden.indexOf(k) >= 0); });
    host.classList.toggle('editing', !!editing);
    $$('.block-bar', host).forEach(function (b) { b.remove(); });
    if (!editing) return;
    order.forEach(function (k, i) {
      var off = bp.hidden.indexOf(k) >= 0, bar = document.createElement('div');
      bar.className = 'block-bar'; bar.setAttribute('data-k', k);
      bar.innerHTML = '<b>' + H(els[k].getAttribute('data-title') || k) + '</b><span class="bar-btns"><button type="button" class="mini" data-b="up" aria-label="ひとつ上へ"' + (i === 0 ? ' disabled' : '') + '>↑</button>' +
        '<button type="button" class="mini" data-b="down" aria-label="ひとつ下へ"' + (i === order.length - 1 ? ' disabled' : '') + '>↓</button>' +
        '<button type="button" class="mini" data-b="vis" aria-pressed="' + (off ? 'false' : 'true') + '">' + (off ? '表示' : '非表示') + '</button></span>';
      els[k].insertBefore(bar, els[k].firstChild);
    });
  }
  function wireBlocks() {
    var host = $('#blocks'), btn = $('#edit-home'), reset = $('#reset-home');
    if (!host) return;
    var editing = P.edit === '1';
    function show() {
      applyBlocks(editing);
      if (reset) reset.hidden = !editing;
      if (btn) { btn.setAttribute('aria-pressed', editing ? 'true' : 'false'); btn.textContent = editing ? '編集を終える' : 'ホームを編集'; }
    }
    host.addEventListener('click', function (ev) {
      var b = ev.target.closest ? ev.target.closest('[data-b]') : null;
      if (!b) return;
      var k = b.closest('.block-bar').getAttribute('data-k'), bp = blockPrefs(), order = $$('[data-block]', host).map(function (el) { return el.getAttribute('data-block'); });
      var i = order.indexOf(k), act = b.getAttribute('data-b');
      if (act === 'up' && i > 0) { order.splice(i, 1); order.splice(i - 1, 0, k); }
      else if (act === 'down' && i < order.length - 1) { order.splice(i, 1); order.splice(i + 1, 0, k); }
      else if (act === 'vis') { var h = bp.hidden.indexOf(k); if (h >= 0) bp.hidden.splice(h, 1); else bp.hidden.push(k); }
      S.prefs.blocks = { order: order, hidden: bp.hidden }; persist(); show();
      stat(act === 'vis' ? (bp.hidden.indexOf(k) >= 0 ? 'act:block_hide:' + k : 'act:block_show:' + k) : 'act:block_move');
    });
    if (reset) reset.addEventListener('click', function () { S.prefs.blocks = { order: [], hidden: [] }; persist(); show(); toast('元の並びに戻しました。'); });
    if (btn) btn.addEventListener('click', function () { editing = !editing; show(); if (editing) toast('↑↓で並べ替えできます。非表示にもできます。'); });
    show();
  }

  function pageHome() {
    renderDaily(); renderMine(); renderInterests(); renderRegion(); wireBlocks();
    var cb = blockPrefs();
    if (cb.order.length || cb.hidden.length) { stat('home_order:' + (cb.order.length ? cb.order.join(',') : 'default')); cb.hidden.forEach(function (k) { stat('home_hidden:' + k); }); }
    var grid = $('#grid'), more = $('#more'), pool = [], shown = 6, random = null, ready = null, mine = (S.prefs.genres || []).slice();
    if (P.today && P.pg) mine = P.pg.split(',').map(function (s) { return CONF.groups[CONF.slugs.indexOf(s)]; }).filter(Boolean);   // tests: ?today=...&pg=sports,exams stands in for the chosen genres
    function poolFor() { var p = mine.length ? pool.filter(function (c) { return mine.indexOf(c.group) >= 0; }) : pool; return p.length >= 6 || !mine.length ? p : pool; }
    function fetchPool() {  // the catalogue is downloaded only when someone asks for more, shuffles or searches
      if (!ready) ready = loadCatalog().then(function (cat) { pool = liveFrom(cat || []); return pool; });
      return ready;
    }
    function draw() {
      var from = poolFor(), list = random ? random.slice(0, shown) : diverse(from, shown);
      render(grid, random ? list.map(catItem) : ordered(list.map(catItem)));
      if (more) more.hidden = shown >= Math.min(from.length, 36);
    }
    if (mine.length) {   // chosen genres: the "soon" block is theirs, drawn at once (the page's own six cards are the general ones)
      var sh2 = $('#soon-h'); if (sh2) sh2.textContent = 'あなたのジャンルのもうすぐの日';
      fetchPool().then(function () { if (pool.length) draw(); });
    }
    // the first screen is the cards already in the page (counted again here); a saved order is applied to them without any download
    var idx = {};
    S.order.forEach(function (k, i) { idx[k] = i; });
    $$('.card', grid).sort(function (a, b) {
      var x = idx[a.getAttribute('data-key')], y = idx[b.getAttribute('data-key')];
      return (x == null ? 1e6 : x) - (y == null ? 1e6 : y);
    }).forEach(function (c) { grid.appendChild(c); });
    var sh = $('#shuffle');
    if (sh) sh.addEventListener('click', function () { fetchPool().then(function () { if (!pool.length) return; random = weighted(poolFor(), 36); draw(); stat('act:shuffle'); }); });
    if (more) more.addEventListener('click', function () { fetchPool().then(function () { shown = Math.min(shown + 6, 36); draw(); stat('act:more'); }); });
  }

  /* ---------- 地域: 大 = 地域, 中 = 地方, 小 = 都道府県 ---------- */
  function pageRegionHub() {
    var areas = $('#reg-areas'), prefs = $('#reg-prefs'), found = $('#reg-found'), out = $('#reg-cards'), cat = [], st = { a: '', r: P.r || '' }, AREAS = CONF.areas || [];
    function areaOf(pref) { for (var i = 0; i < AREAS.length; i++) if (AREAS[i][1].indexOf(pref) >= 0) return AREAS[i][0]; return ''; }
    if (st.r && !areaOf(st.r)) st.r = '';
    st.a = P.a || areaOf(st.r) || '';
    function count(pref) { return regionHits(cat, pref).length; }
    function run() {
      var hs = [];
      if (st.r) hs = regionHits(cat, st.r);
      areas.innerHTML = AREAS.map(function (a) {
        var n = a[1].reduce(function (s, p) { return s + count(p); }, 0);
        return '<button type="button" class="chip" data-reg-area="' + H(a[0]) + '" aria-pressed="' + (st.a === a[0]) + '">' + H(a[0]) + '<small> ' + n + '</small></button>';
      }).join('');
      var cur = AREAS.filter(function (a) { return a[0] === st.a; })[0];
      prefs.hidden = !cur;
      prefs.innerHTML = cur ? cur[1].map(function (p) { return '<button type="button" class="chip" data-reg-pref="' + H(p) + '" aria-pressed="' + (st.r === p) + '">' + H(p) + '<small> ' + count(p) + '</small></button>'; }).join('') : '';
      render(out, hs.slice(0, 60).map(catItem));
      found.textContent = st.r ? (hs.length ? st.r + 'の日 ' + hs.length + '件' + (hs.length > 60 ? '(近い順に60件)' : '') : st.r + 'の日は、まだありません。全国の日は、ホームやジャンルのページにあります。') : '地方を選んでください。';
      try { history.replaceState(null, '', '/region/' + (st.r ? '?r=' + encodeURIComponent(st.r) : st.a ? '?a=' + encodeURIComponent(st.a) : '')); } catch (e) { /* ignore */ }
    }
    areas.addEventListener('click', function (ev) { var b = ev.target.closest ? ev.target.closest('[data-reg-area]') : null; if (b) { st.a = b.getAttribute('data-reg-area'); st.r = ''; run(); } });
    prefs.addEventListener('click', function (ev) { var b = ev.target.closest ? ev.target.closest('[data-reg-pref]') : null; if (b) { st.r = b.getAttribute('data-reg-pref'); stat('act:region_hub'); run(); } });
    loadCatalog().then(function (c) { cat = c || []; if (!c) found.textContent = '読み込めませんでした。しばらくして開き直してください。'; run(); });
  }

  /* ---------- search ---------- */
  function norm(s) {
    return String(s || '').normalize('NFKC').toLowerCase().replace(/[ァ-ヶ]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 0x60); }).replace(/\s+/g, ' ').trim();
  }
  function hayOf(c) { return norm([c.title, c.subject, c.what, c.category, c.group, c.place || c.region, c.kind].concat(c.tags || []).join(' ')); }
  function matchCat(cat, q, limit) {
    var terms = norm(q).split(' ').filter(Boolean);
    if (!terms.length) return [];
    var hits = cat.filter(function (c) {
      if (c.status === 'ended' && !c.keep) return false;   // a kept day (a big event, a history day) is found after it has passed too
      var hay = hayOf(c);
      return terms.every(function (t) { return hay.indexOf(t) >= 0; });
    }).sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; });
    return limit ? hits.slice(0, limit) : hits;
  }
  function pageSearch() {
    var q = $('#q'), out = $('#results'), info = $('#found'), st = { g: P.g || '', m: P.m || '', s: P.s || '', t: P.t === '1' }, cat = [], statT, topSubs = {};
    q.value = P.q || '';
    function sync() {
      var u = '/search/?' + [q.value ? 'q=' + encodeURIComponent(q.value) : '', st.g ? 'g=' + st.g : '', st.g && st.m ? 'm=' + encodeURIComponent(st.m) : '', st.g && st.m && st.s ? 's=' + encodeURIComponent(st.s) : '', st.t ? 't=1' : ''].filter(Boolean).join('&');
      try { history.replaceState(null, '', u.replace(/\?$/, '')); } catch (e) { /* ignore */ }
    }
    function run() {
      var terms = norm(q.value).split(' ').filter(Boolean);
      $$('[data-g-chip]').forEach(function (b) { b.setAttribute('aria-pressed', (b.getAttribute('data-g-chip') === st.g) ? 'true' : 'false'); });
      var tb = $('#f-son'); if (tb) tb.setAttribute('aria-pressed', st.t ? 'true' : 'false');
      var gi = CONF.slugs.indexOf(st.g);
      levels(gi);   // first: it drops a middle or small choice the catalogue does not have (a broken address), then the list is made
      var hits = cat.filter(function (c) {
        if (c.status === 'ended' && !c.keep) return false;
        if (gi >= 0 && c.group !== CONF.groups[gi]) return false;
        if (gi >= 0 && st.m && c.mid !== st.m) return false;
        if (gi >= 0 && st.m && st.s && (st.s === '*' ? topSubs[c.subject] : c.subject !== st.s)) return false;
        if (st.t && !c.son_toku) return false;
        var hay = hayOf(c);
        return terms.every(function (t) { return hay.indexOf(t) >= 0; });
      }).sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; });
      clearTimeout(statT); statT = setTimeout(function () { if (terms.length) stat(hits.length ? 'act:search_hit' : 'act:search_miss'); }, 1500);
      var shown = hits.slice(0, 60);
      render(out, shown.map(catItem));
      info.textContent = hits.length ? hits.length + '件' + (hits.length > 60 ? '(近い順に60件)' : '') : '';
      var none = $('#none');
      none.hidden = hits.length > 0;
      var add = $('#none-add');
      if (add) add.href = '/add/' + (q.value ? '?title=' + encodeURIComponent(q.value) : '');
      var ask = $('#none-ask');
      if (ask) ask.href = '/contact/?kind=request' + (q.value ? '&q=' + encodeURIComponent(q.value.slice(0, 60)) : '');
      sync();
    }
    function levels(gi) {   // 中 chips of the chosen genre (counts of the days still to come), and 小 chips of the chosen 中
      var mb = $('#mid-chips'), sb = $('#sub-chips'), g = gi >= 0 ? CONF.groups[gi] : '', nm = {}, ns = {}, ml, sl;
      if (!mb || !sb || !cat.length) return;   // before the catalogue is here nothing can be judged
      cat.forEach(function (c) {
        if (c.status === 'ended' || c.group !== g || !c.mid) return;
        nm[c.mid] = (nm[c.mid] || 0) + 1;
        if (st.m === c.mid && c.subject) ns[c.subject] = (ns[c.subject] || 0) + 1;
      });
      ml = Object.keys(nm).sort(function (a, b) { return (a === 'その他') - (b === 'その他') || nm[b] - nm[a] || (a < b ? -1 : 1); });   // "その他" is the last 中
      if (st.m && !nm[st.m]) { st.m = ''; st.s = ''; }
      var allS = Object.keys(ns).sort(function (a, b) { return ns[b] - ns[a] || (a < b ? -1 : 1); }), many = allS.length > SUBCAP, restN = 0;
      sl = many ? allS.slice(0, SUBCAP - 1) : allS; topSubs = {}; sl.forEach(function (s) { topSubs[s] = 1; });
      if (many) allS.slice(SUBCAP - 1).forEach(function (s) { restN += ns[s]; });   // the small ones that did not fit are one "その他" (s=*)
      if (st.s && st.s !== '*' && !ns[st.s]) st.s = '';
      if (st.s === '*' && !many) st.s = '';
      mb.hidden = !g || ml.length < 2;
      mb.innerHTML = mb.hidden ? '' : '<button type="button" class="chip" data-m-chip="" aria-pressed="' + (st.m ? 'false' : 'true') + '">' + H(g) + 'すべて</button>' + ml.map(function (m) {
        return '<button type="button" class="chip" data-m-chip="' + H(m) + '" aria-pressed="' + (st.m === m ? 'true' : 'false') + '">' + H(m) + '<small> ' + nm[m] + '</small></button>';
      }).join('');
      sb.hidden = !st.m || sl.length < 2;
      sb.innerHTML = sb.hidden ? '' : '<button type="button" class="chip" data-s-chip="" aria-pressed="' + (st.s ? 'false' : 'true') + '">' + H(st.m) + 'すべて</button>' + sl.map(function (s) {
        return '<button type="button" class="chip" data-s-chip="' + H(s) + '" aria-pressed="' + (st.s === s ? 'true' : 'false') + '">' + H(s) + '<small> ' + ns[s] + '</small></button>';
      }).join('') + (many ? '<button type="button" class="chip" data-s-chip="*" aria-pressed="' + (st.s === '*' ? 'true' : 'false') + '">その他<small> ' + restN + '</small></button>' : '');
    }
    var mBox = $('#mid-chips'), sBox = $('#sub-chips');
    if (mBox) mBox.addEventListener('click', function (ev) { var b = ev.target.closest ? ev.target.closest('[data-m-chip]') : null; if (b) { st.m = b.getAttribute('data-m-chip'); st.s = ''; run(); } });
    if (sBox) sBox.addEventListener('click', function (ev) { var b = ev.target.closest ? ev.target.closest('[data-s-chip]') : null; if (b) { st.s = b.getAttribute('data-s-chip'); run(); } });
    var t;
    q.addEventListener('input', function () { clearTimeout(t); t = setTimeout(run, 120); });
    $('#searchform').addEventListener('submit', function (e) { e.preventDefault(); run(); });
    $$('[data-g-chip]').forEach(function (b) { b.addEventListener('click', function () { st.g = b.getAttribute('data-g-chip'); st.m = ''; st.s = ''; run(); }); });
    var tb = $('#f-son');
    if (tb) tb.addEventListener('click', function () { st.t = !st.t; run(); });
    loadCatalog().then(function (c) { cat = c || []; if (!c) info.textContent = '読み込めませんでした。しばらくして開き直してください。'; run(); });
  }


  /* ---------- carry over to another device with a Google account: the data goes to the visitor's own Google Drive (a hidden app folder);
     this site's server never holds it.  Shown only when config.json has google_client_id. ---------- */
  var GCID = CONF.gclient || '';
  function loadGis(cb) {
    if (window.google && google.accounts && google.accounts.oauth2) return cb();
    var el = document.createElement('script');
    el.src = 'https://accounts.google.com/gsi/client'; el.onload = cb; el.onerror = function () { toast('Google に接続できませんでした。'); };
    document.head.appendChild(el);
  }
  function gToken(cb) {
    loadGis(function () {
      google.accounts.oauth2.initTokenClient({ client_id: GCID, scope: 'https://www.googleapis.com/auth/drive.appdata',
        callback: function (r) { if (r && r.access_token) cb(r.access_token); else toast('Google との接続を取り消しました。'); } }).requestAccessToken({ prompt: '' });
    });
  }
  function gApi(tok, url, opt) {
    opt = opt || {}; opt.headers = Object.assign({ Authorization: 'Bearer ' + tok }, opt.headers || {});
    return fetch(url, opt).then(function (r) { if (!r.ok) throw new Error(r.status); return r; });
  }
  function gFind(tok) {
    return gApi(tok, 'https://www.googleapis.com/drive/v3/files?spaces=appDataFolder&fields=files(id)&q=' + encodeURIComponent("name='atomou.json'")).then(function (r) { return r.json(); })
      .then(function (j) { return j.files && j.files[0] ? j.files[0].id : null; });
  }
  function gPut(tok, id, obj) {
    var json = JSON.stringify(obj);
    if (id) return gApi(tok, 'https://www.googleapis.com/upload/drive/v3/files/' + id + '?uploadType=media', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: json });
    var b = 'atomou' + Math.random().toString(36).slice(2);
    return gApi(tok, 'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart', { method: 'POST', headers: { 'Content-Type': 'multipart/related; boundary=' + b },
      body: '--' + b + '\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n' + JSON.stringify({ name: 'atomou.json', parents: ['appDataFolder'] }) + '\r\n--' + b +
        '\r\nContent-Type: application/json\r\n\r\n' + json + '\r\n--' + b + '--' });
  }
  function syncNow() {
    stat('act:sync');
    gToken(function (tok) {
      gFind(tok).then(function (id) {
        if (!id) return gPut(tok, null, S).then(function () { toast('Google ドライブに保存しました。別の端末でも同じ手順で読み込めます。'); });
        return gApi(tok, 'https://www.googleapis.com/drive/v3/files/' + id + '?alt=media').then(function (r) { return r.json(); }).then(function (remote) {
          S = mergeStates(S, normalize(remote)); persist(); applyPrefs();
          return gPut(tok, id, S).then(function () { renderMy(); toast('同期しました。'); });
        });
      }).catch(function () { toast('同期できませんでした。しばらくして、もう一度お試しください。'); });
    });
  }

  /* ---------- my page ---------- */
  function renderMy() {
    var grid = $('#my-grid'), empty = $('#my-empty'), tools = $('#my-tools');
    loadCatalog().then(function (cat) {
      var items = myItems(cat || []);
      empty.hidden = items.length > 0; tools.hidden = !items.length;
      grid.setAttribute('data-save-order', '1');
      render(grid, items);
    });
  }
  function pageMy() {
    renderMy();
    var grid = $('#my-grid');
    wireReorderToggle($('#reorder'), grid);
    if (P.added) { toast('保存しました。'); try { history.replaceState(null, '', '/my/'); } catch (e) { /* ignore */ } }
    var big = $('#p-big'), alarm = $('#p-alarm');
    big.checked = !!S.prefs.big; alarm.value = S.prefs.alarm;
    var st = $('#p-stats'), sb = $('#sync-box'), sn = $('#sync-now');
    if (st) { st.checked = !!S.prefs.stats; st.addEventListener('change', function () { S.prefs.stats = st.checked; persist(); toast(st.checked ? 'ご協力ありがとうございます。' : '統計の送信を止めました。'); }); }
    if (sb && GCID) { sb.hidden = false; sn.addEventListener('click', syncNow); }
    big.addEventListener('change', function () { S.prefs.big = big.checked; persist(); applyPrefs(); });
    alarm.addEventListener('change', function () { S.prefs.alarm = alarm.value; persist(); toast('通知の時間を変更しました。'); });
    $('#ics-all').addEventListener('click', function () {
      loadCatalog().then(function (cat) {
        var evs = [], by = {};
        (cat || []).forEach(function (c) { by[c.id] = c; });
        S.entries.forEach(function (e) {
          var d = C.parse(e.date);
          if (d && e.precision === 'day') evs.push({ uid: 'm-' + e.id, title: e.title, date: d, time: e.time || '', yearly: !!e.yearly, every100: !!e.every100, alarm: e.alarm || S.prefs.alarm });
        });
        S.saved.forEach(function (id) {
          var c = by[id], d = c && C.parse(c.date);
          if (d && c.precision === 'day') evs.push({ uid: 'e-' + id, title: c.title, date: d, alarm: S.prefs.alarm });
        });
        if (!evs.length) { toast('ファイルにできる日がありません。'); return; }
        ICS.download('atomou-all.ics', ICS.build(evs, 'あと何日、もう何日'));
        toast(evs.length + '件の予定をファイルにしました。');
      });
    });
    $('#backup').addEventListener('click', function () { download('atomou-backup.json', JSON.stringify(S, null, 1)); });
    $('#restore').addEventListener('change', function (ev) {
      var f = ev.target.files[0];
      if (!f) return;
      var rd = new FileReader();
      rd.onload = function () {
        try {
          var o = JSON.parse(rd.result);
          if (!o || !Array.isArray(o.entries)) throw new Error('bad');
          localStorage.setItem(KEY, JSON.stringify(o)); S = load(); persist(); applyPrefs(); renderMy(); toast('読み込みました。');
        } catch (e) { toast('このファイルは読み込めませんでした。'); }
      };
      rd.readAsText(f);
    });
    $('#wipe').addEventListener('click', function () {
      if (!window.confirm('この端末の記録と設定をすべて消します。元に戻せません。よろしいですか。')) return;
      S = blank(); persist(); applyPrefs(); renderMy(); big.checked = false; toast('すべて消しました。');
    });
  }

  function whenToken(t) {  // dates the "today's numbers" page links to, worked out from the device's today
    var y = TODAY[0], c;
    if (t === 'year-end') return [y, 12, 31];
    if (t === 'new-year') return [y + 1, 1, 1];
    if (t === 'fy-start') { c = [y, 4, 1]; return C.cmp(c, TODAY) <= 0 ? [y + 1, 4, 1] : c; }
    if (t === 'fy-end') { c = [y, 3, 31]; return C.cmp(c, TODAY) < 0 ? [y + 1, 3, 31] : c; }
    if (t === 'today') return TODAY;
    return null;
  }

  var MIC_SVG = '<svg class="mic" viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" focusable="false"><path fill="currentColor" d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.9V22h2v-3.1A7 7 0 0 0 19 12h-2z"/></svg>';
  function micHint(what) { return '<p class="hint mic-hint">' + MIC_SVG + '<span>' + (what || '') + 'キーボードのマイクで、声でも入れられます。</span></p>'; }
  window.AtomouMicHint = micHint;

  /* ---------- add ---------- */
  function pageAdd() {
    var root = $('#wizard'), st = { kind: '', p: 'day', words: [] };
    root.innerHTML =
      '<section id="s1"><h2>1. どんな日ですか</h2><div class="tiles">' + Object.keys(KINDS).map(function (k) {
        return '<button type="button" class="tile" data-kind="' + k + '"><span>' + H(KINDS[k].t) + '</span><br><small class="muted">' + H(KINDS[k].d) + '</small></button>';
      }).join('') + '</div></section>' +
      '<section id="s2" hidden><h2>2. いつの日ですか</h2><div class="seg" role="group" aria-label="日付の細かさ">' +
      '<button type="button" class="chip" data-p="day" aria-pressed="true">年月日まで分かる</button><button type="button" class="chip" data-p="month" aria-pressed="false">年と月だけ</button>' +
      '<button type="button" class="chip" data-p="year" aria-pressed="false">年だけ</button></div>' +
      '<div class="field"><label for="f-day" id="lab-date">日付を選ぶ</label><input type="date" id="f-day" min="0100-01-01" max="2200-12-31">' +
      '<input type="month" id="f-month" hidden placeholder="2026-10"><input type="number" id="f-year" hidden inputmode="numeric" min="1" max="2200" placeholder="例 1990"></div>' +
      '<div class="field"><label for="f-say">文字や声で入力する(例: 12月25日)</label><input type="text" id="f-say" autocomplete="off" maxlength="30" placeholder="12月25日 / 2027年3月3日 / 明日">' +
      '<p class="hint" id="say-note" aria-live="polite"></p>' + micHint('') + '</div>' +
      '<button type="button" class="chip" id="f-today">今日にする</button><p class="hint" id="h-approx" hidden>年や月までの日付は、「約」つきで数えます。</p><p class="err" id="e-date" role="alert"></p>' +
      '<div id="live" class="live" hidden aria-live="polite"></div></section>' +
      '<section id="s3" hidden><h2>3. 名前</h2><p class="hint">候補を選ぶか、短く入力します。</p><div class="chips" id="f-words"></div>' +
      '<div class="field"><label for="f-title">名前</label><input type="text" id="f-title" maxlength="40" autocomplete="off">' + micHint('') + '</div></section>' +
      '<section id="s4" hidden><h2>4. 時刻・くり返し</h2>' +
      '<div class="field" id="f-timebox" hidden><label for="f-time">時刻(任意)</label><input type="time" id="f-time"></div>' +
      '<label class="chip" id="l-yearly"><input type="checkbox" id="f-yearly"> 毎年くり返す</label> <label class="chip" id="l-100"><input type="checkbox" id="f-100"> 100日ごとの節目も入れる</label>' +
      '<p class="hint">記録したあと、メモとやることを書けます。</p></section>' +
      '<p id="quiet-note" class="notice quiet" hidden>静かに記録できます。広告は表示しません。</p>' +
      '<p><button type="button" class="btn" id="f-save" hidden>この日を記録する</button></p>';
    var $f = function (id) { return document.getElementById(id); };
    function show(id, on) { $f(id).hidden = !on; }
    function readDate() {
      var d = null, v;
      if (st.p === 'day') { v = $f('f-day').value; d = v ? C.parse(v) : null; }
      else if (st.p === 'month') {
        var m = /^(\d{4})-(\d{2})$/.exec($f('f-month').value.trim());
        d = m && +m[2] >= 1 && +m[2] <= 12 ? [+m[1], +m[2], 1] : null;
      } else { var y = parseInt($f('f-year').value, 10); d = y >= 1 && y <= 2200 ? [y, 1, 1] : null; }
      return d;
    }
    function titleNow() { var t = $f('f-title').value.trim(); return t || (st.kind ? KINDS[st.kind].t : ''); }
    function update() {
      var d = readDate(), k = KINDS[st.kind] || {};   // no kind chosen yet (the page opens that way): nothing to show, but nothing to throw either
      ['s3', 's4', 'live', 'f-save'].forEach(function (id) { show(id, !!d && !!st.kind); });
      show('s4', !!d && st.p === 'day');
      show('quiet-note', !!k.quiet);
      show('l-100', !k.quiet && !k.time && st.p === 'day');
      show('f-timebox', !!k.time && st.p === 'day');
      if (!d) { $f('e-date').textContent = ''; return; }
      var r = C.countdown(d, TODAY, st.p);
      var live = $f('live');
      live.className = 'live' + (r.dir === 'mou' ? ' mou' : '');
      live.innerHTML = '<div>' + H(titleNow()) + '</div><div class="big">' + H(r.big) + '</div>' + (r.sub ? '<div class="muted">合計 ' + H(r.sub) + '</div>' : '') +
        '<div class="muted">' + H(fmtDate(C.iso(d), st.p)) + '</div>';
    }
    function setKind(k) {
      st.kind = k;
      $$('[data-kind]', root).forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-kind') === k ? 'true' : 'false'); });
      show('s2', true);
      var kd = KINDS[k];
      $f('f-yearly').checked = !!kd.yearly; $f('f-100').checked = !!kd.r100;
      $f('f-words').innerHTML = kd.words.map(function (w) { return '<button type="button" class="chip" data-word="' + H(w) + '">' + H(w) + '</button>'; }).join('');
      show('s3', false);
      update();
      $f('s2').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    function say() {
      var v = $f('f-say').value, note = $f('say-note'), d;
      if (!v.trim()) { note.textContent = ''; return; }
      d = C.parseSpoken(v, st.p, TODAY);
      if (!d) { note.textContent = st.p === 'day' ? '読み取れませんでした。年月日で入力してください(例: 12月25日)。' : st.p === 'month' ? '読み取れませんでした。年と月で入力してください(例: 2026年10月)。' : '読み取れませんでした。年で入力してください(例: 1990年)。'; return; }
      if (st.p === 'day') $f('f-day').value = C.iso(d);
      else if (st.p === 'month') $f('f-month').value = String(d[0]).padStart(4, '0') + '-' + String(d[1]).padStart(2, '0');
      else $f('f-year').value = d[0];
      note.textContent = '→ ' + fmtDate(C.iso(d), st.p);
      update();
    }
    function setP(p) {
      st.p = p;
      $$('[data-p]', root).forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-p') === p ? 'true' : 'false'); });
      $f('f-day').hidden = p !== 'day'; $f('f-month').hidden = p !== 'month'; $f('f-year').hidden = p !== 'year';
      $f('lab-date').setAttribute('for', p === 'day' ? 'f-day' : p === 'month' ? 'f-month' : 'f-year');
      $f('lab-date').textContent = p === 'day' ? '日付を選ぶ' : p === 'month' ? '年と月(例 2026-10)' : '年(例 1990)';
      $f('f-today').hidden = p !== 'day'; $f('h-approx').hidden = p === 'day';
      $f('f-say').value = ''; $f('say-note').textContent = '';
      update();
    }
    root.addEventListener('click', function (ev) {
      var t = ev.target.closest('button');
      if (!t) return;
      if (t.hasAttribute('data-kind')) setKind(t.getAttribute('data-kind'));
      else if (t.hasAttribute('data-p')) setP(t.getAttribute('data-p'));
      else if (t.id === 'f-today') { $f('f-day').value = C.iso(TODAY); $f('f-say').value = ''; $f('say-note').textContent = ''; update(); }
      else if (t.hasAttribute('data-word')) {
        var w = t.getAttribute('data-word'), cur = $f('f-title').value;
        $f('f-title').value = (w.charAt(0) === 'の' && cur) ? cur + w : w; update();
      }
      else if (t.id === 'f-save') save();
    });
    $f('f-say').addEventListener('input', say);
    ['f-day', 'f-month', 'f-year'].forEach(function (id) { $f(id).addEventListener('input', function () { $f('f-say').value = ''; $f('say-note').textContent = ''; }); });
    ['f-day', 'f-month', 'f-year', 'f-title', 'f-time'].forEach(function (id) { $f(id).addEventListener('input', update); $f(id).addEventListener('change', update); });
    function save() {
      var d = readDate();
      if (!d) { $f('e-date').textContent = '日付を入れてください。'; return; }
      var k = KINDS[st.kind], e = {
        id: uid(), title: titleNow(), date: C.iso(d), precision: st.p, kind: st.kind, quiet: !!k.quiet,
        yearly: st.p === 'day' && $f('f-yearly').checked, every100: st.p === 'day' && !k.quiet && !k.time && $f('f-100').checked, alarm: k.quiet ? 'none' : '', created: C.iso(TODAY),
        time: k.time && st.p === 'day' && /^\d{2}:\d{2}$/.test($f('f-time').value) ? $f('f-time').value : ''
      };
      if (window.AtomouApp && window.AtomouApp.tier && window.AtomouApp.tier.blocked(1) && !k.quiet) return;   // a free planner is full (the reason is shown)
      S.entries.push(e); stat('act:add:' + e.kind);
      if (!persist()) return;  // storage blocked: stay on the form (the toast explains) instead of leaving and losing what was typed
      location.href = '/plan/?key=m:' + e.id + '&new=1';
    }
    if (P.kind && KINDS[P.kind]) setKind(P.kind);
    if (P.title) { $f('f-title').value = P.title; }
    var when = P.date && C.parse(P.date) ? C.parse(P.date) : whenToken(P.when);
    if (when) { if (!st.kind) setKind('memo'); $f('f-day').value = C.iso(when); }
    update();
  }

  /* ---------- category page (filter by sub-category) ---------- */
  function pageCategory() {
    var chips = $$('[data-cat-chip]'), cards = $$('#grid .card'), subBox = $('#subchips'), mid = '', sub = '', top = {};
    var hm = /[#&]m=([^&]+)/.exec(location.hash || ''), hs = /[#&]s=([^&]+)/.exec(location.hash || '');
    if (hm) { try { mid = decodeURIComponent(hm[1]); } catch (e) { mid = ''; } }
    if (hs && mid) { try { sub = decodeURIComponent(hs[1]); } catch (e) { sub = ''; } }
    function keep() { try { history.replaceState(null, '', location.pathname + (mid ? '#m=' + encodeURIComponent(mid) + (sub ? '&s=' + encodeURIComponent(sub) : '') : '')); } catch (e) { /* ignore */ } }
    function apply() {   // 大 is the page; 中 = data-cat; 小 = data-sub
      chips.forEach(function (x) { x.setAttribute('aria-pressed', x.getAttribute('data-cat-chip') === mid ? 'true' : 'false'); });
      cards.forEach(function (card) { card.hidden = (!!mid && card.getAttribute('data-cat') !== mid) || (!!sub && card.getAttribute('data-sub') !== sub); });
      if (!subBox) return;
      var n = {}, list, all, many, restN = 0;
      cards.forEach(function (card) { if (mid && card.getAttribute('data-cat') === mid) { var s = card.getAttribute('data-sub') || ''; if (s) n[s] = (n[s] || 0) + 1; } });
      all = Object.keys(n).sort(function (a, b) { return n[b] - n[a] || (a < b ? -1 : 1); }); many = all.length > SUBCAP;
      list = many ? all.slice(0, SUBCAP - 1) : all; top = {}; list.forEach(function (s) { top[s] = 1; });
      if (many) all.slice(SUBCAP - 1).forEach(function (s) { restN += n[s]; });
      cards.forEach(function (card) { if (sub) card.hidden = (!!mid && card.getAttribute('data-cat') !== mid) || (sub === '*' ? !!top[card.getAttribute('data-sub')] : card.getAttribute('data-sub') !== sub); });
      subBox.hidden = !(mid && list.length > 1);
      subBox.innerHTML = subBox.hidden ? '' : '<button type="button" class="chip" data-sub-chip="" aria-pressed="' + (sub ? 'false' : 'true') + '">' + H(mid) + 'すべて</button>' + list.map(function (s) {
        return '<button type="button" class="chip" data-sub-chip="' + H(s) + '" aria-pressed="' + (sub === s ? 'true' : 'false') + '">' + H(s) + '<small> ' + n[s] + '</small></button>';
      }).join('') + (many ? '<button type="button" class="chip" data-sub-chip="*" aria-pressed="' + (sub === '*' ? 'true' : 'false') + '">その他<small> ' + restN + '</small></button>' : '');
    }
    chips.forEach(function (b) {
      b.addEventListener('click', function () {
        mid = b.getAttribute('data-cat-chip'); sub = '';
        keep(); apply();
      });
    });
    if (subBox) subBox.addEventListener('click', function (ev) {
      var b = ev.target.closest ? ev.target.closest('[data-sub-chip]') : null;
      if (!b) return;
      sub = b.getAttribute('data-sub-chip'); keep(); apply();
    });
    if (mid && !chips.some(function (x) { return x.getAttribute('data-cat-chip') === mid; })) { mid = ''; sub = ''; }
    if (sub && sub !== '*' && !cards.some(function (c) { return c.getAttribute('data-cat') === mid && c.getAttribute('data-sub') === sub; })) sub = '';
    apply();
  }

  /* ---------- today's numbers page ---------- */
  function pageToday() {
    var n = C.dayOfYear(TODAY), fy = C.fiscalYear(TODAY), vals = {
      'year': '' + n[0], 'year-left': '' + n[1], 'newyear': '' + (n[1] + 1), 'newyear-y': '' + (TODAY[0] + 1), 'fy': '' + fy[2], 'fy-y': '' + fy[0], 'fy-pass': '' + fy[1],
      'today': fmtDate(C.iso(TODAY), 'day'), 'y': '' + TODAY[0]
    };
    $$('[data-num]').forEach(function (el) { el.textContent = vals[el.getAttribute('data-num')] || ''; });
    $$('a[data-when]').forEach(function (a) {
      var d = whenToken(a.getAttribute('data-when'));
      if (d) a.setAttribute('href', a.getAttribute('href') + (a.getAttribute('href').indexOf('?') < 0 ? '?' : '&') + 'date=' + C.iso(d));
    });
  }

  document.addEventListener('atomou:changed', function () {
    if (page === 'home') renderMine(); else if (page === 'my') renderMy();
  });

  /* ---------- the first screen of a visitor who has recorded nothing yet ---------- */
  function renderHero() {
    var h = $('#hero-cta');
    if (h) h.hidden = S.entries.length > 0 || S.saved.length > 0;
  }
  document.addEventListener('atomou:changed', renderHero);

  /* ---------- the contact form, when it was reached from "send it as a day I would like to see" on the search page ---------- */
  function prefillContact() {
    var f = document.querySelector('form.cf');
    if (!f || !P.kind) return;
    var sel = f.querySelector('select[name="kind"]'), ta = f.querySelector('textarea');
    if (sel && P.kind === 'request') { Array.prototype.forEach.call(sel.options, function (o) { if (o.value.indexOf('載せてほしい') === 0) sel.value = o.value; }); }
    if (ta && P.q && !ta.value) ta.value = '載せてほしい日: ' + String(P.q).slice(0, 60) + '\n(いつ頃か、どこで確認できるか、わかれば書いてください)\n';
  }

  /* ---------- start ---------- */
  function chipFade() {   // a row of chips that goes on past the screen edge fades at that edge (so people who do not know "swipe" see there is more)
    $$('.chiprow, .chips.scroll').forEach(function (r) {
      function upd() { r.classList.toggle('more-right', r.scrollWidth - r.clientWidth - r.scrollLeft > 4); }
      upd(); r.addEventListener('scroll', upd, { passive: true }); window.addEventListener('resize', upd);
    });
  }
  prefillContact();
  applyPrefs();
  hydrate(document);
  renderSeason();
  renderHero();
  chipFade();
  stat('view:' + (/^[a-z]+$/.test(page) ? page : 'other'));
  stat('skin:' + S.prefs.skin);
  if (S.prefs.big) stat('big:on');
  if (page === 'home') pageHome();
  else if (page === 'search') pageSearch();
  else if (page === 'regionhub') pageRegionHub();
  else if (page === 'my') pageMy();
  else if (page === 'add') pageAdd();
  else if (page === 'skins') pageSkins();
  else if (page === 'category') pageCategory();
  else if (page === 'today') pageToday();
  else if (page === 'interests') pageInterests();
  window.AtomouApp = { toggleSave: toggleSave, regionHits: regionHits, interestHits: interestHits, matchCat: matchCat, catItem2: catItem,  C: C, ICS: ICS, CONF: CONF, P: P, TODAY: TODAY, page: page, $: $, $$: $$, H: H, state: function () { return S; }, setState: function (x) { S = x; }, persist: persist, stat: stat, toast: toast, toastAct: toastAct,
    loadCatalog: loadCatalog, catItem: catItem, ownItem: ownItem, cardHtml: cardHtml, hydrate: hydrate, fillCard: fillCard, fmtDate: fmtDate, wd: wd, occ: occ, nextYearly: nextYearly, KINDS: KINDS,
    findEntry: findEntry, uid: uid, icsFor: icsFor, removeEntry: removeEntry, normalize: normalize, tipFor: tipFor, nextLines: nextLines, applyPrefs: applyPrefs };
  if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost') && !P.today) {
    window.addEventListener('load', function () { navigator.serviceWorker.register('/sw.js').catch(function () { /* the site works without it */ }); });
  }
  window.Atomou = { state: function () { return S; }, today: TODAY, tipFor: tipFor, nextLines: nextLines, whenToken: whenToken, stat: stat, statQueue: function () { return statQ; },
    normalize: normalize, mergeStates: mergeStates };
})();
