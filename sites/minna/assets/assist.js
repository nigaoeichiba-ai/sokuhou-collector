// みんなのイラスト: the helper panel ("お手伝い"). It runs in this browser: what is typed here is only compared with the site's own lists (the illustrations, the pages, the answers
// in data/assist.json) and is not sent anywhere, except when the visitor presses a request button (then the same one short wish goes to api/q.php, like the request box).
// No AI model is needed; rules and word lists only.  Loaded the first time the button is pressed (app.js: initAssist).
(function () {
  "use strict";
  var A = window.minnaApp; if (!A) return;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = A.esc, norm = A.norm, panel = null, log = null, input = null, opener = document.getElementById("assist-open"), dataP = null, asking = false;
  var FILLER = /(ください|下さい|ほしいです|ほしい|欲しい|さがしています|さがして|探しています|探して|ありますか|ありませんか|ないですか|教えてください|教えて|おしえて|使いたいです|使いたい|つかいたい|のイラスト|イラスト|いらすと|の絵|絵が|絵を|絵|かわいい|可愛い|おしゃれな|おしゃれ|無料の|無料|フリー素材|フリー|素材|に使えます|に使える|使えます|使える|に使って|使って)/g;
  var REQ = /(リクエスト|描いてほしい|描いて欲しい|描いてください|作ってほしい|作ってください|つくってほしい)/;

  function loadData() { return A.loadAssist(); }
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function say(who, html) { var d = el("div", "as-msg " + who, html); log.appendChild(d); log.scrollTop = log.scrollHeight; return d; }
  function chips(list) {
    var row = el("div", "as-chips");
    list.forEach(function (c) { var b = el("button", "chip", esc(c[0])); b.type = "button"; b.addEventListener("click", function () { row.remove(); c[1](); }); row.appendChild(b); });
    log.appendChild(row); log.scrollTop = log.scrollHeight;
  }
  function strip(text) { // the words to look for: polite and filler phrases out, a particle left at the end of a word out ("年賀状に" -> "年賀状")
    return String(text || "").replace(FILLER, " ").replace(/[?？。、!！]/g, " ").replace(/(\S{2,}?)(?:に|で|を|は|が|と|の|も)(?=\s|$)/g, "$1").replace(/(^|\s)(?:に|で|を|は|が|と|の|も)(?=\s|$)/g, " ").replace(/\s+/g, " ").trim();
  }
  var NOTHING_LEFT = /(したい|します|お願い|おねがい|できますか|できる|ですか|です|ます|ほしい|欲しい|使える|使って|いいですか|大丈夫|ですか|を|が|は|の|に|で|と|か|\s|[?？。、!！])/g;
  var BLOCKED = "既存のキャラクター・商品名・実在の人物・特定の作家の絵は、扱っていません(リクエストも、お受けできません)。オリジナルの動物や人物のイラストなら、さがせます。";
  function miniCards(rows, n) {
    return '<div class="as-cards">' + rows.slice(0, n).map(function (r) {
      return '<a class="as-card" href="/illust/' + r[0] + '/"><span class="checker"><img src="/thumbs/' + r[0] + '.webp" alt="" width="64" height="64" loading="lazy"></span><small>' + esc(r[1]) + "</small></a>";
    }).join("") + "</div>";
  }

  function sendRequest(text, src) {
    return A.loadRules().then(function (rules) {
      var why = rules ? A.refuseW(rules, text) : "";
      if (why) { say("bot", esc(why) + "<br>ほかの言い方で、もう一度、書いてみてください。"); return; }
      return A.sendWish({ w: text, s: src }).then(function (r) { say("bot", esc(r.msg)); if (r.ok) A.saveWish(text); });
    });
  }
  function offerRequest(text) {
    var w = strip(text) || text;
    chips([["「" + w.slice(0, 20) + "」を、リクエストする", function () { say("me", "リクエストする"); sendRequest(w, "miss"); }], ["ほかの言葉でさがす", function () { say("bot", "ほかの言葉を、入れてください。"); input.focus(); }]]);
  }
  function showResults(res, original, tFilter) {
    var q = strip(original) || original;
    var link = '<a href="/search/?q=' + encodeURIComponent(q) + (tFilter ? "&t=" + encodeURIComponent(tFilter) : "") + '">ぜんぶ見る</a>';
    if (res.exact.length) {
      say("bot", res.exact.length + "点、見つかりました。" + miniCards(res.exact, 6) + link);
      if (!tFilter && res.exact.length > 12) {
        loadData().then(function (d) {
          var c = {}; res.exact.forEach(function (r) { c[r[4]] = (c[r[4]] || 0) + 1; });
          var top = Object.keys(c).filter(function (k) { return c[k] >= 3 && d.touches[k]; }).sort(function (a, b) { return c[b] - c[a]; }).slice(0, 4);
          if (top.length > 1) {
            say("bot", "タッチを、しぼりこめます。");
            chips(top.map(function (k) { return [d.touches[k] + "(" + c[k] + ")", function () { say("me", d.touches[k]); search(original, k); }]; }));
          }
        });
      }
      return;
    }
    if (res.near.length) { say("bot", "ぴったりの絵は、まだ、ありません。近いものは、こちらです。" + miniCards(res.near, 6) + link); }
    else { say("bot", "ぴったりの絵は、まだ、ありません。"); }
    if (res.suggest.length) say("bot", "もしかして: " + res.suggest.map(function (s) { return '<a href="/search/?q=' + encodeURIComponent(s) + '">' + esc(s) + "</a>"; }).join("、") + "?");
    offerRequest(original);
  }
  function search(text, tFilter) {
    return Promise.all([A.loadIndex(), A.loadSyn()]).then(function (v) {
      return A.loadVocab().then(function (vocab) { return A.searchAll(v[0], v[1], vocab, strip(text) || text, "", tFilter || ""); });
    }).then(function (res) { showResults(res, text, tFilter); });
  }
  function faqFor(flatText, faq) {
    var best = null, bestN = 0;
    faq.forEach(function (f) { var n = f.k.filter(function (k) { return flatText.indexOf(norm(k)) >= 0; }).length; if (n > bestN) { best = f; bestN = n; } });
    return best;
  }
  function handle(text) {
    text = String(text || "").trim(); if (!text) return;
    say("me", esc(text));
    if (asking) { asking = false; return sendRequest(text, "form"); }
    if (REQ.test(text) && text.replace(REQ, "").replace(NOTHING_LEFT, "").length < 2) {
      asking = true; say("bot", "どんなイラストが、ほしいですか? ひとことで、書いてください(例: こたつでみかんを食べるひつじ)。書いた言葉を、リクエストとして送ります。既存のキャラクターや、実在の人物は、お受けできません。"); return;
    }
    return A.loadRules().then(function (rules) {
      var why = rules ? A.refuseW(rules, text) : "";
      if (why && /お受けできません/.test(why)) { say("bot", /キャラクター|商品名|人物|作家/.test(why) ? BLOCKED : esc(why)); return "blocked"; }
    }).then(function (blocked) {
      if (blocked) return;
      return Promise.all([loadData(), A.loadSyn(), A.loadVocab()]).then(function (v) { return answer(text, v[0], v[1], v[2]); });
    });
  }
  function answer(text, d, idx, vocab) {
    {
      var f = norm(text), ans = faqFor(f, d.faq), words = norm(strip(text)).split(/\s+/).filter(Boolean);
      if (ans) say("bot", esc(ans.a) + (ans.u ? '<br><a href="' + esc(ans.u) + '">' + esc(ans.l || "くわしく") + "</a>" : ""));
      var pg = A.pagesFor(words, idx, d.pages);
      if (pg.length) say("bot", "こんなページも、あります。<ul class=\"as-links\">" + pg.map(function (p) { return '<li><a href="' + esc(p.u) + '">' + esc(p.n) + "</a><small>" + esc(p.t || "") + "</small></li>"; }).join("") + "</ul>");
      if (ans) { // an answer was given: look for pictures only if the rest of the sentence names something the library knows
        var left = norm(strip(text)).replace(new RegExp(ans.k.map(function (k) { return norm(k).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).join("|"), "g"), "").replace(NOTHING_LEFT, "");
        if (!splitPhrase(left, vocab).length) return;
      }
      return search(text);
    }
  }
  function splitPhrase(s, vocab) { // the known words that fit in s (the same idea as the search page; a copy here keeps assist.js independent of app.js internals)
    return Object.keys(vocab).filter(function (t) { return s.indexOf(t) >= 0; });
  }
  function build() {
    panel = el("section", "assist"); panel.id = "assist-panel"; panel.setAttribute("role", "dialog"); panel.setAttribute("aria-label", "お手伝い"); panel.hidden = true;
    panel.innerHTML = '<header><b>お手伝い</b><button type="button" class="as-x" aria-label="とじる">×</button></header><div class="as-log" role="log" aria-live="polite"></div>' +
      '<form class="as-form"><input type="text" name="m" maxlength="80" placeholder="さがしたいものを、書いてください" autocomplete="off" aria-label="メッセージ"><button class="btn" type="submit">送る</button></form>' +
      '<p class="as-note">ここに書いた言葉は、この端末の中だけで使われます。リクエストを送るボタンを押したときだけ、その言葉を送ります。</p>';
    document.body.appendChild(panel);
    log = $(".as-log", panel); input = $("input", panel);
    $(".as-x", panel).addEventListener("click", close);
    $(".as-form", panel).addEventListener("submit", function (e) { e.preventDefault(); var v = input.value; input.value = ""; handle(v); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !panel.hidden) close(); });
    say("bot", "こんにちは。さがしている絵や、知りたいことを、教えてください。");
    loadData().then(function (d) {
      chips((d.chips || []).map(function (c) { return [c, function () { handle(c); }]; }));
    });
  }
  function open() { if (!panel) build(); panel.hidden = false; opener.setAttribute("aria-expanded", "true"); input.focus(); }
  function close() { panel.hidden = true; opener.setAttribute("aria-expanded", "false"); opener.focus(); }
  window.minnaAssist = { toggle: function () { if (!panel || panel.hidden) open(); else close(); }, handle: handle };
})();
