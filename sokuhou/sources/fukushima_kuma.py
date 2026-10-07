"""福島県(クマの出没情報・件数だけを保存する)。

福島県は、データの再利用の許可を明示していない(県サイトの著作権の案内は、無断の転用・引用を認めていない)。だから、市町村・日付・件数だけを取り出して、月別・市町村別に集計し、
場所・座標・自由記述は、取得も保存もしない(`outFields` は日付と市町村の列だけ、`returnGeometry=false`)。
取得元: 福島県の公式ページが埋め込む ArcGIS の公開 Web マップ(下の WEBMAP_ID)が指す、FeatureServer のレイヤー。
サービス名は毎年変わるので、レイヤーの住所は固定せず、Web マップから探す(1つに決まらなければ、保存せずに例外にする)。
"""
from __future__ import annotations

import json
import sys

from sokuhou.sources import arcgis_counts

PAGE = "https://www.pref.fukushima.lg.jp/sec/16035b/tukinowaguma-mokugeki.html"
WEBMAP_ID = "8624f0116bcf45c58c1205097eb629ae"
LAYER_PATTERN = r"福島県クマ目撃ポイント.*/FeatureServer/0$"
DATE_FIELD = "kuma_date"
CITY_FIELD = "city"
CREDIT = ("出典: 福島県「福島県クマ目撃マップ」(https://www.pref.fukushima.lg.jp/sec/16035b/tukinowaguma-mokugeki.html)の公開データから、"
          "市町村別・月別の件数だけを、当サイトが集計して作成(場所などの詳しい記録は、福島県のページでご確認ください)")
UPDATE_NOTE = "福島県が、ほぼ毎日更新します。最新の記録は、更新時点から遅れます。件数は、クマの目撃のほか、痕跡や被害の報告を含みます"
MIN_ROWS = 300
UNPARSED_LIMIT = 0.02
EMPTY_CITY_LIMIT = 0.02


class FukushimaKumaSourceError(arcgis_counts.ArcgisCountsError):
    pass


def collect(fetch=None, sleep=None, now=None) -> dict:
    kw = {"sleep": sleep} if sleep else {}
    return arcgis_counts.collect_counts(
        source="fukushima", prefecture="福島県", webmap_id=WEBMAP_ID, layer_pattern=LAYER_PATTERN, date_field=DATE_FIELD, city_field=CITY_FIELD,
        page=PAGE, credit=CREDIT, update_note=UPDATE_NOTE, min_rows=MIN_ROWS, unparsed_limit=UNPARSED_LIMIT, empty_city_limit=EMPTY_CITY_LIMIT,
        error=FukushimaKumaSourceError, fetch=fetch, now=now, **kw)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
