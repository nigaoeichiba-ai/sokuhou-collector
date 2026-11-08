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
        build.render_site(raw, CFG, cls.out, release=True, prefs={"miyagi": full})

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
            files = build.render_site(raw, CFG, Path(tmp), release=True, prefs=None)
        self.assertFalse([f for f in files if f.startswith("digest/")])


class TopCityTest(unittest.TestCase):
    def test_most_rows_city_and_ties(self):
        rows = [dict(row("2026-09-22"), city="B市"), dict(row("2026-09-23"), city="B市"), dict(row("2026-09-24"), city="C町"),
                dict(row("2026-09-14"), city="A市")]
        src = digest.pref_source("miyagi", "宮城県", pref(rows, {"9": 4}, "2026-10-04"))
        self.assertEqual(digest.top_cities(src, "2026-W39"), (["B市"], 2, 3))
        rows2 = [dict(row("2026-09-22"), city="B市"), dict(row("2026-09-23"), city="C町")]
        src2 = digest.pref_source("miyagi", "宮城県", pref(rows2, {"9": 2}, "2026-10-04"))
        self.assertEqual(digest.top_cities(src2, "2026-W39"), (["B市", "C町"], 1, 2))
        self.assertEqual(digest.top_cities(src, "2026-W41"), ([], 0, 0))

    def test_rows_after_as_of_are_not_counted(self):
        rows = [dict(row("2026-09-22"), city="B市"), dict(row("2026-10-06"), city="Z市"), dict(row("2026-10-07"), city="Z市")]
        src = digest.pref_source("miyagi", "宮城県", pref(rows, {"9": 1, "10": 2}, "2026-10-04"))
        self.assertEqual(digest.top_cities(src, "2026-W41"), ([], 0, 0))


class SnapshotTest(unittest.TestCase):
    """Weeks counted once stay after the municipality's list no longer allows counting them."""

    def live(self):
        rows = [dict(row("2026-09-22"), city="B市"), dict(row("2026-09-23"), city="B市"), dict(row("2026-09-24"), city="C町")]
        src = digest.pref_source("miyagi", "宮城県", pref(rows, {"9": 3}, "2026-10-04"))
        return digest.build([src], first_day=date(2026, 9, 21))

    def test_entry_matches_a_hand_count(self):
        dig = self.live()
        self.assertEqual(digest.entry(dig, "miyagi", "2026-W39"),
                         {"count": 3, "first": "2026-09-22", "last": "2026-09-24", "cities": {"B市": 2, "C町": 1}})

    def test_snapshot_keeps_a_week_the_list_no_longer_covers(self):
        snap = digest.updated_snapshot(None, self.live())
        self.assertEqual(snap["weeks"]["2026-W39"]["miyagi"]["count"], 3)
        # later the prefecture's list only holds one row, the month no longer adds up: the live digest has no such week
        later = digest.build([digest.pref_source("miyagi", "宮城県", pref([row("2026-10-01")], {"9": 3, "10": 1}, "2026-10-11"))],
                             first_day=date(2026, 9, 21))
        self.assertNotIn("2026-W39", later["weeks"])
        merged = digest.merge_snapshot(later, snap)
        self.assertEqual(merged["by_week"]["2026-W39"], {"miyagi": 3})
        self.assertIn("2026-W39", merged["weeks"])
        self.assertEqual(digest.entry(merged, "miyagi", "2026-W39")["cities"], {"B市": 2, "C町": 1})

    def test_a_week_counted_from_today_wins_and_replaces_the_saved_figure(self):
        snap = {"version": 1, "weeks": {"2026-W39": {"miyagi": {"count": 99, "first": None, "last": None, "cities": {}}}}}
        dig = digest.merge_snapshot(self.live(), snap)
        self.assertEqual(dig["by_week"]["2026-W39"]["miyagi"], 3)
        self.assertNotIn(("2026-W39", "miyagi"), dig["frozen"])
        self.assertEqual(digest.updated_snapshot(snap, dig)["weeks"]["2026-W39"]["miyagi"]["count"], 3)

    def test_frozen_weeks_are_not_rewritten_and_a_source_that_is_gone_stays_out(self):
        snap = {"version": 1, "weeks": {"2026-W30": {"miyagi": {"count": 4, "first": "2026-07-20", "last": "2026-07-22", "cities": {"X市": 4}},
                                                       "stopped": {"count": 7, "first": None, "last": None, "cities": {}}}}}
        dig = digest.merge_snapshot(self.live(), snap)
        self.assertEqual(dig["by_week"]["2026-W30"], {"miyagi": 4})        # "stopped" is not a source of today's build
        again = digest.updated_snapshot(snap, dig)
        self.assertEqual(again["weeks"]["2026-W30"]["miyagi"]["count"], 4)
        self.assertEqual(again["weeks"]["2026-W30"]["stopped"]["count"], 7)  # kept in the file, shown nowhere

    def test_saved_week_page_renders_with_its_note_and_older_weeks_in_the_hub(self):
        from tests.test_kuma_build import CFG, HAVE_PYPDF, raw_data
        if not HAVE_PYPDF:
            self.skipTest("pypdf is not installed")
        raw = raw_data()
        raw["notices"] = []
        snap = {"version": 1, "weeks": {"2026-W30": {"miyagi": {"count": 4, "first": "2026-07-20", "last": "2026-07-22", "cities": {"X市": 4}}}}}
        full = {**GOOD, "source": "miyagi", "source_page": "https://example.jp/m", "credit": "出典:テスト", "update_note": "更新します"}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            build.render_site(raw, CFG, out, release=True, prefs={"miyagi": full}, snapshot=snap)
            t = (out / "digest/2026-W30/index.html").read_text(encoding="utf-8")
            self.assertIn("合計4件", t)
            self.assertIn("X市の4件", t)
            self.assertIn("保存した値", t)
            self.assertIn("/digest/2026-W30/", (out / "digest/index.html").read_text(encoding="utf-8"))
            live_page = (out / "digest/2026-W39/index.html").read_text(encoding="utf-8")
            self.assertNotIn("保存した値", live_page)

    def test_update_cli_writes_only_when_something_changed(self):
        from sites.kuma import digest_snapshot
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            full = {**GOOD, "source": "miyagi", "source_page": "https://example.jp/m", "credit": "出典:テスト", "update_note": "更新します"}
            (data / "miyagi_kuma.json").write_text(__import__("json").dumps(full, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(digest_snapshot.update(data))
            self.assertFalse(digest_snapshot.update(data))
            saved = __import__("json").loads((data / "kuma_digest_snapshot.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["weeks"]["2026-W39"]["miyagi"]["count"], 3)
