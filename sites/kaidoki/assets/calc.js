/* 実質価格の計算。入力は利用者が自分で入れた数字だけ。値はどこにも送らない・保存しない。 */
(function () {
  function num(v) { var n = parseFloat(String(v).replace(/,/g, "")); return isFinite(n) && n > 0 ? n : 0; }
  function compute(o) {
    var price = num(o.price), ship = num(o.ship), coupon = Math.min(num(o.coupon), price);
    var rate = num(o.rate), cap = num(o.cap), use = Math.min(Math.max(num(o.use), 0), 100);
    var after = price - coupon;
    var base = o.excl_tax ? after / 1.1 : after;
    var raw = Math.floor(base * rate / 100);
    var pts = cap > 0 ? Math.min(raw, cap) : raw;
    var capped = cap > 0 && raw > cap;
    var usable = Math.floor(pts * use / 100);
    var pay = after + ship;
    return { pay: pay, points: pts, capped: capped, usable: usable, real: pay - usable, rate_eff: pay > 0 ? usable / pay * 100 : 0 };
  }
  function yen(n) { return Math.round(n).toLocaleString("ja-JP") + "円"; }
  if (typeof module !== "undefined") { module.exports = { compute: compute }; }
  if (typeof document === "undefined") { return; }
  function read(col) {
    var q = function (k) { return col.querySelector('[name="' + k + '"]'); };
    return { price: q("price").value, ship: q("ship").value, coupon: q("coupon").value, rate: q("rate").value, cap: q("cap").value,
             use: q("use").value, excl_tax: q("excl_tax").checked };
  }
  function show(col) {
    var r = compute(read(col)), out = col.querySelector(".calc-out");
    if (!read(col).price) { out.innerHTML = "<p>商品の価格を入れると、ここに結果が出ます。</p>"; return; }
    out.innerHTML = '<dl class="calc-dl"><dt>支払う金額</dt><dd>' + yen(r.pay) + '</dd><dt>付くポイント</dt><dd>' + r.points.toLocaleString("ja-JP") +
      'ポイント' + (r.capped ? '(上限で止まっています)' : '') + '</dd><dt>使い切るポイント</dt><dd>' + r.usable.toLocaleString("ja-JP") +
      'ポイント</dd><dt>実質価格</dt><dd class="calc-real">' + yen(r.real) + '</dd></dl>';
  }
  document.querySelectorAll(".calc-col").forEach(function (col) {
    col.addEventListener("input", function () { show(col); });
    col.addEventListener("change", function () { show(col); });
    show(col);
  });
})();
