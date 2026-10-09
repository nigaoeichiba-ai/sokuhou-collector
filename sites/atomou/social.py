"""atomou: the daily posts (what the growth routine writes, and posts once an account is connected).

    python -m sites.atomou.social [--today YYYY-MM-DD] [--out FILE] [--post]

Every day it picks up to three posts from the verified, public catalogue (never a quiet day, never anything of a visitor):
  - a count: a day that is 1, 7, 30 or 100 days away ("「共通テスト」まで、あと100日。出典つきの公式の日付です。"),
  - a field: the next dates of one field (a different one each day),
  - on Mondays: the main dates of the coming week.
It writes them as Markdown (the workflow shows it on the run's summary page, so the owner can paste a post by hand) and, with --post, sends them to the accounts whose
secrets are set (Bluesky: ATOMOU_BSKY_HANDLE + ATOMOU_BSKY_APP_PASSWORD; Mastodon: ATOMOU_MASTODON_BASE + ATOMOU_MASTODON_TOKEN).  Without a secret nothing is sent.
A post is facts and a link, in plain words: no "おめでとう", no hashtags beyond the field's name, no mentions, no promise of a result.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from sites.atomou import catalog

HERE = Path(__file__).resolve().parent
COUNTS = (1, 7, 30, 100)
MAX_POSTS = 3
WD = "月火水木金土日"


def _site(cfg: dict | None = None) -> str:
    cfg = cfg or json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    return str(cfg["site_url"]).rstrip("/")


def _short(s: str, n: int = 28) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _md(e: dict) -> str:
    d = date.fromisoformat(e["date"])
    return f"{d.month}/{d.day}({WD[d.weekday()]})"


def public_days(entries: list[dict], today: date) -> list[dict]:
    """Whole days still to come that may be posted (verified catalogue entries, not quiet, with a day)."""
    return sorted((e for e in entries if e["precision"] == "day" and not e["quiet"] and date.fromisoformat(e["date"]) > today and e["status"] != "ended"),
                  key=lambda e: (e["date"], e["id"]))


def count_post(e: dict, today: date, base: str) -> str:
    n = (date.fromisoformat(e["date"]) - today).days
    if n == 1:
        return f"明日、{_md(e)}は「{_short(e['title'])}」です。\n出典つきの公式の日付です。\n{base}/e/{e['id']}/"
    return f"「{_short(e['title'])}」まで、あと{n}日。{_md(e)}です。\n出典つきの公式の日付です。\n{base}/e/{e['id']}/"


def field_post(subject: str, rows: list[dict], base: str) -> str:
    lines = [f"{subject}の、これからの日付。"] + [f"・{_md(e)} {_short(e['title'], 24)}" for e in rows[:3]]
    return "\n".join(lines) + f"\n{base}/search/?q={quote(subject)}"


def week_post(rows: list[dict], today: date, base: str) -> str:
    end = today + timedelta(days=6)
    lines = [f"今週({today.month}/{today.day}〜{end.month}/{end.day})の主な日付。"] + [f"・{_md(e)} {_short(e['title'], 24)}" for e in rows[:5]]
    return "\n".join(lines) + f"\n{base}/"


def pick(entries: list[dict], today: date, base: str) -> list[dict]:
    """[{"kind": "count|field|week", "text": ..., "url": ...}], at most MAX_POSTS, the same for the same day."""
    days = public_days(entries, today)
    posts: list[dict] = []
    used_subjects: set[str] = set()
    for n in COUNTS:     # one count per day: the nearest distance that has a day, a different subject each time round
        rows = [e for e in days if (date.fromisoformat(e["date"]) - today).days == n]
        if rows:
            e = rows[today.toordinal() % len(rows)]
            posts.append({"kind": "count", "text": count_post(e, today, base), "url": f"{base}/e/{e['id']}/", "id": e["id"]})
            used_subjects.add(e["subject"])
            break
    by: dict[str, list[dict]] = {}
    for e in days:
        by.setdefault(e["subject"], []).append(e)
    subjects = sorted(s for s, v in by.items() if len(v) >= 2 and s not in used_subjects)
    if subjects:
        s = subjects[today.toordinal() % len(subjects)]
        posts.append({"kind": "field", "text": field_post(s, by[s], base), "url": f"{base}/search/?q={quote(s)}", "subject": s})
    if today.weekday() == 0:
        week = [e for e in days if (date.fromisoformat(e["date"]) - today).days <= 6]
        if len(week) >= 2:
            posts.append({"kind": "week", "text": week_post(week, today, base), "url": f"{base}/"})
    return posts[:MAX_POSTS]


def markdown(posts: list[dict], today: date) -> str:
    out = [f"# atomou 今日の投稿の下書き({today.isoformat()})", ""]
    if not posts:
        out.append("今日は投稿に向く日付がありません。")
    for i, p in enumerate(posts, 1):
        out += [f"## {i}. {p['kind']}", "", "```", p["text"], "```", ""]
    out.append("貼り付けて投稿するのは、X・LINE オープンチャットなど。自動で送るのは、Bluesky と Mastodon に、シークレットが設定されているときだけです。")
    return "\n".join(out) + "\n"


# ---------------- sending (only when the secrets are set) ----------------
def _post_json(url: str, body: dict, headers: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def bluesky_facets(text: str) -> list[dict]:
    """Links in a Bluesky post are clickable only with a 'facet' giving the byte range of the address."""
    facets = []
    start = 0
    while True:
        i = text.find("https://", start)
        if i < 0:
            break
        j = i
        while j < len(text) and text[j] not in " \n":
            j += 1
        facets.append({"index": {"byteStart": len(text[:i].encode("utf-8")), "byteEnd": len(text[:j].encode("utf-8"))},
                       "features": [{"$type": "app.bsky.richtext.facet#link", "uri": text[i:j]}]})
        start = j
    return facets


def send_bluesky(posts: list[dict], handle: str, password: str) -> int:
    sess = _post_json("https://bsky.social/xrpc/com.atproto.server.createSession", {"identifier": handle, "password": password}, {})
    sent = 0
    for p in posts:
        rec = {"$type": "app.bsky.feed.post", "text": p["text"], "createdAt": datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S.000Z"), "langs": ["ja"], "facets": bluesky_facets(p["text"])}
        _post_json("https://bsky.social/xrpc/com.atproto.repo.createRecord", {"repo": sess["did"], "collection": "app.bsky.feed.post", "record": rec}, {"Authorization": "Bearer " + sess["accessJwt"]})
        sent += 1
    return sent


def send_mastodon(posts: list[dict], base: str, token: str) -> int:
    sent = 0
    for p in posts:
        _post_json(base.rstrip("/") + "/api/v1/statuses", {"status": p["text"], "language": "ja", "visibility": "public"}, {"Authorization": "Bearer " + token})
        sent += 1
    return sent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--today")
    ap.add_argument("--out")
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args(argv)
    today = date.fromisoformat(a.today) if a.today else datetime.now(ZoneInfo("Asia/Tokyo")).date()
    entries, _ = catalog.build_catalog(today)
    posts = pick(entries, today, _site())
    md = markdown(posts, today)
    if a.out:
        with Path(a.out).open("a", encoding="utf-8") as f:
            f.write(md)
    else:
        sys.stdout.buffer.write(md.encode("utf-8"))
    if a.post and posts:
        env = os.environ
        if env.get("ATOMOU_BSKY_HANDLE") and env.get("ATOMOU_BSKY_APP_PASSWORD"):
            print("bluesky:", send_bluesky(posts, env["ATOMOU_BSKY_HANDLE"], env["ATOMOU_BSKY_APP_PASSWORD"]), "sent")
        else:
            print("bluesky: no secrets, nothing sent")
        if env.get("ATOMOU_MASTODON_BASE") and env.get("ATOMOU_MASTODON_TOKEN"):
            print("mastodon:", send_mastodon(posts, env["ATOMOU_MASTODON_BASE"], env["ATOMOU_MASTODON_TOKEN"]), "sent")
        else:
            print("mastodon: no secrets, nothing sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
