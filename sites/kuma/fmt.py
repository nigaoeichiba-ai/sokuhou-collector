"""Small text / table formatters shared by the kuma site's page builders."""
from __future__ import annotations


def n(v) -> str:
    return "-" if v is None else f"{v:,}"


def fy_label(y: str) -> str:
    """'R07' -> '令和7年度'."""
    return f"令和{int(y[1:])}年度"


def fy_start(y: str) -> int:
    return 2018 + int(y[1:])


def jp_date(iso: str) -> str:
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{y}年{m}月{d}日"


def md(iso: str) -> str:
    _, m, d = (int(x) for x in iso.split("-"))
    return f"{m}月{d}日"


def ratio_text(new: int, old: int) -> str:
    """'約2.5倍', '38%減', '同じ' -- from two counts, never typed by hand."""
    if not old:
        return "比べられません"
    if new == old:
        return "同じ"
    if new > old * 1.5:
        return f"約{new / old:.1f}倍"
    pct = round(abs(new - old) / old * 100)
    return f"{pct}%{'増' if new > old else '減'}"


def table(head: list[str], rows: list[list[str]], cls: str = "") -> str:
    th = "".join(f"<th>{h}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tablewrap"><table{" class=" + cls if cls else ""}><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def day_text(iso_ts: str, year: bool = False) -> str:
    """'2026-10-03T08:30:00+09:00' -> '10月3日 8時30分ごろ' (with the year: '2026年10月3日 ...')."""
    day, clock = iso_ts[:10], iso_ts[11:16]
    head = jp_date(day) if year else md(day)
    if not clock:  # a source that publishes only the date (Okayama)
        return head
    h, m = (int(x) for x in clock.split(":"))
    return f"{head} {h}時{m:02d}分ごろ" if (h, m) != (0, 0) else head
