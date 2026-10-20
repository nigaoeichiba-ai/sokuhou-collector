"""What is particular about one prefecture's minimum wage, as sentences that are written only when they are true of that prefecture.

Every sentence below is chosen by a computed fact (a rank that moved, a neighbour that is higher, a date that is the latest in the country ...); a prefecture
for which a fact does not hold gets no sentence for it.  Nothing is filled in with a number swapped into the same wording.  Numbers come from long_history
(the Ministry's 2003 document joined to the current workbook) and the current workbook; the neighbours from adjacency.py.
"""
from __future__ import annotations

import math
from datetime import date

from sites.saichin.adjacency import NEIGHBOURS
from sites.saichin.articles import GUIDELINE, RANK_OF
from sites.saichin.places import PLACES
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
        was = f"10年前の{k.esc(ten['label'])}は{ten['rank']}位でした。"
        if diff >= 8:
            out.append(f"{was}この10年で、{diff}位も上がっています。")
        elif diff >= 3:
            out.append(f"{was}{diff}位上がっています。")
        elif diff >= 1:
            out.append(f"{was}{diff}位だけ上がりました。")
        elif diff == 0:
            out.append(f"10年前の{k.esc(ten['label'])}も{ten['rank']}位で、順位は同じです。")
        elif diff > -3:
            out.append(f"{was}{-diff}位だけ下がりました。")
        elif diff > -8:
            out.append(f"{was}{-diff}位下がっています。")
        else:
            out.append(f"{was}この10年で、{-diff}位も下がっています。")
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
    if below == 0 or above == 0:
        word = "下回った" if below == 0 else "上回った"
        out = [f"全国加重平均を{word}年度は、{k.esc(gaps[0][1])}から一度もありません。"]
        ten = next((g for g in gaps if g[0] == gaps[-1][0] - 10), None)
        if ten is not None and ten[2] != 0 and cur != 0:
            g0, g1 = abs(ten[2]), abs(cur)
            side = "上" if cur > 0 else "下"
            if g1 < g0 * 0.7:
                out.append(f"全国加重平均との差は、{k.esc(ten[1])}の{g0:g}円から{g1:g}円に縮まり、{side}側から近づいています。")
            elif g1 > g0 * 1.3:
                out.append(f"全国加重平均との差は、{k.esc(ten[1])}の{g0:g}円から{g1:g}円に広がっています。")
        return out
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
    rr = r["raise_rank"]
    place = ("上位5位以内" if rr <= 5 else "上から3分の1の中" if rr <= 15 else "ちょうど真ん中のあたり" if rr <= 31 else "下から3分の1の中" if rr <= 42 else "下位5位以内")
    out = []
    diff = mine - nat
    if diff == 0:
        out.append(f"{k.esc(d['label'])}の引上げ額+{mine}円は、全国加重平均の+{nat}円と同じで、47都道府県中{rr}位({place})です。")
    else:
        size = "大きく" if abs(diff) >= 10 else ("" if abs(diff) >= 3 else "わずかに")
        word = "上回り" if diff > 0 else "下回り"
        out.append(f"{k.esc(d['label'])}の引上げ額+{mine}円は、全国加重平均の+{nat}円を{size}{word}、47都道府県中{rr}位({place})です。")
    three = [e for e in r["long"][-3:]]
    sum3 = sum(e["raise"] for e in three if e["raise"] is not None)
    sum3_nat = sum(round(avg[e["fy"]]) - round(avg[e["fy"] - 1]) for e in three)
    if sum3 != sum3_nat:
        d3 = abs(sum3 - sum3_nat)
        size3 = "大きく" if d3 >= 15 else ("" if d3 >= 5 else "わずかに")
        out.append(f"{k.esc(three[0]['label'])}からの3年度では、合わせて+{sum3}円で、全国加重平均の+{sum3_nat}円を{size3}{'上回っています' if sum3 > sum3_nat else '下回っています'}。")
    return out


WEEKDAYS = "月火水木金土日"


