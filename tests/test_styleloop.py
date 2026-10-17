"""sokuhou.styleloop: short texts out of built pages, the checks a rewording must pass, the rewrite dictionary applied to HTML, the judge (with a fake Codex).

Negative tests first: a rewording that changes a number / a name / the meaning must be refused; a judge that fails must not mark anything as fine; the dictionary must not
touch links, scripts or text inside a longer sentence (for a short original).
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sokuhou import styleloop as sl

PAGE = """<!doctype html><html><head><title>贈りどきカレンダー | よろこぶプレゼント</title>
<meta name="description" content="1つの商品を仕様・価格の位置・渡し方まで掘り下げた記事です。">
<script>var t='詳しく読む';</script></head><body>
<nav><a href="/a/">詳しく読む</a><a href="/b/">相手から</a></nav>
<h1>詳しく読む</h1>
<h2><span>入力は</span>端末の中</h2>
<p>詳しく読むための説明です。<a href="/x/">詳しく読む</a></p>
<button>リンクをコピー</button><img src="a.png" alt="詳しく読む">
<blockquote>詳しく読む</blockquote><pre>詳しく読む</pre>
<input type="submit" value="詳しく読む"><a href="/c/" aria-label="詳しく読む">x</a>
</body></html>"""


def units_of(raw: str) -> list[tuple[str, str]]:
    return sl.page_units(raw)


class Extract(unittest.TestCase):
    def test_short_texts_are_found_by_kind(self):
        got = units_of(PAGE)
        self.assertIn(("title", "贈りどきカレンダー | よろこぶプレゼント"), got)
        self.assertIn(("description", "1つの商品を仕様・価格の位置・渡し方まで掘り下げた記事です。"), got)
        self.assertIn(("nav", "詳しく読む"), got)
        self.assertIn(("heading", "詳しく読む"), got)
        self.assertIn(("button", "リンクをコピー"), got)
        self.assertIn(("alt", "詳しく読む"), got)
        self.assertIn(("aria", "詳しく読む"), got)

    def test_what_cannot_be_replaced_exactly_is_not_listed(self):
        got = units_of(PAGE)
        self.assertFalse(any(t == "入力は端末の中" for _, t in got))                 # two text nodes in one heading: no exact replacement possible
        self.assertEqual([k for k, t in got if t == "詳しく読む"].count("heading"), 1)  # not the one in the script, the blockquote or the pre

    def test_legal_pages_are_not_read(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "privacy").mkdir()
            (Path(d) / "privacy" / "index.html").write_text(PAGE, encoding="utf-8")
            (Path(d) / "index.html").write_text(PAGE, encoding="utf-8")
            u = sl.extract_units(Path(d))
            self.assertEqual(u["詳しく読む"].pages, 1)


class Invariants(unittest.TestCase):
    def test_a_good_rewording_passes(self):
        self.assertEqual(sl.check_rewrite("詳しく読む", "注目の商品", "yorokobu", "heading"), [])
        self.assertEqual(sl.check_rewrite("ならびかえ", "並び替え", "minna", "label"), [])

    def test_numbers_names_and_claims_may_not_change(self):
        self.assertTrue(any("numbers" in b for b in sl.check_rewrite("価格は3,000円から", "価格は3,500円から", None)))
        self.assertTrue(any("numbers" in b for b in sl.check_rewrite("入学式の2〜3週間前", "入学式の2〜4週間前", None)))
        self.assertTrue(any("names" in b for b in sl.check_rewrite("Amazonで選ぶ贈り物", "ネットで選ぶ贈り物", None)))
        self.assertTrue(any("names" in b for b in sl.check_rewrite("「ほのぼの便り」を読む", "便りを読む", None)))
        self.assertTrue(any("claim" in b for b in sl.check_rewrite("この商品の特徴", "この商品を試した結果", "yorokobu")))
        self.assertTrue(any("emoji" in b for b in sl.check_rewrite("この商品の特徴", "この商品の特徴✨", None)))
        self.assertTrue(any("markup" in b for b in sl.check_rewrite("この商品の特徴", "<b>この商品</b>の特徴", None)))
        self.assertEqual(sl.check_rewrite("詳しく読む", "詳しく読む", None), ["empty or unchanged"])

    def test_a_popularity_claim_may_not_be_added_by_a_rewording(self):
        self.assertTrue(any("claim" in b for b in sl.check_rewrite("種類の違う選ばれている贈り物", "種類が違う人気の贈り物", None)))
        self.assertEqual(sl.check_rewrite("人気の贈り物", "人気の贈り物をまとめました", None), [])                # already there: not a new claim

    def test_words_the_owner_asked_to_replace_may_go(self):
        self.assertEqual(sl.check_rewrite("ソムリエの提案", "編集部の提案", "yorokobu", "heading"), [])

    def test_everyday_words_with_a_kanji_numeral_are_not_numbers(self):
        self.assertEqual(sl.digits("迷ったときの次の一歩"), [])
        self.assertEqual(sl.digits("一言入れて探す"), [])
        self.assertEqual(sl.digits("三日前に届く"), ["三"])
        self.assertTrue(sl.check_rewrite("三日前に届く", "前日に届く", None))

    def test_length_and_the_sites_own_rules(self):
        self.assertTrue(any("longer" in b for b in sl.check_rewrite("詳しく読む", "この商品について仕様や価格帯や渡し方までくわしく読むことができます", None)))
        self.assertTrue(any("hiragana" in b for b in sl.check_rewrite("絞り込む", "しぼりこめるようになっています", "minna")))
        self.assertTrue(any("spaced" in b for b in sl.check_rewrite("あと何日で来る", "あと 何日 で 来る", "atomou")))
        self.assertTrue(any("commas" in b for b in sl.check_rewrite("渡す日と食べる日を決める", "渡す日と、食べる日を、決める", "yorokobu")))
        self.assertTrue(any("naturaljp" in b for b in sl.check_rewrite("商品の特徴", "商品の特徴と言えるでしょう。", None)))

    def test_a_rewording_that_is_itself_a_stiff_compound_is_refused(self):
        self.assertTrue(any("short-text" in b for b in sl.check_rewrite("詳しく読む", "価格の位置まで掘り下げる", None)))


class Sentences(unittest.TestCase):
    def test_suspicious_body_sentences_become_units_and_a_big_rewrite_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "index.html").write_text("<html><body><p>時期、量、保存性を整え、無理なく扱える形に整えます。迷う相手には早めに手配すると整います。ふつうの文です。</p></body></html>", encoding="utf-8")
            u = sl.sentence_units(Path(d), "yorokobu")
            self.assertEqual(u, {})                                                    # a density rule needs several on a page: a lone sentence is not a unit
            (Path(d) / "index.html").write_text("<html><body><p>これは参考になれば幸いです。ふつうの文です。</p><p>それでは、さっそく見ていきましょう。</p></body></html>", encoding="utf-8")
            u = sl.sentence_units(Path(d), "yorokobu")
            self.assertIn("それでは、さっそく見ていきましょう。", u)
            self.assertEqual(u["それでは、さっそく見ていきましょう。"].kind, "sentence")
        old = "近年、ギフト市場への注目が高まっています。楽天市場のランキングでは、今年も食品が上位に並びました。"
        self.assertTrue(any("small edit" in b for b in sl.check_rewrite(old, "母の日の贈り物は、予算より先に相手が毎日使うものから絞ると選びやすくなります。", None, "sentence")))
        self.assertEqual(sl.check_rewrite("本記事では、ランキングについて詳しく解説します。", "ランキングについて詳しく説明します。", None, "sentence"), [])


class Dictionary(unittest.TestCase):
    def rw(self, **pairs):
        return sl.Rewriter([{"from": k, "to": v} for k, v in pairs.items()])

    def test_exact_text_nodes_attributes_title_and_description_are_replaced(self):
        out = self.rw(**{"詳しく読む": "注目の商品", "1つの商品を仕様・価格の位置・渡し方まで掘り下げた記事です。": "気になる商品をくわしく調べました。",
                         "贈りどきカレンダー | よろこぶプレゼント": "贈りどきカレンダー | よろこぶプレゼント"}).page(PAGE)
        self.assertIn("<h1>注目の商品</h1>", out)
        self.assertIn('<a href="/a/">注目の商品</a>', out)
        self.assertIn('alt="注目の商品"', out)
        self.assertIn('aria-label="注目の商品"', out)
        self.assertIn('value="注目の商品"', out)
        self.assertIn('content="気になる商品をくわしく調べました。"', out)

    def test_links_scripts_quotes_pre_and_longer_sentences_are_left_alone(self):
        out = self.rw(**{"詳しく読む": "注目の商品"}).page(PAGE)
        self.assertIn('href="/a/"', out)
        self.assertIn("var t='詳しく読む';", out)                                      # script
        self.assertIn("<blockquote>詳しく読む</blockquote>", out)
        self.assertIn("<pre>詳しく読む</pre>", out)
        self.assertIn("<p>詳しく読むための説明です。", out)                              # a short original is replaced as a whole node only

    def test_a_long_original_is_replaced_inside_a_longer_text_and_escaping_is_kept(self):
        raw = "<p>前の文です。1つの商品を仕様・価格の位置・渡し方まで掘り下げた記事です。後の文は A &amp; B です。</p>"
        out = self.rw(**{"1つの商品を仕様・価格の位置・渡し方まで掘り下げた記事です。": "気になる商品をくわしく調べました。"}).page(raw)
        self.assertEqual(out, "<p>前の文です。気になる商品をくわしく調べました。後の文は A &amp; B です。</p>")

    def test_applying_twice_changes_nothing_more_and_the_rest_of_the_page_is_byte_identical(self):
        rw = self.rw(**{"詳しく読む": "注目の商品"})
        once = rw.page(PAGE)
        self.assertEqual(self.rw(**{"詳しく読む": "注目の商品"}).page(once), once)
        self.assertEqual(once.replace("注目の商品", "詳しく読む"), PAGE.replace("<pre>詳しく読む</pre>", "<pre>詳しく読む</pre>"))

    def test_apply_dir_with_a_dictionary_file(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sl, "DATA", Path(d) / "style"):
            ok, why = sl.add_entry("yorokobu", "詳しく読む", "注目の商品", "owner", "見出しは短く", "heading", today="2026-10-17")
            self.assertTrue(ok, why)
            self.assertFalse(sl.add_entry("yorokobu", "詳しく読む", "注目の商品", "owner")[0])      # no duplicate
            site = Path(d) / "site"
            site.mkdir()
            (site / "index.html").write_text(PAGE, encoding="utf-8")
            (site / "privacy").mkdir()
            (site / "privacy" / "index.html").write_text(PAGE, encoding="utf-8")
            hits = sl.apply_dir(site, "yorokobu")
            self.assertGreaterEqual(hits["replacements"], 5)
            self.assertEqual((hits["pages"], hits["skipped_entries"], hits["skipped_files"]), (1, 0, 0))
            self.assertIn("注目の商品", (site / "index.html").read_text(encoding="utf-8"))
            self.assertEqual((site / "privacy" / "index.html").read_text(encoding="utf-8"), PAGE)      # legal page untouched
            self.assertEqual(sl.apply_dir(site, "minna")["replacements"], 0)                                          # another site's dictionary is not used

    def test_add_refuses_what_the_checks_refuse(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sl, "DATA", Path(d) / "style"):
            ok, why = sl.add_entry("minna", "価格は3,000円から", "価格は3,500円から")
            self.assertFalse(ok)
            self.assertEqual(sl.load_rewrites("minna"), [])
            self.assertTrue(sl.add_entry("minna", "価格は3,000円から", "価格は3,500円から", force=True)[0])      # an owner's own correction may be forced


class FailOpen(unittest.TestCase):
    """The deploy step: whatever is wrong with the dictionary, the page keeps its own text and the run does not fail."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patch = mock.patch.object(sl, "DATA", Path(self.tmp.name) / "style")
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.site = Path(self.tmp.name) / "site"
        self.site.mkdir()
        (self.site / "index.html").write_text(PAGE, encoding="utf-8")

    def run_cli(self, *extra):
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = sl.main(["apply", str(self.site), "--site", "yorokobu", *extra])
        return rc, out.getvalue()

    def test_an_empty_or_missing_dictionary_does_nothing(self):
        rc, out = self.run_cli("--fail-open")
        self.assertEqual(rc, 0)
        self.assertEqual((self.site / "index.html").read_text(encoding="utf-8"), PAGE)
        self.assertIn("dictionary lines=0", out)

    def test_a_few_lines_are_applied_and_counted(self):
        sl.add_entry("yorokobu", "詳しく読む", "注目の商品", force=True)
        rc, out = self.run_cli("--fail-open")
        self.assertEqual(rc, 0)
        self.assertIn("dictionary lines=1 usable=1 skipped=0 pages changed=1", out)
        self.assertNotIn("注目の商品", out)                                                  # the log carries counts, never the wording

    def test_a_line_that_breaks_a_check_today_is_left_out_with_a_warning(self):
        f = sl.rewrites_path("yorokobu")
        f.parent.mkdir(parents=True)
        f.write_text(json.dumps({"entries": [{"from": "価格は3,000円から", "to": "価格は3,500円から", "kind": "heading", "added": "2026-10-17", "by": "codex"}]}, ensure_ascii=False), encoding="utf-8")
        (self.site / "index.html").write_text("<h1>価格は3,000円から</h1>", encoding="utf-8")
        rc, out = self.run_cli("--fail-open")
        self.assertEqual(rc, 0)
        self.assertEqual((self.site / "index.html").read_text(encoding="utf-8"), "<h1>価格は3,000円から</h1>")
        self.assertIn("::warning::styleloop", out)
        self.assertIn("skipped=1", out)

    def test_a_broken_dictionary_file_changes_nothing_and_does_not_fail_the_run(self):
        f = sl.rewrites_path("yorokobu")
        f.parent.mkdir(parents=True)
        f.write_text("{ not json", encoding="utf-8")
        rc, out = self.run_cli("--fail-open")
        self.assertEqual(rc, 0)
        self.assertIn("not valid JSON", out)
        self.assertEqual((self.site / "index.html").read_text(encoding="utf-8"), PAGE)

    def test_a_rewording_text_is_escaped_so_it_can_never_become_markup(self):
        sl.add_entry("yorokobu", "詳しく読む", "<b>注目</b>の商品", force=True)
        self.run_cli("--fail-open")
        out = (self.site / "index.html").read_text(encoding="utf-8")
        self.assertIn("&lt;b&gt;注目&lt;/b&gt;の商品", out)
        self.assertEqual(sl.TAGS.findall(out), sl.TAGS.findall(PAGE))

    def test_the_structure_guard_keeps_a_page_whose_markup_or_link_would_change(self):
        sl.add_entry("yorokobu", "詳しく読む", "注目の商品", force=True)
        for broken in (PAGE.replace("</h1>", "</h1><hr>").replace("注目の商品", "注目の商品"), PAGE.replace('href="/a/"', 'href="/evil/"')):
            with mock.patch.object(sl.Rewriter, "page", return_value=broken):
                rc, out = self.run_cli("--fail-open")
            self.assertEqual(rc, 0)
            self.assertEqual((self.site / "index.html").read_text(encoding="utf-8"), PAGE)
            self.assertIn("left alone=1", out)

    def test_an_exception_inside_the_step_is_a_warning_with_fail_open(self):
        with mock.patch.object(sl, "apply_dir", side_effect=RuntimeError("boom")):
            rc, out = self.run_cli("--fail-open")
            self.assertEqual(rc, 0)
            self.assertIn("::warning::", out)
            rc2, _ = self.run_cli()
            self.assertEqual(rc2, 1)                                                       # without the flag a failure is a failure (for the keeper's own runs)

    def test_naturaljp_reads_the_published_text_so_a_fixed_sentence_is_no_longer_reported(self):
        from sokuhou import naturaljp as nj
        nj._published_rw.clear()
        page = "<html><body><p>それでは、さっそく見ていきましょう。</p><p>ふつうの文です。</p></body></html>"
        (self.site / "page.html").write_text(page, encoding="utf-8")
        before = [h.rule for h in nj.check_file(self.site / "page.html", "yorokobu")]
        self.assertIn("lets_go", before)
        sl.add_entry("yorokobu", "それでは、さっそく見ていきましょう。", "まず予算を決めます。", force=True)
        nj._published_rw.clear()
        after = [h.rule for h in nj.check_file(self.site / "page.html", "yorokobu")]
        self.assertNotIn("lets_go", after)
        nj._published_rw.clear()


