"""Writes sites/shiken/content/*.json and site.json from the dates in facts.py / data/ and the pages in pages_*.py.

    python -m sites.shiken.gen         (from sokuhou-collector/)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .common import CHECKED
from .sources import SOURCES

SITE = Path(__file__).resolve().parents[1]


def all_pages() -> list[dict]:
    from . import pages_hub, pages_exam, pages_nyushi, pages_deep
    out = []
    for m in (pages_hub, pages_exam, pages_nyushi, pages_deep):
        out += m.pages()
    from .extra import EXTRA, EXTRA_METHOD_TABLE
    for p in out:
        if p["path"] in EXTRA:
            p["sections"] = p["sections"][:-1] + EXTRA[p["path"]] + p["sections"][-1:] if p["sections"][-1]["h2"].startswith("最終確認") else p["sections"] + EXTRA[p["path"]]
        if p["path"] == "/method/":
            p["sections"][2]["table"] = EXTRA_METHOD_TABLE
    return [finalize(p) for p in out]


CLOSING = "最終的な日程は、主催団体の公式発表でご確認ください。日程は変更されることがあります。申し込む前に、必ず確かめてください。"
DROP = re.compile(r"(日程と金額の|日付の)?確認日は2026年11月3日です。|申込の前に、次の公式ページで[^。]*確かめてください。|申込の前に、必ず公式ページで確かめてください。")


def finalize(p: dict) -> dict:
    """The owner's rule (2026-11-03): no source URL, no 'checked on' day per row, no list of official links on a page.  What stays: the page's update day,
    one closing sentence on every page, and the method page.  (The dates are still read from the primary sources when they are made.)"""
    p["sources"] = ["official"]
    secs = []
    for s in p["sections"]:
        s = dict(s)
        s.pop("html", None) if "http" in s.get("html", "") else None
        s["paras"] = [t for t in (DROP.sub("", t).strip() for t in s.get("paras", [])) if t]
        secs.append(s)
    last = secs[-1]
    if last.get("h2") == "最終確認は公式で":
        last["paras"] = last["paras"] + [CLOSING]
    else:
        secs.append({"h2": "最終確認は公式で", "paras": [CLOSING]})
    p["sections"] = secs
    return p


def write() -> int:
    pages = all_pages()
    content = SITE / "content"
    for f in content.glob("*.json"):
        f.unlink()
    for p in pages:
        p.setdefault("updated", CHECKED)
        slug = p["path"].strip("/").replace("/", "-") or "home"
        (content / f"{slug}.json").write_text(json.dumps(p, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    site = json.loads((SITE / "site.json").read_text(encoding="utf-8"))
    site["sources"] = SOURCES
    site["updated"] = CHECKED
    site.update({
        "nav": [["日程の一覧", "/schedule/", "/schedule/"], ["締切が近い順", "/deadlines/", "/deadlines/"], ["入試", "/nyushi/", "/nyushi/"],
                ["方法と出典", "/method/", "/method/"]],
        "footer_html": "日程は、各試験団体・省庁・教育委員会の公式発表をもとにしています。最終的な日程は、主催団体の公式発表でご確認ください。",
        "purpose": "資格試験と入学試験の、申込・出願の期間、試験日、合格発表日を、公式ページで確かめた日付だけで並べること。受験する人が、締切を見落とさないための道具です。",
        "update_text": "試験団体が日程を発表したら、公式ページで日付を確かめて入れ替え、各ページの最終更新日を書き換えます。年度が替わるたびに、全ページの日付を公式ページから取り直します。直した内容は「訂正と更新の記録」に残します。",
        "disclaimer": [
            "日程は、試験団体や教育委員会が変更することがあります。申し込む前に、必ず公式ページで最新の内容を確かめてください。",
            "このサイトは、日付と制度の事実を伝えるものです。個々の受験について、出願先や受験資格の判断はしません。",
        ],
        "method": [
            "試験団体・省庁・教育委員会の公式ページを開き、日付を読み取って表に入れています。曜日と「あと何日」は日付から計算しています。",
            "公式ページに載っていない日程は、推測で補いません。その試験は、次の回が未発表であることだけを載せています。",
            "各団体の表や文章は写していません。日付や金額という事実だけを、当サイトの表に組み直しています。",
        ],
    })
    (SITE / "site.json").write_text(json.dumps(site, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(pages)


if __name__ == "__main__":
    print(write(), "pages")
