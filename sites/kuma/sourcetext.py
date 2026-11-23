"""画面の本文・表・見出しから、情報元の名前(環境省)を外す(オーナー指示 2026-11-15/17『情報元の具体的な記載は画面に出さない』、窓口の指示 2026-11-23)。

title・description・h1 は originnames.py が受け持つ。ここは、ページ全体の文章に残る『環境省の表』『環境省が…』のような出どころの言い方を、
『公的な表』『国が…』のような一般的な言い方に置き換える。残すのは、ライセンスの必須表記(『出典:環境省…を加工して作成。環境省が作成したものではありません』)だけ。
ビルドの最後(originnames のあと)に、全ページへかける。元の文章(各 .py・data)は変えない: 数字・日付・計算は触らない。
"""
from __future__ import annotations

import re

from sites.kuma.originnames import SUBJECT_PAGES, _H1, _META, _TITLE

CREDIT = re.compile(r"出典: ?環境省.*?環境省が作成したものではありません|環境省[^<>。]*?加工して作成したもので、環境省・自治体が作成したものではありません", re.S)     # the licence credit and the same-meaning disclaimer(免責・引用の説明)
RULES = [
    (re.compile(r"環境省「[^」]*」"), "国の公表資料"),
    (re.compile(r"[(（]環境省・"), "("),
    (re.compile(r"[(（]環境省[)）]"), "(公的な統計)"),
    (re.compile(r"環境省・"), "国・"),
    (re.compile(r"環境省(?=[(（]\d)"), "公的な表"),
    (re.compile(r"÷環境省"), "÷公的な表"),
    (re.compile(r"環境省(?=は|が)"), "国"),
    (re.compile(r"環境省の(?=表|統計|資料|一覧|数字|出没件数|許可捕獲数|死亡事故|速報値|<strong>速報値|集計|件数|出没情報|人身被害|クマのデータ|堅果)"), "公的な"),
    (re.compile(r"環境省の"), "国の"),
    (re.compile(r"環境省"), "国"),
]


def clean(text: str) -> str:
    for rx, rep in RULES:
        text = rx.sub(rep, text)
    return text


def scrub(rel: str, t: str) -> str:
    if not rel.endswith((".html", ".xml")) or "環境省" not in t:
        return t
    keep: list[str] = []

    def stash(m: re.Match) -> str:
        keep.append(m.group(0))
        return f"\x00{len(keep) - 1}\x00"
    body = CREDIT.sub(stash, t)
    if rel in SUBJECT_PAGES:        # 環境省・自治体の発表そのものが主題のページ: 題・説明・h1 は originnames.py の決まりどおり、そのまま
        for rx in (_TITLE, _META, _H1):
            body = rx.sub(stash, body)
    body = clean(body)
    return re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], body)


def scrub_all(pages: dict) -> int:
    n = 0
    for rel, t in pages.items():
        if isinstance(t, str):
            new = scrub(rel, t)
            if new != t:
                pages[rel] = new
                n += 1
    return n
