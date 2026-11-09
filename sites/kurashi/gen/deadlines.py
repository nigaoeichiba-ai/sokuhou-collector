"""The dated deadlines that a reader can put in a calendar (.ics), and the pages that show them.

The dates are the constants of pages_hub (the same ones the tables use), so a calendar file and the table on the page cannot disagree.
site.json gets the catalog ("deadlines"); each page gets the ids of the deadlines it shows ("deadline_ids"). hooks.py makes the buttons and the files.
"""
from __future__ import annotations

from datetime import date

from .pages_hub import (CLOSED_FROM, KAKUTEI_END, KAKUTEI_START, KYOTSU, NENGA_NEW_YEAR, NENGA_SALE_END, NENGA_START, ONESTOP_CHANGE, REFUND_START,
                        YEAR_END)

LAST_WEEKDAY = date(2026, 12, 28)          # the last weekday the national offices are open before the year-end holiday

# id, date, name (the title of the calendar entry), lead (the short form the home page's answer uses, only where it has one), the page that explains it
CATALOG = [
    ("nengajo-hikiuke", NENGA_START, "年賀状の引受開始", "年賀状の引受開始", "/nengajo/"),
    ("nengajo-motojitsu", NENGA_NEW_YEAR, "年賀状を元日に届ける差し出し日の目安", "", "/nengajo/"),
    ("gyosei-saigo-heijitsu", LAST_WEEKDAY, "国の行政機関の最後の平日", "", "/nenmatsu-nenshi/"),
    ("gyosei-yasumi", CLOSED_FROM, "国の行政機関の年末年始の休みの開始", "", "/nenmatsu-nenshi/"),
    ("nenmatsu-shime", YEAR_END, "ふるさと納税・医療費の年内の締め", "ふるさと納税・医療費の締め", "/furusato/deadline/"),
    ("kanpu-start", REFUND_START, "令和8年分の還付申告を出せる最初の日", "", "/kakutei-shinkoku/kanpu/"),
    ("onestop-henko", ONESTOP_CHANGE, "ワンストップ特例の変更届の期限", "ワンストップ特例の変更届の期限", "/furusato/one-stop/"),
    ("nengajo-hanbai-end", NENGA_SALE_END, "年賀はがきの販売の最終日", "", "/nengajo/"),
    ("kyotsu-honshiken", KYOTSU[0], "大学入学共通テストの本試験", "", "/month/1/"),
    ("shinkoku-start", KAKUTEI_START, "確定申告の期間の初日", "確定申告の期間の初日", "/kakutei-shinkoku/"),
    ("shinkoku-end", KAKUTEI_END, "確定申告と納税の期限(原則)", "", "/kakutei-shinkoku/"),
]

# the deadlines each page shows (the rows of its own table); a page that is not here has no buttons
BY_PAGE = {
    "/": ["nengajo-hikiuke", "nengajo-motojitsu", "gyosei-yasumi", "nenmatsu-shime", "onestop-henko", "shinkoku-start", "shinkoku-end"],
    "/month/": [c[0] for c in CATALOG],
    "/month/11/": ["nenmatsu-shime"],
    "/month/12/": ["nengajo-hikiuke", "nengajo-motojitsu", "gyosei-saigo-heijitsu", "gyosei-yasumi", "nenmatsu-shime"],
    "/month/1/": ["kanpu-start", "onestop-henko", "nengajo-hanbai-end", "kyotsu-honshiken"],
    "/month/2/": ["shinkoku-start"],
    "/month/3/": ["shinkoku-end"],
    "/nengajo/": ["nengajo-hikiuke", "nengajo-motojitsu", "nengajo-hanbai-end"],
    "/nenmatsu-nenshi/": ["gyosei-saigo-heijitsu", "gyosei-yasumi"],
    "/furusato/deadline/": ["nenmatsu-shime", "onestop-henko", "shinkoku-end"],
    "/furusato/one-stop/": ["onestop-henko"],
    "/kakutei-shinkoku/": ["shinkoku-start", "shinkoku-end"],
    "/kakutei-shinkoku/junbi/": ["nenmatsu-shime", "kanpu-start", "shinkoku-start", "shinkoku-end"],
    "/kakutei-shinkoku/kanpu/": ["kanpu-start"],
    "/iryouhi-koujo/": ["nenmatsu-shime"],
}


def catalog_json() -> list[dict]:
    return [{"id": i, "date": x.isoformat(), "name": n, "lead": lead, "url": u} for i, x, n, lead, u in CATALOG]
