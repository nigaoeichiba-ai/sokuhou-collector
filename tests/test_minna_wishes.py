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
    "お歳暮のお礼状に添える絵", "天皇誕生日のカレンダー", "殺し文句の吹き出し", "雪だるまとこたつ", "うさぎの餅つき", "ねこのお弁当", "サッカーをする子ども", "ヘアカットをする美容師", "裸足で走る子ども", "テロップ付きのニュース番組",
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
        self.assertEqual(wishes.refusal("ＰＯＫＥＭＯＮ")[0], "ip")                  # full-width Latin letters are folded and the common English spellings are in the list
        self.assertEqual(wishes.refusal("ＶＴｕｂｅｒ")[0], "ip")                  # full-width letters are folded

    def test_adult_violence_personal_and_length(self):
        self.assertEqual(wishes.refusal("全裸の女の子")[0], "adult")
        self.assertEqual(wishes.refusal("血まみれの兵士")[0], "violence")
        self.assertEqual(wishes.refusal("連絡は 03-1234-5678 まで")[0], "personal")
        self.assertEqual(wishes.refusal("https://example.com/")[0], "personal")
        self.assertEqual(wishes.refusal("a@b.co")[0], "personal")
        self.assertEqual(wishes.refusal("あ")[0], "length")
        self.assertEqual(wishes.refusal("あ" * 61)[0], "length")

    def test_spellings_that_try_to_slip_past_are_caught(self):
        for w in ("ポ・ケ・モン", "ポケ​モン", "ポ ケ モ ン", "pokemon", "Mickey", "ドラえもーん", "ディ-ズ-ニ-", "pac-man", "ＨＥＬＬＯ ＫＩＴＴＹ"):
            self.assertNotEqual(wishes.refusal(w)[0], "", w)

    def test_hyphens_survive_for_the_personal_data_patterns(self):
        self.assertEqual(wishes.refusal("03-1234-5678")[0], "personal")
        self.assertEqual(wishes.refusal("０３－１２３４－５６７８")[0], "personal")

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
            f, fk = wishes.flat(w), wishes.flat_keep(w)
            for g in cr["groups"]:
                if any(t in f for t in g["terms"]):
                    return g["k"]
            return "personal" if any(re.search(p, fk, re.I) for p in cr["personal"]) else ""
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

    def test_php_checks_the_sender_counts_under_one_lock_and_needs_mbstring(self):
        php = build.request_php(self.cfg)
        self.assertIn("function same_site", php)
        self.assertIn("HTTP_REFERER", php)
        self.assertNotRegex(php, r"\$origin !== ''")                                     # no 'no Origin header is fine'
        self.assertIn("function bump_counter", php)
        self.assertIn("flock($fh, LOCK_EX)", php)
        self.assertIn("function_exists('mb_convert_kana')", php)
        self.assertNotRegex(php, r"file_put_contents\(\$rate")                           # the old read-then-write counter is gone

    def test_php_separator_class_covers_every_separator_python_removes(self):
        php = build.request_php(self.cfg)
        line = next(l for l in php.splitlines() if l.startswith("$flat = preg_replace("))
        chars = line.replace("\\", "")
        for c in wishes.SEPARATORS:
            self.assertIn(c, chars, c)
        self.assertIn(r"\x{200B}-\x{200D}", php)                                    # zero-width characters are removed on the server too

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

    def test_a_long_letter_is_judged_too(self):
        ledger = []
        wishes.add_new([{"id": "g1111111", "at": "2026-10-12T09:00:00+09:00", "site": "minna", "kind": "イラストのリクエスト", "message": "ピカチュウの絵をください。" + "あ" * 300, "email": "", "page": ""},
                        {"id": "g2222222", "at": "2026-10-12T09:00:00+09:00", "site": "minna", "kind": "イラストのリクエスト", "message": "ひつじのイラストをお願いします。" + "あ" * 300 + " 連絡先は 090-1234-5678 です", "email": "", "page": ""},
                        {"id": "g3333333", "at": "2026-10-12T09:00:00+09:00", "site": "minna", "kind": "イラストのリクエスト", "message": "ひつじがこたつでみかんを食べるイラストを、年賀状に使いたいので、描いてください。" + "あ" * 300, "email": "", "page": ""}], ledger)
        self.assertEqual([(r["status"], r["auto"]) for r in ledger], [("declined", "ip"), ("declined", "personal"), ("new", "")])

    def test_reading_does_not_print_the_wording(self):
        import io
        from contextlib import redirect_stdout
        ledger = []
        wishes.add_new([{"id": "h1111111", "at": "2026-10-12T09:00:00+09:00", "site": "minna", "kind": "request", "message": "ひみつのことばXYZ", "email": "", "page": "q:u=;t=;s=form"}], ledger)
        with tempfile.TemporaryDirectory() as d:
            lp = Path(d) / "ledger.jsonl"
            wishes.write_ledger(ledger, lp)
            buf = io.StringIO()
            with mock.patch.object(wishes, "LEDGER", lp), redirect_stdout(buf):
                wishes.main(["list"])
                self.assertNotIn("ひみつのことばXYZ", buf.getvalue())
                wishes.main(["list", "--show"])
                self.assertIn("ひみつのことばXYZ", buf.getvalue())

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
        for needle in ('id="req-form"', 'name="w"', 'maxlength="60"', "お受けできないもの", 'id="req-mine"', "プライバシーポリシー"):
            self.assertIn(needle, html)
        self.assertNotIn("リクエストへの", html)                 # nothing has been answered yet: the board is not shown at all, not even as an empty promise

    def test_data_files_carry_the_rules_and_the_board(self):
        files = build.request_data_files()
        self.assertIn("uses", json.loads(files["data/request-rules.json"]))
        self.assertIn("rows", json.loads(files["data/request-board.json"]))


