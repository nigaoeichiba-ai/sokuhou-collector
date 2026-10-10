"""atomou: the list of daily-updated media sites (data/atomou/media_sites.json) is complete, has no duplicates and keeps the news portals the owner ruled out out of it."""
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = json.loads((ROOT / "data" / "atomou" / "media_sites.json").read_text(encoding="utf-8"))


class MediaSites(unittest.TestCase):
    def test_one_hundred_sites_each_with_a_tier_and_a_reason(self):
        sites = DATA["sites"]
        self.assertGreaterEqual(len(sites), 100)
        hosts = set()
        for s in sites:
            self.assertIn(s["tier"], DATA["tiers"], s["name"])
            self.assertTrue(s["why"] and s["url"].startswith("https://") and s["groups"], s["name"])
            h = urlparse(s["url"]).netloc.lower().replace("www.", "")
            self.assertNotIn(h, hosts, s["name"])
            hosts.add(h)

    def test_no_portal_or_social_network_is_in_the_list(self):
        for s in DATA["sites"]:
            h = urlparse(s["url"]).netloc.lower()
            for bad in ("yahoo.", "twitter.", "x.com", "instagram.", "facebook.", "tiktok.", "youtube."):
                self.assertNotIn(bad, h, s["name"])

    def test_known_bans_stay_in_the_last_tier(self):
        by = {urlparse(s["url"]).netloc: s["tier"] for s in DATA["sites"]}
        self.assertEqual(by.get("prtimes.jp"), "C")                       # 『有償目的で…利用する行為』の禁止
        self.assertEqual(by.get("kyodonewsprwire.jp"), "C")


if __name__ == "__main__":
    unittest.main()
