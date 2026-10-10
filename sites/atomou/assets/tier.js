/* The plan (free / plus) of this device's planner: how many cards a free planner may hold, how sharing earns more room, and what only the plus plan has.
   Everything here is decided on the device and is switched on by config "plans.on" (off: nothing is limited and nothing is shown).
   A free planner holds `free_cards` cards of its own writing (a deleted card gives its place back; changing a card is always possible) (an official day put in with ☆ is not counted, and a quiet day - a memorial - is never counted);
   every `shares_per_slot` times a day is sent, one more card fits (up to `extra_max`).  The count of sends is kept in this device's preferences: it is a nudge towards
   telling people about the site, not a lock (the server learns nothing about it).  The plus plan: no limit on cards, a card or a picture without the site's signature
   and link, any number of days before for the notices, and a choice of morning or evening for them.  Plus is read from the member's own record (member.js keeps a copy). */
(function () {
  'use strict';
  var A = window.AtomouApp;
  if (!A) return;
  var C = A.C, CF = (A.CONF && A.CONF.plans) || {}, ON = !!CF.on, FREE = Math.max(1, +CF.free_cards || 5), PER = Math.max(1, +CF.shares_per_slot || 3), MORE = Math.max(0, +CF.extra_max || 20), PLUS_OPEN = !!CF.plus_open;   // plus_open: the plus plan can be had (until then nothing speaks of it)
  var FREE_REMIND = Array.isArray(CF.free_remind) && CF.free_remind.length ? CF.free_remind : [7, 1];

  function member() { try { var m = JSON.parse(localStorage.getItem('atomou.member') || 'null'); return m && typeof m === 'object' ? m : null; } catch (e) { return null; } }
  function plus() {
    if (!ON) return true;   // plans are not switched on: everything is open
    var m = member();
    return !!(m && (m.plan === 'plus' || (/^\d{4}-\d{2}-\d{2}$/.test(String(m.free_until || '')) && m.free_until >= C.iso(A.TODAY))));
  }
  function used() {   // the cards the visitor wrote and still has (not the official days put in with ☆, not a quiet day); deleting a card gives its place back
    return A.state().entries.filter(function (e) { return !e.quiet; }).length;
  }
  function limit() { return FREE + Math.min(MORE, Math.floor((A.state().prefs.shares || 0) / PER)); }
  function room() { return (!ON || plus()) ? Infinity : Math.max(0, limit() - used()); }
  function say() {
    return '無料プランで書けるカードは、いま' + limit() + '枚までです(' + used() + '枚使っています)。' + (Math.floor((A.state().prefs.shares || 0) / PER) >= MORE ? '' : '人に送ると、' + PER + '回ごとに1枚ふえます。') + '使わないカードを消しても、空きます。' + (PLUS_OPEN ? 'プラスプランなら、枚数の制限はありません。' : '');
  }
  function blocked(n) {   // true (and the reason shown) when n more cards would not fit
    if (room() >= (n || 1)) return false;
    A.toast(say());
    return true;
  }
  function shared() {   // one more send (a link, a picture, a copy) was made
    if (!ON) return;
    var S = A.state(), before = Math.floor((S.prefs.shares || 0) / PER);
    S.prefs.shares = Math.min(9999, (S.prefs.shares || 0) + 1);
    A.persist();
    if (!plus() && Math.floor(S.prefs.shares / PER) > before && before < MORE) A.toast('カードを送ってくれてありがとうございます。書けるカードが1枚ふえました。');
  }
  function remindAllowed(r) { return plus() || FREE_REMIND.indexOf(r) >= 0; }

  function box() {
    var el = A.$('#tier-box');
    if (!el || !ON) return;
    var p = plus(), left = PER - ((A.state().prefs.shares || 0) % PER);
    el.innerHTML = '<h2 id="plan-h">プラン</h2><div class="panel"><p><b>' + (p ? 'プラスプラン' : '無料プラン') + '</b></p>' +
      (p ? '<p>カードの枚数に制限はありません。署名なしで送れます。知らせの日数と時間帯を、自由に決められます。</p>' :
        '<p>書けるカード: <b>' + used() + ' / ' + limit() + '枚</b>' + (Math.floor((A.state().prefs.shares || 0) / PER) >= MORE ? '(送って増やせる枚数の上限です)' : '(あと' + left + '回送ると、1枚ふえます)') + '</p><p class="hint">公式の日付を「予定に入れる」は、枚数に入りません。大切な人を思う日も、入りません。カードを消すと、その分だけ空きます。' + (PLUS_OPEN ? 'プラスプランは、制限なし・署名なし・知らせを自由に決められます。' : '') + '</p>') + '</div>';
  }
  if (A.page === 'my') box();
  document.addEventListener('atomou:saved', box);
  A.tier = { on: ON, plusOpen: PLUS_OPEN, plus: plus, used: used, limit: limit, room: room, blocked: blocked, shared: shared, remindAllowed: remindAllowed, freeRemind: FREE_REMIND };
})();
