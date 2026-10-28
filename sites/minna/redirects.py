"""みんなのイラスト: 301 redirects for URLs that used to exist and are gone (Search Console "見つかりませんでした(404)", 2026-10-28).

A keyword page (/tag/<hash>/) exists only for the 150 biggest keywords, so a keyword that falls out of the list leaves a dead URL; a picture that review hides leaves one too.
Each old URL goes to the page that holds what it held: the set or the genre that has most of the keyword's pictures, the keyword list for a keyword no longer known by name.
A source must never be a page of the build (a redirect would hide it): sites/minna tests check that, and that every target exists.
"""
from __future__ import annotations

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


def htaccess_lines() -> str:
    return "".join(f"RewriteRule ^{old}(/.*)?$ {new} [R=301,L]\n" for old, new in REDIRECTS.items())
