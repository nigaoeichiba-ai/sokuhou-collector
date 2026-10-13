"""新潟県(クマの出没情報・記録を一覧にする)。

新潟県環境対策課(鳥獣管理係)が、書面(メール)で回答した(2026-10-13): このサイトでの利用は可能、広告(Google AdSense 等)のあるサイトでも可、
取得の方法・頻度の希望や禁止はない。出典の表記は「新潟県鳥獣被害対策支援センター「にいがたクマ出没マップ」」のように書く、という条件。
だから「利用の許可が明示されている」取得元として、日付・市町村・地区名・種別・頭数・位置の記録を保存して載せる。通報者のアドレスや、自由記述の「出没時の状況」は、
取得も保存もしない(`outFields` は、下の FIELDS の列だけ)。
取得元: 新潟県の公式ページが埋め込む ArcGIS の公開 Web マップ(下の WEBMAP_ID)が指す、FeatureServer のレイヤー。
サービス名は毎年変わるので、レイヤーの住所は固定せず、Web マップから探す(1つに決まらなければ、保存せずに例外にする)。
"""
from __future__ import annotations

import json
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta
from urllib.parse import quote, urlencode

from sokuhou.sources import arcgis_counts, kumalib

PAGE = "https://www.pref.niigata.lg.jp/site/tyoujyutaisakusienn/241009kumamap.html"
WEBMAP_ID = "03084a546fec4551b20b302e2be3145e"
LAYER_PATTERN = r"survey123_[0-9a-f]+_results/FeatureServer/0$"
TYPE_FIELD = "field_8"       # 出没区分: 目撃 / 痕跡 / 人身
CITY_FIELD = "field_7"       # 出没市町村
AREA_FIELD = "field_17"      # 出没地区
DATE_FIELD = "field_20"      # 出没日
COUNT_FIELD = "field_26"     # 頭数 ('１頭', '不明' ...)
FIELDS = (TYPE_FIELD, CITY_FIELD, AREA_FIELD, DATE_FIELD, COUNT_FIELD)
CREDIT = ("出典: 新潟県鳥獣被害対策支援センター「にいがたクマ出没マップ」(https://www.pref.niigata.lg.jp/site/tyoujyutaisakusienn/241009kumamap.html)の公開データを、"
          "新潟県環境対策課の許可を得て、加工して作成(新潟県が作成したものではありません)")
UPDATE_NOTE = "新潟県が、ほぼ毎日更新します。最新の記録は、更新時点から遅れます。件数は、クマの目撃のほか、痕跡や人身被害の報告を含みます"
MIN_ROWS = 300
UNPARSED_LIMIT = 0.02
EMPTY_CITY_LIMIT = 0.02
MAX_PAGES = 50
FIRST_DAY = date(2019, 4, 1)
LAT_RANGE, LON_RANGE = (36.7, 38.6), (137.3, 140.1)      # Niigata prefecture (with a margin): a point outside is a typing error and is dropped


class NiigataKumaSourceError(arcgis_counts.ArcgisCountsError):
    pass


def query_url(layer: str, *, oid: str, offset: int) -> str:
    """Only the columns of FIELDS; the position in WGS84 (the report's address and the free text are not wanted)."""
    params = {"where": "1=1", "outFields": ",".join(FIELDS), "returnGeometry": "true", "outSR": 4326, "orderByFields": oid, "resultOffset": offset,
              "resultRecordCount": arcgis_counts.PAGE_SIZE, "f": "json"}
    return f"{layer}/query?{urlencode(params, quote_via=quote)}"


def fetch_rows(layer: str, oid: str, fetch, sleep) -> list[dict]:
    """[{**attributes, '_x', '_y'}]: the wanted columns and the point (nothing else of a feature is looked at)."""
    rows: list[dict] = []
    offset = 0
    for _ in range(MAX_PAGES):
        data = arcgis_counts._json(fetch(query_url(layer, oid=oid, offset=offset)), NiigataKumaSourceError, "query")
        feats = data.get("features")
        if not isinstance(feats, list):
            raise NiigataKumaSourceError("query: no 'features' list")
        for f in feats:
            g = f.get("geometry") or {}
            rows.append({**(f.get("attributes") or {}), "_x": g.get("x"), "_y": g.get("y")})
        if not feats or not data.get("exceededTransferLimit"):
            return rows
        offset += len(feats)
        sleep(arcgis_counts.PAUSE)
    raise NiigataKumaSourceError(f"query: more than {MAX_PAGES} pages")


