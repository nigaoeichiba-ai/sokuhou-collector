"""Research note: when bear reports peak in a week, is it because more municipalities report, or because the same ones report more?
Per week: reports, municipalities with at least one report, and the number of municipalities expected if the week's reports fell on municipalities
in proportion to the season's shares (300 random draws, fixed seed).  Six sources with 200+ records from 1 April to 30 September 2026.

python sites/kuma/research/scripts/spread_vs_volume.py
"""
from __future__ import annotations

import random
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
MAIN = ("akita", "miyagi", "niigata")           # 600+ records: read in the text; the other three are shown in the table only
END = date(2026, 9, 30)
N_WEEKS = ((END - common.FY_START).days + 1) // 7
DRAWS = 300


def md(d: date) -> str:
    return f"{d.month}月{d.day}日"


def week_label(i: int) -> str:
    s = common.FY_START + timedelta(days=7 * i)
    return f"{md(s)}〜{md(s + timedelta(days=6))}"


def median(v: list[float]) -> float:
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def analyse(key: str) -> dict:
    s = common.load_source(key)
    wk: dict[int, list[str]] = defaultdict(list)
    season = Counter()
    for r in s["rows"]:
        d = r[0].date() if isinstance(r[0], datetime) else r[0]
        i = (d - common.FY_START).days // 7
        if d > END or i >= N_WEEKS:
            continue
        wk[i].append(r[2])
        season[r[2]] += 1
    cities, w = list(season), [season[c] for c in season]
    rng = random.Random(20261025)
    n = [len(wk[i]) for i in range(N_WEEKS)]
    act = [len(set(wk[i])) for i in range(N_WEEKS)]
    exp = [sum(len(set(rng.choices(cities, w, k=n[i]))) for _ in range(DRAWS)) / DRAWS if n[i] else 0.0 for i in range(N_WEEKS)]
    order = sorted(range(N_WEEKS), key=lambda i: (-n[i], i))
    third = N_WEEKS // 3
    busy, quiet = order[:third], order[-third:]
    big = [i for i in range(N_WEEKS) if n[i] >= 10]          # weeks with 10+ reports: the observed/expected ratio is read only for these
    ratio = [act[i] / exp[i] for i in big]
    low = min(big, key=lambda i: act[i] / exp[i])
    return dict(label=SOURCES[key], total=sum(n), cities=len(season), n=n, act=act, exp=exp, busy=busy, quiet=quiet, big=big,
                busy_act=median([act[i] for i in busy]), quiet_act=median([act[i] for i in quiet]),
                busy_n=median([n[i] for i in busy]), quiet_n=median([n[i] for i in quiet]),
                peak=order[0], mean_ratio=sum(ratio) / len(ratio) if ratio else 0.0, low=low,
                as_of=s["as_of"], credit=s["credit"])


