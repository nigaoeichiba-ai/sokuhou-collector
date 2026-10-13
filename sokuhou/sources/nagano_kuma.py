"""長野市(ツキノワグマの目撃出没情報。月1回のPDF。件数と、場所つきの記録を保存する)。

市のサイトの著作権の案内は、私的使用・引用など以外の無断の複製・転用を認めていない(再利用の許可は明示されていない)。しかし、この一覧は、他の複数のサイト
(クマの出没を集めた民間のサイトなど)や報道が同じ内容を載せている(2026-10-13 に確認)。オーナーの方針(2026-10-13)「2媒体以上に同じ内容があれば、
広く公開された事実として掲載する」に従い、場所つきの記録を保存する。PDF の住所は更新のたびに変わるので、市のページのリンクから探す。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

from sokuhou.sources import kumacounts, kumalib, prefpdfs

PAGE = "https://www.city.nagano.nagano.jp/n162000/contents/p001080.html"
CREDIT = ("出典: 長野市「野生獣(クマなど)の出没」(https://www.city.nagano.nagano.jp/n162000/contents/p001080.html)の公開データから、月別の件数を、当サイトが集計して作成"
          "(長野市が作成したものではありません)")
UPDATE_NOTE = ("長野市が、月1回(締め日の1週間ほど後)に更新します。最新の記録は、更新時点から1か月ほど遅れます。"
               "件数は、市役所・支所に寄せられた目撃と、足跡や被害などの痕跡(出没)の報告です")
MIN_ROWS = 20


class NaganoKumaSourceError(prefpdfs.PdfListError):
    pass


def fetch(url: str) -> bytes:
    return kumacounts.fetch(url)


def collect(now: datetime | None = None) -> dict:
    today = kumacounts.today_jst(now)
    era = kumalib.fiscal_start(today) - 2018
    rows, url = prefpdfs.read_pdf_rows(PAGE, fetch, {"label": f"令和{era}年", "href": "kuma_"}, prefpdfs.parse_nagano_city, kumacounts.pause)
    return prefpdfs.collect_list(source="nagano", page=PAGE, credit=CREDIT, update_note=UPDATE_NOTE, rows=rows, file_url=url, today=today,
                                 min_rows=MIN_ROWS, error=NaganoKumaSourceError)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(collect(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write(chr(10))
