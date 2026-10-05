import unittest

from sokuhou import prefectures, tilegrid


def adjacent(a, b):
    ax, ay = tilegrid.TILES[a]
    bx, by = tilegrid.TILES[b]
    return abs(ax - bx) + abs(ay - by) == 1


class TileGridTest(unittest.TestCase):
    def test_all_prefecture_slugs_are_present(self):
        self.assertEqual(set(tilegrid.TILES), set(prefectures.SLUG.values()))
        self.assertEqual(len(tilegrid.TILES), 47)

    def test_positions_are_unique_and_in_bounds(self):
        positions = list(tilegrid.TILES.values())
        self.assertEqual(len(positions), len(set(positions)))
        for col, row in positions:
            self.assertGreaterEqual(col, 0)
            self.assertLess(col, tilegrid.GRID_COLS)
            self.assertGreaterEqual(row, 0)
            self.assertLess(row, tilegrid.GRID_ROWS)

    def test_tiles_returns_source_order_triplets(self):
        expected = [(slug, *tilegrid.TILES[slug]) for slug in prefectures.SLUG.values()]
        self.assertEqual(tilegrid.tiles(), expected)

    def test_kanto_adjacency(self):
        self.assertTrue(adjacent("tokyo", "kanagawa"))
        self.assertTrue(adjacent("tokyo", "chiba"))
        self.assertTrue(adjacent("tokyo", "saitama"))

    def test_kinki_adjacency(self):
        self.assertTrue(adjacent("osaka", "hyogo"))
        self.assertTrue(adjacent("osaka", "kyoto"))
        self.assertTrue(adjacent("osaka", "nara"))
        self.assertTrue(adjacent("osaka", "wakayama"))

    def test_tohoku_adjacency(self):
        self.assertTrue(adjacent("aomori", "iwate") or adjacent("aomori", "akita"))
        self.assertTrue(adjacent("akita", "iwate") or adjacent("akita", "yamagata"))
