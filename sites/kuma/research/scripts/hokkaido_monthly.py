"""Research note: which month do bear reports peak in Hokkaido's municipalities, and is October really rising?  Monthly counts of data/higumap_kuma.json (R08).

Pools the 27 municipalities by month, turns October (a part month) into a per-day rate, lists the 12 municipalities with 30+ records,
and shows how much of October comes from the two municipalities that peak in October.

python sites/kuma/research/scripts/hokkaido_monthly.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

MIN_RECORDS = 30
MONTHS = [4, 5, 6, 7, 8, 9, 10]
DAYS = {4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30}


def main() -> None:
    raw = json.loads((common.DATA / "higumap_kuma.json").read_text(encoding="utf-8"))
    as_of = date.fromisoformat(raw["as_of"])
    assert as_of.month == 10
    DAYS[10] = as_of.day                                   # October is counted up to the latest day only
    cities = {k: {m: v["monthly"]["R08"].get(str(m), 0) for m in MONTHS} | {"latest": v["latest"]} for k, v in raw["municipalities"].items()}
    total = {m: sum(c[m] for c in cities.values()) for m in MONTHS}
    n_all = sum(total.values())
    assert n_all == raw["total_fy"]
    rate = {m: total[m] / DAYS[m] for m in MONTHS}
    peak = max(MONTHS, key=lambda m: rate[m])
    big = {k: c for k, c in cities.items() if sum(c[m] for m in MONTHS) >= MIN_RECORDS}
    peak_of = {k: max(MONTHS, key=lambda m: c[m] / DAYS[m]) for k, c in big.items()}
    oct_peak = [k for k, p in peak_of.items() if p == 10]
    jun_peak = [k for k, p in peak_of.items() if p == 6]
    top2 = sorted(cities, key=lambda k: -cities[k][10])[:2]
    assert set(top2) == set(oct_peak), (top2, oct_peak)
    rest = {m: total[m] - sum(cities[k][m] for k in top2) for m in MONTHS}
    rest_rate = {m: rest[m] / DAYS[m] for m in MONTHS}
    oct_top2 = sum(cities[k][10] for k in top2)
    oct_gt_sep = [k for k, c in cities.items() if c[10] / DAYS[10] > c[9] / DAYS[9]]
    active = {m: sum(1 for c in cities.values() if c[m] > 0) for m in MONTHS}

    print(total, {m: round(r, 2) for m, r in rate.items()}, peak, peak_of, top2, oct_top2, rest, {m: round(r, 2) for m, r in rest_rate.items()}, len(oct_gt_sep), active)
    assert peak == 6 and rate[10] > rate[9] and rest_rate[10] < rest_rate[9]

    def mo(m: int) -> str:
        return f"{m}月"

    def pk(m: int) -> str:
        return mo(m)

    month_rows = [[mo(m) + (f"(1〜{DAYS[10]}日)" if m == 10 else ""), f"{total[m]:,}", f"{rate[m]:.1f}", f"{rest[m]:,}", f"{rest_rate[m]:.1f}", f"{active[m]}"] for m in MONTHS]
    order = sorted(big, key=lambda k: -sum(big[k][m] for m in MONTHS))
    city_rows = [[k, f"{sum(big[k][m] for m in MONTHS):,}", pk(peak_of[k]), f"{big[k][9]}", f"{big[k][10]}", common.jp(big[k]["latest"]) if hasattr(common, "jp") else big[k]["latest"]] for k in order]
    chart = {"kind": "bars", "labels": [mo(m) for m in MONTHS], "values": [round(rate[m], 1) for m in MONTHS],
             "title": "北海道の27市町村の記録、1日あたりの件数(月別)",
             "desc": f"北海道の27市町村の令和8年度の記録を、月ごとの1日あたりの件数にした棒グラフ。6月が{rate[6]:.1f}件でいちばん多く、9月に{rate[9]:.1f}件まで下がり、10月は{rate[10]:.1f}件に戻る。"}

    n_big = len(big)
    big_sum = sum(sum(c[m] for m in MONTHS) for c in big.values())
    d = common.jp(raw["as_of"]) if hasattr(common, "jp") else raw["as_of"]
    t2 = "・".join(top2)
    n_pop = len(cities)
    doc = {
        "slug": "hokkaido-monthly", "date": common.today().isoformat(), "data_as_of": raw["as_of"],
        "title": "北海道のヒグマの記録は何月が多いか。27市町村の月別と、10月に増える2市町",
        "h1": f"北海道のヒグマの記録は6月がいちばん多い。10月に戻って見えるのは{top2[0]}と{top2[1]}の分",
        "description": f"北海道の{n_pop}市町村の令和8年度の記録{n_all}件を月別に数えました。6月が1日{rate[6]:.1f}件で最多。10月の増加は士別市と愛別町を除くと消えます。",
        "lead": (f"北海道の{n_pop}市町村について、令和8年度の記録{n_all}件(4月1日〜{common.jp(raw['as_of'])})を月ごとに数えました。1日あたりの件数が最も多いのは6月の{rate[6]:.1f}件で、9月に{rate[9]:.1f}件まで下がります。"
                 f"10月は{rate[10]:.1f}件と、9月より増えて見えます。ただし{t2}の2つで10月の{oct_top2}件(全体の{common.pct(oct_top2, total[10])}%)を占め、この2つを除くと10月は1日{rest_rate[10]:.1f}件で、9月の{rest_rate[9]:.1f}件より少なくなります。"),
        "findings": [
            f"{n_pop}市町村を合わせた1日あたりの記録は、6月が{rate[6]:.1f}件で最多、4月が{rate[4]:.1f}件、9月が{rate[9]:.1f}件です。件数の多い{n_big}市町村のうち、最も多い月が6月の市町村は{len(jun_peak)}、10月の市町村は{len(oct_peak)}あります。",
            f"10月(1〜{DAYS[10]}日)は{total[10]}件、1日{rate[10]:.1f}件で、9月の{rate[9]:.1f}件を上回ります。{t2}の2つが{oct_top2}件を占めます。",
            f"この2つを除くと、10月は1日{rest_rate[10]:.1f}件で9月の{rest_rate[9]:.1f}件を下回ります。全体で見た10月の増加は、2市町の動きで説明がつきます。",
        ],
        "sections": [
            {"h2": "月別に見る、北海道の27市町村の件数",
             "paragraphs": [f"集めたのは、複数の公開情報で一致を確認できた{n_pop}市町村の記録です。北海道の全市町村ではなく、令和8年度の記録は合わせて{n_all}件です。目撃のほか、痕跡や捕獲などの報告を含みます。",
                            f"10月は{DAYS[10]}日分しかないので、月の件数どうしを比べず、1日あたりに直しました。6月の{total[6]}件は1日{rate[6]:.1f}件、7月の{total[7]}件は1日{rate[7]:.1f}件です。8月は1日{rate[8]:.1f}件、9月は{rate[9]:.1f}件と下がります。"],
             "chart": chart,
             "table": {"head": ["月", "27市町村の件数", "1日あたり", f"{t2}を除く件数", "除いたときの1日あたり", "記録のあった市町村数"], "rows": month_rows,
                       "note": f"10月は1日から{DAYS[10]}日までの分です。1日あたりは、月の件数をその月の日数(10月は{DAYS[10]}日)で割りました。"}},
            {"h2": f"件数の多い{n_big}市町村は、6月型が多い",
             "paragraphs": [f"記録が{MIN_RECORDS}件以上ある{n_big}市町村({big_sum}件)を取り出し、1日あたりの件数が最も多い月を調べました。6月の市町村が{len(jun_peak)}、10月の市町村が{len(oct_peak)}で、残りは5月・7月・8月に分かれます。",
                            f"10月が最多なのは{t2}です。{top2[0]}は9月の{cities[top2[0]][9]}件から10月は{cities[top2[0]][10]}件に、{top2[1]}は9月の{cities[top2[1]][9]}件から10月は{cities[top2[1]][10]}件になりました。月別の件数だけでは、この2つの市町で何が起きているかは分かりません。"],
             "table": {"head": ["市町村", "4〜10月の記録", "1日あたり最多の月", "9月の件数", "10月の件数", "最新の記録日"], "rows": city_rows,
                       "note": "1日あたりの件数が最も多い月を表に書きました。同じ件数の月が並ぶときは、早い月です。"}},
            {"h2": "10月の増加は、2つの市町を外すと消える",
             "paragraphs": [f"{t2}の10月の{oct_top2}件を外して、残りの{n_pop - 2}市町村で数え直すと、10月は{rest[10]}件、1日{rest_rate[10]:.1f}件でした。9月は{rest[9]}件、1日{rest_rate[9]:.1f}件ですから、10月の方が少なくなります。",
                            f"9月より10月の方が1日あたりの件数が多い市町村は、{n_pop}のうち{len(oct_gt_sep)}あります。秋に記録が増える市町村はほかにもありますが、件数が小さく、全体を押し上げているのは大きく増えた2つです。",
                            "秋の記録は、熊が山から下りてくるときに増えると言われます。ただし、この記録だけでは、熊が増えたのか、人が見かけて届けることが増えたのかは分かりません。"]},
            {"h2": "道内の記録を読むときの使い方",
             "paragraphs": ["自分の町の記録が多い月は、その町の最近の記録で確かめてください。このページの数字は、27市町村の合計の傾向です。それぞれの町の状態は、市町村のページ(最新の目撃情報)と、町が出す注意の呼びかけで確かめてください。",
                            "山に入る日や畑に出る日が、記録の多い月と重なるときは、鈴やラジオなどを使い、単独の行動を避けるのが一般的な心がけです。詳しい対処は、対処法のページにまとめています。"]},
        ],
        "method": [
            f"データは、当サイトが複数の公開情報から月別に集計した{n_pop}市町村の令和8年度(2026年4月1日〜)の件数です。元は https://higumap.info/recent で、最新の記録日は{d}、取得日は{common.jp(raw['fetched_at'][:10])}です。北海道の全市町村ではありません。",
            f"件数は、目撃のほか、痕跡や捕獲などの報告を含み、種類は分けていません。10月は1日から{DAYS[10]}日までの分で、月の日数で割った1日あたりの件数で比べました。{n_big}市町村の表は、令和8年度の記録が{MIN_RECORDS}件以上ある市町村です。計算に使ったスクリプトは公開しています。",
        ],
        "caveats": [
            "市町村によって、記録が入る時期や頻度が違います。最新の記録日が9月までの市町村は、10月の分がまだ入っていないだけかもしれません。10月の数字は、のちに増えることがあります。",
            f"{n_pop}市町村は、データが確認できた市町村だけで、道内の傾向とは言えません。{n_big}市町村の表も、件数の多い町を取り出した結果です。",
            "記録は、熊の数や動きをそのまま表すものではありません。人が見かけたこと、届けたことの記録です。2つの町の10月の増え方の理由は、この記録からは分かりません。",
        ],
        "credits": ["出典:" + raw["credit"]],
        "script": "sites/kuma/research/scripts/hokkaido_monthly.py",
        "related": [{"label": "北海道の最新の目撃情報(市町村別・月別)", "href": "/live/hokkaido/"},
                    {"label": "今季の初出没日(市町村ごと)", "href": "/research/first-sighting/"},
                    {"label": "県ごとのピーク月の型", "href": "/research/peak-month-type/"},
                    {"label": "季節ごとのまとめ", "href": "/season/"}, {"label": "熊に出会わないための対処法", "href": "/guide/"}],
    }
    common.write_note(doc)


if __name__ == "__main__":
    main()
