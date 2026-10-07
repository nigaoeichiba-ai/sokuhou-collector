"""Site-wide invariants for a BUILT site folder (the release/ directory), checked in CI before anything is uploaded.

    python -m sokuhou.sitecheck release --base https://yorokobu-present.com

Why it exists: unit tests that look for strings in a fixture build did not notice a link to a month page that did not exist, tables that overflow a
phone, or an empty section on real content.  This checks the real build, page by page.  Every rule returns a message naming the page, so a failure is
actionable; any problem fails the deploy.

Rules (each is a list entry in RULES below):
  links      every internal href/src (page, image, script, stylesheet) resolves to a file in the build
  sitemap    every URL in sitemap.xml resolves; every indexable page is in the sitemap (thanks/404 pages are noindex and exempt)
  head       an indexable page has a title, a meta description, exactly one h1 and a canonical URL on the site's own host
  leaks      no "None", "undefined", "NaN", "{{" or "}}" in the visible text; no empty <a href>
  tables     every <table> sits inside .tablewrap (otherwise it can push a phone's width out)
  empty      no heading directly followed by another heading of the same or a higher level (an empty section)
  lists      no empty <ul>/<ol> (a list a script fills in carries aria-live)
  images     every <img> has a src and an alt attribute
"""
from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urldefrag, urlparse

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
LEAKS = ("None", "undefined", "NaN", "{{", "[object Object]")
SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "sms:", "line:", "intent:")


