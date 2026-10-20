"""The minimum wages of Showa 52 to Heisei 15 (1977-2003), from the Ministry's 2003 council document.

Source: 厚生労働省「地域別最低賃金に関するデータ(時間額)」(https://www.mhlw.go.jp/shingi/2003/12/s1202-3h.html).  It lists every prefecture by rank group (A to D),
so a prefecture that changed rank appears in two or more rows, each with "-" for the years it was in another group; `parse` merges the rows.
Kyoto had two rates (south and north) from Showa 54 to Heisei 1; the page lists them as "京都(南)" and "京都(北)".
`history_old.json` is a snapshot of the parsed page (it is a fixed historical document, so the build does not fetch it); the tests parse the saved page and
require the snapshot to be exactly its result.  The build refuses the snapshot if its Heisei 14 and 15 amounts differ from the current workbook (see build.check_old_history).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).parent
SNAPSHOT = HERE / "history_old.json"
PAGE = "https://www.mhlw.go.jp/shingi/2003/12/s1202-3h.html"
TITLE = "地域別最低賃金に関するデータ(時間額)"
FIRST_FY, LAST_FY = 1977, 2003          # Showa 52 .. Heisei 15: 27 columns
SPLIT = {"京都(南)": "south", "京都(北)": "north"}
_NUM = re.compile(r"^-$|^\d+(\.\d+)?$")
_RANK = re.compile(r"^[ＡＢＣＤ]ランク$")


class OldHistoryError(Exception):
    pass


def _cells(page: bytes) -> list[str]:
    text = page.decode("cp932", errors="replace")
    text = re.sub(r"<[^>]+>", "\t", text).replace("&nbsp;", " ")
    cells = [c.strip().replace("　", "").replace("（", "(").replace("）", ")") for c in re.split(r"\t+", text)]
    return [c for c in cells if c]


def parse(page: bytes) -> dict:
    """The page's amounts per prefecture and year, and the national weighted average (Showa 53 onwards)."""
    cells = _cells(page)
    n_years = LAST_FY - FIRST_FY + 1
    try:
        start = next(i for i, c in enumerate(cells) if "地域別最低賃金額の推移" in c and i > 100)
    except StopIteration:
        raise OldHistoryError("the table of regional amounts was not found") from None
    rows, k = [], start
    while k < len(cells):
        c = cells[k]
        if _RANK.match(c):
            k += 1
            continue
        window = cells[k + 1:k + 1 + n_years]
        if len(window) == n_years and not _NUM.match(c) and all(_NUM.match(x) for x in window):
            rows.append((c, window))
            k += 1 + n_years
            continue
        k += 1
    prefectures: dict[str, dict[str, float]] = {}
    for name, window in rows:
        series = prefectures.setdefault(name, {})
        for fy, v in zip(range(FIRST_FY, LAST_FY + 1), window):
            if v == "-":
                continue
            value = float(v)
            if str(fy) in series and series[str(fy)] != value:
                raise OldHistoryError(f"{name} {fy}: two different amounts in the rows of different rank groups")
            series[str(fy)] = int(value) if value == int(value) else value
    # the national weighted average: "合計" followed by (円, amount, (rate)) for Showa 53 .. Heisei 15
    try:
        i = cells.index("合計")
    except ValueError:
        raise OldHistoryError("the row of national weighted averages was not found") from None
    amounts = [c for c in cells[i + 1:i + 1 + 3 * (n_years - 1)] if re.fullmatch(r"\d{3}", c)]
    if len(amounts) != n_years - 1:
        raise OldHistoryError(f"expected {n_years - 1} national averages, found {len(amounts)}")
    average = {str(fy): int(a) for fy, a in zip(range(FIRST_FY + 1, LAST_FY + 1), amounts)}
    south, north = prefectures.pop("京都(南)", {}), prefectures.pop("京都(北)", {})
    return {
        "source_page": PAGE, "source_title": TITLE, "first_fiscal_year": FIRST_FY, "last_fiscal_year": LAST_FY,
        "prefectures": prefectures, "kyoto_split": {"south": south, "north": north}, "national_weighted_average": average,
    }


def load() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def dumps(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


if __name__ == "__main__":      # python -m sites.saichin.history_old PAGE.html  -> rewrites the snapshot from a saved copy of the page
    import sys
    SNAPSHOT.write_text(dumps(parse(Path(sys.argv[1]).read_bytes())), encoding="utf-8", newline="\n")
    print("wrote", SNAPSHOT)
