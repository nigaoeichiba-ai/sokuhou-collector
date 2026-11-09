"""Research note: how many bear records share the same day and the same place text with another record?  Six prefectures; compared with 1,000 reshuffles of the dates inside each town-week.

python sites/kuma/research/scripts/same-place-same-day.py
"""
from __future__ import annotations

import random
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "niigata": "新潟県", "toyama": "富山県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
SHUFFLES = 1000


def norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s).replace(" ", "").replace("　", "")


def day(r):
    return r[0].date() if isinstance(r[0], datetime) else r[0]


def extra(rows: list, dates: list) -> int:
    """Records beyond the first one of each (day, town, place text) group."""
    c = Counter((d, r[2], norm(r[3])) for d, r in zip(dates, rows))
    return sum(v - 1 for v in c.values() if v > 1)


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    rng = random.Random(20261107)
    st = {}
    for k, src in data.items():
        rows = src["rows"]
        ds = [day(r) for r in rows]
        obs = extra(rows, ds)
        cells = defaultdict(list)
        for i, r in enumerate(rows):
            cells[(r[2], (ds[i] - common.FY_START).days // 7)].append(i)
        res = []
        for _ in range(SHUFFLES):
            nd = ds[:]
            for ix in cells.values():
                v = [ds[i] for i in ix]
                rng.shuffle(v)
                for i, d in zip(ix, v):
                    nd[i] = d
            res.append(extra(rows, nd))
        groups = defaultdict(list)
        for r, d in zip(rows, ds):
            groups[(d, r[2], norm(r[3]))].append(r)
        multi = [v for v in groups.values() if len(v) > 1]
        gaps = []
        for v in multi:
            ts = [x[0] for x in v if isinstance(x[0], datetime)]
            if len(ts) == len(v):
                gaps.append((max(ts) - min(ts)).total_seconds() / 60)
        by_month = Counter()
        tot_month = Counter(d.month for d in ds)
        for v in multi:
            by_month[day(v[0]).month] += len(v) - 1
        wk = Counter((d - common.FY_START).days // 7 for d in ds)
        first = {}
        for i, key in enumerate((d, r[2], norm(r[3])) for d, r in zip(ds, rows)):
            first.setdefault(key, i)
        wk2 = Counter((ds[i] - common.FY_START).days // 7 for i in first.values())
        peak = max(wk, key=lambda w: wk[w])
        sign = sum(1 for v in multi if any(not x[1].startswith("目撃") for x in v))
        st[k] = dict(peak_raw=wk[peak], peak_dedup=wk2[peak], peak_week=peak, peak_dedup_max=max(wk2.values()), sign_groups=sign,
                     n=len(rows), obs=obs, groups=len(multi), biggest=max((len(v) for v in multi), default=1),
                     mean=sum(res) / SHUFFLES, lo=min(res), hi=max(res), ge=sum(1 for x in res if x >= obs) / SHUFFLES,
                     gaps=gaps, zero=sum(1 for g in gaps if g == 0), hour=sum(1 for g in gaps if 0 < g <= 60),
                     longer=sum(1 for g in gaps if g > 60), month=by_month, tot_month=tot_month)
    as_of = max(s["as_of"] for s in data.values())
    today = common.today().isoformat()
    names = list(SOURCES)
    pc1 = lambda a, b: f"{a / b * 100:.1f}%"
    tot_n = sum(st[k]["n"] for k in names)
    tot_obs = sum(st[k]["obs"] for k in names)
    over = [SOURCES[k] for k in names if st[k]["ge"] < 0.05]
    over_txt = "・".join(over) if over else "なし"
    ak, mi = st["akita"], st["miyagi"]
    timed = [k for k in names if st[k]["gaps"]]
    rows1 = [[SOURCES[k], f"{st[k]['n']:,}", f"{st[k]['obs']}", pc1(st[k]["obs"], st[k]["n"]), f"{st[k]['biggest']}"] for k in names]
    rows2 = [[SOURCES[k], f"{st[k]['obs']}", f"{st[k]['mean']:.1f}", f"{st[k]['lo']}〜{st[k]['hi']}", f"{st[k]['ge'] * 100:.1f}%"] for k in names]
    rows3 = [[SOURCES[k], f"{len(st[k]['gaps'])}", f"{st[k]['zero']}", f"{st[k]['hour']}", f"{st[k]['longer']}"] for k in timed]
    months = [4, 5, 6, 7, 8, 9]
    rows4 = [[f"{m}月", f"{ak['tot_month'][m]}", f"{ak['month'][m]}", pc1(ak["month"][m], ak["tot_month"][m]),
              f"{mi['tot_month'][m]}", f"{mi['month'][m]}", pc1(mi["month"][m], mi["tot_month"][m])] for m in months]
    rows5 = [[SOURCES[k], f"{st[k]['n']:,}", f"{st[k]['n'] - st[k]['obs']:,}", f"{st[k]['peak_raw']}", f"{st[k]['peak_dedup']}"] for k in names]
    ak_zero, ak_g = ak["zero"], len(ak["gaps"])
    mi_zero, mi_g = mi["zero"], len(mi["gaps"])
    jul = ak["month"][7] / ak["tot_month"][7] * 100
    sep = ak["month"][9] / ak["tot_month"][9] * 100
    lo = min(st[k]["obs"] / st[k]["n"] for k in names) * 100
    hi = max(st[k]["obs"] / st[k]["n"] for k in names) * 100

    doc = {
        "slug": "same-place-same-day", "date": today, "data_as_of": as_of,
        "title": "同じ日に同じ場所で重なった熊の記録は、全体の何割か",
        "h1": "同じ日・同じ場所の熊(クマ)の記録は、全体の何割か",
        "description": f"秋田・宮城・新潟・富山・山口・山梨の令和8年度{tot_n:,}件のうち、同じ日に同じ市町村・同じ場所の表記で重なった記録は{tot_obs}件でした。割合は{lo:.1f}%から{hi:.1f}%。秋田県では時刻まで同じ組が{ak_zero}組ありました。",
        "lead": (f"熊の記録の件数には、同じ場所の同じ出来事が重ねて数えられているものも含まれるのでしょうか。6県の令和8年度{tot_n:,}件で、同じ日・同じ市町村・同じ場所の表記が重なった記録を数えると、2件目以降は{tot_obs}件、全体の{tot_obs / tot_n * 100:.1f}%でした。"
                 f"県別では{lo:.1f}%から{hi:.1f}%です。日付を週の中で入れ替えても重なりは出ますが、実際はそれを上回った県が{len(over)}県({over_txt})ありました。"),
        "findings": [
            f"6県の{tot_n:,}件のうち、同じ日・同じ市町村・同じ場所の表記が別の記録と重なっていた記録(2件目以降)は{tot_obs}件({tot_obs / tot_n * 100:.1f}%)でした。県別では{'、'.join(f'{SOURCES[k]}{pc1(st[k]['obs'], st[k]['n'])}' for k in names)}です。",
            f"同じ市町村・同じ週の中で日付を入れ替えた場合に偶然出る重なりを超えたのは、{over_txt}でした。{SOURCES['akita']}は実際{ak['obs']}件に対し入れ替えの平均{ak['mean']:.0f}件、{SOURCES['miyagi']}は実際{mi['obs']}件に対し{mi['mean']:.0f}件です。",
            f"時刻まで分かる重なりのうち、{SOURCES['akita']}は{ak_g}組中{ak_zero}組が分単位まで同じ時刻、{SOURCES['miyagi']}は{mi_g}組中{mi_zero}組が同じ時刻でした。同じ出来事が複数の通報や入力で残った可能性があります。",
        ],
        "sections": [
            {"h2": "同じ日に同じ場所の表記で重なった記録を数える",
             "paragraphs": [f"令和8年度(2026年4月1日から)の記録のうち、観測日・市町村・場所の表記の3つがすべて同じ記録を、1つの組にまとめました。場所の表記は、全角と半角、スペースの違いをそろえてから比べています。組の中で最初の1件を除いた分を「重なった記録」と呼び、集計しました。",
                            f"6県の{tot_n:,}件のうち、重なった記録は{tot_obs}件です。県別の割合は{lo:.1f}%から{hi:.1f}%で、多くても全体の数%でした。1つの組に最も多く重なったのは{max(st[k]['biggest'] for k in names)}件です。",
                            "これは「同じ熊を重ねて数えている」と決めつける数字ではありません。通報が複数あった、同じ地区の別の場所が同じ町名で記録された、といった場合も含みます。ここで分かるのは、表記が同じになった記録がどれくらいあるかです。"],
             "table": {"head": ["県", "記録の数", "重なった記録(2件目以降)", "全体に対する割合", "1組で最も多く重なった件数"], "rows": rows1,
                       "note": "記録の数は令和8年度の全件です。重なりは、日付・市町村・場所の表記がすべて同じ記録です。"}},
            {"h2": "偶然に出る重なりと比べる",
             "paragraphs": [f"「場所の表記」には、字名のように広い範囲を指すものがあります。同じ町内に何件も記録が出る時期なら、日付が別でも、たまたま同じ日に同じ表記が重なることもあります。そこで、同じ市町村・同じ週の記録どうしで日付だけを入れ替え、重なりの件数を{SHUFFLES:,}回数え直しました。",
                            f"表のとおり、秋田県は実際の{ak['obs']}件に対し、入れ替えた場合は平均{ak['mean']:.0f}件(範囲{ak['lo']}〜{ak['hi']}件)でした。宮城県も実際の{mi['obs']}件に対し平均{mi['mean']:.0f}件です。入れ替えた{SHUFFLES:,}回のうち実際以上になった割合が5%未満だったのは{over_txt}でした。",
                            "偶然の範囲に収まった県は、この数え方では、偶然と区別できる重なりがあるとは言えません。件数の少ない県は、重なりが数件なので、判断の材料にはなりにくい点にも注意してください。"],
             "table": {"head": ["県", "実際の重なり(件)", "入れ替えた場合の平均", "入れ替えた場合の範囲", "入れ替えで実際以上になった割合"], "rows": rows2,
                       "note": f"入れ替えは、同じ市町村・同じ週の記録の日付を並べ替える作業を、各県{SHUFFLES:,}回行いました。"}},
            {"h2": "時刻まで分かる県では、重なった記録の間隔を見る",
             "paragraphs": [f"秋田・宮城・山口・山梨は、時刻のある記録があります。重なった組のうち、組の記録すべてに時刻がある組について、最も早い記録と最も遅い記録の間隔を、分単位で集計しました。",
                            f"秋田県は{ak_g}組のうち{ak_zero}組が、分まで同じ時刻でした。1時間以内(同時刻を除く)は{ak['hour']}組、1時間より空いたのは{ak['longer']}組です。宮城県は{mi_g}組のうち{mi_zero}組が同じ時刻、1時間以内が{mi['hour']}組、1時間より空いたのが{mi['longer']}組でした。",
                            "同じ時刻で同じ場所の表記になる記録は、同じ出来事が重ねて入力された場合と、同じ時刻に複数頭を見た場合の、どちらも考えられます。記録からはどちらか分かりません。1時間以上空いた組は、別の出来事か、同じ熊が場所に残っていたのかも分かりません。"],
             "table": {"head": ["県", "時刻の分かる重なり(組)", "同じ時刻", "1時間以内", "1時間より空いた"], "rows": rows3,
                       "note": "新潟県・富山県の記録には時刻がありません。山口県・山梨県は重なった組が少ないため、傾向は読み取れません。"}},
            {"h2": "月ごとに見ると、秋田県は7月に重なりが多い",
             "paragraphs": [f"重なりが多かった秋田県と宮城県を、月別に分けました。秋田県は4月から9月まで毎月重なりがあり、割合が最も高かったのは7月の{jul:.1f}%、最も低かったのは9月の{sep:.1f}%です。",
                            f"宮城県は{mi['month'][6]}件の重なりがあった6月が最も多く、7月以降は少なくなっています。月によって割合が変わる理由は、このデータからは分かりません。記録の多い時期に、通報や入力の集まり方が変わった可能性はありますが、確かめられていません。"],
             "table": {"head": ["月", "秋田県の記録", "重なり", "割合", "宮城県の記録", "重なり", "割合"], "rows": rows4,
                       "note": "4〜9月のみです。10月以降は、秋田県の記録が9月末までのため、そろえて載せていません。"}},
            {"h2": "重なりを1件にまとめると、数字はどれくらい変わるか",
             "paragraphs": [f"重なった記録を1件にまとめて数え直すと、6県の合計は{tot_n:,}件から{tot_n - tot_obs:,}件になります。減るのは{tot_obs / tot_n * 100:.1f}%です。",
                            f"週別の件数への影響も小さいです。最も件数の多い週にすると、秋田県は{ak['peak_raw']}件が{ak['peak_dedup']}件、宮城県は{mi['peak_raw']}件が{mi['peak_dedup']}件になります。どちらも、まとめる前に件数が最も多かった週です。",
                            f"重なった組のうち、痕跡や人身被害を含む組は6県で{sum(st[k]['sign_groups'] for k in names)}組だけです。重なりの多くは、目撃どうしの記録でした。足跡や糞、食害のように、同じ場所に残るものを別の日に報告した記録は、日付が違うため、ここには入っていません。"],
             "table": {"head": ["県", "記録の数", "重なりを1件にまとめた数", "件数の最も多い週(そのまま)", "同じ週(まとめた後)"], "rows": rows5,
                       "note": "週は4月1日から7日ごとです。件数の最も多い週は、そのままの数え方で決めています。"}},
            {"h2": "この数え方から、何が言えて何が言えないか",
             "paragraphs": ["言えるのは、6県とも、同じ日・同じ場所の表記が重なった記録は全体の数%にとどまることです。件数の最も多い週で比べても、まとめて減るのは秋田県・宮城県とも数%です。",
                            "言えないのは、重なった記録がすべて同じ熊の同じ出来事かどうかです。通報の経路や、場所の書き方は県によって違います。また、場所の表記が違っても同じ出来事を指す記録は、このノートでは重なりに入れていません。実際の重複は、ここで数えた数より多い可能性があります。",
                            "件数を見るときは、1件が1頭を意味するわけではないことを覚えておいてください。"]},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録です。秋田・宮城・新潟・富山・山口・山梨の6県で、記録の最新日は秋田県が{data['akita']['as_of']}、宮城県が{data['miyagi']['as_of']}などです。計算した日は{today}、使った記録の最新日は{as_of}です。",
            "「重なった記録」は、観測日・市町村・場所の表記(全角半角・空白をそろえたもの)がすべて同じ記録のうち、各組の2件目以降です。場所の表記は、県が記録に付けた文字列そのままで、住所の細かさは県によって違います。",
            f"偶然の目安は次のとおりです。同じ市町村・同じ週(4月1日から7日ごと)の記録で日付を並べ替え、重なりを数え直しました。各県{SHUFFLES:,}回で、乱数の種は固定しています。「5%未満」は検定の結論ではなく目安です。",
            "時刻の間隔は、組に属する記録すべてに時刻がある場合だけ集計しました。時刻が0時0分のみの日付だけの記録は、時刻なしとして扱っています。",
            "計算のスクリプトは公開しています。数字はすべてスクリプトが出しています。個別の場所の表記は、このノートには載せていません。",
        ],
        "caveats": [
            "これは報告された記録の件数です。熊の実際の数や行動を直接示すものではありません。",
            "場所の表記が同じでも、別の出来事のことがあります。表記が違っても、同じ出来事のことがあります。",
            "県ごとに記録の集め方・場所の書き方が違うため、県どうしの割合の大小は、そのまま比べられません。",
            "1年度分(令和8年度)だけです。ほかの年に同じ形になるかは、この記録だけでは言えません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/same-place-same-day.py",
        "related": [{"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"},
                    {"label": "新潟県の最新の目撃情報", "href": "/live/niigata/"}, {"label": "週ごとのまとめ", "href": "/digest/"},
                    {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)


main()
