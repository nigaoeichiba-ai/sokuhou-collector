/* あと何日、もう何日: push notifications ("the site tells you").
   The server (api/push.php) gets only the subscription and the DAYS on which to knock; the text of every reminder stays on the device:
   this file writes a small mirror {"YYYY-MM-DD|slot": [{t: text, u: url}]} into the Cache API, and sw.js reads it when a push arrives.
   Slots: m = morning, e = the evening before.  The "alarm" setting (morning / eve / week / none) decides which day and slot. */
(function () {
  'use strict';
  var A = window.AtomouApp;
  if (!A) return;
  var C = A.C, S = A.state, $ = A.$, P = A.P, TODAY = A.TODAY, CONF = A.CONF;
  var KEY = CONF.vapid || '', WINDOW = 400, API = '/api/push.php', MIRROR = '/_notice', CACHE = 'atomou-notice';
  var SLOT = { morning: { off: 0, s: 'm', pre: '' }, eve: { off: -1, s: 'e', pre: '明日 ' }, week: { off: -7, s: 'm', pre: '1週間後 ' } };

  function supported() {
    return !!KEY && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window && (location.protocol === 'https:' || location.hostname === 'localhost');
  }
  function iosNeedsHomeScreen() {
    var ua = navigator.userAgent || '';
    return /iP(hone|ad|od)/.test(ua) && !window.navigator.standalone && !(window.matchMedia && window.matchMedia('(display-mode: standalone)').matches);
  }
  function key(d, s) { return C.iso(d) + '|' + s; }

  /* ---------- which days to knock on, and what to say then (computed on the device) ---------- */
  function plan(cat, today) {
    today = today || TODAY;
    var Pl = window.AtomouPlan, st = S(), items = Pl.planItems(cat), dates = {}, mirror = {}, last = C.addDays(today, WINDOW);
    function add(d, s, text, url) {
      if (C.cmp(d, today) < 0 || C.cmp(d, last) > 0) return;
      var k = key(d, s);
      dates[k] = { d: C.iso(d), s: s };
      (mirror[k] = mirror[k] || []).push({ t: text, u: url });
    }
    items.forEach(function (it) {
      var d0 = C.parse(it.date);
      if (!d0 || it.p !== 'day') return;
      var e = it.own ? A.findEntry(it.id) : null, alarm = it.own ? (e ? (e.alarm || st.prefs.alarm) : 'none') : st.prefs.alarm, slot = SLOT[alarm];
      var url = '/plan/?key=' + encodeURIComponent(it.key), turns = [], y;
      if (it.yearly) { for (y = Math.max(today[0], d0[0]); y <= last[0] + 1; y++) turns.push(A.occ(d0, y)); } else turns.push(d0);   // a yearly day comes round twice within 400 days
      turns.forEach(function (base) {
        if (slot) add(C.addDays(base, slot.off), slot.s, slot.pre + it.title + (it.time ? ' ' + it.time : ''), url);
        Pl.notesOf(it.key).tasks.forEach(function (t) {
          if (t.done) return;
          add(C.addDays(base, -t.before), 'm', 'やること: ' + t.text + '(' + it.title + ')', url);
        });
      });
      if (slot && it.own && it.every100 && !it.quiet) {   // the 100-day marks
        for (var n = 100; C.cmp(C.addDays(d0, n + slot.off), last) <= 0; n += 100) add(C.addDays(d0, n + slot.off), slot.s, slot.pre + it.title + ' から' + n + '日', url);
      }
    });
    if (window.AtomouMember && window.AtomouMember.extraNotices) window.AtomouMember.extraNotices(today).forEach(function (x) { add(x.d, x.s, x.t, x.u); });   // a monitor's questionnaire reminder
    var list = Object.keys(dates).sort().map(function (k) { return dates[k]; });
    return { dates: list, mirror: mirror, hash: list.map(function (x) { return x.d + x.s; }).join(',') };
  }

  function writeMirror(mirror) {
    if (!('caches' in window)) return Promise.resolve();
    return caches.open(CACHE).then(function (c) { return c.put(new Request(MIRROR), new Response(JSON.stringify(mirror), { headers: { 'Content-Type': 'application/json' } })); }).catch(function () { /* the push still arrives; it just says less */ });
  }
  function post(body) {
    return fetch(API, { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: JSON.stringify(body), keepalive: true }).then(function (r) { return r.status === 204 || r.ok; });
  }
  function b64ToBytes(s) {
    var pad = '='.repeat((4 - s.length % 4) % 4), raw = atob((s + pad).replace(/-/g, '+').replace(/_/g, '/')), out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }
  function current() {
    if (!supported()) return Promise.resolve(null);
    return navigator.serviceWorker.ready.then(function (reg) { return reg.pushManager.getSubscription(); }).catch(function () { return null; });
  }

  /* ---------- keep the server's day list equal to the device's ---------- */
  var syncing = false;
  function sync(force) {
    var st = S();
    if (!st.prefs.push || syncing) return Promise.resolve(false);
    syncing = true;
    return current().then(function (sub) {
      if (!sub) { syncing = false; return false; }
      return A.loadCatalog().then(function (cat) {
        var p = plan(cat || []);
        return writeMirror(p.mirror).then(function () {
          if (!force && p.hash === st.prefs.pushHash) return true;
          return post({ v: 1, sub: sub.toJSON(), dates: p.dates }).then(function (ok) {
            if (ok) { st.prefs.pushHash = p.hash; A.persist(); }
            return ok;
          });
        });
      });
    }).catch(function () { return false; }).then(function (r) { syncing = false; return r; });
  }

  function subscribe() {
    return navigator.serviceWorker.ready.then(function (reg) {
      return reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(KEY) });
    }).then(function (sub) {
      var st = S();
      st.prefs.push = true; st.prefs.pushHash = ''; A.persist();
      A.stat('act:push_on');
      return sync(true).then(function (ok) { return ok ? sub : Promise.reject(new Error('server')); });
    });
  }
  function unsubscribe() {
    return current().then(function (sub) {
      var st = S();
      st.prefs.push = false; st.prefs.pushHash = ''; A.persist();
      A.stat('act:push_off');
      if (!sub) return true;
      var ep = sub.endpoint;
      return sub.unsubscribe().catch(function () { return true; }).then(function () { return post({ v: 1, endpoint: ep, off: true }).catch(function () { return false; }); });
    });
  }

  /* ---------- the box on the my page ---------- */
  function pageMy() {
    var box = $('#push-box');
    if (!box) return;
    var status = $('#push-status'), on = $('#push-on'), off = $('#push-off'), ios = $('#push-ios');
    if (!supported()) {
      box.hidden = false;
      status.textContent = KEY ? 'このブラウザは通知に対応していません。' : '通知は準備中です。';
      on.hidden = off.hidden = true;
      if (iosNeedsHomeScreen() && KEY) { ios.hidden = false; status.textContent = 'iPhone では、ホーム画面に追加し、そのアイコンから開くと通知を使えます。'; }
      return;
    }
    box.hidden = false;
    function show(sub) {
      var granted = Notification.permission === 'granted' && !!sub && S().prefs.push;
      on.hidden = granted; off.hidden = !granted;
      status.textContent = granted ? 'この端末に届きます。' : (Notification.permission === 'denied' ? 'ブラウザの設定で通知が止まっています。サイトの設定で許可してください。' : '通知はオフです。');
      ios.hidden = !(iosNeedsHomeScreen() && !granted);
    }
    current().then(show);
    offerInstall(box);
    on.addEventListener('click', function () {
      on.disabled = true;
      subscribe().then(function (sub) { A.toast('この端末で通知を受け取ります。'); show(sub); })
        .catch(function () { A.toast(Notification.permission === 'denied' ? '通知が許可されませんでした。' : '通知を始められませんでした。しばらくして、もう一度お試しください。'); show(null); })
        .then(function () { on.disabled = false; });
    });
    off.addEventListener('click', function () {
      off.disabled = true;
      unsubscribe().then(function () { A.toast('通知を止めました。'); show(null); off.disabled = false; });
    });
    $('#p-alarm').addEventListener('change', function () { S().prefs.pushHash = ''; sync(true); });
  }

  /* ---------- "add to the home screen" where the browser offers it (Chrome on Android, desktop Chrome/Edge); iPhone has no such button, hence the written steps ---------- */
  var deferredInstall = null;
  window.addEventListener('beforeinstallprompt', function (ev) { ev.preventDefault(); deferredInstall = ev; document.dispatchEvent(new Event('atomou:installable')); });
  window.addEventListener('appinstalled', function () { deferredInstall = null; A.stat('act:installed'); });
  function offerInstall(host) {
    function put() {
      if (!deferredInstall || host.querySelector('[data-install]')) return;
      var p = document.createElement('p');
      p.innerHTML = '<button type="button" class="btn ghost" data-install>ホーム画面に追加する</button>';
      host.appendChild(p);
      p.querySelector('button').addEventListener('click', function () {
        var d = deferredInstall; deferredInstall = null;
        if (!d) return;
        A.stat('act:install_ask');
        d.prompt();
        if (d.userChoice) d.userChoice.then(function (c) { if (c && c.outcome === 'accepted') p.remove(); else put(); }, function () { /* ignore */ });
      });
    }
    put();
    document.addEventListener('atomou:installable', put);
  }

  /* ---------- right after a day was recorded: the two things that make the day "kept" (plan page, ?new=1) ---------- */
  function afterSave(plan, quiet) {
    var H = A.H, h = '';
    if (iosNeedsHomeScreen()) {   // Safari removes what a site stored after about a week of Safari use without a visit; an icon on the home screen is exempt
      h = '<p>iPhone の Safari では、しばらくこのサイトを使わないと、保存した日が消えることがあります。</p>' +
        '<p>共有ボタンから「ホーム画面に追加」し、そのアイコンから開くと、消えにくくなります。通知も、そのアイコンから開くと使えます。</p>' +
        '<p>念のため、<a href="/my/#backup-h">バックアップ</a>で書き出しておくと安心です。</p>';
    } else if (supported() && !quiet && Notification.permission === 'default' && !S().prefs.push) {
      h = '<p>決めた日に、この端末へ通知します。時間はマイページで変えられます。</p>' +
        '<p><button type="button" class="btn" id="as-push">この端末に通知を届ける</button></p><p class="hint" id="as-msg" role="status"></p>';
    }
    if (!h && !deferredInstall) {   // nothing to say yet: the browser may still announce that the page can be installed
      document.addEventListener('atomou:installable', function again() { document.removeEventListener('atomou:installable', again); afterSave(plan, quiet); });
      return;
    }
    var el = document.createElement('section');
    el.className = 'panel after-save';
    el.id = 'after-save';
    el.innerHTML = '<h2>' + (iosNeedsHomeScreen() ? 'この日を忘れないために' : h ? 'この日を、お知らせしますか' : 'この日を、すぐ開けるように') + '</h2>' + (h || '<p>ホーム画面に追加すると、アプリのように開けます。</p>');
    plan.insertAdjacentElement('beforebegin', el);   // above the day's card: the first screen after saving, not below the memo
    offerInstall(el);
    var b = el.querySelector('#as-push');
    if (b) b.addEventListener('click', function () {
      b.disabled = true;
      subscribe().then(function () { el.querySelector('#as-msg').textContent = 'この端末に届きます。'; b.hidden = true; A.toast('この端末で通知を受け取ります。'); })
        .catch(function () { el.querySelector('#as-msg').textContent = Notification.permission === 'denied' ? '通知が許可されませんでした。' : '通知を始められませんでした。マイページから、もう一度お試しください。'; b.disabled = false; });
    });
  }

  // ask the browser to keep the saved days (Chrome and Safari answer without a dialog; Firefox would ask, so it is not asked there)
  if (!/Firefox\//.test(navigator.userAgent || '') && navigator.storage && navigator.storage.persist && S().entries && S().entries.length) {
    try { navigator.storage.persist().catch(function () { /* ignore */ }); } catch (e) { /* ignore */ }
  }

  if (A.page === 'my') pageMy();
  document.addEventListener('atomou:changed', function () { sync(false); });
  document.addEventListener('atomou:saved', function () { sync(false); });   // any saved change (a fixed date, a deleted day, a new task) reaches the server's list
  if (!P.today) setTimeout(function () { sync(false); }, 1500);   // after a change made on another page (or on another device), the server's list follows
  window.AtomouPush = { plan: plan, sync: sync, supported: supported, afterSave: afterSave, SLOT: SLOT };
})();