def _bears(text: object) -> int | None:
    """'１頭' -> 1, '不明' -> None."""
    m = __import__("re").search(r"(\d+)", unicodedata.normalize("NFKC", str(text or "")))
    return int(m.group(1)) if m and int(m.group(1)) > 0 else None


def _point(a: dict) -> dict:
    x, y = a.get("_x"), a.get("_y")
    if isinstance(x, (int, float)) and isinstance(y, (int, float)) and LAT_RANGE[0] <= y <= LAT_RANGE[1] and LON_RANGE[0] <= x <= LON_RANGE[1]:
        return kumalib.coord(y, x)
    return {}


def build_sightings(rows: list[dict], names: dict[str, dict[str, str]], today: date) -> tuple[list[dict], int]:
    """(sightings, rows that could not be used; rows before FIRST_DAY are skipped)."""
    out: list[dict] = []
    bad = 0
    newest_ok = today + timedelta(days=2)
    for a in rows:
        d = arcgis_counts._day(a.get(DATE_FIELD))
        city = arcgis_counts.norm_city(names.get(CITY_FIELD, {}).get(str(a.get(CITY_FIELD)), str(a.get(CITY_FIELD) or "")), "新潟県")
        if d is not None and d < FIRST_DAY:
            continue
        if d is None or d > newest_ok or not city:
            bad += 1
            continue
        kind = names.get(TYPE_FIELD, {}).get(str(a.get(TYPE_FIELD)), str(a.get(TYPE_FIELD) or "")).strip() or "目撃"
        out.append({"observed_at": d.isoformat(), "city": city, "place": str(a.get(AREA_FIELD) or "").strip(), "count": _bears(a.get(COUNT_FIELD)), "kind": kind,
                    "species": "ツキノワグマ", **_point(a)})
    return out, bad


def domains(info: dict) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for f in info.get("fields", []):
        dom = f.get("domain") or {}
        if dom.get("type") == "codedValue":
            out[f["name"]] = {str(c["code"]): str(c["name"]) for c in dom.get("codedValues", [])}
    return out


def collect(fetch=None, sleep=None, now: datetime | None = None) -> dict:
    fetch = fetch or kumalib.polite_fetch
    sleep = sleep or time.sleep
    today = (now or datetime.now(kumalib.JST)).astimezone(kumalib.JST).date()
    webmap = arcgis_counts._json(fetch(f"{arcgis_counts.PORTAL}{WEBMAP_ID}/data?f=json"), NiigataKumaSourceError, "web map")
    layer = arcgis_counts.layer_url_from_webmap(webmap, LAYER_PATTERN, NiigataKumaSourceError)
    sleep(arcgis_counts.PAUSE)
    info = arcgis_counts._json(fetch(f"{layer}?f=json"), NiigataKumaSourceError, "layer")
    oid, _ = arcgis_counts.check_layer(info, DATE_FIELD, CITY_FIELD, NiigataKumaSourceError)
    missing = [f for f in FIELDS if f not in {x.get("name") for x in info.get("fields", [])}]
    if missing:
        raise NiigataKumaSourceError(f"columns are gone: {missing}")
    sleep(arcgis_counts.PAUSE)
    rows = fetch_rows(layer, oid, fetch, sleep)
    if len(rows) < MIN_ROWS:
        raise NiigataKumaSourceError(f"too few rows: {len(rows)} < {MIN_ROWS}")
    sightings, bad = build_sightings(rows, domains(info), today)
    if not sightings:
        raise NiigataKumaSourceError("no usable rows")
    if bad / len(rows) > max(UNPARSED_LIMIT, EMPTY_CITY_LIMIT):
        raise NiigataKumaSourceError(f"too many unusable rows (no readable date or municipality): {bad}/{len(rows)}")
    as_of = max(date.fromisoformat(s["observed_at"]) for s in sightings)
    return kumalib.package(source="niigata", credit=CREDIT, update_note=UPDATE_NOTE, as_of=as_of, sightings=sightings, page=PAGE, files=[layer],
                           unparsed=bad)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write(chr(10))
