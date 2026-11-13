# -*- coding: utf-8 -*-
"""出典表記の切り替え(オーナー決定 2026-11-14、Muse 指示 sokuhou/inbox/出典表記の切り替え_指示_2026-11-14.md)。
本文中の出典の注記・出典の節・表の出典の列・出典のリンク一覧を外し、出どころは記事の最下部の「出典:」(page の credit)にまとめる。リンクは貼らない。
文の主語として入っている出どころ(「厚生労働省が公表した数字では」など)と、価格・料金の確認日は残す。
ファイルの整形(インデントの癖)を変えないよう、文字列の置き換えで直す。置き換えのあとに JSON として読めることを確かめる。何度実行しても同じ結果になる(冪等)。"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE / "content"

# a whole section made only of "（出典：…）": the object and the comma after it go
NOTE_SECTION = re.compile(r'\{\s*"paras":\s*\[\s*"（出典：[^"]*）"\s*\]\s*\},\s*')
# "（窓口が2026年11月12日に確認）" in the credit line: the desk's own wording means nothing to a reader
DESK = re.compile(r'[（(](?:[^()（）"]*?)窓口が[0-9年月日]+に確認[）)]')


def sub_once(t: str, old: str, new: str, name: str) -> str:
    if old not in t:
        return t
    assert t.count(old) == 1, f"{name}: {old[:30]!r} found {t.count(old)} times"
    return t.replace(old, new)


changed = []
for f in sorted(C.glob("*.json")):
    t = f.read_text(encoding="utf-8")
    n = NOTE_SECTION.sub("", t)
    n = DESK.sub("", n)
    slug = f.stem
    if slug == "trend-fire-prevention-week":       # the "出典" section repeats the credit line at the end of the page
        n = re.sub(r'\{\s*"h2":\s*"出典",\s*"html":\s*"<ul>(?:[^"\\]|\\.)*</ul>"\s*\},?\s*', "", n)
        n = re.sub(r',(\s*)\]\s*\}\s*$', r'\1] }', n) if False else n
    if slug == "trend-nengajo-hayawari":
        n = sub_once(n, '"出典・確認日"', '"料金と締切の確認日"', slug)               # the checked day of the prices stays near the prices
        n = sub_once(n, "各社の公式ページ（下の出典欄）から確認できます。", "各社の公式ページから確認できます。", slug)
        # the list of the companies' price pages (links) is a source list: the credit line names the same companies and the Post Office paper
        n = re.sub(r'\{\s*"html":\s*"<ul><li><a href=\\"https://nenga\.print-netsquare\.com/info/price/\\"(?:[^"\\]|\\.)*</ul>"\s*\},?\s*', "", n)
    if slug == "trend-shichigosan":      # the table's "出典" column: the credit line at the end names the same shrines
        n = re.sub(r',\s*"出典"(\s*\])', r"\1", n)
        n = re.sub(r',\s*"(?:明治神宮|鶴岡八幡宮)公式案内"(\s*\])', r"\1", n)
    if slug == "trend-engel-coefficient":    # the last column mixed the source with a remark: keep the remark, name the sources in the credit line
        n = n.replace('"出典・系列"', '"補足"')
        for old, new in (("総務省統計局「家計調査報告 2025年平均結果の概要」。1981年以来44年ぶりの高水準", "1981年以来44年ぶりの高水準"),
                         ("総務省統計局「家計調査報告 2026年9月分」。名目4.5%減、実質6.8%減", "名目4.5%減、実質6.8%減"),
                         ("同上。名目0.2%増、実質2.5%減。用途分類の食料費とは範囲が違うため、係数の分子ではない", "名目0.2%増、実質2.5%減。用途分類の食料費とは範囲が違うため、係数の分子ではない"),
                         ("総務省統計局「家計調査」詳細結果表（用途分類）。前年同月は29.0%", "前年同月は29.0%"),
                         ("同上。収入が高い世帯ほど割合が低い", "収入が高い世帯ほど割合が低い")):
            n = n.replace(f'"{old}"', f'"{new}"')
        n = re.sub(r'"credit":\s*"[^"]*"', '"credit": "総務省統計局「家計調査報告 2025年平均結果の概要」「家計調査報告 2026年9月分」「家計調査」詳細結果表(用途分類。e-Stat)、消費者物価指数、帝国データバンクの調査をもとに作成"', n, count=1)
    if n != t:
        try:
            json.loads(n)
        except json.JSONDecodeError:       # the removed object was the last one of its list: drop the comma left before the closing bracket
            n = re.sub(r',(\s*\])', r"\1", n)
        json.loads(n)                      # must still be JSON
        f.write_bytes(n.encode("utf-8"))
        changed.append(f.name)
print("changed:", len(changed), changed)
