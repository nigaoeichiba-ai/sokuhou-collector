"""The first view of the top page of sale-calendar.com (prototype v4 and v5, owner decisions 2026-11-10).

sokuhou/newsite.py calls post() after the pages are rendered.  Only index.html changes: the header and the first view (hero, countdown bar, judge card,
next-sale card, genre links) replace the old header and h1 (the "answer" line stays under the first view); every section below them (いま分かっている日程 ...) and every
other page stay as they were.
v4 (Rakuten shopping marathon) is shown until SWITCH_AT (2026-11-11 1:59 JST, the end of the marathon), v5 (Yahoo! Black Friday) from then on.  Both are written into the HTML:
the one that fits the build time (JST) is the page, the other sits in a <template> and the visitor's own clock swaps them at SWITCH_AT, so a build that is served late is still
right.  The remaining time is counted in the visitor's browser from fixed times (never written into the build).
KAIDOKI_NOW=2026-11-11T02:00 fixes the build time (tests); KAIDOKI_TODAY alone means noon of that day.
No product price, no shop or item ranking.  No mall data: the pictures are our own."""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

SWITCH_AT = datetime(2026, 11, 11, 1, 59, tzinfo=JST)      # the marathon ends: from here on the Yahoo! Black Friday first view

ICONS_OLD = re.compile(r'<link rel="icon" href="/favicon\.ico"[^>]*>\n<link rel="icon" type="image/png" sizes="32x32"[^>]*>\n<link rel="apple-touch-icon"[^>]*>\n')
ICONS_NEW = ('<link rel="icon" href="/favicon.ico" sizes="any">\n'
             '<link rel="icon" type="image/png" sizes="32x32" href="/assets/fv/d-gold-bag-32.png">\n'
             '<link rel="icon" type="image/png" sizes="16x16" href="/assets/fv/d-gold-bag-16.png">\n'
             '<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">\n')

HEADER = """<header class="fvh"><div class="fwrap">
<a class="flogo" href="/"><img class="mark" src="/assets/fv/d-gold-bag-180.png" width="46" height="46" alt="買い時カレンダーのロゴマーク（深い赤に金の紙袋）"><span class="name">買い時カレンダー<small>SALE-CALENDAR.COM</small></span></a>
<nav aria-label="メイン">
<a href="/calendar/">日程カレンダー</a>
<a href="/buytime/">買い時</a>
<a href="/kaden/">商品ジャンル</a>
<a href="/calc/" class="cta">計算ツール</a>
</nav>
</div></header>
"""

V4 = """<section class="hero">
<div class="hero-grid">
<div class="hero-copy">
<div class="live-row"><span class="live">開催中</span><span class="en">RAKUTEN SHOPPING MARATHON</span></div>
<h1>お買い物マラソン、<br><span class="gold">11月11日1時59分に</span><br>ゴールを迎えます！</h1>
<p class="sub">セールの日程は、主催者の公式発表で確かめたものだけ。未発表は未発表のまま、予想で埋めない。買い時の見極めは、ここから始まります。</p>
<div class="hero-cta">
<a class="fbtn fbtn-gold" href="/rakuten/marathon/">開催中のセールを見る</a>
<a class="fbtn fbtn-ghost" href="/yahoo/">次のセールに備える</a>
</div>
</div>
<div class="hero-visual">
<img src="/assets/fv/main-confetti.webp" width="2240" height="1120" alt="クリーム地に赤い買い物カートとギフト、風船と紙吹雪が舞うセールのキービジュアル">
<span class="cap">キービジュアルはセールの雰囲気を表すイラストです</span>
</div>
</div>
</section>

<div class="fwrap countbar">
<div class="fcard">
<div>
<div class="sale-name"><span class="mall">楽天</span> お買い物マラソン 2026年11月（ジャンル祭と同時開催）</div>
<div class="sale-dates">11月4日（水）20:00 〜 11月11日（水）1:59</div>
<div class="sale-facts">エントリーは11月2日10:00から受付中 ｜ 買い回りの特典は上限7,000ポイント ｜ 付与は12月15日頃の予定（主催者発表）</div>
</div>
<div class="count" id="count" aria-label="終了までのカウントダウン">
<div class="cell"><div class="num" id="cd-d">-</div><div class="lab">日</div></div>
<div class="cell"><div class="num" id="cd-h">-</div><div class="lab">時間</div></div>
<div class="cell"><div class="num" id="cd-m">-</div><div class="lab">分</div></div>
<div class="cell"><div class="num" id="cd-s">-</div><div class="lab">秒</div></div>
</div>
<div class="count-note">終了までの残り時間は、見ている人の時計で計算しています。終わったセールは「終了」と表示します。</div>
</div>
</div>

<div class="fwrap judge">
<div class="fcard">
<div class="face">辛口</div>
<div>
<div class="who">編集部の辛口ジャッジ</div>
<p>上限7,000ポイントに届くのは、10ショップの買い回りでも約77,778円の買い物から。届かない買い方を「損」とは言わない。買う物が先、上限はあと。それがこのセールとの正しい付き合い方だ。</p>
</div>
</div>
</div>

<div class="fwrap next">
<div class="fcard">
<div class="copy">
<div class="kicker">NEXT BIG MATCH</div>
<div class="name">Yahoo!ショッピング<br>ブラックフライデー2026</div>
<div class="dates">11月22日（日）0:00 スタート 〜 11月30日（月）1:59<span id="next-days"></span></div>
<p class="desc">マラソンの次に控える大一番。欲しい物のリストは、今のうちに作っておくのが勝ち筋です。</p>
</div>
<div class="visual"><img src="/assets/fv/next-blackfriday.jpg" width="1368" height="456" alt="黒と金のブラックフライデーのキービジュアル。黒い買い物袋と金のギフトボックス"></div>
</div>
</div>

"""

