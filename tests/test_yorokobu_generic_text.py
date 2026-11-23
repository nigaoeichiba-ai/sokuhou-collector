import json
import re
import unittest
from pathlib import Path

from sites.yorokobu import relevance

CONTENT = Path(__file__).resolve().parent.parent / "sites" / "yorokobu" / "content"
PERSON = re.compile(r"妻|夫|母|父|彼氏|彼女|祖父|祖母|息子|娘")


def load(name):
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


class GenericTextTest(unittest.TestCase):
    def test_amazon_pick_without_recipients_names_no_person(self):
        """A pick that is shown to every recipient of an occasion must not say who it suits (a Kindle 'for a wife' was shown on the teen page, 2026-11-23)."""
        for p in load("amazon_picks.json")["picks"]:
            if not p.get("recipients"):
                self.assertIsNone(PERSON.search(p["why"]), p["asin"] + ": " + p["why"])

    def test_birthday_occasion_text_names_no_person(self):
        """The birthday text is on every birthday page (teen, wife, mother ...): no one person in it."""
        o = next(x for x in load("occasions.json")["occasions"] if x["slug"] == "birthday")
        for k in ("blurb", "timing", "tips", "avoid", "portrait_note"):
            v = o.get(k)
            v = " ".join(v) if isinstance(v, list) else (v or "")
            self.assertIsNone(PERSON.search(v), k + ": " + v)

    def test_child_art_label_idea_takes_label_stickers_and_not_bottle_or_beauty_labels(self):
        t = next(x for x in load("themes.json")["themes"] if x["slug"] == "child-art-keepsakes")
        idea = next(i for i in t["ideas"] if i["label"] == "作品ラベル")
        ok = lambda name: relevance.fits_idea(name, idea["must"], idea.get("not"))
        self.assertTrue(ok("作品用 ネームシール 防水 300枚"))
        self.assertTrue(ok("お名前シール 耐水 ラベルシール"))
        self.assertFalse(ok("ワイン ボトル ラベル 300ml"))          # the former loose word 「ラベル」 let this through
        self.assertFalse(ok("ラベル ヘアアイロン 32mm サロン"))
        self.assertFalse(ok("ラベル 300ml"))


if __name__ == "__main__":
    unittest.main()
