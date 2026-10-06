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

  document.addEventListener("DOMContentLoaded", function () {
    initShare();
    var f = $("form.finder");
    if (f) window.YorokobuFinder(f);
    initBrowse(); initConcierge(); initFavorites();
  });
})();
