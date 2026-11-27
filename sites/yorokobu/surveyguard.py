"""Owner 2026-11-17: no figure of another party's study on a page (no research company's or study's name, no share, breakdown, sample size or period).
What stays: the trend in the site's own words (「ある調査では〜の傾向です」), amounts a reader acts on, and the numbers the site computed itself.

`problems(text)` returns what a sentence shows that it must not.  content.load() runs it over every editorial text (`check_content`), so a page with such a
sentence cannot be built; the tests run it over the scripts and the built pages as well, and prove that it finds the old sentences.

The patterns are narrow on purpose: a product text may say 「綿100%」, a flower shop may be named 日比谷花壇, and the privacy page counts the answers of a survey
the reader made.  A name that is also a shop is refused only where it is given as the maker of a study.
"""
from __future__ import annotations

import re

# names that stand only for research (a company that publishes studies, a studies' release service)
RESEARCH_NAMES = ("アイディエーション", "クロス・マーケティング", "野村総合研究所", "エン・ジャパン", "エンバイト", "GMOアスク", "インテージ", "マクロミル", "ネオマーケティング",
                  "矢野経済", "博報堂", "楽天インサイト", "PR TIMES", "PRTIMES", "Google トレンド", "Googleトレンド", "くらひろ")
_SHOPS = r"(?:日比谷花壇|花キューピット|郵便局のネットショップ|父の日\.jp|母の日\.jp|マイナビ)"
_N = r"[0-9０-９][0-9０-９,，.．]*"
PATTERNS = (
    ("a sample size", re.compile(rf"{_N}\s*人(?:を対象|への(?:アンケート|調査)|に聞|を調査|が回答)")),
    ("a sample size", re.compile(rf"有効回答|回答(?:者|数)[はがも]?\s*[:：]?\s*{_N}|(?<![A-Za-z_])[nNｎ]\s*[=＝]\s*[1-9１-９][0-9０-９,，]{{2,}}")),
    ("a share of a study", re.compile(rf"(?:調査|アンケート)[^。]{{0,80}}?{_N}\s*(?:[%％]|パーセント|ポイント|割)")),
    ("a share of a study", re.compile(rf"{_N}\s*(?:[%％]|パーセント|ポイント|割)[^。]{{0,60}}?(?:調査|アンケート|回答)")),
    ("a share of people", re.compile(rf"{_N}\s*(?:[%％]|パーセント|割)(?:の人|が[^。]{{0,6}}人)|人は(?:、)?{_N}\s*(?:[%％]|割)")),
    ("the period of a study", re.compile(r"調査(?:時期|期間)")),
    ("a study named by a shop", re.compile(rf"{_SHOPS}[^。]{{0,40}}?(?:調査|アンケート)")),
)
# keys of the content files that are records for the editors, never put on a page
RECORD_KEYS = frozenset({"studies", "sources", "source", "survey_budget", "url", "urls", "src", "refs", "evidence", "research"})


def problems(text: str) -> list[str]:
    out = [f"a research name: {n}" for n in RESEARCH_NAMES if n in text]
    for what, pat in PATTERNS:
        m = pat.search(text)
        if m:
            out.append(f"{what}: {m.group(0)}")
    return out


def walk(value, where: str):
    """(where, text) of every string of a content value, leaving out the records."""
    if isinstance(value, str):
        yield where, value
    elif isinstance(value, dict):
        for k, v in value.items():
            if k not in RECORD_KEYS:
                yield from walk(v, f"{where}.{k}")
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            yield from walk(v, f"{where}.{i}")


def check_content(content: dict) -> list[str]:
    return [f"{where}: {p}" for where, text in walk(content, "content") for p in problems(text)]
