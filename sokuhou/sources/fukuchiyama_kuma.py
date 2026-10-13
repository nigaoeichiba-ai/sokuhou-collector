"""京都府福知山市(クマの目撃場所のお知らせ。件数と、場所つきの記録を保存する)。

市のサイトの著作権の案内は、再利用の許可を明示していない。しかし、この一覧は、他の複数のサイト(クマの出没を集めた民間のサイトなど)が同じ内容を載せている
(2026-10-13 に確認)。オーナーの方針(2026-10-13)「2媒体以上に同じ内容があれば、広く公開された事実として掲載する」に従い、場所つきの記録を保存する。
市の一覧ページから、令和N年度の月別のページを読む(月ごとにページがあり、日付と場所が表になっている)。座標・PDFの中身は保存しない。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

from sokuhou.sources import corroborated, kumacounts, kumalib, prefpdfs

PAGE = corroborated.FUKUCHIYAMA_PAGE
CREDIT = ("出典: 福知山市「熊出没情報」(https://www.city.fukuchiyama.lg.jp/soshiki/27/2615.html)の公開データから、月別の件数を、当サイトが集計して作成"
          "(福知山市が作成したものではありません)")
UPDATE_NOTE = "福知山市が、目撃のたびに(ほぼ随時)更新します。最新の記録は、更新時点から遅れます。件数は、クマの目撃の場所のお知らせです"
MIN_ROWS = 5


class FukuchiyamaKumaSourceError(prefpdfs.PdfListError):
    pass


def fetch(url: str) -> bytes:
    return kumacounts.fetch(url)


def collect(now: datetime | None = None) -> dict:
    today = kumacounts.today_jst(now)
    era = kumalib.fiscal_start(today) - 2018
    rows = corroborated.fukuchiyama_reader(era)(fetch, kumacounts.pause)
    return prefpdfs.collect_list(source="fukuchiyama", page=PAGE, credit=CREDIT, update_note=UPDATE_NOTE, rows=rows, file_url=PAGE, today=today,
                                 min_rows=MIN_ROWS, error=FukuchiyamaKumaSourceError)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write(chr(10))
