"""Finds and reads the RSS / Atom feeds that municipalities and prefectures publish (shared by the sites; first user: kuma-sokuho.com).

The bear sightings are only one use of a municipal feed.  Events, deadlines, notices, closures and the like are what other projects
(for example the countdown service "あと何日、もう何日") can use, so the registry keeps every feed, not only the bear ones:

    discover(top_page_html, base_url) -> candidate feed addresses of one site
    parse_feed(bytes) -> {"title", "items": [{"title", "link", "date", "summary"}]}   (RSS 2.0, RSS 1.0 / RDF, Atom)
    is_bear(item) -> True if the item is about bears (the kuma site reads those)

Every request goes through `kumalib.polite_fetch` (robots.txt, an identifying User-Agent); `scan()` waits between requests.
Only titles, links, dates and a short summary are kept (the feed is the publisher's own announcement for readers and other programs).
"""
from __future__ import annotations

import html as htmllib
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse

from sokuhou.sources import kumalib

MAX_ITEMS = 30
MAX_SUMMARY = 160
FEED_TYPES = ("application/rss+xml", "application/atom+xml", "application/rdf+xml")
BEAR_WORDS = re.compile(r"クマ|ヒグマ|ツキノワ|熊(?![本谷野取ケヶ])")       # not 熊本 / 熊谷 / 熊野 / 熊取 (place names)
LINK_HINT = re.compile(r"rss|atom|feed|\.xml|\.rdf", re.I)


class FeedError(ValueError):
    pass


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _text(el) -> str:
    return "".join(el.itertext()).strip() if el is not None else ""


def _first(kids: dict, *names: str):
    """The first child that exists (an XML element without children is falsy, so `a or b` would skip it)."""
    for n in names:
        if kids.get(n) is not None:
            return kids[n]
    return None


def _clean(s: str) -> str:
    s = htmllib.unescape(s or "")
    s = re.sub(r"</?(?:p|br|div|li|ul|ol|tr|td|th|h\d|table)[^>]*>", " ", s, flags=re.I)     # block tags separate words; inline tags (b, span, a) do not
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).strip()


def parse_date(text: str) -> str | None:
    """RSS (RFC 822) and Atom / Dublin Core (ISO 8601) dates as an ISO date (Japan time); anything else -> None."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        dt = None
    if dt is None:
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            m = re.match(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
            if not m:
                return None
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
            except ValueError:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(kumalib.JST).date().isoformat()


def parse_feed(body: bytes) -> dict:
    """A feed as {title, items}; raises FeedError when the document is not a feed (an HTML page, an error page)."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        raise FeedError(f"not XML: {e}") from e
    kind = _local(root.tag)
    if kind not in ("rss", "feed", "rdf"):
        raise FeedError(f"not a feed: <{kind}>")
    channel = root.find("channel") if kind == "rss" else root
    if channel is None:
        raise FeedError("RSS without a channel")
    title = _clean(_text(next((c for c in channel if _local(c.tag) == "title"), None)))
    entries = [e for e in root.iter() if _local(e.tag) in ("item", "entry")]
    items = []
    for e in entries:
        kids = {}
        for c in e:
            kids.setdefault(_local(c.tag), c)
        link = ""
        if "link" in kids:
            href = kids["link"].get("href")
            link = (href or _text(kids["link"])).strip()
        if not link and "guid" in kids:
            link = _text(kids["guid"]) if _text(kids["guid"]).startswith("http") else ""
        when = parse_date(_text(_first(kids, "pubdate", "date", "published", "updated")))
        summary = _clean(_text(_first(kids, "description", "summary", "encoded")))[:MAX_SUMMARY]
        t = _clean(_text(kids.get("title")))
        if t and link:
            items.append({"title": t, "link": link, "date": when, "summary": summary})
    if not items and kind == "rss" and not entries:
        pass      # an empty feed is still a feed
    items.sort(key=lambda i: i["date"] or "", reverse=True)
    return {"title": title, "items": items[:MAX_ITEMS]}


def discover(page_html: str, base_url: str) -> list[str]:
    """Candidate feed addresses on one page: <link rel="alternate" type="application/rss+xml"> first, then links that look like a feed."""
    out: list[str] = []
    host = urlparse(base_url).netloc

    def add(u: str) -> None:
        u = urljoin(base_url, htmllib.unescape(u.strip()))
        if urlparse(u).scheme in ("http", "https") and urlparse(u).netloc == host and u not in out:
            out.append(u)

    for tag in re.findall(r"<link\b[^>]*>", page_html, re.I):
        if re.search(r'rel=["\']?alternate', tag, re.I) and any(t in tag.lower() for t in FEED_TYPES):
            m = re.search(r'href=["\']([^"\']+)', tag, re.I)
            if m:
                add(m.group(1))
    for href, inner in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page_html, re.I | re.S):
        if LINK_HINT.search(href) or re.search(r"\bRSS\b|RDF|Atom", _clean(inner), re.I):
            add(href)
    return out[:12]


def is_bear(item: dict) -> bool:
    return bool(BEAR_WORDS.search(f"{item.get('title', '')} {item.get('summary', '')}"))


