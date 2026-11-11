// Day counts and the print button. The build already wrote the right numbers for the day it ran; this corrects them to the reader's own day (Japan time).
(function () {
  "use strict";
  var f = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit" });
  var p = f.format(new Date()).split("-");
  var y = +p[0], m = +p[1], d = +p[2];
  var base = Date.UTC(y, m - 1, d);
  function diff(iso) {
    var a = iso.split("-");
    return Math.round((Date.UTC(+a[0], +a[1] - 1, +a[2]) - base) / 86400000);
  }
  var nodes = document.querySelectorAll(".nd");
  for (var i = 0; i < nodes.length; i++) {
    var el = nodes[i], k = el.getAttribute("data-k"), t = null;
    if (k === "md") t = m + "月" + d + "日";
    else if (k === "ymd") t = y + "年" + m + "月" + d + "日";
    else {
      var n = diff(el.getAttribute("data-d"));
      if (k === "rel") t = n > 0 ? n + "日後" : n === 0 ? "今日" : (el.getAttribute("data-p") || "過ぎた");
      else if (n >= 0) t = String(k === "weeks" ? Math.floor(n / 7) : n);
    }
    if (t !== null) el.textContent = t;
  }
  var btn = document.querySelectorAll("[data-print]");
  for (var j = 0; j < btn.length; j++) {
    btn[j].hidden = false;
    btn[j].addEventListener("click", function () { window.print(); });
  }

  // the switch view (month table / Gantt chart), the selected day and its panel, the today line of the Gantt chart
  var tracks = document.querySelectorAll(".gk[data-start]");
  for (var t = 0; t < tracks.length; t++) {
    var s = tracks[t].getAttribute("data-start").split("-"), en = tracks[t].getAttribute("data-end").split("-");
    var a0 = Date.UTC(+s[0], +s[1] - 1, +s[2]), a1 = Date.UTC(+en[0], +en[1] - 1, +en[2]) + 86400000;
    var line = tracks[t].querySelector(".gtoday");
    if (!line) continue;
    var pc = (base - a0) / (a1 - a0) * 100;
    if (pc < 0 || pc > 100) line.style.display = "none";
    else line.style.left = pc.toFixed(3) + "%";
  }
  var views = document.querySelectorAll(".kv");
  Array.prototype.forEach.call(views, function (kv) {
    kv.classList.add("js");
    var tabs = kv.querySelectorAll(".sw-b");
    Array.prototype.forEach.call(tabs, function (b) {
      b.addEventListener("click", function () {
        kv.setAttribute("data-view", b.getAttribute("data-v"));
        Array.prototype.forEach.call(tabs, function (o) { o.setAttribute("aria-selected", o === b ? "true" : "false"); });
      });
    });
    var days = kv.querySelectorAll("button.dc[data-day]");
    Array.prototype.forEach.call(days, function (c) {
      c.addEventListener("click", function () {
        Array.prototype.forEach.call(days, function (o) { o.setAttribute("aria-pressed", o === c ? "true" : "false"); });
        Array.prototype.forEach.call(kv.querySelectorAll(".dpanel"), function (p) {
          if (p.getAttribute("data-day") === c.getAttribute("data-day")) p.setAttribute("data-on", ""); else p.removeAttribute("data-on");
        });
      });
    });
  });
})();