def date_story(d: dict, r: dict, k) -> list[str]:
    cur = date.fromisoformat(r["effective_date"])
    all_dates = sorted(date.fromisoformat(x["effective_date"]) for x in d["rows"])
    same = sum(1 for x in all_dates if x == cur)
    earlier = sum(1 for x in all_dates if x < cur)
    later = sum(1 for x in all_dates if x > cur)
    out = []
    first_day = all_dates[0]
    day = f"{k.jp_date(cur.isoformat())}({WEEKDAYS[cur.weekday()]}曜日)"
    part = "月の初め" if cur.day <= 7 else ("月の中ごろ" if cur.day <= 21 else "月末に近い日")
    if cur == first_day and same > 1:
        out.append(f"{k.esc(d['label'])}の発効日の{day}は、全国で最も早い日で、{same}都道府県が同じ日です。")
    elif cur == first_day:
        out.append(f"{k.esc(d['label'])}の発効日の{day}は、全国で最も早い日です。")
    elif later == 0:
        second = max(x for x in all_dates if x < cur)
        out.append(f"{k.esc(d['label'])}の発効日の{day}は、全国で最も遅い日です(次に遅い日は{k.jp_date(second.isoformat())})。")
    else:
        out.append(f"{k.esc(d['label'])}の発効日の{day}は、{part}で、早い方から数えて{earlier + 1}番目の日です。{later}都道府県は、これより遅く発効します。")
    hist = [e for e in r["history"] if e["raise"] and e["effective_date"] and e["fy"] < r["history"][-1]["fy"]][-10:]
    if len(hist) >= 5:
        oct1 = sum(1 for e in hist if date.fromisoformat(e["effective_date"]) <= date(e["fy"], 10, 1))
        if oct1 == len(hist):
            out.append(f"直近{len(hist)}回の改定は、すべて10月1日までに発効しています。")
        elif oct1 == 0:
            out.append(f"直近{len(hist)}回の改定は、10月1日に発効した年度がなく、日付は年度ごとに動いています。")
        elif oct1 * 2 > len(hist):
            out.append(f"直近{len(hist)}回の改定のうち、10月1日までに発効したのは{oct1}回で、半分を超えます。")
        else:
            out.append(f"直近{len(hist)}回の改定のうち、10月1日までに発効したのは{oct1}回だけです。")
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


def monthly_table(d: dict, r: dict, k) -> str:
    low = math.ceil(r["amount"] * 8 * 250 / 12 / 100) * 100
    hours130 = 1_300_000 / (52 * r["amount"])
    a20 = r["amount"] * 20 * 52
    frame = (f"週20時間でも年収が130万円を超えます({a20 / 10000:.1f}万円)" if a20 > 1_300_000
             else f"週{hours130:.1f}時間(週20時間では{a20 / 10000:.1f}万円)")
    return ('<div class="tablewrap"><table><thead><tr><th>項目</th><th>目安</th></tr></thead><tbody>'
            f'<tr><th scope="row">月給の下限(1日8時間・年250日。手当を除く)</th><td>{low:,}円</td></tr>'
            f'<tr><th scope="row">最低賃金で働いて、年収が130万円になる週の労働時間</th><td>{frame}</td></tr>'
            '</tbody></table></div>')


def band_story(d: dict, r: dict, k) -> list[str]:
    rank = r["rank"]
    if rank == 1:
        return [f"{rank}位は、47都道府県の先頭です。"]
    if rank <= 5:
        return [f"{rank}位は、全国の上位5都道府県に入る高さです。"]
    if rank <= 10:
        return [f"{rank}位は、上から10番目までに入ります。"]
    if rank <= 15:
        return [f"{rank}位は、全国の上位3分の1にあたります。"]
    if rank <= 23:
        return [f"{rank}位は、真ん中より少し上です。"]
    if rank == 24:
        return [f"{rank}位は、47都道府県のちょうど真ん中です。"]
    if rank <= 31:
        return [f"{rank}位は、真ん中より少し下です。"]
    if rank <= 37:
        return [f"{rank}位は、全国の下位3分の1にあたります。"]
    if rank <= 42:
        return [f"{rank}位は、下から10番目までに入ります。"]
    if rank <= 46:
        return [f"{rank}位は、全国の下位5都道府県に入る低さです。"]
    return [f"{rank}位は、47都道府県の最後です。"]


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

