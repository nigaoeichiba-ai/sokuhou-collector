"""Builds this site (the scaffold of sokuhou/newsite.py).  python sites/shiken/build.py --release --out release

The scaffold writes every page with the heading and the answer first.  Here, just before the files are written, the heading block of the pages with a hero
is wrapped (the home page, the detail page of 宅建 and the entrance-exam feature), and the calendar files (ics/*.ics) are added.  The text is not changed.
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sokuhou import newsite, sitekit  # noqa: E402

HEAD = re.compile(r'(<h1>.*?</h1>\n(?:<p class="answer">.*?</p>\n)?)', re.S)
HERO = {"index.html": "hero", "takken/index.html": "tk-hero", "tokushu-nyushi/index.html": "tk-hero"}


def finish(pages: dict) -> dict:
    from sites.shiken.gen import ics
    for rel, html in list(pages.items()):
        if not (isinstance(html, str) and rel.endswith("index.html")):
            continue
        cls = HERO.get(rel)
        if cls and "<!--hero-end-->" in html:
            a, b = html.split("<!--hero-end-->", 1)
            m = HEAD.search(a)
            if m:
                pages[rel] = a[:m.start()] + f'<div class="{cls}">' + a[m.start():] + "</div>" + b
        elif "<h1>" in html:
            m = HEAD.search(html)
            if m:
                pages[rel] = html[:m.start()] + '<div class="pagehead">' + m.group(1) + "</div>" + html[m.end():]
    pages.update(ics.files())
    return pages


if __name__ == "__main__":
    # "N days left" and the lists in date order count from today: the content is made again from the dates (gen/facts.py, data/) on every build
    from sites.shiken import gen  # noqa: E402
    gen.write()
    write = sitekit.write_pages
    sitekit.write_pages = lambda pages, out: write(finish(pages), out)
    newsite.main_build(Path(__file__).resolve().parent)
