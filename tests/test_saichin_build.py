import json
import re
import tempfile
import unittest
from pathlib import Path

from sites.saichin import build
from sokuhou.sources import mhlw_minwage

FIXTURE = Path(__file__).parent / "fixtures" / "mhlw_minwage_history.xlsx"
BASE_CFG = {"site_url": "https://saichin-sokuho.com", "site_name": "最低賃金速報",
            "operator_name": None, "contact_email": None, "adsense_pub_id": None}
FULL_CFG = {**BASE_CFG, "operator_name": "テスト運営", "contact_email": "info@example.com"}


def _raw():
    raw = mhlw_minwage.parse_xlsx(FIXTURE.read_bytes())
    raw.update({"source_page": mhlw_minwage.PAGE, "source_file": "x.xlsx", "fetched_at": "2026-10-05T17:00:00+09:00"})
    return raw


class BuildTestBase(unittest.TestCase):
    def render(self, cfg, release=False):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "dist"
        files = build.render_site(_raw(), cfg, out, release=release)
        return out, files

    @staticmethod
    def read(out, rel):
        return (out / rel).read_text(encoding="utf-8")


class PreviewBuildTest(BuildTestBase):
    def setUp(self):
        self.out, self.files = self.render(BASE_CFG)

    def test_file_set(self):
        from sites.saichin import ogimage
        expected = 76 + 1 + 1 + 1 + 48 + (48 if ogimage.available() else 0)  # + feed.xml, feed/dates.xml, notify page, 48 calendars, share cards (default + 47 prefectures)
        self.assertEqual(len(self.files), expected)
        html_pages = [f for f in self.files if f.endswith('.html')]
        self.assertEqual(len(html_pages), 1 + 47 + 8 + 3 + 2 + 1 + 6 + 3 + 1)  # home, prefectures, areas, rankings, calendar+history, notify, guides, legal, 404
        for rel in ("index.html", "shiga/index.html", "okinawa/index.html", "about/index.html",
                    "privacy/index.html", "contact/index.html", "404.html", "sitemap.xml", "robots.txt"):
            self.assertIn(rel, self.files)
        self.assertTrue((self.out / "assets" / "app.js").exists())
        self.assertFalse((self.out / "ads.txt").exists())

    def test_htaccess_keeps_the_https_redirect(self):
        text = self.read(self.out, ".htaccess")
        self.assertIn("RewriteCond %{HTTPS} !on", text)
        self.assertIn("RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]", text)
        self.assertNotIn(chr(13), text)  # LF only, as Apache expects

    def test_preview_is_not_indexable(self):
        self.assertIn("Disallow: /", self.read(self.out, "robots.txt"))
        for rel in ("index.html", "shiga/index.html", "about/index.html"):
            self.assertIn('content="noindex,nofollow"', self.read(self.out, rel))
        self.assertIn("プレビュー版", self.read(self.out, "index.html"))

    def test_no_template_leftovers(self):
        for rel in self.files:
            if rel.endswith(".html"):
                text = self.read(self.out, rel)
                self.assertNotIn("{source}", text, rel)
                self.assertNotIn("{{", text, rel)
                self.assertNotIn("None", text, rel)

    def test_prefecture_page_content(self):
        text = self.read(self.out, "shiga/index.html")
        for needle in ("滋賀県の最低賃金(令和8年度) 1,136円", "2026年10月3日", "+56円", "1,080円",
                       "全国加重平均 1,177円", 'rel="canonical" href="https://saichin-sokuho.com/shiga/"'):
            self.assertIn(needle, text)
        higher = sum(1 for p in _raw()["prefectures"] if p["history"]["2026"]["amount"] > 1136)  # independent count
        self.assertEqual(higher, 11)
        self.assertEqual(re.search(r"47都道府県中 (\d+)位", text).group(1), str(higher + 1))  # ties share a rank

    def test_ranks_and_monthly_estimate(self):
        d = build.prepare(_raw())
        by = {r["short"]: r for r in d["rows"]}
        self.assertEqual(by["東京"]["rank"], 1)
        self.assertEqual(by["宮崎"]["rank"], 47)
        self.assertEqual(sorted(r["rank"] for r in d["rows"])[0], 1)
        self.assertEqual(build.monthly_estimate(1136), 196900)  # 1136 * 40 * 52 / 12 = 196,906.7

    def test_static_pages_do_not_claim_a_time_relative_state(self):
        for r in build.prepare(_raw())["rows"]:
            self.assertNotIn("発効済み", self.read(self.out, f"{r['slug']}/index.html"), r["slug"])

    def test_history_is_contiguous_and_ordered(self):
        tokyo = next(r for r in build.prepare(_raw())["rows"] if r["short"] == "東京")
        labels = [h["label"] for h in tokyo["history"]]
        self.assertEqual(labels[0], "平成28年度")
        self.assertEqual(labels[-1], "令和8年度")
        self.assertIn("令和元年度", labels)
        self.assertEqual(len(labels), 11)

    def test_index_links_resolve_and_embedded_json_is_valid(self):
        text = self.read(self.out, "index.html")
        links = set(re.findall(r'href="(/[a-z]+/)"', text))
        self.assertTrue({"/shiga/", "/tokyo/", "/about/", "/privacy/", "/contact/"} <= links)
        for link in links:
            self.assertTrue((self.out / link.strip("/") / "index.html").exists(), link)
        payload = re.search(r'<script type="application/json" id="data">(.*?)</script>', text, re.S).group(1)
        self.assertEqual(len(json.loads(payload)), 47)
        self.assertNotIn("<", payload)

    def test_sitemap_lists_every_page(self):
        locs = re.findall(r"<loc>(.*?)</loc>", self.read(self.out, "sitemap.xml"))
        self.assertEqual(len(locs), 71)  # every html page except 404
        self.assertIn("https://saichin-sokuho.com/shiga/", locs)

    def test_privacy_page_has_the_ad_disclosures(self):
        text = self.read(self.out, "privacy/index.html")
        for needle in ("Google AdSense", "adssettings.google.com", "aboutads.info", "policies.google.com/technologies/partner-sites"):
            self.assertIn(needle, text)


