"""atomou 案3: the usual days of the cherry blossoms and the autumn leaves, counted from the Japan Meteorological Agency's long series of seasonal observations (生物季節観測 累年値).

Only what was observed in the past is used: no forecast is made or shown (the Meteorological Service Act limits who may forecast).  The four series come from
https://www.data.jma.go.jp/sakura/data/ruinenchi/ (004 さくらの開花, 005 さくらの満開, 013 いちょうの黄葉, 015 かえでの紅葉; read on 2026-10-11 with the owner's permission; the terms are the 公共データ利用規約
(第1.0版): the source is named and a change is said: 「気象庁 ... を加工して作成」).  The files are kept as they are in data/atomou/jma/ (Shift_JIS, CRLF).

File layout (from the Agency's description of the format): line 1 = the number and name of the series; line 2 = the header; lines 3- = one station each: the station number, the name, then for each year
1953..2032 the observed day as month*100+day (0 = not observed) followed by a remark (6-9: which tree and where), then the Agency's own normal (1991-2020), earliest and latest.
The usual day here is our own count: the mean of the last ten years that have a value (the Agency's 平年値 is another thing and is not used).  The Agency's own earliest and latest are used to check ours.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "atomou" / "jma"
OUT = ROOT / "data" / "atomou" / "phenology.json"
BASE = "https://www.data.jma.go.jp/sakura/data/"
SERIES = [("004", "sakura-open", "さくらの開花"), ("005", "sakura-full", "さくらの満開"), ("013", "ginkgo", "いちょうの黄葉"), ("015", "maple", "かえでの紅葉")]
FIRST_YEAR = 1953
YEARS = 80        # the columns 1953..2032 (the file has room for the years to come)
REF = 2001        # a year that is not a leap year: the day of the year of a month and day

# the station that stands for each prefecture (the Agency's station in or near the prefectural capital); the station names are those of the files
PREF_STATION = {
    "北海道": "札幌", "青森県": "青森", "岩手県": "盛岡", "宮城県": "仙台", "秋田県": "秋田", "山形県": "山形", "福島県": "福島", "茨城県": "水戸", "栃木県": "宇都宮", "群馬県": "前橋",
    "埼玉県": "熊谷", "千葉県": "銚子", "東京都": "東京", "神奈川県": "横浜", "新潟県": "新潟", "富山県": "富山", "石川県": "金沢", "福井県": "福井", "山梨県": "甲府", "長野県": "長野",
    "岐阜県": "岐阜", "静岡県": "静岡", "愛知県": "名古屋", "三重県": "津", "滋賀県": "彦根", "京都府": "京都", "大阪府": "大阪", "兵庫県": "神戸", "奈良県": "奈良", "和歌山県": "和歌山",
    "鳥取県": "鳥取", "島根県": "松江", "岡山県": "岡山", "広島県": "広島", "山口県": "下関", "徳島県": "徳島", "香川県": "高松", "愛媛県": "松山", "高知県": "高知", "福岡県": "福岡",
    "佐賀県": "佐賀", "長崎県": "長崎", "熊本県": "熊本", "大分県": "大分", "宮崎県": "宮崎", "鹿児島県": "鹿児島", "沖縄県": "那覇",
}


def doy(mmdd: int) -> int:
    """The day of the year (1..365) of a month*100+day, counted in a year without a leap day."""
    return (date(REF, mmdd // 100, mmdd % 100) - date(REF, 1, 1)).days + 1


def ordinal(key: str, mmdd: int) -> int:
    """The place of a day on the line of one season.  A winter-flowering cherry of the south is entered with a day of November or December: that is the end of the year BEFORE (earlier than
    January).  An autumn leaf of the south may be entered with a day of January to March: that is the start of the year AFTER (later than December)."""
    n = doy(mmdd)
    if key.startswith("sakura"):
        return n - 365 if mmdd >= 1101 else n
    return n + 365 if mmdd <= 331 else n


def mmdd_of(n: int) -> int:
    n = (n - 1) % 365 + 1
    d = date(REF, 1, 1) + timedelta(days=n - 1)
    return d.month * 100 + d.day


def parse(path: Path) -> dict:
    """{'name': the series' name, 'stations': [{'id', 'name', 'years': {year: mmdd}, 'jma': {'normal', 'earliest', 'earliest_year', 'latest', 'latest_year'}}]}"""
    rows = list(csv.reader(io.StringIO(path.read_bytes().decode("cp932"))))
    stations = []
    for r in rows[2:]:
        if not r or not r[0].strip():
            continue
        years, rm = {}, {}
        for i in range(YEARS):
            v = int(r[2 + 2 * i] or 0)
            if v > 0:
                years[FIRST_YEAR + i] = v
                rm[FIRST_YEAR + i] = int(r[3 + 2 * i] or 0)
        t = 2 + 2 * YEARS     # normal, remark, earliest, remark, earliest year, latest, remark, latest year
        stations.append({"id": r[0].strip(), "name": r[1].replace("　", "").strip(), "years": years, "rm": rm,
                         "jma": {"normal": int(r[t] or 0), "earliest": int(r[t + 2] or 0), "earliest_year": int(r[t + 4] or 0), "latest": int(r[t + 5] or 0), "latest_year": int(r[t + 7] or 0)}})
    return {"name": rows[0][1].strip(), "stations": stations}


def stats(key: str, years: dict[int, int], last: int) -> dict | None:
    """The usual day (the mean of the last ten years that have a value, within last-9..last), the earliest and the latest day of the whole series, and the last ten years' days.
    All the observations count (an alternative tree too: the station's own flower, e.g. Hokkaido's), so the earliest and latest can differ from the Agency's, which use the regular tree only."""
    if not years:
        return None
    recent = {y: v for y, v in years.items() if last - 9 <= y <= last}
    early = min(years.items(), key=lambda kv: (ordinal(key, kv[1]), -kv[0]))      # a tie goes to the later year
    late = max(years.items(), key=lambda kv: (ordinal(key, kv[1]), kv[0]))
    out = {"first": min(years), "count": len(years), "early": [early[1], early[0]], "late": [late[1], late[0]], "recent": [recent.get(y, 0) for y in range(last - 9, last + 1)]}
    out["usual"] = mmdd_of(round(sum(ordinal(key, v) for v in recent.values()) / len(recent))) if len(recent) >= 5 else 0
    out["ro"] = [ordinal(key, v) if v else 0 for v in out["recent"]]      # the places on the line of the season, for the small chart      # fewer than 5 of the last ten years: no usual day
    return out


def build() -> dict:
    series = [(sid, key, parse(RAW / f"ruinenchi_{sid}.csv")) for sid, key, _ in SERIES]
    last = max(y for _, _, s in series for st in s["stations"] for y in st["years"])
    items = []
    for sid, key, s in series:
        rows = []
        for st in s["stations"]:
            x = stats(key, st["years"], last)
            if x and (x["usual"] or st["jma"]["normal"]):
                rows.append({"n": st["name"], "normal": st["jma"]["normal"], **x})      # normal: the Agency's own 平年値 of the file (1991-2020), 0 when it has none
        items.append({"id": key, "name": s["name"], "src": f"{BASE}ruinenchi/{sid}.csv", "stations": rows})
    return {"v": 1, "last": last, "read": "2026-10-11", "source": BASE + "index.html", "map": PREF_STATION, "items": items}


def write() -> None:
    OUT.write_text(json.dumps(build(), ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def load() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8"))


def stations_with(data: dict) -> list[str]:
    """The names of the stations that have a usual day for at least one series, in the order of the first series."""
    seen: list[str] = []
    for it in data["items"]:
        for st in it["stations"]:
            if st["n"] not in seen:
                seen.append(st["n"])
    return seen


if __name__ == "__main__":
    write()
    d = load()
    print("wrote", OUT, "last year", d["last"], [(i["id"], len(i["stations"])) for i in d["items"]])
