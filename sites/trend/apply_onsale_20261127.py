#!/usr/bin/env python3
"""2026-11-27: the Amazon Black Friday early sale and the winter Seishun 18 ticket are on sale from today, so the two
articles stop speaking of them as coming (desk request 2026-11-27 and the 11/27 deadline row).  Safe to run twice."""
import json
import os

CONTENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content")
TODAY = "2026-11-27"
BASIS = "2026年11月27日現在"

AMAZON = [
    ("Amazonブラックフライデーは11月27日スタート！楽天の終了後に先行セールが始まる",
     "Amazonブラックフライデーは開催中！先行セールは29日23時59分まで"),
    ("先行セールは11月27日0時開始で例年より遅い。楽天は11月25日に終了。これからはAmazonの日程に合わせて、買う物を決める",
     "先行セールは開催中で11月29日23時59分まで。本セールは11月30日0時から12月7日23時59分まで"),
    ("Amazonのブラックフライデーは、先行セールが11月27日0時に始まります。例年の前倒しの流れとは違い、予想より遅いスタートです。先に始まった楽天ブラックフライデーは、11月25日1時59分に終了しました。買い物の予定は、楽天とAmazonで分けて組み立てるのが現実的です。まず日付を手帳かカレンダーに入れて、楽天で済ませる物とAmazonまで待つ物を仕分けしましょう。",
     "Amazonのブラックフライデーは、先行セールが11月27日0時に始まりました。先行セールは11月29日23時59分まで開催中です。本セールは11月30日0時から12月7日23時59分まで。買う物が決まっている場合は、先行セールの価格から確認しましょう。"),
    ("Amazonのブラックフライデーは、先行セールが11月27日0時に始まります。例年の前倒しの流れとは違い、予想より遅いスタートです。",
     "Amazonのブラックフライデーは、先行セールが11月27日0時に始まりました。11月29日23時59分まで開催中です。"),
    ("Amazonのブラックフライデーは、先行セールが11月27日0時に始まります。",
     "Amazonのブラックフライデーは、先行セールが11月27日0時に始まりました。"),
    ("さらに、楽天が11月25日1時59分に終わってから、Amazonの先行セールが始まるまでは約46時間あります。",
     "楽天が11月25日1時59分に終わってから、Amazonの先行セールが始まるまでは約46時間でした。"),
    ("この表で確認できるのは、2つのセールの期間が重ならないということです。楽天の終了後は、約46時間の空白をはさんでAmazonが始まる日程です。両方を使うなら、買う順番を決めやすい並びです。",
     "この表で確認できるのは、2つのセールの期間が重ならないということです。楽天は終了したので、いま比べる相手はAmazonの先行セールと本セールになります。"),
    ("<ol><li>日付を4つ、カレンダーに入れます。楽天の終了（11月25日1時59分）、Amazonの先行セール開始（11月27日0時）、本セール開始（11月30日0時）、セール全体の終了（12月7日23時59分）です。</li><li>欲しい物を「すぐ買う物」と「Amazonまで待つ物」に仕分けします。急ぎの物は、先に判断しておきましょう。</li>",
     "<ol><li>日付を3つ、カレンダーに入れます。先行セールの終了（11月29日23時59分）、本セール開始（11月30日0時）、セール全体の終了（12月7日23時59分）です。</li><li>欲しい物を「先行セールで買う物」と「本セールまで様子を見る物」に仕分けします。急ぎの物は、先に判断しておきましょう。</li>"),
    ("<li>セール前の通常価格を記録しておきます。手順は、11月11日公開の「ブラックフライデー前にやること」の記事で紹介しています。この記事は日程が確定した続報の位置づけです。</li>",
     "<li>表示されているセール価格が、ふだんの価格と比べて安いのかを確かめます。比べ方は、11月11日公開の「ブラックフライデー前にやること」の記事で紹介しています。</li>"),
    (">Amazonのセールを楽天市場で探す</a>", ">ブラックフライデーの商品を楽天市場で探す</a>"),
    (">AmazonでAmazonのセールを探す</a>", ">ブラックフライデーの商品をAmazonで探す</a>"),
]

SEISHUN = [
    ("青春18きっぷ冬版は11月27日発売！ いつまで買える？3日間と5日間の選び方",
     "青春18きっぷ冬版が発売スタート！いつまで買える？3日間と5日間の選び方"),
    ("2026年度の冬の青春18きっぷは、11月27日に発売が始まります。",
     "2026年度の冬の青春18きっぷは、11月27日に発売が始まりました。"),
]


TODO = {"deadline": "2026-11-29", "badge": "先行セールは11月29日まで", "title": "Amazonの先行セール、29日の夜までに中身を確認",
        "text": "先行セールは11月29日23時59分まで開催中です。急ぎの物から価格を確かめ、残りは30日からの本セールと見比べましょう。"}


def edit(slug, pairs):
    path = os.path.join(CONTENT, slug + ".json")
    d = json.load(open(path, encoding="utf-8"))
    if d["updated"] == TODAY:
        print("skip (already):", slug)
        return

    def walk(v):
        if isinstance(v, str):
            for old, new in pairs:
                if old in v:
                    used.add(old)
                    v = v.replace(old, new)
            return v
        if isinstance(v, list):
            return [walk(x) for x in v]
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        return v

    used = set()
    d = walk(d)
    missing = [old for old, _ in pairs if old not in used]
    assert not missing, (slug, missing)
    d["updated"], d["data_basis"] = TODAY, BASIS
    if slug == "trend-amazon-blackfriday-nittei":
        d["todo"] = TODO
    open(path, "w", encoding="utf-8", newline="").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    print("changed", slug)


if __name__ == "__main__":
    edit("trend-amazon-blackfriday-nittei", AMAZON)
    edit("trend-seishun18-fuyu-2026", SEISHUN)
