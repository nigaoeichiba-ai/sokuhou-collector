/* 商品比較 (/compare/<kind>/): the buttons that re-order the rows of the table.  The rows are already in the order of 総合点 in the page; without this script the table is still complete. */
(function () {
  "use strict";
  var list = document.getElementById("cmp-list");
  var bar = document.querySelector(".cmp-bar");
  if (!list || !bar) return;
  var rows = Array.prototype.slice.call(list.children);
  var KEYS = {
    score: function (a, b) { return num(b, "score") - num(a, "score"); },
    price: function (a, b) { return num(a, "price") - num(b, "price"); },
    rating: function (a, b) { return num(b, "rating") - num(a, "rating"); },
    points: function (a, b) { return num(b, "points") - num(a, "points"); }
  };
  function num(el, k) { return Number(el.getAttribute("data-" + k)) || 0; }
  function sortBy(key) {
    rows.slice().sort(function (a, b) { return KEYS[key](a, b) || num(a, "order") - num(b, "order"); }).forEach(function (r, i) {
      list.appendChild(r);
      var no = r.querySelector(".cmp-no");
      if (no) no.textContent = String(i + 1);
    });
    Array.prototype.forEach.call(bar.querySelectorAll(".cmp-sort"), function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-sort") === key ? "true" : "false"); });
  }
  bar.hidden = false;
  bar.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest(".cmp-sort");
    if (b && KEYS[b.getAttribute("data-sort")]) sortBy(b.getAttribute("data-sort"));
  });
})();
