#!/usr/bin/env python3
"""2026-11-25: affiliate search links (Rakuten / Amazon, no price) for the 15 articles that had none, placed right before
the "今日からできること" section (never inside it).  Also: the USJ article named a travel site without a link, so the name is
replaced by a general phrase until the link code exists.  Safe to run twice."""
import json
import os
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apply_20261123 as base  # noqa: E402

# slug: (reason sentence, search word for Rakuten, search word for Amazon)
ITEMS = {
    "aeon-blackfriday-2026": ("羽毛布団を選ぶなら、サイズと重さを決めてから、通販の商品ページでも同じ条件のものを見比べられます。", "羽毛布団", "羽毛布団"),
    "godzilla-0-0-boxoffice": ("映画の余韻を家でも楽しみたいなら、関連グッズを通販で探す手があります。", "ゴジラ グッズ", "ゴジラ グッズ"),
    "google-store-blackfriday": ("本体を選んだら、ケースや画面の保護フィルムも一緒に用意しておくと、届いた日から安心して使えます。", "Pixel ケース", "Pixel ケース"),
    "influenza-yobousesshu-hiyou": ("予防接種とあわせて、毎日の対策に使う道具も切らさないようにしておきたいところです。", "不織布マスク", "不織布マスク"),
    "kfc-haitoku-burger": ("お店に行けない日に家でチキンを楽しみたいなら、冷凍のフライドチキンを通販で探す手もあります。", "冷凍 フライドチキン", "冷凍 フライドチキン"),
    "nenmatsu-chosei-kaisei-fuyo62": ("控除の証明書や給与の書類は、まとめて保管できるファイルがあると、年末に探し回らずに済みます。", "書類ファイル", "書類ファイル"),
    "nenmatsu-chosei-shorui": ("届いた証明書は、項目ごとに分けられるファイルに入れておくと、提出前の確認がしやすくなります。", "書類ファイル", "書類ファイル"),
    "netflix-nesage": ("料金を見直すついでに、テレビで見る環境も確認しておきたい人は、接続機器を通販で比べられます。", "ストリーミング 端末", "ストリーミング 端末"),
    "nozomi-zensekishitei": ("指定席を取ったら、移動の荷物も早めに用意しておくと、当日の乗り降りが楽になります。", "スーツケース 機内持ち込み", "スーツケース 機内持ち込み"),
    "raize-kairyo-nesage": ("車を選んだあとの備えとして、車内の汚れを防ぐ用品も通販で探せます。", "ライズ フロアマット", "ライズ フロアマット"),
    "soccer-brazil-2026": ("次の試合を自宅で盛り上げたいなら、応援用のグッズを通販で探せます。", "サッカー日本代表 グッズ", "サッカー日本代表 グッズ"),
    "starbucks-capsule-toy": ("カプセルトイと一緒にコーヒーの時間も楽しみたいなら、タンブラーを通販で探す手があります。", "タンブラー 保温", "タンブラー 保温"),
    "tate-drama-kaiyaku": ("支払いを見直すなら、毎月の引き落としを書き出せる家計簿があると、不要な契約に気づきやすくなります。", "家計簿", "家計簿"),
    "us-groundstop": ("空港で足止めになったときに備えるなら、スマホを充電できる道具を手荷物に入れておくと安心です。", "モバイルバッテリー", "モバイルバッテリー"),
    "yen-intervention": ("円安で出費が増えやすい時期は、支出を書き出して見直すと、削れるところが見えてきます。", "家計簿", "家計簿"),
}


def anchor(href, text):
    return '<a href="%s" rel="nofollow sponsored noopener" target="_blank">%s</a>（PR）' % (href, text)


def main():
    for slug, (reason, rq, aq) in ITEMS.items():
        p = os.path.join(base.CONTENT, "trend-%s.json" % slug)
        d = json.load(open(p, encoding="utf-8"))
        secs = d["sections"]
        if any('rel=\\"nofollow sponsored' in json.dumps(s, ensure_ascii=False) for s in secs):
            continue
        idx = [i for i, s in enumerate(secs) if s.get("h2", "").startswith("今日") or "今日やること" in s.get("h2", "")]
        idx = idx or [i for i, s in enumerate(secs) if "h2" in s]  # no action section: before the last heading
        assert idx, slug
        rk = anchor(base.rakuten(rq).replace("&", "&amp;"), rq.replace(" ", "の") + "を楽天市場で探す")
        am = anchor("https://www.amazon.co.jp/s?k=%s&amp;tag=amazonmacs-22" % urllib.parse.quote(aq), "Amazonで" + aq.replace(" ", "の") + "を探す")
        secs.insert(idx[-1], {"html": "<p>%s</p><p>%s</p><p>%s</p>" % (reason, rk, am)})
        open(p, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
        print("linked", slug)
    p = os.path.join(base.CONTENT, "trend-usj-winter-kids-free.json")
    raw = open(p, encoding="utf-8").read()
    out = raw.replace("楽天トラベルやじゃらんなどの宿泊予約サイト", "楽天トラベルなどの宿泊予約サイト")
    if out != raw:
        open(p, "w", encoding="utf-8", newline="").write(out)
        print("usj name replaced")


if __name__ == "__main__":
    main()