class DeployWiring(unittest.TestCase):
    """The step in .github/workflows/deploy.yml: after the build, before the checks that can stop a deploy, and fail-open."""

    def lines(self):
        return (sl.ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8").splitlines()

    def test_the_dictionary_step_sits_between_the_build_and_the_site_check(self):
        names = [l.strip() for l in self.lines() if l.strip().startswith("- name:")]
        i = next(k for k, n in enumerate(names) if n.startswith("- name: Natural-wording dictionary"))
        self.assertTrue(names[i - 1].startswith("- name: Build (release)"), names[i - 1])
        self.assertTrue(names[i + 1].startswith("- name: Site check"), names[i + 1])
        self.assertTrue(names[i + 2].startswith("- name: Phone-width layout check"), names[i + 2])

    def test_the_step_is_fail_open_and_runs_only_when_the_site_is_deployed(self):
        lines = self.lines()
        i = next(k for k, l in enumerate(lines) if "Natural-wording dictionary" in l)
        block = chr(10).join(lines[i:i + 3])
        self.assertIn("steps.gate.outputs.go == 'true'", block)
        self.assertIn("python -m sokuhou.styleloop apply release --site ${{ matrix.site }} --fail-open", block)
        self.assertNotIn("continue-on-error", block)
        self.assertNotIn(": ", lines[i].split("name:", 1)[1])                       # a ': ' in a plain YAML scalar would break the whole workflow


class WordChoice(unittest.TestCase):
    """The owner lesson of 2026-10-17: name a person by a role, name the thing given, offer 3+ wordings and pick the one in use."""
    OLD = "集まりを開いた人へ後日そっと労う贈り方"

    def test_the_two_owner_corrections_are_models_and_the_principles_are_in_both_prompts(self):
        befores = [e["before"] for e in sl.examples()]
        self.assertIn(self.OLD, befores)
        self.assertIn("集まりを開いた人へ、後日贈るお礼", befores)
        p = sl.judge_prompt("yorokobu", [sl.Unit("heading", self.OLD)])
        for word in ("幹事", "お礼の品", "3つ以上", "key", "役割の名前", "単独の抽象名詞", "名詞を動詞にかける"):
            self.assertIn(word, p)
        v = sl.verify_prompt("yorokobu", [(self.OLD, "x")])
        for word in ("役割の名前", "抽象名詞", "word_choice_ok"):
            self.assertIn(word, v)

    def test_the_rules_find_the_three_shapes(self):
        def flags(t):
            return {r for r, _ in sl.short_flags(sl.Unit("heading", t))}
        self.assertIn("person_phrase", flags("集まりを開いた人へ"))
        self.assertIn("person_phrase", flags("手伝ってくれた人にお礼"))
        self.assertIn("bare_noun", flags("後日贈るお礼"))
        self.assertIn("verb_modifies_noun", flags("後日そっと労う贈り方"))
        self.assertEqual(flags("幹事や主催者へ、後日贈るお礼の品"), set())
        self.assertEqual(flags("お礼の品の選び方"), set())

    def test_the_answer_the_owner_corrected_is_refused_and_the_owners_own_wording_passes(self):
        bad = sl.check_rewrite(self.OLD, "集まりを開いた人へ、後日贈るお礼", None, "heading")
        self.assertTrue(any("short-text rules" in b for b in bad), bad)
        self.assertEqual(sl.check_rewrite(self.OLD, "幹事や主催者へ、後日贈るお礼の品", None, "heading"), [])
        self.assertTrue(any("short-text" in b for b in sl.check_rewrite("幹事への贈り物", "集まりを開いてくれた人への贈り物", None, "heading")))   # a role turned back into an explanation

    def test_a_person_can_ask_the_same_question_from_the_command_line(self):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc_bad = sl.main(["check", "--site", "yorokobu", "--from", self.OLD, "--to", "集まりを開いた人へ、後日贈るお礼"])
            rc_ok = sl.main(["check", "--site", "minna", "--from", "しぼりこめます", "--to", "絞り込めます", "--kind", "label"])
        self.assertEqual((rc_bad, rc_ok), (1, 0))
        self.assertIn("NOT accepted", out.getvalue())

    def item(self, cands, choice=1):
        return {"id": 1, "natural": False, "candidates": [{"text": t, "key": k} for t, k in cands], "choice": choice, "why": "役割の名前に", "confidence": "high"}

    def test_the_wording_in_use_wins_and_the_reason_says_so(self):
        u = sl.Unit("heading", self.OLD)
        cands = [("幹事や主催者へ、後日贈るお礼の品", "幹事 お礼 品"), ("世話役へ後日贈るお礼の品", "世話役 お礼 品"), ("まとめ役へ後日贈るお礼の品", "まとめ役 お礼 品")]
        scores = {"幹事 お礼 品": 9, "世話役 お礼 品": 2, "まとめ役 お礼 品": 0}
        text, order, problems = sl.choose("minna", u, self.item(cands, choice=2), scorer=scores.get)
        self.assertEqual(text, "幹事や主催者へ、後日贈るお礼の品")                       # the judge preferred #2; people type #1 more
        self.assertIn("幹事や主催者へ", sl.evidence(order))
        self.assertIn("9", sl.evidence(order))
        text2, order2, _ = sl.choose("minna", u, self.item(cands, choice=2), scorer=lambda k: None)       # nothing measurable: the judge own choice stands
        self.assertEqual(text2, "世話役へ後日贈るお礼の品")
        self.assertIn("辞書に根拠なし", sl.evidence(order2))
        text3, _, _ = sl.choose("minna", u, self.item(cands, choice=3), scorer=lambda k: 4)             # equal scores: the judge choice
        self.assertEqual(text3, "まとめ役へ後日贈るお礼の品")

    def test_candidates_that_fail_the_checks_never_win_whatever_they_score(self):
        u = sl.Unit("heading", self.OLD)
        cands = [("集まりを開いた人へ、後日贈るお礼", "お礼"), ("幹事へ後日贈るお礼の品", "幹事 お礼 品")]
        text, order, _ = sl.choose("minna", u, self.item(cands), scorer=lambda k: 20 if k == "お礼" else 1)
        self.assertEqual(text, "幹事へ後日贈るお礼の品")
        none, order, problems = sl.choose("minna", u, self.item(cands[:1]), scorer=lambda k: 20)
        self.assertIsNone(none)
        self.assertTrue(problems)

    def test_suggestions_are_cached_and_a_failure_is_not_a_score(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sl, "DATA", Path(d) / "style"):
            calls = []

            def fetch(q):
                calls.append(q)
                return ["幹事 お礼 品", "幹事 お礼 品 予算"]
            self.assertEqual(sl.suggest_score("幹事 お礼", fetch=fetch), 4)
            self.assertEqual(sl.suggest_score("幹事 お礼", fetch=fetch), 4)
            self.assertEqual(calls, ["幹事 お礼"])

            def down(q):
                raise OSError("offline")
            self.assertIsNone(sl.suggest_score("世話役 お礼", fetch=down))
            self.assertIsNone(sl.suggest_score("", fetch=fetch))
            self.assertIsNone(sl.suggest_score("母の日 ほかに贈る人", fetch=lambda q: []))                    # a long phrase nobody types as it is: no evidence, not a zero
            self.assertIsNone(sl.suggest_score("母の日 ほかに贈る人", fetch=fetch))                          # (and the empty answer is cached)

    def test_judge_records_the_candidates_and_the_evidence(self):
        answers = {self.OLD: {"natural": False, "candidates": [{"text": "幹事や主催者へ、後日贈るお礼の品", "key": "幹事 お礼 品"}, {"text": "世話役へ後日贈るお礼の品", "key": "世話役 お礼 品"},
                                                             {"text": "ホストへ後日贈るお礼の品", "key": "ホスト お礼 品"}], "choice": 2, "why": "役割の名前に", "confidence": "high"}}

        def run(prompt):
            asked = json.loads(prompt.rsplit("入力:" + chr(10), 1)[1])
            if "同じ意味・同じ事実のままか" in prompt:
                return json.dumps({"items": [{"id": a["id"], "same_meaning": True, "natural": True, "word_choice_ok": True} for a in asked]}, ensure_ascii=False)
            return json.dumps({"items": [{"id": a["id"], **answers[a["text"]]} for a in asked]}, ensure_ascii=False)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sl, "DATA", Path(d) / "style"):
            st = sl.judge({self.OLD: sl.Unit("heading", self.OLD, 2)}, "minna", batches=1, accept=True, runner=run, scorer={"幹事 お礼 品": 8, "世話役 お礼 品": 3, "ホスト お礼 品": 1}.get)
            self.assertEqual(st["accepted"], 1)
            e = sl.load_rewrites("minna")[0]
            self.assertEqual(e["to"], "幹事や主催者へ、後日贈るお礼の品")
            self.assertIn("サジェスト", e["why"])
            rec = sl.load_judged("minna")[sl.key_of(self.OLD)]
            self.assertEqual(len(rec["candidates"]), 3)

    def test_rejudge_replaces_a_dictionary_line_only_when_a_better_checked_wording_is_confirmed(self):
        old, cur = "母の日のほかの相手", "母の日に贈るほかの相手"

        def run_factory(choice_text, same=True):
            def run(prompt):
                asked = json.loads(prompt.rsplit("入力:" + chr(10), 1)[1])
                if "同じ意味・同じ事実のままか" in prompt:
                    return json.dumps({"items": [{"id": a["id"], "same_meaning": same, "natural": True, "word_choice_ok": True} for a in asked]}, ensure_ascii=False)
                self.assertIn(asked[0]["current"], (cur, "父の日に贈るほかの相手"))             # the line in the dictionary is offered as a candidate
                return json.dumps({"items": [{"id": a["id"], "natural": False, "candidates": [{"text": a["current"], "key": "a"}, {"text": choice_text, "key": "b"}, {"text": "母の日にほかに贈る相手", "key": "c"}],
                                              "choice": 2, "why": "語順", "confidence": "high"} for a in asked]}, ensure_ascii=False)
            return run
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sl, "DATA", Path(d) / "style"):
            sl.add_entry("yorokobu", old, cur, force=True, today="2026-10-17")
            units = sl.rejudge_units("yorokobu", "dictionary")
            self.assertEqual(units[old].current, cur)
            st = sl.judge(units, "yorokobu", batches=1, accept=True, runner=run_factory("母の日にほかに贈る相手"), force=True, replace=True)
            self.assertEqual(st["replaced"], 1)
            e = sl.load_rewrites("yorokobu")[0]
            self.assertEqual((e["to"], e["prev"]), ("母の日にほかに贈る相手", cur))
            sl.add_entry("yorokobu", "父の日のほかの相手", "父の日に贈るほかの相手", force=True, today="2026-10-17")      # the second look refuses: the line stays as it was
            units = {"父の日のほかの相手": sl.rejudge_units("yorokobu", "dictionary")["父の日のほかの相手"]}
            st = sl.judge(units, "yorokobu", batches=1, accept=True, runner=run_factory("父の日にほかに贈る相手", same=False), force=True, replace=True)
            self.assertEqual(st.get("replaced", 0), 0)
            self.assertEqual({x["from"]: x["to"] for x in sl.load_rewrites("yorokobu")}["父の日のほかの相手"], "父の日に贈るほかの相手")


