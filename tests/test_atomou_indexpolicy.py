"""Which date pages are indexed is decided by the page's content (sites/atomou/indexpolicy.py).  Negative cases: each gate and each loss of score must be seen."""
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import catalog, indexpolicy as ip  # noqa: E402

TODAY = date(2026, 10, 14)
LAUNCH = date(2026, 9, 1)


def mk(i, **kw):
    e = {"id": f"x{i}", "title": f"第{i}回 テスト大会の開催", "subject": f"S{i}", "what": "大会が開かれる", "date": "2026-11-10", "precision": "day", "status": "active",
         "publish_on": "2026-09-01", "basis": "official", "official_url": "https://example.jp/", "place": "東京都", "kind": "開催", "keep": False, "estimated": False,
         "date_end": "2026-11-11", "history": [], "result": None}
    e.update(kw)
    return e


def decide(*es, **kw):
    return ip.decide(list(es), TODAY, LAUNCH, kw.pop("per_week", 1000), **kw)


class Policy(unittest.TestCase):
    def test_a_good_page_is_indexed(self):
        d = decide(mk(1))["x1"]
        self.assertTrue(d["index"], d)
        self.assertGreaterEqual(d["score"], ip.THRESHOLD)

    def test_each_gate_stops_a_page(self):
        cases = {
            "not-public-yet": mk(1, publish_on="2026-12-01"),
            "over": mk(1, date="2026-10-01", date_end="2026-10-02", status="ended"),
            "date-not-exact": mk(1, estimated=True),
            "date-not-exact ": mk(1, precision="month"),
            "source-stale": mk(1, status="stale"),
        }
        for want, e in cases.items():
            d = decide(e)["x1"]
            self.assertFalse(d["index"], want)
            self.assertEqual(d["reason"], want.strip())

    def test_a_kept_day_passes_the_gates_a_plain_day_does_not(self):
        e = mk(1, date="2001-11-18", date_end=None, status="ended", keep=True)
        self.assertTrue(decide(e)["x1"]["index"])
        self.assertFalse(decide(mk(1, date="2001-11-18", date_end=None, status="ended"))["x1"]["index"])

    def test_a_result_is_always_indexed_even_past_the_ramp(self):
        r = mk(1, date="2026-10-01", date_end=None, status="ended", result={"facts": []})
        d = decide(r, mk(2), per_week=0)
        self.assertTrue(d["x1"]["index"])
        self.assertEqual(d["x2"]["reason"], "ramp")

    def test_thin_pages_stay_out(self):
        thin = mk(1, official_url=None, basis="press", place="", date_end=None, what="", date="2027-06-01")
        d = decide(thin)["x1"]
        self.assertFalse(d["index"])
        self.assertEqual(d["reason"], "score")

    def test_template_copies_lose_points(self):
        es = [mk(i, subject="最低賃金", title=f"県{i}の最低賃金が改定", kind="改定") for i in range(1, 7)]
        d = ip.decide(es, TODAY, LAUNCH, 1000)
        self.assertGreater(d["x1"]["score"], d["x6"]["score"])
        self.assertEqual(d["x1"]["score"] - d["x6"]["score"], 15)

    def test_the_ramp_takes_the_best_score_first(self):
        weak = mk(1)
        strong = mk(2, history=["2025-11-10"], keep=True)
        d = ip.decide([weak, strong], TODAY, TODAY, 1)
        self.assertTrue(d["x2"]["index"])
        self.assertEqual(d["x1"]["reason"], "ramp")

    def test_real_catalogue_decides_every_entry_and_never_indexes_a_gated_one(self):
        entries, _ = catalog.build_catalog(TODAY)
        d = ip.decide(entries, TODAY, LAUNCH)
        self.assertEqual(set(d), {e["id"] for e in entries})
        for e in entries:
            if d[e["id"]]["index"] and not e.get("result"):
                self.assertIsNone(ip.gate(e, TODAY), e["title"])
        self.assertTrue(any(v["index"] for v in d.values()))
        self.assertTrue(any(v["reason"] == "score" for v in d.values()))


if __name__ == "__main__":
    unittest.main()
