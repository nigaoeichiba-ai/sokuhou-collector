// みんなのイラスト: online colouring ("オンラインぬりえ"). A line drawing is shown on white; a tap fills the shape under the finger with the chosen colour.
// Everything happens in this browser (canvas); nothing is sent anywhere.  The picture is kept as a lightness map L (0 = line, 255 = paper) and a layer of fills;
// the canvas shows L multiplied by the fill colour, so the soft edges of a line stay a darker shade of the colour and no white halo is left beside it.
// A drawing whose outline has a small gap would let the colour run out into the background: so a shape is found with the lines made a little thicker (the thinnest
// thickening after which the inside no longer joins the outside is chosen per picture), then the colour is spread back up to the real line.
(function () {
  "use strict";
  var root = document.getElementById("nurie-app"); if (!root) return;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;"); }
  var COLORS = ["#ff4d6d", "#ff8a3d", "#ffc93c", "#a3d65c", "#2fd09b", "#38bdf8", "#4d6dff", "#a78bfa", "#f78fb3", "#8a5a3c", "#9aa5a0", "#ffffff"];
  var T = 140;                      // lightness from which a pixel belongs to a shape (below it: line)
  var MAXW = 900, MAXH = 1100, UNDO = 20, SEALS = [0, 2, 4, 6, 8], TINY = 3000;
  var stage = $("#nu-stage"), canvas = $("#nu-canvas"), ctx = canvas.getContext("2d", { willReadFrequently: true });
  var st = { W: 0, H: 0, L: null, A: null, bar: null, seal: 0, fill: null, color: COLORS[0], undo: [], id: "", title: "" };

  function pack(hex) { var n = parseInt(hex.slice(1), 16); return (0xff000000 | ((n & 255) << 16) | (((n >> 8) & 255) << 8) | (n >> 16)) >>> 0; }   // ABGR as the canvas stores it
  function render() {
    var out = ctx.createImageData(st.W, st.H), d = out.data, L = st.L, f = st.fill, i, l, c, p;
    for (i = 0; i < L.length; i++) {
      l = L[i] / 255; c = f[i]; p = i * 4;
      if (c) { d[p] = (c & 255) * l; d[p + 1] = ((c >> 8) & 255) * l; d[p + 2] = ((c >> 16) & 255) * l; }
      else { d[p] = d[p + 1] = d[p + 2] = L[i]; }
      d[p + 3] = 255;
    }
    ctx.putImageData(out, 0, 0);
  }
  function status(t) { $("#nu-msg").textContent = t; }
  function pushUndo() { if (st.undo.length >= UNDO) st.undo.shift(); st.undo.push(st.fill.slice()); }   // the one place that keeps the undo list short (a fill and a reset both use it)

  // the pixels within r of a line (a square window, two passes)
  function thicken(L, W, H, r) {
    var bar = new Uint8Array(W * H), tmp = new Uint8Array(W * H), x, y, k, i;
    if (!r) return bar;
    for (y = 0; y < H; y++) for (x = 0; x < W; x++) {
      i = y * W + x; if (L[i] >= T) continue;
      var a = Math.max(0, x - r), b = Math.min(W - 1, x + r); for (k = a; k <= b; k++) tmp[y * W + k] = 1;
    }
    for (x = 0; x < W; x++) for (y = 0; y < H; y++) {
      if (!tmp[y * W + x]) continue;
      var c = Math.max(0, y - r), d = Math.min(H - 1, y + r); for (k = c; k <= d; k++) bar[k * W + x] = 1;
    }
    return bar;
  }
  // how much of the picture's own inside (opaque, light) is joined to the outside, when the lines are thickened by r
  function leakShare(r) {
    var W = st.W, H = st.H, L = st.L, A = st.A, bar = thicken(L, W, H, r), seen = new Uint8Array(W * H), stack = [], i, x, y;
    function ok(j) { return L[j] >= T && !bar[j] && !seen[j]; }
    for (x = 0; x < W; x++) { i = x; if (ok(i)) { seen[i] = 1; stack.push(i); } i = (H - 1) * W + x; if (ok(i)) { seen[i] = 1; stack.push(i); } }
    for (y = 0; y < H; y++) { i = y * W; if (ok(i)) { seen[i] = 1; stack.push(i); } i = y * W + W - 1; if (ok(i)) { seen[i] = 1; stack.push(i); } }
    var n;
    while (stack.length) {
      i = stack.pop(); x = i % W;
      if (x > 0 && ok(n = i - 1)) { seen[n] = 1; stack.push(n); }
      if (x < W - 1 && ok(n = i + 1)) { seen[n] = 1; stack.push(n); }
      if (i >= W && ok(n = i - W)) { seen[n] = 1; stack.push(n); }
      if (i < W * (H - 1) && ok(n = i + W)) { seen[n] = 1; stack.push(n); }
    }
    var inside = 0, joined = 0;
    for (i = 0; i < W * H; i++) { if (A[i] && L[i] >= T) { inside++; if (seen[i]) joined++; } }
    return { share: inside ? joined / inside : 0, bar: bar };
  }

  function load(id, title) {
    var img = new Image();
    status("読み込んでいます…");
    img.onload = function () {
      var s = Math.min(2, MAXW / img.naturalWidth, MAXH / img.naturalHeight);
      st.W = canvas.width = Math.round(img.naturalWidth * s); st.H = canvas.height = Math.round(img.naturalHeight * s);
      ctx.clearRect(0, 0, st.W, st.H); ctx.imageSmoothingQuality = "high"; ctx.drawImage(img, 0, 0, st.W, st.H);
      var px = ctx.getImageData(0, 0, st.W, st.H).data, n = st.W * st.H, i, a;
      st.L = new Uint8Array(n); st.A = new Uint8Array(n); st.fill = new Uint32Array(n);
      for (i = 0; i < n; i++) {
        a = px[i * 4 + 3] / 255; st.A[i] = a > 0.5 ? 1 : 0;
        st.L[i] = ((px[i * 4] * 0.299 + px[i * 4 + 1] * 0.587 + px[i * 4 + 2] * 0.114) * a + 255 * (1 - a)) | 0;
      }
      var best = null, k, r;
      for (k = 0; k < SEALS.length; k++) {
        r = leakShare(SEALS[k]); if (!best || r.share < best.share - 0.0005) { best = { share: r.share, bar: r.bar, seal: SEALS[k] }; }
        if (r.share <= 0.03) { best = { share: r.share, bar: r.bar, seal: SEALS[k] }; break; }
      }
      st.bar = best.bar; st.seal = best.seal; st.leaky = best.share > 0.03;
      st.undo = []; st.id = id; st.title = title || id; render();
      canvas.setAttribute("aria-label", st.title + "の塗り絵。色を選び、塗りたい場所をタップします。");
      stage.hidden = false; $("#nu-title").textContent = st.title;
      var u = new URL(location.href); u.searchParams.set("id", id); history.replaceState(null, "", u);
      status(st.leaky ? "この絵は線に切れ目があり、色が外にはみ出すことがあります。その場合は「ひとつ戻す」を押してください。" : "色を選び、塗りたい場所をタップしてください。");
      stage.scrollIntoView({ behavior: "smooth", block: "start" });
    };
    img.onerror = function () { status("この絵を読み込めませんでした。別の絵を選んでください。"); };
    img.src = "/files/" + id + ".webp";
  }

  // flood from i0 over the pixels that are paper (not line), not within the thickening, and still have the colour `target`; returns the pixels or null when it grew past `limit`
  function flood(i0, target, useBar, limit) {
    var W = st.W, H = st.H, L = st.L, F = st.fill, bar = st.bar, seen = new Uint8Array(W * H), stack = [i0], region = [], n, i, xx;
    function ok(j) { return !seen[j] && L[j] >= T && F[j] === target && (!useBar || !bar[j]); }
    seen[i0] = 1;
    while (stack.length) {
      i = stack.pop(); region.push(i); if (limit && region.length > limit) return null;
      xx = i % W;
      if (xx > 0 && ok(n = i - 1)) { seen[n] = 1; stack.push(n); }
      if (xx < W - 1 && ok(n = i + 1)) { seen[n] = 1; stack.push(n); }
      if (i >= W && ok(n = i - W)) { seen[n] = 1; stack.push(n); }
      if (i < W * (H - 1) && ok(n = i + W)) { seen[n] = 1; stack.push(n); }
    }
    return region;
  }
  function spread(region, target, color, steps) { // the colour goes on up to the real line (over the pixels the thickening had kept out)
    var W = st.W, H = st.H, L = st.L, F = st.fill, front = region, s, j, i, xx, n;
    for (s = 0; s < steps; s++) {
      var next = [];
      for (j = 0; j < front.length; j++) {
        i = front[j]; xx = i % W;
        if (xx > 0 && L[n = i - 1] >= T && F[n] === target) { F[n] = color; next.push(n); }
        if (xx < W - 1 && L[n = i + 1] >= T && F[n] === target) { F[n] = color; next.push(n); }
        if (i >= W && L[n = i - W] >= T && F[n] === target) { F[n] = color; next.push(n); }
        if (i < W * (H - 1) && L[n = i + W] >= T && F[n] === target) { F[n] = color; next.push(n); }
      }
      front = next; if (!front.length) break;
    }
  }
  function nearest(x, y, want, radius) { // the closest pixel for which want(i) holds, looking ring by ring
    var W = st.W, H = st.H, r, dx, dy, nx, ny;
    for (r = 1; r <= radius; r++) for (dy = -r; dy <= r; dy++) for (dx = -r; dx <= r; dx++) {
      if (Math.max(Math.abs(dx), Math.abs(dy)) !== r) continue;
      nx = x + dx; ny = y + dy; if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
      if (want(ny * W + nx)) return ny * W + nx;
    }
    return -1;
  }
  function fillAt(x, y, color) {
    var W = st.W, L = st.L, F = st.fill, bar = st.bar, i0 = y * W + x, region = null, target;
    if (L[i0] < T) { i0 = nearest(x, y, function (j) { return L[j] >= T; }, 5); if (i0 < 0) return false; }
    target = F[i0]; if (target === color) return false;
    var snap = F.slice();
    if (!bar[i0]) region = flood(i0, target, true, 0);
    else {
      region = flood(i0, target, false, TINY);                                  // a small spot next to a line: fill it as it is
      if (!region) { var j = nearest(i0 % W, (i0 / W) | 0, function (k) { return L[k] >= T && !bar[k]; }, 10); if (j >= 0) { region = flood(j, F[j], true, 0); target = F[j]; } }
    }
    if (!region || !region.length) return false;
    if (st.undo.length >= UNDO) st.undo.shift();
    st.undo.push(snap);
    for (var k = 0; k < region.length; k++) F[region[k]] = color;
    if (st.seal) spread(region, target, color, st.seal + 1);
    return true;
  }
  canvas.addEventListener("pointerup", function (e) {
    if (!st.L) return;
    var rc = canvas.getBoundingClientRect(), x = Math.floor((e.clientX - rc.left) * st.W / rc.width), y = Math.floor((e.clientY - rc.top) * st.H / rc.height);
    if (x < 0 || y < 0 || x >= st.W || y >= st.H) return;
    if (fillAt(x, y, pack(st.color))) { render(); status("塗りました。続けて塗れます。"); } else status("線の上は塗れません。線の内側をタップしてください。");
  });

  // palette
  var pal = $("#nu-palette");
  pal.innerHTML = COLORS.map(function (c, n) { return '<button type="button" class="nu-c' + (n === 0 ? " on" : "") + '" style="background:' + c + '" data-c="' + c + '" aria-label="' + (c === "#ffffff" ? "白(消しゴム)" : "色 " + (n + 1)) + '"></button>'; }).join("") +
    '<label class="nu-own">自分の色<input type="color" value="#ff4d6d" aria-label="好きな色"></label>';
  function choose(c) { st.color = c; $$(".nu-c", pal).forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-c") === c); }); }
  pal.addEventListener("click", function (e) { var b = e.target.closest(".nu-c"); if (b) choose(b.getAttribute("data-c")); });
  $(".nu-own input", pal).addEventListener("input", function (e) { choose(e.target.value); });

  // buttons
  $("#nu-undo").addEventListener("click", function () { if (st.undo.length) { st.fill = st.undo.pop(); render(); status("ひとつ戻しました。"); } else status("戻せる操作はありません。"); });
  $("#nu-reset").addEventListener("click", function () { if (!st.L) return; pushUndo(); st.fill = new Uint32Array(st.W * st.H); render(); status("白紙に戻しました(「ひとつ戻す」で元に戻せます)。"); });
  $("#nu-save").addEventListener("click", function () {
    if (!st.L) return;
    canvas.toBlob(function (b) { var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "nurie-" + st.id + ".png"; document.body.appendChild(a); a.click(); a.remove(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000); status("保存しました。"); }, "image/png");
  });
  $("#nu-print").addEventListener("click", function () {
    if (!st.L) return;
    var box = $("#nu-printbox"); box.innerHTML = '<img alt="' + esc(st.title) + '" src="' + canvas.toDataURL("image/png") + '">'; box.hidden = false;
    document.body.classList.add("nu-printing");
    var img = $("img", box), done = function () { window.print(); document.body.classList.remove("nu-printing"); box.hidden = true; box.innerHTML = ""; };
    if (img.complete) done(); else img.onload = done;
  });
  $("#nu-other").addEventListener("click", function () { stage.hidden = true; $("#nu-pick").scrollIntoView({ behavior: "smooth", block: "start" }); });

  // the pictures to choose from: every line drawing of the library
  fetch("/data/items.json").then(function (r) { return r.json(); }).then(function (rows) {
    var lines = rows.filter(function (r) { return r[4] === "lineart" && /^[a-z0-9][a-z0-9-]*$/.test(r[0]); });
    $("#nu-list").innerHTML = '<ul class="nu-list">' + lines.map(function (r) { return '<li><button type="button" class="nu-pickbtn" data-id="' + esc(r[0]) + '" data-title="' + esc(r[1]) + '"><span class="checker"><img src="/thumbs/' + esc(r[0]) + '.webp" alt="" width="120" height="' + Math.round(120 * r[7] / r[6]) + '" loading="lazy"></span><b>' + esc(r[1]) + "</b></button></li>"; }).join("") + "</ul>";
    $("#nu-count").textContent = lines.length + "点";
    var first = new URLSearchParams(location.search).get("id");
    if (first) { var hit = lines.filter(function (r) { return r[0] === first; })[0]; if (hit) load(hit[0], hit[1]); }
  }).catch(function () { $("#nu-list").innerHTML = "<p>絵の一覧を読み込めませんでした。時間を置いてもう一度開いてください。</p>"; });
  $("#nu-list").addEventListener("click", function (e) { var b = e.target.closest(".nu-pickbtn"); if (b) load(b.getAttribute("data-id"), b.getAttribute("data-title")); });
  window.minnaNurie = { _state: st, _fillAt: fillAt, _render: render, _pack: pack };   // for the page's own checks
})();
