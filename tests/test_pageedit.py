"""sokuhou.pageedit: one page, one Codex call, an editor's rewrite; only the invariants are checked by machine (with a fake Codex here)."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from sokuhou import pageedit as pe
from sokuhou import styleloop as sl

PAGE = """<!doctype html><html><head><title>お中元の贈り物 夏の挨拶を涼しく整える基本 | よろこぶプレゼント</title>
<meta name="description" content="お中元は日ごろの感謝を夏の挨拶として届ける贈り物です。"></head><body>
<header><a href="/">トップ</a></header>
<main><h1><span>お中元の贈り物 夏の挨拶を涼しく整える基本</span></h1>
<p>お中元は日ごろの感謝を夏の挨拶として届ける贈り物です。習慣として続くこともあるため、時期と量と保存性を整え、相手の家や職場で無理なく扱える形に整えます。</p>
<p><b>PR</b> このページには広告を含みます</p>
<h2>地域の時期に合わせる</h2>
<p>お中元の時期は地域で少し差があります。関東では七月上旬から中旬、関西では七月中旬から八月中旬を目安に考えることが多いです。</p>
<ul><li>京都利休園 黒ほうじ ティーバッグ 2本セット</li><li>★4.8(833件)送料無料</li></ul>
<p>詳しくは<a href="/x/">こちら</a>をご覧ください。</p>
<blockquote><p>おかげさまで、今年もたのしくすごせました。</p></blockquote>
<button>リンクをコピー</button></main>
<footer><p>運営者情報編集方針</p></footer></body></html>"""


def fake(answer, claims=None, claims_down=False):
    """A fake Codex.  The claims check (a second call) says all is well unless `claims` maps the start of a before-text to the flags to raise."""
    def run(prompt):
        run.prompts.append(prompt)
        if "added_claim" in prompt:
            if claims_down:
                raise RuntimeError("claims check down")
            asked = json.loads(prompt.rsplit("入力:" + chr(10), 1)[1])
            items = []
            for a in asked:
                flags = next((f for k, f in (claims or {}).items() if a["before"].startswith(k)), {})
                items.append({"id": a["id"], "added_claim": False, "hedge_removed": False, "condition_dropped": False, "problem": "", **flags})
            return json.dumps({"items": items}, ensure_ascii=False)
        return "了解しました。" + chr(10) + json.dumps(answer, ensure_ascii=False) + chr(10) + "以上。"
    run.prompts = []
    return run


class Units(unittest.TestCase):
    def test_the_displayed_text_in_order_with_what_can_be_replaced_exactly(self):
        u = pe.page_units(PAGE)
        kinds = [(x.kind, x.editable) for x in u]
        texts = [x.text for x in u]
        self.assertEqual(u[0].kind, "title")
        self.assertTrue(u[0].editable)                                              # the bar and spaces of a page title are not a product title
        self.assertIn(("heading", True), kinds)                                     # a heading with a span around its one text node is editable
        by_text = {x.text: x for x in u}
        self.assertFalse(by_text["PR このページには広告を含みます"].editable)           # two text nodes: shown, not editable
        self.assertFalse(by_text["詳しくはこちらをご覧ください"].editable) if "詳しくはこちらをご覧ください" in by_text else None
        self.assertFalse(by_text["京都利休園 黒ほうじ ティーバッグ 2本セット"].editable)  # a shop's product title is somebody else's data
        self.assertFalse(by_text["★4.8(833件)送料無料"].editable)
        self.assertTrue(by_text["リンクをコピー"].editable)
        for skipped in ("トップ", "運営者情報編集方針", "おかげさまで、今年もたのしくすごせました。"):
            self.assertNotIn(skipped, texts)                                        # menus, footers and quoted examples are not the page's own prose

    def test_a_long_page_is_cut_at_a_heading_and_every_part_keeps_the_headings(self):
        body = "".join(f"<h2>見出し{i}</h2>" + "".join(f"<p>これは{i}番目の節の{j}番目の段落で、内容があります。</p>" for j in range(30)) for i in range(4))
        units = pe.page_units(f"<html><head><title>長いページ</title></head><body><main>{body}</main></body></html>")
        parts = pe.chunks(units)
        self.assertGreater(len(parts), 1)
        heads = [u.id for u in units if u.kind in ("title", "heading")]
        for part in parts:
            self.assertTrue(set(heads) <= {u.id for u in part})
        self.assertEqual(sorted({u.id for part in parts for u in part}), sorted(u.id for u in units))
        self.assertEqual(len(pe.chunks(pe.page_units(PAGE))), 1)


class Prompt(unittest.TestCase):
    def test_the_prompt_is_the_editor_prompt_with_the_page_and_the_site_filled_in(self):
        units = pe.page_units(PAGE)
        p = pe.build_prompt("yorokobu", "guide/ochugen/index.html", units)
        self.assertIn("20年働いてきた編集者", p)
        self.assertIn("gift_ja.json", p)
        self.assertIn("贈り方ガイド", p)
        self.assertIn("落ち着いた「です・ます」", p)
        self.assertIn("u1 | title | お中元の贈り物", p)
        self.assertIn("(編集不可・参考)", p)
        self.assertNotIn("{{UNITS}}", p)
        self.assertNotIn("{{SITE}}", p)
        self.assertNotIn("=== ここから ===", p)
        for site in pe.SITE_INFO:
            self.assertIn(pe.SITE_INFO[site]["dict_file"], pe.build_prompt(site, "x/index.html", units))


class Editing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.object(sl, "DATA", Path(self.tmp.name) / "style")
        p.start()
        self.addCleanup(p.stop)
        self.units = pe.page_units(PAGE)
        self.id = {x.text: x.id for x in self.units}

    def answer(self, **kw):
        base = {"diagnosis": ["見出し: 雰囲気語が多い"], "edits": [], "deleted": [], "needs_check": [], "structure_suggestions": [], "unchanged_count": 0}
        base.update(kw)
        return base

    def test_edits_that_pass_the_invariants_go_into_the_dictionary_and_the_rest_are_refused_with_reasons(self):
        h = "お中元の贈り物 夏の挨拶を涼しく整える基本"
        para = next(x for x in self.units if x.text.startswith("お中元の時期は地域で"))
        edits = [
            {"id": self.id[h], "after": "お中元の贈り物 時期・品物・のし", "why": "具体語に"},
            {"id": para.id, "after": "お中元の時期は地域で少し差があります。関東は七月上旬から中旬、関西は七月中旬から八月中旬を目安に考えることが多いです。", "why": "整理"},   # a big rewrite of a paragraph is fine
            {"id": self.id["地域の時期に合わせる"], "after": "地域別 お中元の時期は8月まで", "why": "数字を足した"},                          # a number out of nowhere
            {"id": self.id["PR このページには広告を含みます"], "after": "広告を含みます", "why": "x"},                               # not editable
            {"id": "u999", "after": "存在しない", "why": "x"},
        ]
        run = fake(self.answer(edits=edits, needs_check=[{"id": para.id, "question": "関西の時期は百貨店の案内で確かめたか"}], deleted=[self.id["リンクをコピー"]],
                               structure_suggestions=[f"{self.id[h]} と {para.id} を入れ替える"], unchanged_count=3))
        rep = pe.edit_page("yorokobu", "guide/ochugen/index.html", PAGE, runner=run, today="2026-10-17")
        self.assertEqual([a["to"] for a in rep["accepted"]][0], "お中元の贈り物 時期・品物・のし")
        self.assertEqual(len(rep["accepted"]), 2)
        self.assertEqual(len(rep["rejected"]), 2)
        reasons = " ".join(" ".join(r["problems"]) for r in rep["rejected"])
        self.assertIn("numbers differ", reasons)
        self.assertIn("not editable", reasons)
        self.assertEqual(rep["needs_check"][0]["question"], "関西の時期は百貨店の案内で確かめたか")
        self.assertEqual(rep["deleted"], ["リンクをコピー"])
        self.assertIn("入れ替える", rep["structure_suggestions"][0])
        self.assertIn("「お中元の贈り物", rep["structure_suggestions"][0])               # ids are turned back into the text for the report
        entries = sl.load_rewrites("yorokobu")
        self.assertEqual(len(entries), 2)
        self.assertTrue(all(e["by"] == "editor" and e.get("edit") for e in entries))

    def test_a_page_edit_survives_the_check_at_deploy_time_but_a_sentence_mode_rewrite_does_not_get_its_exemption(self):
        para = next(x for x in self.units if x.text.startswith("お中元の時期は地域で"))
        new = "七月上旬から中旬が関東、七月中旬から八月中旬が関西の目安とされることが多く、地域で時期が違うため、先に相手の住まいを確かめます。"
        pe.edit_page("yorokobu", "x/index.html", PAGE, runner=fake(self.answer(edits=[{"id": para.id, "after": new, "why": "整理"}])), today="2026-10-17")
        entries, skipped = sl.usable_entries("yorokobu", warn=lambda m: None)
        self.assertEqual((len(entries), skipped), (1, 0))
        self.assertTrue(sl.check_rewrite(para.text, new, "yorokobu", "para"))        # as a sentence-mode rewrite it would be refused (not a small edit)

    def test_the_comma_rule_of_yorokobu_is_applied_to_the_editors_text_not_held_against_it(self):
        para = next(x for x in self.units if x.text.startswith("お中元の時期は地域で"))
        new = "お中元の時期は、地域で、少し差があります。関東では、七月上旬から中旬、関西では、七月中旬から八月中旬を目安に考えることが多いです。"
        rep = pe.edit_page("yorokobu", "x/index.html", PAGE, runner=fake(self.answer(edits=[{"id": para.id, "after": new, "why": "x"}])), accept=False)
        self.assertEqual(len(rep["accepted"]), 1)
        self.assertNotIn("、地域で、", rep["accepted"][0]["to"])

    def test_a_failed_call_is_a_failure_not_a_clean_page(self):
        def broken(prompt):
            raise RuntimeError("codex down")
        rep = pe.edit_page("yorokobu", "x/index.html", PAGE, runner=broken)
        self.assertIn("codex down", rep["failed"])
        self.assertEqual(rep["accepted"], [])
        rep2 = pe.edit_page("yorokobu", "x/index.html", PAGE, runner=lambda p: "JSON ではありません")
        self.assertTrue(rep2["failed"])
        self.assertEqual(sl.load_rewrites("yorokobu"), [])

    def test_dry_run_changes_nothing_and_returns_the_prompt(self):
        rep = pe.edit_page("yorokobu", "x/index.html", PAGE, runner=fake({}), dry=True)
        self.assertIn("20年働いてきた編集者", rep["prompt"])
        self.assertEqual(sl.load_rewrites("yorokobu"), [])

    def test_next_pages_skips_a_page_whose_text_was_edited_and_has_not_changed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            body = "".join(f"<p>これは本文の{i}番目の段落で、三十字を超える長さの文章として数えられるように書いています。</p>" for i in range(4))
            for rel in ("guide/a/index.html", "guide/b/index.html", "privacy/index.html"):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text(f"<html><head><title>題</title></head><body><main><h1>題</h1>{body}</main></body></html>", encoding="utf-8")
            got = [r for r, _ in pe.next_pages("yorokobu", root, 5)]
            self.assertEqual(sorted(got), ["guide/a/index.html", "guide/b/index.html"])          # the legal page is never edited
            raw = (root / "guide/a/index.html").read_text(encoding="utf-8")
            pe.save_edited("yorokobu", {"guide/a/index.html": {"hash": pe.content_hash(pe.page_units(raw)), "date": "2026-10-17"}})
            self.assertEqual([r for r, _ in pe.next_pages("yorokobu", root, 5)], ["guide/b/index.html"])
            (root / "guide/a/index.html").write_text(raw.replace("本文の0番目", "本文の九番目"), encoding="utf-8")           # the text changed: edited again
            self.assertIn("guide/a/index.html", [r for r, _ in pe.next_pages("yorokobu", root, 5)])


class Paragraphs(unittest.TestCase):
    """The checks for a rewritten paragraph: no careful wording lost (counted by machine), nothing added or dropped (a second Codex call)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.object(sl, "DATA", Path(self.tmp.name) / "style")
        p.start()
        self.addCleanup(p.stop)
        self.units = pe.page_units(PAGE)
        self.para = next(x for x in self.units if x.text.startswith("お中元の時期は地域で"))
        self.good = "お中元を贈る時期には地域差があります。関東では七月上旬から中旬、関西では七月中旬から八月中旬を目安に考えることが多いです。"

    def edit(self, after, **kw):
        ans = {"diagnosis": [], "edits": [{"id": self.para.id, "after": after, "why": "整理"}], "deleted": [], "needs_check": [], "structure_suggestions": [], "unchanged_count": 0}
        return pe.edit_page("yorokobu", "x/index.html", PAGE, runner=fake(ans, **kw), today="2026-10-17")

    def test_a_clean_rewrite_is_taken_after_the_second_look(self):
        rep = self.edit(self.good)
        self.assertEqual(len(rep["accepted"]), 1)
        self.assertEqual(len(sl.load_rewrites("yorokobu")), 1)

    def test_hedges_are_counted_and_a_rewrite_with_fewer_is_refused_by_machine(self):
        self.assertEqual(pe.hedges("関東では七月上旬から中旬を目安に考えることが多いです。場合があります。"), 3)
        flat = "お中元を贈る時期には地域差があります。関東では七月上旬から中旬、関西では七月中旬から八月中旬です。"
        rep = self.edit(flat)
        self.assertEqual(rep["accepted"], [])
        self.assertIn("careful wording removed", rep["rejected"][0]["problems"][0])
        self.assertEqual(sl.load_rewrites("yorokobu"), [])

    def test_the_second_look_refuses_an_added_claim_a_lost_hedge_or_a_dropped_condition(self):
        for flag in ("added_claim", "hedge_removed", "condition_dropped"):
            rep = self.edit(self.good, claims={"お中元の時期は": {flag: True, "problem": "元に無い"}})
            self.assertEqual(rep["accepted"], [], flag)
            self.assertIn(flag.split("_")[0], rep["rejected"][0]["problems"][0].replace(" ", "_"))
            self.assertEqual(sl.load_rewrites("yorokobu"), [], flag)

    def test_when_the_second_look_is_down_no_paragraph_is_taken_but_a_heading_still_is(self):
        h = next(x for x in self.units if x.text == "地域の時期に合わせる")
        ans = {"diagnosis": [], "edits": [{"id": self.para.id, "after": self.good, "why": "x"}, {"id": h.id, "after": "地域別 お中元の時期", "why": "見出し"}], "deleted": [], "needs_check": [],
               "structure_suggestions": [], "unchanged_count": 0}
        rep = pe.edit_page("yorokobu", "x/index.html", PAGE, runner=fake(ans, claims_down=True), today="2026-10-17")
        self.assertEqual([a["to"] for a in rep["accepted"]], ["地域別 お中元の時期"])
        self.assertTrue(rep["claims_check_failed"])
        self.assertIn("not taken", rep["rejected"][0]["problems"][0])

    def test_headings_and_buttons_are_not_sent_to_the_second_look(self):
        h = next(x for x in self.units if x.text == "地域の時期に合わせる")
        ans = {"diagnosis": [], "edits": [{"id": h.id, "after": "地域別 お中元の時期", "why": "見出し"}], "deleted": [], "needs_check": [], "structure_suggestions": [], "unchanged_count": 0}
        run = fake(ans)
        pe.edit_page("yorokobu", "x/index.html", PAGE, runner=run, today="2026-10-17")
        self.assertFalse(any("added_claim" in p for p in run.prompts))


class RewriterWithManyLongLines(unittest.TestCase):
    def test_a_long_original_is_found_inside_a_longer_text_and_many_lines_stay_fast(self):
        entries = [{"from": f"これは{i}番目の長い原文で、書き直される予定の段落です。", "to": f"{i}番目の段落です。"} for i in range(800)]
        rw = sl.Rewriter(entries)
        t0 = time.time()
        page = "".join(f"<p>これは{i}番目の長い原文で、書き直される予定の段落です。</p><p>前置き。これは{i}番目の長い原文で、書き直される予定の段落です。後書き。</p>" for i in range(0, 800, 40))
        out = rw.page(page)
        self.assertLess(time.time() - t0, 2)
        self.assertIn("<p>40番目の段落です。</p>", out)
        self.assertIn("<p>前置き。40番目の段落です。後書き。</p>", out)
        self.assertNotIn("長い原文", out)


if __name__ == "__main__":
    unittest.main()