def _amounts(x: dict) -> dict[int, float]:
    return {e["fy"]: e["amount"] for e in x["long"] if e["amount"] is not None}


def _near(d: dict, r: dict) -> list[dict]:
    return [x for x in d["rows"] if x["short"] in NEIGHBOURS[r["short"]]]


def swap_story(d: dict, r: dict, k) -> list[str]:
    """The land neighbour with which the order of the two amounts changed most recently, and the last year it stood the other way."""
    mine = _amounts(r)
    found = []
    for x in _near(d, r):
        theirs = _amounts(x)
        years = sorted(set(mine) & set(theirs))
        sign = lambda y: (mine[y] > theirs[y]) - (mine[y] < theirs[y])  # noqa: E731
        cur = sign(years[-1])
        if cur == 0:
            continue
        flip = next((y for y in reversed(years) if sign(y) == -cur), None)
        if flip is not None:
            found.append((flip, x, cur))
    if not found:
        return []
    flip, x, cur = max(found, key=lambda t: (t[0], t[1]["name"]))
    label = next(e["label"] for e in r["long"] if e["fy"] == flip)
    link = _name_list([x], k)
    if cur > 0:
        return [f"{link}より低かった最後の年度は{k.esc(label)}で、その後は同額か、{link}より高い額です。"]
    return [f"{link}より高かった最後の年度は{k.esc(label)}で、その後は同額か、{link}より低い額です。"]


def gap_story(d: dict, r: dict, k) -> list[str]:
    """How the gap to the nearest land neighbour above (else below) has moved in ten years; nothing if the order changed (swap_story tells that)."""
    near = _near(d, r)
    higher = sorted((x for x in near if x["amount"] > r["amount"]), key=lambda x: (x["amount"], x["name"]))
    lower = sorted((x for x in near if x["amount"] < r["amount"]), key=lambda x: (-x["amount"], x["name"]))
    if higher:
        x, side = higher[0], "上"
    elif lower:
        x, side = lower[0], "下"
    else:
        return []
    last_fy = r["long"][-1]["fy"]
    mine, theirs = _amounts(r), _amounts(x)
    ten = last_fy - 10
    if ten not in mine or ten not in theirs:
        return []
    g0, g1 = abs(theirs[ten] - mine[ten]), abs(theirs[last_fy] - mine[last_fy])
    if (theirs[ten] > mine[ten]) != (theirs[last_fy] > mine[last_fy]) or g0 == 0 or g1 == 0:
        return []
    label = next(e["label"] for e in r["long"] if e["fy"] == ten)
    link = _name_list([x], k)
    if g1 < g0:
        move = f"{g0:g}円から{g1:g}円に縮まりました"
    elif g1 > g0:
        move = f"{g0:g}円から{g1:g}円に広がりました"
    else:
        move = f"{g0:g}円のまま変わっていません"
    return [f"最も近い{side}の{link}との差は、{k.esc(label)}の{move}。"]


def guideline_story(d: dict, r: dict, k) -> list[str]:
    """Reiwa 8 only: the prefecture's rank in the Ministry's guideline and its rise against the guideline (the figures of the two press releases)."""
    if r["long"][-1]["fy"] != 2026 or r["short"] not in RANK_OF:
        return []
    rank = RANK_OF[r["short"]]
    guide = GUIDELINE[rank]
    got = r["raise"]
    mates = [x for x in d["rows"] if RANK_OF[x["short"]] == rank]
    n = len(mates)
    if got == guide:
        return [f"{k.esc(d['label'])}の目安は{rank}ランクの+{guide}円で、決まった引上げ額は目安と同じです。"]
    over = got - guide
    pos = 1 + sum(1 for x in mates if x["raise"] - guide > over)
    if pos == 1:
        tail = f"同じ{rank}ランクの{n}都道府県の中で、上乗せが最も大きい県です。"
    else:
        tail = f"同じ{rank}ランクの{n}都道府県の中では、上乗せが大きい方から{pos}番目です。"
    return [f"{k.esc(d['label'])}の目安は{rank}ランクの+{guide}円で、決まった額は目安より{over}円多い+{got}円です。" + tail]


