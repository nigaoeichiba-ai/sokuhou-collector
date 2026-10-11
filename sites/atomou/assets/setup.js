/* First-visit setup (home page only): three short steps that make the home page the visitor's own - the fields they care about (at least one; a whole genre, or only a middle or small part of it),
   the prefecture they live in (optional) and a first day of their own (they can try the form).  It sits at the top of the home page and does not hide the page (no full-screen overlay: the page stays
   readable for search engines and ad reviewers), and "あとで選ぶ" is always there.  What is chosen is kept in the visitor's own settings (prefs.genres = whole genres, prefs.mids = "genre>middle",
   prefs.subs = "genre>middle>small", prefs.region, prefs.setup); it can be changed later from the home page ("ジャンルを選び直す") and from /interests/.
   The middle and small names come from the catalogue itself (what the site really has), fetched when the panel opens; without it the genres alone can still be chosen.
   The tests and screenshots pass ?today=, which keeps the panel away unless ?setup=1. */
(function () {
  'use strict';
  var A = window.AtomouApp;
  if (!A || A.page !== 'home') return;
  var $ = A.$, H = A.H, P = A.P, C = A.C, CONF = A.CONF, S = A.state(), box = $('#setup');
  if (!box) return;
  var step = 1, sel = (S.prefs.genres || []).slice(), selM = (S.prefs.mids || []).slice(), selS = (S.prefs.subs || []).slice(), reg = S.prefs.region || '';
  var tree = null, openG = '', openM = '';   // tree[genre][middle] = { n, s: { small: n } } from the catalogue
  A.setupOpen = false;

  function save(done) {
    S = A.state();
    S.prefs.genres = sel.filter(function (g) { return CONF.groups.indexOf(g) >= 0; });
    S.prefs.mids = selM.slice(0, 80);
    S.prefs.subs = selS.slice(0, 80);
    S.prefs.region = CONF.regions && CONF.regions.indexOf(reg) >= 0 ? reg : '';
    if (done) S.prefs.setup = true;
    A.persist();
    S = A.state();   // what was kept (a name the page does not know is dropped on the way in)
    selM = (S.prefs.mids || []).slice(); selS = (S.prefs.subs || []).slice();
  }
  function count() { return sel.length + selM.length + selS.length; }
  var EX = { 'お金・税金・制度': '最低賃金・年金・確定申告', '買い物・料金・セール': '年賀状・セール・値上げ', 'スポーツ': '野球・マラソン・剣道', '学校・資格': '入試・英検・TOEIC', '天気・災害': '流星群・満月・節分',
    'おでかけ・旅行': '祭り・紅葉・イルミネーション', 'スマホ・ネット・アプリ': 'スマホ料金・アプリの終了', '趣味・ゲーム・アニメ': 'コミケ・将棋・手芸', 'エンタメ・音楽・賞': '紅白・映画賞・ノーベル賞', '健康・くらし': '健康週間・予防接種・結婚', 'グルメ・食のイベント': 'ボジョレー・カニ漁・食べ歩き', '路線・交通': 'ダイヤ改正・運賃・観光列車', '経済・政治': '選挙・日銀・法律の施行', '国際': '国際会議・海外の行事', 'イベント・チケット': 'ライブ・展覧会・チケット発売' };
  function marks(g) { var i = CONF.groups.indexOf(g) + 1; return '<span class="mark m' + i + '" data-g="' + i + '" aria-hidden="true"></span>'; }
  function head(n) { return '<h2 id="setup-h">はじめに、1枚だけあなたの忘れたくない日をカードにします。</h2><p class="step-n" aria-live="polite">' + n + ' / 3</p>'; }
  function has(list, k) { return list.indexOf(k) >= 0; }
  function drop(list, test) { for (var i = list.length - 1; i >= 0; i--) if (test(list[i])) list.splice(i, 1); }
  function toggle(list, k) { var i = list.indexOf(k); if (i >= 0) list.splice(i, 1); else list.push(k); }

  function buildTree(cat) {
    var t = {};
    (cat || []).forEach(function (c) {
      if (c.status === 'ended' && !c.keep) return;
      var g = c.group, m = c.mid, s = c.subject;
      if (!g || !m || CONF.groups.indexOf(g) < 0) return;
      var gg = t[g] || (t[g] = {}), mm = gg[m] || (gg[m] = { n: 0, s: {} });
      mm.n++;
      if (s && s !== m) mm.s[s] = (mm.s[s] || 0) + 1;
    });
    return t;
  }
  function byCount(o, f) { return Object.keys(o).sort(function (a, b) { return f(o[b]) - f(o[a]) || (a < b ? -1 : 1); }); }

  function pickChip(attr, key, label, small, pressed, locked, mark) {
    return '<button type="button" class="chip" ' + attr + '="' + H(key) + '" aria-pressed="' + pressed + '"' + (locked ? ' aria-disabled="true"' : '') + '>' + (mark || '') +
      '<span class="chip-t">' + H(label) + (small ? '<small>' + H(small) + '</small>' : '') + '</span></button>';
  }
  function foldBtn(attr, key, open, what) {
    return '<button type="button" class="chip fold" ' + attr + '="' + H(key) + '" aria-expanded="' + open + '" aria-label="' + H(what) + '"><span aria-hidden="true">' + (open ? '▲' : '▼') + '</span></button>';
  }
  function panel() {
    var g = openG, mids = tree && tree[g];
    if (!g || !mids) return '';
    var whole = has(sel, g), names = byCount(mids, function (x) { return x.n; }), h = '<div class="pick-panel" role="group" aria-label="' + H(g) + 'の中分類">' +
      '<p class="hint">「' + H(g) + '」のなかから、気になる分野だけを選べます。' + (whole ? 'いまはジャンル全体を選んでいます。細かく選ぶには、上のジャンルの選択を外してください。' : '▼で、さらに細かく選べます。') + '</p><div class="chiprow wrap">';
    names.forEach(function (m) {
      var key = g + '>' + m, mid = whole || has(selM, key), isOpen = openM === m && !!Object.keys(mids[m].s).length;
      h += '<span class="pick">' + pickChip('data-m-pick', key, m, '' + mids[m].n, mid, whole) + (Object.keys(mids[m].s).length ? foldBtn('data-open-m', m, isOpen, '「' + m + '」の小分類を' + (isOpen ? '閉じる' : '開く')) : '') + '</span>';
    });
    h += '</div>';
    if (openM && mids[openM] && Object.keys(mids[openM].s).length) {
      var covered = whole || has(selM, g + '>' + openM), subs = byCount(mids[openM].s, function (x) { return x; });
      h += '<div class="pick-sub" role="group" aria-label="' + H(openM) + 'の小分類"><p class="hint">「' + H(openM) + '」のなかから選ぶ' + (covered ? '(上の選択に含まれています)' : '') + '</p><div class="chiprow wrap">' +
        subs.map(function (s) { var key = g + '>' + openM + '>' + s; return pickChip('data-s-pick', key, s, '' + mids[openM].s[s], covered || has(selS, key), covered); }).join('') + '</div></div>';
    }
    return h + '</div>';
  }
  function exampleCards() {
    var f = function (title, kind, g, days) { return A.cardHtml({ key: 'eg:' + days, title: title, date: C.iso(C.addDays(A.TODAY, days)), p: 'day', kind: kind, g: g, what: '', own: false, href: '' }); };
    return '<div class="eg-cards" role="group" aria-label="カードの例">' + f('友だちと旅行', '予定', A.KINDS.event.g, 30) + f('はじめて会った日', '記念日', A.KINDS.anniversary.g, -100) + '</div>';
  }
  function view(focus) {
    var h = '';
    if (step === 1) {
      h = head(1) + '<p class="intro-lead">気になるジャンルを選んでください(いくつでも)。選んだジャンルの日に関する情報が優先的に表示されます。' + (tree ? '右の▼から、中分類・小分類だけを選ぶこともできます。' : '') + '</p><div class="chiprow wrap" role="group" aria-label="ジャンル">' +
        (CONF.shown || CONF.groups).map(function (g) {
          return '<span class="pick">' + pickChip('data-g-pick', g, g, EX[g] || '', has(sel, g), false, marks(g)) + (tree && tree[g] ? foldBtn('data-open-g', g, openG === g, '「' + g + '」の中分類を' + (openG === g ? '閉じる' : '開く')) : '') + '</span>';
        }).join('') + '</div>' + panel() +
        '<p class="hint" id="pick-sum" aria-live="polite">' + (count() ? count() + '件を選んでいます。' : 'まだ選んでいません。') + '</p>' +
        '<p class="intro-btns"><button type="button" class="btn" data-setup="next"' + (count() ? '' : ' disabled') + '>次へ</button> <button type="button" class="btn ghost" data-setup="later">あとで選ぶ</button></p>';
    } else if (step === 2) {
      h = head(2) + '<p class="intro-lead">お住まいの都道府県を選ぶと、そのエリアのイベントなど地域の情報が優先的に表示されます。(選ばなくても使えます)</p><div class="field"><label class="vh" for="setup-reg">都道府県</label><select id="setup-reg"><option value="">選ばない</option>' +
        (CONF.regions || []).map(function (r) { return '<option value="' + H(r) + '"' + (r === reg ? ' selected' : '') + '>' + H(r) + '</option>'; }).join('') + '</select></div>' +
        '<p class="intro-btns"><button type="button" class="btn" data-setup="next">次へ</button> <button type="button" class="btn ghost" data-setup="back">戻る</button></p>';
    } else {
      h = head(3) + '<p class="intro-lead">最後に、未来や過去の忘れたくない日を1つ登録してみましょう。今日から数えて、未来の日(予定)は「あと○日」、過去の日(思い出)は「もう○日」と表示されます。この表示を「カード」と呼びます。○日に近づいたら通知の設定をしたり、カードを友だちに送ることもできます。</p>' +
        '<p class="hint">カードの例です(見本で、記録はされません)。</p>' + exampleCards() +
        '<nav class="chiprow wrap" aria-label="入れてみる日"><a class="chip" href="/add/?kind=birthday" data-setup="add">誕生日</a><a class="chip" href="/add/?kind=anniversary" data-setup="add">記念日</a><a class="chip" href="/add/?kind=event" data-setup="add">予定</a><a class="chip" href="/add/?kind=until" data-setup="add">楽しみな日・期限</a></nav>' +
        '<p class="intro-btns"><button type="button" class="btn" data-setup="done">はじめる</button> <button type="button" class="btn ghost" data-setup="back">戻る</button></p>' +
        '<p class="hint">使い方は、画面右下の「? ヒント」からいつでも見られます。</p>';
    }
    box.innerHTML = h;
    if (step === 3) Array.prototype.forEach.call(box.querySelectorAll('.eg-cards .card'), function (card) {
      Array.prototype.forEach.call(card.querySelectorAll('.c-act,.c-move'), function (x) { x.parentNode.removeChild(x); });
      A.fillCard(card);
    });
    var f = focus ? box.querySelector(focus) : null;
    if (!f && step > 1) f = box.querySelector('button.btn:not([disabled]), select, a.chip');
    if (f) f.focus({ preventScroll: true });
  }
  function close() { box.hidden = true; box.innerHTML = ''; document.body.classList.remove('intro-open'); A.setupOpen = false; }
  function finish(later) {
    save(true); A.stat(later ? 'act:setup_later' : 'act:setup_done');
    if (!later) { S = A.state(); S.prefs.intro = true; A.persist(); }   // the first-visit introduction is not shown again (it is, when the setup was put off)
    close();
    if (!later) location.replace('/');   // the home page is built again from the chosen genres
  }
  function loadTree() {
    if (tree || !A.loadCatalog) return;
    A.loadCatalog().then(function (cat) { if (!cat || tree) return; tree = buildTree(cat); if (A.setupOpen && step === 1) view(); });
  }

  var first = !S.prefs.setup && (!P.today || P.setup === '1');
  if (P.setup === '1') { step = P.step === '2' ? 2 : P.step === '3' ? 3 : 1; if (!count() && step > 1) sel = [CONF.groups[0]]; }
  if (first) { A.setupOpen = true; box.hidden = false; document.body.classList.add('intro-open'); view(); loadTree(); A.stat('act:setup_show'); }
  else if (S.prefs.setup) {   // after the setup: a small way back, under the page's heading
    var re = $('#setup-redo');
    if (re) { re.hidden = false; }
  }
  function sameFocus(b) {
    var attrs = ['data-g-pick', 'data-m-pick', 'data-s-pick', 'data-open-g', 'data-open-m'], i, v;
    for (i = 0; i < attrs.length; i++) { v = b.getAttribute(attrs[i]); if (v) return '[' + attrs[i] + '="' + v.replace(/"/g, '\\"') + '"]'; }
    return '';
  }
  box.addEventListener('click', function (ev) {
    var b = ev.target.closest ? ev.target.closest('[data-setup],[data-g-pick],[data-m-pick],[data-s-pick],[data-open-g],[data-open-m]') : null;
    if (!b) return;
    if (b.getAttribute('aria-disabled') === 'true') return;   // already included in a larger choice
    var g = b.getAttribute('data-g-pick'), m = b.getAttribute('data-m-pick'), s = b.getAttribute('data-s-pick'), og = b.getAttribute('data-open-g'), om = b.getAttribute('data-open-m');
    if (g) {
      toggle(sel, g);
      if (has(sel, g)) { drop(selM, function (k) { return k.indexOf(g + '>') === 0; }); drop(selS, function (k) { return k.indexOf(g + '>') === 0; }); }
      view(sameFocus(b)); return;
    }
    if (m) {
      toggle(selM, m);
      if (has(selM, m)) drop(selS, function (k) { return k.indexOf(m + '>') === 0; });
      view(sameFocus(b)); return;
    }
    if (s) { toggle(selS, s); view(sameFocus(b)); return; }
    if (og) { openG = openG === og ? '' : og; openM = ''; view(sameFocus(b)); return; }
    if (om) { openM = openM === om ? '' : om; view(sameFocus(b)); return; }
    var a = b.getAttribute('data-setup');
    if (a === 'next') { if (step === 2) reg = ($('#setup-reg') || {}).value || ''; if (step === 1 && !count()) return; step++; view(); }
    else if (a === 'back') { if (step === 2) reg = ($('#setup-reg') || {}).value || ''; step = Math.max(1, step - 1); view(); }
    else if (a === 'done') finish(false);
    else if (a === 'later') finish(true);
    else if (a === 'add') { save(true); S = A.state(); S.prefs.intro = true; A.persist(); A.stat('act:setup_add'); }   // the link goes on to the form
  });
  var redo = $('#setup-redo');
  if (redo) redo.addEventListener('click', function (ev) {
    var b = ev.target.closest ? ev.target.closest('button') : null;
    if (!b) return;
    S = A.state(); sel = (S.prefs.genres || []).slice(); selM = (S.prefs.mids || []).slice(); selS = (S.prefs.subs || []).slice(); reg = S.prefs.region || ''; step = 1; redo.hidden = true;
    box.hidden = false; A.setupOpen = true; document.body.classList.add('intro-open'); view(); loadTree(); box.scrollIntoView({ block: 'start' });
  });
})();
