"""A one-off look at what the Rakuten APIs really return for the links and the pictures (run by the workflow yorokobu-rakuten-probe).

It prints SHAPES only (the affiliate ID and the shops' own names are replaced by placeholders): which fields carry a link, the path and the names of the
parameters of the affiliate link the API gives (`affiliateUrl`), whether the item URL carries tracking, the `_ex=` sizes of the picture URLs, and how many items
have only the 64-px picture.  Nothing is written to a file.
"""
from __future__ import annotations

import collections
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

from sokuhou import rakuten

ROOT = Path(__file__).resolve().parents[2]


def shape(url: str, aff_id: str) -> str:
    """The URL with the ID and the shop/item names masked: host, path pattern and the names (not the values) of the parameters."""
    if not url:
        return "(none)"
    u = urllib.parse.urlsplit(url)
    path = u.path.replace(aff_id, "<ID>") if aff_id else u.path
    if u.netloc in ("item.rakuten.co.jp", "thumbnail.image.rakuten.co.jp"):
        path = re.sub(r"[^/]+", "<x>", path)
    q = urllib.parse.parse_qsl(u.query, keep_blank_values=True)
    names = []
    for k, v in q:
        if k in ("pc", "m"):
            inner = urllib.parse.urlsplit(v)
            iq = [a for a, _ in urllib.parse.parse_qsl(inner.query, keep_blank_values=True)]
            names.append(f"{k}=<{inner.scheme}://{inner.netloc}{re.sub(r'[^/]+', '<x>', inner.path)}{'?' + '&'.join(iq) if iq else ''}>")
        elif k == "_ex":
            names.append(f"_ex={v}")
        else:
            names.append(f"{k}=<v>")
    return f"{u.scheme}://{u.netloc}{path}" + ("?" + "&".join(names) if names else "")


def main() -> int:
    app, key = os.environ.get("RAKUTEN_APP_ID"), os.environ.get("RAKUTEN_ACCESS_KEY")
    if not (app and key):
        print("the Rakuten secrets are not set")
        return 1
    cfg = json.loads((ROOT / "sites" / "yorokobu" / "config.json").read_text(encoding="utf-8"))
    aff = cfg["rakuten_affiliate_id"]
    client = rakuten.Client(app, key, referer=cfg["site_url"].rstrip("/") + "/", affiliate_id=aff, min_interval=1.5)
    batches = {"search": [], "ranking": []}
    def take(kind, fn, **kw):
        try:
            batches[kind] += fn(**kw)
        except rakuten.RakutenError as e:
            print(f"{kind} {kw}: {str(e)[:120]}")
    for kw in ("ハンドクリーム ギフト", "お菓子 詰め合わせ", "タオル ギフト", "ボールペン", "おもちゃ 子供", "紅茶 ギフト"):
        take("search", client.search, keyword=kw, hits=30)
    take("ranking", client.ranking, age=30, sex=1, page=1)
    take("ranking", client.ranking, genreId=100227, page=1)
    for name, raws in batches.items():
        raws = [r.get("Item", r) for r in raws]
        print(f"== {name}: {len(raws)} items")
        if not raws:
            continue
        print("fields:", " ".join(sorted(raws[0])))
        for field in ("affiliateUrl", "itemUrl", "shopAffiliateUrl"):
            c = collections.Counter(shape(r.get(field) or "", aff) for r in raws)
            print(f"-- {field}: {sum(1 for r in raws if r.get(field))} of {len(raws)} have it")
            for s, n in c.most_common(4):
                print(f"   {n:3d} x {s}")
        for field in ("mediumImageUrls", "smallImageUrls"):
            c = collections.Counter()
            for r in raws:
                for e in (r.get(field) or [])[:1]:
                    c[shape(e.get("imageUrl") if isinstance(e, dict) else e, aff)] += 1
            print(f"-- {field}: {sum(1 for r in raws if r.get(field))} of {len(raws)} have it")
            for s, n in c.most_common(4):
                print(f"   {n:3d} x {s}")
        only_small = [r for r in raws if not r.get("mediumImageUrls") and r.get("smallImageUrls")]
        none = [r for r in raws if not r.get("mediumImageUrls") and not r.get("smallImageUrls")]
        print(f"-- items with only the small (64px) picture: {len(only_small)}; with no picture: {len(none)}")
        same = sum(1 for r in raws if r.get("affiliateUrl") and r.get("itemUrl") and r["affiliateUrl"] == r["itemUrl"])
        print(f"-- items whose affiliateUrl equals itemUrl: {same}")
    # does the link carry OUR affiliate ID?  (asked three ways; the ID itself is never printed)
    print("== which ID is in the link")
    ours = aff.split(".")
    for label, kw in (("with affiliateId=ours", {"affiliateId": aff}), ("without affiliateId", {})):
        c2 = rakuten.Client(app, key, referer=cfg["site_url"].rstrip("/") + "/", affiliate_id=None, min_interval=1.5)
        try:
            raws = [r.get("Item", r) for r in c2.search(keyword="ハンドクリーム ギフト", hits=10, **kw)]
        except rakuten.RakutenError as e:
            print(label, str(e)[:100])
            continue
        print(f"{label}: itemUrl shapes:", dict(collections.Counter(shape(r.get("itemUrl") or "", aff) for r in raws)))
        links = [r.get("affiliateUrl") or "" for r in raws]
        ids = [urllib.parse.urlsplit(u).path.split("/")[2] if u.count("/") > 3 else "" for u in links]
        pos = [sum(1 for i in ids if len(i.split(".")) == 4 and i.split(".")[k] == ours[k]) for k in range(len(ours))]
        print(f"{label}: per position of the 4 parts, links whose part equals ours (position 1..4): {pos} of {len(ids)}; "
              f"parts shared across the links per position (distinct values): {[len({i.split('.')[k] for i in ids if len(i.split('.')) == 4}) for k in range(4)]}")
        print(f"{label}: {len(links)} links; carry our whole ID: {sum(aff in u for u in links)}; carry any part of our ID: {sum(any(x in u for x in ours) for u in links)}; "
              f"distinct IDs in the links: {len(set(ids))}; ID shape: {sorted({re.sub(r'[a-z]', 'a', re.sub(r'[0-9]', '9', i)) for i in ids})[:3]}; "
              f"rafcid present: {sum('rafcid=' in u for u in links)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
