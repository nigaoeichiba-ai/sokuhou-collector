"""sale-calendar.com: every entry of a shop with an affiliate programme (or a store in an affiliated mall) carries its affiliate link (owner 2026-11-12: "貼れるものは全部貼る").

Pinned here: a shop of the calendar is either linked (a mall, an ASP programme of ours, a store in a mall) or listed in NO_LINK with the reason; every entry of a linked shop has its link(s) in the page
(a missing one fails, with a negative test); a link has the PR mark, target=_blank and rel="nofollow sponsored noopener"; each mall's link is on its own line; the forms of the programmes are the ones given
(Rakuten hgc, Amazon tag only, ValueCommerce MyLink with the counter, A8.net text link with the pixel); nothing of a mall's catalogue (price, image, rank) and no ranking words."""
from __future__ import annotations

import os
import re
import unittest

os.environ.setdefault("KAIDOKI_TODAY", "2026-11-12")

from sites.kaidoki.redesign import affiliate as AFF  # noqa: E402
from sites.kaidoki.redesign import schedule as S  # noqa: E402
from tests.test_kaidoki_redesign import build  # noqa: E402

SPONSORED = re.compile(r'<a href="[^"]+" target="_blank" rel="nofollow sponsored noopener">.*?</a>', re.S)
LINKED = set(AFF.MALLS) | set(AFF.ASP) | set(AFF.STORES)


def uncovered(items, render=S.item_li) -> list[str]:
    """The entries that should carry a link and whose rendered html has fewer sponsored anchors than links."""
    bad = []
    for it in items:
        want = len(AFF.links_for(it)) if it["mall"] in LINKED else 0
        if len(SPONSORED.findall(render(it))) < want:
            bad.append(it["id"])
    return bad


