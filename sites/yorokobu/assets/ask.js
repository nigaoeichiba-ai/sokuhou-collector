/* 「それとなく聞く」アンケート: the page that makes the link (#ask-make), the page the other person answers on (#ask-respond) and the results (#ask-mine).
   A survey is {id, key}: the id is in the link, the key (kept only on the device that made it) is what lets that device read the answers (api/ask.php).
   The questions are in the page itself; the other person sends only the ids of the options they chose.  The results are added up and read in the browser. */
(function () {
  "use strict";
  var API = "/api/ask.php", LIST_KEY = "yorokobu.ask", PUSH_KEY = "yorokobu.ask.push", MAX_ANSWERS = 40;
  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function json(el) { try { return JSON.parse(el.getAttribute("data-json")); } catch (e) { return null; } }
  function store(k, v) { try { if (v === undefined) return JSON.parse(localStorage.getItem(k) || "null"); localStorage.setItem(k, JSON.stringify(v)); } catch (e) { return null; } }
  function rid() {
    var b = new Uint8Array(16); (window.crypto || window.msCrypto).getRandomValues(b);
    var s = ""; for (var i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
    return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "").slice(0, 22);
  }
  function api(op, body) {
    var data = { v: 1, op: op }; for (var k in body) data[k] = body[k];
    return fetch(API, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }).then(function (r) {
      return r.text().then(function (t) { var j = null; try { j = t ? JSON.parse(t) : null; } catch (e) {} return { status: r.status, json: j }; });
    });
  }
  function storageOk() { try { localStorage.setItem("yorokobu.t", "1"); localStorage.removeItem("yorokobu.t"); return true; } catch (e) { return false; } }
  function surveys() { var l = store(LIST_KEY); return Array.isArray(l) ? l : []; }
  function saveSurveys(l) { store(LIST_KEY, l.slice(0, 30)); }
  function today() { var d = new Date(); return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2); }

  // ---------------------------------------------------------------- the results: added up and read (pure functions, tested in the browser)
  var ORDER = ["b2000", "b5000", "b10000", "b20000", "bmore"], UPPER = { b2000: 2000, b5000: 5000, b10000: 10000, b20000: 20000, bmore: null };
  var AVOID_ZERO = { scent: ["bath_care", "beauty"], sweet: ["sweets"], alcohol: ["alcohol"] };       // a thing the person avoids takes its interest groups out
  var AVOID_HALF = { allergy: ["sweets", "gourmet"], bulky: ["cozy_home", "kitchen", "outdoor"] };   // and these are only asked for with care
  function analyze(qs, interests, rows) {
    var n = rows.length, per = {}, score = {}, contrib = {}, labels = {};
    qs.forEach(function (q) { per[q.id] = {}; q.options.forEach(function (o) { labels[q.id + "." + o.id] = o.label; }); });
    rows.forEach(function (r) {
      qs.forEach(function (q) {
        var chosen = r.a && r.a[q.id]; if (!chosen) return;
        chosen.forEach(function (oid) {
          var o = q.options.filter(function (x) { return x.id === oid; })[0]; if (!o) return;
          per[q.id][oid] = (per[q.id][oid] || 0) + 1;
          for (var g in (o.w || {})) { score[g] = (score[g] || 0) + o.w[g]; (contrib[g] = contrib[g] || {})[q.id + "." + oid] = (contrib[g][q.id + "." + oid] || 0) + o.w[g]; }
        });
      });
    });
    var avoidQ = qs.filter(function (q) { return q.key === "avoid"; })[0], budgetQ = qs.filter(function (q) { return q.key === "budget"; })[0];
    var avoid = {}, zero = {}, half = {};
    if (avoidQ) for (var a in per[avoidQ.id]) {
      avoid[a] = per[avoidQ.id][a];
      if (a === "none" || avoid[a] * 2 < n) continue;                                                // it counts when at least half of the people say so
      (AVOID_ZERO[a] || []).forEach(function (g) { zero[g] = 1; }); (AVOID_HALF[a] || []).forEach(function (g) { half[g] = 1; });
    }
    var ranked = Object.keys(score).filter(function (g) { return interests[g] && !zero[g]; }).map(function (g) { return { id: g, score: score[g] * (half[g] ? 0.5 : 1) }; })
      .sort(function (x, y) { return y.score - x.score || (x.id < y.id ? -1 : 1); });
    ranked.forEach(function (r) {
      r.reasons = Object.keys(contrib[r.id]).map(function (k) { return { label: labels[k], q: k.split(".")[0], count: per[k.split(".")[0]][k.split(".")[1]], w: contrib[r.id][k] }; })
        .sort(function (x, y) { return y.w - x.w || y.count - x.count; }).slice(0, 2);
    });
    var budget = null;
    if (budgetQ) {                                                                                     // the middle answer of the amounts people said they take easily
      var list = []; ORDER.forEach(function (b) { for (var i = 0; i < (per[budgetQ.id][b] || 0); i++) list.push(b); });
      if (list.length) budget = { band: list[Math.floor((list.length - 1) / 2)], count: list.length };
      if (budget) budget.upper = UPPER[budget.band];
    }
    return { n: n, per: per, ranked: ranked, avoid: avoid, zero: Object.keys(zero), half: Object.keys(half), budget: budget };
  }
  function pct(c, n) { return n ? Math.round(c / n * 100) : 0; }

  // ---------------------------------------------------------------- make the link
  function initMake(root) {
    var data = json(root), msg = $(".ask-msg", root), out = $(".ask-out", root), busy = false;
    function say(t) { msg.textContent = t; msg.hidden = !t; }
    $("[data-make]", root).addEventListener("click", function () {
      if (busy) return; say("");
      if (!storageOk()) return say("このブラウザは、結果を読むための鍵を保存できない設定です(プライベートモードなど)。通常のモードで開いてください。");
      busy = true;
      var mode = ($("input[name=mode]:checked", root) || {}).value === "s" ? "s" : "o", id = rid(), key = rid();
      api("new", { id: id, key: key, mode: mode }).then(function (r) {
        busy = false;
        if (r.status === 429) return say("今日は作れる数の上限に達しました。明日、もう一度お試しください。");
        if (r.status !== 204) return say("作れませんでした。時間をおいてもう一度お試しください。");
        var l = surveys(); l.unshift({ id: id, key: key, m: mode, c: today() }); saveSurveys(l);
        show(id, mode);
        resubscribe();
      }).catch(function () { busy = false; say("つながりませんでした。通信の状態を確かめてもう一度お試しください。"); });
    });
    function show(id, mode) {
      var link = data.base + (mode === "s" ? "/ask/s/#" : "/ask/r/#") + id;
      var text = mode === "s" ? "最近の好みを知りたくて選ぶだけの1分アンケートを作りました。答えてもらえるとうれしいです。" : "プレゼントを選ぶ参考にしたいので、1分でできるアンケートに答えてもらえませんか。選ぶだけです。";
      $(".ask-link", root).value = link; $(".ask-say", root).textContent = text;
      $("[data-line]", root).href = "https://line.me/R/share?text=" + encodeURIComponent(text + "\n" + link);
      $("[data-mail]", root).href = "mailto:?subject=" + encodeURIComponent("アンケートのお願い") + "&body=" + encodeURIComponent(text + "\n" + link);
      $("[data-mine]", root).href = "/ask/mine/#" + id;
      var nb = $("[data-native]", root); if (navigator.share) { nb.hidden = false; nb.onclick = function () { navigator.share({ title: "アンケートのお願い", text: text, url: link }).catch(function () {}); }; }
      $(".copy-link", root).onclick = function () { if (navigator.clipboard) navigator.clipboard.writeText(link); this.textContent = "コピーしました"; };
      $("[data-qr]", root).onclick = function () { if (window.YorokobuShowQr) window.YorokobuShowQr(link, "このアンケート"); };
      $(".ask-secret", root).hidden = mode !== "s";
      out.hidden = false; out.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  // ---------------------------------------------------------------- the page the other person answers
  function initRespond(root) {
    var data = json(root), m = /^#([A-Za-z0-9_-]{22})$/.exec(location.hash), form = $(".ask-form", root), lead = $("[data-lead]", root), msg = $(".ask-msg", root);
    function say(t) { msg.textContent = t; msg.hidden = !t; }
    if (!m) { lead.textContent = "アンケートのリンクが正しくないようです。リンクを送った人にもう一度たずねてください。"; return; }
    var id = m[1], intro = data.intro;
    document.title = intro.title; $(".ask-h1", root).textContent = intro.title; lead.textContent = intro.lead;
    if (store("yorokobu.ans." + id)) { lead.textContent = intro.done; return; }
    data.q.forEach(function (q) {
      var fs = document.createElement("fieldset"); fs.className = "ask-q"; fs.setAttribute("data-q", q.id);
      var lg = document.createElement("legend"); lg.textContent = q.text + (q.multi ? "(" + q.max + "つまで)" : ""); fs.appendChild(lg);
      var box = document.createElement("div"); box.className = "ask-opts";
      q.options.forEach(function (o) {
        var lab = document.createElement("label"); lab.className = "ask-opt"; var inp = document.createElement("input");
        inp.type = q.multi ? "checkbox" : "radio"; inp.name = q.id; inp.value = o.id;
        var span = document.createElement("span"); span.textContent = o.label; lab.appendChild(inp); lab.appendChild(span); box.appendChild(lab);
        if (!q.multi) inp.addEventListener("click", function () { if (inp.getAttribute("data-was") === "1") { inp.checked = false; inp.removeAttribute("data-was"); } else { $$("input", box).forEach(function (x) { x.removeAttribute("data-was"); }); inp.setAttribute("data-was", "1"); } update(); });
        else inp.addEventListener("change", function () { var on = $$("input:checked", box); $$("input", box).forEach(function (x) { x.disabled = !x.checked && on.length >= q.max; }); update(); });
      });
      fs.appendChild(box); form.appendChild(fs);
    });
    var btn = document.createElement("button"); btn.type = "submit"; btn.className = "btn big"; btn.textContent = "送信する"; btn.disabled = true;
    var p = document.createElement("p"); p.appendChild(btn); form.appendChild(p);
    function chosen() { var a = {}; data.q.forEach(function (q) { var v = $$("input:checked", $("[data-q=" + q.id + "]", form)).map(function (x) { return x.value; }); if (v.length) a[q.id] = v; }); return a; }
    function update() { btn.disabled = !Object.keys(chosen()).length; }
    form.hidden = false;
    form.addEventListener("submit", function (e) {
      e.preventDefault(); btn.disabled = true; say("");
      api("answer", { id: id, a: chosen() }).then(function (r) {
        if (r.status === 204) { store("yorokobu.ans." + id, 1); form.hidden = true; lead.textContent = intro.done; return; }
        btn.disabled = false;
        if (r.status === 404) return say("このアンケートは終了したようです。");
        if (r.status === 429) return say("回答の受付が、いっぱいになったようです。");
        say("送れませんでした。時間をおいてもう一度お試しください。");
      }).catch(function () { btn.disabled = false; say("つながりませんでした。通信の状態を確かめてもう一度お試しください。"); });
    });
  }

  // ---------------------------------------------------------------- notifications (Web Push): a message with no content, made by the service worker
  function b64ToBytes(s) { s = s.replace(/-/g, "+").replace(/_/g, "/"); while (s.length % 4) s += "="; var r = atob(s), o = new Uint8Array(r.length); for (var i = 0; i < r.length; i++) o[i] = r.charCodeAt(i); return o; }
  function watchList() { return surveys().map(function (s) { return { id: s.id, key: s.key }; }); }
  function resubscribe() {                                                                              // after making another survey: the same subscription watches it too
    if (!store(PUSH_KEY) || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.ready.then(function (reg) { return reg.pushManager.getSubscription(); }).then(function (sub) { if (sub) api("sub", { sub: sub.toJSON(), watch: watchList() }); }).catch(function () {});
  }
  function pushOn(vapid, status) {
    if (!("serviceWorker" in navigator) || !("PushManager" in window) || !window.Notification) { status("このブラウザでは通知を使えません。iPhone・iPad は、共有ボタンから「ホーム画面に追加」して、そのアイコンから開いてください。"); return Promise.resolve(); }
    return Notification.requestPermission().then(function (perm) {
      if (perm !== "granted") { status("通知が許可されませんでした。ブラウザの設定でこのサイトの通知を許可してください。"); return; }
      return navigator.serviceWorker.register("/sw.js").then(function () { return navigator.serviceWorker.ready; }).then(function (reg) {
        return reg.pushManager.getSubscription().then(function (s) { return s || reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(vapid) }); });
      }).then(function (sub) { return api("sub", { sub: sub.toJSON(), watch: watchList() }); }).then(function (r) {
        if (r.status === 204) { store(PUSH_KEY, 1); status("この端末に、回答が届いたときの通知を送ります(数分おくれることがあります)。"); } else status("通知の登録に失敗しました。時間をおいてもう一度お試しください。");
      });
    }).catch(function () { status("通知の登録に失敗しました。"); });
  }
  function pushOff(status) {
    navigator.serviceWorker.ready.then(function (reg) { return reg.pushManager.getSubscription(); }).then(function (sub) {
      if (!sub) return; var ep = sub.endpoint; return sub.unsubscribe().then(function () { return api("sub", { off: 1, sub: { endpoint: ep } }); });
    }).then(function () { store(PUSH_KEY, 0); status("通知を止めました。"); }).catch(function () { status("通知を止められませんでした。ブラウザの設定から止めてください。"); });
  }

  // ---------------------------------------------------------------- the results page
  function initMine(root) {
    var data = json(root), msg = $(".ask-msg", root), list = $(".ask-list", root), det = $(".ask-detail", root), recP = window.YorokobuRec ? window.YorokobuRec.load(root.getAttribute("data-rec")) : null;
    function say(t) { msg.textContent = t; msg.hidden = !t; }
    var hm = /^#([A-Za-z0-9_-]{22})\.([A-Za-z0-9_-]{22})$/.exec(location.hash);                          // a link to the results made on another device: it carries the key
    if (hm) { var l0 = surveys(); if (!l0.some(function (s) { return s.id === hm[1]; })) { l0.unshift({ id: hm[1], key: hm[2], m: "o", c: today() }); saveSurveys(l0); } history.replaceState(null, "", "#" + hm[1]); }
    function route() {
      var id = (/^#([A-Za-z0-9_-]{22})$/.exec(location.hash) || [])[1], s = surveys().filter(function (x) { return x.id === id; })[0];
      if (id && s) { list.hidden = true; det.hidden = false; showDetail(s); } else { det.hidden = true; list.hidden = false; showList(); }
    }
    window.addEventListener("hashchange", route);
    function showList() {
      var l = surveys(); list.innerHTML = "";
      if (!l.length) { say("この端末で作ったアンケートはまだありません。"); list.innerHTML = '<p class="more"><a class="btn" href="/ask/">アンケートを作る</a></p>'; return; }
      say("この端末で作ったアンケートです。");
      l.forEach(function (s) {
        var card = document.createElement("a"); card.className = "ask-card"; card.href = "#" + s.id;
        card.innerHTML = '<b>' + (s.m === "s" ? "好みの調査として聞いたアンケート" : "プレゼントのためと伝えたアンケート") + "</b><span>" + esc(s.c) + ' に作成 ・ <i class="n">回答を確認中…</i></span>';
        list.appendChild(card);
        api("read", { id: s.id, key: s.key }).then(function (r) { $(".n", card).textContent = r.status === 200 ? "回答 " + r.json.n + "件" : (r.status === 403 || r.status === 404 ? "見つかりません(期限切れ)" : "確認できません"); }).catch(function () { $(".n", card).textContent = "確認できません"; });
      });
      list.insertAdjacentHTML("beforeend", '<p class="more"><a class="btn btn-sub" href="/ask/">新しいアンケートを作る</a></p>');
    }
    function showDetail(s) {
      det.innerHTML = '<p class="more"><a href="#">← アンケートの一覧</a></p><p class="ask-msg2">回答を読み込んでいます…</p>';
      api("read", { id: s.id, key: s.key }).then(function (r) {
        if (r.status !== 200) { det.innerHTML = '<p class="more"><a href="#">← アンケートの一覧</a></p><p class="notice">このアンケートの回答を読めませんでした(作ってから120日たつと自動で消えます)。</p>'; return; }
        var rows = r.json.r, A = analyze(data.q, data.interests, rows), mode = r.json.m === "s" ? "secret" : "open";
        var html = '<p class="more"><a href="#">← アンケートの一覧</a></p><h2>' + (mode === "secret" ? "好みの調査として聞いたアンケート" : "プレゼントのためと伝えたアンケート") + '</h2>' +
          '<p class="ask-sum"><b>' + rows.length + '</b>件の回答(上限 ' + MAX_ANSWERS + '件)・' + esc(r.json.c) + ' に作成</p>';
        if (!rows.length) html += '<p class="notice">まだ回答がありません。リンクを送った相手が答えるとここに集計が出ます。</p>';
        else { html += summary(A, mode); }
        html += '<section class="ask-tools"><h3>このアンケートの操作</h3><p class="more"><button type="button" class="btn btn-sub" data-reload>最新の回答を読み込む</button> <button type="button" class="btn btn-sub" data-copy>別の端末で見るリンクをコピー</button> ' +
          '<button type="button" class="btn btn-sub" data-resend>回答を依頼するリンクを出す</button> <button type="button" class="btn btn-sub" data-del>このアンケートを消す</button></p>' +
          (data.vapid ? '<p class="more"><button type="button" class="btn" data-push>この端末で通知を受け取る</button> <button type="button" class="btn btn-sub" data-pushoff hidden>通知を止める</button></p>' : "") +
          '<p class="ask-note ask-pushmsg" role="status"></p><p class="ask-note">「別の端末で見るリンク」には結果を読むための鍵が入っています。自分のLINEやメールだけに送ってください。</p></section>';
        det.innerHTML = html;
        $("[data-reload]", det).onclick = showDetail.bind(null, s);
        $("[data-copy]", det).onclick = function () { var u = data.base + "/ask/mine/#" + s.id + "." + s.key; if (navigator.clipboard) navigator.clipboard.writeText(u); this.textContent = "コピーしました"; };
        $("[data-resend]", det).onclick = function () { var u = data.base + (mode === "secret" ? "/ask/s/#" : "/ask/r/#") + s.id; if (window.YorokobuShowQr) window.YorokobuShowQr(u, "このアンケート"); if (navigator.clipboard) navigator.clipboard.writeText(u); this.textContent = "リンクをコピーしました"; };
        $("[data-del]", det).onclick = function () { if (!confirm("このアンケートと届いた回答を消します。よろしいですか。")) return; api("del", { id: s.id, key: s.key }).then(function () { saveSurveys(surveys().filter(function (x) { return x.id !== s.id; })); location.hash = ""; }); };
        var pm = $(".ask-pushmsg", det), on = $("[data-push]", det), off = $("[data-pushoff]", det);
        if (on) { if (store(PUSH_KEY)) { on.hidden = true; off.hidden = false; } on.onclick = function () { pushOn(data.vapid, function (t) { pm.textContent = t; if (/送ります/.test(t)) { on.hidden = true; off.hidden = false; } }); }; off.onclick = function () { pushOff(function (t) { pm.textContent = t; on.hidden = false; off.hidden = true; }); }; }
        if (rows.length && recP) recP.then(function (rec) { products(A, rec, mode); }).catch(function () {});
      }).catch(function () { det.innerHTML = '<p class="more"><a href="#">← アンケートの一覧</a></p><p class="notice">読み込めませんでした。通信の状態を確かめてください。</p>'; });
    }
    function summary(A, mode) {
      var h = "";
      if (A.n < 3) h += '<p class="notice">回答が' + A.n + '件です。少ないうちは1人の答えで集計が大きく変わります。参考として見てください。</p>';
      h += '<section class="ask-agg"><h3>質問ごとの集計</h3>';
      data.q.forEach(function (q) {
        var per = A.per[q.id], total = Object.keys(per).reduce(function (a, k) { return a + per[k]; }, 0); if (!total) return;
        h += '<div class="ask-aq"><h4>' + esc(q[mode]) + '</h4><div class="hb">' + q.options.filter(function (o) { return per[o.id]; }).sort(function (a, b) { return per[b.id] - per[a.id]; }).map(function (o) {
          return '<div class="hb-row"><span class="hb-l">' + esc(o.label) + '</span><span class="hb-track"><i class="hb-fill s1" style="width:' + pct(per[o.id], A.n) + '%"></i></span><span class="hb-v">' + per[o.id] + "人(" + pct(per[o.id], A.n) + "%)</span></div>";
        }).join("") + "</div></div>";
      });
      h += "</section>";
      h += '<section class="ask-read"><h3>回答からわかること</h3><ul class="ask-lines">';
      if (!A.ranked.length) h += "<li>好みの手がかりになる回答が、まだありません。</li>";
      A.ranked.slice(0, 3).forEach(function (r, i) {
        var why = r.reasons.map(function (x) { return "「" + esc(x.label) + "」と答えた人が" + x.count + "人"; }).join("、");
        h += "<li><b>" + (i + 1) + ". " + esc(data.interests[r.id]) + "</b>(" + why + ")</li>";
      });
      A.zero.forEach(function (g) { });
      var notes = [];
      if (A.avoid.scent && A.avoid.scent * 2 >= A.n) notes.push("香りが強いものは苦手と答えた人が" + A.avoid.scent + "人います。入浴剤や美容品はおすすめから外しています。");
      if (A.avoid.sweet && A.avoid.sweet * 2 >= A.n) notes.push("甘いものは苦手と答えた人が" + A.avoid.sweet + "人います。お菓子はおすすめから外しています。");
      if (A.avoid.alcohol && A.avoid.alcohol * 2 >= A.n) notes.push("お酒は避けたいと答えた人が" + A.avoid.alcohol + "人います。お酒はおすすめから外しています。");
      if (A.avoid.allergy) notes.push("食物アレルギーがあると答えた人が" + A.avoid.allergy + "人います。食べものを選ぶときは原材料の表示を必ず確かめてください。");
      if (A.avoid.bulky && A.avoid.bulky * 2 >= A.n) notes.push("場所をとるものは避けたいと答えた人が" + A.avoid.bulky + "人います。大きな品は控えめにしています。");
      if (A.avoid.flashy) notes.push("派手なデザインは避けたいと答えた人が" + A.avoid.flashy + "人います。落ち着いた色・デザインの品を選んでください。");
      notes.forEach(function (t) { h += "<li>" + esc(t) + "</li>"; });
      if (A.budget) h += "<li>気軽に受け取れる金額感は中央の回答で「" + esc(optLabel("budget", A.budget.band)) + "」です(" + A.budget.count + "人が回答)。</li>";
      h += "</ul></section>";
      h += '<section class="ask-rec" hidden><h3>回答に合わせたおすすめ</h3><div class="ask-recbody"></div></section>';
      return h;
    }
    function optLabel(key, oid) { var q = data.q.filter(function (x) { return x.key === key; })[0]; var o = q && q.options.filter(function (x) { return x.id === oid; })[0]; return o ? o.label : oid; }
    function products(A, rec, mode) {
      var box = $(".ask-rec", det); if (!box) return; var body = $(".ask-recbody", box), h = "", upper = A.budget ? A.budget.upper : null;
      A.ranked.slice(0, 3).forEach(function (r, i) {
        var g = rec.groups[r.id]; if (!g) return;
        h += '<div class="ask-recgroup"><h4>' + (i + 1) + ". " + esc(g.label) + '</h4><p class="ask-why">' + r.reasons.map(function (x) { return "「" + esc(x.label) + "」と答えた人が" + x.count + "人"; }).join("、") + "。" +
          (g.range ? " 当サイトの" + esc(g.label) + "の商品(" + g.range.n + "点)は価格の中央値が" + window.YorokobuRec.yen(g.range.med) + "、" + window.YorokobuRec.yen(g.range.p25) + "〜" + window.YorokobuRec.yen(g.range.p75) + "が中心です。" : "") + "</p>" +
          window.YorokobuRec.block(g, { max: upper, n: 4 }) + "</div>";
      });
      if (A.budget && rec.tiers) {
        var tier = null; rec.bands.forEach(function (b) { if (b[0] === A.budget.band) tier = b[1]; });
        if (tier && rec.tiers.indexOf(tier) >= 0) h += '<p class="more"><a class="btn btn-sub" href="/budget/' + tier + '/">この予算でほかの贈り物も見る</a></p>';
      }
      if (!h) return; h += '<p class="fresh">価格・在庫は' + esc(rec.fresh) + '時点の情報です。購入時に楽天市場の店舗に表示されている価格が、その商品の販売に適用されます。</p>';
      body.innerHTML = h; box.hidden = false;
    }
    route();
  }

  window.YorokobuAsk = { analyze: analyze, rid: rid };
  function boot() {
    var make = $("#ask-make"), res = $("#ask-respond"), mine = $("#ask-mine");
    if (make) initMake(make);
    if (res) initRespond(res);
    if (mine) initMine(mine);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
