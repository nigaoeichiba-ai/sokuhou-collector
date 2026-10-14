// みんなのイラスト: the print makers ("カレンダー", "名前入り印刷": name tags, seat cards, certificates, and the 年賀状 on a postcard).
// A page is drawn on a canvas (A4 at 150 dpi; a postcard, 100 x 148 mm, at 300 dpi) in this browser from an illustration of the library and what is typed here; it can be saved as a PNG or printed.
// Nothing typed here leaves the browser.  Uses the search of app.js (window.minnaApp) to pick the illustration.
// (app.js defines window.minnaApp when it runs; this file is loaded before it, so the work starts at DOMContentLoaded.)
(function () {
  "use strict";
  function main() {
  var A = window.minnaApp, root = document.getElementById("maker-app"); if (!A || !root) return;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var kind = root.getAttribute("data-kind");
  var W = 1240, H = 1754;                                       // A4 portrait at 150 dpi
  if (kind === "nenga") { W = 1181; H = 1748; }                 // a postcard (100 x 148 mm) at 300 dpi
  var SANS = '"Hiragino Sans","Hiragino Kaku Gothic ProN","Yu Gothic UI","Yu Gothic","Meiryo","Noto Sans JP","Noto Sans CJK JP",system-ui,sans-serif';
  var SERIF = '"Hiragino Mincho ProN","Yu Mincho","MS PMincho","Noto Serif JP","Noto Serif CJK JP",serif';
  var INK = "#26211d", TEAL = "#1f6f67";
  var canvas = $("#mk-canvas"), ctx = canvas.getContext("2d"), msg = $("#mk-msg"), img = null, picked = null;
  canvas.width = W; canvas.height = H;

  // ---------- Japanese national holidays (the same rules as printables.py; years 2022 to 2099 are right, the dates of a year can change by law)
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function key(y, m, d) { return y + "-" + pad(m) + "-" + pad(d); }
  function nthMonday(y, m, n) { var d = new Date(Date.UTC(y, m - 1, 1)), wd = (d.getUTCDay() + 6) % 7, first = 1 + (7 - wd) % 7; return first + 7 * (n - 1); }
  function equinox(y, spring) { return Math.floor((spring ? 20.8431 : 23.2488) + 0.242194 * (y - 1980) - Math.floor((y - 1980) / 4)); }
  function dow(y, m, d) { return new Date(Date.UTC(y, m - 1, d)).getUTCDay(); }           // 0 = Sunday
  function holidays(y) {
    var h = {}, fixed = [[1, 1, "元日"], [2, 11, "建国記念の日"], [2, 23, "天皇誕生日"], [4, 29, "昭和の日"], [5, 3, "憲法記念日"], [5, 4, "みどりの日"], [5, 5, "こどもの日"], [8, 11, "山の日"], [11, 3, "文化の日"], [11, 23, "勤労感謝の日"]];
    fixed.forEach(function (f) { h[key(y, f[0], f[1])] = f[2]; });
    h[key(y, 1, nthMonday(y, 1, 2))] = "成人の日"; h[key(y, 7, nthMonday(y, 7, 3))] = "海の日"; h[key(y, 9, nthMonday(y, 9, 3))] = "敬老の日"; h[key(y, 10, nthMonday(y, 10, 2))] = "スポーツの日";
    h[key(y, 3, equinox(y, true))] = "春分の日"; h[key(y, 9, equinox(y, false))] = "秋分の日";
    var t = Date.UTC(y, 0, 2), end = Date.UTC(y, 11, 31), day = 86400000;
    function k(ms) { var d = new Date(ms); return key(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate()); }
    for (; t < end; t += day) { var kk = k(t); if (!h[kk] && new Date(t).getUTCDay() !== 0 && h[k(t - day)] && h[k(t + day)]) h[kk] = "国民の休日"; }
    Object.keys(h).sort().forEach(function (kk) {
      var p = kk.split("-").map(Number);
      if (dow(p[0], p[1], p[2]) === 0 && h[kk] !== "振替休日") {
        var n = Date.UTC(p[0], p[1] - 1, p[2]) + day; while (h[k(n)]) n += day; h[k(n)] = "振替休日";
      }
    });
    return h;
  }

  // ---------- drawing helpers
  function fit(im, bw, bh) { var s = Math.min(bw / im.width, bh / im.height); return [im.width * s, im.height * s]; }
  function drawImg(im, x, y, bw, bh) { if (!im) return; var d = fit(im, bw, bh); ctx.drawImage(im, x + (bw - d[0]) / 2, y + (bh - d[1]) / 2, d[0], d[1]); }
  function fitText(text, font, maxW, maxPx, minPx) { var px = maxPx; do { ctx.font = font.replace("{px}", px); if (ctx.measureText(text).width <= maxW) return px; px -= 2; } while (px > minPx); return minPx; }
  function wrapLines(text, maxW) {
    var lines = [], line = "";
    Array.from(text).forEach(function (ch) { if (ch === "\n") { lines.push(line); line = ""; return; } if (ctx.measureText(line + ch).width > maxW && line) { lines.push(line); line = ch; } else line += ch; });
    if (line) lines.push(line);
    return lines;
  }
  function wrapSentences(text, maxW) {                          // one sentence at a time, so a line does not break in the middle of a phrase when the sentence fits
    var out = [];
    (text.match(/[^。]+。?/g) || []).forEach(function (s) { wrapLines(s, maxW).forEach(function (l) { out.push(l); }); });
    return out;
  }
  function val(name) { var e = $('[name="' + name + '"]', root); return e ? e.value : ""; }
  function clean(s, n) { return String(s || "").replace(/[\u0000-\u001f\u007f]/g, "").trim().slice(0, n); }

  // ---------- calendar
  var WEEK_SUN = ["日", "月", "火", "水", "木", "金", "土"];
  function drawCalendar() {
    var y = +val("year"), m = +val("month"), mon = val("start") === "mon", showAdj = $('[name="adj"]', root).checked;
    ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, W, H);
    var hol = holidays(y);
    ctx.textBaseline = "alphabetic"; ctx.textAlign = "left"; ctx.fillStyle = TEAL;
    ctx.font = "700 46px " + SANS; ctx.fillText(y + "年", 80, 150);
    ctx.fillStyle = INK; ctx.font = "800 210px " + SANS; ctx.fillText(m + "月", 74, 360);
    ctx.fillStyle = "#6a6159"; ctx.font = "500 30px " + SANS; ctx.fillText(["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"][m - 1], 82, 410);
    drawImg(img, 520, 60, 660, 640);
    // the grid
    var top = 790, left = 80, cw = (W - 160) / 7, headH = 64, rows = 6, rh = (H - 110 - top - headH) / rows;
    var order = mon ? [1, 2, 3, 4, 5, 6, 0] : [0, 1, 2, 3, 4, 5, 6];
    ctx.textAlign = "center"; ctx.font = "700 32px " + SANS;
    order.forEach(function (wd, i) {
      ctx.fillStyle = wd === 0 ? "#b3261e" : wd === 6 ? "#1d5fa8" : INK;
      ctx.fillText(WEEK_SUN[wd], left + cw * i + cw / 2, top + 44);
    });
    ctx.strokeStyle = TEAL; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(left, top + headH); ctx.lineTo(W - left, top + headH); ctx.stroke();
    var first = dow(y, m, 1), col0 = mon ? (first + 6) % 7 : first, dim = new Date(Date.UTC(y, m, 0)).getUTCDate(), prevDim = new Date(Date.UTC(y, m - 1, 0)).getUTCDate();
    ctx.strokeStyle = "#d9d2c6"; ctx.lineWidth = 1.5;
    for (var r = 0; r <= rows; r++) { ctx.beginPath(); ctx.moveTo(left, top + headH + r * rh); ctx.lineTo(W - left, top + headH + r * rh); ctx.stroke(); }
    for (var c = 0; c <= 7; c++) { ctx.beginPath(); ctx.moveTo(left + c * cw, top + headH); ctx.lineTo(left + c * cw, top + headH + rows * rh); ctx.stroke(); }
    for (var i = 0; i < rows * 7; i++) {
      var n = i - col0 + 1, inMonth = n >= 1 && n <= dim, cx = left + (i % 7) * cw, cy = top + headH + Math.floor(i / 7) * rh, dd, mm = m, yy = y, wd = order[i % 7];
      if (inMonth) { dd = n; }
      else if (showAdj) { if (n < 1) { dd = prevDim + n; mm = m - 1; if (mm < 1) { mm = 12; yy = y - 1; } } else { dd = n - dim; mm = m + 1; if (mm > 12) { mm = 1; yy = y + 1; } } }
      else continue;
      var name = (inMonth ? hol[key(y, m, dd)] : holidays(yy)[key(yy, mm, dd)]) || "";
      ctx.textAlign = "left"; ctx.fillStyle = (wd === 0 || name) ? "#b3261e" : wd === 6 ? "#1d5fa8" : INK; ctx.globalAlpha = inMonth ? 1 : 0.35;
      ctx.font = "700 40px " + SANS; ctx.fillText(String(dd), cx + 12, cy + 48);
      if (name) { var hp = fitText(name, "500 {px}px " + SANS, cw - 18, 21, 14); ctx.font = "500 " + hp + "px " + SANS; ctx.fillText(name, cx + 12, cy + rh - 16); }
      ctx.globalAlpha = 1;
    }
    ctx.textAlign = "right"; ctx.fillStyle = "#8a8176"; ctx.font = "500 22px " + SANS; ctx.fillText("minna-no-illust.com", W - 80, H - 50);
    ctx.textAlign = "left";
  }

  // ---------- name tags, seat cards, certificates
  function nameFont() { return val("face") === "serif" ? "800 {px}px " + SERIF : "800 {px}px " + SANS; }
  function drawTagCell(x, y, w, h, name, sub) {
    ctx.save(); ctx.setLineDash([10, 8]); ctx.strokeStyle = "#9a9187"; ctx.lineWidth = 2; ctx.strokeRect(x + 1, y + 1, w - 2, h - 2); ctx.restore();
    var imgW = img ? Math.min(h * 0.62, w * 0.34) : 0, pad = 30;
    if (img) drawImg(img, x + pad, y + (h - imgW) / 2, imgW, imgW);
    var tx = x + pad + imgW + (img ? 14 : 0), tw = w - (tx - x) - pad, cx = tx + tw / 2;
    ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillStyle = INK;
    var px = fitText(name, nameFont(), tw, Math.round(h * 0.34), 28); ctx.font = nameFont().replace("{px}", px);
    ctx.fillText(name, cx, y + h / 2 - (sub ? 18 : 0));
    if (sub) { var sp = fitText(sub, "500 {px}px " + SANS, tw, 30, 18); ctx.font = "500 " + sp + "px " + SANS; ctx.fillStyle = "#4a423b"; ctx.fillText(sub, cx, y + h / 2 + px * 0.55 + 6); }
    ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
  }
  function drawTags() {
    var name = clean(val("name"), 14) || "なまえ", sub = clean(val("sub"), 20), tpl = val("tpl");
    ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, W, H);
    if (tpl === "seat") {                                        // a card folded in the middle: the upper half is turned round so both sides read
      var hh = H / 2;
      ctx.save(); ctx.translate(W, hh); ctx.rotate(Math.PI); drawTagCell(0, 0, W, hh, name, sub); ctx.restore();
      drawTagCell(0, hh, W, hh, name, sub);
      ctx.save(); ctx.setLineDash([14, 10]); ctx.strokeStyle = "#b9b0a4"; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(0, hh); ctx.lineTo(W, hh); ctx.stroke(); ctx.restore();
    } else {                                                     // eight name tags (2 x 4); the dashed lines are the cutting guides
      var cw = 560, ch = 390, gx = (W - cw * 2) / 2, gy = (H - ch * 4) / 2;
      for (var r = 0; r < 4; r++) for (var c = 0; c < 2; c++) drawTagCell(gx + c * cw, gy + r * ch, cw, ch, name, sub);
    }
  }
  function drawCert() {
    var name = clean(val("name"), 16) || "山田 太郎", body = clean(val("body"), 120) || "あなたは優れた成績を収めました。ここにその功績をたたえ、賞状を贈ります。", date = clean(val("date"), 24), from = clean(val("from"), 30);
    ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = TEAL; ctx.lineWidth = 8; ctx.strokeRect(60, 60, W - 120, H - 120); ctx.lineWidth = 2; ctx.strokeRect(84, 84, W - 168, H - 168);
    ctx.textAlign = "center"; ctx.fillStyle = INK;
    ctx.font = "800 150px " + SERIF; ctx.fillText("賞　状", W / 2, 330);
    drawImg(img, W / 2 - 230, 400, 460, 340);
    var nf = "700 {px}px " + SERIF; var px = fitText(name + "　殿", nf, W - 360, 90, 40); ctx.font = nf.replace("{px}", px); ctx.fillText(name + "　殿", W / 2, 880);
    ctx.font = "500 42px " + SERIF; var lines = wrapLines(body, W - 340); ctx.fillStyle = INK;
    lines.slice(0, 6).forEach(function (l, i) { ctx.fillText(l, W / 2, 1030 + i * 74); });
    ctx.textAlign = "right"; ctx.font = "500 40px " + SERIF;
    if (date) ctx.fillText(date, W - 200, 1500);
    if (from) { ctx.font = "700 50px " + SERIF; ctx.fillText(from, W - 200, 1590); }
    ctx.textAlign = "left";
  }

  // ---------- 年賀状 (the message side of a postcard: a greeting, the date, a picture, a message and the sender)
  function drawNenga() {
    var M = 96, col = val("color") || "#b3261e", serif = val("face") !== "sans", FACE = serif ? SERIF : SANS;
    var greet = val("greet") || "あけましておめでとうございます", date = clean(val("date"), 20), body = clean(val("body"), 90), from = clean(val("from"), 24);
    ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, W, H);
    if ($('[name="frame"]', root).checked) { ctx.strokeStyle = col; ctx.lineWidth = 4; ctx.strokeRect(60, 60, W - 120, H - 120); }
    ctx.textAlign = "center"; ctx.textBaseline = "alphabetic"; ctx.fillStyle = col;
    var gf = "800 {px}px " + FACE, gp = fitText(greet, gf, W - 2 * M - 20, greet.length <= 4 ? 170 : 110, 44); ctx.font = gf.replace("{px}", gp);
    ctx.fillText(greet, W / 2, 250);
    if (date) { ctx.fillStyle = INK; ctx.font = "600 44px " + FACE; ctx.fillText(date, W / 2, 330); }
    var top = 390, bottom = H - 130, picH = 640, textTop = top, picTop = top, textH = bottom - top - picH - 20;
    if (val("pos") === "bottom") { picTop = bottom - picH; } else { textTop = top + picH + 20; }
    drawImg(img, M, picTop, W - 2 * M, picH);
    ctx.fillStyle = INK; ctx.font = "500 46px " + FACE;
    var lines = wrapSentences(body, W - 2 * M - 40).slice(0, 5), lh = 74, y = textTop + 70;
    lines.forEach(function (l, i) { ctx.fillText(l, W / 2, y + i * lh); });
    if (from) { ctx.textAlign = "right"; var fp = fitText(from, "700 {px}px " + FACE, W - 2 * M - 40, 56, 30); ctx.font = "700 " + fp + "px " + FACE; ctx.fillText(from, W - M - 20, textTop + textH - 10); }
    ctx.textAlign = "left";
  }

  var drawNow = { nenga: drawNenga, calendar: drawCalendar, nametag: function () { return val("tpl") === "cert" ? drawCert() : drawTags(); } }[kind];
  var timer = 0;
  function redraw() { clearTimeout(timer); timer = setTimeout(function () { try { drawNow(); } catch (e) { msg.textContent = "表示できませんでした。入力を確かめてください。"; } }, 80); }

  // ---------- picking the illustration
  function pick(row) {
    if (!A.safeSlug(row[0])) return;
    var im = new Image(); msg.textContent = "読み込んでいます…";
    im.onload = function () { img = im; picked = row; msg.textContent = "選んだイラスト: " + row[1]; $$("#mk-list button").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-id") === row[0] ? "true" : "false"); }); drawNow(); };
    im.onerror = function () { msg.textContent = "このイラストを読み込めませんでした。別のイラストを選んでください。"; };
    im.src = "/files/" + row[0] + ".png";
  }
  function showRows(rows) {
    var list = $("#mk-list"), n = Math.min(rows.length, 36);
    list.innerHTML = rows.slice(0, 36).filter(function (r) { return A.safeSlug(r[0]); }).map(function (r) {
      return '<button type="button" data-id="' + r[0] + '" aria-pressed="false" title="' + A.esc(r[1]) + '"><img src="/thumbs/' + r[0] + '.webp" alt="' + A.esc(r[1]) + '" width="96" height="96" loading="lazy"></button>';
    }).join("");
    $("#mk-count").textContent = rows.length ? (rows.length > 36 ? rows.length + "点のうち36点を表示" : rows.length + "点") : "見つかりませんでした";
    $$("#mk-list button").forEach(function (b, i) { b.addEventListener("click", function () { pick(rows[i]); }); });
  }
  function search() {
    var q = $('[name="q"]', root).value.trim();
    Promise.all([A.loadIndex(), A.loadSyn(), A.loadVocab()]).then(function (v) {
      var res = A.searchAll(v[0], v[1], v[2], q, "", "");
      showRows(res.exact.length ? res.exact : res.near);
    });
  }
  $('[name="q"]', root).addEventListener("input", function () { clearTimeout(search.t); search.t = setTimeout(search, 250); });
  $("#mk-search", root).addEventListener("submit", function (e) { e.preventDefault(); search(); });
  $$("[data-q]", root).forEach(function (b) { b.addEventListener("click", function () { $('[name="q"]', root).value = b.getAttribute("data-q"); search(); }); });

  // ---------- options
  $$("input, select, textarea", $("#mk-opts")).forEach(function (e) { e.addEventListener("input", redraw); e.addEventListener("change", redraw); });
  if (kind === "nametag") {
    var tpl = $('[name="tpl"]', root);
    var sync = function () { $$("[data-for]", root).forEach(function (e) { e.hidden = e.getAttribute("data-for").split(" ").indexOf(tpl.value) < 0; }); };
    tpl.addEventListener("change", sync); sync();
  }
  function fileName() { if (kind === "nenga") return "nengajo.png"; return kind === "calendar" ? "calendar-" + val("year") + "-" + pad(+val("month")) + ".png" : "print-" + val("tpl") + ".png"; }
  $("#mk-save").addEventListener("click", function () {
    drawNow();
    canvas.toBlob(function (b) { var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = fileName(); document.body.appendChild(a); a.click(); a.remove(); msg.textContent = "保存しました。"; }, "image/png");
  });
  $("#mk-print").addEventListener("click", function () {
    drawNow();
    var box = $("#mk-printbox"); box.innerHTML = '<img alt="印刷するページ" src="' + canvas.toDataURL("image/png") + '">'; box.hidden = false;
    document.body.classList.add("nu-printing");
    var pageStyle = null;
    if (kind === "nenga") { pageStyle = document.createElement("style"); pageStyle.textContent = "@page{size:100mm 148mm;margin:0}"; document.head.appendChild(pageStyle); }      // the postcard size, if the printer offers it
    var im = $("img", box), done = function () { window.print(); document.body.classList.remove("nu-printing"); box.hidden = true; box.innerHTML = ""; if (pageStyle) pageStyle.remove(); };
    if (im.complete) done(); else im.onload = done;
  });

  // ---------- start: this month (calendar), a first picture, a first drawing
  if (kind === "calendar") {
    var now = new Date(), ys = $('[name="year"]', root), ms = $('[name="month"]', root);
    for (var y = now.getFullYear() - 1; y <= now.getFullYear() + 4; y++) { var o = document.createElement("option"); o.value = y; o.textContent = y + "年"; ys.appendChild(o); }
    for (var m = 1; m <= 12; m++) { var o2 = document.createElement("option"); o2.value = m; o2.textContent = m + "月"; ms.appendChild(o2); }
    ys.value = now.getFullYear(); ms.value = now.getMonth() + 1;
  } else if (kind === "nenga") {
    var nd = new Date(), ny = nd.getMonth() >= 8 ? nd.getFullYear() + 1 : nd.getFullYear();      // from September on, the coming New Year
    $('[name="date"]', root).value = ny >= 2019 ? "令和" + (ny - 2018) + "年 元旦" : ny + "年 元旦";
  } else {
    var dt = new Date(); $('[name="date"]', root).value = dt.getFullYear() + "年" + (dt.getMonth() + 1) + "月" + dt.getDate() + "日";
  }
  drawNow();
  $('[name="q"]', root).value = kind === "nenga" ? "年賀状" : "ひつじ"; search();
  var want = (location.search.match(/[?&]id=([^&]+)/) || [])[1];                                  // ?id=<picture>: a picture page sends its own picture here
  if (want && A.safeSlug(want)) A.loadIndex().then(function (rows) { var r = rows.filter(function (x) { return x[0] === want; })[0]; if (r) pick(r); });
  window.minnaMaker = { holidays: holidays, redraw: drawNow };
  }
  if (document.readyState === "complete") main(); else document.addEventListener("DOMContentLoaded", main);
})();
