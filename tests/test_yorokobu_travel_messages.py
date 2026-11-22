"""/travel/ の『宿泊を贈るときの一言メッセージ例』: travel_messages.json is validated, rendered with copy buttons, and the real file is valid."""
import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from sites.yorokobu import build, content
from tests.test_yorokobu_build import CFG, FIX

REAL = Path(build.__file__).parent / "content"


class TravelMessagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name) / "content"
        shutil.copytree(FIX, d)
        occs = json.loads((d / "occasions.json").read_text(encoding="utf-8"))
        cls.base = occs["occasions"][0]
        cls.slug = cls.base["slug"]
        cls.d = d

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def entry(self, **kw):
        e = {"occasion": self.slug, "intro": "旅の贈り物に添える一言です。", "sets": [{"to": "祖父母へ", "style": "やわらかい", "lines": ["ありがとう。ゆっくり楽しんできてね。"]}],
             "closing": ["いつもありがとう。"]}
        e.update(kw)
        return e

    def load(self, *entries):
        (self.d / "travel_messages.json").write_text(json.dumps({"travel_messages": list(entries)}, ensure_ascii=False), encoding="utf-8")
        return content.load(self.d)

    def test_valid_entries_are_loaded_by_occasion(self):
        c = self.load(self.entry())
        self.assertEqual(list(c["travel_messages"]), [self.slug])

    def test_unknown_occasion_missing_field_and_duplicate_stop_the_build(self):
        with self.assertRaises(content.BuildError):
            self.load(self.entry(occasion="no-such-occasion"))
        bad = self.entry()
        del bad["closing"]
        with self.assertRaises(content.BuildError):
            self.load(bad)
        with self.assertRaises(content.BuildError):
            self.load(self.entry(), self.entry())

    def test_travel_page_shows_the_messages_with_hidden_copy_buttons(self):
        c = self.load(self.entry())
        # the page shows an occasion only when it is one of TRAVEL_OCCASIONS, so point the list at the fixture's occasion for this test
        old = build.TRAVEL_OCCASIONS
        build.TRAVEL_OCCASIONS = (self.slug,)
        try:
            items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
            out = Path(self.tmp.name) / "site"
            build.render_site(c, items, CFG, out, release=True, today=date(2026, 5, 3))
        finally:
            build.TRAVEL_OCCASIONS = old
        t = (out / "travel/index.html").read_text(encoding="utf-8")
        self.assertIn("宿泊を贈るときの一言メッセージ例", t)
        self.assertEqual(t.count('class="msg-text"'), 2)                      # 1 line + 1 closing phrase
        self.assertIn("ゆっくり楽しんできてね。", t)
        self.assertEqual(t.count("data-copy hidden"), 2)

    def test_without_the_file_the_section_is_absent(self):
        (self.d / "travel_messages.json").unlink(missing_ok=True)
        c = content.load(self.d)
        self.assertEqual(c["travel_messages"], {})

    def test_the_real_file_covers_the_two_occasions_and_every_line_is_a_plain_sentence(self):
        data = json.loads((REAL / "travel_messages.json").read_text(encoding="utf-8"))["travel_messages"]
        self.assertEqual([m["occasion"] for m in data], ["respect-for-aged-day", "wedding-anniversary"])
        for m in data:
            for s in m["sets"]:
                for ln in s["lines"]:
                    self.assertTrue(ln.endswith(("。", "ね。")), ln)
                    self.assertLessEqual(len(ln), 60, ln)
