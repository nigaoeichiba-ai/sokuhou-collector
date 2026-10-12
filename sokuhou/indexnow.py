"""IndexNow for every public site: the key file, "what changed since the last deploy", and the submission.

IndexNow tells Bing and the other engines that take part (Yandex, Naver, Seznam, Amazon, Yep; Google does not) which URLs are new or changed.
The key is public by design: data/indexnow_keys.json holds one per host, the deploy puts /<key>.txt in the release, and the engines fetch it to
check that the sender owns the site.  Nothing here is secret.

    python -m sokuhou.indexnow prepare  --root release --base https://saichin-sokuho.com     # writes release/<key>.txt
    python -m sokuhou.indexnow snapshot --base https://saichin-sokuho.com --out prev_sitemap.xml   # the sitemap that is live BEFORE the new build goes up
    python -m sokuhou.indexnow submit   --root release --base https://saichin-sokuho.com --prev prev_sitemap.xml [--dry-run] [--all]

What is sent: the URLs of the new sitemap that were not in the previous one, then those whose <lastmod> changed (newest first), at most 1,000 per run
(10,000 with --all, the protocol's limit).  Without a previous sitemap nothing is sent: a missing snapshot must not turn into a flood of unchanged URLs.
Page content is never compared, so a site whose sitemap says "everything changed today" sends up to the cap each day; the fix for that is in its sitemap.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
KEYS_FILE = ROOT / "data" / "indexnow_keys.json"
ENDPOINT = "https://api.indexnow.org/indexnow"
UA = "Mozilla/5.0 (compatible; sokuhou-indexnow/1.0; +https://saichin-sokuho.com/)"   # the hosts refuse the bare Python agent (403)
KEY_RE = re.compile(r"[0-9a-f]{16,128}")
MAX_URLS = 10000          # the protocol's limit per request
DEFAULT_CAP = 1000        # a normal deploy changes a handful of pages; more than this is a sitemap that claims everything changed


class IndexNowError(ValueError):
    pass


def load_keys(path: Path = KEYS_FILE) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    keys = data["hosts"]
    for host, key in keys.items():
        if not KEY_RE.fullmatch(key):
            raise IndexNowError(f"the key of {host} must be 16-128 hex characters")
    return keys


def host_of(base: str) -> str:
    u = urlparse(base)
    if u.scheme != "https" or not u.netloc or u.path not in ("", "/"):
        raise IndexNowError(f"base must look like https://example.com, got {base!r}")
    return u.netloc


def key_for(base: str, keys: dict[str, str] | None = None) -> str:
    keys = load_keys() if keys is None else keys
    host = host_of(base)
    if host not in keys:
        raise IndexNowError(f"no IndexNow key for {host} in data/indexnow_keys.json")
    return keys[host]


def parse_sitemap(xml: str | bytes) -> dict[str, str]:
    """{url: lastmod} in document order ('' when a URL has no lastmod).  A sitemap index is refused: none of our sites uses one."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        raise IndexNowError(f"the sitemap is not valid XML: {e}") from e
    if root.tag.rsplit("}", 1)[-1] == "sitemapindex":
        raise IndexNowError("a sitemap index is not supported (list the pages in one sitemap.xml)")
    out: dict[str, str] = {}
    for url in root:
        if url.tag.rsplit("}", 1)[-1] != "url":
            continue
        loc = lastmod = ""
        for child in url:
            name = child.tag.rsplit("}", 1)[-1]
            if name == "loc":
                loc = (child.text or "").strip()
            elif name == "lastmod":
                lastmod = (child.text or "").strip()
        if loc:
            out[loc] = lastmod
    return out


def changed(prev: dict[str, str], new: dict[str, str], cap: int = DEFAULT_CAP) -> list[str]:
    """New URLs first (in sitemap order), then URLs whose lastmod differs (newest first); a URL without a lastmod is never 'changed'."""
    added = [u for u in new if u not in prev]
    modified = sorted((u for u, m in new.items() if u in prev and m and m != prev[u]), key=lambda u: new[u], reverse=True)
    return (added + modified)[:cap]


