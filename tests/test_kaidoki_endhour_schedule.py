"""The calendars and the top page treat a sale as ended from the hour written for its end (楽天ブラックフライデー: 11/25 1:59), not only from the next day: schedule.over() and the script (calendar.js).  Negative: the day-only rule would keep it."""
from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from sites.kaidoki.gen import facts
from sites.kaidoki.redesign import schedule as S

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "sites" / "kaidoki" / "redesign" / "static" / "scripts" / "calendar.js"
D = date(2026, 11, 25)


def item(when="2026年11月19日(木)20時から11月25日(水)1時59分まで", kind="confirmed"):
    return {"kind": kind, "s": "2026-11-19", "e": "2026-11-25", "when": when}


class ScheduleOverTest(unittest.TestCase):
    def over(self, it, hm):
        with mock.patch.dict(os.environ, {"KAIDOKI_NOW": f"2026-11-25T{hm}"}):
            return S.over(it, D)

    def test_the_end_hour_is_read_from_the_words(self):
        self.assertEqual(S.end_hm(item()), "01:59")
        self.assertEqual(S.end_hm(item("11月24日(火)12時まで")), "12:00")
        self.assertEqual(S.end_hm(item("11月25日(水)まで")), "")
        self.assertEqual(S.end_hm(item(kind="expected")), "")

    def test_over_after_the_end_hour_only(self):
        self.assertFalse(self.over(item(), "01:59"))
        self.assertTrue(self.over(item(), "02:00"))
        self.assertFalse(self.over(item("11月25日(水)まで"), "23:00"))      # negative: no hour written -> the day decides

    def test_past_and_future_days(self):
        self.assertTrue(S.over(item(), date(2026, 11, 26)))
        self.assertFalse(S.over(item(), date(2026, 11, 24)))

    def test_the_rakuten_black_friday_entry_has_its_hour(self):
        ev = [S.ev_item(e) for e in facts.EVENTS if e["id"] == "rbf-2026"][0]
        self.assertEqual(S.end_hm(ev), "01:59")


class ScriptTest(unittest.TestCase):
    def test_the_script_decides_by_the_hour(self):
        src = JS.read_text(encoding="utf-8")
        self.assertIn("isOver(e, li.dataset.et) ? '終了'", src)
        self.assertNotIn("e < today ? '終了'", src)
        node = shutil.which("node") or shutil.which("deno")
        self.assertTrue(node, "node or deno is needed")
        a = src[src.index("  function isOver"):].split("\n", 1)[0] + "\n"      # the function is written on one line
        code = ("function jstNow(){return new Date(Date.parse(NOW)+9*3600*1000);}\nvar NOW;\n" + a +
                "var out=[];['01:59','02:00'].forEach(function(t){NOW='2026-11-25T'+t+':00+09:00';out.push(isOver('2026-11-25','01:59'));out.push(isOver('2026-11-25',''));});console.log(out.join(','));")
        cmd = [node, "-e", code] if "node" in Path(node).stem.lower() else [node, "eval", code]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.stdout.strip(), "false,false,true,false", r.stderr)


if __name__ == "__main__":
    unittest.main()
