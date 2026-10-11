/* 贈り物ドック: the person describes whom they want to give to; the report (grade, a line per item with its number and evaluation, three kinds to look for with
   their reasons, notes) is worked out here in the browser from dock/data.json (made by the build from the site's own products and surveys) and ask/rec.json.
   What is typed is not sent anywhere.  Only, if the box is ticked, the options chosen are counted (api/ask.php op "stat": a counter per option, nothing else). */
(function () {
  "use strict";
  var DAY = 86400000;
  var W = { budget: 25, time: 20, info: 20, clarity: 20, risk: 15 };
  var AVOID_ZERO = { scent: ["bath_care", "beauty"], sweet: ["sweets"], alcohol: ["alcohol"] };
  var AVOID_HALF = { allergy: ["sweets", "gourmet"], bulky: ["cozy_home", "kitchen", "outdoor"] };
  // Where a survey says what is usual for an occasion, the kind gets a point or two (the source is shown next to it).
  var OCC_BONUS = {
    "mothers-day": [{ g: "plants", w: 2, why: "母の日に贈る予定の品では、カーネーションなどの花が44%で最多(エン・ジャパン 2025年、903人)" }],
    "fathers-day": [{ g: "alcohol", w: 2, why: "父の日に贈る予定の品では、お酒・ドリンクが38%で最多(エン・ジャパン 2025年、903人)" }],
    "valentine": [{ g: "sweets", w: 3, why: "バレンタインに渡したいものの1位は、男女とも、チョコレート(クロス・マーケティング 2026年、1,100人)" }],
    "ochugen": [{ g: "sweets", w: 2, why: "お中元に贈った品で最多は、和菓子・洋菓子の44.1%(郵便局のネットショップ 2025年、408人)" }]
  };
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function yen(n) { return "¥" + Math.round(n).toLocaleString("ja-JP"); }
  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function clamp(x, a, b) { return Math.max(a, Math.min(b, x)); }
  function isoLocal(d) { return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2); }
  function parseDay(s) { var p = s.split("-"); return new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2])); }

  // ---------------------------------------------------------------- the report (a pure function: the tests call it with data and an input)
  function diagnose(inp, data, rec, todayStr) {
    var today = parseDay(todayStr), occ = null, i;
    data.occasions.forEach(function (o) { if (o.slug === inp.occ) occ = o; });
    // the date: the one typed, or the next date of a day that is the same for everybody
    var target = null;
    if (inp.date) target = parseDay(inp.date);
    else if (occ && occ.dates.length) { for (i = 0; i < occ.dates.length; i++) { var dd = parseDay(occ.dates[i]); if (dd >= today) { target = dd; break; } } }
    var days = target ? Math.round((target - today) / DAY) : null;
    // the kinds: points from the interests, the types, the occasion; some kinds are taken out or halved by what the person avoids
    var score = {}, why = {}; function add(g, w, t) { if (!data.groups[g]) return; score[g] = (score[g] || 0) + w; (why[g] = why[g] || []).push(t); }
    (inp.interests || []).forEach(function (g) { add(g, 3, "「興味があるもの」で選ばれています"); });
    (inp.types || []).forEach(function (slug) { data.types.forEach(function (t) { if (t.slug === slug) for (var g in t.w) add(g, t.w[g], "タイプ「" + t.name + "」が好む傾向があります(編集部の目安)"); }); });
    ((occ && OCC_BONUS[occ.slug]) || []).forEach(function (b) { add(b.g, b.w, "調査: " + b.why); });
    var zero = {}, half = {};
    (inp.avoid || []).forEach(function (a) { (AVOID_ZERO[a] || []).forEach(function (g) { zero[g] = 1; }); (AVOID_HALF[a] || []).forEach(function (g) { half[g] = 1; }); });
    if (inp.age === "u20") zero.alcohol = 1;
    var ranked = Object.keys(score).filter(function (g) { return !zero[g]; }).map(function (g) { return { id: g, score: score[g] * (half[g] ? 0.5 : 1) }; })
      .sort(function (a, b) { return b.score - a.score || (a.id < b.id ? -1 : 1); });
    var top = ranked.slice(0, 3);
    var out = { days: days, target: target ? isoLocal(target) : null, occ: occ, top: top, zero: Object.keys(zero), rows: [] };
    // 1. budget against the price of the products (the occasion's, or the three kinds')
    var ref = occ && occ.range ? { n: occ.range.n, med: occ.range.med, p25: occ.range.p25, p75: occ.range.p75, label: "当サイトの「" + occ.name + "」の商品" } : null;
    if (!ref && top.length) {
      var rs = top.map(function (t) { return data.groups[t.id].range; }).filter(Boolean);
      if (rs.length) ref = { n: rs.reduce(function (a, r) { return a + r.n; }, 0), med: mean(rs, "med"), p25: mean(rs, "p25"), p75: mean(rs, "p75"), label: "おすすめの種類の商品" };
    }
    var budget = Number(inp.budget) > 0 ? Number(inp.budget) : null;
    var sBudget = null, cBudget;
    if (budget && ref) {
      var r = budget / ref.med; sBudget = r >= 0.8 && r <= 1.6 ? 100 : r < 0.8 ? clamp(Math.round(100 - (0.8 - r) / 0.8 * 100), 30, 100) : clamp(Math.round(100 - (r - 1.6) * 10), 70, 100);
      cBudget = "予算" + yen(budget) + "は、" + ref.label + "(" + ref.n + "点)の価格の中央値" + yen(ref.med) + "の" + (Math.round(r * 100) / 100) + "倍です。真ん中の半分の商品は、" + yen(ref.p25) + "〜" + yen(ref.p75) + "です。";
      if (r < 0.8) cBudget += " 予算より安い商品が多い価格帯です。選べる商品は、少なめになります。"; else if (r > 1.6) cBudget += " 予算に余裕があります。少し良いものも選べます。";
      if (occ && occ.facts.length) cBudget += " 調査では「" + occ.facts[0] + "」です(くわしくは、データ室)。";
    } else if (budget) { sBudget = null; cBudget = "予算" + yen(budget) + "を、比べる商品の数字が足りないため、点数にはしていません。"; }
    else cBudget = "予算が入力されていないため、点数にはしていません。";
    out.rows.push({ key: "budget", name: "予算", value: budget ? yen(budget) : "—", score: sBudget, comment: cBudget });
    // 2. time
    var sTime = null, cTime;
    if (days === null) cTime = "渡したい日が入力されていないため、点数にはしていません。";
    else if (days < 0) { sTime = 10; cTime = "渡したい日が、すぎています。遅れてもよいお祝いかどうかを確かめて、選びなおしてください。"; }
    else { sTime = days >= 28 ? 100 : days >= 21 ? 95 : days >= 14 ? 80 : days >= 7 ? 60 : days >= 3 ? 40 : 20;
      cTime = "渡したい日まで、あと" + days + "日。" + (days >= 21 ? "余裕があります。じっくり選べます。" : days >= 14 ? "まだ余裕があります。日付指定の商品は、早めの注文が安心です。" : days >= 7 ? "選ぶ時間は、あまり長くありません。届くまでの日数を、商品ページで確かめてください。" : "お急ぎです。翌日配送の商品や、受け取りやすい形を優先してください。"); }
    out.rows.push({ key: "time", name: "時期の余裕", value: days === null ? "—" : (days < 0 ? "すぎている" : "あと" + days + "日"), score: sTime, comment: cTime });
    // 3. what is known about the person
    var nInt = (inp.interests || []).length, nTy = (inp.types || []).length, nAv = (inp.avoid || []).length;
    var info = Math.min(60, 15 * nInt) + (nTy ? 15 : 0) + (inp.age ? 8 : 0) + (inp.gender ? 5 : 0) + (nAv ? 12 : 0);
    info = Math.min(100, info);
    out.rows.push({ key: "info", name: "相手の情報量", value: "興味" + nInt + "・タイプ" + nTy + "・避けたい" + nAv, score: info,
      comment: info >= 70 ? "手がかりが、そろっています。" : info >= 40 ? "手がかりは、ある程度あります。興味を1つ足すと、候補がしぼれます。" : "手がかりが少ない状態です。食べもの・飲みものなどの消えものが、無難です。" });
    // 4. how clear the favourite is
    var clarity, cClar;
    if (top.length >= 3) { var gap = (top[0].score - top[2].score) / top[0].score; clarity = Math.round(40 + 60 * gap); cClar = "1位の点が" + fmt(top[0].score) + "、3位が" + fmt(top[2].score) + "です。" + (gap >= 0.4 ? "好みの方向が、はっきりしています。" : "候補の差が小さく、決め手に欠けます。相手に、それとなく聞けると確実です。"); }
    else if (top.length) { clarity = 50; cClar = "候補になった種類が" + top.length + "つです。手がかりを足すと、比べられます。"; }
    else { clarity = null; cClar = "候補になる手がかりがありません。興味やタイプを選んでみてください。"; }
    out.rows.push({ key: "clarity", name: "好みの手がかり", value: top.length ? top.length + "種類" : "—", score: clarity, comment: cClar });
    // 5. how unlikely it is to go wrong
    var sRisk = null, cRisk;
    if (top.length) {
      var avg = top.reduce(function (a, t) { return a + data.groups[t.id].risk; }, 0) / top.length, adj = Math.max(0.05, avg - info / 100 * 0.15);
      sRisk = Math.round(100 * (1 - adj));
      cRisk = "1位の「" + data.groups[top[0].id].label + "」で起こりやすい失敗は、" + data.groups[top[0].id].risk_note + "。(編集部の目安で、統計ではありません)";
    } else cRisk = "候補がないため、点数にはしていません。";
    out.rows.push({ key: "risk", name: "外しにくさ", value: sRisk === null ? "—" : sRisk + "点", score: sRisk, comment: cRisk });
    // overall
    var tot = 0, wsum = 0; out.rows.forEach(function (row) { if (row.score !== null) { tot += row.score * W[row.key]; wsum += W[row.key]; } });
    out.total = wsum ? Math.round(tot / wsum) : null;
    out.grade = out.total === null ? "—" : out.total >= 85 ? "A" : out.total >= 70 ? "B" : out.total >= 55 ? "C" : out.total >= 40 ? "D" : "E";
    out.verdict = { A: "準備が、よく整っています。候補の中から選べば、外しにくい状態です。", B: "おおむね、準備ができています。足りないところを補えば、さらに選びやすくなります。", C: "もう少し、手がかりを足すと、選びやすくなります。", D: "手がかりか、時間が足りない状態です。無理に好みを当てず、無難な選び方をおすすめします。", E: "判断の材料が、かなり少ない状態です。まず、相手の好みを、それとなく聞いてみてください。" }[out.grade] || "入力が少ないため、総合評価は出せません。";
    out.rows.forEach(function (row) { row.eval = row.score === null ? "—" : row.score >= 75 ? "◎" : row.score >= 50 ? "○" : "△"; row.cls = row.score === null ? "mid" : row.score >= 75 ? "" : row.score >= 50 ? "mid" : "low"; });
    // notes
    var notes = [];
    if ((inp.avoid || []).indexOf("allergy") >= 0) notes.push("食物アレルギーがある相手です。食べものは、原材料の表示を必ず確かめてください。");
    if (zero.alcohol && inp.age === "u20") notes.push("20歳未満の相手には、お酒を勧めません。");
    if (inp.age === "60s" || inp.age === "70s") notes.push("軽くて扱いやすい品が向きます。細かい文字や、複雑な操作の品は、避けると安心です。");
    if (inp.memo) notes.push("メモ: " + inp.memo);
    if (!occ) notes.push("贈る目的が決まっていないため、イベント向けの数字は使っていません。");
    out.notes = notes;
    out.budget = budget;
    return out;
  }
  function mean(rs, k) { return Math.round(rs.reduce(function (a, r) { return a + r[k]; }, 0) / rs.length); }
  function fmt(x) { return Math.round(x * 10) / 10; }

  // ---------------------------------------------------------------- the page
  function readInput(form) {
    function vals(name) { return $$("input[name=" + name + "]:checked", form).map(function (x) { return x.value; }); }
    return { occ: form.elements.occ.value, date: form.elements.date.value, gender: form.elements.gender.value, age: form.elements.age.value, types: vals("type").slice(0, 2),
      interests: vals("int").slice(0, 5), avoid: vals("avoid"), budget: form.elements.budget.value, memo: (form.elements.memo.value || "").replace(/\s+/g, " ").trim().slice(0, 80) };
  }
  function renderReport(box, rep, inp, data, rec) {
    var Rec = window.YorokobuRec, h = '<article class="sheet"><div class="sheet-head"><div class="sheet-grade" aria-label="総合評価">' + esc(rep.grade) + '</div><div><h2>贈り物ドック 結果票</h2>' +
      '<p class="sheet-score"><b>' + (rep.total === null ? "—" : rep.total) + '</b><small> / 100点 総合評価 ' + esc(rep.grade) + '</small></p><p class="sheet-case">' + esc(rep.verdict) + '</p>' +
      '<p class="sheet-case">' + esc(caseLine(rep, inp)) + '</p></div></div>';
    h += '<table><thead><tr><th>項目</th><th>入力・数値</th><th>点数</th><th>評価</th><th>コメント</th></tr></thead><tbody>' + rep.rows.map(function (r) {
      return '<tr><th scope="row">' + esc(r.name) + '</th><td class="num" data-h="入力・数値">' + esc(r.value) + '</td><td class="num" data-h="点数">' + (r.score === null ? "—" : r.score) + '</td><td data-h="評価"><span class="ev ' + r.cls + '">' + r.eval + '</span></td><td>' + esc(r.comment) + "</td></tr>";
    }).join("") + "</tbody></table>";
    h += "<h3>おすすめの種類(上位3つ)</h3>";
    if (!rep.top.length) h += '<p class="sheet-note">候補になる手がかりがありません。興味やタイプを選んで、もう一度診断してください。</p>';
    rep.top.forEach(function (t, i) {
      var g = data.groups[t.id], rg = rec && rec.groups[t.id], reasons = (t.why || []).slice();
      var lines = reasonsOf(inp, rep, t, data);
      h += '<div class="sheet-kind"><h4>' + (i + 1) + ". " + esc(g.label) + "<small>(合計 " + fmt(t.score) + "点)</small></h4><ul>" + lines.map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + "</ul>" +
        (rg && Rec ? Rec.block(rg, { max: rep.budget ? Math.round(rep.budget * 1.15) : null, gender: inp.gender, n: 4 }) : "") + "</div>";
    });
    h += '<div class="sheet-note"><b>備考</b><ul>' + (rep.notes.length ? rep.notes.map(function (n) { return "<li>" + esc(n) + "</li>"; }).join("") : "<li>特記事項はありません。</li>") + "</ul></div>";
    h += '<p class="sheet-note">計算のしかたは、ページ下の「診断のしくみ」に書いています。「外しにくさ」と、タイプの好みは編集部の目安で、統計ではありません。価格・在庫は' + esc(rec ? rec.fresh : "") + "時点の情報です。</p>";
    h += '<div class="sheet-tools"><button type="button" class="btn" data-print>印刷する</button><button type="button" class="btn btn-sub" data-img>画像で保存</button><button type="button" class="btn btn-sub" data-copy>結果をコピー</button>' + links(rep, inp) + "</div></article>";
    box.innerHTML = h; box.hidden = false;
    $("[data-print]", box).onclick = function () { window.print(); };
    $("[data-copy]", box).onclick = function () { if (navigator.clipboard) navigator.clipboard.writeText(summary(rep, data)); this.textContent = "コピーしました"; };
    $("[data-img]", box).onclick = function () { saveImage(rep, data); };
    box.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function caseLine(rep, inp) {
    var bits = []; if (rep.occ) bits.push(rep.occ.name); if (rep.target) bits.push(rep.target.replace(/-/g, "/") + "まで"); if (inp.age) bits.push({ u20: "10代以下", "20s": "20代", "30s": "30代", "40s": "40代", "50s": "50代", "60s": "60代", "70s": "70代以上" }[inp.age]);
    if (inp.gender) bits.push(inp.gender === "f" ? "女性" : "男性"); return "診断した内容: " + (bits.join(" / ") || "(目的・日付は未入力)");
  }
  function reasonsOf(inp, rep, t, data) {
    var g = data.groups[t.id], lines = [];
    if ((inp.interests || []).indexOf(t.id) >= 0) lines.push("選んだ「興味があるもの」に入っています。");
    (inp.types || []).forEach(function (slug) { data.types.forEach(function (ty) { if (ty.slug === slug && ty.w[t.id]) lines.push("タイプ「" + ty.name + "」が好む傾向があります(編集部の目安)。"); }); });
    ((rep.occ && OCC_BONUS[rep.occ.slug]) || []).forEach(function (b) { if (b.g === t.id) lines.push("調査: " + b.why + "。"); });
    if (g.range) lines.push("当サイトの" + g.label + "の商品(" + g.range.n + "点)は、価格の中央値が" + yen(g.range.med) + "、真ん中の半分が" + yen(g.range.p25) + "〜" + yen(g.range.p75) + "です。" +
      (rep.budget ? (rep.budget >= g.range.p25 ? "予算は、この範囲に届いています。" : "予算が、この価格帯より低めです。小さな品を選ぶ必要があります。") : ""));
    lines.push("起こりやすい失敗: " + g.risk_note + "(編集部の目安)。");
    return lines;
  }
  function links(rep, inp) {
    var h = ""; if (rep.occ && rep.occ.board) h += '<a class="btn btn-sub" href="' + esc(rep.occ.board) + '">' + esc(rep.occ.name) + "の調査(データ室)</a>";
    if (rep.occ) h += '<a class="btn btn-sub" href="/occasion/' + esc(rep.occ.slug) + '/">' + esc(rep.occ.name) + "のおすすめ</a>";
    return h;
  }
  function summary(rep, data) {
    return "贈り物ドックの結果: 総合評価" + rep.grade + (rep.total === null ? "" : "(" + rep.total + "点)") + "。おすすめの種類: " + (rep.top.map(function (t) { return data.groups[t.id].label; }).join("、") || "なし") + "。\n" + location.origin + "/dock/";
  }
  function saveImage(rep, data) {
    var FONT = '"Zen Kaku Gothic New","Hiragino Sans","Yu Gothic UI","Meiryo",sans-serif', Wd = 1080, rows = rep.rows, tops = rep.top, H = 460 + rows.length * 78 + (tops.length ? 90 + tops.length * 64 : 0) + 130;
    var c = document.createElement("canvas"); c.width = Wd; c.height = H; var g = c.getContext("2d");
    g.fillStyle = "#fbf6ee"; g.fillRect(0, 0, Wd, H); g.fillStyle = "#fff"; g.strokeStyle = "#e9dfd0"; g.lineWidth = 3;
    g.beginPath(); if (g.roundRect) g.roundRect(24, 24, Wd - 48, H - 48, 32); else g.rect(24, 24, Wd - 48, H - 48); g.fill(); g.stroke();
    g.fillStyle = "#2b2621"; g.font = "700 46px " + FONT; g.fillText("贈り物ドック 結果票", 70, 118);
    g.fillStyle = "#fde8e3"; g.beginPath(); if (g.roundRect) g.roundRect(70, 160, 190, 190, 36); else g.rect(70, 160, 190, 190); g.fill();
    g.fillStyle = "#c63a2a"; g.font = "800 120px " + FONT; g.textAlign = "center"; g.fillText(rep.grade, 165, 300); g.textAlign = "left";
    g.fillStyle = "#2b2621"; g.font = "700 64px " + FONT; g.fillText((rep.total === null ? "—" : rep.total) + "点", 300, 245);
    g.font = "400 28px " + FONT; g.fillStyle = "#4a423b"; wrap(g, rep.verdict, 300, 292, Wd - 370, 40, 2);
    var y = 420; g.font = "700 26px " + FONT; g.fillStyle = "#766c62"; g.fillText("項目", 70, y); g.fillText("入力・数値", 360, y); g.fillText("点数", 700, y); g.fillText("評価", 820, y);
    rows.forEach(function (r) { y += 78; g.strokeStyle = "#f2e9db"; g.lineWidth = 2; g.beginPath(); g.moveTo(70, y - 50); g.lineTo(Wd - 70, y - 50); g.stroke();
      g.fillStyle = "#2b2621"; g.font = "700 30px " + FONT; g.fillText(r.name, 70, y); g.font = "400 28px " + FONT; g.fillText(clip(g, r.value, 300), 360, y); g.fillText(r.score === null ? "—" : String(r.score), 700, y); g.font = "700 34px " + FONT; g.fillText(r.eval, 830, y); });
    if (tops.length) { y += 90; g.fillStyle = "#c63a2a"; g.font = "700 30px " + FONT; g.fillText("おすすめの種類", 70, y); tops.forEach(function (t, i) { y += 64; g.fillStyle = "#2b2621"; g.font = "400 32px " + FONT; g.fillText((i + 1) + ".  " + data.groups[t.id].label, 70, y); }); }
    g.fillStyle = "#766c62"; g.font = "400 24px " + FONT; g.fillText("よろこぶプレゼント  yorokobu-present.com  (点数の一部は編集部の目安です)", 70, H - 66);
    c.toBlob(function (blob) {
      if (!blob) return; var file = null; try { file = new File([blob], "okurimono-dock.png", { type: "image/png" }); } catch (e) {}
      if (file && navigator.canShare && navigator.share && navigator.canShare({ files: [file] })) { navigator.share({ files: [file], title: "贈り物ドック 結果票" }).catch(function () {}); return; }
      var a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "okurimono-dock.png"; document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
    }, "image/png");
  }
  function wrap(g, text, x, y, w, lh, maxLines) { var line = "", n = 0; for (var i = 0; i < text.length; i++) { if (g.measureText(line + text[i]).width > w && line) { g.fillText(line, x, y + n * lh); n++; line = ""; if (n >= maxLines) return; } line += text[i]; } if (line) g.fillText(line, x, y + n * lh); }
  function clip(g, t, w) { t = String(t); while (g.measureText(t).width > w && t.length > 2) t = t.slice(0, -2) + "…"; return t; }

  // counters: how often an option was chosen (the names of the options, nothing typed, nothing that identifies a visitor)
  function band(days) { return days === null ? "none" : days < 0 ? "past" : days < 7 ? "d0-6" : days < 14 ? "d7-13" : days < 21 ? "d14-20" : "d21up"; }
  function bandBudget(b) { return !b ? "none" : b <= 2000 ? "b2000" : b <= 5000 ? "b5000" : b <= 10000 ? "b10000" : b <= 20000 ? "b20000" : "bmore"; }
  function counterKeys(inp, rep) {
    var k = ["dock.n.all", "dock.occ." + (inp.occ || "none"), "dock.age." + (inp.age || "none"), "dock.gender." + (inp.gender || "none"), "dock.grade." + rep.grade, "dock.budget." + bandBudget(rep.budget), "dock.days." + band(rep.days)];
    (inp.interests || []).forEach(function (x) { k.push("dock.int." + x); }); (inp.types || []).forEach(function (x) { k.push("dock.type." + x); }); (inp.avoid || []).forEach(function (x) { k.push("dock.avoid." + x); });
    rep.top.slice(0, 1).forEach(function (t) { k.push("dock.top." + t.id); });
    return k.filter(function (x) { return /^dock\.[a-z0-9]{1,8}\.[a-z0-9_-]{1,32}$/.test(x); });
  }

  function init(root) {
    var form = $(".dock-form", root), box = $(".dock-report", root), data = null, rec = null;
    Promise.all([fetch(root.getAttribute("data-src")).then(function (r) { return r.json(); }), window.YorokobuRec.load(root.getAttribute("data-rec"))]).then(function (x) { data = x[0]; rec = x[1]; }).catch(function () { box.hidden = false; box.innerHTML = '<p class="notice">データを読み込めませんでした。時間をおいて、もう一度お試しください。</p>'; });
    function limitChecks(name, max) { $$("input[name=" + name + "]", form).forEach(function (x) { x.addEventListener("change", function () { var on = $$("input[name=" + name + "]:checked", form); $$("input[name=" + name + "]", form).forEach(function (y) { y.disabled = !y.checked && on.length >= max; }); }); }); }
    limitChecks("type", 2); limitChecks("int", 5);
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!data) { box.hidden = false; box.innerHTML = '<p class="notice">データを読み込んでいます。少し待ってから、もう一度押してください。</p>'; return; }
      var inp = readInput(form), d = new Date(), ts = d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2);
      var rep = diagnose(inp, data, rec, ts); renderReport(box, rep, inp, data, rec);
      var okc = $("input[name=count]", form);
      if (okc && okc.checked) { try { fetch("/api/ask.php", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ v: 1, op: "stat", k: counterKeys(inp, rep) }), keepalive: true }).catch(function () {}); } catch (err) {} }
    });
  }
  window.YorokobuDock = { diagnose: diagnose, counterKeys: counterKeys };
  function boot() { var r = $("#dock"); if (r) init(r); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