class Judge(unittest.TestCase):
    not_same: set = set()

    def units(self, *texts):
        return {t: sl.Unit("heading", t, 3, "index.html", {"heading"}) for t in texts}

    def runner(self, answers):
        """A fake Codex: answers by the text of each item (the order inside a batch is the judge's own)."""
        calls = []

        def run(prompt):
            calls.append(prompt)
            if "同じ意味・同じ事実のままか" in prompt:                      # the second look: every pair is fine unless the test says otherwise
                pairs = json.loads(prompt.rsplit("入力:" + chr(10), 1)[1])
                return json.dumps({"items": [{"id": p["id"], "same_meaning": p["before"] not in self.not_same, "natural": True} for p in pairs]}, ensure_ascii=False)
            asked = json.loads(prompt.rsplit("入力:" + chr(10), 1)[1])
            items = []
            for it in asked:
                a = answers.get(it["text"])
                if a is not None:
                    items.append({"id": it["id"], **a})
            return "了解しました。" + chr(10) + json.dumps({"items": items}, ensure_ascii=False) + chr(10) + "以上です。"
        run.calls = calls
        return run

    def test_the_owner_corrections_are_in_the_prompt(self):
        p = sl.judge_prompt("yorokobu", [sl.Unit("heading", "詳しく読む")])
        self.assertIn("注目の商品", p)
        self.assertIn("掘り下げた", p)
        self.assertIn("詳しく読む", p)
        self.assertIn("固有名", p)

    def test_proposed_accepted_rejected_and_natural_are_told_apart(self):
        items = {"詳しい検索": {"natural": True}, "詳しく読む": {"natural": False, "better": "注目の商品", "why": "短く", "confidence": "high"},
                 "価格は3,000円から": {"natural": False, "better": "価格は3,500円から", "why": "x", "confidence": "high"},
                 "一覧から選ぶ": {"natural": False, "better": "一覧で選ぶ", "why": "好み", "confidence": "low"}}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sl, "DATA", Path(d) / "style"):
            u = self.units("詳しい検索", "詳しく読む", "価格は3,000円から", "一覧から選ぶ")
            run = self.runner(items)
            st = sl.judge(u, "yorokobu", batches=1, accept=True, runner=run, today="2026-10-17")
            self.assertEqual((st["natural"], st["accepted"], st["rejected"], st["proposed"]), (1, 1, 1, 1))
            self.assertEqual([e["to"] for e in sl.load_rewrites("yorokobu")], ["注目の商品"])          # only the clear (high confidence) and checked one entered the dictionary
            judged = sl.load_judged("yorokobu")
            self.assertEqual(len(judged), 4)
            # asked once: the next run asks only about what is new
            run2 = self.runner({})
            sl.judge(self.units("詳しい検索", "詳しく読む", "価格は3,000円から", "一覧から選ぶ"), "yorokobu", batches=1, runner=run2)
            self.assertEqual(run2.calls, [])

    def test_the_second_look_can_refuse_a_rewording_that_changes_the_meaning(self):
        answers = {"詳しく読む": {"natural": False, "better": "注目の商品", "why": "短く", "confidence": "high"}}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sl, "DATA", Path(d) / "style"):
            self.not_same = {"詳しく読む"}
            try:
                st = sl.judge(self.units("詳しく読む"), "yorokobu", batches=1, accept=True, runner=self.runner(answers))
            finally:
                self.not_same = set()
            self.assertEqual((st.get("accepted", 0), st["proposed"]), (0, 1))
            self.assertEqual(sl.load_rewrites("yorokobu"), [])
            self.assertIn("second look", " ".join(sl.load_judged("yorokobu")[sl.key_of("詳しく読む")]["problems"]))
        def no_answer(prompt):
            if "同じ意味・同じ事実のままか" in prompt:
                raise RuntimeError("verifier down")
            return self.runner(answers)(prompt)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sl, "DATA", Path(d) / "style"):
            st = sl.judge(self.units("詳しく読む"), "yorokobu", batches=1, accept=True, runner=no_answer)
            self.assertEqual(sl.load_rewrites("yorokobu"), [])                                    # no second look, no change
            self.assertEqual(st["verify_failed"], 1)

    def test_a_judge_that_fails_marks_nothing_as_fine(self):
        def broken(prompt):
            raise RuntimeError("codex failed")
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sl, "DATA", Path(d) / "style"):
            st = sl.judge(self.units("詳しく読む"), "yorokobu", batches=2, runner=broken)
            self.assertEqual(st["failed_batches"], 1)
            self.assertEqual(sl.load_judged("yorokobu"), {})
            self.assertEqual(sl.load_rewrites("yorokobu"), [])
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sl, "DATA", Path(d) / "style"):
            st = sl.judge(self.units("詳しく読む"), "yorokobu", batches=1, runner=lambda p: "JSON ではありません")
            self.assertEqual(st["failed_batches"], 1)
            self.assertEqual(sl.load_judged("yorokobu"), {})

    def test_an_answer_that_skips_an_item_leaves_it_to_be_asked_again(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sl, "DATA", Path(d) / "style"):
            st = sl.judge(self.units("詳しい検索", "詳しく読む"), "yorokobu", batches=1, runner=self.runner({"詳しい検索": {"natural": True}}))
            self.assertEqual(st["unanswered"], 1)
            self.assertEqual(len(sl.load_judged("yorokobu")), 1)

    def test_names_and_cut_off_titles_are_not_asked_about(self):
        u = self.units("2026年10月", "ワインセット ギフトBOX付き ボルドー産 赤白ワイン 2本 3300円…", "詳しく読む")
        self.assertEqual([x.text for x in sl.pending_units(u, "yorokobu", {})], ["詳しく読む"])


