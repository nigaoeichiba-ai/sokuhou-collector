"""Research note: how often do records repeat in the same district?  The share of a prefecture's records that fall in districts with several records, and the districts with the most.

A record's district is the town/district name in its place text, without the prefecture and municipality in front and without house numbers (cut at the first digit or space).
Street-level and lot-level details are never shown.

python sites/kuma/research/scripts/place_repeat.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
MIN_RECORDS = 200
REPEAT = 3           # a district with this many records or more is a "repeat" district


def norm_city(city: str) -> str:
    return re.sub(r"^[^市区町村]{1,5}郡(?=[^市区町村郡]+[町村]$)", "", city.strip())


def district(city: str, place: str) -> str:
    i = place.find(city)
    x = place[i + len(city):] if i >= 0 else place
    x = re.split(r"[\s　(（]|[0-9０-９]|丁目", x)[0]
    x = re.sub(r"^(大字|字)", "", x)
    x = re.sub(r"(周辺|地内|付近|地区)$", "", x)
    return x.strip()


def main() -> None:
    data, per = {}, {}
    for k in SOURCES:
        src = common.load_source(k)
        end = date.fromisoformat(src["as_of"])
        c = Counter()
        n = 0
        for r in src["rows"]:
            d = r[0].date() if isinstance(r[0], datetime) else r[0]
            if d > end or not r[2]:
                continue
            area = district(norm_city(r[2]), r[3])
            if len(area) < 2:
                continue
            n += 1
            c[(norm_city(r[2]), area)] += 1
        data[k] = src
        per[k] = (n, c)
    rows, stats = [], {}
    for k, label in SOURCES.items():
        n, c = per[k]
        if n < MIN_RECORDS:
            continue
        rep = {a: v for a, v in c.items() if v >= REPEAT}
        rep_records = sum(rep.values())
        top = c.most_common(1)[0]
        stats[k] = dict(n=n, areas=len(c), rep_areas=len(rep), rep_share=rep_records / n * 100, top=top, single=sum(1 for v in c.values() if v == 1))
        rows.append([label, f"{n:,}", f"{len(c):,}", f"{len(rep)}", f"{rep_records / n * 100:.0f}%", f"{top[0][0]} {top[0][1]}({top[1]}件)"])
    order = sorted(stats, key=lambda k: stats[k]["rep_share"], reverse=True)
    hi, lo = order[0], order[-1]
    full = SOURCES
    as_of = max(s["as_of"] for s in data.values())
    top_rows = []
    for k in order:
        for (city, area), v in per[k][1].most_common(3):
            top_rows.append([full[k], city, area, f"{v}"])
    total = sum(s["n"] for s in stats.values())
    single_all = sum(s["single"] for s in stats.values())
    areas_all = sum(s["areas"] for s in stats.values())

    doc = {
        "slug": "place-repeat", "date": common.today().isoformat(), "data_as_of": as_of,
        "title": "熊(クマ)の目撃は、同じ地区でくり返されるか。6県の記録を、地区ごとに数える",
        "h1": "同じ地区で、記録がくり返されるか。地区ごとの件数から、「3件以上」の地区の割合を数える",
        "description": f"秋田・宮城・新潟・富山・山口・山梨の令和8年度の記録{total:,}件を、地区(大字・町名)ごとに数え、3件以上の記録がある地区に入る割合を県別に比べました。{full[hi]}が{stats[hi]['rep_share']:.0f}%で最大です。",
        "lead": (f"熊の目撃は、同じ地区で何度も記録されるのか、それとも地区ごとに1件ずつ散らばるのか。令和8年度の記録のうち、場所が書かれた{total:,}件を、地区(大字・町名のレベル)ごとに数えました。"
                 f"番地までは使わず、市町村の下の地区名だけを見ます。{REPEAT}件以上の記録がある地区を「くり返しの多い地区」として、そこに入る記録の割合を県ごとに出します。"),
        "findings": [
            f"{REPEAT}件以上の記録がある地区に入る記録の割合は、{full[hi]}が{stats[hi]['rep_share']:.0f}%でいちばん大きく、{full[lo]}が{stats[lo]['rep_share']:.0f}%でいちばん小さくなりました。",
            f"{len(stats)}県の合計{areas_all:,}地区のうち、記録が1件だけの地区は{single_all:,}地区({single_all / areas_all * 100:.0f}%)です。",
            "地区ごとの件数が最も多かったのは、" +"、".join(f"{r[0]}{r[1]}{r[2]}({r[3]}件)" for r in sorted(top_rows, key=lambda r: -int(r[3]))[:3]) + "です。",
        ],
        "sections": [
            {"h2": "県ごとの、地区の数と、くり返しの多い地区の割合",
             "paragraphs": [f"記録の場所から、市町村の下の地区名を取り出して数えました。「{REPEAT}件以上の地区」は、年度の記録が{REPEAT}件以上ある地区、右から2番目の列は、その地区に入る記録が全体のどれだけを占めるかです。"],
             "table": {"head": ["県", "場所が読めた記録", "地区の数", f"{REPEAT}件以上の地区", "それらの地区に入る記録の割合", "最も件数の多い地区"], "rows": rows,
                       "note": "地区名は、記録に書かれた大字・町名で、番地・丁目は使っていません。地区名が読み取れない記録(市町村名だけなど)は、数えていません。"}},
            {"h2": "県ごとの、件数の多い地区(上位3)",
             "paragraphs": ["地区は、市町村の下の大字・町名です。個別の場所や、番地は載せていません。件数の多い地区は、広い地区や、人の出入りが多い地区の場合もあります。"],
             "table": {"head": ["県", "市町村", "地区", "記録(件)"], "rows": top_rows}},
            {"h2": "くり返しの多い地区に入る記録の割合(グラフ)",
             "paragraphs": [f"県ごとに、{REPEAT}件以上の地区に入る記録の割合を並べました。"],
             "chart": {"kind": "bars", "labels": [full[k] for k in order], "values": [round(stats[k]["rep_share"], 1) for k in order], "title": f"{REPEAT}件以上の地区に入る記録の割合(%)",
                       "desc": f"令和8年度の記録のうち、同じ地区に{REPEAT}件以上の記録がある地区に入る割合を、県ごとに比べた棒グラフ。"}},
        ],
        "method": [
            f"各県の自治体が公表している目撃の記録のうち、令和8年度(2026年4月1日から)の、場所が書かれたものを、公表の最新日まで数えました。記録が{MIN_RECORDS}件に届かない県は、対象にしていません。",
            "地区名は、場所の文字から、先頭の都道府県名・市町村名を除き、最初の数字・空白・「丁目」の前までを取ったものです。「大字」「字」と、末尾の「周辺」「地内」「付近」「地区」は外しました。2文字に満たないものは数えていません。",
            f"同じ市町村の同じ地区名の記録を、同じ地区として数えました。地区名の書き方が記録ごとに違う場合(表記ゆれ)は、別の地区として数えるため、くり返しは実際より少なく出ることがあります。",
        ],
        "caveats": [
            "記録の件数が多い地区は、熊が多い地区とは限りません。人が多く通る場所ほど、見つかりやすく、報告されやすくなります。",
            "場所の書き方は、県や市町村で違います。地区の粒度が違うため、県どうしの割合の大小は、そのまま比べられません。",
            "同じ個体が複数回報告されている場合もあります。件数は、熊の頭数ではありません。令和8年度の記録だけで、ほかの年にも同じ地区が多いかは、言えません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/place_repeat.py",
        "related": [{"label": "県内の出没の集まり方(上位3市町の割合)", "href": "/research/concentration/"}, {"label": "秋田県の最新の目撃情報", "href": "/live/akita/"},
                    {"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"}, {"label": "市町村名から探す", "href": "/search/"}],
    }
    common.write_note(doc)
    print({k: (s["n"], s["areas"], s["rep_areas"], round(s["rep_share"]), s["top"]) for k, s in stats.items()})


if __name__ == "__main__":
    main()
