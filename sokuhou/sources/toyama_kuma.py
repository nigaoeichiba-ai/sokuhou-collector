"""富山県(クマの出没情報・記録を一覧にする)。

富山県自然保護課が、2026-10-06 の問い合わせに書面(メール)で回答した: このサイトでの利用は可能、出典の表記や条件は特にない、広告のあるサイトでも可、
取得の方法・頻度の希望や禁止もない。だから「利用の許可が明示されている」取得元として、日付・市町村・地区名・種別・頭数の記録を保存して載せる。
問い合わせで「位置座標や、個人が特定され得る情報は掲載しない」と約束したので、座標(`returnGeometry=false`)と自由記述の「概要」・通報者の欄は、取得も保存もしない
(`outFields` は、下の FIELDS の列だけ)。
取得元: 富山県の公式ページが埋め込む ArcGIS の公開 Web マップ(下の WEBMAP_ID)が指す、FeatureServer のレイヤー。
サービス名は毎年変わるので、レイヤーの住所は固定せず、Web マップから探す(1つに決まらなければ、保存せずに例外にする)。
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timedelta
from urllib.parse import quote, urlencode

from sokuhou.sources import arcgis_counts, kumalib

PAGE = "https://www.pref.toyama.jp/1709/kurashi/kankyoushizen/shizen/yaseiseibutsu/kumap.html"
WEBMAP_ID = "778bb8dbaf1b4f46a2a07c17d15528a1"
LAYER_PATTERN = r"survey123_[0-9a-f]+_results/FeatureServer/0$"
TYPE_FIELD = "HoukokuType"
DATE_FIELD = "HasseiDateTime"
CITY_FIELD = "HasseiCity"
AREA_FIELD = "HasseiArea"
BEAR_FIELDS = ("BearAdult", "BearYoung", "BearUnknown")
FIELDS = (TYPE_FIELD, DATE_FIELD, CITY_FIELD, AREA_FIELD, *BEAR_FIELDS)
CREDIT = ("出典: 富山県「富山県ツキノワグマ出没情報地図【クマっぷ】」(https://www.pref.toyama.jp/1709/kurashi/kankyoushizen/shizen/yaseiseibutsu/kumap.html)の公開データを、"
          "富山県自然保護課の許可を得て、加工して作成(富山県が作成したものではありません)")
UPDATE_NOTE = "富山県が、市町村からの報告を受けて、ほぼ随時更新します。件数は、クマの目撃のほか、痕跡や人身被害の報告を含みます"
MIN_ROWS = 100
UNPARSED_LIMIT = 0.02
EMPTY_CITY_LIMIT = 0.02
MAX_PAGES = 50
FIRST_DAY = date(2019, 4, 1)   # the site labels fiscal years R01 (2019) onward; older rows of the layer (2016-2018) are left out


class ToyamaKumaSourceError(arcgis_counts.ArcgisCountsError):
    pass


def query_url(layer: str, *, oid: str, offset: int) -> str:
    """Only the columns of FIELDS, and no geometry (the coordinates and the free text are not wanted)."""
    params = {"where": "1=1", "outFields": ",".join(FIELDS), "returnGeometry": "false", "orderByFields": oid, "resultOffset": offset,
              "resultRecordCount": arcgis_counts.PAGE_SIZE, "f": "json"}
    return f"{layer}/query?{urlencode(params, quote_via=quote)}"


def fetch_rows(layer: str, oid: str, fetch, sleep) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    for _ in range(MAX_PAGES):
        data = arcgis_counts._json(fetch(query_url(layer, oid=oid, offset=offset)), ToyamaKumaSourceError, "query")
        feats = data.get("features")
        if not isinstance(feats, list):
            raise ToyamaKumaSourceError("query: no 'features' list")
        rows.extend(f.get("attributes") or {} for f in feats)
        if not feats or not data.get("exceededTransferLimit"):
            return rows
        offset += len(feats)
        sleep(arcgis_counts.PAUSE)
    raise ToyamaKumaSourceError(f"query: more than {MAX_PAGES} pages")


def _bears(a: dict) -> int | None:
    """Adults + young + unknown; None when no number is given (or the sum is 0)."""
    total = sum(int(v) for v in (a.get(f) for f in BEAR_FIELDS) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0)
    return total or None


def build_sightings(rows: list[dict], names: dict[str, dict[str, str]], today: date) -> tuple[list[dict], int]:
    """(sightings, rows that could not be used; rows before FIRST_DAY are skipped, not counted as unusable).  names: the layer's coded-value domains {field: {code: name}}."""
    out: list[dict] = []
    bad = 0
    newest_ok = today + timedelta(days=2)
    for a in rows:
        d = arcgis_counts._day(a.get(DATE_FIELD))
        city = arcgis_counts.norm_city(names.get(CITY_FIELD, {}).get(str(a.get(CITY_FIELD)), str(a.get(CITY_FIELD) or "")), "富山県")
        if d is not None and d < FIRST_DAY:
            continue
        if d is None or d > newest_ok or not city:
            bad += 1
            continue
        kind = names.get(TYPE_FIELD, {}).get(str(a.get(TYPE_FIELD)), str(a.get(TYPE_FIELD) or "")).strip() or "目撃"
        out.append({"observed_at": d.isoformat(), "city": city, "place": str(a.get(AREA_FIELD) or "").strip(), "count": _bears(a), "kind": kind,
                    "species": "ツキノワグマ"})
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
    webmap = arcgis_counts._json(fetch(f"{arcgis_counts.PORTAL}{WEBMAP_ID}/data?f=json"), ToyamaKumaSourceError, "web map")
    layer = arcgis_counts.layer_url_from_webmap(webmap, LAYER_PATTERN, ToyamaKumaSourceError)
    sleep(arcgis_counts.PAUSE)
    info = arcgis_counts._json(fetch(f"{layer}?f=json"), ToyamaKumaSourceError, "layer")
    oid, _ = arcgis_counts.check_layer(info, DATE_FIELD, CITY_FIELD, ToyamaKumaSourceError)
    missing = [f for f in FIELDS if f not in {x.get("name") for x in info.get("fields", [])}]
    if missing:
        raise ToyamaKumaSourceError(f"columns are gone: {missing}")
    sleep(arcgis_counts.PAUSE)
    rows = fetch_rows(layer, oid, fetch, sleep)
    if len(rows) < MIN_ROWS:
        raise ToyamaKumaSourceError(f"too few rows: {len(rows)} < {MIN_ROWS}")
    sightings, bad = build_sightings(rows, domains(info), today)
    if not sightings:
        raise ToyamaKumaSourceError("no usable rows")
    if bad / len(rows) > max(UNPARSED_LIMIT, EMPTY_CITY_LIMIT):
        raise ToyamaKumaSourceError(f"too many unusable rows (no readable date or municipality): {bad}/{len(rows)}")
    as_of = max(date.fromisoformat(s["observed_at"]) for s in sightings)
    return kumalib.package(source="toyama", credit=CREDIT, update_note=UPDATE_NOTE, as_of=as_of, sightings=sightings, page=PAGE, files=[layer],
                           unparsed=bad)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
