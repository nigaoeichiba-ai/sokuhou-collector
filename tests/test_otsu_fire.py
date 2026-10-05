import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sokuhou.sources import jgrants, otsu_fire

JST = timezone(timedelta(hours=9))
FIXTURE = Path(__file__).parent / "fixtures" / "otsu_saigai.html"


def _load() -> str:
    return FIXTURE.read_bytes().decode("cp932", errors="strict")


class OtsuFireTest(unittest.TestCase):
    def test_snapshot_parses_all_incidents(self):
        d = otsu_fire.parse(_load(), now=datetime(2026, 10, 5, 16, 0, tzinfo=JST))
        self.assertEqual(len(d["incidents"]), 10)
        self.assertTrue(d["no_active_incident"])
        first = d["incidents"][0]
        self.assertEqual(first["place"], "大津市松が丘六丁目付近")
        self.assertEqual(first["kind"], "自火報作動")
        self.assertEqual(first["started_at"], "2026-10-04T23:41:00+09:00")
        self.assertEqual(first["resolved_at"], "2026-10-05T00:10:00+09:00")
        self.assertEqual(first["result"], "非火災と判明")
        self.assertEqual(first["status"], "resolved")

    def test_snapshot_has_no_unparsed_messages(self):
        d = otsu_fire.parse(_load(), now=datetime(2026, 10, 5, 16, 0, tzinfo=JST))
        self.assertEqual(d["unparsed"], [])

    def test_unknown_message_format_is_surfaced(self):
        d = otsu_fire.parse("<ul><li>10月05日 15時30分 新しい形式の文章です</li></ul>", now=datetime(2026, 10, 5, 16, 0, tzinfo=JST))
        self.assertEqual(len(d["unparsed"]), 1)

    def test_every_incident_has_a_resolution_in_snapshot(self):
        d = otsu_fire.parse(_load(), now=datetime(2026, 10, 5, 16, 0, tzinfo=JST))
        self.assertTrue(all(e["status"] == "resolved" for e in d["incidents"]))

    def test_year_rolls_back_across_new_year(self):
        d = otsu_fire.parse(_load(), now=datetime(2027, 1, 2, 9, 0, tzinfo=JST))
        self.assertTrue(all(e["started_at"].startswith("2026-") for e in d["incidents"]))

    def test_open_incident_is_reported_without_resolution(self):
        html = (
            "<ul><li>10月05日 15時30分 大津市瀬田一丁目付近で建物火災が発生し、"
            "消防車等が出動しています。</li></ul>"
        )
        d = otsu_fire.parse(html, now=datetime(2026, 10, 5, 16, 0, tzinfo=JST))
        self.assertEqual(len(d["incidents"]), 1)
        self.assertEqual(d["incidents"][0]["status"], "reported")
        self.assertNotIn("resolved_at", d["incidents"][0])
        self.assertFalse(d["no_active_incident"])


class JgrantsTest(unittest.TestCase):
    def test_parse_builds_detail_url_and_keeps_fields(self):
        payload = {"result": [{"id": "abc", "title": "T", "subsidy_max_limit": 5, "extra": "drop"}]}
        d = jgrants.parse(payload)
        self.assertEqual(d["total"], 1)
        item = d["subsidies"][0]
        self.assertEqual(item["detail_url"], "https://www.jgrants-portal.go.jp/subsidy/abc")
        self.assertNotIn("extra", item)

    def test_build_url_encodes_keyword(self):
        self.assertIn("keyword=%E8%A3%9C%E5%8A%A9%E9%87%91", jgrants.build_url("補助金"))


if __name__ == "__main__":
    unittest.main()
