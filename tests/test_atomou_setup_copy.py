"""atomou: the first-visit setup and the add page keep the owner's wording (2026-10-11), the kinds are named as listed, and the guide button stays visible while the setup is open."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import usecases  # noqa: E402

ASSETS = ROOT / "sites" / "atomou" / "assets"


def read(name: str) -> str:
    return (ASSETS / name).read_text(encoding="utf-8")


class SetupCopyTest(unittest.TestCase):
    def test_setup_wording(self):
        js = read("setup.js")
        for text in ("はじめに、1枚だけあなたの忘れたくない日をカードにします。",
                     "選んだジャンルの日に関する情報が優先的に表示されます。",
                     "そのエリアのイベントなど地域の情報が優先的に表示されます。",
                     "未来や過去の忘れたくない日を1つ登録してみましょう。",
                     "未来の日(予定)は「あと○日」、過去の日(思い出)は「もう○日」",
                     "この表示を「カード」と呼びます。",
                     "通知の設定をしたり、カードを友だちに送ることもできます。",
                     "カードの例です"):
            self.assertIn(text, js)
        for old in ("あなたに近い日を選びます", "ホームの先頭に並びます", "近くの日もホームに出ます", "「あと○日」「もう○日」が出て"):
            self.assertNotIn(old, js)

    def test_the_setup_offers_middle_and_small_parts(self):
        js = read("setup.js")
        for key in ("data-m-pick", "data-s-pick", "data-open-g", "data-open-m", "prefs.mids", "prefs.subs"):
            self.assertIn(key, js)
        app = read("app.js")
        self.assertIn("function pickList(", app)
        self.assertIn("function picked(", app)
        self.assertIn("s.prefs.mids = pickList(p.mids, 2); s.prefs.subs = pickList(p.subs, 3);", app)

    def test_the_hint_button_exists_while_the_setup_is_open(self):
        css = read("style.css")
        self.assertNotIn(".intro-open .guide-btn{display:none}", css)
        self.assertIn("画面右下の「? ヒント」", read("setup.js"))

    def test_the_guide_button_is_called_hint(self):
        self.assertIn("ヒント", read("guide.js"))


class AddPageCopyTest(unittest.TestCase):
    def test_the_old_voice_wording_is_gone_everywhere(self):
        for name in ("app.js", "card.js", "plan.js", "setup.js"):
            js = read(name)
            self.assertNotIn("文字や声で入力する", js, name)
            self.assertNotIn("キーボードのマイクで", js, name)

    def test_steps_and_kinds(self):
        app = read("app.js")
        a, b, c = (app.index(x) for x in ("1. 記録したい日", "2. どんな日ですか", "3. 時刻・くり返し"))
        self.assertLess(a, b)
        self.assertLess(b, c)
        for label in ("今日", "年月日", "年と月だけ", "年だけ", "文字で日付を入力する"):
            self.assertIn(label, app)
        m = re.search(r"var KINDS = \{(.*?)\n  \};", app, re.S)
        names = re.findall(r"t: '([^']+)'", m.group(1))
        self.assertEqual(names, ["予定", "記念日", "誕生日", "大切な日", "はじめた日", "楽しみな日・期限", "そのほか"])

    def test_the_microphone_is_a_button_with_a_label(self):
        app = read("app.js")
        self.assertIn('class="mic-btn" aria-label="声で入力する"', app)
        self.assertIn("webkitSpeechRecognition", app)
        self.assertIn("ja-JP", app)

    def test_the_use_cases_follow_the_new_order(self):
        for u in usecases.USECASES:
            steps = u["steps"]
            self.assertTrue(3 <= len(steps) <= 5, u["slug"])
            text = " ".join(steps)
            self.assertNotIn("いつの日ですか", text, u["slug"])
            self.assertNotIn("大切な人を思う日』", text, u["slug"])
            kind = [i for i, s in enumerate(steps) if "『どんな日ですか』" in s]
            date = [i for i, s in enumerate(steps) if "『記録したい日』" in s]
            if kind:
                self.assertTrue(date, u["slug"])
                self.assertLess(date[0], kind[0], f"{u['slug']}: the date comes first now")


if __name__ == "__main__":
    unittest.main()
