#!/usr/bin/env python3
"""2026-11-27: add the day's articles from their final drafts (Drive).  Same page shape and link markers as
apply_batch_20261126.  An article is built only when its card image is back and its alt text (what is lettered on the
card, written after looking at it) is filled in.  Safe to run twice.  Usage: apply_batch_20261127.py slug [slug ...]"""
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apply_batch_20261126 as day26  # noqa: E402

prev = day26.prev
TODAY = "2026-11-27"
DATA_BASIS = "2026年11月27日現在"
F = "記事最終稿_%s_2026-11-27.md"
C = "card_%s.webp"


def a(name, crumb, kw, related, catfrom):
    return (F % name, C % name, crumb, kw, related, catfrom)


ARTICLES = {
    "trend-nhk-hai-figure-2026": a("NHK杯2026", "NHK杯フィギュア2026", "NHK杯 フィギュア", ["trend-fns-kayosai-2026", "trend-futagoza-ryuseigun-2026", "trend-kohaku-2026"], "trend-fns-kayosai-2026"),
    "trend-chichibu-yomatsuri-2026": a("秩父夜祭2026", "秩父夜祭2026の回り方", "秩父夜祭", ["trend-yorunoyo-2026", "trend-kandansa-hirou", "trend-nenmatsu-9renkyu-2026"], "trend-yorunoyo-2026"),
    "trend-tullys-fukubukuro-2027": a("タリーズ福袋2027", "タリーズ福袋2027", "タリーズ福袋", ["trend-starbucks-fukubukuro-2027", "trend-misdo-fukubukuro-2027", "trend-ucc-coffee-price"], "trend-starbucks-fukubukuro-2027"),
    "trend-dune-part3-saijoei": a("デューン第3作", "デューンPART3", "デューン PART3", ["trend-kusuriya-eiga-yoshu", "trend-game-hatsubai-2026-12", "trend-netflix-nesage"], "trend-kusuriya-eiga-yoshu"),
    "trend-kagome-nesage-2027": a("カゴメ値上げ2027", "カゴメの値上げ", "カゴメ 値上げ", ["trend-ajinomoto-mayonnaise-nesage", "trend-pan-nesage-2027", "trend-meiji-nesage-2027"], "trend-ajinomoto-mayonnaise-nesage"),
    "trend-sendai-hikari-pageant-2026": a("仙台光のページェント2026", "仙台光のページェント2026", "仙台 光のページェント", ["trend-christmas-market-2026-nyujoryo", "trend-yorunoyo-2026", "trend-nenmatsu-shinkansen-hatsubai-2026"], "trend-yorunoyo-2026"),
    "trend-atami-fuyu-hanabi-2026": a("熱海の冬花火2026", "熱海の冬花火2026", "熱海の花火", ["trend-yorunoyo-2026", "trend-nenmatsu-9renkyu-2026", "trend-nenmatsu-shinkansen-hatsubai-2026"], "trend-yorunoyo-2026"),
    "trend-midosuji-illumination-2026": a("御堂筋イルミ2026", "御堂筋イルミ2026", "御堂筋イルミネーション", ["trend-yorunoyo-2026", "trend-christmas-market-2026-nyujoryo", "trend-nenmatsu-9renkyu-2026"], "trend-yorunoyo-2026"),
    "trend-danto-kanki-yuki-sonae": a("暖冬の急な寒気", "暖冬と雪の備え", "雪の備え", ["trend-elnino-danto-2026", "trend-winter-tire-kanki", "trend-teiden-danbou"], "trend-elnino-danto-2026"),
    "trend-suidokan-toketsu-boshi": a("水道管の凍結対策", "水道管の凍結防止", "水道管の凍結防止", ["trend-teiden-danbou", "trend-heat-shock-kan", "trend-osouji-november"], "trend-osouji-november"),
    "trend-hinoiri-hayai-2026": a("日の入りいちばん早い", "日の入りが早い時期", "日の入り", ["trend-toji-2026-yuzu-kabocha", "trend-futagoza-ryuseigun-2026", "trend-yorunoyo-2026"], "trend-toji-2026-yuzu-kabocha"),
    "trend-winter-camp-neru-sobi": a("冬キャンプの寝る装備", "冬キャンプの寝る装備", "冬キャンプ", ["trend-teiden-danbou", "trend-futagoza-ryuseigun-2026", "trend-winter-tire-kanki"], "trend-futagoza-ryuseigun-2026"),
}

