"""群馬県(クマの出没情報。件数と、場所つきの記録を保存する)。

群馬県の「クマ出没マップ」(ArcGIS の FeatureServer。県のページ https://www.pref.gunma.jp/page/7141.html から案内されている)の行を読む。
県のサイトの著作権の案内は「無断で複製・転用することはできません」(引用など著作権法で認められる場合を除く)で、再利用の許可は明示されていない。
しかし、この一覧は、他の複数のサイト(クマの出没を集めた民間のサイトなど)が同じ内容を載せている(2026-10-13 に確認)。
オーナーの方針(2026-10-13)「2媒体以上に同じ内容があれば、広く公開された事実として掲載する」に従い、場所つきの記録を保存する(`corroborated.py`)。座標・自由記述は保存しない。

県の表には市町村の列がない。「場所」の文字列の先頭から市町村を割り出す(郡名は除く。合併前の町村名は、いまの市町村に直す)。
先頭に市町村名がない行(「県道○○線 ○○付近」など)は、市町村別の表では「市町村が分からないもの」にまとめる。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime

from sokuhou.sources import corroborated, kumacounts

PAGE = "https://www.pref.gunma.jp/page/7141.html"
LAYER = "https://services7.arcgis.com/DkC6f6v0YUQX0rke/arcgis/rest/services/survey123_a77f33a9b9f649cfada5c7983c67874b_results/FeatureServer/0"
DATE_FIELD = "field_18"
PLACE_FIELD = "field_11"
COUNT_FIELD = "field_8"
NOTE_FIELD = "field10"
PAGE_SIZE = 1000
UNKNOWN = "市町村が分からないもの"
CREDIT = ("出典: 群馬県「クマ出没マップ」(https://www.pref.gunma.jp/page/7141.html)の公開データから、市町村別・月別の件数を、当サイトが集計して作成"
          "(群馬県が作成したものではありません)")
UPDATE_NOTE = ("群馬県が、ほぼ随時更新します。最新の記録は、更新時点から遅れます。県の表には市町村の欄がないため、場所の書き方から市町村を割り出しています"
               "(市町村名が書かれていないものは、「市町村が分からないもの」にまとめています)。件数は、目撃のほか、痕跡の報告を含みます")
MIN_ROWS = 100
UNPARSED_LIMIT = 0.03
EMPTY_CITY_LIMIT = 0.0       # an unreadable place never counts as "no municipality": it goes to UNKNOWN

MUNICIPALITIES = ["前橋市", "高崎市", "桐生市", "伊勢崎市", "太田市", "沼田市", "館林市", "渋川市", "藤岡市", "富岡市", "安中市", "みどり市", "榛東村", "吉岡町",
                  "上野村", "神流町", "下仁田町", "南牧村", "甘楽町", "中之条町", "長野原町", "嬬恋村", "草津町", "高山村", "東吾妻町", "片品村", "川場村", "昭和村",
                  "みなかみ町", "玉村町", "板倉町", "明和町", "千代田町", "大泉町", "邑楽町"]
FORMER = {"松井田町": "安中市", "妙義町": "富岡市", "利根町": "沼田市", "白沢町": "沼田市", "倉渕町": "高崎市", "榛名町": "高崎市", "箕郷町": "高崎市",
          "群馬町": "高崎市", "吉井町": "高崎市", "新里町": "桐生市", "黒保根町": "桐生市", "赤城村": "渋川市", "北橘村": "渋川市", "小野上村": "渋川市",
          "子持村": "渋川市", "伊香保町": "渋川市", "月夜野町": "みなかみ町", "水上町": "みなかみ町", "新治村": "みなかみ町", "笠懸町": "みどり市",
          "大間々町": "みどり市", "大胡町": "前橋市", "宮城村": "前橋市", "粕川町": "前橋市", "境町": "伊勢崎市", "赤堀町": "伊勢崎市", "尾島町": "太田市",
          "新田町": "太田市", "藪塚本町": "太田市", "吾妻町": "東吾妻町"}


class GunmaKumaSourceError(ValueError):
    pass


def fetch(url: str) -> bytes:
    return kumacounts.fetch(url)


def clean_place(text: object) -> str:
    return re.sub(r"[\s　]+", " ", str(text or "")).strip()


def city_of(place: str) -> str:
    """The municipality a place text starts with (county name dropped, a merged town named by today's municipality), else UNKNOWN."""
    p = re.sub(r"^[^\s市町村]{1,4}郡", "", clean_place(place))
    for m in sorted(MUNICIPALITIES, key=len, reverse=True):
        if p.startswith(m):
            return m
    for old, new in FORMER.items():
        if p.startswith(old):
            return new
    return UNKNOWN


def read_rows(features: list[dict]) -> list[dict]:
    """[{day, place, city, count, note}] of every feature; a feature without the date or the place column is an error (the layer changed)."""
    out = []
    for f in features:
        a = f.get("attributes") if isinstance(f, dict) else None
        if not isinstance(a, dict) or DATE_FIELD not in a or PLACE_FIELD not in a:
            raise GunmaKumaSourceError(f"a feature lost {DATE_FIELD} / {PLACE_FIELD}")
        place = clean_place(a[PLACE_FIELD])
        out.append({"day": kumacounts.jst_date(a[DATE_FIELD]), "place": place, "city": city_of(place), "count": a.get(COUNT_FIELD),
                    "note": str(a.get(NOTE_FIELD) or "")})
    return out


def records(rows: list[dict]) -> list[dict]:
    """The rows as stored records (date, municipality, place, kind, count), the ones with a known municipality and a place only."""
    out = []
    for r in rows:
        if r["day"] is None or not r["place"]:
            continue
        count = r["count"]
        kind = corroborated.kind_of(r["note"]) if r["note"] else "目撃"
        out.append({"observed_at": r["day"].isoformat(), "city": r["city"], "place": r["place"][:corroborated.MAX_PLACE], "kind": kind,
                    "count": count if isinstance(count, int) and not isinstance(count, bool) and count > 0 else None})
    return out


def collect(now: datetime | None = None) -> dict:
    today = kumacounts.today_jst(now)
    since = kumacounts.window_start(today)
    where = f"{DATE_FIELD} >= timestamp '{since.isoformat()} 00:00:00'"
    params = {"where": where, "outFields": f"{DATE_FIELD},{PLACE_FIELD},{COUNT_FIELD},{NOTE_FIELD}", "returnGeometry": "false", "orderByFields": "objectid"}
    feats = kumacounts.query_all(fetch, LAYER, params, error=GunmaKumaSourceError, page_size=PAGE_SIZE)
    rows = read_rows(feats)
    result = kumacounts.build_counts(
        [(r["day"], r["city"]) for r in rows], error=GunmaKumaSourceError, today=today, source="gunma", credit=CREDIT, update_note=UPDATE_NOTE,
        page=PAGE, files=[LAYER], min_rows=MIN_ROWS, unparsed_limit=UNPARSED_LIMIT, empty_limit=EMPTY_CITY_LIMIT, require_municipality=False)
    recs = sorted(corroborated.current_year(records(rows), today), key=lambda r: (r["observed_at"], r["place"]), reverse=True)
    if recs:
        result["corroborated"] = recs
        result["corroborated_on"] = {city: today.isoformat() for city in sorted({r["city"] for r in recs})}
    return result


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
