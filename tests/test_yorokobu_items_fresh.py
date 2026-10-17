"""sites/yorokobu/items_fresh.py: the deploy's page data comes from the server's private folder (made by the scheduled workflow yorokobu-items) and is topped up with a few calls, instead of a 40
minute fetch cached in the public repository's Actions cache (2026-10-18, owner order: no shop data in a public place)."""
import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from sites.yorokobu import content as ct
from sites.yorokobu import items_fresh as F
from sokuhou import rakuten

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures" / "yorokobu"
JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 18, 7, 0, tzinfo=JST)


def data_for(c: dict, hours_old: float = 5) -> dict:
    return {"version": 2, "curated": True, "fetched_at": (NOW - timedelta(hours=hours_old)).isoformat(timespec="seconds"),
            "pairs": {ct.pair_key(p): {"ideas": [], "tiers": {}} for p in ct.pages(c)}, "portrait": [],
            "daily": {code: {"code": code, "name": "x"} for code in F.dp.rakuten_codes(c.get("daily") or [])},
            "likes": {r["slug"]: [] for r in c.get("recipients") or [] if r.get("like_rows")}, "stats": {}}


class FreshTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = ct.load()

    def test_complete_and_recent_data_is_used_as_it_is_without_the_api(self):
        d = data_for(self.c)
        out, why = F.prepare(d, self.c, {}, NOW, 36, lambda: self.fail("no API call is needed"))
        self.assertIs(out, d)
        self.assertIn("nothing to top up", why)

    def test_no_data_or_old_data_means_the_full_refresh(self):
        self.assertIsNone(F.prepare(None, self.c, {}, NOW, 36, lambda: None)[0])
        self.assertIsNone(F.prepare(data_for(self.c, hours_old=50), self.c, {}, NOW, 36, lambda: None)[0])
        broken = data_for(self.c)
        broken["fetched_at"] = "never"
        self.assertIsNone(F.prepare(broken, self.c, {}, NOW, 36, lambda: None)[0])

    def test_new_daily_items_are_looked_up_one_by_one_and_added(self):
        d = data_for(self.c)
        new = sorted(d["daily"])[:2]
        for code in new:
            del d["daily"][code]
        looked = []

        def lookup(client, code, state, total):
            looked.append(code)
            return {"code": code, "name": "fresh"}
        with mock.patch.object(F.rf, "lookup", lookup):
            out, why = F.prepare(d, self.c, {}, NOW, 36, lambda: object())
        self.assertEqual(sorted(looked), new)
        self.assertEqual({k: out["daily"][k]["name"] for k in new}, {k: "fresh" for k in new})
        self.assertNotIn(new[0], d["daily"])                                    # the file that was read is not changed
        self.assertIn("topped up 2 daily items", why)

    def test_a_few_new_pages_are_topped_up_and_many_mean_the_full_refresh(self):
        d = data_for(self.c)
        keys = list(d["pairs"])
        for k in keys[:2]:
            del d["pairs"][k]
        with mock.patch.object(F.rf, "refresh", lambda c, client, picks, keys=None: {"pairs": {k: {"ideas": [], "tiers": {}, "new": True} for k in keys}}):
            out, why = F.prepare(d, self.c, {}, NOW, 36, lambda: object())
        self.assertTrue(all(out["pairs"][k].get("new") for k in keys[:2]))
        self.assertEqual(len(out["pairs"]), len(keys))
        many = data_for(self.c)
        for k in keys[: len(keys) // 2]:
            del many["pairs"][k]
        self.assertIsNone(F.prepare(many, self.c, {}, NOW, 36, lambda: object())[0])
        self.assertIn("too different", F.prepare(many, self.c, {}, NOW, 36, lambda: object())[1])

    def test_without_an_api_key_a_needed_top_up_means_the_full_refresh_and_a_failed_one_too(self):
        d = data_for(self.c)
        del d["daily"][sorted(d["daily"])[0]]
        self.assertIsNone(F.prepare(d, self.c, {}, NOW, 36, lambda: None)[0])

        def boom(*a, **k):
            raise rakuten.RakutenError("429")
        with mock.patch.object(F.rf, "lookup", boom):
            out, why = F.prepare(d, self.c, {}, NOW, 36, lambda: object())
        self.assertIsNone(out)
        self.assertIn("top-up failed", why)

    def test_missing_like_lines_mean_the_full_refresh(self):
        d = data_for(self.c)
        d["likes"].pop(next(iter(d["likes"])))
        self.assertIsNone(F.prepare(d, self.c, {}, NOW, 36, lambda: None)[0])


class WorkflowTest(unittest.TestCase):
    def test_the_items_workflow_stores_privately_and_never_commits_or_caches(self):
        t = (ROOT / ".github" / "workflows" / "yorokobu-items.yml").read_text(encoding="utf-8")
        self.assertIn("privatedata push yorokobu_items.json", t)
        self.assertIn("contents: read", t)
        for bad in ("git push", "git add", "actions/cache", "upload-artifact"):
            self.assertNotIn(bad, t)
        self.assertIn("group: yorokobu-items", t)                              # not the deploy's group: it would cancel a waiting deploy

    def test_the_file_is_pulled_by_default_and_ignored_by_git(self):
        from sites.yorokobu import privatedata
        self.assertIn("yorokobu_items.json", privatedata.FILES)
        self.assertIn("yorokobu_items.json", (ROOT / "data" / ".gitignore").read_text(encoding="utf-8").split())


if __name__ == "__main__":
    unittest.main()