class CoverageTest(unittest.TestCase):
    items = S.all_items()

    def test_every_shop_is_linked_or_has_a_reason(self):
        self.assertEqual(set(S.ENT), LINKED | set(AFF.NO_LINK))
        self.assertFalse(LINKED & set(AFF.NO_LINK))
        for sid, why in AFF.NO_LINK.items():
            self.assertTrue(why, sid)

    def test_every_entry_of_a_linked_shop_has_a_link_and_the_others_have_none(self):
        for it in self.items:
            links = AFF.links_for(it)
            if it["mall"] in LINKED:
                self.assertTrue(links, it["id"])
            else:
                self.assertEqual(links, [], it["id"])

    def test_the_rendered_entry_carries_every_link(self):
        self.assertEqual(uncovered(self.items), [])

    def test_negative_a_missing_link_is_caught(self):
        self.assertEqual(uncovered(self.items, lambda it: SPONSORED.sub("", S.item_li(it))), sorted({i["id"] for i in self.items if i["mall"] in LINKED}, key=[x["id"] for x in self.items].index))
        # a linked shop whose links were dropped from the table is found by the coverage rule of test_every_entry_of_a_linked_shop_has_a_link_and_the_others_have_none
        saved = AFF.STORES["nitori"]
        AFF.STORES["nitori"] = []
        try:
            self.assertEqual([i["id"] for i in self.items if i["mall"] in LINKED and not AFF.links_for(i)], ["c-nitori-bf"])
        finally:
            AFF.STORES["nitori"] = saved

    def test_the_built_pages_carry_the_links_of_every_entry(self):
        pages = build({"KAIDOKI_REDESIGN": "1"}, products=[])
        cal = pages["calendar/index.html"]
        segs = cal.split('<li class="cal-item')
        for it in self.items:
            links = AFF.links_for(it)
            if not links or it["kind"] == "regular":
                continue
            mine = [sg for sg in segs if f'>{S.e(it["title"])}<' in sg or f'>{S.e(it["title"])}</a>' in sg]
            self.assertTrue(mine, it["id"])
            self.assertTrue(any(len(SPONSORED.findall(sg)) >= len(links) for sg in mine), it["id"])
        for rel in ("index.html", "calendar/rakuten/index.html", "calendar/amazon/index.html", "calendar/yahoo/index.html"):
            self.assertIn('class="aff-disclose"', pages[rel], rel)
            self.assertRegex(pages[rel], r"PR</span>「PR」の付いたリンクは広告です", rel)

    def test_the_forms_of_the_programmes(self):
        cfg = AFF.CFG
        for it in self.items:
            lines = AFF.links_for(it)
            for l in lines:
                self.assertTrue(l["label"] and not re.search(r"最安|おすすめ|ランキング|人気|お得|今すぐ|クリック|こちら", l["label"]), l)
                if l["kind"] == "rakuten":
                    self.assertTrue(l["href"].startswith(f"https://hb.afl.rakuten.co.jp/hgc/{cfg['rakuten_affiliate_id']}/?pc=https%3A%2F%2F"), l)
                    self.assertNotRegex(l["href"], r"amazon|yahoo|valuecommerce|a8\.net|&m=", l)
                elif l["kind"] == "amazon":
                    self.assertRegex(l["href"], r"^https://www\.amazon\.co\.jp/(?:[a-z/]+\?tag=|s\?k=[^&]+&tag=)" + cfg["amazon_tracking_id"] + "$")
                elif l["kind"] == "vc":
                    if AFF.ASP.get(it["mall"], ("",))[0] == "vctext":      # a VC text ad: its own landing page, no vc_url (the form the tool gave)
                        self.assertRegex(l["href"], r"^//ck\.jp\.ap\.valuecommerce\.com/servlet/referral\?sid=3787704&pid=\d+$")
                    else:
                        self.assertRegex(l["href"], r"^//ck\.jp\.ap\.valuecommerce\.com/servlet/referral\?sid=3787704&pid=\d+&vc_url=https%3A%2F%2F")
                    self.assertIn(AFF.VC_PID[l["key"]], l["href"])
                elif l["kind"] == "a8":
                    self.assertRegex(l["href"], r"^https://px\.a8\.net/svt/ejp\?a8mat=[0-9A-Z+]+$")
                else:
                    self.fail(l)
                html = AFF.anchor(l)
                self.assertIn('target="_blank" rel="nofollow sponsored noopener">', html)

    def test_every_a8_code_is_in_the_form_given_and_named(self):
        for key, (mat, host) in AFF.A8_MAT.items():
            self.assertRegex(mat, r"^[0-9A-Z]{6}\+[0-9A-Z]+\+[0-9A-Z]+\+[0-9A-Z]+$", key)
            self.assertRegex(host, r"^www\d+$", key)
            self.assertIn(key, AFF.ASP_NAME, key)
            self.assertIn(f"a8mat={mat}", AFF.a8_href(key))
            self.assertIn(f"a8mat={mat}", AFF.a8_pixel(key))
        # the approved shops with no dated sale yet (Alpen / Sports Depot, Oisix) are kept ready; once they are in ASP they must be linked (the coverage tests above then pin it)
        for key in ("alpen", "oisix"):
            self.assertTrue(key in AFF.ASP or key not in S.ENT, f"{key} is a shop of the calendar but has no link")

    def test_negative_a_shop_with_a_code_but_no_link_is_caught(self):
        saved = dict(S.ENT)
        S.ENT["alpen"] = ("スポーツデポ・アルペン", "ア", "brand")
        try:
            self.assertFalse("alpen" in AFF.ASP or "alpen" not in S.ENT)
        finally:
            S.ENT.clear()
            S.ENT.update(saved)

    def test_each_mall_link_is_on_its_own_line(self):
        for it in self.items:
            out = AFF.lines(AFF.links_for(it))
            for ln in re.findall(r'<p class="aff-line">(.*?)</p>', out):
                self.assertEqual(len(re.findall(r"<a href=", ln)), 1, it["id"])
                self.assertIn('<span class="pr-chip">PR</span>', ln)
        # a shop in several malls has one line per mall: Dyson (Rakuten, Yahoo!, Amazon)
        dy = [i for i in self.items if i["mall"] == "dyson"][0]
        self.assertEqual([l["kind"] for l in AFF.links_for(dy)], ["rakuten", "vc", "amazon"])

    def test_the_stores_are_the_shops_own_pages_of_a_mall(self):
        for sid, stores in AFF.STORES.items():
            for kind, target in stores:
                if kind == "rakuten":
                    self.assertRegex(target, r"^https://www\.rakuten\.co\.jp/[a-z0-9-]+/$", sid)
                elif kind == "yahoo":
                    self.assertRegex(target, r"^https://store\.shopping\.yahoo\.co\.jp/[a-z0-9-]+/$", sid)
                else:
                    self.assertEqual(kind, "amazon_s", sid)

    def test_no_link_for_a_shop_waiting_for_its_programme_or_without_one(self):
        for sid in ("sonystore", "lg", "uniqlo"):
            self.assertEqual([l for it in self.items if it["mall"] == sid for l in AFF.links_for(it)], [], sid)

    def test_stardomain_has_its_a8_link_now_that_the_programme_approved_it(self):
        links = [l for it in self.items if it["mall"] == "stardomain" for l in AFF.links_for(it)]
        self.assertTrue(links)
        self.assertTrue(all(l["kind"] == "a8" and "スタードメイン" in l["label"] and l["href"].startswith("https://px.a8.net/svt/ejp?a8mat=") for l in links))

    def test_nta_has_its_valuecommerce_link_to_its_own_campaign_page(self):
        links = [l for it in self.items if it["mall"] == "nta" for l in AFF.links_for(it)]
        self.assertTrue(links)
        for l in links:
            self.assertEqual(l["kind"], "vc")
            self.assertIn("sid=3787704&pid=892749530", l["href"])
            self.assertIn("vc_url=https%3A%2F%2Fwww.nta.co.jp%2F", l["href"])      # only the programme's own domain
            self.assertIn("日本旅行", l["label"])

    def test_jalan_has_its_valuecommerce_link_to_its_own_campaign_page(self):
        links = [l for it in self.items if it["mall"] == "jalan" for l in AFF.links_for(it)]
        self.assertTrue(links)
        for l in links:
            self.assertEqual(l["kind"], "vc")
            self.assertIn("sid=3787704&pid=892753320", l["href"])
            self.assertIn("vc_url=https%3A%2F%2Fwww.jalan.net%2F", l["href"])      # only the programme's own domain
            self.assertIn("じゃらんnet", l["label"])
            self.assertNotIn("http", l["label"])

    def test_yamada_has_its_rakuten_and_yahoo_stores(self):
        links = [l for it in self.items if it["mall"] == "yamada" for l in AFF.links_for(it)]
        self.assertGreaterEqual(len(links), 2)
        text = " ".join(str(l) for l in links)
        self.assertIn("yamada-denki", text)
        self.assertIn("hb.afl.rakuten.co.jp", text)
        self.assertIn("valuecommerce", text)
        self.assertTrue(all("ヤマダデンキ" in l["label"] and "ウェブコム" not in l["label"] for l in links))

    def test_randoseru_has_one_link_to_each_mall_with_the_pr_mark(self):
        from sites.kaidoki.redesign import render as R
        h = R.page_affiliate("/randoseru/")
        anchors = re.findall(r'<a [^>]*href="([^"]+)"[^>]*target="_blank"[^>]*rel="([^"]*)"[^>]*>([^<]*)', h)
        self.assertEqual(len(anchors), 3)
        for href, rel, text in anchors:
            self.assertEqual(rel, "nofollow sponsored noopener")
            self.assertNotIn("http", text)
            self.assertTrue(text.endswith("を見る"), text)
        self.assertIn("hb.afl.rakuten.co.jp", anchors[0][0])
        self.assertIn("tag=amazonmacs-22", anchors[1][0])
        self.assertIn("valuecommerce.com", anchors[2][0])
        self.assertEqual(h.count('class="pr-chip"'), 4)      # three lines + the disclosure sentence
        self.assertEqual(R.page_affiliate("/kaden/pc/"), "")

    def test_conditions_of_the_advertisers(self):
        text = " ".join(l["label"] for it in self.items for l in AFF.links_for(it))
        # オルビス: partnered at ValueCommerce (advertiser condition in the ASP ledger: no 「公式」「オフィシャル」, point back up to 20%); the name itself may be shown
        orb = [it for it in self.items if it["mall"] == "orbis"]
        self.assertTrue(orb)
        shown = " ".join(str(v) for it in orb for v in it.values()) + " " + " ".join(l["label"] for it in orb for l in AFF.links_for(it))
        bad = r"公式|オフィシャル|ポイント還元|[0-9]+%"
        self.assertNotRegex(shown, bad)
        for wrong in ("オルビス公式オンラインショップのページを見る", "オルビスオフィシャルサイト", "最大30%ポイント還元"):      # the check does catch the words
            self.assertRegex(wrong, bad)
        from sites.kaidoki.redesign import schedule as _S      # the segment name shown on the Orbis row must not carry 「公式」 either
        self.assertNotRegex(_S.SEGMENTS[_S.ENT["orbis"][2]], bad)
        self.assertNotRegex(text, r"クーポン|ポイントバック|還元")      # DHC: no coupon is introduced; only the dates stand on the page


