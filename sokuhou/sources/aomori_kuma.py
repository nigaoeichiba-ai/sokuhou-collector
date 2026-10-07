"""青森県「くまログあおもり」(クマの出没情報・件数だけを保存する)。

くまログあおもりの利用規約(https://kumalog-aomori.info/term)は、第4条で「当サイトに掲載されている個々の情報(文章、写真等)は、著作権の対象となっています」とし、
再利用を許す記載はない。だから、応答のうち `sighting_datetime`(日付)・`municipality_name`(市町村)・`verified`(確認状況)の3つだけを読み、
メモリの中で数えて、件数と最新日だけを保存する。住所・座標・自由記述(`sighting_condition`)などは、読んだ直後に捨てる。
住民の投稿には、県が確認していないもの(`verified` が 0 =「未確認」)が混ざる(令和8年度は約36%)。数えるのは、確認済み(`verified` が 1)だけ。
期間は、月ごとに分けて、1秒以上あけて取得する(1月〜3月は1回)。
"""
from __future__ import annotations

import json
import sys
from calendar import monthrange
from datetime import date, datetime
from urllib.parse import quote

from sokuhou.sources import kumacounts

PAGE = "https://kumalog-aomori.info/"
API = "https://kumalog-aomori.info/api/ver1/sightings/post_list_external"
BEAR = 1   # animal_species_ids[] = 1 (ツキノワグマ)
CREDIT = ("出典: 青森県「くまログあおもり」(https://kumalog-aomori.info/)の公開データから、市町村別・月別の件数だけを、当サイトが集計して作成"
          "(場所などの詳しい記録は、くまログあおもりでご確認ください。青森県が作成したものではありません)")
UPDATE_NOTE = ("青森県が、ほぼ随時更新します。住民の投稿のうち、県が確認していないもの(未確認)は数えていないため、投稿から数日たって、件数が増えることがあります。"
               "件数は、目撃のほか、痕跡や人身被害の報告を含みます")
MIN_ROWS = 300
UNPARSED_LIMIT = 0.02
EMPTY_CITY_LIMIT = 0.03


class AomoriKumaSourceError(ValueError):
    pass


def fetch(url: str) -> bytes:
    return kumacounts.fetch(url)


def periods(today: date) -> list[tuple[date, date]]:
    """January-March of the fiscal year's calendar year in one request, then one request per month up to this month."""
    y = kumacounts.window_start(today).year
    out = [(date(y, 1, 1), date(y, 3, 31))]
    d = date(y, 4, 1)
    while d <= today:
        out.append((d, date(d.year, d.month, monthrange(d.year, d.month)[1])))
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return out


def url_for(start: date, end: date) -> str:
    return (f"{API}?filter[startdate]={start.isoformat()}&filter[enddate]={end.isoformat()}&filter[animal_species_ids][]={BEAR}"
            .replace("[", quote("[")).replace("]", quote("]")))


def _day(text: object) -> date | None:
    try:
        return date.fromisoformat(str(text)[:10])
    except ValueError:
        return None


def read_rows(body: bytes) -> tuple[list[tuple[int, date | None, object]], int]:
    """([(id, date, municipality)] of the confirmed records, number of unconfirmed records skipped).  Nothing else of a record is kept."""
    data = kumacounts.load_json(body, AomoriKumaSourceError, "api")
    result = data.get("result")
    if not isinstance(result, list) or data.get("count") != len(result):
        raise AomoriKumaSourceError("api: 'result' is missing, or 'count' does not match it")
    rows, skipped = [], 0
    for r in result:
        if not isinstance(r, dict) or not {"id", "sighting_datetime", "municipality_name", "verified"} <= set(r):
            raise AomoriKumaSourceError("api: a record lost one of id / sighting_datetime / municipality_name / verified")
        if r["verified"] != 1:
            skipped += 1
            continue
        rows.append((r["id"], _day(r["sighting_datetime"]), r["municipality_name"]))
    return rows, skipped


def collect(now: datetime | None = None) -> dict:
    today = kumacounts.today_jst(now)
    by_id: dict[int, tuple[date | None, object]] = {}
    for i, (start, end) in enumerate(periods(today)):
        if i:
            kumacounts.pause()
        rows, _skipped = read_rows(fetch(url_for(start, end)))
        for rid, day, city in rows:
            by_id[rid] = (day, city)
    return kumacounts.build_counts(
        list(by_id.values()), error=AomoriKumaSourceError, today=today, source="aomori", credit=CREDIT, update_note=UPDATE_NOTE, page=PAGE,
        files=[API], min_rows=MIN_ROWS, unparsed_limit=UNPARSED_LIMIT, empty_limit=EMPTY_CITY_LIMIT)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
