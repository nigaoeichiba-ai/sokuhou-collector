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

    def test_portrait_notes_are_limited(self):
        self.assertLessEqual(sum(1 for p in self.c["pairs"] if p.get("portrait_note")), 32)
        for where, parts in self.texts():
            for t in parts:
                self.assertNotIn("楽天", t)


if __name__ == "__main__":
    unittest.main()
