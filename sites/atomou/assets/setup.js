/* First-visit setup (home page only): three short steps that make the home page the visitor's own - the genres they care about (one at least), the prefecture they live in
   (optional) and a first day of their own (they can try the form).  It sits at the top of the home page and does not hide the page (no full-screen overlay: the page stays readable for
   search engines and ad reviewers), and "あとで選ぶ" is always there.  What is chosen is kept in the visitor's own settings (prefs.genres, prefs.region, prefs.setup);
   it can be changed later from the home page ("ジャンルを選び直す") and from /interests/.  The tests and screenshots pass ?today=, which keeps the panel away unless ?setup=1. */
(function () {
  'use strict';
  var A = window.AtomouApp;
  if (!A || A.page !== 'home') return;
  var $ = A.$, H = A.H, P = A.P, CONF = A.CONF, S = A.state(), box = $('#setup');
  if (!box) return;
  var step = 1, sel = (S.prefs.genres || []).slice(), reg = S.prefs.region || '';
  A.setupOpen = false;

  function save(done) {
    S = A.state();
    S.prefs.genres = sel.filter(function (g) { return CONF.groups.indexOf(g) >= 0; });
    S.prefs.region = CONF.regions && CONF.regions.indexOf(reg) >= 0 ? reg : '';
    if (done) S.prefs.setup = true;
    A.persist();
  }
  var EX = { 'お金・税金・制度': '最低賃金・年金・確定申告', '買い物・料金・セール': '年賀状・セール・値上げ', 'スポーツ': '野球・マラソン・剣道', '学校・資格': '入試・英検・TOEIC', '天文・暦': '流星群・満月・節分',
    'おでかけ・旅行': '祭り・紅葉・イルミネーション', '通信・IT・アプリ': 'スマホ料金・アプリの終了', '趣味・ゲーム・アニメ': 'コミケ・将棋・手芸', 'エンタメ・音楽・賞': '紅白・ライブ・映画賞', '暮らし・健康・グルメ': '健康週間・結婚・食のイベント' };
  function marks(g) { var i = CONF.groups.indexOf(g) + 1; return '<span class="mark m' + i + '" data-g="' + i + '" aria-hidden="true"></span>'; }
  function head(n) { return '<h2 id="setup-h">はじめに、あなたに近い日を選びます</h2><p class="step-n" aria-live="polite">' + n + ' / 3</p>'; }
  function view() {
    var h = '';
    if (step === 1) {
      h = head(1) + '<p class="intro-lead">気になるジャンルを選んでください(いくつでも)。選んだジャンルの日が、ホームの先頭に並びます。</p><div class="chiprow wrap" role="group" aria-label="ジャンル">' +
        CONF.groups.map(function (g) { return '<button type="button" class="chip" data-g-pick="' + H(g) + '" aria-pressed="' + (sel.indexOf(g) >= 0) + '">' + marks(g) + '<span class="chip-t">' + H(g) + (EX[g] ? '<small>' + H(EX[g]) + '</small>' : '') + '</span></button>'; }).join('') + '</div>' +
        '<p class="intro-btns"><button type="button" class="btn" data-setup="next"' + (sel.length ? '' : ' disabled') + '>次へ</button> <button type="button" class="btn ghost" data-setup="later">あとで選ぶ</button></p>';
    } else if (step === 2) {
      h = head(2) + '<p class="intro-lead">お住まいの都道府県を選ぶと、近くの日もホームに出ます(選ばなくても使えます)。</p><div class="field"><label class="vh" for="setup-reg">都道府県</label><select id="setup-reg"><option value="">選ばない</option>' +
        (CONF.regions || []).map(function (r) { return '<option value="' + H(r) + '"' + (r === reg ? ' selected' : '') + '>' + H(r) + '</option>'; }).join('') + '</select></div>' +
        '<p class="intro-btns"><button type="button" class="btn" data-setup="next">次へ</button> <button type="button" class="btn ghost" data-setup="back">戻る</button></p>';
    } else {
      h = head(3) + '<p class="intro-lead">最後に、自分の日を1つ入れてみましょう。「あと○日」「もう○日」が出て、知らせやカードで友だちに送ることもできます。</p>' +
        '<nav class="chiprow wrap" aria-label="入れてみる日"><a class="chip" href="/add/?kind=birthday" data-setup="add">誕生日</a><a class="chip" href="/add/?kind=anniversary" data-setup="add">記念日</a><a class="chip" href="/add/?kind=event" data-setup="add">予定</a><a class="chip" href="/add/?kind=until" data-setup="add">楽しみな日・期限</a></nav>' +
        '<p class="intro-btns"><button type="button" class="btn" data-setup="done">はじめる</button> <button type="button" class="btn ghost" data-setup="back">戻る</button></p>' +
        '<p class="hint">使い方は、画面上の「?」からいつでも見られます。</p>';
    }
    box.innerHTML = h;
    var f = box.querySelector('button.btn:not([disabled]), select, a.chip');
    if (f && step > 1) f.focus({ preventScroll: true });
  }
  function close() { box.hidden = true; box.innerHTML = ''; document.body.classList.remove('intro-open'); A.setupOpen = false; }
  function finish(later) {
    save(true); A.stat(later ? 'act:setup_later' : 'act:setup_done');
    if (!later) { S = A.state(); S.prefs.intro = true; A.persist(); }   // the first-visit introduction is not shown again (it is, when the setup was put off)
    close();
    if (!later) location.replace('/');   // the home page is built again from the chosen genres
  }

  var first = !S.prefs.setup && (!P.today || P.setup === '1');
  if (P.setup === '1') { step = P.step === '2' ? 2 : P.step === '3' ? 3 : 1; if (!sel.length && step > 1) sel = [CONF.groups[0]]; }
  if (first) { A.setupOpen = true; box.hidden = false; document.body.classList.add('intro-open'); view(); A.stat('act:setup_show'); }
  else if (S.prefs.setup) {   // after the setup: a small way back, under the page's heading
    var re = $('#setup-redo');
    if (re) { re.hidden = false; }
  }
  box.addEventListener('click', function (ev) {
    var b = ev.target.closest ? ev.target.closest('[data-setup],[data-g-pick]') : null;
    if (!b) return;
    var g = b.getAttribute('data-g-pick');
    if (g) {
      var i = sel.indexOf(g);
      if (i >= 0) sel.splice(i, 1); else sel.push(g);
      b.setAttribute('aria-pressed', i >= 0 ? 'false' : 'true');   // changed in place: the focus stays on the chip
      var nx = box.querySelector('[data-setup="next"]'); if (nx) nx.disabled = !sel.length;
      return;
    }
    var a = b.getAttribute('data-setup');
    if (a === 'next') { if (step === 2) reg = ($('#setup-reg') || {}).value || ''; if (step === 1 && !sel.length) return; step++; view(); }
    else if (a === 'back') { if (step === 2) reg = ($('#setup-reg') || {}).value || ''; step = Math.max(1, step - 1); view(); }
    else if (a === 'done') finish(false);
    else if (a === 'later') finish(true);
    else if (a === 'add') { save(true); S = A.state(); S.prefs.intro = true; A.persist(); A.stat('act:setup_add'); }   // the link goes on to the form
  });
  var redo = $('#setup-redo');
  if (redo) redo.addEventListener('click', function (ev) {
    var b = ev.target.closest ? ev.target.closest('button') : null;
    if (!b) return;
    S = A.state(); sel = (S.prefs.genres || []).slice(); reg = S.prefs.region || ''; step = 1; redo.hidden = true;
    box.hidden = false; A.setupOpen = true; document.body.classList.add('intro-open'); view(); box.scrollIntoView({ block: 'start' });
  });
})();
