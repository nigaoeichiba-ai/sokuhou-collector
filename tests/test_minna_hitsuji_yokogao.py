"""みんなのイラスト: the sheep side-view guide (2026-11-14).  The size table is recomputed a second way from each series' own json; the facing directions
were checked by opening the images (head faces right, the six silhouettes face left)."""
import json
import unittest
from pathlib import Path

from tests.test_minna_sitecache import shared_site

LIB = Path(__file__).resolve().parents[1] / "sites" / "minna" / "library"


def item(series, name):
    d = json.loads((LIB / series / "series.json").read_text(encoding="utf-8"))
    return [i for i in d["items"] if i["id"] == f"{series}-{name}"][0]


class HitsujiYokogao(unittest.TestCase):
    def page(self) -> str:
        out, _ = shared_site()
        return (out / "guide" / "hitsuji-yokogao" / "index.html").read_text(encoding="utf-8")

    def test_size_table_matches_the_series_data(self):
        html = self.page()
        names = [("cool-sheep-pop", "head")] + [("eto-sheep-silhouette", n) for n in ("stand", "walk", "jump", "lie", "lamb", "pair")]
        for s, n in names:
            i = item(s, n)
            w, h = i["w"], i["h"]
            self.assertIn(f"{w}×{h}px", html, i["id"])
            self.assertIn(f"{round(w / 300 * 25.4)}×{round(h / 300 * 25.4)}mm", html, i["id"])
            self.assertIn(f"{round(w / 150 * 25.4)}×{round(h / 150 * 25.4)}mm", html, i["id"])

    def test_links_both_ways_and_series_exist(self):
        out, _ = shared_site()
        html = self.page()
        for p in ("/series/cool-sheep-pop/", "/series/eto-sheep-silhouette/", "/guide/shoyo-license/"):
            self.assertIn(f'href="{p}"', html)
        self.assertIn("/guide/hitsuji-yokogao/", (out / "guide" / "eto-ichiran" / "index.html").read_text(encoding="utf-8"))
        self.assertIn("/guide/hitsuji-yokogao/", (out / "guide" / "index.html").read_text(encoding="utf-8"))
        self.assertIn("/guide/hitsuji-yokogao/", (out / "sitemap.xml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
