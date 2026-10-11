import json
import unittest
from datetime import datetime

from pathlib import Path

from sites.yorokobu import fetch, refresh
from sokuhou import rakuten
from tests.test_yorokobu_fetch import CONTENT, FILTERS, FakeTransport, client, raw_item

CONTENT_DIR_REAL = Path(__file__).resolve().parents[1] / "sites" / "yorokobu" / "content"
PICKS = {
    "birthday-boyfriend": [
        {"picks": [{"code": "p1", "note": "毎日使う定番です。"}, {"code": "p2", "note": "革の質感のレビューが多いです。"}], "backups": ["b1", "b2"]},
        {"picks": [{"code": "n1", "note": "名入れできます。"}], "backups": []},
    ],
    "mothers-day-mother": [{"picks": [{"code": "f1", "note": "花束です。"}], "backups": ["f2"]}],
}


def item_for(url, gone=(), sold_out=()):
    import urllib.parse
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    code = q.get("itemCode", [None])[0]
    if code is None:
        return [raw_item("s1", 2000, "z1"), raw_item("s2", 2500, "z2"), raw_item("s3", 3000, "z3"), raw_item("s4", 3500, "z4")]  # keyword search
    if code in gone:
        return []
    shop, _, number = code.partition(":")
    it = raw_item(code, 2000, "s" + code, reviews=40)
    it["itemCode"] = code
    it["availability"] = 0 if code in sold_out else 1
    return [it]


class RefreshTest(unittest.TestCase):
    def run_refresh(self, gone=(), sold_out=()):
        t = FakeTransport(lambda u: item_for(u, gone, sold_out))
        data = refresh.refresh(CONTENT, client(t), {k: json.loads(json.dumps(v).replace('"p1"', '"p1"')) for k, v in PICKS.items()},
                               now=datetime(2026, 10, 7, 7, 0))
        return data, t

    def test_each_pick_is_looked_up_by_item_code_and_keeps_its_note(self):
        data, t = self.run_refresh()
        ideas = data["pairs"]["birthday-boyfriend"]["ideas"]
        self.assertEqual([i["code"] for i in ideas[0]["items"]], ["p1", "p2"])
        self.assertEqual(ideas[0]["items"][0]["note"], "毎日使う定番です。")
        self.assertTrue(any("itemCode=p1" in u for u, _ in t.urls))
        self.assertEqual(data["stats"]["replaced"], 0)

    def test_the_daily_picks_of_the_newest_days_are_looked_up_again_and_a_gone_one_is_left_out_of_the_data(self):
        import copy
        day = json.loads((CONTENT_DIR_REAL / "daily" / "2026-10-11.json").read_text(encoding="utf-8"))
        content = dict(CONTENT)
        content["daily"] = [day]
        gone = (day["rakuten"][2]["code"],)
        t = FakeTransport(lambda u: item_for(u, gone, ()))
        data = refresh.refresh(content, client(t), {k: copy.deepcopy(v) for k, v in PICKS.items()}, now=datetime(2026, 10, 11, 7, 0))
        self.assertEqual(sorted(data["daily"]), sorted(e["code"] for i, e in enumerate(day["rakuten"]) if e["code"] not in gone))
        self.assertTrue(all(any(f"itemCode={e['code'].replace(':', '%3A')}" in u or f"itemCode={e['code']}" in u for u, _ in t.urls) for e in day["rakuten"]))
        self.assertEqual(refresh.dp.rakuten_codes([]), [])                       # no day files: nothing to look up

    def test_a_pick_that_is_gone_or_sold_out_is_replaced_by_the_first_good_backup(self):
        data, _ = self.run_refresh(gone=("p1",), sold_out=("b1",))
        codes = [i["code"] for i in data["pairs"]["birthday-boyfriend"]["ideas"][0]["items"]]
        self.assertEqual(codes, ["p2", "b2"])        # p1 is gone, b1 is sold out: b2 steps in
        self.assertEqual(data["stats"]["replaced"], 1)
        self.assertEqual(data["stats"]["dropped"], 1)

    def test_an_idea_whose_picks_all_died_falls_back_to_the_keyword_search(self):
        data, _ = self.run_refresh(gone=("n1",))
        items = data["pairs"]["birthday-boyfriend"]["ideas"][1]["items"]
        self.assertTrue(items and all(i["code"].startswith("s") for i in items))
        self.assertEqual(data["stats"]["searched_ideas"], 2)   # that idea, and the mother page's idea (its only pick died too: f1 is looked up but backups are used first)

    def test_picks_that_do_not_fit_the_person_are_swapped_out(self):
        def transport(url):
            res = item_for(url)
            if "itemCode=f1" in url:
                res[0]["itemName"] = "レディース 花柄 ストール"   # fine for a mother
            if "itemCode=p1" in url:
                res[0]["itemName"] = "レディース 長財布"          # wrong for a boyfriend
            return res
        data = refresh.refresh(CONTENT, client(FakeTransport(transport)), PICKS, now=datetime(2026, 10, 7, 7, 0))
        codes = [i["code"] for i in data["pairs"]["birthday-boyfriend"]["ideas"][0]["items"]]
        self.assertNotIn("p1", codes)
        self.assertIn("b1", codes)

    def test_pages_without_picks_still_get_products(self):
        data = refresh.refresh(CONTENT, client(FakeTransport(lambda u: item_for(u))), {}, now=datetime(2026, 10, 7, 7, 0))
        self.assertTrue(all(any(i["items"] for i in v["ideas"]) for v in data["pairs"].values()))


