"""Owner decision D36 (2026-11-27): saichin, kuma and minna no longer load the AdSense script, their privacy policy no longer names the service, and ads.txt stays."""
import json
import unittest
from pathlib import Path

from sites.kuma import build as kuma
from sokuhou import sitekit

ROOT = Path(sitekit.__file__).parent.parent
OFF = ("saichin", "kuma", "minna")


def cfg_of(site: str) -> dict:
    return json.loads((ROOT / "sites" / site / "config.json").read_text(encoding="utf-8"))


class AdSenseOff(unittest.TestCase):
    def test_the_three_sites_are_off_and_keep_the_account_id_for_ads_txt(self):
        for site in OFF:
            cfg = cfg_of(site)
            self.assertFalse(sitekit.adsense_tag_on(cfg), site)
            self.assertTrue(cfg["adsense_pub_id"], site)
            self.assertIn("ads.txt", sitekit.standard_files({}, cfg, False, "2026-11-27"), site)

    def test_the_switch_is_what_turns_it_off(self):
        for site in OFF:                                                    # negative: without the setting the same config would load the script again
            self.assertTrue(sitekit.adsense_tag_on({k: v for k, v in cfg_of(site).items() if k != "adsense_tag"}), site)
        self.assertFalse(sitekit.adsense_tag_on({}))

    def test_the_built_pages_carry_no_tag_and_the_privacy_page_does_not_name_the_service(self):
        site = kuma.SITE                                                    # (any site description: the privacy page is the shared one)
        for name in OFF:
            cfg = cfg_of(name)
            pages = sitekit.legal_pages(site, cfg, False, purpose="x", sources_html="", update_text="", disclaimer_html="x", contact_notice="x")
            for rel, text in pages.items():
                if isinstance(text, str) and rel.endswith(".html"):
                    self.assertNotIn("adsbygoogle", text, f"{name} {rel}")
            privacy = pages["privacy/index.html"]
            for word in ("AdSense", "adssettings.google.com", "partner-sites"):
                self.assertNotIn(word, privacy, name)
            self.assertIn("広告について", privacy, name)
            self.assertIn("AdSense", sitekit.legal_pages(site, {**cfg, "adsense_tag": True}, False, purpose="x", sources_html="", update_text="",
                                                         disclaimer_html="x", contact_notice="x")["privacy/index.html"], name)


if __name__ == "__main__":
    unittest.main()
