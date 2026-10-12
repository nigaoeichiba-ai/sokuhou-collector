import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from sites.minna import build, factory, wishes

ORDINARY = [
    "こたつでみかんを食べるひつじ", "ファンタジーのドラゴン", "ナチュラルな花かんむり", "グローバルな会議のイラスト", "ワンピースを着た女の子", "ラーメンのナルト", "にもつを運ぶ猫",
    "家に帰ろうとしている犬", "日本人の家族が食卓をかこむ", "アップルパイとりんご", "運動会のフレーム", "ハロウィンのかぼちゃのライン", "リアルなカエル", "おじいちゃんとおばあちゃんのおでかけ",
    "お歳暮のお礼状に添える絵", "雪だるまとこたつ", "うさぎの餅つき", "ねこのお弁当", "サッカーをする子ども", "ヘアカットをする美容師", "裸足で走る子ども", "テロップ付きのニュース番組",
    "スタンプをおす手", "マリンブルーの海", "お正月の鏡もち", "ドラマのワンシーンのような夕焼け",
]


class Refusals(unittest.TestCase):
    def test_ordinary_wishes_are_not_refused(self):
        for w in ORDINARY:
            self.assertEqual(wishes.refusal(w)[0], "", w)

    def test_existing_characters_brands_and_people_are_refused(self):
        self.assertEqual(wishes.refusal("ピカチュウとおにぎり")[0], "ip")
        self.assertEqual(wishes.refusal("ポケモンっぽいキャラ")[0], "ip")
        self.assertEqual(wishes.refusal("ミッキーの年賀状")[0], "ip")
        self.assertEqual(wishes.refusal("スターバックスのカップ")[0], "brand")
        self.assertEqual(wishes.refusal("芸能人の似顔絵")[0], "person")
        self.assertEqual(wishes.refusal("人気作家の絵をまねして")[0], "style")

    def test_katakana_and_hiragana_are_one_word(self):
        self.assertEqual(wishes.refusal("ぴかちゅう")[0], "ip")
        self.assertEqual(wishes.refusal("ＰＯＫＥＭＯＮ".lower())[0], "")          # the Latin spelling is not in the list: the triage by hand sees it
        self.assertEqual(wishes.refusal("ＶＴｕｂｅｒ")[0], "ip")                  # full-width letters are folded

    def test_adult_violence_personal_and_length(self):
        self.assertEqual(wishes.refusal("全裸の女の子")[0], "adult")
        self.assertEqual(wishes.refusal("血まみれの兵士")[0], "violence")
        self.assertEqual(wishes.refusal("連絡は 03-1234-5678 まで")[0], "personal")
        self.assertEqual(wishes.refusal("https://example.com/")[0], "personal")
        self.assertEqual(wishes.refusal("a@b.co")[0], "personal")
        self.assertEqual(wishes.refusal("あ")[0], "length")
        self.assertEqual(wishes.refusal("あ" * 61)[0], "length")

    def test_trial_words_are_marked(self):
        self.assertEqual(wishes.refusal("動作確認 ひつじ")[0], "test")

    def test_every_refusal_has_a_message(self):
        for w in ("ピカチュウ", "スターバックス", "似顔絵", "まねして", "ヌード", "死体", "03-1234-5678"):
            why, msg = wishes.refusal(w)
            self.assertTrue(why and msg, w)


class ClientRules(unittest.TestCase):
    def test_terms_are_already_flat(self):
        for g in wishes.client_rules()["groups"]:
            for t in g["terms"]:
                self.assertEqual(wishes.flat(t), t)

    def test_same_verdict_as_the_page_and_server_algorithm(self):
        """The page and api/q.php flatten a wish and look for the flattened terms: re-run that here and compare with refusal()."""
        cr = wishes.client_rules()

        def verdict(w):
            f = wishes.flat(w)
            for g in cr["groups"]:
                if any(t in f for t in g["terms"]):
                    return g["k"]
            return "personal" if any(re.search(p, f, re.I) for p in cr["personal"]) else ""
        for w in [*ORDINARY, "ピカチュウ", "ぐでたま", "スタバ", "全裸", "死体", "https://a.b/", "03-1111-2222", "まねして描いて"]:
            self.assertEqual(verdict(w), wishes.refusal(w)[0] if wishes.refusal(w)[0] not in ("length", "test") else "", w)

    def test_regexes_have_no_tilde_and_compile(self):
        for p in wishes.client_rules()["personal"]:
            self.assertNotIn("~", p)
            re.compile(p)


