"""埼玉県(クマの出没情報・件数だけを保存する)。

埼玉県は、データの再利用の許可を明示していない(県サイトの著作権の案内は、転載に担当課の承認を求めている)。
だから、「埼玉県ツキノワグマ出没マップ」の ArcGIS FeatureServer から、出没日(field_1)と市町村名(field_4)の2列だけを取り(`outFields`、`returnGeometry=false`)、
メモリの中で月別・市町村別に数えて、件数と最新日だけを保存する。地名・概要・被害状況・自由記述・報告者などは、取得も保存もしない。
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime

from sokuhou.sources import kumacounts

PAGE = "https://www.pref.saitama.lg.jp/a0508/tyouzyu/kumatyui.html"
LAYER = "https://services9.arcgis.com/n65w8AXGaYPTqFYI/arcgis/rest/services/survey123_3123e5ed452d4e89845e4ba6129c1e2d_results/FeatureServer/0"
DATE_FIELD = "field_1"
CITY_FIELD = "field_4"
PAGE_SIZE = 1000
CREDIT = ("出典: 埼玉県「埼玉県ツキノワグマ出没マップ」(https://www.pref.saitama.lg.jp/a0508/tyouzyu/kumatyui.html)の公開データから、"
          "市町村別・月別の件数だけを、当サイトが集計して作成(場所などの詳しい記録は、埼玉県のページでご確認ください)")
UPDATE_NOTE = "埼玉県が、市町村からの報告を受けて、ほぼ随時更新します。最新の記録は、更新時点から遅れます。件数は、市町村が県に報告した、クマの出没の件数です"
MIN_ROWS = 40
UNPARSED_LIMIT = 0.03
EMPTY_CITY_LIMIT = 0.03


class SaitamaKumaSourceError(ValueError):
    pass


def fetch(url: str) -> bytes:
    return kumacounts.fetch(url)


def read_rows(features: list[dict]) -> list[tuple[date | None, object]]:
    out = []
    for f in features:
        a = f.get("attributes") if isinstance(f, dict) else None
        if not isinstance(a, dict) or DATE_FIELD not in a or CITY_FIELD not in a:
            raise SaitamaKumaSourceError(f"a feature lost {DATE_FIELD} / {CITY_FIELD}")
        out.append((kumacounts.jst_date(a[DATE_FIELD]), a[CITY_FIELD]))
    return out


def collect(now: datetime | None = None) -> dict:
    params = {"where": "1=1", "outFields": f"{DATE_FIELD},{CITY_FIELD}", "returnGeometry": "false", "orderByFields": "objectid"}
    feats = kumacounts.query_all(fetch, LAYER, params, error=SaitamaKumaSourceError, page_size=PAGE_SIZE)
    return kumacounts.build_counts(
        read_rows(feats), error=SaitamaKumaSourceError, today=kumacounts.today_jst(now), source="saitama", credit=CREDIT,
        update_note=UPDATE_NOTE, page=PAGE, files=[LAYER], min_rows=MIN_ROWS, unparsed_limit=UNPARSED_LIMIT, empty_limit=EMPTY_CITY_LIMIT)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