class SourceAndLearning(unittest.TestCase):
    def test_source_replacement_with_backup_and_revert(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sl, "ROOT", Path(d)), mock.patch.object(sl, "DATA", Path(d) / "data" / "style"):
            src = Path(d) / "sites" / "yorokobu"
            src.mkdir(parents=True)
            (src / "build.py").write_text('H = "詳しく読む"\nS = "詳しく読むための説明です"\nD = "1つの商品を仕様・価格の位置・渡し方まで掘り下げた記事です。"\n', encoding="utf-8")
            sl.add_entry("yorokobu", "詳しく読む", "注目の商品", force=True, today="2026-10-17")
            sl.add_entry("yorokobu", "1つの商品を仕様・価格の位置・渡し方まで掘り下げた記事です。", "気になる商品をくわしく調べました。", force=True, today="2026-10-17")
            done = sl.apply_source("yorokobu", dry=True)
            self.assertEqual(len(done), 2)
            self.assertIn("詳しく読む", (src / "build.py").read_text(encoding="utf-8"))               # dry run changes nothing
            sl.apply_source("yorokobu")
            text = (src / "build.py").read_text(encoding="utf-8")
            self.assertIn('H = "注目の商品"', text)
            self.assertIn('S = "詳しく読むための説明です"', text)                                        # a short original only as a whole string
            self.assertIn("気になる商品をくわしく調べました。", text)
            self.assertTrue(all(e.get("in_source") for e in sl.load_rewrites("yorokobu")))
            self.assertEqual(sl.apply_source("yorokobu", dry=True), [])                                 # done once
            self.assertEqual(sl.revert_source("yorokobu"), 1)
            self.assertIn('H = "詳しく読む"', (src / "build.py").read_text(encoding="utf-8"))
            self.assertFalse(any(e.get("in_source") for e in sl.load_rewrites("yorokobu")))

    def test_a_kind_of_rewording_that_comes_up_three_times_is_a_rule_candidate(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sl, "DATA", Path(d) / "style"):
            for occ in ("母の日", "父の日", "敬老の日"):
                sl.add_entry("yorokobu", f"{occ}のほかの相手", f"{occ}に贈るほかの相手", force=True, today="2026-10-17")
            sl.add_entry("minna", "全部見る", "すべて見る", force=True, today="2026-10-17")
            c = sl.learn_candidates()
            self.assertTrue(any(new == "に贈る" or "贈る" in new for _, new, n, _ in c if n >= 3), c)
            self.assertEqual(sl.learn_candidates(min_count=5), [])

    def test_report_lists_before_and_after(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sl, "DATA", Path(d) / "style"):
            sl.add_entry("yorokobu", "詳しく読む", "注目の商品", "owner", "短く", force=True, today="2026-10-17")
            r = sl.report("yorokobu", "2026-10-17")
            self.assertIn("「詳しく読む」→「注目の商品」", r)
            self.assertEqual(sl.report("yorokobu", "2026-10-18"), "")


if __name__ == "__main__":
    unittest.main()
