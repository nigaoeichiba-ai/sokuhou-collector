"""The numbers written in sites/minna/library/icon-animals-round-flat/guide.json: how much of each picture lies outside the circle whose diameter is the picture's shorter side (centred on the picture)."""
import json
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

LIB = Path(__file__).resolve().parent.parent / "sites" / "minna" / "library" / "icon-animals-round-flat"
STATED = {"neko": 4.1, "inu": 3.4, "usagi": 23.1, "kuma": 10.8, "kitsune": 4.2, "panda": 12.3, "tanuki": 5.2, "risu": 5.0, "fukuro": 5.1, "penguin": 3.5, "kaeru": 8.7, "hitsuji": 0.8}


def outside(name: str) -> float:
    a = np.array(Image.open(LIB / f"icon-animals-round-flat-{name}.webp").convert("RGBA"))[:, :, 3] > 40
    h, w = a.shape
    yy, xx = np.mgrid[0:h, 0:w]
    r = min(w, h) / 2
    inside = ((xx - w / 2) ** 2 + (yy - h / 2) ** 2) <= r * r
    return float((a & ~inside).sum() / a.sum() * 100)


class RoundCrop(unittest.TestCase):
    def test_the_percentages_in_the_guide_are_the_measured_ones(self):
        for name, stated in STATED.items():
            self.assertAlmostEqual(outside(name), stated, delta=0.4, msg=name)

    def test_the_rabbit_is_the_one_that_sticks_out_most_and_the_sheep_the_least(self):
        m = {n: outside(n) for n in STATED}
        self.assertEqual(max(m, key=m.get), "usagi")
        self.assertEqual(min(m, key=m.get), "hitsuji")
        self.assertLess(m["hitsuji"], 1.0)

    def test_the_guide_says_what_was_measured(self):
        g = json.loads((LIB / "guide.json").read_text(encoding="utf-8"))
        text = " ".join(g["points"])
        for word in ("23%", "0.8%", "12%", "11%", "9%", "3.4%", "3.5%"):
            self.assertIn(word, text, word)


if __name__ == "__main__":
    unittest.main()
