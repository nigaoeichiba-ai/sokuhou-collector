"""SEO sweep of 2026-10-20: the searched words in two titles, and a second inbound link for pages that had one (themes, reading articles, deep-read products)."""
import collections
import unittest

from sites.yorokobu import build, content, features


class TitlesTest(unittest.TestCase):
    c = content.load()

    def test_the_consumables_theme_carries_the_searched_word(self):
        t = next(x for x in self.c["themes"] if x["slug"] == "consumables")
        self.assertIn("消え物ギフト", t["title"])
        self.assertIn("消え物ギフト", t["lead"])
        self.assertLessEqual(len(t["title"]), 40)

    def test_the_travel_article_says_present_in_title_and_lead(self):
        a = next(x for x in self.c["articles"] if x["slug"] == "gift-for-people-on-the-move")
        self.assertIn("プレゼント", a["title"])
        self.assertIn("プレゼント", a["lead"])
        self.assertTrue(a["title"].startswith("移動が多い人へのプレゼント"))


class InternalLinksTest(unittest.TestCase):
    c = content.load()

    def test_every_theme_is_linked_from_ten_others_of_its_group(self):
        live = list(self.c["themes"])
        inbound = collections.Counter()
        for t in live:
            for x in build.theme_neighbours(live, t):
                inbound[x["slug"]] += 1
        groups = collections.Counter(t["group"] for t in live)
        for t in live:
            want = min(10, groups[t["group"]] - 1)
            self.assertGreaterEqual(inbound[t["slug"]], want, t["slug"])

    def test_a_neighbour_list_never_holds_the_theme_itself_and_stays_in_the_group(self):
        live = list(self.c["themes"])
        for t in live:
            ns = build.theme_neighbours(live, t)
            self.assertNotIn(t["slug"], [x["slug"] for x in ns])
            self.assertTrue(all(x["group"] == t["group"] for x in ns))
            self.assertEqual(len({x["slug"] for x in ns}), len(ns))

    def test_the_old_first_ten_rule_would_be_caught(self):                    # negative: the first ten of the group linked from everyone leaves the rest with no link
        live = list(self.c["themes"])
        big = collections.Counter(t["group"] for t in live).most_common(1)[0][0]
        group = [t for t in live if t["group"] == big]
        self.assertGreater(len(group), 11)
        first_ten = {x["slug"] for x in group[:10]}
        old = collections.Counter(x["slug"] for t in group for x in [y for y in group if y["slug"] != t["slug"]][:10])
        self.assertTrue(any(old[t["slug"]] == 0 for t in group if t["slug"] not in first_ten))
        new = collections.Counter(x["slug"] for t in group for x in build.theme_neighbours(live, t))
        self.assertTrue(all(new[t["slug"]] >= 1 for t in group))

    def test_a_theme_lists_the_articles_that_name_it(self):
        a = next(x for x in self.c["articles"] if x["themes"])
        slug = a["themes"][0]
        t = next(x for x in self.c["themes"] if x["slug"] == slug)
        html = build.theme_reads(self.c, t)
        self.assertIn(f'href="/read/{a["slug"]}/"', html)
        self.assertIn("この気持ちの読みもの", html)
        self.assertEqual(build.theme_reads(self.c, {"slug": "no-such-theme"}), "")

    def test_every_article_is_named_by_at_least_one_theme_page(self):
        by_theme = collections.Counter()
        for a in self.c["articles"]:
            for s in a.get("themes") or []:
                by_theme[s] += 1
        live = {t["slug"] for t in self.c["themes"]}
        orphans = [a["slug"] for a in self.c["articles"] if not any(s in live for s in (a.get("themes") or []))]
        self.assertEqual(orphans, [])

    def test_the_picks_hub_lists_every_deep_read_product_not_only_the_newest_four(self):
        feats = [{"slug": f"f{i}", "title": f"記事{i}", "catch": "x", "date": "2026-10-1%d" % (i % 10)} for i in range(9)]
        html = features.teaser({"site_url": "x"}, {}, feats, None, 60)
        for f in feats:
            self.assertIn(f'/pick/{f["slug"]}/', html)
        self.assertNotIn("/pick/f8/", features.teaser({"site_url": "x"}, {}, feats, None, 4))     # (the old limit: why the older ones had one link)


if __name__ == "__main__":
    unittest.main()
