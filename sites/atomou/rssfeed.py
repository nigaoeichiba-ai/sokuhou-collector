"""The headlines of the big news sites' RSS feeds (data/atomou/rss_sources.json): the entrance for the daily research, so that a result or a new date is not hunted by search one by one.

    python sites/atomou/rssfeed.py fetch --out cache.json          # read every feed now (robots.txt is asked first; a feed that fails is skipped and named)
    python sites/atomou/rssfeed.py match --cache cache.json        # for each finished day waiting for a result (results_queue.py): the articles about it, by feed (never two of one company counted twice)
    python sites/atomou/rssfeed.py leads --cache cache.json        # headlines that name a day and an announcement/start/sale: leads for new cards

The cache is only a work file for the research (outside the repository's data; it is not published and nothing of it is shown on the site).  A headline is a clue, never a source: the day or the
result is read on the organizer's page and on another company's page, and written in our own words (resultcheck.py / seedcheck.py do the checking).  Never logs in, never passes a block."""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sites.atomou import catalog, results_queue, seedcheck  # noqa: E402

SOURCES = ROOT / "data" / "atomou" / "rss_sources.json"
JST = timezone(timedelta(hours=9))
STOP = {"開催", "大会", "試合", "戦", "第", "回", "国際", "親善", "日本", "決勝", "予選", "全国", "世界", "選手権", "発表", "開幕", "開始"}   # words in nearly every title: they match nothing in particular


def strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def parse_time(s: str | None) -> str | None:
    """An ISO time in JST ('2026-10-13T12:30:03+09:00'), or None when the feed gives no readable time."""
    if not s:
        return None
    s = s.strip()
    try:
        dt = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(JST).isoformat(timespec="seconds")


def parse_feed(xml: str, source: dict) -> list[dict]:
    """The items of an RSS 2.0, RSS 1.0 (RDF) or Atom feed: {source, company, title, link, published, summary}.  An item without an https link or a title is dropped."""
    xml = re.sub(r"<!DOCTYPE[^>]*>", "", xml)             # no entity tricks: a feed is read as plain data
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    out = []
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag not in ("item", "entry"):
            continue
        kid = {c.tag.rsplit("}", 1)[-1]: c for c in node}
        title = strip_tags(kid["title"].text if "title" in kid else "")
        link = ""
        if "link" in kid:
            link = (kid["link"].text or kid["link"].attrib.get("href") or "").strip()
        when = parse_time(next((kid[k].text for k in ("pubDate", "date", "updated", "published") if k in kid), None))
        summary = strip_tags(next((kid[k].text for k in ("description", "summary", "encoded", "content") if k in kid and kid[k].text), ""))[:240]
        if link.startswith("http://"):
            link = "https://" + link[len("http://"):]          # the sites answer on https; a plain http link is not kept
        if title and link.startswith("https://"):
            out.append({"source": source["id"], "company": source["company"], "title": title, "link": link, "published": when, "summary": summary})
    return out


def allowed(url: str, fetch_text=None) -> bool:
    """robots.txt of the site lets our fetch read the feed (a robots.txt that cannot be read is taken as 'no rule', as a browser does)."""
    p = urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        text = (fetch_text or (lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=seedcheck.UA), timeout=15).read().decode("utf-8", "replace")))(f"{p.scheme}://{p.netloc}/robots.txt")
    except Exception:
        return True
    rp.parse(text.splitlines())
    return rp.can_fetch(seedcheck.UA["User-Agent"], url)


def fetch_all(sources: list[dict], get=None, robots=None) -> tuple[list[dict], list[tuple]]:
    get = get or (lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=seedcheck.UA), timeout=25).read().decode("utf-8", "replace"))
    robots = robots or allowed
    items, failed, seen = [], [], set()
    for s in sources:
        try:
            if not robots(s["url"]):
                failed.append((s["id"], "robots.txt does not allow"))
                continue
            got = parse_feed(get(s["url"]), s)
        except Exception as e:                      # a feed down is not a failure of the day
            failed.append((s["id"], str(e)[:80]))
            continue
        if not got:
            failed.append((s["id"], "no items"))
        for it in got:
            if it["link"] not in seen:
                seen.add(it["link"])
                items.append(it)
    return items, failed


