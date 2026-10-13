"""北海道のヒグマ出没(複数の公開情報で一致を確認できた市町村の分。月別の件数だけを保存し、出典は載せない)。

北海道は、全道の出没件数を集計・公表していない(環境省の表の北海道は「-」)。市町村は、それぞれのサイトで出没情報を公開しており、
道内の60あまりの市町村は、同じ仕組み「ひぐまっぷ」(https://higumap.info/ 、民間のダッピスタジオ合同会社。市町村が自分で登録する)で、地図つきの一覧を公開している。
このアダプタは、その公開マップが画面の描画に使っている一覧(日付・位置・ひと言)から、市町村ごとの日付だけを読んで数える。位置・内容は保存しない。

載せるのは CONFIRMED の市町村だけ(オーナーの方針 2026-10-13「2媒体以上に同じ内容があれば、広く公開された事実として掲載する。出典・リンクは記載しない」)。
2026-10-13 の確認: (1) 市町村の公式ページ(または道の「市町村ヒグマ関連情報リンク集」)が、ひぐまっぷを自分の公開手段として案内している、かつ
(2) 市の公式ページに別の一覧があって件数が一致した(士別70/70・苫小牧44/44・千歳41/41・釧路27/27)、または競合の KumaWatch の直近1年・90日の件数と、
差が max(3, 15%) 以内(手作業で1回だけ照合。競合へ毎日アクセスはしない)。一致しなかった市町村は載せない。
新しい市町村を足すときは、同じ確認をして CONFIRMED に入れる(docs/KUMA_HOKKAIDO_CHIBA_2026-10-13.md の手順)。
空知総合振興局が載せている4市町(美唄市・芦別市・新十津川町・浦臼町)は、sorachi_kuma と二重にならないよう除く。日付を載せない市町村は数えない。
1回に約130アクセス(市町村ごとに2回)で、間隔をあける。
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime

from sokuhou.sources import kumacounts, kumalib

ROOT = "https://higumap.info"
PAGE = ROOT + "/recent"
CREDIT = "複数の公開情報で一致を確認できた市町村の分を、公開されている情報から、当サイトが月別に集計して作成(各市町村が作成したものではありません)"
UPDATE_NOTE = ("各市町村が、情報が入るたびに(ほぼ随時)更新します。最新の記録は、更新時点から遅れます。件数は、目撃のほか、痕跡や捕獲などの報告を含みます。"
               "道内の一部の市町村の分だけで、道全体の件数ではありません")
IN_SORACHI = frozenset({"美唄市", "芦別市", "新十津川町", "浦臼町"})      # already counted, with their places, by sorachi_kuma
MIN_ROWS = 300
UNPARSED_LIMIT = 0.05
EMPTY_LIMIT = 0.02
CONFIRMED = frozenset({       # towns whose two publications agree (checked by hand on 2026-10-13, see the docstring)
    "せたな町", "上ノ国町", "中川町", "千歳市", "厚岸町", "厚沢部町", "厚真町", "名寄市", "士別市", "安平町", "当麻町", "恵庭市", "愛別町", "木古内町", "松前町",
    "標茶町", "池田町", "津別町", "滝上町", "紋別市", "置戸町", "興部町", "苫小牧市", "訓子府町", "釧路市", "鶴居村", "黒松内町"})
UNDATED_SHARE = 0.5          # a municipality whose reports mostly carry no date is not counted at all


class HigumapKumaSourceError(ValueError):
    pass


def fetch(url: str) -> bytes:
    return kumacounts.fetch(url)


def _json(body: bytes, what: str):
    try:
        return json.loads(body)
    except ValueError as e:
        raise HigumapKumaSourceError(f"{what}: not JSON ({e})") from e


def map_ids(body: bytes) -> list[str]:
    ids = _json(body, "city list")
    if not isinstance(ids, list) or not ids or not all(isinstance(x, (str, int)) and re.fullmatch(r"\d{1,6}", str(x)) for x in ids):
        raise HigumapKumaSourceError("city list: unexpected shape")
    return [str(x) for x in ids]


def city_of_page(page: str) -> tuple[str, str]:
    """(the map's city id, the municipality's name) from the public map page."""
    cid = re.search(r'data-city-id="(\d+)"', page)
    name = re.search(r'data-city-name="([^"]*)"', page)
    if not cid or not name:
        raise HigumapKumaSourceError("map page: city id or name not found")
    return cid.group(1), html.unescape(name.group(1)).strip()


def days(body: bytes) -> tuple[list, int]:
    """([date of each report], the number of reports without a date)."""
    data = _json(body, "reports")
    reports = data.get("list") if isinstance(data, dict) else None
    if not isinstance(reports, list):
        raise HigumapKumaSourceError("reports: no 'list'")
    got, undated = [], 0
    for r in reports:
        d = kumacounts.jst_date(r.get("foundDt")) if isinstance(r, dict) else None
        if d is None:
            undated += 1
        else:
            got.append(d)
    return got, undated


def collect(now=None, fetch_fn=None, pause=None) -> dict:
    fetch_fn = fetch_fn or fetch
    pause = pause or kumacounts.pause
    today = kumacounts.today_jst(now)
    year = kumalib.fiscal_start(today)
    ids = map_ids(fetch_fn(f"{ROOT}/recent/pmCityList"))
    rows: list = []
    seen: set[str] = set()
    for mid in ids:
        pause()
        cid, name = city_of_page(fetch_fn(f"{ROOT}/map/{mid}/{year}").decode("utf-8", "replace"))
        if name in IN_SORACHI or name not in CONFIRMED or name in seen or not kumacounts.is_municipality(name):
            continue
        pause()
        got, undated = days(fetch_fn(f"{ROOT}/map/reportsJson?cityId={cid}&fiscalYear={year}"))
        if not got or undated / (undated + len(got)) > UNDATED_SHARE:
            continue
        seen.add(name)
        rows += [(d, name) for d in got]
        rows += [(None, name)] * undated
    return kumacounts.build_counts(rows, error=HigumapKumaSourceError, today=today, source="higumap", credit=CREDIT, update_note=UPDATE_NOTE, page=PAGE,
                                   files=[f"{ROOT}/map/reportsJson"], min_rows=MIN_ROWS, unparsed_limit=UNPARSED_LIMIT, empty_limit=EMPTY_LIMIT)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out = collect()
    json.dump({k: v for k, v in out.items() if k != "municipalities"}, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write(chr(10))
