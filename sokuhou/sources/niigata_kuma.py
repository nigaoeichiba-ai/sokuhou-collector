"""新潟県(クマの出没情報・件数だけを保存する)。

新潟県は、データの再利用の許可を明示していない(県サイトの著作権の案内は、無断の転載・複製を認めていない)。だから、市町村・日付・件数だけを取り出して、月別・市町村別に集計し、
場所・座標・自由記述は、取得も保存もしない(ただし2026-10-13のオーナーの方針で、上越市が自分のページ(PDF)にも載せている目撃は、2つの公開情報が一致したものとして、出典を示さずに場所つきで保存する。`corroborated.py`)(`outFields` は日付と市町村の列だけ、`returnGeometry=false`)。
取得元: 新潟県の公式ページが埋め込む ArcGIS の公開 Web マップ(下の WEBMAP_ID)が指す、FeatureServer のレイヤー。
サービス名は毎年変わるので、レイヤーの住所は固定せず、Web マップから探す(1つに決まらなければ、保存せずに例外にする)。
"""
from __future__ import annotations

import json
import sys
import time

from sokuhou.sources import arcgis_counts, corroborated

PAGE = "https://www.pref.niigata.lg.jp/site/tyoujyutaisakusienn/241009kumamap.html"
WEBMAP_ID = "03084a546fec4551b20b302e2be3145e"
LAYER_PATTERN = r"survey123_[0-9a-f]+_results/FeatureServer/0$"
DATE_FIELD = "field_20"
CITY_FIELD = "field_7"
CREDIT = ("出典: 新潟県「にいがたクマ出没マップ」(https://www.pref.niigata.lg.jp/site/tyoujyutaisakusienn/241009kumamap.html)の公開データから、"
          "市町村別・月別の件数だけを、当サイトが集計して作成(場所などの詳しい記録は、新潟県のページでご確認ください)")
UPDATE_NOTE = "新潟県が、ほぼ毎日更新します。最新の記録は、更新時点から遅れます。件数は、クマの目撃のほか、痕跡や人身被害の報告を含みます"
MIN_ROWS = 300
UNPARSED_LIMIT = 0.02
EMPTY_CITY_LIMIT = 0.02


class NiigataKumaSourceError(arcgis_counts.ArcgisCountsError):
    pass


def collect(fetch=None, sleep=None, now=None) -> dict:
    kw = {"sleep": sleep} if sleep else {}
    nap = sleep or time.sleep

    def confirm(result, rows, today, fetch_fn):
        """Joetsu City's own list (a PDF behind its page) is read too; the sightings the prefecture also lists are stored with their place."""
        return corroborated.attach(result, rows, [corroborated.joetsu_reader()], fetch_fn, today, lambda: nap(arcgis_counts.PAUSE))

    return arcgis_counts.collect_counts(
        source="niigata", prefecture="新潟県", webmap_id=WEBMAP_ID, layer_pattern=LAYER_PATTERN, date_field=DATE_FIELD, city_field=CITY_FIELD,
        page=PAGE, credit=CREDIT, update_note=UPDATE_NOTE, min_rows=MIN_ROWS, unparsed_limit=UNPARSED_LIMIT, empty_city_limit=EMPTY_CITY_LIMIT,
        error=NiigataKumaSourceError, fetch=fetch, now=now, corroborate=confirm, **kw)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
