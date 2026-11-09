"""Privacy page wording of みんなのイラスト (2026-11-09): AdSense is in use, A8.net is named, the Amazon sentence is gone while there are no Amazon links; other sites keep their text."""
import unittest

from sokuhou import sitekit
from sites.minna import build

SITE = {"source_html": "x", "nav": [], "css": "/assets/style.css"}


class PrivacyWording(unittest.TestCase):
    def test_the_default_text_is_unchanged_for_a_site_that_sets_nothing(self):
        import json
        from pathlib import Path
        self.assertNotIn("privacy_adsense_in_use", json.loads((Path(sitekit.__file__).parent.parent / "sites" / "kuma" / "config.json").read_text(encoding="utf-8")))
        src = Path(sitekit.__file__).read_text(encoding="utf-8")
        self.assertIn('"利用する場合があります"', src)

    def test_minna_says_it_uses_adsense_and_names_a8_and_has_no_amazon_sentence(self):
        import json
        from pathlib import Path
        cfg = json.loads((Path(build.__file__).parent / "config.json").read_text(encoding="utf-8"))
        self.assertTrue(cfg["privacy_adsense_in_use"])
        self.assertIn("A8.net", cfg["privacy_affiliate_note_html"])
        self.assertNotIn("amazon", build.PR_STORES)
        legal_cfg = {k: v for k, v in cfg.items() if not (k == "amazon_tracking_id" and "amazon" not in build.PR_STORES)}
        self.assertEqual(sitekit.amazon_disclosure(legal_cfg), "")


if __name__ == "__main__":
    unittest.main()
