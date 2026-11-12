"""Daily freshness check of sale-calendar.com (kaidoki).  Read only: no network, no keys, no product data of a mall.

    python -m sites.kaidoki.redesign.tools.freshness [--today 2026-11-12] [--out report.md] [--strict]

It lists what a person (or the daily routine) has to read again, from the data the site is built from:
  1. 今日・明日に終わるもの / 今日始まるもの (confirmed entries)
  2. 終わったのに、まだ確定として出ているもの (the end passed; the calendars keep the past, but the product pages and sentences must not say "開催中")
  3. 予想の日が過ぎたのに、確定になっていないもの (expected entries whose day has come: read the organiser again)
  4. 発表予定日が来た・過ぎたのに、日程が未発表のままのもの (notices)
  5. 確認日が古いもの (checked older than STALE_DAYS), listed per entry and per product page store row
  6. 商品ページの店ごとの確認日が古い / 終了日が過ぎた行
Exit code: 0 when nothing is due, 1 with --strict when something is.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PRODUCTS = Path(__file__).resolve().parents[1] / "products"
JST = timezone(timedelta(hours=9))
STALE_DAYS = 7          # the weekly Tuesday round reads every row again; a row older than this has been missed
JA_DATE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


def _d(x) -> date | None:
    if isinstance(x, date):
        return x
    if not x:
        return None
    try:
        return date.fromisoformat(str(x)[:10])
    except ValueError:
        m = JA_DATE.search(str(x))
        return date(int(m[1]), int(m[2]), int(m[3])) if m else None


def check_items(items: list[dict], today: date) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {k: [] for k in ("ending", "starting", "ended_confirmed", "expected_due", "notice_due", "stale")}
    tomorrow = today + timedelta(days=1)
    for it in items:
        kind, title, mall = it.get("kind"), it.get("title", ""), it.get("mall", "")
        s, e, chk = _d(it.get("s")), _d(it.get("e")), _d(it.get("checked"))
        label = f"{title}({mall}) {it.get('when', '')}"
        if kind == "confirmed" and e:
            if e in (today, tomorrow):
                out["ending"].append(f"{'今日' if e == today else '明日'}終わる: {label}")
            if s == today and "開始日は確認していません" not in it.get("when", ""):
                out["starting"].append(f"今日始まる: {label}")
            if e < today and (today - e).days <= 3:
                out["ended_confirmed"].append(f"終わったばかり(本文・商品ページに『開催中』が残っていないか): {label}")
        if kind == "expected" and (s or _d(f"{it['mo']}-01") if it.get("mo") else s):
            first = s or _d(f"{it['mo']}-01")
            if first and first <= today:
                out["expected_due"].append(f"予想の日が来た・過ぎた(公式を読んで確定にするか、予想を直す): {label}")
        if kind == "notice" and s and s <= today:
            out["notice_due"].append(f"発表予定日が来た・過ぎた(日程が出ているか): {label}")
        if kind in ("confirmed", "expected", "notice") and chk and (today - chk).days > STALE_DAYS and (not e or e >= today):
            out["stale"].append(f"確認日が{(today - chk).days}日前: {label}")
    return out


def check_products(products: list[dict], today: date) -> list[str]:
    out = []
    for p in products:
        slug = p.get("slug", "?")
        page_chk = _d(p.get("checked"))
        if page_chk is None:
            out.append(f"確認日が読めない: 商品ページ {slug}")
        elif (today - page_chk).days > STALE_DAYS:
            out.append(f"確認日が{(today - page_chk).days}日前: 商品ページ {slug}")
        for st in p.get("stores", []):
            c = _d(st.get("checked"))
            if c is None:
                out.append(f"確認日なし: {slug} / {st.get('name')}")
            elif (today - c).days > STALE_DAYS:
                out.append(f"確認日が{(today - c).days}日前: {slug} / {st.get('name')}")
            for row in st.get("rows", []):
                text = " ".join(map(str, row))
                for m in JA_DATE.finditer(text):
                    ed = date(int(m[1]), int(m[2]), int(m[3]))
                    after, before = text[m.end():m.end() + 4], text[max(0, m.start() - 1):m.start()]
                    if after.startswith(("まで", "に終了", "終了")) or before in ("〜", "～"):
                        if ed < today:
                            out.append(f"終了日が過ぎた行: {slug} / {st.get('name')} / {row[0]} ({ed.isoformat()})")
    return out


def load_products() -> list[dict]:
    res = []
    for f in sorted(PRODUCTS.glob("*.json")):
        res.append(json.loads(f.read_text(encoding="utf-8")))
    return res


def render(today: date, groups: dict[str, list[str]], prods: list[str], n_items: int, n_products: int) -> str:
    titles = {"ending": "1. 今日・明日に終わるもの", "starting": "2. 今日始まるもの", "ended_confirmed": "3. 終わったばかりのもの",
              "expected_due": "4. 予想の日が来たもの", "notice_due": "5. 発表予定日が来たもの", "stale": "6. 確認日が古いカレンダーの項目"}
    lines = [f"# SALEカレンダー 鮮度点検 {today.isoformat()}", "",
             f"点検した範囲: カレンダーの項目 {n_items} 件、商品ページ {n_products} ページ(確認日の古さの基準 {STALE_DAYS} 日)。ネットワークは使っていません。", ""]
    total = 0
    for k, t in titles.items():
        rows = groups[k]
        total += len(rows)
        lines += [f"## {t}({len(rows)}件)", ""] + ([f"- {r}" for r in rows] if rows else ["- なし"]) + [""]
    total += len(prods)
    lines += [f"## 7. 商品ページ(店ごとの確認日・終了日)({len(prods)}件)", ""] + ([f"- {r}" for r in prods] if prods else ["- なし"]) + [""]
    lines += [f"合計: {total} 件", ""]
    return "\n".join(lines)


def run(today: date) -> tuple[str, int]:
    sys.path.insert(0, str(ROOT))
    from sites.kaidoki.redesign.schedule import all_items
    items = all_items()
    prods = load_products()
    groups = check_items(items, today)
    pr = check_products(prods, today)
    text = render(today, groups, pr, len(items), len(prods))
    return text, sum(len(v) for v in groups.values()) + len(pr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--today")
    ap.add_argument("--out")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv)
    today = date.fromisoformat(a.today) if a.today else datetime.now(JST).date()
    text, n = run(today)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    return 1 if (a.strict and n) else 0


if __name__ == "__main__":
    raise SystemExit(main())
