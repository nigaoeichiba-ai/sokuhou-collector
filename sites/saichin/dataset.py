"""The downloadable data of the minimum-wage site: every prefecture in every year, as one CSV and one JSON, plus the Dataset markup.

The rows are the same numbers the prefecture pages print (build.prepare()); nothing is added.  The source is MHLW's history workbook; its terms are the
Public Data License v1.0 (PDL1.0): name the source, say that the data was edited and by whom, and do not present it as made by the government.
"""
from __future__ import annotations

import csv
import io
import json

CSV_NAME = "minimum-wage.csv"
JSON_NAME = "minimum-wage.json"
PDL_URL = "https://www.digital.go.jp/resources/open_data/public_data_license_v1.0"
MHLW_NOTICE_URL = "https://www.mhlw.go.jp/chosakuken/index.html"
# Checks of the data against other sources, newest last.  Add a line when a new check is done (never edit an old one): the date, what was compared, the result.
VERIFICATIONS = [
    {"date": "2026-10-15", "what": "令和8年度の47都道府県の最低賃金・前年度の額・引上げ額・発効日を、厚生労働省「令和8年度地域別最低賃金全国一覧」(PDF)と照合",
     "result": "47都道府県すべて一致"},
]
BUILD_CHECKS = ("ページを作るたびに次の3つを確かめています。1つでも満たさなければ公開しません。"
                "全都道府県に全年度のデータがあること。最低賃金が前の年度より下がっていないこと。"
                "全国加重平均が、その年度の最も低い県と最も高い県の間にあること。")
COLUMNS = ["都道府県", "年度(西暦)", "年度(和暦)", "最低賃金(円)", "前年度からの引上げ(円)", "発効日", "全国順位", "発効日の補正(元の日付)"]


def rows(d: dict) -> list[dict]:
    """One row per prefecture and year, in prefecture order (as MHLW lists them) and then year order."""
    out = []
    for r in d["rows"]:
        for h in r["history"]:
            out.append({
                "prefecture": r["name"], "fiscal_year": h["fy"], "fiscal_year_label": h["label"], "amount_yen": h["amount"], "raise_yen": h["raise"],
                "effective_date": h["effective_date"], "rank_of_47": h["rank"], "effective_date_original": h.get("date_fixed_from"),
            })
    return out


def csv_bytes(d: dict) -> bytes:
    """UTF-8 with a byte order mark (Japanese Excel reads it correctly), CRLF line ends, empty cells where a value does not exist."""
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(COLUMNS)
    for r in rows(d):
        w.writerow([r["prefecture"], r["fiscal_year"], r["fiscal_year_label"], r["amount_yen"], "" if r["raise_yen"] is None else r["raise_yen"],
                    r["effective_date"] or "", r["rank_of_47"], r["effective_date_original"] or ""])
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def json_text(d: dict, cfg: dict) -> str:
    base = cfg["site_url"].rstrip("/")
    first, last = d["rows"][0]["history"][0], d["rows"][0]["history"][-1]
    payload = {
        "title": f"地域別最低賃金(47都道府県・{first['label']}〜{last['label']})",
        "as_of": d["fetched_date"],
        "source": {
            "name": "厚生労働省「地域別最低賃金の全国一覧」(平成14年度から令和8年度までの地域別最低賃金改定状況)",
            "url": d["source_page"], "license": "公共データ利用規約(第1.0版)PDL1.0", "license_url": PDL_URL,
        },
        "verification": {"checks": VERIFICATIONS, "every_build": BUILD_CHECKS},
        "processing": "このデータは、出典の表の各年度の額を、このサイトが都道府県ごとに並べ替え、引上げ額と全国順位(同額は同じ順位)を計算したものです。厚生労働省が作成したものではありません。",
        "published_by": {"name": cfg["site_name"], "url": base + "/"},
        "note": f"{last['label']}の額は、発効日より前でも、決まった新しい額です。発効日の前は、その県では1つ前の年度の額が適用されています。",
        "national_weighted_average": {str(y["fy"]): round(y["avg"]) for y in d["years"]},
        "columns": {
            "prefecture": "都道府県", "fiscal_year": "年度(西暦。2025は令和7年度)", "fiscal_year_label": "年度(和暦)", "amount_yen": "最低賃金(円/時)",
            "raise_yen": "前年度からの引上げ(円。最初の年度は null)", "effective_date": "発効日", "rank_of_47": "全国順位(同額は同じ順位)",
            "effective_date_original": "出典の表の日付を補正したときの、元の日付(通常は null)",
        },
        "rows": rows(d),
    }
    return json.dumps(payload, ensure_ascii=False, indent=1) + "\n"


def dataset_ld(d: dict, cfg: dict) -> dict:
    """schema.org Dataset (Google Dataset Search): a name, a description of 50+ characters, and the two files."""
    base = cfg["site_url"].rstrip("/")
    first, last = d["rows"][0]["history"][0], d["rows"][0]["history"][-1]
    return {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": f"地域別最低賃金の推移(47都道府県・{first['label']}〜{last['label']})",
        "description": (f"47都道府県の地域別最低賃金(時間額)を、{first['label']}から{last['label']}まで年度別にそろえたデータです。"
                        "各年度の額、前年度からの引上げ額、発効日、全国順位を、CSVとJSONで配布しています。出典は厚生労働省の公表資料です。"),
        "inLanguage": "ja", "keywords": ["最低賃金", "地域別最低賃金", "都道府県", "時給", "推移"],
        "url": base + "/data/", "isAccessibleForFree": True, "dateModified": d["fetched_date"],
        "license": PDL_URL,
        "creator": {"@type": "Organization", "name": cfg["site_name"], "url": base + "/"},
        "isBasedOn": d["source_page"],
        "temporalCoverage": f"{first['fy']}/{last['fy'] + 1}", "spatialCoverage": {"@type": "Country", "name": "日本"},
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": f"{base}/data/{CSV_NAME}"},
            {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{base}/data/{JSON_NAME}"},
        ],
    }


def ld_script(d: dict, cfg: dict) -> str:
    return '<script type="application/ld+json">' + json.dumps(dataset_ld(d, cfg), ensure_ascii=False).replace("</", "<\\/") + "</script>\n"
