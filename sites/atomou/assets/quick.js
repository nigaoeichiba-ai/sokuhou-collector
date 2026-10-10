/* Quick add and live search.
   - "かんたん入力": a bottom sheet opened by the + in the tab bar / the menu, the calendar's "この日に予定を追加" and so on.  One line of ordinary Japanese
     ("明日 19時 デート", "12/25 クリスマス", "来週の土曜 友だちと食事") is read for the date, the time and the kind; Enter saves.  The wizard (/add/) stays for the rest.
   - suggestions under the search box (home and genre pages) as you type.
   All of it works on this browser's data only. */
(function () {
  'use strict';
  var A = window.AtomouApp;
  if (!A) return;
  var C = A.C, H = A.H, $ = A.$, $$ = A.$$, TODAY = A.TODAY, KINDS = A.KINDS;

  /* ---------- reading one line ---------- */
  var WDS = '日月火水木金土';
  function wdIdx(a) { return ((C.toDays(a[0], a[1], a[2]) % 7) + 11) % 7; }
  function weekdayOf(week, idx) {  // week 0 = this week (Sun..Sat), 1 = next, 2 = the one after; Monday first is not assumed
    var start = C.addDays(TODAY, -wdIdx(TODAY));  // this week's Sunday
    return C.addDays(start, 7 * week + idx);
  }
  function clampDay(y, m, d) { return d <= C.dim(y, m) ? [y, m, d] : null; }
  var KEYS = [
    ['birthday', /誕生日|バースデー|生まれた日/], ['memorial', /命日|法要|法事|一周忌|三回忌|七回忌|回忌|月命日|納骨/], ['anniversary', /記念日|結婚|付き合|出会った|入籍/],
    ['since', /禁煙|禁酒|はじめた日|始めた日|スタート|開始した日/], ['until', /試験|締切|締め切り|提出|期限|旅行|ライブ|コンサート|発売|申込|申し込み|出願/],
    ['event', /デート|会議|打ち合わせ|打合せ|ミーティング|面談|病院|通院|歯医者|予約|食事|ランチ|ディナー|飲み会|集まり|授業|レッスン|出張|発表|面接/]
  ];
  function kindOf(t) { for (var i = 0; i < KEYS.length; i++) if (KEYS[i][1].test(t)) return KEYS[i][0]; return ''; }
  function guessKind(t) { return kindOf(t) || 'event'; }

  function parse(raw) {
    var s = String(raw || '').normalize('NFKC'), out = { title: '', date: null, time: '', kind: 'event', yearly: false, dateFound: false, timeFound: false };
    function cut(re) { var r = re.exec(s); if (!r) return null; s = s.slice(0, r.index) + ' ' + s.slice(r.index + r[0].length); return r; }
    var m, d = null, y = TODAY[0];
    if ((m = cut(/(\d{4})\s*[年\/\-.]\s*(\d{1,2})\s*[月\/\-.]\s*(\d{1,2})\s*日?/))) d = clampDay(+m[1], +m[2], +m[3]);
    else if ((m = cut(/(\d{1,2})\s*月\s*(\d{1,2})\s*日?/)) || (m = cut(/(?:^|\s)(\d{1,2})\s*\/\s*(\d{1,2})(?=\s|$|[^\d])/))) {
      var mo = +m[1], dd = +m[2];
      if (mo >= 1 && mo <= 12) {
        d = clampDay(y, mo, dd);
        if (d && C.cmp(d, TODAY) < 0) d = clampDay(y + 1, mo, dd);
      }
    }
    else if ((m = cut(/明々後日|しあさって/))) d = C.addDays(TODAY, 3);
    else if ((m = cut(/明後日|あさって/))) d = C.addDays(TODAY, 2);
    else if ((m = cut(/明日|あした|あす/))) d = C.addDays(TODAY, 1);
    else if ((m = cut(/今日|きょう|本日/))) d = TODAY;
    else if ((m = cut(/昨日|きのう/))) d = C.addDays(TODAY, -1);
    else if ((m = cut(/(今週|来週|再来週)\s*の?\s*([日月火水木金土])\s*曜?日?/))) d = weekdayOf(m[1] === '今週' ? 0 : m[1] === '来週' ? 1 : 2, WDS.indexOf(m[2]));
    else if ((m = cut(/([日月火水木金土])\s*曜日?/))) { d = weekdayOf(0, WDS.indexOf(m[1])); if (C.cmp(d, TODAY) < 0) d = C.addDays(d, 7); }
    else if ((m = cut(/(\d+)\s*日\s*後/))) d = C.addDays(TODAY, +m[1]);
    else if ((m = cut(/(\d+)\s*週間?\s*後/))) d = C.addDays(TODAY, 7 * +m[1]);
    else if ((m = cut(/(\d+)\s*[かヶケ]?\s*月\s*後/))) d = C.addMonths(TODAY, +m[1]);
    else if ((m = cut(/来月\s*の?\s*(\d{1,2})\s*日/))) { var nm = C.addMonths([TODAY[0], TODAY[1], 1], 1); d = clampDay(nm[0], nm[1], +m[1]); }
    else if ((m = cut(/(?:^|\s)(\d{1,2})\s*日(?!間|後)/))) {
      d = clampDay(TODAY[0], TODAY[1], +m[1]);
      if (!d || C.cmp(d, TODAY) < 0) { var n2 = C.addMonths([TODAY[0], TODAY[1], 1], 1); d = clampDay(n2[0], n2[1], +m[1]); }
    }
    if (d) { out.date = d; out.dateFound = true; }
    var tm;
    if ((tm = cut(/(午前|午後|朝|夜|夕方)?\s*(\d{1,2})\s*:\s*(\d{2})/)) || (tm = cut(/(午前|午後|朝|夜|夕方)?\s*(\d{1,2})\s*時\s*(?:(半)|(\d{1,2})\s*分?)?/))) {
      var hh = +tm[2], mi = tm[3] === '半' ? 30 : (+tm[3] || +tm[4] || 0), ap = tm[1];
      if ((ap === '午後' || ap === '夜' || ap === '夕方') && hh < 12) hh += 12;
      if (hh <= 23 && mi <= 59) { out.time = ('0' + hh).slice(-2) + ':' + ('0' + mi).slice(-2); out.timeFound = true; }
    }
    var t = s.replace(/[\s　]+/g, ' ').replace(/^[\s,、。・:：の]+|[\s,、。・:：]+$/g, '').replace(/^(に|は|を|で|から)\s*/, '').trim();
    out.kind = guessKind(t || raw);
    if (out.kind === 'birthday' || out.kind === 'anniversary' || out.kind === 'memorial') out.yearly = true;
    out.title = t.slice(0, 40) || KINDS[out.kind].t;
    return out;
  }

  /* ---------- the sheet ---------- */
  var sheet = null, back = null, dirty = { date: false, time: false, kind: false };
  function fmt(d) { return d ? d[1] + '月' + d[2] + '日(' + A.wd(d) + ')' : ''; }
  function summary(p, d) {
    if (!d) return '日付を選んでください。「今日」「明日」でも選べます。';
    var n = C.totalDays(TODAY, d);
    return fmt(d) + (p.time ? ' ' + p.time : '') + ' ・ ' + (n === 0 ? '今日' : n === 1 ? '明日' : n > 0 ? 'あと' + n + '日' : 'もう' + (-n) + '日');
  }
  function close() {
    if (!sheet) return;
    sheet.remove(); back.remove(); sheet = back = null; document.removeEventListener('keydown', onKey);
  }
  function onKey(ev) { if (ev.key === 'Escape') close(); }
  function open(preset) {
    if (sheet) return;
    preset = preset || {};
    dirty = { date: false, time: false, kind: false };
    back = document.createElement('div'); back.className = 'sheet-back';
    sheet = document.createElement('div'); sheet.className = 'sheet'; sheet.setAttribute('role', 'dialog'); sheet.setAttribute('aria-modal', 'true'); sheet.setAttribute('aria-label', '予定を記録する');
    sheet.innerHTML = '<div class="sheet-grip" aria-hidden="true"></div>' +
      '<label class="vh" for="qa-text">予定の内容</label>' +
      '<input id="qa-text" type="text" autocomplete="off" enterkeyhint="done" maxlength="60" placeholder="例: 明日 19時 デート" value="' + H(preset.title || '') + '">' +
      '<p class="qa-sum" id="qa-sum" aria-live="polite"></p>' +
      '<div class="qa-chips" role="group" aria-label="日付を選ぶ"><button type="button" class="chip" data-qd="0">今日</button><button type="button" class="chip" data-qd="1">明日</button>' +
      '<button type="button" class="chip" data-qd="sat">今週末</button><button type="button" class="chip" data-qd="next">来週</button></div>' +
      '<div class="qa-row"><label>日付<input type="date" id="qa-date"></label><label>時刻<input type="time" id="qa-time"></label>' +
      '<label>種類<select id="qa-kind">' + Object.keys(KINDS).map(function (k) { return '<option value="' + k + '">' + H(KINDS[k].t) + '</option>'; }).join('') + '</select></label></div>' +
      '<div class="qa-ex" aria-label="例"><button type="button" class="chip" data-ex="明日 19時 デート">明日 19時 デート</button><button type="button" class="chip" data-ex="12/25 クリスマス">12/25 クリスマス</button>' +
      '<button type="button" class="chip" data-ex="来週の土曜 友だちと食事">来週の土曜 友だちと食事</button></div>' +
      '<div class="qa-act"><button type="button" class="btn" id="qa-save">残す</button><a class="btn ghost" href="/add/">詳しく</a></div>';
    document.body.appendChild(back); document.body.appendChild(sheet);
    var txt = $('#qa-text'), dt = $('#qa-date'), tm = $('#qa-time'), kd = $('#qa-kind');
    if (preset.date) { dt.value = C.iso(preset.date); dirty.date = true; }
    function refresh() {
      var p = parse(txt.value);
      if (!dirty.date) dt.value = p.date ? C.iso(p.date) : '';
      if (!dirty.time) tm.value = p.time || '';
      if (!dirty.kind) kd.value = p.kind;
      var d = C.parse(dt.value);
      $('#qa-sum').textContent = summary({ time: tm.value }, d);
      return { p: p, d: d };
    }
    function save() {
      var r = refresh(), d = r.d;
      if (!d) { $('#qa-sum').textContent = '日付を選んでください。「今日」「明日」でも選べます。'; dt.focus(); return; }
      var kind = kd.value, k = KINDS[kind] || KINDS.memo, st = A.state(), e = {
        id: A.uid(), title: r.p.title, date: C.iso(d), precision: 'day', kind: kind, quiet: !!k.quiet, yearly: !!k.yearly || r.p.yearly, every100: false,
        alarm: k.quiet ? 'none' : st.prefs.alarm, created: C.iso(TODAY), time: kind === 'event' ? (tm.value || '') : ''
      };
      if (e.title === KINDS[kind].t && txt.value.trim() === '') e.title = k.t;
      if (A.tier && A.tier.blocked(1) && !k.quiet) return;
      st.entries.push(e); A.stat('act:add:' + kind); A.stat('act:quick');
      if (!A.persist()) return;
      close(); done(e);
    }
    txt.addEventListener('input', refresh);
    [dt, tm, kd].forEach(function (el) { el.addEventListener('change', function () { dirty[el === dt ? 'date' : el === tm ? 'time' : 'kind'] = true; refresh(); }); });
    txt.addEventListener('keydown', function (ev) { if (ev.key === 'Enter') { ev.preventDefault(); save(); } });
    sheet.addEventListener('click', function (ev) {
      var b = ev.target.closest ? ev.target.closest('button') : null;
      if (!b) return;
      if (b.id === 'qa-save') save();
      else if (b.hasAttribute('data-qd')) {
        var v = b.getAttribute('data-qd'), d;
        if (v === 'sat') d = weekdayOf(0, 6); else if (v === 'next') d = weekdayOf(1, 1); else d = C.addDays(TODAY, +v);
        if (C.cmp(d, TODAY) < 0) d = C.addDays(d, 7);
        dt.value = C.iso(d); dirty.date = true; refresh();
      } else if (b.hasAttribute('data-ex')) { txt.value = b.getAttribute('data-ex'); dirty = { date: false, time: false, kind: false }; refresh(); txt.focus(); }
    });
    back.addEventListener('click', close);
    document.addEventListener('keydown', onKey);
    refresh();
    setTimeout(function () { txt.focus(); }, 30);
    A.stat('act:quick_open');
  }

  /* ---------- the notice after saving: open it, put it back, or add the next one ---------- */
  function done(e) {
    var old = $('#toast'); if (old) old.remove();
    var t = document.createElement('div'); t.id = 'toast'; t.className = 'toast act'; t.setAttribute('role', 'status');
    t.innerHTML = '<span>「' + H(e.title) + '」を ' + H(fmt(C.parse(e.date))) + (e.time ? ' ' + H(e.time) : '') + ' に記録しました</span>' +
      '<a class="btn small" href="/plan/?key=m:' + H(e.id) + '">開く</a><button type="button" class="btn small ghost" data-undo="1">元に戻す</button>';
    document.body.appendChild(t);
    var timer = setTimeout(function () { t.remove(); }, 7000);
    t.addEventListener('click', function (ev) {
      if (!ev.target.closest || !ev.target.closest('[data-undo]')) return;
      clearTimeout(timer);
      var st = A.state();
      st.entries = st.entries.filter(function (x) { return x.id !== e.id; });
      A.persist(); t.remove(); A.toast('元に戻しました。');
      document.dispatchEvent(new CustomEvent('atomou:changed'));
    });
    document.dispatchEvent(new CustomEvent('atomou:changed'));
  }

  // the "+" and the menu item open the sheet; the link to /add/ stays for other uses (and when scripts do not run)
  document.addEventListener('click', function (ev) {
    var a = ev.target.closest ? ev.target.closest('a[href]') : null;
    if (!a || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.button) return;
    var href = a.getAttribute('href'), m = /^\/add\/(?:\?kind=event&date=(\d{4}-\d{2}-\d{2}))?$/.exec(href);
    if (!m || !(a.closest('header.site') || a.closest('.tabbar') || a.closest('.day-panel') || a.closest('.cal-tools'))) return;
    ev.preventDefault();
    open(m[1] ? { date: C.parse(m[1]) } : {});
  });
  window.AtomouQuick = { open: open, parse: parse, kindOf: kindOf };
  if (A.P.quick === '1') setTimeout(function () { open({}); }, 300);

  /* ---------- suggestions under the search box ---------- */
  function wireSuggest() {
    var q = $('#q'), box = $('#suggest');
    if (!q || !box || A.page === 'search') return;
    var cat = null;
    function hide() { box.hidden = true; box.innerHTML = ''; }
    function show() {
      var v = q.value.trim();
      if (!cat) return;
      if (!v) {
        box.innerHTML = '<p class="sg-h">よく検索される言葉</p><div class="chips">' + ['年賀状', 'ふるさと納税', '共通テスト', '流星群', '最低賃金', '確定申告', '将棋', 'ドラフト'].map(function (w) {
          return '<a class="chip" href="/search/?q=' + encodeURIComponent(w) + '">' + H(w) + '</a>';
        }).join('') + '</div>';
        box.hidden = false; return;
      }
      var hits = A.matchCat(cat, v, 6);
      if (!hits.length) { box.innerHTML = '<p class="sg-h">見つかりません。言葉を短くするか、ジャンルから探してください。</p>'; box.hidden = false; return; }
      box.innerHTML = hits.map(function (c) {
        var n = C.totalDays(TODAY, C.parse(c.date));
        return '<a class="sg" href="/e/' + H(c.id) + '/"><span class="sg-t">' + H(c.title) + '</span><span class="sg-m">' + H(c.subject || c.category) + ' ・ ' + H(fmt(C.parse(c.date))) + ' ・ ' +
          (n === 0 ? '今日' : n > 0 ? 'あと' + n + '日' : 'もう' + (-n) + '日') + '</span></a>';
      }).join('') + '<a class="sg sg-all" href="/search/?q=' + encodeURIComponent(v) + '">「' + H(v) + '」の結果をすべて見る</a>';
      box.hidden = false;
    }
    var t;
    q.addEventListener('input', function () { clearTimeout(t); t = setTimeout(show, 60); });
    q.addEventListener('focus', function () { A.loadCatalog().then(function (c) { cat = c || []; show(); }); });
    document.addEventListener('click', function (ev) { if (!ev.target.closest('.sbox')) hide(); });
    q.addEventListener('keydown', function (ev) { if (ev.key === 'Escape') hide(); });
  }
  wireSuggest();
})();
