"""Partner (A8.net) box (sites/minna/partners.py): nothing without a link, the programme's code exactly as given, never in a Rakuten box, no coupon words, an advertisement notice at the top."""
import re
import unittest
from unittest import mock

from sites.minna import build, partners
from tests.test_minna_sitecache import shared_site

BASE = {"site_url": "https://minna-no-illust.com", "site_name": "みんなのイラスト", "operator_name": "テスト", "contact_own": True}
IDS = {"rakuten_affiliate_id": "aaaa.bbbb.cccc.dddd", "rakuten_tracking_id": "minna", "amazon_tracking_id": "amazonmacs-22"}
SLUG = "nenga-tsukurikata"
CODE = ('<a href="https://px.a8.net/svt/ejp?a8mat=TEST+TEST+TEST+TEST" rel="nofollow">年賀状の注文はこちら</a>'
        '<img border="0" width="1" height="1" src="https://www16.a8.net/0.gif?a8mat=TEST+TEST+TEST+TEST" alt="">')
REAL = ('<a href="https://px.a8.net/svt/ejp?a8mat=4BGH3G+CRMRNE+33J0+15UCEA" rel="nofollow">喪中・年賀状印刷は年賀状スクウェアで</a>\n'
        '<img border="0" width="1" height="1" src="https://www17.a8.net/0.gif?a8mat=4BGH3G+CRMRNE+33J0+15UCEA" alt="">')
WITH = {SLUG: {"heading": "年賀状の印刷サービスの例", "html": CODE}}


def page(links):
    _items, series = build.load_data()
    g = next(x for x in build.load_guides() if x["slug"] == SLUG)
    with mock.patch.dict(partners.LINKS, links, clear=True):
        return build.guide_page({**BASE, **IDS}, False, g, series)


