"""みんなのイラスト: 301 redirects for URLs that used to exist and are gone (Search Console "見つかりませんでした(404)", 2026-10-28).

A keyword page (/tag/<hash>/) exists only for the 150 biggest keywords, so a keyword that falls out of the list leaves a dead URL; a picture that review hides leaves one too.
Each old URL goes to the page that holds what it held: the set or the genre that has most of the keyword's pictures, the keyword list for a keyword no longer known by name.
A source must never be a page of the build (a redirect would hide it): sites/minna tests check that, and that every target exists.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

# old path (no slash at the start, no slash at the end; anything below it goes too) -> new path
REDIRECTS: dict[str, str] = {
    "tag/7d1895fb2a": "/genre/work/",                             # 資料 (24 pictures, all in the 仕事 genre)
    "tag/397b9ee986": "/series/telework-duotone/",                 # テレワーク
    "tag/6a061031cf": "/series/dinosaur-pose/",                    # きょうりゅう
    "tag/6508da39b2": "/pose/",                                    # しょんぼりする (one pose from each of 15 sets)
    "tag/a1205627c2": "/series/nabe-oden-kawaii/",                 # 鍋
    "tag/82deecf20f": "/series/care-watercolor/",                  # 福祉
    "tag/78a43a548c": "/series/barber-retro/",                     # 昭和
    "tag/2490ced5ac": "/series/yokai-friends-original/",           # おばけ
    "tag/09e7384c81": "/genre/animals/",                           # 動物 (674 pictures; it has a page 4 that no longer exists)
    "tag/1294ac309a": "/tag/",                                     # keywords whose name is no longer known
    "tag/2baa0ba385": "/tag/",
    "tag/f016214243": "/tag/",
    "tag/22504c644b": "/tag/",
    "tag/48515e3974": "/tag/",
    "illust/christmas-pixel-wreath": "/series/christmas-pixel/",   # hidden after review
}


def htaccess_lines(extra: dict[str, str] | None = None) -> str:
    return "".join(f"RewriteRule ^{old}(/.*)?$ {new} [R=301,L]\n" for old, new in {**REDIRECTS, **(extra or {})}.items())


PUBLISHED_TAGS = Path(__file__).resolve().parent / "content" / "published_tags.json"


def published_tags() -> list[str]:
    """Every keyword that has ever had a page (content/published_tags.json; `python sites/minna/build.py --record-tags` adds the ones of the current build)."""
    return json.loads(PUBLISHED_TAGS.read_text(encoding="utf-8"))["tags"] if PUBLISHED_TAGS.exists() else []


def record_tags(current: set[str]) -> int:
    """Add the keywords of the current build to the file; returns how many were new."""
    have = set(published_tags())
    new = set(current) - have
    PUBLISHED_TAGS.write_text(json.dumps({"tags": sorted(have | set(current))}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="")
    return len(new)


def auto_tag_redirects(published: list[str], built_urls: set[str], tag_url, tagged, series_urls: dict[str, str], genres: set[str], manual: dict[str, str]) -> dict[str, str]:
    """A keyword page exists only for the 150 biggest keywords (MAX_TAG_PAGES), so a keyword that has had a page and falls out of the list would leave a dead URL.
    Each such keyword goes to the set that holds at least half of its pictures, else the genre that does, else the keyword list.  A hand-written entry of REDIRECTS wins."""
    out: dict[str, str] = {}
    for t in published:
        url = tag_url(t)
        key = url.strip("/")
        if url in built_urls or key in manual:
            continue
        its = tagged(t)
        target = "/tag/"
        if its:
            s, n = Counter(i["series"] for i in its).most_common(1)[0]
            g, m = Counter(i["genre"] for i in its).most_common(1)[0]
            if n * 2 >= len(its) and s in series_urls:
                target = series_urls[s]
            elif m * 2 >= len(its) and g in genres:
                target = f"/genre/{g}/"
        out[key] = target
    return out
