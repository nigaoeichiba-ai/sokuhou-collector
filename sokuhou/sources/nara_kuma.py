"""奈良県(クマの出没情報・件数だけを保存する)。

奈良県は、データの再利用の許可を明示していない(県サイトの著作権の案内は「無断で複製・転用することはできません」。FeatureServer の説明欄も空)。
だから、ArcGIS の FeatureServer から、目撃日時(field_9)と市町村(field_6)の2列だけを取り(`outFields`、`returnGeometry=false`)、
メモリの中で月別・市町村別に数えて、件数と最新日だけを保存する。座標・状況の文章などは、取得も保存もしない。場所(大字)・目撃数・種類は、他の複数の媒体が同じ一覧を載せているため(2026-10-13のオーナーの方針)、出典を示さずに保存する。
「クマ」と「クマらしき」(field_14)は、区別せず数える。field_6 に「大台ヶ原」のような地名が入る行は、市町村名でなくても、そのまま1つの地域として数える。
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime

from sokuhou.sources import corroborated, kumacounts

PAGE = "https://www.pref.nara.jp/n118/p043003.html"
LAYER = "https://pub-gis.nsa.pref.nara.jp/server/rest/services/Hosted/survey123_492ede82f5ae450ea7171fb986f04bd0_results/FeatureServer/0"
DATE_FIELD = "field_9"
CITY_FIELD = "field_6"
PLACE_FIELD = "field_7"        # 大字
KIND_FIELD = "field_4"         # 情報種別 (目撃 / 痕跡 ...)
COUNT_FIELD = "field_10"       # 目撃数
TARGET_FIELD = "field_14"      # クマ / クマらしき
PAGE_SIZE = 1000
CREDIT = ("出典: 奈良県「ツキノワグマ出没情報」(https://www.pref.nara.jp/n118/p043003.html)の公開データから、地域別・月別の件数だけを、当サイトが集計して作成"
          "(場所などの詳しい記録は、奈良県のページでご確認ください)")
UPDATE_NOTE = ("奈良県が、ほぼ随時更新します。最新の記録は、更新時点から遅れます。件数は、「クマ」と「クマらしき」の報告を合わせたものです。"
               "地域には、「大台ヶ原」のように、市町村ではない地名で報告されたものも、そのまま含みます")
MIN_ROWS = 60
UNPARSED_LIMIT = 0.02
EMPTY_CITY_LIMIT = 0.03


class NaraKumaSourceError(ValueError):
    pass


def fetch(url: str) -> bytes:
    return kumacounts.fetch(url)


def read_rows(features: list[dict]) -> list[tuple[date | None, object]]:
    """[(date, municipality)]: the two requested columns, nothing else of a feature is looked at."""
    out = []
    for f in features:
        a = f.get("attributes") if isinstance(f, dict) else None
        if not isinstance(a, dict) or DATE_FIELD not in a or CITY_FIELD not in a:
            raise NaraKumaSourceError(f"a feature lost {DATE_FIELD} / {CITY_FIELD}")
        out.append((kumacounts.jst_date(a[DATE_FIELD]), a[CITY_FIELD]))
    return out


def read_records(features: list[dict]) -> list[dict]:
    """The prefecture's own rows with their place (大字): only because other publications carry this same list (see collect)."""
    out = []
    for f in features:
        a = f.get("attributes") if isinstance(f, dict) else None
        day = kumacounts.jst_date(a.get(DATE_FIELD)) if isinstance(a, dict) else None
        city = kumacounts.norm_city(a.get(CITY_FIELD)) if isinstance(a, dict) else ""
        if day is None or not city:
            continue
        place = str(a.get(PLACE_FIELD) or "").strip()
        if not place:
            continue
        count = a.get(COUNT_FIELD)
        out.append({"observed_at": day.isoformat(), "city": city, "place": place + ("(クマらしき動物)" if "らしき" in str(a.get(TARGET_FIELD) or "") else ""),
                    "kind": corroborated.kind_of(str(a.get(KIND_FIELD) or "目撃")), "count": count if isinstance(count, int) and not isinstance(count, bool) and count > 0 else None})
    return out


def collect(now: datetime | None = None) -> dict:
    fields = ",".join([DATE_FIELD, CITY_FIELD, PLACE_FIELD, KIND_FIELD, COUNT_FIELD, TARGET_FIELD])
    params = {"where": "1=1", "outFields": fields, "returnGeometry": "false", "orderByFields": "objectid"}
    feats = kumacounts.query_all(fetch, LAYER, params, error=NaraKumaSourceError, page_size=PAGE_SIZE)
    today = kumacounts.today_jst(now)
    result = kumacounts.build_counts(
        read_rows(feats), error=NaraKumaSourceError, today=today, source="nara", credit=CREDIT, update_note=UPDATE_NOTE,
        page=PAGE, files=[LAYER], min_rows=MIN_ROWS, unparsed_limit=UNPARSED_LIMIT, empty_limit=EMPTY_CITY_LIMIT, require_municipality=False)
    # Owner's rule (2026-10-13): what two or more publications carry is public.  Several other sites (checked by hand on 2026-10-13: a news-and-map site,
    # a bear-watch site and a private page) list this same prefectural list, down to the time of day, so its rows are stored with their place.
    records = sorted(corroborated.current_year(read_records(feats), today), key=lambda r: (r["observed_at"], r["place"]), reverse=True)
    if records:
        result["corroborated"] = records
        result["corroborated_on"] = {city: today.isoformat() for city in sorted({r["city"] for r in records})}
    return result


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