GENRES = """<div class="fwrap genres">
<div class="lab">商品ジャンルから探す</div>
<div class="row">
<a href="/kaden/" class="hot">家電</a>
<a href="/kaden/pc/">パソコン</a>
<a href="/kaden/eakon/">エアコン</a>
<a href="/kaden/reizoko/">冷蔵庫</a>
<a href="/kaden/small/">掃除機・洗濯機・テレビ</a>
<a href="/randoseru/">ランドセル</a>
</div>
</div>
"""

V5 = """<section class="hero">
<div class="hero-grid">
<div class="hero-copy">
<div class="live-row"><span class="live" id="phase-badge">開幕迫る</span><span class="en">YAHOO! SHOPPING BLACK FRIDAY 2026</span></div>
<h1>ブラックフライデー<br><span class="gold">11月22日0時に</span><br>いよいよ開幕！</h1>
<p class="sub">Yahoo!ショッピングの大型セールが、11月22日（日）0時に始まります。セールの日程は、主催者の公式発表で確かめたものだけ。欲しい物のリストは、開幕前に作っておくのが勝ち筋です。</p>
<div class="hero-cta">
<a class="fbtn fbtn-gold" href="/calendar/">セールの日程を見る</a>
<a class="fbtn fbtn-ghost" href="/buytime/">買い時を調べる</a>
</div>
</div>
<div class="hero-visual">
<img src="/assets/fv/next-blackfriday.jpg" width="1368" height="456" alt="黒と金のブラックフライデーのキービジュアル。黒い買い物袋と金のギフトボックス">
<span class="cap">キービジュアルはセールの雰囲気を表すイラストです</span>
</div>
</div>
</section>

<div class="fwrap countbar">
<div class="fcard">
<div>
<div class="sale-name"><span class="mall">Yahoo!ショッピング</span> ブラックフライデー 2026</div>
<div class="sale-dates">11月22日（日）0:00 〜 11月30日（月）1:59</div>
<div class="sale-facts">期間中の11月25日（水）は「5のつく日」も重なります（PayPayポイント+4%、要エントリー、上限は1人2,000円相当）｜ 最終日は、最もポイントが付く日として主催者が案内しています</div>
</div>
<div class="count" id="count" aria-label="終了までのカウントダウン">
<div class="cell"><div class="num" id="cd-d">-</div><div class="lab">日</div></div>
<div class="cell"><div class="num" id="cd-h">-</div><div class="lab">時間</div></div>
<div class="cell"><div class="num" id="cd-m">-</div><div class="lab">分</div></div>
<div class="cell"><div class="num" id="cd-s">-</div><div class="lab">秒</div></div>
</div>
<div class="count-note" id="count-label">開幕までの残り時間は、見ている人の時計で計算しています。期間中は終了までの残り時間に切り替わります。</div>
</div>
</div>

<div class="fwrap judge">
<div class="fcard">
<div class="face">辛口</div>
<div>
<div class="who">編集部の辛口ジャッジ</div>
<p>主催者の案内では、最終日が最もポイントの付く日だ。ただし在庫は最終日まで待ってくれない。リスト作りは今のうちに済ませて、買う日は条件と在庫を見て決める。それと、期間中の25日は「5のつく日」も重なる。エントリーを忘れるな。</p>
</div>
</div>
</div>

<div class="fwrap next">
<div class="fcard">
<div class="copy">
<div class="kicker">NEXT BIG MATCH</div>
<div class="name">次の大型セールは<br>公式発表待ちです</div>
<div class="dates">12月は大型企画の予告が出ています</div>
<p class="desc">Yahoo!ショッピングは12月からの大型企画で最大25%付与と予告していますが、日程と内容は変わる場合があるという注記つきで、確定ではありません。このサイトでは、公式に確定した日程だけを扱います。</p>
</div>
<div class="visual"><img src="/assets/fv/next-blackfriday.jpg" width="1368" height="456" alt="黒と金のブラックフライデーのキービジュアル。黒い買い物袋と金のギフトボックス"></div>
</div>
</div>

"""

