"""shiken-nittei.com の公開ゲート: 文章のNG語が1語でも残っていたら、テストが落ちて、公開（デプロイ）が止まる。

走査は sites/shiken/tools/check_text.py（窓口の指定の一覧）。ここで、ビルド後の全ページを、日付を変えて走査する。
公開前チェックの記録（sites/shiken/tools/checks/prepublish_*.md）が無い・未記入の公開も、止める。
"""
from __future__ import annotations

import importlib.util
import os
import re
import tempfile
import unittest
from pathlib import Path

from sokuhou import newsite

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "sites" / "shiken"
TOOLS = SITE / "tools"


def load_checker():
    spec = importlib.util.spec_from_file_location("shiken_check_text", TOOLS / "check_text.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_pages(pages: dict, out: Path) -> None:
    for rel, body in pages.items():
        if isinstance(body, str) and rel.endswith(".html"):
            p = out / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")


class GateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sites.shiken import gen
        gen.write()
        cls.mod = load_checker()
        # ルールの正は ng_rules.json(Drive)。CIにはリポジトリ内の控え(同じversion)を使う。
        hard, soft, white, cls.version, exc = cls.mod.load_rules(str(TOOLS / "ng_rules.json"))
        cls.mod.HARD_PATTERNS, cls.mod.SOFT_PATTERNS, cls.mod.WHITELIST, cls.mod.EXCEPTIONS = hard, soft, white, exc

    def scan_built(self):
        pages, _ = newsite.build_pages(SITE, release=True, strict_seo=True)
        with tempfile.TemporaryDirectory() as tmp:
            write_pages(pages, Path(tmp))
            files, hard, soft, _loc, _app = self.mod.scan(tmp)
        return files, hard

    def test_no_hard_ng_word_is_left_in_any_page(self):
        files, hard = self.scan_built()
        self.assertGreaterEqual(len(files), 30)
        self.assertEqual(hard, [], "NG語が残っています: " + "; ".join(f"{r}[{l}]" for r, l, _ in hard[:10]))

    def test_the_text_stays_clean_on_other_days_too(self):
        # 毎日のデプロイで日付が替わると、文章が変わる(残り日数・「始まっています」など)。その日も0件であること。
        from sites.shiken.gen import common
        before = common.TODAY
        try:
            for day in ("2026-11-20", "2026-12-20"):   # 2027-01-11 以降は、申込締切の残る試験がなくなる(別件: 日程データの更新が要る)
                common.set_today(day)
                from sites.shiken import gen
                gen.write()
                _files, hard = self.scan_built()
                self.assertEqual(hard, [], f"{day}: " + "; ".join(f"{r}[{l}]" for r, l, _ in hard[:10]))
        finally:
            common.set_today(before.isoformat())
            from sites.shiken import gen
            gen.write()

    def test_a_page_with_an_ng_word_is_stopped(self):
        # 負例: わざとNG語を入れたページで、走査が「公開不可」(終了コード1)を返すこと。
        for word in ("並びます", "いちばん近い", "読み物", "入口", "棚", "見てください"):
            with tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / "index.html").write_text(f"<html><body><p>試験が{word}。</p></body></html>", encoding="utf-8")
                _files, hard, _soft, _loc, _app = self.mod.scan(tmp)
                self.assertTrue(hard, word)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "index.html").write_text("<html><body><p>クレジットカード決済が使えます。</p></body></html>", encoding="utf-8")
            self.assertEqual(self.mod.scan(tmp)[1], [])          # 支払い手段の名称は対象外

    def test_the_command_exits_with_1_on_a_hit_and_0_on_a_clean_folder(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "index.html").write_text("<html><body><p>日程が並びます。</p></body></html>", encoding="utf-8")
            r = subprocess.run([sys.executable, str(TOOLS / "check_text.py"), tmp], capture_output=True)
            self.assertEqual(r.returncode, 1)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "index.html").write_text("<html><body><p>日程が表示されます。</p></body></html>", encoding="utf-8")
            r = subprocess.run([sys.executable, str(TOOLS / "check_text.py"), tmp], capture_output=True)
            self.assertEqual(r.returncode, 0)

    def test_a_rules_file_that_cannot_be_read_stops_the_gate(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "index.html").write_text("<html><body><p>日程が表示されます。</p></body></html>", encoding="utf-8")
            r = subprocess.run([sys.executable, str(TOOLS / "check_text.py"), tmp, "--rules", str(Path(tmp) / "none.json")], capture_output=True)
            self.assertEqual(r.returncode, 2)
            r = subprocess.run([sys.executable, str(TOOLS / "check_text.py"), tmp, "--rules", str(TOOLS / "ng_rules.json")], capture_output=True)
            self.assertEqual(r.returncode, 0)

    def test_fetching_the_rules_stops_on_any_failure_and_never_falls_back(self):
        import json
        import subprocess
        import sys
        fetch = str(TOOLS / "fetch_rules.py")
        good = TOOLS / "ng_rules.json"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "got.json"
            r = subprocess.run([sys.executable, fetch, good.as_uri(), str(out)], capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("version=", r.stdout)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["version"], self.version)
            out.unlink()
            bad = {"": "", "empty url": None}
            for name, body in (("not json", "{oops"), ("no version", json.dumps({"hard": [{"label": "a", "pattern": "a"}]})),
                               ("empty hard", json.dumps({"hard": [], "version": "x"})), ("no pattern", json.dumps({"hard": [{"label": "a"}], "version": "x"}))):
                p = Path(tmp) / "bad.json"
                p.write_text(body, encoding="utf-8")
                r = subprocess.run([sys.executable, fetch, p.as_uri(), str(out)], capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                self.assertEqual(r.returncode, 1, name)
                self.assertFalse(out.exists(), name)               # 失敗しても、控えや古い内容を書き出さない
            for url in ("", (Path(tmp) / "missing.json").as_uri()):
                r = subprocess.run([sys.executable, fetch, url, str(out)], capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                self.assertEqual(r.returncode, 1, url)

    def test_the_deploy_workflow_runs_the_gate_and_does_not_swallow_a_failure(self):
        import json
        text = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
        i = text.index("- name: Text gate (")
        step = text[i:text.index("- name: Upload text gate report")]
        for needle in ("fetch_rules.py", "check_text.py", "secrets.SHIKEN_RULES_URL", "matrix.textgate", 'if [ "$MODE" = "stop" ]', "exit \"$rc\""):
            self.assertIn(needle, step, needle)
        self.assertNotIn("continue-on-error", step)
        self.assertNotIn("drive.google.com", text)                       # the address of the master file is in the Secrets, not in this file
        reg = json.loads((ROOT / "data" / "sites.json").read_text(encoding="utf-8"))
        shiken = [s for s in reg["sites"] if s["name"] == "shiken"][0]
        self.assertEqual(shiken.get("textgate"), "stop")                 # a failed gate stops shiken (the others: the default, shadow)
        self.assertIn(reg["defaults"].get("textgate"), ("shadow", "stop"))

    def test_the_live_monitor_never_reports_an_unread_site_as_zero(self):
        spec = importlib.util.spec_from_file_location("shiken_scan_live", TOOLS / "scan_live.py")
        live = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(live)
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.md"
            live.page_urls = lambda base: None                              # a site that cannot be read
            old = sys.argv
            sys.argv = ["scan_live.py", str(TOOLS / "ng_rules.json"), str(out), "shiken"]
            try:
                rc = live.main()
            finally:
                sys.argv = old
            text = out.read_text(encoding="utf-8")
        self.assertEqual(rc, 3)
        self.assertIn("取得できず", text)
        self.assertIn(f"version: {self.version}", text)
        self.assertNotRegex(text, r"shiken \| 0ページ")

    def test_the_live_monitor_counts_hits_per_word_and_applies_the_exceptions_of_the_site(self):
        spec = importlib.util.spec_from_file_location("shiken_scan_live2", TOOLS / "scan_live.py")
        live = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(live)
        import sys
        pages = {"https://shiken-nittei.com/a/": "<p>日程が並びます。いちばん近い日。</p>", "https://shiken-nittei.com/b/": "<p>日程が表示されます。</p>"}
        live.page_urls = lambda base: list(pages)
        live.get = lambda url: pages.get(url)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.md"
            old = sys.argv
            sys.argv = ["scan_live.py", str(TOOLS / "ng_rules.json"), str(out), "shiken"]
            try:
                rc = live.main()
            finally:
                sys.argv = old
            text = out.read_text(encoding="utf-8")
        self.assertEqual(rc, 0)
        self.assertIn("ハードNG 2 件", text)
        self.assertIn("並びます 1", text)

    def test_the_copy_of_the_rules_has_the_version_of_the_master_when_the_drive_is_here(self):
        master = Path("H:/マイドライブ/文章ツール/ng_rules.json")
        if not master.exists():
            self.skipTest("Drive の正が、この環境にない")
        import json
        self.assertEqual(json.loads(master.read_text(encoding="utf-8"))["version"], self.version)

    def test_there_is_a_filled_pre_publication_record(self):
        records = sorted((TOOLS / "checks").glob("prepublish_*.md"))
        self.assertTrue(records, "tools/checks/ に prepublish_日付.md がありません。tools/checklist_template.md をコピーして埋めてください")
        text = records[-1].read_text(encoding="utf-8")
        self.assertNotIn("はい／いいえ", text, f"{records[-1].name}: 未記入の項目があります")
        self.assertRegex(text, r"判定[^\n]*公開する")
        self.assertNotRegex(text, r"判定[^\n]*公開しない[^\n]*\n*$")
        self.assertNotRegex(text, r"\|\s*[^|\n]+\s*\|\s*\|\s*$", f"{records[-1].name}: NG語の件数が空の行があります")


if __name__ == "__main__":
    unittest.main()
