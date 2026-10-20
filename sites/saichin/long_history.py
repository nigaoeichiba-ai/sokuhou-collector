"""One series per prefecture from Showa 52 (1977) to the current year: the Ministry's 2003 document (history_old) joined to the current workbook.

Checked on every build (`check`): the old snapshot must agree with the workbook where they overlap (Heisei 14 and 15, every prefecture), have every year, never fall.
Kyoto had two regional rates from Showa 54 to Heisei 1: those years have `amount` None and the two rates in `split`.
"""
from __future__ import annotations

OLD_FIRST = 1977


class LongHistoryError(Exception):
    pass


def era_label(fy: int) -> str:
    if fy <= 1988:
        return f"昭和{fy - 1925}年度"
    if fy == 1989:
        return "平成元年度"
    if fy <= 2018:
        return f"平成{fy - 1988}年度"
    if fy == 2019:
        return "令和元年度"
    return f"令和{fy - 2018}年度"


def check(raw: dict, old: dict) -> None:
    """Refuse an old snapshot that does not fit the workbook; a site built from a bad join is not published."""
    first, last = old["first_fiscal_year"], old["last_fiscal_year"]
    names = [p["name"] for p in raw["prefectures"]]
    if sorted(old["prefectures"]) != sorted(names):
        raise LongHistoryError("the old document and the workbook do not list the same prefectures")
    split_years = sorted(int(y) for y in old["kyoto_split"]["south"])
    if split_years != sorted(int(y) for y in old["kyoto_split"]["north"]) or split_years != list(range(split_years[0], split_years[-1] + 1)):
        raise LongHistoryError("Kyoto's south and north series must cover the same run of years")
    for p in raw["prefectures"]:
        name, series = p["name"], old["prefectures"][p["name"]]
        want = [y for y in range(first, last + 1) if not (name == "京都" and y in split_years)]
        if sorted(int(y) for y in series) != want:
            raise LongHistoryError(f"{name}: the old document has gaps or extra years")
        values = []
        for y in range(first, last + 1):
            if str(y) in series:
                values.append(series[str(y)])
            elif name == "京都":
                values.append(max(old["kyoto_split"]["south"][str(y)], old["kyoto_split"]["north"][str(y)]))
        for y in (2002, 2003, 2004):
            if str(y) not in p["history"]:
                raise LongHistoryError(f"{name}: the workbook has no {y}, so the old document cannot be checked against it")
        for y in (2002, 2003):
            if series[str(y)] != p["history"][str(y)]["amount"]:
                raise LongHistoryError(f"{name} {y}: the old document says {series[str(y)]}, the workbook {p['history'][str(y)]['amount']}")
        if any(not 100 <= v <= 1500 for v in values):
            raise LongHistoryError(f"{name}: an old amount is out of range")
        if any(b < a for a, b in zip(values, values[1:])) or values[-1] > p["history"]["2004"]["amount"]:
            raise LongHistoryError(f"{name}: an old amount falls")
    for part in ("south", "north"):
        v = [old["kyoto_split"][part][str(y)] for y in split_years]
        if any(b < a for a, b in zip(v, v[1:])):
            raise LongHistoryError(f"Kyoto {part}: an old amount falls")
    for y, a in old["national_weighted_average"].items():
        amts = [old["prefectures"][n][y] for n in names if y in old["prefectures"][n]]
        if int(y) in split_years:
            amts += [old["kyoto_split"][part][y] for part in ("south", "north")]
        if not min(amts) <= a <= max(amts):
            raise LongHistoryError(f"{y}: the old national average {a} is outside the prefectures' range")
    for y in (2002, 2003):
        if str(y) not in raw["national_weighted_average"]:
            raise LongHistoryError(f"the workbook has no national average for {y}")
        if abs(old["national_weighted_average"][str(y)] - round(raw["national_weighted_average"][str(y)])) > 1:
            raise LongHistoryError(f"{y}: the old national average does not fit the workbook")


def build(raw: dict, old: dict, last_fy: int) -> tuple[dict[str, list[dict]], list[dict]]:
    """({short name: [entry per fiscal year 1977..last_fy]}, [national entry per year]).

    entry: fy, label, amount (None in Kyoto's split years), split ({"south", "north"} or None), raise, raise_pct, rank, avg, avg_gap, old (True before Heisei 14).
    A year's ranks count the prefectures that have a single amount in it (46 in Kyoto's split years).
    """
    check(raw, old)
    split = old["kyoto_split"]
    years = list(range(OLD_FIRST, last_fy + 1))
    avg: dict[int, float] = {int(y): a for y, a in old["national_weighted_average"].items() if int(y) < 2002}
    avg.update({int(y): a for y, a in raw["national_weighted_average"].items()})
    amount: dict[str, dict[int, float | None]] = {}
    for p in raw["prefectures"]:
        s = {}
        for y in years:
            if y >= 2002:
                s[y] = p["history"][str(y)]["amount"]
            else:
                s[y] = old["prefectures"][p["name"]].get(str(y))
        amount[p["name"]] = s
    entries: dict[str, list[dict]] = {}
    for name, s in amount.items():
        out, prev = [], None
        for y in years:
            a = s[y]
            rank = None if a is None else 1 + sum(1 for o in amount.values() if o[y] is not None and o[y] > a)
            rise = None if a is None or prev is None else round(a - prev, 2)
            out.append({
                "fy": y, "label": era_label(y), "amount": a,
                "split": ({"south": split["south"][str(y)], "north": split["north"][str(y)]} if a is None else None),
                "raise": rise, "raise_pct": None if rise is None else rise / prev * 100, "rank": rank,
                "avg": avg.get(y), "avg_gap": None if a is None or y not in avg else round(a - round(avg[y]), 2), "old": y < 2002,
            })
            prev = a
        entries[name] = out
    national = []
    for y in years:
        vals = [(o[y], n) for n, o in amount.items() if o[y] is not None]
        if y in (int(k) for k in split["south"]):
            vals += [(split["south"][str(y)], "京都(南)"), (split["north"][str(y)], "京都(北)")]
        hi, lo = max(v for v, _ in vals), min(v for v, _ in vals)
        national.append({
            "fy": y, "label": era_label(y), "avg": avg.get(y), "max": hi, "min": lo,
            "max_names": sorted(n for v, n in vals if v == hi), "min_names": sorted(n for v, n in vals if v == lo),
        })
    prev_avg = None
    for n in national:
        n["avg_up"] = None if prev_avg is None or n["avg"] is None else round(round(n["avg"]) - round(prev_avg))
        n["avg_pct"] = None if n["avg_up"] is None else n["avg_up"] / round(prev_avg) * 100
        prev_avg = n["avg"]
    return entries, national


def yen_text(v: float | int | None) -> str:
    """296円, 320.88円 (the old document gives a few amounts with decimals)."""
    if v is None:
        return "-"
    return f"{int(v):,}円" if v == int(v) else f"{v:,.2f}".rstrip("0").rstrip(".") + "円"
