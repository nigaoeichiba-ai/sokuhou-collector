"""The plan of a planner (free / plus): the card limit, what sending earns, the notices, the signature - decided on the device, and only when the config switches it on."""
import html
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_atomou_core_js import find_chrome  # noqa: E402

ASSETS = Path(__file__).resolve().parents[1] / "sites/atomou/assets"
CONFIG = json.loads((Path(__file__).resolve().parents[1] / "sites/atomou/config.json").read_text(encoding="utf-8"))

PAGE = """<!doctype html><meta charset="utf-8"><script>
window.ATOMOU = { v: 'x', groups: ['手続き・お金'], slugs: ['deadline'], skins: { basic: { card: 'plain' } }, plans: %(plans)s };
localStorage.setItem('atomou.v1', %(stored)s);
%(member)s
</script><script src="%(core)s"></script><script src="%(ics)s"></script><pre id="out">pending</pre><script src="%(app)s"></script><script src="%(tier)s"></script>
<script>var T = window.AtomouApp.tier, out = { on: T.on, plus: T.plus(), used: T.used(), limit: T.limit(), room: T.room(), ok: T.remindAllowed(30), ok7: T.remindAllowed(7) };
T.shared(); T.shared(); T.shared(); out.limitAfter = T.limit(); out.shares = window.Atomou.state().prefs.shares;
document.getElementById('out').textContent = JSON.stringify(out);</script>"""


@unittest.skipUnless(find_chrome(), "browser checks run locally")
class TierInChrome(unittest.TestCase):
    def run_page(self, plans: dict, entries: list, member: dict | None = None) -> dict:
        stored = {"v": 1, "entries": entries, "prefs": {}}
        mem = "localStorage.setItem('atomou.member', " + json.dumps(json.dumps(member)) + ");" if member else ""
        with tempfile.TemporaryDirectory() as td:
            page = Path(td) / "p.html"
            page.write_text(PAGE % {"plans": json.dumps(plans), "stored": json.dumps(json.dumps(stored, ensure_ascii=False)), "member": mem,
                                    **{n: (ASSETS / f"{n}.js").as_uri() for n in ("core", "ics", "app", "tier")}}, encoding="utf-8")
            r = subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={Path(td) / 'prof'}", "--virtual-time-budget=4000",
                                "--dump-dom", page.as_uri() + "?today=2026-10-10"], capture_output=True, timeout=120)
        dom = r.stdout.decode("utf-8", "replace")
        a = dom.index('<pre id="out">') + len('<pre id="out">')
        return json.loads(html.unescape(dom[a:dom.index("</pre>", a)]))

    ON = {"on": True, "free_cards": 5, "shares_per_slot": 3, "extra_max": 20, "free_remind": [7, 1]}

    @staticmethod
    def entry(i, date="2026-12-01", kind="event", quiet=False, yearly=False):
        return {"id": f"e{i}", "title": f"予定{i}", "date": date, "precision": "day", "kind": kind, "quiet": quiet, "yearly": yearly}

    def test_the_config_ships_with_plans_off(self):
        self.assertFalse(CONFIG["plans"]["on"])        # nothing is limited until the owner switches it on

    def test_with_plans_off_nothing_is_limited(self):
        r = self.run_page({}, [self.entry(i) for i in range(9)])
        self.assertTrue(r["plus"])
        self.assertIsNone(r["room"])                   # Infinity does not survive JSON: null

    def test_a_free_planner_holds_five_upcoming_cards_and_a_quiet_or_past_one_does_not_count(self):
        entries = [self.entry(i) for i in range(4)] + [self.entry(8, quiet=True, kind="memorial"), self.entry(9, date="2020-01-01"), self.entry(10, date="2020-01-01", yearly=True)]
        r = self.run_page(self.ON, entries)
        self.assertEqual((r["plus"], r["used"], r["limit"], r["room"]), (False, 5, 5, 0))     # 4 upcoming + 1 yearly day; the memorial and the past day are free
        self.assertEqual((r["ok"], r["ok7"]), (False, True))                                  # 30 days before is plus; 7 days before is free

    def test_sending_three_times_makes_room_for_one_more(self):
        r = self.run_page(self.ON, [self.entry(i) for i in range(5)])
        self.assertEqual((r["limit"], r["limitAfter"], r["shares"]), (5, 6, 3))

    def test_a_member_with_a_free_period_or_the_plus_plan_is_not_limited(self):
        for member in ({"plan": "plus"}, {"free_until": "2027-01-01"}):
            r = self.run_page(self.ON, [self.entry(i) for i in range(9)], member)
            self.assertTrue(r["plus"], member)
            self.assertTrue(r["ok"], member)
        r = self.run_page(self.ON, [self.entry(i) for i in range(9)], {"free_until": "2026-01-01"})   # the period is over
        self.assertFalse(r["plus"])


if __name__ == "__main__":
    unittest.main()
