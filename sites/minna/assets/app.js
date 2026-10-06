// みんなのイラスト: the background switcher on detail pages, the card maker, the copy-link button.
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  function initBg() {
    var box = $("#bgbox"); if (!box) return;
    $$(".bgsw button").forEach(function (b) {
      b.addEventListener("click", function () {
        var c = b.getAttribute("data-bg");
        box.classList.toggle("solid", !!c); box.style.backgroundColor = c || "";
        $$(".bgsw button").forEach(function (x) { x.classList.toggle("on", x === b); });
      });
    });
  }

  var TITLES = { birthday: "おたんじょうび おめでとう", thanks: "いつも ありがとう", congrats: "おめでとう", cheer: "おうえん してるよ" };
  var imgCache = {};
  function loadImg(src) {
    return new Promise(function (resolve) {
      if (imgCache[src]) return resolve(imgCache[src]);
      var im = new Image(); im.onload = function () { imgCache[src] = im; resolve(im); }; im.onerror = function () { resolve(null); }; im.src = src;
    });
  }
  function wrap(ctx, text, maxW) {
    var lines = [], line = "";
    Array.from(text).forEach(function (ch) {
      if (ch === "\n") { lines.push(line); line = ""; return; }
      if (ctx.measureText(line + ch).width > maxW && line) { lines.push(line); line = ch; } else line += ch;
    });
    if (line) lines.push(line);
    return lines;
  }
  function rr(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }

  window.MinnaCard = {
    draw: async function (canvas, v, chars) {
      try {
        // a slow or blocked font request must not keep the card from being drawn: wait at most 1.5 s, then use the fallback face
        await Promise.race([Promise.all([document.fonts.load('900 40px "Zen Maru Gothic"'), document.fonts.load('400 40px "Mochiy Pop One"')]), new Promise(function (r) { setTimeout(r, 1500); })]);
      } catch (e) {}
      var ctx = canvas.getContext("2d"), W = canvas.width, H = canvas.height, INK = "#2b1b14";
      ctx.fillStyle = v.color; ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = "rgba(255,255,255,.55)";
      for (var y = 30; y < H; y += 54) for (var x = 30 + ((y / 54) % 2) * 27; x < W; x += 54) { ctx.beginPath(); ctx.arc(x, y, 4, 0, 6.3); ctx.fill(); }
      ctx.lineWidth = 10; ctx.strokeStyle = INK; rr(ctx, 40, 40, W - 80, H - 80, 60); ctx.stroke();
      ctx.textAlign = "center"; ctx.fillStyle = INK;
      var title = TITLES[v.tpl] || "";
      ctx.font = '400 92px "Mochiy Pop One", "Zen Maru Gothic", sans-serif';
      var ty = 230; wrap(ctx, title.replace(" ", "\n"), W - 200).forEach(function (l, i) {
        ctx.fillStyle = "#fff"; ctx.fillText(l, W / 2 + 5, ty + i * 112 + 5); ctx.fillStyle = INK; ctx.fillText(l, W / 2, ty + i * 112);
      });
      if (v.to) { ctx.font = '900 54px "Zen Maru Gothic", sans-serif'; ctx.textAlign = "left"; ctx.fillText(v.to + (/さん|ちゃん|くん|様$/.test(v.to) ? "" : "さん") + "へ", 110, 140); ctx.textAlign = "center"; }
      var ch = chars.filter(function (c) { return c.id === v.char; })[0] || chars[0];
      var im = ch ? await loadImg(ch.src) : null;
      if (im) {
        var s = Math.min(760 / im.width, 560 / im.height);
        ctx.drawImage(im, (W - im.width * s) / 2, 440 + (560 - im.height * s) / 2, im.width * s, im.height * s);
      }
      if (v.msg) {
        ctx.fillStyle = "#fff"; ctx.lineWidth = 6; ctx.strokeStyle = INK; rr(ctx, 110, 1010, W - 220, 190, 36); ctx.fill(); ctx.stroke();
        ctx.fillStyle = INK; ctx.font = '900 44px "Zen Maru Gothic", sans-serif';
        var ls = wrap(ctx, v.msg, W - 300).slice(0, 3), top = 1105 - (ls.length - 1) * 30;
        ls.forEach(function (l, i) { ctx.fillText(l, W / 2, top + i * 60); });
      }
      ctx.textAlign = "right"; ctx.font = '900 40px "Zen Maru Gothic", sans-serif'; ctx.fillStyle = INK;
      if (v.from) ctx.fillText(v.from + "より", W - 110, 1262);
      ctx.textAlign = "left"; ctx.font = '700 26px "Zen Maru Gothic", sans-serif'; ctx.fillStyle = "rgba(43,27,20,.6)"; ctx.fillText("minna-no-illust.com", 110, 1262);
    }
  };

  function initCard() {
    var app = $("#card-app"); if (!app) return;
    var data = JSON.parse(app.getAttribute("data-json")), canvas = $("canvas", app), img = $(".card-img", app);
    var f = { tpl: $('[name="tpl"]', app), to: $('[name="to"]', app), msg: $('[name="msg"]', app), from: $('[name="from"]', app), char: $('[name="char"]', app), color: $('[name="color"]', app) };
    var timer = null;
    function values() { return { tpl: f.tpl.value, to: f.to.value.trim(), msg: f.msg.value.trim(), from: f.from.value.trim(), char: f.char.value, color: f.color.value }; }
    function redraw() { clearTimeout(timer); timer = setTimeout(function () { window.MinnaCard.draw(canvas, values(), data.chars); img.hidden = true; }, 120); }
    Object.keys(f).forEach(function (k) { f[k].addEventListener("input", redraw); f[k].addEventListener("change", redraw); });
    var q = new URLSearchParams(location.search);
    if (q.get("c") && f.char.querySelector('option[value="' + q.get("c") + '"]')) f.char.value = q.get("c");
    $("[data-save]", app).addEventListener("click", async function () {
      await window.MinnaCard.draw(canvas, values(), data.chars);
      var url = canvas.toDataURL("image/png");
      img.src = url; img.hidden = false;
      var a = document.createElement("a"); a.href = url; a.download = "card.png"; document.body.appendChild(a); a.click(); a.remove();
    });
    window.MinnaCard.draw(canvas, values(), data.chars);
  }

  document.addEventListener("DOMContentLoaded", function () { initBg(); initCard(); });
})();
