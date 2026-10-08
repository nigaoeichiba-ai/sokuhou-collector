/* あと何日、もう何日: members (free; a one-time code by e-mail, no password).  Talks to api/m.php; the session is an HttpOnly cookie.
   The e-mail notices are opt-in: only then do the days (and a short title each) go to the server, computed by push.js's planner. */
(function () {
  'use strict';
  var A = window.AtomouApp;
  if (!A || !A.CONF.members) return;
  var $ = A.$, H = A.H, S = A.state, API = '/api/m.php', MC = A.CONF.members || {}, TIERS = MC.tiers || {};
  function call(body) {
    return fetch(API, { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: JSON.stringify(Object.assign({ v: 1 }, body)), credentials: 'same-origin' })
      .then(function (r) { return r.status === 204 ? { ok: true, data: {} } : r.json().then(function (j) { return { ok: r.ok, status: r.status, data: j }; }); });
  }
  function fmt(iso) { var d = A.C.parse(iso); return d ? d[0] + '年' + d[1] + '月' + d[2] + '日' : ''; }
  function months(n) { return n % 12 === 0 ? (n / 12) + '年間' : n === 6 ? '半年間' : n + 'か月'; }
  function tierText(m) {
    if (m.free_until && m.free_until >= A.C.iso(A.TODAY)) return 'すべての機能を' + fmt(m.free_until) + 'まで使えます(' + (m.tier === 'referred' ? '紹介' : (TIERS[m.tier] || '先着')) + ')。';
    return '無料プランです。';
  }

  function noticeDates() {
    if (!window.AtomouPush) return Promise.resolve([]);
    return A.loadCatalog().then(function (cat) {
      var p = window.AtomouPush.plan(cat || []);
      return p.dates.map(function (x) { var k = x.d + '|' + x.s, lines = p.mirror[k] || []; return { d: x.d, s: x.s, t: lines.map(function (l) { return l.t; }).join(' / ').slice(0, 60) }; });
    });
  }

  function pageMy() {
    var box = $('#member-box');
    if (!box) return;
    box.hidden = false;
    var me = null, email = '';
    function view(html) { box.querySelector('.m-body').innerHTML = html; }
    function stepOut() {
      view('<p>会員になると、メールのお知らせと先着の特典を使えます。無料で、パスワードはありません。</p><div class="panel" id="m-pools" hidden></div>' +
        '<div class="field"><label for="m-email">メールアドレス</label><input type="email" id="m-email" autocomplete="email" inputmode="email" value="' + H(email) + '"></div>' +
        '<p><button type="button" class="btn" id="m-send">確認コードを送る</button></p>' +
        '<p class="hint">コードを入力すると、<a href="/terms/">利用規約</a>と<a href="/privacy/#members">プライバシーポリシー</a>に同意したことになります。</p>');
      call({ a: 'seats' }).then(function (r) {
        var el = $('#m-pools'), pools = (r.ok && r.data && r.data.pools) || [], open = pools.filter(function (x) { return x.left > 0; });
        if (!el) return;
        if (!open.length) { el.innerHTML = '<p>先着の枠は埋まりました。紹介リンクから登録すると、' + months(MC.ref) + 'すべての機能が無料です。</p>'; el.hidden = false; return; }
        el.innerHTML = '<p><b>先着の特典</b>(どちらかを選びます)</p>' + open.map(function (x, i) {
          return '<p><label class="lab pool"><input type="radio" name="m-want" value="' + H(x.id) + '"' + (i === open.length - 1 ? ' checked' : '') + '> <b>' + H(TIERS[x.id] || x.id) + '</b> 残り' + x.left + '名<br>' +
            '<span class="muted">登録日から' + months(x.months) + '、すべての機能が無料。' + (x.tester ? '条件: 登録の1週間後と1か月後に、1分のアンケートに答える。' : '条件はありません。') + '</span></label></p>';
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
          if (r.ok) { me = r.data.member; A.stat('act:member_login'); A.toast('ログインしました。'); stepIn(); return; }
          A.toast(r.data.error === 'wrong' ? 'コードが違います。' + (r.data.left > 0 ? 'あと' + r.data.left + '回。' : '') : 'コードの期限が切れました。もう一度送ってください。');
          if (r.data.error !== 'wrong') stepOut();
        }, function () { A.toast('確認できませんでした。'); });
      });
    }
    function surveyDue() {   // a tester's questionnaire: the first after a week, the second after a month
      if (!me || me.tier !== 'tester') return 0;
      var c = A.C.parse(me.created), done = me.surveys || [];
      if (!c) return 0;
      var days = A.C.totalDays(c, A.TODAY);
      if (days >= 30 && done.indexOf(2) < 0) return 2;
      if (days >= 7 && done.indexOf(1) < 0) return 1;
      return 0;
    }
    function surveyHtml() {
      var n = surveyDue();
      if (!n) return '';
      function opts(name, list) { return list.map(function (o, i) { return '<label class="lab"><input type="radio" name="' + name + '" value="' + o[0] + '"' + (i ? '' : ' checked') + '> ' + o[1] + '</label>'; }).join(''); }
      return '<div class="panel" id="m-survey"><h3>テスターのアンケート(' + n + '/2・1分)</h3>' +
        '<p>どのくらい使っていますか。</p>' + opts('s-freq', [['daily', 'ほぼ毎日'], ['weekly', '週に数回'], ['rarely', 'ときどき']]) +
        '<p>いちばん使う機能は。</p>' + opts('s-use', [['count', '日数を数える'], ['calendar', 'カレンダー'], ['todo', 'やること'], ['official', '公式の日付'], ['notice', '通知'], ['other', 'そのほか']]) +
        '<div class="field"><label for="s-text">分かりにくい所や、ほしい機能(任意)</label><textarea id="s-text" maxlength="300" rows="3"></textarea></div>' +
        '<p><button type="button" class="btn" id="s-send" data-n="' + n + '">送る</button></p></div>';
    }
    function wireSurvey() {
      var b = $('#s-send');
      if (!b) return;
      b.addEventListener('click', function () {
        var f = document.querySelector('input[name="s-freq"]:checked'), u = document.querySelector('input[name="s-use"]:checked');
        b.disabled = true;
        call({ a: 'survey', n: +b.getAttribute('data-n'), answers: { freq: f ? f.value : '', use: u ? u.value : '', text: $('#s-text').value } }).then(function (r) {
          if (r.ok) { me = r.data.member; A.stat('act:tester_survey'); A.toast('ご協力ありがとうございます。'); stepIn(); } else { A.toast('送れませんでした。'); b.disabled = false; }
        });
      });
    }
    function stepIn() {
      var link = location.origin + '/?ref=' + me.ref_code;
      view('<p><b>' + H(me.email) + '</b><br>' + H(tierText(me)) + '</p>' + surveyHtml() +
        '<div class="field"><label class="lab" for="m-notice"><input type="checkbox" id="m-notice"' + (me.notices.on ? ' checked' : '') + '> メールでもお知らせする(通知と同じ日・同じ時間)</label></div>' +
        '<p class="hint">オンにすると、知らせる日と予定の名前(短く)をサーバーに預かります。オフにすると消します。</p>' +
        '<h3>紹介</h3><p>この紹介リンクから登録した人は、' + months(MC.ref) + 'すべての機能を無料で使えます。1人の登録につき、あなたにも' + months(MC.give) + '足されます(' + MC.cap + '人まで)。</p>' +
        '<p><input type="text" readonly value="' + H(link) + '" id="m-link"> <button type="button" class="btn small ghost" id="m-copy">コピー</button></p>' +
        '<p><button type="button" class="btn small ghost" id="m-logout">ログアウト</button> <button type="button" class="btn small ghost" id="m-delete">退会する</button></p>');
      wireSurvey();
      $('#m-copy').addEventListener('click', function () { try { navigator.clipboard.writeText(link).then(function () { A.toast('コピーしました。'); }); } catch (e) { $('#m-link').select(); } });
      $('#m-notice').addEventListener('change', function () {
        var on = $('#m-notice').checked;
        noticeDates().then(function (dates) { return call({ a: 'update', notices: { on: on, dates: dates } }); }).then(function (r) {
          if (r.ok) { me = r.data.member; A.toast(on ? 'メールでもお知らせします。' : 'メールのお知らせを止めました。'); } else { A.toast('保存できませんでした。'); $('#m-notice').checked = !on; }
        });
      });
      $('#m-logout').addEventListener('click', function () { call({ a: 'logout' }).then(function () { me = null; A.toast('ログアウトしました。'); stepOut(); }); });
      $('#m-delete').addEventListener('click', function () {
        if (!window.confirm('会員の登録を消します。この端末の記録は残ります。よろしいですか。')) return;
        call({ a: 'delete' }).then(function () { me = null; A.toast('退会しました。'); stepOut(); });
      });
    }
    call({ a: 'me' }).then(function (r) { if (r.ok) { me = r.data.member; stepIn(); } else stepOut(); }, stepOut);
  }

  // a referral link: /?ref=CODE is remembered on the device until the person registers
  try { var m = /[?&]ref=([A-Z2-9]{8})\b/.exec(location.search); if (m) localStorage.setItem('atomou.ref', m[1]); } catch (e) { /* ignore */ }
  if (A.page === 'my') pageMy();
  // when the member has the e-mail notices on, the days follow the device (same trigger as the push list)
  document.addEventListener('atomou:changed', function () {
    if (A.page !== 'my') return;
    var cb = $('#m-notice');
    if (cb && cb.checked) noticeDates().then(function (dates) { return call({ a: 'update', notices: { on: true, dates: dates } }); }).catch(function () { /* next time */ });
  });
})();
