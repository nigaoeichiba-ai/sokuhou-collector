"""Linkage: a new article or a changed date reaches the home page, the category, the related pages and the affiliate links BY ITSELF, and a leak stops the deploy.
(Owner 2026-11-15: "when I update an article the top page, the categories and the related places must update automatically; done by hand something is always missed".)

Two halves, one file:

1. complete(pages, spec)  -- called by sokuhou/newsite.py before the pages are rendered.  What a writer used to do by hand is derived from the content:
     * `tags` (a list of words on an article): articles that share a tag list each other under 「関連するページ」 (at most RELATED_MAX, the closest first);
     * a related link is always both ways: when A lists B, and A and B hang under the same parent page, B lists A (the text is A's h1).
   The home page, the category pages, the parent's list of children, the breadcrumb and the sitemap already came out of the content (newsite.py and the site's hooks.py).

2. check_dir(root, base, site)  -- the deploy gate (python -m sokuhou.linkage release --base URL --site NAME), on the REAL build.  Rules (a rule key is "rule|page|detail"):
     orphan          an indexable page nothing else links to
     parent-missing  the page above (the second last item of its breadcrumb) does not link to it: the category / list / hub lacks the page
     related-oneway  A's 「関連するページ」 lists B, they share a parent, but B does not list A
     home-newest     the newest `home_newest` articles (JSON-LD datePublished) are not all linked from the home page (data/linkage/config.json)
     url-as-anchor   the visible text of a link is a URL or a bare domain (owner rule 2026-11-13: a link is worded, never an address)
     affiliate-missing  a page names an affiliated advertiser (data/linkage/advertisers.json) but has no affiliate link for it, or the link is not marked PR / sponsored
     site rules      sites/<site>/linkcheck.py check(root, base, pages) -> [key, ...] for what only that site knows (trend: the flash list; kaidoki: the home's schedule vs /calendar/)
   Modes (data/sites.json "linkage", default "shadow"): stop = any finding stops; ratchet = a finding that is not in data/linkage/baseline_<site>.json stops
   (what existed when the gate was introduced is listed there and shrinks; never grows by hand); shadow = printed only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "linkage"
RELATED_MAX = 4
RELATED_H2 = "関連するページ"
BLOCK_RE = re.compile(r"<h2>" + RELATED_H2 + r'</h2>\s*<ul class="links">(.*?)</ul>', re.S)
URL_TEXT = re.compile(r"^(https?://|www\.)\S+$|^[A-Za-z0-9][A-Za-z0-9.-]*\.(com|jp|net|org|info|biz|co\.jp|or\.jp|go\.jp|ne\.jp|io|me|tv)(/\S*)?$", re.I)
AFFILIATE_HOSTS = ("hb.afl.rakuten.co.jp", "px.a8.net", "ck.jp.ap.valuecommerce.com", "ck.jp.ap.valuecommerce.com", "t.afi-b.com", "h.accesstrade.net", "amzn.to")
AMAZON_TAG = "amazonmacs-22"


# ------------------------------------------------------------------ 1. completing the content
def complete(pages: list[dict], spec: dict | None = None) -> list[dict]:
    """Fill in `related` from `tags` and make every related link two-way (in place; returns pages).  Only pages that opt in (a `related` list or `tags`) are touched."""
    by = {p["path"]: p for p in pages}
    cap = int((spec or {}).get("related_max", RELATED_MAX))

    def has(p: dict, path: str) -> bool:
        return any(r["path"] == path for r in p.get("related", []))

    def add(p: dict, q: dict) -> None:
        if q["path"] != p["path"] and not has(p, q["path"]):
            p.setdefault("related", []).append({"path": q["path"], "text": q["h1"]})

    tagged = [p for p in pages if p.get("tags") and not p.get("noindex")]
    for p in tagged:
        mine = set(p["tags"])
        peers = [q for q in tagged if q is not p and q.get("kind") == p.get("kind") and mine & set(q["tags"])]
        # closest first; among equals the newer one first
        peers.sort(key=lambda q: (len(mine & set(q["tags"])), q.get("published") or q.get("updated") or ""), reverse=True)
        room = cap - len(p.get("related", []))
        for q in peers[: max(room, 0)]:
            add(p, q)
    for p in pages:                                  # two-way: B lists A whenever A lists B (siblings only: a hub's list of its children is another thing)
        for r in list(p.get("related", [])):
            q = by.get(r["path"])
            if q is None or q.get("noindex") or p.get("noindex"):
                continue
            if q.get("parent") == p.get("parent") and q.get("kind") == p.get("kind") and q["path"] != "/" and not p.get("no_reverse"):
                add(q, p)
    return pages


# ------------------------------------------------------------------ 2. the gate
class Info:
    def __init__(self, rel: str, path: str, pg, out: set[str], html: str):
        self.rel, self.path, self.pg, self.out, self.html = rel, path, pg, out, html


def load(root: Path, base: str) -> dict[str, Info]:
    from sokuhou import sitecheck as sc
    root = Path(root)
    pages: dict[str, Info] = {}
    for f in sorted(root.rglob("*.html")):
        rel = f.relative_to(root).as_posix()
        if rel == "404.html" or re.fullmatch(r"google[0-9a-f]+\.html", rel):
            continue
        pg = sc.parse(f)
        pages[sc._own_path(rel)] = Info(rel, sc._own_path(rel), pg, set(), f.read_text(encoding="utf-8", errors="replace"))
    for path, info in pages.items():
        for tag, ref in info.pg.links:
            if tag != "a":
                continue
            t = sc._local(root, base, info.rel, ref)
            if t is not None and t.exists():
                q = sc._own_path(t.relative_to(root).as_posix())
                if q != path:
                    info.out.add(q)
    return pages


def _ld(info: Info, typ: str) -> list[dict]:
    out = []
    for b in info.pg.ld:
        try:
            d = json.loads(b)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == typ:
            out.append(d)
    return out


def _parent(info: Info, base: str) -> str | None:
    for d in _ld(info, "BreadcrumbList"):
        items = d.get("itemListElement") or []
        if len(items) >= 2:
            return urlparse(str(items[-2].get("item", ""))).path or "/"
    return None


def _related(info: Info, pages: dict[str, Info], base: str) -> list[str]:
    from sokuhou import sitecheck as sc
    m = BLOCK_RE.search(info.html)
    if not m:
        return []
    out = []
    for h in re.findall(r'href="([^"]+)"', m.group(1)):
        u = urlparse(h).path
        if u in pages:
            out.append(u)
    return out


def load_config() -> dict:
    f = DATA / "config.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def load_advertisers(site: str) -> list[dict]:
    f = DATA / "advertisers.json"
    if not f.exists():
        return []
    return [a for a in json.loads(f.read_text(encoding="utf-8")).get("advertisers", []) if site in a.get("sites", [])]


def find(root: Path, base: str, site: str | None = None) -> list[str]:
    """Every finding of the generic rules and the site's own, as 'rule|page|detail' keys."""
    pages = load(root, base)
    cfg = load_config().get(site or "", {})
    out: list[str] = []
    inbound = {p: 0 for p in pages}
    for p, i in pages.items():
        for q in i.out:
            if q in inbound:
                inbound[q] += 1
    for p, i in sorted(pages.items()):
        if p == "/" or i.pg.noindex:
            continue
        if inbound[p] == 0:
            out.append(f"orphan|{p}|nothing links to this page")
        par = _parent(i, base)
        if par and par in pages and p not in pages[par].out:
            out.append(f"parent-missing|{p}|{par} does not link to it")
        pr = _parent(i, base)
        for q in _related(i, pages, base):
            j = pages.get(q)
            if j is not None and not j.pg.noindex and _parent(j, base) == pr and p not in _related(j, pages, base):
                out.append(f"related-oneway|{p}|{q} does not link back")
    n = int(cfg.get("home_newest", 0))
    home = pages.get("/")
    if n and home is not None:
        arts = []
        for p, i in pages.items():
            if i.pg.noindex:
                continue
            for d in _ld(i, "Article"):
                if d.get("datePublished"):
                    arts.append((d["datePublished"], p))
        arts.sort(reverse=True)
        if len(arts) >= n:
            cut = arts[n - 1][0]
            must = [p for d, p in arts if d > cut]
            ties = [p for d, p in arts if d == cut]
            for p in must:
                if p not in home.out:
                    out.append(f"home-newest|{p}|one of the {n} newest articles is not on the home page")
            need = n - len(must)
            if sum(1 for p in ties if p in home.out) < need:
                out.append(f"home-newest|{ties[0]}|the home page shows too few of the newest articles ({cut})")
    for p, i in sorted(pages.items()):
        for h, t in i.pg.anchor_text:
            if t and URL_TEXT.match(t.strip()):
                out.append(f"url-as-anchor|{p}|{t.strip()[:60]}")
    out += _affiliate(pages, site) if site else []
    if site:
        f = ROOT / "sites" / site / "linkcheck.py"
        if f.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location(f"_linkcheck_{site}", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            out += list(mod.check(Path(root), base, pages))
    return sorted(set(out))


def _is_affiliate(href: str) -> bool:
    u = urlparse(href if "//" in href else "//" + href.lstrip("/"))
    if any(h in (u.netloc or "") for h in AFFILIATE_HOSTS):
        return True
    return AMAZON_TAG in href


def _affiliate(pages: dict[str, Info], site: str) -> list[str]:
    out = []
    ads = load_advertisers(site)
    if not ads:
        return out
    for p, i in sorted(pages.items()):
        if i.pg.noindex:
            continue
        text = " ".join(i.pg.text)
        links = [(h, t) for h, t in i.pg.anchor_text if _is_affiliate(h)]
        for ad in ads:
            names = ad["names"]
            if not any(n in text for n in names):
                continue
            ok = any(any(n in t for n in names) or any(tok in h for tok in ad.get("href_has", [])) for h, t in links)
            if not ok:
                ok = any(re.search(r'<a[^>]+href="[^"]*(?:' + "|".join(re.escape(h) for h in AFFILIATE_HOSTS) + r')[^"]*"[^>]*>[^<]*<img[^>]+alt="[^"]*(?:' + "|".join(map(re.escape, names)) + ')', i.html))
            if not ok:
                out.append(f"affiliate-missing|{p}|{ad['id']}: the page names {names[0]} but has no affiliate link for it")
        for m in re.finditer(r"<a\b([^>]*)>", i.html):
            a = m.group(1)
            hm = re.search(r'href="([^"]+)"', a)
            if hm and _is_affiliate(hm.group(1)) and "valuecommerce.com/servlet/gifbanner" not in hm.group(1):
                rel = (re.search(r'rel="([^"]*)"', a) or [None, ""])[1]
                if "sponsored" not in rel or "nofollow" not in rel:
                    out.append(f"affiliate-rel|{p}|an affiliate link without rel=\"nofollow sponsored\": {hm.group(1)[:60]}")
                    break
    return out


def baseline(site: str) -> set[str]:
    f = DATA / f"baseline_{site}.json"
    return set(json.loads(f.read_text(encoding="utf-8")).get("keys", [])) if f.exists() else set()


def mode_of(site: str) -> str:
    try:
        reg = json.loads((ROOT / "data" / "sites.json").read_text(encoding="utf-8"))
    except OSError:
        return "shadow"
    d = reg.get("defaults", {}).get("linkage", "shadow")
    for s in reg.get("sites", []):
        if s["name"] == site:
            return s.get("linkage", d)
    return d


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--base", required=True)
    ap.add_argument("--site", required=True)
    ap.add_argument("--mode", choices=("stop", "ratchet", "shadow"))
    ap.add_argument("--write-baseline", action="store_true", help="write the current findings as the baseline (run once when the gate is introduced; never to hide a new leak)")
    a = ap.parse_args(argv)
    found = find(Path(a.root), a.base, a.site)
    if a.write_baseline:
        DATA.mkdir(parents=True, exist_ok=True)
        (DATA / f"baseline_{a.site}.json").write_text(json.dumps({"site": a.site, "keys": found}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"baseline written: {len(found)} finding(s)")
        return 0
    mode = a.mode or mode_of(a.site)
    known = baseline(a.site)
    new = [k for k in found if k not in known]
    gone = sorted(known - set(found))
    print(f"linkage [{a.site}] mode={mode}: {len(found)} finding(s), {len(new)} new, {len(gone)} of the baseline already fixed")
    shown = found if mode == "stop" else new
    for k in shown[:60]:
        print("  - " + k.replace("|", ": ", 1).replace("|", " - ", 1))
    if gone:
        print(f"  (fixed since the baseline, remove from data/linkage/baseline_{a.site}.json: {len(gone)})")
    if mode == "shadow":
        return 0
    return 1 if shown else 0


if __name__ == "__main__":
    sys.exit(main())