class Assist(unittest.TestCase):
    def jsnorm(self, w):
        import unicodedata
        t = unicodedata.normalize("NFKC", w).lower()
        return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in t)

    def test_synonym_groups_are_safe_to_match_as_substrings(self):
        groups = json.loads((Path(build.__file__).parent / "content" / "synonyms.json").read_text(encoding="utf-8"))["groups"]
        seen = {}
        for g in groups:
            for w in g:
                n = self.jsnorm(w)
                # the page looks for each word as a substring of titles and tags: a one-character word is only for the kanji of animals and a few plain nouns
                self.assertTrue(len(n) >= 2 or w in "猫犬兎熊鳥魚蛙龍竜鬼愛桜羊暦枠", w)
                if n in seen and seen[n] is not g:
                    self.fail(f"{w} is in two groups: {seen[n][0]} and {g[0]}")
                seen[n] = g
            self.assertGreaterEqual(len({self.jsnorm(w) for w in g}), 2, g)

    def test_every_page_has_the_helper_button_and_the_data_files_exist(self):
        html = build.page({"site_url": "https://minna-no-illust.com", "site_name": "みんなのイラスト"}, True, path="/x/", title="t", description="d", body="<h1>x</h1>")
        self.assertIn('id="assist-open"', html)
        self.assertIn('data-src="/assets/assist.js"', html)
        self.assertTrue((Path(build.__file__).parent / "assets" / "assist.js").exists())

    def test_assist_data_points_to_real_kinds_of_pages(self):
        data = build.assist_data([], [{"slug": "g1", "title": "読みもの", "description": "せつめい"}], 2027, {"shojo": []})
        urls = [p["u"] for p in data["pages"]]
        self.assertIn("/guide/g1/", urls)
        self.assertIn("/printables/shojo/", urls)
        self.assertIn("/printables/calendar-2027/", urls)
        for f in data["faq"]:
            self.assertTrue(f["k"] and f["a"])
            self.assertTrue(f.get("u", "/").startswith("/"))
        self.assertIn("kawaii", data["touches"])

    def test_the_helper_answers_match_the_licence_page(self):
        faq = json.dumps(build.ASSIST_FAQ, ensure_ascii=False)
        license_html = build.license_page({"site_url": "https://minna-no-illust.com", "site_name": "みんなのイラスト"}, True)
        for must in ("商用", "クレジット", "素材集", "商標"):
            self.assertIn(must, faq)
            self.assertIn(must, license_html)

    def test_search_page_has_ways_in_and_the_data_it_needs(self):
        html = build.search_page({"site_url": "https://minna-no-illust.com", "site_name": "みんなのイラスト"}, True)
        self.assertIn('id="search-chips"', html)
        self.assertIn("/search/?q=", html)
        files = build.request_data_files()
        self.assertIn("data/request-rules.json", files)


class Nurie(unittest.TestCase):
    cfg = {"site_url": "https://minna-no-illust.com", "site_name": "みんなのイラスト"}

    def test_every_element_the_script_looks_for_is_on_the_page(self):
        html = build.nurie_page(self.cfg, True, [])
        js = (Path(build.__file__).parent / "assets" / "nurie.js").read_text(encoding="utf-8")
        wanted = set(re.findall(r'\$\("#([a-z-]+)"\)', js)) | {"nurie-app"}
        for i in wanted:
            self.assertIn(f'id="{i}"', html, i)
        self.assertIn('<script src="/assets/nurie.js" defer></script>', html)
        self.assertIn("FAQPage", html)

    def test_the_page_is_in_the_menu_and_the_card_maker_keeps_its_own_entry(self):
        labels = {n[0]: n for n in build.BASE_NAV}
        self.assertEqual(labels["ぬりえ"][1], "/tool/nurie/")
        self.assertNotEqual(labels["カードをつくる"][2], labels["ぬりえ"][2])
        self.assertFalse(labels["ぬりえ"][1].startswith(labels["カードをつくる"][2]))

    def test_a_line_drawing_has_a_button_to_colour_it_and_other_pictures_do_not(self):
        cfg = json.loads((Path(build.__file__).parent / "config.json").read_text(encoding="utf-8"))
        items, series = build.load_data()
        line = next(i for i in items if i["touch"] == "lineart")
        other = next(i for i in items if i["touch"] != "lineart")
        self.assertIn(f'/tool/nurie/?id={line["id"]}', build.illust_page(cfg, True, line, items, series, []))
        self.assertNotIn("/tool/nurie/?id=", build.illust_page(cfg, True, other, items, series, []))

    def test_the_page_does_not_send_anything(self):
        js = (Path(build.__file__).parent / "assets" / "nurie.js").read_text(encoding="utf-8")
        self.assertNotRegex(js, r"XMLHttpRequest|sendBeacon|method:\s*[\"']POST")
        self.assertNotIn("/api/", js)


