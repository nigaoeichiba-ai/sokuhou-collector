/* Products of the site for the pages that work out what to give from answers (ask.js: the results of a survey, dock.js: the 診断ドック).
   ask/rec.json is made by the build: per interest group the site's best products of that kind, the price range of all of them and the searches.
   Nothing here sends anything anywhere; the links are the same Rakuten / Amazon links the rest of the site has. */
(function () {
  "use strict";
  var cache = null;
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function yen(n) { return "¥" + Number(n).toLocaleString("ja-JP"); }
  function load(url) {
    if (!cache) cache = fetch(url || "/ask/rec.json").then(function (r) { if (!r.ok) throw new Error("rec"); return r.json(); });
    return cache;
  }
  // the products of a group that fit the person (a title made for the other sex is left out) and the price (max / min in yen, either may be null): asked of api/items.php, a few at a time
  function pick(group, o) {
    o = o || {};
    if (!group.n_items) return Promise.resolve([]);
    var q = "?g=" + encodeURIComponent(group.id) + "&n=" + (o.n || 4) + (o.max != null ? "&max=" + Math.round(o.max) : "") + (o.min != null ? "&min=" + Math.round(o.min) : "") + (o.gender ? "&gender=" + encodeURIComponent(o.gender) : "");
    return fetch("/api/items.php" + q).then(function (r) { if (!r.ok) throw new Error("items"); return r.json(); }).then(function (j) { return (j && j.items) || []; }).catch(function () { return []; });
  }
  function card(it) {
    var rel = ' target="_blank" rel="nofollow sponsored noopener"';
    return '<li class="item"><div class="item-img"><a href="' + esc(it.u) + '"' + rel + '><img src="' + esc(it.i) + '" alt="' + esc(it.n || "楽天市場の商品ページ") + '"></a></div>' +
      '<div class="item-body">' + (it.n ? '<p class="item-blurb">' + esc(it.n) + '</p>' : "") + '<p class="price">' + yen(it.p) + '</p>' +
      '<div class="item-btns"><span class="btn"><a href="' + esc(it.u) + '"' + rel + '>楽天市場で見る</a></span></div></div></li>';
  }
  function amazon(group, o) {
    if (!group.a) return "";
    o = o || {};
    return group.a;                                                    // Amazon's own form of a link: the keyword and the tag only
  }
  // a block for one group: its products (within the price) and one button each for the Rakuten and the Amazon search
  var seq = 0;
  function block(group, o) {
    o = o || {};
    var rel = ' target="_blank" rel="nofollow sponsored noopener"', id = "recslot" + (++seq);
    // the products arrive a moment later into the slot (the caller puts this text on the page at once)
    pick(group, o).then(function (items) {
      var tries = 0;
      (function put() {
        var el = document.getElementById(id);
        if (!el) { if (tries++ < 60) requestAnimationFrame(put); return; }
        el.innerHTML = items.length ? '<ul class="items mini">' + items.map(card).join("") + "</ul>" : '<p class="ask-none">この予算に合う商品は今日の商品データには見つかりませんでした。下のボタンから探せます。</p>';
      })();
    });
    var cards = '<div id="' + id + '" class="rec-slot"></div>';
    var btns = '<span class="btn"><a href="' + esc(group.r) + '"' + rel + '>楽天市場で「' + esc(group.q) + '」を探す</a></span>' + (group.a ? '<span class="btn"><a href="' + esc(amazon(group, o)) + '"' + rel + '>Amazonで探す</a></span>' : "");
    return cards + '<p class="more">' + btns + "</p>";
  }
  window.YorokobuRec = { load: load, pick: pick, card: card, block: block, esc: esc, yen: yen };
})();
