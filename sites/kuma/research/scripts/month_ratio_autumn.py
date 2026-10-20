"""Research note: how much do sightings fall from October to November?  The Ministry of the Environment's monthly table (R04-R07, the four full fiscal years).

Ratio = November / October.  A prefecture-year counts only when October has MIN_OCT sightings or more (a ratio of two small numbers moves by one or two sightings).

python sites/kuma/research/scripts/month_ratio_autumn.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

YEARS = ["R04", "R05", "R06", "R07"]
MIN_OCT = 100
OCT, NOV, DEC = 6, 7, 8          # positions in the April-to-March list


def main() -> None:
    env = common.load_env()
    S = env["sightings"]
    nat = S["national"]["monthly"]
    nat_ratio = {y: nat[y][NOV] / nat[y][OCT] for y in YEARS}
    nat_dec = {y: nat[y][DEC] / nat[y][NOV] for y in YEARS}
    rows, valid = [], {}
    for p in S["prefectures"]:
        m = p["monthly"]
        if any(v is None for y in YEARS for v in m[y]):
            continue
        cells, got = [], {}
        for y in YEARS:
            o, n = m[y][OCT], m[y][NOV]
            if o >= MIN_OCT:
                got[y] = n / o
                cells.append(f"{n / o * 100:.0f}%({o:,}→{n:,})")
            else:
                cells.append("-")
        if len(got) >= 2:
            valid[p["name"]] = got
            rows.append((p["name"], cells, got))
    rows.sort(key=lambda r: sum(r[2].values()) / len(r[2]))
    pairs = [(k, y, v) for k, g in valid.items() for y, v in g.items()]
    below = sum(1 for _, _, v in pairs if v < 1)
    lo = min(pairs, key=lambda t: t[2])
    hi = max(pairs, key=lambda t: t[2])
    lo_nat, hi_nat = min(nat_ratio.values()), max(nat_ratio.values())
    full = common.full_name
    data_as_of = env["sightings"]["updated"]
    series = []
    for i, y in enumerate(YEARS):
        base = nat[y][OCT]
        series.append({"label": common.fy(y), "values": [round(nat[y][k] / base * 100, 1) for k in range(5, 12)], "cls": f"c{i + 1}"})
    spread = [max(g.values()) - min(g.values()) for g in valid.values()]
    top = sorted(valid, key=lambda k: -(max(valid[k].values()) - min(valid[k].values())))

    doc = {
        "slug": "month-ratio-autumn", "date": common.today().isoformat(), "data_as_of": data_as_of,
        "title": "熊(クマ)の出没は、10月から11月にかけてどれだけ減るか。環境省の月別から、4年度分を数える",
        "h1": "秋の終わりの減り方。熊(クマ)の出没件数は、10月から11月に、何割になるか",
        "description": f"環境省の月別の出没件数(令和4〜7年度)から、11月の件数が10月の何%かを、全国と{len(valid)}道府県で数えました。全国は{lo_nat * 100:.0f}〜{hi_nat * 100:.0f}%で、県と年で大きく違います。",
        "lead": ("出没の件数は、秋に増えて、冬に向けて減ります。では、10月から11月で、どれだけ減るのか。環境省が公表している月別の出没件数のうち、"
                 f"令和4年度から令和7年度までの4年度分で、11月の件数が10月の何%になったかを数えました。全国の数字と、10月の件数が{MIN_OCT}件以上あった道府県の数字を、並べて見ます。"),
        "findings": [
            f"全国の11月は、10月の{lo_nat * 100:.0f}%から{hi_nat * 100:.0f}%の間でした。4年度とも、11月は10月より少なくなりました。12月はさらに減って、11月の{min(nat_dec.values()) * 100:.0f}〜{max(nat_dec.values()) * 100:.0f}%です。",
            f"道府県ごとに見ると、10月が{MIN_OCT}件以上の{len(pairs)}組(道府県と年度の組み合わせ)のうち、11月が10月より少なかったのは{below}組です。いちばん減ったのは{full(lo[0])}の{common.fy(lo[1])}({lo[2] * 100:.0f}%)、いちばん減らなかったのは{full(hi[0])}の{common.fy(hi[1])}({hi[2] * 100:.0f}%)でした。",
            f"同じ県でも、年度で割合が変わります。{len(valid)}道府県のうち、年度による割合の差(最大と最小の差)が50ポイント以上だったのは{sum(1 for s in spread if s >= 0.5)}県です。",
        ],
        "sections": [
            {"h2": "全国の、10月から12月への動き",
             "paragraphs": [f"全国の月別の件数を、10月を100として、9月から3月まで並べました。10月から11月にかけての落ち方は、{lo_nat * 100:.0f}〜{hi_nat * 100:.0f}%の幅に収まっています。"
                            "一方で、10月の件数そのものは、年度で大きく違います(令和4年度は" + f"{nat['R04'][OCT]:,}件、令和7年度は{nat['R07'][OCT]:,}件)。"],
             "chart": {"kind": "lines", "x_labels": [f"{common.MONTHS[k]}月" for k in range(5, 12)], "series": series,
                       "title": "全国の月別の出没件数(10月=100)", "desc": "令和4〜7年度の、全国の月別の出没件数を、10月を100として9月から3月まで比べた折れ線グラフ。"}},
            {"h2": "道府県別の、11月が10月の何%か",
             "paragraphs": [f"10月の件数が{MIN_OCT}件以上あった年度だけを数えました。「→」の前が10月、後が11月の件数です。件数が少ない県と年度は、1〜2件の違いで割合が大きく動くため、「-」にしています。",
                            "表は、平均の割合が低い(減り方が大きい)順です。"],
             "table": {"head": ["道府県"] + [common.fy(y) for y in YEARS],
                       "rows": [[full(n)] + cells for n, cells, _ in rows],
                       "note": f"環境省の表の数字です(速報値で、後から修正されます)。表にない道府県は、10月が{MIN_OCT}件以上の年度が2年度に届かなかった県です。"}},
            {"h2": "年度でどれくらい違うか",
             "paragraphs": [f"同じ県でも、年度で割合は変わります。たとえば{full(top[0])}は、{'、'.join(f'{common.fy(y)}が{v * 100:.0f}%' for y, v in valid[top[0]].items())}でした。年度による差が大きい県は、{'・'.join(full(k) for k, s in sorted(zip(valid, spread), key=lambda t: -t[1])[:3])}です(最大と最小の差が大きい順)。",
                            "ひとつの県の数字を、翌年の11月の目安にすることはできません。10月から11月の減り方は、その年の出没の多さや通報の状況など、この表にない事情でも変わる可能性がありますが、この記録だけでは確かめられません。"]},
        ],
        "method": [
            f"環境省「クマの出没情報(速報値)」の月別の表(都道府県ごとの月別の件数)を使いました。対象は、4月から翌年3月までが公表済みの、令和4年度から令和7年度の4年度です。令和8年度は、10月・11月が公表されていないため、含めていません。",
            f"11月の件数を10月の件数で割り、%にしました(四捨五入)。道府県と年度の組は、10月が{MIN_OCT}件以上のときだけ数えました。全国は、環境省の表の「計」の行です。",
            f"環境省「クマに関する各種情報・取組」のページを{common.jp(common.MOE_CHECKED)}に開き、出没情報の表が掲載されていることを確かめました。表の数字は、{common.jp(data_as_of)}に更新されたものを使っています。",
        ],
        "caveats": [
            "出没件数は、都道府県ごとに数え方が違います(目撃だけか、痕跡も含むか、通報を受けたものか)。件数の大小は県どうしで比べられません。このノートは、同じ県の10月と11月の比を見ているので、数え方の違いは、比の中でほぼ打ち消されます。ただし、数え方が年度の途中で変わっていれば、その影響は残ります。",
            "10月から11月の減り方が、クマの数や行動の変化を表すとは言えません。報告の件数は、人の出入り(山菜・きのこ採りや狩猟、収穫の時期)や通報の受け付けにも左右されます。",
            "4年度分だけの数字です。令和8年度の10月・11月がどうなるかは、まだ分かりません。",
        ],
        "credits": [common.MOE_CREDIT],
        "script": "sites/kuma/research/scripts/month_ratio_autumn.py",
        "related": [{"label": "全国の月別の出没件数(推移)", "href": "/trend/"}, {"label": "何月に多いか(都道府県別)", "href": "/season/"},
                    {"label": "出没件数ランキング", "href": "/ranking/sightings/"}, {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)
    print(nat_ratio, nat_dec, len(pairs), below, lo, hi, [round(s, 2) for s in spread])


if __name__ == "__main__":
    main()
