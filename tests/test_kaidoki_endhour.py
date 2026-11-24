"""sale-calendar.com: a sale that ends at 1:59 of its last day is 'done' from 2:00 of that day (found 2026-11-25: 楽天ブラックフライデー ended 11/25 1:59 but the pages said 開催中 until 11/26 because the phase used the day only).
The hour of the build decides on the last day; with only KAIDOKI_TODAY set (the other tests) the day alone decides, as before.  Negative: the old day-only rule would call 2:00 'now'."""
from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ("from sites.kaidoki.gen import common as c, facts;e=facts.BY_ID['rbf-2026'];print(c.phase(e), c.state(e))")


def run(today, now=None):
    env = {**os.environ, "KAIDOKI_TODAY": today, "PYTHONIOENCODING": "utf-8"}
    env.pop("KAIDOKI_NOW", None)
    if now:
        env["KAIDOKI_NOW"] = f"{today}T{now}"
    return subprocess.run(["python", "-c", CODE], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=env).stdout.strip()


class EndHourTest(unittest.TestCase):
    def test_before_and_at_the_end_hour_it_is_still_on(self):
        self.assertEqual(run("2026-11-25", "01:59"), "now 本日最終日")
        self.assertEqual(run("2026-11-25", "00:10"), "now 本日最終日")

    def test_from_the_next_minute_it_is_done(self):
        self.assertEqual(run("2026-11-25", "02:00"), "done 終了")
        self.assertEqual(run("2026-11-25", "09:30"), "done 終了")

    def test_the_day_before_and_the_day_after(self):
        self.assertEqual(run("2026-11-24", "23:00"), "now 開催中")
        self.assertEqual(run("2026-11-26", "00:30"), "done 終了")

    def test_with_only_the_day_the_old_rule_holds(self):
        self.assertEqual(run("2026-11-25"), "now 本日最終日")


BUILD = ("from sites.kaidoki.gen import write; write()\nfrom sokuhou import newsite; from pathlib import Path\n"
         "newsite.build_pages(Path('sites/kaidoki').resolve(), release=True, strict_seo=True); print('BUILD-OK')")


class LaterDaysBuildTest(unittest.TestCase):
    """The release build (strict SEO) must pass on later days too: on 2026-11-25 every deploy stopped because the ended page lost its main term, and in January the December deadline page would have gone thin."""

    def test_the_release_build_passes_on_later_days(self):
        try:
            for day in ("2026-11-25", "2026-12-01", "2026-12-26", "2027-01-11"):
                env = {**os.environ, "KAIDOKI_TODAY": day, "KAIDOKI_NOW": f"{day}T07:00", "PYTHONIOENCODING": "utf-8"}
                r = subprocess.run(["python", "-c", BUILD], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=env)
                self.assertIn("BUILD-OK", r.stdout, f"{day}: {(r.stdout + r.stderr)[-600:]}")
        finally:        # leave the generated content as the other tests expect it
            env = {**os.environ}
            env.pop("KAIDOKI_NOW", None)
            subprocess.run(["python", "-c", "from sites.kaidoki.gen import write; write()"], cwd=ROOT, capture_output=True, env=env)


if __name__ == "__main__":
    unittest.main()
