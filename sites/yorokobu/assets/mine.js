/* 「お気に入り」と「最近チェックした商品」 (kept in this browser only) and the count of which products are pressed.
   - Every page: a press on a product's shop button is added to the list "最近チェックした商品" (this browser only) and, once per product and day, counted as one
     press of that product (api/ask.php op "stat": a counter per product, nothing else; no address, no id, no time).  Nothing is counted for a browser that says
     "Do Not Track", for a script-driven browser, or for a press that a person did not make.
   - /favorites/ (#myitems): shows 気になるリスト and 最近チェックした商品 from this browser, with the products' present price and links from /list/items.json. */
(function () {
  "use strict";
  var FAV = "yorokobu.favs", RECENT = "yorokobu.recent", POP = "yorokobu.pop", MAX_RECENT = 30;
  function read(key, fallback) { try { var v = JSON.parse(localStorage.getItem(key) || "null"); return v === null ? fallback : v; } catch (e) { return fallback; } }
  function write(key, v) { try { localStorage.setItem(key, JSON.stringify(v)); } catch (e) { /* private window: nothing is kept */ } }
  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function yen(n) { return "¥" + Number(n).toLocaleString("ja-JP"); }
  // a link that comes from a data file (the products of /list/items.json) is drawn only when it goes to a shop of ours: https and a known host
  var HOSTS = ["hb.afl.rakuten.co.jp", "item.rakuten.co.jp", "search.rakuten.co.jp", "www.amazon.co.jp"];
  var IMG_HOSTS = ["thumbnail.image.rakuten.co.jp", "image.rakuten.co.jp"];     // Rakuten's own picture hosts (no Amazon picture is ever kept)
  function safeUrl(u) {
    try { var x = new URL(String(u), location.origin); return x.protocol === "https:" && HOSTS.indexOf(x.hostname) >= 0 ? x.href : ""; } catch (e) { return ""; }
  }
  function safeImg(u) {
    try { var x = new URL(String(u), location.origin); return x.protocol === "https:" && IMG_HOSTS.indexOf(x.hostname) >= 0 ? x.href : ""; } catch (e) { return ""; }
  }
  function dnt() { return navigator.doNotTrack === "1" || navigator.doNotTrack === "yes" || window.doNotTrack === "1" || navigator.msDoNotTrack === "1"; }
  var memDone = {};                                                      // the once-a-day rule when localStorage is not available
  function dayKey() { var d = new Date(); return d.getFullYear() * 10000 + (d.getMonth() + 1) * 100 + d.getDate(); }

  // ---- the key of a product for the counter: rakuten item codes ("shop:1000123") and Amazon ASINs, in the form the counter accepts
  var CODE = /^[A-Za-z0-9._:-]{3,64}$/;
  function counterKey(code, asin) {
    if (asin && /^[A-Z0-9]{10}$/.test(asin)) return "pop.a." + asin;
    if (code && CODE.test(code)) return "pop.r." + code;
    return null;
  }
  function beacon(key) {
    if (!key || dnt() || navigator.webdriver) return;
    var st = read(POP, {});
    var today = dayKey();
    if (st.day !== today) st = { day: today, done: [] };
    if (memDone[key] === today || st.done.indexOf(key) >= 0 || st.done.length >= 40) return;     // once per product and day; a person does not press forty products a day
    memDone[key] = today;
    st.done.push(key);
    write(POP, st);
    try { fetch("/api/ask.php", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ v: 1, op: "stat", k: [key] }), keepalive: true }).catch(function () {}); } catch (e) { /* not counted */ }
  }
  function remember(entry) {
    var list = read(RECENT, []).filter(function (x) { return x && x.id !== entry.id; });
    list.unshift(entry);
    write(RECENT, list.slice(0, MAX_RECENT));
  }
  function press(a) {
    var card = a && a.closest && a.closest("[data-code], [data-asin]");
    if (!card) return false;
    var code = card.getAttribute("data-code") || "", asin = card.getAttribute("data-asin") || "";
    var h = $("h3", card), nameEl = $(".pick-name", card);
    var name = ((nameEl && nameEl.textContent) || (h && h.textContent) || "").trim().slice(0, 80);
    var price = card.getAttribute("data-price") || "";
    if (name && (code || asin)) remember({ id: asin ? "a:" + asin : "r:" + code, code: code, asin: asin, name: name, price: price, t: Date.now() });
    beacon(counterKey(code, asin));
    return true;
  }
  document.addEventListener("click", function (e) {
    if (!e.isTrusted) return;                                              // a click made by a script is not a person's press
    var a = e.target.closest && e.target.closest('a[rel~="sponsored"]');
    if (a) press(a);
  }, true);

  // ---- the heart in the header: a link to /favorites/ with the number of saved products
  function header() {
    var nav = $("header.site nav");
    if (!nav || $(".fav-link", nav)) return;
    var n = read(FAV, []).length;
    var a = document.createElement("a");
    a.className = "fav-link"; a.href = "/favorites/"; a.setAttribute("aria-label", "お気に入り");
    a.innerHTML = '<span aria-hidden="true">♥</span>お気に入り' + (n ? ' <b class="fav-n">' + n + "</b>" : "");
    nav.appendChild(a);
  }

  // ---- /favorites/
  function card(it, extra) {
    it = Object.assign({}, it, { u: safeUrl(it.u), a: safeUrl(it.a), i: safeImg(it.i) });
    var rel = ' rel="sponsored nofollow noopener" target="_blank"';
    var attrs = ' data-code="' + esc(it.code || "") + '"' + (it.asin ? ' data-asin="' + esc(it.asin) + '"' : "") + ' data-price="' + esc(it.p || "") + '"';
    return '<li class="item"' + attrs + '><a class="item-img" href="' + esc(it.u) + '"' + rel + '><img src="' + esc(it.i) + '" alt="' + esc(it.n) + '" width="300" height="300" loading="lazy"></a>' +
      '<div class="item-body"><h3><a href="' + esc(it.u) + '"' + rel + ">" + esc(it.n) + '</a></h3><p class="price">' + yen(it.p) + "</p>" + (extra || "") +
      '<div class="item-btns"><a class="btn" href="' + esc(it.u) + '"' + rel + '>楽天市場で見る</a>' + (it.a ? '<a class="btn" href="' + esc(it.a) + '"' + rel + ' aria-label="Amazonで同じ商品を探す">Amazonで探す</a>' : "") + "</div></div></li>";
  }
  function amazonCard(x, extra) {                       // an Amazon product kept with ♡: its name and the Amazon link it had (no price, no picture: Amazon's rules)
    var u = safeUrl(x.url), asin = String(x.code).slice(2);
    if (!u || !/^[A-Z0-9]{10}$/.test(asin)) return plain({ name: x.name, price: "" });
    var rel = ' rel="sponsored nofollow noopener" target="_blank"';
    return '<li class="item item-az" data-asin="' + esc(asin) + '"><div class="item-body"><h3><a href="' + esc(u) + '"' + rel + ">" + esc(x.name) + '</a></h3><p class="fav-gone">価格・在庫はAmazonのページでご確認ください。</p>' +
      (extra || "") + '<div class="item-btns"><a class="btn" href="' + esc(u) + '"' + rel + '>Amazonで見る</a></div></div></li>';
  }
  function plain(x) {                                   // a product that is no longer on the site: its name and the price it had, and a search
    return '<li class="item gone"><div class="item-body"><h3>' + esc(x.name) + "</h3>" + (x.price ? '<p class="price">' + yen(x.price) + '<small>(保存したときの価格)</small></p>' : "") +
      '<p class="fav-gone">いまのサイトには載っていません。商品名で探してみてください。</p></div></li>';
  }
  function favorites(root) {
    var db = {};
    var favs = read(FAV, []), recent = read(RECENT, []);
    var favBox = $("#my-favs"), recBox = $("#my-recent");
    function paint() {
      favs = read(FAV, []); recent = read(RECENT, []);
      favBox.innerHTML = favs.length ? favs.map(function (x) {
        var it = db[x.code];
        var rm = '<button type="button" class="btn btn-sub fav-rm" data-code="' + esc(x.code) + '">リストから外す</button>';
        if (String(x.code).indexOf("a:") === 0) return amazonCard(x, rm);
        return it ? card({ code: x.code, n: it.n, p: it.p, i: it.i, u: it.u, a: it.a }, rm) : plain({ name: x.name, price: x.price });
      }).join("") : "";
      $("#my-favs-empty").hidden = favs.length > 0;
      $("#my-favs-wrap").hidden = favs.length === 0;
      var shownRecent = recent.filter(function (x) { return x.code && db[x.code]; }).slice(0, 12);
      recBox.innerHTML = shownRecent.map(function (x) { var it = db[x.code]; return card({ code: x.code, n: it.n, p: it.p, i: it.i, u: it.u, a: it.a }); }).join("");
      $("#my-recent-wrap").hidden = shownRecent.length === 0;
      $("#my-recent-empty").hidden = shownRecent.length > 0;
      $$(".fav-rm", favBox).forEach(function (b) {
        b.addEventListener("click", function () { write(FAV, read(FAV, []).filter(function (x) { return x.code !== b.getAttribute("data-code"); })); paint(); });
      });
      var n = $("#my-favs-n"); if (n) n.textContent = favs.length;
    }
    $("#my-recent-clear").addEventListener("click", function () { write(RECENT, []); paint(); });
    fetch(root.getAttribute("data-src")).then(function (r) { return r.json(); }).then(function (d) { db = d || {}; paint(); }).catch(function () { paint(); });
    // the list sent as a link (the same address /list/ reads); sharing is the one the page offers
    var send = $("#my-send");
    if (send) send.addEventListener("click", function () {
      var codes = read(FAV, []).slice(0, 12).map(function (x) { return encodeURIComponent(x.code); }).join(",");
      if (!codes) return;
      var url = location.origin + "/list/?c=" + codes;
      if (navigator.share) navigator.share({ title: "贈り物の候補", text: "贈り物の候補です。どれが合うか、意見をください。", url: url }).catch(function () {});
      else if (navigator.clipboard) { navigator.clipboard.writeText(url); send.textContent = "リンクをコピーしました"; }
    });
  }
  function init() {
    header();
    var root = $("#myitems");
    if (root) favorites(root);
  }
  window.YorokobuMine = { counterKey: counterKey, press: press, safeUrl: safeUrl, safeImg: safeImg };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
