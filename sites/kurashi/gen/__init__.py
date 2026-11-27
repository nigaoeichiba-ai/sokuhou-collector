"""Writes sites/kurashi/content/*.json and site.json from the pages of gen/pages_*.py.

    python -m sites.kurashi.gen            (from sokuhou-collector/)

The content is generated because every date, weekday and day count is computed (the deadlines move every year); the JSON is what the build reads.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import deadlines, extras, pages_hub, pages_life, pages_money, shop_links
from .common import CHECKED, SITE_UPDATED, sources_json
from .titles import TITLES

SITE = Path(__file__).resolve().parent.parent


def all_pages() -> list[dict]:
    pages = pages_hub.pages() + pages_money.pages() + pages_life.pages()
    more = extras.extras()
    for p in pages:
        p["sections"] = p["sections"] + more.pop(p["path"], [])
        p["title"], p["h1"] = TITLES[p["path"]]
        if p["path"] in deadlines.BY_PAGE:
            p["deadline_ids"] = deadlines.BY_PAGE[p["path"]]
        if p["path"] == "/method/":
            p["primary_kw"] = "初日不算入"
    assert not more, f"extras for pages that do not exist: {list(more)}"
    for p in pages:
        if p["path"] in shop_links.A8_SECTIONS:
            p["sections"].append(shop_links.a8_section(p["path"]))
        if p["path"] in shop_links.AT_SECTIONS:
            p["sections"].extend(shop_links.at_sections(p["path"]))
        if p["path"] in shop_links.SHOP_PAGES:
            p["sections"].append(shop_links.section(p["path"]))
    return pages


def file_name(path: str) -> str:
    return "home.json" if path == "/" else re.sub(r"[^a-z0-9]+", "-", path.strip("/").lower()).strip("-") + ".json"


def site_json() -> dict:
    return {
        "og_image": "/assets/og.jpg",          # the share image (1200x630) made by `newsite og`; without this line the share tags disappear
        "glyph": "暦",
        "updated": SITE_UPDATED,
        "home_label": "トップ",
        "nav": [["月別", "/month/", "/month/"], ["人生の節目", "/life/", "/life/"], ["引っ越し", "/moving/", "/moving/"], ["確定申告", "/kakutei-shinkoku/", "/kakutei-shinkoku/"],
                ["期限の数え方", "/method/", "/method/"]],
        "footer_html": "公式の発表をはじめとする複数の情報をもとにしています。",
        "purpose": "暮らしの手続きと準備を、月ごとと出来事ごとに、期限つきで整理して載せること。期限は法律の条文などで確かめ、日付と曜日は計算で出します。",
        "update_text": f"期限は毎年変わるので、毎年11月に制度の変更と法令を見直します。直した項目は、ページの最終更新日が変わります。最初の確認は{CHECKED}です。",
        "disclaimer": [
            "このサイトは、制度の事実と手順を載せるもので、個別の事情への助言はしません。税金・年金・保険・届出の判断は、税務署・市区町村・勤務先などの窓口で確かめておきましょう。",
            "期限は、法律の改正や制度の見直しで変わります。手続きの前に、窓口の案内で最新の内容を確認してください。",
        ],
        "method": [
            "法令の条文をはじめ、複数の情報を確かめて書いています。",
            "日付・曜日・起点からの日数は、手で書かずにプログラムで計算します。確認できなかったことは書きません。",
        ],
        "corrections": [],
        "sources_style": "credit",
        "credits": ["公式の発表をはじめとする複数の情報をもとにしています。"],
        "sources": sources_json(),
        "deadlines": deadlines.catalog_json(),
    }


def main() -> None:
    pages = all_pages()
    content = SITE / "content"
    for f in content.glob("*.json"):
        f.unlink()
    for p in pages:
        (content / file_name(p["path"])).write_text(json.dumps(p, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (SITE / "site.json").write_text(json.dumps(site_json(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(pages)} pages written to {content}")


if __name__ == "__main__":
    main()
