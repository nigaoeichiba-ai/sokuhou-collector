/* A QR code generator for the pages of よろこぶプレゼント: draws the address of the page the visitor is on, so that a phone can open it from the screen of a PC.
   Byte mode (UTF-8), error correction level M, versions 1-10 (up to 213 bytes: an address of this site fits easily). Everything happens in the browser;
   nothing is sent anywhere.  The method follows the QR Code standard (ISO/IEC 18004): Reed-Solomon over GF(256), the eight masks and their penalty. */
(function () {
  "use strict";
  var ECC_PER_BLOCK = [0, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26];      // level M, versions 1..10
  var NUM_BLOCKS = [0, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5];

  function rawModules(ver) {
    var r = (16 * ver + 128) * ver + 64;
    if (ver >= 2) { var a = Math.floor(ver / 7) + 2; r -= (25 * a - 10) * a - 55; if (ver >= 7) r -= 36; }
    return r;
  }
  function dataCodewords(ver) { return Math.floor(rawModules(ver) / 8) - ECC_PER_BLOCK[ver] * NUM_BLOCKS[ver]; }

  function utf8(text) { return Array.prototype.slice.call(new TextEncoder().encode(text)); }

  // ---- Reed-Solomon
  var EXP = [], LOG = [];
  (function () { var x = 1; for (var i = 0; i < 255; i++) { EXP[i] = x; LOG[x] = i; x <<= 1; if (x & 256) x ^= 0x11D; } for (i = 255; i < 512; i++) EXP[i] = EXP[i - 255]; })();
  function gmul(a, b) { return a === 0 || b === 0 ? 0 : EXP[LOG[a] + LOG[b]]; }
  function generator(deg) {
    var g = [1];
    for (var i = 0; i < deg; i++) {
      var n = g.concat([0]);
      for (var j = 0; j < g.length; j++) { n[j + 1] ^= gmul(g[j], EXP[i]); }
      g = n;
    }
    return g;                                                           // g[0] is the leading coefficient (1)
  }
  function remainder(data, deg) {
    var g = generator(deg), res = new Array(deg).fill(0);
    data.forEach(function (b) {
      var f = b ^ res.shift();
      res.push(0);
      for (var i = 0; i < deg; i++) res[i] ^= gmul(g[i + 1], f);
    });
    return res;
  }

  function bitsOf(bytes, ver) {
    var bits = [];
    function put(v, n) { for (var i = n - 1; i >= 0; i--) bits.push((v >>> i) & 1); }
    put(4, 4); put(bytes.length, ver >= 10 ? 16 : 8);
    bytes.forEach(function (b) { put(b, 8); });
    var cap = dataCodewords(ver) * 8;
    put(0, Math.min(4, cap - bits.length));
    while (bits.length % 8) bits.push(0);
    for (var pad = 0xEC; bits.length < cap; pad ^= 0xEC ^ 0x11) put(pad, 8);
    var out = [];
    for (var i = 0; i < bits.length; i += 8) { var v = 0; for (var k = 0; k < 8; k++) v = (v << 1) | bits[i + k]; out.push(v); }
    return out;
  }

  function interleave(data, ver) {
    var nb = NUM_BLOCKS[ver], ecc = ECC_PER_BLOCK[ver], raw = Math.floor(rawModules(ver) / 8);
    var shortCount = nb - raw % nb, shortLen = Math.floor(raw / nb), blocks = [], k = 0;
    for (var i = 0; i < nb; i++) {
      var len = shortLen - ecc + (i < shortCount ? 0 : 1);
      var d = data.slice(k, k + len); k += len;
      blocks.push({ d: d, e: remainder(d, ecc) });
    }
    var out = [];
    for (i = 0; i < shortLen - ecc + 1; i++) blocks.forEach(function (b) { if (i < b.d.length) out.push(b.d[i]); });
    for (i = 0; i < ecc; i++) blocks.forEach(function (b) { out.push(b.e[i]); });
    return out;
  }

  function alignPositions(ver) {
    if (ver === 1) return [];
    var n = Math.floor(ver / 7) + 2, size = ver * 4 + 17;
    var step = ver === 32 ? 26 : Math.ceil((ver * 4 + 4) / (n * 2 - 2)) * 2, r = [6];
    for (var p = size - 7; r.length < n; p -= step) r.splice(1, 0, p);
    return r;
  }

  function build(text, forceMask) {
    var bytes = utf8(text), ver = 0;
    for (var v = 1; v <= 10; v++) { if (4 + (v >= 10 ? 16 : 8) + bytes.length * 8 <= dataCodewords(v) * 8) { ver = v; break; } }
    if (!ver) return null;
    var size = ver * 4 + 17, mod = [], fn = [], i, j;
    for (i = 0; i < size; i++) { mod.push(new Array(size).fill(false)); fn.push(new Array(size).fill(false)); }
    function set(x, y, dark) { mod[y][x] = dark; fn[y][x] = true; }
    for (i = 0; i < size; i++) { set(6, i, i % 2 === 0); set(i, 6, i % 2 === 0); }                      // timing
    [[3, 3], [size - 4, 3], [3, size - 4]].forEach(function (c) {                                      // finders with their separators
      for (var dy = -4; dy <= 4; dy++) for (var dx = -4; dx <= 4; dx++) {
        var x = c[0] + dx, y = c[1] + dy; if (x < 0 || y < 0 || x >= size || y >= size) continue;
        var d = Math.max(Math.abs(dx), Math.abs(dy)); set(x, y, d !== 2 && d !== 4);
      }
    });
    var al = alignPositions(ver);
    al.forEach(function (ax, a) { al.forEach(function (ay, b) {
      if ((a === 0 && b === 0) || (a === 0 && b === al.length - 1) || (a === al.length - 1 && b === 0)) return;
      for (var dy = -2; dy <= 2; dy++) for (var dx = -2; dx <= 2; dx++) set(ax + dx, ay + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
    }); });
    function drawFormat(mask) {
      var data = (0 << 3) | mask, rem = data;                                                           // level M = 00
      for (i = 0; i < 10; i++) rem = (rem << 1) ^ ((rem >>> 9) * 0x537);
      var bits = ((data << 10) | rem) ^ 0x5412;
      function bit(k) { return ((bits >>> k) & 1) !== 0; }
      for (i = 0; i <= 5; i++) set(8, i, bit(i));
      set(8, 7, bit(6)); set(8, 8, bit(7)); set(7, 8, bit(8));
      for (i = 9; i < 15; i++) set(14 - i, 8, bit(i));
      for (i = 0; i < 8; i++) set(size - 1 - i, 8, bit(i));
      for (i = 8; i < 15; i++) set(8, size - 15 + i, bit(i));
      set(8, size - 8, true);
    }
    drawFormat(0);                                                                                      // (reserves the cells; drawn again with the chosen mask)
    if (ver >= 7) {
      var r = ver; for (i = 0; i < 12; i++) r = (r << 1) ^ ((r >>> 11) * 0x1F25);
      var vb = (ver << 12) | r;
      for (i = 0; i < 18; i++) { var dark = ((vb >>> i) & 1) !== 0, a = size - 11 + i % 3, b = Math.floor(i / 3); set(a, b, dark); set(b, a, dark); }
    }
    var codewords = interleave(bitsOf(bytes, ver), ver), bi = 0, total = codewords.length * 8;
    for (var right = size - 1; right >= 1; right -= 2) {                                                // data, in the zigzag the standard prescribes
      if (right === 6) right = 5;
      for (var vert = 0; vert < size; vert++) for (j = 0; j < 2; j++) {
        var x = right - j, up = ((right + 1) & 2) === 0, y = up ? size - 1 - vert : vert;
        if (!fn[y][x] && bi < total) { mod[y][x] = ((codewords[bi >>> 3] >>> (7 - (bi & 7))) & 1) !== 0; bi++; }
      }
    }
    function applyMask(m) {
      for (var y = 0; y < size; y++) for (var x = 0; x < size; x++) {
        if (fn[y][x]) continue;
        var inv;
        switch (m) {
          case 0: inv = (x + y) % 2 === 0; break; case 1: inv = y % 2 === 0; break; case 2: inv = x % 3 === 0; break; case 3: inv = (x + y) % 3 === 0; break;
          case 4: inv = (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0; break; case 5: inv = x * y % 2 + x * y % 3 === 0; break;
          case 6: inv = (x * y % 2 + x * y % 3) % 2 === 0; break; default: inv = ((x + y) % 2 + x * y % 3) % 2 === 0;
        }
        if (inv) mod[y][x] = !mod[y][x];
      }
    }
    function penalty() {
      var p = 0, y, x, run, k;
      function line(get) {
        var runs = [], c = get(0); run = 1;
        for (k = 1; k < size; k++) { if (get(k) === c) run++; else { runs.push(run); run = 1; c = get(k); } }
        runs.push(run);
        return runs;
      }
      for (var dir = 0; dir < 2; dir++) for (y = 0; y < size; y++) {
        var get = dir === 0 ? function (t) { return mod[y][t]; } : function (t) { return mod[t][y]; };
        line(get).forEach(function (r) { if (r >= 5) p += r - 2; });
        for (x = 0; x + 10 < size; x++) {                                                              // 1:1:3:1:1 with four light modules at either end
          var s = ""; for (k = 0; k < 11; k++) s += get(x + k) ? "1" : "0";
          if (s === "10111010000" || s === "00001011101") p += 40;
        }
      }
      for (y = 0; y + 1 < size; y++) for (x = 0; x + 1 < size; x++) { var c = mod[y][x]; if (c === mod[y][x + 1] && c === mod[y + 1][x] && c === mod[y + 1][x + 1]) p += 3; }
      var dark = 0; mod.forEach(function (row) { row.forEach(function (c) { if (c) dark++; }); });
      p += Math.max(0, Math.ceil(Math.abs(dark * 20 - size * size * 10) / (size * size)) - 1) * 10;
      return p;
    }
    var best = 0, bestP = Infinity;
    for (var m = 0; m < 8; m++) { applyMask(m); drawFormat(m); var pp = penalty(); if (pp < bestP) { bestP = pp; best = m; } applyMask(m); }
    if (forceMask !== undefined) best = forceMask;
    applyMask(best); drawFormat(best);
    return { size: size, version: ver, modules: mod, mask: best };
  }

  function safe(t) { return String(t).replace(/[&<>"']/g, ""); }
  function svg(text, opts) {
    var q = build(text);
    if (!q) return "";
    opts = opts || {};
    var quiet = opts.quiet === undefined ? 4 : opts.quiet, n = q.size + quiet * 2, path = "";
    for (var y = 0; y < q.size; y++) for (var x = 0; x < q.size; x++) if (q.modules[y][x]) path += "M" + (x + quiet) + " " + (y + quiet) + "h1v1h-1z";
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + n + " " + n + '" shape-rendering="crispEdges" role="img" aria-label="' + safe(opts.label || "QRコード") + '">' +
      '<rect width="' + n + '" height="' + n + '" fill="#fff"/><path d="' + path + '" fill="' + safe(opts.color || "#2b2621") + '"/></svg>';
  }

  window.YorokobuQR = { build: build, svg: svg };
})();
