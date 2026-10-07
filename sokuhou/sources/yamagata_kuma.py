"""山形県(クマ目撃マップの元データ・件数だけを保存する)。

山形県は、データの再利用の許可を明示していない(県サイトの著作権の案内は「複製、転用をすることはできません」)。だから、CSV の「市町村」(列名は「ユーザ名」)と
「目撃した日付」の2列だけを読み、メモリの中で月別・市町村別に数えて、件数と最新日だけを保存する。緯度・経度・地名・備考などの列は、読んだ直後に捨てる。
CSV の住所は日付入りのファイル名(`YYYYMMDD_kemonote-cleaned.csv`)で変わるので、県の「クマに関する情報」ページのリンクから探す。
CSV は暦年(1月1日から)なので、年が変わる1月には令和7年度の4〜12月分が消える。その場合は件数が足りず、保存せずに例外になる。
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from datetime import date, datetime
from urllib.parse import urljoin, urlparse

from sokuhou.sources import kumacounts

PAGE = "https://www.pref.yamagata.jp/050011/kurashi/shizen/seibutsu/about_kuma/kuma_yamagata_top.html"
LINK = re.compile(r'href="([^"]*?(\d{8})_kemonote-cleaned\.csv)"')
CITY_COLUMN = "ユーザ名"
DATE_COLUMN = "目撃した日付"
CREDIT = ("出典: 山形県「クマ目撃マップ」の元データ(https://www.pref.yamagata.jp/050011/kurashi/shizen/seibutsu/about_kuma/kuma_yamagata_top.html)から、"
          "市町村別・月別の件数だけを、当サイトが集計して作成(場所などの詳しい記録は、山形県のページでご確認ください)")
UPDATE_NOTE = "山形県が、1〜2週間ごとに更新します。最新の記録は、更新時点から遅れます。件数は、クマの目撃の報告を数えたもので、暦年(1月から)のデータから年度分を取り出しています"
MIN_ROWS = 300
UNPARSED_LIMIT = 0.02
EMPTY_CITY_LIMIT = 0.03


class YamagataKumaSourceError(ValueError):
    pass


def fetch(url: str) -> bytes:
    return kumacounts.fetch(url)


def csv_url_from_page(html: str) -> str:
    """The newest `YYYYMMDD_kemonote-cleaned.csv` link of the prefecture's page (always on the prefecture's own host)."""
    links = sorted({(m.group(2), urljoin(PAGE, m.group(1))) for m in LINK.finditer(html)})
    if not links:
        raise YamagataKumaSourceError("no kemonote-cleaned.csv link on the page")
    url = links[-1][1]
    if urlparse(url).netloc != urlparse(PAGE).netloc:
        raise YamagataKumaSourceError(f"the CSV is not on the prefecture's host: {url}")
    return url


def _day(text: str) -> date | None:
    m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", text.strip())
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def read_rows(data: bytes) -> list[tuple[date | None, str]]:
    """[(sighting date, municipality)] and nothing else: the other columns (position, place name, remarks) are never kept."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise YamagataKumaSourceError(f"CSV is not UTF-8: {e}") from e
    reader = csv.reader(io.StringIO(text))
    header = [h.strip() for h in next(reader, [])]
    if CITY_COLUMN not in header or DATE_COLUMN not in header:
        raise YamagataKumaSourceError(f"CSV header changed: {header[:6]}")
    ci, di = header.index(CITY_COLUMN), header.index(DATE_COLUMN)
    out = []
    for raw in reader:
        if not any(c.strip() for c in raw):
            continue
        out.append((_day(raw[di]) if di < len(raw) else None, raw[ci] if ci < len(raw) else ""))
    return out


def parse(data: bytes, url: str, today: date | None = None) -> dict:
    return kumacounts.build_counts(
        read_rows(data), error=YamagataKumaSourceError, today=today or kumacounts.today_jst(), source="yamagata", credit=CREDIT,
        update_note=UPDATE_NOTE, page=PAGE, files=[url], min_rows=MIN_ROWS, unparsed_limit=UNPARSED_LIMIT, empty_limit=EMPTY_CITY_LIMIT)


def collect(now: datetime | None = None) -> dict:
    url = csv_url_from_page(fetch(PAGE).decode("utf-8", "replace"))
    kumacounts.pause()
    return parse(fetch(url), url, kumacounts.today_jst(now))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
