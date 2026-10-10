/* The shareable card (/card/).
   A card is a day with a name, a note and a few "do this N days before" items, written by the visitor and sent as a LINK.  Everything it says is inside the link after the "#"
   (a browser never sends that part to a server): the person who opens the link sees the card with today's count, and can put it into their own planner with one tap, add it to
   Google Calendar / Outlook, save it as a picture, or change it and send their own version.  Nothing is stored on our server.
   The words on a card were written by whoever made the link; this site does not check them (the card says so), and a card cannot hold an address or a picture of someone else's. */
(function () {
  'use strict';
  var A = window.AtomouApp;
  if (!A || A.page !== 'card') return;
  var C = A.C, H = A.H, $ = A.$, $$ = A.$$, TODAY = A.TODAY, KINDS = A.KINDS;

  var THEMES = [
    { n: '白', bg: '#FFFFFF', fg: '#1A1A1A', ac: '#1A56B8' }, { n: '青', bg: '#1A56B8', fg: '#FFFFFF', ac: '#FFE08A' }, { n: '赤', bg: '#B91C3C', fg: '#FFFFFF', ac: '#FFE08A' },
    { n: '緑', bg: '#0B6B3A', fg: '#FFFFFF', ac: '#D7F5A8' }, { n: '紫', bg: '#5B21B6', fg: '#FFFFFF', ac: '#FFD6F0' }, { n: '黒', bg: '#14181F', fg: '#F2F2F2', ac: '#7DBBFF' }, { n: '付箋', bg: '#FFF1A8', fg: '#3F3500', ac: '#B45309', sticky: true },
    { n: '黄', bg: '#FFE600', fg: '#1A1A1A', ac: '#B00020' }, { n: 'ピンク', bg: '#FFE4EC', fg: '#4A1F2E', ac: '#C2185B' }, { n: '紺', bg: '#0E2A55', fg: '#EAF1FF', ac: '#FFB26B' }, { n: '生成り', bg: '#F5EFE3', fg: '#3B3224', ac: '#A0431C' }
  ];
  var KIND_OK = ['event', 'anniversary', 'birthday', 'since', 'until', 'memo'];   // no memorial: such a day is never turned into a card to send
  var MAX = { t: 40, m: 200, task: 60, tasks: 8 };

  /* ---------- starting points: what a card is often for ---------- */
  var TEMPLATES = [
    { id: 'live', n: 'ライブ・イベントの告知', t: '〇〇 ワンマンライブ', m: '開場・開演・会場・チケットのことを書く', k: 'until', th: 5, days: 45, tasks: [{ b: 30, x: 'チケットを確かめる' }, { b: 7, x: '持ち物を確かめる' }, { b: 1, x: '行き方を確かめる' }] },
    { id: 'friend', n: '友だちとの約束', t: '〇〇とごはん', tm: '12:00', m: '集合場所・お店のことを書く', k: 'event', th: 7, days: 7, tasks: [{ b: 1, x: '集合場所を確かめる' }] },
    { id: 'work', n: '取引先との打ち合わせ', t: '〇〇の打ち合わせ', tm: '10:00', m: '場所(または会議のURL以外の目印)・資料のことを書く', k: 'event', th: 8, days: 7, tasks: [{ b: 3, x: '資料を送る' }, { b: 1, x: '話すことを確かめる' }] },
    { id: 'shop', n: '今日の買い物', t: '今日の買い物', tm: '17:00', m: '行く店・予算のことを書く', k: 'event', th: 3, days: 0, tasks: [{ b: 0, x: '牛乳' }, { b: 0, x: '卵' }, { b: 0, x: 'パン' }] },
    { id: 'deadline', n: '提出の締切', t: '〇〇の提出', m: '提出先・必要なものを書く', k: 'until', th: 2, days: 14, tasks: [{ b: 7, x: '書類をそろえる' }, { b: 1, x: '最後に見直す' }] },
    { id: 'trip', n: '旅行の準備', t: '〇〇旅行', m: '行き先・集合のことを書く', k: 'until', th: 1, days: 60, tasks: [{ b: 30, x: '宿と交通を予約する' }, { b: 7, x: '持ち物を確かめる' }, { b: 1, x: '荷造りをする' }] }
  ];

  /* ---------- the link ---------- */
  function b64enc(s) {
    var bytes = new TextEncoder().encode(s), bin = '';
    for (var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }
  function b64dec(s) {
    s = s.replace(/-/g, '+').replace(/_/g, '/'); while (s.length % 4) s += '=';
    var bin = atob(s), bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder().decode(bytes);
  }
  function clean(o) {   // whatever came in a link is reduced to known shapes
    if (!o || typeof o !== 'object') return null;
    var d = C.parse(String(o.d || ''));
    if (!d) return null;
    var tasks = (Array.isArray(o.tasks) ? o.tasks : []).slice(0, MAX.tasks).map(function (t) {
      var b = Math.floor(+(t && t.b)), x = String(t && t.x != null ? t.x : '').replace(/[\u0000-\u001f<>]/g, '').trim().slice(0, MAX.task);
      return x && b >= 0 && b <= 365 ? { b: b, x: x } : null;
    }).filter(Boolean);
    return {
      t: String(o.t == null ? '' : o.t).replace(/[\u0000-\u001f<>]/g, '').trim().slice(0, MAX.t), d: C.iso(d),
      tm: /^([01]\d|2[0-3]):[0-5]\d$/.test(String(o.tm)) ? o.tm : '', m: String(o.m == null ? '' : o.m).replace(/[\u0000-\u0008<>]/g, '').trim().slice(0, MAX.m),
      th: Math.max(0, Math.min(THEMES.length - 1, Math.floor(+o.th) || 0)), tasks: tasks,
      e: /^[0-9a-f]{10}$/.test(String(o.e)) ? o.e : '', k: KIND_OK.indexOf(o.k) >= 0 ? o.k : 'event'
    };
  }
  function pack(card) { return b64enc(JSON.stringify(card)); }
  function fromHash() {
    var m = /[#&]c=([A-Za-z0-9_-]+)/.exec(location.hash || '');
    if (!m) return null;
    try { return clean(JSON.parse(b64dec(m[1]))); } catch (e) { return null; }
  }
  function linkOf(card) { return linked && A.shared ? A.shared.linkOf(linked, false) : location.origin + '/card/#c=' + pack(card); }

  /* ---------- reading the day ---------- */
  function count(card) {
    var d = C.parse(card.d), n = C.totalDays(TODAY, d);
    return { n: n, big: n > 0 ? 'あと' + n + '日' : n === 0 ? '今日' : 'もう' + (-n) + '日' };
  }
  function when(card) { var d = C.parse(card.d); return A.fmtDate(card.d, 'day') + (card.tm ? ' ' + card.tm : ''); }
  function words(card) {
    var c = count(card), name = card.t ? '「' + card.t + '」' : 'この日';
    return c.n > 0 ? name + 'まで、あと' + c.n + '日(' + when(card) + ')。' : c.n === 0 ? name + 'は今日です。' : name + 'から、もう' + (-c.n) + '日。';
  }

  /* ---------- drawing the card on the page ---------- */
  function cardHtml(card) {
    var th = THEMES[card.th], c = count(card), tasks = card.tasks.slice().sort(function (a, b) { return b.b - a.b; });
    var h = '<div class="xcard' + (th.sticky ? ' xsticky' : '') + '" style="--xbg:' + th.bg + ';--xfg:' + th.fg + ';--xac:' + th.ac + '">' +
      '<div class="x-top">あと何日、もう何日</div><h2 class="x-title">' + H(card.t || '(題名なし)') + '</h2>' +
      '<div class="x-big">' + H(c.big) + '</div><div class="x-date">' + H(when(card)) + '</div>';
    if (card.m) h += '<p class="x-note">' + H(card.m).replace(/\n/g, '<br>') + '</p>';
    if (tasks.length) {
      h += '<ul class="x-tasks">' + tasks.map(function (t) {
        var due = C.addDays(C.parse(card.d), -t.b), left = C.totalDays(TODAY, due);
        return '<li><span>' + (t.b ? t.b + '日前' : '当日') + '(' + due[1] + '/' + due[2] + ')</span> ' + H(t.x) + (left < 0 ? ' <i>済み</i>' : '') + '</li>';
      }).join('') + '</ul>';
    }
    return h + '<div class="x-foot">atomou.com</div></div>';
  }

  /* ---------- the picture (1200x630 for chat and X, 1080x1080 for Instagram, 1080x1920 for stories and shorts) ---------- */
  var SIZES = { wide: [1200, 630], square: [1080, 1080], story: [1080, 1920] };
  function signed() { return !(A.tier && A.tier.on && A.tier.plus() && A.state().prefs.noSign); }   // plus may send a picture or words without the site's name and link
  function drawCard(card, size) {
    var wh = SIZES[size] || SIZES.wide, W = wh[0], Hh = wh[1], cv = document.createElement('canvas'), g = cv.getContext('2d'), th = THEMES[card.th], c = count(card);
    var font = getComputedStyle(document.body).fontFamily || 'sans-serif', k = W / 1200, pad = Math.round(70 * k), story = size === 'story';
    cv.width = W; cv.height = Hh;
    g.fillStyle = th.bg; g.fillRect(0, 0, W, Hh);
    g.fillStyle = th.ac; g.fillRect(0, 0, W, Math.round(16 * k));
    g.textBaseline = 'alphabetic'; g.fillStyle = th.fg; if (signed()) { g.globalAlpha = .7; g.font = '700 ' + Math.round(34 * k) + 'px ' + font; g.fillText('あと何日、もう何日', pad, Math.round(100 * k)); } g.globalAlpha = 1;
    function wrap(text, fontPx, maxW, rows) {
      g.font = '800 ' + fontPx + 'px ' + font;
      var lines = [], cur = '', i, ch;
      for (i = 0; i < text.length; i++) { ch = text.charAt(i); if (g.measureText(cur + ch).width > maxW && cur) { lines.push(cur); cur = ch; } else cur += ch; }
      if (cur) lines.push(cur);
      if (lines.length > rows) { lines = lines.slice(0, rows); lines[rows - 1] = lines[rows - 1].slice(0, -1) + '…'; }
      return lines;
    }
    var y = Math.round((story ? 560 : 200) * k), tp = Math.round((story ? 84 : 60) * k);
    g.fillStyle = th.fg;
    wrap(card.t || '', tp, W - 2 * pad, story ? 4 : 3).forEach(function (ln) { g.font = '800 ' + tp + 'px ' + font; g.fillText(ln, pad, y); y += Math.round(tp * 1.3); });
    y += Math.round((story ? 120 : 30) * k);
    g.fillStyle = th.ac; g.font = '900 ' + Math.round((story ? 230 : 170) * k) + 'px ' + font; g.fillText(c.big, pad, y + Math.round((story ? 180 : 140) * k));
    y += Math.round((story ? 250 : 190) * k);
    g.fillStyle = th.fg; g.globalAlpha = .85; g.font = '600 ' + Math.round((story ? 48 : 38) * k) + 'px ' + font; g.fillText(when(card), pad + 4, y); y += Math.round(56 * k);
    if (card.m && (size !== 'wide' || y < Hh - 140 * k)) {
      var np = Math.round(36 * k);
      wrap(card.m.replace(/\n/g, ' '), np, W - 2 * pad, story ? 4 : 1).forEach(function (ln) { g.font = '600 ' + np + 'px ' + font; g.fillText(ln, pad + 4, y); y += Math.round(np * 1.5); });
    }
    if (card.tasks.length && size !== 'wide') {   // the things to do, nearest the day last
      var tk = Math.round(40 * k), list = card.tasks.slice().sort(function (a, b) { return b.b - a.b; }).slice(0, story ? 5 : 3);
      y += Math.round(20 * k);
      list.forEach(function (t) {
        g.globalAlpha = .18; g.fillStyle = th.fg; g.fillRect(pad, y - Math.round(tk * 0.95), W - 2 * pad, Math.round(tk * 1.5));
        g.globalAlpha = .95; g.fillStyle = th.fg; g.font = '800 ' + tk + 'px ' + font; g.fillText((t.b ? t.b + '日前' : '当日') + '  ' + t.x.slice(0, 22), pad + 16, y + Math.round(tk * 0.15));
        y += Math.round(tk * 1.8);
      });
    }
    if (signed()) { g.globalAlpha = .7; g.textAlign = 'right'; g.font = '600 ' + Math.round(32 * k) + 'px ' + font; g.fillText('atomou.com', W - pad, Hh - Math.round(44 * k)); }
    return cv;
  }
  function saveImage(card, size) {
    drawCard(card, size).toBlob(function (blob) {
      if (!blob) { A.toast('画像を作れませんでした。'); return; }
      var file = null;
      try { file = new File([blob], 'atomou-card.png', { type: 'image/png' }); } catch (e) { file = null; }
      if (file && navigator.canShare && navigator.canShare({ files: [file] })) { navigator.share({ files: [file] }).catch(function () { /* closed */ }); return; }
      var url = URL.createObjectURL(blob), a = document.createElement('a');
      a.href = url; a.download = 'atomou-card-' + size + '.png'; document.body.appendChild(a); a.click();
      setTimeout(function () { URL.revokeObjectURL(url); a.remove(); }, 1000);
      A.toast('画像を保存しました。');
    }, 'image/png');
  }

  /* ---------- into my planner ---------- */
  function addToPlanner(card) {
    var S = A.state(), id = A.uid(), key = 'm:' + id;
    if (S.entries.length >= 500) { A.toast('記録が多いため、追加できません。マイページで整理してください。'); return null; }
    if (A.tier && A.tier.blocked(1)) return null;
    S.entries.push({ id: id, title: card.t || '(題名なし)', date: card.d, precision: 'day', kind: card.k, quiet: false, yearly: false, every100: false, alarm: '', time: card.tm || '', created: C.iso(TODAY) });
    if (card.m || card.tasks.length) {
      S.notes[key] = { memo: card.m, tasks: card.tasks.map(function (t) { return { id: Math.random().toString(36).slice(2, 8), before: t.b, text: t.x, done: false }; }) };
    }
    if (card.e && S.saved.indexOf(card.e) < 0) S.saved.push(card.e);
    A.persist();
    A.stat('act:card_add');
    return key;
  }

  /* ---------- the page ---------- */
  var box = $('#card-box'), card = fromHash(), editing = !card || /[#&]edit=1/.test(location.hash || ''), linked = null, sref = A.shared && A.shared.parseRef(location.hash);   // linked: a card kept up to date on the server
  if (sref) { card = null; editing = false; }
  var draft = card || { t: '', d: C.iso(C.addDays(TODAY, 30)), tm: '', m: '', th: 0, tasks: [], e: '', k: 'event' };

  function shareHtml() {
    return '<div class="share share-row" id="x-share" data-text="" data-url="" title="リンクを渡すと、相手の画面にこのカードが開きます。"><span class="share-lead">送る</span>' + AtomouShare.icons(['line', 'x', 'copy', 'native']) +
      '<span class="share-sep" aria-hidden="true"></span><span class="share-lead">画像</span>' +
      '<button type="button" class="sbt sbt-t" data-x-img="wide" title="横長(X・LINE)">横</button><button type="button" class="sbt sbt-t" data-x-img="square" title="正方形(Instagram)">正</button><button type="button" class="sbt sbt-t" data-x-img="story" title="縦長(ストーリーズ・TikTok・Shorts)">縦</button></div>' +
      '<p class="hint">画像は、横=X・LINE、正=Instagram、縦=ストーリーズ・TikTok・Shorts。</p>' +
      (A.tier && A.tier.on ? (A.tier.plus() ? '<p><label class="lab" for="x-nosign"><input type="checkbox" id="x-nosign"' + (signed() ? '' : ' checked') + '> 署名とリンクを入れずに送る(プラスプラン)</label></p>' : '<p class="hint">画像と文に、サイトの名前とリンクが入ります。' + (A.tier.plusOpen ? 'プラスプランでは、入れずに送れます。' : '') + '</p>') : '');
  }
  function wireShare(card) {
    var s = $('#x-share'); if (!s) return;
    s.setAttribute('data-text', words(card) + (card.m ? '\n' + card.m.slice(0, 60) : ''));
    s.setAttribute('data-url', linkOf(card));
    if (signed()) s.removeAttribute('data-nolink'); else s.setAttribute('data-nolink', '1');   // a card sent as words only carries no link
    if (window.AtomouShare) AtomouShare.init(s);
  }
  function calLinks(card) {
    var d = C.parse(card.d), detail = (card.m ? card.m + '\n' : '') + 'カード: ' + linkOf(card);
    var g = AtomouShare.googleUrl(card.t || 'カード', card.d, detail), o = AtomouShare.outlookUrl(card.t || 'カード', card.d, detail);
    return '<a class="btn small ghost" href="' + H(g) + '" target="_blank" rel="noopener">Googleカレンダーに追加</a> <a class="btn small ghost" href="' + H(o) + '" target="_blank" rel="noopener">Outlookに追加</a>';
  }

  /* ---------- a card kept up to date: the extra actions ---------- */
  function when_(ts) { var d = new Date((+ts || 0) * 1000); return isNaN(d) || !ts ? '' : (d.getMonth() + 1) + '月' + d.getDate() + '日 ' + ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2); }
  function sharedViewHtml() {
    if (!linked) return '';
    var fol = A.shared.find(linked.id), following = !!(fol && fol.follow !== false);
    return '<div class="x-shared" id="x-shared"><p><b>更新が届く共有カード</b>' + (linked.upd ? '(最終更新: ' + H(when_(linked.upd)) + ')' : '') + '</p>' +
      '<p class="x-actions">' + (following ? '<button type="button" class="btn small ghost" id="x-unfollow">フォローをやめる</button>' : '<button type="button" class="btn small" id="x-follow">このカードをフォローする(更新をお知らせ)</button>') +
      (linked.e ? ' <button type="button" class="btn small" id="x-edit-shared">編集して更新する</button>' : '') + ' <button type="button" class="btn small ghost" id="x-report">問題を知らせる</button></p>' +
      '<p class="hint">リンクを知っている人は、だれでもこのカードを読めます。' + (linked.e ? 'いま開いているのは編集用のリンクです。知っている人は、だれでも直せます。他の人には、読むだけのリンクを渡してください。' : '') + '</p>' +
      (linked.e ? '<p class="x-actions"><button type="button" class="btn small ghost" data-copy="' + H(A.shared.linkOf(linked, false)) + '">読むだけのリンクをコピー</button> <button type="button" class="btn small ghost" data-copy="' + H(A.shared.linkOf(linked, true)) + '">編集用のリンクをコピー</button> <button type="button" class="btn small ghost" id="x-del-shared">この共有カードを消す</button></p>' : '') + '</div>';
  }
  function copyText(t) {
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(function () { A.toast('コピーしました。'); }, function () { A.toast('コピーできませんでした。'); });
    else A.toast('コピーできませんでした。');
  }
  function wireSharedView() {
    var s = $('#x-shared'); if (!s) return;
    s.addEventListener('click', function (ev) {
      var b = ev.target.closest ? ev.target.closest('button') : null;
      if (!b) return;
      if (b.hasAttribute('data-copy')) { copyText(b.getAttribute('data-copy')); return; }
      if (b.id === 'x-follow') {
        if (A.shared.follow(linked, { card: card, ver: linked.ver, upd: linked.upd })) {
          if (window.Notification && Notification.permission === 'default') { try { Notification.requestPermission(); } catch (e) { /* the browser decides */ } }
          A.toast('フォローしました。更新があると、お知らせします。'); viewMode();
        }
      } else if (b.id === 'x-unfollow') { A.shared.unfollow(linked.id); A.toast('フォローをやめました。'); viewMode(); }
      else if (b.id === 'x-edit-shared') { draft = clean(JSON.parse(JSON.stringify(card))); editing = true; history.replaceState(null, '', location.pathname + location.search + '#s=' + linked.id + '.' + linked.k + '.' + linked.e + '&edit=1'); render(); }
      else if (b.id === 'x-report') { A.shared.report(linked.id).then(function (ok) { A.toast(ok ? '知らせました。ありがとうございます。' : '送れませんでした。'); }); }
      else if (b.id === 'x-del-shared') {
        if (window.confirm('この共有カードを消します。フォローしている人にも見えなくなります。よろしいですか。')) A.shared.remove(linked).then(function (ok) { if (ok) { A.toast('消しました。'); location.href = '/card/'; } else A.toast('消せませんでした。'); });
      }
    });
  }
  function sharedEditHtml() {
    if (!A.shared || !A.shared.supported()) return '';
    var can = !!(linked && linked.e);
    return '<p class="x-actions"><button type="button" class="btn" id="x-shared-go">' + (can ? '共有カードを更新する' : '更新が届く共有カードにする') + '</button></p>' +
      '<p class="hint">' + (can ? 'フォローしている人に、新しい内容が届きます。' : 'リンクを渡した人のカードが、あなたの更新に合わせて変わります。内容は暗号にして預かり、鍵はリンクの中にだけあります。') + '</p><div id="x-shared-out" aria-live="polite"></div>';
  }
  function wireSharedEdit() {
    var go = $('#x-shared-go'); if (!go) return;
    go.addEventListener('click', function () {
      readForm(); draft.tasks = draft.tasks.filter(function (t) { return t.x; });
      if (!draft.t) { A.toast('題名を入れてください。'); return; }
      var c = clean(draft), out = $('#x-shared-out');
      var can = !!(linked && linked.e);
      if (!can && A.tier && A.tier.sharedBlocked && A.tier.sharedBlocked()) return;
      go.disabled = true; out.textContent = '送っています…';
      var job = can ? A.shared.update(linked, c).then(function (r) { linked.ver = r.ver; linked.upd = r.upd; return linked; }) : A.shared.create(c).then(function (x) { linked = x; return x; });
      job.then(function (x) {
        card = c; history.replaceState(null, '', location.pathname + location.search + '#s=' + x.id + '.' + x.k + '.' + x.e);
        out.innerHTML = '<p>' + (can ? '更新しました。フォローしている人には、サイトを開いたとき、または数分のうちに届きます。' : '共有カードができました。') + '</p><p class="x-actions"><button type="button" class="btn small" id="x-view">できあがりを見る</button></p>' + shareHtml();
        wireShare(card);
        $('#x-view').addEventListener('click', function () { editing = false; render(); window.scrollTo(0, 0); });
        go.disabled = false;
      }, function (err) {
        go.disabled = false;
        if (err && err.message === 'conflict') {
          out.innerHTML = '<p>他の人が先に更新しました。最新の内容を読み込んでから、もう一度直してください。</p><p class="x-actions"><button type="button" class="btn small" id="x-newest">最新の内容を読み込む</button></p>';
          $('#x-newest').addEventListener('click', function () {
            A.shared.read(linked).then(function (r) { linked.ver = r.ver; linked.upd = r.upd; draft = clean(r.card) || draft; A.shared.put({ id: linked.id, ver: r.ver, seen: r.ver }); render(); }, function () { A.toast('読み込めませんでした。'); });
          });
        } else out.textContent = err && err.message === 'limit' ? '今日は、共有カードを作れる数に達しました。明日、もう一度お試しください。' : '送れませんでした。しばらくして、もう一度お試しください。';
      });
    });
  }
  function viewMode() {
    A.stat('act:card_view');
    box.innerHTML = '<div id="x-card">' + cardHtml(card) + '</div>' +
      '<p class="x-actions"><button type="button" class="btn" id="x-add">自分の予定帳に入れる</button> ' + calLinks(card) + '</p>' +
      '<p class="hint" id="x-added" aria-live="polite"></p>' +
      '<p class="x-actions"><button type="button" class="btn small ghost" id="x-edit">このカードを直して、自分のカードにする</button> <a class="btn small ghost" href="/card/">新しいカードを作る</a>' + (card.e ? ' <a class="btn small ghost" href="/e/' + H(card.e) + '/">この日の公式ページ(出典つき)</a>' : '') + '</p>' +
      sharedViewHtml() + shareHtml() +
      '<p class="small muted">このカードの内容は、リンクを作った人が書いたものです。当サイトは内容を確認していません。心当たりのないカードや、不審なお願いが書かれたカードは、開かずに閉じてください。</p>';
    wireShare(card);
    wireSharedView();
    $('#x-add').addEventListener('click', function () {
      var key = addToPlanner(card);
      if (key) { $('#x-added').innerHTML = '予定帳に入れました。<a href="/plan/?key=' + H(key) + '">メモ・やることを見る</a> / <a href="/calendar/">カレンダーを見る</a>'; A.toast('予定帳に入れました。'); }
    });
    $('#x-edit').addEventListener('click', function () { linked = null; draft = clean(JSON.parse(JSON.stringify(card))); editing = true; history.replaceState(null, '', location.pathname + location.search + '#edit=1'); render(); });
  }

  function editMode() {
    var d = draft;
    box.innerHTML = '<p class="lead muted">日付・ひとこと・やることを入れて、リンクや画像でだれにでも送れます。受け取った人は、1タップで自分の予定帳に入れられます。</p>' +
      '<div class="x-paste"><label class="lab" for="x-paste">調べた文章を貼り付ける(Google や AI の答え、チラシの文章など)</label><textarea id="x-paste" rows="3" maxlength="4000" placeholder="例: 〇〇ワンマンライブ 2026年12月1日(火) 開場18:00 開演19:00 渋谷…"></textarea>' +
      '<p class="x-actions"><button type="button" class="btn small" id="x-find">日付を探す</button> </p><div id="x-found" aria-live="polite"></div></div>' +
      '<div class="x-tpl"><span class="lab">こんなときに(押すと、例が入ります)</span><div class="chiprow">' + TEMPLATES.map(function (t) { return '<button type="button" class="chip" data-tpl="' + t.id + '">' + H(t.n) + '</button>'; }).join('') + '</div></div>' +
      '<div class="x-grid"><form id="x-form" autocomplete="off">' +
      '<div class="field"><label for="x-t">題名(例: 〇〇バンド ワンマンライブ)</label><input type="text" id="x-t" maxlength="' + MAX.t + '" value="' + H(d.t) + '"></div>' +
      '<div class="field"><label for="x-d">日付</label><input type="date" id="x-d" value="' + H(d.d) + '"></div>' +
      '<div class="field"><label for="x-say">文字で日付を入力する</label><input type="text" id="x-say" maxlength="30" placeholder="12月25日 / 2027年3月3日">' + (window.AtomouMicHint ? window.AtomouMicHint() : '') + '</div>' +
      '<div class="field"><label for="x-tm">時刻(なくてもよい)</label><input type="time" id="x-tm" value="' + H(d.tm) + '"></div>' +
      '<div class="field"><label for="x-m">ひとこと(場所・持ち物・連絡先など。リンクのアドレスは入れられません)</label><textarea id="x-m" rows="3" maxlength="' + MAX.m + '">' + H(d.m) + '</textarea></div>' +
      '<div class="field"><label for="x-k">種類</label><select id="x-k">' + KIND_OK.map(function (k) { return '<option value="' + k + '"' + (d.k === k ? ' selected' : '') + '>' + H(KINDS[k].t) + '</option>'; }).join('') + '</select></div>' +
      '<div class="field"><span class="lab">色</span><div class="x-themes" role="group" aria-label="色">' + THEMES.map(function (t, i) { return '<button type="button" class="x-th" data-th="' + i + '" aria-pressed="' + (d.th === i) + '" style="background:' + t.bg + ';color:' + t.fg + ';border-color:' + t.ac + '">' + H(t.n) + '</button>'; }).join('') + '</div></div>' +
      '<div class="field"><span class="lab">やること(何日前までに)</span><div id="x-tasks"></div><button type="button" class="btn small ghost" id="x-addtask">やることを足す</button></div>' +
      '</form><div class="x-side"><div id="x-card"></div>' + sharedEditHtml() + '<p class="x-actions"><button type="button" class="btn" id="x-make">リンクをつくる</button></p><div id="x-out"></div></div></div>';
    taskRows(); preview(); wireEdit(); wireSharedEdit();
    $('#x-find').addEventListener('click', function () { findDays($('#x-paste').value); });
    if (pasted) { $('#x-paste').value = pasted; pasted = ''; findDays($('#x-paste').value); }
    $('.x-tpl').addEventListener('click', function (ev) {
      var b = ev.target.closest ? ev.target.closest('[data-tpl]') : null, tp = b && TEMPLATES.filter(function (x) { return x.id === b.getAttribute('data-tpl'); })[0];
      if (tp) { draft = clean({ t: tp.t, d: C.iso(C.addDays(TODAY, tp.days)), tm: tp.tm || '', m: tp.m, th: tp.th, k: tp.k, tasks: tp.tasks }) || draft; A.stat('act:card_tpl_' + tp.id); editMode(); window.scrollTo(0, 0); }
    });
  }
  var pasted = '';
  var SNS_HOSTS = /(^|\.)(x\.com|twitter\.com|instagram\.com|facebook\.com|tiktok\.com|youtube\.com|youtu\.be|threads\.net|t\.co)$/;
  function linksIn(text) {   // the web addresses written in the pasted words: a post of a social site points to the organiser's own page, which is the one to read the date from
    var seen = {}, out = [];
    (String(text || '').match(/https?:\/\/[^\s<>"'　)）」』]+/g) || []).forEach(function (u) {
      var host = '';
      try { host = new URL(u).hostname.replace(/^www\./, ''); } catch (e) { return; }
      if (!host || seen[u] || out.length >= 5) return;
      seen[u] = 1; out.push({ url: u, host: host, sns: SNS_HOSTS.test(host) });
    });
    return out;
  }
  function linksHtml(text) {
    var ls = linksIn(text);
    if (!ls.length) return '';
    var sns = ls.some(function (l) { return l.sns; });
    return '<p class="hint">' + (sns ? 'SNSの投稿は、日付が変わることがあります。主催者の公式ページや、予約・チケットのページを開いて、日付が書かれた文章をもう一度貼ると、確かな日付になります。' : '文章の中のリンクです。日付が書かれたページを開いて、その文章を貼ることもできます。') + '</p><ul class="x-links">' +
      ls.map(function (l) { return '<li><a href="' + H(l.url) + '" target="_blank" rel="noopener noreferrer nofollow">' + H(l.host) + '</a>' + (l.sns ? ' <span class="small muted">(SNSの投稿)</span>' : '') + '</li>'; }).join('') + '</ul>';
  }
  function findDays(text) {   // days in the words: pick one and it fills the card (the title, the date, the time, and the words around it as the note)
    var out = $('#x-found'), list = C.extractDays(text, TODAY);
    A.stat('act:card_paste');
    if (!text.trim()) { out.textContent = '文章を貼り付けてください。'; return; }
    if (!list.length) { out.innerHTML = '<p>日付が見つかりませんでした。「12月1日」「2026年12月1日」のように書かれた日付を探します。下の欄に、日付を直接入れることもできます。</p>' + linksHtml(text); return; }
    out.innerHTML = '<p class="hint">見つかった日付です。使うものを押すと、カードに入ります。</p><div class="x-cands">' + list.map(function (c, i) {
      return '<button type="button" class="chip" data-cand="' + i + '">' + H(A.fmtDate(c.iso, 'day') + (c.time ? ' ' + c.time : '') + (c.title ? ' ' + c.title.slice(0, 18) : '')) + '</button>';
    }).join('') + '</div>' + linksHtml(text);
    out.onclick = function (ev) {
      var b = ev.target.closest ? ev.target.closest('[data-cand]') : null, c = b && list[+b.getAttribute('data-cand')];
      if (!c) return;
      draft = clean({ t: c.title || draft.t, d: c.iso, tm: c.time, m: c.context.slice(0, MAX.m), th: draft.th, tasks: draft.tasks, e: '', k: draft.k }) || draft;
      editMode(); window.scrollTo(0, 0); A.toast('カードに入れました。題名やひとことを直してください。');
    };
  }
  function taskRows() {
    $('#x-tasks').innerHTML = draft.tasks.map(function (t, i) {
      return '<div class="x-task"><select data-tb="' + i + '" aria-label="何日前">' + [0, 1, 3, 7, 14, 30, 60, 100].map(function (b) { return '<option value="' + b + '"' + (t.b === b ? ' selected' : '') + '>' + (b ? b + '日前' : '当日') + '</option>'; }).join('') + '</select>' +
        '<input type="text" data-tx="' + i + '" maxlength="' + MAX.task + '" value="' + H(t.x) + '" aria-label="やること"><button type="button" class="mini" data-td="' + i + '" aria-label="消す">×</button></div>';
    }).join('');
  }
  function readForm() {   // the fields are copied as they are typed; the task rows stay as they are (an empty row is still being written)
    var v = function (id) { var el = $('#' + id); return el ? el.value : ''; };
    var d = C.parse(v('x-d'));
    draft.t = v('x-t').replace(/[\u0000-\u001f<>]/g, '').slice(0, MAX.t);
    if (d) draft.d = C.iso(d);
    draft.tm = /^([01]\d|2[0-3]):[0-5]\d$/.test(v('x-tm')) ? v('x-tm') : '';
    draft.m = v('x-m').replace(/[\u0000-\u0008<>]/g, '').slice(0, MAX.m);
    draft.k = KIND_OK.indexOf(v('x-k')) >= 0 ? v('x-k') : 'event';
  }
  function preview() { var el = $('#x-card'); if (el) el.innerHTML = cardHtml(draft); }
  function wireEdit() {
    var form = $('#x-form');
    form.addEventListener('input', function (ev) {
      var t = ev.target;
      if (t.hasAttribute('data-tx')) { draft.tasks[+t.getAttribute('data-tx')].x = t.value.slice(0, MAX.task); }
      else if (t.hasAttribute('data-tb')) { draft.tasks[+t.getAttribute('data-tb')].b = +t.value; }
      else if (t.id === 'x-say') { var d = C.parseSpoken(t.value, 'day', TODAY); if (d) { $('#x-d').value = C.iso(d); } }
      readForm(); preview();
    });
    form.addEventListener('change', function () { readForm(); preview(); });
    form.addEventListener('click', function (ev) {
      var b = ev.target.closest ? ev.target.closest('button') : null;
      if (!b) return;
      if (b.hasAttribute('data-th')) { draft.th = +b.getAttribute('data-th'); $$('.x-th').forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); }); preview(); }
      else if (b.id === 'x-addtask') { readForm(); if (draft.tasks.length < MAX.tasks) { draft.tasks.push({ b: 7, x: '' }); taskRows(); } }
      else if (b.hasAttribute('data-td')) { draft.tasks.splice(+b.getAttribute('data-td'), 1); taskRows(); preview(); }
    });
    form.addEventListener('submit', function (ev) { ev.preventDefault(); });
    $('#x-make').addEventListener('click', function () {
      readForm();
      draft.tasks = draft.tasks.filter(function (t) { return t.x; });
      if (!draft.t) { A.toast('題名を入れてください。'); return; }
      card = clean(draft); history.replaceState(null, '', location.pathname + location.search + '#c=' + pack(card));
      A.stat('act:card_make');
      $('#x-out').innerHTML = '<p>リンクができました。このリンクを開いた人に、カードが届きます。</p><p class="x-actions"><button type="button" class="btn small" id="x-view">できあがりを見る</button></p>' + shareHtml();
      wireShare(card);
      $('#x-view').addEventListener('click', function () { editing = false; render(); window.scrollTo(0, 0); });
    });
  }
  function render() { if (editing) editMode(); else viewMode(); }
  box.addEventListener('click', function (ev) {
    var b = ev.target.closest ? ev.target.closest('[data-x-img]') : null;
    if (b) { var cc = editing ? clean(draft) : card; if (cc) { A.stat('act:card_img'); saveImage(cc, b.getAttribute('data-x-img')); } }
  });

  // a card made from a day: #from=c:<official id> or #from=m:<own id> (the visitor chose to turn it into a card)
  function prefill() {
    var sh = /[#&]share=([A-Za-z0-9_-]+)/.exec(location.hash || '');
    if (sh && !card) {   // words handed over from another app's share sheet (the service worker turned the post into this link; nothing went to a server)
      try { var o = JSON.parse(b64dec(sh[1])); pasted = [o.title, o.text, o.url].filter(Boolean).join('\n').slice(0, 4000); editing = true; } catch (e) { pasted = ''; }
      history.replaceState(null, '', location.pathname + location.search + '#edit=1');
      return Promise.resolve();
    }
    var m = /[#&]from=([cm]):([A-Za-z0-9_-]{1,40})/.exec(location.hash || '');
    if (!m) return Promise.resolve();
    if (m[1] === 'm') {
      var e = A.findEntry(m[2]);
      if (e && !e.quiet && e.precision === 'day') { var n = (A.state().notes['m:' + e.id]) || { memo: '', tasks: [] }; draft = clean({ t: e.title, d: e.date, tm: e.time, m: n.memo, k: e.kind === 'memorial' ? 'event' : e.kind, tasks: n.tasks.map(function (t) { return { b: t.before, x: t.text }; }) }) || draft; }
      else A.toast('この日は、カードにできません。');
      return Promise.resolve();
    }
    return A.loadCatalog().then(function (cat) {
      var c = (cat || []).filter(function (x) { return x.id === m[2]; })[0];
      if (c && !c.quiet && c.precision === 'day') draft = clean({ t: c.title, d: c.date, e: c.id, k: 'event', th: 0, m: '', tasks: [] }) || draft;
    });
  }
  function loadShared() {
    if (!A.shared || !A.shared.supported()) { box.innerHTML = '<p class="notice">このブラウザでは、共有カードを開けません。新しいブラウザでお試しください。</p>'; return; }
    box.innerHTML = '<p class="muted">共有カードを読み込んでいます…</p>';
    A.shared.read(sref).then(function (r) {
      card = clean(r.card);
      if (!card) throw new Error('key');
      linked = { id: sref.id, k: sref.k, e: sref.e, ver: r.ver, upd: r.upd };
      var fol = A.shared.find(sref.id);
      if (fol) A.shared.put({ id: sref.id, e: sref.e || fol.e || '', ver: r.ver, seen: r.ver, upd: r.upd, t: card.t, d: card.d, changed: false });
      editing = /[#&]edit=1/.test(location.hash || '') && !!sref.e;
      if (editing) draft = clean(JSON.parse(JSON.stringify(card)));
      render();
    }, function (err) {
      var m = err && err.message;
      box.innerHTML = '<p class="notice">' + (m === 'none' ? 'この共有カードは見つかりません。消されたか、長い間更新がなく、期限が切れた可能性があります。' : m === 'blocked' ? 'このカードは、問題があると知らされたため、表示できません。' : m === 'key' ? 'リンクが正しくないようです。リンクの最後まで、そのままコピーしてください。' : '読み込めませんでした。しばらくして、開き直してください。') + '</p><p><a class="btn" href="/card/">新しいカードを作る</a></p>';
    });
  }
  if (sref) loadShared();
  else prefill().then(function () { if (!card && /[#&]from=/.test(location.hash || '')) editing = true; render(); });
  window.addEventListener('hashchange', function () {
    var r = A.shared && A.shared.parseRef(location.hash);   // another shared card's link was pasted into the address bar: read it from the start
    if (r && (!sref || r.id !== sref.id || (!!r.e !== !!sref.e))) { location.reload(); return; }
    var c = fromHash(); if (c) { card = c; editing = false; render(); } });
  window.AtomouCard = { pack: pack, clean: clean, drawCard: drawCard, words: words };
})();
