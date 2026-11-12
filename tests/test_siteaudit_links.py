"""Affiliate links in natural places and no link whose visible text is a URL (owner, 2026-11-13).

kuma: the equipment guides (prepare, spray, home) carry a Rakuten row and an Amazon row per tool, each with a PR mark, rel="nofollow sponsored noopener" and target="_blank";
the guides about meeting a bear and reading the data carry none.  minna: the printing guides have a Rakuten box (and the A8 partner box where the code is held).
saichin: the monthly-pay guide has the A8 job link next to the PR notice.  A link text that is itself a URL is found by url_text_links (negative cases below).
"""
import re
import unittest

from sites.kuma import build as kuma_build
from sites.kuma import content as kuma_content

URL_TEXT = re.compile(r"^(https?://|www\.)\S+$|^[\w-]+(\.[\w-]+)*\.(com|jp|net|org)(/\S*)?$")


def url_text_links(html: str) -> list[str]:
    out = []
    for m in re.finditer(r"<a\b[^>]*href=[^>]*>(.*?)</a>", html, re.S):
        text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if URL_TEXT.match(text):
            out.append(text)
    return out


CFG = {"site_url": "https://kuma-sokuho.com", "site_name": "クマ出没速報", "operator_name": "テスト運営", "contact_form_url": "https://forms.example.com/x",
       "contact_email": None, "adsense_pub_id": None, "rakuten_affiliate_id": "aaaa.bbbb.cccc.dddd", "amazon_tracking_id": "amazonmacs-22"}


class UrlTextTest(unittest.TestCase):
    def test_detects_a_link_whose_text_is_a_url(self):
        self.assertEqual(url_text_links('<a href="/x/">https://kuma-sokuho.com/live/akita/</a>'), ["https://kuma-sokuho.com/live/akita/"])
        self.assertEqual(url_text_links('<a href="/x/"><b>example.com</b></a>'), ["example.com"])

    def test_words_and_mixed_text_pass(self):
        self.assertEqual(url_text_links('<a href="/x/">秋田県のページ</a> <a href="/y/">「ママワークス」<b>mamaworks.jp</b></a>'), [])


class KumaGuideBoxTest(unittest.TestCase):
    def guide(self, slug):
        g = next(x for x in kuma_content.GUIDES if x["slug"] == slug)
        return kuma_build.guide_page(g, CFG, False)

    def test_equipment_guides_have_both_stores_in_separate_lists_with_pr_and_rel(self):
        for slug in kuma_build.GUIDE_GOODS_SLUGS:
            html = self.guide(slug)
            box = html.split('<aside class="pr-guide-box">', 1)[1].split("</aside>", 1)[0]
            rk = re.findall(r'<a href="https://hb\.afl\.rakuten\.co\.jp/hgc/aaaa\.bbbb\.cccc\.dddd/\?pc=[^"]+" target="_blank" rel="nofollow sponsored noopener"><span class="pr-note">PR</span>[^<]+</a>', box)
            am = re.findall(r'<a href="https://www\.amazon\.co\.jp/s\?k=[^"]+&amp;tag=amazonmacs-22" target="_blank" rel="nofollow sponsored noopener"><span class="pr-note">PR</span>[^<]+</a>', box)
            self.assertTrue(rk and am, slug)
            self.assertEqual(len(rk), box.count("hb.afl.rakuten"), slug)
            self.assertEqual(len(am), box.count("amazon.co.jp/s?k"), slug)
            self.assertNotIn("rakuten", "".join(am))
            self.assertEqual(url_text_links(html), [], slug)

    def test_a_guide_about_meeting_a_bear_or_reading_data_has_no_box(self):
        for slug in ("encounter", "data"):
            self.assertNotIn("pr-guide-box", self.guide(slug), slug)

    def test_no_box_without_ids(self):
        g = next(x for x in kuma_content.GUIDES if x["slug"] == "prepare")
        html = kuma_build.guide_page(g, {k: v for k, v in CFG.items() if "affiliate" not in k and "tracking" not in k}, False)
        self.assertNotIn("pr-guide-box", html)


class MinnaPrintGuidesTest(unittest.TestCase):
    def test_printing_guides_have_a_rakuten_box(self):
        from sites.minna import build
        for slug in ("mochu-hagaki", "nenmatsu-junbi-calendar", "hagaki-size-ichiran", "bounenkai-annai"):
            self.assertIn(slug, build.GUIDE_PR, slug)

    def test_use_hub_boxes_are_for_hubs_that_exist_and_hold_things_only(self):
        from sites.minna import build, usehubs
        self.assertTrue(set(build.USE_PR) <= {h["slug"] for h in usehubs.HUBS})
        for heading, rows in build.USE_PR.values():
            for label, kw in rows:
                self.assertNotRegex(label, r"サービス|の印刷$|切手")
                self.assertNotIn("印刷", kw)


if __name__ == "__main__":
    unittest.main()
