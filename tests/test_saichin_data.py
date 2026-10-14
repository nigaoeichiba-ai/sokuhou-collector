"""/data/ (CSV and JSON of every prefecture in every year), the Dataset markup and /cite/."""
import csv
import io
import json
import re

from sites.saichin import build, dataset
from tests.test_saichin_pages import CFG, SiteFixture, _raw


def independent_rows(raw):
    """Every (prefecture, year) row, recomputed straight from the workbook without using build.prepare()."""
    out = {}
    for p in raw["prefectures"]:
        for y in range(2002, 2027):
            amount = p["history"][str(y)]["amount"]
            prev = p["history"].get(str(y - 1))
            rank = 1 + sum(1 for q in raw["prefectures"] if q["history"][str(y)]["amount"] > amount)
            out[(p["name"], y)] = (amount, None if prev is None else amount - prev["amount"], rank)
    return out


class DataFilesTest(SiteFixture):
    def csv_rows(self):
        raw = (self.out / "data" / dataset.CSV_NAME).read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), "Japanese Excel needs the byte order mark")
        return list(csv.reader(io.StringIO(raw[3:].decode("utf-8"))))

    def test_the_csv_has_one_row_per_prefecture_and_year_and_every_number_is_recomputed_independently(self):
        rows = self.csv_rows()
        self.assertEqual(rows[0], dataset.COLUMNS)
        self.assertEqual(len(rows) - 1, 47 * 25)
        expected = independent_rows(_raw())
        seen = set()
        names = {r["name"]: r["short"] for r in self.d["rows"]}
        for pref, fy, label, amount, raise_, eff, rank, original in rows[1:]:
            key = (names[pref], int(fy))
            seen.add(key)
            exp_amount, exp_raise, exp_rank = expected[key]
            self.assertEqual((int(amount), None if raise_ == "" else int(raise_), int(rank)), (exp_amount, exp_raise, exp_rank), key)
            self.assertRegex(eff, r"^\d{4}-\d{2}-\d{2}$", key)
        self.assertEqual(len(seen), 47 * 25)

    def test_empty_cells_not_the_word_none(self):
        text = (self.out / "data" / dataset.CSV_NAME).read_bytes().decode("utf-8")
        self.assertNotIn("None", text)
        first_years = [r for r in self.csv_rows()[1:] if r[1] == "2002"]
        self.assertEqual(len(first_years), 47)
        self.assertTrue(all(r[4] == "" for r in first_years))                    # no previous year, so no raise

    def test_the_json_carries_the_same_rows_and_the_source_and_the_processing_note(self):
        data = json.loads((self.out / "data" / dataset.JSON_NAME).read_text(encoding="utf-8"))
        self.assertEqual(len(data["rows"]), 47 * 25)
        csv_rows = self.csv_rows()[1:]
        self.assertEqual([(r["prefecture"], str(r["fiscal_year"]), str(r["amount_yen"]), str(r["rank_of_47"])) for r in data["rows"]],
                         [(r[0], r[1], r[3], r[6]) for r in csv_rows])
        self.assertEqual(data["source"]["license_url"], dataset.PDL_URL)
        self.assertIn("mhlw.go.jp", data["source"]["url"])
        self.assertIn("厚生労働省が作成したものではありません", data["processing"])
        self.assertEqual(data["as_of"], self.d["fetched_date"])
        self.assertEqual(len(data["national_weighted_average"]), 25)

    def test_the_files_are_published_and_not_in_the_sitemap(self):
        self.assertIn(f"data/{dataset.CSV_NAME}", self.files)
        self.assertIn(f"data/{dataset.JSON_NAME}", self.files)
        sitemap = self.read("sitemap.xml")
        self.assertIn("https://saichin-sokuho.com/data/<", sitemap)
        self.assertIn("https://saichin-sokuho.com/cite/<", sitemap)
        self.assertNotIn(".csv", sitemap)


class DatasetMarkupTest(SiteFixture):
    def ld(self):
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', self.read("data/index.html"), re.S)
        self.assertIsNotNone(m)
        return json.loads(m.group(1))

    def test_the_dataset_markup_meets_the_conditions_of_dataset_search(self):
        ld = self.ld()
        self.assertEqual(ld["@type"], "Dataset")
        self.assertGreaterEqual(len(ld["description"]), 50)
        self.assertTrue(ld["name"])
        urls = {d["contentUrl"] for d in ld["distribution"]}
        self.assertEqual(urls, {f"https://saichin-sokuho.com/data/{dataset.CSV_NAME}", f"https://saichin-sokuho.com/data/{dataset.JSON_NAME}"})
        self.assertEqual(ld["license"], dataset.PDL_URL)
        self.assertEqual(ld["url"], "https://saichin-sokuho.com/data/")
        self.assertEqual(ld["temporalCoverage"], "2002/2027")

    def test_only_the_data_page_carries_the_markup(self):
        for rel in self.files:
            if rel.endswith(".html") and rel != "data/index.html":
                self.assertNotIn("application/ld+json", self.read(rel), rel)


class CiteAndLinksTest(SiteFixture):
    def test_the_cite_page_names_the_source_the_license_the_date_and_the_three_rules(self):
        page = self.read("cite/index.html")
        self.assertEqual(page.count("<h1>"), 1)
        self.assertIn(dataset.PDL_URL, page)
        self.assertIn(self.d["source_page"], page)
        self.assertIn(build.jp_date(self.d["fetched_date"]), page)
        for needle in ("出典(サイトの名前とページのURL)", "編集・加工したことと、加工した人", "国が作ったものであるかのように見せない",
                       "厚生労働省が運営しているものではありません"):
            self.assertIn(needle, page)
        quotes = re.findall(r'<p class="quote">(.*?)</p>', page, re.S)
        self.assertEqual(len(quotes), 2)
        self.assertIn("加工して作成", quotes[0])
        self.assertIn("PDL1.0", quotes[0])

    def test_every_prefecture_page_and_the_history_page_link_to_the_data_and_the_cite_page(self):
        for rel in [f"{r['slug']}/index.html" for r in self.d["rows"]] + ["history/index.html"]:
            page = self.read(rel)
            self.assertIn('href="/data/"', page, rel)
            self.assertIn('href="/cite/"', page, rel)

    def test_the_data_page_lists_the_columns_the_csv_really_has(self):
        page = self.read("data/index.html")
        for column in dataset.COLUMNS:
            self.assertIn(f"<td>{column}</td>", page, column)
