"""Research note: when a municipality has a bear report, how often is there another report from the same municipality the day before, the same day or the day after?
Compared with the same records after shuffling the dates among the reports of the same week (300 shuffles, fixed seed), which keeps each week's volume
and each municipality's share and removes only the "same municipality, close dates" link.  Six sources with 200+ records, 1 April to 30 September 2026.

python sites/kuma/research/scripts/same-town-streak.py
"""
from __future__ import annotations

import random
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
MAIN = ("akita", "miyagi", "niigata")
END = date(2026, 9, 30)
DRAWS = 300
MONTHS = [4, 5, 6, 7, 8, 9]


def load(key: str, merge_sendai: bool = False) -> tuple[list[tuple[date, str]], dict]:
    s = common.load_source(key)
    rows = []
    for r in s["rows"]:
        d = r[0].date() if isinstance(r[0], datetime) else r[0]
        if d <= END:
            c = "仙台市" if merge_sendai and r[2].startswith("仙台市") else r[2]
            rows.append((d, c))
    return rows, s


def linked(rows: list[tuple[date, str]]) -> list[bool]:
    """For each report: is there another report from the same municipality on the same day or the day before or after?"""
    cnt: Counter = Counter((c, d.toordinal()) for d, c in rows)
    out = []
    for d, c in rows:
        o = d.toordinal()
        out.append(cnt[(c, o)] > 1 or cnt[(c, o - 1)] > 0 or cnt[(c, o + 1)] > 0)
    return out


def same_day(rows: list[tuple[date, str]]) -> float:
    cnt = Counter((c, d.toordinal()) for d, c in rows)
    return sum(1 for d, c in rows if cnt[(c, d.toordinal())] > 1) / len(rows)


