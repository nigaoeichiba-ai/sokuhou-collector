"""D26: the check of "no source on the screen" finds what the old pages showed (negative tests), and passes the new notice."""
import unittest

from tests import yorokobu_d26 as d26  # noqa: E402
from sites.yorokobu import seasonal  # noqa: E402


class D26Test(unittest.TestCase):
    def test_finds_the_old_forms(self):
        old_list = '<h2>出典(確認日 2026年10月15日)</h2><ul><li><a href="https://www.mistore.jp/a" rel="noopener nofollow">三越伊勢丹 A</a></li></ul>'
        self.assertIn("word 出典", d26.problems(old_list))
        self.assertIn("link www.mistore.jp", d26.problems(old_list))
        self.assertIn("word 出典", d26.problems("<p>出典: 株式会社アイディエーション「調査」</p>"))
        self.assertIn("word 参考にした", d26.problems('<p class="quick-src">参考にした出典: 高島屋</p>'))
        self.assertIn("link prtimes.jp", d26.problems('<figcaption><a href="https://prtimes.jp/x">調査</a></figcaption>'))

    def test_finds_an_advertising_link_without_target_and_rel(self):
        bare = '<a href="//ck.jp.ap.valuecommerce.com/servlet/referral?sid=1&pid=2" rel="nofollow">Yahoo!</a>'
        self.assertEqual(d26.problems(bare), ["affiliate link without target/rel ck.jp.ap.valuecommerce.com"])
        self.assertEqual(d26.problems(bare.replace('rel="nofollow"', 'target="_blank" rel="nofollow sponsored noopener"')), [])

    def test_passes_what_may_be_shown(self):
        ok = ('<p class="seas-checked">確認日 2026年10月15日</p><a href="https://hb.afl.rakuten.co.jp/hgc/x" target="_blank" rel="nofollow sponsored noopener">楽天で探す</a>'
              '<a href="https://developers.rakuten.com/">Supported by Rakuten Developers</a><a href="https://line.me/R/share?text=a">LINEで送る</a>')
        self.assertEqual(d26.problems(ok), [])

    def test_the_foot_block_shows_the_date_and_no_source(self):
        srcs = {"a": {"name": "三越伊勢丹 A", "short": "三越伊勢丹", "url": "https://www.mistore.jp/a", "date": ""}}
        html = seasonal.sources_block(seasonal.source_items(["a"], srcs), "2026-10-15", "早見表", own_view=False)
        self.assertIn("確認日 2026年10月15日", html)
        self.assertEqual(d26.problems(html), [])
        self.assertNotIn("<a ", html)


if __name__ == "__main__":
    unittest.main()