def count_story(d: dict, r: dict, k) -> list[str]:
    """In the last ten revisions: how often the rise reached the national weighted average's rise, and how often it was +50 yen or more.  Only the notable counts are written."""
    avg = {y["fy"]: y["avg"] for y in d["years"]}
    last = [e for e in r["long"][-10:] if e["raise"] is not None]
    if len(last) < 10:
        return []
    nat = lambda e: round(avg[e["fy"]]) - round(avg[e["fy"] - 1])  # noqa: E731
    reach = sum(1 for e in last if e["raise"] >= nat(e))
    out = []
    if reach == 0:
        out.append("直近10回の改定で、引上げ額が全国加重平均の引上げ額に届いた年度は、一度もありません。")
    elif reach <= 2:
        out.append(f"直近10回の改定のうち、引上げ額が全国加重平均の引上げ額以上だったのは{reach}回だけです。")
    elif reach == 10:
        out.append("直近10回の改定は、すべて全国加重平均の引上げ額以上でした。")
    elif reach >= 8:
        out.append(f"直近10回の改定のうち{reach}回は、引上げ額が全国加重平均の引上げ額以上でした。")
    big = [e for e in last if e["raise"] >= 50]
    if not big:
        out.append("+50円以上の引上げは、直近10回の改定では一度もありません。")
    elif len(big) == 1:
        out.append(f"+50円以上の引上げは、直近10回では{k.esc(big[0]['label'])}の1回だけです。")
    elif len(big) >= 4:
        out.append(f"+50円以上の引上げは、直近10回のうち{len(big)}回あり、最初は{k.esc(big[0]['label'])}です。")
    return out


def tie_story(d: dict, r: dict, k) -> list[str]:
    same = sorted((x for x in d["rows"] if x["amount"] == r["amount"] and x is not r), key=lambda x: x["name"])
    if not same:
        return []
    return [f"{r['amount']:,}円は、{_name_list(same, k)}と同じ額です。"]


def rank_move_story(d: dict, r: dict, k) -> list[str]:
    """The one-year step in which the rank moved most (4 places or more)."""
    s = [e for e in r["long"] if e["rank"] is not None]
    best = None
    for a, b in zip(s, s[1:]):
        if b["fy"] - a["fy"] != 1:
            continue
        move = a["rank"] - b["rank"]
        if best is None or abs(move) > abs(best[0]):
            best = (move, b, a)
    if best is None or abs(best[0]) < 4:
        return []
    move, b, a = best
    word = "上がりました" if move > 0 else "下がりました"
    return [f"1年で順位が最も大きく動いたのは{k.esc(b['label'])}で、{a['rank']}位から{b['rank']}位に{word}。"]


def lead_diff(d: dict, r: dict, k) -> str:
    """The second sentence under the title: where the new amount stands against the national weighted average."""
    diff = r["amount"] - round(d["avg"])
    avg = f"(全国加重平均 {k.yen(round(d['avg']))})"
    name = k.esc(r["name"])
    if diff == 0:
        return f"{name}の額は、全国加重平均と同じ額です{avg}。"
    size = abs(diff)
    word = "高い" if diff > 0 else "低い"
    if size <= 5:
        return f"{name}の額は、全国加重平均とほぼ同じ水準で、{size}円{word}額です{avg}。"
    if size >= 100:
        return f"{name}の額は、全国加重平均より{size}円も{word}額です{avg}。"
    if size >= 40:
        return f"{name}の額は、全国加重平均より{size}円{word}、差の大きい水準です{avg}。"
    return f"{name}の額は、全国加重平均より{size}円{word}額です{avg}。"


