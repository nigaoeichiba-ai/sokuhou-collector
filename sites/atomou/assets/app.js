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
  var TODAY = (function () {
    var p = P.today && /^\d{4}-\d{2}-\d{2}$/.test(P.today) ? C.parse(P.today) : null;
    if (p) return p;
    var n = new Date();
    return [n.getFullYear(), n.getMonth() + 1, n.getDate()];
  })();

  /* ---------- state ---------- */
  var S = blank();
  function blank() { return { v: 1, entries: [], saved: [], order: [], genre: {}, prefs: { skin: 'basic', big: false, alarm: 'morning', blocks: { order: [], hidden: [] } } }; }
  function load() {
    var s = blank();
    try {
      var raw = localStorage.getItem(KEY);
      if (raw) {
        var o = JSON.parse(raw);
        s.entries = (o.entries || []).filter(function (e) { return e && e.id && e.title != null && C.parse(e.date); });
        s.saved = (o.saved || []).filter(function (x) { return typeof x === 'string'; });
        s.order = (o.order || []).filter(function (x) { return typeof x === 'string'; });
        s.genre = o.genre || {};
        Object.keys(s.prefs).forEach(function (k) { if (o.prefs && o.prefs[k] != null) s.prefs[k] = o.prefs[k]; });
      }
    } catch (e) { /* storage blocked: the page still works for this visit */ }
    return s;
  }
  var warned = false;
  function persist() {
    try { localStorage.setItem(KEY, JSON.stringify(S)); return true; } catch (e) {
      if (!warned) { warned = true; toast('この端末では保存できませんでした(プライベートモードなど)。このページを閉じると消えます。'); }
      return false;
    }
  }
  S = load();

  /* ---------- small helpers ---------- */
  var toastTimer;
  function toast(msg) {
    var t = $('#toast');
    if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    t.textContent = msg; t.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.hidden = true; }, 4200);
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
    anniversary: { t: '記念日', d: '結婚・付き合った日・開店など', g: 3, yearly: true, r100: true, words: ['結婚記念日', '付き合った日', '出会った日', '開店した日'] },
    birthday: { t: '誕生日', d: '家族・友だち・推し', g: 2, yearly: true, r100: false, words: ['の誕生日', '家族の誕生日', '推しの誕生日'] },
    memorial: { t: '大切な人を思う日', d: '命日・ペット・あの日', g: 0, yearly: true, r100: false, quiet: true, words: ['命日', 'ペットの命日', 'あの日'] },
    since: { t: 'はじめた日', d: '禁煙・転職・引っ越し・ダイエット', g: 4, yearly: false, r100: true, words: ['禁煙をはじめた日', '引っ越した日', '転職した日', 'ダイエットをはじめた日'] },
    until: { t: '楽しみな日・期限', d: '旅行・試験・提出・ライブ', g: 1, yearly: false, r100: false, words: ['旅行', '試験', 'ライブ', '提出の期限'] },
    memo: { t: 'そのほか', d: 'ほかのなんでも', g: 6, yearly: false, r100: false, words: [] }
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
      out.push(when(y, e.kind === 'birthday' ? '次の誕生日(' + n + '歳)' : e.kind === 'memorial' ? '次の同じ日(' + n + '年)' : '次の記念日(' + n + '年目)'));
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
        if (left <= 150) return 'もうすぐ' + NENKI[n] + 'にあたります。法要をするときは、日程や場所を、早めに家族で相談しておくと安心です。';
      }
      if (left > 0 && left <= 30) return 'もうすぐ同じ日です。お花やお供えは、前もって用意しておけます。';
      return '';
    }
    if (e.yearly) {
      next = nextYearly(d, today); left = C.totalDays(today, next); passed = C.totalDays(lastYearly(d, today), today);
      var bd = e.kind === 'birthday';
      if (left === 0) return bd ? '今日は誕生日です。お祝いのメッセージを送りませんか。' : '今日は記念日です。';
      if (left <= 14) return left + '日後です。プレゼントやお店の予約は、そろそろ決めておくと安心です。';
      if (passed >= 1 && passed <= 30) return bd ? 'お誕生日を、少しすぎました。メッセージは、いまからでも間に合います。' : '記念日を、少しすぎました。まだお祝いしていなければ、ささやかなプレゼントや食事はいかがでしょう。';
      return '';
    }
    if (!e.quiet && e.kind === 'since') {
      var r = nextRound(d, today, e.every100 ? 100 : 1000);
      var gap = C.totalDays(today, r.date);
      if (gap >= 0 && gap <= 7) return 'もうすぐ' + C.group(r.n) + '日目です。ここまで続けてきた日々を、ふり返ってみませんか。';
    }
    return '';
  }

  /* ---------- cards (the same markup as build.py card_html) ---------- */
  function catItem(c) {
    return { key: 'c:' + c.id, id: c.id, title: c.title, date: c.date, p: c.precision || 'day', g: CONF.groups.indexOf(c.group) + 1, kind: c.kind, region: c.region, quiet: !!c.quiet,
      src: c.source_url, checked: c.checked_on, cat: c.category, own: false, href: '/e/' + c.id + '/' };
  }
  function ownItem(e) {
    var k = KINDS[e.kind] || KINDS.memo;
    return { key: 'm:' + e.id, id: e.id, title: e.title, date: e.date, p: e.precision || 'day', g: k.g, kind: k.t, quiet: !!e.quiet, own: true };
  }
  function cardHtml(it) {
    var h = '<article class="card' + (it.quiet ? ' quiet' : '') + '" data-key="' + H(it.key) + '" data-title="' + H(it.title) + '" data-date="' + H(it.date) + '" data-p="' + it.p + '"' +
      (it.g ? ' data-g="' + it.g + '"' : '') + (it.cat ? ' data-cat="' + H(it.cat) + '"' : '') + '>';
    h += '<div class="c-top">' + (it.g ? '<span class="mark m' + it.g + '" data-g="' + it.g + '" aria-hidden="true"></span>' : '') + '<span class="badge">' + H(it.kind) + '</span>' +
      (it.region ? '<span class="reg">' + H(it.region) + '</span>' : '') + '</div>';
    h += '<p class="c-count"><span class="word"></span><span class="num"></span></p><p class="c-sub"></p>';
    h += '<h3 class="c-title">' + (it.href ? '<a href="' + H(it.href) + '">' + H(it.title) + '</a>' : H(it.title)) + '</h3>';
    h += '<p class="c-date">' + H(fmtDate(it.date, it.p)) + '</p>';
    if (it.own) h += '<div class="c-next"></div>';
    else h += '<p class="c-src">出典: ' + H(host(it.src)) + '(確認日 ' + H(it.checked) + ')</p>';
    h += '<div class="c-act">';
    if (!it.own) h += '<button type="button" class="btn small ghost" data-act="save" aria-pressed="false">☆ 保存する</button>';
    if (it.p === 'day') h += '<button type="button" class="btn small" data-act="ics">カレンダーに入れる</button>';
    if (it.own) h += '<button type="button" class="btn small ghost" data-act="del">消す</button>';
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
    var word = $('.word', card), num = $('.num', card), sub = $('.c-sub', card);
    if (word) word.textContent = w[0];
    if (num) num.textContent = w[1];
    if (sub) sub.textContent = r.sub ? '合計 ' + r.sub : '';
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
      sv.textContent = on ? '★ 保存ずみ' : '☆ 保存する';
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
    var per = Math.ceil(n / Math.max(1, CONF.groups.length)), pick = [], seen = {};
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
  function ordered(items) {
    var idx = {};
    S.order.forEach(function (k, i) { idx[k] = i; });
    return items.map(function (it, i) { return { it: it, i: i }; }).sort(function (a, b) {
      var x = idx[a.it.key] == null ? 1e6 + a.i : idx[a.it.key], y = idx[b.it.key] == null ? 1e6 + b.i : idx[b.it.key];
      return x - y;
    }).map(function (o) { return o.it; });
  }
  function moveCard(card, dir) {
    var sib = dir < 0 ? card.previousElementSibling : card.nextElementSibling;
    if (!sib) return;
    if (dir < 0) card.parentNode.insertBefore(card, sib); else card.parentNode.insertBefore(sib, card);
    card.focus && card.scrollIntoView({ block: 'nearest' });
    changed(card.parentNode);
  }
  function changed(grid) {
    if (grid.getAttribute('data-save-order') === '1') {
      S.order = $$('.card', grid).map(function (c) { return c.getAttribute('data-key'); });
      persist();
    }
  }
  function startDrag(card, ev) {
    var grid = card.parentNode, grip = ev.target, id = ev.pointerId;
    ev.preventDefault();
    card.classList.add('dragging'); document.body.classList.add('drag-on');
    try { grip.setPointerCapture(id); } catch (e) { /* the document listeners below work without it */ }
    function move(e) {
      if (e.pointerId !== id) return;
      var y = e.clientY;
      if (y < 70) window.scrollBy(0, -14); else if (y > window.innerHeight - 70) window.scrollBy(0, 14);
      var el = document.elementFromPoint(e.clientX, e.clientY), over = el && el.closest && el.closest('.card');
      if (!over || over === card || over.parentNode !== grid) return;
      var r = over.getBoundingClientRect(), after = (e.clientX - r.left) / r.width + (e.clientY - r.top) / r.height > 1;
      grid.insertBefore(card, after ? over.nextSibling : over);
    }
    function up(e) {
      if (e.pointerId !== id) return;
      document.removeEventListener('pointermove', move); document.removeEventListener('pointerup', up); document.removeEventListener('pointercancel', up);
      card.classList.remove('dragging'); document.body.classList.remove('drag-on'); changed(grid);
    }
    document.addEventListener('pointermove', move); document.addEventListener('pointerup', up); document.addEventListener('pointercancel', up);
  }
  function wireReorderToggle(btn, grid) {
    if (!btn) return;
    btn.addEventListener('click', function () {
      var on = !grid.classList.contains('reorder');
      grid.classList.toggle('reorder', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      btn.textContent = on ? '並べ替えを終わる' : 'カードを動かす';
      if (on) toast('つかむ印(⠿)をドラッグするか、↑↓で動かせます。');
    });
  }

  /* ---------- actions on cards ---------- */
  function icsFor(card) {
    var key = card.getAttribute('data-key') || '', d = C.parse(card.getAttribute('data-date')), title = card.getAttribute('data-title');
    if (!d || card.getAttribute('data-p') !== 'day') { toast('日にちがはっきりしないので、カレンダーには入れられません。'); return; }
    var ev;
    if (key.indexOf('m:') === 0) {
      var e = findEntry(key.slice(2));
      if (!e) return;
      ev = { uid: 'm-' + e.id, title: e.title, date: d, yearly: !!e.yearly, every100: !!e.every100, alarm: e.alarm || 'morning' };
    } else {
      ev = { uid: 'e-' + key.slice(2), title: title, date: d, alarm: S.prefs.alarm };
      if (S.saved.indexOf(key.slice(2)) < 0) { S.saved.push(key.slice(2)); persist(); fillCard(card); }
      var g = card.getAttribute('data-g');
      if (g && CONF.groups[g - 1]) { bump(CONF.groups[g - 1]); persist(); }
    }
    ICS.download('atomou-' + key.slice(2) + '.ics', ICS.build([ev], title));
    toast('カレンダーのファイルを作りました。開いて、予定に入れてください。');
  }
  function toggleSave(card) {
    var id = (card.getAttribute('data-key') || '').slice(2), i = S.saved.indexOf(id), g = card.getAttribute('data-g');
    if (i >= 0) { S.saved.splice(i, 1); toast('保存をはずしました。'); }
    else { S.saved.push(id); if (g && CONF.groups[g - 1]) bump(CONF.groups[g - 1]); toast('保存しました。マイページで見られます。'); }
    persist();
    $$('.card[data-key="c:' + id + '"]').forEach(fillCard);
    if (page === 'my') renderMy();
  }
  function removeEntry(card) {
    var id = (card.getAttribute('data-key') || '').slice(2), e = findEntry(id);
    if (!e || !window.confirm('「' + e.title + '」を消しますか。')) return;
    S.entries = S.entries.filter(function (x) { return x.id !== id; });
    S.order = S.order.filter(function (k) { return k !== 'm:' + id; });
    persist(); toast('消しました。');
    if (page === 'my') renderMy(); else if (page === 'home') renderMine();
  }
  document.addEventListener('click', function (ev) {
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
  document.addEventListener('pointerdown', function (ev) {
    var g = ev.target.closest ? ev.target.closest('[data-act="grip"]') : null;
    if (g && (ev.button === 0 || ev.pointerType === 'touch' || ev.pointerType === 'pen')) startDrag(g.closest('.card'), ev);
  });

  /* ---------- skins ---------- */
  function applyPrefs() {
    var r = document.documentElement, id = (P.skin && CONF.skins[P.skin]) ? P.skin : S.prefs.skin, sk = CONF.skins[id];  // ?skin= is for screenshots and tests
    if (!sk || id === 'basic') { r.removeAttribute('data-skin'); r.setAttribute('data-card', 'plain'); }
    else { r.setAttribute('data-skin', id); r.setAttribute('data-card', sk.card); }
    if (S.prefs.big) r.setAttribute('data-big', '1'); else r.removeAttribute('data-big');
  }
  function pageSkins() {
    var box = $('#skin-list');
    function mark() { $$('.skin', box).forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-skin') === S.prefs.skin ? 'true' : 'false'); }); }
    box.addEventListener('click', function (ev) {
      var b = ev.target.closest('.skin');
      if (!b) return;
      S.prefs.skin = b.getAttribute('data-skin'); persist(); applyPrefs(); mark();
      toast('「' + b.getAttribute('data-name') + '」にしました。');
    });
    mark();
  }

  /* ---------- home ---------- */
  function renderDaily() {
    var el = $('#daily');
    if (!el) return;
    var n = C.dayOfYear(TODAY), fy = C.fiscalYear(TODAY);
    el.innerHTML = '<span>今日は ' + fmtDate(C.iso(TODAY), 'day') + '</span><a href="/today/#year">' + TODAY[0] + '年は、もう' + n[0] + '日め(年末まであと' + n[1] + '日)</a>' +
      '<a href="/today/#newyear">' + (TODAY[0] + 1) + '年まであと' + (n[1] + 1) + '日</a><a href="/today/#fy">' + fy[0] + '年度(4月から)は、あと' + fy[2] + '日</a>';
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
  function renderMine() {
    var box = $('#mine'), grid = $('#mine-grid');
    if (!box) return;
    loadCatalog().then(function (cat) {
      var items = myItems(cat).slice(0, 4);
      box.hidden = !items.length;
      if (items.length) render(grid, items);
    });
  }

  /* ---------- home blocks: reorder / show / hide (this device only) ---------- */
  var BLOCKS = ['search', 'cats', 'daily', 'mine', 'soon', 'record', 'usecases'];
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
        '<button type="button" class="mini" data-b="vis" aria-pressed="' + (off ? 'false' : 'true') + '">' + (off ? '出す' : 'かくす') + '</button></span>';
      els[k].insertBefore(bar, els[k].firstChild);
    });
  }
  function wireBlocks() {
    var host = $('#blocks'), btn = $('#edit-home');
    if (!host) return;
    var editing = P.edit === '1';
    function show() {
      applyBlocks(editing);
      if (btn) { btn.setAttribute('aria-pressed', editing ? 'true' : 'false'); btn.textContent = editing ? 'ホームの並べかえを終わる' : 'ホームの並べかえ・表示を変える'; }
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
    });
    if (btn) btn.addEventListener('click', function () { editing = !editing; show(); if (editing) toast('各ブロックの ↑↓ で並べかえ、「かくす」で表示を切りかえられます。'); });
    show();
  }

  function pageHome() {
    renderDaily(); renderMine(); wireBlocks();
    var grid = $('#grid'), pool = [];
    wireReorderToggle($('#reorder'), grid);
    loadCatalog().then(function (cat) {
      if (!cat) return;
      pool = liveFrom(cat);
      render(grid, diverse(pool, 12).map(catItem));
    });
    var sh = $('#shuffle');
    if (sh) sh.addEventListener('click', function () {
      if (!pool.length) { hydrate(grid); return; }
      render(grid, weighted(pool, 12).map(catItem));
    });
  }

  /* ---------- search ---------- */
  function norm(s) {
    return String(s || '').normalize('NFKC').toLowerCase().replace(/[ァ-ヶ]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 0x60); }).replace(/\s+/g, ' ').trim();
  }
  function pageSearch() {
    var q = $('#q'), out = $('#results'), info = $('#found'), st = { g: P.g || '', t: P.t === '1' }, cat = [];
    q.value = P.q || '';
    function sync() {
      var u = '/search/?' + [q.value ? 'q=' + encodeURIComponent(q.value) : '', st.g ? 'g=' + st.g : '', st.t ? 't=1' : ''].filter(Boolean).join('&');
      try { history.replaceState(null, '', u.replace(/\?$/, '')); } catch (e) { /* ignore */ }
    }
    function run() {
      var terms = norm(q.value).split(' ').filter(Boolean);
      $$('[data-g-chip]').forEach(function (b) { b.setAttribute('aria-pressed', (b.getAttribute('data-g-chip') === st.g) ? 'true' : 'false'); });
      var tb = $('#f-son'); if (tb) tb.setAttribute('aria-pressed', st.t ? 'true' : 'false');
      var gi = CONF.slugs.indexOf(st.g);
      var hits = cat.filter(function (c) {
        if (c.status === 'ended') return false;
        if (gi >= 0 && c.group !== CONF.groups[gi]) return false;
        if (st.t && !c.son_toku) return false;
        var hay = norm([c.title, c.category, c.group, c.region, c.kind].concat(c.tags || []).join(' '));
        return terms.every(function (t) { return hay.indexOf(t) >= 0; });
      }).sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; });
      var shown = hits.slice(0, 60);
      render(out, shown.map(catItem));
      info.textContent = hits.length ? hits.length + '件' + (hits.length > 60 ? '(近い順に60件を表示)' : '') : '';
      var none = $('#none');
      none.hidden = hits.length > 0;
      var add = $('#none-add');
      if (add) add.href = '/add/' + (q.value ? '?title=' + encodeURIComponent(q.value) : '');
      sync();
    }
    var t;
    q.addEventListener('input', function () { clearTimeout(t); t = setTimeout(run, 120); });
    $('#searchform').addEventListener('submit', function (e) { e.preventDefault(); run(); });
    $$('[data-g-chip]').forEach(function (b) { b.addEventListener('click', function () { st.g = b.getAttribute('data-g-chip'); run(); }); });
    var tb = $('#f-son');
    if (tb) tb.addEventListener('click', function () { st.t = !st.t; run(); });
    loadCatalog().then(function (c) { cat = c || []; if (!c) info.textContent = '読み込めませんでした。時間をおいて、開き直してください。'; run(); });
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
    if (P.added) { toast('残しました。この端末の中だけに保存しています。'); try { history.replaceState(null, '', '/my/'); } catch (e) { /* ignore */ } }
    var big = $('#p-big'), alarm = $('#p-alarm');
    big.checked = !!S.prefs.big; alarm.value = S.prefs.alarm;
    big.addEventListener('change', function () { S.prefs.big = big.checked; persist(); applyPrefs(); });
    alarm.addEventListener('change', function () { S.prefs.alarm = alarm.value; persist(); toast('次からのカレンダーに使います。'); });
    $('#ics-all').addEventListener('click', function () {
      loadCatalog().then(function (cat) {
        var evs = [], by = {};
        (cat || []).forEach(function (c) { by[c.id] = c; });
        S.entries.forEach(function (e) {
          var d = C.parse(e.date);
          if (d && e.precision === 'day') evs.push({ uid: 'm-' + e.id, title: e.title, date: d, yearly: !!e.yearly, every100: !!e.every100, alarm: e.alarm || 'morning' });
        });
        S.saved.forEach(function (id) {
          var c = by[id], d = c && C.parse(c.date);
          if (d && c.precision === 'day') evs.push({ uid: 'e-' + id, title: c.title, date: d, alarm: S.prefs.alarm });
        });
        if (!evs.length) { toast('入れられる日がまだありません。'); return; }
        ICS.download('atomou-all.ics', ICS.build(evs, 'あと何日、もう何日'));
        toast(evs.length + '件を、カレンダーのファイルにしました。');
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
      if (!window.confirm('この端末に残した日と設定を、すべて消します。よろしいですか。')) return;
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
      '<button type="button" class="chip" id="f-today">今日にする</button><p class="err" id="e-date" role="alert"></p>' +
      '<div id="live" class="live" hidden aria-live="polite"></div></section>' +
      '<section id="s3" hidden><h2>3. 名前をつけましょう</h2><p class="hint">あとで見て分かる名前なら十分です。選ぶだけでも使えます。</p><div class="chips" id="f-words"></div>' +
      '<div class="field"><label for="f-title">名前</label><input type="text" id="f-title" maxlength="40" autocomplete="off"></div></section>' +
      '<section id="s4" hidden><h2>4. カレンダーのお知らせ</h2>' +
      '<label class="chip" id="l-yearly"><input type="checkbox" id="f-yearly"> 毎年くり返す</label> <label class="chip" id="l-100"><input type="checkbox" id="f-100"> 100日ごとの節目も入れる</label>' +
      '<div class="field"><label for="f-alarm">知らせる時間</label><select id="f-alarm"><option value="morning">当日の朝9時</option><option value="eve">前の日の夜9時</option><option value="week">1週間前の朝9時</option><option value="none">お知らせなし</option></select></div>' +
      '<p class="hint">カレンダーアプリの設定によっては、お知らせが出ないことがあります。</p></section>' +
      '<p id="quiet-note" class="notice quiet" hidden>大切な日は、静かに残します。広告やおすすめは出しません。</p>' +
      '<p><button type="button" class="btn" id="f-save" hidden>この日を残す</button></p>' +
      '<p class="hint">名前や日付は、この端末の中だけに保存します。サーバーには送りません。</p>';
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
      var d = readDate(), k = KINDS[st.kind];
      ['s3', 's4', 'live', 'f-save'].forEach(function (id) { show(id, !!d && !!st.kind); });
      show('s4', !!d && st.p === 'day');
      show('quiet-note', !!d && !!k.quiet);
      show('l-100', !k.quiet && st.p === 'day');
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
      $f('f-yearly').checked = !!kd.yearly; $f('f-100').checked = !!kd.r100; $f('f-alarm').value = S.prefs.alarm;
      $f('f-words').innerHTML = kd.words.map(function (w) { return '<button type="button" class="chip" data-word="' + H(w) + '">' + H(w) + '</button>'; }).join('');
      show('s3', false);
      update();
      $f('s2').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    function setP(p) {
      st.p = p;
      $$('[data-p]', root).forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-p') === p ? 'true' : 'false'); });
      $f('f-day').hidden = p !== 'day'; $f('f-month').hidden = p !== 'month'; $f('f-year').hidden = p !== 'year';
      $f('lab-date').setAttribute('for', p === 'day' ? 'f-day' : p === 'month' ? 'f-month' : 'f-year');
      $f('lab-date').textContent = p === 'day' ? '日付を選ぶ' : p === 'month' ? '年と月を入れる(例 2026-10)' : '年を入れる(例 1990)';
      $f('f-today').hidden = p !== 'day';
      update();
    }
    root.addEventListener('click', function (ev) {
      var t = ev.target.closest('button');
      if (!t) return;
      if (t.hasAttribute('data-kind')) setKind(t.getAttribute('data-kind'));
      else if (t.hasAttribute('data-p')) setP(t.getAttribute('data-p'));
      else if (t.id === 'f-today') { $f('f-day').value = C.iso(TODAY); update(); }
      else if (t.hasAttribute('data-word')) {
        var w = t.getAttribute('data-word'), cur = $f('f-title').value;
        $f('f-title').value = (w.charAt(0) === 'の' && cur) ? cur + w : w; update();
      }
      else if (t.id === 'f-save') save();
    });
    ['f-day', 'f-month', 'f-year', 'f-title', 'f-alarm'].forEach(function (id) { $f(id).addEventListener('input', update); $f(id).addEventListener('change', update); });
    function save() {
      var d = readDate();
      if (!d) { $f('e-date').textContent = '日付を入れてください。'; return; }
      var k = KINDS[st.kind], e = {
        id: uid(), title: titleNow(), date: C.iso(d), precision: st.p, kind: st.kind, quiet: !!k.quiet,
        yearly: st.p === 'day' && $f('f-yearly').checked, every100: st.p === 'day' && !k.quiet && $f('f-100').checked, alarm: $f('f-alarm').value, created: C.iso(TODAY)
      };
      S.entries.push(e); S.prefs.alarm = e.alarm === 'none' ? S.prefs.alarm : e.alarm;
      persist();
      location.href = '/my/?added=1';
    }
    if (P.kind && KINDS[P.kind]) setKind(P.kind);
    if (P.title) { $f('f-title').value = P.title; }
    var when = P.date && C.parse(P.date) ? C.parse(P.date) : whenToken(P.when);
    if (when) { if (!st.kind) setKind('memo'); $f('f-day').value = C.iso(when); }
    if (P.alarm && /^(morning|eve|week|none)$/.test(P.alarm)) $f('f-alarm').value = P.alarm;
    update();
  }

  /* ---------- category page (filter by sub-category) ---------- */
  function pageCategory() {
    var chips = $$('[data-cat-chip]'), cards = $$('#grid .card');
    chips.forEach(function (b) {
      b.addEventListener('click', function () {
        var c = b.getAttribute('data-cat-chip');
        chips.forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
        cards.forEach(function (card) { card.hidden = !!c && card.getAttribute('data-cat') !== c; });
      });
    });
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

  /* ---------- start ---------- */
  applyPrefs();
  hydrate(document);
  if (page === 'home') pageHome();
  else if (page === 'search') pageSearch();
  else if (page === 'my') pageMy();
  else if (page === 'add') pageAdd();
  else if (page === 'skins') pageSkins();
  else if (page === 'category') pageCategory();
  else if (page === 'today') pageToday();
  window.Atomou = { state: function () { return S; }, today: TODAY, tipFor: tipFor, nextLines: nextLines, whenToken: whenToken };
})();
