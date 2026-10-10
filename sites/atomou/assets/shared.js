/* Shared cards that stay up to date (the card page /card/ and the list on the my page).
   A card is written in the browser, locked with a random key (AES-GCM) and only the locked text goes to the server (api/s.php).  The key is in the part of the link after "#":
   a browser never sends that part to a server, so the server cannot read a card.  Whoever has the link can read the card; whoever has the editor's link (the same, with a third part)
   can change it.  A change is a new version of the same card: the people who follow it are told, when they open the site and every few minutes while it is open.
   The links:  /card/#s=<id>.<key>          to read (and to follow)
               /card/#s=<id>.<key>.<edit>   to read and to change
   What this device keeps (localStorage "atomou.shared"): for each card followed or made: its id, key, edit part, the version seen, the title and the day (so that the list works without the network). */
(function () {
  'use strict';
  var A = window.AtomouApp;
  if (!A) return;
  var $ = A.$, H = A.H, C = A.C;
  var KEY = 'atomou.shared', API = '/api/s.php', MAX_FOLLOW = 30, timer = null, fixture = (A.P.today && A.P.sharedapi && /^\/[\w./-]+$/.test(A.P.sharedapi)) ? A.P.sharedapi : '';

  /* ---------- bytes and text ---------- */
  function b64u(bytes) { var s = ''; for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]); return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''); }
  function unb64u(s) { s = String(s).replace(/-/g, '+').replace(/_/g, '/'); while (s.length % 4) s += '='; var bin = atob(s), out = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i); return out; }
  function rand(n) { var b = new Uint8Array(n); crypto.getRandomValues(b); return b; }
  function supported() { return !!(window.crypto && crypto.subtle && window.TextEncoder && window.fetch); }
  function aes(keyB64, usage) { return crypto.subtle.importKey('raw', unb64u(keyB64), { name: 'AES-GCM' }, false, [usage]); }
  function lock(keyB64, obj) {   // -> base64url of iv(12) + ciphertext
    var iv = rand(12);
    return aes(keyB64, 'encrypt').then(function (k) { return crypto.subtle.encrypt({ name: 'AES-GCM', iv: iv }, k, new TextEncoder().encode(JSON.stringify(obj))); }).then(function (ct) {
      var all = new Uint8Array(12 + ct.byteLength); all.set(iv, 0); all.set(new Uint8Array(ct), 12); return b64u(all);
    });
  }
  function unlock(keyB64, text) {
    var all = unb64u(text);
    return aes(keyB64, 'decrypt').then(function (k) { return crypto.subtle.decrypt({ name: 'AES-GCM', iv: all.slice(0, 12) }, k, all.slice(12)); }).then(function (pt) { return JSON.parse(new TextDecoder().decode(pt)); });
  }
  function sha256hex(s) {
    return crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)).then(function (h) { var a = new Uint8Array(h), o = ''; for (var i = 0; i < a.length; i++) o += (a[i] < 16 ? '0' : '') + a[i].toString(16); return o; });
  }

  /* ---------- the server ---------- */
  /* tests and screenshots (?today=...&sharedapi=mem): a stand-in server kept in this browser's localStorage, with the same answers as api/s.php */
  function memServer(d) {
    var KEY_ = 'atomou.mem.shared', db; try { db = JSON.parse(localStorage.getItem(KEY_) || '{}'); } catch (e) { db = {}; }
    function done(status, data) { try { localStorage.setItem(KEY_, JSON.stringify(db)); } catch (e) { /* the stand-in only */ } return { status: status, data: data }; }
    if (d.a === 'peek') { return done(200, { ok: true, changed: (d.items || []).map(function (it) { var c = db[it.id]; return !c ? { id: it.id, gone: true } : c.ver !== it.ver ? { id: it.id, ver: c.ver, upd: c.upd } : null; }).filter(Boolean) }); }
    var c = db[d.id], now = Math.floor(Date.now() / 1000);
    if (d.a === 'create') { if (c) return done(409, { error: 'exists' }); db[d.id] = { eh: d.eh, ct: d.ct, ver: 1, upd: now, rep: [] }; return done(200, { ok: true, ver: 1, upd: now }); }
    if (!c) return done(404, { error: 'none' });
    if (d.a === 'get') return c.blocked ? done(410, { error: 'blocked' }) : done(200, { ok: true, ver: c.ver, ct: c.ct, upd: c.upd });
    if (d.a === 'report') { c.rep.push('r' + c.rep.length); if (c.rep.length >= 3) c.blocked = true; return done(200, { ok: true }); }
    return sha256hex(d.e || '').then(function (h) {
      if (h !== c.eh) return done(403, { error: 'editor' });
      if (d.a === 'delete') { delete db[d.id]; return done(200, { ok: true }); }
      if (d.base !== c.ver) return done(409, { error: 'conflict', ver: c.ver, ct: c.ct, upd: c.upd });
      c.ct = d.ct; c.ver++; c.upd = now; return done(200, { ok: true, ver: c.ver, upd: c.upd });
    });
  }
  function call(body) {
    if (A.P.today && A.P.sharedapi === 'mem') return Promise.resolve(memServer(Object.assign({ v: 1 }, body)));
    var url = fixture || API;
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: JSON.stringify(Object.assign({ v: 1 }, body)), cache: 'no-store' }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) { return { status: r.status, data: j || {} }; });
    });
  }

  /* ---------- what this device keeps ---------- */
  function list() { try { var l = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(l) ? l.filter(ok) : []; } catch (e) { return []; } }
  function ok(x) { return x && /^[A-Za-z0-9_-]{22}$/.test(x.id) && /^[A-Za-z0-9_-]{43}$/.test(x.k) && (!x.e || /^[A-Za-z0-9_-]{20,64}$/.test(x.e)); }
  function save(l) { try { localStorage.setItem(KEY, JSON.stringify(l.slice(0, MAX_FOLLOW))); } catch (e) { /* the list is a nicety; the link is the card */ } }
  function find(id) { return list().filter(function (x) { return x.id === id; })[0] || null; }
  function put(entry) {
    var l = list().filter(function (x) { return x.id !== entry.id; });
    var old = find(entry.id);
    l.unshift(Object.assign({}, old || {}, entry));
    save(l);
  }
  function drop(id) { save(list().filter(function (x) { return x.id !== id; })); }
  function parseRef(h) {
    var m = /[#&]s=([A-Za-z0-9_-]{22})\.([A-Za-z0-9_-]{43})(?:\.([A-Za-z0-9_-]{20,64}))?/.exec(h || '');
    return m ? { id: m[1], k: m[2], e: m[3] || '' } : null;
  }
  function linkOf(x, withEdit) { return location.origin + '/card/#s=' + x.id + '.' + x.k + (withEdit && x.e ? '.' + x.e : ''); }

  /* ---------- make, read, change, delete, report ---------- */
  function create(cardObj) {   // -> {id, k, e, ver}
    var id = b64u(rand(16)), k = b64u(rand(32)), e = b64u(rand(24));
    return Promise.all([lock(k, cardObj), sha256hex(e)]).then(function (r) { return call({ a: 'create', id: id, eh: r[1], ct: r[0] }); }).then(function (res) {
      if (res.status === 429) throw new Error('limit');
      if (!res.data.ok) throw new Error(res.data.error || 'create');
      var x = { id: id, k: k, e: e, ver: res.data.ver, seen: res.data.ver, upd: res.data.upd, t: cardObj.t, d: cardObj.d, mine: true };
      put(x); A.stat('act:shared_make');
      return x;
    });
  }
  function read(ref) {   // -> {card, ver, upd}
    return call({ a: 'get', id: ref.id }).then(function (res) {
      if (res.status === 404) throw new Error('none');
      if (res.status === 410) throw new Error('blocked');
      if (!res.data.ok) throw new Error(res.data.error || 'get');
      return unlock(ref.k, res.data.ct).then(function (card) { return { card: card, ver: res.data.ver, upd: res.data.upd }; }, function () { throw new Error('key'); });
    });
  }
  function update(x, cardObj) {   // x has the edit part
    return lock(x.k, cardObj).then(function (ct) { return call({ a: 'update', id: x.id, e: x.e, base: x.ver, ct: ct }); }).then(function (res) {
      if (res.status === 409) { var err = new Error('conflict'); err.newest = res.data; throw err; }
      if (!res.data.ok) throw new Error(res.data.error || 'update');
      put({ id: x.id, ver: res.data.ver, seen: res.data.ver, upd: res.data.upd, t: cardObj.t, d: cardObj.d }); A.stat('act:shared_update');
      return res.data;
    });
  }
  function remove(x) { return call({ a: 'delete', id: x.id, e: x.e }).then(function (res) { if (res.data.ok) drop(x.id); return !!res.data.ok; }); }
  function report(id) { return call({ a: 'report', id: id }).then(function (res) { return !!res.data.ok; }); }

  /* ---------- following: what changed since I looked ---------- */
  function follow(ref, info) {
    var l = list();
    if (!find(ref.id) && l.length >= MAX_FOLLOW) { A.toast('フォローできる共有カードは' + MAX_FOLLOW + '枚までです。'); return false; }
    put({ id: ref.id, k: ref.k, e: ref.e || (find(ref.id) || {}).e || '', ver: info.ver, seen: info.ver, upd: info.upd, t: info.card.t, d: info.card.d, follow: true });
    A.stat('act:shared_follow');
    return true;
  }
  function unfollow(id) { var x = find(id); if (x && x.mine) put({ id: id, follow: false }); else drop(id); }
  function check() {   // one request for all; the ones with a newer version are read, shown and noted
    var l = list().filter(function (x) { return x.follow !== false; });
    if (!l.length || !supported()) return Promise.resolve([]);
    return call({ a: 'peek', items: l.map(function (x) { return { id: x.id, ver: x.seen || x.ver || 0 }; }) }).then(function (res) {
      var ch = (res.data && res.data.changed) || [];
      return Promise.all(ch.map(function (c) {
        var x = find(c.id);
        if (!x) return null;
        if (c.gone) { put({ id: c.id, gone: true }); return { id: c.id, gone: true, t: x.t }; }
        return read(x).then(function (r) {
          put({ id: c.id, ver: r.ver, upd: r.upd, t: r.card.t, d: r.card.d, changed: true });
          return { id: c.id, t: r.card.t, d: r.card.d };
        }, function () { return null; });
      })).then(function (arr) { return arr.filter(Boolean); });
    }).catch(function () { return []; });
  }
  function seen(id, ver) { put({ id: id, seen: ver, ver: ver, changed: false }); }

  /* ---------- the notice (while the site is open) ---------- */
  function announce(changed) {
    changed.forEach(function (c) {
      if (c.gone) return;
      A.toast('共有カードが更新されました: ' + (c.t || '(題名なし)').slice(0, 30));
      try {
        if (window.Notification && Notification.permission === 'granted' && A.state().prefs.sharedAlert !== false) {
          var opt = { body: '共有カードが更新されました', tag: 'shared-' + c.id, data: { url: '/card/#s=' + (find(c.id) ? find(c.id).id + '.' + find(c.id).k : '') } };
          if (navigator.serviceWorker && navigator.serviceWorker.ready) navigator.serviceWorker.ready.then(function (r) { r.showNotification((c.t || 'カード').slice(0, 60), opt); });
        }
      } catch (e) { /* a nicety */ }
    });
    if (changed.length) { A.stat('act:shared_changed'); renderList(); document.dispatchEvent(new CustomEvent('atomou:shared', { detail: changed })); }
  }
  function poll() {
    clearInterval(timer);
    if (document.visibilityState !== 'visible' || !list().length) return;
    timer = setInterval(function () { check().then(announce); }, 5 * 60 * 1000);
  }

  /* ---------- the list on the my page ---------- */
  function renderList() {
    var box = $('#shared-box');
    if (!box) return;
    var l = list().filter(function (x) { return x.follow !== false || x.mine; });
    box.hidden = !l.length;
    if (!l.length) { box.innerHTML = ''; return; }
    box.innerHTML = '<h2>共有カード</h2><p class="hint">リンクで共有している、更新が届くカードです。更新があると「更新あり」と出ます。</p><ul class="plist">' + l.map(function (x) {
      var n = x.d && C.parse(x.d) ? C.totalDays(A.TODAY, C.parse(x.d)) : null;
      return '<li><a href="' + H(linkOf(x, true)) + '"><b>' + H(x.t || '(題名なし)') + '</b></a>' + (n != null ? ' <span class="muted">' + H(n > 0 ? 'あと' + n + '日' : n === 0 ? '今日' : 'もう' + (-n) + '日') + '</span>' : '') +
        (x.changed ? ' <span class="badge">更新あり</span>' : '') + (x.gone ? ' <span class="muted">(削除されたか、期限切れです)</span>' : '') + (x.mine ? ' <span class="muted">(自分で作った)</span>' : '') + '</li>';
    }).join('') + '</ul>';
  }

  A.shared = { supported: supported, list: list, find: find, put: put, drop: drop, parseRef: parseRef, linkOf: linkOf, create: create, read: read, update: update, remove: remove, report: report,
    follow: follow, unfollow: unfollow, check: check, seen: seen, renderList: renderList, sha256hex: sha256hex, lock: lock, unlock: unlock };

  document.addEventListener('visibilitychange', function () { poll(); if (document.visibilityState === 'visible' && list().length) check().then(announce); });
  if (A.page !== 'card') { renderList(); }
  if (list().length && supported() && A.page !== 'card') { check().then(announce); }
  poll();
})();
