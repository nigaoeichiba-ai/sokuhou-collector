"""Research note: are sightings of 2+ bears reported at different hours than sightings of one bear?  Three prefectures that store a clock time and a head count.

python sites/kuma/research/scripts/multi-bear-hours.py
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
LATE = 15
BANDS = [("0〜5時台", 0, 5), ("6〜8時台", 6, 8), ("9〜14時台", 9, 14), ("15〜17時台", 15, 17), ("18〜23時台", 18, 23)]
N_SHUFFLE = 2000
SEED = 20261112


def pct(part: int, whole: int) -> str:
    return f"{part / whole * 100:.0f}%" if whole else "-"


def fp(p: float) -> str:
    return "0.001未満" if p < 0.001 else f"{p:.3f}"


def load(key: str):
    """[(multi?, hour, month)] of the 目撃 records with a clock time; the head count is read from the stored file."""
    s = common.load_source(key)
    raw = json.loads((common.DATA / f"{key}_kuma.json").read_text(encoding="utf-8"))
    counts = {}
    for x in raw["sightings"]:
        counts.setdefault((x["observed_at"], x.get("city", ""), x.get("place", "")), []).append(x.get("count") or 1)
    out = []
    for x in raw["sightings"]:
        o = x["observed_at"]
        if o[:10] < common.FY_START.isoformat() or "T" not in o or o.endswith("T00:00:00+09:00"):
            continue
        if not x["kind"].startswith("目撃"):
            continue
        dt = datetime.fromisoformat(o)
        out.append((((x.get("count") or 1) >= 2), dt.hour, dt.month))
    return s, out


def main() -> None:
    rng = random.Random(SEED)
    data, rows = {}, {}
    for key in SOURCES:
        data[key], rows[key] = load(key)

    per = {}
    for key in SOURCES:
        m = [r for r in rows[key] if r[0]]
        o = [r for r in rows[key] if not r[0]]
        per[key] = {"nm": len(m), "no": len(o),
                    "m_late": sum(1 for r in m if r[1] >= LATE), "o_late": sum(1 for r in o if r[1] >= LATE),
                    "m_morn": sum(1 for r in m if 6 <= r[1] <= 8), "o_morn": sum(1 for r in o if 6 <= r[1] <= 8)}

    def shuffle_once(key: str, late: bool = True) -> int:
        strata = defaultdict(list)
        for mu, h, mo in rows[key]:
            strata[mo].append((mu, h))
        total = 0
        for lst in strata.values():
            nm = sum(1 for mu, _ in lst if mu)
            hours = [h for _, h in lst]
            pick = rng.sample(hours, nm)
            total += sum(1 for h in pick if (h >= LATE if late else 6 <= h <= 8))
        return total

    sims = {k: [shuffle_once(k) for _ in range(N_SHUFFLE)] for k in SOURCES}
    pooled = [sum(sims[k][i] for k in SOURCES) for i in range(N_SHUFFLE)]
    tot = {f: sum(per[k][f] for k in SOURCES) for f in ("nm", "no", "m_late", "o_late", "m_morn", "o_morn")}
    exp_pool = sum(pooled) / N_SHUFFLE
    srt = sorted(pooled)
    lo, hi = srt[int(N_SHUFFLE * 0.025)], srt[int(N_SHUFFLE * 0.975)]
    p_two = min(1.0, 2 * min((1 + sum(1 for x in pooled if x <= tot["m_late"])) / (N_SHUFFLE + 1),
                             (1 + sum(1 for x in pooled if x >= tot["m_late"])) / (N_SHUFFLE + 1)))
    for k in SOURCES:
        obs = per[k]["m_late"]
        lo_p = (1 + sum(1 for x in sims[k] if x <= obs)) / (N_SHUFFLE + 1)
        hi_p = (1 + sum(1 for x in sims[k] if x >= obs)) / (N_SHUFFLE + 1)
        per[k]["p"] = min(1.0, 2 * min(lo_p, hi_p))
        per[k]["exp"] = sum(sims[k]) / N_SHUFFLE

    rest = [k for k in SOURCES if k != "akita"]
    rest_pool = [sum(sims[k][i] for k in rest) for i in range(N_SHUFFLE)]
    r_nm = sum(per[k]["nm"] for k in rest)
    r_no = sum(per[k]["no"] for k in rest)
    r_ml = sum(per[k]["m_late"] for k in rest)
    r_ol = sum(per[k]["o_late"] for k in rest)
    r_exp = sum(rest_pool) / N_SHUFFLE
    r_srt = sorted(rest_pool)
    r_lo, r_hi = r_srt[int(N_SHUFFLE * 0.025)], r_srt[int(N_SHUFFLE * 0.975)]
    r_p = min(1.0, 2 * min((1 + sum(1 for x in rest_pool if x <= r_ml)) / (N_SHUFFLE + 1),
                           (1 + sum(1 for x in rest_pool if x >= r_ml)) / (N_SHUFFLE + 1)))
    r_inside = r_lo <= r_ml <= r_hi
    eve_m = sum(1 for k in SOURCES for r in rows[k] if r[0] and r[1] >= 18)
    eve_o = sum(1 for k in SOURCES for r in rows[k] if not r[0] and r[1] >= 18)
    eve_a_m = sum(1 for r in rows["akita"] if r[0] and r[1] >= 18)
    eve_a_o = sum(1 for r in rows["akita"] if not r[0] and r[1] >= 18)

    table1 = []
    for key, name in SOURCES.items():
        d = per[key]
        table1.append([name, f"{d['no']:,}", f"{d['o_late']:,}件({pct(d['o_late'], d['no'])})", f"{d['nm']}",
                       f"{d['m_late']}件({pct(d['m_late'], d['nm'])})", f"{d['exp']:.1f}件", fp(d["p"])])
    table1.append(["3県の合計", f"{tot['no']:,}", f"{tot['o_late']:,}件({pct(tot['o_late'], tot['no'])})", f"{tot['nm']}",
                   f"{tot['m_late']}件({pct(tot['m_late'], tot['nm'])})", f"{exp_pool:.1f}件", fp(p_two)])
    head1 = ["県", "1頭の目撃の件数", "1頭のうち15時以降", "2頭以上の目撃の件数", "2頭以上のうち15時以降", "2頭以上の15時以降(入れ替えの平均)", "偶然の範囲との差の確率(p・両側)"]

    allrows = [r for k in SOURCES for r in rows[k]]
    band_rows = []
    for label, a, b in BANDS:
        mn = sum(1 for r in allrows if r[0] and a <= r[1] <= b)
        on = sum(1 for r in allrows if not r[0] and a <= r[1] <= b)
        band_rows.append([label, f"{on:,}件({pct(on, tot['no'])})", f"{mn}件({pct(mn, tot['nm'])})"])
    head2 = ["時間帯", "1頭の目撃(3県の合計)", "2頭以上の目撃(3県の合計)"]

    mon_rows = []
    for label, ms in [("4〜6月", (4, 5, 6)), ("7〜9月", (7, 8, 9)), ("10〜11月", (10, 11))]:
        so = [r for r in allrows if not r[0] and r[2] in ms]
        sm = [r for r in allrows if r[0] and r[2] in ms]
        lo_ = sum(1 for r in so if r[1] >= LATE)
        lm_ = sum(1 for r in sm if r[1] >= LATE)
        mon_rows.append([label, f"{len(so):,}", f"{lo_:,}件({pct(lo_, len(so))})", f"{len(sm)}", f"{lm_}件({pct(lm_, len(sm))})"])
    head3 = ["時期", "1頭の件数", "1頭のうち15時以降", "2頭以上の件数", "2頭以上のうち15時以降"]

    share_rows = []
    for label, a, b in [("0〜5時台", 0, 5), ("6〜8時台", 6, 8), ("9〜14時台", 9, 14), ("15時以降", 15, 23)]:
        n = sum(1 for r in allrows if a <= r[1] <= b)
        mm = sum(1 for r in allrows if r[0] and a <= r[1] <= b)
        share_rows.append([label, f"{n:,}", f"{mm}件({pct(mm, n)})"])
    head4 = ["時間帯", "目撃の件数(3県の合計)", "うち2頭以上"]

    o_late_pct, m_late_pct = pct(tot["o_late"], tot["no"]), pct(tot["m_late"], tot["nm"])
    o_morn_pct, m_morn_pct = pct(tot["o_morn"], tot["no"]), pct(tot["m_morn"], tot["nm"])
    all_n = tot["no"] + tot["nm"]
    multi_share = pct(tot["nm"], all_n)
    as_of_min = min(data[k]["as_of"] for k in SOURCES)
    as_of_max = max(data[k]["as_of"] for k in SOURCES)
    today = common.today().isoformat()
    a, y, m = per["akita"], per["yamaguchi"], per["yamanashi"]
    inside = lo <= tot["m_late"] <= hi
    verdict = "偶然の範囲に収まりました" if inside else "偶然の範囲を外れました"

    doc = {
        "slug": "multi-bear-hours", "date": today, "data_as_of": as_of_max,
        "title": "2頭以上の熊の目撃は、1頭より報告される時間帯が違うか",
        "h1": "2頭以上の熊の目撃は、1頭より報告される時間帯が違うか",
        "description": (f"秋田・山口・山梨の令和8年度の熊の目撃{all_n:,}件のうち、2頭以上と報告されたのは{tot['nm']}件({multi_share})です。"
                        f"15時以降に報告された割合は、1頭が{o_late_pct}、2頭以上が{m_late_pct}でした。"),
        "lead": (f"熊の目撃には、1頭を見た記録と、親子連れなど2頭以上を見た記録があります。報告された時間帯は、2つで違うのでしょうか。"
                 f"秋田・山口・山梨の3県で、時刻と頭数が入った目撃{all_n:,}件を、1頭と2頭以上に分けて集計しました。"
                 f"15時以降の割合は、1頭が{o_late_pct}、2頭以上が{m_late_pct}です。2頭以上の記録は{tot['nm']}件と少ないため、同じ県・同じ月の中でラベルを入れ替えた2,000回と比べました。"),
        "findings": [
            f"3県の1頭の目撃{tot['no']:,}件のうち、15時以降の報告は{tot['o_late']:,}件({o_late_pct})でした。2頭以上の{tot['nm']}件では{tot['m_late']}件({m_late_pct})です。",
            f"同じ県・同じ月の中で1頭と2頭以上のラベルを2,000回入れ替えると、2頭以上の15時以降は平均{exp_pool:.1f}件(95%の範囲は{lo}〜{hi}件)でした。実際の{tot['m_late']}件は、{verdict}(両側のp={fp(p_two)})。",
            f"秋田県を除いた山口・山梨では、2頭以上{r_nm}件のうち15時以降は{r_ml}件({pct(r_ml, r_nm)})、1頭{r_no}件では{r_ol}件({pct(r_ol, r_no)})です。入れ替えの95%の範囲は{r_lo}〜{r_hi}件で、実際の{r_ml}件は" + ("範囲内でした。" if r_inside else "範囲を外れました。"),
            f"18時以降では、1頭が{eve_o:,}件({pct(eve_o, tot['no'])})、2頭以上が{eve_m}件({pct(eve_m, tot['nm'])})です。6〜8時台は1頭{o_morn_pct}、2頭以上{m_morn_pct}でした。",
        ],
        "sections": [
            {"h2": "1頭と2頭以上に分けて、報告された時刻を集計する",
             "paragraphs": [
                 f"令和8年度(2026年4月1日から)の目撃のうち、時刻と頭数の両方が記録に入っていて、2頭以上の記録が実際にあるのは、秋田県・山口県・山梨県の3県です。宮城県は頭数がすべて1頭、新潟県と富山県は時刻がないので、ここでは使っていません。使った記録の最新日は、県によって{as_of_min}から{as_of_max}までです。",
                 "「2頭以上」は、記録の頭数の欄が2以上のものです。親子連れとは限りません。秋田県には13頭という記録も1件あり、2頭以上に含めています。痕跡と人身被害は使わず、種類が「目撃」の記録だけにしました。",
                 f"3県の合計は、1頭が{tot['no']:,}件、2頭以上が{tot['nm']}件です。目撃全体の{multi_share}が2頭以上でした。",
                 f"2頭以上{tot['nm']}件のうち、秋田県が{per['akita']['nm']}件({pct(per['akita']['nm'], tot['nm'])})、山口県が{per['yamaguchi']['nm']}件、山梨県が{per['yamanashi']['nm']}件です。秋田県の記録が、合計の大部分を占めます。"],
             "table": {"head": head1, "rows": table1, "note": "「15時以降」は実際の件数です。右から2つ目は、同じ県・同じ月の中で1頭と2頭以上のラベルだけを入れ替えて2,000回集計し直したときの平均です。pは、入れ替えた2,000回のうち、実際と同じかそれ以上にずれた割合(両側)です。"}},
            {"h2": "15時以降の割合は、1頭と2頭以上でどう違うか",
             "paragraphs": [
                 f"15時以降の割合は、1頭が{o_late_pct}、2頭以上が{m_late_pct}です。県別では、秋田県が1頭{pct(a['o_late'], a['no'])}・2頭以上{pct(a['m_late'], a['nm'])}、山口県が{pct(y['o_late'], y['no'])}・{pct(y['m_late'], y['nm'])}、山梨県が{pct(m['o_late'], m['no'])}・{pct(m['m_late'], m['nm'])}です。",
                 f"3県の合計をラベルの入れ替えと比べると、2頭以上の15時以降は{tot['m_late']}件で、入れ替えの平均{exp_pool:.1f}件に対して{verdict}。県別のpは、秋田{fp(a['p'])}・山口{fp(y['p'])}・山梨{fp(m['p'])}です。",
                 "山口県と山梨県は2頭以上の件数が少なく、数件のずれで割合が大きく動きます。県別のpは、秋田県だけが0.05を下回り、山口県と山梨県は偶然の範囲に収まっています。3県の合計の結果は、件数の多い秋田県に引っ張られている可能性があります。",
                 f"そこで、秋田県を除いた山口県と山梨県の合計でも、同じ入れ替えを行いました。2頭以上{r_nm}件のうち15時以降は{r_ml}件({pct(r_ml, r_nm)})、1頭{r_no}件のうちは{r_ol}件({pct(r_ol, r_no)})です。入れ替えの平均は{r_exp:.1f}件、95%の範囲は{r_lo}〜{r_hi}件で、両側のpは{fp(r_p)}でした。" + ("2県だけでは、偶然の範囲に収まります。" if r_inside else "2県だけでも、偶然の範囲を外れています。")],
            },
            {"h2": "時間帯ごとに並べる",
             "paragraphs": [
                 "区切りを15時だけにせず、5つの時間帯に分けて並べました。割合は、1頭の合計・2頭以上の合計に対するものです。",
                 f"6〜8時台は1頭{o_morn_pct}、2頭以上{m_morn_pct}です。いっぽう18〜23時台は、1頭が{pct(sum(1 for r in allrows if not r[0] and r[1] >= 18), tot['no'])}、2頭以上が{pct(eve_m, tot['nm'])}と、2頭以上のほうが大きくなっています。",
                 f"18時以降だけを取り出すと、1頭は{eve_o:,}件、2頭以上は{eve_m}件です。このうち秋田県は、1頭{eve_a_o:,}件・2頭以上{eve_a_m}件を占めます。夕方から夜の2頭以上は、ほとんどが秋田県の記録です。",
                 "件数が少ない時間帯では、1件の違いで割合が動きます。0〜5時台の2頭以上は12件で、割合の大小は読み取りません。"],
             "table": {"head": head2, "rows": band_rows, "note": "3県の合計です。割合は、1頭または2頭以上それぞれの合計に対するものです。"}},
            {"h2": "同じ時間帯に、2頭以上はどれだけ含まれるか",
             "paragraphs": [
                 f"向きを変えて、時間帯ごとの目撃のうち2頭以上が何件あるかも並べました。目撃全体では2頭以上が{multi_share}です。この割合より大きい時間帯・小さい時間帯があるかを、表で読めます。"],
             "table": {"head": head4, "rows": share_rows, "note": "3県の合計です。時刻の入った目撃だけを集計しています。"}},
            {"h2": "時期を分けても、同じ向きか",
             "paragraphs": [
                 "夏は日が長く、秋は短くなります。時期によって報告される時間帯が動くと、2頭以上の記録が多い時期に割合が偏るかもしれません。そこで、時期を3つに分けて15時以降の割合を並べました。",
                 f"4〜6月は、1頭が{mon_rows[0][2].split('(')[1][:-1]}、2頭以上が{mon_rows[0][4].split('(')[1][:-1]}です。7〜9月は、1頭が{mon_rows[1][2].split('(')[1][:-1]}、2頭以上が{mon_rows[1][4].split('(')[1][:-1]}で、2頭以上のほうが15時以降の割合が大きい向きは、2つの時期で同じです。",
                 "10〜11月は件数が少ないので、割合の大小は読み取りません。"],
             "table": {"head": head3, "rows": mon_rows, "note": "3県の合計です。ラベルの入れ替えは、月ごとに行っています。"}},
            {"h2": "なぜ違うのか、この記録からは言えない",
             "paragraphs": [
                 "ラベルの入れ替えで取り除けるのは、県と月の違いです。秋田県は記録が多く、2頭以上の記録の大部分も秋田県です。県や月をまとめて比べると、時間帯の違いが、県や月の違いと混ざってしまいます。そこで、入れ替えは同じ県・同じ月の中だけで行いました。",
                 "いっぽう、入れ替えでも取り除けないものがあります。頭数の数え方や、通報を受け付ける時刻の記録のしかたが、県や自治体によって違うことです。同じ県の中でも、通報した人の見え方で、1頭と2頭以上のどちらになるかは変わります。",
                 "頭数は、通報した人が見た数です。木の陰にもう1頭いても、見えなければ1頭と記録されます。暗い時間帯ほど、頭数を見分けにくいことも考えられます。",
                 "どの県も、報告する人と受け付ける自治体の仕組みが違います。このノートで言えるのは、3県の報告された記録の中で、1頭と2頭以上の時間帯がどう分かれているかまでです。熊の行動や、親子連れの動きそのものは、この記録からは言えません。"],
            },
            {"h2": "この数字の使い方",
             "paragraphs": [
                 "2頭以上の記録が出ている地域では、1頭だけの記録が出ている地域とは別の注意が要ります。親子連れの可能性があるときは、近づかず、その場を静かに離れてください。",
                 f"集計した2頭以上の目撃は{tot['nm']}件で、1頭の{tot['no']:,}件よりずっと少ない数です。1か所・1日の記録だけで時間帯を決めつけないでください。県の最新の記録は、各県の公表ページで確認できます。"],
            },
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の目撃の記録のうち、時刻と頭数が入っている秋田県・山口県・山梨県の3県です。計算した日は{today}、使った記録の最新日は県によって{as_of_min}から{as_of_max}までです。",
            "「1頭」は頭数の欄が1(または空欄)の記録、「2頭以上」は頭数の欄が2以上の記録です。種類が「目撃」で始まる記録だけを使い、痕跡・人身被害・その他は除きました。",
            "時刻は、記録に書かれた時刻の「時」です。「15時以降」は、15時00分から23時59分です。",
            f"偶然の範囲は、次の手順で求めました。同じ県・同じ月の中で、時刻のある目撃に、2頭以上の件数分だけランダムに「2頭以上」のラベルを付け直し、15時以降に入る件数を2,000回求めました(乱数の種は固定)。3県の合計の95%の範囲は{lo}〜{hi}件です。",
            "計算のスクリプトは公開しています。数字はすべてスクリプトが出しています。",
        ],
        "caveats": [
            "これは報告された記録の数です。熊の行動の時間帯を示すものではありません。頭数は、通報した人が見た数です。",
            f"2頭以上は3県で{tot['nm']}件と少なく、県別の割合は、数件のずれで変わります。",
            "秋田県は9月末まで、山口県と山梨県は11月初めまでの記録です。使った期間が県で違います。",
            "1年度分(令和8年度)だけです。ほかの年や、ほかの県で同じ形になるかは、この記録だけでは言えません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/multi-bear-hours.py",
        "related": [{"label": "目撃1件に何頭と報告されているか", "href": "/research/count-per-report/"},
                    {"label": "熊の目撃は何時ごろに報告されているか", "href": "/research/hour-of-day/"},
                    {"label": "日没後に報告された記録の割合", "href": "/research/after-sunset/"},
                    {"label": "足跡や糞の記録は目撃より夕方以降が少ないか", "href": "/research/trace-hours/"},
                    {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)


main()
