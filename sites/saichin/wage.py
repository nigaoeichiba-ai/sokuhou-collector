"""Joins the wage structure survey (e-Stat) with the minimum wage that was in force when the survey was taken.

The survey measures June pay of year Y. The minimum wage in force then is the last one that took effect on or
before June 30 of Y, which is the previous fiscal year's amount (for the Reiwa 7 survey, the October 2024 revision).
Comparing June-2025 pay with the October-2026 minimum wage would mix two different years, so it is not done.
"""
from __future__ import annotations

import re

SOURCE_PAGE = "https://www.e-stat.go.jp/stat-search/files?tclass=000001229518&cycle=0"
SOURCE_LABEL = "厚生労働省「賃金構造基本統計調査」(政府統計の総合窓口 e-Stat)"
SURVEY_PAGE = "https://www.mhlw.go.jp/toukei/list/chinginkouzou.html"


class WageError(ValueError):
    pass


def survey_year(label: str) -> int:
    """'令和7年' -> 2025."""
    m = re.fullmatch(r"令和(\d+)年", label)
    if not m:
        raise WageError(f"unexpected survey year label {label!r}")
    return 2018 + int(m.group(1))


def hourly(pay_k: float, hours: int) -> int:
    """Scheduled pay per month (thousand yen) divided by scheduled hours per month, rounded to a yen."""
    return round(pay_k * 1000 / hours)


def annual(total_cash_k: float, bonus_k: float) -> int:
    """Yearly pay in yen: June cash pay times 12 plus a year of bonuses (the usual 'annual income' reading)."""
    return round((total_cash_k * 12 + bonus_k) * 1000)


def _rank(values: dict[str, float]) -> dict[str, int]:
    """1 = highest; ties share a rank."""
    return {k: 1 + sum(1 for v in values.values() if v > x) for k, x in values.items()}


def view(wage: dict, d: dict) -> dict:
    """Per-prefecture figures plus the national row, keyed by prefecture name; raises if anything does not line up."""
    year = survey_year(wage["year_label"])
    cutoff = f"{year}-06-30"
    by_name = {p["name"]: p for p in wage["prefectures"]}
    avg_by_fy = {y["fy"]: y["avg"] for y in d["years"]}
    rows: dict[str, dict] = {}
    for r in d["rows"]:
        w = by_name.get(r["name"])
        if w is None:
            raise WageError(f"{r['name']} is missing from the wage survey")
        in_force = [h for h in r["history"] if h["effective_date"] and h["effective_date"] <= cutoff]
        if not in_force:
            raise WageError(f"{r['name']}: no minimum wage in force at {cutoff} in the history")
        h = max(in_force, key=lambda x: x["effective_date"])
        hr = hourly(w["scheduled_pay_k"], w["scheduled_hours"])
        rows[r["name"]] = {
            "pay_k": w["scheduled_pay_k"], "male_k": w["male"]["scheduled_pay_k"], "female_k": w["female"]["scheduled_pay_k"],
            "hours": w["scheduled_hours"], "hourly": hr, "annual": annual(w["total_cash_k"], w["bonus_k"]),
            "min_then": h["amount"], "min_then_label": h["label"], "min_then_fy": h["fy"],
            "ratio": h["amount"] / hr,
        }
    for key, field in (("pay_rank", "pay_k"), ("hourly_rank", "hourly"), ("annual_rank", "annual"), ("ratio_rank", "ratio")):
        ranks = _rank({n: v[field] for n, v in rows.items()})
        for n, v in rows.items():
            v[key] = ranks[n]
    n = wage["national"]
    fys = {v["min_then_fy"] for v in rows.values()}
    if len(fys) != 1:
        raise WageError(f"prefectures disagree on the fiscal year in force at {cutoff}: {sorted(fys)}")
    fy_then = fys.pop()
    if fy_then not in avg_by_fy:
        raise WageError(f"no national average minimum wage for fiscal year {fy_then}")
    hr = hourly(n["scheduled_pay_k"], n["scheduled_hours"])
    national = {
        "pay_k": n["scheduled_pay_k"], "male_k": n["male"]["scheduled_pay_k"], "female_k": n["female"]["scheduled_pay_k"],
        "hours": n["scheduled_hours"], "hourly": hr, "annual": annual(n["total_cash_k"], n["bonus_k"]),
        "min_then": round(avg_by_fy[fy_then]), "ratio": round(avg_by_fy[fy_then]) / hr,
    }
    return {"year_label": wage["year_label"], "year": year, "min_then_label": next(iter(rows.values()))["min_then_label"],
            "rows": rows, "national": national, "source_page": wage.get("source_page") or SOURCE_PAGE}
