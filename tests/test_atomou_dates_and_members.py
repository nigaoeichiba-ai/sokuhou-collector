"""atomou (2026-11-14, before the full version goes public): the dates read right and nothing of the membership / plan is left.
Dates: "the days to come" on the home page are days to come; a day that has begun and not ended is counted to its end ("あと9日 (終了まで)"), on the card, in the sentence on its page and in the script that
counts again for the visitor; an outside calendar gets the day the card names ("… 開幕" is one day); a count worked out on the build day is not written as a fixed sentence.
Membership: no sign-up box, no first-come places, no referral code, no plan box or card limit, no terms of membership and no member receiver on the server (data/atomou ... SUBSCRIPTION_RESTORE.md says how to bring them back)."""
from __future__ import annotations

import re
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build, catalog  # noqa: E402
from tests.test_atomou_build import CFG  # noqa: E402

TODAY = date(2026, 11, 14)      # a day on which many days of the data have begun and not ended (the data only grows)

ASOF = re.compile(r'<span class="asof"[^>]*>.*?</span>', re.S)


class Dates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = build.build_pages(CFG, release=False, today=TODAY)
        cls.entries, _ = catalog.build_catalog(TODAY)
        cls.running = [e for e in cls.entries if e.get("date_end") and e["precision"] == "day" and e["date"] < TODAY.isoformat() <= e["date_end"] and e["status"] != "ended"]

    def test_there_are_days_that_have_begun_to_try_it_on(self):
        self.assertGreater(len(self.running), 5)

    def test_the_home_block_of_days_to_come_has_only_days_to_come(self):
        home = self.pages["index.html"]
        block = re.search(r'id="soon-h".*?</section>', home, re.S).group(0)
        for d in re.findall(r'<article class="card[^"]*"[^>]*data-date="([^"]+)"', block):
            self.assertGreaterEqual(d, TODAY.isoformat(), d)
        self.assertNotIn("(過去)", block)

    def test_a_card_of_a_day_that_has_begun_counts_to_its_end(self):
        e = self.running[0]
        card = build.card_html(e)
        self.assertIn(f'data-end="{e["date_end"]}"', card)
        self.assertRegex(card, r'<span class="word">(あと|)</span>')
        self.assertTrue("(終了まで)" in card or "(最終日)" in card, card)
        self.assertNotIn("(過去)", card)

    def test_a_card_of_a_day_to_come_and_of_a_day_that_has_ended_are_as_before(self):
        future = next(e for e in self.entries if e["date"] > TODAY.isoformat() and not e.get("date_end") and e["precision"] == "day")
        self.assertNotIn("(終了まで)", build.card_html(future))
        past = {**future, "date": "2026-09-01", "date_end": "2026-09-05"}
        c = build.card_html(past)
        self.assertIn("(過去)", c)
        self.assertNotIn("(終了まで)", c)

    def test_no_page_of_a_day_has_a_count_written_for_the_build_day(self):
        # outside the sentence that the browser writes again, no "as of <date>" count is left on any page of a day
        for path, html in self.pages.items():
            if path.startswith("e/") and isinstance(html, str) and path.endswith("index.html"):
                body = ASOF.sub("", html)
                self.assertNotRegex(re.sub(r"<[^>]+>", " ", body), r"の時点で、(あと|もう)\d+日", path)

    def test_the_sentence_of_a_day_that_has_begun_counts_to_the_end(self):
        found = 0
        for e in self.running:
            page = self.pages[f"e/{e['id']}/index.html"]
            m = ASOF.search(page)
            if m:
                found += 1
                self.assertIn("終了まで", m.group(0)) if e["date_end"] != TODAY.isoformat() else self.assertIn("最終日", m.group(0))
        self.assertGreater(found, 3)

    def test_an_outside_calendar_gets_the_one_day_for_a_card_named_for_a_start(self):
        e = {"title": "マリー・アントワネット・スタイル(横浜美術館) 開幕", "date": "2026-08-01", "date_end": "2026-11-23"}
        self.assertEqual(build.calendar_last_day(e), date(2026, 8, 1))
        e2 = {"title": "洞爺湖ロングラン花火大会", "date": "2026-04-28", "date_end": "2026-10-31"}
        self.assertEqual(build.calendar_last_day(e2), date(2026, 10, 31))
        self.assertEqual(build.calendar_last_day({"title": "x", "date": "2026-08-01"}), date(2026, 8, 1))
        url = build.google_calendar_url(e, "https://example.test/e/x/")
        self.assertIn("dates=20260801/20260802", url)

    def test_the_script_counts_the_same_way(self):
        js = (ROOT / "sites" / "atomou" / "assets" / "app.js").read_text(encoding="utf-8")
        for s in ("data-end", "(終了まで)", "(最終日)", "fillAsof", "C.iso(TODAY)"):
            self.assertIn(s, js, s)


class NoMembership(unittest.TestCase):
    WORDS = ("あともうメンバー", "先着300", "先着モニター", "先着30", "紹介コード", "無料プラン", "プラスプラン", "あと3回送ると", "書けるカード", "会員登録", "会員になる", "会員の方", "無料のあいだ")

    @classmethod
    def setUpClass(cls):
        cls.pages = build.build_pages(CFG, release=False, today=TODAY)

    def test_the_config_has_no_membership(self):
        for k in ("member_mail_from", "member_tiers", "member_ref_months", "plans"):
            self.assertNotIn(k, CFG, k)

    def test_no_receiver_and_no_terms_of_membership_are_built(self):
        self.assertNotIn("api/m.php", self.pages)
        self.assertNotIn("terms/index.html", self.pages)
        self.assertNotIn("/terms/", self.pages["index.html"])

    def test_no_page_speaks_of_it(self):
        for path, html in self.pages.items():
            if not (isinstance(html, str) and path.endswith(".html")):
                continue                      # the pages (the dormant code of the membership, SUBSCRIPTION_RESTORE.md, shows nothing without the config)
            if path.startswith("e/"):
                continue                      # the days' own words ("会員先行発売" and so on) are not the site's
            visible = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
            visible = visible.replace("当サイトは、会員登録などの機能を持ちません。", "")      # the privacy page says that it has none
            for w in self.WORDS:
                self.assertNotIn(w, visible, f"{path}: {w}")

    def test_the_page_config_carries_no_members_and_no_plans(self):
        home = self.pages["index.html"]
        self.assertNotIn('"members"', home)
        self.assertNotIn('"plans"', home)

    def test_the_privacy_page_says_what_is_taken_in_the_owners_words(self):
        privacy = self.pages["privacy/index.html"]
        self.assertIn("匿名で利用統計に利用させていただきます(件数のみ。個人は特定しません)", privacy)
        self.assertNotIn("会員登録", re.sub(r"当サイトは、会員登録などの機能を持ちません。", "", privacy))


if __name__ == "__main__":
    unittest.main()
