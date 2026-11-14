# -*- coding: utf-8 -*-
"""NEWT ブラックフライデーの記事を公開する(2026-11-14)。
本文は Muse の最終稿 sokuhou/inbox/記事最終稿_NEWTブラックフライデー_2026-11-14.md(オーナー承認済み)をそのまま構造にしたもの。
カード・アイキャッチの画像は Muse が用意した card-newt-blackfriday.webp(sokuhou/outbox)。
何度実行しても同じ結果になる。"""
import json
import re
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
C = HERE / "content"
IMG = HERE / "assets" / "img"
SLUG = "trend-newt-blackfriday"
SRC_IMG = Path("H:/マイドライブ/sokuhou/outbox/card-newt-blackfriday.webp")

if SRC_IMG.exists():
    im = Image.open(SRC_IMG).convert("RGB")
    im.resize((1280, round(im.height * 1280 / im.width)), Image.LANCZOS).save(IMG / "eye-trend-newt-blackfriday.webp", "WEBP", quality=82, method=6)

LINK = '<a href="https://newt.net/sale-teaser" target="_blank" rel="noopener">NEWTのセール特設ページ</a>'
page = {
    "updated": "2026-11-14",
    "data_basis": "2026年11月14日12時現在",
    "sources": [],
    "credit": "株式会社令和トラベル「旅行予約サービス『NEWT』、『BLACK FRIDAY』セールを開催」（2026年11月9日発表）、トラベルWatch（2026年11月14日）をもとに作成",
    "path": f"/{SLUG}/",
    "top_lead": "NEWTのBFは今日12時スタート。1万円クーポンの受け取りは11時59分で終了済み。",
    "kind": "article",
    "parent": "/",
    "title": "NEWTのブラックフライデーが始まった 1万円クーポンの受け取りは11時59分で終了",
    "h1": "NEWTのブラックフライデーが始まった 1万円クーポンの受け取りは11時59分で終了",
    "category": "暮らし",
    "published": "2026-11-14",
    "seq": 41,
    "crumb": "NEWTのブラックフライデー",
    "primary_kw": "NEWTのブラックフライデー",
    "secondary_kw": ["NEWT クーポン", "NEWT セール 2026", "海外ツアー 先着 セール"],
    "intent": 1,
    "description": "旅行予約サービスNEWTのブラックフライデーが11月14日12時に開始。1万円OFFクーポンの受け取りは11時59分で終了済みです。クーポンの条件、先着ツアーの例、週末の最大50％OFFクーポンをまとめました。",
    "answer": "NEWTのブラックフライデーは11月14日12時に始まり、11月28日11時59分まで続きます。1万円OFFクーポンの受け取りは今日11時59分で終わりました。受け取れた方は条件を確かめて予約へ、間に合わなかった方は毎週土日の最大50％OFF先着クーポンを狙えます。",
    "related": [
        {"path": "/trend-blackfriday-price/", "text": "ブラックフライデーは価格を比較する前に、通常価格を記録しておく"},
        {"path": "/trend-usj-winter-kids-free/", "text": "USJの冬イベント、11月13日開幕！子ども1名無料の「キッズ」特典"},
    ],
    "sections": [
        {"html": '<p class="eyecatch"><img src="/assets/img/eye-trend-newt-blackfriday.webp" width="1280" alt="NEWTのブラックフライデーを表す絵。赤と黄色の放射状の背景に、SALEの値札、飛行機、自由の女神、台北101、エッフェル塔、クーポンのメッセージが届いたスマートフォン" fetchpriority="high"></p>'},
        {"paras": [
            "旅行予約サービス「NEWT（ニュート）」のブラックフライデーは、今日11月14日（土）の12時に始まりました。このセールには、先に動かないと取り逃がすものが1つありました。公式LINEの新規友だち追加でもらえる海外ツアー10,000円OFFクーポンは、受け取りが今日11時59分まで。セールが始まる1分前に締め切られる形で、受け取りはすでに終わっています。",
            "先に結論です。セールは11月28日（土）11時59分まで続きます。クーポンを受け取った方は、今日からの予約で使えます。受け取りに間に合わなかった方も、期間中の毎週土日には最大50％OFFの先着クーポンが出るので、狙う機会は残ります。",
            "読者が押さえるべき点は、次の3つです。",
        ]},
        {"html": "<ul><li>クーポンの受け取りは今日11時59分で終わった（セール開始の1分前に締め切り）</li><li>クーポンには条件がある（新規の友だち追加だけ、初回の予約だけ、旅行金額10万円以上）</li><li>クーポンはセールの先着ツアーには使えない。通常のツアーや宿の予約が対象</li></ul>"},
        {"h2": "ここは誤解しないで クーポンの条件"},
        {"paras": [
            "10,000円OFFクーポンは、事前告知期間（11月9日12時から今日11時59分まで）に、公式LINEを新しく友だち追加した方だけが対象です。すでに友だち登録している方は、今回のクーポンはもらえません。",
            "使える場面も決まっています。NEWTでの初回の予約だけ、旅行金額が10万円以上のときだけです。そして大事なのが、ブラックフライデーのセール対象ツアーには、このクーポンは使えません。クーポンが使えるのは、通常販売のツアーと宿・ホテルの予約です。先着セールツアーを狙う場合はクーポンとは別に、12時の開始に合わせて動く形になります。クーポンの利用数には上限があり、達し次第終わります。",
        ]},
        {"h2": "セールの中身 先着ツアーと週末クーポン"},
        {"paras": [
            "セールの目玉は、主要エリアの先着セールツアーです。韓国19,800円から、台湾29,800円から、ハワイ139,800円からといった価格です。先着なので、人気の行き先は早めに埋まる見込みです。",
            "変わり種もあります。行き先が直前まで分からない「韓国のどこかへ行けるミステリーツアー」は、成田発の直行便で午前出発、2泊3日・燃油込みで1名25,000円です。NEWT Bespokeの南極ツアーは200万円OFFの1名22,222,220円からという、眺めるだけでも楽しい枠もあります。",
            "セール期間中の毎週土日は、海外ツアー最大50％OFFの先着クーポンも出ます。今日の12時に取り逃がしても、週末ごとに狙う機会は残ります。",
        ]},
        {"table": {"caption": "", "cols": ["項目", "内容"], "num_cols": [], "rows": [
            ["セール期間", "11月14日（土）12時から11月28日（土）11時59分"],
            ["10,000円OFFクーポンの受け取り", "今日11時59分で終了（公式LINEの新規友だち追加が条件だった）"],
            ["クーポンの条件", "初回の予約だけ、旅行金額10万円以上、セール対象ツアーには使えない"],
            ["先着ツアーの例", "韓国19,800円から、台湾29,800円から、ハワイ139,800円から"],
            ["週末のクーポン", "毎週土日、海外ツアー最大50％OFF（先着）"],
        ]}},
        {"h2": "自分はどれ？状況別の動き方"},
        {"paras": ["ここまでの条件を、読者の状況ごとに並べ直しました。新しい事実は足しておらず、上の内容の整理です。"]},
        {"table": {"caption": "", "cols": ["状況", "使えるもの", "動き方"], "num_cols": [], "rows": [
            ["クーポンを受け取れた", "10,000円OFFクーポン", "通常のツアーか宿の予約で使う。初回の予約で旅行金額10万円以上が条件"],
            ["受け取りに間に合わなかった", "毎週土日の最大50％OFF先着クーポン", "土日に海外ツアーを狙う。先着なので早めに動く"],
            ["先着セールツアーを狙う", "韓国・台湾・ハワイなどの先着ツアー", "10,000円OFFクーポンは使えないので、クーポンとは別に考える"],
        ]}},
        {"h2": "今日からできること"},
        {"html": "<ol><li>クーポンを受け取った方は、使える条件（初回の予約だけ、旅行金額10万円以上、セール対象ツアーには使えない）を公式ページで確かめてから予約に進む</li><li>12時の開始に合わせて、特設ページで先着ツアーの残りを確認する。クーポンはセールツアーには使えないので、通常ツアーに使う計画と分けて考える</li><li>今日決めきれない場合は、期間中の土日の最大50％OFFクーポンを狙う日を決めておく。セールは11月28日11時59分まで</li></ol>"},
        {"html": f"<p>{LINK}は、NEWTの公式サイトで公開されています。クーポンの細かい利用条件も、公式ページで確かめてから予約に進んでください。</p>"},
    ],
}

