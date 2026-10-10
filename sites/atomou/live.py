"""The live feed (速報): headlines of OFFICIAL feeds (a ministry, the central bank, a game maker's own news, a platform's own blog), taken every few minutes, with the day they speak of.

    python sites/atomou/live.py --state live_state.json --out live.v1.json

What it takes: only feeds that publish for reuse (RSS / RDF / Atom of the owner of the information) and are listed in data/atomou/live_sources.json.  What it keeps of an item: the title,
the address of the official page, the source's name, the time, the genre, and a day written in the title or the short description.  Never the body, a picture or a thumbnail.  Social
networks, news portals and the press agencies are not read (their terms do not allow it).  The page behind the address is the one to trust: an item says "自動検出" until the day is checked
(see sites/atomou/recheck.py, later).

Politeness: a conditional request (ETag / Last-Modified), a minimum gap per source, a name and a contact in the User-Agent, a short time-out, and a source that fails again and again is left alone
for longer and longer.  The output keeps the last 72 hours."""
import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES_FILE = ROOT / "data" / "atomou" / "live_sources.json"
UA = "atomou-bot/1.0 (+https://atomou.com; official feeds only; contact via the site's form)"
KEEP_HOURS = 72
MAX_ITEMS = 300
TITLE_MAX = 80
JST = timezone(timedelta(hours=9))
# what is never shown: a death, an accident, a disaster's damage (no day to count to, and it is not ours to hurry)
# what is not worth a push of a headline: minutes, papers of a committee, hiring, the result of a consultation
NOISE = re.compile(r"議事録|議事概要|配布資料|会議資料|資料$|採用|プレエントリー|インターンシップ|意見募集の結果|分科会|部会|専門調査会|審議会|作業班|ワーキンググループ|記者会見|内示|交付決定")
# an item says something to count to: an announcement, a start, a sale, a deadline, a release, a meeting date
EVENTFUL = re.compile(r"発売|予約|受付|開始|締切|施行|改定|開催|公表|発表|決定|解禁|終了|募集|配信|公開|リリース|アップデート|開業|就航|打ち上げ|打上げ|投票|選挙|会合|サミット|\d+月\d+日|[０-９]+月[０-９]+日")
SENSITIVE = re.compile(r"死去|訃報|逝去|追悼|お悔やみ|事故|被害|遭難|殺人|逮捕|不祥事|謝罪|リコール|不具合|脆弱性|障害|訴訟")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def load_sources(path=SOURCES_FILE):
    data = json.loads(path.read_text(encoding="utf-8"))
    return [s for s in data["sources"] if s.get("on", True) and str(s.get("url", "")).startswith("https://")]


# ---------- reading the bytes of a feed ----------
def decode(body: bytes, content_type: str = "") -> str:
    """Text of a feed: the encoding comes from the XML declaration, else the HTTP header, else UTF-8 (Japanese government feeds are often Shift_JIS)."""
    m = re.search(rb"<\?xml[^>]*encoding=[\"']([\w-]+)[\"']", body[:300])
    enc = (m.group(1).decode("ascii") if m else "") or (re.search(r"charset=([\w-]+)", content_type or "", re.I) or [None, ""])[1] or "utf-8"
    enc = {"shift_jis": "cp932", "shift-jis": "cp932", "sjis": "cp932", "x-sjis": "cp932", "euc-jp": "euc_jp"}.get(enc.lower(), enc)
    try:
        return body.decode(enc)
    except (LookupError, UnicodeDecodeError):
        return body.decode("utf-8", "replace")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _text(el) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", "".join(el.itertext()))).strip() if el is not None else ""


def _iso(s: str) -> datetime:
    """An ISO 8601 time such as 2026-10-10T09:30:00+09:00, 2026-10-10T00:30:00Z or 2026-10-10 (Python 3.6 on the server has no datetime.fromisoformat)."""
    s = s.strip().replace("Z", "+0000")
    s = re.sub(r"([+-]\d\d):(\d\d)$", lambda m: m.group(1) + m.group(2), s)
    s = re.sub(r"\.\d+(?=[+-]\d{4}$|$)", "", s)
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M%z", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(s)


