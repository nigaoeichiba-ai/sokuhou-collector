// よろこぶプレゼント: reveal on scroll, the gift finder, filters and sorting, the concierge keyword search, and the "気になるリスト".
// Everything is progressive: without JavaScript every product is visible and every link works.
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  // ---------------------------------------------------------------- reveal on scroll
  (function () {
    var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced || !("IntersectionObserver" in window)) return;
    document.documentElement.classList.add("js");
    var els = $$(".tile, .chip-ic, .idea, .keepsake, ul.check li, ul.warn li, .panel-grid li");
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { rootMargin: "0px 0px -6% 0px" });
    els.forEach(function (el, i) {
      el.classList.add("rv");
      el.style.transitionDelay = Math.min(i % 8, 7) * 40 + "ms";
      io.observe(el);
    });
    setTimeout(function () { els.forEach(function (el) { el.classList.add("in"); }); }, 1600); // never leave content hidden
  })();

  // ---------------------------------------------------------------- the gift finder (top page)
  window.YorokobuFinder = function (f) {
    var map = {};
    try { map = JSON.parse(f.getAttribute("data-map") || "{}"); } catch (e) {}
    var o = f.elements.o, r = f.elements.r, b = f.elements.b, msg = $(".finder-msg", f);
    function recipientsOf(occ) { return occ && map[occ] ? Object.keys(map[occ]) : null; }
    function occasionsOf(rec) { if (!rec) return null; return Object.keys(map).filter(function (k) { return map[k][rec]; }); }
    function refresh() {
      var allowedR = recipientsOf(o.value), allowedO = occasionsOf(r.value);
      Array.prototype.forEach.call(r.options, function (op) { op.disabled = !!op.value && !!allowedR && allowedR.indexOf(op.value) < 0; });
      Array.prototype.forEach.call(o.options, function (op) { op.disabled = !!op.value && !!allowedO && allowedO.indexOf(op.value) < 0; });
      if (r.value && r.options[r.selectedIndex].disabled) r.value = "";
      if (o.value && o.options[o.selectedIndex].disabled) o.value = "";
      var tiers = o.value && r.value && map[o.value] && map[o.value][r.value] ? map[o.value][r.value] : null;
      Array.prototype.forEach.call(b.options, function (op) { op.disabled = !!op.value && !!tiers && tiers.indexOf(op.value) < 0; });
      if (b.value && b.options[b.selectedIndex].disabled) b.value = "";
      msg.hidden = true;
    }
    o.addEventListener("change", refresh);
    r.addEventListener("change", refresh);
    f.addEventListener("submit", function (e) {
      e.preventDefault();
      var ov = o.value, rv = r.value, bv = b.value;
      if (!ov && !rv) { msg.textContent = "イベントか、贈る相手を、選んでください。"; msg.hidden = false; return; }
      if (ov && rv) { location.href = "/gift/" + ov + "-" + rv + "/" + (bv ? "?b=" + encodeURIComponent(bv) : "") + "#browse"; return; }
      location.href = ov ? "/occasion/" + ov + "/" : "/for/" + rv + "/";
    });
    refresh();
  };

  // ---------------------------------------------------------------- filters and sorting on a gift page
  function initBrowse() {
    var sec = $("#browse");
    if (!sec) return;
    var list = $(".grid-all", sec), items = $$("li.item", list), count = $(".count", sec), empty = $(".empty", sec);
    if (!list) return;
    var state = { tier: "", type: "", ship: false, gift: false, sort: "rank" };
    items.forEach(function (el, i) { el.setAttribute("data-order", i); });
    function num(el, k) { return Number(el.getAttribute("data-" + k)); }
    function apply() {
      var shown = items.filter(function (el) {
        return (!state.tier || el.getAttribute("data-tier") === state.tier) && (!state.type || el.getAttribute("data-type") === state.type) &&
          (!state.ship || el.getAttribute("data-ship") === "1") && (!state.gift || el.getAttribute("data-gift") === "1");
      });
      var key = {
        "rank": function (a, b) { return num(a, "order") - num(b, "order"); },
        "reviews": function (a, b) { return num(b, "reviews") - num(a, "reviews"); },
        "rating": function (a, b) { return num(b, "rating") - num(a, "rating") || num(b, "reviews") - num(a, "reviews"); },
        "price-asc": function (a, b) { return num(a, "price") - num(b, "price"); },
        "price-desc": function (a, b) { return num(b, "price") - num(a, "price"); }
      }[state.sort];
      items.forEach(function (el) { el.hidden = shown.indexOf(el) < 0; });
      shown.sort(key).forEach(function (el) { list.appendChild(el); });
      count.textContent = shown.length + "点を表示中";
      empty.hidden = shown.length > 0;
    }
    $$(".chipset", sec).forEach(function (set) {
      var name = set.getAttribute("data-filter");
      set.addEventListener("click", function (e) {
        var btn = e.target.closest(".chipbtn");
        if (!btn) return;
        state[name] = btn.getAttribute("data-v");
        $$(".chipbtn", set).forEach(function (x) { x.classList.toggle("on", x === btn); x.setAttribute("aria-pressed", x === btn ? "true" : "false"); });
        apply();
      });
    });
    $("[data-sort]", sec).addEventListener("change", function (e) { state.sort = e.target.value; apply(); });
    $("[data-ship]", sec).addEventListener("change", function (e) { state.ship = e.target.checked; apply(); });
    $("[data-gift]", sec).addEventListener("change", function (e) { state.gift = e.target.checked; apply(); });
    var m = /[?&]b=([^&#]+)/.exec(location.search); // preset from ?b=<budget>
    if (m) {
      var btn = $('.chipset[data-filter="tier"] .chipbtn[data-v="' + decodeURIComponent(m[1]) + '"]', sec);
      if (btn) btn.click();
    }
    apply();
  }

  // ---------------------------------------------------------------- the concierge: free words -> Rakuten search (affiliate redirect)
  function initConcierge() {
    $$("form.kw-form").forEach(function (f) {
      f.addEventListener("submit", function (e) {
        e.preventDefault();
        var q = f.elements.q.value.replace(/\s+/g, " ").trim();
        if (!q) { f.elements.q.focus(); return; }
        if (!/ギフト|プレゼント|贈り物/.test(q)) q += " ギフト";
        var aff = f.getAttribute("data-aff"), trk = f.getAttribute("data-trk");
        var target = "https://search.rakuten.co.jp/search/mall/" + encodeURIComponent(q) + "/";
        var url = "https://hb.afl.rakuten.co.jp/hgc/" + aff + "/" + (trk || "") + "?pc=" + encodeURIComponent(target) + "&m=" + encodeURIComponent(target);
        window.open(url, "_blank", "noopener");
      });
    });
  }

  // ---------------------------------------------------------------- 気になるリスト (kept in this browser only) and sharing
  function initFavorites() {
    var KEY = "yorokobu.favs", favs = [];
    try { favs = JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { favs = []; }
    var buttons = $$(".fav");
    if (!buttons.length) return;
    function save() { try { localStorage.setItem(KEY, JSON.stringify(favs)); } catch (e) {} }
    function has(code) { return favs.some(function (x) { return x.code === code; }); }
    var bar = document.createElement("div");
    bar.className = "fav-bar"; bar.hidden = true;
    bar.innerHTML = '<button type="button" class="fav-open">♥ 気になるリスト <b>0</b></button><div class="fav-panel" hidden><h3>気になるリスト</h3><ul></ul>' +
      '<p class="fav-note">このブラウザにだけ保存されます。</p><div class="fav-actions"><a class="btn" target="_blank" rel="noopener">LINEで送る</a><button type="button" class="btn btn-sub fav-copy">コピー</button></div></div>';
    document.body.appendChild(bar);
    var panel = $(".fav-panel", bar), ul = $("ul", panel);
    function text() {
      var lines = favs.map(function (x) { return "・" + x.name + "(¥" + Number(x.price).toLocaleString() + ")"; });
      return "贈り物の候補です。どれがよさそう?\n" + lines.join("\n") + "\n" + location.href.split("#")[0];
    }
    function paint() {
      $$(".item").forEach(function (li) {
        var b = $(".fav", li);
        if (!b) return;
        var on = has(li.getAttribute("data-code"));
        b.classList.toggle("on", on); b.textContent = on ? "♥" : "♡"; b.setAttribute("aria-pressed", on ? "true" : "false");
      });
    }
    function render() {
      $("b", bar).textContent = favs.length;
      bar.hidden = favs.length === 0;
      ul.innerHTML = "";
      favs.forEach(function (x) {
        var li = document.createElement("li");
        li.innerHTML = '<span></span><button type="button" aria-label="外す">×</button>';
        $("span", li).textContent = x.name + " ¥" + Number(x.price).toLocaleString();
        $("button", li).addEventListener("click", function () { favs = favs.filter(function (y) { return y.code !== x.code; }); save(); paint(); render(); });
        ul.appendChild(li);
      });
      $("a.btn", panel).href = "https://line.me/R/msg/text/?" + encodeURIComponent(text());
    }
    buttons.forEach(function (b) {
      b.addEventListener("click", function () {
        var code = b.closest(".item").getAttribute("data-code");
        if (has(code)) favs = favs.filter(function (x) { return x.code !== code; });
        else favs.push({ code: code, name: b.getAttribute("data-name"), price: b.getAttribute("data-price") });
        save(); paint(); render();
      });
    });
    $(".fav-open", bar).addEventListener("click", function () { panel.hidden = !panel.hidden; });
    $(".fav-copy", bar).addEventListener("click", function () {
      if (navigator.clipboard) navigator.clipboard.writeText(text());
      this.textContent = "コピーしました";
    });
    paint(); render();
  }

  function initShare() {
    $$(".share-btn.copy").forEach(function (b) {
      b.addEventListener("click", function () {
        var u = b.getAttribute("data-url");
        if (navigator.clipboard) navigator.clipboard.writeText(u);
        b.textContent = "コピーしました";
        setTimeout(function () { b.textContent = "リンクをコピー"; }, 2000);
      });
    });
  }


  // ---------------------------------------------------------------- たいせつな日メモ: saved only in this browser, shown as countdowns, exported as calendar files
  var MEMO_KEY = "yorokobu.memo";
  function memoLoad() { try { return JSON.parse(localStorage.getItem(MEMO_KEY) || "[]"); } catch (e) { return []; } }
  function memoSave(list) { try { localStorage.setItem(MEMO_KEY, JSON.stringify(list)); } catch (e) {} }
  function iso(d) { return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
  function today0() { var t = new Date(); return new Date(t.getFullYear(), t.getMonth(), t.getDate()); }
  function parseIso(s) { var p = s.split("-"); return new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2])); }
  function addDays(d, n) { var x = new Date(d.getTime()); x.setDate(x.getDate() + n); return x; }
  // the next date of an entry: a fixed-date occasion from the build's table, a personal one from its month and day
  function nextDate(e, fixed, now) {
    now = now || today0();
    if (fixed[e.occ]) {
      for (var i = 0; i < fixed[e.occ].length; i++) { var f = parseIso(fixed[e.occ][i]); if (f >= now) return f; }
      return null;
    }
    for (var y = now.getFullYear(); y <= now.getFullYear() + 1; y++) {
      var day = e.d; if (e.m === 2 && e.d === 29 && !(y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0))) day = 28;
      var c = new Date(y, e.m - 1, day);
      if (c >= now) return c;
    }
    return null;
  }
  function daysUntil(date, now) { return Math.round((date.getTime() - (now || today0()).getTime()) / 86400000); }
  function label(e, names) { return (e.name || names.rec[e.rec] || "") + "の" + (names.occ[e.occ] || ""); }
  function giftHref(e, pairs) { return pairs.indexOf(e.occ + "-" + e.rec) >= 0 ? "/gift/" + e.occ + "-" + e.rec + "/" : "/occasion/" + e.occ + "/"; }
  function icsEscape(t) { return String(t).replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n"); }
  function icsFold(line) {
    var out = [], cur = "", enc = new TextEncoder();
    Array.from(line).forEach(function (ch) {
      var limit = out.length ? 74 : 75;
      if (enc.encode(cur + ch).length > limit) { out.push(cur); cur = ch; } else cur += ch;
    });
    out.push(cur);
    return out.join("\r\n ");
  }
  function ymd(d) { return iso(d).replace(/-/g, ""); }
  function buildIcs(entries, data, now) {
    var lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//yorokobu-present.com//memo//JA", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:たいせつな日(よろこぶプレゼント)"];
    var stamp = ymd(now || today0()) + "T000000Z";
    entries.forEach(function (e) {
      var nd = nextDate(e, data.fixed, now); if (!nd) return;
      var url = data.base + giftHref(e, data.pairs);
      var title = label(e, data.names);
      lines.push("BEGIN:VEVENT", "UID:" + e.id + "@yorokobu-present.com", "DTSTAMP:" + stamp, "DTSTART;VALUE=DATE:" + ymd(nd), "DTEND;VALUE=DATE:" + ymd(addDays(nd, 1)));
      if (!data.fixed[e.occ]) lines.push("RRULE:FREQ=YEARLY");
      lines.push("SUMMARY:" + icsEscape(title), "DESCRIPTION:" + icsEscape(title + "。贈り物の候補を見る: " + url), "URL:" + url, "TRANSP:TRANSPARENT");
      [21, 7].forEach(function (n) {
        lines.push("BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:" + icsEscape(title + "まで" + (n === 21 ? "3週間" : "1週間") + "。贈り物を選びませんか?"), "TRIGGER:-P" + n + "D", "END:VALARM");
      });
      lines.push("END:VEVENT");
    });
    lines.push("END:VCALENDAR");
    return lines.map(icsFold).join("\r\n") + "\r\n";
  }
  function googleHref(e, data, now) {
    var nd = nextDate(e, data.fixed, now); if (!nd) return "#";
    var start = addDays(nd, -21), url = data.base + giftHref(e, data.pairs), title = label(e, data.names);
    var q = "action=TEMPLATE&text=" + encodeURIComponent(title + "まで3週間。贈り物を選ぼう") + "&dates=" + ymd(start) + "/" + ymd(addDays(start, 1)) +
      "&details=" + encodeURIComponent(title + "(" + (nd.getMonth() + 1) + "月" + nd.getDate() + "日)の贈り物を、そろそろ考えませんか?\n" + url) + (data.fixed[e.occ] ? "" : "&recur=" + encodeURIComponent("RRULE:FREQ=YEARLY"));
    return "https://calendar.google.com/calendar/render?" + q;
  }
  function download(name, text) {
    var blob = new Blob([text], { type: "text/calendar;charset=utf-8" }), a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }
  window.YorokobuMemo = { nextDate: nextDate, daysUntil: daysUntil, buildIcs: buildIcs, googleHref: googleHref, label: label };

  function initMemo() {
    var app = $("#memo-app");
    if (!app) return;
    var data = JSON.parse(app.getAttribute("data-json")), form = $(".memo-add", app), list = $(".memo-list", app), empty = $(".memo-empty", app), all = $(".memo-all", app);
    var fixedNote = $(".memo-fixed", app), when = $(".when", app);
    function onOcc() {
      var occ = form.elements.occ.value, fx = data.fixed[occ];
      when.hidden = !!fx; form.elements.date.required = !fx;
      if (fx) { var nd = nextDate({ occ: occ }, data.fixed); fixedNote.textContent = "この日は、毎年、日にちが決まっています。次は " + (nd.getMonth() + 1) + "月" + nd.getDate() + "日です。"; fixedNote.hidden = false; }
      else fixedNote.hidden = true;
    }
    form.elements.occ.addEventListener("change", onOcc);
    var q = new URLSearchParams(location.search);
    if (q.get("o") && form.elements.occ.querySelector('option[value="' + q.get("o") + '"]')) form.elements.occ.value = q.get("o");
    if (q.get("r") && form.elements.rec.querySelector('option[value="' + q.get("r") + '"]')) form.elements.rec.value = q.get("r");
    onOcc();
    function render() {
      var entries = memoLoad(), now = today0();
      var rows = entries.map(function (e) { var nd = nextDate(e, data.fixed, now); return { e: e, nd: nd, n: nd ? daysUntil(nd, now) : 9999 }; }).sort(function (a, b) { return a.n - b.n; });
      list.innerHTML = "";
      rows.forEach(function (r) {
        var li = document.createElement("li"); li.className = "memo-card" + (r.n <= 21 ? " soon" : "");
        var nd = r.nd;
        li.innerHTML = '<div class="row1"><b></b><span class="cd"></span></div><small></small><div class="acts"></div>';
        $("b", li).textContent = label(r.e, data.names);
        $(".cd", li).textContent = r.n === 0 ? "きょう!" : "あと" + r.n + "日";
        $("small", li).textContent = nd ? (nd.getMonth() + 1) + "月" + nd.getDate() + "日" + (r.n <= 21 ? "(そろそろ選びはじめましょう)" : "") : "";
        var acts = $(".acts", li);
        var go = document.createElement("a"); go.className = "go"; go.href = giftHref(r.e, data.pairs); go.textContent = "おすすめを見る"; acts.appendChild(go);
        var g = document.createElement("a"); g.href = googleHref(r.e, data, now); g.target = "_blank"; g.rel = "noopener"; g.textContent = "Googleカレンダー"; acts.appendChild(g);
        var ic = document.createElement("button"); ic.type = "button"; ic.textContent = ".ics(iPhoneなど)"; ic.addEventListener("click", function () { download("tasetsunahi.ics", buildIcs([r.e], data, now)); }); acts.appendChild(ic);
        var line = document.createElement("a"); line.target = "_blank"; line.rel = "noopener"; line.textContent = "LINEで相談";
        line.href = "https://line.me/R/share?text=" + encodeURIComponent(label(r.e, data.names) + "まで" + (r.n === 0 ? "きょう" : "あと" + r.n + "日") + "。そろそろ一緒に考えない?\n" + data.base + giftHref(r.e, data.pairs)); acts.appendChild(line);
        var del = document.createElement("button"); del.type = "button"; del.textContent = "削除";
        del.addEventListener("click", function () { memoSave(memoLoad().filter(function (x) { return x.id !== r.e.id; })); render(); }); acts.appendChild(del);
        list.appendChild(li);
      });
      empty.hidden = entries.length > 0; all.hidden = entries.length === 0;
    }
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var f = form.elements, occ = f.occ.value, e = { id: "m" + Date.now().toString(36) + Math.floor(Math.random() * 1000), name: f.name.value.trim(), rec: f.rec.value, occ: occ };
      if (!data.fixed[occ]) {
        if (!f.date.value) return;
        var dt = parseIso(f.date.value); e.m = dt.getMonth() + 1; e.d = dt.getDate();
      }
      var entries = memoLoad(); if (entries.length >= 40) entries.shift();
      entries.push(e); memoSave(entries); form.reset(); onOcc(); render();
    });
    $("[data-all-ics]", app).addEventListener("click", function () { download("tasetsunahi.ics", buildIcs(memoLoad(), data, today0())); });
    render();
  }

  // the top page strip: with something saved, the nearest days as countdown cards
  function initMemoStrip() {
    var strip = $("#memo-strip");
    if (!strip) return;
    var entries = memoLoad();
    if (!entries.length) return;
    var meta = document.querySelector("form.finder"), data = null;
    try { data = JSON.parse(strip.getAttribute("data-json") || "null"); } catch (e) {}
    if (!data) return;
    var now = today0();
    var rows = entries.map(function (e) { var nd = nextDate(e, data.fixed, now); return { e: e, n: nd ? daysUntil(nd, now) : 9999 }; }).sort(function (a, b) { return a.n - b.n; }).slice(0, 3);
    var inner = $(".memo-strip-in > div", strip);
    var html = '<h2>大切な日まで</h2><div class="cards">';
    rows.forEach(function (r) {
      html += '<a class="memo-card' + (r.n <= 21 ? " soon" : "") + '" href="' + giftHref(r.e, data.pairs) + '"><div class="row1"><b>' + label(r.e, data.names).replace(/[<>&]/g, "") + '</b><span class="cd">' + (r.n === 0 ? "きょう!" : "あと" + r.n + "日") + '</span></div><small>おすすめを見る</small></a>';
    });
    inner.innerHTML = html + '</div><p style="margin-top:8px"><a class="btn btn-sub" href="/memo/">たいせつな日メモ</a></p>';
  }

  // ---------------------------------------------------------------- tools: etiquette checker, calculators, persona quiz
  function norm(s) {
    // katakana -> hiragana, full-width -> half-width, lower case, no spaces: "クシ" and "くし" match the same entry
    return (s || "").toLowerCase().replace(/[ァ-ヶ]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 96); })
      .replace(/[！-～]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 65248); }).replace(/\s+/g, "");
  }
  function initTaboo() {
    var box = $("#tbcheck"); if (!box) return;
    var q = $('[name="q"]', box), o = $('[name="o"]', box), msg = $(".tb-msg", box), items = $$(".tb", box);
    function run() {
      var term = norm(q.value), occ = o.value, shown = 0;
      items.forEach(function (li) {
        var names = (li.getAttribute("data-names") || "").split(" ").map(norm).filter(Boolean), occs = (li.getAttribute("data-occ") || "").split(",");
        var okName = !term || names.some(function (n) { return n.indexOf(term) >= 0 || (n.length >= 2 && term.indexOf(n) >= 0); });
        var okOcc = !occ || !li.getAttribute("data-occ") || occs.indexOf(occ) >= 0;
        li.hidden = !(okName && okOcc); if (!li.hidden) shown++;
      });
      msg.textContent = (term || occ) ? (shown ? shown + "件、見つかりました。" : "とくに知られている注意は、見つかりませんでした。ふつうに贈って大丈夫なことが多いです。") : "下のリストから、品の名前でしぼりこめます。";
    }
    q.addEventListener("input", run); o.addEventListener("change", run);
    var pre = new URLSearchParams(location.search).get("q"); if (pre) { q.value = pre; run(); }
  }

  function yen(n) { return Math.round(n).toLocaleString("ja-JP") + "円"; }
  function initCalc() {
    var back = $('[data-calc="return"]'), split = $('[data-calc="split"]');
    if (back) {
      var a = $('[name="amount"]', back), range = $('[data-out="range"]', back);
      var run = function () { var v = parseFloat(a.value) || 0; range.textContent = v > 0 ? yen(v / 3) + " 〜 " + yen(v / 2) : "金額を入れてください"; };
      a.addEventListener("input", run); run();
    }
    if (split) {
      var tot = $('[name="total"]', split), ppl = $('[name="people"]', split), each = $('[data-out="each"]', split), note = $('[data-out="note"]', split);
      var run2 = function () {
        var t = parseFloat(tot.value) || 0, p = Math.max(1, parseInt(ppl.value, 10) || 1), e = Math.ceil(t / p / 10) * 10;
        each.textContent = "一人 " + yen(e);
        note.textContent = p + "人で、合計 " + yen(e * p) + " になります(10円単位に切り上げ)。";
      };
      tot.addEventListener("input", run2); ppl.addEventListener("input", run2); run2();
    }
  }

  function initQuiz() {
    var root = $("#quiz"); if (!root) return;
    var data = JSON.parse(root.getAttribute("data-json")), card = $(".quiz-card", root), start = $("[data-start]", root), i = 0, score = {};
    data.slugs.forEach(function (s) { score[s] = 0; });
    function show() {
      var q = data.questions[i];
      $(".quiz-step", card).textContent = "質問 " + (i + 1) + " / " + data.questions.length;
      $(".quiz-q", card).textContent = q.text;
      var box = $(".quiz-opts", card); box.innerHTML = "";
      q.options.forEach(function (op) {
        var b = document.createElement("button"); b.type = "button"; b.className = "quiz-opt"; b.textContent = op.label;
        b.addEventListener("click", function () {
          Object.keys(op.w).forEach(function (s) { score[s] += op.w[s]; });
          i++;
          if (i < data.questions.length) { show(); return; }
          var best = data.slugs.slice().sort(function (x, y) { return score[y] - score[x]; })[0];
          location.href = "/diagnosis/" + best + "/";
        });
        box.appendChild(b);
      });
    }
    start.addEventListener("click", function () { start.parentNode.hidden = true; card.hidden = false; show(); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initShare();
    var f = $("form.finder");
    if (f) window.YorokobuFinder(f);
    initBrowse(); initConcierge(); initFavorites(); initMemo(); initMemoStrip();
    initTaboo(); initCalc(); initQuiz();
  });
})();
