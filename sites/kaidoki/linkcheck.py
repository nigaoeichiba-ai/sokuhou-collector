"""kaidoki's own rules of the linkage gate (sokuhou/linkage.py calls check()).
  home-schedule  every sale in the top page's 「いま分かっている日程」 table (name and period) is on /calendar/ too: the top page and the calendar come from one data set, and
                 a table of two malls on the top while the calendar knows more (2026-11-15) must not be published again.  The names are read as the table shows them."""
from __future__ import annotations

import re
from html import unescape
from pathlib import Path


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


def check(root: Path, base: str, pages: dict) -> list[str]:
    home, cal = pages.get("/"), pages.get("/calendar/")
    if home is None or cal is None:
        return ["home-schedule|/|the top page or /calendar/ is missing"]
    out = []
    cal_text = _text(cal.html)
    m = re.search(r"<h2[^>]*>いま分かっている日程</h2>(.*?)(?=<h2|</main>|</article>)", home.html, re.S)
    if not m:
        return ["home-schedule|/|no 「いま分かっている日程」 section on the top page"]
    rows = re.findall(r"<tr>(.*?)</tr>", m.group(1), re.S)
    n = 0
    for r in rows:
        cells = [_text(c).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
        if len(cells) < 3 or cells[0] == "モール":
            continue
        n += 1
        name, period = cells[1].replace("【発表予定日】", "").strip(), cells[2]
        # a confirmed sale shows its whole period on both pages; an announcement day (【発表予定日】, "11月19日(木)の午前") the calendar shows in its day grid, so only its name is compared
        if name not in cal_text or ("から" in period and period not in cal_text):
            out.append(f"home-schedule|/|{name} ({period}) is on the top page but not on /calendar/")
    if n == 0:
        out.append("home-schedule|/|the schedule table of the top page has no sale")
    return out
