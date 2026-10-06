"""Weekly digest of municipal sightings: counts come from the lists, truncated lists are left out, nothing after as-of."""
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.kuma import build, digest


def row(day, kind="目撃"):
    return {"observed_at": f"{day}T08:00:00+09:00", "city": "A市", "place": "x", "count": 1, "kind": kind, "species": "クマ"}


def pref(rows, monthly, as_of, **kw):
    return {"as_of": as_of, "fy_current": "R08", "fetched_at": "2026-10-06T06:00:00+09:00", "monthly": {"R08": monthly},
            "sightings": rows, **kw}


# 2026-09-21 (Mon) .. 09-27 (Sun) = W39; 09-28 .. 10-04 = W40
GOOD = pref([row("2026-09-14"), row("2026-09-22"), row("2026-09-22"), row("2026-09-27", "痕跡"), row("2026-09-30")],
            {"9": 5, "10": 0}, "2026-10-04")
TRUNC = pref([row("2026-09-22")], {"9": 400}, "2026-10-04")  # the list is far shorter than the prefecture's own month


class DigestTest(unittest.TestCase):
    def test_week_keys_are_monday_to_sunday(self):
        self.assertEqual(digest.week_key(date(2026, 9, 27)), "2026-W39")
        self.assertEqual(digest.week_key(date(2026, 9, 28)), "2026-W40")
        self.assertEqual(digest.week_start("2026-W40"), date(2026, 9, 28))
        self.assertEqual(digest.prev_key("2026-W01"), "2025-W52")

    def test_fiscal_year_label(self):
        self.assertEqual(digest.fy_key(date(2026, 3, 31)), "R07")
        self.assertEqual(digest.fy_key(date(2026, 4, 1)), "R08")

    def test_counts_per_week_all_kinds_and_only_when_month_adds_up(self):
        src = digest.pref_source("miyagi", "宮城県", GOOD)
        dig = digest.build([src], first_day=date(2026, 9, 7))
        self.assertEqual(dig["by_week"]["2026-W39"], {"miyagi": 3})
        self.assertEqual(dig["by_week"]["2026-W38"], {"miyagi": 1})
        self.assertEqual(dig["by_week"]["2026-W37"], {"miyagi": 0})

    def test_the_week_includes_a_month_without_a_monthly_figure_only_if_it_matches(self):
        # October has no row and monthly 0 -> counts as consistent; a week touching a month that disagrees is dropped.
        bad = pref(GOOD["sightings"], {"9": 6, "10": 0}, "2026-10-04")
        dig = digest.build([digest.pref_source("miyagi", "宮城県", bad)], first_day=date(2026, 9, 7))
        self.assertEqual(dig["weeks"], [])

    def test_truncated_list_is_excluded_not_miscounted(self):
        dig = digest.build([digest.pref_source("akita", "秋田県", TRUNC), digest.pref_source("miyagi", "宮城県", GOOD)],
                           first_day=date(2026, 9, 7))
        for k in dig["weeks"]:
            self.assertNotIn("akita", dig["by_week"][k])

    def test_nothing_after_the_as_of_date_and_only_complete_weeks(self):
        late = pref(GOOD["sightings"] + [row("2026-10-06")], {"9": 5, "10": 1}, "2026-10-04")
        dig = digest.build([digest.pref_source("miyagi", "宮城県", late)], first_day=date(2026, 9, 7))
        self.assertNotIn("2026-W41", dig["weeks"])
        self.assertEqual(dig["by_week"]["2026-W40"], {"miyagi": 1})

    def test_common_total_uses_only_sources_in_both_weeks(self):
        a = digest.pref_source("miyagi", "宮城県", GOOD)
        dig = {"by_week": {"2026-W39": {"miyagi": 3}, "2026-W40": {"miyagi": 1, "yamaguchi": 9}}, "weeks": [], "sources": {"miyagi": a}}
        self.assertEqual(digest.common_total(dig, "2026-W40"), (1, 3, ["miyagi"]))


class DigestPagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_kuma_build import CFG, HAVE_PYPDF, raw_data
        if not HAVE_PYPDF:
            raise unittest.SkipTest("pypdf is not installed")
        raw = raw_data()
        raw["notices"] = []
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        full = {**GOOD, "source": "miyagi", "source_page": "https://example.jp/m", "credit": "出典:テスト", "update_note": "更新します"}
        build.render_site(raw, CFG, cls.out, release=True, otsu=None, prefs={"miyagi": full})

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_week_page_states_the_count_and_the_comparison_from_the_data(self):
        t = self.read("digest/2026-W39/index.html")
        self.assertIn("2026年9月21日から9月27日", t)
        self.assertIn("合計3件", t)
        self.assertIn("前の週", t)

    def test_hub_and_sitemap_list_the_weeks_and_caution_is_shown(self):
        hub = self.read("digest/index.html")
        self.assertIn("/digest/2026-W39/", hub)
        self.assertIn("そのまま比べられません", hub)
        self.assertIn("/digest/2026-W39/", self.read("sitemap.xml"))
        self.assertIn("/digest/", self.read("index.html"))  # the header link

    def test_no_digest_without_any_list(self):
        from tests.test_kuma_build import CFG, raw_data
        raw = raw_data()
        raw["notices"] = []
        with tempfile.TemporaryDirectory() as tmp:
            files = build.render_site(raw, CFG, Path(tmp), release=True, otsu=None, prefs=None)
        self.assertFalse([f for f in files if f.startswith("digest/")])
