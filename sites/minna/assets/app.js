// みんなのイラスト: background switcher, in-browser export, favourites, search, ZIP of a set, the card maker.
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

  var TITLES = { birthday: "おたんじょうび おめでとう", thanks: "いつも ありがとう", congrats: "おめでとう", cheer: "おうえん してるよ", newyear: "あけまして おめでとう" };
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


  // ---------- favourites (this browser only)
  var FAV_KEY = "minna:favs";
  function favs() { try { var v = JSON.parse(localStorage.getItem(FAV_KEY) || "[]"); return Array.isArray(v) ? v : []; } catch (e) { return []; } }
  function saveFavs(a) { try { localStorage.setItem(FAV_KEY, JSON.stringify(a.slice(0, 500))); } catch (e) {} }
  function paintFavs() {
    var f = favs();
    $$("[data-fav]").forEach(function (b) {
      var on = f.indexOf(b.getAttribute("data-fav")) >= 0;
      b.setAttribute("aria-pressed", on ? "true" : "false");
      b.classList.toggle("on", on);
      if (b.classList.contains("fav-big")) b.textContent = (on ? "♥ お気に入り済み" : "♡ お気に入り");
      else { b.textContent = on ? "♥" : "♡"; b.setAttribute("aria-label", on ? "お気に入りから外す" : "お気に入りに入れる"); }
    });
  }
  function initFav() {
    document.addEventListener("click", function (e) {
      var b = e.target.closest ? e.target.closest("[data-fav]") : null; if (!b) return;
      e.preventDefault();
      var id = b.getAttribute("data-fav"), f = favs(), i = f.indexOf(id);
      if (i >= 0) f.splice(i, 1); else f.unshift(id);
      saveFavs(f); paintFavs();
    });
    paintFavs();
  }

  // ---------- search index
  var indexP = null;
  function loadIndex() {
    if (!indexP) indexP = fetch("/data/items.json").then(function (r) { return r.json(); }).catch(function () { return []; });
    return indexP;
  }
  function norm(s) { // katakana -> hiragana, lower case, full-width ascii -> half-width
    return String(s || "").toLowerCase().replace(/[ァ-ヶ]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 96); })
      .replace(/[！-～]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 65248); });
  }
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;"); }
  function cardHtml(r) {
    var w = Math.min(r[6], 360), h = Math.round(r[7] * w / r[6]);
    return '<li class="ic"><a class="illust-card" href="/illust/' + r[0] + '/"><span class="checker"><img src="/thumbs/' + r[0] + '.webp" alt="' + esc(r[1]) + '" width="' + w + '" height="' + h + '" loading="lazy"></span><b>' + esc(r[1]) + '</b></a>' +
      '<button class="fav" type="button" data-fav="' + r[0] + '" aria-pressed="false" aria-label="お気に入りに入れる">♡</button></li>';
  }
  function initSearch() {
    var app = $("#search-app"); if (!app) return;
    var list = $("#search-results"), status = $("#search-status"), more = $("#search-more"), q = $('[name="q"]', app), g = $('[name="g"]', app), t = $('[name="t"]', app);
    var params = new URLSearchParams(location.search);
    q.value = params.get("q") || ""; g.value = params.get("g") || ""; t.value = params.get("t") || "";
    var hits = [], shown = 0, STEP = 60;
    function draw(reset) {
      if (reset) { list.innerHTML = ""; shown = 0; }
      var slice = hits.slice(shown, shown + STEP);
      list.insertAdjacentHTML("beforeend", slice.map(cardHtml).join("")); shown += slice.length;
      more.hidden = shown >= hits.length; paintFavs();
    }
    function run() {
      loadIndex().then(function (rows) {
        var words = norm(q.value).split(/\s+/).filter(Boolean);
        if (!words.length && !g.value && !t.value) { hits = []; status.textContent = "キーワードを入れてください。ひらがな・カタカナは、どちらでも見つかります。"; list.innerHTML = ""; more.hidden = true; return; }
        hits = rows.filter(function (r) {
          if (g.value && r[3] !== g.value) return false;
          if (t.value && r[4] !== t.value) return false;
          var hay = norm(r[1] + " " + r[2] + " " + r[5]);
          return words.every(function (w) { return hay.indexOf(w) >= 0; });
        });
        status.textContent = hits.length ? hits.length + "点、見つかりました。" : "見つかりませんでした。ほかの言葉で、さがしてみてください。";
        draw(true);
      });
    }
    app.addEventListener("submit", function (e) { e.preventDefault(); var u = new URL(location.href); u.search = new URLSearchParams({ q: q.value, g: g.value, t: t.value }).toString(); history.replaceState(null, "", u); run(); });
    g.addEventListener("change", function () { app.dispatchEvent(new Event("submit", { cancelable: true })); });
    t.addEventListener("change", function () { app.dispatchEvent(new Event("submit", { cancelable: true })); });
    more.addEventListener("click", function () { draw(false); });
    run();
  }
  function initFavPage() {
    var list = $("#fav-results"); if (!list) return;
    var status = $("#fav-status");
    loadIndex().then(function (rows) {
      var f = favs(), by = {}; rows.forEach(function (r) { by[r[0]] = r; });
      var hits = f.map(function (id) { return by[id]; }).filter(Boolean);
      status.textContent = hits.length ? hits.length + "点、お気に入りに入っています。" : "まだ、お気に入りはありません。イラストの♡を押すと、ここに並びます。";
      list.innerHTML = hits.map(cardHtml).join(""); paintFavs();
    });
  }

  // ---------- in-browser export of one illustration (background, size, JPG) and copy to the clipboard
  function loadImage(src) { return new Promise(function (ok, ng) { var im = new Image(); im.onload = function () { ok(im); }; im.onerror = ng; im.src = src; }); }
  function render(im, o) {
    var W = im.naturalWidth, H = im.naturalHeight, cw = W, ch = H, sc = 1;
    if (o.size === "sq1080") { cw = ch = 1080; sc = Math.min(900 / W, 900 / H); }
    else if (o.size === "wide") { cw = 1280; ch = 720; sc = Math.min(1000 / W, 600 / H); }
    else if (o.size === "hagaki") { cw = 1181; ch = 1748; sc = Math.min(1000 / W, 1400 / H); }
    var c = document.createElement("canvas"); c.width = cw; c.height = ch; var x = c.getContext("2d");
    if (o.bg || o.fmt === "jpg") { x.fillStyle = o.bg || "#ffffff"; x.fillRect(0, 0, cw, ch); }
    var dw = W * sc, dh = H * sc; x.imageSmoothingQuality = "high"; x.drawImage(im, (cw - dw) / 2, (ch - dh) / 2, dw, dh);
    return c;
  }
  function initExport() {
    var box = $(".export"); if (!box) return;
    var msg = $("[data-export-msg]", box);
    function opts() { return { fmt: $('[name="fmt"]', box).value, bg: $('[name="bg"]', box).value, size: $('[name="size"]', box).value }; }
    $("[data-export]", box).addEventListener("click", function () {
      var o = opts();
      loadImage(box.getAttribute("data-src")).then(function (im) {
        var c = render(im, o), type = o.fmt === "jpg" ? "image/jpeg" : "image/png";
        c.toBlob(function (b) {
          var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = box.getAttribute("data-name") + (o.size === "orig" ? "" : "-" + o.size) + "." + (o.fmt === "jpg" ? "jpg" : "png");
          document.body.appendChild(a); a.click(); a.remove(); msg.textContent = "保存しました。";
        }, type, 0.92);
      }).catch(function () { msg.textContent = "保存できませんでした。ダウンロードのボタンを、お使いください。"; });
    });
    $("[data-copy]", box).addEventListener("click", function () {
      var o = opts();
      if (!navigator.clipboard || !window.ClipboardItem) { msg.textContent = "このブラウザでは、コピーできません。保存を、お使いください。"; return; }
      loadImage(box.getAttribute("data-src")).then(function (im) {
        render(im, { fmt: "png", bg: o.bg, size: o.size }).toBlob(function (b) {
          navigator.clipboard.write([new ClipboardItem({ "image/png": b })]).then(function () { msg.textContent = "コピーしました。貼りつけて、使えます。"; }, function () { msg.textContent = "コピーできませんでした。"; });
        }, "image/png");
      });
    });
  }

  // ---------- ZIP of a set (store only, built in the browser)
  var CRC = (function () { var t = [], n, k, c; for (n = 0; n < 256; n++) { c = n; for (k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  function crc32(u8) { var c = 0xffffffff; for (var i = 0; i < u8.length; i++) c = CRC[(c ^ u8[i]) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; }
  function zip(files) { // files: [{name, data: Uint8Array}]
    var enc = new TextEncoder(), parts = [], central = [], off = 0;
    function u16(v) { return [v & 255, (v >>> 8) & 255]; } function u32(v) { return [v & 255, (v >>> 8) & 255, (v >>> 16) & 255, (v >>> 24) & 255]; }
    files.forEach(function (f) {
      var name = enc.encode(f.name), crc = crc32(f.data), sz = f.data.length;
      var lh = [].concat(u32(0x04034b50), u16(20), u16(0x0800), u16(0), u16(0), u16(0x21), u32(crc), u32(sz), u32(sz), u16(name.length), u16(0));
      parts.push(new Uint8Array(lh), name, f.data);
      central.push({ name: name, crc: crc, sz: sz, off: off }); off += lh.length + name.length + sz;
    });
    var cstart = off, csize = 0;
    central.forEach(function (c) {
      var h = [].concat(u32(0x02014b50), u16(20), u16(20), u16(0x0800), u16(0), u16(0), u16(0x21), u32(c.crc), u32(c.sz), u32(c.sz), u16(c.name.length), u16(0), u16(0), u16(0), u16(0), u32(0), u32(c.off));
      parts.push(new Uint8Array(h), c.name); csize += h.length + c.name.length;
    });
    parts.push(new Uint8Array([].concat(u32(0x06054b50), u16(0), u16(0), u16(central.length), u16(central.length), u32(csize), u32(cstart), u16(0))));
    return new Blob(parts, { type: "application/zip" });
  }
  function initZip() {
    $$("[data-zip]").forEach(function (b) {
      b.addEventListener("click", function () {
        var urls = JSON.parse(b.getAttribute("data-files")), label = b.textContent; b.disabled = true; b.textContent = "まとめています…";
        Promise.all(urls.map(function (u) { return fetch(u).then(function (r) { return r.arrayBuffer(); }).then(function (a) { return { name: u.split("/").pop(), data: new Uint8Array(a) }; }); }))
          .then(function (files) {
            var a = document.createElement("a"); a.href = URL.createObjectURL(zip(files)); a.download = b.getAttribute("data-name") + ".zip"; document.body.appendChild(a); a.click(); a.remove();
            b.textContent = "保存しました"; setTimeout(function () { b.textContent = label; b.disabled = false; }, 2500);
          }).catch(function () { b.textContent = "うまく、まとめられませんでした"; setTimeout(function () { b.textContent = label; b.disabled = false; }, 2500); });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () { initBg(); initCard(); initFav(); initSearch(); initFavPage(); initExport(); initZip(); });

})();
