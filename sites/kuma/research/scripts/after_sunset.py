"""Research note: do bear reports follow the clock or the sun?  Evening and morning reports against the day's sunset and sunrise, by month.
(Akita, Miyagi: months with 100+ timed records; Yamaguchi and Yamanashi only in the pooled table.)

python sites/kuma/research/scripts/after_sunset.py
"""
from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
COMPARED = ("akita", "miyagi")
CENTRE = {"miyagi": (38.27, 140.87), "yamaguchi": (34.19, 131.47), "yamanashi": (35.66, 138.57)}    # prefectural office; Akita uses the point of each record
MIN_MONTH = 100                 # a month with fewer timed records than this is not compared
EVENING = (15 * 60, 21 * 60)    # minutes after midnight
MORNING = (3 * 60, 11 * 60)
BOOT, SEED = 1000, 20261022


def sun_minutes(d: date, lat: float, lon: float) -> tuple[float, float]:
    """(sunrise, sunset) in minutes after midnight, Japan time (NOAA general solar position formulas; a few minutes of error)."""
    n = d.timetuple().tm_yday
    g = 2 * math.pi / 365 * (n - 1)
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
            - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    la = math.radians(lat)
    ha = math.degrees(math.acos(math.cos(math.radians(90.833)) / (math.cos(la) * math.cos(decl)) - math.tan(la) * math.tan(decl)))
    return 720 - 4 * (lon + ha) - eqt + 540, 720 - 4 * (lon - ha) - eqt + 540


def hm(minutes: float) -> str:
    m = int(round(minutes))
    return f"{m // 60}:{m % 60:02d}"


def spearman(x: list[float], y: list[float]) -> float:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for t in range(i, j + 1):
                r[order[t]] = (i + j) / 2 + 1
            i = j + 1
        return r
    rx, ry = ranks(x), ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    return num / math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))


def boot_ci(vals: list[float], rng: random.Random) -> tuple[float, float]:
    meds = sorted(median(rng.choices(vals, k=len(vals))) for _ in range(BOOT))
    return meds[int(BOOT * 0.05)], meds[int(BOOT * 0.95) - 1]


def records(key: str) -> list[tuple[date, int, float, float]]:
    """(day, minute of day, sunrise, sunset) of every timed record of the fiscal year."""
    raw = json.loads((common.DATA / f"{key}_kuma.json").read_text(encoding="utf-8"))
    out = []
    for x in raw["sightings"]:
        o = x["observed_at"]
        if o[:10] < common.FY_START.isoformat() or "T" not in o or o.endswith("T00:00:00+09:00"):
            continue
        t = datetime.fromisoformat(o)
        if key == "miyagi" and t.hour in (0, 12):         # noon entered as 0:xx (see the hour-of-day note)
            continue
        la, lo = (float(x["lat"]), float(x["lon"])) if key == "akita" else CENTRE[key]
        rise, sset = sun_minutes(t.date(), la, lo)
        out.append((t.date(), t.hour * 60 + t.minute, rise, sset))
    return out


