"""石狩市(北海道)「石狩市ヒグマ出没情報」: 石狩市が、自市のオープンデータとして公開している ArcGIS の Web マップ(CC BY 4.0・石狩市の承諾は不要)の、点のレイヤー。

石狩市のオープンデータ利用規約(https://www.city.ishikari.hokkaido.jp/_res/projects/default_project/_page_/001/002/441/1002441_002.pdf)は、公開するデータを
CC BY 4.0 で利用できるとし、改変して使うときは、出典と改変したことを書き、石狩市が作成したかのように公表しないよう求めている。石狩市のオープンデータの Hub
(https://environment-ishikari.hub.arcgis.com)には、このマップが「CC-BY-4.0」として載っている。
取得するのは、日時・場所・種類の3列と、点の座標だけ(「経緯」の自由記述は、取得も保存もしない)。日時は文字(令和8年10月8日(木曜日) 17時40分頃、数字が全角のものもある)なので、
日付と時刻に読み直す。「年度」の列は、「令和7」「最新」など、そろっていないので、使わない(日付から数える)。
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import date, datetime, time, timedelta
from urllib.parse import quote, urlencode

from sokuhou.sources import kumalib

LAYER = "https://services7.arcgis.com/9WKv3OOuUkGgAibZ/arcgis/rest/services/" + quote("石狩市ヒグマ出没情報") + "/FeatureServer/0"
PAGE = "https://www.city.ishikari.hokkaido.jp/kurashi/kankyo/1001830/1002415.html"
CREDIT = ("出典:石狩市「石狩市ヒグマ出没情報」(石狩市オープンデータ、"
          "クリエイティブ・コモンズ・ライセンス表示4.0国際 https://creativecommons.org/licenses/by/4.0/deed.ja)の日時・場所・種類・座標を、当サイトが整理して利用しています"
          "(改変しています。石狩市が作成したものではありません)")
UPDATE_NOTE = "石狩市が、通報を受けて、随時更新します。「ヒグマらしき動物」は、目撃(らしき)として載せています"
FIELDS = ("OBJECTID", "日時", "場所", "種類")
MIN_ROWS = 100
UNPARSED_LIMIT = 0.03
PAGE_SIZE = 1000
MAX_PAGES = 20
PREFIX_CITIES = ("石狩市", "札幌市", "当別町", "小樽市", "江別市", "新篠津村", "増毛町", "北広島市")
DATE = re.compile(r"令和\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日")
TIME = re.compile(r"(\d{1,2})\s*時\s*(?:(\d{1,2})\s*分)?")
TRACE_WORDS = ("糞", "足跡", "痕跡", "爪", "食痕")


class IshikariKumaSourceError(ValueError):
    pass


def query_url(offset: int) -> str:
    params = {"where": "1=1", "outFields": ",".join(FIELDS), "returnGeometry": "true", "outSR": 4326, "orderByFields": "OBJECTID",
              "resultOffset": offset, "resultRecordCount": PAGE_SIZE, "f": "json"}
    return f"{LAYER}/query?{urlencode(params, quote_via=quote)}"


def parse_when(raw: object) -> tuple[date, time | None] | None:
    text = unicodedata.normalize("NFKC", str(raw or ""))
    m = DATE.search(text)
    if not m:
        return None
    try:
        day = date(2018 + int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    t = TIME.search(text[m.end():])
    clock = None
    if t:
        try:
            clock = time(int(t.group(1)), int(t.group(2) or 0))
        except ValueError:
            clock = None
    return day, clock


def kind_of(species: object) -> str:
    s = str(species or "")
    if any(w in s for w in TRACE_WORDS):
        return "痕跡"
    if "らしき" in s or "ような" in s:
        return "目撃(ヒグマらしき)"
    return "目撃"


def city_and_place(raw: object) -> tuple[str, str]:
    text = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(raw or ""))).strip()
    for c in PREFIX_CITIES:
        if text.startswith(c):
            return c, text[len(c):].strip()
    return "石狩市", text


def build(features: list[dict], today: date) -> tuple[list[dict], int]:
    rows, bad = [], 0
    newest_ok = today + timedelta(days=2)
    for f in features:
        a = f.get("attributes") or {}
        when = parse_when(a.get("日時"))
        if when is None or when[0] > newest_ok:
            bad += 1
            continue
        day, clock = when
        city, place = city_and_place(a.get("場所"))
        g = f.get("geometry") or {}
        lon, lat = g.get("x"), g.get("y")
        rec = {"observed_at": datetime.combine(day, clock, kumalib.JST).isoformat() if clock else day.isoformat(), "city": city, "place": place, "count": None,
               "kind": kind_of(a.get("種類")), "species": "ヒグマ"}
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and 41 <= lat <= 46 and 139 <= lon <= 146:
            rec.update(kumalib.coord(lat, lon))
        rows.append(rec)
    return rows, bad


def collect(fetch=None, now: datetime | None = None, sleep=None) -> dict:
    import time as _time
    fetch = fetch or kumalib.polite_fetch
    sleep = sleep or _time.sleep
    today = (now or datetime.now(kumalib.JST)).astimezone(kumalib.JST).date()
    info = _json(fetch(f"{LAYER}?f=json"), "layer")
    have = {f.get("name") for f in info.get("fields", [])}
    if not set(FIELDS) <= have or info.get("geometryType") != "esriGeometryPoint":
        raise IshikariKumaSourceError(f"the layer changed: columns {sorted(map(str, have))}")
    features, offset = [], 0
    for _ in range(MAX_PAGES):
        sleep(1.0)
        data = _json(fetch(query_url(offset)), "query")
        got = data.get("features")
        if not isinstance(got, list):
            raise IshikariKumaSourceError("query: no 'features' list")
        features.extend(got)
        if not got or not data.get("exceededTransferLimit"):
            break
        offset += len(got)
    else:
        raise IshikariKumaSourceError(f"query: more than {MAX_PAGES} pages")
    if len(features) < MIN_ROWS:
        raise IshikariKumaSourceError(f"too few rows: {len(features)} < {MIN_ROWS}")
    rows, bad = build(features, today)
    if bad / len(features) > UNPARSED_LIMIT:
        raise IshikariKumaSourceError(f"too many rows without a readable date: {bad}/{len(features)}")
    as_of = max(date.fromisoformat(r["observed_at"][:10]) for r in rows)
    return kumalib.package(source="ishikari", credit=CREDIT, update_note=UPDATE_NOTE, as_of=as_of, sightings=rows, page=PAGE, files=[LAYER], unparsed=bad)


def _json(body: bytes, what: str) -> dict:
    try:
        data = json.loads(body)
    except ValueError as e:
        raise IshikariKumaSourceError(f"{what}: not JSON ({e})") from e
    if not isinstance(data, dict) or "error" in data:
        raise IshikariKumaSourceError(f"{what}: error answer: {str(data)[:200]}")
    return data


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
