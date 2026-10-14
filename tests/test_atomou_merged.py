"""atomou: one event listed under two titles (data/atomou/merged.json) shows once.  The list is checked against the data: the title that stays exists, the one that goes is still in the seed files
(otherwise the line is stale), and a drop never happens when the kept title is missing."""
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import catalog  # noqa: E402

TODAY = date(2026, 10, 13)


def seed(title, d="2027-02-07", **kw):
    it = {"title": title, "date": d, "kind": "開催", "group": "スポーツ", "category": "マラソン", "subject": "マラソン", "what": "大会の日", "place": "香川県", "source_url": "https://official.example/" + hashlib.sha1((title + d).encode("utf-8")).hexdigest()[:8],
          "source_quote": "2027年2月7日", "verified": True, "checked_on": "2026-10-12", "precision": "day"}
    it.update(kw)
    return it


def build_in(tmp, seeds, merged):
    d = Path(tmp)
    (d / "seed_t.json").write_text(json.dumps(seeds, ensure_ascii=False), encoding="utf-8")
    (d / "merged.json").write_text(json.dumps({"merged": merged}, ensure_ascii=False), encoding="utf-8")
    return catalog.build_catalog(TODAY, seed_dir=d, blocklist={"keywords": []})


class Merging(unittest.TestCase):
    def test_the_dropped_title_goes_and_the_kept_stays(self):
        with tempfile.TemporaryDirectory() as t:
            entries, rej = build_in(t, [seed("第79回 香川丸亀国際ハーフマラソン"), seed("香川丸亀国際ハーフマラソン(第79回)", subject="ハーフマラソン")],
                                    [{"date": "2027-02-07", "drop": "香川丸亀国際ハーフマラソン(第79回)", "keep": "第79回 香川丸亀国際ハーフマラソン"}])
        self.assertEqual([e["title"] for e in entries], ["第79回 香川丸亀国際ハーフマラソン"])
        self.assertEqual(rej["統合(同じ出来事)"], 1)

    def test_nothing_is_dropped_when_the_kept_title_is_missing_or_the_day_differs(self):
        with tempfile.TemporaryDirectory() as t:
            entries, _ = build_in(t, [seed("香川丸亀国際ハーフマラソン(第79回)")], [{"date": "2027-02-07", "drop": "香川丸亀国際ハーフマラソン(第79回)", "keep": "第79回 香川丸亀国際ハーフマラソン"}])
        self.assertEqual(len(entries), 1)                                  # the kept one does not exist: the only card stays
        with tempfile.TemporaryDirectory() as t:
            entries, _ = build_in(t, [seed("A大会"), seed("A大会 別名", subject="別名大会"), seed("A大会 別名", d="2027-03-07", subject="別名大会", source_quote="2027年3月7日")], [{"date": "2027-02-07", "drop": "A大会 別名", "keep": "A大会"}])
        self.assertEqual(sorted((e["title"], e["date"]) for e in entries), [("A大会", "2027-02-07"), ("A大会 別名", "2027-03-07")])      # only the line of that day

    def test_a_broken_line_is_ignored(self):
        with tempfile.TemporaryDirectory() as t:
            entries, _ = build_in(t, [seed("X"), seed("Y", subject="別の題材")], [{"date": "2027-02-07", "drop": "X", "keep": "X"}, {"date": "2027-02-07", "drop": "", "keep": "Y"}, {"drop": "X"}])
        self.assertEqual(len(entries), 2)


class TheList(unittest.TestCase):
    def test_every_line_has_its_kept_card_and_its_dropped_title_is_still_in_the_data(self):
        lines = catalog.load_merged()
        self.assertGreaterEqual(len(lines), 20)
        entries, _ = catalog.build_catalog(TODAY)
        have = {(e["title"], e["date"]) for e in entries}
        raw = {(str(it.get("title", "")).strip(), it.get("date")) for _, it in catalog.load_seeds(catalog.SEED_DIR)}
        for m in lines:
            self.assertIn((m["keep"], m["date"]), have, f"the kept card is missing: {m}")
            self.assertNotIn((m["drop"], m["date"]), have, f"still shown: {m}")
            self.assertIn((m["drop"], m["date"]), raw, f"stale line (the title is not in the data any more): {m}")
        keys = [(m["drop"], m["date"]) for m in lines]
        self.assertEqual(len(keys), len(set(keys)))
        kept = {(m["keep"], m["date"]) for m in lines}
        self.assertFalse(kept & set(keys), "a card is both kept and dropped")


if __name__ == "__main__":
    unittest.main()
