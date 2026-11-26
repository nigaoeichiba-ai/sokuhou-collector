"""Sets used together (the year-end greetings) link to each other from their set pages."""
import unittest

from sites.minna import build as B


def _set(slug):
    return {"slug": slug, "title": slug, "url": f"/series/{slug}/", "touch": "flat", "items": []}


class FamilyBoxTest(unittest.TestCase):
    series = [_set(s) for s in ("oseibo-reijo-wa", "nenga-jimai-flat", "nenga-frames-wa", "cats-flat")]

    def test_a_member_links_to_the_other_members_and_not_to_itself(self):
        html = B.family_box(self.series[0], self.series)
        self.assertIn('href="/series/nenga-jimai-flat/"', html)
        self.assertIn('href="/series/nenga-frames-wa/"', html)
        self.assertNotIn('href="/series/oseibo-reijo-wa/"', html)
        self.assertNotIn('href="/series/cats-flat/"', html)

    def test_a_set_outside_every_family_and_a_lonely_member_get_no_block(self):
        self.assertEqual(B.family_box(self.series[3], self.series), "")
        self.assertEqual(B.family_box(self.series[0], [self.series[0], self.series[3]]), "")


if __name__ == "__main__":
    unittest.main()
