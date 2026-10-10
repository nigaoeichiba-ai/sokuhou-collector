"""Does a built site copy sentences from other sites?  A measurement, not a verdict.

    python -m sokuhou.originality release --ref https://example.com/a --ref https://example.com/b [--min 14] [--ignore 環境省 ...]

Every page of the built folder is cut into runs of `--min` characters (spaces removed); a run that also occurs on a reference page is a shared run.
Official names (a ministry's document title, a prefecture's map name) are quoted on purpose, so the report lists the shared text and the person
reading it decides.  Run it for every new kind of page, against the pages the new page was inspired by; write the result in the page's notes.
Only the reference pages' text is read (the pages are fetched once, with an identifying User-Agent).
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (compatible; kuma-sokuho-originality-check/1.0; +https://kuma-sokuho.com/about/)"
MIN_RUN = 14


def page_text(raw_html: str, main_only: bool = True) -> str:
    """The visible text: scripts and styles dropped; for a built page only the <main> part (menus and footers repeat on every page)."""
    if main_only and "<main" in raw_html:
        raw_html = raw_html.split("<main", 1)[1].split(">", 1)[1].split("</main>", 1)[0]
    raw_html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw_html)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw_html))).strip()


def runs(text: str, n: int = MIN_RUN) -> set[str]:
    t = re.sub(r"\s", "", text)
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def shared(mine: str, reference: str, n: int = MIN_RUN) -> list[str]:
    """The longest stretches of text both contain (each at least n characters), longest first."""
    a, b = re.sub(r"\s", "", mine), re.sub(r"\s", "", reference)
    common = runs(a, n) & runs(b, n)
    out, i = [], 0
    while i <= len(a) - n:
        if a[i:i + n] in common:
            j = i + n
            while j < len(a) and a[j - n + 1:j + 1] in common:
                j += 1
            out.append(a[i:j])
            i = j
        else:
            i += 1
    return sorted(set(out), key=len, reverse=True)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def check(site_dir: Path, references: dict[str, str], n: int = MIN_RUN, ignore: tuple[str, ...] = ()) -> list[tuple[str, str, str]]:
    """[(page, reference, shared text)] for every page of the built folder; `ignore` drops shared stretches that are only these official names."""
    ref_runs = {name: runs(text, n) for name, text in references.items()}
    out = []
    for f in sorted(site_dir.rglob("index.html")):
        raw = f.read_text(encoding="utf-8")
        if "<main" not in raw:
            continue
        text = page_text(raw)
        t = re.sub(r"\s", "", text)
        mine = runs(t, n)
        for name, rr in ref_runs.items():
            if not mine & rr:
                continue
            for s in shared(text, references[name], n):
                rest = s
                for x in ignore:
                    rest = rest.replace(x, "")
                if len(rest) < n:        # nothing but the official names that are quoted on purpose (and a few characters around them)
                    continue
                out.append(("/" + f.parent.relative_to(site_dir).as_posix() + "/", name, s))
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("site_dir")
    ap.add_argument("--ref", action="append", required=True, help="a reference page's address (repeat)")
    ap.add_argument("--min", type=int, default=MIN_RUN)
    ap.add_argument("--ignore", action="append", default=[], help="an official name that is quoted on purpose (repeat)")
    args = ap.parse_args(argv)
    refs = {}
    for u in args.ref:
        try:
            refs[u] = page_text(fetch(u), main_only=False)
        except Exception as e:  # noqa: BLE001 - say which reference could not be read; never treat that as "no overlap"
            print(f"could not read {u}: {e}", file=sys.stderr)
    if not refs:
        print("no reference page could be read: nothing was measured", file=sys.stderr)
        return 2
    hits = check(Path(args.site_dir), refs, args.min, tuple(args.ignore))
    for page, ref, text in hits[:60]:
        print(f"{page}  <- {ref}\n    「{text[:120]}」({len(text)}文字)")
    print(f"measured {len(refs)} reference page(s) against {args.site_dir}: {len(hits)} shared stretch(es) of {args.min}+ characters")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
