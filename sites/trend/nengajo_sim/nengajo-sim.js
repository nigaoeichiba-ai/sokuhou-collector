/* 年賀状印刷の総額シミュレーター(今日の話題)。
 * 数字は各社の公式料金ページ(2026-11-13 確認。各社の締切は 2026-11-17 確認、年賀状スクエアの46%OFF価格と締切は 2026-11-19 確認。45%OFF(11/24〜11/29 23:59。11/28に公式で延長を確認)の21〜30枚の印刷代3,912円は 2026-11-24 と 11-28 に公式で確認、ほかの枚数の45%OFF価格は通常価格×55%から計算した目安)。金額は税込、割引がかかるのは印刷代だけ。
 * 計算は compute() で行い、ブラウザの画面(下半分)はその結果を並べるだけ。 */
(function (root) {
  "use strict";
  var CHECKED = "2026-11-28";
  var POSTCARD = 85;       // 年賀はがき1枚(Rakpo だけ 80 円)
  var JST = "+09:00";
  function at(s) { return Date.parse(s + JST); }

  var SQUARE_NORMAL = [6029, 6560, 7113, 7701, 8136, 9126, 9688, 10047, 10437, 10974, 11763, 12437, 13246, 13706, 14168, 14625, 14987, 15350, 15725, 16407];
  // 45%OFF(期間限定セール 11/24〜11/29 23:59): 21〜30枚(3,912円)は公式の価格表で確認。ほかの帯は通常価格×55%の計算値(目安)
  var SQUARE_SALE45 = [3316, 3608, 3912, 4236, 4475, 5019, 5328, 5526, 5740, 6036, 6470, 6840, 7285, 7538, 7792, 8044, 8243, 8442, 8649, 9024];
  var SQUARE_SALE = [3256, 3543, 3842, 4159, 4394, 4929, 5232, 5426, 5637, 5926, 6352, 6716, 7153, 7401, 7651, 7898, 8093, 8289, 8492, 8860];   // 46%OFF(お買い得定番・カラー)

  // 挨拶状ドットコム: 5〜50枚は5枚刻み、60〜100枚は10枚刻み。[枚数, 通常価格, 40%OFF価格]
  var AISATSU = [[5, 4262, 2557], [10, 4840, 2904], [15, 5472, 3283], [20, 6105, 3663], [25, 6737, 4042], [30, 7370, 4422], [35, 8002, 4801],
    [40, 8635, 5181], [45, 9267, 5560], [50, 9900, 5940], [60, 11055, 6633], [70, 12210, 7326], [80, 13365, 8019], [90, 14520, 8712], [100, 15675, 9405]];

  // Rakpo: 10〜100枚(10枚刻み)。[枚数, 定価, 55%OFF価格]
  var RAKPO = [[10, 5200, 2340], [20, 5700, 2565], [30, 6200, 2790], [40, 6700, 3015], [50, 7200, 3240], [60, 7700, 3465], [70, 8200, 3690], [80, 8700, 3915], [90, 9200, 4140], [100, 9700, 4365]];

  var DEADLINES = {
    square: { until: at("2026-11-30T00:00:00"), label: "11月29日(日)23:59", rate: "45%OFF", first: at("2026-11-24T00:00:00"), firstLabel: "11月23日(月)23:59", firstRate: "46%OFF" },
    shimauma: { until: at("2026-11-30T13:00:00"), label: "11月30日(月)12:59", rate: "12%OFF" },
    aisatsu: { until: at("2026-11-24T00:00:00"), label: "11月23日(月)24:00", rate: "40%OFF" },
    rakpo: { until: at("2026-11-17T02:00:00"), label: "11月16日(月)26:00", rate: "55%OFF" }
  };

  var LINKS = {
    square: ["年賀状スクエア", "https://nenga.print-netsquare.com/info/price/", "年賀状スクエア 料金表"],
    shimauma: ["しまうまプリント", "https://nenga.n-pri.jp/price/", "しまうまプリント 年賀状印刷の価格"],
    aisatsu: ["挨拶状ドットコム", "https://nenga-org.aisatsujo.jp/guide/order/price.html", "挨拶状ドットコム 価格"],
    rakpo: ["Rakpo", "https://rakpo.com/price/", "Rakpo 価格"]
  };

  function ceilStep(rows, n, key) {   // n 以上でいちばん小さい掲載枚数の行
    for (var i = 0; i < rows.length; i++) if ((key ? rows[i][0] : rows[i]) >= n) return i;
    return -1;
  }

  function sale(company, now) { return now < DEADLINES[company].until; }

  function row(company, o) {
    var r = { id: company, name: LINKS[company][0], onSale: o.onSale, saleLabel: DEADLINES[company].label, saleRate: DEADLINES[company].rate,
      postcard: o.postcard, print: o.print, printMax: o.printMax == null ? o.print : o.printMax, address: o.address, shipping: o.shipping,
      estimate: !!o.estimate, unavailable: !!o.unavailable, notes: o.notes || [], printQty: o.printQty };
    if (!o.unavailable) {
      r.min = r.postcard + r.print + r.address + r.shipping;
      r.max = r.postcard + r.printMax + r.address + r.shipping;
    }
    return r;
  }

  // opts: { qty: 10〜200, address: bool, aisatsuLogin: bool, now: ミリ秒(省略で現在) }
  function compute(opts) {
    var n = Math.floor(Number(opts.qty));
    var now = opts.now == null ? Date.now() : opts.now;
    if (!(n >= 10 && n <= 200)) return { ok: false, error: "枚数は10〜200の整数で入れてください。" };
    var addr = !!opts.address, out = [], i;

    // 年賀状スクエア: 帯(10枚ごと)の料金。宛名印刷・送料は0円
    // 11/23 23:59 までは46%OFF、11/24 0:00〜11/29 23:59 は45%OFF(期間限定セールが入れ替わった)
    var s = sale("square", now);
    var sq = DEADLINES.square, first = now < sq.first;
    i = Math.ceil(n / 10) - 1;
    var sqPrint = !s ? SQUARE_NORMAL[i] : (first ? SQUARE_SALE : SQUARE_SALE45)[i];
    var sqNotes = addr ? ["宛名印刷は、会員なら無料です"] : [];
    if (s && !first && i !== 2) sqNotes.push("45%OFFの印刷代は、通常価格から割引率で計算した目安です。21〜30枚の3,912円だけが公式の価格表で確認した金額です。注文画面で、最終の金額を確認しておきましょう");
    var sqRow = row("square", { onSale: s, postcard: POSTCARD * n, print: sqPrint, address: 0, shipping: 0, notes: sqNotes });
    if (s && first) { sqRow.saleLabel = sq.firstLabel; sqRow.saleRate = sq.firstRate; }
    out.push(sqRow);

    // しまうまプリント: 1枚の単価×枚数。枚数割のあとに早割
    s = sale("shimauma", now);
    var vr = n >= 200 ? 45 : n >= 100 ? 35 : n >= 50 ? 25 : n >= 30 ? 15 : 0;
    var unit = Math.floor(165 * (100 - vr) / 100);
    if (s) unit = Math.floor(unit * 88 / 100);
    out.push(row("shimauma", { onSale: s, postcard: POSTCARD * n, print: unit * n, address: 0, shipping: n <= 108 ? 330 : 880, printQty: n,
      notes: ["1枚あたり印刷代" + unit + "円(枚数割を適用)。送料はゆうパケット330円(108枚まで)、109枚以上はゆうパック880円です"].concat(addr ? ["宛名印刷は無料です。投函代行を選ぶと送料は0円になります(条件は公式ページで確認)"] : []) }));

    // 挨拶状ドットコム: 公式表は100枚まで
    s = sale("aisatsu", now);
    if (n > 100) {
      out.push(row("aisatsu", { onSale: s, unavailable: true, notes: ["公式の料金表は100枚までです。101枚以上は、同社の見積もりシミュレーションで確認できます"] }));
    } else {
      i = ceilStep(AISATSU, n, true);
      var login = !!opts.aisatsuLogin;
      out.push(row("aisatsu", { onSale: s, postcard: POSTCARD * n, print: AISATSU[i][s ? 2 : 1], address: addr ? Math.floor(n * 253 / 10) : 0, shipping: login ? 0 : 330,
        estimate: AISATSU[i][0] !== n, printQty: AISATSU[i][0],
        notes: ["はがき代は、同社の価格ページにある1枚85円で計算しています。年賀はがきは売り切れると注文できなくなります。注文する前に、同社の注文画面で、はがきが選べるかを確かめておきましょう"]
          .concat(addr ? ["宛名印刷は1件25.3円(基本料金は2027年1月11日まで0円)"] : [])
          .concat(login ? ["マイページにログインして注文する場合の送料無料で計算しています"] : ["送料330円で計算しています。マイページにログインして注文すると0円です"]) }));
    }

    // Rakpo: 公式表は100枚まで。はがき代は80円
    s = sale("rakpo", now);
    if (n > 100) {
      out.push(row("rakpo", { onSale: s, unavailable: true, notes: ["公式の料金表は100枚までです。101枚以上は、同社の見積もりで確認できます"] }));
    } else {
      i = ceilStep(RAKPO, n, true);
      out.push(row("rakpo", { onSale: s, postcard: 80 * n, print: RAKPO[i][s ? 2 : 1], address: addr ? Math.floor(n * 275 / 10) : 0, shipping: 0,
        estimate: RAKPO[i][0] !== n, printQty: RAKPO[i][0],
        notes: ["はがき代は同社が5円引きした1枚80円です"].concat(addr ? ["宛名印刷は会員専用で、1件27.5円(税込)です"] : []) }));
    }

    // いちばん安い会社(計算できた会社のうち、総額の下限が最小のもの)
    var ok = out.filter(function (r) { return !r.unavailable; }).sort(function (a, b) { return a.min - b.min || a.max - b.max; });
    var rest = out.filter(function (r) { return r.unavailable; });
    var rows = ok.concat(rest);
    return { ok: true, qty: n, address: addr, now: now, rows: rows, cheapest: ok[0].id };
  }

  var api = { compute: compute, CHECKED: CHECKED, DEADLINES: DEADLINES, LINKS: LINKS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.NengajoSim = api;
  if (typeof document === "undefined") return;

  // ---- 画面 ----
  function yen(v) { return String(v).replace(/\B(?=(\d{3})+(?!\d))/g, ",") + "円"; }
  function esc(t) { return String(t).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function range(a, b) { return a === b ? yen(a) : yen(a) + "〜" + yen(b); }

  function render(res, box, summary) {
    if (!res.ok) { summary.textContent = res.error; box.innerHTML = ""; return; }
    var top = res.rows[0], others = res.rows.filter(function (r) { return !r.unavailable; });
    var worst = others[others.length - 1];
    summary.textContent = res.qty + "枚・宛名印刷" + (res.address ? "あり" : "なし") + "。総額が最も安いのは" + top.name + "で、" + range(top.min, top.max) + "です"
      + (worst !== top ? "(最も高い" + worst.name + "とは、下限どうしで" + yen(worst.min - top.min) + "の差)。" : "。");
    box.innerHTML = res.rows.map(function (r, k) {
      var badge = r.id === res.cheapest ? '<span class="nsim-best">最安</span>' : "";
      var state = r.onSale ? "早割" + r.saleRate + "適用中(" + r.saleLabel + "まで)" : "早割は終了しました。通常価格で計算しています";
      var head = '<div class="nsim-head"><span class="nsim-rank">' + (r.unavailable ? "-" : k + 1) + '</span><span class="nsim-name">' + esc(r.name) + "</span>" + badge
        + '<span class="nsim-total">' + (r.unavailable ? "公式で確認" : range(r.min, r.max)) + "</span></div>";
      var body = r.unavailable ? "" : '<dl class="nsim-dl"><div><dt>はがき代</dt><dd>' + yen(r.postcard) + "</dd></div><div><dt>印刷代</dt><dd>" + range(r.print, r.printMax)
        + "</dd></div><div><dt>宛名印刷</dt><dd>" + (r.address ? yen(r.address) : "0円") + "</dd></div><div><dt>送料</dt><dd>" + (r.shipping ? yen(r.shipping) : "0円") + "</dd></div></dl>";
      var tags = r.unavailable ? "" : '<p class="nsim-state' + (r.onSale ? "" : " ended") + '">' + esc(state) + "</p>";
      var notes = r.notes.slice();
      if (r.estimate) notes.unshift("公式の表に" + res.qty + "枚の掲載がないため、印刷代は" + r.printQty + "枚の価格で計算した目安です(実際の注文画面で、最終の金額を確認しておきましょう)");
      var nl = notes.length ? '<ul class="nsim-notes">' + notes.map(function (t) { return "<li>" + esc(t) + "</li>"; }).join("") + "</ul>" : "";
      return '<li class="nsim-item' + (r.id === res.cheapest ? " best" : "") + '">' + head + body + tags + nl + "</li>";
    }).join("");
  }

  function nowFromUrl() {
    try { var m = /[?&]now=([^&]+)/.exec(location.search); if (m) { var t = Date.parse(decodeURIComponent(m[1]) + JST); if (!isNaN(t)) return t; } } catch (e) {}
    return null;
  }

  function start() {
    var form = document.getElementById("nsim-form");
    if (!form) return;
    var box = document.getElementById("nsim-results"), summary = document.getElementById("nsim-summary");
    var qty = document.getElementById("nsim-qty"), login = document.getElementById("nsim-login");
    var fixed = nowFromUrl();
    function go() {
      var addr = form.querySelector('input[name="nsim-addr"]:checked');
      render(compute({ qty: qty.value, address: addr && addr.value === "yes", aisatsuLogin: login.checked, now: fixed }), box, summary);
    }
    form.addEventListener("submit", function (e) { e.preventDefault(); go(); });
    form.addEventListener("input", go);
    form.addEventListener("change", go);
    go();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})(typeof window !== "undefined" ? window : this);