class Specials(unittest.TestCase):
    def test_every_special_names_real_series_guides_and_has_real_text(self):
        import glob
        from sites.minna import specials
        slugs = {json.loads(Path(f).read_text(encoding="utf-8"))["slug"] for f in glob.glob(str(Path(build.__file__).parent / "library" / "*" / "series.json"))}
        guide_slugs = {g["slug"] for g in json.loads((Path(build.__file__).parent / "content" / "guides.json").read_text(encoding="utf-8"))["guides"]}
        seen = set()
        for sp in specials.SPECIALS:
            self.assertNotIn(sp["slug"], seen)
            seen.add(sp["slug"])
            for m in sp["match_series"]:
                self.assertTrue(m.endswith("*") or m in slugs, f"{sp['slug']}: {m}")
            for g in sp.get("guides", []):
                self.assertIn(g, guide_slugs, f"{sp['slug']}: {g}")
            self.assertGreaterEqual(len(sp["faq"]), 2 if sp["slug"] in ("otayori", "frames-lines", "bousai", "shichigosan", "business", "senior", "flowers") else 1)
            self.assertGreaterEqual(sum(len(p) for p in sp["intro"]), 120 if sp["slug"] in ("otayori", "frames-lines", "bousai", "shichigosan", "business", "senior", "flowers") else 0, sp["slug"])

    def test_the_disaster_page_does_not_pretend_to_be_official(self):
        from sites.minna import specials
        sp = next(s for s in specials.SPECIALS if s["slug"] == "bousai")
        text = " ".join(sp["intro"]) + " ".join(a for _, a in sp["faq"])
        self.assertIn("公式", text)
        self.assertIn("代わりにはなりません", text)


class Votes(unittest.TestCase):
    def test_plus_votes_count_for_the_title_and_planned_rows_stand_on_the_board(self):
        ledger = []
        wishes.add_new([{"id": "aaaa1111", "at": "2026-10-12T09:00:00+09:00", "site": "minna", "kind": "request", "message": "運動会のフレーム", "email": "", "page": "q:u=;t=;s=form"}], ledger)
        ledger[0].update(status="accepted", title="運動会のフレーム", public=True)
        for n in range(3):
            wishes.add_new([{"id": f"bbbb000{n}", "at": "2026-10-13T09:00:00+09:00", "site": "minna", "kind": "request", "message": "運動会のフレーム", "email": "", "page": "q:u=;t=;s=plus"}], ledger)
        self.assertEqual([r["status"] for r in ledger], ["accepted", "merged", "merged", "merged"])
        rows = wishes.board_rows(ledger)
        self.assertEqual((rows[0]["title"], rows[0]["status"], rows[0]["asked"]), ("運動会のフレーム", "つくる予定", 4))

    def test_decide_with_a_title_puts_it_on_the_board(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "ledger.jsonl"
            wishes.write_ledger([{"id": "R1", "at": "2026-10-12T09:00:00+09:00", "wish": "こたつのひつじ", "use": "", "touch": "", "src": "form", "status": "new", "auto": "", "note": "", "series": "", "title": "", "public": False}], ledger)
            with mock.patch.object(wishes, "LEDGER", ledger):
                wishes.main(["decide", "R1", "accepted", "--title", "こたつのひつじ"])
                self.assertEqual(wishes.board_rows(wishes.read_ledger())[0]["status"], "つくる予定")

    def test_the_board_has_a_want_button_only_on_rows_not_done(self):
        board = {"v": 1, "updated": "", "rows": [
            {"title": "予定のもの", "status": "つくる予定", "series": "", "date": "2026-10-12", "asked": 3, "kw": []},
            {"title": "できたもの", "status": "公開しました", "series": "req-x", "date": "2026-10-12", "asked": 1, "kw": []}]}
        with mock.patch.object(build, "request_board", return_value=board):
            html = build.request_page({"site_url": "https://minna-no-illust.com", "site_name": "みんなのイラスト", "contact_own": True, "contact_kinds": ["イラストのリクエスト", "その他"]}, True)
        self.assertIn("リクエストへの", html)
        self.assertIn('data-plus="予定のもの"', html)
        self.assertNotIn('data-plus="できたもの"', html)
        self.assertIn("3人が、ほしいと言いました", html)


if __name__ == "__main__":
    unittest.main()
