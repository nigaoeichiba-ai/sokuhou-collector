import tempfile
import unittest
from pathlib import Path

from sokuhou import originality as o

PAGE = '<html><body><nav>メニュー メニュー メニュー メニュー メニュー</nav><main><h1>見出し</h1><p>{}</p></main><footer>共通のフッターの文章です</footer></body></html>'


def site(texts: dict[str, str]) -> tempfile.TemporaryDirectory:
    tmp = tempfile.TemporaryDirectory()
    for rel, text in texts.items():
        p = Path(tmp.name) / rel / "index.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(PAGE.format(text), encoding="utf-8")
    return tmp


class OriginalityTest(unittest.TestCase):
    def test_a_copied_sentence_is_found_with_its_page_and_reference(self):
        copied = "クマの出没は秋にドングリが凶作の年に急に増えるため注意が必要です"
        tmp = site({"copy": "私たちの文章。" + copied + "。そのあとは独自の説明です。", "own": "完全に別の文章だけが入っています。環境省の数字を自分で数えました。"})
        self.addCleanup(tmp.cleanup)
        hits = o.check(Path(tmp.name), {"https://ref.example/a": "前置き。" + copied + "。後書き。"})
        self.assertEqual([(p, r) for p, r, _ in hits], [("/copy/", "https://ref.example/a")])
        self.assertIn(copied, hits[0][2])

    def test_independent_text_is_not_reported_and_short_common_phrases_are_not_either(self):
        tmp = site({"own": "令和8年度の記録は287件です。最新は10月7日の分までです。"})
        self.addCleanup(tmp.cleanup)
        ref = {"r": "令和8年度の記録を載せています。最新の更新は毎日です。クマの出没に注意してください。"}
        self.assertEqual(o.check(Path(tmp.name), ref), [])

    def test_menus_and_footers_are_not_measured(self):
        tmp = site({"a": "本文だけが違う内容のページです。"})
        self.addCleanup(tmp.cleanup)
        self.assertEqual(o.check(Path(tmp.name), {"r": "メニューメニューメニューメニューメニュー 共通のフッターの文章です"}), [])

    def test_an_official_name_can_be_ignored_on_purpose(self):
        name = "ツキノワグマ出没情報地図【クマっぷ】"
        tmp = site({"t": "出典:富山県「" + name + "」を加工して作成"})
        self.addCleanup(tmp.cleanup)
        ref = {"r": "リンク集 " + name + " 公式"}
        self.assertEqual(len(o.check(Path(tmp.name), ref)), 1)
        self.assertEqual(o.check(Path(tmp.name), ref, ignore=(name,)), [])

    def test_shared_returns_the_longest_stretch_first(self):
        mine = "あ" * 3 + "ABCDEFGHIJKLMNOPQRSTUVWXYZ" + "い" * 3 + "0123456789abcdefgh"
        ref = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" + "ほか" + "0123456789abcdefgh"
        got = o.shared(mine, ref, 14)
        self.assertEqual(got[0], "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        self.assertEqual(len(got), 2)

    def test_page_text_takes_main_only_and_drops_scripts(self):
        raw = "<nav>NAV</nav><main><p>本文</p><script>var x=1</script></main><footer>FOOT</footer>"
        self.assertEqual(o.page_text(raw), "本文")
        self.assertIn("NAV", o.page_text(raw, main_only=False))

    def test_no_readable_reference_is_not_reported_as_no_overlap(self):
        from unittest import mock
        with mock.patch.object(o, "fetch", side_effect=OSError("down")):
            self.assertEqual(o.main(["somewhere", "--ref", "https://x.example/"]), 2)


if __name__ == "__main__":
    unittest.main()
