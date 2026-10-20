"""What is particular about one prefecture's minimum wage, as sentences that are written only when they are true of that prefecture.

Every sentence below is chosen by a computed fact (a rank that moved, a neighbour that is higher, a date that is the latest in the country ...); a prefecture
for which a fact does not hold gets no sentence for it.  Nothing is filled in with a number swapped into the same wording.  Numbers come from long_history
(the Ministry's 2003 document joined to the current workbook) and the current workbook; the neighbours from adjacency.py.
"""
from __future__ import annotations

import math
from datetime import date

from sites.saichin.adjacency import NEIGHBOURS
from sites.saichin.long_history import yen_text


def _name_list(rows: list[dict], k) -> str:
    return "、".join(f'<a href="/{x["slug"]}/">{k.esc(x["name"])}</a>' for x in rows)


def _ordinal_in_region(d: dict, r: dict) -> tuple[int, int, list[dict]]:
    mates = sorted((x for x in d["rows"] if x["region_slug"] == r["region_slug"]), key=lambda x: (-x["amount"], x["name"]))
    pos = 1 + sum(1 for x in mates if x["amount"] > r["amount"])
    return pos, len(mates), mates


# ---------------------------------------------------------------- the families of sentences
def rank_story(d: dict, r: dict, k) -> list[str]:
    s = [e for e in r["long"] if e["rank"] is not None]
    last = s[-1]
    ten = next((e for e in s if e["fy"] == last["fy"] - 10), None)
    first = s[0]
    best, worst = min(e["rank"] for e in s), max(e["rank"] for e in s)
    out = []
    if best == worst:
        return [f"全国順位は、{k.esc(first['label'])}から{k.esc(last['label'])}まで、ずっと{best}位です。"]
    if last["rank"] == best:
        out.append(f"{k.esc(last['label'])}の{last['rank']}位は、{k.esc(first['label'])}以降で最も高い順位です。")
    elif last["rank"] == worst:
        out.append(f"{k.esc(last['label'])}の{last['rank']}位は、{k.esc(first['label'])}以降で最も低い順位です。")
    if ten:
        diff = ten["rank"] - last["rank"]
        if diff >= 3:
            out.append(f"10年前の{k.esc(ten['label'])}は{ten['rank']}位でした。{diff}位上がっています。")
        elif diff <= -3:
            out.append(f"10年前の{k.esc(ten['label'])}は{ten['rank']}位でした。{-diff}位下がっています。")
        else:
            out.append(f"10年前の{k.esc(ten['label'])}も{ten['rank']}位で、順位はほとんど動いていません。")
    diff0 = first["rank"] - last["rank"]
    if diff0 >= 6:
        out.append(f"{k.esc(first['label'])}の{first['rank']}位からは、{diff0}位上がりました。")
    elif diff0 <= -6:
        out.append(f"{k.esc(first['label'])}の{first['rank']}位からは、{-diff0}位下がりました。")
    # a lead that was lost or won: the years the prefecture held the best / worst rank of its series
    if len(out) == 1 and best != last["rank"] and worst != last["rank"]:
        years = [e["label"] for e in s if e["rank"] == best]
        out.append(f"これまでで最も高かったのは{best}位({k.esc(years[0])}{'など' if len(years) > 1 else ''})です。")
    return out


def average_story(d: dict, r: dict, k) -> list[str]:
    gaps = [(e["fy"], e["label"], e["avg_gap"]) for e in r["long"] if e["avg_gap"] is not None]
    cur = gaps[-1][2]
    sign = lambda v: (v > 0) - (v < 0)  # noqa: E731
    above = sum(1 for _, _, g in gaps if g > 0)
    below = sum(1 for _, _, g in gaps if g < 0)
    if above == 0 and below == 0:
        return []
    if below == 0:
        return [f"全国加重平均を下回った年度は、{k.esc(gaps[0][1])}から一度もありません。"]
    if above == 0:
        return [f"全国加重平均を上回った年度は、{k.esc(gaps[0][1])}から一度もありません。"]
    cur_sign = sign(cur)
    if cur_sign == 0:
        return [f"{k.esc(d['label'])}は全国加重平均と同じ額です。"]
    flip = next((i for i in range(len(gaps) - 1, -1, -1) if sign(gaps[i][2]) != cur_sign and sign(gaps[i][2]) != 0), None)
    word = "上回る" if cur_sign > 0 else "下回る"
    other = "下回って" if cur_sign > 0 else "上回って"
    if flip is None:
        return []
    start = gaps[flip + 1] if flip + 1 < len(gaps) else gaps[-1]
    run = len(gaps) - 1 - flip
    out = [f"全国加重平均を{word}状態は、{k.esc(start[1])}から{run}年度続いています(その前の{k.esc(gaps[flip][1])}は{other}いました)。"]
    out.append(f"これまでに全国加重平均を上回った年度は{above}、下回った年度は{below}です。")
    return out