def shuffled(rows: list[tuple[date, str]], rng: random.Random) -> list[tuple[date, str]]:
    wk: dict[int, list[int]] = defaultdict(list)
    for i, (d, _) in enumerate(rows):
        wk[(d - common.FY_START).days // 7].append(i)
    out: list = [None] * len(rows)
    for idx in wk.values():
        ds = [rows[i][0] for i in idx]
        rng.shuffle(ds)
        for i, d in zip(idx, ds):
            out[i] = (d, rows[i][1])
    return out


def analyse(key: str, merge_sendai: bool = False) -> dict:
    rows, s = load(key, merge_sendai)
    lk = linked(rows)
    actual = sum(lk) / len(rows)
    rng = random.Random(20261026)
    sims = []
    sims_day = []
    for _ in range(DRAWS):
        sh = shuffled(rows, rng)
        sims.append(sum(linked(sh)) / len(sh))
        sims_day.append(same_day(sh))
    sims_sorted = sorted(sims)
    month = {}
    for m in MONTHS:
        idx = [i for i, (d, _) in enumerate(rows) if d.month == m]
        month[m] = (sum(lk[i] for i in idx) / len(idx) if idx else 0.0, len(idx))
    return dict(total=len(rows), cities=len({c for _, c in rows}), actual=actual, sim_mean=sum(sims) / DRAWS, sim_lo=sims_sorted[0], sim_hi=sims_sorted[-1],
                above=sum(1 for x in sims if x >= actual), same_day=same_day(rows), sim_day=sum(sims_day) / DRAWS, month=month,
                as_of=s["as_of"], credit=s["credit"])


def p(x: float, digits: int = 0) -> str:
    return f"{x * 100:.{digits}f}%"


def main() -> None:
    res = {k: analyse(k) for k in SOURCES}
    sendai = analyse("miyagi", merge_sendai=True)
    for k, r in res.items():
        print(k, r["total"], r["cities"], round(r["actual"], 3), round(r["sim_mean"], 3), round(r["sim_lo"], 3), round(r["sim_hi"], 3), "above", r["above"],
              "same_day", round(r["same_day"], 3), round(r["sim_day"], 3))
        assert r["total"] >= 200, k
    print("miyagi merged", round(sendai["actual"], 3), round(sendai["sim_mean"], 3), sendai["above"])
    ak, mi, ni, to, ya, yn = (res[k] for k in SOURCES)
    # the reading in the text: Akita, Niigata and Toyama are inside the range of the shuffles; Miyagi is at the top of it; Yamanashi is above its mean
    assert ak["sim_lo"] <= ak["actual"] <= ak["sim_hi"] and ni["sim_lo"] <= ni["actual"] <= ni["sim_hi"]

    rows = []
    for k, r in res.items():
        rows.append([r["label"] if "label" in r else SOURCES[k], f"{r['total']:,}", f"{r['cities']}", p(r["actual"]), p(r["sim_mean"]),
                     f"{p(r['sim_lo'])}〜{p(r['sim_hi'])}", f"{r['above']}回"])
    month_rows = []
    for m in MONTHS:
        month_rows.append([f"{m}月"] + [f"{p(res[k]['month'][m][0])}({res[k]['month'][m][1]}件)" for k in MAIN])
    series = []
    for j, k in enumerate(MAIN):
        series.append({"label": SOURCES[k], "values": [round(res[k]["month"][m][0] * 100, 1) for m in MONTHS], "cls": f"c{j + 1}"})
    chart = {"kind": "lines", "x_labels": [f"{m}月" for m in MONTHS], "series": series,
             "title": "前後1日に同じ市町村の別の報告がある記録の割合(月別)",
             "desc": "秋田県・宮城県・新潟県の令和8年度、4月から9月までの月ごとに、記録のうち、同じ日か前後1日に同じ市町村から別の報告がある記録の割合を示した折れ線グラフ。"}

    as_of = max(r["as_of"] for r in res.values())
    total_n = sum(r["total"] for r in res.values())
    ak_m = {m: ak["month"][m][0] for m in MONTHS}
    ak_lo_m = min(MONTHS, key=lambda m: ak_m[m])
    ak_hi_m = max(MONTHS, key=lambda m: ak_m[m])

    doc = {
        "slug": "same-town-streak", "date": common.today().isoformat(), "data_as_of": as_of,
        "title": "熊(クマ)の目撃が出た市町村で、翌日も続く割合。6県の前後1日",
        "h1": f"熊(クマ)の報告が出た市町村では、前後1日にも続くのか。秋田県は{p(ak['actual'])}、山梨県は{p(yn['actual'])}",
        "description": f"秋田・宮城・新潟・富山・山口・山梨の令和8年度4〜9月{total_n:,}件で、同じ市町村に前後1日の別の報告がある割合を数えました。県で{p(yn['actual'])}から{p(ak['actual'])}まで開き、日付を週内で入れ替えた偶然の値とほぼ同じでした。",
        "lead": (f"熊の報告が出た市町村では、前の日か次の日にも、同じ市町村から報告が出るのでしょうか。6県の記録{total_n:,}件で、同じ日、または前後1日に、同じ市町村の別の報告がある記録の割合を数えました。"
                 f"秋田県は{p(ak['actual'])}、宮城県は{p(mi['actual'])}、新潟県は{p(ni['actual'])}、山梨県は{p(yn['actual'])}です。"
                 f"ただし、同じ週の中で日付を入れ替えても、秋田県は{p(ak['sim_mean'])}、新潟県は{p(ni['sim_mean'])}と、ほとんど変わりません。続いて報告される割合は、週の件数でほぼ決まります。入れ替えた{DRAWS}回のすべてを上回ったのは、宮城県だけでした。"),
        "findings": [
            f"前後1日に同じ市町村の別の報告がある記録の割合は、秋田県{p(ak['actual'])}、宮城県{p(mi['actual'])}、新潟県{p(ni['actual'])}、富山県{p(to['actual'])}、山口県{p(ya['actual'])}、山梨県{p(yn['actual'])}です。件数の多い県ほど高くなっています。",
            f"同じ週の記録の日付を入れ替える計算を{DRAWS}回くり返すと、秋田県は平均{p(ak['sim_mean'])}({p(ak['sim_lo'])}〜{p(ak['sim_hi'])})、新潟県は平均{p(ni['sim_mean'])}で、実際の値はその範囲に入ります。富山県・山口県・山梨県も同じです。「続けて出た」ように見えても、同じ週の件数が多ければ、偶然でも同じくらい続きます。",
            f"宮城県は実際{p(mi['actual'],1)}で、入れ替えた平均{p(mi['sim_mean'],1)}より高く、{DRAWS}回のうち実際以上になったのは{mi['above']}回でした。差は約{(mi['actual']-mi['sim_mean'])*100:.0f}ポイントです。仙台市の区を1つにまとめて数え直すと、実際{p(sendai['actual'],1)}、入れ替えた平均{p(sendai['sim_mean'],1)}になります。",
            f"同じ日に同じ市町村から2件以上ある記録の割合は、秋田県{p(ak['same_day'])}、宮城県{p(mi['same_day'])}、新潟県{p(ni['same_day'])}です。",
        ],
        "sections": [
            {"h2": "6県の割合と、日付を入れ替えた偶然の値",
             "paragraphs": [f"4月1日から9月30日の記録について、1件ごとに「同じ日、または前の日か次の日に、同じ市町村から別の報告があるか」を調べ、ある記録の割合を出しました。下の表の「実際」です。",
                            f"それだけでは、続いているのか、件数が多いから重なっただけなのかが分かりません。そこで、同じ週の中で記録の日付だけを入れ替え、同じ数え方をする計算を{DRAWS}回行いました。週ごとの件数も、市町村ごとの件数も変わりません。変わるのは、同じ市町村の記録が近い日に並ぶかどうかだけです。",
                            f"結果は、秋田県・新潟県・富山県・山口県・山梨県が、入れ替えた{DRAWS}回の範囲に入りました。宮城県だけは、{DRAWS}回のどれよりも高く出ています。仙台市の区をまとめて数え直しても、同じです。山梨県は、{yn["cities"]}市町村に{yn["total"]}件で1市町村あたりが少なく、割合が低い県です。"],
             "table": {"head": ["県", "4〜9月の記録", "市町村", "実際(前後1日に同じ市町村の別の報告)", "日付を入れ替えた平均", "入れ替えた300回の範囲", "300回のうち実際以上"], "rows": rows,
                       "note": "市町村は、記録の「市町村」の欄の名前で数えています。宮城県は仙台市の区ごとに別の市町村として数えています。"}},
            {"h2": f"月ごとに見ると、秋田県は{ak_hi_m}月が{p(ak_m[ak_hi_m])}、{ak_lo_m}月が{p(ak_m[ak_lo_m])}",
             "paragraphs": [f"月別では、秋田県の件数が多い月ほど割合が高くなります。秋田県は{ak_hi_m}月が{p(ak_m[ak_hi_m])}、{ak_lo_m}月が{p(ak_m[ak_lo_m])}です。件数の少ない月は、同じ市町村に近い日の報告が並びにくく、割合が下がります。",
                            "県ごとに記録の件数が大きく違うため、県どうしの割合は、そのまま比べないでください。"],
             "chart": chart,
             "table": {"head": ["月", "秋田県", "宮城県", "新潟県"], "rows": month_rows, "note": "かっこ内は、その月の記録の件数です。"}},
            {"h2": "読み方と、この分析でわからないこと",
             "paragraphs": ["前後1日に同じ市町村の報告が並んでも、同じ個体が居続けたとは言えません。記録は、人が見つけて届けた件数です。同じ個体が別の場所へ動いた場合も、別の個体が来た場合も、同じように記録されます。",
                            "お住まいの市町村で今日報告が出たとき、明日も出るかを、この数字から予想することはできません。県全体の件数が多い時期は、続けて出やすい、というところまでが、記録から言えることです。お住まいの市町村の直近の報告は、各県の最新の目撃情報のページで確かめてください。"]},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録のうち、4月1日から9月30日の分です。秋田県{ak['total']:,}件、宮城県{mi['total']:,}件、新潟県{ni['total']:,}件、富山県{to['total']:,}件、山口県{ya['total']:,}件、山梨県{yn['total']:,}件です。秋田県の記録が9月30日で止まっているため、ほかの県もそこで切りました。目撃も痕跡も区別せず、1件を1と数えています。時刻は使わず、日付だけを使いました。",
            f"1件ごとに、記録の「市町村」の欄の名前が同じで、日付が同じか前後1日の、別の記録があるかを調べました。比べる計算では、4月1日から7日ずつ週に区切り、週の中で記録の日付をランダムに入れ替えます。入れ替えたあとの記録で同じ割合を出し、これを{DRAWS}回くり返して、平均・最小・最大を求めました(乱数の種は固定)。計算に使ったスクリプトは公開しています。",
        ],
        "caveats": [
            "日付を週の中で入れ替えた値と近いことは、「近い日に続く動きが無い」ことの証明ではありません。週より細かい動き(2〜3日の滞在など)があっても、件数が多い県では見分けられません。",
            "同じ現場への複数の通報が、別々の記録として公表されている場合があります。記録が重複していても、この分析では区別できません。",
            "令和8年度の4〜9月だけの結果です。記録が少ない県は、割合のぶれが大きくなります。",
        ],
        "credits": [res[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/same-town-streak.py",
        "related": [{"label": "件数が多い週は市町村が増えるのか", "href": "/research/spread-vs-volume/"},
                    {"label": "県内の出没の上位3市町の割合", "href": "/research/concentration/"},
                    {"label": "4〜9月の記録のあった日の割合", "href": "/research/record-days/"},
                    {"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "熊に出会わないための対処法", "href": "/guide/"}],
    }
    common.write_note(doc)


if __name__ == "__main__":
    main()
