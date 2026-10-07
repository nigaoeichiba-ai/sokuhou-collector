"""富山県(クマの出没情報・件数だけを保存する)。

富山県は、データの再利用の許可を明示していない(県サイトの著作権の案内は、無断の複製・転用を認めていない)。だから、市町村・日付・件数だけを取り出して、月別・市町村別に集計し、
場所・座標・自由記述は、取得も保存もしない(`outFields` は日付と市町村の列だけ、`returnGeometry=false`)。
取得元: 富山県の公式ページが埋め込む ArcGIS の公開 Web マップ(下の WEBMAP_ID)が指す、FeatureServer のレイヤー。
サービス名は毎年変わるので、レイヤーの住所は固定せず、Web マップから探す(1つに決まらなければ、保存せずに例外にする)。
"""
from __future__ import annotations

import json
import sys

from sokuhou.sources import arcgis_counts

PAGE = "https://www.pref.toyama.jp/1709/kurashi/kankyoushizen/shizen/yaseiseibutsu/kumap.html"
WEBMAP_ID = "778bb8dbaf1b4f46a2a07c17d15528a1"
LAYER_PATTERN = r"survey123_[0-9a-f]+_results/FeatureServer/0$"
DATE_FIELD = "HasseiDateTime"
CITY_FIELD = "HasseiCity"
CREDIT = ("出典: 富山県「富山県ツキノワグマ出没情報地図【クマっぷ】」(https://www.pref.toyama.jp/1709/kurashi/kankyoushizen/shizen/yaseiseibutsu/kumap.html)の公開データから、"
          "市町村別・月別の件数だけを、当サイトが集計して作成(場所などの詳しい記録は、富山県のページでご確認ください)")
UPDATE_NOTE = "富山県が、市町村からの報告を受けて、ほぼ随時更新します。件数は、クマの目撃のほか、痕跡や人身被害の報告を含みます"
MIN_ROWS = 100
UNPARSED_LIMIT = 0.02
EMPTY_CITY_LIMIT = 0.02


class ToyamaKumaSourceError(arcgis_counts.ArcgisCountsError):
    pass


def collect(fetch=None, sleep=None, now=None) -> dict:
    kw = {"sleep": sleep} if sleep else {}
    return arcgis_counts.collect_counts(
        source="toyama", prefecture="富山県", webmap_id=WEBMAP_ID, layer_pattern=LAYER_PATTERN, date_field=DATE_FIELD, city_field=CITY_FIELD,
        page=PAGE, credit=CREDIT, update_note=UPDATE_NOTE, min_rows=MIN_ROWS, unparsed_limit=UNPARSED_LIMIT, empty_city_limit=EMPTY_CITY_LIMIT,
        error=ToyamaKumaSourceError, fetch=fetch, now=now, **kw)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
