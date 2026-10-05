"""Post new entries of an Atom feed to Bluesky, so that one feed can reach followers of any of our sites.

Stateless: before posting, the account's own recent posts are read from the public AppView and any entry whose
link already appears there is skipped. Entries older than --max-age-days are never posted, so a first run does
not flood the account with history. Without --post nothing is sent (dry run).

Credentials come from the environment, never from arguments or files in the repo:
    BLUESKY_HANDLE        e.g. info-s.bsky.social
    BLUESKY_APP_PASSWORD  an app password (xxxx-xxxx-xxxx-xxxx) made in Bluesky settings, not the login password

    python -m sokuhou.notify.bluesky --feed https://saichin-sokuho.com/feed/dates.xml            # dry run
    python -m sokuhou.notify.bluesky --feed https://saichin-sokuho.com/feed/dates.xml --post
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

PDS = "https://bsky.social"
APPVIEW = "https://public.api.bsky.app"
USER_AGENT = "sokuhou-notify/0.1 (+https://github.com/nigaoeichiba-ai/sokuhou-collector)"
LIMIT = 300  # Bluesky counts graphemes; code points are never fewer, so this is a safe upper bound
ATOM = "{http://www.w3.org/2005/Atom}"
APP_PASSWORD = re.compile(r"[a-z0-9]{4}(-[a-z0-9]{4}){3}")


@dataclass(frozen=True)
class Entry:
    id: str
    title: str
    link: str
    summary: str
    updated: date


class Http:
    """The only place that touches the network; tests pass a fake with the same two methods."""

    def get(self, url: str) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as res:
            return res.read()

    def post_json(self, url: str, body: dict, token: str | None = None) -> dict:
        headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.loads(res.read())


def parse_feed(xml: bytes) -> list[Entry]:
    root = ET.fromstring(xml)
    out = []
    for e in root.findall(f"{ATOM}entry"):
        link = e.find(f"{ATOM}link")
        out.append(Entry(
            id=(e.findtext(f"{ATOM}id") or "").strip(),
            title=(e.findtext(f"{ATOM}title") or "").strip(),
            link=(link.get("href") if link is not None else "") or "",
            summary=(e.findtext(f"{ATOM}summary") or "").strip(),
            updated=date.fromisoformat((e.findtext(f"{ATOM}updated") or "")[:10]),
        ))
    return [x for x in out if x.id and x.title and x.link]


def compose(entry: Entry) -> str:
    """Title, then as much of the summary as fits, then the link (links count in full toward the limit)."""
    tail = "\n" + entry.link
    room = LIMIT - len(entry.title) - len(tail) - 1
    summary = entry.summary
    if summary and room > 10:
        if len(summary) > room:
            summary = summary[: room - 1].rstrip("、, ") + "…"
        return f"{entry.title}\n{summary}{tail}"
    return f"{entry.title}{tail}"


def link_facet(text: str, link: str) -> dict:
    """Bluesky facets use UTF-8 byte offsets, not character offsets."""
    start = text.rindex(link)
    b0 = len(text[:start].encode("utf-8"))
    return {"index": {"byteStart": b0, "byteEnd": b0 + len(link.encode("utf-8"))},
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": link}]}


def record_for(entry: Entry, now: datetime) -> dict:
    text = compose(entry)
    if len(text) > LIMIT:
        raise ValueError(f"post too long ({len(text)}): {entry.id}")
    return {
        "$type": "app.bsky.feed.post", "text": text, "langs": ["ja"],
        "createdAt": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "facets": [link_facet(text, entry.link)],
        "embed": {"$type": "app.bsky.embed.external",
                  "external": {"uri": entry.link, "title": entry.title, "description": entry.summary[:300]}},
    }


def posted_links(http: Http, handle: str, max_pages: int = 5) -> set[str]:
    """Links of the account's own top-level posts. Reposts and other people's posts must not count as 'already told'."""
    links: set[str] = set()
    cursor = None
    for _ in range(max_pages):
        url = f"{APPVIEW}/xrpc/app.bsky.feed.getAuthorFeed?actor={handle}&limit=100&filter=posts_no_replies"
        if cursor:
            url += f"&cursor={cursor}"
        data = json.loads(http.get(url))
        for item in data.get("feed", []):
            post = item.get("post", {})
            if item.get("reason") or post.get("author", {}).get("handle") != handle:
                continue
            rec = post.get("record", {})
            ext = (rec.get("embed") or {}).get("external") or {}
            if ext.get("uri"):
                links.add(ext["uri"])
            for f in rec.get("facets") or []:
                for feat in f.get("features", []):
                    if feat.get("uri"):
                        links.add(feat["uri"])
        cursor = data.get("cursor")
        if not cursor:
            break
    return links


def select(entries: list[Entry], posted: set[str], today: date, max_age_days: int, max_posts: int) -> list[Entry]:
    """Oldest first, so a backlog is told in order; entries already posted or too old are dropped."""
    fresh = [e for e in entries if e.link not in posted and today - e.updated <= timedelta(days=max_age_days)]
    return sorted(fresh, key=lambda e: (e.updated, e.id))[:max_posts]


def run(feed_url: str, handle: str, *, password: str | None, post: bool, max_posts: int, max_age_days: int,
        today: date, now: datetime, http: Http | None = None) -> list[str]:
    http = http or Http()
    entries = parse_feed(http.get(feed_url))
    todo = select(entries, posted_links(http, handle), today, max_age_days, max_posts)
    texts = []
    session = None
    if post and todo:
        if not password or not APP_PASSWORD.fullmatch(password):
            raise SystemExit("BLUESKY_APP_PASSWORD must be an app password (xxxx-xxxx-xxxx-xxxx); refusing to continue")
        session = http.post_json(f"{PDS}/xrpc/com.atproto.server.createSession",
                                 {"identifier": handle, "password": password})
    failed = []
    for entry in todo:
        try:
            rec = record_for(entry, now)
        except ValueError as e:  # one malformed entry must not block the others
            failed.append(str(e))
            continue
        if session:
            try:
                http.post_json(f"{PDS}/xrpc/com.atproto.repo.createRecord",
                               {"repo": session["did"], "collection": "app.bsky.feed.post", "record": rec},
                               token=session["accessJwt"])
            except urllib.error.HTTPError as e:
                failed.append(f"{entry.id}: HTTP {e.code}")
                if e.code == 429 or e.code >= 500:  # rate limited or server trouble: stop, the next run continues
                    break
                continue
        texts.append(rec["text"])
    if failed:
        print("failed: " + "; ".join(failed), file=sys.stderr)
        raise SystemExit(f"{len(failed)} post(s) failed; {len(texts)} done")
    return texts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--feed", required=True)
    ap.add_argument("--post", action="store_true", help="actually post; default is a dry run")
    ap.add_argument("--max-posts", type=int, default=3)
    ap.add_argument("--max-age-days", type=int, default=7)
    args = ap.parse_args()
    handle = os.environ.get("BLUESKY_HANDLE")
    if not handle:
        sys.exit("set BLUESKY_HANDLE")
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    texts = run(args.feed, handle, password=os.environ.get("BLUESKY_APP_PASSWORD"), post=args.post,
                max_posts=args.max_posts, max_age_days=args.max_age_days, today=now.date(), now=now)
    print(f"{'posted' if args.post else 'dry run, would post'} {len(texts)}")
    for t in texts:
        print("---\n" + t)


if __name__ == "__main__":
    main()
