"""静岡県(クマ出没情報のPDF。件数と、場所つきの記録を保存する)。

静岡県のサイトの著作権の案内は、私的使用・引用など以外の無断の複製・転用を認めていない(再利用の許可は明示されていない)。
しかし、この一覧は、他の複数のサイト(クマの出没を集めた民間のサイトなど)が同じ内容を載せている(2026-10-13 に確認)。
オーナーの方針(2026-10-13)「2媒体以上に同じ内容があれば、広く公開された事実として掲載する」に従い、場所つきの記録を保存する(`prefpdfs.py`)。
PDF の住所は更新のたびに変わるので、県のページのリンクから探す。座標・自由記述は保存しない。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

from sokuhou.sources import kumacounts, kumalib, prefpdfs

PAGE = "https://www.pref.shizuoka.jp/kurashikankyo/shizenkankyo/wild/1017680.html"
CREDIT = ("出典: 静岡県「クマ出没情報」(https://www.pref.shizuoka.jp/kurashikankyo/shizenkankyo/wild/1017680.html)の公開データから、市町村別・月別の件数を、当サイトが集計して作成"
          "(静岡県が作成したものではありません)")
UPDATE_NOTE = "静岡県が、不定期(ほぼ週1回)に更新します。最新の記録は、更新時点から遅れます。件数は、クマの目撃の報告です"
MIN_ROWS = 40


class ShizuokaKumaSourceError(prefpdfs.PdfListError):
    pass


def fetch(url: str) -> bytes:
    return kumacounts.fetch(url)


def collect(now: datetime | None = None) -> dict:
    today = kumacounts.today_jst(now)
    fy = kumalib.fiscal_start(today)
    rows, url = prefpdfs.read_pdf_rows(PAGE, fetch, {"label": f"令和{fy - 2018}年度クマ出没情報"}, lambda text: prefpdfs.parse_shizuoka(text, fy), kumacounts.pause)
    return prefpdfs.collect_list(source="shizuoka", page=PAGE, credit=CREDIT, update_note=UPDATE_NOTE, rows=rows, file_url=url, today=today,
                                 min_rows=MIN_ROWS, error=ShizuokaKumaSourceError)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write(chr(10))