def main() -> None:
    rng = random.Random(SEED)
    data = {k: common.load_source(k) for k in SOURCES}
    recs = {k: records(k) for k in SOURCES}
    res: dict[str, dict] = {}
    rows_eve, rows_morn, skipped = [], [], {}
    for k in COMPARED:
        by = defaultdict(list)
        for r in recs[k]:
            by[r[0].month].append(r)
        months = [m for m in common.MONTHS if len(by[m]) >= MIN_MONTH]
        skipped[k] = [m for m in common.MONTHS if 0 < len(by[m]) < MIN_MONTH]
        d = {}
        for m in months:
            eve = [r for r in by[m] if EVENING[0] <= r[1] < EVENING[1]]
            mor = [r for r in by[m] if MORNING[0] <= r[1] < MORNING[1]]
            clock = median(r[1] for r in eve)
            lo, hi = boot_ci([r[1] for r in eve], rng)
            sunset = median(r[3] for r in eve)
            rel = median(r[1] - r[3] for r in eve)
            mclock = median(r[1] for r in mor)
            mrel = median(r[1] - r[2] for r in mor)
            msunrise = median(r[2] for r in mor)
            after = common.pct(sum(1 for r in by[m] if r[1] > r[3]), len(by[m]))
            d[m] = dict(n=len(by[m]), n_eve=len(eve), clock=clock, lo=lo, hi=hi, sunset=sunset, rel=rel, n_mor=len(mor), mclock=mclock, mrel=mrel, sunrise=msunrise, after=after)
            rows_eve.append([SOURCES[k], f"{m}月", f"{len(by[m]):,}", f"{len(eve):,}", hm(clock), f"{hm(lo)}〜{hm(hi)}", hm(sunset), f"{-rel:.0f}分前"])
            rows_morn.append([SOURCES[k], f"{m}月", f"{len(mor):,}", hm(mclock), hm(msunrise), f"{mrel:.0f}分後"])
        clock_range = max(v["clock"] for v in d.values()) - min(v["clock"] for v in d.values())
        sunset_range = max(v["sunset"] for v in d.values()) - min(v["sunset"] for v in d.values())
        rel_range = max(v["rel"] for v in d.values()) - min(v["rel"] for v in d.values())
        mclock_range = max(v["mclock"] for v in d.values()) - min(v["mclock"] for v in d.values())
        sunrise_range = max(v["sunrise"] for v in d.values()) - min(v["sunrise"] for v in d.values())
        mrel_range = max(v["mrel"] for v in d.values()) - min(v["mrel"] for v in d.values())
        res[k] = dict(months=months, d=d, clock_range=clock_range, sunset_range=sunset_range, rel_range=rel_range,
                      mclock_range=mclock_range, sunrise_range=sunrise_range, mrel_range=mrel_range, n=sum(v["n"] for v in d.values()))

    pooled_rows = []
    pooled = {}
    for k, label in SOURCES.items():
        r = recs[k]
        after = common.pct(sum(1 for x in r if x[1] > x[3]), len(r), 1)
        before = common.pct(sum(1 for x in r if x[1] < x[2]), len(r), 1)
        within = common.pct(sum(1 for x in r if x[3] - 60 <= x[1] <= x[3]), len(r), 1)
        pooled[k] = dict(n=len(r), after=after, before=before, within=within)
        pooled_rows.append([label, f"{len(r):,}", f"{within:.1f}%", f"{after:.1f}%", f"{before:.1f}%"])

    a, mi = res["akita"], res["miyagi"]
    # the text says the share after sunset falls as the sunset gets later: the script stops if the months do not show it
    a_pairs = sorted((v["sunset"], v["after"]) for v in a["d"].values())
    assert all(x[1] >= y[1] for x, y in zip(a_pairs, a_pairs[1:])), a_pairs
    rho = {}
    for k in COMPARED:
        pts = [(v["sunset"], v["after"]) for v in res[k]["d"].values()]
        rho[k] = spearman([p[0] for p in pts], [p[1] for p in pts])
    assert rho["akita"] < -0.8 and rho["miyagi"] < 0, rho

    common_months = [m for m in (4, 5, 6, 7, 8) if m in a["months"] and m in mi["months"]]
    chart = {"kind": "lines", "x_labels": [f"{m}月" for m in common_months],
             "series": [{"label": "秋田県", "values": [a["d"][m]["after"] for m in common_months]},
                        {"label": "宮城県", "values": [mi["d"][m]["after"] for m in common_months]}],
             "title": "日没後に報告された記録の割合(%)",
             "desc": f"秋田県と宮城県の令和8年度、{common_months[0]}月から{common_months[-1]}月まで。時刻つきの記録のうち、その日の日没より後に報告された記録の割合を月ごとに並べた折れ線グラフ。"}

    as_of = max(s["as_of"] for s in data.values())
    n_cmp = a["n"] + mi["n"]
    all_n = sum(p["n"] for p in pooled.values())
    a_hi = max(a["d"], key=lambda m: a["d"][m]["after"])
    a_lo = min(a["d"], key=lambda m: a["d"][m]["after"])
    mi_hi, mi_lo = max(mi["d"], key=lambda m: mi["d"][m]["after"]), min(mi["d"], key=lambda m: mi["d"][m]["after"])
    max_after_k = max(SOURCES, key=lambda k: pooled[k]["after"])
    min_after_k = min(SOURCES, key=lambda k: pooled[k]["after"])
    share_rows = []
    for k in COMPARED:
        for m in res[k]["months"]:
            v = res[k]["d"][m]
            share_rows.append([SOURCES[k], f"{m}月", f"{v['n']:,}", hm(median(r[3] for r in recs[k] if r[0].month == m)), f"{v['after']:.0f}%"])
    skip_note = "、".join(f"{SOURCES[k]}の{'・'.join(str(m) + '月' for m in skipped[k])}" for k in COMPARED if skipped[k])
    doc = {
        "slug": "after-sunset", "date": common.today().isoformat(), "data_as_of": as_of,
        "title": "熊(クマ)の目撃報告は日没後にどれだけあるか。秋田・宮城の月別",
        "h1": f"熊(クマ)の目撃報告のうち、日没後は何%か。秋田県は{a_lo}月の{a['d'][a_lo]['after']:.0f}%から{a_hi}月の{a['d'][a_hi]['after']:.0f}%",
        "description": f"秋田・宮城の令和8年度の時刻つき記録{n_cmp:,}件を、その日の日没と比べました。秋田県では、日没が遅い月ほど日没後の報告の割合が小さくなっています。",
        "lead": (f"熊の目撃は暗くなってから報告されることが多いのでしょうか。秋田県と宮城県の時刻つきの記録{n_cmp:,}件を、記録の日の日没と比べました。"
                 f"日没より後に報告された記録は、秋田県で{a['d'][a_lo]['after']:.0f}%({a_lo}月)から{a['d'][a_hi]['after']:.0f}%({a_hi}月)、宮城県で{mi['d'][mi_lo]['after']:.0f}%({mi_lo}月)から{mi['d'][mi_hi]['after']:.0f}%({mi_hi}月)です。秋田県では日没が遅い月ほどこの割合が小さく、宮城県は同じ向きですが弱い傾きでした。"),
        "findings": [
            f"日没より後に報告された記録の割合は、秋田県で月により{a['d'][a_lo]['after']:.0f}〜{a['d'][a_hi]['after']:.0f}%、宮城県で{mi['d'][mi_lo]['after']:.0f}〜{mi['d'][mi_hi]['after']:.0f}%でした。月ごとの日没の時刻と順位を比べると、秋田県は日没が遅い月ほど割合が小さくなります(順位相関{rho['akita']:.2f})。宮城県も同じ向きですが弱く({rho['miyagi']:.2f})、9月は日没が最も早いのに割合は高くありません。",
            f"夕方(15〜21時)に報告された記録の中央の時刻は、秋田県で{hm(min(v['clock'] for v in a['d'].values()))}から{hm(max(v['clock'] for v in a['d'].values()))}、宮城県で{hm(min(v['clock'] for v in mi['d'].values()))}から{hm(max(v['clock'] for v in mi['d'].values()))}です。月による動きは{a['clock_range']:.0f}分と{mi['clock_range']:.0f}分です。同じ月々で日没は{a['sunset_range']:.0f}分と{mi['sunset_range']:.0f}分動くので、報告の時刻が日没に追いついているとは言えません。",
            f"時刻つきの{all_n:,}件(4県)の{round(sum(p['n'] * p['after'] for p in pooled.values()) / all_n, 1)}%が日没後の報告でした。県別では{SOURCES[min_after_k]}の{pooled[min_after_k]['after']:.1f}%から{SOURCES[max_after_k]}の{pooled[max_after_k]['after']:.1f}%まで差があります。",
        ],
        "sections": [
            {"h2": "日没後に報告された記録の割合(月別)",
             "paragraphs": ["時刻のある記録を月ごとに集め、報告の時刻が、その記録の日の日没より後だった割合を出しました。日没は、秋田県は記録ごとの位置、宮城県は県庁の位置で計算しています。表の「日没(中央)」は、その月の記録の日没の時刻の中央値です。",
                            f"月ごとの割合と、月の日没の時刻の順位を比べました。順位相関は、秋田県が{rho['akita']:.2f}、宮城県が{rho['miyagi']:.2f}です。−1に近いほど、日没が遅い月に割合が小さいことを表します。月の数が{len(a['months'])}と{len(mi['months'])}しかないので、強い結論ではなく、向きの目安です。"],
             "table": {"head": ["県", "月", "時刻つき記録", "日没(中央)", "日没後の報告"], "rows": share_rows,
                       "note": f"時刻つき記録が{MIN_MONTH}件に届かない月は比べていません({skip_note})。"}},
            {"h2": "割合の推移",
             "paragraphs": [f"4月から8月の割合を結びました。秋田県は4月の{a['d'][4]['after']:.0f}%から7月の{a['d'][7]['after']:.0f}%まで下がり、8月に{a['d'][8]['after']:.0f}%へ戻ります。8月は日没が7月より{(a['d'][7]['sunset'] - a['d'][8]['sunset']):.0f}分早まる月です。"],
             "chart": chart},
            {"h2": "春と秋の夕方に、気をつけて読むところ",
             "paragraphs": [f"月ごとの日没(中央)は、秋田県で{hm(a['d'][4]['sunset'])}(4月)から{hm(a['d'][7]['sunset'])}(7月)、宮城県で{hm(mi['d'][4]['sunset'])}(4月)から{hm(mi['d'][7]['sunset'])}(7月)まで動きます。宮城県の9月は{hm(mi['d'][9]['sunset'])}で、7月より{mi['d'][7]['sunset'] - mi['d'][9]['sunset']:.0f}分早く暮れます。夕方の報告の中央は、宮城県の9月で{hm(mi['d'][9]['clock'])}、7月で{hm(mi['d'][7]['clock'])}でした。",
                            f"報告が集まる時刻が17〜18時ごろのままで、日没だけが早まる月は、同じ時刻の外出でも、日没後にあたる割合が変わります。宮城県の4月は、報告の中央が{hm(mi['d'][4]['clock'])}で日没の{hm(mi['d'][4]['sunset'])}に近く、日没後の割合も{mi['d'][4]['after']:.0f}%と、表の中で最も高くなっています。",
                            "ただし、この割合は、報告があった記録の中での割合です。日没後に出歩く人は少なく、見つかる件数も少ないはずなので、「日没後の割合が小さい=暗い時間の出没が少ない」とは言えません。自治体の啓発資料では、早朝や夕方に注意が必要とされています。くわしくは[[熊に出会わないための対処法|/guide/]]に書きました。"]},
            {"h2": "夕方の報告の時刻は、日没ほど動かない",
             "paragraphs": [f"15時から21時に報告された記録の中央の時刻を、日没と並べます。「90%の幅」は、記録を無作為に取り直して中央値を出す作業を{BOOT:,}回くり返したときの、中央値の5%点から95%点です。記録が少ない月は、幅が広くなります。",
                            f"秋田県は日没が{a['sunset_range']:.0f}分動く間に、夕方の報告の中央は{a['clock_range']:.0f}分の動きでした。宮城県は日没の{mi['sunset_range']:.0f}分に対して{mi['clock_range']:.0f}分です。報告が日没に合わせて動いているなら、日没の何分前かは月によらず揃うはずですが、秋田県で{a['rel_range']:.0f}分、宮城県で{mi['rel_range']:.0f}分の開きがありました。日没後の割合が夏に小さくなるのは、日没が遅くなるほど、報告の時刻がその後ろに届きにくくなるためと読めます。"],
             "table": {"head": ["県", "月", "夕方の記録", "報告の中央", "90%の幅", "日没(中央)", "日没まで"], "rows": [[r[0], r[1], r[3], r[4], r[5], r[6], r[7]] for r in rows_eve],
                       "note": "夕方の記録は、15時から21時に報告された記録です。「日没まで」は、報告の中央の時刻が日没の何分前かを表します。"}},
            {"h2": "山口県・山梨県を含む、日没前後の報告",
             "paragraphs": ["時刻つきの記録すべてについて、日没前の1時間に報告された割合と、日没後・日の出前に報告された割合を出しました。月は区切らず、令和8年度の全期間です。山口県と山梨県は、時刻つきの記録が少ないため、ここだけに入れています。"],
             "table": {"head": ["県", "時刻つき記録", "日没前の1時間", "日没後", "日の出前"], "rows": pooled_rows,
                       "note": "日没後・日の出前は、報告の時刻がその日の日没より後、日の出より前の記録です。"}},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録のうち、時刻のあるものです。秋田県{pooled['akita']['n']:,}件、宮城県{pooled['miyagi']['n']:,}件、山口県{pooled['yamaguchi']['n']:,}件、山梨県{pooled['yamanashi']['n']:,}件で、記録の最新日は県で違います。宮城県は、0時台と12時台の記録を除きました(12時台を0時台と入力した疑いがあるため。くわしくは[[時間帯のノート|/research/hour-of-day/]])。",
            "日の出・日没は、米国海洋大気庁(NOAA)の太陽位置の式で計算し、太陽の中心が地平線から0.833度下にくる時刻としました。国立天文台の暦と数分ずれることがあります。秋田県は記録ごとの緯度・経度、そのほかの県は県庁の位置を使っています。",
            f"月ごとの比較は、時刻つきの記録が{MIN_MONTH}件以上ある月だけです。夕方は15時から21時の記録の中央値を使いました。順位相関は、月ごとの日没の時刻と、日没後の割合の順位から出したスピアマンの値です。90%の幅は、記録の取り直しを{BOOT:,}回、乱数の種{SEED}で出しています。計算に使ったスクリプトは公開しています。",
        ],
        "caveats": [
            "この記録の時刻が、熊を見た時刻なのか、通報を受けた時刻なのか、公表のために入力した時刻なのかは、県によって違い、記録からは分かりません。報告の時刻が時計に合いやすいのは、通報や入力が人の1日の動きに左右されるためとも考えられますが、この記録だけでは確かめられません。",
            "日没後の報告が少ないことは、暗い時間に熊がいない、という意味ではありません。暗い時間は人の外出が少なく、見つかる機会も報告される機会も少ないためです。熊が日没に合わせて動くかどうかは、この分析では分かりません。",
            "月の数が少ない(秋田県5、宮城県6)ので、相関は目安です。秋田県と宮城県の8月・9月は、記録の追加が済んでいない可能性があり、件数に偏りがあります。",
            "日の出・日没は計算値で、山や建物による日の入りの早まりは入っていません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/after_sunset.py",
        "related": [{"label": "熊の目撃は何時ごろに報告されているか", "href": "/research/hour-of-day/"},
                    {"label": "今年のピークはいつか(週ごとの件数)", "href": "/research/weekly-peak/"},
                    {"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"},
                    {"label": "熊に出会わないための対処法", "href": "/guide/"}],
    }
    common.write_note(doc)
    for k in COMPARED:
        r = res[k]
        print(k, {x: (round(y, 1) if isinstance(y, float) else y) for x, y in r.items() if x != "d"})
        for m, v in r["d"].items():
            print(" ", m, {x: round(y, 1) for x, y in v.items()})
    print(pooled, skipped, as_of)


if __name__ == "__main__":
    main()
