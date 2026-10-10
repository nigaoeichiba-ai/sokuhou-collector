"""Taking days in from another calendar's .ics file (read on the device; the same file twice adds nothing twice)."""
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
CRLF = chr(13) + chr(10)
ICS = CRLF.join([
    "BEGIN:VCALENDAR", "VERSION:2.0",
    "BEGIN:VEVENT", "UID:a1@example.com", "SUMMARY:歯医者", "DTSTART;TZID=Asia/Tokyo:20261020T150000", "DESCRIPTION:保険証を\\n持っていく", "END:VEVENT",
    "BEGIN:VEVENT", "UID:a2@example.com", "SUMMARY:結婚記念日", "DTSTART;VALUE=DATE:20151025", "RRULE:FREQ=YEARLY", "END:VEVENT",
    "BEGIN:VEVENT", "UID:a3@example.com", "SUMMARY:UTCの会議", "DTSTART:20261021T230000Z", "END:VEVENT",
    "BEGIN:VEVENT", "UID:a4@example.com", "SUMMARY:毎週の会", "DTSTART;VALUE=DATE:20261012", "RRULE:FREQ=WEEKLY", "END:VEVENT",
    "BEGIN:VEVENT", "UID:a5@example.com", "SUMMARY:昔の予定", "DTSTART;VALUE=DATE:20200101", "END:VEVENT",
    "BEGIN:VEVENT", "UID:a6@example.com", "SUMMARY:やめた予定", "DTSTART;VALUE=DATE:20261030", "STATUS:CANCELLED", "END:VEVENT",
    "BEGIN:VEVENT", "UID:a7@example.com", "SUMMARY:長い題名の予定の折り返し", " 、続き<b>", "DTSTART;VALUE=DATE:20261105", "END:VEVENT",
    "END:VCALENDAR", ""])

PAGE = """<!doctype html><meta charset="utf-8"><script>
window.ATOMOU = { v: 'x', groups: ['お金・税金・制度'], slugs: ['deadline'], skins: { basic: { card: 'plain' } } };
</script><script src="%(core)s"></script><script src="%(ics)s"></script><pre id="out">pending</pre><script src="%(app)s"></script><script src="%(ical)s"></script>
<script>var r = window.AtomouIcal.parse(%(text)s); document.getElementById('out').textContent = JSON.stringify(r);</script>"""


@unittest.skipUnless(find_chrome(), "browser checks run locally")
class IcalInChrome(unittest.TestCase):
    def parse(self) -> dict:
        with tempfile.TemporaryDirectory() as td:
            page = Path(td) / "p.html"
            page.write_text(PAGE % {"text": json.dumps(ICS, ensure_ascii=False), **{n: (ASSETS / f"{n}.js").as_uri() for n in ("core", "ics", "app", "ical")}}, encoding="utf-8")
            r = subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={Path(td) / 'prof'}", "--virtual-time-budget=4000",
                                "--dump-dom", page.as_uri() + "?today=2026-10-10"], capture_output=True, timeout=120)
        dom = r.stdout.decode("utf-8", "replace")
        a = dom.index('<pre id="out">') + len('<pre id="out">')
        return json.loads(html.unescape(dom[a:dom.index("</pre>", a)]))

    def test_a_calendar_file_becomes_days(self):
        r = self.parse()
        by = {e["title"]: e for e in r["events"]}
        self.assertEqual((by["歯医者"]["date"], by["歯医者"]["time"]), ("2026-10-20", "15:00"))
        self.assertEqual(by["歯医者"]["memo"], "保険証を\n持っていく")
        self.assertTrue(by["結婚記念日"]["yearly"])
        self.assertEqual((by["UTCの会議"]["date"], by["UTCの会議"]["time"]), ("2026-10-22", "08:00"))     # 23:00 UTC is 08:00 the next day in Japan
        self.assertTrue(by["毎週の会"]["repeat"])                                                          # only the first day is taken, and the page says so
        self.assertNotIn("昔の予定", by)                                                                   # well in the past
        self.assertNotIn("やめた予定", by)                                                                  # cancelled
        self.assertEqual(r["skipped"], 2)
        self.assertEqual(by["長い題名の予定の折り返し、続き b"]["title"], "長い題名の予定の折り返し、続き b")     # a folded line is joined, markup is dropped
        self.assertTrue(all("<" not in e["title"] for e in r["events"]))
        ids = [e["id"] for e in r["events"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(i.startswith("i") for i in ids))


if __name__ == "__main__":
    unittest.main()
