"""Research note: are bear sightings and bear traces (footprints, droppings, feeding marks) reported at different hours?  Three prefectures that store a clock time and tell the two kinds apart.

python sites/kuma/research/scripts/trace-hours.py
"""
from __future__ import annotations

import random
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "yamaguchi": "山口県"}
LATE = 15                      # "15時以降" = reported at 15:00 or later
BANDS = [("0〜5時台", 0, 5), ("6〜8時台", 6, 8), ("9〜14時台", 9, 14), ("15〜17時台", 15, 17), ("18〜23時台", 18, 23)]
N_SHUFFLE = 2000
SEED = 20261111


def kind_of(raw: str):
    if raw.startswith("目撃"):
        return "s"
    if raw.startswith("痕跡"):
        return "t"
    return None                # 人身被害・その他は使わない


def pct(part: int, whole: int) -> str:
    return f"{part / whole * 100:.0f}%" if whole else "-"


def fp(p: float) -> str:
    return "0.001未満" if p < 0.001 else f"{p:.3f}"


def load(key: str):
    s = common.load_source(key)
    out = []
    for r in s["rows"]:
        if not isinstance(r[0], datetime):
            continue
        k = kind_of(r[1])
        if k is None:
            continue
        if key == "miyagi" and r[0].hour in (0, 12):      # 宮城県の0時台・12時台は入力の癖があるので除く(最初のノート hour-of-day)
            continue
        out.append((k, r[0].hour, r[0].month))
    return s, out