def merge(old: list[dict], new: list[dict], today: date, keep_days: int = 14) -> list[dict]:
    """A feed shows only its last 50 or so headlines: the daily run adds the new ones to the earlier ones and forgets what is older than two weeks."""
    lo = (today - timedelta(days=keep_days)).isoformat()
    seen, out = set(), []
    for it in new + old:
        if it["link"] in seen or (it.get("published") or "9999")[:10] < lo:
            continue
        seen.add(it["link"])
        out.append(it)
    return out


def tokens(title: str) -> list[str]:
    """The words of a day's title that point at it: names of teams, events, people (not '第38回', years, or the words every title has)."""
    t = re.sub(r"[（(][^）)]*[）)]", " ", title)
    t = re.sub(r"第?\d+[回期戦節節試合日]|\d{4}年?|\d+", " ", t)
    parts = re.split(r"[\s・/／、,，\-~〜「」『』]+", t)
    out = []
    for p in parts:
        if len(p) >= 2 and p not in STOP and p not in out:
            out.append(p)
    return out


RESULT_WORDS = ("勝", "敗", "優勝", "V", "連覇", "制す", "突破", "進出", "決定", "金メダル", "銀メダル", "銅メダル", "本塁打", "完封", "引き分け", "逆転", "惜敗", "初戦", "第2戦", "第3戦")


def score(row: dict, item: dict) -> int:
    """How well a headline fits a finished day: the name words it shares (two, or one long name), and a word that says an outcome.  0 = not about it."""
    toks = tokens(row["title"])
    hay = item["title"] + " " + item["summary"]
    hit = [t for t in toks if t in hay]
    won = any(w in item["title"] for w in RESULT_WORDS)
    if len(hit) >= 2 or (hit and any(len(t) >= 5 for t in hit) and won):
        return len(hit) * 2 + (1 if won else 0)
    return 0


def match(rows: list[dict], items: list[dict], per_day: int = 6) -> dict:
    """{ 'date title': [items] } for each waiting day: articles published on or after the day (JST), best matching first, one per company until every company has one."""
    out = {}
    for r in rows:
        day = (r.get("date_end") or r["date"])
        good = []
        for it in items:
            if not it["published"] or it["published"][:10] < day:
                continue                              # before the day: it is a preview, not a result
            sc = score(r, it)
            if sc:
                good.append((sc, it))
        good.sort(key=lambda x: (-x[0], x[1]["published"]))
        picked, firsts, rest = [], set(), []
        for sc, it in good:
            (rest if it["company"] in firsts else picked).append(it)
            firsts.add(it["company"])
        out[f"{r['date']} {r['title']}"] = (picked + rest)[:per_day]
    return out


LEAD_WORDS = ("発表", "決定", "開催", "発売", "公開", "開幕", "開始", "放送", "配信", "解禁")


def leads(items: list[dict]) -> list[dict]:
    """Headlines that carry a day (月日) and an announcement word: a clue for a new card, to be read on the organizer's page."""
    return [it for it in items if re.search(r"\d{1,2}月\d{1,2}日|\d{4}年\d{1,2}月", it["title"] + it["summary"]) and any(w in it["title"] for w in LEAD_WORDS)]


def load_sources(path: Path = SOURCES) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [s for s in data["sources"] if str(s.get("url", "")).startswith("https://")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "match", "leads"])
    ap.add_argument("--out")
    ap.add_argument("--cache")
    ap.add_argument("--days", type=int, default=8)
    a = ap.parse_args(argv)
    if a.cmd == "fetch":
        items, failed = fetch_all(load_sources())
        path = Path(a.out or "rss_cache.json")
        old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        items = merge(old, items, datetime.now(JST).date())
        path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        print(f"{len(items)} headlines kept from {len(load_sources()) - len(failed)} feeds; skipped: {failed}")
        return 0
    items = json.loads(Path(a.cache).read_text(encoding="utf-8"))
    if a.cmd == "leads":
        for it in leads(items):
            print(f"{it['published'] or '-'}  {it['company']}  {it['title']}  {it['link']}")
        return 0
    today = datetime.now(JST).date()
    entries, _ = catalog.build_catalog(today)
    rows = results_queue.queue(entries, today, a.days, 60)
    got = match(rows, items)
    for k, v in got.items():
        print(k)
        for it in v:
            print(f"    {it['company']}  {it['title']}  {it['link']}")
    print(f"{sum(1 for v in got.values() if v)} of {len(got)} waiting days have articles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
