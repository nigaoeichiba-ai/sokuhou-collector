"""Tests for the notification outputs (calendar files, dated feed, notify page) and the Bluesky poster."""
import json
import re
import unittest
import urllib.error
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

from sites.saichin import build
from sokuhou.notify import bluesky
from tests.test_saichin_pages import SiteFixture

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 5, 18, 0, tzinfo=JST)


def unfold(ics: str) -> list[str]:
    return ics.replace("\r\n ", "").split("\r\n")


class CalendarFilesTest(SiteFixture):
    def raw(self, rel):
        return (self.out / rel).read_bytes().decode("utf-8")  # read_text would turn CRLF into LF

    def test_every_prefecture_has_a_calendar_and_there_is_one_for_all(self):
        for r in self.d["rows"]:
            self.assertIn(f"calendar/{r['slug']}.ics", self.files)
        self.assertIn("calendar/all.ics", self.files)

    def test_prefecture_calendar_matches_the_data(self):
        r = next(x for x in self.d["rows"] if x["slug"] == "tokyo")
        lines = unfold(self.raw("calendar/tokyo.ics"))
        self.assertEqual(lines[0], "BEGIN:VCALENDAR")
        self.assertIn(f"DTSTART;VALUE=DATE:{r['effective_date'].replace('-', '')}", lines)
        end = date.fromisoformat(r["effective_date"]) + timedelta(days=1)
        self.assertIn(f"DTEND;VALUE=DATE:{end:%Y%m%d}", lines)
        self.assertIn(f"SUMMARY:東京都の最低賃金が{r['amount']:,}円に(発効日)".replace(",", "\\,"), lines)
        self.assertIn("TRIGGER:-PT15H", lines)
        self.assertEqual(lines[-2], "END:VCALENDAR")

    def test_lines_are_crlf_and_at_most_75_octets(self):
        for rel in self.files:
            if rel.endswith(".ics"):
                raw = (self.out / rel).read_bytes()
                self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), rel)
                for line in raw.split(b"\r\n"):
                    self.assertLessEqual(len(line), 75, (rel, line))

    def test_folding_never_splits_a_character(self):
        folded = build.ics_fold("SUMMARY:" + "最低賃金" * 30)
        for part in folded.split("\r\n "):
            part.encode("utf-8").decode("utf-8")
        self.assertEqual(folded.replace("\r\n ", ""), "SUMMARY:" + "最低賃金" * 30)

    def test_all_calendar_has_one_event_per_effective_date(self):
        lines = unfold(self.raw("calendar/all.ics"))
        dates = {r["effective_date"] for r in self.d["rows"]}
        self.assertEqual(lines.count("BEGIN:VEVENT"), len(dates))
        uids = [x for x in lines if x.startswith("UID:")]
        self.assertEqual(len(uids), len(set(uids)))

    def test_carriage_returns_cannot_break_a_content_line(self):
        self.assertNotIn("\r", build.ics_escape("a\r\nb\rc"))
        self.assertEqual(build.ics_escape("a\r\nb\rc"), "a\\nb\\nc")

    def test_stamp_carries_the_time_of_day_in_utc(self):
        lines = unfold(self.raw("calendar/tokyo.ics"))
        self.assertIn("DTSTAMP:20261005T080000Z", lines)  # fixture fetched_at is 2026-10-05T17:00:00+09:00
        self.assertIn("LAST-MODIFIED:20261005T080000Z", lines)

    def test_text_is_escaped(self):
        self.assertEqual(build.ics_escape("a,b;c\\d\ne"), "a\\,b\\;c\\\\d\\ne")

    def test_htaccess_serves_ics(self):
        self.assertIn("text/calendar", self.read(".htaccess"))


class DatesFeedTest(SiteFixture):
    def entries(self):
        root = ET.fromstring(self.read("feed/dates.xml"))
        return root.findall("{http://www.w3.org/2005/Atom}entry")

    def test_one_entry_per_past_effective_date_with_matching_count(self):
        past = {}
        for r in self.d["rows"]:
            if r["effective_date"] <= self.d["fetched_date"]:
                past.setdefault(r["effective_date"], []).append(r)
        self.assertEqual(len(self.entries()), len(past))
        ns = "{http://www.w3.org/2005/Atom}"
        for e in self.entries():
            iso = e.findtext(f"{ns}updated")[:10]
            n = len(past[iso])
            self.assertRegex(e.findtext(f"{ns}title"), rf"{n}都道府県で")
            self.assertEqual(len(e.findtext(f"{ns}summary").split("、")), n)
            self.assertTrue(e.find(f"{ns}link").get("href").endswith(f"/calendar/#d-{iso}"))

    def test_calendar_page_has_the_anchor_the_feed_points_to(self):
        html = self.read("calendar/index.html")
        for e in self.entries():
            iso = e.findtext("{http://www.w3.org/2005/Atom}updated")[:10]
            self.assertIn(f'id="d-{iso}"', html)