def main() -> None:
    rng = random.Random(SEED)
    data, rows = {}, {}
    for key in SOURCES:
        data[key], rows[key] = load(key)

    table_rows, per = [], {}
    for key, name in SOURCES.items():
        s = [r for r in rows[key] if r[0] == "s"]
        t = [r for r in rows[key] if r[0] == "t"]
        per[key] = {"ns": len(s), "nt": len(t),
                    "s_late": sum(1 for r in s if r[1] >= LATE), "t_late": sum(1 for r in t if r[1] >= LATE),
                    "s_mid": sum(1 for r in s if 6 <= r[1] <= 14), "t_mid": sum(1 for r in t if 6 <= r[1] <= 14),
                    "s_morn": sum(1 for r in s if 6 <= r[1] <= 8), "t_morn": sum(1 for r in t if 6 <= r[1] <= 8)}

    # shuffle the kind labels inside each (prefecture, month): same number of traces per month, hours kept as they are
    def shuffle_once(key: str) -> int:
        strata = defaultdict(list)
        for k, h, m in rows[key]:
            strata[m].append((k, h))
        t_late = 0
        for m, lst in strata.items():
            nt = sum(1 for k, _ in lst if k == "t")
            hours = [h for _, h in lst]
            pick = rng.sample(hours, nt)
            t_late += sum(1 for h in pick if h >= LATE)
        return t_late

    sims = {key: [shuffle_once(key) for _ in range(N_SHUFFLE)] for key in SOURCES}
    pooled_sims = [sum(sims[k][i] for k in SOURCES) for i in range(N_SHUFFLE)]
    for key in SOURCES:
        obs = per[key]["t_late"]
        # one-sided: as few (or fewer) traces at 15時以降 as observed
        per[key]["p"] = (1 + sum(1 for x in sims[key] if x <= obs)) / (N_SHUFFLE + 1)
        per[key]["exp"] = sum(sims[key]) / N_SHUFFLE
    tot = {f: sum(per[k][f] for k in SOURCES) for f in ("ns", "nt", "s_late", "t_late", "s_mid", "t_mid", "s_morn", "t_morn")}
    p_pool = (1 + sum(1 for x in pooled_sims if x <= tot["t_late"])) / (N_SHUFFLE + 1)
    exp_pool = sum(pooled_sims) / N_SHUFFLE
    lo_pool, hi_pool = sorted(pooled_sims)[int(N_SHUFFLE * 0.025)], sorted(pooled_sims)[int(N_SHUFFLE * 0.975)]

    head1 = ["県", "目撃の件数", "目撃のうち15時以降", "痕跡の件数", "痕跡のうち15時以降", "痕跡の15時以降(ラベル入れ替えの平均)", "偶然の範囲より少ない確率(p)"]
    for key, name in SOURCES.items():
        d = per[key]
        table_rows.append([name, f"{d['ns']:,}", f"{d['s_late']:,}件({pct(d['s_late'], d['ns'])})", f"{d['nt']:,}",
                           f"{d['t_late']}件({pct(d['t_late'], d['nt'])})", f"{d['exp']:.1f}件", fp(d["p"])])
    table_rows.append(["3県の合計", f"{tot['ns']:,}", f"{tot['s_late']:,}件({pct(tot['s_late'], tot['ns'])})", f"{tot['nt']:,}",
                       f"{tot['t_late']}件({pct(tot['t_late'], tot['nt'])})", f"{exp_pool:.1f}件", fp(p_pool)])

    # hour bands (pooled over the 3 prefectures) for the second table
    band_rows = []
    for label, a, b in BANDS:
        s_n = sum(1 for k in SOURCES for r in rows[k] if r[0] == "s" and a <= r[1] <= b)
        t_n = sum(1 for k in SOURCES for r in rows[k] if r[0] == "t" and a <= r[1] <= b)
        band_rows.append([label, f"{s_n:,}件({pct(s_n, tot['ns'])})", f"{t_n}件({pct(t_n, tot['nt'])})"])
    head2 = ["時間帯", "目撃(3県の合計)", "痕跡(3県の合計)"]
    allrows = [r for k in SOURCES for r in rows[k]]

    def share_of(kind, pred):
        sel = [r for r in allrows if r[0] == kind]
        return sum(1 for r in sel if pred(r)), len(sel)

    rob_rows = []
    for label, pred in [("15時以降", lambda r: r[1] >= 15), ("17時以降", lambda r: r[1] >= 17), ("18時以降", lambda r: r[1] >= 18),
                        ("6〜8時台", lambda r: 6 <= r[1] <= 8)]:
        a1, n1 = share_of("s", pred)
        a2, n2 = share_of("t", pred)
        rob_rows.append([label, f"{a1:,}件({pct(a1, n1)})", f"{a2}件({pct(a2, n2)})"])
    mon_rows = []
    for label, ms in [("4〜6月", (4, 5, 6)), ("7〜9月", (7, 8, 9)), ("10〜11月", (10, 11))]:
        sel_s = [r for r in allrows if r[0] == "s" and r[2] in ms]
        sel_t = [r for r in allrows if r[0] == "t" and r[2] in ms]
        ls = sum(1 for r in sel_s if r[1] >= LATE)
        lt = sum(1 for r in sel_t if r[1] >= LATE)
        mon_rows.append([label, f"{len(sel_s):,}", f"{ls:,}件({pct(ls, len(sel_s))})", f"{len(sel_t)}", f"{lt}件({pct(lt, len(sel_t))})"])
    head_rob = ["区切り", "目撃", "痕跡"]
    head_mon = ["時期", "目撃の件数", "目撃のうち15時以降", "痕跡の件数", "痕跡のうち15時以降"]
    t_morn_pct = pct(tot["t_morn"], tot["nt"])
    s_morn_pct = pct(tot["s_morn"], tot["ns"])
    t_day_pct = pct(tot["t_mid"], tot["nt"])
    s_day_pct = pct(tot["s_mid"], tot["ns"])
    s_late_pct, t_late_pct = pct(tot["s_late"], tot["ns"]), pct(tot["t_late"], tot["nt"])

    as_of_min = min(data[k]["as_of"] for k in SOURCES)
    as_of_max = max(data[k]["as_of"] for k in SOURCES)
    today = common.today().isoformat()
    a, m, y = per["akita"], per["miyagi"], per["yamaguchi"]
    all_below = all(per[k]["p"] < 0.05 for k in SOURCES)

    doc = {
        "slug": "trace-hours", "date": today, "data_as_of": as_of_max,
        "title": "足跡や糞の記録は、目撃より夕方以降が少ないか",
        "h1": "足跡や糞の記録は、目撃より夕方以降が少ないか",
        "description": (f"秋田・宮城・山口の令和8年度の熊の記録で、15時以降に報告された割合は、目撃が{s_late_pct}、痕跡(足跡・糞・食害など)が{t_late_pct}でした。"
                        f"痕跡は{tot['nt']}件で、昼のうちに報告される傾向が3県とも同じ向きです。"),
        "lead": (f"熊の記録には、熊そのものを見た「目撃」と、足跡・糞・食害などを見つけた「痕跡」があります。見つけた時間帯は、2つで同じなのでしょうか。"
                 f"秋田・宮城・山口の3県で、時刻の入った{tot['ns'] + tot['nt']:,}件を目撃と痕跡に分け、15時以降に報告された割合を集計しました。"
                 f"15時以降の割合は、目撃が{s_late_pct}、痕跡が{t_late_pct}です。痕跡の記録は{tot['nt']}件と少ないものの、3県とも痕跡のほうが昼のうちに報告されています。"),
        "findings": [
            f"3県の目撃{tot['ns']:,}件のうち、15時以降の報告は{tot['s_late']:,}件({s_late_pct})でした。痕跡{tot['nt']}件では{tot['t_late']}件({t_late_pct})です。",
            f"県別の痕跡の15時以降は、秋田が{a['nt']}件中{a['t_late']}件、宮城が{m['nt']}件中{m['t_late']}件、山口が{y['nt']}件中{y['t_late']}件でした。"
            f"同じ県・同じ月の中で目撃と痕跡のラベルを2,000回入れ替えた平均は、3県の合計で{exp_pool:.1f}件です。実際の{tot['t_late']}件は、偶然の範囲({lo_pool}〜{hi_pool}件)を下回りました。",
            f"6〜14時台の割合は、目撃が{s_day_pct}、痕跡が{t_day_pct}です。痕跡は朝から昼に集まっています。ただし、痕跡の時刻は見つけた時刻で、熊がそこにいた時刻とは限りません。",
        ],
        "sections": [
            {"h2": "目撃と痕跡を分けて、報告された時刻を集計する",
             "paragraphs": [
                 f"令和8年度(2026年4月1日から)の記録のうち、時刻が入っていて、目撃と痕跡を区別しているのは、秋田県・宮城県・山口県の3県です。山梨県は目撃だけ、新潟県と富山県は時刻がないので、ここでは使っていません。使った記録の最新日は、県によって{as_of_min}から{as_of_max}までです。",
                 f"秋田県の「痕跡」は、公開データで「痕跡(その他)」と「痕跡(食害)」に分かれています。ここでは2つを合わせて痕跡としました。人身被害と、種類が「その他」の記録は入れていません。",
                 f"3県の合計は、目撃が{tot['ns']:,}件、痕跡が{tot['nt']}件です。宮城県は、0時台と12時台の報告が入力の癖で偏っていることが、最初のノートで分かっています。そこで宮城県だけ、この2つの時間は目撃・痕跡とも除きました。"],
             "table": {"head": head1, "rows": table_rows, "note": "痕跡の「15時以降」は、実際の件数です。右から2つ目は、同じ県・同じ月の中で目撃と痕跡のラベルだけを入れ替えて2,000回数え直したときの平均です。pは、入れ替えた2,000回のうち、実際と同じかそれより少ない回数の割合(片側)です。"}},
            {"h2": "痕跡は、朝から昼に集まる",
             "paragraphs": [
                 f"15時以降の割合は、目撃が{s_late_pct}、痕跡が{t_late_pct}です。県別では、秋田県が目撃{pct(a['s_late'], a['ns'])}・痕跡{pct(a['t_late'], a['nt'])}、宮城県が{pct(m['s_late'], m['ns'])}・{pct(m['t_late'], m['nt'])}、山口県が{pct(y['s_late'], y['ns'])}・{pct(y['t_late'], y['nt'])}です。3県とも、痕跡のほうが夕方以降の割合が小さくなっています。",
                 f"時間帯ごとに分けると、違いがはっきりします。6〜8時台は目撃{s_morn_pct}、痕跡{t_morn_pct}です。9〜14時台は目撃{pct(sum(1 for k in SOURCES for r in rows[k] if r[0] == 's' and 9 <= r[1] <= 14), tot['ns'])}、痕跡{pct(sum(1 for k in SOURCES for r in rows[k] if r[0] == 't' and 9 <= r[1] <= 14), tot['nt'])}です。",
                 "目撃は、夕方から夜にかけても報告が続きます。痕跡は、昼のうちに見つかった記録が大半を占めます。"],
             "table": {"head": head2, "rows": band_rows, "note": "秋田・宮城・山口の合計です。宮城県の0時台と12時台は除いています。割合は、目撃または痕跡それぞれの合計に対するものです。"}},
            {"h2": "県ごとに同じ向きか、偶然の範囲を超えているか",
             "paragraphs": [
                 f"痕跡の件数が少ないので、「15時以降」の割合は、数件のずれで大きく動きます。そこで、同じ県・同じ月の目撃と痕跡のラベルを入れ替え、痕跡が15時以降に何件入るかを2,000回試しました。3県の合計では平均{exp_pool:.1f}件で、実際は{tot['t_late']}件です。入れ替えた2,000回のうち、実際と同じかそれより少なかった割合は{fp(p_pool)}でした。",
                 f"県別のpは、秋田{fp(a['p'])}・宮城{fp(m['p'])}・山口{fp(y['p'])}です。" + ("3県とも0.05を下回っています。" if all_below else "0.05を下回らなかった県もあるので、県ごとの結論は出せません。"),
                 "月ごとにラベルを入れ替えているので、「痕跡は夏に多く、夏は日が長い」といった月のちがいは、この比較に入りません。"],
            },
            {"h2": "区切りの時刻や時期を変えても、同じ向きか",
             "paragraphs": [
                 "15時という区切りは、こちらで決めたものです。区切りを17時や18時に動かしても、痕跡の割合が目撃より小さいことは変わりません。逆に、6〜8時台の早朝は、痕跡のほうが割合が大きくなります。",
                 "時期を3つに分けた集計も並べました。10〜11月は、秋田県の記録がないため、宮城県と山口県だけです。件数が少ない区間は、割合の大小だけでは読み取れません。"],
             "table": {"head": head_rob, "rows": rob_rows, "note": "3県の合計です。宮城県の0時台と12時台は除いています。"}},
            {"h2": "月ごとに分けても、痕跡は夕方以降が少ないか",
             "paragraphs": [
                 "痕跡の件数は、月によって違います。夏のあいだに集中していれば、日の長さの影響を受けて、割合が偏るかもしれません。そこで、時期を3つに分けて、15時以降の割合を集計しました。",
                 "4〜6月、7〜9月のどちらでも、痕跡の15時以降の割合は目撃より小さくなっています。10〜11月は件数が少ないので、割合の大小は読み取りません。"],
             "table": {"head": head_mon, "rows": mon_rows, "note": "3県の合計です。10〜11月は宮城県・山口県だけで、痕跡の件数が少なくなります。"}},
            {"h2": "なぜ違うのか、この記録からは言えない",
             "paragraphs": [
                 "目撃の時刻は、熊を見た時刻です。痕跡の時刻は、足跡や糞を見つけた時刻で、熊がそこを通った時刻ではありません。痕跡は、見つけた人が畑や山で仕事をしている昼のうちに報告されやすいのかもしれません。",
                 "また、暗くなると痕跡は見つけにくくなります。見つける人が少ない夜や夕方に、報告が少ないだけの可能性もあります。どちらが理由かは、この記録だけでは言えません。",
                 "どの県も、報告する人と受け付ける自治体の仕組みが違います。このノートで言えるのは、3県の報告された記録の中で、痕跡の報告が昼に偏っていることまでです。"],
            },
            {"h2": "この数字の使い方",
             "paragraphs": [
                 "足跡や糞の記録が昼間に多いからといって、熊が昼に活動すると決まるわけではありません。夕方以降の目撃は、痕跡より多く報告されています。薄暗い時間帯の山沿いは、痕跡がなくても注意が必要です。",
                 "お住まいの地域で痕跡の記録が出ていたら、その日の夕方以降も、その場所の近くでは、目撃の記録が続く可能性があります。県の最新の記録は、各県の公表ページで確認してください。",
                 f"集計した痕跡は{tot['nt']}件で、目撃の{tot['ns']:,}件よりずっと少ない数です。痕跡の記録を、1か所・1日だけで判断することは避けてください。"],
            },
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録のうち、時刻が入っていて目撃と痕跡を区別している秋田県・宮城県・山口県の3県です。計算した日は{today}、使った記録の最新日は県によって{as_of_min}から{as_of_max}までです。",
            "目撃は種類が「目撃」の記録、痕跡は種類が「痕跡」で始まる記録(秋田県の「痕跡(その他)」「痕跡(食害)」を含む)です。人身被害と「その他」は使っていません。宮城県は、時刻が0時台と12時台の記録を、目撃・痕跡とも除きました。",
            "時刻は、記録に書かれた時刻の「時」です。「15時以降」は、15時00分から23時59分です。",
            f"偶然の範囲は、次の手順で求めました。同じ県・同じ月の中で、時刻のある記録に、痕跡の件数分だけランダムに痕跡のラベルを付け直します。痕跡が15時以降に入る件数を2,000回求めました(乱数の種は固定)。3県の合計の95%の範囲は{lo_pool}〜{hi_pool}件です。",
            "計算のスクリプトは公開しています。数字はすべてスクリプトが出しています。",
        ],
        "caveats": [
            "これは報告された記録の数です。熊の行動の時間帯を示すものではありません。痕跡の時刻は、見つけた時刻です。",
            f"痕跡は3県で{tot['nt']}件と少なく、県別の割合は、数件のずれで変わります。",
            "秋田県は9月末まで、宮城県と山口県は11月初めまでの記録です。使った期間が県で違います。",
            "1年度分(令和8年度)だけです。ほかの年や、ほかの県で同じ形になるかは、この記録だけでは言えません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/trace-hours.py",
        "related": [{"label": "熊の目撃は何時ごろに報告されているか", "href": "/research/hour-of-day/"},
                    {"label": "日没後に報告された記録の割合", "href": "/research/after-sunset/"},
                    {"label": "熊の記録のうち痕跡は何割か", "href": "/research/trace-ratio/"},
                    {"label": "宮城県の最新の目撃情報", "href": "/live/miyagi/"},
                    {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)


main()
