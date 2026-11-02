"""2026-11-02: the daily picks could not be written: the candidates came only from the top 10 places of each genre's ranking, 53 products after the 30 days of rest, bunched in
wedding, wine and baby goods.  Now: the whole kept ranking, the age-and-sex lists, the editors' shortlist and the pages' products are sources; the rest period is shortened step by
step while the pool is small; and a product comes from one place once.  (All of it is read from data/, the private store's files; the tests use made-up products.)"""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import date
from pathlib import Path
from unittest import mock

from sites.yorokobu import pickresearch as pr


def prod(code, price=2000, reviews=100, rating=4.6, url=None):
    return {"code": code, "name": f"商品{code}", "price": price, "reviews": reviews, "rating": rating, "shop": "店", "url": url or f"https://item.rakuten.co.jp/{code.replace(':', '/')}/?x=1"}


def files(root: Path, genres=3, per_genre=20, people=2, cands=2, page_items=3):
    seg = {}
    for g in range(genres):
        seg[f"g-{g}"] = {"kind": "genre", "label": f"ジャンル{g}", "items": [prod(f"s{g}:{i}") for i in range(per_genre)]}
    for p in range(people):
        seg[f"f{p}"] = {"kind": "people", "label": f"世代{p}", "items": [prod(f"p{p}:{i}") for i in range(10)]}
    (root / "yorokobu_ranking.json").write_text(json.dumps({"segments": seg}), encoding="utf-8")
    (root / "yorokobu_candidates.json").write_text(json.dumps({"pairs": {f"k{c}": [[prod(f"c{c}:{i}") for i in range(8)], [prod(f"d{c}:{i}") for i in range(8)]] for c in range(cands)}}), encoding="utf-8")
    (root / "yorokobu_items.json").write_text(json.dumps({"pairs": {"pg": {"ideas": [{"items": [prod(f"i{n}:{i}") for i in range(page_items)]} for n in range(3)], "tiers": {}}}}), encoding="utf-8")


def run(root, used_by_window, n=500, **kw):
    err = io.StringIO()
    with mock.patch.object(pr, "used_codes", lambda w, today=None: used_by_window(w)), redirect_stderr(err):
        out = pr.candidates(n, root=root, today=date(2026, 11, 2), **kw)
    return out, err.getvalue()


class CandidatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        files(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_source_adds_products_and_a_product_is_there_once(self):
        out, err = run(self.root, lambda w: set(), min_pool=10)
        by = {}
        for it in out:
            by[it["src"]] = by.get(it["src"], 0) + 1
        self.assertEqual(set(by), {"ranking-genre", "ranking-people", "candidates", "pages"})
        self.assertEqual(len(out), len({it["code"] for it in out}))
        self.assertEqual(by["ranking-genre"], 60)                  # the whole kept ranking, not the first 10 places of each genre
        self.assertIn("ranking-genre", err)

    def test_the_products_are_spread_over_genres_not_one_genre_after_the_other(self):
        out, _ = run(self.root, lambda w: set(), min_pool=10)
        first = [f'{it["src"]}|{it["genre"]}' for it in out[:6]]
        self.assertEqual(len(set(first)), 6)

    def test_used_products_and_weak_ones_are_left_out(self):
        weak = json.loads((self.root / "yorokobu_ranking.json").read_text(encoding="utf-8"))
        weak["segments"]["g-0"]["items"][0] = prod("w:1", price=500)
        weak["segments"]["g-0"]["items"][1] = prod("w:2", reviews=5)
        weak["segments"]["g-0"]["items"][2] = prod("w:3", rating=4.0)
        (self.root / "yorokobu_ranking.json").write_text(json.dumps(weak), encoding="utf-8")
        out, _ = run(self.root, lambda w: {"s1:0", "s1:1"}, min_pool=10)
        codes = {it["code"] for it in out}
        self.assertFalse(codes & {"w:1", "w:2", "w:3", "s1:0", "s1:1"})

    def test_the_rest_period_is_shortened_while_the_pool_is_small(self):
        windows = []
        recent = {f"s{g}:{i}" for g in range(3) for i in range(20)}              # everything of the ranking was used in the last 30 days (and 21)

        def used(w):
            windows.append(w)
            return recent if w >= 21 else set()
        out, err = run(self.root, used, min_pool=70)
        self.assertEqual(windows, [30, 21, 14])
        self.assertIn("rest 14 days", err)
        self.assertGreaterEqual(len(out), 70)

    def test_when_the_pool_is_enough_the_period_stays_at_30_days(self):
        windows = []
        run(self.root, lambda w: windows.append(w) or set(), min_pool=10)
        self.assertEqual(windows, [30])

    def test_a_missing_file_is_a_source_with_nothing_in_it(self):
        (self.root / "yorokobu_candidates.json").unlink()
        (self.root / "yorokobu_items.json").unlink()
        out, _ = run(self.root, lambda w: set(), min_pool=10)
        self.assertEqual({it["src"] for it in out}, {"ranking-genre", "ranking-people"})
        empty = Path(tempfile.mkdtemp())
        self.assertEqual(run(empty, lambda w: set(), min_pool=10)[0], [])

    def test_the_old_rule_would_have_left_few_products(self):                 # negative: only the first 10 places of each genre
        out, _ = run(self.root, lambda w: set(), min_pool=10)
        old = [it for it in out if it["src"] == "ranking-genre" and it["rank"] < 10]
        self.assertEqual(len(old), 30)
        self.assertGreater(len(out), 2 * len(old))

    def test_the_url_of_a_product_is_found_in_the_shortlist_too(self):
        real = pr.sources
        with mock.patch.object(pr, "sources", lambda root=None: real(self.root)):
            self.assertTrue(pr.item_url("c0:3", {"segments": {}}).startswith("https://item.rakuten.co.jp/c0/3/"))
            self.assertIsNone(pr.item_url("zz:9", {"segments": {}}))


if __name__ == "__main__":
    unittest.main()
