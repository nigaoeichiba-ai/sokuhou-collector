"""2026-10-25: the deep-read article for r8 of the day was started on a product that had an article since 10/18 (bodum-pavina-glass) and was stopped after the draft, the pictures and
the review.  The candidates now know which products are covered, and the build refuses two articles about one product."""
import unittest

from sites.yorokobu import features, pickresearch
from sokuhou.sitekit import BuildError


def day(date, rcodes=(), asins=()):
    return {"date": date, "rakuten": [{"code": c} for c in rcodes], "amazon": [{"asin": a} for a in asins]}


DAYS = [day("2026-10-25", ["s:8", "s:9"], ["B0AAAA"]), day("2026-10-18", ["s:1", "s:2", "s:3"], ["B0BBBB"])]
FEATS = [{"slug": "pavina", "date": "2026-10-18", "ref": "r3"}, {"slug": "bag", "date": "2026-10-18", "ref": "a1"}]


class FeaturedTest(unittest.TestCase):
    def test_the_codes_and_asins_of_the_existing_articles(self):
        self.assertEqual(features.featured_codes(FEATS, DAYS), {"s:3": "pavina", "B0BBBB": "bag"})

    def test_a_feature_of_a_day_that_has_no_file_is_skipped_not_a_crash(self):
        self.assertEqual(features.featured_codes([{"slug": "x", "date": "2020-01-01", "ref": "r1"}], DAYS), {})

    def test_two_articles_about_one_product_are_reported(self):
        later = [{"slug": "pavina", "date": "2026-10-18", "ref": "r3"}]
        days = [day("2026-10-25", ["s:3"]), *DAYS[1:]]            # the same item code picked again a week later
        dup = later + [{"slug": "pavina-2", "date": "2026-10-25", "ref": "r1"}]
        msg = features.duplicate_features(dup, days)
        self.assertEqual(len(msg), 1)
        self.assertIn("pavina-2", msg[0])
        self.assertEqual(features.duplicate_features(FEATS, DAYS), [])

    def test_the_build_stops_on_two_articles_about_one_product(self):
        days = [day("2026-10-25", ["s:3"]), *DAYS[1:]]
        feats = [{"slug": "pavina", "date": "2026-10-18", "ref": "r3"}, {"slug": "pavina-2", "date": "2026-10-25", "ref": "r1"}]
        with self.assertRaises(BuildError):
            features.build_pages({"c": {"features": feats, "daily": days}}, {}, False)

    def test_the_real_articles_are_one_per_product(self):
        self.assertEqual(features.duplicate_features(pickresearch._features(), pickresearch.dp.load_days()), [])

    def test_the_list_for_the_next_article_marks_the_products_that_have_one(self):
        rows = pickresearch.featurable("2026-10-25")
        self.assertTrue(rows)
        marks = {ref: mark for ref, key, mark in rows}
        done = features.featured_codes(pickresearch._features(), pickresearch.dp.load_days())
        for ref, key, mark in rows:
            self.assertEqual(bool(mark), key in done, ref)


if __name__ == "__main__":
    unittest.main()
