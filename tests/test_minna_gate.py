"""みんなのイラスト: the gate (sites/minna/gate.py) keeps a new set off the site until its thick page is ready, and never touches a set that was already published (owner decision 2026-10-29)."""
import json
import unittest
from pathlib import Path

from sites.minna import build, gate, setguides

PUB = set(json.loads(gate.PUBLISHED.read_text(encoding="utf-8"))["slugs"])


def real_set(slug: str):
    items, series = build.load_data()
    its = [i for i in items if i["series"] == slug]
    return items, series, its


def good_spec(its: list[dict], slug: str) -> dict:
    return {"why": "このセットの紹介です。" * 6, "frame": False,
            "picks": {i["id"][len(slug) + 1:]: "この素材の使いどころを書いた行です。" for i in its},
            "points": ["使い方の段落です。" * 16 for _ in range(4)],
            "examples": [("eto-lineup-kawaii-1", "見本1", [], "大きさ"), ("eto-lineup-kawaii-2", "見本2", [], "大きさ")]}


class Gate(unittest.TestCase):
    def test_the_published_list_is_every_set_that_was_on_the_site_and_each_exists(self):
        items, series = build.load_data()
        slugs = {s["slug"] for s in series if not s.get("legacy")}
        self.assertEqual(PUB - slugs, set(), "a published set is gone from the library")
        self.assertGreaterEqual(len(PUB), 285)

    def test_a_set_without_a_guide_that_is_not_published_is_held_back_with_its_pictures(self):
        items, series, its = real_set("koala-pose")
        log = []
        items2, series2, held = gate.apply(items, series, published=PUB - {"koala-pose"}, log=log.append)
        self.assertEqual(list(held), ["koala-pose"])
        self.assertIn("ガイドがない", held["koala-pose"][0])
        self.assertTrue(its)
        self.assertEqual([i for i in items2 if i["series"] == "koala-pose"], [])
        self.assertNotIn("koala-pose", [s["slug"] for s in series2])
        self.assertEqual(len(items) - len(items2), len(its))
        self.assertTrue(any(line.startswith("held back: koala-pose (") for line in log) or "koala-pose" in gate._logged)

    def test_a_published_set_and_a_legacy_set_are_never_held_back_whatever_their_guide(self):
        items, series, _ = real_set("koala-pose")
        _, series2, held = gate.apply(items, series, published=PUB, specs={}, log=lambda *_: None)
        self.assertEqual(held, {})
        self.assertEqual(len(series2), len(series))
        legacy = [s for s in series if s.get("legacy")]
        self.assertTrue(legacy)
        _, series3, held3 = gate.apply(items, series, published=set(), specs={}, log=lambda *_: None)
        self.assertTrue(all(s["slug"] in {x["slug"] for x in series3} for s in legacy))
        self.assertNotIn(legacy[0]["slug"], held3)

    def test_a_good_guide_lets_a_new_set_through(self):
        items, series, its = real_set("koala-pose")
        spec = good_spec(its, "koala-pose")
        self.assertEqual(gate.problems("koala-pose", its, spec), [])
        _, series2, held = gate.apply(items, series, published=PUB - {"koala-pose"}, specs={"koala-pose": spec}, log=lambda *_: None)
        self.assertEqual(held, {})
        self.assertIn("koala-pose", [s["slug"] for s in series2])

    def test_each_way_a_guide_can_be_too_thin_holds_the_set_back(self):
        _, _, its = real_set("koala-pose")
        slug = "koala-pose"
        for name, edit, needle in [
            ("a picture without a line", lambda s: s["picks"].pop(next(iter(s["picks"]))), "行のない素材"),
            ("a line without a picture", lambda s: s["picks"].update({"ghost": "どこにもない素材の行です。"}), "素材のない行"),
            ("a line that is nothing", lambda s: s["picks"].update({next(iter(s["picks"])): "x"}), "短すぎる"),
            ("a short introduction", lambda s: s.update({"why": "短い"}), "why"),
            ("three paragraphs", lambda s: s["points"].pop(), "段落が足りない"),
            ("four thin paragraphs", lambda s: s.update({"points": ["短い。"] * 4}), "段落が足りない"),
            ("one example", lambda s: s["examples"].pop(), "完成例が足りない"),
            ("an example without its file", lambda s: s["examples"].__setitem__(0, ("no-such-example", "x", [], "x")), "画像がない"),
            ("an unknown number in a paragraph", lambda s: s["points"].__setitem__(0, "数は{no_such_number}です。" * 40), "書き込み"),
        ]:
            spec = good_spec(its, slug)
            edit(spec)
            why = gate.problems(slug, its, spec)
            self.assertTrue(why and any(needle in w for w in why), f"{name}: {why}")

    def test_no_guide_at_all_is_a_reason_and_an_empty_dict_too(self):
        _, _, its = real_set("koala-pose")
        self.assertIn("ガイドがない", gate.problems("koala-pose", its, None)[0])
        self.assertIn("ガイドがない", gate.problems("koala-pose", its, {})[0])

    def test_the_seven_guides_of_2026_10_29_pass_the_gate_on_their_own_merits(self):
        items, _ = build.load_data()
        old_four = {"event-frames-flat", "bowing-greetings-flat", "winter-prep-year-end-flat", "eto-lineup-kawaii"}      # published before the gate, shorter, and safe by the published list
        seven = {k: v for k, v in setguides.GUIDES.items() if k not in old_four}
        self.assertEqual(len(seven), 7)
        for slug, spec in seven.items():
            its = [i for i in items if i["series"] == slug]
            self.assertEqual(gate.problems(slug, its, spec), [], slug)

    def test_the_build_leaves_a_held_set_out_of_the_data_the_site_is_made_from(self):
        items, series = build.load_data()
        self.assertEqual({i["series"] for i in items} - {s["slug"] for s in series}, set())
        self.assertGreaterEqual(len({s["slug"] for s in series if not s.get("legacy")}), 285)


