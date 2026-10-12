/* 贈り物コンシェルジュ (sites/yorokobu/concierge.py).  Rules and word lists, no AI; it runs here in the browser and reads /concierge-data.json (made from the site's content).
   What is typed stays on the device, unless 「送る」 is pressed on a box that says what is done with it (api/ask.php op "voice").  The kinds of question asked are counted
   (op "stat", keys cq.*: a number per kind, no text, no address) unless the browser says Do Not Track. */
(function () {
  "use strict";
  var DATA = null, loading = null;
  var state = { occ: "", rec: "", tier: "", askedRec: false, askedOcc: false, askedTier: false, done: false };
  var root, panel, log, form, input, opener;
  function $(s, r) { return (r || document).querySelector(s); }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  // ---------------------------------------------------------------- reading a sentence
  function norm(s) { return String(s || "").normalize("NFKC").toLowerCase().replace(/\s+/g, " ").trim(); }
  // the first word of the list that the text holds (the longest ones are tried first); returns {slug, word} and the text without that word (so 母の日 does not also say 母)
  var KANJI = /[一-鿿]/;
  function find(list, text) {
    var best = null;
    list.forEach(function (item) {
      item.w.forEach(function (w0) {
        var w = norm(w0);
        for (var i = w ? text.indexOf(w) : -1; i >= 0; i = text.indexOf(w, i + 1)) {
          // a one-character word (夫, 母, 父, 妻) is a person only on its own: 丈夫 and 夫婦 are other words
          if (w.length === 1 && KANJI.test(w) && (KANJI.test(text.charAt(i - 1) || " ") || KANJI.test(text.charAt(i + 1) || " "))) continue;
          if (!best || w.length > best.word.length || (w.length === best.word.length && i < best.at)) best = { slug: item.s, word: w, at: i };
          break;
        }
      });
    });
    return best;
  }
  function without(text, hit) { return hit ? text.replace(hit.word, " ") : text; }
  // yen in a sentence: 5000円, 5千円, 1万円, 1.5万円, 2万5千円, 3000〜5000円 (the upper figure); a bare number (an age, a count) is not money; returns a number or 0
  function yenOf(text) {
    var t = String(text).replace(/,/g, ""), best = 0, m;
    var combo = /(\d+)\s*万\s*(\d+)\s*千/g;
    while ((m = combo.exec(t))) best = Math.max(best, parseInt(m[1], 10) * 10000 + parseInt(m[2], 10) * 1000);
    var re = /(\d+(?:\.\d+)?)\s*(万|千)?\s*(円|えん)?/g;
    while ((m = re.exec(t))) {
      if (!m[2] && !m[3]) continue;
      var n = parseFloat(m[1]);
      var v = m[2] === "万" ? n * 10000 : m[2] === "千" ? n * 1000 : n;
      if (v >= 500 && v <= 1000000 && v > best) best = v;
    }
    return best;
  }
  function tierOf(yen) {
    if (!yen || !DATA) return "";
    var hit = "";
    DATA.tiers.forEach(function (t) { if (yen >= t.min && (t.max === null || yen <= t.max) && !hit) hit = t.s; });
    return hit;
  }
  function theme(text) { return find(DATA.themes.filter(function (t) { return t.w.length; }).map(function (t) { return { s: t.s, w: t.w }; }), text); }
  function ambiguous(text) {
    var out = null;
    Object.keys(DATA.amb).forEach(function (w) { if (!out && text.indexOf(norm(w)) >= 0) out = { word: w, slugs: DATA.amb[w] }; });
    return out;
  }
  // what the sentence says: {occ, rec, tier, amb, theme, intent}
  function read(raw) {
    var text = norm(raw), r = { occ: "", rec: "", tier: "", amb: null, theme: "", intent: "" };
    var o = find(DATA.occ, text); if (o) r.occ = o.slug;
    var rest = without(text, o);
    var p = find(DATA.rec, rest), am = ambiguous(rest);
    if (am && (!p || norm(am.word).length > p.word.length)) r.amb = am;            // 祖父母 is not 祖父
    else if (p) r.rec = p.slug;
    r.tier = tierOf(yenOf(text));
    if (!r.occ && !r.rec) { var th = theme(text); if (th) r.theme = th.slug; }
    if (/セール|マラソン|お得|安く|ポイント|プライム/.test(text)) r.intent = "sale";
    else if (/いつまで|間に合|急ぎ|急い|明日|あした|今日|届/.test(text)) r.intent = "urgent";
    else if (/のし|熨斗|マナー|お返し|失礼|相場/.test(text)) r.intent = "manners";
    else if (/好み|何が好き|わからない|分からない|何を贈|なにを贈/.test(text)) r.intent = "what";
    return r;
  }

  // ---------------------------------------------------------------- the pages the answer points to
  function nameOf(list, slug) { for (var i = 0; i < list.length; i++) if (list[i].s === slug) return list[i].n; return slug; }
  function pairKey() { return state.occ + "-" + state.rec; }
  function hasPair() { return !!(state.occ && state.rec && DATA.pairs[pairKey()]); }
  function links() {
    var out = [];
    if (hasPair()) {
      var tiers = DATA.pairs[pairKey()] || [];
      var q = state.tier && tiers.indexOf(state.tier) >= 0 ? "?b=" + encodeURIComponent(state.tier) + "#browse" : "";
      out.push({ href: "/gift/" + pairKey() + "/" + q, title: nameOf(DATA.occ, state.occ) + " × " + nameOf(DATA.rec, state.rec) + "の贈り物", note: q ? "予算に合うものを、先に表示します。" : "迷ったときは、先頭の4点から。" });
    } else if (state.occ) out.push({ href: "/occasion/" + state.occ + "/", title: nameOf(DATA.occ, state.occ) + "のプレゼント", note: "相手を選んで、おすすめを見られます。" });
    else if (state.rec) out.push({ href: "/for/" + state.rec + "/", title: nameOf(DATA.rec, state.rec) + "へのプレゼント", note: "喜ばれやすいものと、イベント別のおすすめ。" });
    if (state.occ && DATA.guides.indexOf(state.occ) >= 0) out.push({ href: "/guide/" + state.occ + "/", title: nameOf(DATA.occ, state.occ) + "の読みもの", note: "いつまでに、何を、どう渡すか。" });
    if (state.occ && state.rec) out.push({ href: "/memo/?o=" + state.occ + "&r=" + state.rec, title: "この日を忘れないように、登録する", note: "たいせつな日メモ(このブラウザの中だけ)。" });
    return out;
  }

  function dnt() { return navigator.doNotTrack === "1" || navigator.doNotTrack === "yes" || window.doNotTrack === "1" || navigator.msDoNotTrack === "1"; }
  // ---------------------------------------------------------------- counting (anonymous: a key per kind of question, nothing else)
  var sent = {};
  function count(keys) {
    if (dnt() || navigator.webdriver) return;
    keys = keys.filter(function (k) { return /^cq\.[a-z]{1,6}\.[a-z0-9_-]{1,32}$/.test(k) && !sent[k]; });
    if (!keys.length) return;
    keys.forEach(function (k) { sent[k] = 1; });
    try { fetch("/api/ask.php", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ v: 1, op: "stat", k: keys }), keepalive: true }).catch(function () {}); } catch (e) { /* not counted */ }
  }
  // text only when asked for (a button that says so); the same checks as the server
  // the same rules as the server's (which is the check that counts): plain text first (NFKC, every dash alike), then phone numbers, mail, links, addresses
  function unsafe(text) {
    var n = String(text).normalize("NFKC").replace(/[\u2010-\u2015\u2212\u30FC\uFF0D\uFF70\u2043]/g, "-");
    return /[0-9](?:[\s\-.\/()・,]*[0-9]){6,}/.test(n) || /@|https?:|www\.|\u3012|ftp:/.test(n) ||
      /[a-z0-9][a-z0-9-]*\.(?:com|net|org|jp|info|biz|io|me|tv|co|ne|app|dev)(?:[\/\s.]|$)/i.test(n) || /(?:\bat\b|アットマーク|アット).{0,30}(?:\bdot\b|ドット)/i.test(n) ||
      /(?:都|道|府|県).{0,12}(?:市|区|町|村|郡)/.test(n) || /[0-9]+\s*(?:丁目|番地)|[0-9]+\s*番\s*[0-9]*\s*号/.test(n);
  }
  function sendVoice(kind, text, done) {
    text = String(text || "").replace(/\s+/g, " ").trim();
    if (text.length < 2 || text.length > 80) return done("2〜80字で書いてください。");
    if (unsafe(text)) return done("電話番号・住所・メールアドレス・リンクのように見える部分があります。個人の情報は、書かないでください。");
    fetch("/api/ask.php", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ v: 1, op: "voice", k: kind, t: text }) })
      .then(function (r) { done(r.ok ? "" : "送れませんでした。時間をおいて、もう一度お試しください。", r.ok); }).catch(function () { done("送れませんでした。"); });
  }

  // ---------------------------------------------------------------- the conversation
  function bubble(html, who) {
    var d = document.createElement("div");
    d.className = "cc-msg cc-" + (who || "bot");
    d.innerHTML = html;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
    return d;
  }
  function chips(items, onPick) {
    var d = document.createElement("div"); d.className = "cc-chips";
    items.forEach(function (it) {
      var b = document.createElement("button"); b.type = "button"; b.className = "cc-chip"; b.textContent = it.label;
      b.addEventListener("click", function () { d.querySelectorAll("button").forEach(function (x) { x.disabled = true; }); bubble(esc(it.label), "me"); onPick(it); });
      d.appendChild(b);
    });
    log.appendChild(d); log.scrollTop = log.scrollHeight;
  }
  function linkCards(items) {
    var h = "";
    items.forEach(function (l) { h += '<a class="cc-link" href="' + esc(l.href) + '"><b>' + esc(l.title) + "</b><span>" + esc(l.note || "") + "</span></a>"; });
    return h ? '<div class="cc-links">' + h + "</div>" : "";
  }
  function askRec(msg) {
    var avail = DATA.rec.filter(function (r) { return !state.occ || DATA.pairs[state.occ + "-" + r.s]; });
    bubble(esc(msg));
    chips(avail.map(function (r) { return { label: r.n, s: r.s }; }).concat([{ label: "決まっていない", s: "" }]), function (it) { state.rec = it.s; if (it.s) count(["cq.rec." + it.s]); next(); });
  }
  function askOcc(msg) {
    var avail = DATA.occ.filter(function (o) { return !state.rec || DATA.pairs[o.s + "-" + state.rec]; });
    bubble(esc(msg));
    chips(avail.map(function (o) { return { label: o.n, s: o.s }; }).concat([{ label: "決まっていない", s: "" }]), function (it) { state.occ = it.s; if (it.s) count(["cq.occ." + it.s]); next(); });
  }
  function askTier() {
    var tiers = hasPair() ? (DATA.pairs[pairKey()] || []) : DATA.tiers.map(function (t) { return t.s; });
    bubble("ご予算は、どのくらいですか。");
    chips(DATA.tiers.filter(function (t) { return tiers.indexOf(t.s) >= 0; }).map(function (t) { return { label: t.l, s: t.s }; }).concat([{ label: "決めていない", s: "" }]),
      function (it) { state.tier = it.s; if (it.s) count(["cq.bud." + it.s]); next(); });
  }
  var topic = "";
  function fresh() { return { occ: "", rec: "", tier: "", askedRec: false, askedOcc: false, askedTier: false, done: false }; }
  function next() {                                         // the next thing to ask, or the answer
    if (!state.rec && !state.askedRec) { state.askedRec = true; return askRec("どなたに贈りますか。"); }
    if (!state.occ && !state.askedOcc) { state.askedOcc = true; return askOcc(topic === "manners" ? "どの日の贈り物ですか。" : "どんな日の贈り物ですか。"); }
    if (topic !== "manners" && hasPair() && !state.askedTier) { state.askedTier = true; return askTier(); }
    answer();
  }
  var fed = false;
  function answer() {
    state.done = true;
    var ls = links();
    var kind = hasPair() ? "hit" : ls.length ? "part" : "miss";
    count(["cq.res." + kind]);
    if (!ls.length) { bubble("うまく絞れませんでした。下の欄に、ひとことで書いてみてください(例: 母の日に、母へ 5000円くらい)。"); return feedback(false); }
    var lead = hasPair() ? "ご相談の内容に合う、ページがあります。" : "近いページをご案内します。";
    bubble(esc(lead) + linkCards(ls));
    feedback(true);
  }
  function feedback(found) {
    if (fed) return; fed = true;
    bubble("お探しの情報は、見つかりましたか。");
    chips([{ label: "見つかった", y: 1 }, { label: "見つからない", y: 0 }], function (it) {
      count(["cq.fb." + (it.y ? "yes" : "no")]);
      if (it.y) return bubble("ありがとうございます。ほかにも、お困りのことがあれば、お知らせください。");
      bubble("よろしければ、どのような情報がほしかったか、教えてください。選ぶだけでも、書いても構いません。送らなくても、そのままお使いいただけます。");
      chips(DATA.why.map(function (w, i) { return { label: w, i: i }; }), function (w) {
        count(["cq.why.w" + w.i]);
        voiceBox("why", "ほかにお困りのこと(任意・80字まで)");
      });
    });
  }
  function voiceBox(kind, placeholder, preset) {
    var d = document.createElement("form"); d.className = "cc-voice";
    d.innerHTML = '<input type="text" maxlength="80" placeholder="' + esc(placeholder) + '" aria-label="' + esc(placeholder) + '"><button type="submit" class="btn btn-sub">送る</button>' +
      '<p class="cc-note">送った文章は、サイトの改善だけに使います。名前・連絡先・住所は、書かないでください。送らずに閉じても、そのままお使いいただけます。</p><p class="cc-err" role="alert" hidden></p>';
    if (preset) d.querySelector("input").value = preset;
    d.addEventListener("submit", function (e) {
      e.preventDefault();
      var err = d.querySelector(".cc-err");
      sendVoice(kind, d.querySelector("input").value, function (msg, ok) {
        if (ok) { d.innerHTML = "<p>送りました。ありがとうございます。</p>"; return; }
        err.textContent = msg; err.hidden = false;
      });
    });
    log.appendChild(d); log.scrollTop = log.scrollHeight;
  }
  function begin() {
    state = fresh(); topic = ""; fed = false; log.innerHTML = "";
    bubble("こんにちは。贈り物のご相談を、承ります。<br><b>どういったことで、お困りですか。</b>");
    chips(DATA.topics.map(function (t) { return { label: t.label, id: t.id, reply: t.reply }; }), function (t) { pickTopic(t); });
  }
  function pickTopic(t) {
    topic = t.id; count(["cq.need." + t.id]);
    if (t.id === "other") { bubble(esc(t.reply)); input.focus(); return; }
    if (t.id === "sale") { bubble(esc(t.reply) + linkCards([{ href: "/sale/", title: "セールの日程と、買うタイミング", note: "お買い物マラソン・プライム感謝祭など" }])); return feedback(true); }
    if (t.id === "what") {
      bubble(esc(t.reply) + linkCards([{ href: "/ask/", title: "それとなく、ほしいものを聞く", note: "相手に送るアンケート。答えは選ぶだけ。" }, { href: "/dock/", title: "贈り物ドック", note: "相手のことを入れると、結果票でおすすめを返します。" },
        { href: "/tool/", title: "診断・ツール", note: "タイプ診断や、ガチャなど。" }]));
      return feedback(true);
    }
    if (t.id === "manners") { bubble(esc(t.reply)); state.askedRec = true; return next(); }
    bubble(esc(t.reply));
    next();
  }
  function onText(raw) {
    raw = String(raw || "").trim();
    if (!raw) return;
    bubble(esc(raw), "me");
    if (state.done) { state = fresh(); topic = ""; fed = false; }            // the last question was answered: a new sentence is a new question
    var r = read(raw);
    if (r.intent) count(["cq.need." + r.intent]);
    if (r.intent === "sale") { bubble("セールの日程を、まとめています。" + linkCards([{ href: "/sale/", title: "セールの日程と、買うタイミング", note: "お買い物マラソン・プライム感謝祭など" }])); return feedback(true); }
    if (r.occ) { state.occ = r.occ; count(["cq.occ." + r.occ]); }
    if (r.rec) { state.rec = r.rec; count(["cq.rec." + r.rec]); }
    if (r.tier) { state.tier = r.tier; state.askedTier = true; count(["cq.bud." + r.tier]); }
    if (r.intent === "manners") { topic = "manners"; state.askedRec = true; }
    if (r.intent === "urgent" || r.intent === "what") topic = r.intent;
    if (r.amb && !state.rec) {
      bubble(esc("「" + r.amb.word + "」は、どちらでしょうか。"));
      state.askedRec = true;
      chips(r.amb.slugs.map(function (s) { return { label: nameOf(DATA.rec, s), s: s }; }), function (it) { state.rec = it.s; count(["cq.rec." + it.s]); next(); });
      return;
    }
    if (!state.occ && !state.rec && r.theme) {
      count(["cq.res.theme"]);
      var tn = nameOf(DATA.themes.map(function (t) { return { s: t.s, n: t.n }; }), r.theme);
      bubble("「" + esc(tn) + "」のページがあります。" + linkCards([{ href: "/theme/" + r.theme + "/", title: tn, note: "気持ちや興味から選んだ、贈り物の例。" }]));
      return feedback(true);
    }
    if (!state.occ && !state.rec) {
      count(["cq.res.miss"]);
      var q = raw.indexOf("ギフト") >= 0 || raw.indexOf("プレゼント") >= 0 ? raw : raw + " ギフト";
      var target = "https://search.rakuten.co.jp/search/mall/" + encodeURIComponent(q) + "/";
      var aff = DATA.aff.id ? "https://hb.afl.rakuten.co.jp/hgc/" + DATA.aff.id + "/" + (DATA.aff.trk || "") + "?pc=" + encodeURIComponent(target) + "&m=" + encodeURIComponent(target) : "";
      bubble("うまく読み取れませんでした。「だれに」「どんな日に」「予算は」のうち、わかるものを、書き添えてください(例: 父の日に、父へ 5000円くらい)。" +
        (aff ? '<br>言葉のまま、楽天市場で探すこともできます。<div class="cc-links"><a class="cc-link" href="' + esc(aff) + '" target="_blank" rel="sponsored nofollow noopener"><b>「' + esc(raw.slice(0, 30)) + '」を楽天市場で探す</b><span>広告(PR)のリンクです。</span></a></div>' : ""));
      bubble("この言葉を、サイトの改善のために送ってもよければ、下の「送る」を押してください。");
      voiceBox("miss", "", raw.slice(0, 80));
      return feedback(false);
    }
    next();
  }

  // ---------------------------------------------------------------- the corner button and the panel
  function build() {
    root = document.createElement("div");
    root.className = "cc"; root.innerHTML =
      '<button type="button" class="cc-open" aria-expanded="false" aria-controls="cc-panel"><span aria-hidden="true">?</span>贈り物の相談</button>' +
      '<section class="cc-panel" id="cc-panel" role="dialog" aria-label="贈り物コンシェルジュ" hidden><header><b>贈り物コンシェルジュ</b><button type="button" class="cc-close" aria-label="閉じる">×</button></header>' +
      '<div class="cc-log" aria-live="polite"></div><form class="cc-form"><input type="text" maxlength="120" placeholder="ひとことで(例: 母の日に、母へ 5000円くらい)" aria-label="ご相談の内容"><button type="submit" class="btn">送る</button></form>' +
      '<p class="cc-foot">規則と言葉のリストで案内しています。書いた内容は、「送る」を押した文章のほかは、この端末の外へ出ません。</p></section>';
    document.body.appendChild(root);
    opener = $(".cc-open", root); panel = $(".cc-panel", root); log = $(".cc-log", root); form = $(".cc-form", root); input = $("input", form);
    opener.addEventListener("click", toggle);
    $(".cc-close", root).addEventListener("click", function () { toggle(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !panel.hidden) toggle(false); });
    form.addEventListener("submit", function (e) { e.preventDefault(); var v = input.value; input.value = ""; if (DATA) onText(v); });
  }
  function toggle(open) {
    open = typeof open === "boolean" ? open : panel.hidden;
    panel.hidden = !open; opener.setAttribute("aria-expanded", open ? "true" : "false"); root.classList.toggle("on", open);
    if (!open) return;
    if (!DATA) {
      if (!loading) loading = fetch("/concierge-data.json").then(function (r) { if (!r.ok) throw new Error("data"); return r.json(); });
      log.innerHTML = '<div class="cc-msg cc-bot">読み込んでいます…</div>';
      loading.then(function (d) { DATA = d; begin(); }).catch(function () { log.innerHTML = '<div class="cc-msg cc-bot">読み込めませんでした。時間をおいて、もう一度お試しください。</div>'; loading = null; });
    }
  }
  window.YorokobuConcierge = { read: function (t) { return read(t); }, setData: function (d) { DATA = d; }, yenOf: yenOf };
  function init() { if (!document.querySelector(".cc")) build(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