class PartnerBox(unittest.TestCase):
    def test_no_link_no_frame_no_mark_no_notice(self):
        for links in ({}, {SLUG: {"heading": "x", "html": ""}}, {SLUG: {"heading": "x", "html": "  \n "}}):
            with mock.patch.dict(partners.LINKS, links, clear=True):
                self.assertEqual(partners.box(SLUG), "")
                self.assertEqual(partners.top_notice(SLUG), "")
            html = page(links)
            for word in ("pr-partner", "pr-top", "a8.net"):
                self.assertNotIn(word, html, word)

    def test_the_data_file_holds_only_empty_entries_or_a8_code(self):
        """Until the programme gives the code the entry is empty (nothing is shown); when it does, it is pasted as given, so it is an A8.net link."""
        self.assertIn(SLUG, partners.LINKS)
        for slug, e in partners.LINKS.items():
            html = e["html"].strip()
            self.assertTrue(html == "" or ("a8.net" in html and html.startswith("<a ")), slug)

    def test_the_code_is_on_the_page_exactly_as_given(self):
        """AFFILIATE_RULES.md 3b: nothing added, nothing taken away: the page holds the provided string, byte for byte, and its tags carry no extra attribute."""
        html = page(WITH)
        self.assertIn(CODE, html)
        self.assertEqual(html.count(CODE), 1)
        self.assertEqual(re.findall(r"<a [^>]*a8\.net[^>]*>", html), ['<a href="https://px.a8.net/svt/ejp?a8mat=TEST+TEST+TEST+TEST" rel="nofollow">'])
        self.assertEqual(re.findall(r"<img [^>]*a8\.net[^>]*>", html), ['<img border="0" width="1" height="1" src="https://www16.a8.net/0.gif?a8mat=TEST+TEST+TEST+TEST" alt="">'])

    def test_the_partner_box_is_its_own_box_apart_from_the_rakuten_box(self):
        html = page(WITH)
        boxes = re.findall(r'<aside class="pr-box[^"]*">.*?</aside>', html, re.S)
        self.assertEqual(len(boxes), 2)
        partner = next(b for b in boxes if "pr-partner" in b)
        rakuten = next(b for b in boxes if "pr-partner" not in b)
        self.assertNotIn("rakuten", partner.lower().replace("楽天", ""))
        self.assertNotIn("a8.net", rakuten)
        self.assertIn("広告(A8.net)", partner)
        self.assertIn('class="pr-note">PR<', partner)
        self.assertNotIn("amazon", partner.lower())

    def test_the_box_sits_right_after_its_section_and_the_notice_is_in_the_first_view(self):
        html = page(WITH)
        h2 = html.index("自分で刷るか、印刷サービスに頼むか")
        sec_end = html.index("</section>", h2)
        self.assertEqual(html.index('<aside class="pr-box pr-partner">'), sec_end + len("</section>"))
        self.assertTrue(html.index("<h1") < html.index('class="pr-top"') < html.index("<h2"))

    def test_the_words_around_the_code_follow_the_programme_rules(self):
        """No coupons in our text; no programme name words in the heading (search advertising rule); one partner per page."""
        for slug, e in partners.LINKS.items():
            self.assertNotRegex(e["heading"], r"クーポン|割引券|ネットスクウェア|年賀状スクエア|スクエア|スクウェア|しまうま", slug)
        html = page(WITH)
        partner = re.search(r'<aside class="pr-box pr-partner">.*?</aside>', html, re.S).group(0)
        self.assertNotIn("クーポン", re.sub(r"<[^>]+>", "", partner))
        with mock.patch.dict(partners.LINKS, WITH, clear=True):
            self.assertNotIn("クーポン", partners.top_notice(SLUG))
        self.assertEqual(html.count('class="pr-box pr-partner"'), 1)

    def test_the_provided_code_is_in_the_data_file_exactly(self):
        """2026-11-09: the code the owner copied from A8.net (programme 年賀状スクウェア), pasted without a changed character."""
        self.assertEqual(partners.LINKS[SLUG]["html"], REAL)

    def test_the_built_page_holds_it_once_with_the_PR_mark_before_the_link(self):
        _items, series = build.load_data()
        g = next(x for x in build.load_guides() if x["slug"] == SLUG)
        html = build.guide_page({**BASE, **IDS}, False, g, series)
        self.assertEqual(html.count(REAL), 1)
        box = html.index('<aside class="pr-box pr-partner">')
        self.assertTrue(box < html.index('class="pr-note">PR<', box) < html.index("px.a8.net", box))
        self.assertTrue(html.index('class="pr-top"') < html.index("px.a8.net"))

    def test_no_other_page_of_the_site_has_an_a8_link(self):
        out, _ = shared_site()
        found = sorted(p.relative_to(out).as_posix() for p in out.rglob("*.html") if "px.a8.net" in p.read_text(encoding="utf-8"))
        self.assertEqual(found, ["guide/mochu-hagaki/index.html", "guide/nenga-tsukurikata/index.html", "guide/nenmatsu-junbi-calendar/index.html"])      # 2026-11-13: the same programme on two more pages about printing the cards

    def test_no_price_or_discount_claim_around_the_link_and_no_programme_name_in_the_head(self):
        _items, series = build.load_data()
        g = next(x for x in build.load_guides() if x["slug"] == SLUG)
        html = build.guide_page({**BASE, **IDS}, False, g, series)
        ours = re.search(r'<aside class="pr-box pr-partner">.*?</aside>', html, re.S).group(0).replace(REAL, "") + partners.top_notice(SLUG)
        self.assertNotRegex(re.sub(r"<[^>]+>", "", ours), r"クーポン|割引|送料無料|OFF|円引|最安|無料で")
        head = re.sub(r"\s+", " ", re.search(r"<head>.*?</head>", html, re.S).group(0)) + re.search(r"<h1>.*?</h1>", html).group(0)
        self.assertNotRegex(head, r"ネットスクウェア|ネットスクエア|年賀状スクエア|年賀状スクウェア|スクエア|スクウェア")

    def test_every_marked_section_has_an_entry(self):
        for g in build.load_guides():
            for sec in g["sections"]:
                if sec.get("partner"):
                    self.assertIn(g["slug"], partners.LINKS)


if __name__ == "__main__":
    unittest.main()
