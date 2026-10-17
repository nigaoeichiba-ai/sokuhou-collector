"""商品カードの短い名前 (sites/yorokobu/shortname.py): ブランドと品名、数語。販売店の検索語・販促語は出さない。「…」で切らない。元の題の言葉だけを使う。"""
import html
import json
import statistics
import unittest
from pathlib import Path

from sites.yorokobu import build, shortname

ROOT = Path(__file__).resolve().parents[1]

# (the shop's title, what the card shows).  Real titles, taken from the data of 2026-10-17.
CASES = [
    ("お菓子 おしゃれ 高級 プレゼント 凛菓 ティラミス 詰め合わせ 抹茶スイーツ 個包装", "凛菓 ティラミス 詰め合わせ"),
    ("マラソン期間中 エントリー&買いまわりでポイント最大11倍！ ROYCE’ ロイズ 生チョコレート ランキング受賞 ギフト", "ROYCE’ ロイズ 生チョコレート"),
    ("10月14日20時スタート！ウェッジウッド ワイルドストロベリー ティーバッグ3種入り 18個アソートセットプチギフト 紅茶", "ウェッジウッド ワイルドストロベリー ティーバッグ3種入り"),
    ("ロクシタン ハンドクリーム ギフト 女性 誕生日プレゼント 人気 プチギフト パリスガールボックス ミニ 10ml 北欧風", "ロクシタン ハンドクリーム 10ml"),
    ("(ギフト)イニシャルタオルハンカチ 1枚 今治タオル タオル (ポスト投函) プチギフトボックス入り", "イニシャルタオルハンカチ 1枚"),
    ("【50%OFF】 夫婦箸 ペアセット 結婚祝い めおと箸 お箸 ギフトボックス入り はし 漆塗り おしゃれ 大人 プレゼント ギフト", "夫婦箸 ペアセット めおと箸 お箸"),
    ("ポロ ラルフローレン メンズソックス", "ポロ ラルフローレン メンズソックス"),
    ("特価文具セット（男）{ 文具 新入学 文具 詰め合わせ お祝い セット ギフト", "文具 詰め合わせ セット"),
    ("P5倍 イヤホン ワイヤレスイヤホン 液晶イヤホン 新型モデル", "ワイヤレスイヤホン 液晶イヤホン"),
    ("ゴディバ公式（GODIVA）チョコレートケーキ 誕生日 送料込 ギフト 贈答 プレゼント", "ゴディバ公式（GODIVA）チョコレートケーキ"),
    ("DEAN &amp; DELUCA(ディーン&amp;デルーカ) ギフトカタログ CHARCOAL(チャコール)", "DEAN & DELUCA(ディーン&デルーカ) ギフトカタログ"),
]


class NameTest(unittest.TestCase):
    def test_real_titles_become_the_name_of_the_product(self):
        for title, want in CASES:
            got = shortname.short_name(build.strip_occasions(title))
            self.assertEqual(got, want, title)

    def test_the_shops_title_is_never_cut_with_an_ellipsis_and_is_never_empty(self):
        for title in ("A " * 80, "ギフト プレゼント 誕生日", "送料無料", "x"):
            out = shortname.short_name(title)
            self.assertTrue(out.strip(), title)
            self.assertNotIn("…", out)

    def test_every_word_shown_comes_from_the_title_and_nothing_is_added(self):
        for title, _ in CASES:
            plain = html.unescape(title)
            for w in shortname.short_name(build.strip_occasions(title)).split():
                self.assertIn(w.strip("（）()"), plain.replace("＆", "&"), (title, w))

    def test_the_dictionary_overrides_the_rules_for_one_item_code(self):
        shortname._DICT = {"shop:1": "凛菓 ティラミス"}
        try:
            self.assertEqual(shortname.short_name("お菓子 おしゃれ 高級 プレゼント 凛菓 ティラミス", code="shop:1"), "凛菓 ティラミス")
            self.assertNotEqual(shortname.short_name("お菓子 おしゃれ 高級 プレゼント 凛菓 ティラミス", code="shop:2"), "")
        finally:
            shortname._DICT = None

    def test_build_short_is_for_the_sites_own_names_only_a_shops_product_gets_blurb_py(self):
        self.assertEqual(build.short("お菓子 おしゃれ 高級 プレゼント 凛菓 ティラミス 詰め合わせ"), "凛菓 ティラミス 詰め合わせ")

    def test_a_size_or_a_count_of_the_title_is_kept_after_the_product(self):
        self.assertEqual(shortname.short_name("ポーチ シンプル 軽量 レディース 化粧品 コスメ 整理 収納 容量 3L"), "ポーチ レディース 化粧品 コスメ 3L")

    @unittest.skipUnless((ROOT / "data" / "yorokobu_compare.json").exists(), "the Rakuten data is in the private store (privatedata.py), not in the repository")
    def test_over_the_real_data_the_names_are_short_and_use_no_search_words(self):
        data = json.loads((ROOT / "data" / "yorokobu_compare.json").read_text(encoding="utf-8"))
        names = [i["name"] for g in data["groups"].values() for i in g]
        self.assertGreater(len(names), 500)
        shorts = [shortname.short_name(build.strip_occasions(n)) for n in names]
        lens = [len(s) for s in shorts]
        self.assertLessEqual(statistics.median(lens), 26)
        self.assertLess(sum(l > 40 for l in lens) / len(lens), 0.03)
        self.assertTrue(all(s.strip() and "…" not in s for s in shorts))
        for s in shorts:
            for w in s.split():
                self.assertNotIn(w, ("ギフト", "プレゼント", "送料無料", "誕生日", "おしゃれ", "人気"), s)


if __name__ == "__main__":
    unittest.main()
