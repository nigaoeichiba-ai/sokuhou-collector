/* 速報: the headlines of official feeds (made every few minutes by sites/atomou/live.py and put at /live/live.v1.json) shown on the home page and on /topics/, the ones that
   match the visitor's own words (好きな分野・言葉) first.  The words never leave the device: the list comes to the page, and the page does the matching.
   With "好きな言葉の速報を知らせる" on (the interests page) and the browser's notification permission given, a new matching headline is announced while the site is open
   (a notice from the device itself; there is no push from a server for words).  The file is never needed: without it the block stays hidden.  A headline is a link to the official
   page, which is the one to trust; a day in a headline is read by a rule, so it says 自動検出. */
(function () {
  'use strict';
  var A = window.AtomouApp;
  if (!A) return;
  var $ = A.$, H = A.H, C = A.C, CONF = A.CONF, P = A.P;
  var home = $('#live-list'), topics = $('#live-list-t');
  var alertBox = $('#live-alert');

  /* ---------- 再確認中: the days the checking robot (sites/atomou/recheck.py) could not find on their official page any more ---------- */
  var RC_URL = (A.P.today && A.P.recheck && /^\/[\w./-]+$/.test(A.P.recheck)) ? A.P.recheck : '/live/recheck.v1.json', rc = null;
  function markRc() {
    if (!rc) return;
    A.$$('.card[data-key^="c:"]:not([data-rc])').forEach(function (card) {
      card.setAttribute('data-rc', '1');
      var id = (card.getAttribute('data-key') || '').slice(2);
      if (!rc[id]) return;
      var top = card.querySelector('.c-top');
      if (top) top.insertAdjacentHTML('beforeend', '<span class="badge warn">再確認中</span>');
      if (A.page === 'event' && card.classList.contains('big') && !$('.rc-note')) card.insertAdjacentHTML('beforebegin', '<p class="notice rc-note">出典のページで、この日付が見つかりませんでした。変わったかもしれません。出典の公式ページで確かめてください。</p>');
    });
  }
  if (A.page !== 'my' && A.page !== 'card' && A.page !== 'add' && A.page !== 'plan') {
    fetch(RC_URL, { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      if (!j || !Array.isArray(j.changed) || !j.changed.length) return;
      rc = {}; j.changed.forEach(function (i) { if (/^[0-9a-f]{10}$/.test(i)) rc[i] = 1; });
      markRc();
      var watch = $('#blocks') || $('main') || document.body;
      new MutationObserver(function () { clearTimeout(markRc.t); markRc.t = setTimeout(markRc, 80); }).observe(watch, { childList: true, subtree: true });
    }).catch(function () { /* no file: nothing is marked */ });
  }
  if (!home && !topics && !alertBox) return;
  var URL_ = (P.today && P.livesrc && /^\/[\w./-]+$/.test(P.livesrc)) ? P.livesrc : '/live/live.v1.json';   // tests: ?today=...&livesrc=/fixtures/live.json
  var SEEN_KEY = 'atomou.live.seen', items = [], timer = null;

  function norm(s) { return String(s || '').normalize('NFKC').toLowerCase().replace(/[ァ-ヶ]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 0x60); }).replace(/\s+/g, ' ').trim(); }
  function words() {   // what the visitor likes: fields and words (and nothing else); short ones would match everything
    var list = (P.today && P.words) ? P.words.split(',') : (A.state().interests || []);   // tests: ?today=...&words=ゲーム,日銀
    return list.map(function (w) { return { w: w, n: norm(w) }; }).filter(function (x) { return x.n.length >= 2; });
  }
  function matchOf(it, ws) {
    var hay = norm([it.t, it.s, it.g, it.m, it.k].join(' '));
    for (var i = 0; i < ws.length; i++) if (hay.indexOf(ws[i].n) >= 0) return ws[i].w;
    return '';
  }
  function ago(iso) {
    var t = Date.parse(iso), m = Math.max(0, Math.round((Date.now() - t) / 60000));
    if (!t) return '';
    return m < 2 ? 'いま' : m < 60 ? m + '分前' : m < 60 * 36 ? Math.round(m / 60) + '時間前' : Math.round(m / 1440) + '日前';
  }
  function dayText(d) {
    var p = C.parse(d);
    if (!p) return '';
    var n = C.totalDays(A.TODAY, p);
    return A.fmtDate(d, 'day') + (n > 0 ? '(あと' + n + '日)' : n === 0 ? '(今日)' : '');
  }
  function row(it, hit) {
    var g = CONF.groups.indexOf(it.g) + 1, safe = /^https:\/\//.test(it.u || '');
    if (!safe) return '';
    var add = it.d && C.parse(it.d) && C.totalDays(A.TODAY, C.parse(it.d)) >= 0 ? ' <a class="btn small ghost" href="/add/?kind=event&amp;title=' + encodeURIComponent(it.t.slice(0, 40)) + '&amp;date=' + it.d + '">予定に入れる</a>' : '';
    return '<li class="live-i' + (hit ? ' hit' : '') + '">' + (g ? '<span class="mark m' + g + '" data-g="' + g + '" aria-hidden="true"></span>' : '') +
      '<div class="live-b"><a class="live-t" href="' + H(it.u) + '" target="_blank" rel="noopener noreferrer nofollow">' + H(it.t) + '</a>' +
      '<p class="small muted">' + H(it.s) + ' ・ ' + H(ago(it.p)) + ' ・ 自動検出' + (it.d ? ' ・ 日付: ' + H(dayText(it.d)) : '') + (hit ? ' ・ <b>あなたの言葉: ' + H(hit) + '</b>' : '') + '</p>' + add + '</div></li>';
  }
  function draw() {
    var ws = words(), rows = items.map(function (it) { return { it: it, hit: matchOf(it, ws) }; });
    rows.sort(function (a, b) { return (b.hit ? 1 : 0) - (a.hit ? 1 : 0) || (a.it.p < b.it.p ? 1 : -1); });   // yours first, then the newest
    var box = $('#live');
    if (home) {
      var mine = S_genres(), pick = rows.filter(function (r) { return r.hit || !mine.length || mine.indexOf(r.it.g) >= 0; }).slice(0, 6);
      home.innerHTML = pick.map(function (r) { return row(r.it, r.hit); }).join('');
      if (box) box.hidden = !pick.length;
    }
    if (topics) {
      topics.innerHTML = rows.slice(0, 40).map(function (r) { return row(r.it, r.hit); }).join('');
      var sec = $('#live-t'); if (sec) sec.hidden = !rows.length;
    }
  }
  function S_genres() {   // the genres of the visitor's choice, whole or in part
    var p = A.state().prefs, out = (p.genres || []).slice();
    (p.mids || []).concat(p.subs || []).forEach(function (k) { var g = String(k).split('>')[0]; if (out.indexOf(g) < 0) out.push(g); });
    return out;
  }

  /* ---------- a new headline of the visitor's words, while the site is open ---------- */
  function seenList() { try { return JSON.parse(localStorage.getItem(SEEN_KEY) || 'null'); } catch (e) { return null; } }
  function saveSeen(ids) { try { localStorage.setItem(SEEN_KEY, JSON.stringify(ids.slice(0, 300))); } catch (e) { /* the notice is a nicety */ } }
  function announce() {
    var seen = seenList(), ids = items.map(function (i) { return i.id; });
    if (seen === null) { saveSeen(ids); return; }   // the first look: what is there is not "new"
    if (!A.state().prefs.liveAlert) { saveSeen(ids.concat(seen)); return; }
    var ws = words(), fresh = items.filter(function (i) { return seen.indexOf(i.id) < 0 && matchOf(i, ws); }).slice(0, 3);
    saveSeen(ids.concat(seen));
    fresh.forEach(function (i) {
      A.toast('あなたの言葉の速報: ' + i.t.slice(0, 40));
      try {
        if (window.Notification && Notification.permission === 'granted') {
          var opt = { body: i.s + ' ・ 公式ページで確かめてください', tag: 'live-' + i.id, data: { url: i.u } };
          if (navigator.serviceWorker && navigator.serviceWorker.ready) navigator.serviceWorker.ready.then(function (r) { r.showNotification(i.t.slice(0, 60), opt); });
          else new Notification(i.t.slice(0, 60), opt);
        }
      } catch (e) { /* nothing more to do */ }
    });
    if (fresh.length) A.stat('act:live_alert');
  }

  function load() {
    fetch(URL_, { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      if (!j || !Array.isArray(j.items)) return;
      items = j.items.filter(function (i) { return i && i.t && i.u && i.id; });
      draw(); announce();
    }).catch(function () { /* no live file: the block stays hidden */ });
  }
  function poll() {
    clearInterval(timer);
    if (document.visibilityState === 'visible') timer = setInterval(load, 5 * 60 * 1000);
  }
  document.addEventListener('visibilitychange', function () { poll(); if (document.visibilityState === 'visible') load(); });

  /* ---------- the switch on the interests page ---------- */
  if (alertBox) {
    var cb = $('#live-alert-cb');
    if (cb) {
      cb.checked = !!A.state().prefs.liveAlert;
      cb.addEventListener('change', function () {
        var S = A.state(); S.prefs.liveAlert = cb.checked; A.persist(); A.stat('act:live_alert_' + (cb.checked ? 'on' : 'off'));
        if (cb.checked && window.Notification && Notification.permission === 'default') { try { Notification.requestPermission(); } catch (e) { /* the browser decides */ } }
        var note = $('#live-alert-note');
        if (note) note.textContent = cb.checked ? (window.Notification && Notification.permission === 'denied' ? 'ブラウザの通知が許可されていないので、画面の中のお知らせだけになります。' : 'オンにしました。') : 'オフにしました。';
      });
    }
  }
  if (home || topics) { load(); poll(); }
  A.live = { draw: draw, count: function () { return items.length; } };
})();