def parse_time(s: str):
    s = (s or "").strip()
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError, IndexError):
        d = None
    if d is None:
        try:
            d = _iso(s)
        except ValueError:
            return None
    return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=JST).astimezone(timezone.utc)


def parse_feed(text: str):
    """RSS 2.0 / RDF (RSS 1.0) / Atom -> [{title, url, desc, time}].  Anything that is not well-formed gives []."""
    text = re.sub(r"^<\?xml[^>]*\?>", "", text.lstrip("﻿ \r\n\t"))
    try:
        root = ET.fromstring(text.encode("utf-8"))
    except ET.ParseError:
        return []
    out = []
    for el in root.iter():
        if _local(el.tag) not in ("item", "entry"):
            continue
        kid = {}
        for c in el:
            k = _local(c.tag)
            if k == "link":
                href = c.get("href") or (c.text or "").strip()
                if href and (c.get("rel") in (None, "alternate") or "link" not in kid):
                    kid["link"] = href
            elif k not in kid:
                kid[k] = _text(c)
        t = parse_time(kid.get("pubdate") or kid.get("published") or kid.get("updated") or kid.get("date") or "")
        out.append({"title": re.sub(r"\s+", " ", kid.get("title", "")), "url": kid.get("link", ""), "desc": re.sub(r"\s+", " ", kid.get("description") or kid.get("summary") or kid.get("encoded") or "")[:300], "time": t})
    return out


# ---------- the day an item speaks of ----------
_DAY = re.compile(r"(?:(\d{4})\s*年\s*)?(\d{1,2})\s*月\s*(\d{1,2})\s*日")


def day_in(text: str, published: date) -> str:
    """The first day (not already a week past) named in the words, as YYYY-MM-DD; a day without a year is the next such day.  '' when there is none."""
    s = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    for m in _DAY.finditer(s):
        y, mo, d = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
        try:
            if y:
                dt = date(y, mo, d)
            else:
                dt = date(published.year, mo, d)
                if dt < published - timedelta(days=60):   # a month or two back is a day that has passed; much older is next year's
                    dt = date(published.year + 1, mo, d)
        except ValueError:
            continue
        if dt >= published - timedelta(days=7):
            return dt.isoformat()
    return ""


# ---------- genre ----------
def classify(src: dict, title: str):
    """(group, mid, subject): the source's own, or the first rule of the source whose pattern is in the title."""
    for rule in src.get("rules", []):
        if re.search(rule["re"], title):
            return rule["group"], rule.get("mid", "その他"), rule.get("subject", src.get("subject", ""))
    return src["group"], src.get("mid", "その他"), src.get("subject", "")


def item_id(url: str) -> str:
    return hashlib.sha1(url.split("#")[0].encode("utf-8")).hexdigest()[:10]


def make_items(src: dict, entries, now: datetime, seen: dict):
    out = []
    for e in entries:
        url, title = e["url"], e["title"][:TITLE_MAX * 2]
        if not url.startswith("https://") or not title or SENSITIVE.search(title):
            continue
        if NOISE.search(title) or not (EVENTFUL.search(title) or day_in(title, now.astimezone(JST).date())):
            continue
        if src.get("only") and not re.search(src["only"], title):
            continue
        if src.get("skip") and re.search(src["skip"], title):
            continue
        iid = item_id(url)
        first = seen.get(iid) or now.isoformat(timespec="minutes")
        pub = e["time"] or parse_time(first) or now
        if now - pub > timedelta(hours=KEEP_HOURS) or pub - now > timedelta(hours=6):
            continue
        g, m, sub = classify(src, title)
        out.append({"id": iid, "t": title[:TITLE_MAX], "u": url, "s": src["name"], "x": src["id"], "p": pub.astimezone(timezone.utc).isoformat(timespec="minutes"),
                    "f": first, "d": day_in(title + " " + e.get("desc", ""), pub.astimezone(JST).date()), "g": g, "m": m, "k": sub})
    return out


