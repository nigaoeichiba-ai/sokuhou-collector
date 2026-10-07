"""Tell Bing and the other IndexNow search engines which URLs exist / changed (Google does not take part: it reads the sitemap).

    python -m sites.minna.indexnow [--base https://minna-no-illust.com] [--dry-run]

The key is public by design: config.json holds it, the build publishes /<key>.txt, and this script posts the URL list of the live sitemap.
Run it after a deploy (the daily routine does).  At most 10,000 URLs per request.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENDPOINT = "https://api.indexnow.org/indexnow"
UA = "Mozilla/5.0 (compatible; minna-indexnow/1.0; +https://minna-no-illust.com/)"


def payload(cfg: dict, urls: list[str]) -> dict:
    base = cfg["site_url"].rstrip("/")
    host = base.split("://", 1)[1]
    key = cfg["indexnow_key"]
    if not re.fullmatch(r"[0-9a-f]{16,128}", key):
        raise ValueError("indexnow_key must be 16-128 hex characters")
    bad = [u for u in urls if not u.startswith(base + "/")]
    if bad:
        raise ValueError(f"URLs outside {base}: {bad[:3]}")
    return {"host": host, "key": key, "keyLocation": f"{base}/{key}.txt", "urlList": urls[:10000]}


def sitemap_urls(base: str) -> list[str]:
    req = urllib.request.Request(base.rstrip("/") + "/sitemap.xml", headers={"User-Agent": UA})      # the host refuses the bare Python agent (403)
    with urllib.request.urlopen(req, timeout=60) as r:
        xml = r.read().decode("utf-8")
    return re.findall(r"<loc>([^<]+)</loc>", xml)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    base = a.base or cfg["site_url"]
    body = payload(cfg, sitemap_urls(base))
    if a.dry_run:
        print(f"would send {len(body['urlList'])} URLs for {body['host']}")
        return 0
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        print(f"IndexNow answered {r.status} for {len(body['urlList'])} URLs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
