/* Product shelves (sokuhou/mallstore.py).  A <div class="shelf" data-shelf="id" data-label="the site's own word for the product kind" hidden> asks /api/shelf.php for a few
   products and shows them as cards: the picture is the link (the affiliate link exactly as the API's product page gave it), the card says the site's own word (a shop's title is
   never shown and never linked), the price carries the day it was taken, the PR note is next to the cards.  With no product (or any error) the shelf stays hidden. */
(function () {
  if (window.__shelfRan) { return; }
  window.__shelfRan = true;
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) { e.className = cls; } if (text) { e.textContent = text; } return e; }
  function yen(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }
  function day(u) { var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(u || ""); return m ? m[1] + "年" + parseInt(m[2], 10) + "月" + parseInt(m[3], 10) + "日時点" : ""; }
  function link(href) { var a = document.createElement("a"); a.href = href; a.target = "_blank"; a.rel = "nofollow sponsored noopener"; return a; }
  function show(box, d) {
    var label = box.getAttribute("data-label") || "", list = el("ul", "shelf-list");
    d.items.forEach(function (it) {
      if (!it || typeof it.h !== "string" || it.h.indexOf("https://hb.afl.rakuten.co.jp/") !== 0 || typeof it.i !== "string" || it.i.indexOf("https://") !== 0) { return; }
      var li = el("li", "shelf-card"), pic = link(it.h), img = document.createElement("img"), btn = el("span", "btn shelf-btn"), b = link(it.h);
      pic.className = "shelf-img";
      img.src = it.i; img.alt = label;
      pic.appendChild(img);
      b.textContent = "楽天市場で見る";
      btn.appendChild(b);
      li.appendChild(pic);
      li.appendChild(el("span", "shelf-word", label));
      li.appendChild(el("span", "shelf-price", yen(it.p) + "円(" + (day(d.u) || "取得時点") + ")"));
      li.appendChild(btn);
      list.appendChild(li);
    });
    if (!list.childNodes.length) { return; }
    box.appendChild(el("p", "shelf-pr", "PR 楽天市場の商品へのリンクを含みます"));
    box.appendChild(list);
    box.appendChild(el("p", "shelf-note", "価格は上の日付の時点のものです。買う前に、リンク先で最新の価格と在庫を確かめてください。"));
    box.hidden = false;
  }
  function run() {
    var boxes = document.querySelectorAll(".shelf[data-shelf]");
    Array.prototype.forEach.call(boxes, function (box) {
      fetch("/api/shelf.php?s=" + encodeURIComponent(box.getAttribute("data-shelf")), { credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) { if (d && d.items && d.items.length) { show(box, d); } })
        .catch(function () {});
    });
  }
  if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", run); } else { run(); }
})();
