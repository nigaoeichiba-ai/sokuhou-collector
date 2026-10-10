/* Screen guide: a short step-by-step tour that points at the real buttons of the page.  It never starts over the page by itself: a first-time visitor
   of the home page is shown an introduction (what the site is, three things it does) with a button to start the tour, and the first time another page is opened
   a slim bar offers the tour (not when ?today= is used, which the tests and screenshots use).  The "?" / "ガイド" buttons and the "使い方" link start it at any time.
   What was seen is kept in the visitor's own settings (prefs.tour, prefs.intro); nothing is sent anywhere. */
(function () {
  'use strict';
  var A = window.AtomouApp;
  if (!A) return;
  var $ = A.$, H = A.H, P = A.P, page = A.page;
  var TOURS = {
    home: [
      ['[data-block="search"] input[type="search"]', '日付や行事を検索できます。例: 年賀状'],
      ['[data-block="cats"] .chiprow a', 'ジャンルからも探せます。横にスライドすると続きが表示されます。'],
      ['#grid .card [data-act="save"]', '「予定に入れる」で、カレンダーに入ります。'],
      ['#grid .card', 'カードはドラッグで動かせます。スマホは長押ししてから動かせます。'],
      ['.tabbar a[href="/calendar/"], header.site nav a[href="/calendar/"]', '予定に入れた日は、ここに並びます。'],
      ['.tabbar a[href="/add/"], header.site nav a[href="/add/"]', '自分の予定や記念日は、ここから1行で記録できます。例: 明日 19時 デート']
    ],
    calendar: [
      ['.cal-tools', '「月」と「一覧」を切り替えます。'],
      ['.cal-grid', '日付を選ぶと、その日の予定とやることが下に表示されます。'],
      ['#day-panel .btn', 'ここから予定を追加できます。予定を押すと、メモとやることを書けます。']
    ],
    plan: [
      ['#p-memo', 'メモは自動で保存されます。'],
      ['#t-text', '「何日前までに何をするか」を書けます。期限の日はカレンダーとホームに出ます。'],
      ['.plan-card .c-act', '削除もここからできます。']
    ],
    add: [
      ['#s1 .tile', 'まず、どんな日かを選びます。デートや会議は予定です。']
    ],
    search: [
      ['#q', '言葉を入れると日付が出ます。ジャンルでも絞れます。'],
      ['[data-g-chip]', 'ジャンルを選ぶと、そのジャンルだけになります。']
    ]
  };

  /* The "ヒント" sheet: what this page does, in a few lines, on every page that has something to operate (the owner: "the pages are not yet intuitive").  The spotlight tour
     (TOURS) is offered from the sheet where the page has one.  Every line describes a thing the page really has. */
  var HINTS = {
    home: ['「さがす」に言葉を入れると、日付が出ます。例: 年賀状', 'カードの「予定に入れる」を押すと、カレンダーに入ります。', '好きな分野とお住まいの地域を選ぶと、ホームが自分向けになります。', '下の「ホームを編集」で、ブロックの並び替えや非表示ができます。'],
    search: ['言葉を短く入れると、見つかりやすくなります。', 'ジャンルを選ぶと、その下に中分類・小分類が出て、さらに絞れます。', '見つからない言葉は、そのまま自分の日として記録できます。'],
    category: ['上の中分類を押すと絞れます。選ぶと、小分類(題材)が出ます。', 'カードの「予定に入れる」で、自分の予定帳に入ります。', 'ページの下から、このジャンルの日をカレンダーアプリで購読できます。'],
    event: ['出典と確認日が載っています。公式の日付を、確かめてから使えます。', '「予定に入れる」で、自分の予定帳に入ります。', '共有のアイコンで、LINE・X・リンクのコピーなどで送れます。「カードにして送る」では、ひとこと付きのカードを作れます。', 'Google カレンダー・Outlook・ファイルで、ふだんのカレンダーアプリにも入れられます。'],
    my: ['記録した日と、予定に入れた日が並びます。', '通知をオンにすると、予定の日にお知らせが届きます。', 'カレンダーのファイル(.ics)の取り込み・書き出しと、バックアップができます。', '機種変更の前に、バックアップを書き出してください。'],
    plan: ['メモは、書くと自動で保存されます。', '「やること」に、何日前までに何をするかを書きます。期限の日は、カレンダーとホームに出ます。', '「知らせ」で、あと何日の知らせを選べます。この日の知らせは、スイッチで止められます。', '友だちに送るときは、下の共有のアイコンを使います。'],
    add: ['まず種類を選びます。日付と名前だけで記録できます。', '「明日 19時 デート」のように、1行で入れることもできます。', '日付は、年月日・年月・年だけ、から選べます。', '保存したあとで、メモとやることを足せます。'],
    calendar: ['「月」と「一覧」を切り替えられます。', '日付を選ぶと、その日の予定とやることが下に出ます。', '予定を押すと、メモとやることを書けます。'],
    interests: ['分野を押すと、ホームに「好きな分野の日」が並びます。', 'お住まいの都道府県を選ぶと、その地域の日もホームに出ます。', '好きな言葉は、自由に足せます。日付がまだない分野は「準備中」です。'],
    card: ['日付・題名・ひとことを入れて、カードを作ります。', '調べた文章を貼り付けて「日付を探す」を押すと、日付を拾ってカードに入れます。', '色(付箋の色もあります)や、こんなときのひな形を選べます。', 'リンクや画像で送れます。受け取った人は、1タップで自分の予定帳に入れられます。'],
    skins: ['選ぶと、すぐ見た目が変わります。', '文字を大きくする設定があります。', '暗い配色も選べます。'],
    manual: ['知りたい項目の見出しから探せます。', '画面のガイドは、実際のボタンを指しながら案内します。'],
    today: ['今日が、年のなんにち目か、年末・年度末まであと何日かが分かります。', '数字を押すと、その日を予定にしたり、記録したりできます。'],
    use: ['場面ごとの使い方です。自分に近いものを選んでください。', '各ページの「やってみる」から、そのまま記録できます。']
  };
  var steps = TOURS[page] || [];
  if (!steps.length) {   // a page without a tour of its own (the manual, a day's page...): the "ガイドを見る" button opens the home page's tour; the "ヒント" sheet is still here
    document.addEventListener('click', function (ev) { var b = ev.target.closest ? ev.target.closest('[data-guide]') : null; if (b) location.href = '/?guide=1'; });
  }
  var idx = 0, live = [], shade, hole, tip, btn;

  function seen() { var t = A.state().prefs.tour || {}; return !!t[page]; }
  function markSeen() { var st = A.state(); st.prefs.tour = st.prefs.tour || {}; st.prefs.tour[page] = true; A.persist(); }
  function visible(el) { var r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'; }
  function usable() {
    return steps.map(function (s) {
      var el = Array.prototype.slice.call(document.querySelectorAll(s[0])).filter(visible)[0];
      return el ? { el: el, text: s[1] } : null;
    }).filter(Boolean);
  }
  function place() {
    if (!live[idx]) return;
    var el = live[idx].el, r = el.getBoundingClientRect(), pad = 6;
    hole.style.left = Math.max(0, r.left - pad) + 'px'; hole.style.top = Math.max(0, r.top - pad) + 'px';
    hole.style.width = (r.width + pad * 2) + 'px'; hole.style.height = (r.height + pad * 2) + 'px';
    var below = (r.top + r.height / 2) < window.innerHeight * 0.5;
    tip.className = 'guide-tip ' + (below ? 'at-bottom' : 'at-top');
  }
  function show() {
    var step = live[idx], last = idx === live.length - 1;
    step.el.scrollIntoView({ block: 'center', behavior: 'instant' });  // not smooth: the spotlight must not lag behind the page
    tip.innerHTML = '<p class="g-n">' + (idx + 1) + ' / ' + live.length + '</p><p class="g-t">' + H(step.text) + '</p>' +
      '<div class="g-b"><button type="button" class="btn small ghost" data-g="close">閉じる</button>' +
      (idx > 0 ? '<button type="button" class="btn small ghost" data-g="prev">戻る</button>' : '') +
      '<button type="button" class="btn small" data-g="next">' + (last ? '終わり' : '次へ') + '</button></div>';
    place();
    var nb = tip.querySelector('[data-g="next"]');
    if (nb) nb.focus({ preventScroll: true });
  }
  function stop(done) {
    [shade, hole, tip].forEach(function (e) { if (e && e.parentNode) e.parentNode.removeChild(e); });
    shade = hole = tip = null;
    window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true); document.removeEventListener('keydown', onKey);
    markSeen();
    if (done) A.stat('act:guide_done');
  }
  function onKey(ev) { if (ev.key === 'Escape') stop(false); else if (ev.key === 'ArrowRight') go(1); else if (ev.key === 'ArrowLeft') go(-1); }
  function go(d) {
    if (!tip) return;
    var n = idx + d;
    if (n >= live.length) { stop(true); return; }
    if (n < 0) return;
    idx = n; show();
  }
  function start() {
    if (tip) return;
    live = usable();
    if (!live.length) return;
    idx = 0;
    shade = document.createElement('div'); shade.className = 'guide-shade';
    hole = document.createElement('div'); hole.className = 'guide-hole';
    tip = document.createElement('div'); tip.className = 'guide-tip'; tip.setAttribute('role', 'dialog'); tip.setAttribute('aria-label', 'この画面の使い方ガイド'); tip.tabIndex = -1;
    document.body.appendChild(shade); document.body.appendChild(hole); document.body.appendChild(tip);
    shade.addEventListener('click', function () { stop(false); });
    tip.addEventListener('click', function (ev) {
      var b = ev.target.closest ? ev.target.closest('[data-g]') : null;
      if (!b) return;
      var a = b.getAttribute('data-g');
      if (a === 'close') stop(false); else go(a === 'next' ? 1 : -1);
    });
    window.addEventListener('resize', place); window.addEventListener('scroll', place, true); document.addEventListener('keydown', onKey);
    A.stat('act:guide_start');
    show();
  }
  var sheet = null;
  function tipsFor() {
    var t = (HINTS[page] || []).slice();
    if (page === 'card' && A.tier && A.tier.on) t.push('自分で書けるカードは' + A.tier.limit() + '枚までです。使わないカードを消すと空きます。カードを人に送ると、書ける枚数がふえます。');
    return t;
  }
  function closeSheet() {
    if (!sheet) return;
    sheet.parentNode.removeChild(sheet); sheet = null;
    document.removeEventListener('keydown', onSheetKey);
    if (btn) btn.focus({ preventScroll: true });
  }
  function onSheetKey(ev) { if (ev.key === 'Escape') closeSheet(); }
  function openHints() {
    if (sheet) return closeSheet();
    if (tip) return;   // the spotlight tour is running
    sheet = document.createElement('div'); sheet.className = 'hint-sheet'; sheet.setAttribute('role', 'dialog'); sheet.setAttribute('aria-modal', 'true'); sheet.setAttribute('aria-label', 'このページのヒント');
    sheet.innerHTML = '<div class="hs-back" data-hs="close"></div><div class="hs-box" tabindex="-1"><h2>このページのヒント</h2><ul>' + tipsFor().map(function (x) { return '<li>' + H(x) + '</li>'; }).join('') + '</ul>' +
      '<p class="hs-act">' + (steps.length ? '<button type="button" class="btn small" data-hs="tour">画面で順に見る</button>' : '') + '<a class="btn small ghost" href="/manual/">くわしい使い方</a><button type="button" class="btn small ghost" data-hs="close">閉じる</button></p></div>';
    sheet.addEventListener('click', function (ev) {
      var b = ev.target.closest ? ev.target.closest('[data-hs]') : null;
      if (!b) return;
      var a = b.getAttribute('data-hs');
      closeSheet();
      if (a === 'tour') setTimeout(start, 50);
    });
    document.body.appendChild(sheet);
    document.addEventListener('keydown', onSheetKey);
    A.stat('act:hint_open');
    sheet.querySelector('.hs-box').focus({ preventScroll: true });
  }
  if (HINTS[page]) {
    btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'guide-btn'; btn.setAttribute('aria-label', 'このページのヒントを見る'); btn.innerHTML = '<span aria-hidden="true">?</span> ヒント';
    btn.addEventListener('click', openHints);
    document.body.appendChild(btn);   // wide screens: a button at the bottom right
    var icons = document.querySelector('.hicons');   // phones: in the header, next to search (a floating button covered calendar days and card buttons)
    if (icons) {
      var hb = document.createElement('button');
      hb.type = 'button'; hb.className = 'guide-icon'; hb.setAttribute('aria-label', 'このページのヒントを見る'); hb.innerHTML = '<span aria-hidden="true">?</span>';
      hb.addEventListener('click', openHints);
      icons.insertBefore(hb, icons.firstChild);
    }
  }
  document.addEventListener('click', function (ev) { var b = ev.target.closest ? ev.target.closest('[data-guide]') : null; if (b && steps.length) start(); });
  window.AtomouGuide = { start: start, steps: steps, hints: openHints };
  // the offer: the home page's introduction card, or a slim bar on the other pages (once; never in the tests, which pass ?today=)
  function offer() {
    var main = document.querySelector('main') || document.body, bar = document.createElement('div');
    bar.className = 'guide-offer'; bar.setAttribute('role', 'region'); bar.setAttribute('aria-label', 'この画面の使い方');
    bar.innerHTML = '<span>この画面の使い方を30秒で確認できます。</span><button type="button" class="btn small" data-o="go">見る</button><button type="button" class="btn small ghost" data-o="no">表示しない</button>';
    bar.addEventListener('click', function (ev) {
      var b = ev.target.closest ? ev.target.closest('[data-o]') : null;
      if (!b) return;
      bar.parentNode.removeChild(bar); markSeen();
      if (b.getAttribute('data-o') === 'go') start();
    });
    main.insertBefore(bar, main.firstChild);
  }
  function intro() {
    var box = document.getElementById('intro'), st = A.state();
    if (!box) return false;
    if (st.prefs.intro && P.intro !== '1') return false;
    box.hidden = false; document.body.classList.add('intro-open');   // the floating guide button would cover the text
    box.addEventListener('click', function (ev) {
      var b = ev.target.closest ? ev.target.closest('[data-intro]') : null;
      if (!b) return;
      box.hidden = true; document.body.classList.remove('intro-open'); st.prefs.intro = true; A.persist();
      A.stat(b.getAttribute('data-intro') === 'start' ? 'act:intro_tour' : 'act:intro_close');
      if (b.getAttribute('data-intro') === 'start') setTimeout(start, 150);
    });
    A.stat('act:intro_show');
    return true;
  }
  if (P.hint === '1' && HINTS[page]) setTimeout(openHints, 300);   // ?hint=1 opens the sheet (the tests and screenshots use it)
  if (P.guide === '1') setTimeout(start, 600);
  else if ((!P.today || P.intro === '1') && P.guide !== '0') {
    if (page === 'home') intro();
    else if (!seen() && !P.today) offer();
  }
})();
