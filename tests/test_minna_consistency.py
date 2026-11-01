"""The plan (specs/<slug>.json) and what the site is built from (library/<slug>/series.json) must say the same: which pictures are shown (drawn and not excluded), the title, the lead."""
import json
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[1] / "sites" / "minna"


class SpecAndSeriesAgree(unittest.TestCase):
    def test_every_spec_matches_its_series_json(self):
        bad = []
        for sp in sorted((R / "specs").glob("*.json")):
            s = json.loads(sp.read_text(encoding="utf-8"))
            slug = s["slug"]
            lib = R / "library" / slug
            ser = json.loads((lib / "series.json").read_text(encoding="utf-8"))
            shown = {i["id"][len(slug) + 1:] for i in ser["items"]}
            expected = {it[0] for it in s["items"] if (lib / f"{slug}-{it[0]}.webp").exists()} - set(s.get("exclude", []))
            if shown != expected:
                bad.append(f"{slug}: pictures differ {sorted(shown ^ expected)}")
            for k in ("title", "lead", "genre", "touch"):
                if s.get(k) != ser.get(k):
                    bad.append(f"{slug}: {k} differs between the spec and series.json")
            for i in ser["items"]:
                if not (lib / i["file"]).exists():
                    bad.append(f"{slug}: file missing {i['file']}")
        self.assertEqual(bad, [], "regenerate series.json (factory write_series_json) or fix the spec")


if __name__ == "__main__":
    unittest.main()