def era_rank_story(d: dict, r: dict, k) -> list[str]:
    """How the rank moved in each era (Showa 52 to Heisei 1, Heisei, Reiwa); 'about the same' within two places."""
    by = {e["fy"]: e["rank"] for e in r["long"] if e["rank"] is not None}
    last = r["long"][-1]["fy"]
    if not all(y in by for y in (1977, 1989, 2018, last)):
        return []

    def move(a: int, b: int) -> str:
        diff = by[a] - by[b]
        if abs(diff) <= 2:
            return "ほぼ横ばい"
        return f"{abs(diff)}位の{'上昇' if diff > 0 else '下落'}"

    return [f"順位の動きを時代で分けると、昭和は{move(1977, 1989)}、平成は{move(1989, 2018)}、令和は{move(2018, last)}です。"]


def overtake_story(d: dict, r: dict, k) -> list[str]:
    """In ten years: how many prefectures this one overtook, and how many overtook it (strictly above at one end, strictly below at the other)."""
    last = r["long"][-1]["fy"]
    ten = last - 10
    mine = _amounts(r)
    up = down = 0
    for x in d["rows"]:
        if x is r:
            continue
        theirs = _amounts(x)
        if ten not in mine or ten not in theirs:
            continue
        if mine[ten] < theirs[ten] and mine[last] > theirs[last]:
            up += 1
        elif mine[ten] > theirs[ten] and mine[last] < theirs[last]:
            down += 1
    if up == 0 and down == 0:
        return []
    if down == 0:
        return [f"この10年で、{up}都道府県を追い越しました。追い越された都道府県はありません。"]
    if up == 0:
        return [f"この10年で、{down}都道府県に追い越されました。追い越した都道府県はありません。"]
    return [f"この10年で、{up}都道府県を追い越し、{down}都道府県に追い越されました。"]


def region_history_story(d: dict, r: dict, k) -> list[str]:
    """The place among the prefectures of its region, now and ten years ago."""
    last = r["long"][-1]["fy"]
    ten = last - 10
    mates = [x for x in d["rows"] if x["region_slug"] == r["region_slug"]]
    now = {x["name"]: _amounts(x).get(last) for x in mates}
    then = {x["name"]: _amounts(x).get(ten) for x in mates}
    if any(v is None for v in list(now.values()) + list(then.values())):
        return []
    p1 = 1 + sum(1 for v in now.values() if v > now[r["name"]])
    p0 = 1 + sum(1 for v in then.values() if v > then[r["name"]])
    label = next(e["label"] for e in r["long"] if e["fy"] == ten)
    n = len(mates)
    if p1 < p0:
        return [f"{k.esc(r['region'])}の{n}都道府県の中での順位は、{k.esc(label)}の{p0}番目から{p1}番目に上がりました。"]
    if p1 > p0:
        return [f"{k.esc(r['region'])}の{n}都道府県の中での順位は、{k.esc(label)}の{p0}番目から{p1}番目に下がりました。"]
    return [f"{k.esc(r['region'])}の{n}都道府県の中での順位は、{k.esc(label)}と同じ{p1}番目です。"]


def reach1000_story(d: dict, r: dict, k) -> list[str]:
    """In which year this prefecture first reached 1,000 yen, and how many prefectures got there earlier / in the same year."""
    first = {}
    for x in d["rows"]:
        e = next((e for e in x["long"] if e["amount"] is not None and e["amount"] >= 1000), None)
        first[x["name"]] = e["fy"] if e else None
    mine = first[r["name"]]
    if mine is None:
        return []
    label = next(e["label"] for e in r["long"] if e["fy"] == mine)
    earlier = sum(1 for v in first.values() if v is not None and v < mine)
    same = sum(1 for v in first.values() if v == mine) - 1
    latest = max(v for v in first.values() if v is not None)
    if earlier == 0:
        head = f"1,000円以上になったのは{k.esc(label)}で、全国で最も早い年度です"
    elif mine == latest:
        return []
    else:
        head = f"1,000円以上になったのは{k.esc(label)}で、{earlier}都道府県が先に届いています"
    tail = f"(同じ年度に届いたのは、ほかに{same}都道府県)。" if same else "(同じ年度に届いたのは、この都道府県だけ)。"
    return [head + tail]