NAMED = (("index.html", "スタードメイン"), ("fashion/sale-coupons/index.html", "ZOZOTOWN"), ("food/lohaco-food/index.html", "ベルーナ"), ("hobby/mall-hobby/index.html", "アルペン"))
ANCHOR = re.compile(r'<a [^>]*href="([^"]+)"[^>]*rel="([^"]*)"[^>]*>([^<]*)', re.S)


def unlinked_names(pages: dict) -> list[str]:
    """The (page, advertiser) pairs where the page names an affiliated advertiser and no sponsored affiliate anchor carries that name (2026-11-16 audit: four such pairs)."""
    bad = []
    for path, name in NAMED:
        html = pages[path]
        links = [(h, t) for h, rel, t in ANCHOR.findall(html) if "sponsored" in rel and re.search(r"a8\.net|valuecommerce|hb\.afl\.rakuten|tag=", h)]
        if name in html and not any(name in t for _, t in links):
            bad.append(f"{path}: {name}")
    return bad


class NamedAdvertiserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = build({"KAIDOKI_REDESIGN": "1"})

    def test_every_named_affiliated_advertiser_has_its_link_with_its_name(self):
        self.assertEqual(unlinked_names(self.pages), [])

    def test_negative_a_page_with_the_name_only_is_caught(self):
        for path, name in NAMED:
            stripped = {**self.pages, path: re.sub(r"<a [^>]*>[^<]*" + name + r"[^<]*(?:<img[^>]*>)?</a>(?:<img[^>]*>)?", name, self.pages[path])}
            self.assertEqual(unlinked_names(stripped), [f"{path}: {name}"], path)


if __name__ == "__main__":
    unittest.main()
