"""The first view of the top page of sale-calendar.com (prototype v4, owner decision 2026-11-10).

sokuhou/newsite.py calls post() after the pages are rendered.  Only index.html changes: the header and the first view (red hero, countdown bar, judge card,
next-sale card, genre links) replace the old header and h1 (the "answer" line stays under the first view); every section below them (いま分かっている日程 ...) and every other page stay as they were.
The remaining time is counted in the visitor's browser from fixed end times (never written into the build).
After the hero's sale has ended (the build day in Japan is past FV_UNTIL) the hero is not applied and the plain top page is built, so a day-old
"ゴールを迎えます" never stays up; replace the sentences below with the next sale's, then move FV_UNTIL.
No product price, no shop or item ranking.  No mall data: the pictures are our own."""
from __future__ import annotations

import re
from datetime import date

FV_UNTIL = date(2026, 11, 11)      # the day the October marathon ends (1:59 on this day)

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

FIRST_VIEW = """<div class="fv">
<section class="hero">
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

<div class="fwrap genres">
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
<script>
(function () {
  var goal = new Date("2026-11-11T01:59:00+09:00").getTime();
  var nextStart = new Date("2026-11-22T00:00:00+09:00").getTime();
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function tick() {
    var now = Date.now();
    var diff = goal - now;
    if (diff <= 0) {
      document.getElementById("count").innerHTML = '<div class="cell" style="min-width:220px"><div class="num" style="font-size:20px;padding:6px 0">終了しました</div></div>';
    } else {
      document.getElementById("cd-d").textContent = Math.floor(diff / 86400000);
      document.getElementById("cd-h").textContent = pad(Math.floor(diff % 86400000 / 3600000));
      document.getElementById("cd-m").textContent = pad(Math.floor(diff % 3600000 / 60000));
      document.getElementById("cd-s").textContent = pad(Math.floor(diff % 60000 / 1000));
    }
    var nd = Math.ceil((nextStart - now) / 86400000);
    document.getElementById("next-days").textContent = nd > 0 ? "（開始まであと" + nd + "日）" : "";
  }
  tick();
  setInterval(tick, 1000);
})();
</script>
</div>
"""


def post(pages: dict, content: list, cfg: dict, spec: dict, site_dir) -> dict:
    from sites.kaidoki.gen.common import TODAY
    if TODAY > FV_UNTIL:
        return pages
    html = pages["index.html"]
    new, n = ICONS_OLD.subn(ICONS_NEW, html, count=1)
    assert n == 1, "kaidoki hooks: the icon links of the layout changed"
    html = new
    html = html.replace('<link rel="stylesheet" href="/assets/style.css', '<link rel="stylesheet" href="/assets/fv.css?v=' + _ver(site_dir) + '">\n<link rel="stylesheet" href="/assets/style.css', 1)
    html, n = re.subn(r'<header class="site">.*?</header>\n', lambda m: HEADER + FIRST_VIEW, html, count=1, flags=re.S)
    assert n == 1, "kaidoki hooks: the header of the layout changed"
    html, n = re.subn(r'<h1>[^<]*</h1>\n(<p class="answer">)', r"\1", html, count=1)      # the hero's h1 is the only h1; the answer line stays (it counts in the page's readable length)
    assert n == 1, "kaidoki hooks: the top page no longer starts with h1 and answer"
    pages["index.html"] = html
    return pages


def _ver(site_dir) -> str:
    import hashlib
    from pathlib import Path
    return hashlib.sha1((Path(site_dir) / "assets" / "fv.css").read_bytes()).hexdigest()[:8]
