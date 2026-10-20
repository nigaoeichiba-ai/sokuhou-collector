"""Research note: does a prefecture's sighting count peak in summer (June-August) or autumn (September-November)?  And does that change with the size of the year?

Ministry of the Environment's monthly table, R04-R07 (the four full fiscal years).  A prefecture is shown when every year has 150+ sightings.

python sites/kuma/research/scripts/peak_month_type.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

YEARS = ["R04", "R05", "R06", "R07"]
MIN_YEAR = 150
M = common.MONTHS


def main() -> None:
    env = common.load_env()
    S = env["sightings"]
    rows, info = [], {}
    for p in S["prefectures"]:
        m = p["monthly"]
        if any(v is None for y in YEARS for v in m[y]) or min(sum(m[y]) for y in YEARS) < MIN_YEAR:
            continue
        per = {}
        for y in YEARS:
            v = m[y]
            t = sum(v)
            per[y] = dict(total=t, peak=M[max(range(12), key=lambda i: v[i])], summer=sum(v[2:5]) / t * 100, autumn=sum(v[5:8]) / t * 100)
        info[p["name"]] = per
        rows.append([common.full_name(p["name"])] + [
            f"{per[y]['peak']}月・{'秋' if per[y]['autumn'] > per[y]['summer'] else '夏'}({per[y]['summer']:.0f}/{per[y]['autumn']:.0f})" for y in YEARS])
    full = common.full_name
    # the type of each prefecture-year: autumn when September-November holds a larger share than June-August
    n_pairs = len(info) * len(YEARS)
    autumn_pairs = sum(1 for per in info.values() for y in YEARS if per[y]["autumn"] > per[y]["summer"])
    # the size of the year against the type: for each prefecture, the year with the most sightings against the year with the fewest
    bigger_autumn = [k for k, per in info.items() if per[max(YEARS, key=lambda y: per[y]["total"])]["autumn"] > per[min(YEARS, key=lambda y: per[y]["total"])]["autumn"]]
    big_year = max(YEARS, key=lambda y: S["national"]["total"][y])
    small_year = min(YEARS, key=lambda y: S["national"]["total"][y])
    nat = S["national"]["monthly"]
    nat_autumn = {y: sum(nat[y][5:8]) / sum(nat[y]) * 100 for y in YEARS}
    nat_summer = {y: sum(nat[y][2:5]) / sum(nat[y]) * 100 for y in YEARS}
    flip = [k for k, per in info.items() if len({per[y]["autumn"] > per[y]["summer"] for y in YEARS}) == 2]
    always_autumn = [k for k, per in info.items() if all(per[y]["autumn"] > per[y]["summer"] for y in YEARS)]
    always_summer = [k for k, per in info.items() if all(per[y]["autumn"] <= per[y]["summer"] for y in YEARS)]
    data_as_of = S["updated"]
    pk = lambda y: M[max(range(12), key=lambda i: nat[y][i])]
    series = [{"label": common.fy(y), "values": [round(nat[y][k] / sum(nat[y]) * 100, 1) for k in range(12)], "cls": f"c{i + 1}"} for i, y in enumerate(YEARS)]
    tot = S["national"]["total"]

    doc = {
        "slug": "peak-month-type", "date": common.today().isoformat(), "data_as_of": data_as_of,
        "title": "熊(クマ)の出没のピークは、夏か秋か。環境省の月別から、道府県と年度で数える",
        "h1": "出没のピークは夏か秋か。6〜8月と9〜11月の割合を、道府県と年度で比べる",
        "description": f"環境省の月別の出没件数(令和4〜7年度)で、6〜8月と9〜11月のどちらに件数が集まったかを{len(info)}道府県で数えました。年度の件数が多い年ほど秋に偏る道府県が{len(bigger_autumn)}ありました。",
        "lead": ("熊(クマ)の出没件数は、月によって大きく違います。では、道府県ごとに見ると、年間の件数のうち、6月から8月に集まるのか、9月から11月に集まるのか。"
                 f"環境省の月別の出没件数のうち、令和4年度から令和7年度の4年度分で、1年度に{MIN_YEAR}件以上あった{len(info)}道府県について、2つの時期の割合を数えました。"),
        "findings": [
            f"{len(info)}道府県×4年度={n_pairs}組のうち、9〜11月の割合が6〜8月より大きかったのは{autumn_pairs}組です。4年度とも秋が大きかったのは{'・'.join(full(k) for k in always_autumn) or 'ありません'}、4年度とも夏が大きかったのは{'・'.join(full(k) for k in always_summer) or 'ありません'}でした。",
            f"同じ道府県で、年度によって夏と秋が入れ替わったのは{len(flip)}道府県です。全国の件数が多かった{common.fy(big_year)}({tot[big_year]:,}件)は、秋が{nat_autumn[big_year]:.0f}%・夏が{nat_summer[big_year]:.0f}%、少なかった{common.fy(small_year)}({tot[small_year]:,}件)は、秋が{nat_autumn[small_year]:.0f}%・夏が{nat_summer[small_year]:.0f}%でした。",
            f"道府県ごとに、件数がいちばん多かった年度と少なかった年度を比べると、多かった年度のほうが秋の割合が大きかったのは{len(info)}道府県のうち{len(bigger_autumn)}道府県でした。",
        ],
        "sections": [
            {"h2": "道府県別の、年度ごとのピークの月と、夏・秋の割合",
             "paragraphs": ["表の「月」は、その年度で出没件数がいちばん多かった月です。かっこの中の数字は、年度の件数のうち、6〜8月が占める割合/9〜11月が占める割合(%)です。「夏」「秋」は、その2つのうち大きい方を示します。"],
             "table": {"head": ["道府県"] + [common.fy(y) for y in YEARS], "rows": rows,
                       "note": f"1年度に{MIN_YEAR}件以上ある道府県だけです。4〜5月・12〜3月の件数は、割合の分母には入っていますが、夏・秋のどちらにも入っていません。"}},
            {"h2": "全国の月別の割合(年度の件数を100とする)",
             "paragraphs": [f"全国の年度の件数を100として、月ごとの割合を並べました。全国の件数が最も多かった{common.fy(big_year)}は{pk(big_year)}月に、最も少なかった{common.fy(small_year)}は{pk(small_year)}月に、山があります。"],
             "chart": {"kind": "lines", "x_labels": [f"{m}月" for m in M], "series": series, "title": "全国の月別の出没件数の割合(年度の件数=100)",
                       "desc": "令和4〜7年度の全国の出没件数について、年度の合計を100として、4月から3月までの月ごとの割合を比べた折れ線グラフ。"}},
            {"h2": "年度の大きさと、秋の割合",
             "paragraphs": [f"道府県ごとに、4年度のうち件数がいちばん多かった年度と、いちばん少なかった年度を選び、9〜11月の割合を比べました。多かった年度のほうが大きかったのは、{'・'.join(full(k) for k in bigger_autumn)}です。",
                            "件数の多い年度に秋の割合が大きくなる傾向は、この数字から読み取れます。ただし、秋に件数が多いから年度の合計が大きくなったのか、合計の大きい年度に秋が目立つのかは、この表だけでは区別できません。"]},
        ],
        "method": [
            "環境省「クマの出没情報(速報値)」の月別の表を使いました。対象は、4月から翌年3月まで公表済みの令和4〜7年度です。令和8年度は、秋の月が公表されていないため、含めていません。",
            f"夏は6・7・8月、秋は9・10・11月の合計を、年度の合計で割って%にしました。ピークの月は、その年度で件数がいちばん多い月です(同数の月があれば、早い月)。1年度に{MIN_YEAR}件に届かない年度のある道府県は、割合が数件で動くため、対象にしていません。",
            f"環境省「クマに関する各種情報・取組」のページを{common.jp(common.MOE_CHECKED)}に開き、出没情報の表が掲載されていることを確かめました。表の数字は、{common.jp(data_as_of)}に更新されたものです。",
        ],
        "caveats": [
            "出没件数は、都道府県ごとに数え方が違います。割合は同じ道府県の中での比べ方で、道府県どうしの件数の大小は比べられません。",
            "夏と秋の割合が変わった理由は、この記録からは言えません。山の実りや気温などの要因は、ここでは扱っていません。",
            "4年度分の数字です。令和8年度の秋の件数は、まだ公表されていません。道府県の区分は環境省の表のままで、同じ県の中の地域差(山沿いと平地など)は見えません。",
        ],
        "credits": [common.MOE_CREDIT],
        "script": "sites/kuma/research/scripts/peak_month_type.py",
        "related": [{"label": "何月に多いか(都道府県別)", "href": "/season/"}, {"label": "全国の推移", "href": "/trend/"},
                    {"label": "前年度の同じ期間との比較", "href": "/ranking/change/"}, {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)
    print(autumn_pairs, n_pairs, always_autumn, always_summer, flip, bigger_autumn, big_year, small_year)


if __name__ == "__main__":
    main()
