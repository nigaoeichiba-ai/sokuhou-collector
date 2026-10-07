"""The illustration factory of みんなのイラスト: specs, the sheet cutter, ingest and the brief for the image generator."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from sites.minna import factory, sheetkit

KEY = (255, 0, 255)


def make_sheet(cols=3, rows=2, n=None, vignette=False, touch_edge=False, size=(900, 600), bg=KEY):
    """A synthetic sheet: soft-edged discs (brown outline, cream inside) on the key colour, one per cell."""
    w, h = size
    k3 = 3                                        # drawn 3x larger and shrunk, so the edges are anti-aliased like a generated picture
    im = Image.new("RGB", (w * k3, h * k3), bg)
    d = ImageDraw.Draw(im)
    n = cols * rows if n is None else n
    for k in range(n):
        cx = (k % cols + 0.5) * w / cols
        cy = (k // cols + 0.5) * h / rows
        r = min(w / cols, h / rows) * 0.32
        if touch_edge and k == 0:
            cx, cy = r - 4, r - 4
        d.ellipse([(cx - r) * k3, (cy - r) * k3, (cx + r) * k3, (cy + r) * k3], fill=(91, 58, 41))
        d.ellipse([(cx - r + 8) * k3, (cy - r + 8) * k3, (cx + r - 8) * k3, (cy + r - 8) * k3], fill=(255, 244, 214))
    im = im.resize((w, h), Image.LANCZOS)
    if vignette:
        arr = np.asarray(im).astype(np.float32)
        yy, xx = np.mgrid[0:h, 0:w]
        fade = (np.hypot(xx - w / 2, yy - h / 2) / np.hypot(w / 2, h / 2))[..., None]
        arr = arr * (1 - 0.55 * fade) + np.array([90, 60, 40], np.float32) * 0.55 * fade
        im = Image.fromarray(arr.astype(np.uint8))
    return im


def make_frame_sheet(smudge: bool):
    """Six square frames (red ring, brown outline) whose middle is plain white or a dark soft smudge, like a generator returns."""
    k3 = 3
    w, h = 900, 600
    im = Image.new("RGB", (w * k3, h * k3), (255, 255, 255))
    d = ImageDraw.Draw(im)
    for k in range(6):
        cx, cy = (k % 3 + 0.5) * w / 3, (k // 3 + 0.5) * h / 2
        r = 110
        d.rectangle([(cx - r) * k3, (cy - r) * k3, (cx + r) * k3, (cy + r) * k3], fill=(91, 58, 41))
        d.rectangle([(cx - r + 6) * k3, (cy - r + 6) * k3, (cx + r - 6) * k3, (cy + r - 6) * k3], fill=(225, 70, 90))
        d.rectangle([(cx - r + 36) * k3, (cy - r + 36) * k3, (cx + r - 36) * k3, (cy + r - 36) * k3], fill=(91, 58, 41))
        d.rectangle([(cx - r + 40) * k3, (cy - r + 40) * k3, (cx + r - 40) * k3, (cy + r - 40) * k3], fill=(255, 255, 255))
    im = im.resize((w, h), Image.LANCZOS)
    if smudge:
        arr = np.asarray(im).astype(np.float32)
        for k in range(6):
            cx, cy = int((k % 3 + 0.5) * w / 3), int((k // 3 + 0.5) * h / 2)
            yy, xx = np.mgrid[0:h, 0:w]
            fade = np.clip(1 - np.hypot(xx - cx, yy - cy) / 70, 0, 1)[..., None]
            inside = (np.abs(xx - cx) < 68) & (np.abs(yy - cy) < 68)
            arr = np.where(inside[..., None], arr * (1 - 0.8 * fade) + np.array([90, 60, 40], np.float32) * 0.8 * fade, arr)
        im = Image.fromarray(arr.astype(np.uint8))
    return im


class SpecsTest(unittest.TestCase):
    def test_every_spec_in_the_repo_is_valid_and_ids_are_unique(self):
        specs = factory.load_specs()          # raises SpecError on any problem
        self.assertGreater(len(specs), 20)
        ids = [factory.item_id(s, it[0]) for s in specs for it in s["items"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_a_bad_spec_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            base = {"slug": "x-y", "title": "t", "genre": "animals", "touch": "kawaii", "lead": "l", "items": [[f"i{k}", "ja", "en"] for k in range(6)]}
            for name, patch, msg in (("x-y", {"genre": "nope"}, "unknown genre"), ("x-y", {"touch": "nope"}, "unknown touch"), ("x-y", {"items": base["items"][:5]}, "multiple"),
                                     ("other", {}, "slug"), ("x-y", {"items": base["items"][:5] + [["i0", "ja", "en"]]}, "duplicate"), ("x-y", {"lead": ""}, "missing lead")):
                p = Path(t) / f"{name}.json"
                p.write_text(json.dumps({**base, **patch}), encoding="utf-8")
                with self.assertRaises(factory.SpecError, msg=msg) as cm:
                    factory.load_spec(p)
                self.assertIn(msg.split()[0], str(cm.exception))


class SheetKitTest(unittest.TestCase):
    def cut(self, im, cols=3, rows=2):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "s.png"
            im.save(p)
            return sheetkit.slice_sheet(p, cols, rows, "#FF00FF")

    def test_a_good_sheet_is_cut_into_transparent_pieces_in_reading_order(self):
        pieces, info = self.cut(make_sheet())
        self.assertEqual(len(pieces), 6)
        self.assertNotIn("count_problem", info)
        for p in pieces:
            self.assertEqual(p.image.mode, "RGBA")
            self.assertEqual(p.image.getpixel((0, 0))[3], 0)                       # corner is transparent
            self.assertEqual(p.problems, [])
        xs = [p.bbox[0] for p in pieces]
        self.assertEqual(xs[:3], sorted(xs[:3]))
        self.assertLess(pieces[0].bbox[1], pieces[3].bbox[1])                      # first row before second

    def test_key_colour_is_gone_from_the_edges(self):
        pieces, _ = self.cut(make_sheet())
        arr = np.asarray(pieces[0].image).astype(int)
        edge = (arr[..., 3] > 0) & (arr[..., 3] < 255)
        self.assertTrue(edge.any())
        pink = (arr[..., 0] > 200) & (arr[..., 1] < 80) & (arr[..., 2] > 200) & edge
        self.assertFalse(pink.any(), "magenta fringe left on the soft edge")

    def test_a_wrong_count_is_reported(self):
        _, info = self.cut(make_sheet(n=5))
        self.assertIn("expected 6", info["count_problem"])

    def test_a_vignette_background_is_cut_by_growing_it_from_the_frame(self):
        pieces, info = self.cut(make_sheet(vignette=True))
        self.assertEqual(info["method"], "flood")
        self.assertEqual(len(pieces), 6)
        self.assertNotIn("count_problem", info)
        self.assertEqual(pieces[0].image.getpixel((0, 0))[3], 0)
        # the cream inside of the disc must survive (not eaten by the background growth)
        c = pieces[0].image
        self.assertEqual(c.getpixel((c.width // 2, c.height // 2))[3], 255)

    def test_frames_get_a_transparent_middle_even_when_the_generator_smudges_it(self):
        for smudge in (False, True):
            with tempfile.TemporaryDirectory() as t:
                p = Path(t) / "s.png"
                make_frame_sheet(smudge).save(p)
                pieces, info = sheetkit.slice_sheet(p, 3, 2, "#FFFFFF", holes=True)
            self.assertEqual(len(pieces), 6, smudge)
            c = pieces[0].image
            self.assertEqual(c.getpixel((c.width // 2, c.height // 2))[3], 0, f"middle not transparent (smudge={smudge})")
            self.assertEqual(c.getpixel((c.width // 2 - 92, c.height // 2))[3], 255, "the frame itself must stay opaque")

    def test_without_the_holes_flag_a_plain_white_middle_is_kept(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "s.png"
            make_frame_sheet(False).save(p)
            pieces, _ = sheetkit.slice_sheet(p, 3, 2, "#FFFFFF", holes=False)
        c = pieces[0].image
        self.assertEqual(c.getpixel((c.width // 2, c.height // 2))[3], 255)

    def test_an_illustration_on_the_sheet_edge_is_flagged(self):
        pieces, _ = self.cut(make_sheet(touch_edge=True))
        self.assertTrue(any("edge" in q for p in pieces for q in p.problems))


class IngestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.old = (factory.SPECS, factory.LIBRARY)
        factory.SPECS, factory.LIBRARY = t / "specs", t / "library"
        factory.SPECS.mkdir()
        self.sheets = t / "sheets"
        self.sheets.mkdir()
        spec = {"slug": "tst-pose", "title": "テスト", "genre": "animals", "touch": "kawaii", "lead": "リード", "subject": "テスト", "tags": ["てすと"],
                "items": [[f"p{k}", f"ポーズ{k}", f"pose {k}"] for k in range(6)]}
        (factory.SPECS / "tst-pose.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        factory.SPECS, factory.LIBRARY = self.old
        self.tmp.cleanup()

    def ingest(self):
        import argparse
        factory.cmd_ingest(argparse.Namespace(series=None, sheets_dir=str(self.sheets)))

    def test_ingest_files_the_items_and_writes_series_json(self):
        make_sheet().save(self.sheets / "tst-pose__01.png")
        self.ingest()
        d = json.loads((factory.LIBRARY / "tst-pose" / "series.json").read_text(encoding="utf-8"))
        self.assertEqual([i["id"] for i in d["items"]], [f"tst-pose-p{k}" for k in range(6)])
        self.assertEqual(d["items"][0]["title"], "ポーズ0テスト")
        self.assertTrue((factory.LIBRARY / "tst-pose" / "tst-pose-p3.webp").exists())
        self.assertEqual(json.loads((self.sheets / "retry.json").read_text()), [])

    def test_a_bad_sheet_is_rejected_and_nothing_is_filed(self):
        make_sheet(n=5).save(self.sheets / "tst-pose__01.png")
        self.ingest()
        self.assertFalse((factory.LIBRARY / "tst-pose").exists())
        retry = json.loads((self.sheets / "retry.json").read_text())
        self.assertEqual(retry[0]["sheet"], "tst-pose__01")
        self.assertIn("expected 6", retry[0]["problem"])

    def test_brief_lists_only_sheets_still_to_draw(self):
        import argparse
        out = Path(self.tmp.name) / "b.md"
        factory.cmd_brief(argparse.Namespace(series=None, sheets_dir=str(self.sheets), out=str(out), limit=None))
        text = out.read_text(encoding="utf-8")
        self.assertIn("tst-pose__01.png", text)
        self.assertIn("ABSOLUTELY NO text", text)
        self.assertIn("pose 5", text)
        make_sheet().save(self.sheets / "tst-pose__01.png")
        self.ingest()
        with self.assertRaises(SystemExit):
            factory.cmd_brief(argparse.Namespace(series=None, sheets_dir=str(self.sheets), out=str(out), limit=None))


if __name__ == "__main__":
    unittest.main()
