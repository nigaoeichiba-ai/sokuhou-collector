"""sokuhou.sametype: the share of a site's indexable pages that are one text with other names in it (AdSense "有用性の低いコンテンツ" on saichin, 2026-10-19:
the 47 prefecture pages overlapped 0.97).  The warning is shadow - it is printed and never fails the check."""
import tempfile
import unittest
from pathlib import Path

from sokuhou import sametype, sitecheck
from sokuhou.prefectures import SHORT

TEMPLATE = ("{p}県の令和8年度の最低賃金は{v}円で、全国加重平均より{d}円低い額です。前の年度から{u}円上がり、発効日は10月1日です。"
            "時給で働く人は、自分の給与明細の時給がこの額を下回っていないかを確かめてください。下回っているときは、労働基準監督署に相談できます。"
            "最低賃金には、通勤手当や残業代は含まれません。")


def page(title, prose_paragraphs, noindex=False):
    robots = '<meta name="robots" content="noindex,follow">' if noindex else ""
    ps = "".join(f"<p>{t}</p>" for t in prose_paragraphs)
    return (f'<!doctype html><html><head><title>{title}</title>{robots}</head><body><header><nav>メニュー</nav></header>'
            f'<main><h1>{title}</h1>{ps}<table><tr><td>表の数字 1,000 円</td></tr></table></main><footer>フッター</footer></body></html>')


def site(files):
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    for rel, text in files.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    return tmp, root


def same_text_site(n=12, extra_unique=2):
    files = {}
    for i, p in enumerate(SHORT[:n]):
        files[f"{p}/index.html"] = page(f"{p}県の最低賃金の推移", [TEMPLATE.format(p=p, v=1000 + i * 7, d=i + 3, u=50 + i)])
    own = [("運営の方針", "運営の方針は、公表された資料だけを使うことです。更新の頻度や訂正の受け付けは、問い合わせの窓口で行っています。"),
           ("出典と取得日", "出典の公表日と取得日は、各ページの末尾に載せています。古くなった数字は見つけしだい差し替え、履歴のページに残します。")]
    for k, (t, text) in enumerate(own[:extra_unique]):
        files[f"about{k}/index.html"] = page(t, [text])
    return files


class MeasureTest(unittest.TestCase):
    def measure(self, files):
        tmp, root = site(files)
        self.addCleanup(tmp.cleanup)
        return sametype.measure(root)

    def test_prefecture_pages_of_one_text_are_detected_like_saichin_with_0_97(self):
        r = self.measure(same_text_site())
        self.assertEqual(r["indexable"], 14)
        self.assertEqual(r["same"], 12)
        self.assertGreater(r["share"], 0.8)
        self.assertTrue(sametype.warning(r).startswith("WARNING [same-type]"))

    def test_pages_written_with_their_own_sentences_are_not_detected(self):
        files = {}
        facts = ["労働局の発表では、県内の事業所の多くが10月の改定に合わせて給与の計算を見直したと伝えられています。",
                 "この地域では、観光の繁忙期に短時間で働く人が多く、シフトの組み方によって時給の比べ方が変わります。",
                 "農業の収穫期だけ雇われる人は、日給で払われることが多く、時間あたりに直して確かめる必要があります。",
                 "製造業の工場が集まるため、夜勤の割増賃金と最低賃金の関係を相談する人が目立ちます。",
                 "島しょ部では、船の便に合わせた働き方があり、拘束される時間と賃金の対象になる時間が食い違うことがあります。",
                 "大学が多い町なので、学生の掛け持ちのアルバイトで、月の合計が扶養の範囲を超えないかを気にする声があります。"]
        for i, p in enumerate(SHORT[:6]):
            files[f"{p}/index.html"] = page(f"{p}県の最低賃金の推移", [TEMPLATE.format(p=p, v=1000 + i, d=i + 3, u=50 + i)[:60], facts[i], f"{p}の暮らしでは、{facts[(i + 3) % 6]}"])
        r = self.measure(files)
        self.assertLess(r["share"], 0.6, r)
        self.assertEqual(sametype.warning(r), "")

    def test_the_tables_the_navigation_and_noindex_pages_do_not_count(self):
        files = same_text_site()
        for p in SHORT[:12]:                                       # all twelve are noindex now: nothing is offered to a search engine
            files[f"{p}/index.html"] = page(f"{p}県の最低賃金の推移", [TEMPLATE.format(p=p, v=1, d=2, u=3)], noindex=True)
        r = self.measure(files)
        self.assertEqual(r["indexable"], 2)                          # the two unrelated pages only
        self.assertFalse([g for g in r["groups"] if g[0].startswith("title:") and g[1] > 1])

    def test_names_and_numbers_are_masked_but_other_words_are_not(self):
        self.assertEqual(sametype.mask("愛知県は1,195円"), sametype.mask("兵庫県は1,172円"))
        self.assertNotEqual(sametype.mask("愛知県は安い"), sametype.mask("愛知県は高い"))


class ShadowTest(unittest.TestCase):
    def test_the_check_prints_the_warning_and_never_counts_it_as_a_problem(self):
        files = same_text_site()
        files["index.html"] = page("トップ", ["これは最初のページです。" * 5]).replace("<main>", '<main><a href="/aichi/">愛知県</a>')
        tmp, root = site(files)
        self.addCleanup(tmp.cleanup)
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sitecheck.main([str(root), "--base", "https://example.test"])
        out = buf.getvalue()
        self.assertIn("WARNING [same-type]", out)
        self.assertNotIn("same-type", " ".join(sitecheck.check_dir(root, "https://example.test")))      # it is printed beside the problems, not among them


if __name__ == "__main__":
    unittest.main()
