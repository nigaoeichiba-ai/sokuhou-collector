"""みんなのイラスト: the hubs by purpose, the tools hub and the print makers (the page markup; the drawing itself is checked in test_minna_e2e)."""
import unittest

from sites.minna import build, specials, usehubs

CFG = {"site_url": "https://minna-no-illust.com", "site_name": "みんなのイラスト"}


def fake_series(n=5):
    out = []
    for k in range(n):
        item = {"id": f"s{k}-a", "title": f"絵{k}", "tags": ["チラシ", "お店"] if k < 4 else ["山"], "w": 360, "h": 360, "genre": "life", "touch": "flat", "series": f"s{k}", "added": "2026-10-01", "file": "a.webp"}
        out.append({"slug": f"s{k}", "title": "チラシの人物" if k == 0 else f"セット{k}", "subject": "", "lead": "お店のポップに使えます。" if k < 2 else "山の景色。", "items": [item],
                    "legacy": False, "touch": "flat", "genre": "life", "added": "2026-10-01", "url": f"/series/s{k}/"})
    return out


class Hubs(unittest.TestCase):
    def test_rank_series_prefers_title_and_lead_over_tags_and_skips_unrelated(self):
        ranked = usehubs.rank_series(["チラシ", "お店"], fake_series(), 10)
        self.assertEqual(ranked[0]["slug"], "s0")                      # the word is in the title and the lead
        self.assertNotIn("s4", [s["slug"] for s in ranked])             # only a mountain: not a flyer picture
        self.assertEqual(len(usehubs.rank_series(["チラシ"], fake_series(), 2)), 2)

    def test_every_hub_points_at_things_that_exist(self):
        slugs = {s["slug"] for s in specials.SPECIALS}
        tools = {u for u, _n, _d in build.TOOLS}
        seen = set()
        for h in usehubs.HUBS:
            self.assertNotIn(h["slug"], seen)
            seen.add(h["slug"])
            self.assertTrue(set(h["specials"]) <= slugs, h["slug"])
            self.assertTrue(set(h["tools"]) <= tools, h["slug"])
            self.assertGreaterEqual(len(h["words"]), 5)
            self.assertTrue(h["intro"] and h["points"])
            for text in [h["name"], h["short"], *h["intro"], *(t for p in h["points"] for t in p)]:
                self.assertNotRegex(text, r"AI|生成")                  # the site's own copy does not stress how the pictures are made (docs/MINNA_COPY_STYLE.md)

    def test_use_pages_are_built_with_sets_points_and_links(self):
        built = [(sp, [], []) for sp in specials.SPECIALS]
        files, live = build.use_pages(CFG, True, fake_series(), built, [])
        self.assertIn("use/index.html", files)
        self.assertTrue(live)
        hub = files[f"use/{live[0]['slug']}/index.html"]
        self.assertIn("<h1>", hub)
        self.assertIn("使うときのポイント", hub)
        self.assertIn('class="set-grid"' if 'class="set-grid"' in build.set_grid(fake_series()[:1]) else "/series/", hub)
        self.assertIn('href="/use/"', files["use/index.html"] + hub)

    def test_a_hub_with_fewer_than_three_sets_is_left_out(self):
        files, live = build.use_pages(CFG, True, fake_series(2), [], [])
        self.assertEqual(live, [])
        self.assertEqual(set(files), {"use/index.html"})


class SetSpecificText(unittest.TestCase):
    def test_series_use_is_the_use_sentence_of_the_lead(self):
        self.assertEqual(build.series_use({"lead": "水彩風の素材です。体操教室の案内に使えます。"}), "体操教室の案内に使えます。")
        self.assertEqual(build.series_use({"lead": "ひとことだけ。"}), "")
        self.assertEqual(build.series_use({"lead": "素材です。色が違います。"}), "")      # no 使え: not a use sentence

    def test_picture_page_names_its_set_and_what_it_is_for(self):
        items, series = build.load_data()
        s = next(x for x in series if not x["legacy"] and build.series_use(x))
        it = s["items"][0]
        html = build.illust_page({**CFG, "operator_name": "テスト"}, True, it, items, series)
        self.assertIn(build.series_use(s), html)
        self.assertIn("このセット:", html)
        self.assertIn(f"{len(s['items'])}点のうちの1点です", html)

    def test_pose_hub_lists_every_pose_set_and_the_sets_link_back(self):
        items, series = build.load_data()
        html, sets = build.pose_page(CFG, True, series)
        self.assertGreaterEqual(len(sets), 10)
        for s in sets:
            self.assertIn(f'href="{s["url"]}"', html)
            self.assertIn("ポーズ", s["title"])
        self.assertIn('href="/pose/"', build.series_page(CFG, True, sets[0], items, series, og=False))
        plain = next(x for x in series if not build.is_pose_set(x))
        self.assertNotIn('href="/pose/"', build.series_page(CFG, True, plain, items, series, og=False))


class Makers(unittest.TestCase):
    def test_nav_has_the_hub_and_the_tools(self):
        hrefs = [n[1] for n in build.BASE_NAV]
        self.assertIn("/use/", hrefs)
        self.assertIn("/tool/", hrefs)
        prefixes = [n[2] for n in build.BASE_NAV]
        self.assertEqual(len(prefixes), len(set(prefixes)))             # no two entries light up on the same page

    def test_maker_pages_load_their_script_and_keep_input_on_the_device(self):
        for kind, path in (("calendar", "/tool/calendar/"), ("nametag", "/tool/nametag/")):
            html = build.maker_page(CFG, True, kind)
            self.assertIn('<script src="/assets/maker.js" defer></script>', html)
            self.assertIn(f'data-kind="{kind}"', html)
            self.assertIn('id="mk-canvas"', html)
            self.assertIn("FAQPage", html)
            self.assertIn(f'rel="canonical" href="https://minna-no-illust.com{path}"', html)
            self.assertNotIn("<form id=\"mk-opts\" class=\"mk-opts\" action", html)        # nothing is submitted anywhere

    def test_tools_page_lists_every_tool(self):
        html = build.tools_page(CFG, True)
        for u, _n, _d in build.TOOLS:
            self.assertIn(f'href="{u}"', html)

    def test_the_helper_knows_the_new_pages(self):
        data = build.assist_data([], [], 2027, {}, [{"slug": "flyer", "name": "チラシ", "words": ["チラシ", "ポスター"]}])
        urls = [p["u"] for p in data["pages"]]
        for u in ("/tool/", "/tool/calendar/", "/tool/nametag/", "/use/flyer/"):
            self.assertIn(u, urls)
        faq_text = " ".join(" ".join(f["k"]) for f in data["faq"])
        self.assertIn("名札", faq_text)
        self.assertIn("カレンダーを作", faq_text)


if __name__ == "__main__":
    unittest.main()
