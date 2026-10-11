/* あと何日、もう何日: members (free; a one-time code by e-mail, no password).  Talks to api/m.php; the session is an HttpOnly cookie.
   - The e-mail notices are opt-in: only then do the days (and a short title each) go to the server, computed by push.js's planner.
   - Monitors (tier id 'tester') answer a one-minute questionnaire after a week and after a month, each within 7 days.  Before the deadline a
     small notice on the home page (it can be put off for the day); after it, a thin bar on every page until it is answered.  Two days before
     the deadline, a reminder goes into the push / e-mail notice list.
   - A small copy of the member's state (tier, start day, questionnaires done) stays on the device ('atomou.member') so the bar can be
     shown on any page; it is refreshed from the server once a day.
   - The thanks page (/thanks/) shows the monthly list (consented pen names only). */
(function () {
  'use strict';
  var A = window.AtomouApp;
  if (!A || !A.CONF.members) return;
  var $ = A.$, H = A.H, C = A.C, API = '/api/m.php', MC = A.CONF.members || {}, TIERS = MC.tiers || {}, CACHE = 'atomou.member', LATER = 'atomou.survey_later';
  var BADGES = { early: '初期メンバー', monitor_star: '名誉モニター', referrer_star: '紹介の達人' };
  function call(body) {
    return fetch(API, { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: JSON.stringify(Object.assign({ v: 1 }, body)), credentials: 'same-origin' })
      .then(function (r) { return r.status === 204 ? { ok: true, data: {} } : r.json().then(function (j) { return { ok: r.ok, status: r.status, data: j }; }); });
  }
  function fmt(iso) { var d = C.parse(iso); return d ? d[0] + '年' + d[1] + '月' + d[2] + '日' : ''; }
  function md(d) { return d[1] + '月' + d[2] + '日'; }
  function months(n) { return n % 12 === 0 ? (n / 12) + '年間' : n === 6 ? '半年間' : n + 'か月'; }
  function tierText(m) {
    if (m.free_until && m.free_until >= C.iso(A.TODAY)) return 'すべての機能を' + fmt(m.free_until) + 'まで使えます(' + (m.tier === 'referred' ? '紹介' : (TIERS[m.tier] || '先着')) + ')。';
    return '無料プランです。';
  }

  /* ---------- the small copy on the device ---------- */
  function readCache() { try { var c = JSON.parse(localStorage.getItem(CACHE) || 'null'); return c && typeof c === 'object' ? c : null; } catch (e) { return null; } }
  function keep(m) {
    try {
      if (!m) { localStorage.removeItem(CACHE); return; }
      localStorage.setItem(CACHE, JSON.stringify({ tier: String(m.tier || ''), plan: m.plan === 'plus' ? 'plus' : '', free_until: /^\d{4}-\d{2}-\d{2}$/.test(String(m.free_until || '')) ? m.free_until : '', created: String(m.created || ''), surveys: (m.surveys || []).filter(function (x) { return x === 1 || x === 2; }), at: C.iso(A.TODAY) }));
    } catch (e) { /* only a nicety */ }
  }

  /* ---------- the monitor's questionnaire: which one is due, and by when ---------- */
  function due(m, today) {   // {n, deadline, late} or null
    if (!m || m.tier !== 'tester') return null;
    var c = C.parse(m.created), done = m.surveys || [], t = today || A.TODAY;
    if (!c) return null;
    var days = C.totalDays(c, t);
    var n = (days >= 30 && done.indexOf(2) < 0) ? 2 : (days >= 7 && done.indexOf(1) < 0) ? 1 : 0;
    if (!n) return null;
    var deadline = C.addDays(c, n === 1 ? 14 : 37);
    return { n: n, deadline: deadline, late: C.cmp(t, deadline) > 0 };
  }
  function upcoming(m) {   // the next questionnaire's deadline (for the reminder two days before), even before it is due
    if (!m || m.tier !== 'tester') return null;
    var c = C.parse(m.created), done = m.surveys || [];
    if (!c) return null;
    if (done.indexOf(1) < 0) return { n: 1, deadline: C.addDays(c, 14) };
    if (done.indexOf(2) < 0) return { n: 2, deadline: C.addDays(c, 37) };
    return null;
  }
  window.AtomouMember = {
    due: due,
    keep: keep,
    extraNotices: function () {   // used by push.js's planner: the reminder two days before the deadline
      var u = upcoming(readCache());
      if (!u) return [];
      return [{ d: C.addDays(u.deadline, -2), s: 'm', t: 'モニターのアンケート(1分)は' + md(u.deadline) + 'までです。', u: '/my/#member' }];
    }
  };

  function banner() {
    if (A.page === 'my') return;
    var d = due(readCache());
    if (!d) return;
    var later = '';
    try { later = localStorage.getItem(LATER) || ''; } catch (e) { later = ''; }
    if (!d.late && (A.page !== 'home' || later === C.iso(A.TODAY))) return;
    var main = document.querySelector('main');
    if (!main || $('#m-due')) return;
    var el = document.createElement('div');
    el.id = 'm-due'; el.className = 'notice';
    el.innerHTML = d.late
      ? 'モニターのアンケート(1分)の期限が過ぎています。回答すると、この表示は消えます。 <a class="btn small" href="/my/#member">答える</a>'
      : 'モニターのアンケート(1分)は、' + md(d.deadline) + 'までにお答えください。 <a class="btn small" href="/my/#member">答える</a> <button type="button" class="btn small ghost" id="m-later">あとで</button>';
    main.insertBefore(el, main.firstChild);
    var b = $('#m-later');
    if (b) b.addEventListener('click', function () { try { localStorage.setItem(LATER, C.iso(A.TODAY)); } catch (e) { /* ignore */ } el.remove(); });
  }

  function noticeDates() {
    if (!window.AtomouPush) return Promise.resolve([]);
    return A.loadCatalog().then(function (cat) {
      var p = window.AtomouPush.plan(cat || []);
      return p.dates.map(function (x) { var k = x.d + '|' + x.s, lines = p.mirror[k] || []; return { d: x.d, s: x.s, t: lines.map(function (l) { return l.t; }).join(' / ').slice(0, 60) }; });
    });
  }

  /* ---------- the box on the my page ---------- */
  function pageMy() {
    var box = $('#member-box');
    if (!box) return;
    box.hidden = false;
    var me = null, email = '';
    function view(html) { box.querySelector('.m-body').innerHTML = html; }
    function stepOut() {
      keep(null);
      view('<p>会員になると、メール通知と先着特典を利用できます。無料で、パスワードは不要です。</p><div class="panel" id="m-pools" hidden></div>' +
        '<div class="field"><label for="m-email">メールアドレス</label><input type="email" id="m-email" autocomplete="email" inputmode="email" value="' + H(email) + '"></div>' +
        '<p><button type="button" class="btn" id="m-send">確認コードを送る</button></p>' +
        '<p class="hint">コードを入力すると、<a href="/terms/">利用規約</a>と<a href="/privacy/#members">プライバシーポリシー</a>に同意したことになります。</p>');
      call({ a: 'seats' }).then(function (r) {
        var el = $('#m-pools'), pools = (r.ok && r.data && r.data.pools) || [], open = pools.filter(function (x) { return x.left > 0; });
        if (!el) return;
        if (!open.length) { el.innerHTML = '<p>先着の枠は埋まりました。紹介リンクから登録すると、' + months(MC.ref) + 'すべての機能を無料で使えます。</p>'; el.hidden = false; return; }
        el.innerHTML = '<p><b>先着の特典</b>(どちらかを選んでください)</p>' + open.map(function (x, i) {
          return '<p><label class="lab pool"><input type="radio" name="m-want" value="' + H(x.id) + '"' + (i === open.length - 1 ? ' checked' : '') + '> <b>' + H(TIERS[x.id] || x.id) + '</b> 残り' + x.left + '名<br>' +
            '<span class="muted">登録日から' + months(x.months) + '、すべての機能を無料で使えます。' + (x.tester ? '条件: 登録の1週間後と1か月後に、1分のアンケートへ回答する(それぞれ7日以内)。' : '条件はありません。') + '</span></label></p>';
        }).join('');
        el.hidden = false;
      }).catch(function () { /* the places are a nicety; signing up works without them */ });
      $('#m-send').addEventListener('click', function () {
        email = $('#m-email').value.trim();
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { A.toast('メールアドレスを確かめてください。'); return; }
        var ref = '';
        try { ref = localStorage.getItem('atomou.ref') || ''; } catch (e) { ref = ''; }
        $('#m-send').disabled = true;
        var w = document.querySelector('input[name="m-want"]:checked');
        call({ a: 'code', email: email, ref: ref, want: w ? w.value : '' }).then(function () { A.stat('act:member_code'); stepCode(); }, function () { A.toast('送れませんでした。しばらくして、もう一度お試しください。'); $('#m-send').disabled = false; });
      });
    }
    function stepCode() {
      view('<p>' + H(email) + ' に6桁の確認コードを送りました。10分以内に入力してください。</p>' +
        '<div class="field"><label for="m-code">確認コード</label><input type="text" id="m-code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]*"></div>' +
        '<p><button type="button" class="btn" id="m-verify">ログイン</button> <button type="button" class="btn ghost" id="m-back">戻る</button></p>');
      $('#m-code').focus();
      $('#m-back').addEventListener('click', stepOut);
      $('#m-verify').addEventListener('click', function () {
        var code = $('#m-code').value.replace(/\D/g, '');
        if (code.length !== 6) { A.toast('6桁の数字を入力してください。'); return; }
        call({ a: 'verify', email: email, code: code }).then(function (r) {
          if (r.ok) { me = r.data.member; keep(me); A.stat('act:member_login'); A.toast('ログインしました。'); stepIn(); return; }
          A.toast(r.data.error === 'wrong' ? 'コードが違います。' + (r.data.left > 0 ? 'あと' + r.data.left + '回。' : '') : 'コードの期限が切れました。もう一度送ってください。');
          if (r.data.error !== 'wrong') stepOut();
        }, function () { A.toast('確認できませんでした。'); });
      });
    }
    function surveyHtml() {
      var d = due(me);
      if (!d) return '';
      function opts(name, list) { return list.map(function (o, i) { return '<label class="lab"><input type="radio" name="' + name + '" value="' + o[0] + '"' + (i ? '' : ' checked') + '> ' + o[1] + '</label>'; }).join(''); }
      return '<div class="panel" id="m-survey"><h3>モニターのアンケート(' + d.n + '/2・1分)</h3>' +
        '<p class="hint">' + (d.late ? '期限(' + md(d.deadline) + ')が過ぎています。答えると、画面の上の表示が消えます。' : md(d.deadline) + 'までにお答えください。期限を過ぎると、回答するまで画面上部に表示されます。') + '</p>' +
        '<p>どのくらいの頻度で使っていますか。</p>' + opts('s-freq', [['daily', 'ほぼ毎日'], ['weekly', '週に数回'], ['rarely', 'ときどき']]) +
        '<p>いちばん使う機能は何ですか。</p>' + opts('s-use', [['count', '日数を数える'], ['calendar', 'カレンダー'], ['todo', 'やること'], ['official', '公式の日付'], ['notice', '通知'], ['other', 'そのほか']]) +
        '<div class="field"><label for="s-text">分かりにくいところや、ほしい機能(任意)</label><textarea id="s-text" maxlength="300" rows="3"></textarea></div>' +
        '<p><button type="button" class="btn" id="s-send" data-n="' + d.n + '">送る</button></p></div>';
    }
    function wireSurvey() {
      var b = $('#s-send');
      if (!b) return;
      b.addEventListener('click', function () {
        var f = document.querySelector('input[name="s-freq"]:checked'), u = document.querySelector('input[name="s-use"]:checked');
        b.disabled = true;
        call({ a: 'survey', n: +b.getAttribute('data-n'), answers: { freq: f ? f.value : '', use: u ? u.value : '', text: $('#s-text').value } }).then(function (r) {
          if (r.ok) { me = r.data.member; keep(me); A.stat('act:monitor_survey'); A.toast('ご協力ありがとうございます。'); stepIn(); } else { A.toast('送れませんでした。'); b.disabled = false; }
        });
      });
    }
    function stepIn() {
      var link = location.origin + '/?ref=' + me.ref_code, badges = (me.badges || []).map(function (b) { return BADGES[b]; }).filter(Boolean);
      view('<p><b>' + H(me.email) + '</b><br>' + H(tierText(me)) + (badges.length ? '<br>称号: ' + H(badges.join('・')) : '') + '</p>' + surveyHtml() +
        '<div class="field"><label class="lab" for="m-notice"><input type="checkbox" id="m-notice"' + (me.notices.on ? ' checked' : '') + '> メールでもお知らせする(通知と同じ日・同じ時間)</label></div>' +
        '<div class="field"><label class="lab" for="m-weekly"><input type="checkbox" id="m-weekly"' + (me.notices.weekly ? ' checked' : '') + (me.notices.on ? '' : ' disabled') + '> 毎週月曜の朝に、1週間の予定と、公式の日をまとめて受け取る</label></div>' +
        '<p class="hint">オンにすると、通知する日と予定名(短く)をサーバーで預かります。オフにすると削除します。</p>' +
        '<h3>紹介</h3><p>この紹介リンクから登録した人は、' + months(MC.ref) + 'すべての機能を無料で使えます。その人が1週間以上あけて2回使うと、あなたにも' + months(MC.give) + '追加されます(' + MC.cap + '人まで)。</p>' +
        '<p><input type="text" readonly value="' + H(link) + '" id="m-link"> <button type="button" class="btn small ghost" id="m-copy">コピー</button></p>' +
        '<h3>協力者のページ</h3><p>紹介の人数と、採用されたご意見を毎月<a href="/thanks/">協力者のページ</a>で紹介します。無料期間の延長や称号を贈ります。掲載するのはペンネームだけです。</p>' +
        '<div class="field"><label for="m-pen">ペンネーム(20字まで)</label><input type="text" id="m-pen" maxlength="20" value="' + H(me.pen || '') + '"></div>' +
        '<div class="field"><label class="lab" for="m-penok"><input type="checkbox" id="m-penok"' + (me.pen_ok ? ' checked' : '') + '> 協力者のページにペンネームを載せてよい</label></div>' +
        '<p><button type="button" class="btn small" id="m-pensave">保存</button></p>' +
        '<p><button type="button" class="btn small ghost" id="m-logout">ログアウト</button> <button type="button" class="btn small ghost" id="m-delete">退会する</button></p>');
      wireSurvey();
      $('#m-copy').addEventListener('click', function () { try { navigator.clipboard.writeText(link).then(function () { A.toast('コピーしました。'); }); } catch (e) { $('#m-link').select(); } });
      $('#m-pensave').addEventListener('click', function () {
        call({ a: 'update', pen: $('#m-pen').value, pen_ok: $('#m-penok').checked }).then(function (r) {
          if (r.ok) { me = r.data.member; A.toast(me.pen_ok ? 'ペンネームを保存しました。協力者のページに掲載します。' : 'ペンネームを保存しました。'); stepIn(); }
          else A.toast(r.data && r.data.error === 'pen' ? 'ペンネームに、メールアドレス・URL・電話番号は使えません。' : '保存できませんでした。');
        });
      });
      $('#m-notice').addEventListener('change', function () {
        var on = $('#m-notice').checked, wk = $('#m-weekly');
        if (wk) { wk.disabled = !on; if (!on) wk.checked = false; }
        noticeDates().then(function (dates) { return call({ a: 'update', notices: { on: on, weekly: !!(wk && wk.checked), dates: dates } }); }).then(function (r) {
          if (r.ok) { me = r.data.member; A.toast(on ? 'メールでも通知します。' : 'メール通知を止めました。'); } else { A.toast('保存できませんでした。'); $('#m-notice').checked = !on; }
        });
      });
      $('#m-weekly').addEventListener('change', function () {
        var wk = $('#m-weekly').checked;
        noticeDates().then(function (dates) { return call({ a: 'update', notices: { on: true, weekly: wk, dates: dates } }); }).then(function (r) {
          if (r.ok) { me = r.data.member; A.toast(wk ? '毎週月曜の朝に、まとめてお送りします。' : '毎週のメールを止めました。'); } else { A.toast('保存できませんでした。'); $('#m-weekly').checked = !wk; }
        });
      });
      $('#m-logout').addEventListener('click', function () { call({ a: 'logout' }).then(function () { me = null; A.toast('ログアウトしました。'); stepOut(); }); });
      $('#m-delete').addEventListener('click', function () {
        if (!window.confirm('会員登録を削除します。この端末の記録は残ります。よろしいですか。')) return;
        call({ a: 'delete' }).then(function () { me = null; A.toast('退会しました。'); stepOut(); });
      });
    }
    call({ a: 'me' }).then(function (r) { if (r.ok) { me = r.data.member; keep(me); stepIn(); } else stepOut(); }, stepOut);
  }

  /* ---------- the thanks page ---------- */
  function pageThanks() {
    var el = $('#thanks-list');
    if (!el) return;
    call({ a: 'thanks' }).then(function (r) {
      var list = (r.ok && r.data && r.data.months) || [];
      if (!list.length) { el.innerHTML = '<p class="muted">最初の発表は、会員の募集を始めた翌月です。</p>'; return; }
      el.innerHTML = list.map(function (x) {
        var y = String(x.month).slice(0, 4), mo = +String(x.month).slice(5, 7);
        return '<section class="panel"><h2>' + H(y) + '年' + mo + '月</h2>' +
          '<h3>紹介</h3>' + ((x.referrers || []).length ? '<ol>' + x.referrers.map(function (p) { return '<li>' + H(p.name) + '(' + (+p.n) + '人)</li>'; }).join('') + '</ol>' : '<p class="muted">この月はいませんでした。</p>') +
          '<h3>採用されたご意見</h3>' + ((x.adopted || []).length ? '<ul>' + x.adopted.map(function (p) { return '<li>' + H(p.name) + ': ' + H(p.note) + '</li>'; }).join('') + '</ul>' : '<p class="muted">この月はありませんでした。</p>') +
          '</section>';
      }).join('');
    }, function () { el.innerHTML = '<p class="muted">読み込めませんでした。しばらくして開き直してください。</p>'; });
  }

  // a referral link: /?ref=CODE is remembered on the device until the person registers
  try { var m = /[?&]ref=([A-Z2-9]{8})\b/.exec(location.search); if (m) localStorage.setItem('atomou.ref', m[1]); } catch (e) { /* ignore */ }
  if (A.page === 'my') pageMy();
  if (A.page === 'thanks') pageThanks();
  // on other pages: refresh the small copy once a day (it also counts as a day of use for the referral check), then the questionnaire bar
  var cached = readCache();
  if (A.page !== 'my' && cached && cached.at !== C.iso(A.TODAY) && !A.P.today) {
    call({ a: 'me' }).then(function (r) { if (r.ok) keep(r.data.member); else if (r.status === 401) keep(null); banner(); }, banner);
  } else {
    banner();
  }
  // when the member has the e-mail notices on, the days follow the device (same trigger as the push list)
  function followDevice() {
    if (A.page !== 'my') return;
    var cb = $('#m-notice');
    if (cb && cb.checked) noticeDates().then(function (dates) { var wk = $('#m-weekly'); return call({ a: 'update', notices: { on: true, weekly: !!(wk && wk.checked), dates: dates } }); }).catch(function () { /* next time */ });
  }
  document.addEventListener('atomou:changed', followDevice);
  document.addEventListener('atomou:saved', followDevice);
})();
