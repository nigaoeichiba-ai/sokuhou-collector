"""Research note: on which day does a municipality's first record of the fiscal year fall?  Municipal sources that list municipality and date (R08).

For each municipality with MIN_RECORDS records or more, the first record of the year (1 April on) and the month it falls in.  The note says that the first record in a list
is not the first appearance of a bear (it is the first one that was reported and published).

python sites/kuma/research/scripts/first_sighting.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
MIN_RECORDS = 10
MIN_CITIES = 8


def norm_city(city: str) -> str:
    import re
    return re.sub(r"^[^市区町村]{1,5}郡(?=[^市区町村郡]+[町村]$)", "", city.strip())


def md(d: date) -> str:
    return f"{d.month}月{d.day}日"


def main() -> None:
    data, firsts = {}, {}
    for k in SOURCES:
        src = common.load_source(k)
        end = date.fromisoformat(src["as_of"])
        by = defaultdict(list)
        for r in src["rows"]:
            d = r[0].date() if isinstance(r[0], datetime) else r[0]
            if d <= end and r[2]:
                by[norm_city(r[2])].append(d)
        data[k] = src
        firsts[k] = {c: (min(v), len(v)) for c, v in by.items() if len(v) >= MIN_RECORDS}
    rows, stats = [], {}
    month_names = {4: "4月", 5: "5月", 6: "6月", 7: "7月以降"}
    for k, label in SOURCES.items():
        f = firsts[k]
        if len(f) < MIN_CITIES:
            continue
        ds = sorted(d for d, _ in f.values())
        med = ds[len(ds) // 2]
        mc = Counter(min(d.month, 7) for d in ds)
        stats[k] = dict(n=len(ds), median=med, earliest=ds[0], latest=ds[-1], by_month=mc, april=mc.get(4, 0) / len(ds) * 100)
        rows.append([label, f"{len(ds)}", md(ds[0]), md(med), md(ds[-1])] + [f"{mc.get(m, 0)}({mc.get(m, 0) / len(ds) * 100:.0f}%)" for m in (4, 5, 6, 7)])
    order = sorted(stats, key=lambda k: stats[k]["april"], reverse=True)
    hi, lo = order[0], order[-1]
    last = {k: max(firsts[k].items(), key=lambda kv: kv[1][0]) for k in stats}
    latest_k = max(stats, key=lambda k: stats[k]["latest"])
    total_c = sum(s["n"] for s in stats.values())
    as_of = max(src["as_of"] for src in data.values())
    # where the first record came late although the municipality has many records: the municipalities with 30+ records whose first record is after 1 May
    late_big = [(SOURCES[k], c, d, n) for k in stats for c, (d, n) in firsts[k].items() if n >= 30 and d >= date(2026, 5, 1)]
    late_big.sort(key=lambda t: (-t[3], t[1]))
    full = SOURCES
    buckets = [("10〜19件", 10, 19), ("20〜49件", 20, 49), ("50件以上", 50, 10**6)]
    bucket_rows, bucket_med = [], {}
    for name, lo_n, hi_n in buckets:
        ds = sorted(d for k in stats for d, n in firsts[k].values() if lo_n <= n <= hi_n)
        if ds:
            bucket_med[name] = ds[len(ds) // 2]
            bucket_rows.append([name, f"{len(ds)}", md(ds[len(ds) // 2]), md(ds[-1]), f"{sum(1 for d in ds if d.month == 4) / len(ds) * 100:.0f}%"])

    doc = {
        "slug": "first-sighting", "date": common.today().isoformat(), "data_as_of": as_of,
        "title": f"熊(クマ)の今年度の最初の記録は、市町村ごとにいつか。{len(stats)}県の「最初の記録の日」を数える",
        "h1": f"今年度の最初の目撃は、いつ記録されたか。市町村ごとの「最初の記録の日」を{len(stats)}県で数える",
        "description": f"{'・'.join(full[k].removesuffix('県') for k in stats)}の令和8年度の記録から、記録が{MIN_RECORDS}件以上ある{total_c}市町村の「最初の記録の日」を数えました。4月に最初の記録があった割合は県で違います。",
        "lead": (f"冬眠から覚めた熊の記録は、市町村ごとに、いつから載り始めるのか。令和8年度(2026年4月1日から)の記録のうち、{MIN_RECORDS}件以上の記録がある市町村について、年度の最初の記録の日を数えました。"
                 f"対象は、{'・'.join(full[k] for k in stats)}の、{total_c}市町村です。"),
        "findings": [
            f"最初の記録が4月だった市町村の割合は、{full[hi]}が{stats[hi]['april']:.0f}%でいちばん大きく、{full[lo]}が{stats[lo]['april']:.0f}%でいちばん小さくなりました。",
            f"最初の記録の日の中央値(市町村を早い順に並べた真ん中)は、" + "、".join(f"{full[k]}が{md(stats[k]['median'])}" for k in order) + "です。",
            (f"記録が30件以上あっても、最初の記録が5月以降だった市町村は{len(late_big)}市町村あります(例: {late_big[0][0]}{late_big[0][1]}の{md(late_big[0][2])}、{late_big[0][3]}件)。" if late_big else "記録が30件以上ある市町村は、すべて、最初の記録が4月でした。"),
        ],
        "sections": [
            {"h2": "県ごとの、最初の記録の日",
             "paragraphs": [f"記録が{MIN_RECORDS}件以上ある市町村だけを数えました。「最も早い」「中央値」「最も遅い」は、市町村の最初の記録の日です。右の4列は、最初の記録が4月・5月・6月・7月以降だった市町村の数(かっこの中は割合)です。"],
             "table": {"head": ["県", "市町村数", "最も早い", "中央値", "最も遅い", "4月", "5月", "6月", "7月以降"], "rows": rows,
                       "note": "4月1日以降の記録から数えています。それより前の冬の記録は、対象に入れていません。"}},
            {"h2": "最初の記録が遅かった市町村",
             "paragraphs": [f"記録の多い市町村でも、最初の記録が遅いところがあります。県ごとに、最初の記録がいちばん遅かった市町村は次のとおりです(記録{MIN_RECORDS}件以上)。"],
             "table": {"head": ["県", "市町村", "最初の記録", "年度の記録(件)"], "rows": [[full[k], last[k][0], md(last[k][1][0]), f"{last[k][1][1]}"] for k in stats]}},
            {"h2": "年度の記録が多い市町村ほど、最初の記録は早いか",
             "paragraphs": ["年度の記録の件数で市町村を3つに分けて、最初の記録の日を比べました。" + (f"最初の記録の日の中央値は、10〜19件の市町村が{md(bucket_med['10〜19件'])}、50件以上の市町村が{md(bucket_med['50件以上'])}です。" if "10〜19件" in bucket_med and "50件以上" in bucket_med else ""),
                            "記録の多い市町村は、年度の初めから記録が載りやすく、最初の記録の日が早くなる傾向が見られます。ただし、これは、記録が多いほど「最初の1件」が早く出やすいという数え方の結果でもあります。"],
             "table": {"head": ["年度の記録", "市町村数", "最初の記録の中央値", "最も遅い", "4月だった割合"], "rows": bucket_rows}},
            {"h2": "4月に最初の記録があった割合(グラフ)",
             "paragraphs": ["県ごとに、最初の記録が4月だった市町村の割合を並べました。"],
             "chart": {"kind": "bars", "labels": [full[k] for k in order], "values": [round(stats[k]["april"], 1) for k in order], "title": "最初の記録が4月だった市町村の割合(%)",
                       "desc": f"記録が{MIN_RECORDS}件以上ある市町村のうち、令和8年度の最初の記録が4月だった割合を、県ごとに比べた棒グラフ。"}},
        ],
        "method": [
            f"各県の自治体が公表している目撃の記録のうち、令和8年度(2026年4月1日から)のものを、公表の最新日まで数えました。市町村は、記録に書かれた市町村名(「〇〇郡」は除く)で分け、年度の記録が{MIN_RECORDS}件以上のものを対象にしました。県内の市町村が{MIN_CITIES}に満たない県は入れていません(山口県は、記録が{MIN_RECORDS}件以上の市町村が少ないため、入っていません)。",
            "最初の記録の日は、その市町村の記録のうち、いちばん早い日付です。痕跡など、種別が目撃でない記録も含みます。日付が公表の日より後になっている記録は、除いています。",
            "対象の県は、記録に市町村名と日付が書かれ、4月から記録が載っている県です。記録を市町村ごとに公表していない県は、対象にしていません。",
        ],
        "caveats": [
            "最初の記録の日は、熊が最初に現れた日ではありません。報告され、公表された最初の記録の日です。報告の受け付けや、記録に入れる基準(痕跡を含むか)が、県や市町村で違います。",
            "公表の始まりが年度の初めからではない市町村もあります。記録が少ない市町村では、最初の記録の日が遅くなりやすく、「記録がない=熊がいない」とは言えません。",
            "令和8年度の1年分だけで、ほかの年にも同じになるかは、この記録だけでは言えません。県どうしの比べは、記録の取り方の違いを含みます。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/first_sighting.py",
        "related": [{"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"},
                    {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"}, {"label": "何月に多いか(都道府県別)", "href": "/season/"}, {"label": "週ごとのまとめ", "href": "/digest/"}],
    }
    common.write_note(doc)
    print(stats, late_big[:3])


if __name__ == "__main__":
    main()
