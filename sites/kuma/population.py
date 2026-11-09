"""Population of each prefecture, for the one ranking where a per-capita figure is fair: injuries and deaths (counted on one national standard).

Source: 総務省統計局「人口推計」第2表 都道府県、男女別人口及び人口性比(総人口。2024年10月1日現在)。the latest annual table published as of 2026-11-09.
The table is read once into population.json (a public government statistic); the build reads only that file.  Refresh once a year:

    python -m sites.kuma.population

Sighting counts are never divided by this: each prefecture counts sightings its own way, so a ratio built from them would compare the counting, not the bears.
"""
from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from sokuhou import prefectures as pf

FILE = Path(__file__).with_name("population.json")
PAGE = "https://www.stat.go.jp/data/jinsui/2024np/index.html"
TABLE = "https://www.stat.go.jp/data/jinsui/2024np/zuhyou/05k2024-2.xlsx"
AS_OF = "2024-10-01"
CREDIT = "出典: 総務省統計局「人口推計」(2024年10月1日現在・総人口。千人単位)を加工して作成。"
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NAMES = [pf.full(s) for s in pf.SHORT]


def parse(workbook: bytes) -> dict[str, int]:
    """{full prefecture name: population in thousands} from table 2 (the names carry a katakana reading after them: 北海道ホッカイドウ)."""
    z = zipfile.ZipFile(io.BytesIO(workbook))
    strings = ["".join(t.text or "" for t in si.iter(_NS + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(_NS + "si")]
    out: dict[str, int] = {}
    for row in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(_NS + "row"):
        cells = {}
        for c in row.findall(_NS + "c"):
            v = c.find(_NS + "v")
            if v is not None:
                cells[re.sub(r"\d+", "", c.get("r"))] = strings[int(v.text)] if c.get("t") == "s" else v.text
        name = next((x for x in NAMES if cells.get("C", "").startswith(x)), None)
        if name and cells.get("E", "").isdigit():
            out[name] = int(cells["E"])
    if set(out) != set(NAMES):
        raise ValueError(f"expected 47 prefectures, got {len(out)}: missing {sorted(set(NAMES) - set(out))}")
    return out


def fetch_and_write() -> dict:
    req = Request(TABLE, headers={"User-Agent": "Mozilla/5.0 (kuma-sokuho population table)"})
    data = parse(urlopen(req, timeout=60).read())
    doc = {"source": CREDIT, "as_of": AS_OF, "unit": "thousand persons", "page": PAGE, "table": TABLE, "fetched": date.today().isoformat(), "population": data}
    FILE.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return doc


def load() -> dict:
    return json.loads(FILE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    d = fetch_and_write()
    print(len(d["population"]), "prefectures,", sum(d["population"].values()), "thousand in total")