f = C / f"{SLUG}.json"
new = json.dumps(page, ensure_ascii=False, indent=1) + "\n"
if not f.exists() or f.read_text(encoding="utf-8") != new:
    f.write_bytes(new.encode("utf-8"))
    print("wrote", f.name)


def add_related(slug: str, path: str, text: str) -> None:
    g = C / f"{slug}.json"
    t = g.read_text(encoding="utf-8")
    if f'"{path}"' in t.split('"related"', 1)[1]:
        return
    nl = "\r\n" if "\r\n" in t else "\n"
    m = re.search(r'("related":\s*\[)(.*?)(\s*\])', t, re.S)
    assert m, slug
    body = m.group(2)
    ind = re.search(r'\n(\s*)\{', body).group(1) if re.search(r'\n(\s*)\{', body) else "  "
    item = f'{nl}{ind}{{{nl}{ind} "path": {json.dumps(path)},{nl}{ind} "text": {json.dumps(text, ensure_ascii=False)}{nl}{ind}}}'
    n = t[:m.end(2)] + "," + item + t[m.end(2):]
    json.loads(n)
    g.write_bytes(n.encode("utf-8"))
    print("related added to", slug)


NEWT_TEXT = "NEWTのブラックフライデーが始まった 1万円クーポンの受け取りは11時59分で終了"
add_related("trend-blackfriday-price", f"/{SLUG}/", NEWT_TEXT)
add_related("trend-usj-winter-kids-free", f"/{SLUG}/", NEWT_TEXT)