class GateEndToEnd(unittest.TestCase):
    """A whole build with a made-up new set (three pictures of the koala set under new ids): it is not on the site, and the log says why."""

    def test_a_new_set_without_a_guide_is_not_in_the_built_site(self):
        import io
        import tempfile
        from contextlib import redirect_stdout
        from unittest import mock

        from sites.minna import model
        from tests.test_minna_sitecache import SHARED_CFG, SHARED_DAY
        real = model.load_library

        def with_new_set():
            items, series = real()
            koala = [i for i in items if i["series"] == "koala-pose"][:3]
            new = [dict(i, id=f"zz-new-{k}", title=f"新しい素材{k}", series="zz-new", tags=["zz-new-tag"]) for k, i in enumerate(koala)]
            series.append({"slug": "zz-new", "title": "新しいセット", "lead": "新しいセットです。使えます。", "genre": "animals", "touch": "kawaii", "tags": [], "season": None,
                           "added": "2026-10-29", "legacy": False, "url": "/series/zz-new/", "ids": [i["id"] for i in new]})
            return items + new, series

        gate._logged.discard("zz-new")
        buf = io.StringIO()
        with mock.patch.object(model, "load_library", with_new_set), tempfile.TemporaryDirectory() as tmp, redirect_stdout(buf):
            out = Path(tmp) / "site"
            files = build.render_site(SHARED_CFG, out, release=True, today=SHARED_DAY)
            self.assertIn("held back: zz-new (", buf.getvalue())
            self.assertFalse(any("zz-new" in f for f in files))
            self.assertNotIn("zz-new", (out / "sitemap.xml").read_text(encoding="utf-8"))
            self.assertNotIn("zz-new", (out / "data" / "items.json").read_text(encoding="utf-8"))
            self.assertTrue((out / "series" / "koala-pose" / "index.html").exists())


if __name__ == "__main__":
    unittest.main()
