"""A picture of 七五三 or 千歳飴 links to the 七五三 special and guide, even when it sits in a general event set."""
import unittest

from sites.minna import build


class ShichigosanLinkTest(unittest.TestCase):
    def test_a_shichigosan_picture_links_to_the_special_and_the_guide(self):
        line = build.shichigosan_line({"title": "千歳飴を持つ子", "tags": ["七五三", "和風"]})
        self.assertIn('href="/special/shichigosan/"', line)
        self.assertIn('href="/guide/shichigosan-guide/"', line)

    def test_the_tag_alone_is_enough(self):
        self.assertIn("/special/shichigosan/", build.shichigosan_line({"title": "着物の子", "tags": ["七五三"]}))

    def test_other_pictures_get_no_line(self):
        self.assertEqual(build.shichigosan_line({"title": "どんぐり", "tags": ["秋"]}), "")


if __name__ == "__main__":
    unittest.main()
