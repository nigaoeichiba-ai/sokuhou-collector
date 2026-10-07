import json
import unittest
from pathlib import Path

from sites.minna import indexnow

CFG = {"site_url": "https://minna-no-illust.com", "indexnow_key": "0123456789abcdef0123456789abcdef"}


class IndexNowTest(unittest.TestCase):
    def test_payload_names_the_key_file_on_the_same_host(self):
        p = indexnow.payload(CFG, ["https://minna-no-illust.com/", "https://minna-no-illust.com/series/sheep-pose/"])
        self.assertEqual(p["host"], "minna-no-illust.com")
        self.assertEqual(p["keyLocation"], "https://minna-no-illust.com/0123456789abcdef0123456789abcdef.txt")
        self.assertEqual(len(p["urlList"]), 2)

    def test_foreign_urls_and_bad_keys_are_refused(self):
        with self.assertRaises(ValueError):
            indexnow.payload(CFG, ["https://example.com/x/"])
        with self.assertRaises(ValueError):
            indexnow.payload({**CFG, "indexnow_key": "short"}, [])

    def test_the_real_config_has_a_valid_key_and_the_build_publishes_it(self):
        cfg = json.loads((Path(indexnow.__file__).parent / "config.json").read_text(encoding="utf-8"))
        indexnow.payload(cfg, [])
        from sites.minna import build
        src = Path(build.__file__).read_text(encoding="utf-8")
        self.assertIn("indexnow_key", src)


if __name__ == "__main__":
    unittest.main()
