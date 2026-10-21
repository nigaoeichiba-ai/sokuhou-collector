"""Research note: do the places where bears are reported move from month to month?  Monthly centre of the recorded points (median latitude and longitude) against the year's centre,
and a shuffle test that asks how large a shift months with no real difference would show by chance.
(Akita, Niigata, Yamaguchi, Yamanashi: the sources that record a position; Akita and Niigata give coordinates for almost every record, Yamaguchi and Yamanashi for about 97%.)

python sites/kuma/research/scripts/latitude_by_month.py
"""
from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "niigata": "新潟県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
MIN_MONTH = 30            # a month with fewer records than this is not compared
SHUFFLES = 2000
SEED = 20261021
KM_LAT = 111.2            # km per degree of latitude


def points(key: str) -> list[tuple[int, float, float]]:
    raw = json.loads((common.DATA / f"{key}_kuma.json").read_text(encoding="utf-8"))
    out = []
    for x in raw["sightings"]:
        if x["observed_at"][:10] < common.FY_START.isoformat() or not x.get("lat") or not x.get("lon"):
            continue
        out.append((int(x["observed_at"][5:7]), float(x["lat"]), float(x["lon"])))
    return out


def km_offset(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    """(north-south km, east-west km) of a point from the centre; north and east are positive."""
    return (lat - lat0) * KM_LAT, (lon - lon0) * KM_LAT * math.cos(math.radians(lat0))


def percentile(vals: list[float], q: float) -> float:
    s = sorted(vals)
    i = (len(s) - 1) * q
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def monthly_shifts(pts, months, lat0, lon0) -> dict[int, float]:
    by = defaultdict(list)
    for m, la, lo in pts:
        by[m].append((la, lo))
    out = {}
    for m in months:
        ns, ew = km_offset(median(p[0] for p in by[m]), median(p[1] for p in by[m]), lat0, lon0)
        out[m] = math.hypot(ns, ew)
    return out


def main() -> None:
    rng = random.Random(SEED)
    data, res, rows, total_all = {}, {}, [], 0
    for k, label in SOURCES.items():
        src = common.load_source(k)
        data[k] = src
        pts = points(k)
        total_all += len(pts)
        lat0, lon0 = median(p[1] for p in pts), median(p[2] for p in pts)
        cnt = defaultdict(int)
        for m, _, _ in pts:
            cnt[m] += 1
        months = [m for m in common.MONTHS if cnt[m] >= MIN_MONTH]
        assert len(months) >= 4, k
        sel = [p for p in pts if p[0] in months]
        observed = monthly_shifts(sel, months, lat0, lon0)
        obs_max = max(observed.values())
        labels = [p[0] for p in sel]
        chance = []
        for _ in range(SHUFFLES):
            rng.shuffle(labels)
            shuffled = [(l, p[1], p[2]) for l, p in zip(labels, sel)]
            chance.append(max(monthly_shifts(shuffled, months, lat0, lon0).values()))
        p95 = percentile(chance, 0.95)
        p50 = percentile(chance, 0.5)
        beyond = round(sum(1 for c in chance if c >= obs_max) / SHUFFLES, 3)
        span_ns = (percentile([p[1] for p in pts], 0.95) - percentile([p[1] for p in pts], 0.05)) * KM_LAT
        span_ew = (percentile([p[2] for p in pts], 0.95) - percentile([p[2] for p in pts], 0.05)) * KM_LAT * math.cos(math.radians(lat0))
        north_share = {}
        for m in months:
            sub = [p for p in pts if p[0] == m]
            north_share[m] = common.pct(sum(1 for p in sub if p[1] > lat0), len(sub), 1)
        by = defaultdict(list)
        for m, la, lo in pts:
            by[m].append((la, lo))
        detail = []
        for m in months:
            la, lo = median(p[0] for p in by[m]), median(p[1] for p in by[m])
            ns, ew = km_offset(la, lo, lat0, lon0)
            detail.append((m, cnt[m], la, ns, ew, observed[m]))
            rows.append([label, f"{m}月", f"{cnt[m]:,}", f"{la:.3f}", f"{ns:+.1f}", f"{ew:+.1f}", f"{observed[m]:.1f}"])
        res[k] = dict(n=len(pts), months=months, obs_max=obs_max, p50=p50, p95=p95, beyond=beyond, span_ns=span_ns, span_ew=span_ew,
                      north_share=north_share, detail=detail, lat0=lat0, lon0=lon0, skipped=[m for m in common.MONTHS if 0 < cnt[m] < MIN_MONTH],
                      top_month=max(observed, key=observed.get))

    as_of = max(s["as_of"] for s in data.values())
    end = min(date.fromisoformat(s["as_of"]) for s in data.values())
    beyond_k = [k for k in SOURCES if res[k]["obs_max"] > res[k]["p95"]]
    within_k = [k for k in SOURCES if k not in beyond_k]
    maxk = max(SOURCES, key=lambda k: res[k]["obs_max"])
    minratio = min(res[k]["obs_max"] / res[k]["span_ns"] * 100 for k in SOURCES)
    maxratio = max(res[k]["obs_max"] / res[k]["span_ns"] * 100 for k in SOURCES)

    test_rows = [[SOURCES[k], f"{res[k]['n']:,}", f"{res[k]['obs_max']:.1f}km({res[k]['top_month']}月)", f"{res[k]['p50']:.1f}km", f"{res[k]['p95']:.1f}km",
                  ("偶然のばらつきを超えた" if k in beyond_k else "偶然のばらつきの範囲"), f"南北{res[k]['span_ns']:.0f}km・東西{res[k]['span_ew']:.0f}km"] for k in SOURCES]
    north_rows = []
    for k in SOURCES:
        ns = res[k]["north_share"]
        north_rows.append([SOURCES[k]] + [f"{ns[m]:.1f}%" if m in ns else "(件数が少なく比べない)" for m in (4, 5, 6, 7, 8, 9, 10)])

    hi_n = max(((k, m, v) for k in SOURCES for m, v in res[k]["north_share"].items()), key=lambda t: t[2])
    lo_n = min(((k, m, v) for k in SOURCES for m, v in res[k]["north_share"].items()), key=lambda t: t[2])
    extra = [f"北側の記録の割合がいちばん大きかったのは{SOURCES[hi_n[0]]}の{hi_n[1]}月の{hi_n[2]:.1f}%、いちばん小さかったのは{SOURCES[lo_n[0]]}の{lo_n[1]}月の{lo_n[2]:.1f}%です。"
             "年間の中央値を境にした割合は、中心の位置が小さく動いた月でも、50%から離れることがあります。"]
    for k in beyond_k:
        top = [d for d in res[k]["detail"] if d[0] == res[k]["top_month"]][0]
        ns, ew = top[3], top[4]
        extra.append(f"偶然のばらつきを超えた{SOURCES[k]}では、ずれが最大の{top[0]}月の中心が、年間の中心から{'北' if ns >= 0 else '南'}へ{abs(ns):.1f}km、{'東' if ew >= 0 else '西'}へ{abs(ew):.1f}kmの位置でした。"
                     f"この月の記録は{top[1]}件です。ほかの月との差は、偶然だけでは出にくい大きさですが、理由はこの記録だけでは分かりません。")
    chart_months = [4, 5, 6, 7, 8, 9, 10]
    # a line chart needs a value for every x label; drop the months nobody can compare
    common_months = [m for m in chart_months if all(m in res[k]["north_share"] for k in SOURCES)]
    chart = {"kind": "lines", "x_labels": [f"{m}月" for m in common_months],
             "series": [{"label": SOURCES[k], "values": [res[k]["north_share"][m] for m in common_months]} for k in SOURCES],
             "title": "年間の中央より北で記録された割合(%)",
             "desc": f"秋田・新潟・山口・山梨の令和8年度の記録のうち、その県の年間の北緯の中央値より北の地点で記録された割合を、{common_months[0]}月から{common_months[-1]}月まで月ごとに並べた折れ線グラフ。"}

    spans = "、".join(f"{SOURCES[k]}は南北およそ{res[k]['span_ns']:.0f}km" for k in SOURCES)
    doc = {
        "slug": "latitude-by-month", "date": common.today().isoformat(), "data_as_of": as_of,
        "title": "熊(クマ)の出没地点は、月ごとに南北へ動くか。4県の位置を測る",
        "h1": "熊(クマ)の記録の中心は、月が変わると何km動くか。4県の位置を月ごとに測る",
        "description": f"秋田・新潟・山口・山梨の令和8年度の記録{total_all:,}件の位置から、月ごとの中心のずれを測り、月を入れ替えた場合のばらつきと比べました。",
        "lead": (f"熊が出る場所は、月が進むと南北や東西に動くのでしょうか。位置の記録がある4県の{total_all:,}件で、月ごとの記録の中心が年間の中心からどれだけずれるかを測りました。"
                 f"いちばん大きいずれは{SOURCES[maxk]}の{res[maxk]['top_month']}月で{res[maxk]['obs_max']:.1f}kmです。月の名前を入れ替えても出る程度のずれかどうかを、県ごとに確かめています。"),
        "findings": [
            f"月ごとの記録の中心と、年間の中心との距離は、最大で{SOURCES[maxk]}の{res[maxk]['obs_max']:.1f}km({res[maxk]['top_month']}月)でした。ほかの県は{min(res[k]['obs_max'] for k in SOURCES if k != maxk):.1f}kmから{max(res[k]['obs_max'] for k in SOURCES if k != maxk):.1f}kmです。",
            f"月の名前を2,000回入れ替えて同じ測り方をすると、最大のずれの95%点は県ごとに{min(res[k]['p95'] for k in SOURCES):.1f}kmから{max(res[k]['p95'] for k in SOURCES):.1f}kmでした。これを超えたのは{('、'.join(SOURCES[k] for k in beyond_k)) if beyond_k else 'どの県もありません'}、範囲に収まったのは{('、'.join(SOURCES[k] for k in within_k)) if within_k else 'ありません'}です。",
            f"最大のずれを、その県の記録の南北のひろがり(5%点から95%点)と比べると、{minratio:.0f}%から{maxratio:.0f}%です。ひろがりが狭い山口県や山梨県では、同じkmでも割合が大きくなります。",
        ],
        "sections": [
            {"h2": "月ごとの中心と、年間の中心とのずれ",
             "paragraphs": ["表の「南北」は、その月の北緯の中央値が、その県の年間の中央値より何km北(+)か南(−)か、「東西」は東(+)か西(−)かを示します。「ずれ」は2つを合わせた直線距離です。件数が30件に届かない月は、中心が偶然に動きやすいため、表に入れていません。"],
             "table": {"head": ["県", "月", "記録", "北緯(中央値)", "南北(km)", "東西(km)", "ずれ(km)"], "rows": rows,
                       "note": f"令和8年度(2026年4月1日から)の記録のうち、位置のあるものです。記録の最新日は県で違い、いちばん早いのは{end.month}月{end.day}日です。"}},
            {"h2": "月の名前を入れ替えて、偶然のずれを測る",
             "paragraphs": ["月ごとのずれが小さく見えても大きく見えても、それだけでは意味が決まりません。記録の数が少ない月は、実際に何も変わっていなくても、中心が数km動くことがあるからです。そこで、記録はそのままに、月の名前だけを無作為に入れ替えて、同じ測り方で最大のずれを出しました。これを2,000回くり返した分布と、実際の値を比べます。",
                            f"「偶然の中央値」は、2,000回の最大のずれの真ん中の値、「95%点」は、大きいほうから数えて5%の位置の値です。実際の最大のずれが95%点を超えていれば、月の違いが何らかの形で記録に出ている、と読めます。超えていなければ、その県の記録だけでは、月で場所が動いたとは言えません。入れ替えの乱数は固定しているので、同じデータなら同じ結果になります。"],
             "table": {"head": ["県", "記録", "実際の最大のずれ", "偶然の中央値", "95%点", "比べた結果", "記録のひろがり(5〜95%点)"], "rows": test_rows,
                       "note": "「ずれ」は月の中心と年間の中心の距離です。比べた月は、記録が30件以上あった月です。"}},
            {"h2": "年間の中央より北の記録が占める割合",
             "paragraphs": ["中心のずれとは別の見方もあります。その県の年間の北緯の中央値より北にある記録が、各月の何%かを数えました。月による動きがなければ、どの月も50%の近くに並びます。"] + extra,
             "table": {"head": ["県", "4月", "5月", "6月", "7月", "8月", "9月", "10月"], "rows": north_rows,
                       "note": "割合は、その月の位置のある記録のうち、年間の北緯の中央値より北にあるものの割合です。30件に届かない月は出していません。"}},
            {"h2": "割合の推移",
             "paragraphs": ["表の割合を、4県に共通して比べられる月だけ線で結びました。"],
             "chart": chart},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録のうち、緯度と経度のある{total_all:,}件です。目撃のほか、痕跡や人身被害の記録も、位置があれば含めています。記録の最新日は県で違い、いちばん早いのは{end.month}月{end.day}日で、それぞれの県の最新の記録まで数えています。",
            f"記録の中心は、緯度と経度それぞれの中央値です。距離は、緯度1度を{KM_LAT}kmとし、東西は緯度に応じて縮めて出した概算です。月の件数が{MIN_MONTH}件に届かない月は、比べていません(" +
            "、".join(f"{SOURCES[k]}の{'・'.join(str(m) + '月' for m in res[k]['skipped'])}" for k in SOURCES if res[k]['skipped']) + ")。",
            f"月の入れ替えは、比べる月の記録をひとまとめにして月の名前を無作為に並べ替え、毎回、月ごとの中心のずれの最大を求める方法です。回数は{SHUFFLES:,}回、乱数の種は{SEED}で固定しました。計算に使ったスクリプトは公開しています。",
            "南北・東西の「ひろがり」は、位置のある記録すべての5%点から95%点までの幅です。山口県と山梨県は、位置のない記録(それぞれ数件)を除いています。",
        ],
        "caveats": [
            "記録の位置は、通報や公表のときに自治体が付けた地点です。市町村の代表点や、目撃地の近くの住所の位置が使われている場合があり、実際の熊のいた場所とは数百m以上ずれることがあります。",
            "記録は、人が見たり通報したりした分だけです。人の出入りが多い場所や月ほど記録が増えるため、記録の中心の動きは、熊の動きそのものではありません。",
            "標高は測っていません。南北・東西に動かなくても、山と里の間を上り下りしている可能性は、この分析では見えません。",
            "月による動きが小さいと言えるのは、令和8年度のこの4県の記録についてだけです。年が違えば、結果も変わる可能性があります。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/latitude_by_month.py",
        "related": [{"label": "県内の出没の集まり方(上位3市町の割合)", "href": "/research/concentration/"},
                    {"label": "同じ地区でくり返す出没", "href": "/research/place-repeat/"},
                    {"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"},
                    {"label": "今年のピークはいつか(週ごとの件数)", "href": "/research/weekly-peak/"}],
    }
    common.write_note(doc)
    for k, r in res.items():
        print(k, {a: (round(b, 2) if isinstance(b, float) else b) for a, b in r.items() if a not in ("detail", "north_share")}, r["north_share"])
    print(end, as_of, total_all)


if __name__ == "__main__":
    main()
