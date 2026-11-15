"""trend: the card of a 16:9 picture shows the whole picture (the title and the 「イメージです。」 at the edges are not cut off); a 3:2 picture is still cropped to the card.
The test picture has a red left edge and a blue right edge: the old centre crop loses both."""
from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "trend"
sys.path.insert(0, str(SITE))
spec = importlib.util.spec_from_file_location("trend_hooks_card", SITE / "hooks.py")
hooks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hooks)


def card_of(w, h):
    im = Image.new("RGB", (w, h), (255, 255, 255))
    for y in range(h):
        for x in range(0, w // 20):
            im.putpixel((x, y), (255, 0, 0))
            im.putpixel((w - 1 - x, y), (0, 0, 255))
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.png"
        im.save(p)
        return Image.open(io.BytesIO(hooks._jpeg_free_card(p))).convert("RGB")


class CardWholePicture(unittest.TestCase):
    def test_wide_picture_keeps_both_edges(self):
        c = card_of(1280, 720)
        self.assertEqual(c.size, (hooks.CARD_W, hooks.CARD_H))
        mid = c.height // 2
        left, right = c.getpixel((3, mid)), c.getpixel((c.width - 4, mid))
        self.assertGreater(left[0], 200)
        self.assertLess(left[1], 80)                # red at the left edge
        self.assertGreater(right[2], 200)
        self.assertLess(right[1], 80)               # blue at the right edge

    def test_three_by_two_picture_is_still_cropped_to_the_card(self):
        c = card_of(1280, 853)
        self.assertEqual(c.size, (hooks.CARD_W, hooks.CARD_H))
        self.assertGreater(c.getpixel((3, c.height // 2))[0], 200)


if __name__ == "__main__":
    unittest.main()