def payload(base: str, key: str, urls: list[str]) -> dict:
    host = host_of(base)
    if not KEY_RE.fullmatch(key):
        raise IndexNowError("the key must be 16-128 hex characters")
    prefix = f"https://{host}/"
    bad = [u for u in urls if not u.startswith(prefix)]
    if bad:
        raise IndexNowError(f"URLs outside {prefix}: {bad[:3]}")
    unique = list(dict.fromkeys(urls))
    if not unique:
        raise IndexNowError("no URLs to send")
    return {"host": host, "key": key, "keyLocation": f"https://{host}/{key}.txt", "urlList": unique[:MAX_URLS]}


def fetch(url: str, opener=urllib.request.urlopen) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with opener(req, timeout=60) as r:
        return r.read()


def post(body: dict, opener=urllib.request.urlopen) -> int:
    """200 (accepted) and 202 (accepted, key check pending) are success; anything else raises."""
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": UA})
    try:
        with opener(req, timeout=60) as r:
            status = r.status
    except urllib.error.HTTPError as e:
        raise IndexNowError(f"IndexNow answered {e.code}") from e
    if status not in (200, 202):
        raise IndexNowError(f"IndexNow answered {status}")
    return status


def prepare(root: Path, base: str, keys: dict[str, str] | None = None) -> Path:
    key = key_for(base, keys)
    path = Path(root) / f"{key}.txt"
    path.write_text(key, encoding="utf-8", newline="")     # the file holds the key and nothing else
    return path


def main(argv: list[str] | None = None, opener=urllib.request.urlopen) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("prepare")
    p1.add_argument("--root", required=True)
    p1.add_argument("--base", required=True)
    p2 = sub.add_parser("snapshot")
    p2.add_argument("--base", required=True)
    p2.add_argument("--out", required=True)
    p3 = sub.add_parser("submit")
    p3.add_argument("--root", required=True)
    p3.add_argument("--base", required=True)
    p3.add_argument("--prev")
    p3.add_argument("--all", action="store_true", help="send every URL of the new sitemap (once, to introduce a site)")
    p3.add_argument("--dry-run", action="store_true")
    p3.add_argument("--cap", type=int, default=DEFAULT_CAP)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "prepare":
            print(f"wrote {prepare(Path(a.root), a.base)}")
            return 0
        base = a.base.rstrip("/")
        if a.cmd == "snapshot":
            try:
                data = fetch(base + "/sitemap.xml", opener)
                entries = parse_sitemap(data)
                if not entries:                                    # an error page or an empty file is not a sitemap: keep nothing
                    raise IndexNowError("the live sitemap lists no URLs")
                Path(a.out).write_bytes(data)
                print(f"saved the live sitemap ({len(entries)} URLs)")
            except Exception as e:  # noqa: BLE001 - a missing snapshot only means "send nothing this time"
                print(f"no snapshot of the live sitemap: {e}")
            return 0
        key = key_for(base)
        new = parse_sitemap((Path(a.root) / "sitemap.xml").read_bytes())
        if a.all:
            urls = list(new)[:MAX_URLS]
        else:
            if not a.prev or not Path(a.prev).exists():
                print("no previous sitemap: nothing sent (run once with --all to introduce the site)")
                return 0
            urls = changed(parse_sitemap(Path(a.prev).read_bytes()), new, a.cap)
        if not urls:
            print("no new or changed URLs: nothing sent")
            return 0
        body = payload(base, key, urls)
        if a.dry_run:
            print(f"would send {len(body['urlList'])} URLs for {body['host']}: {body['urlList'][:3]}")
            return 0
        live_key = fetch(f"{base}/{key}.txt", opener).decode("utf-8", "replace").strip()
        if live_key != key:
            print(f"the key file is not live at {base}/{key}.txt: nothing sent")
            return 1
        print(f"IndexNow answered {post(body, opener)} for {len(body['urlList'])} URLs of {body['host']}")
        return 0
    except (IndexNowError, OSError) as e:
        print(f"IndexNow: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
