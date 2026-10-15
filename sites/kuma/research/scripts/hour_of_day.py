"""Research note: at what hour of the day are bear sightings reported?  (Akita, Miyagi, Yamaguchi, Yamanashi; the records that carry a time.)

python sites/kuma/research/scripts/hour_of_day.py
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
BANDS = [("朝(4〜9時)", range(4, 9)), ("日中(9〜15時)", range(9, 15)), ("夕方(15〜19時)", range(15, 19)), ("夜(19〜4時)", list(range(19, 24)) + list(range(0, 4)))]
WEEK = "月火水木金土日"
MONTH_ROWS = (4, 5, 6, 7)             # Akita's August and September are far smaller than July in the stored data (not yet complete): not compared


def band_of(hour: int) -> str:
    return next(name for name, hours in BANDS if hour in hours)


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    rows: dict[str, list[datetime]] = {}
    dropped_miyagi = 0
    for k, s in data.items():
        times = [r[0] for r in s["rows"] if isinstance(r[0], datetime)]
        if k == "miyagi":
            # the 0 o'clock hour is 9 times the neighbouring night hours and the 12 o'clock hour has almost nothing: noon entered as 0:xx is likely. Both hours are left out.
            kept = [t for t in times if t.hour not in (0, 12)]
            dropped_miyagi = len(times) - len(kept)
            times = kept
        rows[k] = times
    total = sum(len(v) for v in rows.values())
    pooled = Counter(t.hour for v in rows.values() for t in v)
    hour_share = [round(pooled[h] / total * 100, 1) for h in range(24)]
    top = sorted(range(24), key=lambda h: -pooled[h])[:3]
    night_pooled = common.pct(sum(pooled[h] for h in list(range(19, 24)) + list(range(0, 4))), total)

    band_tab = []
    band_share: dict[str, dict[str, float]] = {}
    for k, label in SOURCES.items():
        c = Counter(band_of(t.hour) for t in rows[k])
        n = len(rows[k])
        band_share[k] = {b: common.pct(c[b], n) for b, _ in BANDS}
        band_tab.append([label, f"{n:,}"] + [f"{band_share[k][b]:.0f}%" for b, _ in BANDS])
    day_lo = min(band_share[k]["日中(9〜15時)"] for k in SOURCES)
    day_hi = max(band_share[k]["日中(9〜15時)"] for k in SOURCES)

    # Akita: the share of each band by month (April to July)
    am = {m: Counter(band_of(t.hour) for t in rows["akita"] if t.month == m) for m in MONTH_ROWS}
    month_tab = []
    for m in MONTH_ROWS:
        n = sum(am[m].values())
        month_tab.append([f"{m}月", f"{n:,}"] + [f"{common.pct(am[m][b], n):.0f}%" for b, _ in BANDS])
    night_jul, night_apr_jun = common.pct(am[7]["夜(19〜4時)"], sum(am[7].values())), [common.pct(am[m]["夜(19〜4時)"], sum(am[m].values())) for m in (4, 5, 6)]

    # weekdays: the average number of records on a weekday and on a Saturday or Sunday, per day of the window
    week_tab = []
    ratios = {}
    for k, label in SOURCES.items():
        s = data[k]
        end = date.fromisoformat(s["as_of"])
        days = [common.FY_START + timedelta(days=i) for i in range((end - common.FY_START).days + 1)]
        wk, we = [d for d in days if d.weekday() < 5], [d for d in days if d.weekday() >= 5]
        dates = [(r[0].date() if isinstance(r[0], datetime) else r[0]) for r in s["rows"]]        # every record of the fiscal year, with or without a time
        n_wk, n_we = sum(1 for d in dates if d.weekday() < 5 and d <= end), sum(1 for d in dates if d.weekday() >= 5 and d <= end)
        a_wk, a_we = n_wk / len(wk), n_we / len(we)
        ratios[k] = a_we / a_wk
        week_tab.append([label, f"{a_wk:.1f}", f"{a_we:.1f}", f"{ratios[k] * 100:.0f}%"])
    miyagi_less = round((1 - ratios["miyagi"]) * 100)
    others_less = sorted(round((1 - ratios[k]) * 100) for k in SOURCES if k != "miyagi")

    first_hours = "・".join(f"{h}時台" for h in sorted(top))
    doc = {
        "slug": "hour-of-day", "date": common.today().isoformat(), "data_as_of": max(s["as_of"] for s in data.values()),
        "title": f"熊(クマ)の目撃は何時ごろ?4県の{total:,}件を時間帯別・曜日別に数えた",
        "h1": "熊(クマ)の目撃は、何時ごろに報告されているか",
        "description": f"秋田・宮城・山口・山梨の令和8年度の目撃記録{total:,}件を、時間帯と曜日で数えました。夕方と朝に山があり、日中も約{day_lo:.0f}〜{day_hi:.0f}%。数え方と限界つき。",
        "lead": (f"秋田県・宮城県・山口県・山梨県が公表している令和8年度の熊(クマ)の目撃記録のうち、時刻が書かれている{total:,}件を、時間帯別と曜日別に数えました。"
                 "熊は「朝と夕方に出る」とよく言われます。記録の上では、どう見えるでしょうか。"),
        "findings": [
            f"報告の時刻は、{first_hours}の件数が多く、1日のうちの山は朝と夕方にあります(4県の合計。1位は{top[0]}時台で全体の{hour_share[top[0]]:.1f}%)。",
            f"一方で、日中(9〜15時)の報告も、県によって全体の{day_lo:.0f}〜{day_hi:.0f}%あります。「朝と夕方だけ気をつければよい」とは、記録からは言えません。",
            f"曜日では、宮城県の記録だけが、土日の1日あたりの件数が平日より{miyagi_less}%少なくなっています(ほかの3県は、{others_less[0]}〜{others_less[-1]}%の減りにとどまる)。",
        ],
        "sections": [
            {"h2": "1日のうち、何時台の報告が多いか(4県の合計)",
             "paragraphs": [f"4県の{total:,}件を、報告された時刻の「時」で分けて、全体に対する割合を出しました。多い順に、" + "、".join(f"{h}時台({hour_share[h]:.1f}%)" for h in top)
                            + f"です。夜(19時から4時前まで)の報告は、4県の合計で{night_pooled:.0f}%でした。"],
             "chart": {"kind": "bars", "labels": [f"{h}" for h in range(24)], "values": hour_share, "title": "時間帯別の目撃報告の割合(%)",
                       "desc": "4県の令和8年度の目撃記録を、報告された時刻の「時」ごとに数えた割合。横軸は0時から23時。"}},
            {"h2": "県ごとの時間帯の割合",
             "paragraphs": ["同じ数え方を、県ごとに分けると、次のようになります。割合は、その県の時刻つきの件数を100とした値です。"],
             "table": {"head": ["県", "件数"] + [b for b, _ in BANDS], "rows": band_tab,
                       "note": "朝は4時から9時前まで、日中は9時から15時前まで、夕方は15時から19時前まで、夜は19時から翌4時前までです。"}},
            {"h2": "季節で、時間帯は変わるか(秋田県・4〜7月)",
             "paragraphs": [f"件数が最も多い秋田県で、月ごとの時間帯の割合を見ました。夜(19〜4時)の割合は、4〜6月が{min(night_apr_jun):.0f}〜{max(night_apr_jun):.0f}%、7月が{night_jul:.0f}%でした。"
                            "8月と9月は、保存している件数が7月より大きく少ないため(記録の追加が済んでいない可能性)、比べていません。"],
             "table": {"head": ["月", "件数"] + [b for b, _ in BANDS], "rows": month_tab}},
            {"h2": "曜日で、報告の数は変わるか",
             "paragraphs": ["4月1日から、各県の記録の最新日までの、平日(月〜金)と土日の「1日あたりの件数」を出しました。"],
             "table": {"head": ["県", "平日の1日平均(件)", "土日の1日平均(件)", "土日÷平日"], "rows": week_tab,
                       "note": "宮城県の土日が少ないのは、人の動きや、通報・受け付けの違いが関係している可能性がありますが、この記録だけでは確かめられません。"}},
        ],
        "method": [
            "対象は、令和8年度(2026年4月1日から)の記録のうち、時刻(時・分)が書かれているもの。時刻のない記録(日付だけ)は、数えていません。",
            "時間帯は、報告された時刻の「時」で分けました。割合は、四捨五入しています。曜日の表だけは、時刻のない記録も含めた、令和8年度のすべての記録の日付で数えています。",
            "宮城県の記録は、0時台が隣の夜の時間より9倍ほど多く、12時台がほとんどありません。昼の12時台が0時台と入力された可能性があるため、0時台と12時台の"
            f"{dropped_miyagi}件は、数えていません。",
            "4県の合計は、件数の多い秋田県の形が強く出ます。県ごとの表で、県ごとの違いを見てください。",
        ],
        "caveats": [
            "これは「報告された時刻」です。熊が実際に動いた時刻ではありません。人が外にいる時間帯(通勤・通学・農作業・散歩)に、目撃が多くなる偏りがあるかもしれません。",
            "夜は、見える人が少ないため、件数が少なく見えます。夜に熊がいない、という意味ではありません。",
            "県ごとに、記録の取り方(誰が・どこまで集めるか)が違います。県どうしの件数の大小は、比べられません。比べているのは、各県の中での割合です。",
            "原因を言うものではありません。熊に出会いたくない場所・時間を選ぶための、目安のひとつとして使ってください。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/hour_of_day.py",
        "related": [{"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"},
                    {"label": "山口県の最新の目撃情報", "href": "/live/yamaguchi/"}, {"label": "山梨県の最新の目撃情報", "href": "/live/yamanashi/"},
                    {"label": "週ごとのまとめ", "href": "/digest/"}, {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)
    print(f"total {total}, top hours {top}, day share {day_lo}-{day_hi}, miyagi weekend ratio {ratios['miyagi']:.2f}, dropped miyagi {dropped_miyagi}")
    print({k: round(v, 2) for k, v in ratios.items()})


if __name__ == "__main__":
    main()