class Receiver(unittest.TestCase):
    cfg = {"site_url": "https://minna-no-illust.com"}

    def test_php_is_filled_in_and_the_rules_survive_the_quoting(self):
        php = build.request_php(self.cfg)
        self.assertNotIn("__", php.replace("__DIR__", ""))
        m = re.search(r"json_decode\('(.*)', true\);", php)
        raw = m.group(1).replace("\\\\", "\x00").replace("\\'", "'").replace("\x00", "\\")      # undo PHP single-quote unescaping
        rules = json.loads(raw)
        self.assertEqual(rules, wishes.client_rules())
        self.assertIn("'https://minna-no-illust.com'", php)

    def test_php_keeps_what_the_design_promises(self):
        php = build.request_php(self.cfg)
        self.assertIn("inbox", php)
        self.assertIn("req-", php)
        self.assertNotIn("email'] ??", php)                       # no address field is read
        self.assertIn("'email' => ''", php)
        self.assertNotRegex(php, r"HTTP_USER_AGENT")              # no browser string is kept
        self.assertIn("REMOTE_ADDR", php)                         # only for the salted daily hash
        self.assertIn("sha256", php)
        self.assertIn("X-Robots-Tag: noindex", php)

    def test_uses_and_touches_are_embedded(self):
        php = build.request_php(self.cfg)
        self.assertIn("年賀状", php)
        self.assertIn('"kawaii"', php)


class Ledger(unittest.TestCase):
    def rec(self, id_, msg, page="q:u=年賀状;t=kawaii;s=form", kind="request", site="minna"):
        return {"id": id_, "at": "2026-10-12T09:00:00+09:00", "site": site, "kind": kind, "message": msg, "email": "", "page": page}

    def test_parse_page(self):
        self.assertEqual(wishes.parse_page("q:u=年賀状;t=kawaii;s=miss"), {"u": "年賀状", "t": "kawaii", "s": "miss"})
        self.assertEqual(wishes.parse_page(""), {})

    def test_rows_and_dedupe(self):
        ledger = []
        added = wishes.add_new([self.rec("aaaa1111", "こたつのひつじ"), self.rec("bbbb2222", "ピカチュウ"), self.rec("cccc3333", "x", site="saichin"), self.rec("dddd4444", "動作確認 a")], ledger)
        self.assertEqual([r["id"] for r in added], ["Raaaa1111", "Rbbbb2222", "Rdddd4444"])
        self.assertEqual({r["id"]: r["status"] for r in ledger}, {"Raaaa1111": "new", "Rbbbb2222": "declined", "Rdddd4444": "test"})
        self.assertEqual(wishes.add_new([self.rec("aaaa1111", "こたつのひつじ")], ledger), [])
        self.assertEqual(ledger[0]["use"], "年賀状")

    def test_long_form_requests_are_taken_as_letters(self):
        ledger = []
        wishes.add_new([self.rec("eeee5555", "長い文章" * 20, page="", kind="イラストのリクエスト")], ledger)
        self.assertEqual(ledger[0]["src"], "letter")
        self.assertEqual(wishes.add_new([self.rec("ffff6666", "x", page="", kind="ご意見・ご要望")], ledger), [])

    def test_board_shows_only_our_titles_never_the_visitors_words(self):
        ledger = [
            {"id": "R1", "at": "2026-10-12T09:00:00+09:00", "wish": "ひみつの言葉ABC", "src": "form", "status": "published", "title": "こたつのひつじ", "series": "req-x", "public": True},
            {"id": "R2", "at": "2026-10-13T09:00:00+09:00", "wish": "ほかの言葉XYZ", "src": "form", "status": "drawing", "title": "運動会のフレーム", "series": "req-y", "public": True},
            {"id": "R3", "at": "2026-10-13T10:00:00+09:00", "wish": "非公開の言葉", "src": "form", "status": "new", "title": "", "series": "", "public": False},
        ]
        rows = wishes.board_rows(ledger)
        text = json.dumps(rows, ensure_ascii=False)
        self.assertEqual([r["title"] for r in rows], ["運動会のフレーム", "こたつのひつじ"])       # in the making first
        for secret in ("ひみつの言葉ABC", "ほかの言葉XYZ", "非公開の言葉"):
            self.assertNotIn(secret, text)

    def test_analysis_counts_and_skips_trials(self):
        ledger = [
            {"id": "R1", "at": "2026-10-12T09:00:00+09:00", "wish": "ひつじのこたつ", "use": "年賀状", "touch": "kawaii", "src": "form", "status": "new", "auto": ""},
            {"id": "R2", "at": "2026-10-12T09:00:00+09:00", "wish": "ひつじのぬりえ", "use": "", "touch": "", "src": "miss", "status": "new", "auto": ""},
            {"id": "R3", "at": "2026-10-12T09:00:00+09:00", "wish": "動作確認", "use": "", "touch": "", "src": "test", "status": "test", "auto": "test"},
        ]
        text = wishes.analyze(ledger, vocab=["ひつじ", "こたつ", "ぬりえ"])
        self.assertIn("合計 2 件", text)
        self.assertIn("ひつじ: 2", text)
        self.assertIn("こたつ: 1", text)
        self.assertIn("miss: 1", text)