class RebuildTest(BuildTestBase):
    def test_rebuilding_into_the_same_folder_removes_only_stale_files(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "site"
        first = build.render_site(_raw(), BASE_CFG, out)
        (out / "stale.html").write_text("old", encoding="utf-8")
        (out / "old-dir").mkdir()
        (out / "old-dir" / "x.html").write_text("old", encoding="utf-8")
        second = build.render_site(_raw(), BASE_CFG, out)
        self.assertEqual(first, second)
        self.assertFalse((out / "stale.html").exists())
        self.assertFalse((out / "old-dir" / "x.html").exists())
        on_disk = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
        self.assertEqual(on_disk, second)

    def test_switching_from_preview_to_release_replaces_ads_and_robots(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "site"
        build.render_site(_raw(), {**BASE_CFG, "adsense_pub_id": "pub-1"}, out)
        self.assertTrue((out / "ads.txt").exists())
        build.render_site(_raw(), FULL_CFG, out, release=True)
        self.assertFalse((out / "ads.txt").exists())  # a stale ads.txt must not survive
        self.assertIn("Allow: /", (out / "robots.txt").read_text(encoding="utf-8"))


class ReleaseBuildTest(BuildTestBase):
    def test_release_refuses_without_operator_info(self):
        with self.assertRaises(build.BuildError) as cm:
            self.render(BASE_CFG, release=True)
        self.assertIn("operator_name", str(cm.exception))
        self.assertIn("contact_email", str(cm.exception))

    def test_release_refuses_with_partial_info(self):
        with self.assertRaises(build.BuildError):
            self.render({**BASE_CFG, "operator_name": "x"}, release=True)

    def test_release_is_indexable_and_has_operator_info(self):
        out, _ = self.render(FULL_CFG, release=True)
        self.assertIn("Allow: /", self.read(out, "robots.txt"))
        self.assertIn("Sitemap: https://saichin-sokuho.com/sitemap.xml", self.read(out, "robots.txt"))
        for rel in ("index.html", "shiga/index.html", "about/index.html"):
            self.assertNotIn("noindex", self.read(out, rel))
        self.assertIn("テスト運営", self.read(out, "about/index.html"))
        self.assertNotIn("(未設定)", self.read(out, "about/index.html"))
        self.assertIn("mailto:info@example.com", self.read(out, "contact/index.html"))

    def test_form_only_release_publishes_no_email_address(self):
        cfg = {**BASE_CFG, "operator_name": "テスト運営", "contact_form_url": "https://forms.example.com/abc"}
        out, files = self.render(cfg, release=True)
        self.assertEqual(build.missing_config(cfg), [])
        contact = self.read(out, "contact/index.html")
        self.assertIn('href="https://forms.example.com/abc"', contact)
        self.assertNotIn("mailto:", contact)
        for rel in files:
            if rel.endswith(".html"):
                text = self.read(out, rel)
                self.assertNotIn("(未設定)", text, rel)
                self.assertNotIn("@", text, rel)
        self.assertIn('href="/contact/">お問い合わせフォーム', self.read(out, "about/index.html"))
        self.assertIn("お問い合わせフォーム</a>からお願いします", self.read(out, "privacy/index.html"))

    def test_insecure_form_url_is_rejected(self):
        cfg = {**BASE_CFG, "operator_name": "x", "contact_form_url": "http://forms.example.com/abc"}
        self.assertEqual(len(build.missing_config(cfg)), 1)
        with self.assertRaises(build.BuildError):
            self.render(cfg, release=True)

    def test_missing_config_names_the_fields(self):
        self.assertEqual(build.missing_config(BASE_CFG), ["operator_name", "contact_form_url or contact_email"])
        self.assertEqual(build.missing_config({**BASE_CFG, "operator_name": "x"}), ["contact_form_url or contact_email"])

    def test_adsense_snippet_and_ads_txt_only_when_configured(self):
        out, _ = self.render({**FULL_CFG, "adsense_pub_id": "ca-pub-1234567890123456"}, release=True)
        self.assertIn("client=ca-pub-1234567890123456", self.read(out, "index.html"))
        self.assertEqual(self.read(out, "ads.txt"), "google.com, pub-1234567890123456, DIRECT, f08c47fec0942fa0\n")
        plain, _ = self.render(FULL_CFG, release=True)
        self.assertNotIn("adsbygoogle", self.read(plain, "index.html"))

    def test_operator_text_is_escaped(self):
        out, _ = self.render({**FULL_CFG, "operator_name": 'A&B <script>"x"</script>'}, release=True)
        text = self.read(out, "about/index.html")
        self.assertIn("A&amp;B &lt;script&gt;", text)
        self.assertNotIn("<script>\"x\"", text)


class DataGateTest(unittest.TestCase):
    def test_effective_date_outside_fiscal_year_is_rejected(self):
        raw = _raw()
        raw["prefectures"][0]["history"]["2026"]["effective_date"] = "2030-01-01"
        with self.assertRaises(build.BuildError):
            build.prepare(raw)

    def test_a_decrease_is_rejected(self):
        raw = _raw()
        raw["prefectures"][0]["history"]["2026"]["amount"] = 1
        with self.assertRaises(build.BuildError):
            build.prepare(raw)


if __name__ == "__main__":
    unittest.main()