def main() -> None:
    res = {k: analyse(k) for k in SOURCES}
    for k, r in res.items():
        print(k, r["total"], r["cities"], "busy", r["busy_n"], r["busy_act"], "quiet", r["quiet_n"], r["quiet_act"], "peak", r["peak"], r["n"][r["peak"]], r["act"][r["peak"]],
              "ratio", round(r["mean_ratio"], 2), "low", r["low"], r["act"][r["low"]], round(r["exp"][r["low"]], 1))
        assert r["total"] >= 200, k

    ak, mi, ni = (res[k] for k in MAIN)
    # Akita: the first weeks are the only ones with clearly fewer municipalities; from week 3 on the count of municipalities stays within a narrow band
    ak_early = ak["act"][:3]
    ak_flat = ak["act"][3:17]                              # weeks 4 to 17 (22 April to 29 July)
    ak_n_flat = ak["n"][3:17]
    pts = N_WEEKS
    series = []
    for j, k in enumerate(("akita", "miyagi", "niigata")):
        r = res[k]
        series.append({"label": f"{r['label']}(市町村数÷全体)", "values": [round(a / r["cities"] * 100, 1) for a in r["act"]], "cls": f"c{j + 1}"})
    xl = [md(common.FY_START + timedelta(days=7 * i)) if i % 4 == 0 else "" for i in range(pts)]
    chart = {"kind": "lines", "x_labels": xl, "series": series, "title": "週ごとに報告があった市町村の割合(県内の報告があった市町村の数=100)",
             "desc": "秋田県・宮城県・新潟県の令和8年度、4月から9月までの26週について、その週に1件以上の報告があった市町村の数を、4〜9月に報告のあった市町村の数で割った折れ線グラフ。秋田県は4月下旬から7月まで7割から9割で横ばい。"}

    def pair(r, key):
        return f"{r[key]:g}"

    rows = []
    for k, r in res.items():
        rows.append([r["label"], f"{r['total']:,}", f"{r['cities']}", f"{r['busy_n']:g}件 / {r['busy_act']:g}市町村", f"{r['quiet_n']:g}件 / {r['quiet_act']:g}市町村",
                     f"{r['mean_ratio']:.2f}"])
    peak_rows = []
    for k, r in res.items():
        p = r["peak"]
        peak_rows.append([r["label"], week_label(p), f"{r['n'][p]}件", f"{r['act'][p]}市町村", f"{r['exp'][p]:.1f}市町村"])

    as_of = max(r["as_of"] for r in res.values())
    total_n = sum(r["total"] for r in res.values())
    third = N_WEEKS // 3
    ak_pr, mi_pr, ni_pr = ak["peak"], mi["peak"], ni["peak"]
    mi_gap = mi["exp"][mi_pr] - mi["act"][mi_pr]
    assert 3 <= mi_gap <= 5 and res["toyama"]["act"][res["toyama"]["peak"]] > res["toyama"]["exp"][res["toyama"]["peak"]]

    doc = {
        "slug": "spread-vs-volume", "date": common.today().isoformat(), "data_as_of": as_of,
        "title": "熊(クマ)の目撃が多い週は、報告のある市町村が増えるのか。6県の週別",
        "h1": f"熊(クマ)の目撃が多い週は、市町村が増えるのか、1か所の件数が増えるのか。秋田県は4月下旬から7月まで{min(ak_flat)}〜{max(ak_flat)}市町村で横ばい",
        "description": f"秋田・宮城・新潟・富山・山口・山梨の令和8年度4〜9月{total_n:,}件を週ごとに数え、報告のあった市町村の数と件数を比べました。件数が増える週も、市町村の数はほとんど増えない県がありました。",
        "lead": (f"熊の目撃報告が多い週は、報告のある市町村が増えているのでしょうか。それとも、同じ市町村で件数が増えているのでしょうか。6県の記録{total_n:,}件を、4月1日からの26週に区切って、週ごとの件数と、1件以上の報告があった市町村の数を比べました。"
                 f"秋田県では、件数の多い上位{third}週の市町村数の中央値が{ak['busy_act']:g}、少ない下位{third}週が{ak['quiet_act']:g}です。件数は{ak['busy_n']:g}件と{ak['quiet_n']:g}件で{ak['busy_n'] / ak['quiet_n']:.1f}倍ありますが、市町村の数は{ak['busy_act'] / ak['quiet_act']:.1f}倍にとどまります。"),
        "findings": [
            f"秋田県は、4月22日から7月21日までの{len(ak_flat)}週、1週あたりの件数が{min(ak_n_flat)}〜{max(ak_n_flat)}件と2倍以上動きます。一方、報告のあった市町村は{min(ak_flat)}〜{max(ak_flat)}(県内で報告のある{ak['cities']}市町村中)でほぼ変わりません。多い週は、新しい市町村が加わったのではなく、同じ市町村の件数が増えた週です。",
            f"件数が10件以上の週について、実際の市町村の数が期待値の何倍かを測りました。期待値は、県内の市町村別の割合どおりに件数を割りふったときの数です。平均は秋田県{ak['mean_ratio']:.2f}、宮城県{mi['mean_ratio']:.2f}、新潟県{ni['mean_ratio']:.2f}でした。どれも1より少し小さく、実際は期待値より1割ほど少ない市町村に集まっています。それでも1に近いので、週ごとの市町村の数は、件数と県内の市町村別の割合で、おおむね決まります。",
            f"件数が多い週の市町村の割合を、4〜9月に報告のあった市町村の数に対して出すと、秋田県で{ak['busy_act'] / ak['cities'] * 100:.0f}%前後、宮城県で{mi['busy_act'] / mi['cities'] * 100:.0f}%前後、新潟県で{ni['busy_act'] / ni['cities'] * 100:.0f}%前後です。",
            f"期待値より市町村の数が最も少なかった件数10件以上の週は、秋田県が{week_label(ak['low'])}(実際{ak['act'][ak['low']]}、期待値{ak['exp'][ak['low']]:.1f})です。特定の市町村に集中した週の目安になりますが、理由は記録からは分かりません。",
        ],
        "sections": [
            {"h2": "件数が多い週と少ない週の市町村数",
             "paragraphs": [f"4月1日から7日ずつ26週に区切り、週ごとに記録の件数と、その週に1件以上の記録があった市町村の数を数えました。件数の多い週の上位{third}週と、少ない下位{third}週を取り出し、それぞれの中央値を比べたのが下の表です。",
                            f"秋田県の件数は{ak['busy_n']:g}件と{ak['quiet_n']:g}件で{ak['busy_n'] / ak['quiet_n']:.1f}倍、宮城県は{mi['busy_n']:g}件と{mi['quiet_n']:g}件で{mi['busy_n'] / mi['quiet_n']:.1f}倍です。市町村の数の差は、秋田県{ak['busy_act'] / ak['quiet_act']:.1f}倍、宮城県{mi['busy_act'] / mi['quiet_act']:.1f}倍にとどまります。件数の増減は、市町村の数の増減より、ずっと大きいことになります。"],
             "table": {"head": ["県", "4〜9月の記録", "報告のあった市町村", f"件数が多い上位{third}週(中央値)", f"件数が少ない下位{third}週(中央値)", "実際÷期待値(10件以上の週の平均)"], "rows": rows,
                       "note": "市町村は、記録の「市町村」の欄の名前で数えています。期待値は、4〜9月の市町村別の割合どおりに、その週の件数を市町村へ300回ランダムに割りふったときの、市町村の数の平均です。"}},
            {"h2": "秋田県は4月下旬から、市町村の数が横ばい",
             "paragraphs": [f"秋田県の報告のある{ak['cities']}市町村のうち、1週のうちに記録のあった市町村の数を、折れ線にしました。最初の3週(4月1日〜21日)は{ak_early[0]}、{ak_early[1]}、{ak_early[2]}と少なく、4月22日からの週は{min(ak_flat)}〜{max(ak_flat)}で動きます。件数は同じ期間に{min(ak_n_flat)}件から{max(ak_n_flat)}件まで動いています。",
                            f"宮城県と新潟県は、秋田県ほど横ばいではなく、件数が少ない週は市町村の数も下がっています。それでも、件数が多い週と少ない週の差は、宮城県が{mi['busy_n'] / mi['quiet_n']:.1f}倍に対して市町村の数は{mi['busy_act'] / mi['quiet_act']:.1f}倍、新潟県が{ni['busy_n'] / ni['quiet_n']:.1f}倍に対して{ni['busy_act'] / ni['quiet_act']:.1f}倍で、件数のほうが大きく動きます。"],
             "chart": chart},
            {"h2": "いちばん件数が多い週の中身",
             "paragraphs": [f"県ごとに、件数が最も多い週を取り出し、その週の市町村の数と、期待値を並べました。期待値は、その県の4〜9月の市町村別の割合を変えずに、その週の件数だけを割りふったときの数です。実際の数が期待値に近いほど、その週の報告は、いつもの市町村の割合に近い形で増えたことになります。宮城県は期待値より約{mi_gap:.0f}市町村少なく、富山県は期待値より多い週でした。"],
             "table": {"head": ["県", "件数が最も多い週", "件数", "報告のあった市町村", "市町村の期待値"], "rows": peak_rows,
                       "note": "同じ件数の週があるときは、早い週を取っています。富山県・山口県・山梨県は、1週の件数が小さいため、市町村の数の比較は参考にとどめてください。"}},
            {"h2": "読み方と、この分析でわからないこと",
             "paragraphs": ["「市町村の数が変わらない」ことは、熊が同じ場所にとどまっていることを意味しません。記録は、人が見つけて、届けられた件数です。また、記録の単位は市町村なので、同じ市町村の中で場所が動いたかは見えません。",
                            "お住まいの県で、いまの件数がふだんより多いかを知りたいときは、各県の最新の目撃情報のページで、直近の件数と市町村の並びを確かめてください。件数が増えた週に、お住まいの市町村が入っているかは、あらためて確かめる必要があります。"]},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録のうち、4月1日から9月30日の分です。秋田県{res['akita']['total']:,}件、宮城県{res['miyagi']['total']:,}件、新潟県{res['niigata']['total']:,}件、富山県{res['toyama']['total']:,}件、山口県{res['yamaguchi']['total']:,}件、山梨県{res['yamanashi']['total']:,}件です。秋田県の記録が9月30日で止まっているため、ほかの県もそこで切りました。10月の分は入れていません。目撃も痕跡も区別せず、1件を1と数えています。",
            f"4月1日から7日ずつ区切って{N_WEEKS}週とし、週ごとに、記録の件数と、記録に書かれた市町村の名前の種類の数を数えました。期待値は、4〜9月の市町村別の件数の割合を使い、その週の件数ぶんを市町村に{DRAWS}回割りふって、市町村の数の平均を出したものです(乱数の種は固定)。期待値との比は、週の件数が10件以上の週だけで平均しました。計算に使ったスクリプトは公開しています。",
        ],
        "caveats": [
            "件数が多い週に市町村の数が増えにくいのは、熊の動きだけでなく、人が見つけて届け出る場所、記録の公表の仕方にも左右されます。この分析だけでは、理由は分かりません。",
            "市町村の数は、記録に書かれた名前の種類で数えています。市町村の合併や表記の揺れがあると、数が少し変わることがあります。",
            "令和8年度の4〜9月だけの結果です。10月以降や、ほかの年度には当てはまらないことがあります。記録が少ない県は、1週のぶれが大きくなります。",
        ],
        "credits": [res[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/spread_vs_volume.py",
        "related": [{"label": "今年のピークはいつか(週ごとの件数)", "href": "/research/weekly-peak/"},
                    {"label": "県どうしで週別の件数は同じ週に増減するか", "href": "/research/weekly-comovement/"},
                    {"label": "県内の出没の上位3市町の割合", "href": "/research/concentration/"},
                    {"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "熊に出会わないための対処法", "href": "/guide/"}],
    }
    common.write_note(doc)


if __name__ == "__main__":
    main()