def neighbour_story(d: dict, r: dict, k) -> list[str]:
    near = [x for x in d["rows"] if x["short"] in NEIGHBOURS[r["short"]]]
    if not near:
        return [f"{k.esc(r['name'])}は、陸続きで接する都道府県がありません。通勤で県境をまたぐ場合の比べ方は、ここでは扱いません。"]
    higher = sorted((x for x in near if x["amount"] > r["amount"]), key=lambda x: (-x["amount"], x["name"]))
    lower = sorted((x for x in near if x["amount"] < r["amount"]), key=lambda x: (-x["amount"], x["name"]))
    same = [x for x in near if x["amount"] == r["amount"]]
    n = len(near)
    out = []
    if not higher and not same:
        top = lower[0]
        out.append(f"接する{n}都道府県は、どこも{k.esc(r['name'])}より低い額です。最も近いのは{_name_list([top], k)}で、{r['amount'] - top['amount']}円の差です。")
    elif not lower and not same:
        low = higher[-1]
        out.append(f"接する{n}都道府県は、どこも{k.esc(r['name'])}より高い額です。最も近いのは{_name_list([low], k)}で、{low['amount'] - r['amount']}円の差です。")
    else:
        parts = []
        if higher:
            parts.append(f"高いのは{_name_list(higher, k)}(最大{higher[0]['amount'] - r['amount']}円差)")
        if same:
            parts.append(f"同額なのは{_name_list(same, k)}")
        if lower:
            parts.append(f"低いのは{_name_list(lower, k)}(最大{r['amount'] - lower[-1]['amount']}円差)")
        out.append(f"接する{n}都道府県のうち、" + "、".join(parts) + "です。")
    return out


