"""atomou: the words visitors ask us to look up: forbidden and personal ones are refused in the page, in api/w.php and in the research; nothing about the visitor is kept; the words leave the server encrypted."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build, words  # noqa: E402

FW = json.loads((ROOT / "data" / "atomou" / "forbidden_words.json").read_text(encoding="utf-8"))


class Refusing(unittest.TestCase):
    def test_gambling_adult_crime_a_death_and_personal_information_are_refused(self):
        for w in ("競馬 予想", "パチンコ 新台", "ｶｼﾞﾉ 日本", "ボートレース オッズ", "アダルト 配信", "有名人 訃報", "闇バイト 募集", "電話 09012345678", "連絡は a@example.com", "https://example.com", "東京都千代田区の住所"):
            self.assertNotEqual(words.refusal(w), "", w)
        for w in ("新作ゲーム 発売日", "万博", "共通テスト 2027", "鉄道 ダイヤ改正", "ワールドカップ"):
            self.assertEqual(words.refusal(w), "", w)

    def test_length_and_the_words_typed_to_try_the_receiver(self):
        self.assertEqual(words.refusal("あ"), "length")
        self.assertEqual(words.refusal("あ" * 31), "length")
        self.assertEqual(words.refusal("動作確認テスト"), "test")

    def test_the_tally_counts_the_same_word_in_another_spelling_together_and_drops_what_is_refused(self):
        recs = [{"kind": "word", "message": "ＷＢＣ 日程"}, {"kind": "word", "message": "wbc 日程"}, {"kind": "word", "message": "万博"}, {"kind": "word", "message": "競馬"},
                {"kind": "contact", "message": "万博"}]
        self.assertEqual(words.tally(recs), [("ＷＢＣ 日程", 2), ("万博", 1)])


class Receiver(unittest.TestCase):
    def php(self):
        return build.words_php({"site_url": "https://atomou.com"})

    def test_the_generated_receiver_has_the_same_list_and_only_what_the_notice_says_is_kept(self):
        php = self.php()
        self.assertNotIn("__", php.replace("__DIR__", ""))                         # every placeholder is filled
        for t in FW["terms"][:5]:
            self.assertIn(t.lower(), php)
        self.assertIn("dirname(__DIR__, 2)", php)                                   # the demo copy moves it one level up
        self.assertIn("'message' => $w", php)                                       # the word, the time and a random id: nothing of the visitor
        self.assertNotIn("HTTP_USER_AGENT", php)
        self.assertNotIn("setcookie", php)
        self.assertNotIn("REMOTE_ADDR'] .", php.replace("$ip . '|'", ""))           # the address only goes into the salted daily hash
        self.assertIn("hash('sha256', $ip . '|' . date('Y-m-d')", php)
        self.assertIn("words-", php)
        self.assertEqual(php.count("out(422"), 3)                                    # length, a forbidden term, personal information

    def test_the_page_gets_the_same_refusals_as_the_server(self):
        conf_terms = [t.lower() for t in FW["terms"]]
        pages = build.build_pages(json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8")), release=False)
        self.assertIn("api/w.php", pages)
        html = pages["interests/index.html"]
        self.assertIn('id="int-send"', html)
        m = re.search(r'"fw":\{.*?\}', pages["index.html"]) or re.search(r'"fw":\{.*?\}', html)
        self.assertTrue(m, "the conf has no fw")
        self.assertIn(conf_terms[0], m.group(0))
        js = (ROOT / "sites" / "atomou" / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn("/api/w.php", js)
        self.assertIn("data-word-send", js)

    def test_the_privacy_page_tells_what_is_sent_and_what_is_kept(self):
        pages = build.build_pages(json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8")), release=False)
        text = re.sub(r"<[^>]+>", "", pages["privacy/index.html"])
        for must in ("調べてほしいワード", "押したときだけ", "名前・メールアドレス・アドレス(IP)・クッキーは、ワードに結びつけません", "200日で削除", "お約束できません"):
            self.assertIn(must, text, must)


class Wiring(unittest.TestCase):
    def test_the_workflow_copies_only_the_word_files_encrypted_and_never_the_other_sites(self):
        wf = (ROOT / ".github" / "workflows" / "atomou-words.yml").read_text(encoding="utf-8")
        self.assertIn("words-*.jsonl", wf)
        self.assertIn("openssl smime -encrypt", wf)
        self.assertIn("--site atomou", wf)
        self.assertNotIn("saichin", wf)
        self.assertIn("group: data-commit", wf)


if __name__ == "__main__":
    unittest.main()