class NotifyPageTest(SiteFixture):
    def test_page_lists_all_prefectures_and_feeds(self):
        html = self.read("notify/index.html")
        for r in self.d["rows"]:
            self.assertIn(f'/calendar/{r["slug"]}.ics', html)
        self.assertIn("/feed/dates.xml", html)
        self.assertIn("webcal://saichin-sokuho.com/calendar/all.ics", html)
        self.assertNotIn("Bluesky", html)  # no handle configured in the test config

    def test_social_links_appear_only_when_configured(self):
        d = build.prepare(self.d_raw()) if hasattr(self, "d_raw") else self.d
        cfg = {**build.json.loads("{}"), "site_url": "https://saichin-sokuho.com", "site_name": "x",
               "bluesky_handle": "info-s.bsky.social", "x_handle": "infosokuho"}
        page = build.notify_page(d, cfg, False)
        self.assertIn("https://bsky.app/profile/info-s.bsky.social", page)
        self.assertIn("https://x.com/infosokuho", page)

    def test_pages_link_to_the_notify_page(self):
        self.assertIn("/notify/", self.read("tokyo/index.html"))
        self.assertIn('href="/notify/"', self.read("index.html"))
        self.assertIn("/calendar/tokyo.ics", self.read("tokyo/index.html"))
        self.assertIn("notify/index.html", self.files)
        self.assertIn("https://saichin-sokuho.com/notify/", self.read("sitemap.xml"))


FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><id>tag:x,2026:a</id><title>10月1日、3都道府県で最低賃金の新しい額が発効しました</title>
<link href="https://example.com/calendar/#d-2026-10-01"/><updated>2026-10-01T00:00:00+09:00</updated>
<summary>東京都 1,280円、神奈川県 1,279円、大阪府 1,231円</summary></entry>
<entry><id>tag:x,2026:b</id><title>10月4日、1都道府県で最低賃金の新しい額が発効しました</title>
<link href="https://example.com/calendar/#d-2026-10-04"/><updated>2026-10-04T00:00:00+09:00</updated>
<summary>沖縄県 1,086円</summary></entry>
<entry><id>tag:x,2025:old</id><title>去年のお知らせ</title>
<link href="https://example.com/calendar/#d-2025-10-01"/><updated>2025-10-01T00:00:00+09:00</updated>
<summary>古い</summary></entry>
</feed>""".encode("utf-8")


def mine(link, handle="info-s.bsky.social"):
    return {"post": {"author": {"handle": handle}, "record": {"embed": {"external": {"uri": link}}}}}


class FakeHttp:
    def __init__(self, feed=FEED, authored=None, fail_with=None, fail_times=None):
        self.feed, self.authored, self.calls = feed, authored or [], []
        self.fail_with, self.fail_times = fail_with, fail_times

    def get(self, url):
        self.calls.append(("GET", url))
        if "getAuthorFeed" in url:
            return json.dumps({"feed": self.authored}).encode()
        return self.feed

    def post_json(self, url, body, token=None):
        self.calls.append(("POST", url, body, token))
        if url.endswith("createSession"):
            return {"did": "did:plc:abc", "accessJwt": "jwt"}
        if self.fail_with and (self.fail_times is None or self.fail_times > 0):
            if self.fail_times is not None:
                self.fail_times -= 1
            raise urllib.error.HTTPError(url, self.fail_with, "x", {}, None)
        return {"uri": "at://x"}


class PagedHttp(FakeHttp):
    """Author feed served in pages: the first reply carries a cursor, the second does not."""
    def __init__(self, pages):
        super().__init__()
        self.pages = list(pages)

    def get(self, url):
        if "getAuthorFeed" in url:
            self.calls.append(("GET", url))
            page = self.pages.pop(0)
            body = {"feed": page}
            if self.pages:
                body["cursor"] = "next"
            return json.dumps(body).encode()
        return super().get(url)


def run(http, **kw):
    args = dict(password=None, post=False, max_posts=3, max_age_days=7, today=date(2026, 10, 5), now=NOW, http=http)
    args.update(kw)
    return bluesky.run("https://example.com/feed/dates.xml", "info-s.bsky.social", **args)


class BlueskyTest(unittest.TestCase):
    def test_dry_run_sends_nothing_and_skips_old_entries(self):
        http = FakeHttp()
        texts = run(http)
        self.assertEqual(len(texts), 2)
        self.assertNotIn("去年", "".join(texts))
        self.assertFalse([c for c in http.calls if c[0] == "POST"])

    def test_oldest_first_and_link_in_text(self):
        texts = run(FakeHttp())
        self.assertTrue(texts[0].startswith("10月1日"))
        self.assertTrue(texts[0].endswith("https://example.com/calendar/#d-2026-10-01"))

    def test_already_posted_links_are_skipped(self):
        authored = [mine("https://example.com/calendar/#d-2026-10-01")]
        texts = run(FakeHttp(authored=authored))
        self.assertEqual(len(texts), 1)
        self.assertIn("沖縄県", texts[0])

    def test_reposts_and_other_accounts_do_not_count_as_already_posted(self):
        link = "https://example.com/calendar/#d-2026-10-01"
        repost = {**mine(link), "reason": {"$type": "app.bsky.feed.defs#reasonRepost"}}
        other = mine(link, handle="someone.bsky.social")
        self.assertEqual(len(run(FakeHttp(authored=[repost, other]))), 2)

    def test_dedup_follows_the_cursor(self):
        link = "https://example.com/calendar/#d-2026-10-01"
        http = PagedHttp([[mine("https://example.com/other")], [mine(link)]])
        self.assertEqual(len(run(http)), 1)

    def test_rate_limit_stops_the_run_and_fails_loudly(self):
        http = FakeHttp(fail_with=429)
        with self.assertRaises(SystemExit):
            run(http, post=True, password="abcd-efgh-ijkl-mnop")
        creates = [c for c in http.calls if c[0] == "POST" and c[1].endswith("createRecord")]
        self.assertEqual(len(creates), 1)  # stopped after the first 429, did not hammer the API

    def test_a_client_error_on_one_entry_does_not_block_the_next(self):
        http = FakeHttp(fail_with=400, fail_times=1)
        with self.assertRaises(SystemExit):
            run(http, post=True, password="abcd-efgh-ijkl-mnop")
        creates = [c for c in http.calls if c[0] == "POST" and c[1].endswith("createRecord")]
        self.assertEqual(len(creates), 2)

    def test_posting_logs_in_once_and_creates_records(self):
        http = FakeHttp()
        run(http, post=True, password="abcd-efgh-ijkl-mnop")
        posts = [c for c in http.calls if c[0] == "POST"]
        self.assertEqual(len(posts), 3)  # one login, two records
        self.assertTrue(posts[0][1].endswith("createSession"))
        rec = posts[1][2]["record"]
        self.assertEqual(posts[1][2]["repo"], "did:plc:abc")
        self.assertEqual(posts[1][3], "jwt")
        self.assertEqual(rec["$type"], "app.bsky.feed.post")
        self.assertEqual(rec["embed"]["external"]["uri"], "https://example.com/calendar/#d-2026-10-01")

    def test_login_password_is_refused(self):
        with self.assertRaises(SystemExit):
            run(FakeHttp(), post=True, password="my login password")
        with self.assertRaises(SystemExit):
            run(FakeHttp(), post=True, password=None)

    def test_no_login_when_nothing_to_post(self):
        http = FakeHttp()
        run(http, post=True, password=None, today=date(2027, 1, 1))
        self.assertFalse([c for c in http.calls if c[0] == "POST"])

    def test_max_posts_caps_the_run(self):
        self.assertEqual(len(run(FakeHttp(), max_posts=1)), 1)

    def test_facet_offsets_are_utf8_bytes(self):
        e = bluesky.parse_feed(FEED)[0]
        rec = bluesky.record_for(e, NOW)
        text, facet = rec["text"], rec["facets"][0]
        raw = text.encode("utf-8")
        self.assertEqual(raw[facet["index"]["byteStart"]:facet["index"]["byteEnd"]].decode("utf-8"), e.link)
        self.assertGreater(facet["index"]["byteStart"], len(text.split("\n")[0]))  # not a character offset

    def test_long_summary_is_cut_to_the_limit_and_keeps_the_link(self):
        e = bluesky.Entry("i", "題名" * 5, "https://example.com/x", "県名 1,000円、" * 80, date(2026, 10, 5))
        text = bluesky.compose(e)
        self.assertLessEqual(len(text), bluesky.LIMIT)
        self.assertTrue(text.endswith("https://example.com/x"))
        self.assertIn("…", text)

    def test_real_feed_of_the_site_composes_within_the_limit(self):
        # Every entry of the site's real dated feed must fit in one post.
        from tests.test_saichin_pages import CFG, _raw
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            build.render_site(_raw(), CFG, Path(tmp) / "s", release=True)
            xml = (Path(tmp) / "s" / "feed" / "dates.xml").read_bytes()
        entries = bluesky.parse_feed(xml)
        self.assertTrue(entries)
        for e in entries:
            self.assertLessEqual(len(bluesky.record_for(e, NOW)["text"]), bluesky.LIMIT)


if __name__ == "__main__":
    unittest.main()