def raise_top_story(d: dict, r: dict, k) -> list[str]:
    """In the last ten revisions: in how many the rise was among the ten largest of the 47."""
    last = [e for e in r["long"][-10:] if e["raise"] is not None]
    if len(last) < 10:
        return []
    top = 0
    for e in last:
        rises = [next(y["raise"] for y in x["long"] if y["fy"] == e["fy"]) for x in d["rows"]]
        if 1 + sum(1 for v in rises if v > e["raise"]) <= 10:
            top += 1
    if top == 0:
        return ["直近10回の改定で、引上げ額が47都道府県の上位10位以内に入った年度は、一度もありません。"]
    if top >= 5:
        return [f"直近10回の改定のうち{top}回は、引上げ額が47都道府県の上位10位以内でした。"]
    return []


def biggest_year_story(d: dict, r: dict, k) -> list[str]:
    """Whether this prefecture's biggest rise came in the year in which the national weighted average rose most."""
    s = r["long"]
    rises = [e for e in s if e["raise"] is not None]
    mine = max(rises, key=lambda e: (e["raise"], e["fy"]))
    ups = [y for y in d["long_years"] if y["avg_up"] is not None]
    nat = max(ups, key=lambda y: (y["avg_up"], y["fy"]))
    if mine["fy"] == nat["fy"]:
        return []
    return [f"引上げ額が最も大きかった{k.esc(mine['label'])}は、全国加重平均の引上げ額が最も大きい{k.esc(nat['label'])}とは別の年度です。"]


def places_story(d: dict, r: dict, k) -> list[str]:
    a, b, c = PLACES[r["short"]]
    return [f"{a}、{b}、{c}など、{k.esc(r['name'])}の中ならどこで働いても、適用される最低賃金は同じ{k.yen(r['amount'])}です。"]


# ---------------------------------------------------------------- the block
# The comparisons that every prefecture has (its rise against the national weighted average, the rank in its guideline class, the date's place, the share of the
# top amount) are in compare_table().  Prose is written only for what stands out in this prefecture, so a sentence is there only when its condition holds.
def _raise_facts(d: dict, r: dict) -> dict:
    avg = {y["fy"]: y["avg"] for y in d["years"]}
    nat = lambda fy: round(avg[fy]) - round(avg[fy - 1])  # noqa: E731
    cur_fy = r["long"][-1]["fy"]
    last3 = r["long"][-3:]
    last10 = [e for e in r["long"][-10:] if e["raise"] is not None]
    return {
        "nat": nat(cur_fy), "sum3": sum(e["raise"] for e in last3 if e["raise"] is not None), "sum3_nat": sum(nat(e["fy"]) for e in last3),
        "above3": sum(1 for e in last3 if e["raise"] is not None and e["raise"] > nat(e["fy"])),
        "below3": sum(1 for e in last3 if e["raise"] is not None and e["raise"] < nat(e["fy"])),
        "reach10": sum(1 for e in last10 if e["raise"] >= nat(e["fy"])), "n10": len(last10), "big10": sum(1 for e in last10 if e["raise"] >= 50),
    }