# ---------- fetching ----------
def fetch(src: dict, st: dict, now: datetime, opener=None):
    """One conditional request.  Returns (entries, new state of the source)."""
    s = dict(st)
    gap = int(src.get("every_min", 10)) * 60 * (1 + min(int(s.get("fails", 0)), 6) ** 2)   # a failing source is asked less and less often
    if s.get("at") and time.time() - float(s["at"]) < gap:
        return [], s
    req = urllib.request.Request(src["url"], headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.1"})
    if s.get("etag"):
        req.add_header("If-None-Match", s["etag"])
    if s.get("modified"):
        req.add_header("If-Modified-Since", s["modified"])
    s["at"] = time.time()
    try:
        with (opener or urllib.request.urlopen)(req, timeout=20) as r:
            body = r.read(2_000_000)
            ct = r.headers.get("Content-Type", "")
            s["etag"], s["modified"], s["fails"] = r.headers.get("ETag", ""), r.headers.get("Last-Modified", ""), 0
    except urllib.error.HTTPError as e:
        if e.code == 304:
            s["fails"] = 0
            return [], s
        s["fails"] = int(s.get("fails", 0)) + 1
        s["err"] = f"HTTP {e.code}"
        return [], s
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        s["fails"] = int(s.get("fails", 0)) + 1
        s["err"] = str(e)[:80]
        return [], s
    s.pop("err", None)
    return parse_feed(decode(body, ct)), s


def run(sources, state: dict, now=None, opener=None):
    """-> (public live json, new state, report).  `state` = {"sources": {id: {...}}, "items": {id: item}}."""
    now = now or _now()
    items = {k: v for k, v in (state.get("items") or {}).items() if parse_time(v.get("p", "")) and now - parse_time(v["p"]) <= timedelta(hours=KEEP_HOURS)}
    seen = {k: v["f"] for k, v in items.items()}
    src_state = dict(state.get("sources") or {})
    report = {"ok": 0, "failed": [], "new": 0, "skipped": 0}
    for src in sources:
        entries, ns = fetch(src, src_state.get(src["id"], {}), now, opener)
        src_state[src["id"]] = ns
        if ns.get("err"):
            report["failed"].append(f'{src["id"]}: {ns["err"]}')
        else:
            report["ok"] += 1
        for it in make_items(src, entries, now, seen):
            if it["id"] not in items:
                report["new"] += 1
            items[it["id"]] = {**items.get(it["id"], {}), **it, "f": items.get(it["id"], {}).get("f", it["f"])}
    ranked = sorted(items.values(), key=lambda i: i["p"], reverse=True)[:MAX_ITEMS]
    items = {i["id"]: i for i in ranked}
    pub = {"v": 1, "generated": now.isoformat(timespec="minutes"), "items": [{k: i[k] for k in ("id", "t", "u", "s", "p", "d", "g", "m", "k")} for i in ranked]}
    return pub, {"sources": src_state, "items": items}, report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="live_state.json")
    ap.add_argument("--out", default="live.v1.json")
    ap.add_argument("--sources", default=str(SOURCES_FILE))
    a = ap.parse_args(argv)
    sp = Path(a.state)
    state = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    pub, new_state, rep = run(load_sources(Path(a.sources)), state)
    Path(a.out).write_text(json.dumps(pub, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sp.write_text(json.dumps(new_state, ensure_ascii=False), encoding="utf-8")
    print(f"live: {len(pub['items'])} items ({rep['new']} new), sources ok {rep['ok']}, failed {len(rep['failed'])}")
    for f in rep["failed"]:
        print("  failed:", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
