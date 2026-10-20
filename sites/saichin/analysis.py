"""Numbers behind the /analysis/ pages and the "25 years in numbers" blocks.

Everything here is arithmetic on the history workbook (47 prefectures x every fiscal year since Heisei 14): no outside facts, no causes.
`d` is the dict returned by build.prepare(): d["rows"][i]["history"] is a list of {fy, label, amount, raise, rank, effective_date, date_fixed_from}.
"""
from __future__ import annotations

from datetime import date
from statistics import median

THRESHOLDS = (800, 900, 1000, 1100, 1200)


def short_label(label: str) -> str:
    """'令和8年度' -> 'R8'."""
    return label.replace("年度", "").replace("令和", "R").replace("平成", "H")


def year_amounts(d: dict) -> dict[int, list[tuple[int, dict]]]:
    """fy -> [(amount, row)] for every prefecture."""
    out: dict[int, list[tuple[int, dict]]] = {}
    for r in d["rows"]:
        for h in r["history"]:
            out.setdefault(h["fy"], []).append((h["amount"], r))
    return out


def names(rows: list[dict]) -> str:
    """'東京都', '東京都・神奈川県', '東京都ほか2都県'."""
    ns = [r["name"] for r in rows]
    if len(ns) <= 2:
        return "・".join(ns)
    return f"{ns[0]}ほか{len(ns) - 1}都道府県"


# ---------------------------------------------------------------- gap between the highest and the lowest prefecture
def gap_series(d: dict) -> list[dict]:
    out = []
    for fy, pairs in sorted(year_amounts(d).items()):
        hi = max(a for a, _ in pairs)
        lo = min(a for a, _ in pairs)
        hi_rows = sorted((r for a, r in pairs if a == hi), key=lambda r: r["name"])
        lo_rows = sorted((r for a, r in pairs if a == lo), key=lambda r: r["name"])
        label = next(h["label"] for h in hi_rows[0]["history"] if h["fy"] == fy)
        out.append({"fy": fy, "label": label, "max": hi, "min": lo, "gap": hi - lo, "ratio": lo / hi * 100,
                    "hi_rows": hi_rows, "lo_rows": lo_rows, "n_lo": len(lo_rows)})
    return out


def top_bottom_means(d: dict, k: int = 5) -> list[dict]:
    """Mean of the k highest and the k lowest prefectures in each year (ties at the border broken by name, only for the mean)."""
    out = []
    for fy, pairs in sorted(year_amounts(d).items()):
        amts = sorted((a for a, _ in pairs), reverse=True)
        out.append({"fy": fy, "top": sum(amts[:k]) / k, "bottom": sum(amts[-k:]) / k})
    return out


# ---------------------------------------------------------------- the year each prefecture first reached 800, 900, ... yen
def milestones(d: dict) -> dict[int, list[dict]]:
    """threshold -> prefectures that reached it, in order of the year (then of the name): [{row, fy, label}]."""
    out: dict[int, list[dict]] = {}
    for t in THRESHOLDS:
        got = []
        for r in d["rows"]:
            hit = next((h for h in r["history"] if h["amount"] >= t), None)
            if hit:
                got.append({"row": r, "fy": hit["fy"], "label": hit["label"], "amount": hit["amount"]})
        got.sort(key=lambda g: (g["fy"], g["row"]["name"]))
        out[t] = got
    return out


def national_milestones(d: dict) -> dict[int, dict | None]:
    out = {}
    for t in THRESHOLDS:
        y = next((y for y in d["years"] if round(y["avg"]) >= t), None)
        out[t] = y
    return out


def milestone_rank(ms: dict[int, list[dict]], row: dict, t: int) -> tuple[int, int] | None:
    """(how many prefectures reached `t` in an earlier year + 1, the year) for `row`; None when it has not reached it."""
    got = ms[t]
    mine = next((g for g in got if g["row"] is row), None)
    if mine is None:
        return None
    return 1 + sum(1 for g in got if g["fy"] < mine["fy"]), mine["fy"]


# ---------------------------------------------------------------- ranks
def rank_table(d: dict) -> list[dict]:
    out = []
    for r in d["rows"]:
        h = r["history"]
        ranks = [x["rank"] for x in h]
        out.append({
            "row": r, "first": h[0]["rank"], "last": h[-1]["rank"], "best": min(ranks), "worst": max(ranks),
            "change": h[0]["rank"] - h[-1]["rank"],          # positive: moved up
            "best_years": [x for x in h if x["rank"] == min(ranks)], "worst_years": [x for x in h if x["rank"] == max(ranks)],
        })
    return out


def number_one_years(d: dict) -> list[dict]:
    """Per year: the prefecture(s) in 1st place."""
    out = []
    for g in gap_series(d):
        out.append({"fy": g["fy"], "label": g["label"], "rows": g["hi_rows"]})
    return out


# ---------------------------------------------------------------- how much each year raised the minimum wage
def raise_series(d: dict) -> list[dict]:
    out = []
    avg = {y["fy"]: y["avg"] for y in d["years"]}
    for fy in sorted(avg)[1:]:
        hs = []
        for r in d["rows"]:
            h = next(x for x in r["history"] if x["fy"] == fy)
            hs.append((h["raise"], r, h))
        raises = [x[0] for x in hs]
        hi, lo = max(raises), min(raises)
        label = hs[0][2]["label"]
        out.append({
            "fy": fy, "label": label, "avg_up": round(avg[fy]) - round(avg[fy - 1]),
            "max": hi, "min": lo, "n_hi": sum(1 for x in raises if x == hi), "n_lo": sum(1 for x in raises if x == lo),
            "hi_rows": sorted((r for a, r, _ in hs if a == hi), key=lambda r: r["name"]),
            "lo_rows": sorted((r for a, r, _ in hs if a == lo), key=lambda r: r["name"]),
            "n_zero": sum(1 for x in raises if x == 0),
            "n_30": sum(1 for x in raises if x >= 30), "n_50": sum(1 for x in raises if x >= 50),
        })
    return out