def story_block(d: dict, r: dict, k) -> str:
    f = _raise_facts(d, r)
    diff = r["raise"] - f["nat"]
    raise_sent = raise_story(d, r, k)[:1] if (abs(diff) >= 10 or r["raise_rank"] <= 5 or r["raise_rank"] >= 43) else []
    recent_sent = recent_story(d, r, k) if f["above3"] == 3 or f["below3"] == 3 else []
    pos, n, _ = _ordinal_in_region(d, r)
    region_sent = region_story(d, r, k) if pos in (1, n) else []
    hi, lo = max(x["amount"] for x in d["rows"]), min(x["amount"] for x in d["rows"])
    gap_sent = top_gap_story(d, r, k) if (r["amount"] in (hi, lo) or r["amount"] / hi >= 0.95) else []
    guide = guideline_story(d, r, k) if r["raise"] == GUIDELINE.get(RANK_OF.get(r["short"]), -1) or _guideline_top(d, r) else []
    dates = date_story(d, r, k)
    cur = date.fromisoformat(r["effective_date"])
    all_dates = [date.fromisoformat(x["effective_date"]) for x in d["rows"]]
    extreme = cur == min(all_dates) or cur == max(all_dates)
    sections = [
        ("順位の歩み", band_story(d, r, k) + rank_story(d, r, k) + rank_move_story(d, r, k) + era_rank_story(d, r, k) + overtake_story(d, r, k) + average_story(d, r, k)),
        ("隣の都道府県と比べると", neighbour_story(d, r, k) + swap_story(d, r, k) + gap_story(d, r, k) + tie_story(d, r, k) + region_sent + region_history_story(d, r, k) + gap_sent),
        ("節目と引上げ", reach1000_story(d, r, k) + guide + raise_sent + recent_sent + count_story(d, r, k) + raise_top_story(d, r, k) + biggest_year_story(d, r, k)),
        ("県内で働くとき", places_story(d, r, k)),
        ("発効日", dates[:1] if extreme else dates[1:] if len(dates) > 1 and ("すべて" in dates[1] or "なく" in dates[1]) else []),
    ]
    special = special_story(d, r, k)
    if special:
        sections.append(("この都道府県の表を読むときの注意", special))
    parts = [f"<h2>{k.esc(r['name'])}の最低賃金の特徴</h2>"]
    for head, sentences in sections:
        if sentences:
            parts.append(f"<h3>{head}</h3>\n<p>{''.join(sentences)}</p>")
    return "\n".join(parts) + "\n"


def _guideline_top(d: dict, r: dict) -> bool:
    """True when this prefecture's rise over the guideline is the largest in its guideline class."""
    if r["long"][-1]["fy"] != 2026 or r["short"] not in RANK_OF:
        return False
    mates = [x for x in d["rows"] if RANK_OF[x["short"]] == RANK_OF[r["short"]]]
    return r["raise"] > GUIDELINE[RANK_OF[r["short"]]] and all(x["raise"] <= r["raise"] for x in mates)


def compare_table(d: dict, r: dict, k) -> str:
    """The comparisons with the nation, as a table: the rise against the national weighted average, the guideline class, the effective date's place, the share of the top amount."""
    f = _raise_facts(d, r)
    label = k.esc(d["label"])
    rows = [(f"{label}の引上げ額", f"+{r['raise']}円(全国加重平均 +{f['nat']}円、47都道府県中{r['raise_rank']}位)"),
            ("直近3年度の引上げ額の合計", f"+{f['sum3']}円(全国加重平均 +{f['sum3_nat']}円)"),
            ("直近3回で、引上げ額が全国加重平均を上回った回数", f"{f['above3']}回(下回った回数 {f['below3']}回)")]
    if f["n10"] == 10:
        rows.append(("直近10回で、引上げ額が全国加重平均以上だった回数", f"{f['reach10']}回"))
        rows.append(("直近10回で、+50円以上の引上げだった回数", f"{f['big10']}回"))
    if r["long"][-1]["fy"] == 2026 and r["short"] in RANK_OF:
        rank = RANK_OF[r["short"]]
        guide = GUIDELINE[rank]
        mates = [x for x in d["rows"] if RANK_OF[x["short"]] == rank]
        pos = 1 + sum(1 for x in mates if x["raise"] > r["raise"])
        rows.append((f"{label}の目安({rank}ランク)", f"+{guide}円(決まった引上げ額は、目安との差 {r['raise'] - guide:+d}円。同じ{rank}ランクの{len(mates)}都道府県中、引上げ額は大きい方から{pos}番目)"))
    cur = date.fromisoformat(r["effective_date"])
    all_dates = [date.fromisoformat(x["effective_date"]) for x in d["rows"]]
    earlier, later = sum(1 for x in all_dates if x < cur), sum(1 for x in all_dates if x > cur)
    rows.append(("発効日", f"{k.jp_date(cur.isoformat())}({WEEKDAYS[cur.weekday()]}曜日)。早い方から{earlier + 1}番目で、これより遅い都道府県は{later}つ"))
    hist = [e for e in r["history"] if e["raise"] and e["effective_date"] and e["fy"] < r["history"][-1]["fy"]][-10:]
    if len(hist) >= 5:
        oct1 = sum(1 for e in hist if date.fromisoformat(e["effective_date"]) <= date(e["fy"], 10, 1))
        rows.append((f"直近{len(hist)}回の改定で、10月1日までに発効した回数", f"{oct1}回"))
    pos, n, _ = _ordinal_in_region(d, r)
    rows.append((f"{k.esc(r['region'])}の{n}都道府県の中での順位", f"高い方から{pos}番目"))
    hi = max(x["amount"] for x in d["rows"])
    rows.append(("最も高い額に対する割合", f"{r['amount'] / hi * 100:.1f}%(差 {hi - r['amount']}円)"))
    body = "".join(f'<tr><th scope="row">{a}</th><td>{b}</td></tr>' for a, b in rows)
    return (f'<h2>{k.esc(r["name"])}の引上げ額と発効日を、全国と比べる</h2>\n<div class="tablewrap"><table><thead><tr><th>項目</th><th>{k.esc(r["name"])}</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>\n')


