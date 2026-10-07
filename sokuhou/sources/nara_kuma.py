"""奈良県(クマの出没情報・件数だけを保存する)。

奈良県は、データの再利用の許可を明示していない(県サイトの著作権の案内は「無断で複製・転用することはできません」。FeatureServer の説明欄も空)。
だから、ArcGIS の FeatureServer から、目撃日時(field_9)と市町村(field_6)の2列だけを取り(`outFields`、`returnGeometry=false`)、
メモリの中で月別・市町村別に数えて、件数と最新日だけを保存する。場所(大字)・目撃数・状況・座標などは、取得も保存もしない。
「クマ」と「クマらしき」(field_14)は、区別せず数える。field_6 に「大台ヶ原」のような地名が入る行は、市町村名でなくても、そのまま1つの地域として数える。
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime

from sokuhou.sources import kumacounts

PAGE = "https://www.pref.nara.jp/n118/p043003.html"
LAYER = "https://pub-gis.nsa.pref.nara.jp/server/rest/services/Hosted/survey123_492ede82f5ae450ea7171fb986f04bd0_results/FeatureServer/0"
DATE_FIELD = "field_9"
CITY_FIELD = "field_6"
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


def collect(now: datetime | None = None) -> dict:
    params = {"where": "1=1", "outFields": f"{DATE_FIELD},{CITY_FIELD}", "returnGeometry": "false", "orderByFields": "objectid"}
    feats = kumacounts.query_all(fetch, LAYER, params, error=NaraKumaSourceError, page_size=PAGE_SIZE)
    return kumacounts.build_counts(
        read_rows(feats), error=NaraKumaSourceError, today=kumacounts.today_jst(now), source="nara", credit=CREDIT, update_note=UPDATE_NOTE,
        page=PAGE, files=[LAYER], min_rows=MIN_ROWS, unparsed_limit=UNPARSED_LIMIT, empty_limit=EMPTY_CITY_LIMIT, require_municipality=False)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