class CandidatesTest(unittest.TestCase):
    def test_the_shortlist_has_fitting_products_per_idea_without_repeats(self):
        found = [raw_item(f"c{i}", 2000 + i, f"s{i}") for i in range(20)] + [raw_item("m1", 2000, "sx", name="メンズ 財布")]
        data = fetch.candidates(CONTENT, client(FakeTransport(lambda u: found)), now=datetime(2026, 10, 7, 7, 0))
        lists = data["pairs"]["mothers-day-mother"]
        self.assertEqual(len(lists), 1)
        codes = [i["code"] for i in lists[0]]
        self.assertEqual(len(codes), fetch.CANDIDATES_PER_IDEA)
        self.assertNotIn("m1", codes)
        bf = data["pairs"]["birthday-boyfriend"]
        self.assertFalse({i["code"] for i in bf[0]} & {i["code"] for i in bf[1]})

    def test_a_thin_idea_is_topped_up_with_the_pages_other_keywords(self):
        import urllib.parse
        import copy
        content = copy.deepcopy(CONTENT)
        pair = next(p for p in content["pairs"] if p["occasion"] == "mothers-day")
        kw = "上質 ハンカチ 母"
        pair["keywords"] = [kw]
        few = [raw_item(f"f{i}", 2000 + i, f"s{i}") for i in range(3)]
        many = [raw_item(f"k{i}", 2000 + i, f"t{i}") for i in range(20)]
        asked = []

        def transport(url):
            asked.append(url)
            return many if urllib.parse.quote_plus(kw) in url else few
        data = fetch.candidates(content, client(FakeTransport(transport)), limit_pairs=None, now=datetime(2026, 10, 7, 7, 0))
        codes = [i["code"] for i in data["pairs"]["mothers-day-mother"][0]]
        self.assertGreaterEqual(len(codes), fetch.CANDIDATES_MIN)
        self.assertTrue(any(c.startswith("k") for c in codes))
        self.assertTrue(any("sort=-reviewCount" in u for u in asked))

    def test_new_only_keeps_existing_shortlists_and_searches_the_rest(self):
        asked = []

        def transport(url):
            asked.append(url)
            return [raw_item(f"n{i}", 2000 + i, f"s{i}") for i in range(20)]
        keep = [{"code": "old1", "name": "古い候補"}]
        existing = {"pairs": {"mothers-day-mother": [keep]}}
        data = fetch.candidates(CONTENT, client(FakeTransport(transport)), existing=existing, now=datetime(2026, 10, 7, 7, 0))
        self.assertEqual(data["pairs"]["mothers-day-mother"], [keep])
        self.assertIn("birthday-boyfriend", data["pairs"])
        self.assertTrue(asked)


if __name__ == "__main__":
    unittest.main()
