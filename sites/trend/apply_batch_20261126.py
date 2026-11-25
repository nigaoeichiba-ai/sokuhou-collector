#!/usr/bin/env python3
"""2026-11-26: add the day's articles from their final drafts (Drive).  Builds on apply_batch_20261125 (same page
shape); adds the Yahoo!Shopping, Jalan and Expedia link markers.  An article whose card image is not back yet is
skipped.  Safe to run twice.  Usage: apply_batch_20261126.py slug [slug ...]"""
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apply_batch_20261125 as prev  # noqa: E402
from apply_jalan_expedia_20261125 import EXPEDIA, JALAN, NOTICE, vc  # noqa: E402

TODAY = "2026-11-26"
DATA_BASIS = "2026年11月26日現在"

# slug: (final file, card image, crumb, primary keyword, [related slugs], category from)
ARTICLES = {
    "trend-softbank-hikari-nesage-1201": ("記事最終稿_ソフトバンク光値上げ_2026-11-26.md", "card_ソフトバンク光値上げ.webp", "ソフトバンク光の値上げ", "ソフトバンク光", ["trend-docomo-nesage-1201", "trend-tokyogas-denki-1201", "trend-netflix-nesage"], "trend-docomo-nesage-1201"),
    "trend-megusuri-nesage-1201": ("記事最終稿_目薬値上げ12月_2026-11-26.md", "card_目薬値上げ12月.webp", "目薬の値上げ", "目薬", ["trend-meiji-nesage-2027", "trend-ajinomoto-mayonnaise-nesage", "trend-yakult-nesage"], "trend-meiji-nesage-2027"),
    "trend-pan-nesage-2027": ("記事最終稿_パン値上げ2027_2026-11-26.md", "card_パン値上げ2027.webp", "パンの値上げ", "パン", ["trend-meiji-nesage-2027", "trend-nissui-nesage", "trend-ajinomoto-mayonnaise-nesage"], "trend-meiji-nesage-2027"),
    "trend-toji-2026-yuzu-kabocha": ("記事最終稿_冬至2026_2026-11-26.md", "card_冬至2026.webp", "冬至2026", "冬至", ["trend-heat-shock-kan", "trend-furusato-nozei-nenmatsu", "trend-nenmatsu-9renkyu-2026"], "trend-heat-shock-kan"),
    "trend-seishun18-fuyu-2026": ("記事最終稿_青春18きっぷ冬版_2026-11-26.md", "card_青春18きっぷ冬版.webp", "青春18きっぷ冬版", "青春18きっぷ", ["trend-nenmatsu-shinkansen-hatsubai-2026", "trend-nenmatsu-9renkyu-2026", "trend-nozomi-zensekishitei"], "trend-nenmatsu-9renkyu-2026"),
    "trend-futagoza-ryuseigun-2026": ("記事最終稿_ふたご座流星群2026_2026-11-26.md", "card_ふたご座流星群2026.webp", "ふたご座流星群", "ふたご座流星群", ["trend-shishiza-ryuseigun-2026", "trend-kandansa-hirou", "trend-winter-tire-kanki"], "trend-shishiza-ryuseigun-2026"),
    "trend-nenmatsu-kosoku-waribiki-2026": ("記事最終稿_年末年始の高速割引_2026-11-26.md", "card_年末年始の高速割引.webp", "年末年始の高速割引", "年末年始 高速割引", ["trend-nenmatsu-9renkyu-2026", "trend-jaf-battery-nenmatsu", "trend-winter-tire-kanki"], "trend-nenmatsu-9renkyu-2026"),
    "trend-misdo-fukubukuro-2027": ("記事最終稿_ミスド福袋2027_2026-11-26.md", "card_ミスド福袋2027.webp", "ミスド福袋2027", "ミスド福袋", ["trend-starbucks-fukubukuro-2027", "trend-kfc-christmas-reserve-2026", "trend-osechi-2027"], "trend-starbucks-fukubukuro-2027"),
    "trend-game-hatsubai-2026-12": ("記事最終稿_12月ゲーム発売_2026-11-26.md", "card_12月ゲーム発売.webp", "12月のゲーム発売", "12月 ゲーム発売日", ["trend-switch2-eraberu-soft-set", "trend-switch-shuri-nesage-1116", "trend-square-enix-blackfriday-part2"], "trend-switch2-eraberu-soft-set"),
    "trend-kusuriya-eiga-yoshu": ("記事最終稿_薬屋の映画予習_2026-11-26.md", "card_薬屋の映画予習.webp", "薬屋の映画予習", "薬屋のひとりごと 映画", ["trend-godzilla-0-0-boxoffice", "trend-tate-drama-kaiyaku", "trend-netflix-nesage"], "trend-godzilla-0-0-boxoffice"),
    "trend-fns-kayosai-2026": ("記事最終稿_FNS歌謡祭2026_2026-11-26.md", "card_FNS歌謡祭2026.webp", "FNS歌謡祭2026", "FNS歌謡祭", ["trend-kohaku-2026", "trend-sony-wh1000xm6-xm5", "trend-netflix-nesage"], "trend-kohaku-2026"),
    "trend-ryukogo-taisho-2026": ("記事最終稿_流行語大賞2026_2026-11-26.md", "card_流行語大賞2026.webp", "流行語大賞2026", "流行語大賞", ["trend-punch-kun-ichikawa-zoo", "trend-kohaku-2026", "trend-yorunoyo-2026"], "trend-kohaku-2026"),
}

