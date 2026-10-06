"""Quality gate for the editorial copy of よろこぶプレゼント: no template skeletons, no claims we cannot back up."""
import re
import unittest
from collections import Counter

from sites.yorokobu import content as ct

FORBIDDEN_WORDS = ["調査", "%", "％", "人気", "ランキング", "No.1", "必ず", "絶対", "最高", "楽天", "アフィリ", "AI", "1位"]
TEMPLATE_PHRASES = ["視点を合わせると", "生活の中で出番がある", "節目に、相手をよく見て", "迷ったら普段の使い方に近いもの",
                    "好みが分からないときは高価さより", "使う場面が浮かぶ品なら", "候補を絞りやすくなります"]


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"[。!?!?]", text) if len(s) >= 25]


class ContentQualityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = ct.load()

    def texts(self):
        for o in self.c["occasions"]:
            yield f"occasion {o['slug']}", [o["blurb"], o["timing"], *o["tips"], *o["avoid"], o.get("portrait_note") or ""]
        for r in self.c["recipients"]:
            yield f"recipient {r['slug']}", [r["blurb"], *r["likes"], *r["avoid"]]
        for p in self.c["pairs"]:
            yield f"pair {ct.pair_key(p)}", [p["title"], p["lead"], *p["reasons"], *p["how_to_choose"], p.get("portrait_note") or ""]

    def test_counts(self):
        self.assertEqual(len(self.c["occasions"]), 24)
        self.assertEqual(len(self.c["recipients"]), 18)
        self.assertGreaterEqual(len(self.c["pairs"]), 100)

    def test_no_forbidden_words_or_template_phrases(self):
        bad = []
        for where, parts in self.texts():
            blob = " ".join(parts)
            bad += [(where, w) for w in FORBIDDEN_WORDS + TEMPLATE_PHRASES if w in blob]
        self.assertEqual(bad, [])

    def test_lengths(self):
        bad = []
        for p in self.c["pairs"]:
            k = ct.pair_key(p)
            if not 110 <= len(p["lead"]) <= 260:
                bad.append((k, "lead", len(p["lead"])))
            if len(p["reasons"]) != 3 or len(p["how_to_choose"]) != 3 or len(p["queries"]) != 3:
                bad.append((k, "counts"))
            bad += [(k, "reason", len(x)) for x in p["reasons"] if not 38 <= len(x) <= 140]
            bad += [(k, "how", len(x)) for x in p["how_to_choose"] if not 28 <= len(x) <= 130]
            if not 3 <= len(p["tiers"]) <= 5:
                bad.append((k, "tiers"))
        self.assertEqual(bad, [])

    def test_leads_do_not_share_openings(self):
        openings = Counter(p["lead"][:8] for p in self.c["pairs"])
        self.assertEqual([k for k, v in openings.items() if v > 2], [])

    def test_no_long_sentence_is_repeated_across_pages(self):
        seen = Counter()
        for p in self.c["pairs"]:
            for s in set(sum((sentences(t) for t in [p["lead"], *p["reasons"], *p["how_to_choose"]]), [])):
                seen[s] += 1
        self.assertEqual([s for s, n in seen.items() if n > 2], [])

    def test_every_page_has_four_distinct_ideas_with_a_search_phrase_and_a_reason(self):
        types = {"実用品", "食べもの・飲みもの", "体験・お出かけ", "思い出・名入れ", "癒し・リラックス", "おもしろ・サプライズ", "ファッション小物", "趣味・ホビー", "子ども向け"}
        bad = []
        for p in self.c["pairs"]:
            k = ct.pair_key(p)
            ideas = p["ideas"]
            if len(ideas) != 4 or len({i["label"] for i in ideas}) != 4 or len({i["query"] for i in ideas}) != 4:
                bad.append((k, "ideas"))
            for i in ideas:
                if i["type"] not in types or not 6 <= len(i["query"]) <= 30 or not 30 <= len(i["why"]) <= 95:
                    bad.append((k, i["label"]))
                if any(w in i["why"] + i["label"] for w in FORBIDDEN_WORDS):
                    bad.append((k, "forbidden", i["label"]))
            if len(p["keywords"]) < 6:
                bad.append((k, "keywords"))
        self.assertEqual(bad, [])

    def test_portrait_notes_are_limited(self):
        self.assertLessEqual(sum(1 for p in self.c["pairs"] if p.get("portrait_note")), 32)
        for where, parts in self.texts():
            for t in parts:
                self.assertNotIn("楽天", t)


if __name__ == "__main__":
    unittest.main()


class GuideQualityTest(unittest.TestCase):
    """The reading guides under /guide/: calm, factual, and complete (skipped until content/guides.json exists)."""

    @classmethod
    def setUpClass(cls):
        cls.c = ct.load()

    def test_every_guide_is_complete_and_clean(self):
        if not self.c["guides"]:
            self.skipTest("no guides yet")
        bad = []
        for slug, g in self.c["guides"].items():
            blob = " ".join([g["title"], g["intro"], *[s["h"] + s["body"] for s in g["sections"]], *g["checklist"], *[f["q"] + f["a"] for f in g["faq"]]])
            bad += [(slug, w) for w in FORBIDDEN_WORDS + TEMPLATE_PHRASES if w in blob]
            if not 100 <= len(g["intro"]) <= 220:
                bad.append((slug, "intro", len(g["intro"])))
            if len(g["sections"]) != 4 or len(g["checklist"]) != 5 or len(g["faq"]) != 3:
                bad.append((slug, "counts"))
            bad += [(slug, "section", len(s["body"])) for s in g["sections"] if not 170 <= len(s["body"]) <= 300]
        self.assertEqual(bad, [])

    def test_guides_do_not_repeat_each_other(self):
        sents = Counter(s for g in self.c["guides"].values() for sec in g["sections"] for s in sentences(sec["body"]))
        self.assertEqual([s for s, n in sents.items() if n > 1], [])
