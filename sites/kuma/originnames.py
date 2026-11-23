"""title・meta description・og:title/og:description・h1 から、情報元の名前(環境省・自治体の公式・〇〇県の公式)を外す(オーナー指示 2026-11-15『情報元の具体的な記載は画面に出さない』、
窓口の指示 2026-11-23)。年度・範囲・速報値など、中身を表す言葉は残す。ライセンス表記・必須クレジット(本文下部の出典欄)には触れない。
環境省・自治体の発表そのものを主題にしたページ(お知らせ・取得元・数字の差・数字の読み方・出没情報の案内)は、題の中の名前が出どころでなく主題なので、対象外にする。"""
from __future__ import annotations

import re

SUBJECT_PAGES = frozenset({"news/index.html", "notify/index.html", "cite/index.html", "guide/data/index.html", "official/index.html", "notices/index.html"})
RULES = [
    (re.compile(r"・北海道石狩市・北海道空知総合振興局の公式"), ""),
    (re.compile(r"・[^・()（）、。]{1,12}の公式(?=[)）])"), ""),
    (re.compile(r"(?<=[(（])自治体の公式・"), ""),
    (re.compile(r"[(（]自治体の公式[)）]"), ""),
    (re.compile(r"・自治体の公式"), ""),
    (re.compile(r"自治体の公式・"), ""),
    (re.compile(r"・環境省の速報値"), "の速報値"),
    (re.compile(r"[(（]環境省の速報値[)）]"), "(速報値)"),
    (re.compile(r"環境省の速報値"), "速報値"),
    (re.compile(r"・環境省(?=[)）])"), ""),
    (re.compile(r"[(（]環境省[)）]"), ""),
    (re.compile(r"[(（]環境省の資料[)）]"), ""),
    (re.compile(r"環境省の一覧"), "公表された一覧"),
    (re.compile(r"環境省の資料から"), "公表資料から"),
    (re.compile(r"環境省の資料で"), "公的な資料で"),
    (re.compile(r"環境省の表に"), "表に"),
    (re.compile(r"環境省の出没件数"), "出没件数"),
    (re.compile(r"環境省の許可捕獲数"), "許可捕獲数"),
    (re.compile(r"環境省の月別の出没件数"), "月別の出没件数"),
    (re.compile(r"環境省の月別"), "月別"),
    (re.compile(r"環境省の公表データ"), "公表データ"),
    (re.compile(r"環境省の統計"), "公的な統計"),
    (re.compile(r"環境省の表(?=で|と)"), "公表された表"),
    (re.compile(r"環境省が公表している"), "公表されている"),
    (re.compile(r"[(（]公式[)）]"), ""),
    (re.compile(r"自治体が公式に公表している"), "公表されている"),
]
_TITLE = re.compile(r"(<title>)(.*?)(</title>)", re.S)
_META = re.compile(r'(<meta (?:name="description"|property="og:(?:title|description)") content=")([^"]*)(">)')
_H1 = re.compile(r"(<h1[^>]*>)(.*?)(</h1>)", re.S)


def clean(text: str) -> str:
    for rx, rep in RULES:
        text = rx.sub(rep, text)
    return text


def scrub(rel: str, t: str) -> str:
    if not rel.endswith(".html") or rel in SUBJECT_PAGES:
        return t
    for rx in (_TITLE, _META, _H1):
        t = rx.sub(lambda m: m.group(1) + clean(m.group(2)) + m.group(3), t)
    return t


def scrub_all(pages: dict) -> int:
    n = 0
    for rel, t in pages.items():
        if isinstance(t, str):
            new = scrub(rel, t)
            if new != t:
                pages[rel] = new
                n += 1
    return n
