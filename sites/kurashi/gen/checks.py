"""The ledger of what was checked, and on which day: the check day of a page and the log of the fetches are data here, not typed into the pages.

CHECKED_ON   the pages whose facts (dates, numbers) were checked again against the primary or two secondary sources on a day. The page shows the newest day
             it is listed under ("2026年11月15日確認"). The day of the content change (data_basis is not the update day) is not touched by this.
FETCH_LOG    every source that was asked on a day and what came back. A failed fetch is never a "no change": tests/test_kurashi_site.py lists the failed ones
             that no later "ok" covers, and the daily routine starts with them.
Only things that were really read go in. A page that was not looked at keeps its older day.
"""
from __future__ import annotations

from datetime import date

FIRST = "2026-11-03"

# day -> the pages whose dates were compared with the sources that day
CHECKED_ON = {
    "2026-11-15": [
        "/", "/month/", "/month/11/", "/month/12/", "/month/1/", "/month/2/", "/month/3/",
        "/nengajo/", "/nenmatsu-nenshi/", "/nenmatsu-chosei/",
        "/furusato/deadline/", "/furusato/one-stop/",
        "/kakutei-shinkoku/", "/kakutei-shinkoku/junbi/", "/kakutei-shinkoku/kanpu/", "/kakutei-shinkoku/furusato/",
    ],
}

# (day, what, how, result, note); result is "ok" or "failed". A later "ok" for the same what closes a "failed".
FETCH_LOG = [
    ("2026-11-15", "日本郵便 年賀はがき 引受開始・差出日・販売終了", "日本郵便の2026-08-31発表(検索の引用)+NHK", "ok", "12/20・12/27・1/15。サイトと一致"),
    ("2026-11-15", "日本郵便 /newyear/", "WebFetch・Chrome", "failed", "404(ページが移動)。上の発表で代替"),
    ("2026-11-15", "国税庁 令和8年分 年末調整のしかた(101.pdf)", "Google文書ビューア経由", "ok", "変更点4項目・納期限 令和9年1月12日。サイトの記述と一致"),
    ("2026-11-15", "国税庁 令和8年分 確定申告の期間・還付申告", "国税庁資料+二次情報", "ok", "2027年2月16日〜3月15日、還付は1月1日から。サイトと一致"),
    ("2026-11-15", "ワンストップ特例の期限(1月10日)", "自治体2件+ふるさと納税サイト", "ok", "法の期限は1月10日(日)。紙は自治体により1月12日扱い。サイトの文は変更届と申請書を分けて書いてある"),
    ("2026-11-15", "行政機関の休日(12月29日〜1月3日)", "法令の解説(hourei.net ほか)", "ok", "行政機関の休日に関する法律。サイトと一致"),
    ("2026-11-15", "総務省 ふるさと納税 公式ページ", "WebFetch(403/404)・Chrome・検索", "failed", "公式の本文は未取得。二次情報(freee ほか)で、2025年10月にポイント付与禁止が済み、2026年10月は地場産品基準・募集費用の見直しと確認"),
    ("2026-11-15", "マイナポータル 引越し手続", "WebFetch", "failed", "待機室へ転送。変更のお知らせは未確認"),
    ("2026-11-15", "gyosei.go.jp", "WebFetch", "failed", "名前解決不可。法令の解説で代替済み"),
]


def checked_day(path: str) -> str:
    """ISO day this page was last checked (FIRST when it was never checked again)."""
    days = [day for day, paths in CHECKED_ON.items() if path in paths]
    return max(days) if days else FIRST


def label(iso: str) -> str:
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{y}年{m}月{d}日"


def open_failures() -> list[tuple]:
    """failed fetches that no later 'ok' for the same source covers"""
    out = []
    for i, (day, what, how, res, note) in enumerate(FETCH_LOG):
        if res == "failed" and not any(r == "ok" and w == what and dd >= day for dd, w, _h, r, _n in FETCH_LOG[i + 1:]):
            out.append((day, what, how, note))
    return out


def latest_day() -> date:
    return date.fromisoformat(max(CHECKED_ON))
