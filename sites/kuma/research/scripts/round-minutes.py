"""Research note: do the reported times of bear records pile up on round minutes (:00, :30, multiples of 5)?  Four prefectures that store a clock time.

python sites/kuma/research/scripts/round-minutes.py
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SOURCES = {"akita": "秋田県", "miyagi": "宮城県", "yamaguchi": "山口県", "yamanashi": "山梨県"}
BANDS = [("8時台まで", 0, 8), ("9〜11時台", 9, 11), ("12〜14時台", 12, 14), ("15〜17時台", 15, 17), ("18時台以降", 18, 23)]


def share(part: int, whole: int) -> float:
    return part / whole * 100 if whole else 0.0


def f(x: float) -> str:
    return f"{x:.0f}%"


def f1(x: float) -> str:
    return f"{x:.1f}%"


def stats(times):
    n = len(times)
    c = Counter(t.minute for t in times)
    z = c[0]
    h = c[30]
    m5 = sum(v for m, v in c.items() if m % 5 == 0)
    m10 = sum(v for m, v in c.items() if m % 10 == 0)
    odd = [m for m in c if m % 5 != 0]
    other = n - z - h
    other5 = sum(v for m, v in c.items() if m % 5 == 0 and m not in (0, 30))
    second_half = sum(v for m, v in c.items() if m >= 30)
    return {"n": n, "z": z, "h": h, "m5": m5, "m10": m10, "other": other, "other5": other5, "late": second_half, "odd": sum(c[m] for m in odd)}


def main() -> None:
    data = {k: common.load_source(k) for k in SOURCES}
    times = {k: [r[0] for r in s["rows"] if isinstance(r[0], datetime)] for k, s in data.items()}
    st = {k: stats(v) for k, v in times.items()}
    allt = [t for v in times.values() for t in v]
    tot = stats(allt)
    n = tot["n"]
    as_of = max(s["as_of"] for s in data.values())
    today = common.today().isoformat()

    rows1 = [[SOURCES[k], f"{st[k]['n']:,}", f1(share(st[k]["z"], st[k]["n"])), f1(share(st[k]["h"], st[k]["n"])), f(share(st[k]["m5"], st[k]["n"])), f(share(st[k]["m10"], st[k]["n"]))] for k in SOURCES]
    rows1.append(["4県の合計", f"{n:,}", f1(share(tot["z"], n)), f1(share(tot["h"], n)), f(share(tot["m5"], n)), f(share(tot["m10"], n))])
    rows1.append(["全分に同じ割合なら", "-", "1.7%", "1.7%", "20%", "10%"])

    band_rows = []
    band_vals = []
    for lab, lo, hi in BANDS:
        tt = [t for t in allt if lo <= t.hour <= hi]
        s = stats(tt)
        band_vals.append((lab, s))
        band_rows.append([lab, f"{s['n']:,}", f1(share(s["z"], s["n"])), f1(share(s["h"], s["n"])), f(share(s["m5"], s["n"]))])
    month_rows = []
    month_vals = {}
    for m in range(4, 12):
        tt = [t for t in allt if t.month == m]
        if len(tt) < 100:
            continue
        s = stats(tt)
        month_vals[m] = s
        month_rows.append([f"{m}月", f"{s['n']:,}", f1(share(s["z"], s["n"])), f(share(s["m5"], s["n"]))])
    low5 = min(SOURCES, key=lambda k: share(st[k]['m5'], st[k]['n']))
    q15 = sum(1 for t in allt if t.minute % 15 == 0)
    hi_k = max(SOURCES, key=lambda k: share(st[k]["z"], st[k]["n"]))
    lo_k = min(SOURCES, key=lambda k: share(st[k]["z"], st[k]["n"]))
    zero_hi = max(band_vals, key=lambda b: share(b[1]["z"], b[1]["n"]))
    zero_lo = min(band_vals, key=lambda b: share(b[1]["z"], b[1]["n"]))
    other5_share = share(tot["other5"], tot["other"])
    odd_share = share(tot["odd"], n)
    late_share = share(tot["late"], n)
    exp_m5_other = 100 * 10 / 58
    desc = (f"秋田・宮城・山口・山梨の令和8年度の熊の記録{n:,}件のうち、報告の時刻が「ちょうど〇時0分」だった記録は{f1(share(tot['z'], n))}、5分刻みの分だった記録は{f(share(tot['m5'], n))}でした。"
            f"どの分も同じ割合なら、それぞれ1.7%と20%です。")

    doc = {
        "slug": "round-minutes", "date": today, "data_as_of": as_of,
        "title": "熊の記録の時刻は、切りのいい分に偏っているか",
        "h1": "熊(クマ)の目撃の時刻は、切りのいい分に偏っているか",
        "description": desc,
        "lead": (f"熊の記録には、「午前6時20分」のように分まで書かれたものがあります。ところが、4県の令和8年度の記録{n:,}件で分を数えると、0分が{f1(share(tot['z'], n))}、30分が{f1(share(tot['h'], n))}、5の倍数の分が{f(share(tot['m5'], n))}を占めていました。"
                 f"どの分も同じ割合で現れるなら、0分と30分はそれぞれ1.7%、5の倍数の分は20%のはずです。時刻の分は、実際に熊を見た分を正確に表しているのではなく、報告した人や受け付けた人が切りのよい数に丸めているところが大きいようです。"),
        "findings": [
            f"4県の記録{n:,}件のうち、0分は{tot['z']:,}件({f1(share(tot['z'], n))})、30分は{tot['h']:,}件({f1(share(tot['h'], n))})でした。0分と30分だけで{f(share(tot['z'] + tot['h'], n))}を占めます。",
            f"5の倍数の分は{f(share(tot['m5'], n))}、10の倍数の分は{f(share(tot['m10'], n))}です。5の倍数でない分は{f(odd_share)}しかありません。0分の割合は、{SOURCES[hi_k]}の{f1(share(st[hi_k]['z'], st[hi_k]['n']))}から{SOURCES[lo_k]}の{f1(share(st[lo_k]['z'], st[lo_k]['n']))}まで開いています。",
            f"時間帯別では、0分の割合が最も高いのは{zero_hi[0]}の{f1(share(zero_hi[1]['z'], zero_hi[1]['n']))}、最も低いのは{zero_lo[0]}の{f1(share(zero_lo[1]['z'], zero_lo[1]['n']))}です。時刻の丸め方は、時間帯でも違います。",
        ],
        "sections": [
            {"h2": "分の数字を、0分から59分まで数える",
             "paragraphs": [f"令和8年度(2026年4月1日から)の記録のうち、秋田・宮城・山口・山梨の4県は、日付に加えて「何時何分」まで記録に残っています。時刻のある記録は合わせて{n:,}件です。新潟・富山は日付だけなので入れていません。",
                            "この記録の「分」を数えました。熊を見た時刻がでたらめに分かれているなら、0分から59分までの60通りに、ほぼ同じ件数が散らばるはずです。0分も30分も約1.7%、5の倍数の分(12通り)は合わせて約20%になります。",
                            f"実際は、0分が{f1(share(tot['z'], n))}、30分が{f1(share(tot['h'], n))}で、その2つで全体の{f(share(tot['z'] + tot['h'], n))}です。5の倍数の分は{f(share(tot['m5'], n))}で、期待される20%の{tot['m5'] / (n * 0.2):.1f}倍になります。"],
             "table": {"head": ["県", "時刻のある記録", "0分", "30分", "5の倍数の分", "10の倍数の分"], "rows": rows1,
                       "note": "「全分に同じ割合なら」は、0分から59分までの60通りの分が同じ件数ずつ現れた場合の割合です。"}},
            {"h2": "県によって、丸め方は違う",
             "paragraphs": [f"0分の割合は、{SOURCES[hi_k]}が{f1(share(st[hi_k]['z'], st[hi_k]['n']))}、{SOURCES[lo_k]}が{f1(share(st[lo_k]['z'], st[lo_k]['n']))}です。山梨県は5の倍数の分が{f1(share(st['yamanashi']['m5'], st['yamanashi']['n']))}で、5の倍数でない分の記録は{st['yamanashi']['odd']}件しかありません。",
                            f"逆に5の倍数の分の割合が最も低いのは{SOURCES[low5]}の{f(share(st[low5]['m5'], st[low5]['n']))}で、5の倍数でない分の記録も{st[low5]['odd']}件(その県の{f(share(st[low5]['odd'], st[low5]['n']))})あります。秋田県は件数が最も多く(時刻のある記録{st['akita']['n']:,}件)、5の倍数でない分は{st['akita']['odd']}件({f(share(st['akita']['odd'], st['akita']['n']))})です。報告を受ける人が何分刻みで書き留めるか、報告する人が時計を見て答えるか、といった違いが出ている可能性があります。",
                            f"15分刻み(0・15・30・45分)に広げると、4県で{f(share(q15, n))}になります。0分・30分以外の15分と45分だけで{f(share(q15 - tot['z'] - tot['h'], n))}です。",
                            "どの県の記録でも、0分と30分が突出して多いことは同じです。県の間の違いがどこから来るのかは、記録の元になった発表資料の書き方を見ないと分かりません。"]},
            {"h2": "時間帯で、丸め方は変わるか",
             "paragraphs": [f"時間帯別に0分の割合を見ると、{zero_hi[0]}が{f1(share(zero_hi[1]['z'], zero_hi[1]['n']))}で最も高く、{zero_lo[0]}が{f1(share(zero_lo[1]['z'], zero_lo[1]['n']))}で最も低くなりました。どの時間帯も、期待される1.7%を10倍以上、上回っています。",
                            "時間帯によって0分の割合が少し動くのは、仕事中・移動中など、報告する人の状況や、報告の受け方が違うためかもしれません。ただ、動く幅は、県の間の違いに比べると小さく、時間帯を問わず切りのよい分に偏っていることのほうが目立ちます。"],
             "table": {"head": ["時間帯", "記録の数", "0分", "30分", "5の倍数の分"], "rows": band_rows,
                       "note": "4県を合わせた数字です。時間帯は記録の「時」で分けています。"}},
            {"h2": "月別でも、切りのよい分に偏る",
             "paragraphs": [f"月別では、0分の割合が{min(month_vals, key=lambda m: share(month_vals[m]['z'], month_vals[m]['n']))}月の{f1(min(share(v['z'], v['n']) for v in month_vals.values()))}から{max(month_vals, key=lambda m: share(month_vals[m]['z'], month_vals[m]['n']))}月の{f1(max(share(v['z'], v['n']) for v in month_vals.values()))}まで動きます。月が違っても、切りのよい分に偏ることは変わりません。月別は、記録が100件以上ある月だけを載せました。",
                            f"0分と30分を除いた記録{tot['other']:,}件のうち、5の倍数の分は{tot['other5']:,}件({f(other5_share)})です。0分と30分を除いても、全分に同じ割合なら約{f(exp_m5_other)}ですから、15分刻みや10分刻みの分も多く使われています。"],
             "table": {"head": ["月", "記録の数", "0分", "5の倍数の分"], "rows": month_rows, "note": "記録が100件以上ある月のみ。4県を合わせた数字です。"}},
            {"h2": "「何時台」で数えるとき、どれくらいずれうるか",
             "paragraphs": ["記録の時刻を「何時台」で数えれば、6時台の件数が分かります。ただし、時刻を丸めて報告する人が多いと、本当は5時50分に見た熊が6時0分と報告されて、1つ後の時間台に入ります。",
                            f"ちょうど0分の記録は{tot['z']:,}件で、全体の{f(share(tot['z'], n))}です。0分は時間台の境目に当たるので、丸めの影響をいちばん受けやすい記録です。たとえば「6時」と報告された記録は、実際には5時台の終わりだったかもしれませんし、6時台の始めだったかもしれません。",
                            f"分が30分から59分の記録は全体の{f(late_share)}で、約半分です。時間台ごとの件数の大まかな形は、この丸めがあっても、読み取れると考えています。ただし、この研究ノートでは、丸めを直した場合の時間台ごとの件数を計算していません。",
                            "熊の目撃が多い時間帯を知りたいときは、「何時台」をおよその目安として読み、「15分以内」などの細かい差には使わないのが無難です。"]},
            {"h2": "このデータを使うときの目安",
             "paragraphs": ["自治体が発表する熊の記録を読むとき、時刻は「何時台」までを目安にするのが安全側です。たとえば「朝6時台の記録が多い」は読み取れますが、「6時15分と6時20分のどちらが先か」は、この記録からは分かりません。",
                            "この研究ノートの時間帯の数字(別のノートの「何時ごろに報告されているか」「日没後の記録の割合」)も、時間台や日没の前後の大まかな割合として読んでください。日没の時刻に近い記録は、丸めの影響で前後が入れ替わっている可能性があります。",
                            "お住まいの地域の情報を、自治体の発表で確かめるときは、時刻が「ごろ」であることを頭に入れておくと、読み違いが減ります。"]},
            {"h2": "この数え方から、何が言えて何が言えないか",
             "paragraphs": [f"言えるのは、4県の記録の時刻が、0分・30分・5の倍数の分に大きく偏っていることです。0分が{f1(share(tot['z'], n))}、5の倍数の分が{f(share(tot['m5'], n))}でした。",
                            "言えないのは、丸めがどの段階で起きたかです。報告した人が時計を見て答えたのか、受け付けた人が書き留めたのか、公表資料に載せるときに丸めたのかは、この記録からは分かりません。また、丸めた分の方向(早めに寄せたか遅めに寄せたか)も分かりません。",
                            "この記録の時刻は、「その時刻ごろ」と受け取ってください。1分や2分の差で、出没の前後関係を決めることはできません。"]},
        ],
        "method": [
            f"対象は、令和8年度(2026年4月1日から)の記録のうち、日付だけでなく時刻まで記録のある秋田・宮城・山口・山梨の4県です。計算した日は{today}、使った記録の最新日は{as_of}です。",
            "「分」は、記録の時刻の0〜59の数字です。0分、30分、5の倍数の分(0・5・10…55の12通り)、10の倍数の分(0・10…50の6通り)の割合を数えました。",
            "時間帯は記録の「時」(0〜23)で、8時台まで・9〜11時台・12〜14時台・15〜17時台・18時台以降の5つに分けました。宮城県の0時台と12時台の入力の癖(別のノートで書いたもの)は、このノートでは除外していません。",
            "どの分も同じ割合なら、0分と30分は1/60=1.7%、5の倍数の分は12/60=20%、10の倍数の分は6/60=10%になります。",
            "計算のスクリプトは公開しています。数字はすべてスクリプトが出しています。",
        ],
        "caveats": [
            "これは報告された記録の時刻です。熊が実際に現れた時刻を直接示すものではありません。",
            "丸めがどこで起きたかは分かりません。県によって、報告の受け方・記録の書き方が違う可能性があります。",
            "時刻のある4県だけで、新潟県・富山県などは日付だけのため入っていません。",
            "1年度分(令和8年度)だけです。ほかの年に同じ形になるかは、この記録だけでは言えません。",
        ],
        "credits": [data[k]["credit"] for k in SOURCES],
        "script": "sites/kuma/research/scripts/round-minutes.py",
        "related": [{"label": "熊の目撃は何時ごろに報告されているか", "href": "/research/hour-of-day/"}, {"label": "日没後に報告された記録の割合", "href": "/research/after-sunset/"},
                    {"label": "秋田県の最新の目撃情報", "href": "/live/akita/"}, {"label": "週ごとのまとめ", "href": "/digest/"},
                    {"label": "クマに出会わないために(対処法)", "href": "/guide/"}],
    }
    common.write_note(doc)


main()