# filled in after looking at each returned card
ALT = {
    "trend-nhk-hai-figure-2026": "「氷上の熱戦！週末は応援！」の文字と、テレビのフィギュアスケートに声援を送る祖母と孫のイラスト",
    "trend-chichibu-yomatsuri-2026": "「冬の夜祭り！花火も山車も！」の文字と、灯りのともる山車と花火の前で喜ぶ男女のイラスト",
    "trend-tullys-fukubukuro-2027": "「コーヒー福袋！受け取りを忘れずに！」の文字と、紙袋を抱えて雪の街を走る男性のイラスト",
    "trend-dune-part3-saijoei": "「砂の大作が来る！予習するなら今！」の文字と、映画館で砂漠の映像を見て驚く男性のイラスト",
    "trend-kagome-nesage-2027": "「ケチャップ値上げ！家の在庫は？」の文字と、赤いボトルを手に驚く父親とオムライスを見る子どものイラスト",
    "trend-sendai-hikari-pageant-2026": "「冬の仙台へ！光の並木道！」の文字と、光る並木の下でスマホを掲げる女性2人のイラスト",
    "trend-atami-fuyu-hanabi-2026": "「冬の熱海花火！宿はお早めに！」の文字と、海に上がる花火を指さす年配の夫婦のイラスト",
    "trend-midosuji-illumination-2026": "「光の大通り！大阪の冬散歩！」の文字と、電飾の並木道を歩きながら見上げる男性と若い女性のイラスト",
    "trend-danto-kanki-yuki-sonae": "「暖冬でも油断禁物！靴と雪かきの備え！」の文字と、雪の降る玄関先でスコップを手に空を見る女性のイラスト",
    "trend-suidokan-toketsu-boshi": "「水道管が凍る！冷える前に保温！」の文字と、布を巻いた屋外の蛇口の横で親指を立てる男性のイラスト",
    "trend-hinoiri-hayai-2026": "「もう日が暮れる！帰り道に光る備え！」の文字と、夕焼けの道でランドセルに反射材を付ける母親と子どものイラスト",
    "trend-winter-camp-neru-sobi": "「テントで火はNG！寝る装備でぬくぬく！」の文字と、寝袋にくるまる男性と湯たんぽを抱える女性のイラスト",
}

# deadline data for the top page's "today" box: slug -> (deadline, badge, title, text)
TODO = {
    "trend-nhk-hai-figure-2026": ("2026-11-28", "放送は29日まで", "NHK杯の録画予約を入れる", "競技と放送局は時間帯で変わります。見たい種目の番組を番組表で確かめて予約しましょう。"),
    "trend-chichibu-yomatsuri-2026": ("2026-12-03", "開催は12月2日・3日", "秩父夜祭、行く日と帰りの足を決める", "花火の時間は2日と3日で違います。行く日を決めて、帰りの列車か宿を調べましょう。"),
    "trend-tullys-fukubukuro-2027": ("2026-12-10", "予約は12月10日まで", "タリーズ福袋のWeb予約を確かめる", "数量限定です。受け取る店を決めて、予約画面で受付状況を見ましょう。"),
    "trend-dune-part3-saijoei": ("2026-12-03", "再上映は1週間限定", "デューン前2作の上映時刻を調べる", "IMAXの再上映は対象の劇場だけで、日替わりです。観る日を決めて席を取りましょう。"),
    "trend-sendai-hikari-pageant-2026": ("2026-12-27", "12月4日から27日まで", "仙台の点灯を見に行く日を決める", "曜日で消灯の時刻が変わります。行く日を決めて、宿の空きを調べましょう。"),
    "trend-atami-fuyu-hanabi-2026": ("2026-12-25", "花火は12月6日と25日", "熱海の花火、帰り方を先に決める", "終了後の駅は混みます。泊まるか電車で帰るかを決めて、泊まるなら空室を調べましょう。"),
    "trend-midosuji-illumination-2026": ("2026-12-31", "大みそかまで", "御堂筋イルミに行く日を選ぶ", "中之島の催しも目当てなら、12月11日から25日の間で予定を組みましょう。"),
}


_day26_link = day26.link_html


def link_html(label):
    # the public content may only carry the fixed top page of Yahoo! Shopping (tests/test_trend_site), and the link says so
    mm = re.match(r"Yahoo!ショッピングで(.+?)を探す（PR）", label)
    if mm:
        return day26.vc("892755274", urllib.parse.quote("https://shopping.yahoo.co.jp/", safe=""),
                        "Yahoo!ショッピングのトップから" + mm.group(1) + "を探す")
    return _day26_link(label)


day26.link_html = link_html


def build(slug):
    day26.ARTICLES, day26.TODAY, day26.DATA_BASIS = ARTICLES, TODAY, DATA_BASIS
    day26.ALT = ALT
    day26.build(slug)
    p = os.path.join(prev.CONTENT, slug + ".json")
    d = json.load(open(p, encoding="utf-8"))
    for s in d["sections"]:
        # the Expedia affiliate link needs the same notice as the Jalan one
        if "pid=892757568" in s.get("html", "") and not any(x.get("html") == day26.NOTICE for x in d["sections"]):
            d["sections"].insert(1, {"html": day26.NOTICE})
            break
    if slug in TODO:
        d["todo"] = dict(zip(("deadline", "badge", "title", "text"), TODO[slug]))
    open(p, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    for slug in sys.argv[1:]:
        if os.path.exists(os.path.join(prev.CONTENT, slug + ".json")):
            print("skip (already added):", slug)
            continue
        if not os.path.exists(prev.base.DRIVE + ARTICLES[slug][1]):
            print("skip (image not back):", slug)
            continue
        if slug not in ALT:
            print("skip (alt not written):", slug)
            continue
        build(slug)
        print("built", slug)
