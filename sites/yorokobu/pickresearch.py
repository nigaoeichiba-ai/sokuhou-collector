"""Helpers for the person (or routine) who writes the day's picks: find candidates, read a Rakuten product page as text.

    python -m sites.yorokobu.pickresearch candidates [--n 40]      Rakuten candidates from the stored ranking data (not used in the last 30 days)
    python -m sites.yorokobu.pickresearch page <item code> [...]   save the product page's visible text to work/picks/<code>.txt and print its key lines

The Amazon side is read in a real browser (see FACTORY_PLAYBOOK.md, 「毎日のおすすめ」): search pages and /dp/<ASIN> pages are fetched with `fetch()` from a tab that is
on amazon.co.jp.  Nothing here writes to the site: the day's file (content/daily/YYYY-MM-DD.json) is written by hand and has to pass dailypicks.problems.
"""
from __future__ import annotations

import argparse
import html as _html
import json
import re
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sites.yorokobu import dailypicks as dp  # noqa: E402

WORK = ROOT.parent / "sokuhou-sites" / "work" / "picks"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
KEY_LINES = re.compile(r"内容量|賞味期限|消費期限|保存方法|サイズ|重量|原材料|アレルゲン|アレルギー|のし|ラッピング|包装|配送|送料|素材|容量|対象年齢|産地|製造者|販売者|名称|冷凍|冷蔵|常温|総合評価|評価 ")


def visible_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript|svg)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h\d|dt|dd|table)>", "\n", raw)
    t = _html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t　]+", " ", t)).strip()


def fetch_page(url: str) -> str:
    """The page's text.  Rakuten's item pages are EUC-JP: the charset is read from the page itself."""
    body = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"}), timeout=40).read()
    m = re.search(rb"charset=([A-Za-z0-9_\-]+)", body[:3000])
    enc = {"euc-jp": "euc_jp", "shift_jis": "cp932", "x-sjis": "cp932"}.get((m.group(1).decode() if m else "utf-8").lower(), (m.group(1).decode() if m else "utf-8").lower())
    return visible_text(body.decode(enc, "ignore"))


def item_url(code: str, ranking: dict) -> str | None:
    for seg in ranking["segments"].values():
        for it in seg["items"]:
            if it["code"] == code:
                return it["url"].split("?")[0]
    return None


def candidates(n: int, days: int = 30) -> list[dict]:
    ranking = json.loads((ROOT / "data" / "yorokobu_ranking.json").read_text(encoding="utf-8"))
    used = set()
    for d in dp.load_days():
        if date.fromisoformat(d["date"]) >= date.today() - timedelta(days=days):
            used |= {e["code"] for e in d["rakuten"]}
    out, seen = [], set()
    for rank in range(10):                       # round by round over the genres, so that one genre does not fill the list
        for slug, seg in ranking["segments"].items():
            if seg["kind"] != "genre" or rank >= len(seg["items"]):
                continue
            it = seg["items"][rank]
            if it["code"] in used or it["code"] in seen or it["price"] < 900 or it["reviews"] < 20 or it["rating"] < 4.4:
                continue
            seen.add(it["code"])
            out.append({**it, "genre": seg["label"]})
    return out[:n]


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("candidates")
    c.add_argument("--n", type=int, default=40)
    g = sub.add_parser("page")
    g.add_argument("codes", nargs="+")
    a = ap.parse_args()
    if a.cmd == "candidates":
        for it in candidates(a.n):
            print(f'{it["code"]} | {it["genre"]} | {it["name"][:56]} | {it["price"]}円 ★{it["rating"]} ({it["reviews"]}件) | {it["shop"][:12]}')
        return
    ranking = json.loads((ROOT / "data" / "yorokobu_ranking.json").read_text(encoding="utf-8"))
    WORK.mkdir(parents=True, exist_ok=True)
    for code in a.codes:
        url = item_url(code, ranking)
        if not url:
            print(code, "not in the stored ranking data (give the item page URL to fetch_page instead)")
            continue
        text = fetch_page(url)
        (WORK / (code.replace(":", "_") + ".txt")).write_text(text, encoding="utf-8")
        print(f"===== {code} {url} ({len(text)} chars)")
        print("\n".join(l.strip()[:200] for l in text.splitlines() if KEY_LINES.search(l))[:3500])


if __name__ == "__main__":
    main()