_prev_link = prev.link_html

# what is actually lettered on each card (the desk asks the alt text to match it)
ALT = {
    "trend-softbank-hikari-nesage-1201": "「光回線が値上げ！プランを確認！」の文字と、パソコンを指さして驚く男性のイラスト",
    "trend-megusuri-nesage-1201": "「目薬も値上げ！うちのは対象？」の文字と、目薬の容器を見て驚く女性のイラスト",
    "trend-pan-nesage-2027": "「パンも値上げ！朝食どうする？」の文字と、食パンを前に驚く男性のイラスト",
    "trend-toji-2026-yuzu-kabocha": "「もうすぐ冬至！ゆず湯の準備！」の文字と、かぼちゃを抱える男性とゆず湯のイラスト",
    "trend-seishun18-fuyu-2026": "「冬の18きっぷ！どこまで行く？」の文字と、雪の駅で路線図を広げる男性のイラスト",
    "trend-futagoza-ryuseigun-2026": "「流れ星の当たり年！夜空を見上げよう」の文字と、流れ星を指さす二人のイラスト",
    "trend-nenmatsu-kosoku-waribiki-2026": "「割引なしの日！出発日を確認！」の文字と、料金所の前で手帳を見て驚く家族のイラスト",
    "trend-misdo-fukubukuro-2027": "「ドーナツ福袋！予約いつから？」の文字と、赤い袋とドーナツを手にした親子のイラスト",
    "trend-game-hatsubai-2026-12": "「十二月はゲーム祭！どれを選ぶ？」の文字と、コントローラーを握って喜ぶ女性のイラスト",
    "trend-kusuriya-eiga-yoshu": "「映画の前に予習！どこまで読む？」の文字と、本を読んで目を輝かせる女性のイラスト",
    "trend-fns-kayosai-2026": "「二週連続で歌祭り！録画は大丈夫？」の文字と、テレビの前で盛り上がる祖母と孫のイラスト",
    "trend-ryukogo-taisho-2026": "「今年の言葉は？発表は目前！」の文字と、金色のマイクの前で身を乗り出す女性のイラスト",
}


def link_html(label):
    if label.startswith("じゃらんnet"):
        return JALAN
    if label.startswith("エクスペディア"):
        return EXPEDIA
    mm = re.match(r"Yahoo!ショッピングで(.+?)を探す（PR）", label)
    if mm:
        q = mm.group(1)
        target = "https://shopping.yahoo.co.jp/search?p=" + urllib.parse.quote(q)
        return vc("892755274", urllib.parse.quote(target, safe=""), q + "をYahoo!ショッピングで探す")
    return _prev_link(label)


def build(slug):
    prev.ARTICLES, prev.TODAY, prev.link_html = ARTICLES, TODAY, link_html
    prev.build(slug)
    p = os.path.join(prev.CONTENT, slug + ".json")
    d = json.load(open(p, encoding="utf-8"))
    d["data_basis"] = DATA_BASIS
    for s in d["sections"]:
        if 'class="eyecatch"' in s.get("html", ""):
            s["html"] = re.sub(r'alt="[^"]*"', lambda m: 'alt="%s"' % ALT[slug], s["html"])
    # the Jalan programme requires the affiliate notice at the top of the page
    if any("pid=892757567" in s.get("html", "") for s in d["sections"]) and not any(s.get("html") == NOTICE for s in d["sections"]):
        d["sections"].insert(1, {"html": NOTICE})
    open(p, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    for slug in sys.argv[1:]:
        if os.path.exists(os.path.join(prev.CONTENT, slug + ".json")):
            print("skip (already added):", slug)
            continue
        if not os.path.exists(prev.base.DRIVE + ARTICLES[slug][1]):
            print("skip (image not back):", slug)
            continue
        build(slug)
        print("built", slug)
