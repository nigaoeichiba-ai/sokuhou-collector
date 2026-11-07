"""The logical model of the spec (Exam / Event / PassRateRecord / FeeRecord / Source), made from facts.py and data/.

Every event has a source (an id of sources.py); a pass rate that does not match passed / examinees is refused; a fee that is not confirmed is None ("確認中").
The day a source was read (CHECKED) is kept here and in the data, and is not shown on the pages (owner's rule of 2026-11-03).
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from .common import CHECKED, d, left, md, jp
from .facts import EVENTS, FEES, TOEIC
from .sources import SOURCES

RATES = json.loads((Path(__file__).resolve().parents[1] / "data" / "rates.json").read_text(encoding="utf-8"))

TYPE_LABEL = {"application_start": "申込開始", "application_deadline": "申込締切", "exam": "試験日", "announcement": "合格発表"}
FILE_TYPE = {"application_start": "start", "application_deadline": "deadline", "exam": "exam", "announcement": "result"}
KIND = {"apply_start": "application_start", "apply_end": "application_deadline", "exam": "exam", "result": "announcement"}

# who (the name in facts.py) -> (exam id, name on a card, field, page, organizer)
WHO = {
    "宅建士(令和8年度)": ("takken", "宅地建物取引士(宅建)", "不動産", "/takken/", "不動産適正取引推進機構"),
    "行政書士(令和8年度)": ("gyosei", "行政書士試験", "法律", "/gyosei/", "行政書士試験研究センター"),
    "社労士(令和8年度)": ("sharoshi", "社会保険労務士試験", "労務", "/sharoshi/", "全国社会保険労務士会連合会 試験センター"),
    "介護福祉士(第39回)": ("kaigo", "介護福祉士国家試験(第39回)", "福祉", "/kaigo-fukushi/", "社会福祉振興・試験センター"),
    "看護師(第116回)": ("kangoshi", "看護師国家試験(第116回)", "医療", "/kangoshi/", "厚生労働省"),
    "管理業務主任者(令和8年度)": ("kanri", "管理業務主任者試験", "不動産", "/schedule/", "マンション管理業協会"),
    "中小企業診断士 2次(令和8年度)": ("shindanshi", "中小企業診断士 2次試験", "経営", "/schedule/", "中小企業診断協会"),
    "国家総合職(春)2027年度": ("komuin-sogo", "国家総合職(春)第1次試験", "公務員", "/komuin/", "人事院"),
    "国家一般職(大卒)2027年度": ("komuin-ippan", "国家一般職(大卒)第1次試験", "公務員", "/komuin/", "人事院"),
    "日商簿記 第174回": ("boki-174", "日商簿記 第174回", "会計", "/boki/", "日本商工会議所"),
    "日商簿記 第175回": ("boki-175", "日商簿記 第175回", "会計", "/boki/", "日本商工会議所"),
    "FP1級学科(きんざい)": ("fp1", "FP技能検定1級 学科(きんざい)", "金融", "/fp/", "金融財政事情研究会"),
    "英検 2026年度第3回": ("eiken-3", "英検 2026年度 第3回", "語学", "/eiken/", "日本英語検定協会"),
    "漢検 2026年度第3回": ("kanken-3", "漢検 2026年度 第3回", "語学・教養", "/minkan/", "日本漢字能力検定協会"),
    "共通テスト(令和9年度)": ("kyotsu", "大学入学共通テスト", "大学入試", "/kyotsu/", "大学入試センター"),
    "共通テスト 追・再試験": ("kyotsu-tsuishi", "共通テストの追・再試験", "大学入試", "/kyotsu-tsuishi/", "大学入試センター"),
    "東京大 一般選抜": ("todai", "東京大学 一般選抜", "大学入試", "/kokkoritsu/", "東京大学"),
}

# the time of day where the organisation's page gives one: (who, kind, iso) -> (start, end)
TIMES = {
    ("宅建士(令和8年度)", "exam", "2026-10-18"): ("13:00", "15:00"),
    ("行政書士(令和8年度)", "apply_end", "2026-08-24"): ("17:00", ""),
    ("行政書士(令和8年度)", "exam", "2026-11-08"): ("13:00", "16:00"),
    ("行政書士(令和8年度)", "result", "2027-01-27"): ("09:00", ""),
    ("管理業務主任者(令和8年度)", "exam", "2026-12-06"): ("13:00", "15:00"),
    ("管理業務主任者(令和8年度)", "apply_start", "2026-08-03"): ("10:00", ""),
    ("管理業務主任者(令和8年度)", "apply_end", "2026-09-30"): ("16:59", ""),
    ("共通テスト(令和9年度)", "apply_end", "2026-10-02"): ("17:00", ""),
    ("宅建士(令和8年度)", "result", "2026-11-25"): ("09:30", ""),
    ("FP1級学科(きんざい)", "apply_start", "2026-10-28"): ("10:00", ""),
    ("FP1級学科(きんざい)", "apply_end", "2026-12-01"): ("17:30", ""),
    ("漢検 2026年度第3回", "apply_start", "2026-12-04"): ("09:00", ""),
    ("漢検 2026年度第3回", "apply_end", "2027-01-10"): ("23:59", ""),
    ("東京大 一般選抜", "result", "2027-03-10"): ("12:00", ""),
}


def _event(eid, exam, name, cat, typ, iso, time, end, note, url, source, variant=""):
    return {"id": eid, "exam": exam, "name": name, "cat": cat, "type": typ, "iso": iso, "time": time, "end": end, "note": note, "url": url, "source": source, "variant": variant}


def _take_ids(rows):
    seen = {}
    for e in rows:
        base = f"{e['exam']}-{FILE_TYPE[e['type']]}" + (f"-{e['variant']}" if e["variant"] else "")
        seen[base] = seen.get(base, 0) + 1
        e["id"] = base if seen[base] == 1 else f"{base}-{e['iso'].replace('-', '')}"
    return rows


def build_events() -> list[dict]:
    rows = []
    for who, group, kind, iso, src, note in EVENTS:
        eid, name, cat, url, org = WHO[who]
        t = TIMES.get((who, kind, iso), ("", ""))
        rows.append(_event("", eid, name, cat, KIND[kind], iso, t[0], t[1], note, url, src))
    # TOEIC L&R public tests: one exam per round
    for exam, s, e, res in TOEIC:
        x = d(exam)
        eid = f"toeic-{exam.replace('-', '')}"
        name = f"TOEIC L&R {x.month}月{x.day}日回"
        url = "/minkan/"
        rows += [_event("", eid, name, "語学", "application_start", s, "", "", "", url, "iibc"),
                 _event("", eid, name, "語学", "application_deadline", e, "15:00" if exam == "2026-12-19" else "", "", "", url, "iibc"),
                 _event("", eid, name, "語学", "exam", exam, "", "", "", url, "iibc"),
                 _event("", eid, name, "語学", "announcement", res, "", "", "デジタル公式認定証", url, "iibc")]
    # 宅建: the application is by post or by internet, with different deadlines (the spec's own example)
    tk = ("takken", "宅地建物取引士(宅建)", "不動産", "/takken/")
    rows += [_event("", *tk[:3], "application_start", "2026-07-01", "", "", "郵送申込", tk[3], "retio", "mail"),
             _event("", *tk[:3], "application_deadline", "2026-07-15", "", "", "郵送申込", tk[3], "retio", "mail"),
             _event("", *tk[:3], "application_start", "2026-07-01", "09:30", "", "インターネット申込", tk[3], "retio", "net"),
             _event("", *tk[:3], "application_deadline", "2026-07-31", "23:59", "", "インターネット申込", tk[3], "retio", "net")]
    for e in rows:
        e["name"] = e["name"]
    return _take_ids(sorted(rows, key=lambda e: (e["iso"], e["time"] or "99", e["exam"], e["type"])))


EVENT_LIST = build_events()
BY_ID = {e["id"]: e for e in EVENT_LIST}


def events_of(exam: str) -> list[dict]:
    return [e for e in EVENT_LIST if e["exam"] == exam]


def when_text(e: dict, with_year: bool = True) -> str:
    """2026年11月11日(水) 15:00 : the day, and the time where there is one"""
    s = jp(e["iso"]) if with_year else md(e["iso"])
    if e["time"]:
        s += " " + e["time"] + ("〜" + e["end"] if e["end"] else "")
    return s


def deadline_events(n: int | None = None) -> list[dict]:
    """The application deadlines from today on, the nearest first; on one day, the ones with a time first (as the spec's order says: a deadline without a time goes to the end of the day)."""
    rows = [e for e in EVENT_LIST if e["type"] == "application_deadline" and left(e["iso"]) >= 0]
    rows.sort(key=lambda e: (e["iso"], 0 if e["time"] else 1, e["time"]))
    return rows[:n] if n else rows


def examination_events(n: int | None = None) -> list[dict]:
    rows = [e for e in EVENT_LIST if e["type"] == "exam" and left(e["iso"]) >= 0]
    return rows[:n] if n else rows


def application_start_of(e: dict) -> str | None:
    """the day the application of the same exam opened (for the bar of the timeline), if the page gave one"""
    for x in EVENT_LIST:
        if x["exam"] == e["exam"] and x["type"] == "application_start" and x["variant"] == e["variant"] and x["iso"] <= e["iso"]:
            return x["iso"]
    return None


# ---------------------------------------------------------------- pass rates and fees
def pass_rate_rows(key: str = "takken", n: int = 5) -> list[dict]:
    """The newest n rows of one exam, as PassRateRecord.  A row whose rate is not passed / examinees (within 0.05 points) is refused."""
    out = []
    for r in RATES[key][:n]:
        rate = r.get("rate") if r.get("rate") is not None else r.get("rate_computed")
        if r["examinees"] and abs(r["passed"] / r["examinees"] * 100 - rate) > 0.05 + 1e-9:
            raise ValueError(f"{key} {r['year']}: the rate {rate} is not passed / examinees ({r['passed']} / {r['examinees']})")
        out.append({"year": r["year"], "applicants": r["applicants"], "examinees": r["examinees"], "passers": r["passed"], "rate": rate})
    return out


def sit_rate(row: dict) -> float:
    return row["examinees"] / row["applicants"] * 100


def applicant_basis_rate(row: dict) -> float:
    """Computed when shown, never stored (the spec's rule): passers / applicants"""
    return row["passers"] / row["applicants"] * 100


def fee_records() -> list[dict]:
    rows = [{"exam": k, "amount": v[0], "status": "confirmed", "source": v[1]} for k, v in FEES.items()]
    rows.append({"exam": "管理業務主任者", "amount": 8900, "status": "confirmed", "source": "kanrikyo"})
    for k in ("日商簿記", "FP技能検定", "漢検", "TOEIC L&R"):
        rows.append({"exam": k, "amount": None, "status": "checking", "source": None})
    return rows


def validate() -> None:
    """The build stops on an event without a source that exists, a bad time, or a pass rate that does not fit."""
    for e in EVENT_LIST:
        if e["source"] not in SOURCES_ALL:
            raise ValueError(f"event {e['id']}: source {e['source']!r} is not in sources.py")
        d(e["iso"])
        for t in (e["time"], e["end"]):
            if t and not (len(t) == 5 and t[2] == ":"):
                raise ValueError(f"event {e['id']}: time {t!r}")
    if len({e["id"] for e in EVENT_LIST}) != len(EVENT_LIST):
        raise ValueError("event ids are not unique")
    pass_rate_rows("takken", 14)
    for r in fee_records():
        if r["status"] == "checking" and r["amount"] is not None:
            raise ValueError(f"fee {r['exam']}: an amount for a fee that is being checked")


SOURCES_ALL = set(SOURCES) | {"retio", "gyosei", "sharosi", "sssc", "mhlw_kango", "jfcmca", "jinji", "kentei", "jafp", "kinzai", "ipa", "eiken", "iibc", "kanken", "dnc", "utokyo", "kanrikyo"}
validate()
