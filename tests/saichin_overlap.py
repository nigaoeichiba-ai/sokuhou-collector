"""How alike are pages of one kind?  The measure the AdSense review notes use (docs/growth/ADSENSE_PATH_2026-10-20.md, appendix):
the prose of a page (p, li, h2, h3; tables, scripts, charts, navigation left out) with every number turned into '#' and every prefecture name into '@',
cut into 8-character pieces; the overlap of two pages = shared pieces / the smaller page's pieces.  A page that only swaps the name and the numbers of another
scores close to 1; pages whose sentences differ in what they say score low."""
from __future__ import annotations

import re
from itertools import combinations
from pathlib import Path

NAMES = ("北海道 青森 岩手 宮城 秋田 山形 福島 茨城 栃木 群馬 埼玉 千葉 東京 神奈川 新潟 富山 石川 福井 山梨 長野 岐阜 静岡 愛知 三重 滋賀 京都 大阪 兵庫 奈良 和歌山 "
         "鳥取 島根 岡山 広島 山口 徳島 香川 愛媛 高知 福岡 佐賀 長崎 熊本 大分 宮崎 鹿児島 沖縄").split()
# longest first so that '神奈川' is not eaten by a shorter name
NAMES = sorted(NAMES, key=len, reverse=True)


def prose(html: str) -> str:
    m = re.search(r"<main.*?</main>", html, re.S)
    body = m.group(0) if m else html
    for tag in ("table", "script", "style", "svg", "nav", "figure", "footer"):
        body = re.sub(rf"<{tag}\b.*?</{tag}>", "", body, flags=re.S)
    parts = re.findall(r"<(p|li|h2|h3)\b[^>]*>(.*?)</\1>", body, re.S)
    return "".join(re.sub(r"<[^>]+>", "", t) for _, t in parts)


def normalise(text: str) -> str:
    x = re.sub(r"[0-9,.+\-−％%]+", "#", text)
    for n in NAMES:
        x = x.replace(n, "@")
    return re.sub(r"\s+", "", x)


def shingles(text: str, n: int = 8) -> set[str]:
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def overlap(a: set[str], b: set[str]) -> float:
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def page_shingles(path: Path) -> set[str]:
    return shingles(normalise(prose(path.read_text(encoding="utf-8"))))


def kind_overlap(root: Path, slugs: list[str]) -> dict:
    """mean and maximum overlap over all pairs of the pages /<slug>/index.html, and the size of an average page's prose."""
    sh = {s: page_shingles(root / s / "index.html") for s in slugs}
    pairs = [overlap(sh[a], sh[b]) for a, b in combinations(slugs, 2)]
    worst = max(combinations(slugs, 2), key=lambda ab: overlap(sh[ab[0]], sh[ab[1]]))
    return {"mean": sum(pairs) / len(pairs), "max": max(pairs), "worst": worst, "pieces": sum(len(v) for v in sh.values()) // len(sh)}