def figures_table(d: dict, r: dict, k) -> str:
    """The numbers every prefecture has, as one table (they used to be sentences with a number swapped in)."""
    s = r["long"]
    first = next(e for e in s if e["amount"] is not None)
    last = s[-1]
    n = last["fy"] - first["fy"]
    up = last["amount"] - first["amount"]
    rises = [e for e in s if e["raise"] is not None and e["raise"] > 0]
    top = sorted(rises, key=lambda e: (-e["raise"], -e["fy"]))[0]
    best_pct = max((e for e in s if e["raise_pct"] is not None), key=lambda e: (e["raise_pct"], e["fy"]))
    a10 = next(e for e in s if e["fy"] == last["fy"] - 10)
    b10 = next(e for e in s if e["fy"] == last["fy"] - 20)
    by = {e["fy"]: e["amount"] for e in s if e["amount"] is not None}
    rows = [
        (f"{first['label']}の額", yen_text(first["amount"])),
        (f"{last['label']}の額(決まった額)", yen_text(last["amount"])),
        (f"{n}年間で上がった額", f"+{yen_text(up)}(約{last['amount'] / first['amount']:.1f}倍、1年あたり約{up / n:.0f}円)"),
        ("1年の引上げ額が最も大きかった年度", f"{top['label']}の+{yen_text(top['raise'])}"),
        ("引上げ率が最も大きかった年度", f"{best_pct['label']}の{best_pct['raise_pct']:.1f}%"),
        (f"直近10年間の上がり額({a10['label']}から{last['label']}まで)", f"+{yen_text(last['amount'] - a10['amount'])}"),
        (f"その前の10年間の上がり額({b10['label']}から{a10['label']}まで)", f"+{yen_text(a10['amount'] - b10['amount'])}"),
    ]
    if 1989 in by and 2018 in by:
        rows.append(("平成(元〜30年度)の上がり額", f"+{yen_text(by[2018] - by[1989])}"))
        rows.append((f"令和(元〜{last['fy'] - 2018}年度)の上がり額", f"+{yen_text(last['amount'] - by[2018])}"))
    for t in (1000, 1100, 1200):
        mine = next((e for e in s if e["amount"] is not None and e["amount"] >= t), None)
        rows.append((f"{t:,}円以上になった年度", mine["label"] if mine else "まだ届いていません"))
    nxt = (last["amount"] // 100 + 1) * 100
    if last["amount"] % 100:
        rows.append((f"次の節目の{nxt:,}円まで", f"あと{nxt - last['amount']:g}円"))
    body = "".join(f'<tr><th scope="row">{k.esc(a)}</th><td>{k.esc(b)}</td></tr>' for a, b in rows)
    return (f'<h2>{k.esc(r["name"])}の最低賃金の主な数字</h2>\n<div class="tablewrap"><table><thead><tr><th>項目</th><th>{k.esc(r["name"])}</th></tr></thead>'
            f'<tbody>{body}</tbody><tfoot><tr><td colspan="2">データの取得日: {k.jp_date(d["fetched_date"])}。</td></tr></tfoot></table></div>\n')
