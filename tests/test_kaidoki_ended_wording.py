"""After 楽天ブラックフライデー 2026 ended (11/25 1:59) its two pages speak of it in the past only (found 2026-11-25: the title had changed but sections and the FAQ still said '1時59分までです').  Negative: on the day before, the running words are found by the same check."""
from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNING = ("終了前", "までです", "残りの時間", "済ませておきましょう", "配られます", "発表しています", "発表を待つ", "1時59分です。", "20時からです。")
PAGES = ("rakuten-black-friday-ending", "rakuten-black-friday")
CODE = ("import json;from sites.kaidoki.gen import write;write();\n"
        "print(json.dumps({n: open(f'sites/kaidoki/content/{n}.json', encoding='utf-8').read() for n in %r}))" % (PAGES,))


def pages(day, hm):
    env = {**os.environ, "KAIDOKI_TODAY": day, "KAIDOKI_NOW": f"{day}T{hm}", "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run(["python", "-c", CODE], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=env)
    return json.loads(r.stdout.strip().splitlines()[-1])


def running_words(text):
    doc = json.loads(text)
    body = json.dumps({k: doc.get(k) for k in ("title", "h1", "description", "answer", "sections", "related")}, ensure_ascii=False)
    return [w for w in RUNNING if w in body]


class EndedWordingTest(unittest.TestCase):
    def tearDown(self):
        env = {**os.environ}
        env.pop("KAIDOKI_NOW", None)
        subprocess.run(["python", "-c", "from sites.kaidoki.gen import write; write()"], cwd=ROOT, capture_output=True, env=env)

    def test_after_the_end_no_running_words(self):
        for name, text in pages("2026-11-25", "02:00").items():
            self.assertEqual(running_words(text), [], name)
            self.assertIn("終了", text, name)

    def test_negative_while_it_runs_the_check_finds_them(self):
        got = pages("2026-11-24", "10:00")
        self.assertIn("までです", running_words(got["rakuten-black-friday-ending"]))
        self.assertIn("発表しています", running_words(got["rakuten-black-friday"]))


if __name__ == "__main__":
    unittest.main()
