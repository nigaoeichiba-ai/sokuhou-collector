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
  seo        what Search Console cannot tell before the page is live (added 2026-10-20 after the owner's SEO instruction):
             - a noindex page is not in the sitemap (a page that asks not to be indexed must not be offered either)
             - every JSON-LD block is valid JSON; a BreadcrumbList has 2+ items numbered 1..n with names, and every item URL is on the site's own host and resolves to a page;
               no company name ("株式会社") anywhere in the markup (owner's rule: the company is named only where the law requires it)
             - an internal link is never worded "こちら" / "ここ" alone (the text of a link is what the linked page is about)
             - a canonical URL is the page's own address, except on a page whose canonical is declared on purpose (pagination of a list points to itself too)
  seo_report (not a gate; `python -m sokuhou.sitecheck <folder> --base ... --report`) lists what is only worth a look: duplicate titles / descriptions / h1 among
             indexable pages, titles over 60 characters or descriptions over 120 or under 40, pages with no JSON-LD, indexable pages with fewer than 2 internal links pointing to them
"""
from __future__ import annotations

import argparse
import re
import sys
import threading
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urldefrag, urlparse

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
LEAKS = ("None", "undefined", "NaN", "{{", "[object Object]")
WEAK_ANCHORS = ("こちら", "ここ", "詳しくはこちら", "詳しくはこちら。", "こちらをクリック", "クリック", "click here", "here")   # a link worded like this says nothing about the page it leads to
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
        self.ld: list[str] = []                       # the text of every <script type="application/ld+json">
        self._in_ld = False
        self._ld_buf = ""
        self.anchor_text: list[tuple[str, str]] = []  # (href, visible text) of every <a>
        self._a: list | None = None
        self._svg = 0
        self._title_done = False
        self.h1_text = ""
        self._in_h1 = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "svg":
            self._svg += 1
        if tag == "title" and not self._svg and not self._title_done:      # an inline picture's own <title> is not the page's
            self._in_title = True
        if tag in ("script", "style"):
            self._in_script += 1
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._in_ld = True
            self._ld_buf = ""
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
                self._a = [href, ""]
        if tag in ("img", "script", "source", "iframe", "video", "audio") and a.get("src"):
            self.links.append((tag, a["src"]))
        if tag == "img":
            counter = "valuecommerce.com/servlet/gifbanner" in a.get("src", "")      # the affiliate programme's 1x1 counter is used exactly as its code gives it (no alt)
            if not counter and ("alt" not in a or (not a.get("src") and "hidden" not in a)):     # a hidden <img> is filled in by script
                self.imgs_bad += 1
        if tag == "table" and "tablewrap" not in " ".join(self.stack):
            self.tables_outside += 1
        if re.fullmatch(r"h[1-6]", tag):
            lvl = int(tag[1])
            if lvl == 1:
                self.h1 += 1
                if self.h1 == 1:
                    self._in_h1 = True
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
        if tag == "svg":
            self._svg = max(0, self._svg - 1)
        if tag == "title" and self._in_title:
            self._in_title = False
            self._title_done = True
        if tag == "script" and self._in_ld:
            self._in_ld = False
            self.ld.append(self._ld_buf)
        if tag == "a" and self._a is not None:
            self.anchor_text.append((self._a[0], re.sub(r"\s+", " ", self._a[1]).strip()))
            self._a = None
        if tag == "h1":
            self._in_h1 = False
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
        if self._in_ld:
            self._ld_buf += data
        if self._in_title:
            self.title += data
        if self._in_script:
            return
        if self._a is not None:
            self._a[1] += data
        if self._in_h1:
            self.h1_text += data
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


def _own_path(rel: str) -> str:
    """The address a built file answers at: a/b/index.html -> /a/b/, x.html -> /x.html."""
    return "/" + (rel[: -len("index.html")] if rel.endswith("index.html") else rel)


def jsonld_problems(rel: str, blocks: list[str], root: Path, base: str, page_rel: str) -> list[str]:
    """The `seo` rule for the structured data of one page (see the module docstring)."""
    out: list[str] = []
    host = urlparse(base).netloc.lower()
    import json

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                yield from walk(v)
        elif isinstance(x, list):
            for v in x:
                yield from walk(v)
        elif isinstance(x, str):
            yield x

    for raw in blocks:
        try:
            data = json.loads(raw)
        except ValueError as e:
            out.append(f"{rel}: a JSON-LD block is not valid JSON ({e})")
            continue
        for text in walk(data):
            if "株式会社" in text:
                out.append(f"{rel}: the structured data names a company ({text[:30]!r}); the company is named only on /about/")
                break
        for node in (data if isinstance(data, list) else [data]):
            if not isinstance(node, dict) or node.get("@type") != "BreadcrumbList":
                continue
            items = node.get("itemListElement") or []
            if len(items) < 2:
                out.append(f"{rel}: BreadcrumbList with {len(items)} item(s) (at least 2)")
                continue
            for n, it in enumerate(items, 1):
                if not isinstance(it, dict) or it.get("position") != n or not str(it.get("name") or "").strip():
                    out.append(f"{rel}: BreadcrumbList item {n} has no name or a wrong position")
                    break
                url = it.get("item")
                if url:
                    if urlparse(url).netloc.lower() != host:
                        out.append(f"{rel}: BreadcrumbList item {n} is on another host: {url}")
                    else:
                        t = _local(root, base, page_rel, url)
                        if t is None or not t.exists():
                            out.append(f"{rel}: BreadcrumbList item {n} does not resolve to a page: {url}")
    return out


def sitemap_urls(root: Path) -> list[str]:
    out: list[str] = []
    for sm in sorted(root.glob("sitemap*.xml")):
        out += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm.read_text(encoding="utf-8", errors="replace"))
    return out


def check_dir(root: Path, base: str, require_sitemap: bool = True, skip: tuple[str, ...] = (), links_out: dict | None = None) -> list[str]:
    """Problems found in a built folder, each as '[rule] page: message'.  skip names rules to leave out (see the module docstring).
    With `links_out` (the live check) the links of every page are handed back as {page: [(tag, ref)]} and not looked up in the folder when the 'links' rule is skipped: the live check resolves them against the live site."""
    root = Path(root)
    found: list[tuple[str, str]] = []

    def add(rule: str, msg: str) -> None:
        found.append((rule, msg))

    pages = sorted(p for p in root.rglob("*.html"))
    if not pages:
        return ["[links] no html files in " + str(root)]
    host = urlparse(base).netloc
    indexable: set[Path] = set()
    noindexed: set[Path] = set()
    for f in pages:
        rel = f.relative_to(root).as_posix()
        if re.fullmatch(r"google[0-9a-f]+\.html", rel):     # Search Console's ownership file is not a page
            continue
        pg = parse(f)
        is_404 = rel == "404.html"
        if pg.noindex:
            noindexed.add(f.resolve())
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
            elif urlparse(pg.canonical).path != _own_path(rel):
                add("seo", f"{rel}: canonical is not the page's own address: {pg.canonical}")
        for msg in jsonld_problems(rel, pg.ld, root, base, rel):
            add("seo", msg)
        weak = sorted({t for h, t in pg.anchor_text if t.lower() in WEAK_ANCHORS and _local(root, base, rel, h) is not None})
        if weak:
            add("seo", f"{rel}: internal link(s) worded {', '.join(repr(w) for w in weak)}: say what the linked page is")
        if links_out is not None:
            links_out[rel] = pg.links
        seen: set[str] = set()
        for tag, ref in ([] if (links_out is not None and "links" in skip) else pg.links):
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
        for f in sorted(noindexed & mapped if indexable else ()):       # a whole site that is noindex on purpose (a preview, atomou's sample) lists what it lists
            add("seo", f"{f.relative_to(root.resolve()).as_posix()}: a noindex page is in the sitemap")
        for f in sorted(indexable - mapped):
            add("sitemap", f"{f.relative_to(root.resolve()).as_posix()}: indexable page missing from the sitemap")
    return [f"[{r}] {m}" for r, m in found if r not in skip]


def duplicate_warnings(root: Path) -> list[str]:
    """Shadow warnings printed with every check (never a failure): indexable pages that share a <title> or a meta description.  Each line names the text and up to 3 pages."""
    root = Path(root)
    by_title: dict[str, list[str]] = {}
    by_desc: dict[str, list[str]] = {}
    for f in sorted(root.rglob("*.html")):
        rel = f.relative_to(root).as_posix()
        if rel == "404.html" or re.fullmatch(r"google[0-9a-f]+\.html", rel):
            continue
        pg = parse(f)
        if pg.noindex:
            continue
        if pg.title.strip():
            by_title.setdefault(pg.title.strip(), []).append(rel)
        if pg.description.strip():
            by_desc.setdefault(pg.description.strip(), []).append(rel)
    out = []
    for label, groups in (("title", by_title), ("description", by_desc)):
        dup = {t: r for t, r in groups.items() if len(r) > 1}
        if dup:
            pages = sum(len(r) for r in dup.values())
            first_text, first_pages = next(iter(dup.items()))
            out.append(f"WARNING [duplicate-{label}]: {len(dup)} {label}(s) are shared by {pages} indexable pages, e.g. {first_text[:40]!r}: {', '.join(first_pages[:3])}. Not a failure.")
    return out


def seo_report(root: Path, base: str) -> list[str]:
    """Things worth a look for search, not a gate (the numbers are in the module docstring).  Each line names the page.  Only indexable pages are looked at."""
    root = Path(root)
    host = urlparse(base).netloc
    rows = []
    inbound: dict[Path, int] = {}
    for f in sorted(root.rglob("*.html")):
        rel = f.relative_to(root).as_posix()
        if rel == "404.html" or re.fullmatch(r"google[0-9a-f]+\.html", rel):
            continue
        pg = parse(f)
        rows.append((f, rel, pg))
    for f, rel, pg in rows:
        seen = set()
        for tag, ref in pg.links:
            if tag != "a":
                continue
            t = _local(root, base, rel, ref)
            if t is not None and t.exists() and t.resolve() != f.resolve() and t.resolve() not in seen:
                seen.add(t.resolve())
                inbound[t.resolve()] = inbound.get(t.resolve(), 0) + 1
    out: list[str] = []
    by_title: dict[str, list[str]] = {}
    by_desc: dict[str, list[str]] = {}
    by_h1: dict[str, list[str]] = {}
    for f, rel, pg in rows:
        if pg.noindex:
            continue
        title, desc, h1 = pg.title.strip(), pg.description.strip(), re.sub(r"\s+", " ", pg.h1_text).strip()
        by_title.setdefault(title, []).append(rel)
        by_desc.setdefault(desc, []).append(rel)
        if h1:
            by_h1.setdefault(h1, []).append(rel)
        if len(title) > 60:
            out.append(f"[title-long] {rel}: {len(title)} characters")
        if desc and len(desc) > 120:
            out.append(f"[desc-long] {rel}: {len(desc)} characters")
        if desc and len(desc) < 40:
            out.append(f"[desc-short] {rel}: {len(desc)} characters")
        if not pg.ld and rel != "contact/index.html":
            out.append(f"[no-jsonld] {rel}")
        if rel != "index.html" and inbound.get(f.resolve(), 0) < 2:
            out.append(f"[few-links-in] {rel}: {inbound.get(f.resolve(), 0)} page(s) link to it")
    for label, groups in (("dup-title", by_title), ("dup-desc", by_desc), ("dup-h1", by_h1)):
        for text, rels in groups.items():
            if text and len(rels) > 1:
                out.append(f"[{label}] {len(rels)} pages share {text[:50]!r}: {', '.join(rels[:3])}")
    return out


_tls = threading.local()   # one set of kept-alive connections per worker thread (urllib opened a new TCP+TLS connection for every request: about 0.9 s each from a US runner to a Japanese server)
_all: list = []   # every connection opened, so that check_live can close them all at the end
_all_lock = threading.Lock()
_UA = {"User-Agent": "Mozilla/5.0 (sitecheck; +owner's own site)"}
_REDIRECTS = (301, 302, 303, 307, 308)
_penalty = {"until": 0.0}   # the server said "too many requests" (429): every worker waits until then (Xserver answered 429 to about 1% of the first fast live check of minna, 2026-10-18)
_penalty_lock = threading.Lock()


def _slow_down(seconds: float) -> None:
    import time
    with _penalty_lock:
        _penalty["until"] = max(_penalty["until"], time.monotonic() + seconds)


_pace_state = {"interval": 0.0, "next": 0.0}   # requests per second over all workers: 0 = no limit


def set_rate(per_second: float) -> None:
    """Spread the requests of all workers evenly (a burst of 170 requests per second from one runner got 429 answers, and on 2026-10-18 several runners were cut off from the whole server soon after)."""
    with _penalty_lock:
        _pace_state["interval"] = 1.0 / per_second if per_second and per_second > 0 else 0.0
        _pace_state["next"] = 0.0


def _pace() -> None:
    import time
    with _penalty_lock:
        if not _pace_state["interval"]:
            return
        now = time.monotonic()
        slot = max(now, _pace_state["next"])
        _pace_state["next"] = slot + _pace_state["interval"]
        wait = slot - now
    if wait > 0:
        time.sleep(wait)


def _wait_penalty() -> None:
    import time
    wait = _penalty["until"] - time.monotonic()
    if wait > 0:
        time.sleep(min(wait, 30))


def _connection(scheme: str, netloc: str, timeout: int):
    import http.client
    conns = getattr(_tls, "conns", None)
    if conns is None:
        conns = _tls.conns = {}
    c = conns.get((scheme, netloc))
    if c is None:
        cls = http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
        c = conns[(scheme, netloc)] = cls(netloc, timeout=timeout)
        with _all_lock:
            _all.append(c)
    return c


def close_connections() -> None:
    """Close every kept-alive connection of every worker thread (they would otherwise wait for the garbage collector)."""
    with _all_lock:
        conns, _all[:] = list(_all), []
    for c in conns:
        try:
            c.close()
        except OSError:
            pass
    if hasattr(_tls, "conns"):
        _tls.conns.clear()


def _drop(scheme: str, netloc: str) -> None:
    c = getattr(_tls, "conns", {}).pop((scheme, netloc), None)
    if c is not None:
        try:
            c.close()
        except OSError:
            pass


def _once(method: str, url: str, timeout: int) -> tuple[int, bytes, str]:
    """One request on this thread's kept-alive connection; a stale connection (the server closed it between two requests) is opened again once.
    Returns (status, body, Location header).  Raises OSError / http.client.HTTPException when the server cannot be reached."""
    import http.client
    u = urlparse(url)
    target = (u.path or "/") + (("?" + u.query) if u.query else "")
    for attempt in (0, 1):
        _wait_penalty()
        _pace()
        c = _connection(u.scheme, u.netloc, timeout)
        try:
            c.request(method, target, headers=_UA)
            r = c.getresponse()
            body = r.read()
            if r.will_close:
                _drop(u.scheme, u.netloc)
            if r.status in (429, 503):
                after = r.getheader("Retry-After", "") or ""
                _slow_down(min(int(after), 30) if after.isdigit() else 2)
            return r.status, (body if method == "GET" else b""), r.getheader("Location", "") or ""
        except (OSError, http.client.HTTPException):
            _drop(u.scheme, u.netloc)
            if attempt == 1:
                raise
    raise OSError("unreachable")


def _fetch(url: str, timeout: int = 30, method: str = "GET") -> tuple[int, bytes]:
    """One answer after up to 5 redirects (as urllib followed them)."""
    from urllib.parse import urljoin
    for _ in range(6):
        status, body, loc = _once(method, url, timeout)
        if status in _REDIRECTS and loc:
            url = urljoin(url, loc)
            continue
        return status, body
    return 0, b""


def _get(url: str, timeout: int = 30, retries: int = 2, method: str = "GET") -> tuple[int, bytes]:
    """The answer for a URL.  A failure (no connection, a 5xx) is tried again `retries` more times; "too many requests" (429) is waited out and tried again up to 6 times
    (all workers pause together, see _slow_down) - it says nothing about the page, only about the speed of the check."""
    import time
    last = (0, b"")
    failures = limited = 0
    while True:
        try:
            status, body = _fetch(url, timeout, method)
            if status == 429:
                limited += 1
                if limited > 6:
                    return 429, b""
                time.sleep(min(2 ** limited, 30))
                continue
            if status < 500:
                return status, body
            last = (status, b"")
        except Exception:
            last = (0, b"")
        failures += 1
        if failures > retries:
            return last
        time.sleep(failures)


def _is_page(url: str) -> bool:
    """A link target that is a page (read with GET); anything with another file extension is an asset (checked with HEAD)."""
    last = urlparse(url).path.rsplit("/", 1)[-1]
    return "." not in last or last.endswith((".html", ".htm"))


def _status_of(url: str) -> int:
    """The status a link target answers: GET for pages; HEAD for images, scripts, styles and the like, and when HEAD does not say 200 (some servers refuse it) GET decides."""
    if _is_page(url):
        return _get(url)[0]
    code = _get(url, method="HEAD")[0]
    return code if code == 200 else _get(url)[0]


def light_selection(urls: list[str], sample: int, prev_urls: set[str] | None = None) -> list[str]:
    """The pages of a LIGHT live check: the home page, every page that is new since the previous deploy, and `sample` others picked at random (the same pick for the same site size).
    Used only for content-only deploys (deploy.yml, fast lane): the real build was already checked page by page, and the full live check runs in the daily full deploy."""
    import random
    prev_urls = prev_urls or set()
    new = [u for u in urls if u not in prev_urls] if prev_urls else []
    home = [u for u in urls if urlparse(u).path in ("", "/")]
    rest = [u for u in urls if u not in set(new) and u not in set(home)]
    picked = random.Random(len(urls)).sample(rest, min(sample, len(rest)))
    return list(dict.fromkeys(home + new + picked))


def check_live(base: str, workers: int = 24, probes: tuple[str, ...] = (), sample: int | None = None, prev_urls: set[str] | None = None, rate: float = 80) -> tuple[list[str], int]:
    """See _check_live; the kept-alive connections are closed whatever happens."""
    set_rate(rate)
    try:
        return _check_live(base, workers, probes, sample, prev_urls)
    finally:
        close_connections()
        set_rate(0)


def _check_live(base: str, workers: int, probes: tuple[str, ...] = (), sample: int | None = None, prev_urls: set[str] | None = None) -> tuple[list[str], int]:
    """The deployed site: every sitemap URL answers 200 and obeys the page rules; every internal link on those pages answers 200.
    With `sample` (the light check of a content-only deploy) only the home page, the new pages and `sample` random pages are fetched.
    Returns (problems, number of pages fetched).  Used right after a deploy (a failure rolls the site back) and by the weekly review."""
    import tempfile
    import time
    from concurrent.futures import ThreadPoolExecutor
    t0 = time.monotonic()
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
    all_urls = urls
    if sample is not None:
        urls = light_selection(urls, sample, prev_urls)
        print(f"light live check: {len(urls)} of {len(all_urls)} pages (the home page, the new pages and {sample} random ones)")
    host = urlparse(base).netloc
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        with ThreadPoolExecutor(workers) as ex:
            got = list(ex.map(_get, urls))
        t_pages = time.monotonic()
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
        page_links: dict[str, list] = {}
        problems += check_dir(root, base, skip=("links", "sitemap", "seo"), links_out=page_links)
        targets: dict[str, str] = {}
        for rel in sorted(page_links):
            for tag, ref in page_links[rel]:
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
        known = {u for u in all_urls}
        todo = [t for t in targets if t not in known]
        t_parse = time.monotonic()
        with ThreadPoolExecutor(workers) as ex:
            res = list(ex.map(_status_of, todo))
        for t, code in zip(todo, res):
            if code != 200:
                problems.append(f"[links] {targets[t]}: {t} answered {code}")
    for pr in probes:
        c, _ = _get(base + pr)
        if c != 200:
            problems.append(f"[probe] {base}{pr} answered {c}")
    t_end = time.monotonic()
    print(f"live check timing: {len(urls)} pages in {t_pages - t0:.0f} s, page rules and link list {t_parse - t_pages:.0f} s, {len(todo)} link targets in {t_end - t_parse:.0f} s, {workers} workers")
    return problems, len(urls)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", help="the built folder (omit with --live)")
    ap.add_argument("--base", required=True, help="the site URL, e.g. https://yorokobu-present.com")
    ap.add_argument("--live", action="store_true", help="check the deployed site at --base instead of a folder")
    ap.add_argument("--probe", action="append", default=[], help="an extra path that must answer 200 (with --live)")
    ap.add_argument("--report", action="store_true", help="also print the SEO report (duplicates, long titles, pages few links point to); it never fails the check")
    ap.add_argument("--max", type=int, default=60, help="print at most this many problems")
    ap.add_argument("--workers", type=int, default=24, help="with --live: parallel requests (each worker keeps one connection open)")
    ap.add_argument("--rate", type=float, default=80, help="with --live: at most this many requests per second in all (0 = no limit)")
    ap.add_argument("--sample", type=int, default=None, help="with --live: a LIGHT check (home page, pages new since --prev, and this many random pages); for content-only deploys")
    ap.add_argument("--prev", help="with --sample: the sitemap.xml of the previous deploy (its URLs are not 'new')")
    a = ap.parse_args(argv)
    if a.live:
        prev_urls = None
        if a.prev:
            try:
                prev_urls = set(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", Path(a.prev).read_text(encoding="utf-8", errors="replace")))
            except OSError:
                prev_urls = None
        problems, n = check_live(a.base, workers=a.workers, probes=tuple(a.probe), sample=a.sample, prev_urls=prev_urls, rate=a.rate)
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
    for line in duplicate_warnings(Path(a.root)):         # shadow, like the same-type warning below
        print(line)
    from sokuhou import sametype
    same_warning = sametype.warning(sametype.measure(Path(a.root)))      # shadow: printed, never a failure
    if same_warning:
        print(same_warning)
    if a.report:
        lines = seo_report(Path(a.root), a.base)
        print(f"seo report: {len(lines)} thing(s) worth a look in {n} pages")
        for ln in lines[: a.max]:
            print("  ~ " + ln)
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