def milestone_story(d: dict, r: dict, k) -> list[str]:
    out = []
    amount = r["amount"]
    nxt = (amount // 100 + 1) * 100
    reached = []
    for t in (1000, 1100, 1200):
        mine = next((e for e in r["long"] if e["amount"] is not None and e["amount"] >= t), None)
        if mine:
            reached.append((t, mine["label"]))
    if reached:
        t, label = reached[-1]
        out.append(f"{t:,}円以上になったのは{k.esc(label)}です。")
    else:
        out.append("1,000円には、まだ届いていません。")
    if amount % 100:
        out.append(f"次の節目の{nxt:,}円まで、あと{nxt - amount}円です。")
    return out


def raise_story(d: dict, r: dict, k) -> list[str]:
    avg = {y["fy"]: y["avg"] for y in d["years"]}
    fy = d["rows"][0]["history"][-1]["fy"]
    mine = r["raise"]
    nat = round(avg[fy]) - round(avg[fy - 1])
    out = []
    if mine > nat:
        out.append(f"{k.esc(d['label'])}の引上げ額+{mine}円は、全国加重平均の+{nat}円より{mine - nat}円大きく、47都道府県中{r['raise_rank']}位です。")
    elif mine < nat:
        out.append(f"{k.esc(d['label'])}の引上げ額+{mine}円は、全国加重平均の+{nat}円より{nat - mine}円小さく、47都道府県中{r['raise_rank']}位です。")
    else:
        out.append(f"{k.esc(d['label'])}の引上げ額+{mine}円は、全国加重平均の+{nat}円と同じです。")
    three = [e for e in r["long"][-3:]]
    sum3 = sum(e["raise"] for e in three if e["raise"] is not None)
    sum3_nat = sum(round(avg[e["fy"]]) - round(avg[e["fy"] - 1]) for e in three)
    if sum3 != sum3_nat:
        out.append(f"{k.esc(three[0]['label'])}からの3年度では、合わせて+{sum3}円で、全国加重平均の+{sum3_nat}円より{'大きく' if sum3 > sum3_nat else '小さく'}なっています。")
    return out


def date_story(d: dict, r: dict, k) -> list[str]:
    cur = date.fromisoformat(r["effective_date"])
    all_dates = sorted(date.fromisoformat(x["effective_date"]) for x in d["rows"])
    same = sum(1 for x in all_dates if x == cur)
    earlier = sum(1 for x in all_dates if x < cur)
    later = sum(1 for x in all_dates if x > cur)
    out = []
    first_day = all_dates[0]
    if cur == first_day and same > 1:
        out.append(f"{k.esc(d['label'])}の発効日の{k.jp_date(cur.isoformat())}は、全国で最も早い日で、{same}都道府県が同じ日です。")
    elif cur == first_day:
        out.append(f"{k.esc(d['label'])}の発効日の{k.jp_date(cur.isoformat())}は、全国で最も早い日です。")
    elif later == 0:
        second = max(x for x in all_dates if x < cur)
        out.append(f"{k.esc(d['label'])}の発効日の{k.jp_date(cur.isoformat())}は、全国で最も遅い日です(次に遅い日は{k.jp_date(second.isoformat())})。")
    else:
        out.append(f"{k.esc(d['label'])}の発効日の{k.jp_date(cur.isoformat())}は、早い方から数えて{earlier + 1}番目の日です。{later}都道府県は、これより遅く発効します。")
    hist = [e for e in r["history"] if e["raise"] and e["effective_date"] and e["fy"] < r["history"][-1]["fy"]][-10:]
    if len(hist) >= 5:
        oct1 = sum(1 for e in hist if date.fromisoformat(e["effective_date"]) <= date(e["fy"], 10, 1))
        spread = sorted(date.fromisoformat(e["effective_date"]) for e in hist)
        if oct1 == len(hist):
            out.append(f"直近{len(hist)}回の改定は、すべて10月1日までに発効しています。")
        elif oct1 == 0:
            out.append(f"直近{len(hist)}回の改定は、10月1日に発効した年度がなく、日付は年度ごとに動いています。")
        else:
            out.append(f"直近{len(hist)}回の改定のうち、10月1日までに発効したのは{oct1}回です。")
    return out


def region_story(d: dict, r: dict, k) -> list[str]:
    pos, n, mates = _ordinal_in_region(d, r)
    if pos == 1:
        second = mates[1]
        return [f"{k.esc(r['region'])}の{n}都道府県の中では最も高く、2番目の{_name_list([second], k)}との差は{r['amount'] - second['amount']}円です。"]
    if pos == n:
        above = mates[-2]
        return [f"{k.esc(r['region'])}の{n}都道府県の中では最も低く、1つ上の{_name_list([above], k)}との差は{above['amount'] - r['amount']}円です。"]
    return [f"{k.esc(r['region'])}の{n}都道府県の中では、高い方から{pos}番目です。"]


def special_story(d: dict, r: dict, k) -> list[str]:
    out = []
    zero = [e for e in r["long"][1:] if e["raise"] == 0]
    if zero:
        out.append(f"前の年度と同じ額だったのは、{k.esc(zero[0]['label'])}" + (f"など{len(zero)}回です。" if len(zero) > 1 else "だけです。"))
    if any(e["amount"] is None for e in r["long"]):
        out.append("昭和54年度から平成元年度までは、南部と北部で額が分かれていました。この期間の表は、2つの額を並べています。")
    frac = [e for e in r["long"] if e["amount"] is not None and e["amount"] != int(e["amount"])]
    if frac:
        out.append(f"{k.esc(frac[0]['label'])}などの額に小数があるのは、出典の表のとおりです。")
    return out


def monthly_line(d: dict, r: dict, k) -> str:
    low = math.ceil(r["amount"] * 8 * 250 / 12 / 100) * 100
    hours130 = 1_300_000 / (52 * r["amount"])
    a20 = r["amount"] * 20 * 52
    frame = (f"週20時間でも年収が130万円を超えます({a20 / 10000:.1f}万円)" if a20 > 1_300_000
             else f"年収が130万円になるのは週{hours130:.1f}時間です(週20時間では{a20 / 10000:.1f}万円)")
    return (f"月給の求人は、1日8時間・年250日の勤務なら、手当を除いた月給が{low:,}円を下回ると、最低賃金を下回ります。"
            f"最低賃金で働く場合、{frame}。")


def band_story(d: dict, r: dict, k) -> list[str]:
    rank = r["rank"]
    if rank <= 5:
        return [f"{rank}位は、全国の上位5都道府県に入る高さです。"]
    if rank <= 15:
        return [f"{rank}位は、全国の上位3分の1にあたります。"]
    if rank <= 31:
        return [f"{rank}位は、全国のちょうど真ん中のあたりです。"]
    if rank <= 42:
        return [f"{rank}位は、全国の下位3分の1にあたります。"]
    return [f"{rank}位は、全国の下位5都道府県に入る低さです。"]


def top_gap_story(d: dict, r: dict, k) -> list[str]:
    hi = max(x["amount"] for x in d["rows"])
    lo = min(x["amount"] for x in d["rows"])
    if r["amount"] == hi:
        second = sorted({x["amount"] for x in d["rows"]})[-2]
        return [f"全国で最も高い額で、2番目の額との差は{hi - second}円です。"]
    if r["amount"] == lo:
        second = sorted({x["amount"] for x in d["rows"]})[1]
        return [f"全国で最も低い額で、2番目に低い額との差は{second - lo}円です。"]
    share = r["amount"] / hi * 100
    if share >= 95:
        return [f"最も高い額の{share:.1f}%にあたり、差は{hi - r['amount']}円と小さくなっています。"]
    if share >= 88:
        return [f"最も高い額の{share:.1f}%にあたり、最高額と最低額の間では、上から{(hi - r['amount']) * 100 // (hi - lo)}%の位置です。"]
    return [f"最も高い額の{share:.1f}%にとどまり、差は{hi - r['amount']}円です。"]


def recent_story(d: dict, r: dict, k) -> list[str]:
    avg = {y["fy"]: y["avg"] for y in d["years"]}
    last3 = r["long"][-3:]
    above = [e for e in last3 if e["raise"] is not None and e["raise"] > round(avg[e["fy"]]) - round(avg[e["fy"] - 1])]
    below = [e for e in last3 if e["raise"] is not None and e["raise"] < round(avg[e["fy"]]) - round(avg[e["fy"] - 1])]
    if len(above) == 3:
        return ["直近3回は、3回とも全国加重平均の引上げ額を上回りました。"]
    if len(below) == 3:
        return ["直近3回は、3回とも全国加重平均の引上げ額を下回りました。"]
    if above and not below:
        return [f"直近3回のうち、全国加重平均の引上げ額を上回ったのは{k.esc(above[0]['label'])}などの{len(above)}回で、残りは同じ額でした。"]
    if below and not above:
        return [f"直近3回のうち、全国加重平均の引上げ額を下回ったのは{len(below)}回で、残りは同じ額でした。"]
    return [f"直近3回は、上回った年度が{len(above)}回、下回った年度が{len(below)}回と、全国加重平均の引上げ額との大小が入れ替わっています。"]


def era_story(d: dict, r: dict, k) -> list[str]:
    by = {e["fy"]: e["amount"] for e in r["long"] if e["amount"] is not None}
    if 1989 not in by or 2018 not in by:
        return []
    heisei = by[2018] - by[1989]
    reiwa = by[r["long"][-1]["fy"]] - by[2018]
    base = f"平成(元〜30年度)の上がり額は+{heisei:,}円、令和(元〜{r['long'][-1]['fy'] - 2018}年度)は+{reiwa:,}円です。"
    if reiwa > heisei:
        return [base + "令和のほうが大きく上がっています。"]
    return [base]

# ---------------------------------------------------------------- the block
def story_block(d: dict, r: dict, k) -> str:
    sections = [
        ("順位の歩み", band_story(d, r, k) + rank_story(d, r, k) + average_story(d, r, k)),
        ("隣の都道府県と比べると", neighbour_story(d, r, k) + region_story(d, r, k) + top_gap_story(d, r, k)),
        ("節目と引上げ", milestone_story(d, r, k) + raise_story(d, r, k) + recent_story(d, r, k) + era_story(d, r, k)),
        ("発効日", date_story(d, r, k)),
    ]
    special = special_story(d, r, k)
    if special:
        sections.append(("この都道府県の表を読むときの注意", special))
    parts = [f"<h2>{k.esc(r['name'])}の最低賃金の特徴</h2>"]
    for head, sentences in sections:
        if sentences:
            parts.append(f"<h3>{head}</h3>\n<p>{''.join(sentences)}</p>")
    return "\n".join(parts) + "\n"
