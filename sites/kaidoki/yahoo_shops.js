/* 「いま割引が多いYahoo!ショッピングの店」の欄(sites/kaidoki/shops.py)。固定の文章は、ページの #shops に入っている(hidden)。
   /api/yahoo-shops.php から店ごとの数字をもらい、ジャンルごとの一覧にして、欄を出す。データが無い・古い・失敗のときは、欄は隠れたまま。
   出すのは店名・割引中の件数・割引率・終了日・店の評価と、店のページへの広告リンク(PR・nofollow sponsored noopener・別タブ)だけ。商品名・商品の価格・画像・順位は出さない。 */
(function () {
  var LABELS = __LABELS__, MAX_AGE = __MAX_AGE__, SID = "__VC_SID__", PID = "__VC_PID__";
  var box = document.getElementById("shops");
  if (!box || window.__yshopsRan) { return; }
  window.__yshopsRan = true;
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) { e.className = cls; } if (text) { e.textContent = text; } return e; }
  function num(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }
  function md(s) { var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || ""); return m ? parseInt(m[2], 10) + "月" + parseInt(m[3], 10) + "日" : ""; }
  function fresh(u) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(u || "");
    if (!m) { return false; }
    var age = (Date.now() - new Date(+m[1], +m[2] - 1, +m[3]).getTime()) / 86400000;
    return age >= -1 && age <= MAX_AGE + 1;
  }
  function good(h) { return typeof h === "string" && h.indexOf("//ck.jp.ap.valuecommerce.com/servlet/referral?sid=" + SID + "&pid=" + PID + "&vc_url=") === 0; }
  function shopLi(s) {
    var li = el("li"), a = document.createElement("a"), pix = document.createElement("img"), facts = [];
    a.href = s.h; a.target = "_blank"; a.rel = "nofollow sponsored noopener";
    a.appendChild(document.createTextNode(s.n));
    pix.src = "//ad.jp.ap.valuecommerce.com/servlet/gifbanner?sid=" + SID + "&pid=" + PID;      // the programme's 1x1 counter, as given
    pix.height = 1; pix.width = 0; pix.setAttribute("border", "0");
    a.appendChild(pix);
    var name = el("span", "shop-name"); name.appendChild(a);
    facts.push("割引中 " + num(s.c) + "件");
    facts.push(s.lo === s.hi ? s.hi + "%引き" : s.lo + "〜" + s.hi + "%引き");
    if (md(s.e)) { facts.push("最長" + md(s.e) + "まで"); }
    facts.push("店の評価 " + s.r.toFixed(2) + "(" + num(s.rc) + "件)");
    li.appendChild(name);
    li.appendChild(el("span", "shop-facts", facts.join(" ・ ")));
    return li;
  }
  function show(d) {
    var body = document.getElementById("shops-body"), n = 0;
    d.genres.forEach(function (g) {
      if (!g || !LABELS[g.s] || !g.shops || !g.shops.length) { return; }
      var ul = el("ul", "shops-list");
      g.shops.forEach(function (s) {
        if (!s || !good(s.h) || typeof s.n !== "string" || typeof s.c !== "number") { return; }
        ul.appendChild(shopLi(s));
      });
      if (!ul.childNodes.length) { return; }
      var h = el("h3", "", LABELS[g.s]);
      h.id = "shops-" + g.s;
      body.appendChild(h);
      body.appendChild(ul);
      n += 1;
    });
    if (!n) { return; }
    document.getElementById("shops-date").textContent = md(d.u) + "に確認した内容です。";
    box.hidden = false;
  }
  fetch("/api/yahoo-shops.php", { credentials: "same-origin" })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) { if (d && d.genres && d.genres.length && fresh(d.u)) { show(d); } })
    .catch(function () {});
})();