# ---------------------------------------------------------------- effective dates
def date_series(d: dict) -> list[dict]:
    """For each year, the dates on which the prefectures that changed their amount took effect."""
    out = []
    for fy in sorted(y["fy"] for y in d["years"])[1:]:
        items = []
        for r in d["rows"]:
            h = next(x for x in r["history"] if x["fy"] == fy)
            if h["raise"] and h["effective_date"]:
                items.append((date.fromisoformat(h["effective_date"]), r, h))
        if not items:
            out.append({"fy": fy, "label": next(x["label"] for x in d["rows"][0]["history"] if x["fy"] == fy), "n": 0})
            continue
        items.sort(key=lambda t: (t[0], t[1]["name"]))
        ds = [t[0] for t in items]
        base = date(fy, 10, 1)
        out.append({
            "fy": fy, "label": items[0][2]["label"], "n": len(items),
            "first": ds[0], "last": ds[-1], "first_rows": [t[1] for t in items if t[0] == ds[0]], "last_rows": [t[1] for t in items if t[0] == ds[-1]],
            "span": (ds[-1] - ds[0]).days, "median": median((x - base).days for x in ds), "distinct": len(set(ds)),
            "by_oct1": sum(1 for x in ds if x <= base), "in_oct": sum(1 for x in ds if x.year == fy and x.month == 10 and x.day >= 2),
            "in_nov_dec": sum(1 for x in ds if x.year == fy and x.month in (11, 12)), "next_year": sum(1 for x in ds if x.year > fy),
            "fixed": sum(1 for t in items if t[2].get("date_fixed_from")),
        })
    return out


# ---------------------------------------------------------------- one prefecture and one region over the whole series (Showa 52 to now)
PREF_THRESHOLDS = (500, 600, 700, 800, 900, 1000, 1100, 1200)


def _reach(entries: list[dict], t: float, part: str | None = None) -> dict | None:
    """The first entry whose amount is at least t.  part "south"/"north": Kyoto's two rates stand in for the missing amount of its split years."""
    for e in entries:
        a = e["amount"] if e["amount"] is not None or part is None else e["split"][part]
        if a is not None and a >= t:
            return e
    return None


def reach_years(d: dict) -> dict[float, dict[str, dict]]:
    """threshold -> {short name: {"fy", "label", "labels" (two labels when Kyoto's two rates reached it in different years)}}; Kyoto counts from the later of its two."""
    out: dict[float, dict[str, dict]] = {}
    for t in PREF_THRESHOLDS:
        got = {}
        for r in d["rows"]:
            s = r["long"]
            if r["short"] == "京都" and any(e["amount"] is None for e in s):
                a, b = _reach(s, t, "south"), _reach(s, t, "north")
                if a is None or b is None:
                    continue
                late = max(a, b, key=lambda e: e["fy"])
                got[r["short"]] = {"fy": late["fy"], "label": late["label"],
                                   "labels": None if a["fy"] == b["fy"] else (a["label"], b["label"])}
            else:
                e = _reach(s, t)
                if e:
                    got[r["short"]] = {"fy": e["fy"], "label": e["label"], "labels": None}
        out[t] = got
    return out


def pref_facts(d: dict, r: dict) -> dict:
    s = r["long"]
    first = next(e for e in s if e["amount"] is not None)
    last = s[-1]
    ny = {n["fy"]: n for n in d["long_years"]}
    reached = []
    ry = reach_years(d)
    for t in PREF_THRESHOLDS:
        mine = ry[t].get(r["short"])
        if mine:
            reached.append({"t": t, "label": mine["label"], "labels": mine["labels"], "order": 1 + sum(1 for v in ry[t].values() if v["fy"] < mine["fy"]), "of": len(ry[t])})
    ranks = [(e["rank"], e) for e in s if e["rank"] is not None]
    best, worst = min(x for x, _ in ranks), max(x for x, _ in ranks)
    return {
        "first": first, "last": last, "reached": reached, "best": best, "worst": worst,
        "best_labels": [e["label"] for x, e in ranks if x == best], "worst_labels": [e["label"] for x, e in ranks if x == worst],
        "to_top_first": ny[first["fy"]]["max"] - first["amount"], "to_top_last": ny[last["fy"]]["max"] - last["amount"],
        "to_bottom_first": first["amount"] - ny[first["fy"]]["min"], "to_bottom_last": last["amount"] - ny[last["fy"]]["min"],
        "to_avg_first": first["avg_gap"], "to_avg_last": last["avg_gap"],
        "raises_zero": sum(1 for e in s[1:] if e["raise"] == 0),
    }


def region_facts(d: dict, members: list[dict]) -> dict:
    h0, h1 = members[0]["long"][0], members[0]["long"][-1]

    def at(fy):
        v = [next(x for x in m["long"] if x["fy"] == fy)["amount"] for m in members]
        return min(v), max(v), sum(v) / len(v)
    ups = sorted(((m["long"][-1]["amount"] - m["long"][0]["amount"], m) for m in members), key=lambda t: (-t[0], t[1]["name"]))
    return {"first": at(h0["fy"]), "last": at(h1["fy"]), "ups": ups, "label0": h0["label"], "label1": h1["label"], "fy0": h0["fy"], "fy1": h1["fy"]}