class Page(HTMLParser):
    """Collects what the rules need from one html file."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []       # (tag, url) of internal-candidate references
        self.title = ""
        self.description = ""
        self.canonical = ""
        self.noindex = False
        self.h1 = 0
        self.text: list[str] = []
        self.stack: list[str] = []
        self.tables_outside = 0
        self.imgs_bad = 0
        self.empty_anchors = 0
        self.headings: list[tuple[int, int]] = []     # (level, index into self.text_marks)
        self.heading_text: list[tuple[int, str, bool]] = []   # (level, text, has_content_after)
        self._in_title = False
        self._in_script = 0
        self._cur_h: list | None = None
        self._since_heading = 0                       # text/elements seen since the last heading closed
        self.empty_sections: list[str] = []
        self._last_heading: tuple[int, str] | None = None
        self.empty_lists = 0
        self.empty_list_names: list[str] = []
        self._list_stack: list[list[int]] = []        # item counts of open ul/ol

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag in ("script", "style"):
            self._in_script += 1
        if tag == "meta":
            n = (a.get("name") or "").lower()
            if n == "description":
                self.description = (a.get("content") or "").strip()
            if n == "robots" and "noindex" in (a.get("content") or "").lower():
                self.noindex = True
        if tag == "link" and (a.get("rel") or "").lower() == "canonical":
            self.canonical = a.get("href") or ""
        if tag == "link" and a.get("href") and (a.get("rel") or "").lower() in ("stylesheet", "icon", "manifest", "alternate", "apple-touch-icon", "preload"):
            self.links.append(("link", a["href"]))
        if tag == "a" and "href" in a:
            href = (a["href"] or "").strip()
            if not href:
                self.empty_anchors += 1
            else:
                self.links.append(("a", href))
        if tag in ("img", "script", "source", "iframe", "video", "audio") and a.get("src"):
            self.links.append((tag, a["src"]))
        if tag == "img":
            if "alt" not in a or (not a.get("src") and "hidden" not in a):     # a hidden <img> is filled in by script
                self.imgs_bad += 1
        if tag == "table" and "tablewrap" not in " ".join(self.stack):
            self.tables_outside += 1
        if re.fullmatch(r"h[1-6]", tag):
            lvl = int(tag[1])
            if lvl == 1:
                self.h1 += 1
            prev = self._last_heading
            if prev and self._since_heading == 0 and lvl <= prev[0] and prev[0] > 1:
                self.empty_sections.append(prev[1])
            self._cur_h = [lvl, ""]
            self._since_heading = 0
        elif tag in ("ul", "ol"):
            self._list_stack.append([1 if a.get("aria-live") else 0, a.get("class") or "ul"])     # a live region is filled in by script
        elif tag == "li" and self._list_stack:
            self._list_stack[-1][0] += 1
        if tag not in VOID:
            cls = a.get("class") or ""
            self.stack.append(("." + cls.replace(" ", ".")) if cls else tag)
            if tag not in ("html", "head", "body", "main", "div", "section", "article", "header", "footer", "nav") and not self._cur_h:
                self._since_heading += 1
        else:
            if tag == "img" or tag == "input":
                self._since_heading += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in ("script", "style") and self._in_script:
            self._in_script -= 1
        if re.fullmatch(r"h[1-6]", tag) and self._cur_h:
            lvl, txt = self._cur_h
            txt = txt.strip()
            self._last_heading = (lvl, txt)
            self._cur_h = None
            self._since_heading = 0
        if tag in ("ul", "ol") and self._list_stack:
            n, cls = self._list_stack.pop()
            if n == 0:
                self.empty_lists += 1
                self.empty_list_names.append(cls)
        if tag not in VOID and self.stack:
            self.stack.pop()

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_script:
            return
        if self._cur_h is not None:
            self._cur_h[1] += data
        elif data.strip():
            self._since_heading += 1
            self.text.append(data)


def parse(path: Path) -> Page:
    p = Page()
    p.feed(path.read_text(encoding="utf-8", errors="replace"))
    p.close()
    return p


def _local(root: Path, base: str, page_rel: str, ref: str) -> Path | None:
    """Map a reference found on a page to a file under root, or None when it is not internal."""
    ref = ref.strip()
    if not ref or ref.startswith(SKIP_SCHEMES) or ref.startswith("#"):
        return None
    ref = urldefrag(ref)[0]
    u = urlparse(ref)
    if u.scheme in ("http", "https"):
        host = urlparse(base).netloc
        if not host or u.netloc.lower() != host.lower():
            return None
        path = u.path
    elif ref.startswith("//"):
        return None
    elif u.scheme:
        return None
    else:
        path = u.path
        if not path:
            return None
        if not path.startswith("/"):
            d = "/" + page_rel.rsplit("/", 1)[0] + "/" if "/" in page_rel else "/"
            path = d + path
    path = unquote(path)
    parts: list[str] = []
    for seg in path.split("/"):
        if seg == "..":
            if parts:
                parts.pop()
        elif seg and seg != ".":
            parts.append(seg)
    rel = "/".join(parts)
    cand = root / rel if rel else root
    if path.endswith("/") or cand.is_dir():
        return cand / "index.html"
    return cand


def sitemap_urls(root: Path) -> list[str]:
    out: list[str] = []
    for sm in sorted(root.glob("sitemap*.xml")):
        out += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm.read_text(encoding="utf-8", errors="replace"))
    return out


def check_dir(root: Path, base: str, require_sitemap: bool = True, skip: tuple[str, ...] = ()) -> list[str]:
    """Problems found in a built folder, each as '[rule] page: message'.  skip names rules to leave out (see the module docstring)."""
    root = Path(root)
    found: list[tuple[str, str]] = []

    def add(rule: str, msg: str) -> None:
        found.append((rule, msg))

    pages = sorted(p for p in root.rglob("*.html"))
    if not pages:
        return ["[links] no html files in " + str(root)]
    host = urlparse(base).netloc
    indexable: set[Path] = set()
    for f in pages:
        rel = f.relative_to(root).as_posix()
        if re.fullmatch(r"google[0-9a-f]+\.html", rel):     # Search Console's ownership file is not a page
            continue
        pg = parse(f)
        is_404 = rel == "404.html"
        if not pg.noindex and not is_404:
            indexable.add(f.resolve())
            if not pg.title.strip():
                add("head", f"{rel}: no <title>")
            if not pg.description:
                add("head", f"{rel}: no meta description")
            if pg.h1 != 1:
                add("head", f"{rel}: {pg.h1} <h1> (must be exactly 1)")
            if not pg.canonical:
                add("head", f"{rel}: no canonical URL")
            elif host and urlparse(pg.canonical).netloc.lower() != host.lower():
                add("head", f"{rel}: canonical points to another host: {pg.canonical}")
        seen: set[str] = set()
        for tag, ref in pg.links:
            target = _local(root, base, rel, ref)
            if target is None or ref in seen:
                continue
            seen.add(ref)
            if not target.exists():
                add("links", f"{rel}: broken {tag} reference {ref}")
        text = " ".join(pg.text)
        for bad in LEAKS:
            if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", text) if bad.isalpha() else bad in text:
                add("leaks", f"{rel}: the text contains {bad!r}")
        if pg.empty_anchors:
            add("leaks", f"{rel}: {pg.empty_anchors} link(s) with an empty href")
        if pg.tables_outside:
            add("tables", f"{rel}: {pg.tables_outside} table(s) outside .tablewrap (they can overflow a phone)")
        for h in pg.empty_sections:
            add("empty", f"{rel}: empty section under the heading {h!r}")
        if pg.empty_lists:
            add("lists", f"{rel}: {pg.empty_lists} empty list(s): {', '.join(pg.empty_list_names)}")
        if pg.imgs_bad:
            add("images", f"{rel}: {pg.imgs_bad} <img> without src or alt")
    urls = sitemap_urls(root)
    if not urls and require_sitemap:
        add("sitemap", "no sitemap.xml with <loc> entries")
    mapped: set[Path] = set()
    for u in urls:
        t = _local(root, base, "index.html", u)
        if t is None:
            add("sitemap", f"sitemap: a URL on another host: {u}")
        elif not t.exists():
            add("sitemap", f"sitemap: URL does not resolve to a file: {u}")
        else:
            mapped.add(t.resolve())
    if urls:
        for f in sorted(indexable - mapped):
            add("sitemap", f"{f.relative_to(root.resolve()).as_posix()}: indexable page missing from the sitemap")
    return [f"[{r}] {m}" for r, m in found if r not in skip]


def _get(url: str, timeout: int = 30, retries: int = 2) -> tuple[int, bytes]:
    import time
    import urllib.error
    import urllib.request
    last = (0, b"")
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (sitecheck; +owner's own site)"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            last = (e.code, b"")
            if e.code < 500:
                return last
        except Exception:
            last = (0, b"")
        time.sleep(1 + i)
    return last


def check_live(base: str, workers: int = 8, probes: tuple[str, ...] = ()) -> tuple[list[str], int]:
    """The deployed site: every sitemap URL answers 200 and obeys the page rules; every internal link on those pages answers 200.
    Returns (problems, number of pages fetched).  Used right after a deploy (a failure rolls the site back) and by the weekly review."""
    import tempfile
    from concurrent.futures import ThreadPoolExecutor
    base = base.rstrip("/")
    code, body = _get(base + "/sitemap.xml")
    if code != 200:
        return [f"[sitemap] {base}/sitemap.xml answered {code}"], 0
    urls = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body.decode("utf-8", "replace"))
    extra = [u for u in re.findall(r"<loc>\s*([^<\s]+\.xml)\s*</loc>", body.decode("utf-8", "replace"))]   # a sitemap index
    for sm in extra:
        c2, b2 = _get(sm)
        if c2 == 200:
            urls += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", b2.decode("utf-8", "replace"))
    urls = [u for u in dict.fromkeys(urls) if not u.endswith(".xml")]
    problems: list[str] = []
    if not urls:
        return ["[sitemap] the live sitemap lists no pages"], 0
    host = urlparse(base).netloc
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        with ThreadPoolExecutor(workers) as ex:
            got = list(ex.map(_get, urls))
        for u, (code, body) in zip(urls, got):
            path = urlparse(u).path
            if urlparse(u).netloc.lower() != host.lower():
                problems.append(f"[sitemap] a URL on another host: {u}")
                continue
            if code != 200:
                problems.append(f"[sitemap] {u} answered {code}")
                continue
            rel = path.lstrip("/")
            if not rel or rel.endswith("/"):
                rel += "index.html"
            if not rel.endswith(".html"):
                continue
            f = root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(body)
        # page rules on the mirrored pages; links are resolved against the live site below, not the mirror
        problems += check_dir(root, base, skip=("links", "sitemap"))
        targets: dict[str, str] = {}
        for f in sorted(root.rglob("*.html")):
            rel = f.relative_to(root).as_posix()
            for tag, ref in parse(f).links:
                t = ref.strip()
                if not t or t.startswith(SKIP_SCHEMES) or t.startswith("#") or t.startswith("//"):
                    continue
                u = urlparse(urldefrag(t)[0])
                if u.scheme in ("http", "https") and u.netloc.lower() != host.lower():
                    continue
                if u.scheme not in ("", "http", "https"):
                    continue
                path = u.path or "/"
                if not path.startswith("/"):
                    d = "/" + rel.rsplit("/", 1)[0] + "/" if "/" in rel else "/"
                    path = d + path
                full = base + path + (("?" + u.query) if u.query and "." in path.rsplit("/", 1)[-1] else "")
                targets.setdefault(full, rel)
        known = {u for u in urls}
        todo = [t for t in targets if t not in known]
        with ThreadPoolExecutor(workers) as ex:
            res = list(ex.map(lambda t: _get(t)[0], todo))
        for t, code in zip(todo, res):
            if code != 200:
                problems.append(f"[links] {targets[t]}: {t} answered {code}")
    for pr in probes:
        c, _ = _get(base + pr)
        if c != 200:
            problems.append(f"[probe] {base}{pr} answered {c}")
    return problems, len(urls)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", help="the built folder (omit with --live)")
    ap.add_argument("--base", required=True, help="the site URL, e.g. https://yorokobu-present.com")
    ap.add_argument("--live", action="store_true", help="check the deployed site at --base instead of a folder")
    ap.add_argument("--probe", action="append", default=[], help="an extra path that must answer 200 (with --live)")
    ap.add_argument("--max", type=int, default=60, help="print at most this many problems")
    a = ap.parse_args(argv)
    if a.live:
        problems, n = check_live(a.base, probes=tuple(a.probe))
        if problems:
            print(f"LIVE CHECK FAILED: {len(problems)} problem(s) in {n} pages of {a.base}")
            for pr in problems[: a.max]:
                print("  - " + pr)
            return 1
        print(f"live check ok: {n} pages of {a.base}")
        return 0
    if not a.root:
        ap.error("a folder is needed without --live")
    problems = check_dir(Path(a.root), a.base)
    n = len(list(Path(a.root).rglob("*.html")))
    if problems:
        print(f"SITECHECK FAILED: {len(problems)} problem(s) in {n} pages")
        for p in problems[: a.max]:
            print("  - " + p)
        if len(problems) > a.max:
            print(f"  ... and {len(problems) - a.max} more")
        return 1
    print(f"sitecheck ok: {n} pages, {len(sitemap_urls(Path(a.root)))} sitemap URLs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
