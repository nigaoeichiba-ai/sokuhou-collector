"""Writes sites/kurashi/content/*.json and site.json from the pages of gen/pages_*.py.

    python -m sites.kurashi.gen            (from sokuhou-collector/)

The content is generated because every date, weekday and day count is computed (the deadlines move every year); the JSON is what the build reads.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import pages_hub, pages_life, pages_money
from .common import CHECKED, sources_json
from .titles import TITLES

SITE = Path(__file__).resolve().parent.parent


def all_pages() -> list[dict]:
    pages = pages_hub.pages() + pages_money.pages() + pages_life.pages()
    for p in pages:
        p["title"], p["h1"] = TITLES[p["path"]]
        if p["path"] == "/method/":
            p["primary_kw"] = "初日不算入"
    return pages


def file_name(path: str) -> str:
    return "home.json" if path == "/" else re.sub(r"[^a-z0-9]+", "-", path.strip("/").lower()).strip("-") + ".json"


def site_json() -> dict:
    return {
        "glyph": "暦",
        "updated": "2026-11-03",
        "home_label": "トップ",
        "nav": [["月別", "/month/", "/month/"], ["人生の節目", "/life/", "/life/"], ["引っ越し", "/moving/", "/moving/"], ["確定申告", "/kakutei-shinkoku/", "/kakutei-shinkoku/"],
                ["期限の数え方", "/method/", "/method/"]],
        "footer_html": "期限の根拠は、法律の条文と、国税庁・日本郵便・日本年金機構・厚生労働省などの発表です。各ページの末尾に、機関名・表の名前・基準日・取得日を書いています。",
        "purpose": "暮らしの手続きと準備を、月ごとと出来事ごとに、期限つきで整理して載せること。期限の根拠は法律の条文と国の機関の発表だけにして、日付と曜日は計算で出します。",
        "update_text": f"期限は毎年変わるので、毎年11月に国税庁・日本郵便・法令を見直します。直した項目は、ページの最終更新日が変わります。最初の確認は{CHECKED}です。",
        "disclaimer": [
            "このサイトは、制度の事実と手順を載せるもので、個別の事情への助言はしません。税金・年金・保険・届出の判断は、各ページの出典と、税務署・市区町村・勤務先などの窓口で確かめてください。",
            "期限は、法律の改正や国の発表で変わります。手続きの前に、出典の公開ページで最新の内容を確認してください。",
        ],
        "method": [
            "法令は e-Gov 法令検索の条文を読み、国税庁はタックスアンサーと特集ページを、日本郵便は発表資料を読んで書いています。民間の記事は根拠にしません。",
            "日付・曜日・起点からの日数は、手で書かずにプログラムで計算します。確認できなかったことは書きません。",
        ],
        "corrections": [],
        "sources": sources_json(),
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
