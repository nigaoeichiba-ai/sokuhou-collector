import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from sokuhou import run
from sokuhou.sources import yamanashi_kuma as kuma

FIX = Path(__file__).parent / "fixtures"


def _files():
    return [(FIX / "yamanashi_kuma1.csv").read_bytes(), (FIX / "yamanashi_kuma0.csv").read_bytes()]


def _parse(files=None):
    with mock.patch.object(kuma, "MIN_ROWS", 1):
        return kuma.parse_csvs(files or _files())


class YamanashiKumaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = _parse()

    def test_rows_of_both_files_are_joined_on_the_number(self):
        self.assertEqual(len(self.d["sightings"]), 101)  # 75 + 26 rows, numbers 1-60, 185-198 and 199-224: no overlap in this fixture
        both = _parse([_files()[0], _files()[0], _files()[1]])
        self.assertEqual(len(both["sightings"]), 101)  # the same file twice adds nothing

    def test_newest_first_and_the_first_and_last_rows(self):
        s = self.d["sightings"]
        self.assertEqual(s[0], {"observed_at": "2026-10-05T02:00:00+09:00", "city": "西桂町", "place": "下暮地地内", "count": 1, "kind": "目撃",
                                "species": "ツキノワグマ", "lat": 35.5252, "lon": 138.8436})
        self.assertEqual(s[-1]["observed_at"], "2026-04-02T14:00:00+09:00")
        self.assertEqual(s[-1]["city"], "身延町")
        self.assertEqual([x["observed_at"] for x in s], sorted((x["observed_at"] for x in s), reverse=True))

    def test_as_of_fiscal_year_and_monthly_counts_match_the_csv(self):
        self.assertEqual(self.d["as_of"], "2026-10-05")
        self.assertEqual(self.d["fy_current"], "R08")
        self.assertEqual(self.d["monthly"]["R08"], {"4": 16, "5": 33, "6": 11, "8": 6, "9": 33, "10": 2})  # counted by hand from the fixture
        self.assertEqual(self.d["unparsed"], 0)
        self.assertEqual(self.d["bad_coords"], 0)
        no_pos = [x for x in self.d["sightings"] if "lat" not in x]
        self.assertEqual(sorted(x["city"] for x in no_pos), ["上野原市", "南アルプス市"])  # two rows have no position in the CSV
        self.assertIn((35.5322, 139.0229), {(x.get("lat"), x.get("lon")) for x in self.d["sightings"] if x["city"] == "道志村"})  # "35.53223105822404," had a stray comma

    def test_credit_names_the_prefecture_and_says_it_was_processed(self):
        self.assertIn("(山梨県)", self.d["credit"])
        self.assertIn("加工して作成", self.d["credit"])
        self.assertIn("大まかな付近", self.d["update_note"])

    def test_a_changed_header_or_too_few_rows_is_refused(self):
        bad = _files()[1].replace("目撃市町村".encode(), "市町村名".encode())
        with self.assertRaises(kuma.YamanashiKumaSourceError):
            _parse([bad])
        with self.assertRaises(kuma.YamanashiKumaSourceError):
            with mock.patch.object(kuma, "MIN_ROWS", 500):
                kuma.parse_csvs(_files())

    def test_coordinates_outside_the_prefecture_are_dropped_and_too_many_of_them_refuse_the_file(self):
        text = _files()[1].decode("utf-8-sig")
        one = text.replace("35.69037848", "10.0", 1).encode("utf-8-sig")
        out = _parse([_files()[0], one])
        self.assertEqual(out["bad_coords"], 1)
        self.assertEqual(sum(1 for x in out["sightings"] if "lat" not in x), 3)  # the 2 rows without a position + the one dropped
        every = text.replace("\t", "").encode("utf-8-sig")
        self.assertTrue(every)
        rows = text.splitlines(keepends=True)
        wrecked = "".join(rows[:1] + [r.replace("35.", "9.").replace("138.", "9.") for r in rows[1:]]).encode("utf-8-sig")
        with self.assertRaises(kuma.YamanashiKumaSourceError):
            _parse([wrecked])

    def test_dates_that_do_not_exist_are_counted_as_unparsed(self):
        text = _files()[1].decode("utf-8-sig").replace("2026/9/7", "2026/2/31", 1)
        out = _parse([text.encode("utf-8-sig"), _files()[0]])
        self.assertEqual(out["unparsed"], 1)
        self.assertEqual(len(out["sightings"]), 100)

    def test_collect_reads_both_packages_without_network(self):
        pages = {
            kuma.API + "kuma1": (FIX / "yamanashi_package_kuma1.json").read_bytes(),
            kuma.API + "kuma0": (FIX / "yamanashi_package_kuma0.json").read_bytes(),
            "https://catalog.dataplatform-yamanashi.jp/dataset/bed5301d-75b2-4976-8687-2b2721ae143a/resource/89d2478e-e29e-46e3-9ad3-19bf44822d4d/download/2026kumadata.csv": _files()[0],
            "https://catalog.dataplatform-yamanashi.jp/dataset/0e9f8d75-5773-4cac-be4d-68d50bd819d8/resource/62796404-c80f-47d6-ae88-222f844ee958/download/2026kumadata_new.csv": _files()[1],
        }
        with mock.patch.object(kuma, "fetch", lambda url: SimpleNamespace(body=pages[url])), mock.patch.object(kuma, "MIN_ROWS", 1):
            out = kuma.collect()
        self.assertEqual(len(out["source_file"]), 2)
        self.assertEqual(out["as_of"], "2026-10-05")
        self.assertTrue(out["fetched_at"])

    def test_it_is_registered_and_its_sanity_check_refuses_a_shrinking_year(self):
        names = {s.name for s in run.GROUPS["kuma"]}
        self.assertIn("yamanashi_kuma", names)
        old = {"source": "yamanashi", "sightings": [{"observed_at": "2026-04-02"}] * 100}
        run.check_pref_bear(old, {"source": "yamanashi", "sightings": [{"observed_at": "2026-04-02"}] * 70})
        with self.assertRaises(run.SanityError):
            run.check_pref_bear(old, {"source": "yamanashi", "sightings": [{"observed_at": "2026-04-02"}] * 69})


if __name__ == "__main__":
    unittest.main()