def scan(sites: list[dict], fetch=None, pause=1.0, sleep=time.sleep) -> list[dict]:
    """sites: [{"name", "url"}].  For each site: read the top page, try its feed candidates, keep those that parse.

    Returns [{"name", "site", "feed", "title", "items": n, "newest": date}] (no entry for a site without a feed)."""
    fetch = fetch or kumalib.polite_fetch
    found = []
    for s in sites:
        try:
            top = fetch(s["url"]).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 - a site that cannot be read is just a site without a known feed
            continue
        for cand in discover(top, s["url"]):
            sleep(pause)
            try:
                feed = parse_feed(fetch(cand))
            except Exception:  # noqa: BLE001
                continue
            dates = [i["date"] for i in feed["items"] if i["date"]]
            found.append({"name": s["name"], "site": s["url"], "feed": cand, "title": feed["title"], "items": len(feed["items"]), "newest": max(dates, default=None)})
        sleep(pause)
    return found


# ---------------------------------------------------------------- the daily collection

REGISTRY = "muni_feeds_registry.json"      # data/: [{"id", "name", "site", "feed", "title"}], made by `python -m sokuhou.feedscan discover`
KEEP_DAYS = 21                             # only recent items are stored (the feeds are announcements, not an archive)
KEEP_ITEMS = 15
MAX_FAILED_SHARE = 0.5


def feed_id(url: str) -> str:
    import hashlib
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]


def link_ok(link: str, site: str) -> bool:
    """An item's link must be a public address on the publisher's own site (a feed sometimes carries an intranet address such as http://192.168.0.1/...)."""
    host, own = urlparse(link).netloc.split(":")[0].lower(), urlparse(site).netloc.lower().removeprefix("www.")
    if urlparse(link).scheme not in ("http", "https") or not host or re.fullmatch(r"[\d.]+", host) or "." not in host:
        return False
    return host.removeprefix("www.") == own or host.endswith("." + own)


def recent(items: list[dict], today: date) -> list[dict]:
    lo = date.fromordinal(today.toordinal() - KEEP_DAYS).isoformat()
    return [i for i in items if i["date"] and lo <= i["date"] <= today.isoformat()][:KEEP_ITEMS]


def collect_feeds(registry: list[dict], fetch=None, now: datetime | None = None, sleep=time.sleep, pause=1.0) -> dict:
    """Reads every feed of the registry.  A feed that fails is listed without items (`ok: false`); `merge_feeds` fills it from the last run.

    Raises FeedError when more than half of the feeds fail (the network or the run is broken: nothing is stored)."""
    fetch = fetch or kumalib.polite_fetch
    now = now or datetime.now(kumalib.JST)
    today = now.astimezone(kumalib.JST).date()
    out, failed = [], 0
    for i, r in enumerate(registry):
        if i:
            sleep(pause)
        try:
            feed = parse_feed(fetch(r["feed"]))
            items = recent([i for i in feed["items"] if link_ok(i["link"], r["site"])], today)
            out.append({**r, "ok": True, "items": items})
        except Exception:  # noqa: BLE001 - one site down is normal
            failed += 1
            out.append({**r, "ok": False, "items": []})
    if registry and failed / len(registry) > MAX_FAILED_SHARE:
        raise FeedError(f"{failed} of {len(registry)} feeds failed")
    return {"fetched_at": now.isoformat(), "feeds": out}


def merge_feeds(old: dict | None, new: dict) -> dict:
    """A feed that failed today keeps the items of the last successful run (the other feeds are as read today)."""
    if not old:
        return new
    before = {f["id"]: f for f in old.get("feeds", [])}
    feeds = []
    for f in new["feeds"]:
        if not f["ok"] and f["id"] in before:
            feeds.append({**before[f["id"]], "ok": False})
        else:
            feeds.append(f)
    return {**new, "feeds": feeds}


def _registry_path():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent / "data" / REGISTRY


def collect() -> dict:
    import json
    reg = json.loads(_registry_path().read_text(encoding="utf-8"))
    return collect_feeds(reg)


def check_feeds(old, new):
    if not new["feeds"] or not any(f["ok"] and f["items"] for f in new["feeds"]):
        raise FeedError("no feed returned a recent item")


def discover_to_registry(sites: list[dict], fetch=None) -> list[dict]:
    """The registry for `sites` ([{"name", "url"}]): one entry per feed that parses (a feed with no items is kept: it may be quiet today)."""
    found = scan(sites, fetch)
    seen, out = set(), []
    for f in found:
        if f["feed"] in seen:
            continue
        seen.add(f["feed"])
        out.append({"id": feed_id(f["feed"]), "name": f["name"], "site": f["site"], "feed": f["feed"], "title": f["title"]})
    return out


if __name__ == "__main__":
    import json
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:] == ["discover"]:
        sites = json.loads((_registry_path().parent / "muni_feed_sites.json").read_text(encoding="utf-8"))
        reg = discover_to_registry(sites)
        _registry_path().write_text(json.dumps(reg, ensure_ascii=False, indent=1) + chr(10), encoding="utf-8")
        print(f"{len(reg)} feeds from {len(sites)} sites")
    else:
        print("usage: python -m sokuhou.feedscan discover   (reads data/muni_feed_sites.json, writes data/muni_feeds_registry.json)")
