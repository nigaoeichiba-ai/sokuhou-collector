"""大津市(滋賀県)のクマの目撃情報: 件数と最新の日付だけを保存する。

大津市のホームページは、著作権の項で、引用などを除く無断の複製・転用を認めておらず、再利用の許可を明示していない。だから、他の「許可が明示されていない取得元」と同じに、
市町村・月・件数・最新の日付だけを集計し、場所・座標・説明は、取得も保存もしない(市の「目撃情報一覧」の、日付の見出しだけを読む。場所の行は、読まない)。
取得は、市のページから、robots.txt を確認して、名乗って行う(kumalib.polite_fetch)。以前は、市が公開している Google マイマップの座標つきの記録を載せていたが、やめた。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime

from sokuhou.sources import kumalib

PAGE = "https://www.city.otsu.lg.jp/soshiki/025/1605/g/t/74581.html"
CITY = "大津市"
CREDIT = ("出典: 大津市「熊の目撃情報(令和8年度)」(" + PAGE + ")の公開ページから、市町村別・月別の件数だけを、当サイトが集計して作成"
          "(場所などの詳しい記録は、大津市のページでご確認ください。大津市が作成したものではありません)")
UPDATE_NOTE = "大津市が、随時更新します(更新には数日かかることがあります)。件数は、目撃のほか、痕跡や錯誤捕獲の報告を含みます"
MIN_ROWS = 5
HEADING = "目撃情報一覧"
ENTRY = re.compile(r"<h3[^>]*>\s*令和\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日[^<]*</h3>")


class OtsuKumaSourceError(ValueError):
    pass


def parse(html: str, now: datetime | None = None) -> dict:
    """The dated headings under 「目撃情報一覧」 only (nothing else of an entry is read)."""
    now = now or datetime.now(kumalib.JST)
    today = now.astimezone(kumalib.JST).date()
    at = html.find(HEADING)
    if at < 0:
        raise OtsuKumaSourceError(f"the heading {HEADING!r} is gone (the page changed)")
    rows, bad = [], 0
    for m in ENTRY.finditer(html, at):
        year, month, day = 2018 + int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            d = date(year, month, day)
        except ValueError:
            bad += 1
            continue
        if (d - today).days > 2:      # a date after today + 2 days is a typo
            bad += 1
            continue
        rows.append({"observed_at": d.isoformat(), "city": CITY})
    if len(rows) < MIN_ROWS:
        raise OtsuKumaSourceError(f"too few entries: {len(rows)} < {MIN_ROWS}")
    if bad > max(1, len(rows) // 50):
        raise OtsuKumaSourceError(f"too many entries without a readable date: {bad}")
    as_of = max(date.fromisoformat(r["observed_at"]) for r in rows)
    return kumalib.package_counts(source="otsu", credit=CREDIT, update_note=UPDATE_NOTE, as_of=as_of, rows=rows, page=PAGE, files=[PAGE], unparsed=bad)


def collect(fetch=None, now: datetime | None = None) -> dict:
    fetch = fetch or kumalib.polite_fetch
    return parse(fetch(PAGE).decode("utf-8", "replace"), now)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