SCRIPT = """<script>
(function () {
  var SWITCH = new Date("2026-11-11T01:59:00+09:00").getTime();
  var MARATHON_END = SWITCH;
  var NEXT_START = new Date("2026-11-22T00:00:00+09:00").getTime();
  var BF_START = NEXT_START;
  var BF_END = new Date("2026-11-30T01:59:00+09:00").getTime();
  var host = document.getElementById("fv-host");
  var alt = document.getElementById("fv-alt");
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function el(id) { return document.getElementById(id); }
  function setCount(diff) {
    el("cd-d").textContent = Math.floor(diff / 86400000);
    el("cd-h").textContent = pad(Math.floor(diff % 86400000 / 3600000));
    el("cd-m").textContent = pad(Math.floor(diff % 3600000 / 60000));
    el("cd-s").textContent = pad(Math.floor(diff % 60000 / 1000));
  }
  function ended(badge, label, text) {
    el("count").innerHTML = '<div class="cell" style="min-width:220px"><div class="num" style="font-size:20px;padding:6px 0">終了しました</div></div>';
    if (badge) { badge.textContent = "終了"; }
    if (label) { label.textContent = text; }
  }
  function swapIfNeeded(now) {
    var want = now < SWITCH ? "v4" : "v5";
    if (host.getAttribute("data-fv") === want || !alt) { return; }
    var t = alt.content.cloneNode(true);
    host.innerHTML = "";
    host.appendChild(t);
    var d = host.querySelector("[data-h1]");      // the waiting block holds its heading as a div (a page has one h1); it becomes the h1 now
    if (d) {
      var h = document.createElement("h1");
      h.innerHTML = d.innerHTML;
      d.parentNode.replaceChild(h, d);
    }
    host.setAttribute("data-fv", want);
    alt.parentNode.removeChild(alt);
    alt = null;
  }
  function tick() {
    var now = Date.now();
    swapIfNeeded(now);
    if (host.getAttribute("data-fv") === "v4") {
      if (MARATHON_END - now <= 0) { ended(null, null, ""); } else { setCount(MARATHON_END - now); }
      var nd = Math.ceil((NEXT_START - now) / 86400000);
      el("next-days").textContent = nd > 0 ? "（開始まであと" + nd + "日）" : "";
    } else {
      var badge = el("phase-badge"), label = el("count-label");
      if (now < BF_START) {
        badge.textContent = "開幕迫る";
        label.textContent = "開幕までの残り時間は、見ている人の時計で計算しています。期間中は終了までの残り時間に切り替わります。";
        setCount(BF_START - now);
      } else if (now < BF_END) {
        badge.textContent = "開催中";
        label.textContent = "終了までの残り時間は、見ている人の時計で計算しています。";
        setCount(BF_END - now);
      } else {
        ended(badge, label, "このセールは終了しました。次のセールは公式発表が出たらお知らせします。");
      }
    }
  }
  tick();
  setInterval(tick, 1000);
})();
</script>
"""


def _build_time() -> datetime:
    v = os.environ.get("KAIDOKI_NOW")
    if v:
        return datetime.fromisoformat(v).replace(tzinfo=JST)
    t = os.environ.get("KAIDOKI_TODAY")
    if t:
        return datetime.fromisoformat(t + "T12:00").replace(tzinfo=JST)
    return datetime.now(JST)


def _no_h1(block: str) -> str:
    return block.replace("<h1>", '<div data-h1="1" class="h1">').replace("</h1>", "</div>")


def first_view(now: datetime) -> str:
    """The block of the build time is the page; the other one waits in a <template> for the visitor's clock."""
    v4_now = now < SWITCH_AT
    live, other = (V4, V5) if v4_now else (V5, V4)
    return (f'<div class="fv" id="fv-host" data-fv="{"v4" if v4_now else "v5"}">\n{live}{GENRES}</div>\n'
            f'<template id="fv-alt">\n{_no_h1(other)}{GENRES}</template>\n{SCRIPT}')


def post(pages: dict, content: list, cfg: dict, spec: dict, site_dir) -> dict:
    html = pages["index.html"]
    new, n = ICONS_OLD.subn(ICONS_NEW, html, count=1)
    assert n == 1, "kaidoki hooks: the icon links of the layout changed"
    html = new
    html = html.replace('<link rel="stylesheet" href="/assets/style.css', '<link rel="stylesheet" href="/assets/fv.css?v=' + _ver(site_dir) + '">\n<link rel="stylesheet" href="/assets/style.css', 1)
    block = HEADER + first_view(_build_time())
    html, n = re.subn(r'<header class="site">.*?</header>\n', lambda m: block, html, count=1, flags=re.S)
    assert n == 1, "kaidoki hooks: the header of the layout changed"
    html, n = re.subn(r'<h1>[^<]*</h1>\n(<p class="answer">)', r"\1", html, count=1)      # the hero's h1 is the only h1; the answer line stays (it counts in the page's readable length)
    assert n == 1, "kaidoki hooks: the top page no longer starts with h1 and answer"
    pages["index.html"] = html
    return pages


def _ver(site_dir) -> str:
    import hashlib
    from pathlib import Path
    return hashlib.sha1((Path(site_dir) / "assets" / "fv.css").read_bytes()).hexdigest()[:8]
