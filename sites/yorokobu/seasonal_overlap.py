"""How much of a sheet (/oseibo/ /nenga/ /oiwai/ ...) is the stores' own wording?  Run it before a new sheet is committed:

    python -m sites.yorokobu.seasonal_overlap [--list 16]

It opens the pages each sheet names as its source and, for every sentence, finds the longest run of characters that stands letter for letter in those pages.  The rule of the site: no
sentence shares a run of 20 or more characters with its sources, and no sentence lists three or more items in the order a source lists them (facts such as an amount, a 表書き or a date are short and stay; a stored sentence or a whole list of items is not copied).
The network is used only by this command; the build and the tests do not need it.
"""
from __future__ import annotations

import re
import sys
import urllib.request
from html.parser import HTMLParser

from sites.yorokobu import seasonal

MAX_RUN = 20          # characters; a sentence that shares this many in a row with a source has to be put in our own words
MAX_ITEMS = 3         # listed items; three or more items that stand in the same order in a source are the store's choice and order of items, not a fact: make our own selection


TERMS = ("両親", "祖父母", "兄弟", "姉妹", "きょうだい", "伯父", "伯母", "叔父", "叔母", "おい", "めい", "いとこ", "親類", "親族", "友人", "知人", "上司", "同僚", "部下", "取引先", "隣近所",
         "昇進", "昇格", "栄転", "短大", "専門学校", "大学", "小学校", "中学校", "高校", "幼稚園")      # who gives, and the names of the occasions and schools: fixed terms of the subject, not a store's choice of items


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")
    p = _Text()
    p.feed(html)
    return norm("".join(p.out))


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def longest_run(sentence: str, source: str) -> tuple[int, str]:
    """The longest stretch of `sentence` that also stands, letter for letter, in `source`: (length, the stretch)."""
    best, at = 0, 0
    n = len(sentence)
    for i in range(n):
        j = i + best + 1
        while j <= n and sentence[i:j] in source:
            best, at = j - i, i
            j += 1
    return best, sentence[at:at + best]


def item_run(sentence: str, source: str) -> tuple[int, list[str]]:
    """The most items of a list in `sentence` (split at 、 and ・; what is inside 「」 is left out: those are the names of a 表書き) that stand in the same order, next to each other, in `source`.
    The first and the last item may carry words of the sentence around them ("近い親族からはベビーカー"), so their ends are matched on a part of the word."""
    text = re.sub(r"「[^」]*」", "", sentence)
    items = [x.strip() for x in re.split(r"[、・,。:：()（）]", norm(text)) if x.strip()]
    best: list[str] = []
    n = len(items)
    for i in range(n):
        for j in range(i + 1, n):
            mid = items[i + 1:j]
            if any(not 2 <= len(m) <= 14 for m in mid):
                break
            if j - i + 1 <= len(best):
                continue
            hit = False
            for k in range(len(items[i]) - 1):                                    # the longest tail of the first item first
                head = items[i][k:]
                for cut in range(len(items[j]), 1, -1):                           # the longest start of the last item first
                    tail = items[j][:cut]
                    for sep in ("、", "・"):
                        if sep.join([head, *mid, tail]) in source:
                            hit = True
                            break
                    if hit:
                        break
                if hit:
                    break
            if hit:
                best = [items[i][k:], *mid, items[j][:cut]]
            else:
                break                                                              # a longer run through this gap cannot match either
    return len(best), best


def sentences(page: dict):
    """(section, sentence) of every text of a page; table cells after the first column count, the row names do not."""
    def split(t):
        return [x for x in re.split(r"(?<=。)", t) if x.strip()]
    for s in page["sections"]:
        for t in s.get("p", []) + s.get("list", []) + s.get("check", []) + ([s["note"]] if s.get("note") else []):
            for x in split(t):
                yield s, x
        for r in (s.get("table") or {}).get("rows", []):
            for c in r[1:]:
                for x in split(c):
                    yield s, x


def too_close(data: dict, source_text: dict[str, str], limit: int = MAX_RUN) -> list[tuple[int, str, str, str]]:
    """[(run length, page slug, the shared run, the sentence)] of every sentence whose run with its named sources is `limit` characters or more."""
    out = []
    for pg in data["pages"]:
        for s, x in sentences(pg):
            src = "".join(source_text.get(k, "") for k in s.get("src", []))
            n, run = longest_run(norm(x), src)
            if n >= limit:
                out.append((n, pg["slug"], run, x.strip()))
    out.sort(reverse=True)
    return out


def same_order_items(data: dict, source_text: dict[str, str], limit: int = MAX_ITEMS) -> list[tuple[int, str, list[str], str]]:
    """[(items, page slug, the items, the sentence)] of every sentence that lists `limit` or more items in the order a named source lists them."""
    out = []
    for pg in data["pages"]:
        for s, x in sentences(pg):
            src = "".join(source_text.get(k, "") for k in s.get("src", []))
            n, items = item_run(x, src)
            if n >= limit and not all(any(w in it for w in TERMS) for it in items):
                out.append((n, pg["slug"], items, x.strip()))
    out.sort(reverse=True)
    return out


def main(argv: list[str]) -> int:
    data = seasonal.load()
    texts = {}
    for k, v in data["sources"].items():
        try:
            texts[k] = fetch_text(v["url"])
        except Exception as e:                                   # noqa: BLE001 - say which page could not be read; never treat "could not read" as "no overlap"
            print(f"could not read {k} {v['url']}: {e}")
            return 2
    limit = int(argv[1]) if len(argv) > 1 and argv[0] == "--list" else MAX_RUN
    bad = too_close(data, texts, limit)
    total = sum(len(norm(x)) for pg in data["pages"] for _s, x in sentences(pg))
    covered = 0
    for pg in data["pages"]:
        for s, x in sentences(pg):
            n, _ = longest_run(norm(x), "".join(texts[k] for k in s.get("src", [])))
            covered += n if n >= 12 else 0
    print(f"{len(data['pages'])} pages, {total} characters; {covered * 100 // max(1, total)}% of them in runs of 12+ characters that a named source also has")
    for n, slug, run, x in bad:
        print(f"{n:3d}  [{slug}]  {x}")
    print("too close:", len(bad), f"(run >= {limit})")
    lists = same_order_items(data, texts)
    for n, slug, items, x in lists:
        print(f"{n:3d} items in the source's order  [{slug}]  {'、'.join(items)}")
    print("lists in a source's order:", len(lists), f"({MAX_ITEMS}+ items)")
    return 1 if (bad or lists) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
