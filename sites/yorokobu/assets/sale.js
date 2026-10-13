/* The sale bar (sites/yorokobu/sales.py makes the same sentences at build time; a test compares the two).
   The page may have been built hours ago: this redraws the bar for the minute of the visit.  Nothing is sent anywhere.  Times are Japan time (+09:00). */
(function () {
  "use strict";
  var STORE = { rakuten: "楽天市場", amazon: "Amazon" };
  var WEEKDAY = "日月火水木金土";             // Date#getUTCDay order
  var SOON_DAYS = 14, AHEAD_DAYS = 30, ORDER = { live: 0, entry: 1, soon: 2, ahead: 3 };
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  var HOSTS = ["hb.afl.rakuten.co.jp", "www.amazon.co.jp"];
  function safe(u) { try { var x = new URL(String(u), location.origin); return x.protocol === "https:" && HOSTS.indexOf(x.hostname) >= 0 ? x.href : ""; } catch (e) { return ""; } }
  function jst(ms) { return new Date(ms + 9 * 3600000); }                // read with the getUTC* methods: the clock of Japan
  function dayNo(ms) { var d = jst(ms); return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) / 86400000; }
  function label(ms) {
    var d = jst(ms);
    return (d.getUTCMonth() + 1) + "月" + d.getUTCDate() + "日(" + WEEKDAY.charAt(d.getUTCDay()) + ")" + d.getUTCHours() + "時" + (d.getUTCMinutes() ? d.getUTCMinutes() + "分" : "");
  }
  function phase(e, now) {
    var s = Date.parse(e.start), t = Date.parse(e.end);
    if (s <= now && now <= t) return "live";
    if (now > t) return null;
    if (e.entry && Date.parse(e.entry) <= now && now < s) return "entry";
    var days = dayNo(s) - dayNo(now);
    if (days <= SOON_DAYS) return "soon";
    if (days <= AHEAD_DAYS) return "ahead";
    return null;
  }
  function message(e, now) {
    var ph = phase(e, now);
    if (!ph) return null;
    var store = STORE[e.store], name = e.name, s = Date.parse(e.start), t = Date.parse(e.end), after = e.after || "";
    if (ph === "live") return { phase: ph, tag: "開催中", short: name + " " + label(t) + "まで", text: store + "で" + name + "を開催中です(" + label(t) + "まで)。プレゼントを買うなら、今がおすすめです。" + after, cta: store + "の" + name + "を見る" };
    var days = dayNo(s) - dayNo(now);
    var short = label(s) + "から " + name;
    var tag = days === 0 ? "きょう" : days === 1 ? "あす" : days + "日後";
    if (ph === "entry") return { phase: ph, tag: tag, short: short, text: label(s) + "から" + store + "の" + name + "です。エントリーは受付中です。それまでに贈り物を選んでおくとお得なタイミングで買えます。" + after, cta: name + "の詳細を見る" };
    if (ph === "soon") return { phase: ph, tag: tag, short: short, text: label(s) + "から" + store + "の" + name + "を開催します。それまでに贈り物を選んでおくとお得なタイミングで買えます。" + after, cta: name + "の詳細を見る" };
    return { phase: ph, tag: "開催予定", short: short, text: label(s) + "から" + store + "の" + name + "を開催します。日付が決まっている贈り物はその日に合わせて買うのも一案です。" + after, cta: name + "の詳細を見る" };
  }
  // at most one per shop: the one on now (the earliest to end), else the nearest coming one; two at most
  function choose(events, now, limit) {
    var best = {};
    events.forEach(function (e) {
      var m = message(e, now);
      if (!m) return;
      var key = [ORDER[m.phase], m.phase === "live" ? Date.parse(e.end) : Date.parse(e.start)];
      var cur = best[e.store];
      if (!cur || key[0] < cur.key[0] || (key[0] === cur.key[0] && key[1] < cur.key[1])) best[e.store] = { key: key, e: e, m: m };
    });
    return Object.keys(best).map(function (k) { return best[k]; }).sort(function (a, b) { return a.key[0] - b.key[0] || a.key[1] - b.key[1]; }).slice(0, limit || 2);
  }
  function item(x) {
    return '<p class="sale-item sale-' + x.m.phase + '" data-id="' + esc(x.e.id) + '"><span class="sale-tag">' + esc(x.m.tag) + '</span><span class="sale-short">' + esc(x.m.short) + '</span><span class="sale-text">' + esc(x.m.text) + "</span>" +
      '<a class="btn sale-btn" href="' + esc(safe(x.e.href)) + '" rel="sponsored nofollow noopener" target="_blank">' + esc(x.m.cta) + "</a></p>";
  }
  function render(events, now) { return choose(events, now).map(item).join(""); }
  // closing the bar is remembered for a day, per event and per phase (a sale that starts later is news again)
  var KEY = "yorokobu.sale.closed", DAY = 86400000;
  function closed() { try { return JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { return {}; } }
  function saveClosed(o) { try { localStorage.setItem(KEY, JSON.stringify(o)); } catch (e) { /* private window: the bar just comes back */ } }
  function init() {
    var bar = document.getElementById("sale-bar");
    if (!bar) return;
    var events;
    try { events = JSON.parse(bar.getAttribute("data-sales") || "[]"); } catch (e) { return; }
    var now = Date.now(), seen = closed(), shown = choose(events, now).filter(function (x) { return !(seen[x.e.id + ":" + x.m.phase] > now); });
    var box = bar.querySelector(".sale-items");
    if (!shown.length) { bar.hidden = true; return; }                   // everything is over since the page was built, or the visitor closed it today
    var html = shown.map(item).join("");
    if (box && box.innerHTML !== html) box.innerHTML = html;
    bar.hidden = false;
    if (!bar.querySelector(".sale-close")) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "sale-close"; b.setAttribute("aria-label", "このお知らせをきょうは閉じる"); b.textContent = "×";
      b.addEventListener("click", function () {
        var o = closed();
        shown.forEach(function (x) { o[x.e.id + ":" + x.m.phase] = Date.now() + DAY; });
        saveClosed(o);
        bar.hidden = true;
      });
      bar.querySelector(".sale-in").appendChild(b);
    }
  }
  window.YorokobuSale = { message: message, choose: choose, render: render, safe: safe };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
