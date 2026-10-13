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
  // the products of a group that fit the person (a title made for the other sex is left out) and the price (max / min in yen, either may be null)
  function pick(group, o) {
    o = o || {};
    var items = (group.items || []).filter(function (it) {
      return (!o.gender || !it.g || it.g === o.gender) && (o.max == null || it.p <= o.max) && (o.min == null || it.p >= o.min);
    });
    return items.slice(0, o.n || 4);
  }
  function card(it) {
    var rel = ' rel="sponsored nofollow noopener" target="_blank"';
    return '<li class="item"><a class="item-img" href="' + esc(it.u) + '"' + rel + '><img src="' + esc(it.i) + '" alt="' + esc(it.n) + '" width="300" height="300" loading="lazy"></a>' +
      '<div class="item-body"><h3><a href="' + esc(it.u) + '"' + rel + '>' + esc(it.n) + '</a></h3><p class="price">' + yen(it.p) + '</p>' +
      '<div class="item-btns"><a class="btn" href="' + esc(it.u) + '"' + rel + '>楽天市場で見る</a>' + (it.a ? '<a class="btn" href="' + esc(it.a) + '"' + rel + ' aria-label="Amazonで同じ商品を探す">Amazonで探す</a>' : "") + '</div></div></li>';
  }
  function amazon(group, o) {
    if (!group.a) return "";
    o = o || {};
    return group.a + (o.min ? "&low-price=" + o.min : "") + (o.max ? "&high-price=" + o.max : "");
  }
  // a block for one group: its products (within the price) and one button each for the Rakuten and the Amazon search
  function block(group, o) {
    o = o || {};
    var items = pick(group, o), rel = ' rel="sponsored nofollow noopener" target="_blank"';
    var cards = items.length ? '<ul class="items mini">' + items.map(card).join("") + "</ul>" : '<p class="ask-none">この予算に合う商品は今日の商品データには見つかりませんでした。下のボタンから探せます。</p>';
    var btns = '<a class="btn" href="' + esc(group.r) + '"' + rel + '>楽天市場で「' + esc(group.q) + '」を探す</a>' + (group.a ? '<a class="btn" href="' + esc(amazon(group, o)) + '"' + rel + '>Amazonで探す</a>' : "");
    return cards + '<p class="more">' + btns + "</p>";
  }
  window.YorokobuRec = { load: load, pick: pick, card: card, block: block, esc: esc, yen: yen };
})();