class Spec(unittest.TestCase):
    def test_a_generated_spec_is_valid_for_the_factory_and_drawn_first(self):
        spec = wishes.spec_for("こたつでみかんを食べるひつじ", "a sheep sitting at a kotatsu eating a mikan", "req-20261012-sheep-kotatsu", "kawaii", "animals", "ひつじ", ["ひつじ", "こたつ"], date(2026, 10, 12))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "req-20261012-sheep-kotatsu.json"
            p.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            s = factory.load_spec(p)
        self.assertEqual(len(s["items"]), 6)
        self.assertEqual(factory.priority_of(s), 1)
        self.assertIn("No letters", s["subject_en"])
        self.assertIn("no existing character", s["subject_en"].lower().replace("original design only: ", ""))

    def test_the_cli_writes_a_spec_and_updates_the_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            ledger = d / "ledger.jsonl"
            wishes.write_ledger([{"id": "R9", "at": "2026-10-12T09:00:00+09:00", "wish": "ひつじのこたつ", "use": "", "touch": "", "src": "form", "status": "new", "auto": "", "note": "", "series": "", "title": "", "public": False}], ledger)
            with mock.patch.object(wishes, "LEDGER", ledger), mock.patch.object(wishes, "SPECS", d), mock.patch.object(wishes, "BOARD_FILE", d / "board.json"):
                wishes.main(["spec", "R9", "--title", "こたつのひつじ", "--en", "a sheep at a kotatsu", "--slug", "req-20261012-test-sheep", "--subject", "ひつじ"])
                self.assertTrue((d / "req-20261012-test-sheep.json").exists())
                row = wishes.read_ledger(ledger)[0]
                self.assertEqual((row["status"], row["series"], row["public"]), ("drawing", "req-20261012-test-sheep", True))
                wishes.main(["published", "R9", "req-20261012-test-sheep"])
                board = json.loads((d / "board.json").read_text(encoding="utf-8"))
                self.assertEqual(board["rows"][0]["status"], "公開しました")


class Page(unittest.TestCase):
    def test_request_page_has_the_box_the_board_and_the_refusals(self):
        html = build.request_page({"site_url": "https://minna-no-illust.com", "site_name": "みんなのイラスト", "contact_own": True, "contact_kinds": ["イラストのリクエスト", "その他"]}, True)
        for needle in ('id="req-form"', 'name="w"', 'maxlength="60"', "お受けできないもの", "リクエストへの、お答え", 'id="req-mine"', "プライバシーポリシー"):
            self.assertIn(needle, html)

    def test_data_files_carry_the_rules_and_the_board(self):
        files = build.request_data_files()
        self.assertIn("uses", json.loads(files["data/request-rules.json"]))
        self.assertIn("rows", json.loads(files["data/request-board.json"]))


if __name__ == "__main__":
    unittest.main()
