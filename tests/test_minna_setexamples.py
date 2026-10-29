"""みんなのイラスト: the guides live in library/<slug>/guide.json and the examples can be drawn from a description (card, grid, strip, poster) with the set's own pictures, never enlarged
(2026-10-29: the factory writes both with a new set, and the gate holds the set back until they are there)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from sites.minna import setexamples, setguides

KOALA = setexamples.LIB / "koala-pose"


def nonwhite(im: Image.Image) -> int:
    return sum(1 for px in im.convert("RGB").resize((148, 219)).getdata() if px != (255, 255, 255))


class GuideFiles(unittest.TestCase):
    def test_every_guide_is_a_file_of_its_set_and_the_python_file_holds_none(self):
        files = sorted(p.parent.name for p in setexamples.LIB.glob("*/guide.json"))
        self.assertEqual(files, sorted(setguides.GUIDES))
        self.assertEqual(len(files), 11)
        for f in setexamples.LIB.glob("*/guide.json"):
            g = json.loads(f.read_text(encoding="utf-8"))
            self.assertTrue({"why", "picks", "points", "examples"} <= set(g), f.parent.name)
            for e in g["examples"]:
                self.assertTrue({"name", "caption"} <= set(e), f.parent.name)
        src = Path(setguides.__file__).read_text(encoding="utf-8")
        self.assertNotIn('"tropical-fruits-flat": {', src)


def _fallback_font(size: int, weight: int = 500):
    from PIL import ImageFont
    return ImageFont.load_default(size)


class DeclarativeExamples(unittest.TestCase):
    """The drawing needs a Japanese font (Noto Sans JP); a machine without one (the CI runner) draws the same layout with PIL's built-in font, which is enough to check sizes and fit."""

    def setUp(self):
        if not any(Path(p).exists() for p in setexamples.FONT_PATHS):
            patcher = mock.patch.object(setexamples, "font", _fallback_font)
            patcher.start()
            self.addCleanup(patcher.stop)

    def spec(self, kind: str) -> dict:
        items = [{"item": k, "label": k, "sub": "○円"} for k in ("sleep", "wave", "jump", "run")]
        return {"card": {"type": "card", "size": "hagaki", "title": {"text": "見出し", "size": 48, "colour": "accent"}, "item": "sleep", "scale": 1.0, "top": 170,
                         "lines": [{"text": "一行目", "size": 28, "y": 700}]},
                "grid": {"type": "grid", "size": "hagaki", "title": {"text": "一覧"}, "items": items, "cols": 2, "scale": 0.4, "top": 120},
                "strip": {"type": "strip", "size": "wide", "title": {"text": "一日"}, "items": items, "scale": 0.5, "top": 100},
                "poster": {"type": "poster", "size": "hagaki", "title": {"text": "予定"}, "rows": items[:3], "scale": 0.2}}[kind]

    def test_each_type_draws_a_page_of_the_asked_size_with_something_on_it(self):
        sizes = {"card": (592, 876), "grid": (592, 876), "strip": (1168, 592), "poster": (592, 876)}
        for kind, size in sizes.items():
            im = setexamples.render_spec("koala-pose", self.spec(kind))
            self.assertEqual(im.size, size, kind)
            self.assertGreater(nonwhite(im), 400, kind)

    def test_a_picture_is_never_enlarged_and_one_that_does_not_fit_stops_the_drawing(self):
        with self.assertRaises(AssertionError):
            setexamples.pic("koala-pose", "koala-pose-sleep", 1.5)
        big = self.spec("card")
        big["size"] = [300, 300]
        with self.assertRaises(AssertionError):
            setexamples.render_spec("koala-pose", big)
        tight = self.spec("grid")
        tight["scale"] = 1.0
        with self.assertRaises(AssertionError):
            setexamples.render_spec("koala-pose", tight)

    def test_an_unknown_type_is_refused(self):
        with self.assertRaises(ValueError):
            setexamples.render_spec("koala-pose", {"type": "collage"})

    def test_render_slug_draws_only_the_examples_that_have_a_spec_into_the_examples_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib, out = Path(tmp) / "lib", Path(tmp) / "out"
            (lib / "koala-x").mkdir(parents=True)
            for k in ("sleep", "wave", "jump", "run"):
                shutil.copy(KOALA / f"koala-pose-{k}.webp", lib / "koala-x" / f"koala-x-{k}.webp")
            guide = {"why": "x", "picks": {}, "points": [], "examples": [
                {"name": "koala-x-1", "caption": "c", "spec": self.spec("card")}, {"name": "koala-x-2", "caption": "c"}]}
            (lib / "koala-x" / "guide.json").write_text(json.dumps(guide, ensure_ascii=False), encoding="utf-8")
            with mock.patch.object(setexamples, "LIB", lib), mock.patch.object(setexamples, "OUT", out):
                done = setexamples.render_slug("koala-x")
            self.assertEqual(done, ["koala-x-1"])
            self.assertEqual(sorted(p.name for p in out.iterdir()), ["koala-x-1.webp"])
            self.assertEqual(Image.open(out / "koala-x-1.webp").size, (592, 876))


if __name__ == "__main__":
    unittest.main()
